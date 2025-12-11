"""
Media Downloader for Atria Ads

Downloads full-resolution videos/images by navigating to each ad's detail page.
This is a separate script that can be run after initial scraping.
"""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
import aiohttp
from loguru import logger
from playwright.async_api import async_playwright

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config import ATRIA_CONFIG, RAW_ADS_DIR


class MediaDownloader:
    """Downloads media from Atria by visiting individual ad pages."""
    
    def __init__(self):
        self.email = ATRIA_CONFIG['email']
        self.password = ATRIA_CONFIG['password']
        self.base_url = ATRIA_CONFIG['base_url']
        self.browser = None
        self.page = None
        
    async def __aenter__(self):
        await self.initialize()
        return self
        
    async def __aexit__(self, *args):
        await self.close()
        
    async def initialize(self):
        """Initialize browser."""
        logger.info("Initializing media downloader...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        self.page = await self.context.new_page()
        
    async def close(self):
        """Close browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    async def login(self) -> bool:
        """Login to Atria."""
        try:
            await self.page.goto(f"{self.base_url}/login", wait_until='networkidle')
            await asyncio.sleep(2)
            
            email_input = await self.page.wait_for_selector('input[name="email"], input[type="email"]')
            await email_input.fill(self.email)
            
            password_input = await self.page.wait_for_selector('input[type="password"]')
            await password_input.fill(self.password)
            
            login_btn = await self.page.wait_for_selector('button[type="submit"]')
            await login_btn.click()
            
            await asyncio.sleep(5)
            
            if 'login' not in self.page.url.lower():
                logger.success("Login successful!")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    async def download_ad_media(self, ad_data: dict) -> Optional[str]:
        """
        Download media for a single ad by visiting its page.
        
        Args:
            ad_data: Ad metadata dictionary
            
        Returns:
            Path to downloaded file or None
        """
        ad_link = ad_data.get('ad_link')
        ad_id = ad_data.get('id')
        competitor = ad_data.get('competitor', 'unknown')
        
        if not ad_link:
            logger.warning(f"No ad link for {ad_id}")
            return None
        
        try:
            # Navigate to ad detail page
            full_url = f"{self.base_url}{ad_link}" if ad_link.startswith('/') else ad_link
            logger.info(f"Visiting ad page: {full_url}")
            
            await self.page.goto(full_url, wait_until='networkidle')
            await asyncio.sleep(3)
            
            # Look for video sources
            video_url = None
            
            # Try to find video element
            video_elem = await self.page.query_selector('video source, video[src]')
            if video_elem:
                video_url = await video_elem.get_attribute('src')
            
            # Try to find in network requests
            if not video_url:
                # Look for high-res image
                img_selectors = [
                    'img[src*="adfiles"][src*="1920"]',
                    'img[src*=".mp4"]',
                    'video source[src*=".mp4"]',
                    '[src*="facebook.com"]',
                    '[src*="fbcdn"]',
                ]
                
                for selector in img_selectors:
                    elem = await self.page.query_selector(selector)
                    if elem:
                        video_url = await elem.get_attribute('src')
                        if video_url:
                            break
            
            if video_url:
                # Download the media
                ext = '.mp4' if 'mp4' in video_url or 'video' in video_url else '.jpg'
                filename = f"{competitor}_{ad_id}_full{ext}"
                filepath = RAW_ADS_DIR / filename
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(video_url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            if len(content) > 10000:  # > 10KB
                                async with aiofiles.open(filepath, 'wb') as f:
                                    await f.write(content)
                                logger.success(f"Downloaded: {filename} ({len(content)//1024}KB)")
                                return str(filepath)
                            else:
                                logger.warning(f"File too small: {len(content)} bytes")
            else:
                logger.warning(f"No video/image found for ad {ad_id}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error downloading media for {ad_id}: {e}")
            return None
    
    async def process_ads_file(self, json_file: str, limit: int = None):
        """
        Process ads from a JSON file.
        
        Args:
            json_file: Path to JSON file with ad data
            limit: Maximum number of ads to process
        """
        # Load ads
        with open(json_file) as f:
            ads = json.load(f)
        
        if limit:
            ads = ads[:limit]
        
        logger.info(f"Processing {len(ads)} ads from {json_file}")
        
        # Login
        if not await self.login():
            logger.error("Login failed, aborting")
            return
        
        # Download each ad
        for i, ad in enumerate(ads):
            logger.info(f"Processing ad {i+1}/{len(ads)}: {ad.get('id')}")
            filepath = await self.download_ad_media(ad)
            
            if filepath:
                ad['local_filepath_full'] = filepath
            
            await asyncio.sleep(2)  # Rate limiting
        
        # Save updated JSON
        output_file = RAW_ADS_DIR / f"ads_with_media_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(ads, f, indent=2)
        
        logger.success(f"Saved updated ads to {output_file}")


async def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('json_file', help='Path to ads JSON file')
    parser.add_argument('--limit', type=int, default=5, help='Max ads to process')
    args = parser.parse_args()
    
    async with MediaDownloader() as downloader:
        await downloader.process_ads_file(args.json_file, args.limit)


if __name__ == '__main__':
    asyncio.run(main())

