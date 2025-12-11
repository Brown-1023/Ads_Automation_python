"""
Make.com Webhook Integration Module

Handles bidirectional communication with Make.com:
- Outbound: Send notifications to Make.com when events occur
- Inbound: Receive triggers from Make.com to start workflows
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
from flask import Flask, request, jsonify
from loguru import logger

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config import MAKE_WEBHOOK_CONFIG, WEBHOOK_SERVER_CONFIG


class MakeWebhookClient:
    """Client for sending webhooks to Make.com."""
    
    def __init__(self):
        self.new_ad_url = MAKE_WEBHOOK_CONFIG['new_ad_url']
        self.analysis_complete_url = MAKE_WEBHOOK_CONFIG['analysis_complete_url']
        self.script_ready_url = MAKE_WEBHOOK_CONFIG['script_ready_url']
    
    async def _send_webhook(self, url: str, data: dict) -> bool:
        """
        Send a webhook to Make.com.
        
        Args:
            url: Webhook URL
            data: Data to send
            
        Returns:
            True if successful, False otherwise
        """
        # Skip if URL is not configured or is a placeholder
        if not url or 'your_' in url or url.startswith('http') is False:
            # Silently skip - webhook not configured yet
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=data,
                    headers={'Content-Type': 'application/json'},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        logger.info(f"Webhook sent successfully to {url[:50]}...")
                        return True
                    else:
                        logger.warning(f"Webhook failed: HTTP {response.status}")
                        return False
                        
        except Exception as e:
            logger.debug(f"Webhook skipped (not configured): {url[:30]}...")
            return False
    
    async def notify_new_ad(self, ad_data: dict) -> bool:
        """
        Notify Make.com about a new ad being scraped.
        
        Args:
            ad_data: Ad metadata dictionary
            
        Returns:
            True if successful, False otherwise
        """
        payload = {
            'event': 'new_ad_scraped',
            'timestamp': datetime.now().isoformat(),
            'ad_id': ad_data.get('id'),
            'competitor': ad_data.get('competitor'),
            'domain': ad_data.get('domain'),
            'platform': ad_data.get('platform'),
            'days_active': ad_data.get('days_active'),
            'media_url': ad_data.get('media_url'),
            'local_filepath': ad_data.get('local_filepath'),
        }
        
        return await self._send_webhook(self.new_ad_url, payload)
    
    async def notify_analysis_complete(self, ad_data: dict) -> bool:
        """
        Notify Make.com when analysis is complete.
        
        Args:
            ad_data: Ad metadata with analysis
            
        Returns:
            True if successful, False otherwise
        """
        analysis = ad_data.get('analysis', {}).get('full', {})
        
        payload = {
            'event': 'analysis_complete',
            'timestamp': datetime.now().isoformat(),
            'ad_id': ad_data.get('id'),
            'competitor': ad_data.get('competitor'),
            'transcript': ad_data.get('transcript', '')[:500],  # Truncate for webhook
            'analysis_summary': analysis.get('analysis', '')[:1000],
            'analysis_file': ad_data.get('analysis_file'),
        }
        
        return await self._send_webhook(self.analysis_complete_url, payload)
    
    async def notify_script_ready(self, ad_data: dict) -> bool:
        """
        Notify Make.com when a new script is generated.
        
        Args:
            ad_data: Ad metadata with rewritten script
            
        Returns:
            True if successful, False otherwise
        """
        script_data = ad_data.get('rewritten_script', {})
        
        payload = {
            'event': 'script_ready',
            'timestamp': datetime.now().isoformat(),
            'ad_id': ad_data.get('id'),
            'competitor': ad_data.get('competitor'),
            'script_preview': script_data.get('script', '')[:500],
            'brand_name': script_data.get('brand_name'),
            'script_file': ad_data.get('script_file'),
        }
        
        return await self._send_webhook(self.script_ready_url, payload)
    
    async def notify_batch_complete(self, summary: dict) -> bool:
        """
        Notify Make.com when a batch processing is complete.
        
        Args:
            summary: Summary of batch processing
            
        Returns:
            True if successful, False otherwise
        """
        payload = {
            'event': 'batch_complete',
            'timestamp': datetime.now().isoformat(),
            'total_ads': summary.get('total_ads', 0),
            'successful': summary.get('successful', 0),
            'failed': summary.get('failed', 0),
            'competitors_processed': summary.get('competitors', []),
        }
        
        # Use the analysis complete URL for batch notifications
        return await self._send_webhook(self.analysis_complete_url, payload)


def create_webhook_server(pipeline_handler):
    """
    Create a Flask app to receive webhooks from Make.com.
    
    Args:
        pipeline_handler: Async function to handle pipeline execution
        
    Returns:
        Flask app instance
    """
    app = Flask(__name__)
    app.config['SECRET_KEY'] = WEBHOOK_SERVER_CONFIG['secret_key']
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint."""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
        })
    
    @app.route('/webhook/trigger-scrape', methods=['POST'])
    def trigger_scrape():
        """
        Endpoint to trigger ad scraping from Make.com.
        
        Expected payload:
        {
            "competitors": ["colonbroom.com", "skinnyfit.com"],  // optional, uses all if not specified
            "min_days": 7,  // optional
        }
        """
        try:
            data = request.get_json() or {}
            competitors = data.get('competitors', None)
            min_days = data.get('min_days', 7)
            
            # Run pipeline in background
            asyncio.create_task(pipeline_handler(
                action='scrape',
                competitors=competitors,
                min_days=min_days,
            ))
            
            return jsonify({
                'status': 'accepted',
                'message': 'Scraping pipeline triggered',
                'timestamp': datetime.now().isoformat(),
            }), 202
            
        except Exception as e:
            logger.error(f"Error handling scrape trigger: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/webhook/trigger-analysis', methods=['POST'])
    def trigger_analysis():
        """
        Endpoint to trigger analysis from Make.com.
        
        Expected payload:
        {
            "ad_ids": ["ad_001", "ad_002"],  // optional, processes all pending if not specified
            "analysis_type": "full",  // optional: hooks, angles, emotional, full
        }
        """
        try:
            data = request.get_json() or {}
            ad_ids = data.get('ad_ids', None)
            analysis_type = data.get('analysis_type', 'full')
            
            asyncio.create_task(pipeline_handler(
                action='analyze',
                ad_ids=ad_ids,
                analysis_type=analysis_type,
            ))
            
            return jsonify({
                'status': 'accepted',
                'message': 'Analysis pipeline triggered',
                'timestamp': datetime.now().isoformat(),
            }), 202
            
        except Exception as e:
            logger.error(f"Error handling analysis trigger: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/webhook/trigger-rewrite', methods=['POST'])
    def trigger_rewrite():
        """
        Endpoint to trigger script rewriting from Make.com.
        
        Expected payload:
        {
            "ad_ids": ["ad_001", "ad_002"],  // optional
            "brand_name": "ThermoSlim",  // optional
            "product_benefits": "...",  // optional
        }
        """
        try:
            data = request.get_json() or {}
            ad_ids = data.get('ad_ids', None)
            brand_name = data.get('brand_name', None)
            product_benefits = data.get('product_benefits', None)
            
            asyncio.create_task(pipeline_handler(
                action='rewrite',
                ad_ids=ad_ids,
                brand_name=brand_name,
                product_benefits=product_benefits,
            ))
            
            return jsonify({
                'status': 'accepted',
                'message': 'Script rewriting pipeline triggered',
                'timestamp': datetime.now().isoformat(),
            }), 202
            
        except Exception as e:
            logger.error(f"Error handling rewrite trigger: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/webhook/trigger-full-pipeline', methods=['POST'])
    def trigger_full_pipeline():
        """
        Endpoint to trigger the full pipeline from Make.com.
        
        Expected payload:
        {
            "competitors": ["colonbroom.com"],  // optional
            "brand_name": "ThermoSlim",  // optional
        }
        """
        try:
            data = request.get_json() or {}
            
            asyncio.create_task(pipeline_handler(
                action='full',
                **data,
            ))
            
            return jsonify({
                'status': 'accepted',
                'message': 'Full pipeline triggered',
                'timestamp': datetime.now().isoformat(),
            }), 202
            
        except Exception as e:
            logger.error(f"Error handling full pipeline trigger: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/webhook/status', methods=['GET'])
    def get_status():
        """Get current pipeline status."""
        # This would need to be connected to actual pipeline state
        return jsonify({
            'status': 'idle',
            'last_run': None,
            'timestamp': datetime.now().isoformat(),
        })
    
    return app


def run_webhook_server(pipeline_handler):
    """
    Run the webhook server.
    
    Args:
        pipeline_handler: Async function to handle pipeline execution
    """
    app = create_webhook_server(pipeline_handler)
    port = WEBHOOK_SERVER_CONFIG['port']
    
    logger.info(f"Starting webhook server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == '__main__':
    # Simple test handler
    async def test_handler(**kwargs):
        print(f"Pipeline triggered with: {kwargs}")
    
    run_webhook_server(test_handler)

