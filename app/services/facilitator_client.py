"""
0xmeta Facilitator Client
Handles payment verification and settlement
"""

import os
import logging
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class FacilitatorClient:
    """Async client for 0xmeta facilitator API"""
    
    def __init__(self):
        self.base_url = settings.FACILITATOR_URL.rstrip("/") if hasattr(settings, 'FACILITATOR_URL') else None
        if not self.base_url:
            logger.warning("FACILITATOR_URL not configured")
    
    async def verify_payment(
        self,
        transaction_hash: str,
        chain: str,
        seller_address: str,
        expected_amount: str,
        expected_token: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Verify a payment with 0xmeta facilitator
        
        Args:
            transaction_hash: Transaction/nonce hash
            chain: Network name (base-sepolia, base)
            seller_address: Merchant wallet address
            expected_amount: Expected amount in wei
            expected_token: Token contract address
            metadata: Additional metadata
            
        Returns:
            {"success": bool, "data": dict} or {"success": false, "error": str}
        """
        payload = {
            "transaction_hash": transaction_hash,
            "chain": chain,
            "seller_address": seller_address.lower(),
            "expected_amount": expected_amount,
            "expected_token": expected_token.lower(),
            "metadata": metadata or {},
        }
        
        logger.info(f"🔍 Calling facilitator /v1/verify")
        logger.debug(f"Verify payload: {payload}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/v1/verify",
                    json=payload
                )
            except Exception as e:
                logger.exception("❌ Network error calling facilitator verify")
                return {"success": False, "error": str(e)}
        
        logger.info(f"📥 Facilitator verify response: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"✅ Payment verified successfully")
            return {"success": True, "data": data}
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
        verification_id: str,
        destination_address: str,
        amount: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Settle a verified payment
        
        Args:
            verification_id: ID from verify response
            destination_address: Merchant wallet to receive funds
            amount: Optional amount override
            metadata: Additional metadata
            
        Returns:
            {"success": bool, "data": dict} or {"success": false, "error": str}
        """
        payload = {
            "verification_id": verification_id,
            "destination_address": destination_address.lower(),
        }
        
        if amount:
            payload["amount"] = amount
        
        if metadata:
            payload["metadata"] = metadata
        
        logger.info(f"⚡ Calling facilitator /v1/settle")
        logger.debug(f"Settle payload: {payload}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/v1/settle",
                    json=payload
                )
            except Exception as e:
                logger.exception("❌ Network error calling facilitator settle")
                return {"success": False, "error": str(e)}
        
        logger.info(f"📥 Facilitator settle response: {resp.status_code}")
        
        if resp.status_code == 200:
            logger.info(f"✅ Payment settled successfully")
            return {"success": True, "data": resp.json()}
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