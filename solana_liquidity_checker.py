# solana_liquidity_checker.py

import requests
from solders.pubkey import Pubkey
from solana.rpc.api import Client

SOLANA_RPC_URL     = "https://api.mainnet-beta.solana.com"
PUMPFUN_PROGRAM_ID = "CkFh4b3JikRYwXL1cGpWwh2QDjPdtKr67q6jD9Y4yYD"
JUPITER_QUOTE_URL  = "https://quote-api.jup.ag/v6/quote"

class SolanaLiquidityChecker:
    def __init__(self):
        self.client       = Client(SOLANA_RPC_URL)
        # Pre-parse the PumpFun program ID to a Pubkey for easy comparison
        self.pumpfun_pk   = Pubkey.from_string(PUMPFUN_PROGRAM_ID)

    def is_valid_pubkey(self, addr: str) -> bool:
        try:
            Pubkey.from_string(addr)
            return True
        except Exception:
            return False

    def is_pumpfun_token(self, addr: str) -> bool:
        try:
            # Convert the address into a solders.Pubkey
            target_pk = Pubkey.from_string(addr)
            resp      = self.client.get_account_info(target_pk)
            # Access the owner via .value.owner, not via dict subscripting :contentReference[oaicite:0]{index=0}
            owner_pk  = resp.value.owner
            owner_str = str(owner_pk)
            print(f"[PumpFun] owner of {addr} → {owner_str}")
            # Compare against the known PumpFun program ID
            return owner_str == PUMPFUN_PROGRAM_ID
        except Exception as e:
            print(f"[PumpFun] RPC error checking {addr}: {e}")
            return False

    def is_raydium_liquid(self, addr: str) -> bool:
        params = {
            "inputMint":  "So11111111111111111111111111111111111111112",  # SOL
            "outputMint": addr,
            "amount":     1_000_000,   # 0.001 SOL
            "slippageBps": 100
        }
        try:
            resp = requests.get(JUPITER_QUOTE_URL, params=params, timeout=5)
            print(f"[Raydium] GET {resp.url} → {resp.status_code}")
            data = resp.json()
            routes = data.get("routePlan") or []
            if not routes:
                print(f"[Raydium] no pools → {data}")
                return False
            print(f"[Raydium] pools found → {len(routes)} routes")
            return True
        except Exception as e:
            print(f"[Raydium] HTTP error for {addr}: {e}")
            return False

    def get_trading_options(self, addr: str):
        if not self.is_valid_pubkey(addr):
            return [{"chain":"Solana","protocol":"Invalid","tradable":False}]

        if self.is_pumpfun_token(addr):
            return [{"chain":"Solana","protocol":"PumpFun","tradable":True}]

        if self.is_raydium_liquid(addr):
            return [{"chain":"Solana","protocol":"Raydium","tradable":True}]

        return [{"chain":"Solana","protocol":"Unknown","tradable":False}]
