"""
Atria Ad Spy Platform Scraper

This module handles:
- Authentication with Atria
- Searching for competitor ads
- Filtering ads by duration (7+ days, 21+ days)
- Downloading ad videos/images
- Extracting ad metadata
"""
import asyncio
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import aiofiles
import aiohttp
from loguru import logger
from playwright.async_api import async_playwright, Page, Browser

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config import ATRIA_CONFIG, RAW_ADS_DIR, FILTER_CONFIG, COMPETITORS


class AtriaScraper:
    """Scraper for Atria ad spy platform."""
    
    def __init__(self):
        self.email = ATRIA_CONFIG['email']
        self.password = ATRIA_CONFIG['password']
        self.base_url = ATRIA_CONFIG['base_url']
        self.login_url = ATRIA_CONFIG['login_url']
        self.discovery_url = ATRIA_CONFIG['discovery_url']
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.session_cookies = None
        self.min_days_active = FILTER_CONFIG['min_days_active']
        # Store captured video URLs from network requests
        self.captured_video_urls: dict[str, str] = {}
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        
    async def initialize(self):
        """Initialize the browser instance."""
        logger.info("Initializing Atria scraper...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        self.page = await self.context.new_page()
        
        # Set up network request interception to capture video URLs
        self.page.on("response", self._handle_response)
        
        logger.info("Browser initialized successfully")
    
    async def _handle_response(self, response):
        """
        Handle network responses to capture video URLs.
        This intercepts all responses and looks for video files.
        """
        try:
            url = response.url
            content_type = response.headers.get('content-type', '')
            
            # Check if this is a video file
            is_video = (
                '.mp4' in url.lower() or 
                '.webm' in url.lower() or
                'video/' in content_type.lower() or
                '/video' in url.lower()
            )
            
            if is_video and response.status == 200:
                # Extract ad identifier from URL
                # Atria CDN pattern: adfiles/m{id}_{hash}.mp4
                ad_id_match = re.search(r'adfiles/(m\d+)', url)
                if ad_id_match:
                    ad_identifier = ad_id_match.group(1)
                    self.captured_video_urls[ad_identifier] = url
                    logger.info(f"Captured video URL for {ad_identifier}: {url[:80]}...")
                else:
                    # Store by full filename
                    filename_match = re.search(r'/([^/]+\.(?:mp4|webm))(?:\?|$)', url, re.IGNORECASE)
                    if filename_match:
                        filename = filename_match.group(1)
                        self.captured_video_urls[filename] = url
                        logger.info(f"Captured video URL: {url[:80]}...")
        except Exception as e:
            logger.debug(f"Error handling response: {e}")
        
    async def close(self):
        """Close browser and cleanup."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser closed")
        
    async def login(self, max_retries: int = 3) -> bool:
        """
        Login to Atria platform with retry logic.
        
        Args:
            max_retries: Maximum number of login attempts
            
        Returns:
            bool: True if login successful, False otherwise
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"Login attempt {attempt + 1}/{max_retries}")
                logger.info(f"Navigating to login page: {self.login_url}")
                
                # Navigate with longer timeout
                await self.page.goto(self.login_url, wait_until='domcontentloaded', timeout=120000)
                await asyncio.sleep(3)
                
                # Wait for page to be ready
                try:
                    await self.page.wait_for_load_state('networkidle', timeout=30000)
                except Exception:
                    logger.warning("Network idle timeout, proceeding anyway")
                
                # Fill in email
                logger.info("Filling in credentials...")
                email_input = await self.page.wait_for_selector(
                    'input[name="email"], input[type="email"], input[placeholder*="email" i]', 
                    timeout=20000
                )
                await email_input.click()
                await asyncio.sleep(0.5)
                await email_input.fill('')  # Clear first
                await email_input.type(self.email, delay=30)  # Type slowly
                
                await asyncio.sleep(0.5)
                
                # Fill in password
                password_input = await self.page.wait_for_selector(
                    'input[name="password"], input[type="password"]', 
                    timeout=20000
                )
                await password_input.click()
                await asyncio.sleep(0.5)
                await password_input.fill('')  # Clear first
                await password_input.type(self.password, delay=30)  # Type slowly
                
                await asyncio.sleep(0.5)
                
                # Click login button
                login_button = await self.page.wait_for_selector(
                    'button[type="submit"], button:has-text("Log in")', 
                    timeout=20000
                )
                await login_button.click()
                
                # Wait for navigation to complete
                logger.info("Waiting for login to complete...")
                await asyncio.sleep(8)
                
                # Try to wait for navigation
                try:
                    await self.page.wait_for_load_state('networkidle', timeout=15000)
                except Exception:
                    pass
                
                # Check if login was successful by looking for dashboard elements
                current_url = self.page.url
                if 'login' not in current_url.lower():
                    logger.success("Login successful!")
                    # Save cookies for future use
                    self.session_cookies = await self.context.cookies()
                    return True
                else:
                    logger.warning(f"Login attempt {attempt + 1} failed - still on login page")
                    # Take screenshot for debugging
                    await self.page.screenshot(path=str(RAW_ADS_DIR / f'login_failed_attempt{attempt + 1}.png'))
                    
                    if attempt < max_retries - 1:
                        logger.info("Retrying login...")
                        await asyncio.sleep(3)
                    
            except asyncio.TimeoutError as e:
                logger.warning(f"Login attempt {attempt + 1} timed out: {e}")
                if attempt < max_retries - 1:
                    logger.info("Retrying after timeout...")
                    await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Login error on attempt {attempt + 1}: {e}")
                try:
                    await self.page.screenshot(path=str(RAW_ADS_DIR / f'login_error_attempt{attempt + 1}.png'))
                except Exception:
                    pass
                    
                if attempt < max_retries - 1:
                    await asyncio.sleep(3)
        
        logger.error("All login attempts failed")
        return False
    
    async def search_competitor_ads(self, competitor: dict) -> list[dict]:
        """
        Search for ads from a specific competitor.
        
        Args:
            competitor: Competitor configuration dict with name, domain, and filter
            
        Returns:
            List of ad metadata dictionaries
        """
        ads = []
        domain = competitor['domain']
        filter_keyword = competitor.get('filter')
        
        try:
            # Build search query: domain + filter keyword (e.g., "sereneherbs.com+GLP1")
            if filter_keyword:
                search_query = f"{domain}+{filter_keyword}"
            else:
                search_query = domain
            
            logger.info(f"Searching ads for competitor: {domain} (query: {search_query})")
            
            # Navigate directly to discovery URL with search parameters
            # This is more reliable than typing in the search box
            # format=video filters for video ads, status=active shows only active ads
            search_url = f"{self.discovery_url}?format=video&status=active&q={search_query}&searchType=ad_copy&sortBy=most_relevant"
            logger.info(f"Navigating to: {search_url}")
            
            await self.page.goto(search_url, wait_until='domcontentloaded', timeout=120000)
            await asyncio.sleep(5)  # Wait for page to load
            
            # Wait for network to settle
            try:
                await self.page.wait_for_load_state('networkidle', timeout=30000)
            except Exception:
                logger.warning("Network idle timeout, proceeding anyway")
            
            await asyncio.sleep(3)  # Additional wait for content to render
            
            # Take screenshot for debugging
            await self.page.screenshot(path=str(RAW_ADS_DIR / f'search_results_{domain}.png'))
            
            # Try to find and apply filters (active for 7+ days)
            await self._apply_duration_filter()
            
            # Scroll and collect ads
            ads = await self._collect_ads_from_page(competitor)
            
            logger.info(f"Found {len(ads)} ads for {domain}")
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout searching ads for {domain}")
            await self.page.screenshot(path=str(RAW_ADS_DIR / f'search_error_{domain}.png'))
        except Exception as e:
            logger.error(f"Error searching ads for {domain}: {e}")
            await self.page.screenshot(path=str(RAW_ADS_DIR / f'search_error_{domain}.png'))
            
        return ads
    
    async def _apply_duration_filter(self):
        """Apply filter for ads active for minimum days (7+ days)."""
        try:
            # In Atria, the "Status" dropdown contains duration options
            # Try to click Status button/dropdown first
            status_selectors = [
                'button:has-text("Status")',
                '[data-testid="status-filter"]',
                'div:has-text("Status") >> button',
            ]
            
            status_clicked = False
            for selector in status_selectors:
                try:
                    status_element = await self.page.query_selector(selector)
                    if status_element:
                        await status_element.click()
                        await asyncio.sleep(1)
                        status_clicked = True
                        logger.info("Clicked Status dropdown")
                        break
                except Exception:
                    continue
            
            if status_clicked:
                # Look for "Active for 7+ days" or similar options
                duration_options = [
                    'text="Active for 7+ days"',
                    'text="7+ days"',
                    'text="Running 7+ days"',
                    'text="Active 7+ days"',
                    ':text("7+ days")',
                    ':text("7 days")',
                ]
                
                for option in duration_options:
                    try:
                        option_element = await self.page.query_selector(option)
                        if option_element:
                            await option_element.click()
                            await asyncio.sleep(2)
                            logger.info(f"Applied duration filter: 7+ days active")
                            return
                    except Exception:
                        continue
                        
                # Close the dropdown if no option found
                await self.page.keyboard.press('Escape')
                    
            logger.warning("Could not find duration filter, proceeding without it")
            
        except Exception as e:
            logger.warning(f"Error applying duration filter: {e}")
    
    async def _collect_ads_from_page(self, competitor: dict, max_scroll: int = 10) -> list[dict]:
        """
        Collect ad data from the current page with scrolling.
        
        Args:
            competitor: Competitor configuration
            max_scroll: Maximum number of scroll iterations
            
        Returns:
            List of ad metadata dictionaries
        """
        ads = []
        seen_ids = set()
        
        # Clear captured video URLs for this page
        self.captured_video_urls.clear()
        
        for scroll_count in range(max_scroll):
            # Get the page content to debug
            if scroll_count == 0:
                # Log page structure for debugging
                page_text = await self.page.inner_text('body')
                logger.debug(f"Page text sample: {page_text[:500]}...")
            
            # Atria uses card-based layout - try multiple selectors
            # Based on the actual Atria UI structure
            ad_card_selectors = [
                # Specific Atria card selectors (based on observed structure)
                'div[class*="Card"]:has(button:has-text("Shop"))',
                'div[class*="Card"]:has(span:has-text(".com"))',
                'div:has(button:has-text("Shop Now"))',
                'div:has(button:has-text("Shop now"))',
                # Cards with domain text visible
                'div:has(span:has-text(".com")):has(video)',
                'div:has(span:has-text(".com")):has(img)',
                # Main ad card containers
                '[class*="AdCard"]',
                '[class*="ad-card"]',
                '[class*="creative-card"]',
                # Cards in the main content area with video or Shop button
                'main div:has(video)',
                'main div:has(button:has-text("Shop"))',
                # Generic grid items that contain shop buttons
                '[class*="grid"] > div:has(button)',
            ]
            
            ad_cards = []
            for selector in ad_card_selectors:
                try:
                    cards = await self.page.query_selector_all(selector)
                    if cards and len(cards) > 0:
                        # Filter to only cards that have actual ad content
                        valid_cards = []
                        for card in cards:
                            text = await card.inner_text()
                            # Check if this looks like an ad card (has domain and some text)
                            if len(text) > 50 and ('.com' in text or 'Shop' in text):
                                valid_cards.append(card)
                        
                        if valid_cards:
                            logger.info(f"Found {len(valid_cards)} valid ad cards with selector: {selector}")
                            ad_cards = valid_cards
                            break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            if not ad_cards:
                logger.warning(f"No ad cards found on scroll {scroll_count + 1}")
            
            # First pass: hover over all cards to trigger video loading
            logger.info(f"Hovering over {len(ad_cards)} cards to trigger video loading...")
            for card in ad_cards:
                try:
                    await self._trigger_video_load(card)
                except Exception as e:
                    logger.debug(f"Error hovering card: {e}")
            
            # Wait for videos to load after hovering
            await asyncio.sleep(2)
            
            # Second pass: extract ad data with video URLs
            for card in ad_cards:
                try:
                    ad_data = await self._extract_ad_data(card, competitor)
                    if ad_data and ad_data.get('id') not in seen_ids:
                        # Apply keyword filter if specified
                        if competitor.get('filter'):
                            if not await self._matches_filter(ad_data, competitor['filter']):
                                continue
                        
                        # If it's a video ad, try to get the actual video URL
                        if ad_data.get('video_duration') or ad_data.get('media_type') == 'video':
                            video_url = await self._get_video_url_for_ad(card, ad_data)
                            if video_url:
                                ad_data['media_url'] = video_url
                                ad_data['media_type'] = 'video'
                                logger.info(f"Got video URL for ad {ad_data.get('id')}: {video_url[:80]}...")
                        
                        ads.append(ad_data)
                        seen_ids.add(ad_data.get('id'))
                        logger.debug(f"Found ad: {ad_data.get('id')}")
                except Exception as e:
                    logger.warning(f"Error extracting ad data: {e}")
                    continue
            
            # Scroll down to load more
            await self.page.evaluate('window.scrollBy(0, window.innerHeight)')
            await asyncio.sleep(2)
            
            # Check if we've reached the bottom
            is_at_bottom = await self.page.evaluate('''
                () => window.innerHeight + window.scrollY >= document.body.scrollHeight - 100
            ''')
            
            if is_at_bottom:
                logger.info(f"Reached end of page after {scroll_count + 1} scrolls")
                break
        
        return ads
    
    async def _trigger_video_load(self, card):
        """
        Trigger video loading by hovering and clicking on the card.
        This causes Atria to load the actual video file.
        """
        try:
            # Scroll card into view
            await card.scroll_into_view_if_needed()
            await asyncio.sleep(0.3)
            
            # Hover over the card to trigger lazy loading
            await card.hover()
            await asyncio.sleep(0.5)
            
            # Try to find and click play button or video area
            play_selectors = [
                'button[aria-label*="play" i]',
                'button[class*="play" i]',
                '[class*="play-button"]',
                '[class*="PlayButton"]',
                'svg[class*="play" i]',
                'video',
                '[class*="video-player"]',
                '[class*="VideoPlayer"]',
            ]
            
            for selector in play_selectors:
                try:
                    play_elem = await card.query_selector(selector)
                    if play_elem:
                        await play_elem.click()
                        await asyncio.sleep(1)
                        break
                except Exception:
                    continue
                    
        except Exception as e:
            logger.debug(f"Error triggering video load: {e}")
    
    async def _get_video_url_for_ad(self, card, ad_data: dict) -> Optional[str]:
        """
        Get the video URL for an ad using multiple methods:
        1. Check captured network requests
        2. Try clicking to trigger video load
        3. Extract from DOM elements
        4. Construct from thumbnail URL
        """
        # Method 1: Check if we captured this video URL from network requests
        thumbnail_url = ad_data.get('media_url', '')
        if thumbnail_url:
            # Extract ad identifier from thumbnail URL
            ad_id_match = re.search(r'adfiles/(m\d+)', thumbnail_url)
            if ad_id_match:
                ad_identifier = ad_id_match.group(1)
                if ad_identifier in self.captured_video_urls:
                    return self.captured_video_urls[ad_identifier]
        
        # Method 2: Try clicking to trigger video and capture URL
        video_url = await self._get_video_url_from_click(card)
        if video_url:
            return video_url
        
        # Method 3: Check captured URLs again after clicking
        if thumbnail_url:
            ad_id_match = re.search(r'adfiles/(m\d+)', thumbnail_url)
            if ad_id_match:
                ad_identifier = ad_id_match.group(1)
                if ad_identifier in self.captured_video_urls:
                    return self.captured_video_urls[ad_identifier]
        
        # Method 4: Construct video URL from thumbnail
        if thumbnail_url:
            potential_video = await self._extract_video_url_from_thumbnail(thumbnail_url)
            if potential_video:
                # Verify the URL exists by checking if we can access it
                return potential_video
        
        return None
    
    async def _extract_ad_data(self, card, competitor: dict) -> Optional[dict]:
        """
        Extract metadata from an ad card element.
        
        Args:
            card: Playwright element handle for the ad card
            competitor: Competitor configuration
            
        Returns:
            Dictionary with ad metadata or None
        """
        try:
            # Get all text content for filtering
            card_text = await card.inner_text()
            
            # Skip if this doesn't look like an ad card (too short or no relevant content)
            if not card_text or len(card_text) < 20:
                return None
            
            # Get ad ID from various attributes
            ad_id = await card.get_attribute('data-ad-id')
            if not ad_id:
                ad_id = await card.get_attribute('data-id')
            if not ad_id:
                # Generate ID from content hash
                ad_id = str(abs(hash(card_text)))[:12]
            
            # Get video/image URL - prioritize video first, then high quality images
            media_url = None
            media_type = 'image'  # Default type
            
            # Try video first (look for various video elements and sources)
            video_selectors = [
                'video source[src]',
                'video[src]',
                'source[type*="video"]',
                'source[src*=".mp4"]',
                'source[src*=".webm"]',
                'video source[type="video/mp4"]',
                '[data-video-src]',
                '[data-video-url]',
                '[data-src*=".mp4"]',
                '[data-src*=".webm"]',
            ]
            for selector in video_selectors:
                try:
                    video_elem = await card.query_selector(selector)
                    if video_elem:
                        media_url = await video_elem.get_attribute('src')
                        if not media_url:
                            media_url = await video_elem.get_attribute('data-src')
                        if not media_url:
                            media_url = await video_elem.get_attribute('data-video-src')
                        if not media_url:
                            media_url = await video_elem.get_attribute('data-video-url')
                        if media_url and ('.mp4' in media_url.lower() or '.webm' in media_url.lower() or 'video' in media_url.lower()):
                            media_type = 'video'
                            logger.debug(f"Found video URL: {media_url[:80]}...")
                            break
                except Exception:
                    continue
            
            # Check for video poster (which indicates there's a video)
            if not media_url or media_type != 'video':
                try:
                    video_poster = await card.query_selector('video[poster]')
                    if video_poster:
                        # Get the video src
                        video_src = await video_poster.get_attribute('src')
                        if video_src:
                            media_url = video_src
                            media_type = 'video'
                        else:
                            # Check for source child elements
                            source_elem = await video_poster.query_selector('source')
                            if source_elem:
                                media_url = await source_elem.get_attribute('src')
                                if media_url:
                                    media_type = 'video'
                except Exception:
                    pass
            
            # Check for Atria-specific video CDN URLs
            if not media_url or media_type != 'video':
                try:
                    # Look for any element with video-related URLs in attributes
                    all_elements = await card.query_selector_all('[src*=".mp4"], [src*="video"], [data-src*=".mp4"], [data-src*="video"]')
                    for elem in all_elements:
                        src = await elem.get_attribute('src') or await elem.get_attribute('data-src')
                        if src and ('mp4' in src.lower() or 'video' in src.lower() or 'webm' in src.lower()):
                            media_url = src
                            media_type = 'video'
                            break
                except Exception:
                    pass
            
            # Try to find high-quality image if no video found
            if not media_url:
                # Look for images with CDN URLs (higher quality)
                img_selectors = [
                    'img[src*="cdn.tryatria.com"]',  # Atria CDN
                    'img[src*="adfiles"]',  # Ad files
                    'img[src*="1920"]',  # Full width images
                    'img[src*="http"][src*=".jpeg"]',
                    'img[src*="http"][src*=".jpg"]',
                    'img[src*="http"][src*=".png"]',
                    'img[data-src]',  # Lazy loaded images
                    'img[src*="http"]',  # Any http image
                ]
                
                for selector in img_selectors:
                    try:
                        img_elem = await card.query_selector(selector)
                        if img_elem:
                            # Try data-src first (lazy loaded full image)
                            media_url = await img_elem.get_attribute('data-src')
                            if not media_url:
                                media_url = await img_elem.get_attribute('src')
                            if media_url and len(media_url) > 20:  # Valid URL
                                media_type = 'image'
                                break
                    except Exception:
                        continue
            
            # Also check for background images in style attributes
            if not media_url:
                try:
                    style_elem = await card.query_selector('[style*="background-image"]')
                    if style_elem:
                        style = await style_elem.get_attribute('style')
                        if style:
                            url_match = re.search(r'url\(["\']?(https?://[^"\')\s]+)["\']?\)', style)
                            if url_match:
                                media_url = url_match.group(1)
                                media_type = 'image'
                except Exception:
                    pass
            
            # Get brand/advertiser name (usually in header)
            brand_name = None
            brand_selectors = ['h3', 'h4', '[class*="brand"]', '[class*="name"]', '[class*="title"]']
            for selector in brand_selectors:
                brand_elem = await card.query_selector(selector)
                if brand_elem:
                    brand_name = await brand_elem.inner_text()
                    if brand_name:
                        brand_name = brand_name.strip()[:100]
                        break
            
            # Get domain from the card (Atria shows domain like "buy.hillspet.com")
            domain_text = None
            domain_match = re.search(r'([a-zA-Z0-9-]+\.(?:com|co|net|org|io))', card_text)
            if domain_match:
                domain_text = domain_match.group(1)
            
            # Get date/duration info (Atria shows "Nov 26, 2025 - Present")
            days_active = None
            date_match = re.search(r'(\w+\s+\d+,?\s+\d{4})\s*[-–]\s*(Present|\w+\s+\d+,?\s+\d{4})', card_text)
            if date_match:
                start_date_str = date_match.group(1)
                end_date_str = date_match.group(2)
                try:
                    from dateutil import parser
                    start_date = parser.parse(start_date_str)
                    if end_date_str.lower() == 'present':
                        end_date = datetime.now()
                    else:
                        end_date = parser.parse(end_date_str)
                    days_active = (end_date - start_date).days
                except Exception:
                    pass
            
            # Get video duration (shown as "00:29" etc)
            video_duration = None
            duration_match = re.search(r'(\d{1,2}:\d{2})', card_text)
            if duration_match:
                video_duration = duration_match.group(1)
            
            # Get platform info
            platform = 'Unknown'
            platform_indicators = {
                'facebook': 'Facebook',
                'meta': 'Facebook',
                'instagram': 'Instagram',
                'tiktok': 'TikTok',
                'youtube': 'YouTube',
                'google': 'Google',
            }
            card_text_lower = card_text.lower()
            for indicator, platform_name in platform_indicators.items():
                if indicator in card_text_lower:
                    platform = platform_name
                    break
            
            # Also check for platform icons/images
            if platform == 'Unknown':
                platform_elem = await card.query_selector('img[alt*="facebook" i], img[alt*="meta" i], img[alt*="tiktok" i], img[alt*="youtube" i]')
                if platform_elem:
                    platform_alt = await platform_elem.get_attribute('alt')
                    if platform_alt:
                        platform = platform_alt
            
            # Get ad link
            ad_link = None
            link_elem = await card.query_selector('a[href]')
            if link_elem:
                ad_link = await link_elem.get_attribute('href')
            
            # Determine media type from duration info if not already set
            if video_duration and media_type != 'video':
                media_type = 'video'  # Has duration, so it's a video
            
            return {
                'id': ad_id,
                'competitor': competitor['name'],
                'domain': domain_text or competitor['domain'],
                'brand_name': brand_name,
                'media_url': media_url,
                'media_type': media_type,
                'ad_text': card_text[:500] if card_text else None,
                'days_active': days_active,
                'video_duration': video_duration,
                'platform': platform,
                'ad_link': ad_link,
                'scraped_at': datetime.now().isoformat(),
                'filter_keyword': competitor.get('filter'),
            }
            
        except Exception as e:
            logger.warning(f"Error extracting ad data: {e}")
            return None
    
    async def _matches_filter(self, ad_data: dict, filter_keyword: str) -> bool:
        """
        Check if ad matches the filter keyword.
        
        Args:
            ad_data: Ad metadata dictionary
            filter_keyword: Keyword to filter by (e.g., 'GLP1')
            
        Returns:
            True if ad matches filter, False otherwise
        """
        if not filter_keyword:
            return True
            
        # Check ad text for keyword
        ad_text = (ad_data.get('ad_text') or '').lower()
        return filter_keyword.lower() in ad_text
    
    async def _get_video_url_from_click(self, card) -> Optional[str]:
        """
        Click on a video ad card to trigger video load and extract the .mp4 URL.
        Uses network interception to capture the actual video URL.
        
        Args:
            card: The ad card element to click
            
        Returns:
            Video URL (.mp4) if found, None otherwise
        """
        try:
            # Store count of captured videos before clicking
            videos_before = len(self.captured_video_urls)
            
            # Scroll into view
            await card.scroll_into_view_if_needed()
            await asyncio.sleep(0.3)
            
            # Try multiple click targets
            click_targets = [
                'video',
                '[class*="video"]',
                '[class*="Video"]',
                'button[aria-label*="play" i]',
                '[class*="play"]',
                '[class*="Play"]',
                'img',
                '[class*="thumbnail"]',
                '[class*="Thumbnail"]',
            ]
            
            clicked = False
            for selector in click_targets:
                try:
                    target = await card.query_selector(selector)
                    if target:
                        await target.hover()
                        await asyncio.sleep(0.3)
                        await target.click()
                        clicked = True
                        break
                except Exception:
                    continue
            
            if not clicked:
                # Click on the card itself
                await card.hover()
                await asyncio.sleep(0.3)
                await card.click()
            
            # Wait for video to load (network request)
            await asyncio.sleep(3)
            
            # Check if new video URLs were captured
            if len(self.captured_video_urls) > videos_before:
                # Return the most recently captured video URL
                return list(self.captured_video_urls.values())[-1]
            
            # Fallback: Look for video sources in DOM
            video_selectors = [
                'video source[src*=".mp4"]',
                'video[src*=".mp4"]',
                'source[src*="cdn.tryatria.com"][src*=".mp4"]',
                '[src*="adfiles"][src*=".mp4"]',
                'video source[src*="video"]',
                'video[src*="video"]',
            ]
            
            # Check within the card first
            for selector in video_selectors:
                try:
                    elem = await card.query_selector(selector)
                    if elem:
                        video_url = await elem.get_attribute('src')
                        if video_url and ('.mp4' in video_url.lower() or 'video' in video_url.lower()):
                            logger.info(f"Found video URL in card: {video_url[:80]}...")
                            return video_url
                except Exception:
                    continue
            
            # Check entire page
            for selector in video_selectors:
                try:
                    elem = await self.page.query_selector(selector)
                    if elem:
                        video_url = await elem.get_attribute('src')
                        if video_url and ('.mp4' in video_url.lower() or 'video' in video_url.lower()):
                            logger.info(f"Found video URL on page: {video_url[:80]}...")
                            return video_url
                except Exception:
                    continue
            
            # Check all video elements
            videos = await self.page.query_selector_all('video')
            for video in videos:
                # Check src attribute
                src = await video.get_attribute('src')
                if src and ('.mp4' in src.lower() or 'video' in src.lower()):
                    return src
                
                # Check currentSrc via JavaScript
                try:
                    current_src = await video.evaluate('el => el.currentSrc')
                    if current_src and ('.mp4' in current_src.lower() or 'video' in current_src.lower()):
                        return current_src
                except Exception:
                    pass
                    
                # Check source children
                sources = await video.query_selector_all('source')
                for source in sources:
                    src = await source.get_attribute('src')
                    if src and ('.mp4' in src.lower() or 'video' in src.lower()):
                        return src
            
            # Press Escape to close any modal
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(0.5)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting video URL from click: {e}")
            # Try to recover by pressing Escape
            try:
                await self.page.keyboard.press('Escape')
            except Exception:
                pass
            return None
    
    async def _extract_video_url_from_thumbnail(self, thumbnail_url: str) -> Optional[str]:
        """
        Try to construct video URLs from the thumbnail URL and verify which one works.
        
        Atria CDN patterns observed:
        - Thumbnail: https://cdn.tryatria.com/_images/w:384/q:75/plain/adfiles/m123_abc.jpeg
        - Video might be: https://cdn.tryatria.com/adfiles/m123_abc.mp4
        - Or: https://cdn.tryatria.com/adfiles/m123.mp4
        
        Args:
            thumbnail_url: The thumbnail image URL
            
        Returns:
            Working video URL or None
        """
        if not thumbnail_url or 'cdn.tryatria.com' not in thumbnail_url:
            return None
            
        potential_urls = []
        
        try:
            # Pattern 1: Full ID with hash -> same with .mp4
            # adfiles/m1485875549172375_Uc1qAWjvJm4.jpeg -> adfiles/m1485875549172375_Uc1qAWjvJm4.mp4
            match = re.search(r'adfiles/(m\d+_[^.]+)\.(?:jpeg|jpg|png)', thumbnail_url)
            if match:
                base_id = match.group(1)
                potential_urls.append(f"https://cdn.tryatria.com/adfiles/{base_id}.mp4")
            
            # Pattern 2: Just the m-number without hash
            # adfiles/m1485875549172375_Uc1qAWjvJm4.jpeg -> adfiles/m1485875549172375.mp4
            match = re.search(r'adfiles/(m\d+)', thumbnail_url)
            if match:
                m_id = match.group(1)
                potential_urls.append(f"https://cdn.tryatria.com/adfiles/{m_id}.mp4")
            
            # Pattern 3: Try webm as well
            if match:
                potential_urls.append(f"https://cdn.tryatria.com/adfiles/{match.group(1)}.webm")
            
            # Verify URLs by making HEAD requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://app.tryatria.com/',
            }
            
            async with aiohttp.ClientSession() as session:
                for url in potential_urls:
                    try:
                        async with session.head(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                            if response.status == 200:
                                content_type = response.headers.get('content-type', '')
                                if 'video' in content_type or response.content_length and response.content_length > 100000:
                                    logger.info(f"Found working video URL: {url}")
                                    return url
                    except Exception:
                        continue
                        
        except Exception as e:
            logger.debug(f"Error constructing video URL from thumbnail: {e}")
        
        # Return first potential URL even if not verified (for later download attempt)
        return potential_urls[0] if potential_urls else None
    
    async def download_ad_media(self, ad_data: dict) -> Optional[str]:
        """
        Download the ad media (video/image) to local storage.
        For video ads, tries multiple URL patterns if the first one fails.
        
        Args:
            ad_data: Ad metadata dictionary with media_url
            
        Returns:
            Path to downloaded file or None if failed
        """
        media_url = ad_data.get('media_url')
        media_type = ad_data.get('media_type', 'image')
        video_duration = ad_data.get('video_duration')
        
        if not media_url:
            logger.warning(f"No media URL for ad {ad_data.get('id')}")
            return None
        
        try:
            is_video = (
                '.mp4' in media_url.lower() or 
                '.webm' in media_url.lower() or
                media_type == 'video' or
                video_duration is not None
            )
            
            # Build list of URLs to try
            urls_to_try = []
            
            if '.mp4' in media_url.lower() or '.webm' in media_url.lower():
                # Already a video URL
                urls_to_try.append(media_url)
            elif is_video and 'cdn.tryatria.com' in media_url:
                # This is marked as video but URL is an image - construct video URLs
                # Pattern: adfiles/m1485875549172375_Uc1qAWjvJm4.jpeg -> try .mp4 versions
                
                # Extract the adfiles path
                adfiles_match = re.search(r'adfiles/(m\d+_[^.]+)\.(?:jpeg|jpg|png)', media_url)
                if adfiles_match:
                    base_id = adfiles_match.group(1)
                    urls_to_try.append(f"https://cdn.tryatria.com/adfiles/{base_id}.mp4")
                
                # Also try just the m-number
                m_match = re.search(r'adfiles/(m\d+)', media_url)
                if m_match:
                    m_id = m_match.group(1)
                    urls_to_try.append(f"https://cdn.tryatria.com/adfiles/{m_id}.mp4")
                    urls_to_try.append(f"https://cdn.tryatria.com/adfiles/{m_id}.webm")
                
                # Also add the image URL as fallback
                if '/_images/' in media_url:
                    # Get direct image URL
                    direct_match = re.search(r'/plain/(adfiles/[^\s]+)', media_url)
                    if direct_match:
                        urls_to_try.append(f"https://cdn.tryatria.com/{direct_match.group(1)}")
                urls_to_try.append(media_url)
            else:
                # Image URL - fix to get full size
                if 'cdn.tryatria.com' in media_url:
                    if '/w:' in media_url:
                        media_url = re.sub(r'/w:\d+/', '/w:1920/', media_url)
                    if '/q:' in media_url:
                        media_url = re.sub(r'/q:\d+/', '/q:100/', media_url)
                    
                    # Try direct file URL
                    direct_match = re.search(r'/plain/(adfiles/[^\s]+)', media_url)
                    if direct_match:
                        urls_to_try.append(f"https://cdn.tryatria.com/{direct_match.group(1)}")
                urls_to_try.append(media_url)
            
            # Remove duplicates while preserving order
            urls_to_try = list(dict.fromkeys(urls_to_try))
            
            # Download headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'video/*, image/*',
                'Referer': 'https://app.tryatria.com/',
            }
            
            # Try each URL
            async with aiohttp.ClientSession() as session:
                for url in urls_to_try:
                    try:
                        url_is_video = '.mp4' in url.lower() or '.webm' in url.lower()
                        timeout_seconds = 180 if url_is_video else 60
                        min_file_size = 50000 if url_is_video else 5000  # 50KB for videos
                        
                        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout_seconds)) as response:
                            if response.status == 200:
                                content = await response.read()
                                file_size_kb = len(content) // 1024
                                
                                # Check content type
                                content_type = response.headers.get('content-type', '')
                                actual_is_video = 'video' in content_type or url_is_video
                                
                                # Determine extension
                                if '.mp4' in url.lower() or 'video/mp4' in content_type:
                                    ext = '.mp4'
                                    actual_is_video = True
                                elif '.webm' in url.lower() or 'video/webm' in content_type:
                                    ext = '.webm'
                                    actual_is_video = True
                                elif '.png' in url.lower() or 'image/png' in content_type:
                                    ext = '.png'
                                elif '.gif' in url.lower() or 'image/gif' in content_type:
                                    ext = '.gif'
                                else:
                                    ext = '.jpg'
                                
                                # Validate file size
                                if len(content) < min_file_size:
                                    logger.debug(f"File too small ({len(content)} bytes) from {url[:60]}...")
                                    continue
                                
                                # Create filename
                                competitor_name = ad_data.get('competitor', 'unknown').replace(' ', '_')
                                prefix = "VIDEO_" if actual_is_video else ""
                                filename = f"{prefix}{competitor_name}_{ad_data.get('id')}{ext}"
                                filepath = RAW_ADS_DIR / filename
                                
                                async with aiofiles.open(filepath, 'wb') as f:
                                    await f.write(content)
                                
                                media_desc = "video" if actual_is_video else "image"
                                logger.info(f"Downloaded {media_desc}: {filename} ({file_size_kb}KB)")
                                
                                # Update ad_data with actual URL used
                                ad_data['media_url_downloaded'] = url
                                if actual_is_video:
                                    ad_data['media_type'] = 'video'
                                
                                return str(filepath)
                            else:
                                logger.debug(f"HTTP {response.status} for {url[:60]}...")
                                
                    except asyncio.TimeoutError:
                        logger.debug(f"Timeout for {url[:60]}...")
                        continue
                    except Exception as e:
                        logger.debug(f"Error downloading {url[:60]}...: {e}")
                        continue
            
            # All URLs failed
            logger.warning(f"Failed to download media for ad {ad_data.get('id')} - tried {len(urls_to_try)} URLs")
            ad_data['media_url_full'] = urls_to_try[0] if urls_to_try else media_url
            return None
                        
        except Exception as e:
            logger.error(f"Error downloading ad media: {e}")
            return None
    
    async def scrape_all_competitors(self) -> list[dict]:
        """
        Scrape ads from all configured competitors.
        
        Returns:
            List of all scraped ad metadata
        """
        all_ads = []
        
        # Login first
        if not await self.login():
            logger.error("Failed to login, cannot proceed with scraping")
            return all_ads
        
        # Scrape each competitor
        for competitor in COMPETITORS:
            logger.info(f"Processing competitor: {competitor['name']}")
            ads = await self.search_competitor_ads(competitor)
            
            # Process each ad (download media if possible, but keep all ads)
            for ad in ads:
                # Try to download media
                filepath = await self.download_ad_media(ad)
                if filepath:
                    ad['local_filepath'] = filepath
                
                # Add ad to results even without media file
                # The ad text is the most important data for analysis
                all_ads.append(ad)
            
            logger.info(f"Added {len(ads)} ads from {competitor['name']}")
            
            # Small delay between competitors
            await asyncio.sleep(3)
        
        # Save metadata to JSON
        metadata_file = RAW_ADS_DIR / f"scrape_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        async with aiofiles.open(metadata_file, 'w') as f:
            await f.write(json.dumps(all_ads, indent=2))
        logger.info(f"Saved scrape metadata to {metadata_file}")
        
        return all_ads


async def main():
    """Main function to run the scraper."""
    async with AtriaScraper() as scraper:
        ads = await scraper.scrape_all_competitors()
        print(f"Total ads scraped: {len(ads)}")
        for ad in ads[:5]:  # Print first 5
            print(f"  - {ad.get('competitor')}: {ad.get('id')} ({ad.get('days_active')} days)")


if __name__ == '__main__':
    asyncio.run(main())

