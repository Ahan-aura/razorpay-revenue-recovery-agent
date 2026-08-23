"""
Audit Log Manager for Razorpay Recovery Agent
Maintains an immutable, structured JSON audit log of every classification,
decision, API call, and webhook confirmation.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Handles logging, reading, and querying audit trail entries.
    """

    def __init__(self, output_dir: Optional[str] = None):
        if output_dir:
            self.output_dir = output_dir
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.output_dir = os.path.join(base_dir, "outputs")
        
        os.makedirs(self.output_dir, exist_ok=True)
        self.log_file_path = os.path.join(self.output_dir, "audit_log.json")
        self._init_file()

    def _init_file(self):
        """Initializes empty audit log file if non-existent."""
        if not os.path.exists(self.log_file_path):
            with open(self.log_file_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

    def load_all_records(self) -> List[Dict[str, Any]]:
        """Loads all logged records."""
        try:
            with open(self.log_file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading audit records: {e}")
            return []

    def record_action(
        self,
        payment_event: Dict[str, Any],
        classification: Dict[str, Any],
        policy_decision: Dict[str, Any],
        execution_result: Optional[Dict[str, Any]] = None,
        messaging_result: Optional[Dict[str, Any]] = None,
        verification: str = "simulated",
        outcome: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a structured audit log entry and appends it atomically.
        """
        records = self.load_all_records()
        
        # Determine final outcome label
        if not outcome:
            if policy_decision.get("requires_human_review"):
                outcome = "escalated"
            elif policy_decision.get("action") == "manual_review":
                outcome = "manual_review"
            elif policy_decision.get("action") == "suppress_opt_out":
                outcome = "opt_out_suppressed"
            elif policy_decision.get("action") == "skip_idempotent":
                outcome = "skipped_idempotent"
            elif execution_result and execution_result.get("status") == "system_error":
                outcome = "system_error"
            else:
                outcome = "action_dispatched"

        # Verification tag: live_verified, simulated, or not_applicable
        if outcome in ["escalated", "manual_review", "opt_out_suppressed", "skipped_idempotent"]:
            verification_tag = "not_applicable"
        else:
            verification_tag = verification

        entry = {
            "payment_id": payment_event.get("payment_id"),
            "customer_id": payment_event.get("customer_id"),
            "customer_name": payment_event.get("customer_name", "N/A"),
            "amount": float(payment_event.get("amount", 0)),
            "currency": payment_event.get("currency", "INR"),
            "payment_type": payment_event.get("payment_type", "one_time"),
            "failure_code": payment_event.get("failure_code"),
            "error_description": payment_event.get("error_description"),
            
            # Classification layer
            "classified_failure_type": classification.get("failure_type"),
            "confidence": round(float(classification.get("confidence", 0.0)), 3),
            "classification_reasoning": classification.get("reasoning"),
            
            # Policy decision layer
            "action_taken": policy_decision.get("action"),
            "rule_fired": policy_decision.get("rule_fired"),
            "policy_reason": policy_decision.get("reason"),
            "delay_hours": policy_decision.get("delay_hours", 0),
            "requires_human_review": policy_decision.get("requires_human_review", False),
            "escalation_reason": policy_decision.get("escalation_reason"),
            
            # Execution and verification layer
            "outcome": outcome,
            "verification": verification_tag,
            "action_details": execution_result or {},
            "customer_notification": messaging_result or {},
            "timestamp": datetime.now().isoformat()
        }

        # Update existing record if same payment_id, otherwise append
        existing_index = next((i for i, r in enumerate(records) if r.get("payment_id") == entry["payment_id"]), None)
        if existing_index is not None:
            records[existing_index] = entry
        else:
            records.append(entry)

        with open(self.log_file_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

        return entry

    def clear_logs(self):
        """Clears all audit records (for fresh batch evaluation)."""
        with open(self.log_file_path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
