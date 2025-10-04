#!/usr/bin/env python3
"""
Simple deployment script for Cerebrium
"""
import os

def main():
    print("Deploying Telegram bot to Cerebrium...")
    print("=" * 50)
    
    # Check required files
    required_files = [
        'telegram_post_bot.py',
        'requirements.txt',
        'cerebrium.toml'
    ]
    
    print("Checking files:")
    for file_name in required_files:
        if os.path.exists(file_name):
            print(f"  OK: {file_name}")
        else:
            print(f"  MISSING: {file_name}")
    
    print("\nDeployment instructions:")
    print("1. Open https://dashboard.cerebrium.ai")
    print("2. Find project with ID: p-09661aaf")
    print("3. Upload these files:")
    for file_name in required_files:
        if os.path.exists(file_name):
            print(f"   - {file_name}")
    
    print("\n4. Set environment variables:")
    print("   - TELEGRAM_BOT_TOKEN=8470292535:AAEnht_KLqU3zB01i_VsYzYZxn7zo1hUjI8")
    print("   - PORT=8080")
    print("   - PYTHONUNBUFFERED=1")
    
    print("\n5. Set deployment settings:")
    print("   - Runtime: Custom Python")
    print("   - Entry Point: python telegram_post_bot.py")
    print("   - Port: 8080")
    
    print("\n6. Click Deploy")
    
    print("\nAfter deployment, your bot will be available at:")
    print("https://telegram-post-bot.cerebrium.app")

if __name__ == "__main__":
    main()
