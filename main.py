# main_bot.py
import discord
import re
import requests
import asyncio
from web3 import Web3
from solana_liquidity_checker import SolanaLiquidityChecker
from etherium_trader import EthereumTrader  # Import the new Ethereum trader
import json
from datetime import datetime
import logging
import os
from dotenv import load_dotenv  # Add this import

# Load environment variables from .env file
load_dotenv()  # Add this line at the top

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Trading Configuration
TRADING_CONFIG = {
    "enabled": True,
    "sol_amount": 0.001,  # Amount in SOL to trade on Solana
    "eth_amount": 0.00001,  # Amount in ETH to trade on Ethereum
    "bnb_amount": 0.00001,  # Amount in BNB to trade on BSC
    "slippage_bps": 500,  # 5% slippage for Solana
    "slippage_percent": 5,  # 5% slippage for Ethereum/BSC
    "priority_fee": 0.001,  # Priority fee in SOL
    "auto_execute": True,  # Set to False to only analyze without executing
    "max_market_cap": 1000000,  # Max market cap in USD (optional filter)
}

# RPC endpoints - Use multiple fallback endpoints
RPC_ENDPOINTS = {
    "ethereum": [
        os.getenv("ETHEREUM_RPC_URL", "https://eth.llamarpc.com"),
        "https://rpc.ankr.com/eth",
        "https://eth.public-rpc.com",
        "https://ethereum.publicnode.com",
        "https://eth.rpc.blxrbdn.com"
    ],
    "bsc": [
        "https://bsc-dataseed.binance.org/",
        "https://bsc-dataseed1.defibit.io/",
        "https://bsc-dataseed1.ninicoin.io/",
        "https://bsc.publicnode.com"
    ],
}

# Private keys (use environment variables for security)
PRIVATE_KEYS = {
    "ethereum": os.getenv("ETHEREUM_PRIVATE_KEY"),  # Your Ethereum private key
    "bsc": os.getenv("BSC_PRIVATE_KEY", os.getenv("ETHEREUM_PRIVATE_KEY")),  # BSC private key (can be same as ETH)
    "solana": os.getenv("SOLANA_PRIVATE_KEY"),  # Your Solana private key
}

# Discord token
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not DISCORD_TOKEN:
    # Try alternate names
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if not DISCORD_TOKEN:
        logger.error("DISCORD_BOT_TOKEN not found in environment variables")
        logger.info("Please set DISCORD_BOT_TOKEN in your .env file")
        logger.info("Example: DISCORD_BOT_TOKEN=your_token_here")
        
        # Debug: Print what we actually found
        logger.info("Available environment variables:")
        for key in os.environ:
            if 'DISCORD' in key or 'TOKEN' in key:
                logger.info(f"  {key}: {os.environ[key][:10]}...")  # Only show first 10 chars for security

def get_working_rpc(endpoints):
    """Try multiple RPC endpoints and return the first working one"""
    for endpoint in endpoints:
        try:
            w3 = Web3(Web3.HTTPProvider(endpoint))
            if w3.is_connected():
                logger.info(f"Connected to RPC: {endpoint}")
                return w3, endpoint
            else:
                logger.warning(f"Failed to connect to: {endpoint}")
        except Exception as e:
            logger.warning(f"Error connecting to {endpoint}: {e}")
    
    logger.error(f"All RPC endpoints failed for: {endpoints}")
    return None, None

class ChainAnalyzer:
    def __init__(self):
        # Try to connect to Ethereum with fallback RPCs
        self.eth_provider, self.eth_rpc_url = get_working_rpc(RPC_ENDPOINTS["ethereum"])
        
        # Try to connect to BSC with fallback RPCs
        self.bsc_provider, self.bsc_rpc_url = get_working_rpc(RPC_ENDPOINTS["bsc"])
        
        self.solana_checker = SolanaLiquidityChecker()
        
        # Initialize Ethereum trader (works for both ETH and BSC)
        self.ethereum_trader = None
        self.bsc_trader = None
        
        # In ChainAnalyzer.__init__
        if self.eth_provider and PRIVATE_KEYS.get("ethereum"):
            try:
                self.ethereum_trader = EthereumTrader(
                    self.eth_rpc_url,
                    PRIVATE_KEYS.get("ethereum"),
                    fallback_rpcs=RPC_ENDPOINTS["ethereum"]  # Add fallback RPCs
                )
                logger.info("Ethereum trader initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Ethereum trader: {e}")

        if self.bsc_provider and PRIVATE_KEYS.get("bsc"):
            try:
                self.bsc_trader = EthereumTrader(
                    self.bsc_rpc_url,
                    PRIVATE_KEYS.get("bsc"),
                    fallback_rpcs=RPC_ENDPOINTS["bsc"]  # Add fallback RPCs
                )
                logger.info("BSC trader initialized")
            except Exception as e:
                logger.error(f"Failed to initialize BSC trader: {e}")
        
        logger.info(f"ETH connected: {self.eth_provider is not None}")
        logger.info(f"BSC connected: {self.bsc_provider is not None}")

    def is_evm_address(self, addr: str) -> bool:
        return bool(re.match(r"^0x[a-fA-F0-9]{40}$", addr))

    def is_solana_address(self, addr: str) -> bool:
        return bool(re.match(r"^[A-HJ-NP-Za-km-z1-9]{32,44}$", addr))

    def check_evm_liquidity(self, addr):
        """Check liquidity on EVM chains"""
        opts = []
        
        # Check Ethereum DEXs
        if self.eth_provider and self.ethereum_trader:
            try:
                # Check Uniswap V2
                if self.ethereum_trader.check_uniswap_v2_liquidity(addr):
                    opts.append({
                        "chain": "Ethereum", 
                        "protocol": "UniswapV2", 
                        "tradable": True,
                        "dex_type": "uniswap_v2"
                    })
                
                # Check Sushiswap
                if self.ethereum_trader.check_sushiswap_liquidity(addr):
                    opts.append({
                        "chain": "Ethereum", 
                        "protocol": "Sushiswap", 
                        "tradable": True,
                        "dex_type": "sushiswap"
                    })
            except Exception as e:
                logger.error(f"Error checking Ethereum liquidity: {e}")
        
        # Check BSC DEXs
        if self.bsc_provider and self.bsc_trader:
            try:
                # For BSC, we'll use the same trader but check for PancakeSwap-style liquidity
                # PancakeSwap uses the same contracts as Uniswap V2
                if self.bsc_trader.check_uniswap_v2_liquidity(addr):  # PancakeSwap uses Uniswap V2 style
                    opts.append({
                        "chain": "BSC", 
                        "protocol": "PancakeSwap", 
                        "tradable": True,
                        "dex_type": "pancakeswap"
                    })
            except Exception as e:
                logger.error(f"Error checking BSC liquidity: {e}")
                # If trader fails, add BSC as available (fallback)
                opts.append({
                    "chain": "BSC", 
                    "protocol": "PancakeSwap", 
                    "tradable": True,
                    "dex_type": "pancakeswap"
                })
        
        return opts

    def check_solana_liquidity(self, addr):
        return self.solana_checker.get_trading_options(addr)

    async def execute_trade(self, address: str, trading_options: list, chain_type: str):
        """Execute trade if conditions are met"""
        if not TRADING_CONFIG["enabled"] or not TRADING_CONFIG["auto_execute"]:
            return {"executed": False, "reason": "Auto-execution disabled"}
        
        # Handle Solana trades
        if chain_type == "Solana":
            for option in trading_options:
                if option["chain"] == "Solana" and option["tradable"]:
                    if option["protocol"] == "PumpFun":
                        return await self.execute_pumpfun_trade(address)
                    elif option["protocol"] == "Raydium":
                        return await self.execute_raydium_trade(address)
        
        # Handle EVM trades (Ethereum and BSC)
        elif chain_type == "EVM":
            for option in trading_options:
                if option["tradable"]:
                    # Handle Ethereum trades
                    if option["chain"] == "Ethereum":
                        if option.get("dex_type") == "uniswap_v2":
                            return await self.execute_uniswap_trade(address)
                        elif option.get("dex_type") == "sushiswap":
                            return await self.execute_sushiswap_trade(address)
                    
                    # Handle BSC trades
                    elif option["chain"] == "BSC":
                        if option.get("dex_type") == "pancakeswap":
                            return await self.execute_pancakeswap_trade(address)
        
        return {"executed": False, "reason": "No executable trading options found"}

    async def execute_pumpfun_trade(self, token_address: str):
        """Execute PumpFun trade"""
        try:
            result = await self.solana_checker.buy_pumpfun_token(
                token_address,
                TRADING_CONFIG["sol_amount"]
            )
            return {
                "executed": True,
                "protocol": "PumpFun",
                "amount": TRADING_CONFIG["sol_amount"],
                "signature": result.get("signature"),
                "status": result.get("status", "pending"),
                "chain": "Solana"
            }
        except Exception as e:
            logger.error(f"PumpFun trade failed: {e}")
            return {"executed": False, "reason": f"PumpFun trade failed: {str(e)}"}

    async def execute_raydium_trade(self, token_address: str):
        """Execute Raydium trade"""
        try:
            result = await self.solana_checker.buy_via_jupiter(
                token_address,
                TRADING_CONFIG["sol_amount"],
                TRADING_CONFIG["slippage_bps"]
            )
            return {
                "executed": True,
                "protocol": "Raydium",
                "amount": TRADING_CONFIG["sol_amount"],
                "signature": result.get("signature"),
                "status": result.get("status", "pending"),
                "chain": "Solana"
            }
        except Exception as e:
            logger.error(f"Raydium trade failed: {e}")
            return {"executed": False, "reason": f"Raydium trade failed: {str(e)}"}

    # In execute_uniswap_trade method of ChainAnalyzer:

    async def execute_uniswap_trade(self, token_address: str):
        """Execute Uniswap V2 trade"""
        if not self.ethereum_trader:
            return {"executed": False, "reason": "Ethereum trader not initialized"}
        
        # Check funds before attempting to trade
        if not self.ethereum_trader.has_sufficient_funds(TRADING_CONFIG["eth_amount"]):
            return {
                "executed": False, 
                "reason": f"Insufficient ETH balance for trade amount ({TRADING_CONFIG['eth_amount']}) plus gas"
            }
        
        try:
        
            result = await self.ethereum_trader.buy_on_uniswap_v2(
                token_address,
                TRADING_CONFIG["eth_amount"],
                TRADING_CONFIG["slippage_percent"]
            )
            return {
                "executed": True,
                "protocol": "UniswapV2",
                "amount": TRADING_CONFIG["eth_amount"],
                "currency": "ETH",
                "transaction": result.get("transaction_hash"),
                "status": result.get("status", "pending"),
                "chain": "Ethereum"
            }
        except Exception as e:
            logger.error(f"Uniswap trade failed: {e}")
            return {"executed": False, "reason": f"Uniswap trade failed: {str(e)}"}

    async def execute_sushiswap_trade(self, token_address: str):
        """Execute Sushiswap trade"""
        if not self.ethereum_trader:
            return {"executed": False, "reason": "Ethereum trader not initialized"}
            
        try:
            result = await self.ethereum_trader.buy_on_sushiswap(
                token_address,
                TRADING_CONFIG["eth_amount"],
                TRADING_CONFIG["slippage_percent"]
            )
            return {
                "executed": True,
                "protocol": "Sushiswap",
                "amount": TRADING_CONFIG["eth_amount"],
                "currency": "ETH",
                "transaction": result.get("transaction_hash"),
                "status": result.get("status", "pending"),
                "chain": "Ethereum"
            }
        except Exception as e:
            logger.error(f"Sushiswap trade failed: {e}")
            return {"executed": False, "reason": f"Sushiswap trade failed: {str(e)}"}

    async def execute_pancakeswap_trade(self, token_address: str):
        """Execute PancakeSwap trade on BSC"""
        if not self.bsc_trader:
            return {"executed": False, "reason": "BSC trader not initialized"}
            
        try:
            # Use the same Uniswap V2 function since PancakeSwap is a fork
            result = await self.bsc_trader.buy_on_uniswap_v2(
                token_address,
                TRADING_CONFIG["bnb_amount"],
                TRADING_CONFIG["slippage_percent"]
            )
            return {
                "executed": True,
                "protocol": "PancakeSwap",
                "amount": TRADING_CONFIG["bnb_amount"],
                "currency": "BNB",
                "transaction": result.get("transaction_hash"),
                "status": result.get("status", "pending"),
                "chain": "BSC"
            }
        except Exception as e:
            logger.error(f"PancakeSwap trade failed: {e}")
            return {"executed": False, "reason": f"PancakeSwap trade failed: {str(e)}"}

# Discord Bot Class
class TradingBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.analyzer = ChainAnalyzer()
        logger.info("Discord bot initialized")

    async def on_ready(self):
        logger.info(f'Bot logged in as {self.user}')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for token addresses"
            )
        )

    async def on_message(self, message):
        # Don't respond to own messages
        if message.author == self.user:
            return

        # Check if message contains potential token addresses
        content = message.content.strip()
        
        # Look for addresses in the message
        addresses = []
        
        # Check for Ethereum addresses (0x...)
        eth_addresses = re.findall(r'0x[a-fA-F0-9]{40}', content)
        addresses.extend([(addr, 'EVM') for addr in eth_addresses])
        
        # Check for Solana addresses (base58, 32-44 chars)
        sol_addresses = re.findall(r'\b[A-HJ-NP-Za-km-z1-9]{32,44}\b', content)
        addresses.extend([(addr, 'Solana') for addr in sol_addresses])
        
        # Process each address found
        for address, chain_type in addresses:
            try:
                await self.process_address(message, address, chain_type)
            except Exception as e:
                logger.error(f"Error processing address {address}: {e}")
                await message.channel.send(f"❌ Error processing {address}: {str(e)}")

    async def process_address(self, message, address, chain_type):
        """Process a single address"""
        logger.info(f"Processing {chain_type} address: {address}")
        
        # Send initial processing message
        processing_msg = await message.channel.send(f"🔍 Analyzing {chain_type} address: `{address}`...")
        
        try:
            # Check liquidity based on chain type
            if chain_type == "EVM":
                trading_options = self.analyzer.check_evm_liquidity(address)
            elif chain_type == "Solana":
                trading_options = self.analyzer.check_solana_liquidity(address)
            else:
                await processing_msg.edit(content=f"❌ Unsupported chain type: {chain_type}")
                return
            
            # Format the results
            embed = discord.Embed(
                title=f"💎 Token Analysis: {chain_type}",
                description=f"**Address:** `{address}`",
                color=0x00ff00 if any(opt.get("tradable", False) for opt in trading_options) else 0xff0000,
                timestamp=datetime.utcnow()
            )
            
            # Add trading options
            if trading_options:
                tradable_options = [opt for opt in trading_options if opt.get("tradable", False)]
                non_tradable_options = [opt for opt in trading_options if not opt.get("tradable", False)]
                
                if tradable_options:
                    tradable_text = "\n".join([
                        f"✅ **{opt['protocol']}** on {opt['chain']}"
                        for opt in tradable_options
                    ])
                    embed.add_field(
                        name="🟢 Available on:",
                        value=tradable_text,
                        inline=False
                    )
                    
                    # Add trading config info based on available chains
                    config_info = []
                    if any(opt['chain'] == 'Solana' for opt in tradable_options):
                        config_info.append(f"**Solana:** {TRADING_CONFIG['sol_amount']} SOL ({TRADING_CONFIG['slippage_bps']/100}% slippage)")
                    if any(opt['chain'] == 'Ethereum' for opt in tradable_options):
                        config_info.append(f"**Ethereum:** {TRADING_CONFIG['eth_amount']} ETH ({TRADING_CONFIG['slippage_percent']}% slippage)")
                    if any(opt['chain'] == 'BSC' for opt in tradable_options):
                        config_info.append(f"**BSC:** {TRADING_CONFIG['bnb_amount']} BNB ({TRADING_CONFIG['slippage_percent']}% slippage)")
                    
                    if config_info:
                        embed.add_field(
                            name="⚙️ Trading Config:",
                            value="\n".join(config_info),
                            inline=True
                        )
                
                if non_tradable_options:
                    non_tradable_text = "\n".join([
                        f"❌ **{opt['protocol']}** on {opt['chain']}"
                        for opt in non_tradable_options
                    ])
                    embed.add_field(
                        name="🔴 Not available on:",
                        value=non_tradable_text,
                        inline=False
                    )
            else:
                embed.add_field(
                    name="Status",
                    value="❌ No trading options found",
                    inline=False
                )

            trade_result = None
            if TRADING_CONFIG["enabled"] and any(opt.get("tradable", False) for opt in trading_options):
                try:
                    trade_result = await self.analyzer.execute_trade(address, trading_options, chain_type)
                    
                    if trade_result.get("executed"):
                        embed.add_field(
                            name="🚀 Trade Executed!",
                            value=f"**Protocol:** {trade_result.get('protocol')}\n"
                                f"**Amount:** {trade_result.get('amount')} {trade_result.get('currency', trade_result.get('chain'))}\n"
                                f"**Chain:** {trade_result.get('chain')}\n"
                                f"**Status:** {trade_result.get('status')}\n"
                                f"**TX:** `{trade_result.get('transaction', trade_result.get('signature', 'N/A'))}`",
                            inline=False
                        )
                        embed.color = 0x00ff00
                    else:
                        # Provide more detailed error information
                        reason = trade_result.get('reason', 'Unknown')
                        details = ""
                        
                        if isinstance(reason, dict) and 'message' in reason:
                            if reason['message'] == 'failed to send tx':
                                details = "\n\n**Possible causes:**\n" + \
                                        "- Insufficient funds for transaction and gas\n" + \
                                        "- RPC endpoint connection issues\n" + \
                                        "- Network congestion\n\n" + \
                                        "**Action needed:**\n" + \
                                        "Check your wallet balance and try again"
                        
                        embed.add_field(
                            name="⚠️ Trade Not Executed",
                            value=f"**Reason:** {reason}{details}",
                            inline=False
                        )
                except Exception as e:
                    logger.error(f"Trade execution failed: {e}")
                    embed.add_field(
                        name="❌ Trade Failed",
                        value=f"**Error:** {str(e)}\n\n**Details:** {type(e).__name__}",
                        inline=False
                    )
            
            # Send the final embed
            await processing_msg.edit(content="", embed=embed)
            
        except Exception as e:
            logger.error(f"Error processing address {address}: {e}")
            await processing_msg.edit(content=f"❌ Error processing address: {str(e)}")

# Main execution
def main():
    if not DISCORD_TOKEN:
        logger.error("Discord token not found. Please set DISCORD_BOT_TOKEN in your environment variables.")
        return
    
    # Set up intents
    intents = discord.Intents.default()
    intents.message_content = True  # Required to read message content
    
    # Create and run bot
    bot = TradingBot(intents=intents)
    
    try:
        logger.info("Starting Discord bot...")
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("Invalid Discord token. Please check your DISCORD_BOT_TOKEN.")
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")

if __name__ == "__main__":
    main()