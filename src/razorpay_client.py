"""
Razorpay Test Mode API Client Wrapper
Encapsulates all interactions with the Razorpay API SDK with:
- Robust retry with exponential backoff (2-3 attempts)
- System-level exception wrapping (returns structured system_error instead of crashing)
- Realistic Test-Mode Mock Fallback when sandbox API credentials are not yet supplied
"""

import os
import time
import logging
import random
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

try:
    import razorpay
    RAZORPAY_AVAILABLE = True
except ImportError:
    RAZORPAY_AVAILABLE = False
    logger.warning("razorpay package not installed. Operating in simulation mode.")


class RazorpayRecoveryClient:
    """
    Manages payment recovery actions against Razorpay Test Mode API.
    """

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        max_retries: int = 3
    ):
        self.key_id = key_id or os.getenv("RAZORPAY_KEY_ID", "rzp_test_placeholder")
        self.key_secret = key_secret or os.getenv("RAZORPAY_KEY_SECRET", "secret_placeholder")
        self.max_retries = max_retries
        self.is_live_test_mode = (
            RAZORPAY_AVAILABLE and
            self.key_id.startswith("rzp_test_") and
            self.key_secret != "YourTestKeySecretHere" and
            self.key_secret != "secret_placeholder"
        )

        self.client = None
        if self.is_live_test_mode:
            try:
                self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
                logger.info("Initialized live Razorpay Test Mode Client.")
            except Exception as e:
                logger.error(f"Failed to initialize Razorpay SDK client: {e}")
                self.is_live_test_mode = False

    def create_recovery_payment_link(
        self,
        amount_inr: float,
        customer_id: str,
        customer_name: str,
        customer_email: str,
        customer_contact: str,
        reference_payment_id: str,
        description: str = "Payment Recovery - Complete your transaction"
    ) -> Dict[str, Any]:
        """
        Creates an official Razorpay Payment Link (fully automated via API).
        Converts INR to Paise (e.g. ₹500 -> 50000 paise).
        """
        amount_paise = int(amount_inr * 100)
        payload = {
            "amount": amount_paise,
            "currency": "INR",
            "accept_partial": False,
            "description": description,
            "customer": {
                "name": customer_name,
                "email": customer_email,
                "contact": customer_contact
            },
            "notify": {
                "sms": True,
                "email": True
            },
            "reminder_enable": True,
            "notes": {
                "recovery_agent": "RazorpayRevenueRecoveryAgent_v1",
                "original_payment_id": reference_payment_id,
                "customer_id": customer_id
            },
            "callback_url": "https://example.com/payment-complete",
            "callback_method": "get"
        }

        # Real Live API Call with Retry Loop
        if self.is_live_test_mode and self.client:
            attempt = 0
            while attempt < self.max_retries:
                try:
                    logger.info(f"Dispatching Razorpay Payment Link API call (Attempt {attempt+1})...")
                    res = self.client.payment_link.create(payload)
                    return {
                        "status": "success",
                        "mode": "live_api",
                        "payment_link_id": res.get("id"),
                        "short_url": res.get("short_url"),
                        "amount_inr": amount_inr,
                        "raw_response": res
                    }
                except Exception as e:
                    attempt += 1
                    backoff = 0.5 * (2 ** (attempt - 1))
                    logger.warning(f"Razorpay API attempt {attempt} failed: {e}. Retrying in {backoff}s...")
                    time.sleep(backoff)
            
            # System error logging (Loophole 5 fix)
            return {
                "status": "system_error",
                "mode": "live_api",
                "error": f"Razorpay API timed out or returned error after {self.max_retries} attempts."
            }

        # High-Fidelity Test Mode Sandbox Simulation
        simulated_link_id = f"plink_test_{random.randint(10000000, 99999999)}"
        simulated_url = f"https://rzp.io/i/{simulated_link_id}"
        
        return {
            "status": "success",
            "mode": "sandbox_simulated",
            "payment_link_id": simulated_link_id,
            "short_url": simulated_url,
            "amount_inr": amount_inr,
            "raw_response": {
                "id": simulated_link_id,
                "amount": amount_paise,
                "currency": "INR",
                "short_url": simulated_url,
                "status": "created"
            }
        }

    def simulate_subscription_charge(
        self,
        subscription_id: str,
        reference_payment_id: str
    ) -> Dict[str, Any]:
        """
        Simulates subscription retry. As noted in Loophole 1:
        Razorpay test mode exposes subscription charge outcomes via dashboard toggle.
        We report this step transparently.
        """
        return {
            "status": "pending_manual_toggle_or_webhook",
            "mode": "sandbox_subscription_simulation",
            "subscription_id": subscription_id,
            "original_payment_id": reference_payment_id,
            "note": "Subscription charge trigger registered. Awaiting webhook or dashboard test-charge toggle."
        }
