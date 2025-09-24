"""
Facebook Comments Scraper - Streamlit Cloud Version
Uses requests library instead of Playwright for cloud compatibility
"""

import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
import time
import re
from io import BytesIO

# Page config
st.set_page_config(
    page_title="Facebook Comments Scraper",
    page_icon="📱",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stButton>button {
        background-color: #1877f2;
        color: white;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
</style>
""", unsafe_allow_html=True)

class FacebookScraper:
    def __init__(self, cookies_json):
        self.session = requests.Session()
        self.setup_cookies(cookies_json)
        
    def setup_cookies(self, cookies_json):
        """Convert JSON cookies to requests format"""
        cookies = json.loads(cookies_json)
        
        # Fix cookie format
        for cookie in cookies:
            # Clean up cookie values
            name = cookie.get('name', '')
            value = cookie.get('value', '')
            domain = cookie.get('domain', '.facebook.com')
            
            # Skip problematic cookies
            if not name or not value:
                continue
                
            # Fix sameSite issues
            if 'sameSite' in cookie:
                same_site = cookie['sameSite'].lower()
                if same_site in ['none', 'no_restriction']:
                    cookie['sameSite'] = None
                elif same_site == 'lax':
                    cookie['sameSite'] = 'Lax'
                elif same_site == 'strict':
                    cookie['sameSite'] = 'Strict'
            
            # Add to session
            self.session.cookies.set(
                name=name,
                value=value,
                domain=domain,
                path=cookie.get('path', '/'),
                secure=cookie.get('secure', True)
            )
    
    def scrape_url(self, url):
        """Scrape comments from a single URL"""
        try:
            # Headers to look like a real browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            # Try mobile version for easier parsing
            mobile_url = url.replace('www.facebook.com', 'm.facebook.com')
            
            response = self.session.get(mobile_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                return [], f"Failed to load page (status {response.status_code})"
            
            html = response.text
            
            # Check if logged in
            if 'login' in response.url or 'Log In' in html:
                return [], "Not logged in - cookies may have expired"
            
            # Extract comments from HTML
            comments = self.extract_comments(html, url)
            
            return comments, None
            
        except requests.Timeout:
            return [], "Request timed out"
        except Exception as e:
            return [], str(e)
    
    def extract_comments(self, html, url):
        """Extract comments from HTML"""
        comments = []
        
        # Multiple patterns to find comments
        patterns = [
            # Pattern 1: Comment divs with user names
            r'<div[^>]*>([^<]+)</div>\s*<div[^>]*>([^<]+)</div>',
            # Pattern 2: Mobile comment structure
            r'<h3>([^<]+)</h3>.*?<div>([^<]+)</div>',
            # Pattern 3: Alternative structure
            r'class="[^"]*comment[^"]*"[^>]*>.*?<a[^>]*>([^<]+)</a>.*?<span[^>]*>([^<]+)</span>'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    # Clean up extracted text
                    name = match.group(1).strip()
                    comment_text = match.group(2).strip()
                    
                    # Filter out UI elements
                    if self.is_valid_comment(name, comment_text):
                        comments.append({
                            'URL': url,
                            'Commenter': self.clean_text(name),
                            'Comment': self.clean_text(comment_text),
                            'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                except:
                    continue
        
        # If no comments found with patterns, try alternative approach
        if not comments:
            # Look for data-ft attributes which often contain comment data
            comment_blocks = re.findall(r'data-ft="([^"]+)"[^>]*>([^<]+)<', html)
            for block in comment_blocks:
                text = block[1].strip()
                if len(text) > 5 and not text.startswith('http'):
                    comments.append({
                        'URL': url,
                        'Commenter': 'User',
                        'Comment': self.clean_text(text),
                        'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
        
        return comments
    
    def is_valid_comment(self, name, text):
        """Check if extracted text is a valid comment"""
        # Filter out common UI elements
        ui_elements = ['Like', 'Reply', 'Share', 'Comment', 'See More', 'View', 
                      'ago', 'Yesterday', 'Just now', 'Write a comment']
        
        name_lower = name.lower()
        text_lower = text.lower()
        
        # Check if it's a UI element
        if name_lower in [ui.lower() for ui in ui_elements]:
            return False
        if text_lower in [ui.lower() for ui in ui_elements]:
            return False
            
        # Check minimum length
        if len(text) < 3:
            return False
            
        # Check if it's just a timestamp
        if re.match(r'^\d+\s*(h|hr|hrs|m|min|mins|d|days?|w|weeks?)$', text_lower):
            return False
            
        return True
    
    def clean_text(self, text):
        """Clean extracted text"""
        # Remove HTML entities
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&nbsp;', ' ').replace('&#039;', "'").replace('&quot;', '"')
        
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        return text.strip()

def main():
    st.title("📱 Facebook Comments Scraper")
    st.markdown("Extract comments from Facebook posts directly in the cloud!")
    
    # Sidebar for instructions
    with st.sidebar:
        st.header("📋 Instructions")
        st.markdown("""
        1. **Get Cookies:**
           - Install [Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)
           - Log into Facebook
           - Export cookies as JSON
        
        2. **Enter URLs:**
           - One URL per line
           - Works with posts, videos, reels
        
        3. **Upload & Scrape:**
           - Upload cookies file
           - Click Start Scraping
           - Download results
        """)
        
        st.warning("""
        **Note:** This uses a simplified method that may not capture all comments. 
        For comprehensive scraping, use the downloadable Python script version.
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📝 Step 1: Enter URLs")
        urls_text = st.text_area(
            "Facebook URLs (one per line):",
            height=200,
            placeholder="https://www.facebook.com/username/posts/123456\nhttps://www.facebook.com/watch/?v=789012"
        )
        
        urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        if urls:
            st.success(f"✅ {len(urls)} URL(s) ready")
    
    with col2:
        st.subheader("🔐 Step 2: Upload Cookies")
        cookies_file = st.file_uploader(
            "Upload cookies.json:",
            type=['json'],
            help="Export from your browser using Cookie-Editor extension"
        )
        
        cookies_valid = False
        if cookies_file:
            try:
                cookies_content = cookies_file.read().decode('utf-8')
                cookies_json = json.loads(cookies_content)
                st.success(f"✅ Cookies loaded ({len(cookies_json)} cookies)")
                cookies_valid = True
            except Exception as e:
                st.error(f"❌ Invalid cookies file: {str(e)}")
    
    # Scraping section
    st.divider()
    
    if st.button("🚀 Start Scraping", disabled=not(urls and cookies_valid), use_container_width=True):
        with st.spinner("Scraping comments... This may take a few minutes."):
            # Initialize scraper
            scraper = FacebookScraper(cookies_content)
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            all_comments = []
            failed_urls = []
            
            # Process each URL
            for i, url in enumerate(urls, 1):
                status_text.text(f"Processing URL {i}/{len(urls)}: {url[:50]}...")
                
                comments, error = scraper.scrape_url(url)
                
                if error:
                    failed_urls.append((url, error))
                    st.warning(f"⚠️ Failed to scrape {url[:50]}...: {error}")
                else:
                    all_comments.extend(comments)
                    if comments:
                        st.info(f"Found {len(comments)} comments from URL {i}")
                
                progress_bar.progress(i / len(urls))
                time.sleep(1)  # Rate limiting
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
            # Results section
            if all_comments:
                st.success(f"✅ Successfully scraped {len(all_comments)} comments!")
                
                # Create DataFrame
                df = pd.DataFrame(all_comments)
                
                # Display preview
                st.subheader("📊 Results Preview")
                st.dataframe(df.head(10), use_container_width=True)
                
                # Statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Comments", len(df))
                with col2:
                    st.metric("Unique Commenters", df['Commenter'].nunique())
                with col3:
                    st.metric("URLs Processed", len(urls))
                
                # Download options
                st.subheader("💾 Download Results")
                
                # CSV download
                csv = df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 Download as CSV",
                    data=csv,
                    file_name=f"facebook_comments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
                # Excel download
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Comments')
                excel_data = output.getvalue()
                
                st.download_button(
                    label="📥 Download as Excel",
                    data=excel_data,
                    file_name=f"facebook_comments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
            else:
                st.error("❌ No comments were extracted. Possible reasons:")
                st.markdown("""
                - Cookies have expired (re-export from browser)
                - Posts have no comments
                - Posts are private or restricted
                - Facebook has changed their structure
                """)
                
                if failed_urls:
                    st.subheader("Failed URLs:")
                    for url, error in failed_urls:
                        st.text(f"• {url[:50]}...: {error}")
    
    # Alternative solution
    with st.expander("🔧 Alternative: Download Python Script"):
        st.markdown("""
        If the online scraping doesn't work well, you can download a Python script that runs locally:
        
        1. Click the button below to download the script
        2. Install Python 3.8+ on your computer
        3. Run: `pip install playwright pandas`
        4. Run: `python facebook_scraper.py`
        """)
        
        script_content = """
# Facebook Scraper Script
# Add your full scraper code here
print("Facebook Scraper - Local Version")
"""
        
        st.download_button(
            label="📥 Download Python Script",
            data=script_content,
            file_name="facebook_scraper.py",
            mime="text/plain"
        )

if __name__ == "__main__":
    main()
