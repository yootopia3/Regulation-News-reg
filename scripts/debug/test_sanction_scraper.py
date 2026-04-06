"""
Test script for sanction notice scraping.
This script tests the new fetch_sanction_items method WITHOUT affecting production data.
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz

# Path setup
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from src.collectors.scraper import ContentScraper
import json

def test_sanction_scraping():
    # Load config
    config_path = os.path.join(project_root, 'config', 'agencies.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Get sanction agencies
    sanction_agencies = [a for a in config['agencies'] if a['code'] in ['FSS_SANCTION', 'FSS_MGMT_NOTICE']]
    
    # First, let's manually check what the page looks like
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    month_ago = now - timedelta(days=30)  # Changed to 30 days
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for agency in sanction_agencies:
        print(f"\n{'='*60}")
        print(f"Testing: {agency['code']} - {agency['name']}")
        print(f"{'='*60}")
        
        base_url = agency['url']
        full_url = f"{base_url}&sdate={month_ago.strftime('%Y-%m-%d')}&edate={now.strftime('%Y-%m-%d')}"
        print(f"URL: {full_url}")
        
        try:
            resp = requests.get(full_url, headers=headers, timeout=20, verify=False)
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            rows = soup.select('tbody tr')
            print(f"Found {len(rows)} table rows")
            
            if rows:
                print("\nFirst row HTML (truncated):")
                print(str(rows[0])[:500])
                
                # Try to extract data from first row
                first_row = rows[0]
                td2 = first_row.select_one('td:nth-child(2)')
                td3 = first_row.select_one('td:nth-child(3)')
                td4 = first_row.select_one('td:nth-child(4) a')
                
                print(f"\ntd2 (기관): {td2.get_text(strip=True) if td2 else 'None'}")
                print(f"td3 (날짜): {td3.get_text(strip=True) if td3 else 'None'}")
                print(f"td4 (링크): {td4.get('href') if td4 else 'None'}")
        except Exception as e:
            print(f"Error: {e}")
    
    # Now run the actual scraper
    print("\n" + "="*60)
    print("Running actual scraper...")
    print("="*60)
    
    scraper = ContentScraper()
    
    for agency in sanction_agencies:
        items = scraper.fetch_sanction_items(agency)
        print(f"\n{agency['code']}: {len(items)} items collected")
        
        for i, item in enumerate(items[:3]):
            print(f"  [{i+1}] {item['title']}")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    test_sanction_scraping()
