// State
let eventSource = null;
let cookies = null;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    // Cookie file upload
    document.getElementById('cookieFile').addEventListener('change', handleCookieFile);

    // Cookie text input
    document.getElementById('cookieText').addEventListener('input', handleCookieText);

    // URL text input
    document.getElementById('urlText').addEventListener('input', updateUrlCount);

    // Refresh files on load
    refreshFiles();

    // Check status periodically
    setInterval(checkStatus, 2000);
});

// Handle cookie file upload
async function handleCookieFile(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload-cookies', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            cookies = data.cookies;
            document.getElementById('cookieFileName').textContent = `✓ ${file.name}`;
            document.getElementById('cookieStatus').textContent = `✓ ${cookies.length} cookies loaded`;
            document.getElementById('cookieStatus').className = 'status success';
            document.getElementById('cookieText').value = JSON.stringify(cookies, null, 2);
        } else {
            showError('cookieStatus', data.error);
        }
    } catch (error) {
        showError('cookieStatus', 'Failed to upload file');
    }
}

// Handle cookie text input
function handleCookieText() {
    const text = document.getElementById('cookieText').value.trim();

    if (!text) {
        cookies = null;
        document.getElementById('cookieStatus').textContent = '';
        return;
    }

    try {
        cookies = JSON.parse(text);
        document.getElementById('cookieStatus').textContent = `✓ ${cookies.length} cookies loaded`;
        document.getElementById('cookieStatus').className = 'status success';
    } catch (error) {
        showError('cookieStatus', 'Invalid JSON format');
        cookies = null;
    }
}

// Update URL count
function updateUrlCount() {
    const text = document.getElementById('urlText').value;
    const urls = text.split('\n').filter(line => line.trim() && !line.startsWith('#'));
    document.getElementById('urlCount').textContent = `${urls.length} URLs`;
}

// Start scraping
async function startScraping() {
    // Validate inputs
    if (!cookies) {
        alert('Please provide cookies first');
        return;
    }

    const urlText = document.getElementById('urlText').value.trim();
    if (!urlText) {
        alert('Please provide at least one URL');
        return;
    }

    // Get settings
    const viewport = document.getElementById('viewport').value;

    // Disable start button, enable stop button
    document.getElementById('startBtn').disabled = true;
    document.getElementById('stopBtn').disabled = false;

    // Update status
    updateStatus('running', 'Scraping...');

    // Clear log
    document.getElementById('logOutput').innerHTML = '';

    // Start log stream
    startLogStream();

    // Start scraping
    try {
        const response = await fetch('/api/scrape', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                urls: urlText,
                cookies: cookies,
                settings: {
                    viewport: viewport
                }
            })
        });

        const data = await response.json();

        if (!data.success) {
            alert('Error: ' + data.error);
            updateStatus('error', 'Error');
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
        }
    } catch (error) {
        alert('Failed to start scraping: ' + error.message);
        updateStatus('error', 'Error');
        document.getElementById('startBtn').disabled = false;
        document.getElementById('stopBtn').disabled = true;
    }
}

// Stop scraping
async function stopScraping() {
    try {
        const response = await fetch('/api/stop', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            addLog('⏹️ Stop requested...');
        }
    } catch (error) {
        alert('Failed to stop scraping');
    }
}

// Start log stream
function startLogStream() {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource('/api/logs');

    eventSource.onmessage = function(event) {
        if (event.data && !event.data.startsWith(':')) {
            addLog(event.data);
        }
    };

    eventSource.onerror = function(error) {
        console.error('EventSource error:', error);
        eventSource.close();
        eventSource = null;
    };
}

// Add log message
function addLog(message) {
    const logOutput = document.getElementById('logOutput');
    const div = document.createElement('div');
    div.textContent = message;
    logOutput.appendChild(div);
    logOutput.scrollTop = logOutput.scrollHeight;
}

// Clear log
function clearLog() {
    document.getElementById('logOutput').innerHTML = '';
}

// Check status
async function checkStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        if (!data.running && document.getElementById('stopBtn').disabled === false) {
            // Scraper just finished
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
            updateStatus('idle', 'Ready');

            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }

            // Refresh files
            refreshFiles();
        }
    } catch (error) {
        console.error('Status check failed:', error);
    }
}

// Update status bar
function updateStatus(state, text) {
    const statusBar = document.getElementById('statusBar');
    const statusText = document.getElementById('statusText');

    statusBar.className = `status-bar status-${state}`;
    statusText.textContent = text;
}

// Refresh output files
async function refreshFiles() {
    try {
        const response = await fetch('/api/outputs');
        const files = await response.json();

        const fileList = document.getElementById('fileList');

        if (files.length === 0) {
            fileList.innerHTML = '<p style="color: #65676b;">No output files yet</p>';
            return;
        }

        fileList.innerHTML = files.map(file => `
            <div class="file-item">
                <div class="file-info">
                    <div class="file-name-text">📄 ${file.name}</div>
                    <div class="file-meta">${formatFileSize(file.size)} • ${file.modified}</div>
                </div>
                <a href="/api/download/${file.name}" class="file-download" download>
                    ⬇️ Download
                </a>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to refresh files:', error);
    }
}

// Format file size
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// Show error
function showError(elementId, message) {
    const element = document.getElementById(elementId);
    element.textContent = '✗ ' + message;
    element.className = 'status error';
}
