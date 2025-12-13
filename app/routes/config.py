from fastapi import APIRouter, Depends
from app.core.config import get_settings, Settings
from typing import Dict, Any

router = APIRouter(prefix="/api", tags=["config"])

@router.get("/config")
async def get_config(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Get frontend configuration"""
    return {
        "facilitator_base_url": settings.FACILITATOR_URL,
        "price_usdc_wei": str(settings.PRICE_PER_REQUEST),
        "price_usdc": settings.price_usdc,
        "total_price_usdc_wei": str(settings.total_price_usdc_wei),
        "total_price_usdc": settings.total_price_usdc,
        "chain_id": settings.chain_id,
        "network": settings.PAYMENT_NETWORK,
        "rpc_url": settings.rpc_url,
        "block_explorer": settings.block_explorer,
        "usdc_address": settings.MERCHANT_PRIVATE_KEY,
        "treasury_wallet": settings.OXMETA_TREASURY_WALLET,
        "recipient_wallet": settings.MERCHANT_PAYOUT_WALLET,
        "app_name": settings.APP_NAME,
    }