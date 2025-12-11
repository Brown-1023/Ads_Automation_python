"""
AssemblyAI Transcription Module

Handles video/audio transcription using AssemblyAI API.
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
import assemblyai as aai
from loguru import logger

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config import ASSEMBLYAI_CONFIG, TRANSCRIPTS_DIR


class AssemblyAITranscriber:
    """Transcriber using AssemblyAI API."""
    
    def __init__(self):
        self.api_key = ASSEMBLYAI_CONFIG['api_key']
        if self.api_key:
            aai.settings.api_key = self.api_key
        else:
            logger.warning("AssemblyAI API key not configured")
        
    def transcribe_file(self, file_path: str) -> Optional[dict]:
        """
        Transcribe an audio/video file.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            Dictionary with transcription data or None if failed
        """
        try:
            logger.info(f"Starting transcription for: {file_path}")
            
            # Configure transcription settings
            # Note: speech_model defaults to AssemblyAI's best available model
            # entity_detection disabled due to SDK compatibility issues with new entity types
            config = aai.TranscriptionConfig(
                speaker_labels=True,
                auto_highlights=True,
                sentiment_analysis=True,
                entity_detection=False,  # Disabled - SDK doesn't support all entity types from API
                iab_categories=True,
            )
            
            # Create transcriber and transcribe
            transcriber = aai.Transcriber(config=config)
            transcript = transcriber.transcribe(file_path)
            
            if transcript.status == aai.TranscriptStatus.error:
                logger.error(f"Transcription failed: {transcript.error}")
                return None
            
            # Extract relevant data
            result = {
                'id': transcript.id,
                'file_path': file_path,
                'text': transcript.text,
                'confidence': transcript.confidence,
                'duration_seconds': transcript.audio_duration,
                'word_count': len(transcript.words) if transcript.words else 0,
                'transcribed_at': datetime.now().isoformat(),
            }
            
            # Add speaker labels if available
            if transcript.utterances:
                result['utterances'] = [
                    {
                        'speaker': u.speaker,
                        'text': u.text,
                        'start': u.start,
                        'end': u.end,
                        'confidence': u.confidence,
                    }
                    for u in transcript.utterances
                ]
            
            # Add highlights if available
            if transcript.auto_highlights and transcript.auto_highlights.results:
                result['highlights'] = [
                    {
                        'text': h.text,
                        'count': h.count,
                        'rank': h.rank,
                    }
                    for h in transcript.auto_highlights.results
                ]
            
            # Add sentiment analysis if available
            if transcript.sentiment_analysis:
                result['sentiment'] = [
                    {
                        'text': s.text,
                        'sentiment': s.sentiment.value,
                        'confidence': s.confidence,
                    }
                    for s in transcript.sentiment_analysis
                ]
            
            # Add entities if available
            if transcript.entities:
                result['entities'] = [
                    {
                        'text': e.text,
                        'entity_type': e.entity_type.value,
                    }
                    for e in transcript.entities
                ]
            
            # Add IAB categories if available
            if transcript.iab_categories and transcript.iab_categories.summary:
                result['categories'] = {
                    k: v for k, v in transcript.iab_categories.summary.items()
                }
            
            logger.success(f"Transcription completed: {len(result['text'])} characters")
            return result
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
    
    async def transcribe_file_async(self, file_path: str) -> Optional[dict]:
        """
        Async wrapper for transcription.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            Dictionary with transcription data or None if failed
        """
        # Run synchronous transcription in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.transcribe_file, file_path)
    
    async def transcribe_ad(self, ad_data: dict) -> Optional[dict]:
        """
        Transcribe an ad from its metadata.
        
        Args:
            ad_data: Ad metadata dictionary with local_filepath
            
        Returns:
            Updated ad data with transcription or None if failed
        """
        file_path = ad_data.get('local_filepath')
        if not file_path:
            logger.warning(f"No local file for ad {ad_data.get('id')}")
            return None
        
        # Check if file is a video (needs transcription)
        if not any(file_path.endswith(ext) for ext in ['.mp4', '.webm', '.mov', '.avi', '.mp3', '.wav']):
            logger.info(f"Skipping non-video file: {file_path}")
            return ad_data
        
        # Transcribe
        transcript_data = await self.transcribe_file_async(file_path)
        
        if transcript_data:
            # Add transcription to ad data
            ad_data['transcript'] = transcript_data['text']
            ad_data['transcript_data'] = transcript_data
            
            # Save transcript to file
            transcript_file = TRANSCRIPTS_DIR / f"{ad_data.get('id')}_transcript.json"
            async with aiofiles.open(transcript_file, 'w') as f:
                await f.write(json.dumps(transcript_data, indent=2))
            
            ad_data['transcript_file'] = str(transcript_file)
            logger.info(f"Saved transcript to {transcript_file}")
        
        return ad_data
    
    async def transcribe_batch(self, ads: list[dict]) -> list[dict]:
        """
        Transcribe a batch of ads.
        
        Args:
            ads: List of ad metadata dictionaries
            
        Returns:
            List of updated ad data with transcriptions
        """
        results = []
        
        for i, ad in enumerate(ads):
            logger.info(f"Transcribing ad {i+1}/{len(ads)}: {ad.get('id')}")
            result = await self.transcribe_ad(ad)
            if result:
                results.append(result)
            
            # Small delay to avoid rate limits
            await asyncio.sleep(1)
        
        logger.info(f"Completed transcription for {len(results)}/{len(ads)} ads")
        return results


async def main():
    """Test transcription module."""
    transcriber = AssemblyAITranscriber()
    
    # Test with a sample file if available
    sample_files = list(Path('../data/raw_ads').glob('*.mp4'))
    if sample_files:
        result = await transcriber.transcribe_file_async(str(sample_files[0]))
        if result:
            print(f"Transcription: {result['text'][:200]}...")
    else:
        print("No sample files found for testing")


if __name__ == '__main__':
    asyncio.run(main())

