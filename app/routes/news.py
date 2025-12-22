"""
News API routes with x402 payment via 0xmeta facilitator
"""

from fastapi import APIRouter, HTTPException, Request, Path
from fastapi.responses import JSONResponse
from typing import Tuple

from app.controllers.news_controller import NewsController
from app.services.x402 import X402PaymentVerifier, PaymentRequirements
from app.core.config import settings

import logging

router = APIRouter(prefix="/news", tags=["news"])
logger = logging.getLogger(__name__)


def normalize_category(category: str) -> str:
    """Normalize category name using configured aliases"""
    category_lower = category.lower()
    return settings.CATEGORY_ALIASES.get(category_lower, category_lower)


def create_payment_verifier(category: str) -> X402PaymentVerifier:
    """Factory function to create X402PaymentVerifier for a specific category"""
    return X402PaymentVerifier(
        network=settings.PAYMENT_NETWORK,
        pay_to_address=settings.MERCHANT_PAYOUT_WALLET,
        payment_asset=settings.USDC_TOKEN_ADDRESS,
        asset_name="USDC",
        max_amount_required=str(settings.PRICE_PER_REQUEST),
        resource=f"{settings.BASE_URL}/news/{category}",
        resource_description=f"Access to {category} crypto news and social updates"
    )


@router.get("/")
async def list_categories():
    """
    List all available news categories with descriptions and pricing.
    
    **Returns:** 
    - List of categories with aliases, descriptions, and tickers
    - Pricing information (amount, currency, network)
    - Available features
    """
    return NewsController.list_available_categories(
        price=str(settings.PRICE_PER_REQUEST),
        network=settings.PAYMENT_NETWORK
    )


@router.get("/free/{category}")
async def get_free_news_by_category(
    category: str = Path(..., description="Free category: rwa, macro, or virtuals")
):
    
    normalized_category = normalize_category(category)
    
    # Restrict to free categories only
    FREE_CATEGORIES = ["rwa", "macro_events", "virtuals"]
    if normalized_category not in FREE_CATEGORIES:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Category not available for free access",
                "free_categories": ["rwa", "macro", "virtuals"],
                "message": f"Category '{category}' requires payment",
                "paid_endpoint": f"{settings.BASE_URL}/news/{category}",
                "price": f"{int(settings.PRICE_PER_REQUEST) / 1_000_000} USDC"
            }
        )
    
    # Validate category exists
    if normalized_category not in settings.VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid category",
                "message": f"Category '{category}' is not supported",
                "valid_categories": list(settings.VALID_CATEGORIES)
            }
        )
    
    # Fetch and return data (no payment required)
    logger.info(f"📖 Free access to category: {normalized_category}")
    data = await NewsController.get_news_by_category(normalized_category)
    return JSONResponse(content=data)


@router.get("/{category}")
async def get_news_by_category(
    request: Request,
    category: str = Path(..., description="Category name (e.g., btc, base, ai_agents)")
):
    # Normalize and validate category
    normalized_category = normalize_category(category)
    
    if normalized_category not in settings.VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid category",
                "message": f"Category '{category}' is not supported",
                "valid_categories": list(settings.VALID_CATEGORIES),
                "free_categories": ["rwa", "macro", "virtuals"]
            }
        )
    
    # Create payment verifier for this category
    payment_verifier = create_payment_verifier(normalized_category)
    
    # Verify and settle payment
    logger.info(f"🔐 Checking payment for category: {normalized_category}")
    
    try:
        settled, payment_requirements = await payment_verifier(
            x_payment=request.headers.get("X-Payment"),
            x_payment_hash=request.headers.get("X-Payment-Hash"),
            user_agent=request.headers.get("User-Agent"),
            accept=request.headers.get("Accept")
        )
        
    except HTTPException as e:
        # Re-raise 402 errors with clean response (no HTML)
        if e.status_code == 402:
            logger.warning(f"❌ Payment required for category: {normalized_category}")
            raise
        raise e
    
    # Payment successfully verified and settled
    if settled:
        logger.info(f"✅ Payment settled for category: {normalized_category}")
        data = await NewsController.get_news_by_category(normalized_category)
        return JSONResponse(content=data)
    
    # Fallback (should not reach here)
    logger.error(f"⚠️  Payment verification returned False without raising exception")
    raise HTTPException(
        status_code=402,
        detail={
            "x402Version": 1,
            "error": "Payment verification failed",
            "accepts": [payment_requirements.model_dump(mode='json')]
        }
    )