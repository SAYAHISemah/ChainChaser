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

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Trading Configuration
TRADING_CONFIG = {
    "enabled": True,
    "sol_amount": 0.0001,  # Amount in SOL to trade on Solana
    "eth_amount": 0.0000001,  # Amount in ETH to trade on Ethereum
    "slippage_bps": 500,  # 5% slippage for Solana
    "slippage_percent": 5,  # 5% slippage for Ethereum
    "priority_fee": 0.001,  # Priority fee in SOL
    "auto_execute": True,  # Set to False to only analyze without executing
    "max_market_cap": 1000000,  # Max market cap in USD (optional filter)
}

# RPC endpoints
RPC_ENDPOINTS = {
    "ethereum": os.getenv("ETHEREUM_RPC_URL", "https://eth.llamarpc.com"),  # Free public RPC
    "bsc": "https://bsc-dataseed.binance.org/",
}

# Private keys (use environment variables for security)
PRIVATE_KEYS = {
    "ethereum": os.getenv("ETHEREUM_PRIVATE_KEY"),  # Your Ethereum private key
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

class ChainAnalyzer:
    def __init__(self):
        self.eth_provider = Web3(Web3.HTTPProvider(RPC_ENDPOINTS["ethereum"]))
        self.bsc_provider = Web3(Web3.HTTPProvider(RPC_ENDPOINTS["bsc"]))
        self.solana_checker = SolanaLiquidityChecker()
        
        # Initialize Ethereum trader
        self.ethereum_trader = EthereumTrader(
            RPC_ENDPOINTS["ethereum"],
            PRIVATE_KEYS.get("ethereum")
        )
        
        logger.info(f"ETH connected: {self.eth_provider.is_connected()}")
        logger.info(f"BSC connected: {self.bsc_provider.is_connected()}")

    def is_evm_address(self, addr: str) -> bool:
        return bool(re.match(r"^0x[a-fA-F0-9]{40}$", addr))

    def is_solana_address(self, addr: str) -> bool:
        return bool(re.match(r"^[A-HJ-NP-Za-km-z1-9]{32,44}$", addr))

    def check_evm_liquidity(self, addr):
        """Check liquidity on EVM chains"""
        opts = []
        
        # Check Ethereum DEXs
        if self.eth_provider.is_connected():
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
        
        # BSC liquidity check (placeholder - you can expand this)
        if self.bsc_provider.is_connected():
            opts.append({"chain": "BSC", "protocol": "PancakeSwap", "tradable": True})
        
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
        
        # Handle Ethereum trades
        elif chain_type == "EVM":
            for option in trading_options:
                if option["chain"] == "Ethereum" and option["tradable"]:
                    if option.get("dex_type") == "uniswap_v2":
                        return await self.execute_uniswap_trade(address)
                    elif option.get("dex_type") == "sushiswap":
                        return await self.execute_sushiswap_trade(address)
        
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

    async def execute_uniswap_trade(self, token_address: str):
        """Execute Uniswap V2 trade"""
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
                "transaction": result.get("transaction_hash"),
                "status": result.get("status", "pending"),
                "chain": "Ethereum"
            }
        except Exception as e:
            logger.error(f"Uniswap trade failed: {e}")
            return {"executed": False, "reason": f"Uniswap trade failed: {str(e)}"}

    async def execute_sushiswap_trade(self, token_address: str):
        """Execute Sushiswap trade"""
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
                "transaction": result.get("transaction_hash"),
                "status": result.get("status", "pending"),
                "chain": "Ethereum"
            }
        except Exception as e:
            logger.error(f"Sushiswap trade failed: {e}")
            return {"executed": False, "reason": f"Sushiswap trade failed: {str(e)}"}

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
                    
                    # Add trading config info
                    if chain_type == "Solana":
                        embed.add_field(
                            name="⚙️ Trading Config (Solana):",
                            value=f"Amount: {TRADING_CONFIG['sol_amount']} SOL\nSlippage: {TRADING_CONFIG['slippage_bps']/100}%",
                            inline=True
                        )
                    elif chain_type == "EVM":
                        embed.add_field(
                            name="⚙️ Trading Config (Ethereum):",
                            value=f"Amount: {TRADING_CONFIG['eth_amount']} ETH\nSlippage: {TRADING_CONFIG['slippage_percent']}%",
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
            
            # Execute trade if enabled
            trade_result = None
            if TRADING_CONFIG["enabled"] and any(opt.get("tradable", False) for opt in trading_options):
                try:
                    trade_result = await self.analyzer.execute_trade(address, trading_options, chain_type)
                    
                    if trade_result.get("executed"):
                        embed.add_field(
                            name="🚀 Trade Executed!",
                            value=f"**Protocol:** {trade_result.get('protocol')}\n"
                                  f"**Amount:** {trade_result.get('amount')} {trade_result.get('chain')}\n"
                                  f"**Status:** {trade_result.get('status')}\n"
                                  f"**TX:** `{trade_result.get('transaction', trade_result.get('signature', 'N/A'))}`",
                            inline=False
                        )
                        embed.color = 0x00ff00
                    else:
                        embed.add_field(
                            name="⚠️ Trade Not Executed",
                            value=f"Reason: {trade_result.get('reason', 'Unknown')}",
                            inline=False
                        )
                except Exception as e:
                    logger.error(f"Trade execution failed: {e}")
                    embed.add_field(
                        name="❌ Trade Failed",
                        value=f"Error: {str(e)}",
                        inline=False
                    )
            
            # Update the message with results
            await processing_msg.edit(content="", embed=embed)
            
        except Exception as e:
            logger.error(f"Error in process_address: {e}")
            await processing_msg.edit(content=f"❌ Error analyzing address: {str(e)}")

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