"""
Facebook Comment Scraper - Full Headless Mode
Combines WATCH, REEL, and POST scrapers in pure headless mode
Uses fresh page management to avoid crashes
Fixed: Creates new page for each URL to prevent corruption
"""

import asyncio
import csv
import json
import logging
import random
import re
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright, Page
from typing import Set, List, Dict

# Setup logging
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'facebook_scraper_fullheadless.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FacebookScraperFullHeadless:
    """Unified scraper in full headless mode with proper page management"""

    def __init__(self):
        self.all_comments: List[Dict] = []
        self.processed_texts: Set[str] = set()
        self.BASE_DIR = BASE_DIR
        self.failed_urls: List[str] = []

    def sanitize_cookies(self, cookies: List[Dict]) -> List[Dict]:
        """Sanitize cookies for Playwright compatibility"""
        for cookie in cookies:
            if 'sameSite' in cookie:
                value = str(cookie['sameSite']).lower()
                if value == 'no_restriction':
                    cookie['sameSite'] = 'None'
                elif value in ['lax', 'strict']:
                    cookie['sameSite'] = value.capitalize()
                else:
                    cookie['sameSite'] = 'Lax'
        return cookies

    async def random_delay(self, min_sec: float = 0.2, max_sec: float = 0.4):
        """Random delay to mimic human behavior"""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    def determine_url_type(self, url: str) -> str:
        """Determine if URL is WATCH, REEL, or POST"""
        url_lower = url.lower()

        # WATCH patterns
        watch_patterns = ['/watch/', 'watch?v=', '/video/', '/videos/', '/live/', '/media/']
        if any(pattern in url_lower for pattern in watch_patterns):
            return 'WATCH'

        # REEL patterns
        reel_patterns = ['/reel/', '/reels/']
        if any(pattern in url_lower for pattern in reel_patterns):
            return 'REEL'

        # POST patterns (default)
        return 'POST'

    def extract_name_from_aria(self, aria_label: str) -> str:
        """Extract commenter name from aria-label with timestamp removal"""
        if not aria_label:
            return "Unknown"

        # Handle "Reply by NAME to..." pattern
        if 'Reply by' in aria_label:
            match = re.search(r'Reply by (.+?) to', aria_label)
            if match:
                return match.group(1).strip()
            name = aria_label.replace('Reply by ', '').split(' to ')[0].strip()
        # Handle "Comment by NAME ..." pattern
        elif 'Comment by' in aria_label:
            # FIXED: Handles all timestamp formats
            match = re.search(r'Comment by (.+?)(?:\s+(?:about\s+)?(?:a\s+(?:few\s+)?)?(?:an\s+)?(?:\d+\s+)?(?:second|minute|hour|day|week|month|year)s?\s+ago|,|$)', aria_label)
            if match:
                return match.group(1).strip()
            name = aria_label.replace('Comment by', '').split(',')[0].strip()
        # NEW: Thai "by" variation
        elif 'ความคิดเห็นโดย' in aria_label:
            match = re.search(r'ความคิดเห็นโดย\s+(.+?)(?:\s+เมื่อ|,|$)', aria_label)
            if match:
                return match.group(1).strip()
            name = aria_label.replace('ความคิดเห็นโดย', '').split('เมื่อ')[0].strip()
        # NEW: Thai "from" variation (ความคิดเห็นจาก = Comment from)
        elif 'ความคิดเห็นจาก' in aria_label:
            match = re.search(r'ความคิดเห็นจาก\s+(.+?)\s+เมื่อ', aria_label)
            if match:
                return match.group(1).strip()
            name = aria_label.replace('ความคิดเห็นจาก', '').split('เมื่อ')[0].strip()
        else:
            return "Unknown"

        return name

    def is_meaningful_text(self, text: str) -> bool:
        """Check if text is a valid comment"""
        if not text or len(text.strip()) < 2:
            return False

        ui_patterns = [
            r'^(Like|Reply|Share|Follow|Author)$',
            r'^\d+[wdhmy]$',
            r'^\d{1,3}$',
            r'^(Most relevant|View \d+ repl)',
        ]

        for pattern in ui_patterns:
            if re.match(pattern, text.strip(), re.IGNORECASE):
                return False

        return True

    async def create_browser_and_context(self, playwright, cookies):
        """Create browser and context with minimal stealth (proven to work in headless)"""
        # Minimal args that work in headless mode
        args = ['--no-sandbox', '--disable-setuid-sandbox']

        browser = await playwright.chromium.launch(headless=True, args=args)

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        await context.add_cookies(cookies)
        return browser, context

    # [Include all the scraping methods from facebook_scraper_headless.py here]
    # For brevity, I'll reference them - they're identical to the headless version

    async def click_view_more_watch(self, page: Page) -> bool:
        """Click 'View more comments' button for WATCH videos"""
        result = await page.evaluate("""
            () => {
                const main = document.querySelector('[role="main"]');
                if (!main) return {clicked: false, reason: 'No main container'};

                const buttons = main.querySelectorAll('[role="button"]');

                for (const button of buttons) {
                    const text = button.innerText || '';
                    const textLower = text.toLowerCase();

                    if (textLower.includes('view') &&
                        textLower.includes('more') &&
                        textLower.includes('comment') &&
                        !textLower.includes('repl')) {

                        if (button.offsetParent !== null) {
                            button.click();
                            return {clicked: true, text: text};
                        }
                    }
                }

                return {clicked: false, reason: 'Button not found or not visible'};
            }
        """)

        if result.get('clicked'):
            logger.info(f"✓ Clicked: {result.get('text', 'View more comments')} (WATCH)")
            await self.random_delay(2.0, 3.0)
            return True

        return False

    async def expand_replies_watch(self, page: Page) -> int:
        """Expand reply threads in WATCH videos"""
        result = await page.evaluate("""
            () => {
                const main = document.querySelector('[role="main"]');
                if (!main) return {expanded: 0, reason: 'No main'};

                const buttons = main.querySelectorAll('[role="button"]');
                let expandedCount = 0;

                for (const button of buttons) {
                    const text = (button.innerText || '').toLowerCase();

                    if ((text.includes('view') && text.includes('repl')) ||
                        text.includes('replied') ||
                        text.match(/\\d+\\s*repl/i)) {

                        if (button.querySelector('img') && text.match(/^\\d+$/)) continue;

                        if (button.offsetParent !== null) {
                            button.click();
                            expandedCount++;
                        }
                    }
                }

                return {expanded: expandedCount};
            }
        """)

        count = result.get('expanded', 0)
        if count > 0:
            logger.info(f"Expanded {count} reply threads (WATCH)")
            await self.random_delay(1.0, 2.0)

        return count

    async def scrape_watch(self, page: Page, url: str):
        """Scrape WATCH video comments"""
        logger.info(f"Scraping WATCH: {url}")

        try:
            await page.goto(url, timeout=60000)
            await self.random_delay(3.0, 5.0)

            # Extract caption - FIXED: Use correct selectors from individual scraper
            caption = await page.evaluate("""
                () => {
                    const main = document.querySelector('[role="main"]');
                    if (!main) return '';

                    // Method 1: Look for large spans with caption text (VERIFIED selectors)
                    const spans = main.querySelectorAll('span.x193iq5w, span.x1lliihq');
                    for (const span of spans) {
                        const text = span.innerText || '';
                        // Caption is usually > 10 chars and not UI elements or error messages
                        if (text.length > 10 &&
                            !text.includes('Comments') &&
                            !text.includes('Explore more') &&
                            !text.includes('Latest videos') &&
                            !text.includes('Like') &&
                            !text.includes('Share') &&
                            !text.includes('Sorry') &&           // Filter error messages
                            !text.includes('trouble') &&         // Filter error messages
                            !text.includes('playing') &&         // Filter error messages
                            !text.match(/^\\d+[wdhmy]$/)) {
                            return text;
                        }
                    }

                    // Method 2: Fallback to h2 tags
                    const h2s = main.querySelectorAll('h2');
                    for (const h2 of h2s) {
                        const text = h2.innerText || '';
                        if (text.length > 10 &&
                            !text.includes('Explore more') &&
                            !text.includes('Latest videos') &&
                            !text.includes('Comments') &&
                            !text.includes('Follow')) {
                            return text;
                        }
                    }

                    return '';
                }
            """)

            logger.info(f"Caption: {caption[:100]}..." if caption else "No caption")

            # Initial scroll
            await page.evaluate("window.scrollBy(0, 500)")
            await self.random_delay(2.0, 3.0)

            # Main scraping loop
            max_cycles = 30
            no_new_streak = 0

            for cycle in range(1, max_cycles + 1):
                logger.info(f"=== Cycle {cycle}/{max_cycles} (WATCH) ===")

                cycle_start = len(self.all_comments)

                await self.click_view_more_watch(page)
                await self.expand_replies_watch(page)

                articles = await page.query_selector_all('[role="main"] [role="article"]')

                for article in articles:
                    try:
                        aria_label = await article.get_attribute('aria-label')

                        # Support both English and Thai variations
                        if not aria_label or ('Comment by' not in aria_label and
                                              'Reply by' not in aria_label and
                                              'ความคิดเห็นโดย' not in aria_label and
                                              'ความคิดเห็นจาก' not in aria_label):
                            continue

                        name = self.extract_name_from_aria(aria_label)

                        text_divs = await article.query_selector_all('div[dir="auto"]')
                        comment_text = ""

                        for div in text_divs:
                            div_text = await div.inner_text()
                            if div_text and self.is_meaningful_text(div_text):
                                if div_text.strip() != name:
                                    comment_text = div_text.strip()
                                    break

                        if not comment_text:
                            continue

                        text_normalized = ' '.join(comment_text.split())
                        if text_normalized in self.processed_texts:
                            continue

                        self.processed_texts.add(text_normalized)

                        self.all_comments.append({
                            'URL': url,
                            'Type': 'WATCH',
                            'Caption': caption,
                            'Commenter': name,
                            'Comment': comment_text
                        })

                        logger.info(f"Comment #{len(self.all_comments)}: {name}: {comment_text[:50]}...")

                    except Exception as e:
                        logger.debug(f"Error processing article: {e}")
                        continue

                cycle_new = len(self.all_comments) - cycle_start
                logger.info(f"Cycle {cycle}: Found {cycle_new} new (Total: {len(self.all_comments)})")

                if cycle_new == 0:
                    no_new_streak += 1
                    if no_new_streak >= 4:
                        logger.info(f"No new comments for {no_new_streak} cycles. Done.")
                        break
                else:
                    no_new_streak = 0

            logger.info(f"✅ WATCH complete: {len(self.all_comments)} total comments")

        except Exception as e:
            logger.error(f"Error scraping WATCH {url}: {e}")
            raise

    async def open_reel_comments(self, page: Page) -> bool:
        """Open REEL comments section"""
        for attempt in range(3):
            container = await page.query_selector('div[role="complementary"]')
            if container:
                try:
                    is_visible = await container.is_visible()
                    if is_visible:
                        comments = await page.query_selector_all("div[role='complementary'] div[role='article']")
                        if len(comments) > 0:
                            logger.info(f"Comments auto-loaded with {len(comments)} comments")
                            return True
                except:
                    pass

            if attempt < 2:
                await self.random_delay(0.5, 0.8)

        logger.info("Looking for comment button...")

        button_selectors = [
            "div[aria-label*='Comment'][role='button']",
            "div[aria-label*='comment'][role='button']",
            "svg[aria-label*='Comment']",
            "div[role='button'] svg[aria-label*='Comment']"
        ]

        button = None
        for selector in button_selectors:
            try:
                button = await page.query_selector(selector)
                if button:
                    is_visible = await button.is_visible()
                    if is_visible:
                        logger.info(f"Found comment button: {selector}")
                        break
            except:
                continue

        if button:
            try:
                await button.scroll_into_view_if_needed()
                await self.random_delay(0.3, 0.5)
                await button.click()
                logger.info("Clicked comment button")
                await self.random_delay(2.0, 3.0)

                container = await page.query_selector("div[role='complementary']")
                if container:
                    comments = await page.query_selector_all("div[role='complementary'] div[role='article']")
                    logger.info(f"✓ Comments opened with {len(comments)} comments")
                    return True
            except Exception as e:
                logger.error(f"Error clicking comment button: {e}")

        return False

    async def click_view_more_reel(self, page: Page) -> bool:
        """Click 'View more comments' button for REEL"""
        result = await page.evaluate("""
            () => {
                const comp = document.querySelector('[role="complementary"]');
                if (!comp) return {clicked: false, reason: 'No complementary'};

                const buttons = comp.querySelectorAll('[role="button"]');

                for (const button of buttons) {
                    const text = button.innerText || '';
                    const textLower = text.toLowerCase();

                    if (textLower.includes('view') &&
                        textLower.includes('more') &&
                        textLower.includes('comment')) {

                        if (button.offsetParent !== null) {
                            button.click();
                            return {clicked: true, text: text};
                        }
                    }
                }

                return {clicked: false, reason: 'Button not found or not visible'};
            }
        """)

        if result.get('clicked'):
            logger.info(f"✓ Clicked: {result.get('text', 'View more comments')} (REEL)")
            await self.random_delay(2.0, 3.0)
            return True

        return False

    async def expand_replies_reel(self, page: Page) -> int:
        """Expand reply threads in REEL"""
        result = await page.evaluate("""
            () => {
                const comp = document.querySelector('[role="complementary"]');
                if (!comp) return {expanded: 0};

                const buttons = comp.querySelectorAll('[role="button"]');
                let expandedCount = 0;

                for (const button of buttons) {
                    const text = (button.innerText || '').toLowerCase();

                    if ((text.includes('view') && text.includes('repl')) ||
                        text.includes('replied') ||
                        text.match(/\\d+\\s*repl/i)) {

                        if (button.querySelector('img') && text.match(/^\\d+$/)) continue;

                        if (button.offsetParent !== null) {
                            button.click();
                            expandedCount++;
                        }
                    }
                }

                return {expanded: expandedCount};
            }
        """)

        count = result.get('expanded', 0)
        if count > 0:
            logger.info(f"Expanded {count} reply threads (REEL)")
            await self.random_delay(1.0, 2.0)

        return count

    async def scrape_reel(self, page: Page, url: str):
        """Scrape REEL comments"""
        logger.info(f"Scraping REEL: {url}")

        try:
            await page.goto(url, timeout=60000)
            await self.random_delay(3.0, 5.0)

            await self.open_reel_comments(page)

            # CRITICAL: Click "See more" button FIRST to expand full caption (from individual scraper)
            see_more_clicked = await page.evaluate("""
                () => {
                    const comp = document.querySelector('[role="complementary"]');
                    if (!comp) return false;

                    const buttons = comp.querySelectorAll('[role="button"]');
                    for (const btn of buttons) {
                        const text = (btn.innerText || '').toLowerCase();
                        if (text.includes('see more')) {
                            if (btn.offsetParent !== null) {
                                btn.click();
                                return true;
                            }
                        }
                    }
                    return false;
                }
            """)

            if see_more_clicked:
                logger.info("Clicked 'See more' to expand full caption")
                await self.random_delay(1.0, 1.5)

            # FIXED: Balanced caption extraction - not too strict, not too permissive
            caption = await page.evaluate("""
                () => {
                    const comp = document.querySelector('[role="complementary"]');
                    if (!comp) return null;

                    // Method 1: Look for SPAN with specific classes (verified from inspection)
                    // Caption is in span.x193iq5w or similar, ABOVE comment articles
                    const spans = comp.querySelectorAll('span.x193iq5w, span.x1lliihq');

                    for (const span of spans) {
                        // CRITICAL: Skip if span is inside a comment article
                        if (span.closest('[role="article"]')) continue;

                        const text = span.innerText || '';

                        // Caption should be meaningful text, not a comment or UI element
                        if (text.length > 30 &&
                            !text.includes('Comment by') &&  // Not a comment
                            !text.includes('Reply by') &&    // Not a reply
                            !text.includes('replied') &&     // Not a reply indicator
                            !text.match(/^\\d+[wdhm]/) &&    // Not a timestamp
                            !text.includes('Most relevant')) {

                            // Remove "See more" or "See less" suffix if present
                            return text.replace(/…?\\s*See more$/i, '').replace(/\\s*See less$/i, '').trim();
                        }
                    }

                    // Method 2: Look in DIV before first article (for edge cases)
                    const firstArticle = comp.querySelector('[role="article"]');
                    if (firstArticle) {
                        // Check siblings before first article
                        let current = firstArticle.previousElementSibling;
                        let checked = 0;
                        while (current && checked < 3) {  // Limit check to 3 siblings
                            const text = current.innerText || '';
                            if (text.length > 30 &&
                                !text.includes('Comment') &&
                                !text.includes('Reply') &&
                                !text.includes('Like') &&
                                !text.includes('Share')) {
                                return text.replace(/…?\\s*See more$/, '').trim();
                            }
                            current = current.previousElementSibling;
                            checked++;
                        }
                    }

                    return null;
                }
            """)

            # Return "No caption" when caption is empty or null
            if caption:
                logger.info(f"Caption: {caption[:100]}...")
            else:
                caption = "No caption"
                logger.info("No caption found")

            max_cycles = 50
            no_new_streak = 0

            for cycle in range(1, max_cycles + 1):
                logger.info(f"=== Cycle {cycle}/{max_cycles} (REEL) ===")

                cycle_start = len(self.all_comments)

                await self.click_view_more_reel(page)
                await self.expand_replies_reel(page)

                articles = await page.query_selector_all('div[role="complementary"] div[role="article"]')

                for article in articles:
                    try:
                        aria_label = await article.get_attribute('aria-label')

                        # Support both English and Thai variations
                        if not aria_label or ('Comment by' not in aria_label and
                                              'Reply by' not in aria_label and
                                              'ความคิดเห็นโดย' not in aria_label and
                                              'ความคิดเห็นจาก' not in aria_label):
                            continue

                        name = self.extract_name_from_aria(aria_label)

                        text_divs = await article.query_selector_all('div[dir="auto"]')
                        comment_text = ""

                        for div in text_divs:
                            div_text = await div.inner_text()
                            if div_text and self.is_meaningful_text(div_text):
                                if div_text.strip() != name:
                                    comment_text = div_text.strip()
                                    break

                        if not comment_text:
                            continue

                        text_normalized = ' '.join(comment_text.split())
                        if text_normalized in self.processed_texts:
                            continue

                        self.processed_texts.add(text_normalized)

                        self.all_comments.append({
                            'URL': url,
                            'Type': 'REEL',
                            'Caption': caption,
                            'Commenter': name,
                            'Comment': comment_text
                        })

                        logger.info(f"Comment #{len(self.all_comments)}: {name}: {comment_text[:50]}...")

                    except Exception as e:
                        logger.debug(f"Error processing article: {e}")
                        continue

                cycle_new = len(self.all_comments) - cycle_start
                logger.info(f"Cycle {cycle}: Found {cycle_new} new (Total: {len(self.all_comments)})")

                if cycle_new == 0:
                    no_new_streak += 1
                    if no_new_streak >= 3:
                        logger.info(f"No new comments for {no_new_streak} cycles. Done.")
                        break
                else:
                    no_new_streak = 0

            logger.info(f"✅ REEL complete: {len(self.all_comments)} total comments")

        except Exception as e:
            logger.error(f"Error scraping REEL {url}: {e}")
            raise

    async def scrape_post_comments(self, page: Page, dialog_selector: str, url: str, caption: str) -> int:
        """Scrape visible comments from POST dialog - HELPER FUNCTION"""
        new_count = 0

        articles = await page.query_selector_all(f'{dialog_selector} [role="article"]')

        for article in articles:
            try:
                aria_label = await article.get_attribute('aria-label')
                name = "Unknown"
                
                # 1. Try to extract name from aria-label (Preferred)
                if aria_label and ('Comment by' in aria_label or 
                                  'Reply by' in aria_label or 
                                  'ความคิดเห็นโดย' in aria_label or 
                                  'ความคิดเห็นจาก' in aria_label):
                    name = self.extract_name_from_aria(aria_label)
                
                # 2. Fallback: If no valid aria-label, try to find name in the first link or strong tag
                if name == "Unknown":
                    # Check if it's a valid comment structure (usually has a link to profile)
                    profile_link = await article.query_selector('a[href*="/user/"], a[href*="profile.php"], a[role="link"]')
                    if profile_link:
                        name = await profile_link.inner_text()
                
                # If still unknown and no aria-label, it might be a UI element or the post itself
                if name == "Unknown" and not aria_label:
                    continue

                text_divs = await article.query_selector_all('div[dir="auto"]')
                comment_text = ""

                for div in text_divs:
                    div_text = await div.inner_text()
                    if div_text and self.is_meaningful_text(div_text):
                        if div_text.strip() != name:
                            comment_text = div_text.strip()
                            break

                if not comment_text:
                    continue

                text_normalized = ' '.join(comment_text.split())
                if text_normalized in self.processed_texts:
                    continue

                self.processed_texts.add(text_normalized)

                self.all_comments.append({
                    'URL': url,
                    'Type': 'POST',
                    'Caption': caption,
                    'Commenter': name,
                    'Comment': comment_text
                })

                new_count += 1
                logger.info(f"Comment #{len(self.all_comments)}: {name}: {comment_text[:50]}...")

            except Exception as e:
                logger.debug(f"Error processing article: {e}")
                continue

        return new_count

    async def expand_replies_post(self, page: Page, dialog_selector: str) -> int:
        """Expand reply threads in POST dialog - FIXED to use dialog_selector"""
        expanded = await page.evaluate("""
            (dialogSelector) => {
                const dialog = document.querySelector(dialogSelector);
                if (!dialog) return 0;

                const buttons = dialog.querySelectorAll('[role="button"]');
                let clicked = 0;

                for (const button of buttons) {
                    const text = (button.innerText || '').toLowerCase();

                    // VERIFIED patterns: "replied · X repl" or "View all X repl"
                    if ((text.includes('replied') && text.includes('repl')) ||
                        (text.includes('view') && text.includes('repl'))) {
                        try {
                            button.click();
                            clicked++;
                        } catch (e) {
                            // Ignore click errors
                        }
                    }
                }

                return clicked;
            }
        """, dialog_selector)

        if expanded > 0:
            logger.info(f"Expanded {expanded} reply threads (POST)")
            await self.random_delay(1.5, 2.0)  # Wait for replies to load

        return expanded

    async def scrape_post(self, page: Page, url: str):
        """Scrape POST comments"""
        logger.info(f"Scraping POST: {url}")

        try:
            await page.goto(url, timeout=60000)
            await self.random_delay(3.0, 5.0)

            # FIXED: Find the correct dialog first, then extract caption from within it
            # The POST page may have multiple dialogs (notifications, menus, etc.)
            result = await page.evaluate("""
                () => {
                    // 1. Try to find in dialogs (modal mode)
                    const dialogs = document.querySelectorAll('[role="dialog"]');

                    for (let i = 0; i < dialogs.length; i++) {
                        const dialog = dialogs[i];
                        const hasCaption = dialog.querySelector('[data-ad-preview="message"]') !== null;
                        const articles = dialog.querySelectorAll('[role="article"]');

                        // The correct dialog should have both caption AND articles
                        if (articles.length > 3 && (hasCaption || articles.length > 5)) {
                            // This is likely the main post dialog
                            dialog.setAttribute('data-fb-scraper', 'main-dialog');  // Mark it
                            return {
                                found: true,
                                type: 'dialog',
                                selector: '[data-fb-scraper="main-dialog"]',
                                index: i,
                                articles: articles.length,
                                hasCaption: hasCaption
                            };
                        }
                    }

                    // 2. Fallback: Try to find in main role (full page mode)
                    const main = document.querySelector('[role="main"]');
                    if (main) {
                        const hasCaption = main.querySelector('[data-ad-preview="message"]') !== null;
                        const articles = main.querySelectorAll('[role="article"]');
                        
                        if (hasCaption || articles.length > 0) {
                             main.setAttribute('data-fb-scraper', 'main-role');
                             return {
                                found: true,
                                type: 'main',
                                selector: '[data-fb-scraper="main-role"]',
                                index: 0,
                                articles: articles.length,
                                hasCaption: hasCaption
                            };
                        }
                    }

                    return { found: false, totalDialogs: dialogs.length };
                }
            """)

            if not result.get('found'):
                logger.warning(f"Could not find main dialog (found {result.get('totalDialogs', 0)} total dialogs)")
                return

            # Use the marked dialog selector
            dialog_selector = result.get('selector', '[data-fb-scraper="main-dialog"]')
            logger.info(f"Found {result.get('type', 'container')} #{result['index']} with {result['articles']} articles")

            # Expand caption (Click "See more")
            await page.evaluate("""
                (dialogSelector) => {
                    const dialog = document.querySelector(dialogSelector);
                    if (!dialog) return;
                    
                    const buttons = dialog.querySelectorAll('[role="button"]');
                    for (const button of buttons) {
                        const text = (button.innerText || '').toLowerCase();
                        if (text.includes('see more')) {
                            button.click();
                            return;
                        }
                    }
                }
            """, dialog_selector)
            
            await self.random_delay(1.0, 1.5)

            # FIXED: Extract caption using correct selector from individual scraper
            caption = await page.evaluate("""
                (dialogSelector) => {
                    const dialog = document.querySelector(dialogSelector);
                    if (!dialog) return '';

                    // Method 1: Look for caption with data-ad-preview="message" (VERIFIED selector)
                    const captionEl = dialog.querySelector('[data-ad-preview="message"]');
                    if (captionEl) {
                            !text.includes('Professional dashboard')) {
                            return text.trim();
                        }
                    }

                    return '';
                }
            """, dialog_selector)

            logger.info(f"Caption: {caption[:100]}..." if caption else "No caption")

            dialog = await page.query_selector(dialog_selector)
            if not dialog:
                logger.warning("No dialog found for POST")
                return

            max_cycles = 20
            no_new_streak = 0

            for cycle in range(1, max_cycles + 1):
                logger.info(f"=== Cycle {cycle}/{max_cycles} (POST) ===")

                cycle_start = len(self.all_comments)

                # CRITICAL: Click "View more comments" buttons first (from individual scraper)
                clicked = await page.evaluate("""
                    (dialogSelector) => {
                        const dialog = document.querySelector(dialogSelector);
                        if (!dialog) return 0;

                        const buttons = dialog.querySelectorAll('[role="button"]');
                        let clicked = 0;

                        for (const button of buttons) {
                            const text = button.innerText || '';
                            const textLower = text.toLowerCase();

                            // Look for "View more comments", "View previous comments", etc.
                            if ((textLower.includes('view') && textLower.includes('more') && textLower.includes('comment')) ||
                                (textLower.includes('view') && textLower.includes('previous') && textLower.includes('comment')) ||
                                (textLower.includes('view') && textLower.includes('comment')) ||
                                (textLower.includes('see') && textLower.includes('more') && textLower.includes('comment')) ||
                                (textLower.includes('load') && textLower.includes('more')) ||
                                (textLower.includes('show') && textLower.includes('more')) ||
                                // Number + "more" patterns like "62 more"
                                (textLower.includes('more') && /\\d+/.test(text) && text.length < 30)) {

                                // Skip if it's too short or has reaction images
                                if (text.length < 3 || button.querySelector('img')) continue;

                                try {
                                    button.click();
                                    clicked++;
                                } catch (e) {
                                    // Ignore
                                }
                            }
                        }

                        return clicked;
                    }
                """, dialog_selector)

                if clicked > 0:
                    logger.info(f"Clicked {clicked} 'View more comments' buttons")
                    await self.random_delay(2.5, 3.5)

                # FIXED: Pass dialog_selector to expand_replies_post
                await self.expand_replies_post(page, dialog_selector)

                # Scrape comments using helper function
                await self.scrape_post_comments(page, dialog_selector, url, caption)

                # FIXED: Use comprehensive scrolling logic from individual scraper
                scrolled = await page.evaluate("""
                    (dialogSelector) => {
                        const dialog = document.querySelector(dialogSelector);
                        if (!dialog) return {scrolled: false};

                        // Use cached element if available (from previous cycles)
                        let scrollable = window.__fbScrollElement;

                        // If not cached, find it comprehensively
                        if (!scrollable) {
                            // Method 1: Try style attribute
                            scrollable = dialog.querySelector('[style*="overflow"]');

                            // Method 2: Search ALL elements for computed overflow styles
                            if (!scrollable) {
                                const allElements = dialog.querySelectorAll('*');
                                for (const el of allElements) {
                                    const style = window.getComputedStyle(el);
                                    if ((style.overflowY === 'auto' || style.overflowY === 'scroll') &&
                                        el.scrollHeight > el.clientHeight) {
                                        scrollable = el;
                                        window.__fbScrollElement = el;  // Cache it
                                        break;
                                    }
                                }
                            }
                        }

                        if (!scrollable) return {scrolled: false, reason: 'No scrollable element found'};

                        const oldScrollTop = scrollable.scrollTop;
                        const scrollHeight = scrollable.scrollHeight;
                        const clientHeight = scrollable.clientHeight;
                        const maxScroll = scrollHeight - clientHeight;

                        // SMART: Find last visible comment and scroll past it
                        const lastComment = Array.from(dialog.querySelectorAll('[role="article"]')).pop();
                        if (lastComment) {
                            const rect = lastComment.getBoundingClientRect();
                            const containerRect = scrollable.getBoundingClientRect();
                            const relativeTop = rect.top - containerRect.top + scrollable.scrollTop;

                            // Scroll past the last comment by 80% of viewport height
                            const targetScroll = Math.min(relativeTop + clientHeight * 0.8, maxScroll);
                            scrollable.scrollTop = targetScroll;
                        } else {
                            // Fallback: Aggressive scroll
                            const remainingScroll = maxScroll - oldScrollTop;
                            const scrollAmount = Math.max(clientHeight, remainingScroll * 0.8);
                            scrollable.scrollTop = oldScrollTop + scrollAmount;
                        }

                        const newScrollTop = scrollable.scrollTop;
                        const didScroll = newScrollTop > oldScrollTop || oldScrollTop >= maxScroll - 10;

                        return {scrolled: didScroll, from: oldScrollTop, to: newScrollTop};
                    }
                """, dialog_selector)

                if scrolled.get('scrolled'):
                    logger.info(f"Scrolled: {scrolled['from']} → {scrolled['to']}")
                    await self.random_delay(2.0, 3.0)

                    # CRITICAL: Re-click "View more" buttons after scrolling (from individual scraper)
                    view_more2 = await page.evaluate("""
                        (dialogSelector) => {
                            const dialog = document.querySelector(dialogSelector);
                            if (!dialog) return 0;

                            const buttons = dialog.querySelectorAll('[role="button"]');
                            let clicked = 0;

                            for (const button of buttons) {
                                const text = button.innerText || '';
                                const textLower = text.toLowerCase();

                                if ((textLower.includes('view') && textLower.includes('more') && textLower.includes('comment')) ||
                                    (textLower.includes('view') && textLower.includes('previous') && textLower.includes('comment')) ||
                                    (textLower.includes('view') && textLower.includes('comment')) ||
                                    (textLower.includes('see') && textLower.includes('more') && textLower.includes('comment')) ||
                                    (textLower.includes('load') && textLower.includes('more')) ||
                                    (textLower.includes('show') && textLower.includes('more')) ||
                                    (textLower.includes('more') && /\\d+/.test(text) && text.length < 30)) {

                                    if (text.length < 3 || button.querySelector('img')) continue;

                                    try {
                                        button.click();
                                        clicked++;
                                    } catch (e) {}
                                }
                            }

                            return clicked;
                        }
                    """, dialog_selector)

                    if view_more2 > 0:
                        logger.info(f"Re-clicked {view_more2} 'View more comments' buttons after scroll")
                        await self.random_delay(2.0, 3.0)

                    # CRITICAL: Re-expand reply buttons after scrolling (from individual scraper)
                    await self.expand_replies_post(page, dialog_selector)

                    # CRITICAL: Re-scrape comments after expanding (from individual scraper)
                    await self.scrape_post_comments(page, dialog_selector, url, caption)
                else:
                    logger.info("Cannot scroll further (at bottom or no scroll)")

                cycle_new = len(self.all_comments) - cycle_start
                logger.info(f"Cycle {cycle}: Found {cycle_new} new (Total: {len(self.all_comments)})")

                if cycle_new == 0:
                    no_new_streak += 1
                    if no_new_streak >= 3:
                        logger.info(f"No new comments for {no_new_streak} cycles. Done.")
                        break
                else:
                    no_new_streak = 0

            logger.info(f"✅ POST complete: {len(self.all_comments)} total comments")

        except Exception as e:
            logger.error(f"Error scraping POST {url}: {e}")
            raise

    async def scrape_url(self, page: Page, url: str, url_type: str):
        """Route to appropriate scraper based on URL type"""
        if url_type == 'WATCH':
            await self.scrape_watch(page, url)
        elif url_type == 'REEL':
            await self.scrape_reel(page, url)
        else:  # POST
            await self.scrape_post(page, url)

    async def run(self):
        """Main execution in full headless mode with fresh pages per URL"""
        # Load URLs
        urls_file = self.BASE_DIR / "config" / "urls.txt"
        with open(urls_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        # Load cookies
        cookies_file = self.BASE_DIR / "config" / "cookies.json"
        with open(cookies_file, 'r') as f:
            cookies = json.load(f)

        cookies = self.sanitize_cookies(cookies)

        logger.info(f"{'='*80}")
        logger.info(f"Facebook Scraper - Full Headless Mode")
        logger.info(f"{'='*80}")
        logger.info(f"URLs to process: {len(urls)}")
        logger.info(f"Cookies loaded: {len(cookies)}")
        logger.info(f"Mode: HEADLESS (fresh page per URL)")
        logger.info(f"{'='*80}\n")

        async with async_playwright() as playwright:
            # Create browser and context once
            browser, context = await self.create_browser_and_context(playwright, cookies)
            logger.info(f"✓ Browser launched in headless mode\n")

            for idx, url in enumerate(urls, 1):
                logger.info(f"{'='*80}")
                logger.info(f"URL {idx}/{len(urls)}")
                logger.info(f"{'='*80}")

                url_type = self.determine_url_type(url)
                logger.info(f"Type: {url_type}")
                logger.info(f"URL: {url}")

                # CRITICAL FIX: Create fresh page for each URL
                page = await context.new_page()
                logger.info(f"✓ Created fresh page")

                try:
                    # Route to appropriate scraper
                    if url_type == 'WATCH':
                        await self.scrape_watch(page, url)
                    elif url_type == 'REEL':
                        await self.scrape_reel(page, url)
                    else:  # POST
                        await self.scrape_post(page, url)

                    logger.info(f"✓ Successfully scraped {url_type}")

                except Exception as e:
                    logger.error(f"✗ Error scraping {url_type}: {e}")
                    self.failed_urls.append(url)

                finally:
                    # CRITICAL: Always close page after scraping
                    await page.close()
                    logger.info(f"✓ Closed page")

                # Delay between URLs
                if idx < len(urls):
                    logger.info(f"\n⏳ Waiting 5 seconds before next URL...\n")
                    await asyncio.sleep(5)

            await browser.close()
            logger.info(f"\n✓ Browser closed")

        # Save results
        if self.all_comments:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = self.BASE_DIR / "output" / f"facebook_comments_fullheadless_{timestamp}.csv"

            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=['URL', 'Type', 'Caption', 'Commenter', 'Comment'])
                writer.writeheader()
                writer.writerows(self.all_comments)

            logger.info(f"\n{'='*80}")
            logger.info(f"RESULTS")
            logger.info(f"{'='*80}")
            logger.info(f"✅ Total comments: {len(self.all_comments)}")
            logger.info(f"📁 Saved to: {output_file}")

            if self.failed_urls:
                logger.warning(f"\n⚠️  Failed URLs ({len(self.failed_urls)}):")
                for failed_url in self.failed_urls:
                    logger.warning(f"  - {failed_url}")
            else:
                logger.info(f"🎉 All URLs processed successfully!")

            logger.info(f"{'='*80}\n")
        else:
            logger.warning("\n⚠️  No comments found!")


if __name__ == "__main__":
    # Full headless mode with fresh page management
    scraper = FacebookScraperFullHeadless()
    asyncio.run(scraper.run())
