# Python Version Compatibility Guide

## ✅ Supported Python Versions

| Python Version | Status | Notes |
|----------------|--------|-------|
| **3.12.x** | ✅ **Recommended** | Best compatibility, fully tested |
| **3.11.x** | ✅ Supported | Fully compatible |
| **3.10.x** | ✅ Supported | Fully compatible |
| **3.9.x** | ✅ Supported | Compatible |
| **3.8.x** | ✅ Supported | Minimum version |
| **3.13.x+** | ⚠️ **Not Recommended** | Too new, may have issues |
| **3.7.x or older** | ❌ **Not Supported** | Too old |

---

## Why Python 3.13+ May Not Work

Python 3.13 was released recently (October 2024) and:
- Flask, Playwright, and other packages may not be fully tested
- Some dependencies might break with new Python features
- The async event loop behavior changed slightly

**Recommendation:** Use Python 3.12 for best stability.

---

## Why Python 3.7 or Older Won't Work

- Flask 3.0+ requires Python 3.8+
- Playwright requires Python 3.8+
- Missing modern async/await features
- Security updates discontinued

---

## How to Check Your Python Version

### macOS/Linux:
```bash
python3 --version
```

### Windows:
```cmd
python --version
```

---

## How to Install Python 3.12

### Option 1: Official Python.org (Recommended)

1. Go to: https://www.python.org/downloads/
2. Download: **Python 3.12.x** (latest 3.12 version)
3. Run the installer
4. ✅ Check "Add Python to PATH" (Windows)
5. Complete installation

### Option 2: Homebrew (macOS)

```bash
brew install python@3.12
```

### Option 3: pyenv (Advanced Users)

```bash
# Install pyenv
curl https://pyenv.run | bash

# Install Python 3.12
pyenv install 3.12.0
pyenv global 3.12.0
```

---

## What Happens During Installation

The `INSTALL.command` script will:

1. **Search for compatible Python:**
   - Checks: python3.12, python3.11, python3.10, python3.9, python3.8
   - Falls back to: python3 (if compatible)

2. **Detect version:**
   - Extracts major.minor version (e.g., 3.12)
   - Checks if in supported range (3.8 - 3.12)

3. **Warn if incompatible:**
   - ⚠️ Python 3.13+: Shows warning, asks to continue
   - ❌ Python 3.7 or older: Stops installation

4. **Proceed with installation:**
   - Installs Flask, Playwright, Werkzeug
   - Downloads Chromium browser for Playwright

---

## If You Have Multiple Python Versions

If you have both Python 3.12 and 3.13 installed:

### macOS/Linux:
```bash
# Use specific version
python3.12 -m pip install -r requirements.txt
python3.12 app.py
```

### Update INSTALL.command:
The script **automatically prefers** Python 3.12 over 3.13!

**Search order:**
1. python3.12 ← **Preferred**
2. python3.11
3. python3.10
4. python3.9
5. python3.8
6. python3 (fallback)

---

## Testing Compatibility

### Quick Test:
```bash
cd FB_Scraper_WebApp
python3.12 -c "import flask, playwright; print('✅ All packages work!')"
```

**Expected output:**
```
✅ All packages work!
```

**If error:**
```
ModuleNotFoundError: No module named 'flask'
```
→ Run `INSTALL.command` first

---

## Troubleshooting

### "Python 3.13 detected" warning during install

**Option A: Continue with 3.13 (risky)**
- Press `y` when prompted
- May work, but could have unexpected issues

**Option B: Install Python 3.12 (recommended)**
1. Download from python.org
2. Run `INSTALL.command` again
3. Will automatically use 3.12

### "No compatible Python found"

**Solution:**
1. Install Python 3.12 from python.org
2. Verify: `python3.12 --version`
3. Run `INSTALL.command` again

### Packages fail to install

**Check Python version:**
```bash
python3 --version
```

**If 3.13+:**
- Some packages may not have wheels yet
- Install Python 3.12 alongside 3.13
- Use `python3.12` explicitly

---

## Summary

**Best Setup:**
- ✅ Python 3.12.x
- ✅ macOS, Linux, or Windows
- ✅ Fresh installation via python.org

**Avoid:**
- ❌ Python 3.13+ (too new)
- ❌ Python 3.7 or older (too old)
- ❌ System Python on macOS (may be outdated)

**Installation automatically:**
- ✅ Detects compatible Python
- ✅ Warns about incompatible versions
- ✅ Prefers stable versions (3.8-3.12)

---

## Need Help?

1. **Check version:** `python3 --version`
2. **Install 3.12:** https://www.python.org/downloads/
3. **Read README.md** for more troubleshooting
4. **Contact support** if issues persist

**Bottom line:** Use Python 3.12 for guaranteed compatibility! 🚀
