"""
Deterministic Policy and Decision Engine for Razorpay Payment Recovery
Applies auditable business rules, safety thresholds, stopping conditions,
and regulatory compliance guardrails.

CRITICAL DESIGN RULE: The LLM is strictly confined to classification.
All money-moving actions and stopping gates are 100% deterministic code.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Constants & Guardrails
CONFIDENCE_THRESHOLD = 0.70
MAX_ALLOWED_RETRIES = 3
MIN_RETRY_INTERVAL_HOURS = 24


class PolicyDecision:
    """Structured container for policy outcome."""
    def __init__(
        self,
        action: str,
        should_execute_api: bool,
        rule_fired: str,
        reason: str,
        delay_hours: int = 0,
        requires_human_review: bool = False,
        escalation_reason: Optional[str] = None
    ):
        self.action = action
        self.should_execute_api = should_execute_api
        self.rule_fired = rule_fired
        self.reason = reason
        self.delay_hours = delay_hours
        self.requires_human_review = requires_human_review
        self.escalation_reason = escalation_reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "should_execute_api": self.should_execute_api,
            "rule_fired": self.rule_fired,
            "reason": self.reason,
            "delay_hours": self.delay_hours,
            "requires_human_review": self.requires_human_review,
            "escalation_reason": self.escalation_reason
        }


class PolicyEngine:
    """
    Evaluates classified failure events against merchant and compliance rules.
    """

    def __init__(self, confidence_threshold: float = CONFIDENCE_THRESHOLD):
        self.confidence_threshold = confidence_threshold

    def evaluate_policy(
        self,
        payment_event: Dict[str, Any],
        classification_result: Dict[str, Any],
        audit_history: Optional[list] = None
    ) -> PolicyDecision:
        """
        Evaluates a payment event and classification to determine the recovery action.
        Follows a strict hierarchy of safety checks before action dispatch.
        """
        payment_id = payment_event.get("payment_id", "UNKNOWN")
        retry_count = int(payment_event.get("retry_count", 0))
        opt_out = bool(payment_event.get("opt_out", False))
        failure_type = classification_result.get("failure_type", "technical_error")
        confidence = float(classification_result.get("confidence", 0.0))

        # GATE 0: Idempotency Check (Loophole 4 Fix)
        if audit_history:
            for entry in audit_history:
                if entry.get("payment_id") == payment_id and entry.get("outcome") in ["recovered", "action_dispatched", "pending_webhook"]:
                    return PolicyDecision(
                        action="skip_idempotent",
                        should_execute_api=False,
                        rule_fired="RULE_0_IDEMPOTENCY",
                        reason=f"Payment ID {payment_id} already has active/completed recovery action.",
                        requires_human_review=False
                    )

        # GATE 1: Customer Consent & Opt-Out Guardrail (Loophole 8 Fix)
        if opt_out:
            return PolicyDecision(
                action="suppress_opt_out",
                should_execute_api=False,
                rule_fired="RULE_1_CONSENT_OPT_OUT",
                reason="Customer has opted out of outbound transaction recovery notifications.",
                requires_human_review=False
            )

        # GATE 2: Fraud & Risk Escalation (Zero auto-retry)
        if failure_type == "fraud_suspected":
            return PolicyDecision(
                action="escalate_fraud_review",
                should_execute_api=False,
                rule_fired="RULE_2_FRAUD_BLOCK",
                reason="High risk or suspicious activity detected. Immediate human security escalation.",
                requires_human_review=True,
                escalation_reason="Suspected fraudulent pattern or risk engine rejection."
            )

        # GATE 3: Confidence Gate (Loophole 3 Fix)
        if confidence < self.confidence_threshold:
            return PolicyDecision(
                action="manual_review",
                should_execute_api=False,
                rule_fired="RULE_3_LOW_CONFIDENCE_GATE",
                reason=f"LLM classification confidence {confidence:.2f} is below safety threshold ({self.confidence_threshold}).",
                requires_human_review=True,
                escalation_reason=f"Ambiguous failure reason (confidence {confidence:.2f} < {self.confidence_threshold})"
            )

        # GATE 4: Stopping Rule — Max Retry Limit (Loophole 6 Policy)
        if retry_count >= MAX_ALLOWED_RETRIES:
            return PolicyDecision(
                action="stop_max_retries_reached",
                should_execute_api=False,
                rule_fired="RULE_4_MAX_RETRIES",
                reason=f"Maximum allowed retries ({MAX_ALLOWED_RETRIES}) reached. Halting automated attempts.",
                requires_human_review=True,
                escalation_reason="Exceeded maximum automatic retry attempts."
            )

        # GATE 5: Dynamic Recovery Routing per Failure Category
        if failure_type == "insufficient_funds":
            # Heuristic: Delay retry by 72 hours (3 days) to align with salary or account replenishment cycles
            return PolicyDecision(
                action="schedule_delayed_retry",
                should_execute_api=True,
                rule_fired="RULE_5A_INSUFFICIENT_FUNDS_SALARY_CYCLE",
                reason="Insufficient balance detected. Scheduled retry with 72h cooldown for fund replenishment.",
                delay_hours=72
            )

        elif failure_type == "expired_card":
            # For expired cards, debit retries will always fail -> Send Payment Link for alternative card/UPI
            return PolicyDecision(
                action="create_payment_link",
                should_execute_api=True,
                rule_fired="RULE_5B_EXPIRED_CARD_PAYMENT_LINK",
                reason="Card validity expired. Automated payment link generation for customer payment update.",
                delay_hours=0
            )

        elif failure_type == "mandate_declined":
            # Recurring mandate revoked or limit exceeded -> Generate new payment / mandate update link
            return PolicyDecision(
                action="create_payment_link",
                should_execute_api=True,
                rule_fired="RULE_5C_MANDATE_DECLINED_REAUTH",
                reason="E-mandate declined by bank. Dispatched new payment link for re-authorization.",
                delay_hours=0
            )

        elif failure_type == "bank_timeout":
            # Ephemeral bank gateway latency -> Retry immediately (single attempt)
            return PolicyDecision(
                action="retry_payment_link",
                should_execute_api=True,
                rule_fired="RULE_5D_BANK_TIMEOUT_IMMEDIATE_RETRY",
                reason="Issuer bank timeout detected. Instant retry via fresh payment link or gateway retry.",
                delay_hours=0
            )

        elif failure_type == "technical_error":
            # Transient gateway 5xx error -> Retry immediately
            return PolicyDecision(
                action="retry_payment_link",
                should_execute_api=True,
                rule_fired="RULE_5E_TECH_ERROR_IMMEDIATE_RETRY",
                reason="Transient switch error detected. Instant retry via fallback route.",
                delay_hours=0
            )

        # Default fallback
        return PolicyDecision(
            action="manual_review",
            should_execute_api=False,
            rule_fired="RULE_DEFAULT_FALLBACK",
            reason="Unrecognized scenario routed to operations team.",
            requires_human_review=True,
            escalation_reason="Unhandled failure pattern."
        )
