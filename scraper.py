"""
Facebook Comment Scraper Module
Full scraping logic integrated with web app
Includes multi-cycle scraping, button clicking, and smart scrolling
"""

import asyncio
import csv
import re
import random
import traceback
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser
from typing import List, Dict, Set, Callable, Optional

class FacebookCommentScraper:
    def __init__(self, viewport_size='13_inch', log_callback: Optional[Callable] = None):
        self.all_comments: List[Dict] = []
        self.processed_texts: Set[str] = set()
        self.log_callback = log_callback or print
        self.should_stop = False

        # Viewport settings
        viewports = {
            '13_inch': {'width': 1280, 'height': 800},
            '16_inch': {'width': 1920, 'height': 1080}
        }
        self.VIEWPORT = viewports.get(viewport_size, viewports['13_inch'])

    def log(self, message: str):
        """Log message using callback"""
        if self.log_callback:
            self.log_callback(message)

    def stop(self):
        """Signal scraper to stop"""
        self.should_stop = True
        self.log("⏹️ Stopping scraper...")

    async def random_delay(self, min_sec: float = 0.2, max_sec: float = 0.4):
        """Random delay to mimic human behavior"""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    def sanitize_cookies(self, cookies: List[Dict]) -> List[Dict]:
        """Fix cookie format for Playwright"""
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

    def determine_url_type(self, url: str) -> str:
        """Determine if URL is WATCH, REEL, or POST"""
        url_lower = url.lower()
        watch_patterns = ['/watch/', 'watch?v=', '/video/', '/videos/', '/live/', '/media/']
        if any(pattern in url_lower for pattern in watch_patterns):
            return 'WATCH'
        reel_patterns = ['/reel/', '/reels/']
        if any(pattern in url_lower for pattern in reel_patterns):
            return 'REEL'
        return 'POST'

    def extract_name_from_aria(self, aria_label: str) -> str:
        """Extract commenter name with timestamp removal - supports English and Thai"""
        if not aria_label:
            return "Unknown"

        if 'Reply by' in aria_label:
            match = re.search(r'Reply by (.+?) to', aria_label)
            if match:
                return match.group(1).strip()
            name = aria_label.replace('Reply by ', '').split(' to ')[0].strip()
        elif 'Comment by' in aria_label:
            match = re.search(r'Comment by (.+?)(?:\s+(?:about\s+)?(?:a\s+(?:few\s+)?)?(?:an\s+)?(?:\d+\s+)?(?:second|minute|hour|day|week|month|year)s?\s+ago|,|$)', aria_label)
            if match:
                return match.group(1).strip()
            name = aria_label.replace('Comment by', '').split(',')[0].strip()
        elif 'ความคิดเห็นโดย' in aria_label:
            match = re.search(r'ความคิดเห็นโดย\s+(.+?)(?:\s+เมื่อ|,|$)', aria_label)
            if match:
                return match.group(1).strip()
            name = aria_label.replace('ความคิดเห็นโดย', '').split('เมื่อ')[0].strip()
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

    async def scrape_post_comments(self, page: Page, dialog_selector: str, url: str, caption: str) -> int:
        """Scrape visible comments from POST dialog"""
        if self.should_stop:
            return 0

        new_count = 0
        articles = await page.query_selector_all(f'{dialog_selector} [role="article"]')
        
        # self.log(f"  DEBUG: Found {len(articles)} articles in cycle")

        for article in articles:
            if self.should_stop:
                break

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
                    # self.log(f"  DEBUG: Skipped article - No name found")
                    continue

                text_divs = await article.query_selector_all('div[dir="auto"]')
                comment_text = ""

                for div in text_divs:
                    div_text = await div.inner_text()
                    if div_text and self.is_meaningful_text(div_text):
                        # Avoid capturing the name as the comment
                        if div_text.strip() != name:
                            comment_text = div_text.strip()
                            break

                if not comment_text:
                    # self.log(f"  DEBUG: Skipped article - No meaningful text")
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
                self.log(f"  Comment #{len(self.all_comments)}: {name}: {comment_text[:50]}...")

            except Exception as e:
                # self.log(f"  DEBUG: Error processing article: {e}")
                continue

        return new_count

    async def expand_replies_post(self, page: Page, dialog_selector: str) -> int:
        """Expand reply threads in POST dialog"""
        if self.should_stop:
            return 0

        expanded = await page.evaluate("""
            (dialogSelector) => {
                const dialog = document.querySelector(dialogSelector);
                if (!dialog) return 0;

                const buttons = dialog.querySelectorAll('[role="button"]');
                let clicked = 0;

                for (const button of buttons) {
                    const text = (button.innerText || '').toLowerCase();

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
            self.log(f"  Expanded {expanded} reply threads")
            await self.random_delay(1.5, 2.0)

        return expanded

    async def scrape_post(self, page: Page, url: str):
        """Scrape POST comments with multi-cycle approach"""
        self.log(f"Scraping POST: {url}")

        try:
            # FIXED: Remove wait_until to match working core logic
            await page.goto(url, timeout=60000)
            self.log(f"  ✓ Navigation completed")

            # DIAGNOSTIC: Wait longer for Facebook to load
            await self.random_delay(5.0, 7.0)
            self.log(f"  Waiting for page to fully load...")

            # DIAGNOSTIC: Check what page we're actually on
            page_title = await page.title()
            page_url = page.url
            self.log(f"  Page title: {page_title[:100]}")
            self.log(f"  Current URL: {page_url[:100]}")

            # Find the correct dialog - MATCH ORIGINAL CODE EXACTLY
            result = await page.evaluate("""
                () => {
                    // 1. Try to find in dialogs (modal mode)
                    const dialogs = document.querySelectorAll('[role="dialog"]');

                    for (let i = 0; i < dialogs.length; i++) {
                        const dialog = dialogs[i];
                        const hasCaption = dialog.querySelector('[data-ad-preview="message"]') !== null;
                        const articles = dialog.querySelectorAll('[role="article"]');

                        if (hasCaption) {
                            dialog.setAttribute('data-fb-scraper', 'main-dialog');
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
                        
                        // In full page mode, we might not find caption immediately if it's a shared post
                        // But if we have articles (comments) and it's the main role, it's likely the post
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

            # Log result
            if result.get('found'):
                self.log(f"  ✓ Found {result.get('type', 'container')} #{result['index']} with {result['articles']} articles")

            if not result.get('found'):
                self.log(f"  ⚠️ Could not find main dialog with comments")
                return

            dialog_selector = result.get('selector', '[data-fb-scraper="main-dialog"]')
            self.log(f"  ✓ Using selector: {dialog_selector}")

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

            # Extract caption
            caption = await page.evaluate("""
                (dialogSelector) => {
                    const dialog = document.querySelector(dialogSelector);
                    if (!dialog) return '';

                    const captionEl = dialog.querySelector('[data-ad-preview="message"]');
                    if (captionEl) {
                        return captionEl.innerText || '';
                    }
                    
                    // Fallback: Look for the largest text block that isn't a comment
                    const allDivs = dialog.querySelectorAll('div[dir="auto"]');
                    for (const div of allDivs) {
                        // Skip if inside an article (comment)
                        if (div.closest('[role="article"]')) continue;
                        
                        const text = div.innerText || '';
                        if (text.length > 20) return text;
                    }

                    return '';
                }
            """, dialog_selector)

            self.log(f"  Caption: {caption[:100]}..." if caption else "  No caption")

            max_cycles = 20
            no_new_streak = 0

            for cycle in range(1, max_cycles + 1):
                if self.should_stop:
                    break

                self.log(f"  === Cycle {cycle}/{max_cycles} ===")
                cycle_start = len(self.all_comments)

                # Click "View more comments" buttons
                clicked = await page.evaluate("""
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
                                } catch (e) {
                                    // Ignore
                                }
                            }
                        }

                        return clicked;
                    }
                """, dialog_selector)

                if clicked > 0:
                    self.log(f"  Clicked {clicked} 'View more comments' buttons")
                    await self.random_delay(2.5, 3.5)

                # Expand replies
                await self.expand_replies_post(page, dialog_selector)

                # Scrape comments
                await self.scrape_post_comments(page, dialog_selector, url, caption or "No caption")

                # Smart scrolling
                scrolled = await page.evaluate("""
                    (dialogSelector) => {
                        const dialog = document.querySelector(dialogSelector);
                        if (!dialog) return {scrolled: false};

                        let scrollable = window.__fbScrollElement;

                        if (!scrollable) {
                            scrollable = dialog.querySelector('[style*="overflow"]');

                            if (!scrollable) {
                                const allElements = dialog.querySelectorAll('*');
                                for (const el of allElements) {
                                    const style = window.getComputedStyle(el);
                                    if ((style.overflowY === 'auto' || style.overflowY === 'scroll') &&
                                        el.scrollHeight > el.clientHeight) {
                                        scrollable = el;
                                        window.__fbScrollElement = el;
                                        break;
                                    }
                                }
                            }
                        }

                        if (!scrollable) return {scrolled: false, reason: 'No scrollable element'};

                        const oldScrollTop = scrollable.scrollTop;
                        const scrollHeight = scrollable.scrollHeight;
                        const clientHeight = scrollable.clientHeight;
                        const maxScroll = scrollHeight - clientHeight;

                        const lastComment = Array.from(dialog.querySelectorAll('[role="article"]')).pop();
                        if (lastComment) {
                            const rect = lastComment.getBoundingClientRect();
                            const containerRect = scrollable.getBoundingClientRect();
                            const relativeTop = rect.top - containerRect.top + scrollable.scrollTop;

                            const targetScroll = Math.min(relativeTop + clientHeight * 0.8, maxScroll);
                            scrollable.scrollTop = targetScroll;
                        } else {
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
                    self.log(f"  Scrolled: {scrolled['from']} → {scrolled['to']}")
                    await self.random_delay(2.0, 3.0)

                    # Re-click buttons after scrolling
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
                        self.log(f"  Re-clicked {view_more2} buttons after scroll")
                        await self.random_delay(2.0, 3.0)

                    # Re-expand replies
                    await self.expand_replies_post(page, dialog_selector)

                    # Re-scrape comments
                    await self.scrape_post_comments(page, dialog_selector, url, caption or "No caption")

                cycle_new = len(self.all_comments) - cycle_start
                self.log(f"  Cycle {cycle}: Found {cycle_new} new (Total: {len(self.all_comments)})")

                if cycle_new == 0:
                    no_new_streak += 1
                    if no_new_streak >= 3:
                        self.log(f"  No new comments for {no_new_streak} cycles. Done.")
                        break
                else:
                    no_new_streak = 0

            self.log(f"  ✅ POST complete: {len(self.all_comments)} total comments")

        except Exception as e:
            self.log(f"  ❌ Error scraping POST: {str(e)}")
            raise

    async def click_view_more_watch(self, page: Page) -> bool:
        """Click 'View more comments' button for WATCH videos"""
        if self.should_stop:
            return False

        result = await page.evaluate("""
            () => {
                const main = document.querySelector('[role="main"]');
                if (!main) return {clicked: false};

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

                return {clicked: false};
            }
        """)

        if result.get('clicked'):
            self.log(f"  ✓ Clicked: {result.get('text', 'View more comments')}")
            await self.random_delay(2.0, 3.0)
            return True

        return False

    async def expand_replies_watch(self, page: Page) -> int:
        """Expand reply threads in WATCH videos"""
        if self.should_stop:
            return 0

        result = await page.evaluate("""
            () => {
                const main = document.querySelector('[role="main"]');
                if (!main) return {expanded: 0};

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
            self.log(f"  Expanded {count} reply threads")
            await self.random_delay(1.0, 2.0)

        return count

    async def scrape_watch(self, page: Page, url: str):
        """Scrape WATCH video comments"""
        self.log(f"Scraping WATCH: {url}")

        try:
            # FIXED: Remove wait_until to match working core logic
            await page.goto(url, timeout=60000)
            await self.random_delay(3.0, 5.0)

            # Extract caption
            caption = await page.evaluate("""
                () => {
                    const main = document.querySelector('[role="main"]');
                    if (!main) return '';

                    const spans = main.querySelectorAll('span.x193iq5w, span.x1lliihq');
                    for (const span of spans) {
                        const text = span.innerText || '';
                        if (text.length > 10 &&
                            !text.includes('Comments') &&
                            !text.includes('Explore more') &&
                            !text.includes('Latest videos')) {
                            return text;
                        }
                    }

                    return '';
                }
            """)

            self.log(f"  Caption: {caption[:100]}..." if caption else "  No caption")

            # Initial scroll
            await page.evaluate("window.scrollBy(0, 500)")
            await self.random_delay(2.0, 3.0)

            max_cycles = 30
            no_new_streak = 0

            for cycle in range(1, max_cycles + 1):
                if self.should_stop:
                    break

                self.log(f"  === Cycle {cycle}/{max_cycles} ===")
                cycle_start = len(self.all_comments)

                await self.click_view_more_watch(page)
                await self.expand_replies_watch(page)

                articles = await page.query_selector_all('[role="main"] [role="article"]')

                for article in articles:
                    if self.should_stop:
                        break

                    try:
                        aria_label = await article.get_attribute('aria-label')

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
                            'Caption': caption or "No caption",
                            'Commenter': name,
                            'Comment': comment_text
                        })

                        self.log(f"  Comment #{len(self.all_comments)}: {name}: {comment_text[:50]}...")

                    except Exception as e:
                        continue

                cycle_new = len(self.all_comments) - cycle_start
                self.log(f"  Cycle {cycle}: Found {cycle_new} new (Total: {len(self.all_comments)})")

                if cycle_new == 0:
                    no_new_streak += 1
                    if no_new_streak >= 4:
                        self.log(f"  No new comments for {no_new_streak} cycles. Done.")
                        break
                else:
                    no_new_streak = 0

            self.log(f"  ✅ WATCH complete: {len(self.all_comments)} total comments")

        except Exception as e:
            self.log(f"  ❌ Error scraping WATCH: {str(e)}")
            raise

    async def open_reel_comments(self, page: Page) -> bool:
        """Open REEL comments section"""
        if self.should_stop:
            return False

        for attempt in range(3):
            container = await page.query_selector('div[role="complementary"]')
            if container:
                try:
                    is_visible = await container.is_visible()
                    if is_visible:
                        comments = await page.query_selector_all("div[role='complementary'] div[role='article']")
                        if len(comments) > 0:
                            self.log(f"  Comments auto-loaded with {len(comments)} comments")
                            return True
                except:
                    pass

            if attempt < 2:
                await self.random_delay(0.5, 0.8)

        # Try to click comment button
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
                        self.log(f"  Found comment button")
                        break
            except:
                continue

        if button:
            try:
                await button.scroll_into_view_if_needed()
                await self.random_delay(0.3, 0.5)
                await button.click()
                self.log("  Clicked comment button")
                await self.random_delay(2.0, 3.0)
                return True
            except Exception as e:
                self.log(f"  Error clicking comment button: {e}")

        return False

    async def click_view_more_reel(self, page: Page) -> bool:
        """Click 'View more comments' button for REEL"""
        if self.should_stop:
            return False

        result = await page.evaluate("""
            () => {
                const comp = document.querySelector('[role="complementary"]');
                if (!comp) return {clicked: false};

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

                return {clicked: false};
            }
        """)

        if result.get('clicked'):
            self.log(f"  ✓ Clicked: {result.get('text', 'View more comments')}")
            await self.random_delay(2.0, 3.0)
            return True

        return False

    async def expand_replies_reel(self, page: Page) -> int:
        """Expand reply threads in REEL"""
        if self.should_stop:
            return 0

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
            self.log(f"  Expanded {count} reply threads")
            await self.random_delay(1.0, 2.0)

        return count

    async def scrape_reel(self, page: Page, url: str):
        """Scrape REEL comments"""
        self.log(f"Scraping REEL: {url}")

        try:
            # FIXED: Remove wait_until to match working core logic
            await page.goto(url, timeout=60000)
            await self.random_delay(3.0, 5.0)

            await self.open_reel_comments(page)

            # Click "See more" to expand caption
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
                self.log("  Clicked 'See more' to expand caption")
                await self.random_delay(1.0, 1.5)

            # Extract caption
            caption = await page.evaluate("""
                () => {
                    const comp = document.querySelector('[role="complementary"]');
                    if (!comp) return null;

                    const spans = comp.querySelectorAll('span.x193iq5w, span.x1lliihq');

                    for (const span of spans) {
                        if (span.closest('[role="article"]')) continue;

                        const text = span.innerText || '';

                        if (text.length > 30 &&
                            !text.includes('Comment by') &&
                            !text.includes('Reply by') &&
                            !text.includes('replied') &&
                            !text.match(/^\\d+[wdhm]/)) {

                            return text.replace(/…?\\s*See more$/i, '').replace(/\\s*See less$/i, '').trim();
                        }
                    }

                    return null;
                }
            """)

            self.log(f"  Caption: {caption[:100]}..." if caption else "  No caption")

            max_cycles = 50
            no_new_streak = 0

            for cycle in range(1, max_cycles + 1):
                if self.should_stop:
                    break

                self.log(f"  === Cycle {cycle}/{max_cycles} ===")
                cycle_start = len(self.all_comments)

                await self.click_view_more_reel(page)
                await self.expand_replies_reel(page)

                articles = await page.query_selector_all('div[role="complementary"] div[role="article"]')

                for article in articles:
                    if self.should_stop:
                        break

                    try:
                        aria_label = await article.get_attribute('aria-label')

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
                            'Caption': caption or "No caption",
                            'Commenter': name,
                            'Comment': comment_text
                        })

                        self.log(f"  Comment #{len(self.all_comments)}: {name}: {comment_text[:50]}...")

                    except Exception as e:
                        continue

                cycle_new = len(self.all_comments) - cycle_start
                self.log(f"  Cycle {cycle}: Found {cycle_new} new (Total: {len(self.all_comments)})")

                if cycle_new == 0:
                    no_new_streak += 1
                    if no_new_streak >= 3:
                        self.log(f"  No new comments for {no_new_streak} cycles. Done.")
                        break
                else:
                    no_new_streak = 0

            self.log(f"  ✅ REEL complete: {len(self.all_comments)} total comments")

        except Exception as e:
            self.log(f"  ❌ Error scraping REEL: {str(e)}")
            raise

    async def scrape_url(self, context, url: str, url_index: int, total_urls: int):
        """Scrape a single URL using shared context with fresh page (from working core logic)"""
        if self.should_stop:
            return

        self.log(f"[{url_index}/{total_urls}] {url}")

        url_type = self.determine_url_type(url)
        self.log(f"  Type: {url_type}")

        # CRITICAL FIX: Create fresh PAGE (not context) for each URL
        # Page creation is now inside try block for proper error handling
        try:
            page = await context.new_page()
            self.log(f"  ✓ Created fresh page")

            if url_type == 'POST':
                await self.scrape_post(page, url)
            elif url_type == 'WATCH':
                await self.scrape_watch(page, url)
            else:
                await self.scrape_reel(page, url)

            self.log(f"  ✓ Successfully scraped {url_type}")

        except Exception as e:
            self.log(f"  ❌ Error scraping {url_type}: {str(e)}")
        finally:
            # CRITICAL: Always close page after scraping
            try:
                await page.close()
                self.log(f"  ✓ Closed page")
            except Exception as close_error:
                self.log(f"  ⚠️  Page close warning: {str(close_error)}")

    async def scrape_urls(self, urls: List[str], cookies: List[Dict]) -> Dict:
        """Main scraping function"""
        try:
            self.all_comments = []
            self.processed_texts = set()
            self.should_stop = False

            cookies_sanitized = self.sanitize_cookies(cookies)

            async with async_playwright() as playwright:
                # CRITICAL: Comprehensive browser args for cross-platform stability
                # Includes fixes for Linux, Docker, containers, and resource-constrained environments
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',                          # Essential for containers/Docker
                        '--disable-setuid-sandbox',              # Essential for containers/Docker
                        '--disable-dev-shm-usage',               # CRITICAL for limited /dev/shm (Linux/Docker)
                        '--disable-gpu',                         # Prevent GPU crashes
                        '--disable-software-rasterizer',         # Prevent software rendering issues
                        '--disable-extensions',                  # Reduce overhead
                        '--disable-blink-features=AutomationControlled',  # Reduce detection
                        '--no-first-run',                        # Skip first-run setup
                        '--no-default-browser-check',            # Skip browser check
                        '--disable-background-networking',       # Reduce resource usage
                        '--disable-background-timer-throttling', # Prevent timeouts
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding',
                        '--disable-features=TranslateUI',        # Disable translate popups
                        '--disable-ipc-flooding-protection',     # Prevent IPC issues
                        '--disable-hang-monitor',                # Prevent hang detection
                    ]
                )

                # CRITICAL FIX: Create ONE context for all URLs (from working core logic)
                # This prevents "target closed" errors from repeatedly creating/destroying contexts
                context = await browser.new_context(
                    viewport=self.VIEWPORT,
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                await context.add_cookies(cookies_sanitized)
                self.log(f"✓ Created browser context with {len(cookies_sanitized)} cookies")

                # STABILITY: Let context fully initialize
                await asyncio.sleep(1.0)

                # HEALTH CHECK: Verify browser is working before scraping
                try:
                    self.log("Running browser health check...")
                    test_page = await context.new_page()
                    await test_page.goto('about:blank', timeout=10000)
                    await test_page.close()
                    self.log("✓ Browser health check passed")
                except Exception as health_error:
                    self.log(f"❌ Browser health check FAILED: {health_error}")
                    self.log("⚠️  Browser may be unstable. Try: 1) Reinstall Playwright browsers, 2) Check system resources")
                    raise Exception(f"Browser initialization failed: {health_error}")

                # Process URLs with shared context
                for idx, url in enumerate(urls, 1):
                    if self.should_stop:
                        self.log("⏹️ Stopped by user")
                        break

                    await self.scrape_url(context, url, idx, len(urls))

                    # CRITICAL: Delay between URLs (from original working code)
                    # Gives browser/context time to clean up after closing page
                    if idx < len(urls):
                        self.log("⏳ Waiting 3 seconds before next URL...")
                        await asyncio.sleep(3.0)

                # Close browser gracefully
                try:
                    await browser.close()
                except Exception as close_error:
                    self.log(f"⚠️  Browser close warning: {str(close_error)}")

            # Save results
            if self.all_comments:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_file = f'output/facebook_comments_{timestamp}.csv'

                with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=['URL', 'Type', 'Caption', 'Commenter', 'Comment'])
                    writer.writeheader()
                    writer.writerows(self.all_comments)

                return {
                    'success': True,
                    'output_file': output_file,
                    'total_comments': len(self.all_comments)
                }
            else:
                return {
                    'success': False,
                    'error': 'No comments found'
                }

        except Exception as e:
            self.log(f"⚠️  Error occurred: {str(e)}")

            # Save what we collected, even if there was an error
            if self.all_comments:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_file = f'output/facebook_comments_{timestamp}.csv'

                try:
                    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                        writer = csv.DictWriter(f, fieldnames=['URL', 'Type', 'Caption', 'Commenter', 'Comment'])
                        writer.writeheader()
                        writer.writerows(self.all_comments)

                    self.log(f"✅ Saved {len(self.all_comments)} comments despite error")

                    return {
                        'success': True,
                        'output_file': output_file,
                        'total_comments': len(self.all_comments),
                        'warning': str(e)
                    }
                except Exception as save_error:
                    self.log(f"❌ Could not save CSV: {str(save_error)}")
                    return {
                        'success': False,
                        'error': f"Scraping error: {str(e)}, Save error: {str(save_error)}"
                    }
            else:
                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                self.log(f"❌ Error details: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
