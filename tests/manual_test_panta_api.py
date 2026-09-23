"""
Manual integration test for Panta API client.

This script tests the client against the live Panta API.
Requires a valid PANTA_API_KEY in .env or environment.

Run with: python tests/manual_test_panta_api.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from backend.panta_client import PantaClient, PantaAPIError

# Load environment variables
load_dotenv()


def test_list_markets():
    """Test listing markets from the live API."""
    print("\n=== Testing list_markets ===")
    try:
        client = PantaClient()
        result = client.list_markets(limit=5)
        print(f"✓ Successfully listed markets")
        print(f"  Result keys: {result.keys()}")
        if "results" in result:
            print(f"  Number of markets: {len(result['results'])}")
        client.close()
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_quote_market():
    """Test quoting a market creation."""
    print("\n=== Testing quote_market ===")
    try:
        client = PantaClient()
        quote = client.quote_market(
            question="Will Solana reach $500 by end of 2026?",
            deadline="2026-12-31T23:59:59Z",
            source="https://coindesk.com",
            description="Test market for PantaPredict integration"
        )
        print(f"✓ Successfully quoted market")
        print(f"  Quote ID: {quote.raw.get('quoteId')}")
        print(f"  Fee USDC: {quote.raw.get('feeUsdc')}")
        print(f"  Yes Price: {quote.raw.get('yesPrice')}")
        client.close()
        return True
    except PantaAPIError as e:
        print(f"✗ API Error ({e.status_code}): {e.detail}")
        return False
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_build_market():
    """Test building a market transaction (requires a valid quote)."""
    print("\n=== Testing build_market ===")
    try:
        client = PantaClient()
        
        # First get a quote
        quote = client.quote_market(
            question="Will Ethereum reach $10k by 2027?",
            deadline="2027-12-31T23:59:59Z",
            source="https://ethereum.org"
        )
        
        # Then build (using a dummy wallet address for testing)
        build_result = client.build_market(
            quote,
            creator_wallet="test_wallet_address_placeholder"
        )
        print(f"✓ Successfully built market transaction")
        print(f"  Build ID: {build_result.get('buildId')}")
        print(f"  Has transaction: {'transaction' in build_result}")
        client.close()
        return True
    except PantaAPIError as e:
        print(f"✗ API Error ({e.status_code}): {e.detail}")
        return False
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def main():
    """Run all manual tests."""
    print("=" * 60)
    print("Panta API Client - Manual Integration Tests")
    print("=" * 60)
    
    # Check for API key
    api_key = os.getenv("PANTA_API_KEY")
    if not api_key or api_key.startswith("pk_test_") and "your_key_here" in api_key:
        print("\n⚠ WARNING: PANTA_API_KEY not set or is placeholder")
        print("  Set a valid API key in .env file to test against live API")
        print("  You can get a key from: https://panta.market")
        return
    
    print(f"\nUsing API key: {api_key[:10]}...{api_key[-4:]}")
    
    # Run tests
    results = []
    results.append(("list_markets", test_list_markets()))
    results.append(("quote_market", test_quote_market()))
    results.append(("build_market", test_build_market()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    total_passed = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {total_passed}/{len(results)} tests passed")


if __name__ == "__main__":
    main()
