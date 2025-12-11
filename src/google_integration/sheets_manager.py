"""
Google Sheets Integration Module

Manages data export to Google Sheets for the intelligence layer.
Matches the client's expected format from Creative AI Sheet.
"""
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials
from loguru import logger

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config import GOOGLE_SHEETS_CONFIG, PROJECT_ROOT


class GoogleSheetsManager:
    """Manager for Google Sheets integration."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive',
    ]
    
    # Client's exact column format from Creative AI Sheet
    ADS_COLUMNS = [
        'Ad File Name / Link',           # 1. Identify the source video or downloaded ad file
        'Competitor Name',                # 2. Who ran the ad
        'Platform (TikTok/FB/YouTube/Native)',  # 3. Sorting & grouping ads by channel
        'Transcript (Raw)',               # 4. AI reads this to extract insights
        'Top Hooks',                      # 5. AI extracts the strongest opening lines
        'Top Angles Used',                # 6. AI extracts sales angles used in the ad
        'Pain Points',                    # 7. AI extracts customer frustrations mentioned
        'Emotional Triggers',             # 8. AI extracts emotions the ad activates
        'Why This Ad Works',              # 9. Short AI summary of the winning elements
        'Brand-Aligned Script',           # 10. AI generates a new script for your product
        'Hook Variations (3 Options)',    # 11. AI generates 3 alternative hooks for testing
        'Days Active',                    # Extra: How long the ad has been running
        'Scraped At',                     # Extra: When the ad was scraped
        'Status',                         # Extra: Processing status
    ]
    
    def __init__(self):
        self.spreadsheet_id = GOOGLE_SHEETS_CONFIG['spreadsheet_id']
        self.service_account_file = PROJECT_ROOT / GOOGLE_SHEETS_CONFIG['service_account_file']
        self.client = None
        self.spreadsheet = None
        
    def _initialize_client(self):
        """Initialize the Google Sheets client."""
        if self.client:
            return
            
        try:
            if not self.service_account_file.exists():
                logger.error(f"Service account file not found: {self.service_account_file}")
                logger.info("Please create a Google Cloud service account and download the JSON key")
                return
            
            credentials = Credentials.from_service_account_file(
                str(self.service_account_file),
                scopes=self.SCOPES,
            )
            
            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            logger.info(f"Connected to Google Sheets: {self.spreadsheet.title}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {e}")
    
    def _get_or_create_worksheet(self, name: str) -> Optional[gspread.Worksheet]:
        """Get existing worksheet or create new one."""
        self._initialize_client()
        if not self.spreadsheet:
            return None
            
        try:
            # Try to get existing worksheet
            return self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            # Create new worksheet
            worksheet = self.spreadsheet.add_worksheet(title=name, rows=1000, cols=26)
            logger.info(f"Created new worksheet: {name}")
            return worksheet
    
    def _get_first_worksheet(self) -> Optional[gspread.Worksheet]:
        """Get the first (default) worksheet."""
        self._initialize_client()
        if not self.spreadsheet:
            return None
        
        try:
            worksheets = self.spreadsheet.worksheets()
            if worksheets:
                return worksheets[0]
            return None
        except Exception as e:
            logger.error(f"Failed to get first worksheet: {e}")
            return None
    
    def setup_sheets(self):
        """Set up the worksheet with proper headers."""
        self._initialize_client()
        if not self.spreadsheet:
            logger.error("Cannot set up sheets - client not initialized")
            return
        
        # Use the first worksheet (client's existing sheet)
        worksheet = self._get_first_worksheet()
        if worksheet:
            try:
                # Check row 3 where client has headers
                existing = worksheet.row_values(3)
                if not existing or 'Column Name' in str(existing):
                    # Set up headers in row 1 instead
                    worksheet.update('A1', [self.ADS_COLUMNS])
                    logger.info("Set up headers in worksheet")
                else:
                    logger.info("Worksheet already has data, skipping header setup")
            except Exception as e:
                logger.warning(f"Could not check headers: {e}")
        
        logger.success("Google Sheets setup complete")
    
    def _extract_analysis_sections(self, full_analysis: str) -> dict:
        """
        Extract specific sections from Claude's full analysis.
        
        Args:
            full_analysis: Full analysis text from Claude
            
        Returns:
            Dictionary with extracted sections
        """
        sections = {
            'top_hooks': '',
            'top_angles': '',
            'pain_points': '',
            'emotional_triggers': '',
            'why_it_works': '',
        }
        
        if not full_analysis:
            return sections
        
        # Extract hook analysis
        if 'HOOK' in full_analysis.upper():
            try:
                hook_start = full_analysis.upper().find('HOOK')
                next_section = min(
                    (full_analysis.upper().find(s, hook_start + 4) for s in ['ANGLE', 'EMOTIONAL', 'STRUCTURE', 'CALL'] 
                     if full_analysis.upper().find(s, hook_start + 4) > 0),
                    default=len(full_analysis)
                )
                sections['top_hooks'] = full_analysis[hook_start:next_section].strip()[:1000]
            except Exception:
                pass
        
        # Extract angle analysis
        if 'ANGLE' in full_analysis.upper():
            try:
                angle_start = full_analysis.upper().find('ANGLE')
                next_section = min(
                    (full_analysis.upper().find(s, angle_start + 5) for s in ['EMOTIONAL', 'STRUCTURE', 'CALL', 'KEY'] 
                     if full_analysis.upper().find(s, angle_start + 5) > 0),
                    default=len(full_analysis)
                )
                sections['top_angles'] = full_analysis[angle_start:next_section].strip()[:1000]
            except Exception:
                pass
        
        # Extract emotional triggers
        if 'EMOTIONAL' in full_analysis.upper():
            try:
                emo_start = full_analysis.upper().find('EMOTIONAL')
                next_section = min(
                    (full_analysis.upper().find(s, emo_start + 9) for s in ['STRUCTURE', 'CALL', 'KEY', 'TAKEAWAY'] 
                     if full_analysis.upper().find(s, emo_start + 9) > 0),
                    default=len(full_analysis)
                )
                sections['emotional_triggers'] = full_analysis[emo_start:next_section].strip()[:1000]
            except Exception:
                pass
        
        # Extract pain points from the analysis (usually in angle or emotional section)
        pain_keywords = ['pain point', 'frustration', 'problem', 'struggle', 'challenge']
        for keyword in pain_keywords:
            if keyword in full_analysis.lower():
                try:
                    idx = full_analysis.lower().find(keyword)
                    pain_context = full_analysis[max(0, idx-50):min(len(full_analysis), idx+200)]
                    if sections['pain_points']:
                        sections['pain_points'] += '\n' + pain_context
                    else:
                        sections['pain_points'] = pain_context
                except Exception:
                    pass
        sections['pain_points'] = sections['pain_points'][:1000] if sections['pain_points'] else ''
        
        # Extract "why it works" from key takeaways
        if 'TAKEAWAY' in full_analysis.upper() or 'KEY' in full_analysis.upper():
            try:
                for marker in ['KEY TAKEAWAY', 'TAKEAWAY']:
                    if marker in full_analysis.upper():
                        takeaway_start = full_analysis.upper().find(marker)
                        sections['why_it_works'] = full_analysis[takeaway_start:].strip()[:1000]
                        break
            except Exception:
                pass
        
        return sections
    
    def _extract_hook_variations(self, script_data: dict) -> str:
        """
        Extract or generate hook variations from script data.
        
        Args:
            script_data: Rewritten script data
            
        Returns:
            String with hook variations
        """
        # First check for dedicated hook_variations field
        hook_variations = script_data.get('hook_variations', '')
        if hook_variations:
            return hook_variations[:2000]
        
        script = script_data.get('script', '')
        
        # Try to extract from HOOK VARIATIONS section in script
        if 'HOOK VARIATIONS' in script:
            try:
                variations_section = script.split('HOOK VARIATIONS')[1]
                return variations_section.strip()[:2000]
            except Exception:
                pass
        
        # Fallback: Try to extract hook section from script
        if '[HOOK' in script:
            try:
                hook_section = script.split('[HOOK')[1].split('[')[0]
                return f"Option 1: {hook_section.strip()[:500]}"
            except Exception:
                pass
        
        return ''
    
    def add_ad(self, ad_data: dict) -> bool:
        """
        Add a single ad to the Google Sheet in client's format.
        
        Args:
            ad_data: Ad metadata dictionary
            
        Returns:
            True if successful, False otherwise
        """
        self._initialize_client()
        if not self.spreadsheet:
            return False
        
        try:
            worksheet = self._get_first_worksheet()
            if not worksheet:
                return False
            
            # Extract analysis data
            analysis = ad_data.get('analysis', {})
            full_analysis = analysis.get('full', {}).get('analysis', '')
            
            # Parse sections from analysis
            sections = self._extract_analysis_sections(full_analysis)
            
            # Get rewritten script
            script_data = ad_data.get('rewritten_script', {})
            brand_script = script_data.get('script', '')[:3000] if script_data else ''
            
            # Get hook variations
            hook_variations = self._extract_hook_variations(script_data)
            
            # Determine platform
            platform = ad_data.get('platform', 'Unknown')
            if platform == 'Unknown':
                media_url = ad_data.get('media_url', '')
                if 'facebook' in media_url.lower() or 'fb' in media_url.lower():
                    platform = 'Facebook'
                elif 'tiktok' in media_url.lower():
                    platform = 'TikTok'
                elif 'youtube' in media_url.lower():
                    platform = 'YouTube'
            
            # Prepare row data matching client's format
            row = [
                ad_data.get('local_filepath') or ad_data.get('media_url', ''),  # Ad File Name / Link
                ad_data.get('competitor', ''),                                   # Competitor Name
                platform,                                                        # Platform
                (ad_data.get('transcript') or '')[:5000],                        # Transcript (Raw)
                sections['top_hooks'],                                           # Top Hooks
                sections['top_angles'],                                          # Top Angles Used
                sections['pain_points'],                                         # Pain Points
                sections['emotional_triggers'],                                  # Emotional Triggers
                sections['why_it_works'],                                        # Why This Ad Works
                brand_script,                                                    # Brand-Aligned Script
                hook_variations,                                                 # Hook Variations (3 Options)
                str(ad_data.get('days_active', '')),                            # Days Active
                ad_data.get('scraped_at', datetime.now().isoformat()),          # Scraped At
                'Processed',                                                     # Status
            ]
            
            worksheet.append_row(row)
            logger.info(f"Added ad {ad_data.get('id')} to Google Sheets")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add ad to Google Sheets: {e}")
            return False
    
    def add_ads_batch(self, ads: list[dict]) -> int:
        """
        Add multiple ads to Google Sheets.
        
        Args:
            ads: List of ad metadata dictionaries
            
        Returns:
            Number of ads successfully added
        """
        success_count = 0
        for ad in ads:
            if self.add_ad(ad):
                success_count += 1
        
        logger.info(f"Added {success_count}/{len(ads)} ads to Google Sheets")
        return success_count
    
    def add_script(self, ad_data: dict) -> bool:
        """
        Add a generated script (already included in main add_ad function).
        This is kept for backwards compatibility.
        
        Args:
            ad_data: Ad metadata with rewritten_script
            
        Returns:
            True (script is already added with the ad)
        """
        # Scripts are now included in the main ad row
        return True
    
    def get_all_ads(self) -> list[dict]:
        """
        Get all ads from the worksheet.
        
        Returns:
            List of ad dictionaries
        """
        self._initialize_client()
        if not self.spreadsheet:
            return []
        
        try:
            worksheet = self._get_first_worksheet()
            if not worksheet:
                return []
            
            records = worksheet.get_all_records()
            return records
            
        except Exception as e:
            logger.error(f"Failed to get ads from Google Sheets: {e}")
            return []
    
    def update_ad_status(self, ad_id: str, status: str, notes: str = '') -> bool:
        """
        Update the status of an ad in the sheet.
        
        Args:
            ad_id: The ad ID to update
            status: New status value
            notes: Optional notes to add
            
        Returns:
            True if successful, False otherwise
        """
        self._initialize_client()
        if not self.spreadsheet:
            return False
        
        try:
            worksheet = self._get_first_worksheet()
            if not worksheet:
                return False
            
            # Find the row with this ad ID (in column 1)
            cell = worksheet.find(ad_id)
            if cell:
                # Update status column (column 14)
                worksheet.update_cell(cell.row, 14, status)
                logger.info(f"Updated status for ad {ad_id} to {status}")
                return True
            else:
                logger.warning(f"Ad {ad_id} not found in sheet")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update ad status: {e}")
            return False
    
    def clear_and_setup_headers(self):
        """Clear the sheet and set up proper headers."""
        self._initialize_client()
        if not self.spreadsheet:
            return
        
        try:
            worksheet = self._get_first_worksheet()
            if worksheet:
                # Clear existing content
                worksheet.clear()
                # Add headers
                worksheet.update('A1', [self.ADS_COLUMNS])
                logger.info("Cleared sheet and set up headers")
        except Exception as e:
            logger.error(f"Failed to clear and setup headers: {e}")


async def main():
    """Test Google Sheets integration."""
    manager = GoogleSheetsManager()
    
    # Setup sheets
    manager.setup_sheets()
    
    # Test adding an ad
    test_ad = {
        'id': 'test_001',
        'competitor': 'ColonBroom',
        'domain': 'colonbroom.com',
        'platform': 'Facebook',
        'days_active': 14,
        'local_filepath': '/data/raw_ads/colonbroom_test_001.mp4',
        'transcript': 'Test transcript content here. Are you tired of feeling bloated? I discovered this amazing solution...',
        'scraped_at': datetime.now().isoformat(),
        'analysis': {
            'full': {
                'analysis': '''
1. HOOK ANALYSIS
   - Opening hook: "Are you tired of feeling bloated?"
   - Hook type: Question/Pain point
   - Effectiveness rating: 8/10

2. ANGLE/APPROACH
   - Main selling angle: Personal discovery story
   - Target audience: Health-conscious adults
   - Key benefits: Reduced bloating, better digestion

3. EMOTIONAL TRIGGERS
   - Primary emotion: Frustration with current state
   - Secondary emotions: Hope, curiosity
   - Trigger phrases: "tired of", "discovered", "amazing solution"

4. KEY TAKEAWAYS
   - Strong question hook creates immediate engagement
   - Personal story builds trust
   - Clear benefit statement
'''
            }
        },
        'rewritten_script': {
            'script': '''[HOOK - 0:00-0:05]
"What if I told you the secret to lasting energy isn't in your coffee cup?"

[PROBLEM - 0:05-0:15]
Most people don't realize their afternoon crash comes from gut health issues...

[SOLUTION - 0:15-0:30]
That's why ThermoSlim uses a unique blend of natural ingredients...

[CTA - 0:45-0:60]
Click the link below to try ThermoSlim risk-free today!
''',
            'brand_name': 'ThermoSlim',
        }
    }
    
    manager.add_ad(test_ad)
    print("Test complete - check Google Sheets")


if __name__ == '__main__':
    asyncio.run(main())
