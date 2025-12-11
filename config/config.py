"""
Configuration management for the Creative Intelligence Engine.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
RAW_ADS_DIR = DATA_DIR / 'raw_ads'
TRANSCRIPTS_DIR = DATA_DIR / 'transcripts'
ANALYSIS_DIR = DATA_DIR / 'analysis_results'
PROCESSED_DIR = DATA_DIR / 'processed'
LOGS_DIR = PROJECT_ROOT / 'logs'

# Ensure directories exist
for dir_path in [RAW_ADS_DIR, TRANSCRIPTS_DIR, ANALYSIS_DIR, PROCESSED_DIR, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Atria Configuration
ATRIA_CONFIG = {
    'email': os.getenv('ATRIA_EMAIL', ''),
    'password': os.getenv('ATRIA_PASSWORD', ''),
    'base_url': 'https://app.tryatria.com',
    'login_url': 'https://app.tryatria.com/login',
    'discovery_url': 'https://app.tryatria.com/workspace/discovery',
}

# AssemblyAI Configuration
ASSEMBLYAI_CONFIG = {
    'api_key': os.getenv('ASSEMBLYAI_API_KEY', ''),
}

# Anthropic (Claude) Configuration
ANTHROPIC_CONFIG = {
    'api_key': os.getenv('ANTHROPIC_API_KEY', ''),
    'model': 'claude-sonnet-4-20250514',
    'max_tokens': 4096,
}

# Google Sheets Configuration
GOOGLE_SHEETS_CONFIG = {
    'spreadsheet_id': os.getenv('GOOGLE_SHEETS_ID', '1U3AT_QWiCWAIxelc3ngGP2CiKjn9GPxjgaPczUcE0nM'),
    'service_account_file': os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'config/google_service_account.json'),
}

# Google Drive Configuration
GOOGLE_DRIVE_CONFIG = {
    'folder_id': os.getenv('GOOGLE_DRIVE_FOLDER_ID', '1aK5jJORoquHZsU83T-UJne_vqvG2Fy7F'),
    'service_account_file': os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'config/google_service_account.json'),
}

# Make.com Webhook Configuration
MAKE_WEBHOOK_CONFIG = {
    'new_ad_url': os.getenv('MAKE_WEBHOOK_NEW_AD', ''),
    'analysis_complete_url': os.getenv('MAKE_WEBHOOK_ANALYSIS_COMPLETE', ''),
    'script_ready_url': os.getenv('MAKE_WEBHOOK_SCRIPT_READY', ''),
}

# Local Webhook Server Configuration
WEBHOOK_SERVER_CONFIG = {
    'port': int(os.getenv('WEBHOOK_SERVER_PORT', 5000)),
    'secret_key': os.getenv('WEBHOOK_SECRET_KEY', 'change-this-secret'),
}

# Competitors to track
COMPETITORS = [
    {
        'name': 'ColonBroom',
        'domain': 'colonbroom.com',
        'filter': 'GLP1',  # Only ads featuring GLP1 product
    },
    {
        'name': 'SkinnyFit',
        'domain': 'skinnyfit.com',
        'filter': None,  # All ads
    },
    {
        'name': 'SereneHerbs',
        'domain': 'sereneherbs.com',
        'filter': 'GLP1',  # Only GLP1 ads
    },
]

# Filtering settings
FILTER_CONFIG = {
    'min_days_active': int(os.getenv('MIN_AD_DAYS_ACTIVE', 7)),
    'max_days_active': None,  # No upper limit by default
}

# Analysis prompts
ANALYSIS_PROMPTS = {
    'hook_analysis': """Analyze this ad transcript and identify:
1. The opening hook (first 3-5 seconds)
2. Hook type (question, statement, shocking fact, story, etc.)
3. Emotional trigger used
4. Target pain point addressed

Transcript:
{transcript}

Provide a structured analysis.""",

    'angle_analysis': """Analyze this ad transcript and identify:
1. The main selling angle/approach
2. Key benefits highlighted
3. Unique value proposition
4. Call to action strategy

Transcript:
{transcript}

Provide a structured analysis.""",

    'emotional_triggers': """Analyze this ad transcript and identify all emotional triggers:
1. Primary emotion targeted (fear, desire, curiosity, etc.)
2. Secondary emotions
3. Specific trigger phrases/words
4. Psychological techniques used (scarcity, social proof, authority, etc.)

Transcript:
{transcript}

Provide a detailed breakdown.""",

    'full_analysis': """Perform a comprehensive analysis of this competitor ad:

Transcript:
{transcript}

Analyze and provide:
1. HOOK ANALYSIS
   - Opening hook (first 3-5 seconds)
   - Hook type
   - Effectiveness rating (1-10)

2. ANGLE/APPROACH
   - Main selling angle
   - Target audience
   - Key benefits highlighted

3. EMOTIONAL TRIGGERS
   - Primary emotion
   - Secondary emotions
   - Trigger phrases

4. STRUCTURE
   - Ad format/style
   - Pacing
   - Length effectiveness

5. CALL TO ACTION
   - CTA type
   - Urgency tactics
   - Offer presented

6. KEY TAKEAWAYS
   - What makes this ad work
   - Elements to potentially adapt
   - Weaknesses to avoid

Provide a detailed, actionable analysis.""",

    'script_rewrite': """Based on this competitor ad analysis and transcript, create a new, original script for our brand.

ORIGINAL TRANSCRIPT:
{transcript}

ANALYSIS:
{analysis}

BRAND GUIDELINES:
- Brand: {brand_name}
- Tone: Professional yet relatable
- Target audience: Health-conscious adults interested in weight management
- Key product benefits: {product_benefits}

Create a new script that:
1. Uses a similar effective hook structure but with original content
2. Maintains the emotional appeal
3. Follows our brand voice
4. Includes a clear call to action
5. Is approximately the same length as the original

OUTPUT FORMAT:
[HOOK - 0:00-0:05]
(Script content)

[PROBLEM - 0:05-0:15]
(Script content)

[SOLUTION - 0:15-0:30]
(Script content)

[BENEFITS - 0:30-0:45]
(Script content)

[CTA - 0:45-0:60]
(Script content)

---
SCRIPT NOTES:
(Any production notes or suggestions)""",
}

