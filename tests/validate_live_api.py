"""
Live API validation for PantaPredict.

This script validates the PantaPredict scaffold against the real Panta API.
It tests all endpoints and reports mismatches between assumed and actual response shapes.

Run with: python tests/validate_live_api.py
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from backend.panta_client import PantaClient, PantaAPIError

load_dotenv()

# Test credentials for registration (you should replace these with real values)
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "TestPassword123!"


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def print_json(data, label="Response"):
    """Pretty print JSON data."""
    print(f"\n{label}:")
    print(json.dumps(data, indent=2, default=str))


def step1_obtain_api_key():
    """
    Step 1: Obtain a real API key.
    - POST /auth/register/ with a real email
    - POST /account/keys/ to get a pk_test_ key
    - Confirm the key works with GET /markets/
    """
    print_section("STEP 1: Obtain Real API Key")
    
    try:
        # Register account
        print("\n1a. Registering account...")
        register_result = PantaClient.register_account(TEST_EMAIL, TEST_PASSWORD)
        print_json(register_result, "Register Response")
        
        # Create API key
        print("\n1b. Creating API key...")
        client = PantaClient()  # Will fail if no key, but we'll try
        try:
            key_result = client.create_api_key(label="pantapredict_validation")
            print_json(key_result, "API Key Response")
            
            # Extract the key
            api_key = key_result.get("key") or key_result.get("apiKey")
            if api_key:
                print(f"\n✓ API Key obtained: {api_key[:10]}...{api_key[-4:]}")
                
                # Test the key with a simple markets call
                print("\n1c. Testing key with GET /markets/...")
                markets_result = client.list_markets(limit=1)
                print_json(markets_result, "Markets Response (truncated)")
                print(f"✓ Key works! Found {len(markets_result.get('results', []))} markets")
                
                client.close()
                return api_key
        except PantaAPIError as e:
            print(f"✗ API Error creating key: {e.status_code} - {e.detail}")
            client.close()
            return None
            
    except Exception as e:
        print(f"✗ Failed: {e}")
        return None


def step2_real_quote_call(api_key):
    """
    Step 2: Real quote call.
    - Call quote_market() with real question, deadline, source
    - Print FULL raw JSON response
    - Compare field names against assumptions
    """
    print_section("STEP 2: Real Quote Call")
    
    if not api_key:
        print("⚠ Skipping - no API key available")
        return None
    
    try:
        client = PantaClient(api_key=api_key)
        
        print("\n2a. Calling quote_market()...")
        quote = client.quote_market(
            question="Will Solana reach $500 by end of 2026?",
            deadline="2026-12-31T23:59:59Z",
            source="https://coindesk.com",
            description="Validation test for PantaPredict",
            image_url="https://i.imgur.com/test.jpg"  # Test image URL
        )
        
        print_json(quote.raw, "FULL Quote Response")
        
        # Analyze field names
        print("\n2b. Field Analysis:")
        print(f"  Expected fields: quoteId, feeUsdc, yesPrice")
        print(f"  Actual fields: {list(quote.raw.keys())}")
        
        # Check for expected fields
        expected_fields = ["quoteId", "feeUsdc", "yesPrice"]
        for field in expected_fields:
            if field in quote.raw:
                print(f"  ✓ {field}: {quote.raw[field]}")
            else:
                print(f"  ✗ {field}: MISSING")
        
        # Check for unexpected fields
        for field in quote.raw.keys():
            if field not in expected_fields:
                print(f"  ? {field}: {quote.raw[field]} (unexpected)")
        
        client.close()
        return quote
        
    except PantaAPIError as e:
        print(f"✗ API Error: {e.status_code}")
        print_json(e.detail, "Error Detail")
        return None
    except Exception as e:
        print(f"✗ Failed: {e}")
        return None


def step3_real_build_call(quote, api_key):
    """
    Step 3: Real build call.
    - Use a real Solana test wallet address
    - Call build_market() with the quote
    - Print full raw response
    - Confirm it returns an unsigned transaction
    """
    print_section("STEP 3: Real Build Call")
    
    if not quote or not api_key:
        print("⚠ Skipping - no quote or API key available")
        return None
    
    try:
        client = PantaClient(api_key=api_key)
        
        # Use a real Solana devnet wallet address
        test_wallet = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
        
        print(f"\n3a. Calling build_market() with wallet: {test_wallet}")
        build_result = client.build_market(quote, creator_wallet=test_wallet)
        
        print_json(build_result, "FULL Build Response")
        
        # Analyze transaction field
        print("\n3b. Transaction Analysis:")
        print(f"  Expected field: transaction")
        print(f"  Actual fields: {list(build_result.keys())}")
        
        if "transaction" in build_result:
            tx = build_result["transaction"]
            print(f"  ✓ transaction field found")
            print(f"  Type: {type(tx)}")
            print(f"  Length: {len(str(tx))} chars")
            print(f"  Preview: {str(tx)[:100]}...")
        else:
            print("  ✗ transaction field MISSING")
            # Check for alternative field names
            for field in build_result.keys():
                if "tx" in field.lower() or "transaction" in field.lower():
                    print(f"  ? Found alternative: {field}")
        
        # Check for buildId
        if "buildId" in build_result:
            print(f"  ✓ buildId: {build_result['buildId']}")
        else:
            print("  ✗ buildId field MISSING")
        
        client.close()
        return build_result
        
    except PantaAPIError as e:
        print(f"✗ API Error: {e.status_code}")
        print_json(e.detail, "Error Detail")
        return None
    except Exception as e:
        print(f"✗ Failed: {e}")
        return None


def step4_real_register_call(build_result, api_key):
    """
    Step 4: Real register call.
    - Sign the built transaction (will need external tool/script)
    - Call register_market() with signed transaction
    - Confirm market registers on-chain
    """
    print_section("STEP 4: Real Register Call")
    
    if not build_result or not api_key:
        print("⚠ Skipping - no build result or API key available")
        return None
    
    print("\n⚠ NOTE: Transaction signing requires a Solana wallet.")
    print("   This step requires:")
    print("   1. A real Solana wallet with devnet SOL")
    print("   2. The ability to sign transactions")
    print("   3. Submitting the signed transaction to Panta")
    print("\n   For now, we'll skip actual signing and just show what would be needed.")
    
    # Show what would be needed
    if "transaction" in build_result:
        print(f"\n4a. Unsigned transaction (base64):")
        print(f"  {build_result['transaction'][:100]}...")
        
        print(f"\n4b. To complete registration:")
        print(f"  1. Decode the base64 transaction")
        print(f"  2. Sign it with your wallet")
        print(f"  3. Encode back to base64")
        print(f"  4. Call register_market(build_id, signed_tx)")
        
        if "buildId" in build_result:
            print(f"\n  Build ID for registration: {build_result['buildId']}")
    
    return None


def step5_edge_cases(api_key):
    """
    Step 5: Edge cases to check against real data.
    - Market with null price field
    - Timestamp format in /markets/ response
    - Image URL validation
    """
    print_section("STEP 5: Edge Cases")
    
    if not api_key:
        print("⚠ Skipping - no API key available")
        return
    
    try:
        client = PantaClient(api_key=api_key)
        
        # 5a. Check for null price fields
        print("\n5a. Checking for null price fields in existing markets...")
        markets = client.list_markets(limit=10)
        results = markets.get("results", [])
        
        null_price_count = 0
        for market in results[:3]:  # Check first 3
            print(f"\n  Market: {market.get('question', 'N/A')[:50]}...")
            print(f"    yesPrice: {market.get('yesPrice')}")
            print(f"    primaryYesPrice: {market.get('primaryYesPrice')}")
            print(f"    secondaryYesPrice: {market.get('secondaryYesPrice')}")
            
            if market.get('yesPrice') is None:
                null_price_count += 1
                print(f"    ⚠ NULL price detected")
        
        if null_price_count > 0:
            print(f"\n  ✓ Found {null_price_count} markets with null prices")
        else:
            print(f"\n  ℹ No null prices found in sample (may need newer markets)")
        
        # 5b. Check timestamp format
        print("\n5b. Checking timestamp format...")
        if results:
            first_market = results[0]
            for field in ['createdAt', 'updatedAt', 'deadline']:
                if field in first_market:
                    value = first_market[field]
                    print(f"  {field}: {value} (type: {type(value).__name__})")
        
        # 5c. Test image URL validation
        print("\n5c. Testing image URL validation...")
        test_urls = [
            "https://i.imgur.com/test.jpg",
            "https://example.com/image.png",
            "https://github.com/user/repo/raw/main/image.png"
        ]
        
        for url in test_urls:
            try:
                quote = client.quote_market(
                    question="Test question for image validation",
                    deadline="2026-12-31T23:59:59Z",
                    source="https://example.com",
                    image_url=url
                )
                print(f"  ✓ URL accepted: {url}")
            except PantaAPIError as e:
                print(f"  ✗ URL rejected: {url}")
                print(f"    Error: {e.detail}")
        
        client.close()
        
    except Exception as e:
        print(f"✗ Failed: {e}")


def main():
    """Run all validation steps."""
    print_section("PantaPredict Live API Validation")
    print("This script validates the scaffold against the real Panta API")
    print("and reports any mismatches between assumed and actual response shapes.")
    
    # Check for existing API key
    existing_key = os.getenv("PANTA_API_KEY")
    if existing_key and existing_key and not existing_key.startswith("your_") and not existing_key.startswith("pk_test_dummy"):
        print(f"\nUsing existing API key: {existing_key[:10]}...{existing_key[-4:]}")
        api_key = existing_key
    else:
        print("\nNo valid API key found in environment.")
        print("Attempting to generate a new one...")
        print("Note: This requires valid email/password credentials in the script.")
        api_key = step1_obtain_api_key()
    
    if not api_key:
        print("\n✗ Could not obtain API key. Cannot proceed with validation.")
        print("Please set PANTA_API_KEY in .env with a valid key from https://panta.market")
        print("Or update TEST_EMAIL and TEST_PASSWORD in this script.")
        return
    
    # Run steps
    quote = step2_real_quote_call(api_key)
    build_result = step3_real_build_call(quote, api_key)
    step4_real_register_call(build_result, api_key)
    step5_edge_cases(api_key)
    
    # Summary
    print_section("Validation Summary")
    print("Review the output above for:")
    print("  - Field name mismatches (quoteId vs quote_id, etc.)")
    print("  - Missing or unexpected fields")
    print("  - Null price handling")
    print("  - Timestamp formats")
    print("  - Image URL validation behavior")
    print("\nUpdate panta_client.py and models.py based on findings.")


if __name__ == "__main__":
    main()
