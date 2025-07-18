#!/usr/bin/env python3
"""
Helper script to check and fix private key formats
"""

import os
from dotenv import load_dotenv

load_dotenv()

print("🔐 Private Key Format Checker")
print("=" * 60)

# Check Ethereum key
eth_key = os.getenv("ETHEREUM_PRIVATE_KEY", "")
if eth_key:
    # Remove common prefixes/suffixes
    cleaned = eth_key.strip()
    if cleaned.startswith('0x'):
        cleaned = cleaned[2:]
    
    print(f"\n📍 Ethereum Private Key:")
    print(f"  Original length: {len(eth_key)} characters")
    print(f"  Cleaned length: {len(cleaned)} characters")
    print(f"  First 6 chars: {cleaned[:6]}...")
    
    if len(cleaned) == 64:
        print("  ✅ Correct length (64 hex characters)")
        
        # Check if it's valid hex
        try:
            int(cleaned, 16)
            print("  ✅ Valid hexadecimal format")
        except:
            print("  ❌ Contains non-hex characters")
    else:
        print(f"  ❌ Wrong length! Expected 64, got {len(cleaned)}")
        print("\n  💡 Ethereum private keys should be:")
        print("     - 64 hexadecimal characters (0-9, a-f, A-F)")
        print("     - Example: 'abc123def456...789' (64 chars total)")
        print("     - Or with 0x prefix: '0xabc123def456...789' (66 chars total)")
else:
    print("\n⚠️  No Ethereum private key found")

# Check Solana key
sol_key = os.getenv("SOLANA_PRIVATE_KEY", "")
if sol_key:
    print(f"\n📍 Solana Private Key:")
    print(f"  Length: {len(sol_key)} characters")
    print(f"  First 6 chars: {sol_key[:6]}...")
    
    # Solana keys are typically base58 encoded
    if 44 <= len(sol_key) <= 88:
        print("  ✅ Correct length range for Solana")
    else:
        print(f"  ⚠️  Unusual length for Solana key")

# Check Discord token
discord_token = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
if discord_token:
    print(f"\n📍 Discord Token:")
    print(f"  Length: {len(discord_token)} characters")
    print(f"  First 10 chars: {discord_token[:10]}...")
    
    # Discord tokens have a specific format
    parts = discord_token.split('.')
    if len(parts) == 3:
        print("  ✅ Correct Discord token format (3 parts)")
    else:
        print("  ❌ Invalid Discord token format")
else:
    print("\n❌ No Discord token found!")
    print("  Set DISCORD_BOT_TOKEN or DISCORD_TOKEN in .env")

print("\n" + "=" * 60)
print("📝 Example .env file:")
print("=" * 60)
print("""
# Discord Bot Token (required)
DISCORD_BOT_TOKEN=MTIzNDU2Nzg5.GAbcde.1234567890abcdef_hijklmnop

# Ethereum Configuration (optional)
ETHEREUM_RPC_URL=https://eth.llamarpc.com
ETHEREUM_PRIVATE_KEY=abc123def456789abc123def456789abc123def456789abc123def456789abcd

# Solana Configuration (optional)
SOLANA_PRIVATE_KEY=5KJhS8NrV9...base58_encoded_key...9xQYHz
""")