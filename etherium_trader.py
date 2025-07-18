# ethereum_trader.py
from web3 import Web3
from eth_account import Account
import json
import time
import logging

logger = logging.getLogger(__name__)

# Ethereum contract addresses
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
    def __init__(self, rpc_url, private_key=None):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        
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
                logger.info(f'Ethereum trader initialized. Wallet address: {self.address}')
                
            except Exception as e:
                logger.error(f"Failed to load Ethereum private key: {e}")
                logger.warning("Ethereum trader initialized in read-only mode")
                self.account = None
                self.address = None
        else:
            self.account = None
            self.address = None
            logger.info('Ethereum trader initialized in read-only mode')
        
        # Initialize contract instances
        self.uniswap_v2_router = self.w3.eth.contract(
            address=ETHEREUM_CONTRACTS["uniswapV2Router"],
            abi=UNISWAP_V2_ROUTER_ABI
        )
        
        self.uniswap_v2_factory = self.w3.eth.contract(
            address=ETHEREUM_CONTRACTS["uniswapV2Factory"],
            abi=UNISWAP_V2_FACTORY_ABI
        )
        
        self.sushiswap_router = self.w3.eth.contract(
            address=ETHEREUM_CONTRACTS["sushiswapRouter"],
            abi=UNISWAP_V2_ROUTER_ABI  # Same ABI as Uniswap V2
        )
        
        self.sushiswap_factory = self.w3.eth.contract(
            address=ETHEREUM_CONTRACTS["sushiswapFactory"],
            abi=UNISWAP_V2_FACTORY_ABI  # Same ABI as Uniswap V2
        )

    def get_gas_config(self, value=0):
        """Get gas configuration for transactions"""
        try:
            # Get current gas price
            gas_price = self.w3.eth.gas_price
            
            # Check if EIP-1559 is supported
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
            else:
                # Legacy transaction
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
                'gasPrice': self.w3.eth.gas_price,
                'gas': 500000
            }

    async def check_and_approve_token(self, token_address, spender_address, amount):
        """Check and approve token for spending"""
        if not self.account:
            raise Exception("Wallet not configured for transactions")
            
        token_contract = self.w3.eth.contract(
            address=token_address,
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
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(f'Approval transaction sent: {tx_hash.hex()}')
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            logger.info('Token approved successfully')
            
            return receipt
        else:
            logger.info('Token already approved')
            return None

    async def buy_on_uniswap_v2(self, token_address, eth_amount, slippage=2):
        """Buy tokens on Uniswap V2"""
        if not self.account:
            raise Exception("Wallet not configured for transactions")
            
        try:
            logger.info(f'Buying {token_address} with {eth_amount} ETH on Uniswap V2...')
            
            # Convert ETH amount to wei
            amount_in_wei = self.w3.to_wei(eth_amount, 'ether')
            
            # Define swap path
            path = [ETHEREUM_CONTRACTS["WETH"], token_address]
            
            # Get expected output
            amounts = self.uniswap_v2_router.functions.getAmountsOut(
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
            
            # Build transaction
            swap_tx = self.uniswap_v2_router.functions.swapExactETHForTokens(
                min_output,
                path,
                self.address,
                deadline
            ).build_transaction({
                'from': self.address,
                'value': amount_in_wei,
                'nonce': self.w3.eth.get_transaction_count(self.address),
                **self.get_gas_config(amount_in_wei)
            })
            
            # Sign and send transaction
            signed_tx = self.account.sign_transaction(swap_tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
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
            logger.error(f'Error buying on Uniswap V2: {e}')
            raise

    async def sell_on_uniswap_v2(self, token_address, token_amount, slippage=2):
        """Sell tokens on Uniswap V2"""
        if not self.account:
            raise Exception("Wallet not configured for transactions")
            
        try:
            logger.info(f'Selling {token_amount} tokens on Uniswap V2...')
            
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
                ETHEREUM_CONTRACTS["uniswapV2Router"],
                amount_in
            )
            
            # Define swap path
            path = [token_address, ETHEREUM_CONTRACTS["WETH"]]
            
            # Get expected output
            amounts = self.uniswap_v2_router.functions.getAmountsOut(
                amount_in,
                path
            ).call()
            
            expected_eth_output = amounts[1]
            
            # Calculate minimum output with slippage
            min_output = int(expected_eth_output * (100 - slippage) / 100)
            
            logger.info(f'Expected output: {self.w3.from_wei(expected_eth_output, "ether")} ETH')
            logger.info(f'Minimum output with {slippage}% slippage: {self.w3.from_wei(min_output, "ether")} ETH')
            
            # Set deadline
            deadline = int(time.time()) + 60 * 20
            
            # Build transaction
            swap_tx = self.uniswap_v2_router.functions.swapExactTokensForETH(
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
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
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
            logger.error(f'Error selling on Uniswap V2: {e}')
            raise

    def check_uniswap_v2_liquidity(self, token_address):
        """Check if token has Uniswap V2 liquidity"""
        try:
            pair_address = self.uniswap_v2_factory.functions.getPair(
                token_address,
                ETHEREUM_CONTRACTS["WETH"]
            ).call()
            
            if pair_address == '0x0000000000000000000000000000000000000000':
                logger.info(f'No Uniswap V2 liquidity found for {token_address}')
                return False
            
            logger.info(f'Uniswap V2 pair found at {pair_address}')
            return True
            
        except Exception as e:
            logger.error(f'Error checking Uniswap V2 liquidity: {e}')
            return False

    def check_sushiswap_liquidity(self, token_address):
        """Check if token has Sushiswap liquidity"""
        try:
            pair_address = self.sushiswap_factory.functions.getPair(
                token_address,
                ETHEREUM_CONTRACTS["WETH"]
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
        """Buy tokens on Sushiswap"""
        if not self.account:
            raise Exception("Wallet not configured for transactions")
            
        try:
            logger.info(f'Buying {token_address} with {eth_amount} ETH on Sushiswap...')
            
            # Convert ETH amount to wei
            amount_in_wei = self.w3.to_wei(eth_amount, 'ether')
            
            # Define swap path
            path = [ETHEREUM_CONTRACTS["WETH"], token_address]
            
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
            
            # Build transaction
            swap_tx = self.sushiswap_router.functions.swapExactETHForTokens(
                min_output,
                path,
                self.address,
                deadline
            ).build_transaction({
                'from': self.address,
                'value': amount_in_wei,
                'nonce': self.w3.eth.get_transaction_count(self.address),
                **self.get_gas_config(amount_in_wei)
            })
            
            # Sign and send
            signed_tx = self.account.sign_transaction(swap_tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
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

    def find_best_dex(self, token_address, eth_amount):
        """Find the best DEX for trading"""
        try:
            logger.info(f'Finding best DEX for {token_address} with {eth_amount} ETH...')
            
            # Convert ETH amount to wei
            amount_in_wei = self.w3.to_wei(eth_amount, 'ether')
            path = [ETHEREUM_CONTRACTS["WETH"], token_address]
            
            # Check Uniswap V2
            uniswap_output = 0
            if self.check_uniswap_v2_liquidity(token_address):
                try:
                    amounts = self.uniswap_v2_router.functions.getAmountsOut(
                        amount_in_wei,
                        path
                    ).call()
                    uniswap_output = amounts[1]
                    logger.info(f'Uniswap V2 output: {self.w3.from_wei(uniswap_output, "ether")} tokens')
                except Exception as e:
                    logger.error(f'Error getting Uniswap V2 output: {e}')
            
            # Check Sushiswap
            sushiswap_output = 0
            if self.check_sushiswap_liquidity(token_address):
                try:
                    amounts = self.sushiswap_router.functions.getAmountsOut(
                        amount_in_wei,
                        path
                    ).call()
                    sushiswap_output = amounts[1]
                    logger.info(f'Sushiswap output: {self.w3.from_wei(sushiswap_output, "ether")} tokens')
                except Exception as e:
                    logger.error(f'Error getting Sushiswap output: {e}')
            
            # Determine best DEX
            if uniswap_output > sushiswap_output:
                return {
                    'dex': 'UniswapV2',
                    'output': uniswap_output,
                    'output_formatted': self.w3.from_wei(uniswap_output, 'ether')
                }
            elif sushiswap_output > uniswap_output:
                return {
                    'dex': 'Sushiswap',
                    'output': sushiswap_output,
                    'output_formatted': self.w3.from_wei(sushiswap_output, 'ether')
                }
            elif uniswap_output > 0:
                return {
                    'dex': 'UniswapV2',
                    'output': uniswap_output,
                    'output_formatted': self.w3.from_wei(uniswap_output, 'ether')
                }
            elif sushiswap_output > 0:
                return {
                    'dex': 'Sushiswap',
                    'output': sushiswap_output,
                    'output_formatted': self.w3.from_wei(sushiswap_output, 'ether')
                }
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
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=ERC20_ABI
            )
            
            symbol = token_contract.functions.symbol().call()
            decimals = token_contract.functions.decimals().call()
            
            info = {
                'address': token_address,
                'symbol': symbol,
                'decimals': decimals
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