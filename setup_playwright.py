import subprocess
import sys
import os

def install_playwright():
    print("Checking Playwright installation...")
    try:
        # Check if we can import playwright
        import playwright
    except ImportError:
        print("Installing playwright package...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])

    print("Installing Playwright browsers...")
    try:
        # Run playwright install chromium
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        # Run playwright install-deps (linux only, but safe to run)
        if sys.platform.startswith('linux'):
             subprocess.call([sys.executable, "-m", "playwright", "install-deps", "chromium"])
        print("Playwright installation complete.")
    except Exception as e:
        print(f"Error installing Playwright browsers: {e}")
        sys.exit(1)

if __name__ == "__main__":
    install_playwright()
