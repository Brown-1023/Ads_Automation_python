"""
Claude AI Analysis Module

Handles ad transcript analysis using Anthropic's Claude API:
- Hook identification and analysis
- Angle/approach analysis  
- Emotional triggers detection
- Full comprehensive analysis
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
from anthropic import Anthropic
from loguru import logger

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config import ANTHROPIC_CONFIG, ANALYSIS_DIR, ANALYSIS_PROMPTS


class ClaudeAnalyzer:
    """Analyzer using Claude API for ad content analysis."""
    
    def __init__(self):
        self.api_key = ANTHROPIC_CONFIG['api_key']
        self.model = ANTHROPIC_CONFIG['model']
        self.max_tokens = ANTHROPIC_CONFIG['max_tokens']
        
        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("Anthropic API key not configured")
    
    def _call_claude(self, prompt: str, system_prompt: str = None) -> Optional[str]:
        """
        Make a call to Claude API.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            
        Returns:
            Claude's response text or None if failed
        """
        if not self.client:
            logger.error("Claude client not initialized")
            return None
            
        try:
            messages = [{"role": "user", "content": prompt}]
            
            kwargs = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": messages,
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            response = self.client.messages.create(**kwargs)
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None
    
    async def _call_claude_async(self, prompt: str, system_prompt: str = None) -> Optional[str]:
        """Async wrapper for Claude API calls."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._call_claude, prompt, system_prompt)
    
    async def analyze_hooks(self, transcript: str) -> Optional[dict]:
        """
        Analyze the hooks in an ad transcript.
        
        Args:
            transcript: The ad transcript text
            
        Returns:
            Dictionary with hook analysis or None if failed
        """
        prompt = ANALYSIS_PROMPTS['hook_analysis'].format(transcript=transcript)
        system = "You are an expert ad copywriter and marketing analyst. Analyze ads to identify effective hooks and attention-grabbing techniques. Provide structured, actionable insights."
        
        response = await self._call_claude_async(prompt, system)
        
        if response:
            return {
                'type': 'hook_analysis',
                'analysis': response,
                'analyzed_at': datetime.now().isoformat(),
            }
        return None
    
    async def analyze_angles(self, transcript: str) -> Optional[dict]:
        """
        Analyze the selling angles in an ad transcript.
        
        Args:
            transcript: The ad transcript text
            
        Returns:
            Dictionary with angle analysis or None if failed
        """
        prompt = ANALYSIS_PROMPTS['angle_analysis'].format(transcript=transcript)
        system = "You are an expert ad strategist specializing in direct response marketing. Analyze ads to identify selling angles, value propositions, and persuasion techniques."
        
        response = await self._call_claude_async(prompt, system)
        
        if response:
            return {
                'type': 'angle_analysis',
                'analysis': response,
                'analyzed_at': datetime.now().isoformat(),
            }
        return None
    
    async def analyze_emotional_triggers(self, transcript: str) -> Optional[dict]:
        """
        Analyze emotional triggers in an ad transcript.
        
        Args:
            transcript: The ad transcript text
            
        Returns:
            Dictionary with emotional trigger analysis or None if failed
        """
        prompt = ANALYSIS_PROMPTS['emotional_triggers'].format(transcript=transcript)
        system = "You are a consumer psychology expert specializing in advertising and persuasion. Identify emotional triggers, psychological techniques, and persuasion patterns in ad copy."
        
        response = await self._call_claude_async(prompt, system)
        
        if response:
            return {
                'type': 'emotional_triggers',
                'analysis': response,
                'analyzed_at': datetime.now().isoformat(),
            }
        return None
    
    async def full_analysis(self, transcript: str) -> Optional[dict]:
        """
        Perform comprehensive analysis of an ad transcript.
        
        Args:
            transcript: The ad transcript text
            
        Returns:
            Dictionary with full analysis or None if failed
        """
        prompt = ANALYSIS_PROMPTS['full_analysis'].format(transcript=transcript)
        system = """You are an elite creative strategist with expertise in:
- Direct response advertising
- Consumer psychology
- Copywriting and persuasion
- Video ad production

Provide comprehensive, actionable analysis that can be used to inform new creative development."""
        
        response = await self._call_claude_async(prompt, system)
        
        if response:
            return {
                'type': 'full_analysis',
                'analysis': response,
                'analyzed_at': datetime.now().isoformat(),
            }
        return None
    
    async def structured_analysis(self, transcript: str) -> Optional[dict]:
        """
        Perform structured analysis that returns parsed JSON for Google Sheets.
        
        Args:
            transcript: The ad transcript text
            
        Returns:
            Dictionary with structured fields or None if failed
        """
        prompt = ANALYSIS_PROMPTS['structured_analysis'].format(transcript=transcript)
        system = """You are an elite ad analyst. Extract insights from ad transcripts.
Return ONLY valid JSON with no markdown formatting or extra text.
Be concise but comprehensive in your analysis."""
        
        response = await self._call_claude_async(prompt, system)
        
        if response:
            try:
                # Clean up response - remove any markdown formatting
                cleaned = response.strip()
                if cleaned.startswith('```'):
                    # Remove markdown code blocks
                    cleaned = cleaned.split('```')[1]
                    if cleaned.startswith('json'):
                        cleaned = cleaned[4:]
                    cleaned = cleaned.strip()
                
                # Parse JSON
                parsed = json.loads(cleaned)
                parsed['analyzed_at'] = datetime.now().isoformat()
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse structured analysis JSON: {e}")
                # Return raw response if JSON parsing fails
                return {
                    'top_hooks': response[:500],
                    'top_angles': '',
                    'pain_points': '',
                    'emotional_triggers': '',
                    'why_this_works': '',
                    'raw_response': response,
                    'analyzed_at': datetime.now().isoformat(),
                }
        return None
    
    async def analyze_ad(self, ad_data: dict, analysis_type: str = 'structured') -> Optional[dict]:
        """
        Analyze an ad from its metadata.
        
        Args:
            ad_data: Ad metadata dictionary with transcript
            analysis_type: Type of analysis ('hooks', 'angles', 'emotional', 'full', 'structured')
            
        Returns:
            Updated ad data with analysis or None if failed
        """
        transcript = ad_data.get('transcript')
        if not transcript:
            logger.warning(f"No transcript for ad {ad_data.get('id')}")
            return ad_data
        
        logger.info(f"Analyzing ad {ad_data.get('id')} ({analysis_type})")
        
        # Perform requested analysis
        analysis_map = {
            'hooks': self.analyze_hooks,
            'angles': self.analyze_angles,
            'emotional': self.analyze_emotional_triggers,
            'full': self.full_analysis,
            'structured': self.structured_analysis,
        }
        
        analyzer_func = analysis_map.get(analysis_type, self.structured_analysis)
        analysis_result = await analyzer_func(transcript)
        
        if analysis_result:
            # Add analysis to ad data
            if 'analysis' not in ad_data:
                ad_data['analysis'] = {}
            ad_data['analysis'][analysis_type] = analysis_result
            
            # For structured analysis, also add fields directly to ad_data for easy access
            if analysis_type == 'structured':
                ad_data['top_hooks'] = analysis_result.get('top_hooks', '')
                ad_data['top_angles'] = analysis_result.get('top_angles', '')
                ad_data['pain_points'] = analysis_result.get('pain_points', '')
                ad_data['emotional_triggers'] = analysis_result.get('emotional_triggers', '')
                ad_data['why_this_works'] = analysis_result.get('why_this_works', '')
            
            # Save analysis to file
            analysis_file = ANALYSIS_DIR / f"{ad_data.get('id')}_analysis.json"
            async with aiofiles.open(analysis_file, 'w') as f:
                await f.write(json.dumps(ad_data['analysis'], indent=2))
            
            ad_data['analysis_file'] = str(analysis_file)
            logger.success(f"Analysis completed for ad {ad_data.get('id')}")
        
        return ad_data
    
    async def analyze_batch(self, ads: list[dict], analysis_type: str = 'full') -> list[dict]:
        """
        Analyze a batch of ads.
        
        Args:
            ads: List of ad metadata dictionaries
            analysis_type: Type of analysis to perform
            
        Returns:
            List of updated ad data with analyses
        """
        results = []
        
        for i, ad in enumerate(ads):
            logger.info(f"Analyzing ad {i+1}/{len(ads)}: {ad.get('id')}")
            result = await self.analyze_ad(ad, analysis_type)
            if result:
                results.append(result)
            
            # Small delay to avoid rate limits
            await asyncio.sleep(1)
        
        logger.info(f"Completed analysis for {len(results)}/{len(ads)} ads")
        return results


async def main():
    """Test analysis module."""
    analyzer = ClaudeAnalyzer()
    
    # Test with sample transcript
    sample_transcript = """
    Are you struggling to lose weight no matter what you try? 
    I was just like you until I discovered this one simple trick.
    In just 30 days, I lost 15 pounds without giving up my favorite foods.
    The secret? This natural supplement that targets stubborn belly fat.
    Click the link below to get 50% off today only!
    """
    
    result = await analyzer.full_analysis(sample_transcript)
    if result:
        print("Analysis:")
        print(result['analysis'])
    else:
        print("Analysis failed - check API key configuration")


if __name__ == '__main__':
    asyncio.run(main())

