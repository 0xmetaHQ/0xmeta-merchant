from fastapi import APIRouter, HTTPException, Request, Depends, Path
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Tuple, Dict, Any
from app.controllers.news_controller import NewsController
from app.services.x402 import X402PaymentVerifier, PaymentRequirements
from app.core.config import settings

import os
import logging


router = APIRouter(prefix="/news", tags=["news"])
logger = logging.getLogger(__name__)

# Setup Jinja2 templates
templates = Jinja2Templates(directory="app/templates")


def normalize_category(category: str) -> str:
    """Normalize category name"""
    category_lower = category.lower()
    return settings.CATEGORY_ALIASES.get(category_lower, category_lower)


@router.get("/")
async def list_categories():
    """
    **Returns:** List of valid categories with descriptions and pricing information
    """
    return NewsController.list_available_categories(
        price=str(settings.PRICE_PER_REQUEST),
        network=settings.PAYMENT_NETWORK
    )


def create_payment_verifier(category: str):
    """Factory function to create X402PaymentVerifier with proper parameters"""
    return X402PaymentVerifier(
        network=settings.PAYMENT_NETWORK,
        pay_to_address=settings.MERCHANT_PAYOUT_WALLET,
        payment_asset=settings.USDC_TOKEN_ADDRESS,
        asset_name="USDC",
        max_amount_required=str(settings.PRICE_PER_REQUEST),
        resource=f"{settings.BASE_URL}/news/{category}",
        resource_description=f"Access to {category} crypto news and social updates"
    )


@router.get("/{category}")
async def get_news_by_category(
    request: Request,
    category: str = Path(..., description="Category name (e.g., btc, rwa, ai_agents)"),
):
    """
    Get news and tweets for a specific category
    Requires X402 payment or shows paywall.
    Returns HTML paywall if 402, JSON data if settled.
    """
    # Normalize category
    normalized_category = normalize_category(category)
    
    # Validate category
    if normalized_category not in settings.VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid category",
                "message": f"Category '{category}' is not supported",
                "valid_categories": settings.VALID_CATEGORIES
            }
        )
    
    # Create payment verifier
    payment_verifier = create_payment_verifier(normalized_category)
    
    # Check payment
    try:
        settled, payment_requirements = await payment_verifier(
            x_payment=request.headers.get("X-Payment"),
            user_agent=request.headers.get("User-Agent"),
            accept=request.headers.get("Accept")
        )
    except HTTPException as e:
        # Payment required - show paywall
        if e.status_code == 402:
            return templates.TemplateResponse(
                "paywall.html",
                {
                    "request": request,
                    "category": normalized_category,
                    "amount": "0.01",
                    "network": settings.PAYMENT_NETWORK,
                    "recipient": settings.MERCHANT_PAYOUT_WALLET,
                    "token": settings.MERCHANT_PRIVATE_KEY,
                    "payment_requirements": e.detail.get("accepts", [{}])[0] if isinstance(e.detail, dict) else {},
                    "base_url": settings.BASE_URL
                }
            )
        raise e
    
    # Payment verified - fetch and return data
    if settled:
        data = await NewsController.get_news_by_category(normalized_category)
        return JSONResponse(content=data)
    
    # Shouldn't reach here, but just in case
    raise HTTPException(status_code=402, detail="Payment verification failed")