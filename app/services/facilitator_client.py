"""
0xmeta Facilitator Client - x402 Standard Compliant
Handles payment verification and settlement using x402 protocol
"""

import os
import logging
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class FacilitatorClient:
    """Async client for 0xmeta facilitator API using x402 standard"""
    
    def __init__(self):
        self.base_url = settings.FACILITATOR_URL.rstrip("/") if hasattr(settings, 'FACILITATOR_URL') else None
        if not self.base_url:
            logger.warning("FACILITATOR_URL not configured")
    
    async def verify_payment(
        self,
        payment_payload: Dict[str, Any],
        pay_to: str,
        amount: str,
        token: str,
        chain: str,
    ) -> Dict[str, Any]:
        """
        Verify a payment with 0xmeta facilitator using x402 standard format.
        
        Args:
            payment_payload: Full x402 payment payload with authorization and signature
            pay_to: Merchant wallet address
            amount: Expected amount in wei
            token: Token contract address
            chain: Network name (base-sepolia, base)
            
        Returns:
            {
                "success": bool,
                "data": {
                    "isValid": bool,
                    "message": str,
                    "details": {...}
                }
            }
        """
        # ✅ Build x402 standard request
        x402_request = {
            "paymentPayload": payment_payload,
            "paymentRequirements": {
                "payTo": pay_to.lower(),
                "amount": amount,
                "token": token.lower(),
                "chain": chain
            }
        }
        
        logger.info(f"🔍 Calling facilitator /v1/verify (x402 standard)")
        logger.debug(f"x402 verify request: {x402_request}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/v1/verify",
                    json=x402_request
                )
            except Exception as e:
                logger.exception("❌ Network error calling facilitator verify")
                return {"success": False, "error": str(e)}
        
        logger.info(f"📥 Facilitator verify response: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            
            # ✅ x402 response: {"isValid": true, "message": "...", "details": {...}}
            is_valid = data.get("isValid", False)
            
            logger.info(f"✅ Payment verification: isValid={is_valid}")
            
            return {
                "success": True,
                "data": data,
                "isValid": is_valid,
                "verification_id": data.get("details", {}).get("verification_id")
            }
        else:
            error_text = resp.text
            logger.error(f"❌ Verify failed: {error_text}")
            return {
                "success": False,
                "error": f"HTTP {resp.status_code}: {error_text}",
                "status_code": resp.status_code
            }
    
    async def settle_payment(
        self,
        payment_payload: Dict[str, Any],
        pay_to: str,
        amount: Optional[str] = None,
        chain: str = "base-sepolia",
    ) -> Dict[str, Any]:
        """
        Settle a verified payment using x402 standard format.
        
        Args:
            payment_payload: Full x402 payment payload with authorization and signature
            pay_to: Merchant wallet to receive funds
            amount: Optional amount override
            chain: Network name
            
        Returns:
            {
                "success": bool,
                "data": {
                    "success": bool,
                    "transaction": str,
                    "message": str,
                    "details": {...}
                }
            }
        """
        # ✅ Build x402 standard request
        x402_request = {
            "paymentPayload": payment_payload,
            "paymentRequirements": {
                "payTo": pay_to.lower(),
                "chain": chain
            }
        }
        
        if amount:
            x402_request["paymentRequirements"]["amount"] = amount
        
        logger.info(f"⚡ Calling facilitator /v1/settle (x402 standard)")
        logger.debug(f"x402 settle request: {x402_request}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/v1/settle",
                    json=x402_request
                )
            except Exception as e:
                logger.exception("❌ Network error calling facilitator settle")
                return {"success": False, "error": str(e)}
        
        logger.info(f"📥 Facilitator settle response: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            
            # ✅ x402 response: {"success": true, "transaction": "0x...", "message": "...", "details": {...}}
            settlement_success = data.get("success", False)
            transaction_hash = data.get("transaction")
            
            logger.info(f"✅ Payment settlement: success={settlement_success}, tx={transaction_hash}")
            
            return {
                "success": True,
                "data": data,
                "settlement_success": settlement_success,
                "transaction_hash": transaction_hash,
                "settlement_id": data.get("details", {}).get("settlement_id")
            }
        else:
            error_text = resp.text
            logger.error(f"❌ Settle failed: {error_text}")
            return {
                "success": False,
                "error": f"HTTP {resp.status_code}: {error_text}",
                "status_code": resp.status_code
            }


# Singleton instance
facilitator_client = FacilitatorClient()