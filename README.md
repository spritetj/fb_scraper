# Facebook Comment Scraper Web App

A powerful, user-friendly web application to scrape comments from Facebook Posts, Reels, and Watch videos. Built with Python, Flask, and Playwright.

## 🚀 Features

*   **Web Interface**: Easy-to-use UI for managing scraping tasks.
*   **Multiple Content Types**: Supports Posts, Reels, and Watch videos.
*   **Smart Scraping**: 
    *   Handles "View more comments" and reply expansion automatically.
    *   Detects full-page posts vs. modal dialogs.
    *   "Smart Scroll" to efficiently load comments.
*   **Robustness**: 
    *   Uses Playwright for reliable browser automation.
    *   Handles English and Thai interface elements.
    *   Auto-retry and error logging.
*   **Export**: Downloads scraped data as CSV files.

## 🛠️ Prerequisites

*   **Python 3.8+** installed on your system.
*   **Google Chrome** browser installed.

##  How to Run (Easiest Way)

**No installation required!** You can run this app directly in the cloud using GitHub Codespaces.

1.  **Click this button**:
    
    [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/spritetj/fb_scraper)

2.  **Wait for setup**:
    *   GitHub will create a cloud computer for you.
    *   It will automatically install Python and Playwright (this takes about 2 minutes).

3.  **Start the App**:
    *   In the terminal at the bottom, type:
        ```bash
        python app.py
        ```
    *   A popup will appear saying "Open in Browser". Click it!

---

## 📦 Local Installation (Advanced)

If you prefer to run it on your own computer:

1.  **Clone the repository** (or download the ZIP):
    ```bash
    git clone https://github.com/spritetj/fb_scraper.git
    cd fb_scraper
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Install Playwright browsers**:
    ```bash
    playwright install chromium
    ```

## 🏃‍♂️ How to Run

1.  **Start the application**:
    ```bash
    python app.py
    ```

2.  **Open your browser**:
    *   Go to the URL shown in the terminal (usually `http://localhost:5001` or `http://localhost:5002`).

## 🍪 How to Use

1.  **Get Facebook Cookies**:
    *   Install a browser extension like "Get cookies.txt LOCALLY" or "EditThisCookie".
    *   Log in to Facebook.
    *   Export your cookies as JSON.
    *   Save the file as `cookies.json`.

2.  **Upload Cookies**:
    *   In the web app, click "Upload Cookies" and select your `cookies.json` file.

3.  **Start Scraping**:
    *   Paste the Facebook URL you want to scrape (Post, Reel, or Watch).
    *   Click "Start Scraping".

4.  **Download Results**:
    *   Once finished, click the "Download CSV" button to get your data.

## ⚠️ Important Notes

*   **Cookies**: You must provide valid Facebook cookies. If the scraper says "Could not find main dialog", your cookies might be expired or invalid.
*   **Rate Limiting**: Scraping too fast or too much may get your account temporarily blocked by Facebook. Use with caution.
*   **Headless Mode**: The scraper runs in a visible browser by default. You can modify `scraper.py` to run in headless mode if preferred.

## 📝 License

This project is for educational purposes only. Use responsibly.
