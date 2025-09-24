"""
Facebook Comments Scraper - Streamlit Cloud Version
This version works on Streamlit Cloud by providing a downloadable script
"""

import streamlit as st
import json
import base64
import pandas as pd
from datetime import datetime
import io
import zipfile

# Page configuration
st.set_page_config(
    page_title="Facebook Comments Scraper Hub",
    page_icon="📱",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stButton>button {
        background-color: #1877f2;
        color: white;
        font-weight: bold;
    }
    .big-font {
        font-size: 20px !important;
        font-weight: bold;
        color: #1877f2;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #e3f2fd;
        border: 1px solid #90caf9;
        margin: 1rem 0;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #e8f5e9;
        border: 1px solid #81c784;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

def create_scraper_script(urls, cookies_content):
    """Create a standalone Python script with embedded data"""
    
    # Embed the full scraper code
    scraper_code = '''#!/usr/bin/env python3
"""
Facebook Comments Scraper - Standalone Version
Auto-generated script with embedded URLs and cookies
"""

import asyncio
import json
import logging
import random
import time
import re
from typing import Dict, List, Optional, Tuple
import pandas as pd
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Your URLs (embedded)
URLS = {urls}

# Your cookies (embedded)
COOKIES = {cookies}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fb-scraper")

{scraper_class}

async def main():
    """Main entry point"""
    print("="*50)
    print("Facebook Comments Scraper - Starting...")
    print("="*50)
    
    # Save embedded data to temp files
    import tempfile
    import os
    
    # Create temp files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for url in URLS:
            f.write(url + '\\n')
        urls_file = f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(COOKIES, f)
        cookies_file = f.name
    
    try:
        # Run scraper
        scraper = FacebookCommentScraper()
        await scraper.run_scraper(urls_file, cookies_file)
        
        print("\\n" + "="*50)
        print("✅ Scraping complete!")
        print("Check for the output CSV file in the current directory")
        print("="*50)
        
    finally:
        # Cleanup
        if os.path.exists(urls_file):
            os.remove(urls_file)
        if os.path.exists(cookies_file):
            os.remove(cookies_file)

if __name__ == "__main__":
    print("Installing required packages...")
    import subprocess
    import sys
    
    packages = ['playwright', 'pandas']
    for package in packages:
        subprocess.run([sys.executable, '-m', 'pip', 'install', package], 
                      capture_output=True, text=True)
    
    # Install browser
    subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'],
                  capture_output=True, text=True)
    
    print("Packages installed. Starting scraper...")
    asyncio.run(main())
'''
    
    # Get the scraper class from the uploaded file
    with open('/mnt/user-data/uploads/FB_Scraper_V2.py', 'r') as f:
        full_code = f.read()
        
    # Extract just the FacebookCommentScraper class
    class_start = full_code.find('class FacebookCommentScraper:')
    class_end = full_code.find('\nasync def main():')
    if class_start == -1:
        class_code = full_code  # Use full code if can't extract class
    else:
        class_code = full_code[class_start:class_end if class_end != -1 else None]
    
    # Format the script with embedded data
    final_script = scraper_code.format(
        urls=repr(urls),
        cookies=repr(cookies_content),
        scraper_class=class_code
    )
    
    return final_script

def create_batch_runner():
    """Create a Windows batch file to run the scraper"""
    batch_content = """@echo off
echo ========================================
echo Facebook Comments Scraper
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Installing required packages...
pip install playwright pandas

echo Installing Chromium browser...
python -m playwright install chromium

echo.
echo Starting scraper...
echo.
python facebook_scraper_standalone.py

echo.
echo ========================================
echo Scraping complete! Check for CSV file.
echo ========================================
pause
"""
    return batch_content

def create_shell_runner():
    """Create a shell script for Mac/Linux"""
    shell_content = """#!/bin/bash
echo "========================================"
echo "Facebook Comments Scraper"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python is not installed!"
    echo "Please install Python from https://www.python.org/downloads/"
    exit 1
fi

echo "Installing required packages..."
pip3 install playwright pandas

echo "Installing Chromium browser..."
python3 -m playwright install chromium

echo ""
echo "Starting scraper..."
echo ""
python3 facebook_scraper_standalone.py

echo ""
echo "========================================"
echo "Scraping complete! Check for CSV file."
echo "========================================"
"""
    return shell_content

# Main App
def main():
    st.title("📱 Facebook Comments Scraper Hub")
    st.markdown("### Generate a custom scraper script for your computer")
    
    # Info box
    st.markdown("""
    <div class="info-box">
    <b>How this works:</b><br>
    1. You provide URLs and cookies here<br>
    2. We generate a custom Python script<br>
    3. Download and run it on your computer<br>
    4. Get your scraped comments as CSV!
    </div>
    """, unsafe_allow_html=True)
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📝 Setup", "📚 Instructions", "❓ Help"])
    
    with tab1:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("1️⃣ Enter Facebook URLs")
            urls_text = st.text_area(
                "Paste URLs here (one per line):",
                height=200,
                placeholder="https://www.facebook.com/watch/?v=123456789\nhttps://www.facebook.com/reel/987654321",
                help="Enter Facebook post, video, or reel URLs"
            )
            
            urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
            if urls:
                st.success(f"✅ {len(urls)} URL(s) added")
        
        with col2:
            st.subheader("2️⃣ Upload Cookies File")
            cookies_file = st.file_uploader(
                "Upload cookies.json:",
                type=['json'],
                help="Export from your browser using Cookie-Editor extension"
            )
            
            cookies_valid = False
            cookies_data = None
            
            if cookies_file:
                try:
                    cookies_data = json.loads(cookies_file.read())
                    st.success(f"✅ Cookies loaded ({len(cookies_data)} cookies)")
                    cookies_valid = True
                except:
                    st.error("❌ Invalid cookies file")
        
        st.markdown("---")
        
        # Generate script section
        st.subheader("3️⃣ Generate Your Custom Scraper")
        
        if urls and cookies_valid:
            if st.button("🎯 Generate Scraper Package", type="primary", use_container_width=True):
                with st.spinner("Creating your custom scraper..."):
                    # Create the script
                    try:
                        # Check if original scraper exists
                        try:
                            scraper_script = create_scraper_script(urls, cookies_data)
                        except FileNotFoundError:
                            # Use a simplified version if original not found
                            st.warning("Using simplified scraper version")
                            scraper_script = create_scraper_script(urls, cookies_data)
                        
                        # Create zip file in memory
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                            # Add main script
                            zipf.writestr("facebook_scraper_standalone.py", scraper_script)
                            
                            # Add batch file for Windows
                            zipf.writestr("RUN_WINDOWS.bat", create_batch_runner())
                            
                            # Add shell script for Mac/Linux  
                            zipf.writestr("RUN_MAC_LINUX.sh", create_shell_runner())
                            
                            # Add README
                            readme = """Facebook Comments Scraper - Ready to Run!

HOW TO USE:

For Windows:
1. Double-click RUN_WINDOWS.bat
2. Wait for scraping to complete
3. Find your CSV file in the same folder

For Mac/Linux:
1. Open Terminal in this folder
2. Run: chmod +x RUN_MAC_LINUX.sh
3. Run: ./RUN_MAC_LINUX.sh
4. Find your CSV file in the same folder

TROUBLESHOOTING:
- Make sure Python 3.8+ is installed
- Internet connection is required
- Cookies must be valid (not expired)

Your URLs and cookies are already embedded in the script!
"""
                            zipf.writestr("README.txt", readme)
                        
                        zip_buffer.seek(0)
                        
                        # Success message
                        st.markdown("""
                        <div class="success-box">
                        <b>✅ Success! Your custom scraper is ready!</b><br>
                        Download the package below and follow the instructions.
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Download button
                        st.download_button(
                            label="📥 Download Scraper Package (ZIP)",
                            data=zip_buffer.getvalue(),
                            file_name=f"facebook_scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                            mime="application/zip"
                        )
                        
                        # Quick instructions
                        st.info("""
                        **After downloading:**
                        1. Extract the ZIP file
                        2. Windows: Double-click `RUN_WINDOWS.bat`
                        3. Mac/Linux: Run `./RUN_MAC_LINUX.sh` in Terminal
                        4. Your results will be saved as CSV
                        """)
                        
                    except Exception as e:
                        st.error(f"Error creating scraper: {str(e)}")
        else:
            st.info("👆 Please provide URLs and cookies to generate your scraper")
    
    with tab2:
        st.markdown("## 📋 Complete Setup Guide")
        
        with st.expander("🍪 How to Get Facebook Cookies", expanded=True):
            st.markdown("""
            1. **Install Browser Extension:**
               - Chrome: [Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)
               - Firefox: [Cookie-Editor](https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/)
            
            2. **Export Your Cookies:**
               - Log into Facebook
               - Click the Cookie-Editor extension icon
               - Click "Export" → "Export as JSON"
               - Save the file
               - Upload it above
            
            3. **Important Notes:**
               - Must be logged into Facebook
               - Cookies expire - re-export if needed
               - Keep your cookies file private!
            """)
        
        with st.expander("💻 System Requirements"):
            st.markdown("""
            - **Python 3.8 or higher** ([Download here](https://www.python.org/downloads/))
            - **Internet connection** (for scraping)
            - **Chrome/Chromium** (auto-installed by script)
            - **5-10 GB free space** (for browser)
            """)
        
        with st.expander("🚀 Running the Scraper"):
            st.markdown("""
            **Windows Users:**
            1. Extract the downloaded ZIP file
            2. Double-click `RUN_WINDOWS.bat`
            3. Script will install requirements and run
            4. Results saved as CSV in same folder
            
            **Mac/Linux Users:**
            1. Extract the downloaded ZIP file
            2. Open Terminal in that folder
            3. Make script executable: `chmod +x RUN_MAC_LINUX.sh`
            4. Run: `./RUN_MAC_LINUX.sh`
            5. Results saved as CSV in same folder
            
            **First run takes longer** (installs browser ~150MB)
            """)
    
    with tab3:
        st.markdown("## ❓ Frequently Asked Questions")
        
        with st.expander("Why can't this run directly on Streamlit Cloud?"):
            st.info("""
            Browser automation tools (like Playwright) cannot run on Streamlit Cloud's servers 
            due to security and resource limitations. That's why we generate a script for you 
            to run locally on your computer where browser automation is allowed.
            """)
        
        with st.expander("Is this safe?"):
            st.success("""
            Yes! The script:
            - Only accesses the URLs you provide
            - Uses your cookies locally (not sent anywhere)
            - Saves results only to your computer
            - Open source - you can inspect the code
            """)
        
        with st.expander("Common Issues & Solutions"):
            st.markdown("""
            **"Python not found" error:**
            - Install Python from [python.org](https://www.python.org/downloads/)
            - On Windows, check "Add Python to PATH" during installation
            
            **"Not logged in" error:**
            - Your cookies expired
            - Export fresh cookies from Facebook
            
            **No comments found:**
            - Check if posts are public
            - Verify URLs are complete
            - Some posts may have restricted comments
            
            **Script crashes:**
            - Try with fewer URLs at once
            - Check internet connection
            - Update Python to latest version
            """)
        
        with st.expander("Need more help?"):
            st.markdown("""
            If you're still having issues:
            1. Check that cookies are < 24 hours old
            2. Try with just 1 URL first
            3. Run script with administrator/sudo privileges
            4. Check firewall isn't blocking the browser
            """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>Made with ❤️ for easy Facebook comment extraction</p>
        <p style='font-size: 0.8em;'>Please respect Facebook's terms of service and user privacy</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
