#!/usr/bin/env python3
"""
Export pipeline results to client's desired format (12 columns)
"""

import json
import csv
import os
from datetime import datetime
from pathlib import Path

# Client's 12-column format
CLIENT_COLUMNS = [
    'Ad File Name / Link',
    'Competitor Name',
    'Platform (TikTok/FB/YouTube/Native)',
    'Transcript (Raw)',
    'Top Hooks',
    'Top Angles Used',
    'Pain Points',
    'Emotional Triggers',
    'Why This Ad Works',
    'Brand-Aligned Script',
    'Hook Variations (3 Options)',
    'Notes / Approval'
]

def load_latest_results():
    """Load the most recent pipeline results file."""
    processed_dir = Path('data/processed')
    result_files = list(processed_dir.glob('pipeline_results_*.json'))
    
    if not result_files:
        print("No pipeline results found!")
        return None
    
    # Get the most recent file
    latest_file = max(result_files, key=lambda f: f.stat().st_mtime)
    print(f"Loading: {latest_file}")
    
    with open(latest_file, 'r') as f:
        return json.load(f)


def format_hooks(ad_data):
    """Extract and format top hooks."""
    hooks = ad_data.get('top_hooks', '')
    if not hooks:
        hooks = ad_data.get('analysis', {}).get('structured', {}).get('top_hooks', '')
    return hooks if hooks else 'N/A'


def format_angles(ad_data):
    """Extract and format top angles."""
    angles = ad_data.get('top_angles', '')
    if not angles:
        angles = ad_data.get('analysis', {}).get('structured', {}).get('top_angles', '')
    
    # If it's a list, join it
    if isinstance(angles, list):
        return ', '.join(angles)
    return angles if angles else 'N/A'


def format_pain_points(ad_data):
    """Extract and format pain points."""
    pain_points = ad_data.get('pain_points', '')
    if not pain_points:
        pain_points = ad_data.get('analysis', {}).get('structured', {}).get('pain_points', '')
    
    # If it's a list, join it
    if isinstance(pain_points, list):
        return ', '.join(pain_points)
    return pain_points if pain_points else 'N/A'


def format_emotional_triggers(ad_data):
    """Extract and format emotional triggers."""
    triggers = ad_data.get('emotional_triggers', '')
    if not triggers:
        triggers = ad_data.get('analysis', {}).get('structured', {}).get('emotional_triggers', '')
    
    # If it's a list, join it
    if isinstance(triggers, list):
        return ', '.join(triggers)
    return triggers if triggers else 'N/A'


def format_why_works(ad_data):
    """Extract and format why the ad works."""
    why = ad_data.get('why_this_works', '')
    if not why:
        why = ad_data.get('analysis', {}).get('structured', {}).get('why_this_works', '')
    return why if why else 'N/A'


def format_script(ad_data):
    """Extract and format the brand-aligned script."""
    script = ad_data.get('brand_aligned_script', '')
    if not script:
        script = ad_data.get('rewritten_script', {}).get('script', '')
    return script if script else 'N/A'


def format_hook_variations(ad_data):
    """Extract and format hook variations."""
    variations = ad_data.get('hook_variations', '')
    if not variations:
        variations = ad_data.get('rewritten_script', {}).get('hook_variations', '')
    return variations if variations else 'N/A'


def format_platform(ad_data):
    """Format platform name with improved detection."""
    platform = ad_data.get('platform', 'Unknown')
    
    # If already detected, return it
    if platform and platform != 'Unknown':
        return platform
    
    # Try to detect from ad text or URL
    ad_text = (ad_data.get('ad_text', '') or '').lower()
    media_url = (ad_data.get('media_url', '') or '').lower()
    
    # Check for platform indicators
    if 'tiktok' in ad_text or 'tiktok' in media_url:
        return 'TikTok'
    elif 'youtube' in ad_text or 'youtube' in media_url or 'youtu.be' in media_url:
        return 'YouTube'
    elif 'instagram' in ad_text or 'ig' in ad_text:
        return 'Instagram'
    elif 'facebook' in ad_text or 'fb.com' in media_url:
        return 'Facebook'
    elif 'tryatria.com' in media_url:
        # Atria primarily indexes Meta (Facebook/Instagram) ads
        return 'Meta (FB/IG)'
    
    return 'Unknown'


def format_transcript(ad_data):
    """Format transcript with helpful message if empty."""
    transcript = ad_data.get('transcript', '')
    
    if not transcript or transcript.strip() == '':
        # Check video duration
        duration = ad_data.get('video_duration', '')
        if duration:
            return f'[No speech detected - {duration} video]'
        return '[No speech detected in video]'
    
    return transcript


def convert_to_client_format(results):
    """Convert pipeline results to client's 12-column format."""
    client_data = []
    
    for ad in results:
        # Get transcript
        transcript = format_transcript(ad)
        
        # If no transcript, analysis fields will be empty - show helpful message
        has_transcript = ad.get('transcript', '').strip() != ''
        
        row = {
            'Ad File Name / Link': ad.get('media_url', ad.get('local_filepath', 'N/A')),
            'Competitor Name': ad.get('competitor', 'N/A'),
            'Platform (TikTok/FB/YouTube/Native)': format_platform(ad),
            'Transcript (Raw)': transcript,
            'Top Hooks': format_hooks(ad) if has_transcript else '[Requires transcript]',
            'Top Angles Used': format_angles(ad) if has_transcript else '[Requires transcript]',
            'Pain Points': format_pain_points(ad) if has_transcript else '[Requires transcript]',
            'Emotional Triggers': format_emotional_triggers(ad) if has_transcript else '[Requires transcript]',
            'Why This Ad Works': format_why_works(ad) if has_transcript else '[Requires transcript]',
            'Brand-Aligned Script': format_script(ad) if has_transcript else '[Requires transcript]',
            'Hook Variations (3 Options)': format_hook_variations(ad) if has_transcript else '[Requires transcript]',
            'Notes / Approval': ''  # Empty for client to fill in
        }
        client_data.append(row)
    
    return client_data


def export_to_csv(client_data, output_path):
    """Export to CSV file."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CLIENT_COLUMNS)
        writer.writeheader()
        writer.writerows(client_data)
    print(f"✅ CSV exported: {output_path}")


def export_to_json(client_data, output_path):
    """Export to JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(client_data, f, indent=2, ensure_ascii=False)
    print(f"✅ JSON exported: {output_path}")


def main():
    print("=" * 60)
    print("Exporting Pipeline Results to Client Format")
    print("=" * 60)
    
    # Load results
    results = load_latest_results()
    if not results:
        return
    
    print(f"Found {len(results)} ads to export")
    
    # Convert to client format
    client_data = convert_to_client_format(results)
    
    # Create output directory
    output_dir = Path('data/exports')
    output_dir.mkdir(exist_ok=True)
    
    # Generate timestamp for filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Export to both formats
    csv_path = output_dir / f'client_export_{timestamp}.csv'
    json_path = output_dir / f'client_export_{timestamp}.json'
    
    export_to_csv(client_data, csv_path)
    export_to_json(client_data, json_path)
    
    # Calculate statistics
    complete_ads = sum(1 for ad in client_data if '[Requires transcript]' not in ad['Top Hooks'])
    incomplete_ads = len(client_data) - complete_ads
    
    # Count by competitor
    competitors = {}
    for ad in client_data:
        comp = ad['Competitor Name']
        competitors[comp] = competitors.get(comp, 0) + 1
    
    # Count by platform
    platforms = {}
    for ad in client_data:
        plat = ad['Platform (TikTok/FB/YouTube/Native)']
        platforms[plat] = platforms.get(plat, 0) + 1
    
    print()
    print("=" * 60)
    print("Export Complete!")
    print("=" * 60)
    print(f"📊 Total ads exported: {len(client_data)}")
    print(f"✅ Complete (with analysis): {complete_ads}")
    print(f"⚠️  Incomplete (no transcript): {incomplete_ads}")
    print()
    print("By Competitor:")
    for comp, count in sorted(competitors.items()):
        print(f"  • {comp}: {count} ads")
    print()
    print("By Platform:")
    for plat, count in sorted(platforms.items()):
        print(f"  • {plat}: {count} ads")
    print()
    print(f"📁 CSV file: {csv_path}")
    print(f"📁 JSON file: {json_path}")


if __name__ == '__main__':
    main()

