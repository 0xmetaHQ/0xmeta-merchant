# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional, Dict, Any
from functools import lru_cache

class Settings(BaseSettings):
    # API Configuration
    BASE_URL: str
    FACILITATOR_URL: str
    APP_NAME: str
    
    # Crypto News
    CRYPTO_NEWS_API_KEY: str

    # Game X
    GAME_API_KEY: str
    GAME_ACCESS_TOKEN: str

    # 0xmeta Facilitator
    OXMETA_TREASURY_WALLET: str

    @field_validator("OXMETA_TREASURY_WALLET", mode="before")
    @classmethod
    def validate_treasury_wallet(cls, v: str) -> str:
        """
        Validate treasury wallet address.
        If a private key is provided (64 hex chars), derive the address.
        Ensure the final value is a valid checksum address.
        """
        try:
            # Check if it looks like a private key (64 hex chars, ignoring 0x prefix)
            clean_v = v.lower().replace("0x", "")
            if len(clean_v) == 64:
                # It's a private key, derive address
                try:
                    from eth_account import Account
                    # Ensure 0x prefix
                    pk = f"0x{clean_v}"
                    account = Account.from_key(pk)
                    return account.address
                except ImportError:
                    pass
                except Exception as e:
                    print(f"❌ Error deriving address from key: {e}")
            
            # If not a private key, assume it's an address and checksum it
            from eth_utils import to_checksum_address
            return to_checksum_address(v)
        except Exception:
            return v

    # Payment Network
    PAYMENT_NETWORK: str
    MERCHANT_PAYOUT_WALLET: str
    MERCHANT_PRIVATE_KEY: str
    USDC_TOKEN_ADDRESS: str
    
    PRICE_PER_REQUEST: int = 10000  # in wei (0.01 USDC with 6 decimals)
    
    # Database
    DATABASE_URL: str
    DATABASE_URL_SYNC: str 
    
    # Redis
    REDIS_URL: str
    REDIS_TTL: int = 3600
    
    # Worker Configuration
    DRAMATIQ_REDIS_URL: str
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SHOW_SQL_ALCHEMY_QUERIES: bool = False
    
    # App Configuration
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    API_PORT: int = 8080
    
    # Auto-settle payments
    AUTO_SETTLE: bool = True

    # X Accounts to monitor
    X_ACCOUNTS: List[str] = [
        "lookonchain",
        "pumpdotfun",
        "virtuals_io",
        "useBackroom",
        "CreatorBid",
        "HyperliquidX",
        "solana",
        "base",
        "ArAIstotle",
        "Cointelegraph",
        "TheBlock__",
        "WatcherGuru",
        "cryptodotnews",
        "blockchainrptr",
    ]

    # Valid categories
    VALID_CATEGORIES: List[str] = [
        "btc", "bitcoin",
        "eth", "ethereum",
        "sol", "solana",
        "base",
        "defi",
        "ai_agents", "ai", "agents",
        "rwa",
        "liquidity",
        "macro", "macro_events",
        "pow", "proof_of_work", "mining",
        "memecoins", "meme",
        "stablecoins", "stable",
        "nft", "nfts",
        "gaming",
        "launchpad",
        "virtuals",
        "trends",
        "other"
    ]

    CATEGORY_ALIASES: Dict[str, str] = {
        "bitcoin": "btc",
        "ethereum": "eth",
        "solana": "sol",
        "ai": "ai_agents",
        "agents": "ai_agents",
        "macro": "macro_events",
        "pow": "proof_of_work",
        "mining": "proof_of_work",
        "meme": "memecoins",
        "stable": "stablecoins",
        "nft": "nfts",
    }

    # ✅ NEW: Auto-detect USDC address based on network
    @property
    def usdc_address(self) -> str:
        """Get USDC token address based on PAYMENT_NETWORK"""
        usdc_addresses = {
            "base": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # Base Mainnet
            "base-sepolia": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",  # Base Sepolia
        }
        address = usdc_addresses.get(self.PAYMENT_NETWORK)
        if not address:
            raise ValueError(f"Unsupported PAYMENT_NETWORK: {self.PAYMENT_NETWORK}")
        return address

    # Network configurations
    @property
    def chain_id(self) -> str:
        """Get chain ID based on PAYMENT_NETWORK"""
        network_configs = {
            "base": "0x2105",  # Base Mainnet (8453)
            "base-sepolia": "0x14a34",  # Base Sepolia (84532)
        }
        chain_id = network_configs.get(self.PAYMENT_NETWORK)
        if not chain_id:
            raise ValueError(f"Unsupported PAYMENT_NETWORK: {self.PAYMENT_NETWORK}")
        return chain_id

    @property
    def rpc_url(self) -> str:
        """Get RPC URL based on PAYMENT_NETWORK"""
        network_configs = {
            "base": "https://mainnet.base.org",
            "base-sepolia": "https://sepolia.base.org",
        }
        rpc = network_configs.get(self.PAYMENT_NETWORK)
        if not rpc:
            raise ValueError(f"Unsupported PAYMENT_NETWORK: {self.PAYMENT_NETWORK}")
        return rpc

    @property
    def block_explorer(self) -> str:
        """Get block explorer URL"""
        network_configs = {
            "base": "https://basescan.org",
            "base-sepolia": "https://sepolia.basescan.org",
        }
        explorer = network_configs.get(self.PAYMENT_NETWORK)
        if not explorer:
            raise ValueError(f"Unsupported PAYMENT_NETWORK: {self.PAYMENT_NETWORK}")
        return explorer

    @property
    def price_usdc(self) -> float:
        """Convert wei to USDC (6 decimals)"""
        return self.PRICE_PER_REQUEST / 1000000.0

    @property
    def total_price_usdc_wei(self) -> int:
        """Total price in wei (PRICE_PER_REQUEST + 10000 fee)"""
        return self.PRICE_PER_REQUEST + 10000

    @property
    def total_price_usdc(self) -> float:
        """Total price in USDC"""
        return (self.PRICE_PER_REQUEST + 10000) / 1000000.0
    
    # ✅ NEW: Validation method
    def validate_addresses(self):
        """Validate all Ethereum addresses"""
        from eth_utils import is_address
        
        addresses_to_check = {
            "OXMETA_TREASURY_WALLET": self.OXMETA_TREASURY_WALLET,
            "MERCHANT_PAYOUT_WALLET": self.MERCHANT_PAYOUT_WALLET,
            "usdc_address": self.usdc_address,
        }
        
        for name, address in addresses_to_check.items():
            if not is_address(address):
                raise ValueError(f"Invalid Ethereum address for {name}: {address}")
        
        return True

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    
    # Validate addresses on initialization
    try:
        settings.validate_addresses()
        print("✅ All Ethereum addresses validated successfully")
        print(f"📍 Network: {settings.PAYMENT_NETWORK}")
        print(f"💵 USDC Address: {settings.usdc_address}")
        print(f"🏦 Treasury: {settings.OXMETA_TREASURY_WALLET}")
        print(f"🏪 Merchant: {settings.MERCHANT_PAYOUT_WALLET}")
    except Exception as e:
        print(f"❌ Address validation failed: {e}")
        raise
    
    return settings

settings = get_settings()