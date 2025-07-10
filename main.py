# main_bot.py
import discord
import re
import requests
import asyncio
from web3 import Web3
from solana_liquidity_checker import SolanaLiquidityChecker
import json
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Trading Configuration
TRADING_CONFIG = {
    "enabled": True,
    "sol_amount": 0.001,  # Amount in SOL to trade
    "slippage_bps": 500,  # 5% slippage
    "priority_fee": 0.001,  # Priority fee in SOL
    "auto_execute": True,  # Set to False to only analyze without executing
    "max_market_cap": 1000000,  # Max market cap in USD (optional filter)
}

# RPC endpoints
RPC_ENDPOINTS = {
    "ethereum": "https://mainnet.infura.io/v3/YOUR_INFURA_KEY",
    "bsc": "https://bsc-dataseed.binance.org/",
}

class ChainAnalyzer:
    def __init__(self):
        self.eth_provider = Web3(Web3.HTTPProvider(RPC_ENDPOINTS["ethereum"]))
        self.bsc_provider = Web3(Web3.HTTPProvider(RPC_ENDPOINTS["bsc"]))
        self.solana_checker = SolanaLiquidityChecker()
        
        logger.info(f"ETH connected: {self.eth_provider.is_connected()}")
        logger.info(f"BSC connected: {self.bsc_provider.is_connected()}")

    def is_evm_address(self, addr: str) -> bool:
        return bool(re.match(r"^0x[a-fA-F0-9]{40}$", addr))

    def is_solana_address(self, addr: str) -> bool:
        return bool(re.match(r"^[A-HJ-NP-Za-km-z1-9]{32,44}$", addr))

    def check_evm_liquidity(self, addr):
        opts = []
        if self.bsc_provider.is_connected():
            opts.append({"chain": "BSC", "protocol": "PancakeSwap", "tradable": True})
        if self.eth_provider.is_connected():
            opts += [
                {"chain": "Ethereum", "protocol": "UniswapV2", "tradable": True},
                {"chain": "Ethereum", "protocol": "Sushiswap", "tradable": True},
            ]
        return opts

    def check_solana_liquidity(self, addr):
        return self.solana_checker.get_trading_options(addr)

    async def execute_trade(self, address: str, trading_options: list):
        """Execute trade if conditions are met"""
        if not TRADING_CONFIG["enabled"] or not TRADING_CONFIG["auto_execute"]:
            return {"executed": False, "reason": "Auto-execution disabled"}
        
        for option in trading_options:
            if option["chain"] == "Solana" and option["tradable"]:
                if option["protocol"] == "PumpFun":
                    return await self.execute_pumpfun_trade(address)
                elif option["protocol"] == "Raydium":
                    return await self.execute_raydium_trade(address)
        
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
                "transaction": result.get("signature"),
                "status": result.get("status", "pending")
            }
        except Exception as e:
            logger.error(f"PumpFun trade failed: {e}")
            return {"executed": False, "reason": f"PumpFun trade failed: {str(e)}"}

    async def execute_raydium_trade(self, token_address: str):
        """Execute Raydium trade via Jupiter"""
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
                "transaction": result.get("signature"),
                "status": result.get("status", "pending")
            }
        except Exception as e:
            logger.error(f"Raydium trade failed: {e}")
            return {"executed": False, "reason": f"Raydium trade failed: {str(e)}"}

    async def analyze_and_trade(self, address: str):
        """Analyze token and execute trade if conditions are met"""
        result = {"address": address, "type": None, "tradingOptions": [], "execution": None}
        
        if self.is_evm_address(address):
            result["type"] = "EVM"
            result["tradingOptions"] = self.check_evm_liquidity(address)
        elif self.is_solana_address(address):
            result["type"] = "Solana"
            result["tradingOptions"] = self.check_solana_liquidity(address)
            
            # Execute trade for Solana tokens
            if any(opt["tradable"] for opt in result["tradingOptions"]):
                result["execution"] = await self.execute_trade(address, result["tradingOptions"])
        else:
            raise ValueError("Invalid address format")
        
        return result

# Discord setup
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
analyzer = ChainAnalyzer()

@client.event
async def on_ready():
    print(f" Trading Bot logged in as {client.user}")
    print(f"  Auto-execution: {'ON' if TRADING_CONFIG['auto_execute'] else 'OFF'}")
    print(f" Trade amount: {TRADING_CONFIG['sol_amount']} SOL")

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    # Check for configuration commands
    if message.content.startswith("!config"):
        await handle_config_command(message)
        return
    
    # Extract addresses
    addresses = re.findall(
        r'\b0x[a-fA-F0-9]{40}\b|\b[A-HJ-NP-Za-km-z1-9]{32,44}\b',
        message.content
    )
    
    for addr in addresses:
        try:
            # Add loading reaction
            await message.add_reaction("⏳")
            
            res = await analyzer.analyze_and_trade(addr)
            
            # Format response
            output = f"🔍 **Analysis for {addr[:8]}...{addr[-8:]}**\n"
            output += f"**Type:** {res['type']}\n"
            output += f"**Trading Options:** {len(res['tradingOptions'])} found\n"
            
            for opt in res['tradingOptions']:
                status = "✅" if opt['tradable'] else "❌"
                output += f"  {status} {opt['protocol']} on {opt['chain']}\n"
            
            # Add execution info if available
            if res.get('execution'):
                exec_info = res['execution']
                if exec_info['executed']:
                    output += f"\n **TRADE EXECUTED!**\n"
                    output += f"**Protocol:** {exec_info['protocol']}\n"
                    output += f"**Amount:** {exec_info['amount']} SOL\n"
                    output += f"**Status:** {exec_info['status']}\n"
                    if exec_info.get('transaction'):
                        output += f"**TX:** `{exec_info['transaction'][:16]}...`\n"
                    
                    # Add success reaction
                    await message.add_reaction("✅")
                else:
                    output += f"\n❌ **Trade not executed:** {exec_info['reason']}\n"
            
            await message.channel.send(output)
            
            # Remove loading reaction
            await message.remove_reaction("⏳", client.user)
            
        except ValueError as e:
            await message.channel.send(f"❌ Error: {e}")
            await message.remove_reaction("⏳", client.user)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await message.channel.send(f"❌ Unexpected error occurred")
            await message.remove_reaction("⏳", client.user)

async def handle_config_command(message):
    """Handle configuration commands"""
    parts = message.content.split()
    
    if len(parts) == 1:
        # Show current config
        config_msg = "⚙️ **Current Configuration:**\n"
        config_msg += f"Auto-execute: {'ON' if TRADING_CONFIG['auto_execute'] else 'OFF'}\n"
        config_msg += f"SOL Amount: {TRADING_CONFIG['sol_amount']}\n"
        config_msg += f"Slippage: {TRADING_CONFIG['slippage_bps']/100}%\n"
        config_msg += f"Priority Fee: {TRADING_CONFIG['priority_fee']} SOL\n"
        config_msg += "\n**Commands:**\n"
        config_msg += "`!config toggle` - Toggle auto-execution\n"
        config_msg += "`!config amount <SOL>` - Set trade amount\n"
        config_msg += "`!config slippage <percent>` - Set slippage\n"
        await message.channel.send(config_msg)
        return
    
    if parts[1] == "toggle":
        TRADING_CONFIG["auto_execute"] = not TRADING_CONFIG["auto_execute"]
        status = "ON" if TRADING_CONFIG["auto_execute"] else "OFF"
        await message.channel.send(f" Auto-execution turned {status}")
    
    elif parts[1] == "amount" and len(parts) == 3:
        try:
            amount = float(parts[2])
            if 0 < amount <= 1:  # Reasonable limits
                TRADING_CONFIG["sol_amount"] = amount
                await message.channel.send(f"Trade amount set to {amount} SOL")
            else:
                await message.channel.send("❌ Amount must be between 0 and 1 SOL")
        except ValueError:
            await message.channel.send("❌ Invalid amount format")
    
    elif parts[1] == "slippage" and len(parts) == 3:
        try:
            slippage = float(parts[2])
            if 0 < slippage <= 50:  # 0-50% slippage
                TRADING_CONFIG["slippage_bps"] = int(slippage * 100)
                await message.channel.send(f" Slippage set to {slippage}%")
            else:
                await message.channel.send("❌ Slippage must be between 0 and 50%")
        except ValueError:
            await message.channel.send("❌ Invalid slippage format")

if __name__ == "__main__":
    client.run("xx")



