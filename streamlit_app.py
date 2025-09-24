"""
Facebook Comments Scraper - Web App Version
Easy-to-use interface for non-technical users
"""

import streamlit as st
import asyncio
import json
import os
import time
import pandas as pd
from datetime import datetime
import tempfile
import base64
from io import StringIO
import sys

# Add the scraper module path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import your scraper (we'll modify it slightly)
from fb_scraper_core import FacebookCommentScraper

# Page configuration
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
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #166fe5;
    }
    .success-message {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .error-message {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'scraping_complete' not in st.session_state:
    st.session_state.scraping_complete = False
if 'result_file' not in st.session_state:
    st.session_state.result_file = None
if 'scraping_status' not in st.session_state:
    st.session_state.scraping_status = []

def get_download_link(df, filename):
    """Generate download link for DataFrame"""
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 Download Results ({len(df)} comments)</a>'

async def run_scraper_async(urls, cookies_json, progress_placeholder):
    """Run the scraper with progress updates"""
    scraper = FacebookCommentScraper()
    
    # Create temp files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for url in urls:
            f.write(url + '\n')
        urls_file = f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(cookies_json, f)
        cookies_file = f.name
    
    try:
        # Update progress
        progress_placeholder.info("🔄 Starting scraper...")
        await scraper.run_scraper(urls_file, cookies_file)
        
        # Return results
        return scraper.all_comments
        
    finally:
        # Clean up temp files
        if os.path.exists(urls_file):
            os.remove(urls_file)
        if os.path.exists(cookies_file):
            os.remove(cookies_file)

def main():
    # Header
    st.title("📱 Facebook Comments Scraper")
    st.markdown("Extract comments from Facebook posts, videos, and reels easily!")
    
    # Instructions in expander
    with st.expander("📖 How to use this tool", expanded=True):
        st.markdown("""
        ### Step-by-step Instructions:
        
        1. **Prepare Facebook URLs**
           - Copy the URLs of Facebook posts/videos/reels you want to scrape
           - One URL per line in the text box below
        
        2. **Get Your Facebook Cookies** (One-time setup)
           - Install Chrome extension: [Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)
           - Log into Facebook in Chrome
           - Click the Cookie-Editor extension icon
           - Click "Export" → "Export as JSON"
           - Save the file
        
        3. **Upload & Run**
           - Paste your URLs
           - Upload the cookies JSON file
           - Click "Start Scraping"
           - Download your results!
        """)
    
    st.divider()
    
    # Input section
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📝 Step 1: Enter Facebook URLs")
        urls_text = st.text_area(
            "Paste URLs here (one per line):",
            height=200,
            placeholder="https://www.facebook.com/watch/?v=123456789\nhttps://www.facebook.com/reel/987654321\nhttps://www.facebook.com/username/posts/456789123",
            help="Enter Facebook post, video, or reel URLs. One URL per line."
        )
        
        # Parse URLs
        urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        if urls:
            st.success(f"✅ {len(urls)} URL(s) ready")
    
    with col2:
        st.subheader("🔐 Step 2: Upload Cookies File")
        cookies_file = st.file_uploader(
            "Upload cookies.json file:",
            type=['json'],
            help="Export cookies from your browser using Cookie-Editor extension"
        )
        
        if cookies_file:
            try:
                cookies_json = json.loads(cookies_file.read())
                st.success(f"✅ Cookies loaded ({len(cookies_json)} cookies)")
                cookies_valid = True
            except:
                st.error("❌ Invalid cookies file. Please check the format.")
                cookies_valid = False
        else:
            cookies_valid = False
    
    st.divider()
    
    # Advanced settings (optional)
    with st.expander("⚙️ Advanced Settings (Optional)"):
        col1, col2 = st.columns(2)
        with col1:
            headless = st.checkbox("Run in background mode", value=True, help="Uncheck to see the browser window")
        with col2:
            delay = st.slider("Delay between URLs (seconds)", 1, 5, 2, help="Longer delays are safer")
    
    # Action section
    st.subheader("📊 Step 3: Start Scraping")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Start Scraping", disabled=not (urls and cookies_valid), use_container_width=True):
            if urls and cookies_valid:
                progress_placeholder = st.empty()
                status_placeholder = st.empty()
                
                try:
                    # Reset session state
                    st.session_state.scraping_complete = False
                    st.session_state.result_file = None
                    
                    # Show progress
                    with st.spinner("🔄 Scraping in progress... This may take a few minutes."):
                        # Create event loop and run scraper
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        cookies_data = json.loads(cookies_file.getvalue())
                        comments = loop.run_until_complete(
                            run_scraper_async(urls, cookies_data, progress_placeholder)
                        )
                        loop.close()
                    
                    if comments:
                        # Create DataFrame
                        df = pd.DataFrame(comments)
                        df = df.drop_duplicates(subset=['Comment'], keep='first')
                        
                        # Save results
                        st.session_state.scraping_complete = True
                        st.session_state.result_file = df
                        
                        # Show success
                        progress_placeholder.empty()
                        status_placeholder.success(f"✅ Successfully scraped {len(df)} unique comments from {len(urls)} URLs!")
                    else:
                        status_placeholder.warning("⚠️ No comments found. Please check your URLs and cookies.")
                        
                except Exception as e:
                    progress_placeholder.empty()
                    status_placeholder.error(f"❌ Error: {str(e)}")
                    st.error("Please check your cookies are valid and from a logged-in Facebook session.")
    
    # Results section
    if st.session_state.scraping_complete and st.session_state.result_file is not None:
        st.divider()
        st.subheader("📈 Results")
        
        df = st.session_state.result_file
        
        # Statistics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Comments", len(df))
        with col2:
            st.metric("Unique URLs", df['URL'].nunique())
        with col3:
            st.metric("Unique Commenters", df['Commenter'].nunique())
        with col4:
            avg_length = df['Comment'].str.len().mean()
            st.metric("Avg Comment Length", f"{avg_length:.0f} chars")
        
        # Preview
        st.subheader("👀 Preview (First 10 comments)")
        preview_df = df.head(10)[['Commenter', 'Comment']].copy()
        preview_df['Comment'] = preview_df['Comment'].str[:100] + '...'
        st.dataframe(preview_df, use_container_width=True)
        
        # Download section
        st.subheader("💾 Download Results")
        col1, col2 = st.columns(2)
        
        with col1:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"facebook_comments_{timestamp}.csv"
            
            # CSV download
            csv_data = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 Download as CSV",
                data=csv_data,
                file_name=csv_filename,
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # Excel download
            excel_buffer = StringIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Comments', index=False)
            excel_data = excel_buffer.getvalue()
            
            st.download_button(
                label="📥 Download as Excel",
                data=excel_data,
                file_name=f"facebook_comments_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    
    # Footer
    st.divider()
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>Made with ❤️ for easy Facebook comment extraction</p>
        <p style='font-size: 0.8em;'>⚠️ Please respect Facebook's terms of service and privacy guidelines</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
