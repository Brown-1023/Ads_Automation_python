"""
Creative Intelligence Engine - Main Orchestrator

This is the main entry point for the automation system.
It orchestrates the full pipeline:
1. Scrape competitor ads from Atria
2. Transcribe video ads using AssemblyAI
3. Analyze transcripts using Claude
4. Generate new scripts using Claude
5. Store data in Google Sheets
6. Upload files to Google Drive
7. Send notifications via Make.com webhooks
"""
import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

# Import all modules
from config.config import (
    COMPETITORS,
    RAW_ADS_DIR,
    TRANSCRIPTS_DIR,
    ANALYSIS_DIR,
    PROCESSED_DIR,
)
from src.scrapers import AtriaScraper
from src.transcription import AssemblyAITranscriber
from src.analysis import ClaudeAnalyzer, ScriptRewriter
from src.google_integration import GoogleSheetsManager, GoogleDriveManager
from src.webhooks import MakeWebhookClient
from src.utils import setup_logging, save_json, load_json


class CreativeIntelligenceEngine:
    """Main orchestrator for the Creative Intelligence Engine."""
    
    def __init__(self):
        self.scraper = None
        self.transcriber = AssemblyAITranscriber()
        self.analyzer = ClaudeAnalyzer()
        self.rewriter = ScriptRewriter()
        self.sheets = GoogleSheetsManager()
        self.drive = GoogleDriveManager()
        self.webhook = MakeWebhookClient()
        
        # Track processing state
        self.processed_ads = []
        self.failed_ads = []
        
    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing Creative Intelligence Engine...")
        
        # Setup Google integrations
        self.sheets.setup_sheets()
        self.drive.setup_folder_structure()
        
        logger.success("Engine initialized successfully")
    
    async def scrape_ads(
        self,
        competitors: list[dict] = None,
        min_days: int = 7,
    ) -> list[dict]:
        """
        Scrape ads from Atria for specified competitors.
        
        Args:
            competitors: List of competitor configs (uses default if None)
            min_days: Minimum days active filter
            
        Returns:
            List of scraped ad metadata
        """
        competitors = competitors or COMPETITORS
        all_ads = []
        
        logger.info(f"Starting scrape for {len(competitors)} competitors")
        
        async with AtriaScraper() as scraper:
            all_ads = await scraper.scrape_all_competitors()
        
        logger.info(f"Scraped {len(all_ads)} total ads")
        
        # Notify Make.com about new ads
        for ad in all_ads:
            await self.webhook.notify_new_ad(ad)
        
        return all_ads
    
    async def transcribe_ads(self, ads: list[dict]) -> list[dict]:
        """
        Transcribe all video ads.
        
        Args:
            ads: List of ad metadata dictionaries
            
        Returns:
            List of ads with transcriptions
        """
        logger.info(f"Starting transcription for {len(ads)} ads")
        
        transcribed_ads = await self.transcriber.transcribe_batch(ads)
        
        logger.info(f"Transcribed {len(transcribed_ads)} ads")
        return transcribed_ads
    
    async def analyze_ads(
        self,
        ads: list[dict],
        analysis_type: str = 'full',
    ) -> list[dict]:
        """
        Analyze all transcribed ads.
        
        Args:
            ads: List of ad metadata with transcripts
            analysis_type: Type of analysis to perform
            
        Returns:
            List of ads with analysis
        """
        logger.info(f"Starting {analysis_type} analysis for {len(ads)} ads")
        
        analyzed_ads = await self.analyzer.analyze_batch(ads, analysis_type)
        
        # Notify Make.com about completed analyses
        for ad in analyzed_ads:
            await self.webhook.notify_analysis_complete(ad)
        
        logger.info(f"Analyzed {len(analyzed_ads)} ads")
        return analyzed_ads
    
    async def rewrite_scripts(
        self,
        ads: list[dict],
        brand_name: str = None,
        product_benefits: str = None,
    ) -> list[dict]:
        """
        Generate new scripts from analyzed ads.
        
        Args:
            ads: List of ad metadata with analysis
            brand_name: Brand name for new scripts
            product_benefits: Key product benefits
            
        Returns:
            List of ads with new scripts
        """
        logger.info(f"Starting script generation for {len(ads)} ads")
        
        rewritten_ads = await self.rewriter.rewrite_batch(
            ads,
            brand_name=brand_name,
            product_benefits=product_benefits,
        )
        
        # Notify Make.com about new scripts
        for ad in rewritten_ads:
            await self.webhook.notify_script_ready(ad)
        
        logger.info(f"Generated scripts for {len(rewritten_ads)} ads")
        return rewritten_ads
    
    async def store_data(self, ads: list[dict]):
        """
        Store processed ads in Google Sheets and Drive.
        
        Args:
            ads: List of fully processed ad metadata
        """
        logger.info(f"Storing {len(ads)} ads to Google integrations")
        
        for ad in ads:
            # Add to Google Sheets
            self.sheets.add_ad(ad)
            
            # Add script to scripts sheet
            if ad.get('rewritten_script'):
                self.sheets.add_script(ad)
            
            # Upload files to Google Drive
            drive_ids = self.drive.upload_all_ad_files(ad)
            ad.update(drive_ids)
        
        logger.info("Data storage complete")
    
    async def run_full_pipeline(
        self,
        competitors: list[dict] = None,
        brand_name: str = None,
        product_benefits: str = None,
    ) -> dict:
        """
        Run the complete pipeline from scraping to storage.
        
        Args:
            competitors: Optional list of competitors to process
            brand_name: Brand name for script rewriting
            product_benefits: Product benefits for script rewriting
            
        Returns:
            Summary of pipeline execution
        """
        start_time = datetime.now()
        logger.info("=" * 50)
        logger.info("Starting Full Pipeline Execution")
        logger.info("=" * 50)
        
        try:
            # Initialize
            await self.initialize()
            
            # Step 1: Scrape ads
            logger.info("Step 1: Scraping ads from Atria...")
            ads = await self.scrape_ads(competitors)
            
            if not ads:
                logger.warning("No ads scraped, pipeline complete")
                return {
                    'status': 'complete',
                    'total_ads': 0,
                    'message': 'No ads found to process',
                }
            
            # Step 2: Transcribe
            logger.info("Step 2: Transcribing video ads...")
            ads = await self.transcribe_ads(ads)
            
            # Step 3: Analyze
            logger.info("Step 3: Analyzing ad transcripts...")
            ads = await self.analyze_ads(ads, analysis_type='full')
            
            # Step 4: Rewrite scripts
            logger.info("Step 4: Generating new scripts...")
            ads = await self.rewrite_scripts(ads, brand_name, product_benefits)
            
            # Step 5: Store data
            logger.info("Step 5: Storing data to Google Sheets/Drive...")
            await self.store_data(ads)
            
            # Save final results locally
            results_file = PROCESSED_DIR / f"pipeline_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            save_json(ads, results_file)
            
            # Calculate summary
            duration = (datetime.now() - start_time).total_seconds()
            summary = {
                'status': 'complete',
                'total_ads': len(ads),
                'successful': len([a for a in ads if a.get('rewritten_script')]),
                'failed': len([a for a in ads if not a.get('rewritten_script')]),
                'competitors': list(set(a.get('competitor') for a in ads)),
                'duration_seconds': duration,
                'results_file': str(results_file),
            }
            
            # Notify Make.com of completion
            await self.webhook.notify_batch_complete(summary)
            
            logger.info("=" * 50)
            logger.success(f"Pipeline Complete in {duration:.1f}s")
            logger.info(f"Processed {summary['total_ads']} ads, {summary['successful']} successful")
            logger.info("=" * 50)
            
            return summary
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            return {
                'status': 'error',
                'error': str(e),
            }
    
    async def run_scrape_only(self, competitors: list[dict] = None) -> list[dict]:
        """Run only the scraping step."""
        await self.initialize()
        return await self.scrape_ads(competitors)
    
    async def run_transcribe_only(self, ads_file: str = None) -> list[dict]:
        """Run only the transcription step on existing ads."""
        if ads_file:
            ads = load_json(ads_file) or []
        else:
            # Load most recent scrape results
            results_files = sorted(RAW_ADS_DIR.glob('scrape_results_*.json'), reverse=True)
            if results_files:
                ads = load_json(results_files[0]) or []
            else:
                logger.error("No ads found to transcribe")
                return []
        
        return await self.transcribe_ads(ads)
    
    async def run_analyze_only(
        self,
        ads_file: str = None,
        analysis_type: str = 'full',
    ) -> list[dict]:
        """Run only the analysis step on existing transcribed ads."""
        if ads_file:
            ads = load_json(ads_file) or []
        else:
            # Load most recent transcription results
            results_files = sorted(TRANSCRIPTS_DIR.glob('*.json'), reverse=True)
            if results_files:
                ads = load_json(results_files[0]) or []
            else:
                logger.error("No transcribed ads found to analyze")
                return []
        
        return await self.analyze_ads(ads, analysis_type)
    
    async def run_rewrite_only(
        self,
        ads_file: str = None,
        brand_name: str = None,
        product_benefits: str = None,
    ) -> list[dict]:
        """Run only the script rewriting step on existing analyzed ads."""
        if ads_file:
            ads = load_json(ads_file) or []
        else:
            # Load most recent analysis results
            results_files = sorted(ANALYSIS_DIR.glob('*.json'), reverse=True)
            if results_files:
                ads = load_json(results_files[0]) or []
            else:
                logger.error("No analyzed ads found to rewrite")
                return []
        
        return await self.rewrite_scripts(ads, brand_name, product_benefits)


async def pipeline_handler(**kwargs):
    """
    Handler for webhook-triggered pipeline execution.
    Called by the webhook server when Make.com triggers a workflow.
    """
    engine = CreativeIntelligenceEngine()
    action = kwargs.get('action', 'full')
    
    if action == 'scrape':
        await engine.run_scrape_only(kwargs.get('competitors'))
    elif action == 'analyze':
        await engine.run_analyze_only(
            kwargs.get('ads_file'),
            kwargs.get('analysis_type', 'full'),
        )
    elif action == 'rewrite':
        await engine.run_rewrite_only(
            kwargs.get('ads_file'),
            kwargs.get('brand_name'),
            kwargs.get('product_benefits'),
        )
    else:  # full
        await engine.run_full_pipeline(
            kwargs.get('competitors'),
            kwargs.get('brand_name'),
            kwargs.get('product_benefits'),
        )


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description='Creative Intelligence Engine - Competitor Ad Analysis & Script Generation'
    )
    
    parser.add_argument(
        'action',
        choices=['full', 'scrape', 'transcribe', 'analyze', 'rewrite', 'server'],
        default='full',
        help='Pipeline action to run',
    )
    
    parser.add_argument(
        '--ads-file',
        help='Path to ads JSON file (for transcribe/analyze/rewrite)',
    )
    
    parser.add_argument(
        '--brand-name',
        default='ThermoSlim',
        help='Brand name for script rewriting',
    )
    
    parser.add_argument(
        '--product-benefits',
        default='Natural weight management, metabolism boost, appetite control',
        help='Product benefits for script rewriting',
    )
    
    parser.add_argument(
        '--analysis-type',
        choices=['hooks', 'angles', 'emotional', 'full'],
        default='full',
        help='Type of analysis to perform',
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level',
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port for webhook server (when action=server)',
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    # Create engine
    engine = CreativeIntelligenceEngine()
    
    if args.action == 'server':
        # Run webhook server
        from src.webhooks import run_webhook_server
        run_webhook_server(pipeline_handler)
    else:
        # Run pipeline action
        if args.action == 'full':
            result = asyncio.run(engine.run_full_pipeline(
                brand_name=args.brand_name,
                product_benefits=args.product_benefits,
            ))
        elif args.action == 'scrape':
            result = asyncio.run(engine.run_scrape_only())
        elif args.action == 'transcribe':
            result = asyncio.run(engine.run_transcribe_only(args.ads_file))
        elif args.action == 'analyze':
            result = asyncio.run(engine.run_analyze_only(
                args.ads_file,
                args.analysis_type,
            ))
        elif args.action == 'rewrite':
            result = asyncio.run(engine.run_rewrite_only(
                args.ads_file,
                args.brand_name,
                args.product_benefits,
            ))
        
        print(f"\nResult: {json.dumps(result, indent=2) if isinstance(result, dict) else f'{len(result)} items'}")


if __name__ == '__main__':
    main()

