"""
Google Drive Integration Module

Manages file uploads to Google Drive for ad media storage.
"""
import asyncio
import io
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from loguru import logger

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config import GOOGLE_DRIVE_CONFIG, PROJECT_ROOT


class GoogleDriveManager:
    """Manager for Google Drive integration."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive',
    ]
    
    def __init__(self):
        self.folder_id = GOOGLE_DRIVE_CONFIG['folder_id']
        self.service_account_file = PROJECT_ROOT / GOOGLE_DRIVE_CONFIG['service_account_file']
        self.service = None
        self.folder_cache = {}  # Cache subfolder IDs
        
    def _initialize_service(self):
        """Initialize the Google Drive service."""
        if self.service:
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
            
            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("Connected to Google Drive")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
    
    def _get_or_create_folder(self, folder_name: str, parent_id: str = None) -> Optional[str]:
        """
        Get existing folder or create new one.
        
        Args:
            folder_name: Name of the folder
            parent_id: Parent folder ID (uses root folder if None)
            
        Returns:
            Folder ID or None if failed
        """
        self._initialize_service()
        if not self.service:
            return None
            
        parent_id = parent_id or self.folder_id
        cache_key = f"{parent_id}/{folder_name}"
        
        if cache_key in self.folder_cache:
            return self.folder_cache[cache_key]
        
        try:
            # Search for existing folder
            query = f"name='{folder_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
            ).execute()
            
            files = results.get('files', [])
            if files:
                folder_id = files[0]['id']
                self.folder_cache[cache_key] = folder_id
                return folder_id
            
            # Create new folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id],
            }
            
            file = self.service.files().create(
                body=file_metadata,
                fields='id',
            ).execute()
            
            folder_id = file.get('id')
            self.folder_cache[cache_key] = folder_id
            logger.info(f"Created folder: {folder_name}")
            return folder_id
            
        except Exception as e:
            logger.error(f"Failed to get/create folder {folder_name}: {e}")
            return None
    
    def setup_folder_structure(self):
        """Set up the required folder structure in Google Drive."""
        self._initialize_service()
        if not self.service:
            return
        
        # Main subfolders
        subfolders = [
            'Raw Ads',
            'Transcripts',
            'Analysis',
            'Scripts',
            'Archives',
        ]
        
        # Competitor subfolders under Raw Ads
        competitor_folders = [
            'ColonBroom',
            'SkinnyFit',
            'SereneHerbs',
        ]
        
        for folder in subfolders:
            folder_id = self._get_or_create_folder(folder)
            
            # Create competitor subfolders under Raw Ads
            if folder == 'Raw Ads' and folder_id:
                for competitor in competitor_folders:
                    self._get_or_create_folder(competitor, folder_id)
        
        logger.success("Google Drive folder structure setup complete")
    
    def upload_file(
        self,
        file_path: str,
        folder_name: str = None,
        custom_name: str = None,
    ) -> Optional[str]:
        """
        Upload a file to Google Drive.
        
        Args:
            file_path: Path to the local file
            folder_name: Subfolder name (uses root folder if None)
            custom_name: Custom filename (uses original name if None)
            
        Returns:
            Google Drive file ID or None if failed
        """
        self._initialize_service()
        if not self.service:
            return None
        
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None
        
        try:
            # Determine target folder
            target_folder_id = self.folder_id
            if folder_name:
                target_folder_id = self._get_or_create_folder(folder_name)
                if not target_folder_id:
                    target_folder_id = self.folder_id
            
            # Determine filename and mime type
            filename = custom_name or file_path.name
            mime_type, _ = mimetypes.guess_type(str(file_path))
            mime_type = mime_type or 'application/octet-stream'
            
            # File metadata
            file_metadata = {
                'name': filename,
                'parents': [target_folder_id],
            }
            
            # Upload file
            media = MediaFileUpload(
                str(file_path),
                mimetype=mime_type,
                resumable=True,
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink',
            ).execute()
            
            file_id = file.get('id')
            web_link = file.get('webViewLink')
            
            logger.info(f"Uploaded {filename} to Google Drive: {web_link}")
            return file_id
            
        except Exception as e:
            logger.error(f"Failed to upload file {file_path}: {e}")
            return None
    
    def upload_ad_media(self, ad_data: dict) -> Optional[str]:
        """
        Upload ad media file to Google Drive.
        
        Args:
            ad_data: Ad metadata with local_filepath
            
        Returns:
            Google Drive file ID or None if failed
        """
        file_path = ad_data.get('local_filepath')
        if not file_path:
            logger.warning(f"No local file for ad {ad_data.get('id')}")
            return None
        
        # Determine folder based on competitor
        competitor = ad_data.get('competitor', 'Unknown')
        folder_path = f"Raw Ads/{competitor}"
        
        # Use ad ID as filename prefix
        ad_id = ad_data.get('id', 'unknown')
        file_ext = Path(file_path).suffix
        custom_name = f"{ad_id}{file_ext}"
        
        # Get or create the nested folder structure
        raw_ads_folder = self._get_or_create_folder('Raw Ads')
        if raw_ads_folder:
            competitor_folder = self._get_or_create_folder(competitor, raw_ads_folder)
            if competitor_folder:
                return self.upload_file(file_path, folder_name=None, custom_name=custom_name)
        
        # Fallback to root folder
        return self.upload_file(file_path, custom_name=custom_name)
    
    def upload_transcript(self, ad_data: dict) -> Optional[str]:
        """
        Upload transcript file to Google Drive.
        
        Args:
            ad_data: Ad metadata with transcript_file
            
        Returns:
            Google Drive file ID or None if failed
        """
        file_path = ad_data.get('transcript_file')
        if not file_path:
            logger.warning(f"No transcript file for ad {ad_data.get('id')}")
            return None
        
        return self.upload_file(file_path, folder_name='Transcripts')
    
    def upload_analysis(self, ad_data: dict) -> Optional[str]:
        """
        Upload analysis file to Google Drive.
        
        Args:
            ad_data: Ad metadata with analysis_file
            
        Returns:
            Google Drive file ID or None if failed
        """
        file_path = ad_data.get('analysis_file')
        if not file_path:
            logger.warning(f"No analysis file for ad {ad_data.get('id')}")
            return None
        
        return self.upload_file(file_path, folder_name='Analysis')
    
    def upload_script(self, ad_data: dict) -> Optional[str]:
        """
        Upload script file to Google Drive.
        
        Args:
            ad_data: Ad metadata with script_file
            
        Returns:
            Google Drive file ID or None if failed
        """
        file_path = ad_data.get('script_file')
        if not file_path:
            logger.warning(f"No script file for ad {ad_data.get('id')}")
            return None
        
        return self.upload_file(file_path, folder_name='Scripts')
    
    def upload_all_ad_files(self, ad_data: dict) -> dict:
        """
        Upload all files associated with an ad.
        
        Args:
            ad_data: Ad metadata dictionary
            
        Returns:
            Dictionary of Google Drive file IDs
        """
        results = {}
        
        # Upload media
        media_id = self.upload_ad_media(ad_data)
        if media_id:
            results['media_drive_id'] = media_id
        
        # Upload transcript
        transcript_id = self.upload_transcript(ad_data)
        if transcript_id:
            results['transcript_drive_id'] = transcript_id
        
        # Upload analysis
        analysis_id = self.upload_analysis(ad_data)
        if analysis_id:
            results['analysis_drive_id'] = analysis_id
        
        # Upload script
        script_id = self.upload_script(ad_data)
        if script_id:
            results['script_drive_id'] = script_id
        
        return results
    
    def get_file_link(self, file_id: str) -> Optional[str]:
        """
        Get the web view link for a file.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            Web view link or None if failed
        """
        self._initialize_service()
        if not self.service:
            return None
        
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='webViewLink',
            ).execute()
            
            return file.get('webViewLink')
            
        except Exception as e:
            logger.error(f"Failed to get file link: {e}")
            return None


async def main():
    """Test Google Drive integration."""
    manager = GoogleDriveManager()
    
    # Setup folder structure
    manager.setup_folder_structure()
    
    print("Google Drive setup complete")


if __name__ == '__main__':
    asyncio.run(main())

