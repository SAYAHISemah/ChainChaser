# config.py - Configuration file for the trading bot

# Discord Bot Configuration
DISCORD_BOT_TOKEN = "MTM0ODA2NjQ1ODg1MjEzNDk3NA.GQW67E.bsBIZijNGXPht8sQOiCxiig-0jTmBFdVH_eWek"

# Solana Configuration
SOLANA_PRIVATE_KEY = "0x1d3df5541a2bd53125d125b88ece14dda4c22dbdf43968713d9ba0ede9f94740"  # Your wallet's private key in base58 format
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"

# Trading Configuration
DEFAULT_SLIPPAGE_BPS = 300  # 3% slippage
DEFAULT_PRIORITY_FEE = 0.0005  # SOL
MAX_SOL_PER_TRADE = 1.0  # Maximum SOL per trade for safety

# EVM Configuration (for future expansion)
RPC_ENDPOINTS = {
    "ethereum": "https://mainnet.infura.io/v3/YOUR_INFURA_KEY",
    "bsc": "https://bsc-dataseed.binance.org/"
}

# API Endpoints
PUMPFUN_API_URL = "https://pumpportal.fun/api/trade"
JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_URL = "https://quote-api.jup.ag/v6/swap"

# Requirements.txt content:
"""
discord.py>=2.3.2
web3>=6.11.0
solders>=0.18.1
solana>=0.32.0
requests>=2.31.0
"""

# Setup Instructions:
"""
1. Install requirements:
   pip install discord.py web3 solders solana requests

2. Get Discord Bot Token:
   - Go to https://discord.com/developers/applications
   - Create new application
   - Go to Bot section
   - Create bot and copy token
   - Enable message content intent

3. Get Solana Private Key:
   - Export from Phantom/Solflare wallet
   - Or use: solana-keygen new --outfile wallet.json
   - Convert to base58 if needed

4. Fund your wallet with SOL for trading

5. Invite bot to Discord server with these permissions:
   - Read Messages
   - Send Messages
   - Use Slash Commands
   - Embed Links

6. Update the configuration values in config.py

7. Run: python main_bot.py
"""

# Security Notes:
"""
⚠️  IMPORTANT SECURITY CONSIDERATIONS:

1. NEVER share your private key
2. Use a dedicated trading wallet with limited funds
3. Test on devnet first
4. Set reasonable trading limits
5. Monitor bot activity closely
6. Use environment variables for sensitive data:

   import os
   SOLANA_PRIVATE_KEY = os.getenv('SOLANA_PRIVATE_KEY')
   DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
"""