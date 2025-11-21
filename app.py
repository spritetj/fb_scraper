"""
Facebook Comment Scraper - Web Interface
Simple, user-friendly web app for non-technical users
"""

from flask import Flask, render_template, request, jsonify, send_file, Response
from werkzeug.utils import secure_filename
import json
import os
import threading
import queue
import time
import traceback
from datetime import datetime
from pathlib import Path
import asyncio
from scraper import FacebookCommentScraper

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Global state
scraper_thread = None
scraper_running = False
log_queue = queue.Queue()
current_scraper = None

def log(message):
    """Add message to log queue"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}] {message}"
    log_queue.put(log_message)
    print(log_message)

def run_scraper(urls, cookies, settings):
    """Run scraper in background thread"""
    global scraper_running, current_scraper

    try:
        scraper_running = True
        log("🚀 Starting scraper...")

        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Initialize scraper
        current_scraper = FacebookCommentScraper(
            viewport_size=settings.get('viewport', '13_inch'),
            log_callback=log
        )

        # Run scraper
        result = loop.run_until_complete(
            current_scraper.scrape_urls(urls, cookies)
        )

        if result['success']:
            log(f"✅ Scraping complete! Extracted {result['total_comments']} comments")
            log(f"📁 Saved to: {result['output_file']}")
        else:
            log(f"❌ Scraping failed: {result['error']}")

    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        log(f"❌ Error: {error_msg}")
    finally:
        scraper_running = False
        current_scraper = None
        log("🏁 Scraper stopped")

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/scrape', methods=['POST'])
def start_scrape():
    """Start scraping"""
    global scraper_thread, scraper_running

    if scraper_running:
        return jsonify({'error': 'Scraper already running'}), 400

    data = request.json

    # Validate input
    if not data.get('urls'):
        return jsonify({'error': 'No URLs provided'}), 400

    if not data.get('cookies'):
        return jsonify({'error': 'No cookies provided'}), 400

    # Parse URLs
    urls = [url.strip() for url in data['urls'].split('\n') if url.strip() and not url.startswith('#')]

    if not urls:
        return jsonify({'error': 'No valid URLs found'}), 400

    # Parse cookies
    try:
        if isinstance(data['cookies'], str):
            cookies = json.loads(data['cookies'])
        else:
            cookies = data['cookies']
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid cookie JSON format'}), 400

    # Get settings
    settings = data.get('settings', {})

    # Clear log queue
    while not log_queue.empty():
        log_queue.get()

    # Start scraper thread
    scraper_thread = threading.Thread(
        target=run_scraper,
        args=(urls, cookies, settings),
        daemon=True
    )
    scraper_thread.start()

    return jsonify({'success': True, 'message': 'Scraping started'})

@app.route('/api/stop', methods=['POST'])
def stop_scrape():
    """Stop scraping"""
    global scraper_running, current_scraper

    if not scraper_running:
        return jsonify({'error': 'Scraper not running'}), 400

    log("⏹️ Stop requested by user...")
    scraper_running = False

    # Try to stop gracefully
    if current_scraper:
        current_scraper.stop()

    return jsonify({'success': True, 'message': 'Stopping scraper...'})

@app.route('/api/status')
def get_status():
    """Get scraper status"""
    return jsonify({
        'running': scraper_running,
        'thread_alive': scraper_thread.is_alive() if scraper_thread else False
    })

@app.route('/api/logs')
def stream_logs():
    """Stream logs using Server-Sent Events"""
    def generate():
        while True:
            try:
                # Get log message with timeout
                message = log_queue.get(timeout=1)
                yield f"data: {message}\n\n"
            except queue.Empty:
                # Send heartbeat to keep connection alive
                yield f": heartbeat\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/upload-cookies', methods=['POST'])
def upload_cookies():
    """Upload cookies file"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file:
        try:
            # Read and validate JSON
            cookies = json.load(file)
            return jsonify({'success': True, 'cookies': cookies})
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid JSON file'}), 400

@app.route('/api/outputs')
def list_outputs():
    """List available output files"""
    output_dir = Path(app.config['OUTPUT_FOLDER'])
    files = []

    if output_dir.exists():
        for file in sorted(output_dir.glob('*.csv'), key=lambda x: x.stat().st_mtime, reverse=True):
            files.append({
                'name': file.name,
                'size': file.stat().st_size,
                'modified': datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            })

    return jsonify(files)

@app.route('/api/download/<filename>')
def download_file(filename):
    """Download output file"""
    file_path = Path(app.config['OUTPUT_FOLDER']) / secure_filename(filename)

    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404

    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    # Ensure directories exist
    Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)
    Path(app.config['OUTPUT_FOLDER']).mkdir(exist_ok=True)
    Path('logs').mkdir(exist_ok=True)

    # Auto-install Playwright browsers if needed
    try:
        import setup_playwright
        setup_playwright.install_playwright()
    except Exception as e:
        print(f"Warning: Could not run auto-setup: {e}")

    # Try ports 5001-5010 to avoid conflicts (macOS AirPlay uses 5000)
    import socket

    def find_available_port(start_port=5001, max_port=5010):
        """Find an available port"""
        for port in range(start_port, max_port + 1):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        return None

    port = find_available_port()

    if port is None:
        print("=" * 80)
        print("❌ ERROR: No available ports found (5001-5010)")
        print("=" * 80)
        print("")
        print("Please close other applications using these ports.")
        print("")
        exit(1)

    print("=" * 80)
    print("🚀 Facebook Comment Scraper - Web Interface")
    print("=" * 80)
    print("")
    print(f"📍 Open in browser: http://localhost:{port}")
    print("")
    print("Press Ctrl+C to stop the server")
    print("=" * 80)
    print("")

    app.run(debug=True, host='0.0.0.0', port=port, threaded=True)
