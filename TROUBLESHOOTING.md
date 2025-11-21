# Troubleshooting Guide: "Target page, context or browser has been closed" Error

This guide helps resolve browser crashes when running the Facebook scraper webapp.

---

## 🔍 **Error Description**

If you see this error:
```
❌ Error scraping POST: Target page, context or browser has been closed
```

The browser is **crashing during navigation**. This is an environment issue, not a code bug.

---

## ✅ **Solution 1: Reinstall Playwright Browsers** (MOST COMMON FIX)

The browser binaries may be outdated or corrupted.

```bash
# Navigate to webapp folder
cd FB_Scraper_WebApp

# Reinstall Playwright browsers
python3 -m playwright install chromium

# If that doesn't work, reinstall with dependencies
python3 -m playwright install --with-deps chromium
```

**Why this works:** Updates browser binaries to the latest stable version compatible with your Playwright installation.

---

## ✅ **Solution 2: Check System Resources**

### **On Linux:**
```bash
# Check available memory
free -h

# Check /dev/shm size (should be at least 64MB, preferably 1GB+)
df -h /dev/shm
```

If `/dev/shm` is too small:
```bash
# Increase /dev/shm size temporarily
sudo mount -o remount,size=1G /dev/shm

# Or permanently by editing /etc/fstab
```

### **On macOS:**
```bash
# Check available memory
vm_stat

# Check CPU usage
top -l 1 | grep "CPU usage"
```

### **On Windows:**
```powershell
# Check memory
systeminfo | findstr /C:"Available Physical Memory"
```

---

## ✅ **Solution 3: Update Playwright & Python**

```bash
# Update Playwright
pip install --upgrade playwright

# Reinstall browsers after upgrade
python3 -m playwright install chromium

# Check versions
python3 --version  # Should be 3.8-3.12 (NOT 3.13+)
python3 -m playwright --version
```

---

## ✅ **Solution 4: Run with Increased Resources** (Docker/Containers)

If running in Docker/container, add these to your `docker-compose.yml` or `docker run`:

```yaml
services:
  scraper:
    shm_size: '2gb'  # Increase shared memory
    mem_limit: 4g    # Increase memory limit
```

Or with `docker run`:
```bash
docker run --shm-size=2g --memory=4g ...
```

---

## ✅ **Solution 5: Verify Python Version Compatibility**

```bash
python3 --version
```

**Supported:** Python 3.8 - 3.12
**NOT Supported:** Python 3.13+ (has Playwright compatibility issues)

If you're on Python 3.13:
```bash
# Install Python 3.12
# On macOS:
brew install python@3.12

# On Ubuntu/Debian:
sudo apt install python3.12

# Use Python 3.12 for the scraper
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## ✅ **Solution 6: Test Browser Manually**

Run this simple test to verify Playwright works:

```python
import asyncio
from playwright.async_api import async_playwright

async def test_browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://example.com')
        print(f"Title: {await page.title()}")
        await browser.close()
        print("✅ Browser test passed!")

asyncio.run(test_browser())
```

Save as `test_browser.py` and run:
```bash
python3 test_browser.py
```

If this fails, the issue is with your Playwright installation, not the scraper code.

---

## ✅ **Solution 7: Check Permissions (Linux only)**

```bash
# Give execute permissions to browser binary
chmod +x ~/.cache/ms-playwright/chromium-*/chrome-linux/chrome

# Check if running as root (not recommended)
whoami
```

**Never run as root!** If you must, add `--no-sandbox` is already included in browser args.

---

## 📊 **Diagnostic Logs**

If none of the above work, collect these logs and share them:

```bash
# 1. Check Playwright installation
python3 -m playwright install chromium --dry-run

# 2. Check system info
uname -a  # Linux/Mac
systeminfo  # Windows

# 3. Check browser process limits
ulimit -a  # Linux/Mac

# 4. Run webapp and capture full logs
python3 app.py 2>&1 | tee scraper_debug.log
```

---

## 🆘 **Still Not Working?**

### **Quick Checklist:**
- [ ] Reinstalled Playwright browsers (`python3 -m playwright install chromium`)
- [ ] Python version 3.8-3.12 (NOT 3.13+)
- [ ] At least 2GB RAM available
- [ ] Not running as root
- [ ] `/dev/shm` at least 1GB (Linux)
- [ ] Updated to latest scraper.py file
- [ ] Tested with `test_browser.py` script above

### **What Changed in Latest Fix:**
The updated `scraper.py` includes:
- ✅ 15+ browser args for cross-platform stability
- ✅ `--disable-dev-shm-usage` for Linux/Docker
- ✅ Browser health check before scraping
- ✅ Stabilization delays after context/page creation
- ✅ Comprehensive error messages

---

## 🔄 **Comparison: What Works vs What Doesn't**

| Environment | Status | Fix |
|------------|--------|-----|
| macOS with Playwright 1.40+ | ✅ Works | Use updated scraper.py |
| Linux with small /dev/shm | ❌ Crashes | Increase /dev/shm or use `--disable-dev-shm-usage` |
| Docker with default config | ❌ Crashes | Add `shm_size: '2gb'` |
| Windows with Python 3.13 | ❌ Crashes | Downgrade to Python 3.12 |
| Ubuntu with old Playwright | ❌ Crashes | Update Playwright and reinstall browsers |

---

## 📝 **Report an Issue**

If you've tried everything and it still doesn't work, provide:
1. Your OS & version
2. Python version (`python3 --version`)
3. Playwright version (`python3 -m playwright --version`)
4. Output of `test_browser.py`
5. Full error logs from webapp
6. Output of `df -h /dev/shm` (Linux only)
