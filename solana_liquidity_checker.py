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
from solders.signature import Signature
from solana.rpc.commitment import Confirmed
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
            private_key_bytes = base58.b58decode(PRIVATE_KEY)
            keypair = Keypair.from_bytes(private_key_bytes)
            logger.info(f"Wallet loaded successfully: {keypair.pubkey()}")
            return keypair
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
        """Buy token on PumpFun - FIXED VERSION"""
        if not self.wallet:
            raise Exception("Wallet not loaded")
            
        try:
            # Convert SOL to lamports
            lamports = int(sol_amount * 1_000_000_000)
            
            # Get recent blockhash
            recent_blockhash = self.client.get_latest_blockhash()
            
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
            
            # Decode transaction
            tx_bytes = base64.b64decode(tx_data["transaction"])
            transaction = VersionedTransaction.from_bytes(tx_bytes)
            
            # CRITICAL FIX: Update blockhash to ensure transaction is fresh
            if hasattr(transaction, 'message') and hasattr(transaction.message, 'recent_blockhash'):
                # Create new message with fresh blockhash
                new_message = transaction.message
                new_message.recent_blockhash = recent_blockhash.value.blockhash
                transaction = VersionedTransaction(new_message, transaction.signatures)
            
            # Sign transaction properly
            signature = self.wallet.sign_message(bytes(transaction.message))
            transaction.signatures = [signature]
            
            # Verify transaction is properly signed
            if not transaction.signatures or len(transaction.signatures) == 0:
                raise Exception("Transaction not properly signed")
            
            logger.info(f"[PumpFun] Transaction signed, sending to network...")
            
            # Send transaction with proper options
            result = self.client.send_transaction(
                transaction,
                opts=TxOpts(
                    skip_preflight=False,  # Enable preflight checks
                    preflight_commitment=Confirmed,
                    max_retries=3
                )
            )
            
            if hasattr(result, 'value'):
                signature_str = str(result.value)
            else:
                signature_str = str(result)
            
            logger.info(f"[PumpFun] Transaction sent: {signature_str}")
            
            # Wait for confirmation
            confirmation = self.wait_for_confirmation(signature_str)
            
            return {
                "signature": signature_str,
                "status": "confirmed" if confirmation else "failed",
                "amount": sol_amount,
                "token": token_address,
                "confirmation": confirmation
            }
            
        except Exception as e:
            logger.error(f"[PumpFun] Buy failed: {e}")
            raise

    async def buy_via_jupiter(self, token_address: str, sol_amount: float, slippage_bps: int):
        """Buy token via Jupiter - LEGACY TRANSACTION VERSION"""
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
            
            # Check if we got a valid quote
            if 'outAmount' not in quote_data or int(quote_data['outAmount']) == 0:
                raise Exception("No valid route found or output amount is zero")
            
            logger.info(f"[Jupiter] Quote received, expected output: {quote_data.get('outAmount')}")
            
            # Try to get a legacy transaction format
            swap_data = {
                "userPublicKey": str(self.wallet.pubkey()),
                "quoteResponse": quote_data,
                "wrapAndUnwrapSol": True,
                "computeUnitPriceMicroLamports": 100000,
                "asLegacyTransaction": True  # Request legacy format
            }
            
            logger.info("[Jupiter] Getting legacy transaction...")
            
            swap_response = requests.post(JUPITER_SWAP_URL, json=swap_data, timeout=30)
            
            if swap_response.status_code != 200:
                logger.error(f"Jupiter swap API response: {swap_response.text}")
                # If legacy format fails, try without it
                swap_data.pop("asLegacyTransaction", None)
                swap_response = requests.post(JUPITER_SWAP_URL, json=swap_data, timeout=30)
                
                if swap_response.status_code != 200:
                    raise Exception(f"Jupiter swap failed with status {swap_response.status_code}: {swap_response.text}")
            
            swap_result = swap_response.json()
            
            # Get the serialized transaction
            tx_base64 = swap_result.get("swapTransaction")
            if not tx_base64:
                raise Exception("No transaction data received from Jupiter")
            
            logger.info("[Jupiter] Received transaction from Jupiter, processing...")
            
            # Try to handle both legacy and versioned transactions
            tx_bytes = base64.b64decode(tx_base64)
            
            try:
                # Try as legacy transaction first
                from solana.transaction import Transaction
                
                tx = Transaction.deserialize(tx_bytes)
                logger.info("[Jupiter] Using legacy transaction format")
                
                # Get recent blockhash
                recent_blockhash = self.client.get_latest_blockhash().value.blockhash
                tx.recent_blockhash = recent_blockhash
                
                # Sign with our wallet
                tx.sign(self.wallet)
                
                logger.info("[Jupiter] Legacy transaction signed, sending...")
                
                # Send the transaction
                result = self.client.send_transaction(tx, self.wallet)
                
            except Exception as legacy_error:
                logger.info(f"[Jupiter] Legacy format failed ({legacy_error}), trying versioned...")
                
                # Fall back to versioned transaction
                versioned_tx = VersionedTransaction.from_bytes(tx_bytes)
                
                # Simple signing approach for versioned transaction
                message_bytes = bytes(versioned_tx.message)
                signature = self.wallet.sign_message(message_bytes)
                
                # Replace first signature with ours
                versioned_tx.signatures[0] = signature
                
                logger.info("[Jupiter] Versioned transaction signed, sending...")
                
                # Send the versioned transaction
                result = self.client.send_transaction(
                    versioned_tx,
                    opts=TxOpts(skip_preflight=True, max_retries=3)
                )
            
            if hasattr(result, 'value'):
                signature_str = str(result.value)
            else:
                signature_str = str(result)
            
            logger.info(f"[Jupiter] Transaction sent: {signature_str}")
            
            # Wait for confirmation
            confirmation = self.wait_for_confirmation(signature_str)
            
            return {
                "signature": signature_str,
                "status": "confirmed" if confirmation else "failed",
                "amount": sol_amount,
                "token": token_address,
                "expected_output": quote_data.get("outAmount", "unknown"),
                "confirmation": confirmation
            }
            
        except Exception as e:
            logger.error(f"[Jupiter] Buy failed: {e}")
            import traceback
            logger.error(f"[Jupiter] Full traceback: {traceback.format_exc()}")
            raise

    def wait_for_confirmation(self, signature: str, timeout: int = 60) -> bool:
        """Simple confirmation check using HTTP requests"""
        logger.info(f"Waiting for confirmation of {signature}")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Use direct HTTP request to check status
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getSignatureStatuses",
                    "params": [[signature], {"searchTransactionHistory": True}]
                }
                
                response = requests.post(SOLANA_RPC_URL, json=payload, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'result' in data and data['result']['value'] and data['result']['value'][0]:
                        status = data['result']['value'][0]
                        
                        if status.get('err'):
                            logger.error(f"Transaction failed: {status['err']}")
                            return False
                        
                        confirmation_status = status.get('confirmationStatus', '')
                        
                        if confirmation_status in ['confirmed', 'finalized']:
                            logger.info(f"Transaction confirmed: {signature}")
                            return True
                        
                        logger.info(f"Transaction status: {confirmation_status}")
                    else:
                        logger.info("Transaction not found yet...")
                
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"Error checking confirmation: {e}")
                time.sleep(3)
        
        logger.warning(f"Transaction confirmation timeout after {timeout}s")
        return False

    def get_transaction_status(self, signature: str):
        """Check transaction status - ENHANCED VERSION"""
        try:
            # Check signature status
            result = self.client.get_signature_statuses([signature])
            
            if result.value and result.value[0]:
                status = result.value[0]
                
                status_info = {
                    "confirmed": status.confirmation_status in ["confirmed", "finalized"],
                    "finalized": status.confirmation_status == "finalized",
                    "confirmation_status": status.confirmation_status,
                    "slot": status.slot,
                    "err": status.err
                }
                
                # Try to get transaction details
                try:
                    tx_details = self.client.get_transaction(signature)
                    if tx_details.value:
                        status_info["block_time"] = tx_details.value.block_time
                        status_info["fee"] = tx_details.value.meta.fee if tx_details.value.meta else None
                except:
                    pass  # Transaction details not available yet
                
                return status_info
            
            return {
                "confirmed": False, 
                "finalized": False,
                "confirmation_status": "not_found"
            }
            
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return {
                "confirmed": False, 
                "finalized": False, 
                "error": str(e)
            }

    def get_balance(self) -> float:
        """Get SOL balance of the wallet"""
        if not self.wallet:
            return 0.0
        
        try:
            balance_lamports = self.client.get_balance(self.wallet.pubkey())
            return balance_lamports.value / 1_000_000_000  # Convert to SOL
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0.0

    def simulate_transaction(self, transaction) -> bool:
        """Simulate transaction before sending"""
        try:
            result = self.client.simulate_transaction(transaction)
            
            if result.value.err:
                logger.error(f"Transaction simulation failed: {result.value.err}")
                return False
            
            logger.info("Transaction simulation successful")
            return True
            
        except Exception as e:
            logger.error(f"Transaction simulation error: {e}")
            return False