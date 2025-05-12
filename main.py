# main_bot.py

import discord, re, requests
from web3 import Web3
from solana_liquidity_checker import SolanaLiquidityChecker

# — your RPC endpoints, routers, etc. —
RPC_ENDPOINTS = {
    "ethereum": "https://mainnet.infura.io/v3/YOUR_INFURA_KEY",
    "bsc":      "https://bsc-dataseed.binance.org/"
}

class ChainAnalyzer:
    def __init__(self):
        self.eth_provider   = Web3(Web3.HTTPProvider(RPC_ENDPOINTS["ethereum"]))
        self.bsc_provider   = Web3(Web3.HTTPProvider(RPC_ENDPOINTS["bsc"]))
        self.solana_checker = SolanaLiquidityChecker()

    def is_evm_address(self, addr: str) -> bool:
        return bool(re.match(r"^0x[a-fA-F0-9]{40}$", addr))

    def is_solana_address(self, addr: str) -> bool:
        return bool(re.match(r"^[A-HJ-NP-Za-km-z1-9]{32,44}$", addr))

    def check_evm_liquidity(self, addr):
        opts = []
        if self.bsc_provider.is_connected():
            opts.append({"chain":"BSC","protocol":"PancakeSwap","tradable":True})
        if self.eth_provider.is_connected():
            opts += [
                {"chain":"Ethereum","protocol":"UniswapV2","tradable":True},
                {"chain":"Ethereum","protocol":"Sushiswap","tradable":True},
            ]
        return opts

    def check_solana_liquidity(self, addr):
        # DELEGATION to the separated file
        return self.solana_checker.get_trading_options(addr)

    def analyze(self, address: str):
        result = {"address": address, "type": None, "tradingOptions": []}
        if self.is_evm_address(address):
            result["type"] = "EVM"
            result["tradingOptions"] = self.check_evm_liquidity(address)
        elif self.is_solana_address(address):
            result["type"] = "Solana"
            result["tradingOptions"] = self.check_solana_liquidity(address)
        else:
            raise ValueError("Invalid address format")
        return result

# — Discord setup —
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
analyzer = ChainAnalyzer()

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # extract addresses
    addresses = re.findall(
        r'\b0x[a-fA-F0-9]{40}\b|\b[A-HJ-NP-Za-km-z1-9]{32,44}\b',
        message.content
    )
    for addr in addresses:
        try:
            res    = analyzer.analyze(addr)
            output = f"Analyzed {addr}: Type={res['type']}, Options={res['tradingOptions']}"
            await message.channel.send(output)
            print(output)
        except ValueError as e:
            err = f"Error: {e}"
            await message.channel.send(err)
            print(err)

client.run("MTM0ODA2NjQ1ODg1MjEzNDk3NA.GQW67E.bsBIZijNGXPht8sQOiCxiig-0jTmBFdVH_eWek")
