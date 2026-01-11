"""
x402 Payment Verification using 0xmeta Facilitator
Handles payment verification and settlement with automatic fee splitting
"""

import base64
import json
import logging
from typing import Tuple, Optional
from enum import Enum

from fastapi import HTTPException, Header
from pydantic import BaseModel, Field

from app.services.facilitator_client import facilitator_client

logger = logging.getLogger(__name__)


class PaymentSchemes(Enum):
    EXACT = "exact"


class Extra(BaseModel):
    name: str
    version: str


class PaymentRequirements(BaseModel):
    """x402 payment requirements"""
    scheme: str
    network: str
    maxAmountRequired: str
    resource: str
    description: str
    payTo: str
    maxTimeoutSeconds: int = 60
    asset: str
    extra: Optional[Extra] = None


class X402PaymentVerifier:
    """
    FastAPI dependency for X402 payment verification.
    Uses 0xmeta facilitator for verification and settlement.
    """

    def __init__(
        self,
        network: str,
        pay_to_address: str,
        payment_asset: str,
        asset_name: str,
        max_amount_required: str,
        resource: str,
        resource_description: str,
        eip712_version: str = "2",
    ):
        self.payment_requirements = PaymentRequirements(
            scheme=PaymentSchemes.EXACT.value,
            network=network,
            maxAmountRequired=max_amount_required,
            resource=resource,
            description=resource_description,
            payTo=pay_to_address,
            asset=payment_asset,
            extra=Extra(name=asset_name, version=eip712_version),
        )
        self.network = network

    async def __call__(
        self,
        x_payment: str = Header(None, alias="X-Payment"),
        x_payment_hash: str = Header(None, alias="X-Payment-Hash"),
        user_agent: str = Header(None, alias="User-Agent"),
        accept: str = Header(None)
    ) -> Tuple[bool, PaymentRequirements]:
        """
        Check for payment headers and verify/settle if present.
        
        Returns:
            (False, requirements) - No payment, show paywall
            (True, requirements) - Payment verified and settled
        """
        
        logger.info(
            f"X402 check: x_payment={bool(x_payment)}, x_payment_hash={bool(x_payment_hash)}"
        )

        # No payment headers -> return 402 or show paywall
        if not x_payment and not x_payment_hash:
            if accept and "text/html" in accept:
                return False, self.payment_requirements
            
            raise HTTPException(
                status_code=402,
                detail={
                    "x402Version": 1,
                    "error": "X-Payment header is required.",
                    "accepts": [self.payment_requirements.model_dump(mode='json')]
                }
            )

        # Decode payment payload
        payment_payload_obj = None

        if x_payment:
            try:
                decoded = base64.b64decode(x_payment)
                payment_payload_obj = json.loads(decoded.decode("utf-8"))
                
                logger.info(
                    f"Decoded payment: network={payment_payload_obj.get('network')}, "
                    f"scheme={payment_payload_obj.get('scheme')}"
                )
                
            except Exception as e:
                logger.error(f"Failed to decode X-Payment: {e}")
                raise HTTPException(
                    status_code=402,
                    detail={
                        "x402Version": 1,
                        "error": f"Invalid X-Payment payload: {str(e)}",
                        "accepts": [self.payment_requirements.model_dump(mode='json')]
                    }
                )

        if not payment_payload_obj:
            raise HTTPException(
                status_code=402,
                detail={
                    "x402Version": 1,
                    "error": "Payment payload not found",
                    "accepts": [self.payment_requirements.model_dump(mode='json')]
                }
            )

        # ✅ STEP 1: Verify payment with facilitator (x402 format)
        logger.info("🔍 Calling facilitator /v1/verify (x402 standard)")
        
        verify_result = await facilitator_client.verify_payment(
            payment_payload=payment_payload_obj,
            pay_to=self.payment_requirements.payTo,
            amount=self.payment_requirements.maxAmountRequired,
            token=self.payment_requirements.asset,
            chain=self.network,
        )

        if not verify_result.get("success") or not verify_result.get("isValid"):
            error = verify_result.get("error", "verification failed")
            logger.error(f"❌ Facilitator verify failed: {error}")
            
            raise HTTPException(
                status_code=402,
                detail={
                    "x402Version": 1,
                    "error": f"Payment verification failed: {error}",
                    "accepts": [self.payment_requirements.model_dump(mode='json')]
                }
            )

        logger.info("✅ Payment verified successfully")

        # Extract verification ID from x402 response
        verification_id = verify_result.get("verification_id")
        
        if not verification_id:
            logger.warning("⚠️  No verification_id from facilitator")

        # ✅ STEP 2: Settle payment with facilitator (x402 format)
        logger.info(f"💰 Calling facilitator /v1/settle (x402 standard)")
        
        settle_result = await facilitator_client.settle_payment(
            payment_payload=payment_payload_obj,
            pay_to=self.payment_requirements.payTo,
            amount=self.payment_requirements.maxAmountRequired,
            chain=self.network,
        )

        if not settle_result.get("success") or not settle_result.get("settlement_success"):
            error = settle_result.get("error", "settlement failed")
            logger.error(f"❌ Facilitator settle failed: {error}")
            
            raise HTTPException(
                status_code=402,
                detail={
                    "x402Version": 1,
                    "error": f"Payment settlement failed: {error}",
                    "accepts": [self.payment_requirements.model_dump(mode='json')]
                }
            )

        logger.info("✅ Payment successfully verified and settled via facilitator")
        logger.info(f"💵 Transaction hash: {settle_result.get('transaction_hash')}")
        
        return True, self.payment_requirements