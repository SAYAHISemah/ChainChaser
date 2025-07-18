# solana_liquidity_checker.py
import requests
import json
import base64
import base58
import time
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solana.transaction import Transaction
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
import logging

logger = logging.getLogger(__name__)

SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
PUMPFUN_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"  # Updated PumpFun program ID
JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_URL = "https://quote-api.jup.ag/v6/swap"
PUMPFUN_API_URL = "https://pumpportal.fun/api"

class SolanaLiquidityChecker:
    def __init__(self):
        self.client = Client(SOLANA_RPC_URL)
        self.pumpfun_pk = Pubkey.from_string(PUMPFUN_PROGRAM_ID)
        
        # Load wallet (you need to set this up)
        self.wallet = self.load_wallet()
        
    def load_wallet(self):
        """Load wallet from private key string"""
        # Replace this string with your actual private key from Phantom
        PRIVATE_KEY = "2zGo3B77Lxm4PEeQ3n8KrNk748TcrRXVHnqFz4kXrZUstuYguKDH6QrQPsiocQBzYnhyWY4KrHG68LKmAbwdrYPM"  # Paste your private key here
    
        try:
            # Convert private key string to bytes and create keypair
            import base58
            private_key_bytes = base58.b58decode(PRIVATE_KEY)
            return Keypair.from_bytes(private_key_bytes)
        except Exception as e:
            logger.error(f"Failed to load wallet: {e}")
            return None

    def is_valid_pubkey(self, addr: str) -> bool:
        try:
            Pubkey.from_string(addr)
            return True
        except Exception:
            return False

    def is_pumpfun_token(self, addr: str) -> bool:
        try:
            target_pk = Pubkey.from_string(addr)
            resp = self.client.get_account_info(target_pk)
            
            if resp.value is None:
                return False
                
            owner_pk = resp.value.owner
            owner_str = str(owner_pk)
            
            logger.info(f"[PumpFun] owner of {addr} → {owner_str}")
            return owner_str == PUMPFUN_PROGRAM_ID
            
        except Exception as e:
            logger.error(f"[PumpFun] RPC error checking {addr}: {e}")
            return False

    def is_raydium_liquid(self, addr: str) -> bool:
        params = {
            "inputMint": "So11111111111111111111111111111111111111112",  # SOL
            "outputMint": addr,
            "amount": 1_000_000,  # 0.001 SOL
            "slippageBps": 100
        }
        
        try:
            resp = requests.get(JUPITER_QUOTE_URL, params=params, timeout=10)
            logger.info(f"[Raydium] GET {resp.url} → {resp.status_code}")
            
            if resp.status_code != 200:
                return False
                
            data = resp.json()
            routes = data.get("routePlan", [])
            
            if not routes:
                logger.info(f"[Raydium] no routes found")
                return False
                
            logger.info(f"[Raydium] {len(routes)} routes found")
            return True
            
        except Exception as e:
            logger.error(f"[Raydium] HTTP error for {addr}: {e}")
            return False

    def get_trading_options(self, addr: str):
        if not self.is_valid_pubkey(addr):
            return [{"chain": "Solana", "protocol": "Invalid", "tradable": False}]

        options = []
        
        # Check PumpFun
        if self.is_pumpfun_token(addr):
            options.append({"chain": "Solana", "protocol": "PumpFun", "tradable": True})
        
        # Check Raydium/Jupiter
        if self.is_raydium_liquid(addr):
            options.append({"chain": "Solana", "protocol": "Raydium", "tradable": True})
        
        if not options:
            options.append({"chain": "Solana", "protocol": "Unknown", "tradable": False})
            
        return options

    async def buy_pumpfun_token(self, token_address: str, sol_amount: float):
        """Buy token on PumpFun"""
        if not self.wallet:
            raise Exception("Wallet not loaded")
            
        try:
            # Convert SOL to lamports
            lamports = int(sol_amount * 1_000_000_000)
            
            # PumpFun buy request
            buy_data = {
                "publicKey": str(self.wallet.pubkey()),
                "action": "buy",
                "mint": token_address,
                "denominatedInSol": "true",
                "amount": lamports,
                "slippage": 10,  # 10% slippage
                "priorityFee": 0.0005,  # 0.0005 SOL priority fee
                "pool": "pump"
            }
            
            logger.info(f"[PumpFun] Buying {sol_amount} SOL worth of {token_address}")
            
            # Get transaction from PumpFun API
            response = requests.post(
                f"{PUMPFUN_API_URL}/trade-local",
                json=buy_data,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"PumpFun API error: {response.text}")
            
            tx_data = response.json()
            
            # Decode and sign transaction
            tx_bytes = base64.b64decode(tx_data["transaction"])
            transaction = VersionedTransaction.from_bytes(tx_bytes)
            
            # Sign transaction
            msg_bytes = bytes(transaction.message)
            signature = self.wallet.sign_message(msg_bytes)
            transaction.signatures = [signature]
            
            # Send transaction
            result = self.client.send_transaction(
                transaction,
                opts=TxOpts(skip_preflight=True, preflight_commitment="confirmed")
            )
            
            signature = str(result.value)
            logger.info(f"[PumpFun] Transaction sent: {signature}")
            
            return {
                "signature": signature,
                "status": "pending",
                "amount": sol_amount,
                "token": token_address
            }
            
        except Exception as e:
            logger.error(f"[PumpFun] Buy failed: {e}")
            raise

    async def buy_via_jupiter(self, token_address: str, sol_amount: float, slippage_bps: int):
        """Buy token via Jupiter (Raydium/other DEXs)"""
        if not self.wallet:
            raise Exception("Wallet not loaded")
            
        try:
            # Convert SOL to lamports
            lamports = int(sol_amount * 1_000_000_000)
            
            # Get quote from Jupiter
            quote_params = {
                "inputMint": "So11111111111111111111111111111111111111112",  # SOL
                "outputMint": token_address,
                "amount": lamports,
                "slippageBps": slippage_bps,
                "swapMode": "ExactIn"
            }
            
            logger.info(f"[Jupiter] Getting quote for {sol_amount} SOL → {token_address}")
            
            quote_response = requests.get(JUPITER_QUOTE_URL, params=quote_params, timeout=10)
            
            if quote_response.status_code != 200:
                raise Exception(f"Jupiter quote failed: {quote_response.text}")
            
            quote_data = quote_response.json()
            
            # Get swap transaction
            swap_data = {
                "userPublicKey": str(self.wallet.pubkey()),
                "quoteResponse": quote_data,
                "prioritizationFeeLamports": 100000,  # Priority fee
                "dynamicComputeUnitLimit": True
            }
            
            swap_response = requests.post(JUPITER_SWAP_URL, json=swap_data, timeout=30)
            
            if swap_response.status_code != 200:
                raise Exception(f"Jupiter swap failed: {swap_response.text}")
            
            swap_result = swap_response.json()
            
            # Decode and sign transaction
            tx_bytes = base64.b64decode(swap_result["swapTransaction"])
            transaction = VersionedTransaction.from_bytes(tx_bytes)
            
            # Sign transaction
            msg_bytes = bytes(transaction.message)
            signature = self.wallet.sign_message(msg_bytes)
            transaction.signatures = [signature]
            
            # Send transaction
            result = self.client.send_transaction(
                transaction,
                opts=TxOpts(skip_preflight=True, preflight_commitment="confirmed")
            )
            
            signature = str(result.value)
            logger.info(f"[Jupiter] Transaction sent: {signature}")
            
            return {
                "signature": signature,
                "status": "pending",
                "amount": sol_amount,
                "token": token_address,
                "expected_output": quote_data.get("outAmount", "unknown")
            }
            
        except Exception as e:
            logger.error(f"[Jupiter] Buy failed: {e}")
            raise

    def get_transaction_status(self, signature: str):
        """Check transaction status"""
        try:
            result = self.client.get_signature_statuses([signature])
            if result.value and result.value[0]:
                status = result.value[0]
                return {
                    "confirmed": status.confirmation_status == "confirmed",
                    "finalized": status.confirmation_status == "finalized",
                    "slot": status.slot,
                    "err": status.err
                }
            return {"confirmed": False, "finalized": False}
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return {"confirmed": False, "finalized": False, "error": str(e)}
        



