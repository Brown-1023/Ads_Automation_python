"""
Script Rewriter Module

Uses Claude to generate new ad scripts based on competitor analysis.
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
from config.config import ANTHROPIC_CONFIG, PROCESSED_DIR, ANALYSIS_PROMPTS


class ScriptRewriter:
    """Script rewriter using Claude API."""
    
    def __init__(self):
        self.api_key = ANTHROPIC_CONFIG['api_key']
        self.model = ANTHROPIC_CONFIG['model']
        self.max_tokens = ANTHROPIC_CONFIG['max_tokens']
        
        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("Anthropic API key not configured")
        
        # Default brand guidelines
        self.default_brand_name = "ThermoSlim"
        self.default_product_benefits = "Natural weight management, metabolism boost, appetite control"
    
    def _call_claude(self, prompt: str, system_prompt: str = None) -> Optional[str]:
        """Make a call to Claude API."""
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
    
    async def rewrite_script(
        self,
        transcript: str,
        analysis: str,
        brand_name: str = None,
        product_benefits: str = None,
        style_notes: str = None,
    ) -> Optional[dict]:
        """
        Generate a new script based on competitor ad analysis.
        
        Args:
            transcript: Original ad transcript
            analysis: Analysis of the original ad
            brand_name: Brand name to use in new script
            product_benefits: Key product benefits to highlight
            style_notes: Additional style/tone notes
            
        Returns:
            Dictionary with new script data or None if failed
        """
        brand_name = brand_name or self.default_brand_name
        product_benefits = product_benefits or self.default_product_benefits
        
        prompt = ANALYSIS_PROMPTS['script_rewrite'].format(
            transcript=transcript,
            analysis=analysis,
            brand_name=brand_name,
            product_benefits=product_benefits,
        )
        
        if style_notes:
            prompt += f"\n\nADDITIONAL STYLE NOTES:\n{style_notes}"
        
        # Add request for hook variations
        prompt += """

---

ALSO GENERATE 3 HOOK VARIATIONS:
After the main script, provide 3 alternative opening hooks (first 5 seconds) using different techniques:
1. Question Hook - Ask a provocative question
2. Story Hook - Start with a personal anecdote  
3. Statistic/Fact Hook - Lead with a surprising fact

Format as:
## HOOK VARIATIONS

**Hook 1 (Question):**
[Hook text]

**Hook 2 (Story):**
[Hook text]

**Hook 3 (Fact/Statistic):**
[Hook text]
"""
        
        system = """You are an elite direct response copywriter with decades of experience creating winning ad scripts.
Your scripts consistently generate high conversion rates and ROI.
You understand consumer psychology, persuasion techniques, and what makes people take action.
Create original, compelling scripts that capture attention and drive conversions."""
        
        response = await self._call_claude_async(prompt, system)
        
        if response:
            # Extract hook variations if present
            hook_variations = ''
            if 'HOOK VARIATIONS' in response:
                try:
                    hook_variations = response.split('HOOK VARIATIONS')[1].strip()
                except Exception:
                    pass
            
            return {
                'script': response,
                'hook_variations': hook_variations,
                'brand_name': brand_name,
                'product_benefits': product_benefits,
                'based_on_transcript': transcript[:200] + '...' if len(transcript) > 200 else transcript,
                'created_at': datetime.now().isoformat(),
            }
        return None
    
    async def generate_variations(
        self,
        base_script: str,
        num_variations: int = 3,
        variation_focus: str = 'hooks',
    ) -> list[dict]:
        """
        Generate variations of a script focusing on specific elements.
        
        Args:
            base_script: The base script to create variations from
            num_variations: Number of variations to generate
            variation_focus: What to vary ('hooks', 'ctas', 'angles', 'all')
            
        Returns:
            List of script variation dictionaries
        """
        focus_prompts = {
            'hooks': "Create {n} different opening hooks for this script. Each hook should use a different technique (question, story, shock, statistic, etc.)",
            'ctas': "Create {n} different call-to-action endings for this script. Each CTA should use a different urgency/motivation technique.",
            'angles': "Create {n} versions of this script using different selling angles while keeping the core message.",
            'all': "Create {n} complete variations of this script, each with a unique hook, angle, and CTA combination.",
        }
        
        variation_prompt = focus_prompts.get(variation_focus, focus_prompts['hooks'])
        
        prompt = f"""BASE SCRIPT:
{base_script}

TASK:
{variation_prompt.format(n=num_variations)}

For each variation:
1. Label it clearly (Variation 1, 2, 3, etc.)
2. Explain briefly why this variation might work
3. Provide the complete script section/variation

OUTPUT FORMAT:
## Variation 1: [Brief description]
**Why it works:** [1-2 sentences]
**Script:**
[Script content]

## Variation 2: [Brief description]
...
"""
        
        system = "You are an expert ad copywriter creating A/B test variations. Focus on high-impact differences that will genuinely test different approaches."
        
        response = await self._call_claude_async(prompt, system)
        
        if response:
            return [{
                'variations': response,
                'focus': variation_focus,
                'num_variations': num_variations,
                'base_script': base_script[:200] + '...' if len(base_script) > 200 else base_script,
                'created_at': datetime.now().isoformat(),
            }]
        return []
    
    async def generate_hook_variations(
        self,
        transcript: str,
        brand_name: str = None,
        product_benefits: str = None,
    ) -> Optional[dict]:
        """
        Generate 3 alternative hook variations for testing.
        
        Args:
            transcript: Original ad transcript
            brand_name: Brand name for hooks
            product_benefits: Key product benefits
            
        Returns:
            Dictionary with 3 hook variations or None if failed
        """
        brand_name = brand_name or self.default_brand_name
        product_benefits = product_benefits or self.default_product_benefits
        
        prompt = ANALYSIS_PROMPTS['hook_variations'].format(
            transcript=transcript,
            brand_name=brand_name,
            product_benefits=product_benefits,
        )
        
        system = "You are an expert ad copywriter. Generate compelling hooks. Return ONLY valid JSON."
        
        response = await self._call_claude_async(prompt, system)
        
        if response:
            try:
                # Clean up response
                cleaned = response.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('```')[1]
                    if cleaned.startswith('json'):
                        cleaned = cleaned[4:]
                    cleaned = cleaned.strip()
                
                parsed = json.loads(cleaned)
                return parsed
            except json.JSONDecodeError:
                logger.warning("Failed to parse hook variations JSON")
                return {
                    'hook_1_question': '',
                    'hook_2_story': '',
                    'hook_3_shock': '',
                    'raw_response': response,
                }
        return None
    
    async def rewrite_ad(
        self,
        ad_data: dict,
        brand_name: str = None,
        product_benefits: str = None,
    ) -> Optional[dict]:
        """
        Generate new script from an analyzed ad.
        
        Args:
            ad_data: Ad metadata with transcript and analysis
            brand_name: Brand name for new script
            product_benefits: Key product benefits
            
        Returns:
            Updated ad data with new script or None if failed
        """
        transcript = ad_data.get('transcript')
        
        # Try to get analysis - check both full and structured formats
        analysis = ''
        if ad_data.get('analysis'):
            if 'full' in ad_data['analysis']:
                analysis = ad_data['analysis']['full'].get('analysis', '')
            elif 'structured' in ad_data['analysis']:
                # Build analysis from structured data
                structured = ad_data['analysis']['structured']
                analysis = f"""
Top Hooks: {structured.get('top_hooks', '')}
Top Angles: {structured.get('top_angles', '')}
Pain Points: {structured.get('pain_points', '')}
Emotional Triggers: {structured.get('emotional_triggers', '')}
Why This Works: {structured.get('why_this_works', '')}
"""
        
        if not transcript:
            logger.warning(f"No transcript for ad {ad_data.get('id')}")
            return ad_data
        
        if not analysis:
            # If no analysis, just use transcript
            analysis = "Original ad transcript - analyze during rewrite"
        
        logger.info(f"Rewriting script for ad {ad_data.get('id')}")
        
        script_data = await self.rewrite_script(
            transcript=transcript,
            analysis=analysis,
            brand_name=brand_name,
            product_benefits=product_benefits,
        )
        
        if script_data:
            ad_data['rewritten_script'] = script_data
            
            # Also add brand_aligned_script field for Google Sheets
            ad_data['brand_aligned_script'] = script_data.get('script', '')
            
            # Generate separate hook variations
            hook_vars = await self.generate_hook_variations(
                transcript=transcript,
                brand_name=brand_name,
                product_benefits=product_benefits,
            )
            
            if hook_vars:
                # Format hook variations as a single string for Google Sheets
                hook_variations_text = f"""1. Question: {hook_vars.get('hook_1_question', '')}

2. Story: {hook_vars.get('hook_2_story', '')}

3. Shock/Stat: {hook_vars.get('hook_3_shock', '')}"""
                
                ad_data['hook_variations'] = hook_variations_text
                script_data['hook_variations_parsed'] = hook_vars
            
            # Save to file
            script_file = PROCESSED_DIR / f"{ad_data.get('id')}_script.json"
            async with aiofiles.open(script_file, 'w') as f:
                await f.write(json.dumps(script_data, indent=2))
            
            ad_data['script_file'] = str(script_file)
            logger.success(f"Script generated for ad {ad_data.get('id')}")
        
        return ad_data
    
    async def rewrite_batch(
        self,
        ads: list[dict],
        brand_name: str = None,
        product_benefits: str = None,
    ) -> list[dict]:
        """
        Generate new scripts for a batch of analyzed ads.
        
        Args:
            ads: List of ad metadata dictionaries
            brand_name: Brand name for new scripts
            product_benefits: Key product benefits
            
        Returns:
            List of updated ad data with new scripts
        """
        results = []
        
        for i, ad in enumerate(ads):
            logger.info(f"Rewriting script {i+1}/{len(ads)}: {ad.get('id')}")
            result = await self.rewrite_ad(ad, brand_name, product_benefits)
            if result:
                results.append(result)
            
            # Delay to avoid rate limits
            await asyncio.sleep(2)
        
        logger.info(f"Generated scripts for {len(results)}/{len(ads)} ads")
        return results


async def main():
    """Test script rewriter."""
    rewriter = ScriptRewriter()
    
    sample_transcript = """
    Are you struggling to lose weight no matter what you try? 
    I was just like you until I discovered this one simple trick.
    In just 30 days, I lost 15 pounds without giving up my favorite foods.
    The secret? This natural supplement that targets stubborn belly fat.
    Click the link below to get 50% off today only!
    """
    
    sample_analysis = """
    Hook: Personal story opener with relatable struggle
    Angle: Transformation/discovery narrative
    Emotional triggers: Frustration, hope, desire for easy solution
    CTA: Urgency with discount offer
    """
    
    result = await rewriter.rewrite_script(
        transcript=sample_transcript,
        analysis=sample_analysis,
        brand_name="ThermoSlim",
        product_benefits="Natural metabolism boost, appetite control, energy enhancement",
    )
    
    if result:
        print("Generated Script:")
        print(result['script'])
    else:
        print("Script generation failed - check API key configuration")


if __name__ == '__main__':
    asyncio.run(main())

