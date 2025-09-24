"""
Facebook Comments Scraper - PRODUCTION VERSION
Optimized for all URL types with proper comment filtering
Handles Thai/non-English text correctly
"""

import asyncio
import json
import logging
import os
import random
import time
import re
from typing import Dict, List, Optional, Tuple, Set
import pandas as pd
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError

# Setup production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('facebook_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("fb-scraper")

class FacebookCommentScraper:
    """Production Facebook scraper with optimized comment filtering"""
    
    def __init__(self):
        self.all_comments = []
        self.processed_comment_texts = set()
        self.expanded_buttons = set()
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        
    async def create_delay(self, min_sec: float = 0.3, max_sec: float = 0.6):
        """Optimized delay between actions"""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
        
    def determine_url_type(self, url: str) -> str:
        """Determine URL type for appropriate scraping method"""
        url_lower = url.lower()
        
        watch_patterns = ['/watch/', 'watch?v=', '/video/', '/videos/', '/live/', '/media/']
        if any(pattern in url_lower for pattern in watch_patterns):
            return 'watch'
            
        reel_patterns = ['/reel/', '/reels/']
        if any(pattern in url_lower for pattern in reel_patterns):
            return 'reel'
            
        post_patterns = ['/posts/', '/permalink', 'story.php', '/photo', '/photos/', '/groups/']
        if any(pattern in url_lower for pattern in post_patterns):
            return 'post'
            
        return 'watch'  # Default
        
    def is_meaningful_text(self, text: str, commenter_name: str) -> bool:
        """Determine if text is meaningful comment content"""
        if not text or not text.strip():
            return False
            
        text_clean = text.strip()
        
        if len(text_clean) < 1:
            return False
            
        if text_clean.lower() == commenter_name.lower():
            return False
            
        # Check UI elements
        ui_elements = [
            'like', 'reply', 'share', 'view', 'hide', 'edited', 'translated',
            'write a comment', 'most relevant', 'author', 'top fan'
        ]
        if text_clean.lower() in [ui.lower() for ui in ui_elements]:
            return False
            
        # Check timestamps
        timestamp_patterns = [
            r'^\d+\s*(w|weeks?|d|days?|h|hours?|m|minutes?|s|seconds?|months?|years?)\s*ago$',
            r'^\d+[wdhms]$',
            r'^just now$',
            r'^yesterday$'
        ]
        for pattern in timestamp_patterns:
            if re.match(pattern, text_clean, re.IGNORECASE):
                return False
        
        # Check reaction counts
        if re.match(r'^\d+$', text_clean):
            return False
            
        # Clean text and check if meaningful
        test_text = text_clean
        test_text = re.sub(r'@\w+', '', test_text)
        test_text = re.sub(r'@\s+\w+', '', test_text)
        test_text = re.sub(r'\b(like|reply|share|view|hide)\b', '', test_text, flags=re.IGNORECASE)
        test_text = test_text.strip()
        
        if len(test_text) >= 2:
            if re.match(r'^[\d\s\.\,\!\?\-\+\=\*\(\)\[\]]+$', test_text):
                return False
            return True
        else:
            return False
            
    async def extract_comment_info(self, element) -> Tuple[str, str]:
        """Extract commenter name and comment text"""
        name = "Unknown"
        text = ""
        
        try:
            full_text = await element.inner_text()
            aria_label = await element.get_attribute('aria-label')
            
            # Extract name from aria-label
            if aria_label:
                if 'Comment by' in aria_label:
                    name = aria_label.replace('Comment by', '').strip()
                elif 'Reply by' in aria_label:
                    name = aria_label.replace('Reply by', '').strip()
                    
            # Clean name from timestamps
            time_patterns = [
                r'\s+to\s+[^\']+\'s\s+comment.*$',
                r'\s+to\s+.*?comment.*$',
                r'\s+\d+\s*(weeks?|days?|hours?|minutes?|seconds?|months?|years?)\s*ago.*$',
                r'\s+\d+[wdhms].*$',
                r'\s+Just now.*$',
                r'\s+Yesterday.*$',
                r"'s comment.*$",
                r'\s+ago.*$'
            ]
            
            for pattern in time_patterns:
                name = re.sub(pattern, '', name, flags=re.IGNORECASE).strip()
                
            if 'Top fan' in name:
                name = name.replace('Top fan', '').strip()
                
            if not full_text:
                return name, ""
                
            # Check for stickers
            sticker_element = await element.query_selector("div[aria-label*='sticker']")
            if sticker_element:
                sticker_label = await sticker_element.get_attribute('aria-label')
                if sticker_label and ',' in sticker_label:
                    text = f"[Sticker: {sticker_label.split(',')[0]}]"
                else:
                    text = "[Sticker]"
                return name, text
                
            # Process text lines
            lines = full_text.split('\n')
            comment_lines = []
            
            for line in lines:
                line_clean = line.strip()
                if not line_clean:
                    continue
                    
                # Skip name lines
                if line_clean == name:
                    continue
                    
                # Skip UI elements
                ui_elements = ['Author', 'Top fan', 'Like', 'Reply', 'Share', 'View', 
                              'See more', 'Hide', 'Edited', 'Translated', 'Write a comment']
                if line_clean in ui_elements:
                    continue
                    
                # Skip timestamps
                if re.match(r'^\d+\s*(w|weeks?|d|days?|h|hours?|m|minutes?|seconds?|months?|years?)\s*ago$', line_clean, re.IGNORECASE):
                    continue
                    
                if re.match(r'^\d+[wdhms]$', line_clean, re.IGNORECASE):
                    continue
                    
                # Skip reaction counts
                if re.match(r'^\d+$', line_clean):
                    continue
                    
                comment_lines.append(line_clean)
                
            text = ' '.join(comment_lines)
            
            # Remove tagged usernames
            try:
                attribution_links = await element.query_selector_all("a[attributionsrc*='/privacy_sandbox/comet/register/source/']")
                profile_links = await element.query_selector_all("a[href*='facebook.com/']")
                
                tagged_names = []
                for link in attribution_links + profile_links:
                    link_text = await link.inner_text()
                    if link_text and link_text.strip():
                        tagged_names.append(link_text.strip())
                        
                for tagged_name in tagged_names:
                    if tagged_name in text:
                        text = text.replace(tagged_name, '').strip()
                        text = text.replace('@' + tagged_name, '').strip()
                        
            except:
                pass
                
            # Clean up text
            text = re.sub(r'@\s*(?=\s|$)', '', text).strip()
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Remove commenter name from beginning
            if text.startswith(name + ' '):
                text = text[len(name) + 1:]
            elif text.startswith(name):
                text = text[len(name):]
                
            text = text.strip()
            
            # Validate text meaningfulness
            if not self.is_meaningful_text(text, name):
                return name, ""
                
            return name, text
            
        except Exception as e:
            logger.debug(f"Error extracting comment: {e}")
            return name, ""
            
    async def open_reel_comments(self, page: Page) -> bool:
        """Open reel comments section"""
        await self.create_delay(2.0, 3.0)
        
        # Check if already visible
        comment_container_selectors = [
            "div[role='complementary']",
            "div.x1yztbdb.x1n2onr6.xh8yej3.x1ja2u2z"
        ]
        
        for selector in comment_container_selectors:
            container = await page.query_selector(selector)
            if container and await container.is_visible():
                comments = await page.query_selector_all(f"{selector} div[role='article']")
                if len(comments) > 0:
                    return True
                    
        # Click comment button
        comment_button_selectors = [
            "div[aria-label*='Comment'][role='button']",
            "svg[aria-label*='Comment']"
        ]
        
        for selector in comment_button_selectors:
            button = await page.query_selector(selector)
            if button and await button.is_visible():
                try:
                    await button.click()
                    await self.create_delay(2.0, 3.0)
                    
                    for container_sel in comment_container_selectors:
                        container = await page.query_selector(container_sel)
                        if container and await container.is_visible():
                            return True
                            
                except Exception as e:
                    logger.error(f"Error clicking comment button: {e}")
                    
        return False
        
    async def find_comments_container(self, page: Page, url_type: str) -> Optional[str]:
        """Find comments container based on URL type"""
        container_selectors = {
            'watch': ["div[role='complementary']", "div.x78zum5.xdt5ytf.x6ikm8r.x1odjw0f"],
            'reel': ["div[role='complementary']", "div.x1yztbdb.x1n2onr6.xh8yej3"],
            'post': ["div[role='dialog']", "div[role='main']"]
        }
        
        selectors = container_selectors.get(url_type, container_selectors['post'])
        
        for selector in selectors:
            try:
                element = await page.wait_for_selector(selector, state='visible', timeout=3000)
                if element:
                    return selector
            except:
                continue
                
        return ""
        
    async def extract_caption(self, page: Page, url_type: str) -> str:
        """Extract post caption"""
        caption = "Caption not found"
        
        try:
            if url_type == 'watch':
                await self.create_delay(1.0, 1.5)
                
                see_more_button = await page.query_selector("div[role='button']:has-text('See more')")
                if see_more_button and await see_more_button.is_visible():
                    await see_more_button.click()
                    await self.create_delay(0.5, 1.0)
                
                caption_element = await page.query_selector("div.xjkvuk6.xuyqlj2.x1odjw0f")
                if caption_element:
                    text = await caption_element.inner_text()
                    if text and len(text.strip()) > 10:
                        caption = text.strip()
                        return caption
                        
            elif url_type == 'reel':
                await page.wait_for_selector("div[role='complementary']", timeout=3000)
                await self.create_delay(1.0, 1.5)
                
                see_more_button = await page.query_selector("div[role='button']:has-text('See more')")
                if see_more_button and await see_more_button.is_visible():
                    await see_more_button.click()
                    await self.create_delay(0.5, 1.0)
                
                caption_element = await page.query_selector("div.xf7dkkf.xv54qhq.xz9dl7a.x1n2onr6")
                if caption_element:
                    text = await caption_element.inner_text()
                    if text and len(text.strip()) > 10:
                        caption = text.strip()
                        return caption
                        
            elif url_type == 'post':
                await page.wait_for_selector("div[role='dialog']", timeout=3000)
                await self.create_delay(1.0, 1.5)
                
                primary_element = await page.query_selector("div[role='dialog'] div[data-ad-preview='message']")
                if primary_element:
                    text = await primary_element.inner_text()
                    if text and len(text.strip()) > 10:
                        caption = text.strip()
                        return caption
                        
        except Exception as e:
            logger.debug(f"Error extracting caption: {e}")
            
        return caption
        
    async def scrape_visible_comments(self, page: Page, container_selector: str, post_info: Dict) -> int:
        """Scrape all visible comments"""
        new_comments_count = 0
        
        # Select appropriate comment selectors
        if 'dialog' in container_selector:
            comment_selectors = [
                f"{container_selector} div[aria-label*='Comment by']",
                f"{container_selector} div[aria-label*='Reply by']"
            ]
        else:
            comment_selectors = [
                f"{container_selector} div[role='article'][aria-label*='Comment']",
                f"{container_selector} div[role='article'][aria-label*='Reply']"
            ]
            
        all_elements = []
        seen_positions = set()
        
        for selector in comment_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for elem in elements:
                    try:
                        box = await elem.bounding_box()
                        if box:
                            pos = (round(box['x']), round(box['y']))
                            if pos not in seen_positions:
                                all_elements.append(elem)
                                seen_positions.add(pos)
                        else:
                            all_elements.append(elem)
                    except:
                        all_elements.append(elem)
            except:
                continue
                
        # Process comments
        for element in all_elements:
            try:
                name, text = await self.extract_comment_info(element)
                
                if text and len(text) > 0:
                    if text not in self.processed_comment_texts:
                        self.processed_comment_texts.add(text)
                        
                        comment_data = {
                            'URL': post_info['url'],
                            'Caption': post_info['caption'],
                            'Commenter': name,
                            'Comment': text
                        }
                        
                        self.all_comments.append(comment_data)
                        new_comments_count += 1
                        logger.info(f"Comment #{len(self.all_comments)}: {name}: {text[:50]}...")
                        
            except Exception as e:
                logger.error(f"Error processing comment: {e}")
                
        return new_comments_count
        
    async def expand_all_replies(self, page: Page, container_selector: str) -> int:
        """Expand all reply threads"""
        total_expanded = 0
        max_rounds = 10
        
        for round_num in range(max_rounds):
            buttons_to_click = []
            
            if container_selector:
                all_buttons = await page.query_selector_all(f"{container_selector} div[role='button']")
            else:
                all_buttons = await page.query_selector_all("div[role='button']")
                
            for button in all_buttons:
                try:
                    if not await button.is_visible():
                        continue
                        
                    text = (await button.inner_text()).strip()
                    text_lower = text.lower()
                    
                    is_reply = False
                    if 'view' in text_lower and 'repl' in text_lower:
                        is_reply = True
                    elif 'replied' in text_lower:
                        is_reply = True
                    elif re.search(r'\d+\s*repl', text_lower):
                        is_reply = True
                    elif '•' in text and 'repl' in text_lower:
                        is_reply = True
                        
                    if is_reply:
                        button_id = f"{text}_{round_num}_{await button.evaluate('el => el.offsetTop')}"
                        if button_id not in self.expanded_buttons:
                            buttons_to_click.append((button, text, button_id))
                            
                except:
                    continue
                    
            if not buttons_to_click:
                break
                
            for button, text, button_id in buttons_to_click:
                try:
                    await button.click()
                    self.expanded_buttons.add(button_id)
                    total_expanded += 1
                    await self.create_delay(0.2, 0.4)
                except:
                    continue
                    
            if buttons_to_click:
                await self.create_delay(1.0, 1.5)
                
        return total_expanded
        
    async def click_view_more_comments(self, page: Page, url_type: str) -> bool:
        """Click 'View more comments' button"""
        selectors = [
            "div[role='complementary'] span:has-text('View more comments')",
            "div[role='button'] span:has-text('View more comments')",
            "span:has-text('View more comments')"
        ]
        
        for selector in selectors:
            try:
                button = await page.query_selector(selector)
                if button and await button.is_visible():
                    text = await button.inner_text()
                    if 'view more comments' in text.lower():
                        await button.click()
                        await self.create_delay(1.0, 1.5)
                        return True
            except:
                continue
                
        return False
        
    async def scrape_watch_video(self, page: Page, url: str) -> None:
        """Scrape WATCH/VIDEO type"""
        logger.info("Scraping WATCH/VIDEO...")
        
        caption = await self.extract_caption(page, 'watch')
        post_info = {'url': url, 'caption': caption}
        
        container = await self.find_comments_container(page, 'watch')
        if not container:
            return
            
        no_new_streak = 0
        max_cycles = 50
        
        for cycle in range(1, max_cycles + 1):
            cycle_start = len(self.all_comments)
            
            await self.expand_all_replies(page, container)
            await self.scrape_visible_comments(page, container, post_info)
            view_more_clicked = await self.click_view_more_comments(page, 'watch')
            
            cycle_new = len(self.all_comments) - cycle_start
            
            if cycle == 1 and cycle_new == 0:
                any_comments = await page.query_selector(f"{container} [aria-label*='Comment']")
                if not any_comments:
                    break
                    
            if cycle_new == 0 and not view_more_clicked:
                no_new_streak += 1
                if no_new_streak >= 3:
                    break
            else:
                no_new_streak = 0
                
    async def scrape_reel(self, page: Page, url: str) -> None:
        """Scrape REEL type"""
        logger.info("Scraping REEL...")
        
        if not await self.open_reel_comments(page):
            return
            
        caption = await self.extract_caption(page, 'reel')
        post_info = {'url': url, 'caption': caption}
        
        container = await self.find_comments_container(page, 'reel')
        if not container:
            return
            
        no_new_streak = 0
        max_cycles = 50
        
        for cycle in range(1, max_cycles + 1):
            cycle_start = len(self.all_comments)
            
            await self.expand_all_replies(page, container)
            await self.scrape_visible_comments(page, container, post_info)
            view_more_clicked = await self.click_view_more_comments(page, 'reel')
            
            cycle_new = len(self.all_comments) - cycle_start
            
            if cycle == 1 and cycle_new == 0:
                break
                
            if cycle_new == 0 and not view_more_clicked:
                no_new_streak += 1
                if no_new_streak >= 3:
                    break
            else:
                no_new_streak = 0
                
    async def scrape_post(self, page: Page, url: str) -> None:
        """Scrape POST type"""
        logger.info("Scraping POST...")
        
        caption = await self.extract_caption(page, 'post')
        post_info = {'url': url, 'caption': caption}
        
        container = await self.find_comments_container(page, 'post')
        if not container:
            return
            
        # Quick check for comments
        has_comments = await page.evaluate("""
            () => {
                const dialog = document.querySelector('div[role="dialog"]');
                if (!dialog) return false;
                return dialog.querySelector('[aria-label*="Comment"]') !== null ||
                       dialog.querySelector('ul') !== null;
            }
        """)
        
        if not has_comments:
            return
            
        no_new_streak = 0
        max_cycles = 50
        
        for cycle in range(1, max_cycles + 1):
            cycle_start = len(self.all_comments)
            
            await self.expand_all_replies(page, container)
            await self.create_delay(1.0, 1.5)
            await self.scrape_visible_comments(page, container, post_info)
            
            # Scroll dialog
            await page.evaluate("""
                () => {
                    const dialog = document.querySelector('div[role="dialog"]');
                    if (!dialog) return false;
                    
                    const scrollable = Array.from(dialog.querySelectorAll('*')).find(el =>
                        el.scrollHeight > el.clientHeight &&
                        ['auto', 'scroll'].includes(window.getComputedStyle(el).overflowY)
                    );
                    
                    if (scrollable) {
                        scrollable.scrollTop = scrollable.scrollHeight;
                        return true;
                    }
                    return false;
                }
            """)
            
            await self.create_delay(1.0, 1.5)
            
            # Check if at end
            at_end = await page.evaluate("""
                () => {
                    const texts = Array.from(document.querySelectorAll('div[role="dialog"] *'))
                        .map(el => el.textContent);
                    return texts.some(text => text && text.includes('Most relevant') && 
                                             text.includes('filtered'));
                }
            """)
            
            cycle_new = len(self.all_comments) - cycle_start
            
            if cycle == 1 and cycle_new == 0:
                break
                
            if at_end and cycle_new == 0:
                break
                
            if cycle_new == 0:
                no_new_streak += 1
                if no_new_streak >= 3:
                    break
            else:
                no_new_streak = 0
                
    async def scrape_single_url(self, page: Page, url: str) -> bool:
        """Scrape a single URL"""
        logger.info(f"Scraping: {url[:60]}...")
        
        # Reset for new URL
        self.processed_comment_texts.clear()
        self.expanded_buttons.clear()
        
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=20000)
            await self.create_delay(1.5, 2.0)
            
            url_type = self.determine_url_type(page.url)
            
            if url_type == 'watch':
                await self.scrape_watch_video(page, page.url)
            elif url_type == 'reel':
                await self.scrape_reel(page, page.url)
            elif url_type == 'post':
                await self.scrape_post(page, page.url)
            else:
                await self.scrape_watch_video(page, page.url)
                
            return True
            
        except Exception as e:
            logger.error(f"Error scraping URL: {e}")
            return False
            
    def save_results(self) -> str:
        """Save results to single CSV file"""
        if not self.all_comments:
            logger.warning("No comments to save")
            return ""
            
        df = pd.DataFrame(self.all_comments)
        
        # Remove duplicates
        initial = len(df)
        df = df.drop_duplicates(subset=['Comment'], keep='first')
        removed = initial - len(df)
        if removed > 0:
            logger.info(f"Removed {removed} duplicate comments")
        
        # Save to CSV
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"facebook_comments_{timestamp}.csv"
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        
        logger.info(f"Saved {len(df)} comments to {filename}")
        return filename
        
    async def run_scraper(self, urls_file: str, cookies_file: str):
        """Main scraper runner"""
        logger.info("Starting Facebook Comments Scraper")
        
        # Load URLs
        if not os.path.exists(urls_file):
            logger.error(f"URLs file not found: {urls_file}")
            return
            
        with open(urls_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
            
        logger.info(f"Loaded {len(urls)} URLs")
        
        # Load cookies
        if not os.path.exists(cookies_file):
            logger.error(f"Cookies file not found: {cookies_file}")
            return
            
        with open(cookies_file, 'r', encoding='utf-8') as f:
            raw_cookies = json.load(f)
            
        # Format cookies
        formatted_cookies = []
        for cookie in raw_cookies:
            if 'name' not in cookie or 'value' not in cookie:
                continue
                
            if 'sameSite' in cookie:
                same_site = str(cookie['sameSite']).lower()
                cookie['sameSite'] = {
                    'strict': 'Strict',
                    'lax': 'Lax', 
                    'none': 'None'
                }.get(same_site, 'Lax')
            else:
                cookie['sameSite'] = 'Lax'
                
            if 'domain' in cookie:
                if not cookie['domain'].startswith('.'):
                    cookie['domain'] = '.' + cookie['domain']
            else:
                cookie['domain'] = '.facebook.com'
                
            cookie.setdefault('path', '/')
            cookie.setdefault('secure', True)
            formatted_cookies.append(cookie)
            
        # Start browser
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            context = await browser.new_context(
                user_agent=self.user_agent,
                viewport={'width': 1920, 'height': 1080}
            )
            
            await context.add_cookies(formatted_cookies)
            page = await context.new_page()
            
            # Block resources for speed
            await page.route('**/*.{png,jpg,jpeg,gif,svg,ico}', lambda route: route.abort())
            await page.route('**/fonts/**', lambda route: route.abort())
            
            # Test login
            await page.goto("https://www.facebook.com", wait_until='domcontentloaded', timeout=20000)
            await self.create_delay(1.5, 2.0)
            
            if '/login' in page.url or 'login.php' in page.url:
                logger.error("Not logged in - cookies expired!")
                await browser.close()
                return
            else:
                logger.info("Successfully logged in")
                
            # Process URLs
            start_time = time.time()
            success_count = 0
            
            for i, url in enumerate(urls, 1):
                logger.info(f"Processing URL {i}/{len(urls)}")
                
                if await self.scrape_single_url(page, url):
                    success_count += 1
                    
                if i < len(urls):
                    delay = random.uniform(2, 3)
                    await self.create_delay(delay, delay + 0.5)
                    
            await browser.close()
            
        # Save results
        filename = self.save_results()
        elapsed = time.time() - start_time
        
        # Final report
        logger.info("="*50)
        logger.info("SCRAPING COMPLETED!")
        logger.info(f"Success: {success_count}/{len(urls)} URLs")
        logger.info(f"Total comments: {len(self.all_comments)}")
        logger.info(f"Time: {elapsed:.1f}s ({elapsed/len(urls):.1f}s per URL)")
        if filename:
            logger.info(f"Output file: {filename}")
        logger.info("="*50)
        
async def main():
    """Main entry point"""
    scraper = FacebookCommentScraper()
    
    # Update these paths
    urls_file = "/Users/spritetj/Python/sideProject/FB_scraper/data/input/urls.txt"
    cookies_file = "/Users/spritetj/Python/sideProject/FB_scraper/config/cookies.json"
    
    await scraper.run_scraper(urls_file, cookies_file)
    
if __name__ == "__main__":
    asyncio.run(main())