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
        tx_hash = None

        if x_payment:
            try:
                decoded = base64.b64decode(x_payment)
                payment_payload_obj = json.loads(decoded.decode("utf-8"))
                
                logger.info(
                    f"Decoded payment: network={payment_payload_obj.get('network')}, "
                    f"scheme={payment_payload_obj.get('scheme')}"
                )
                
                # Extract transaction hash from nonce (EIP-3009)
                tx_hash = payment_payload_obj["payload"]["authorization"]["nonce"]
                
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

        # Fallback to X-Payment-Hash header
        if not tx_hash and x_payment_hash:
            if ":" in x_payment_hash:
                _, tx_hash = x_payment_hash.split(":", 1)
            else:
                tx_hash = x_payment_hash

        if not tx_hash:
            raise HTTPException(
                status_code=402,
                detail={
                    "x402Version": 1,
                    "error": "Transaction hash not found in payment headers",
                    "accepts": [self.payment_requirements.model_dump(mode='json')]
                }
            )

        # Normalize transaction hash
        tx_hash = tx_hash.strip()
        if not tx_hash.startswith("0x"):
            tx_hash = "0x" + tx_hash

        logger.info(f"Processing payment with tx_hash: {tx_hash}")

        # Build verification metadata
        metadata = {
            "source": "0xmeta_cryptonews_api",
            "resource": self.payment_requirements.resource
        }

        # Add full payment payload (CRITICAL for EIP-3009)
        if payment_payload_obj:
            metadata["paymentPayload"] = payment_payload_obj
            
            # Extract payer address
            try:
                payer = payment_payload_obj["payload"]["authorization"]["from"]
                metadata["payer"] = payer
                logger.info(f"Payer address: {payer}")
            except Exception as e:
                logger.warning(f"Could not extract payer: {e}")

        # Step 1: Verify payment with facilitator
        logger.info("🔍 Calling facilitator /v1/verify")
        
        verify_result = await facilitator_client.verify_payment(
            transaction_hash=tx_hash.lower(),
            chain=self.network,
            seller_address=self.payment_requirements.payTo.lower(),
            expected_amount=self.payment_requirements.maxAmountRequired,
            expected_token=self.payment_requirements.asset.lower(),
            metadata=metadata
        )

        if not verify_result.get("success"):
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

        # Extract verification ID
        verification_data = verify_result["data"]
        verification_id = (
            verification_data.get("verification_id") or
            verification_data.get("id") or
            verification_data.get("verificationId")
        )

        if not verification_id:
            logger.warning("⚠️  No verification_id from facilitator, skipping settlement")
            return True, self.payment_requirements

        # Step 2: Settle payment with facilitator
        logger.info(f"💰 Calling facilitator /v1/settle with verification_id: {verification_id}")
        
        settle_result = await facilitator_client.settle_payment(
            verification_id=verification_id,
            destination_address=self.payment_requirements.payTo.lower(),
            metadata={"source": "0xmeta_cryptonews_api"}
        )

        if not settle_result.get("success"):
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
        logger.info("💵 Merchant will receive their share via atomic split")
        
        return True, self.payment_requirements