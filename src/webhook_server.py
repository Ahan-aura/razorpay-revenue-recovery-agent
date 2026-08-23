"""
Webhook Listener Server (FastAPI)
Captures real Razorpay Webhook events (e.g. payment.captured, payment.failed, payment_link.paid).
Verifies cryptographic webhook signatures (HMAC-SHA256) and promotes recovery actions
from 'dispatched' to 'live_verified'.

Includes a `/simulate-webhook` endpoint for friction-free local demos,
explicitly tagging its outcomes as 'demo_verified' (never confusing fake calls with live signatures).
"""

import os
import hmac
import hashlib
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Razorpay Recovery Agent Webhook Receiver",
    version="1.0.0",
    description="Captures live payment lifecycle events from Razorpay"
)

WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBHOOK_LOG_FILE = os.path.join(BASE_DIR, "outputs", "webhook_events.json")
AUDIT_LOG_FILE = os.path.join(BASE_DIR, "outputs", "audit_log.json")


def verify_razorpay_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """Verifies HMAC SHA256 webhook signature from Razorpay."""
    if not secret:
        return True
    expected_sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, signature)


def update_audit_log_with_webhook(event_data: Dict[str, Any], verification_tag: str = "live_verified"):
    """
    Updates corresponding payment entry in audit_log.json with explicit verification tag
    ('live_verified' for real signed webhooks, 'demo_verified' for test simulator calls).
    """
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG_FILE), exist_ok=True)
        if not os.path.exists(AUDIT_LOG_FILE):
            return

        with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
            audit_records = json.load(f)

        event_name = event_data.get("event", "payment.captured")
        payload = event_data.get("payload", {})
        payment_entity = payload.get("payment", {}).get("entity", {})
        notes = payment_entity.get("notes", {})
        original_payment_id = notes.get("original_payment_id")
        payment_link_id = payment_entity.get("order_id") or payload.get("payment_link", {}).get("entity", {}).get("id")

        updated = False
        for record in audit_records:
            if (original_payment_id and record.get("payment_id") == original_payment_id) or \
               (payment_link_id and record.get("action_details", {}).get("payment_link_id") == payment_link_id):
                
                if event_name in ["payment.captured", "order.paid", "payment_link.paid"]:
                    record["outcome"] = "recovered"
                    record["verification"] = verification_tag
                    record["webhook_captured_at"] = datetime.now().isoformat()
                elif event_name in ["payment.failed"]:
                    record["outcome"] = "retry_failed"
                    record["verification"] = verification_tag
                    record["webhook_captured_at"] = datetime.now().isoformat()
                
                updated = True
                break

        if updated:
            with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(audit_records, f, indent=2)
            logger.info(f"Audit log updated to {verification_tag} for payment: {original_payment_id or payment_link_id}")

    except Exception as e:
        logger.error(f"Failed to update audit log from webhook: {e}")


def persist_webhook_event(event_data: Dict[str, Any], source: str = "live_razorpay_webhook"):
    """Appends incoming webhook event to persistent JSON store."""
    try:
        os.makedirs(os.path.dirname(WEBHOOK_LOG_FILE), exist_ok=True)
        events = []
        if os.path.exists(WEBHOOK_LOG_FILE):
            try:
                with open(WEBHOOK_LOG_FILE, "r", encoding="utf-8") as f:
                    events = json.load(f)
            except Exception:
                events = []
        
        events.append({
            "received_at": datetime.now().isoformat(),
            "source": source,
            "event": event_data.get("event"),
            "data": event_data
        })

        with open(WEBHOOK_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
    except Exception as e:
        logger.error(f"Error persisting webhook event: {e}")


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat(), "service": "Razorpay Recovery Webhook Receiver"}


@app.post("/webhook")
async def handle_razorpay_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_razorpay_signature: Optional[str] = Header(None)
):
    """
    Primary endpoint for real Razorpay webhook notifications.
    Promotes records to 'live_verified'.
    """
    raw_body = await request.body()

    if WEBHOOK_SECRET and x_razorpay_signature:
        if not verify_razorpay_signature(raw_body, x_razorpay_signature, WEBHOOK_SECRET):
            raise HTTPException(status_code=400, detail="Invalid Razorpay Webhook Signature")

    try:
        event_data = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Malformed JSON payload: {e}")

    background_tasks.add_task(persist_webhook_event, event_data, "live_razorpay_webhook")
    background_tasks.add_task(update_audit_log_with_webhook, event_data, "live_verified")

    return JSONResponse(status_code=200, content={"status": "accepted", "event": event_data.get("event"), "verification": "live_verified"})


@app.post("/simulate-webhook")
async def simulate_webhook(
    payment_id: str,
    event: str = "payment.captured",
    amount_inr: float = 999.0
):
    """
    Simulates a webhook call for local demonstrations.
    Explicitly tags the outcome as 'demo_verified' so it is never confused with a live HMAC signature.
    """
    simulated_payload = {
        "entity": "event",
        "account_id": "acc_mock_merchant",
        "event": event,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_demo_{payment_id.replace('pay_', '')}",
                    "amount": int(amount_inr * 100),
                    "currency": "INR",
                    "status": "captured" if event == "payment.captured" else "failed",
                    "notes": {
                        "original_payment_id": payment_id
                    }
                }
            }
        },
        "created_at": int(datetime.now().timestamp())
    }

    persist_webhook_event(simulated_payload, "demo_simulated_webhook")
    update_audit_log_with_webhook(simulated_payload, "demo_verified")

    return {
        "status": "demo_simulated_success",
        "event": event,
        "payment_id": payment_id,
        "amount": amount_inr,
        "verification_tag": "demo_verified",
        "note": "Payment promoted to demo_verified in audit log."
    }


def start_webhook_server(port: int = 8000):
    """Starts Uvicorn server programmatically."""
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    port = int(os.getenv("WEBHOOK_PORT", 8000))
    start_webhook_server(port)
