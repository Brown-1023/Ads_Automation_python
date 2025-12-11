"""
Google Authentication Setup Script

This script helps you set up Google Cloud authentication for Sheets and Drive.
Run this once to configure your service account.
"""
import json
import os
from pathlib import Path

def main():
    print("=" * 60)
    print("Google Cloud Service Account Setup")
    print("=" * 60)
    print()
    
    config_dir = Path(__file__).parent / 'config'
    service_account_path = config_dir / 'google_service_account.json'
    
    if service_account_path.exists():
        print(f"✓ Service account file already exists: {service_account_path}")
        print()
        with open(service_account_path) as f:
            data = json.load(f)
        print(f"  Email: {data.get('client_email', 'N/A')}")
        print(f"  Project: {data.get('project_id', 'N/A')}")
        print()
        response = input("Do you want to replace it? (y/N): ")
        if response.lower() != 'y':
            print("Setup cancelled.")
            return
    
    print()
    print("To set up Google Cloud authentication:")
    print()
    print("1. Go to: https://console.cloud.google.com/")
    print("2. Create a new project or select an existing one")
    print("3. Enable the following APIs:")
    print("   - Google Sheets API")
    print("   - Google Drive API")
    print()
    print("4. Create a Service Account:")
    print("   - Go to 'IAM & Admin' > 'Service Accounts'")
    print("   - Click 'Create Service Account'")
    print("   - Give it a name (e.g., 'creative-engine-bot')")
    print("   - Grant it 'Editor' role")
    print("   - Click 'Done'")
    print()
    print("5. Create a key for the Service Account:")
    print("   - Click on the service account you just created")
    print("   - Go to 'Keys' tab")
    print("   - Click 'Add Key' > 'Create new key'")
    print("   - Choose 'JSON' format")
    print("   - Download the file")
    print()
    print("6. Share your Google Sheet with the service account email")
    print("   - Open your Google Sheet")
    print("   - Click 'Share'")
    print("   - Add the service account email (found in the JSON file)")
    print("   - Give it 'Editor' access")
    print()
    print("7. Share your Google Drive folder with the service account email")
    print("   - Open your Google Drive folder")
    print("   - Right-click > 'Share'")
    print("   - Add the service account email")
    print("   - Give it 'Editor' access")
    print()
    
    print("-" * 60)
    print()
    print("Paste your service account JSON content below.")
    print("(Copy the entire contents of the downloaded JSON file)")
    print("Press Enter twice when done:")
    print()
    
    lines = []
    empty_count = 0
    while True:
        line = input()
        if line == "":
            empty_count += 1
            if empty_count >= 2:
                break
        else:
            empty_count = 0
            lines.append(line)
    
    json_content = '\n'.join(lines)
    
    try:
        data = json.loads(json_content)
        
        # Validate required fields
        required_fields = ['type', 'project_id', 'private_key', 'client_email']
        missing = [f for f in required_fields if f not in data]
        
        if missing:
            print(f"\n❌ Error: Missing required fields: {missing}")
            return
        
        # Save the file
        with open(service_account_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print()
        print("=" * 60)
        print("✓ Service account saved successfully!")
        print("=" * 60)
        print()
        print(f"File: {service_account_path}")
        print(f"Email: {data.get('client_email')}")
        print(f"Project: {data.get('project_id')}")
        print()
        print("IMPORTANT: Share your Google Sheet and Drive folder with:")
        print(f"  {data.get('client_email')}")
        print()
        
    except json.JSONDecodeError as e:
        print(f"\n❌ Error: Invalid JSON format - {e}")
        return


if __name__ == '__main__':
    main()

