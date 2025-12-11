# Creative Intelligence Engine

A fully automated system for competitor ad analysis and script generation.

## Overview

This system automates the complete workflow of:
1. **Scraping** competitor ads from Atria ad spy platform
2. **Downloading** ad media (videos/images)
3. **Transcribing** video ads using AssemblyAI
4. **Analyzing** transcripts with Claude AI (hooks, angles, emotional triggers)
5. **Generating** new scripts based on competitor insights
6. **Storing** data in Google Sheets and Drive
7. **Integrating** with Make.com for workflow orchestration

## Quick Start

### 1. Install Dependencies

```bash
cd /home/ubuntu/work/Shifu_Ads_Automation
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Environment

Edit `config/.env` with your API keys:

```env
# Required: API Keys
ASSEMBLYAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here

# Atria Credentials (already configured)
ATRIA_EMAIL=office@thermoslim.co
ATRIA_PASSWORD=ThermoSlim1!
```

### 3. Set Up Google Authentication

Run the setup script:

```bash
python setup_google_auth.py
```

This will guide you through setting up a Google Cloud service account.

### 4. Run the Pipeline

```bash
# Run full pipeline
python main.py full

# Or run individual steps
python main.py scrape      # Scrape ads only
python main.py transcribe  # Transcribe scraped ads
python main.py analyze     # Analyze transcripts
python main.py rewrite     # Generate new scripts

# Start webhook server for Make.com
python main.py server --port 5000
```

## Project Structure

```
Shifu_Ads_Automation/
├── main.py                     # Main orchestrator
├── config/
│   ├── config.py               # Configuration settings
│   ├── .env                    # Environment variables
│   └── google_service_account.json  # Google Cloud credentials
├── src/
│   ├── scrapers/
│   │   └── atria_scraper.py    # Atria ad spy scraper
│   ├── transcription/
│   │   └── assemblyai_transcriber.py  # AssemblyAI integration
│   ├── analysis/
│   │   ├── claude_analyzer.py  # Claude AI analysis
│   │   └── script_rewriter.py  # Script generation
│   ├── google_integration/
│   │   ├── sheets_manager.py   # Google Sheets integration
│   │   └── drive_manager.py    # Google Drive integration
│   ├── webhooks/
│   │   └── make_webhook.py     # Make.com webhook integration
│   └── utils/
│       └── helpers.py          # Utility functions
├── data/
│   ├── raw_ads/                # Downloaded ad media
│   ├── transcripts/            # Transcription files
│   ├── analysis_results/       # Analysis outputs
│   └── processed/              # Final processed data
├── logs/                       # Application logs
└── tests/                      # Test files
```

## Configuration

### Competitors

Edit `config/config.py` to modify tracked competitors:

```python
COMPETITORS = [
    {
        'name': 'ColonBroom',
        'domain': 'colonbroom.com',
        'filter': 'GLP1',  # Only ads mentioning GLP1
    },
    {
        'name': 'SkinnyFit',
        'domain': 'skinnyfit.com',
        'filter': None,  # All ads
    },
    {
        'name': 'SereneHerbs',
        'domain': 'sereneherbs.com',
        'filter': 'GLP1',
    },
]
```

### Filtering

Ads are filtered by minimum active duration:

```python
FILTER_CONFIG = {
    'min_days_active': 7,  # Only ads running 7+ days
}
```

## Make.com Integration

### Webhook Endpoints

The system provides webhook endpoints for Make.com to trigger workflows:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/trigger-scrape` | POST | Start ad scraping |
| `/webhook/trigger-analysis` | POST | Analyze transcribed ads |
| `/webhook/trigger-rewrite` | POST | Generate new scripts |
| `/webhook/trigger-full-pipeline` | POST | Run complete pipeline |
| `/webhook/status` | GET | Get pipeline status |
| `/health` | GET | Health check |

### Example Make.com Scenario

1. **HTTP Module**: Call `/webhook/trigger-full-pipeline`
2. **Wait**: Add delay for processing
3. **HTTP Module**: Check `/webhook/status`
4. **Google Sheets**: Read new data
5. **Email/Slack**: Send notification

### Outbound Webhooks

The system sends notifications to Make.com when:
- New ad is scraped
- Analysis is complete
- Script is generated
- Batch processing finishes

Configure webhook URLs in `config/.env`:

```env
MAKE_WEBHOOK_NEW_AD=https://hook.make.com/xxx
MAKE_WEBHOOK_ANALYSIS_COMPLETE=https://hook.make.com/xxx
MAKE_WEBHOOK_SCRIPT_READY=https://hook.make.com/xxx
```

## Google Sheets Format

The system creates three sheets:

### Competitor Ads
| Column | Description |
|--------|-------------|
| ID | Unique ad identifier |
| Competitor | Competitor name |
| Domain | Competitor domain |
| Platform | Ad platform (Facebook, TikTok, etc.) |
| Days Active | How long the ad has been running |
| Ad Text Preview | First 200 chars of ad text |
| Transcript | Video transcript |
| Hook Type | Identified hook type |
| Main Angle | Selling angle |
| Emotional Triggers | Detected triggers |
| Rewritten Script | Generated script preview |

### Generated Scripts
| Column | Description |
|--------|-------------|
| ID | Script identifier |
| Based On Ad | Original ad reference |
| Script Content | Full generated script |
| Hook | Extracted hook section |
| CTA | Call to action section |
| Brand | Brand name used |

### Analysis Summary
Daily summary of processed ads with insights.

## API Requirements

### AssemblyAI
- Sign up at: https://www.assemblyai.com/
- Get API key from dashboard
- Pricing: Pay per audio hour

### Anthropic (Claude)
- Sign up at: https://console.anthropic.com/
- Create API key
- Model used: claude-sonnet-4-20250514

### Google Cloud
- Create project at: https://console.cloud.google.com/
- Enable Sheets and Drive APIs
- Create service account with Editor role
- Download JSON key file

## Troubleshooting

### Atria Login Issues
- Ensure credentials are correct in `.env`
- Check if account is active
- Try logging in manually first

### Transcription Failures
- Verify AssemblyAI API key
- Check file format (MP4, MP3, etc.)
- Ensure sufficient API credits

### Google API Errors
- Verify service account has access
- Check that APIs are enabled
- Ensure sheet/folder IDs are correct

### Make.com Connection Issues
- Verify webhook URLs are correct
- Check that endpoints are accessible
- Review Make.com scenario logs

## Running as a Service

To run the webhook server as a background service:

```bash
# Using nohup
nohup python main.py server --port 5000 > logs/server.log 2>&1 &

# Using systemd (create /etc/systemd/system/creative-engine.service)
[Unit]
Description=Creative Intelligence Engine
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/work/Shifu_Ads_Automation
ExecStart=/home/ubuntu/work/Shifu_Ads_Automation/venv/bin/python main.py server
Restart=always

[Install]
WantedBy=multi-user.target
```

## License

Proprietary - ThermoSlim Internal Use Only

