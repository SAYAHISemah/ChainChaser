# ethereum_trader.py
from web3 import Web3
from eth_account import Account
import json
import time
import logging

logger = logging.getLogger(__name__)

# Contract addresses for different chains
ETHEREUM_CONTRACTS = {
    # Uniswap V2
    "uniswapV2Router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
    "uniswapV2Factory": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
    
    # Sushiswap
    "sushiswapRouter": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
    "sushiswapFactory": "0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac",
    
    # Tokens
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
}

BSC_CONTRACTS = {
    # PancakeSwap V2
    "pancakeV2Router": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
    "pancakeV2Factory": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
    
    # Tokens - Fix EIP-55 checksum issue
    "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2F95cF0F687B7F55"  # We'll fix this in code
}

# ABIs (simplified for the functions we need)
UNISWAP_V2_ROUTER_ABI = json.loads('''[
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [
            {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [
            {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
        ],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForETH",
        "outputs": [
            {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
        ],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]''')

UNISWAP_V2_FACTORY_ABI = json.loads('''[
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"}
        ],
        "name": "getPair",
        "outputs": [
            {"internalType": "address", "name": "pair", "type": "address"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]''')

ERC20_ABI = json.loads('''[
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [
            {"internalType": "bool", "name": "", "type": "bool"}
        ],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "address", "name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"}
        ],
        "name": "balanceOf",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [
            {"internalType": "uint8", "name": "", "type": "uint8"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [
            {"internalType": "string", "name": "", "type": "string"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]''')

class EthereumTrader:
    def __init__(self, rpc_url, private_key=None, fallback_rpcs=None):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.rpc_url = rpc_url
        self.fallback_rpcs = fallback_rpcs or []
        
        # Detect chain based on RPC URL or chain ID
        self.is_bsc = self._detect_bsc_chain(rpc_url)
        
        if private_key:
            try:
                # Clean up private key format
                cleaned_key = private_key.strip()
                
                # Remove 0x prefix if present
                if cleaned_key.startswith('0x'):
                    cleaned_key = cleaned_key[2:]
                
                # Check key length
                if len(cleaned_key) != 64:
                    logger.error(f"Invalid private key length: {len(cleaned_key)} characters (expected 64)")
                    logger.info("Expected format: 64 hex characters (e.g., 'abc123...def456')")
                    logger.info("Or with 0x prefix: 0xabc123...def456 (66 characters total)")
                    raise ValueError(f"Invalid key length: {len(cleaned_key)}")
                
                # Validate hex characters
                try:
                    int(cleaned_key, 16)
                except ValueError:
                    logger.error("Private key contains non-hexadecimal characters")
                    raise ValueError("Invalid hex format")
                
                # Add 0x prefix back for web3
                if not cleaned_key.startswith('0x'):
                    cleaned_key = '0x' + cleaned_key
                
                self.account = Account.from_key(cleaned_key)
                self.address = self.account.address
                chain_name = "BSC" if self.is_bsc else "Ethereum"
                logger.info(f'{chain_name} trader initialized. Wallet address: {self.address}')
                
            except Exception as e:
                logger.error(f"Failed to load private key: {e}")
                logger.warning("Trader initialized in read-only mode")
                self.account = None
                self.address = None
        else:
            self.account = None
            self.address = None
            chain_name = "BSC" if self.is_bsc else "Ethereum"
            logger.info(f'{chain_name} trader initialized in read-only mode')
        
        # Initialize contract instances based on chain
        self._initialize_contracts()

    def _detect_bsc_chain(self, rpc_url):
        """Detect if this is a BSC chain based on RPC URL or chain ID"""
        if any(bsc_indicator in rpc_url.lower() for bsc_indicator in ['bsc', 'binance']):
            return True
        
        # Try to detect by chain ID
        try:
            chain_id = self.w3.eth.chain_id
            return chain_id == 56 or chain_id == 97  # BSC mainnet or testnet
        except:
            return False

    def _initialize_contracts(self):
        """Initialize contract instances based on the detected chain"""
        if self.is_bsc:
            # Fix the WBNB address with proper checksumming
            wbnb_address = self.w3.to_checksum_address("0xbb4CdB9CBd36B01bD1cBaEBF2F95cF0F687B7F55")
            
            # BSC contracts (PancakeSwap)
            self.router_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(BSC_CONTRACTS["pancakeV2Router"]),
                abi=UNISWAP_V2_ROUTER_ABI
            )
            
            self.factory_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(BSC_CONTRACTS["pancakeV2Factory"]),
                abi=UNISWAP_V2_FACTORY_ABI
            )
            
            self.wrapped_native = wbnb_address
            self.native_symbol = "BNB"
            
        else:
            # Ethereum contracts
            self.uniswap_v2_router = self.w3.eth.contract(
                address=self.w3.to_checksum_address(ETHEREUM_CONTRACTS["uniswapV2Router"]),
                abi=UNISWAP_V2_ROUTER_ABI
            )
            
            self.uniswap_v2_factory = self.w3.eth.contract(
                address=self.w3.to_checksum_address(ETHEREUM_CONTRACTS["uniswapV2Factory"]),
                abi=UNISWAP_V2_FACTORY_ABI
            )
            
            self.sushiswap_router = self.w3.eth.contract(
                address=self.w3.to_checksum_address(ETHEREUM_CONTRACTS["sushiswapRouter"]),
                abi=UNISWAP_V2_ROUTER_ABI  # Same ABI as Uniswap V2
            )
            
            self.sushiswap_factory = self.w3.eth.contract(
                address=self.w3.to_checksum_address(ETHEREUM_CONTRACTS["sushiswapFactory"]),
                abi=UNISWAP_V2_FACTORY_ABI  # Same ABI as Uniswap V2
            )
            
            self.wrapped_native = self.w3.to_checksum_address(ETHEREUM_CONTRACTS["WETH"])
            self.native_symbol = "ETH"
            
            # For convenience, also set router_contract to uniswap for unified access
            self.router_contract = self.uniswap_v2_router

    def get_gas_config(self, value=0):
        """Get gas configuration for transactions"""
        try:
            # Get current gas price
            gas_price = self.w3.eth.gas_price
            
            # Check if EIP-1559 is supported (mainly Ethereum)
            if not self.is_bsc:
                try:
                    latest_block = self.w3.eth.get_block('latest')
                    
                    if 'baseFeePerGas' in latest_block:
                        # EIP-1559 transaction
                        base_fee = latest_block['baseFeePerGas']
                        max_priority_fee = self.w3.eth.max_priority_fee
                        max_fee = int(base_fee * 1.2) + max_priority_fee  # 1.2x base fee + priority
                        
                        return {
                            'value': value,
                            'maxFeePerGas': max_fee,
                            'maxPriorityFeePerGas': max_priority_fee,
                            'gas': 500000,  # Default gas limit
                        }
                except:
                    pass
            
            # Legacy transaction (BSC or Ethereum fallback)
            return {
                'value': value,
                'gasPrice': int(gas_price * 1.2),  # 1.2x current gas price
                'gas': 500000,  # Default gas limit
            }
        except Exception as e:
            logger.warning(f'Error getting gas config: {e}')
            # Fallback configuration
            return {
                'value': value,
                'gasPrice': 20000000000,  # 20 gwei fallback
                'gas': 500000
            }

    async def check_and_approve_token(self, token_address, spender_address, amount):
        """Check and approve token for spending"""
        if not self.account:
            raise Exception("Wallet not configured for transactions")
            
        token_contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )
        
        # Check current allowance
        allowance = token_contract.functions.allowance(
            self.address,
            spender_address
        ).call()
        
        if allowance < amount:
            logger.info(f'Approving {spender_address} to spend tokens...')
            
            # Build approval transaction
            approve_tx = token_contract.functions.approve(
                spender_address,
                self.w3.to_wei(2**64 - 1, 'ether')  # Max approval
            ).build_transaction({
                'from': self.address,
                'nonce': self.w3.eth.get_transaction_count(self.address),
                **self.get_gas_config()
            })
            
            # Sign and send transaction
            signed_tx = self.account.sign_transaction(approve_tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            logger.info(f'Approval transaction sent: {tx_hash.hex()}')
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            logger.info('Token approved successfully')
            
            return receipt
        else:
            logger.info('Token already approved')
            return None

    # Add to ethereum_trader.py - update the buy_on_uniswap_v2 method

    async def buy_on_uniswap_v2(self, token_address, native_amount, slippage=2):
        """Buy tokens on Uniswap V2 or PancakeSwap (depending on chain)"""
        if not self.account:
            raise Exception("Wallet not configured for transactions")
            
        try:
            # Make sure token_address is checksummed
            token_address = self.w3.to_checksum_address(token_address)
            
            protocol_name = "PancakeSwap" if self.is_bsc else "Uniswap V2"
            router = self.router_contract if self.is_bsc else self.uniswap_v2_router
            
            logger.info(f'Buying {token_address} with {native_amount} {self.native_symbol} on {protocol_name}...')
            
            # Convert native amount to wei
            amount_in_wei = self.w3.to_wei(native_amount, 'ether')
            
            # Check wallet balance before proceeding
            balance = self.w3.eth.get_balance(self.address)
            if balance < amount_in_wei:
                raise Exception(f"Insufficient {self.native_symbol} balance. Have {self.w3.from_wei(balance, 'ether')}, need {native_amount}")
            
            # Additional balance check for gas
            estimated_gas_cost = self.w3.eth.gas_price * 300000  # Estimate 300k gas units
            if balance < (amount_in_wei + estimated_gas_cost):
                raise Exception(f"Insufficient {self.native_symbol} to cover both transaction amount and gas")
            
            # Define swap path
            path = [self.wrapped_native, token_address]
            
            # Get expected output
            amounts = router.functions.getAmountsOut(
                amount_in_wei,
                path
            ).call()
            
            expected_output = amounts[1]
            
            # Calculate minimum output with slippage
            min_output = int(expected_output * (100 - slippage) / 100)
            
            logger.info(f'Expected output: {self.w3.from_wei(expected_output, "ether")} tokens')
            logger.info(f'Minimum output with {slippage}% slippage: {self.w3.from_wei(min_output, "ether")} tokens')
            
            # Set deadline (20 minutes from now)
            deadline = int(time.time()) + 60 * 20
            
            # Get gas estimate first
            try:
                gas_estimate = router.functions.swapExactETHForTokens(
                    min_output,
                    path,
                    self.address,
                    deadline
                ).estimate_gas({
                    'from': self.address,
                    'value': amount_in_wei
                })
                logger.info(f'Gas estimate: {gas_estimate}')
            except Exception as e:
                logger.warning(f'Gas estimation failed: {e}. Using default gas limit.')
                gas_estimate = 500000  # Default gas limit
            
            # Get nonce
            try:
                nonce = self.w3.eth.get_transaction_count(self.address)
                logger.info(f'Using nonce: {nonce}')
            except Exception as e:
                logger.error(f'Failed to get nonce: {e}')
                raise
            
            # Get custom gas parameters based on chain
            try:
                if self.is_bsc:
                    # BSC typically uses legacy transactions
                    gas_params = {
                        'value': amount_in_wei,
                        'gas': gas_estimate + 50000,  # Add buffer
                        'gasPrice': int(self.w3.eth.gas_price * 1.1)  # 10% more than current
                    }
                else:
                    # Try EIP-1559 for Ethereum
                    try:
                        base_fee = self.w3.eth.get_block('latest')['baseFeePerGas']
                        max_priority_fee = self.w3.eth.max_priority_fee
                        max_fee = int(base_fee * 1.5) + max_priority_fee  # Higher buffer

                        gas_params = {
                            'value': amount_in_wei,
                            'gas': gas_estimate + 50000,  # Add buffer
                            'maxFeePerGas': max_fee,
                            'maxPriorityFeePerGas': max_priority_fee
                        }
                        logger.info(f'Using EIP-1559 gas: {gas_params}')
                    except:
                        # Fallback to legacy
                        gas_params = {
                            'value': amount_in_wei,
                            'gas': gas_estimate + 50000,  # Add buffer
                            'gasPrice': int(self.w3.eth.gas_price * 1.1)  # 10% more than current
                        }
                        logger.info(f'Using legacy gas: {gas_params}')
            except Exception as e:
                logger.warning(f'Error in gas configuration: {e}, using fallback')
                gas_params = {
                    'value': amount_in_wei,
                    'gas': 500000,
                    'gasPrice': 20000000000  # 20 gwei fallback
                }
            
            # Build transaction
            swap_tx = router.functions.swapExactETHForTokens(
                min_output,
                path,
                self.address,
                deadline
            ).build_transaction({
                'from': self.address,
                'nonce': nonce,
                **gas_params
            })
            
            logger.info(f"Transaction prepared: {json.dumps({k: str(v) for k, v in swap_tx.items()}, indent=2)}")
            
            # Sign transaction
            signed_tx = self.account.sign_transaction(swap_tx)
            
            try:
                # Try sending with increased timeout
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                logger.info(f'Transaction submitted: {tx_hash.hex()}')
                
                # Create explorer link
                if self.is_bsc:
                    explorer_link = f'https://bscscan.com/tx/{tx_hash.hex()}'
                else:
                    explorer_link = f'https://etherscan.io/tx/{tx_hash.hex()}'
                
                logger.info(f'Explorer link: {explorer_link}')
                
                # Wait for confirmation with timeout
                try:
                    receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                    logger.info(f'Transaction confirmed! Status: {receipt["status"]}')
                    
                    return {
                        'transaction_hash': tx_hash.hex(),
                        'status': 'confirmed' if receipt['status'] == 1 else 'failed',
                        'gas_used': receipt['gasUsed'],
                        'block_number': receipt['blockNumber'],
                        'explorer_link': explorer_link
                    }
                except Exception as e:
                    logger.warning(f'Transaction confirmation timed out: {e}')
                    return {
                        'transaction_hash': tx_hash.hex(),
                        'status': 'pending',
                        'explorer_link': explorer_link
                    }
                    
            except Exception as send_error:
                logger.error(f'Error sending transaction: {send_error}')
                
                # Try with a different RPC endpoint if available
                if hasattr(self, 'fallback_rpcs') and self.fallback_rpcs:
                    for rpc_url in self.fallback_rpcs:
                        try:
                            logger.info(f'Trying fallback RPC: {rpc_url}')
                            fallback_w3 = Web3(Web3.HTTPProvider(rpc_url))
                            tx_hash = fallback_w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                            logger.info(f'Transaction submitted via fallback RPC: {tx_hash.hex()}')
                            
                            # Create explorer link
                            if self.is_bsc:
                                explorer_link = f'https://bscscan.com/tx/{tx_hash.hex()}'
                            else:
                                explorer_link = f'https://etherscan.io/tx/{tx_hash.hex()}'
                            
                            logger.info(f'Explorer link: {explorer_link}')
                            return {
                                'transaction_hash': tx_hash.hex(),
                                'status': 'pending',
                                'explorer_link': explorer_link
                            }
                        except Exception as fallback_error:
                            logger.warning(f'Fallback RPC failed: {fallback_error}')
                    
                # If all fallbacks fail, raise the original error
                raise send_error
            
        except Exception as e:
            logger.error(f'Error buying on {protocol_name}: {e}')
            raise

    async def sell_on_uniswap_v2(self, token_address, token_amount, slippage=2):
        """Sell tokens on Uniswap V2 or PancakeSwap (depending on chain)"""
        if not self.account:
            raise Exception("Wallet not configured for transactions")
            
        try:
            # Make sure token_address is checksummed
            token_address = self.w3.to_checksum_address(token_address)
            
            protocol_name = "PancakeSwap" if self.is_bsc else "Uniswap V2"
            router = self.router_contract if self.is_bsc else self.uniswap_v2_router
            router_address = self.w3.to_checksum_address(BSC_CONTRACTS["pancakeV2Router"]) if self.is_bsc else self.w3.to_checksum_address(ETHEREUM_CONTRACTS["uniswapV2Router"])
            
            logger.info(f'Selling {token_amount} tokens on {protocol_name}...')
            
            # Create token contract
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=ERC20_ABI
            )
            
            # Get token decimals
            decimals = token_contract.functions.decimals().call()
            
            # Convert token amount to correct units
            amount_in = int(token_amount * 10**decimals)
            
            # Check balance
            balance = token_contract.functions.balanceOf(self.address).call()
            if balance < amount_in:
                raise Exception(f'Insufficient balance. Have {balance / 10**decimals}, need {token_amount}')
            
            # Approve tokens
            await self.check_and_approve_token(
                token_address,
                router_address,
                amount_in
            )
            
            # Define swap path
            path = [token_address, self.wrapped_native]
            
            # Get expected output
            amounts = router.functions.getAmountsOut(
                amount_in,
                path
            ).call()
            
            expected_native_output = amounts[1]
            
            # Calculate minimum output with slippage
            min_output = int(expected_native_output * (100 - slippage) / 100)
            
            logger.info(f'Expected output: {self.w3.from_wei(expected_native_output, "ether")} {self.native_symbol}')
            logger.info(f'Minimum output with {slippage}% slippage: {self.w3.from_wei(min_output, "ether")} {self.native_symbol}')
            
            # Set deadline
            deadline = int(time.time()) + 60 * 20
            
            # Build transaction
            swap_tx = router.functions.swapExactTokensForETH(
                amount_in,
                min_output,
                path,
                self.address,
                deadline
            ).build_transaction({
                'from': self.address,
                'nonce': self.w3.eth.get_transaction_count(self.address),
                **self.get_gas_config()
            })
            
            # Sign and send
            signed_tx = self.account.sign_transaction(swap_tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            logger.info(f'Transaction submitted: {tx_hash.hex()}')
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            logger.info('Transaction confirmed!')
            
            return {
                'transaction_hash': tx_hash.hex(),
                'status': 'confirmed' if receipt['status'] == 1 else 'failed',
                'gas_used': receipt['gasUsed'],
                'block_number': receipt['blockNumber']
            }
            
        except Exception as e:
            logger.error(f'Error selling on {protocol_name}: {e}')
            raise

    def check_uniswap_v2_liquidity(self, token_address):
        """Check if token has Uniswap V2 or PancakeSwap liquidity"""
        try:
            # Ensure token address is checksummed
            token_address = self.w3.to_checksum_address(token_address)
            
            factory = self.factory_contract if self.is_bsc else self.uniswap_v2_factory
            protocol_name = "PancakeSwap" if self.is_bsc else "Uniswap V2"
            
            pair_address = factory.functions.getPair(
                token_address,
                self.wrapped_native
            ).call()
            
            if pair_address == '0x0000000000000000000000000000000000000000':
                logger.info(f'No {protocol_name} liquidity found for {token_address}')
                return False
            
            logger.info(f'{protocol_name} pair found at {pair_address}')
            return True
            
        except Exception as e:
            logger.error(f'Error checking {protocol_name} liquidity: {e}')
            return False

    def check_sushiswap_liquidity(self, token_address):
        """Check if token has Sushiswap liquidity (Ethereum only)"""
        if self.is_bsc:
            return False  # Sushiswap not available on BSC
            
        try:
            # Ensure token address is checksummed
            token_address = self.w3.to_checksum_address(token_address)
            
            pair_address = self.sushiswap_factory.functions.getPair(
                token_address,
                self.wrapped_native
            ).call()
            
            if pair_address == '0x0000000000000000000000000000000000000000':
                logger.info(f'No Sushiswap liquidity found for {token_address}')
                return False
            
            logger.info(f'Sushiswap pair found at {pair_address}')
            return True
            
        except Exception as e:
            logger.error(f'Error checking Sushiswap liquidity: {e}')
            return False

    async def buy_on_sushiswap(self, token_address, eth_amount, slippage=2):
        """Buy tokens on Sushiswap (Ethereum only)"""
        if self.is_bsc:
            raise Exception("Sushiswap is not available on BSC")
            
        if not self.account:
            raise Exception("Wallet not configured for transactions")
            
        try:
            # Ensure token address is checksummed
            token_address = self.w3.to_checksum_address(token_address)
            
            logger.info(f'Buying {token_address} with {eth_amount} ETH on Sushiswap...')
            
            # Convert ETH amount to wei
            amount_in_wei = self.w3.to_wei(eth_amount, 'ether')
            
            # Define swap path
            path = [self.wrapped_native, token_address]
            
            # Get expected output
            amounts = self.sushiswap_router.functions.getAmountsOut(
                amount_in_wei,
                path
            ).call()
            
            expected_output = amounts[1]
            
            # Calculate minimum output with slippage
            min_output = int(expected_output * (100 - slippage) / 100)
            
            logger.info(f'Expected output: {self.w3.from_wei(expected_output, "ether")} tokens')
            
            # Set deadline
            deadline = int(time.time()) + 60 * 20
            
            # Get gas parameters with value included
            gas_params = self.get_gas_config()
            gas_params['value'] = amount_in_wei
            
            # Build transaction
            swap_tx = self.sushiswap_router.functions.swapExactETHForTokens(
                min_output,
                path,
                self.address,
                deadline
            ).build_transaction({
                'from': self.address,
                'nonce': self.w3.eth.get_transaction_count(self.address),
                **gas_params
            })
            
            # Sign and send
            signed_tx = self.account.sign_transaction(swap_tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            logger.info(f'Transaction submitted: {tx_hash.hex()}')
            logger.info(f'Etherscan link: https://etherscan.io/tx/{tx_hash.hex()}')
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            logger.info('Transaction confirmed!')
            
            return {
                'transaction_hash': tx_hash.hex(),
                'status': 'confirmed' if receipt['status'] == 1 else 'failed',
                'gas_used': receipt['gasUsed'],
                'block_number': receipt['blockNumber']
            }
            
        except Exception as e:
            logger.error(f'Error buying on Sushiswap: {e}')
            raise

    def find_best_dex(self, token_address, native_amount):
        """Find the best DEX for trading"""
        try:
            # Ensure token address is checksummed
            token_address = self.w3.to_checksum_address(token_address)
            
            logger.info(f'Finding best DEX for {token_address} with {native_amount} {self.native_symbol}...')
            
            # Convert native amount to wei
            amount_in_wei = self.w3.to_wei(native_amount, 'ether')
            path = [self.wrapped_native, token_address]
            
            options = []
            
            if self.is_bsc:
                # Check PancakeSwap
                if self.check_uniswap_v2_liquidity(token_address):
                    try:
                        amounts = self.router_contract.functions.getAmountsOut(
                            amount_in_wei,
                            path
                        ).call()
                        pancake_output = amounts[1]
                        options.append({
                            'dex': 'PancakeSwap',
                            'output': pancake_output,
                            'output_formatted': self.w3.from_wei(pancake_output, "ether")
                        })
                        logger.info(f'PancakeSwap output: {self.w3.from_wei(pancake_output, "ether")} tokens')
                    except Exception as e:
                        logger.error(f'Error getting PancakeSwap output: {e}')
            else:
                # Check Uniswap V2
                if self.check_uniswap_v2_liquidity(token_address):
                    try:
                        amounts = self.uniswap_v2_router.functions.getAmountsOut(
                            amount_in_wei,
                            path
                        ).call()
                        uniswap_output = amounts[1]
                        options.append({
                            'dex': 'UniswapV2',
                            'output': uniswap_output,
                            'output_formatted': self.w3.from_wei(uniswap_output, "ether")
                        })
                        logger.info(f'Uniswap V2 output: {self.w3.from_wei(uniswap_output, "ether")} tokens')
                    except Exception as e:
                        logger.error(f'Error getting Uniswap V2 output: {e}')
                
                # Check Sushiswap
                if self.check_sushiswap_liquidity(token_address):
                    try:
                        amounts = self.sushiswap_router.functions.getAmountsOut(
                            amount_in_wei,
                            path
                        ).call()
                        sushiswap_output = amounts[1]
                        options.append({
                            'dex': 'Sushiswap',
                            'output': sushiswap_output,
                            'output_formatted': self.w3.from_wei(sushiswap_output, "ether")
                        })
                        logger.info(f'Sushiswap output: {self.w3.from_wei(sushiswap_output, "ether")} tokens')
                    except Exception as e:
                        logger.error(f'Error getting Sushiswap output: {e}')
            
            # Return best option
            if options:
                best_option = max(options, key=lambda x: x['output'])
                logger.info(f'Best DEX: {best_option["dex"]} with {best_option["output_formatted"]} tokens')
                return best_option
            else:
                return {
                    'dex': None,
                    'output': 0,
                    'output_formatted': '0'
                }
                
        except Exception as e:
            logger.error(f'Error finding best DEX: {e}')
            return {
                'dex': None,
                'output': 0,
                'output_formatted': '0'
            }

    def get_token_info(self, token_address):
        """Get basic token information"""
        try:
            # Ensure token address is checksummed
            token_address = self.w3.to_checksum_address(token_address)
            
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=ERC20_ABI
            )
            
            symbol = token_contract.functions.symbol().call()
            decimals = token_contract.functions.decimals().call()
            
            info = {
                'address': token_address,
                'symbol': symbol,
                'decimals': decimals,
                'chain': 'BSC' if self.is_bsc else 'Ethereum'
            }
            
            # Try to get balance if wallet is configured
            if self.address:
                balance = token_contract.functions.balanceOf(self.address).call()
                info['balance'] = balance / 10**decimals
                info['balance_raw'] = balance
            
            return info
            
        except Exception as e:
            logger.error(f'Error getting token info: {e}')
            return None

    def get_native_balance(self):
        """Get native token balance (ETH/BNB)"""
        if not self.address:
            return 0
        
        try:
            balance = self.w3.eth.get_balance(self.address)
            return self.w3.from_wei(balance, 'ether')
        except Exception as e:
            logger.error(f'Error getting native balance: {e}')
            return 0

    def has_sufficient_funds(self, amount_in_eth):
        """Check if the wallet has enough funds for trading and gas"""
        if not self.account:
            return False
        
        try:
            amount_in_wei = self.w3.to_wei(amount_in_eth, 'ether')
            balance = self.w3.eth.get_balance(self.address)
            
            # Estimate gas cost (very rough estimate)
            gas_price = self.w3.eth.gas_price
            estimated_gas = 300000  # 300k gas units as safe estimate
            estimated_gas_cost = gas_price * estimated_gas
            
            # Check if balance covers amount + gas
            if balance < (amount_in_wei + estimated_gas_cost):
                logger.warning(f"Insufficient funds: {self.w3.from_wei(balance, 'ether')} {self.native_symbol} " +
                            f"available, need ~{self.w3.from_wei(amount_in_wei + estimated_gas_cost, 'ether')} " +
                            f"({amount_in_eth} + gas)")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error checking funds: {e}")
            return False