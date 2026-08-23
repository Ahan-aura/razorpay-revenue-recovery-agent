"""
Unit Tests for Policy and Decision Engine
Verifies that all safety gates, stopping rules, confidence thresholds,
and idempotency checks behave deterministically.
"""

import pytest
from src.policy_engine import PolicyEngine, CONFIDENCE_THRESHOLD, MAX_ALLOWED_RETRIES


@pytest.fixture
def engine():
    return PolicyEngine()


def test_idempotency_gate(engine):
    """Test that already-acted-upon payments are skipped."""
    payment_event = {"payment_id": "pay_test_001", "retry_count": 0, "opt_out": False}
    classification = {"failure_type": "expired_card", "confidence": 0.95}
    audit_history = [{"payment_id": "pay_test_001", "outcome": "action_dispatched"}]

    decision = engine.evaluate_policy(payment_event, classification, audit_history)
    assert decision.action == "skip_idempotent"
    assert decision.should_execute_api is False
    assert decision.rule_fired == "RULE_0_IDEMPOTENCY"


def test_customer_opt_out_gate(engine):
    """Test that customers who opted out are not spammed or auto-debited."""
    payment_event = {"payment_id": "pay_test_002", "retry_count": 0, "opt_out": True}
    classification = {"failure_type": "expired_card", "confidence": 0.95}

    decision = engine.evaluate_policy(payment_event, classification)
    assert decision.action == "suppress_opt_out"
    assert decision.should_execute_api is False
    assert decision.rule_fired == "RULE_1_CONSENT_OPT_OUT"


def test_fraud_escalation_gate(engine):
    """Test that suspected fraud immediately triggers human review without automated retries."""
    payment_event = {"payment_id": "pay_test_003", "retry_count": 0, "opt_out": False}
    classification = {"failure_type": "fraud_suspected", "confidence": 0.98}

    decision = engine.evaluate_policy(payment_event, classification)
    assert decision.action == "escalate_fraud_review"
    assert decision.should_execute_api is False
    assert decision.requires_human_review is True
    assert decision.rule_fired == "RULE_2_FRAUD_BLOCK"


def test_low_confidence_gate(engine):
    """Test that confidence below threshold (0.70) is routed to manual review."""
    payment_event = {"payment_id": "pay_test_004", "retry_count": 0, "opt_out": False}
    classification = {"failure_type": "expired_card", "confidence": 0.55}

    decision = engine.evaluate_policy(payment_event, classification)
    assert decision.action == "manual_review"
    assert decision.should_execute_api is False
    assert decision.requires_human_review is True
    assert decision.rule_fired == "RULE_3_LOW_CONFIDENCE_GATE"


def test_max_retries_stopping_rule(engine):
    """Test that payments exceeding max retry threshold are stopped and escalated."""
    payment_event = {"payment_id": "pay_test_005", "retry_count": MAX_ALLOWED_RETRIES, "opt_out": False}
    classification = {"failure_type": "bank_timeout", "confidence": 0.95}

    decision = engine.evaluate_policy(payment_event, classification)
    assert decision.action == "stop_max_retries_reached"
    assert decision.should_execute_api is False
    assert decision.requires_human_review is True
    assert decision.rule_fired == "RULE_4_MAX_RETRIES"


def test_insufficient_funds_delay_policy(engine):
    """Test that insufficient funds schedules a 72-hour delay."""
    payment_event = {"payment_id": "pay_test_006", "retry_count": 0, "opt_out": False}
    classification = {"failure_type": "insufficient_funds", "confidence": 0.92}

    decision = engine.evaluate_policy(payment_event, classification)
    assert decision.action == "schedule_delayed_retry"
    assert decision.should_execute_api is True
    assert decision.delay_hours == 72
    assert decision.rule_fired == "RULE_5A_INSUFFICIENT_FUNDS_SALARY_CYCLE"


def test_expired_card_payment_link(engine):
    """Test that expired cards generate an instant payment link."""
    payment_event = {"payment_id": "pay_test_007", "retry_count": 0, "opt_out": False}
    classification = {"failure_type": "expired_card", "confidence": 0.94}

    decision = engine.evaluate_policy(payment_event, classification)
    assert decision.action == "create_payment_link"
    assert decision.should_execute_api is True
    assert decision.delay_hours == 0
    assert decision.rule_fired == "RULE_5B_EXPIRED_CARD_PAYMENT_LINK"
