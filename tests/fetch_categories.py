"""
Fetch real categories from Panta API to hardcode into Mini App.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from backend.panta_client import PantaClient

load_dotenv()

def main():
    print("Fetching categories from Panta API...")
    
    client = PantaClient()
    categories = client.get_categories()
    
    print("\n=== Real Categories from Panta API ===")
    print(json.dumps(categories, indent=2))
    
    print("\n=== Category List for Mini App ===")
    if "categories" in categories:
        for cat in categories["categories"]:
            print(f'  "{cat}"')
    elif isinstance(categories, list):
        for cat in categories:
            print(f'  "{cat}"')
    else:
        print(f"Unexpected format: {categories}")
    
    client.close()

if __name__ == "__main__":
    main()
