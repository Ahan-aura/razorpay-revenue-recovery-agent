"""
Metrics and Performance Evaluation Layer
Computes revenue recovery rates, actions dispatched, and maintains strict separation
between Dispatched Recovery Actions, Live-Verified Webhooks, and Demo Simulations.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """
    Analyzes audit logs and benchmark datasets to compute transparent KPIs.
    """

    def __init__(self, outputs_dir: Optional[str] = None, data_dir: Optional[str] = None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.outputs_dir = outputs_dir or os.path.join(base_dir, "outputs")
        self.data_dir = data_dir or os.path.join(base_dir, "data")
        self.metrics_file_path = os.path.join(self.outputs_dir, "metrics_summary.json")

    def compute_metrics(self, audit_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates comprehensive, transparent summary metrics from audit log entries.
        Never conflates 'payment link created' with 'cash collected'.
        """
        if not audit_records:
            return {
                "total_records": 0,
                "total_failed_volume_inr": 0,
                "actions_dispatched": {"count": 0, "amount_inr": 0, "dispatch_rate_pct": 0.0},
                "live_verified_recoveries": {"count": 0, "amount_inr": 0, "recovery_rate_pct": 0.0},
                "demo_verified_recoveries": {"count": 0, "amount_inr": 0},
                "unconfirmed_dispatched_links": {"count": 0, "amount_inr": 0},
                "escalations": {"total": 0, "fraud_blocked": 0, "low_confidence_review": 0, "max_retries_exceeded": 0},
                "opt_out_suppressed_count": 0,
                "system_errors_count": 0,
                "breakdown_by_failure_type": {}
            }

        total_records = len(audit_records)
        total_failed_volume = sum(r.get("amount", 0) for r in audit_records)

        # 1. Actions Dispatched (Payment links created / scheduled retries)
        dispatched_records = [
            r for r in audit_records
            if r.get("outcome") in ["action_dispatched", "recovered"]
        ]
        dispatched_amount = sum(r.get("amount", 0) for r in dispatched_records)
        dispatch_rate_pct = (dispatched_amount / total_failed_volume * 100) if total_failed_volume > 0 else 0.0

        # 2. Live-Verified Recoveries (Cryptographically confirmed via real Razorpay Webhook)
        live_verified_records = [
            r for r in audit_records
            if r.get("verification") == "live_verified" and r.get("outcome") == "recovered"
        ]
        live_verified_amount = sum(r.get("amount", 0) for r in live_verified_records)
        live_recovery_rate_pct = (live_verified_amount / total_failed_volume * 100) if total_failed_volume > 0 else 0.0

        # 3. Demo-Verified Recoveries (Confirmed via /simulate-webhook demo endpoint)
        demo_verified_records = [
            r for r in audit_records
            if r.get("verification") == "demo_verified" and r.get("outcome") == "recovered"
        ]
        demo_verified_amount = sum(r.get("amount", 0) for r in demo_verified_records)

        # 4. Dispatched Links Awaiting Webhook Confirmation
        pending_records = [
            r for r in audit_records
            if r.get("outcome") == "action_dispatched" and r.get("verification") in ["simulated", "dispatched_pending"]
        ]
        pending_amount = sum(r.get("amount", 0) for r in pending_records)

        # 5. Escalations & Guardrails
        fraud_escalations = [r for r in audit_records if r.get("rule_fired") == "RULE_2_FRAUD_BLOCK"]
        low_confidence_escalations = [r for r in audit_records if r.get("rule_fired") == "RULE_3_LOW_CONFIDENCE_GATE"]
        max_retries_escalations = [r for r in audit_records if r.get("rule_fired") == "RULE_4_MAX_RETRIES"]
        opt_out_suppressed = [r for r in audit_records if r.get("rule_fired") == "RULE_1_CONSENT_OPT_OUT"]
        system_errors = [r for r in audit_records if r.get("outcome") == "system_error"]

        # Failure Type Breakdown
        type_breakdown = {}
        for r in audit_records:
            f_type = r.get("classified_failure_type", "unknown")
            if f_type not in type_breakdown:
                type_breakdown[f_type] = {"count": 0, "amount_inr": 0, "action": r.get("action_taken")}
            type_breakdown[f_type]["count"] += 1
            type_breakdown[f_type]["amount_inr"] += r.get("amount", 0)

        summary = {
            "total_records": total_records,
            "total_failed_volume_inr": round(total_failed_volume, 2),
            
            # Action Pipeline Metric
            "actions_dispatched": {
                "count": len(dispatched_records),
                "amount_inr": round(dispatched_amount, 2),
                "dispatch_rate_pct": round(dispatch_rate_pct, 2),
                "description": "Total payment links generated and recovery workflows dispatched"
            },
            
            # Real Verified Metric (Razorpay Webhook)
            "live_verified_recoveries": {
                "count": len(live_verified_records),
                "amount_inr": round(live_verified_amount, 2),
                "recovery_rate_pct": round(live_recovery_rate_pct, 2),
                "description": "Actual rupees confirmed collected via cryptographic HMAC-SHA256 Razorpay webhook"
            },

            # Demo Verified Metric (Local Simulation)
            "demo_verified_recoveries": {
                "count": len(demo_verified_records),
                "amount_inr": round(demo_verified_amount, 2),
                "description": "Transactions verified via local demo webhook trigger"
            },

            # Unconfirmed / Pending Customer Checkout
            "unconfirmed_dispatched_links": {
                "count": len(pending_records),
                "amount_inr": round(pending_amount, 2),
                "description": "Dispatched recovery links awaiting customer payment completion"
            },

            # Governance & Escalations
            "escalations": {
                "total": len(fraud_escalations) + len(low_confidence_escalations) + len(max_retries_escalations),
                "fraud_blocked": len(fraud_escalations),
                "low_confidence_review": len(low_confidence_escalations),
                "max_retries_exceeded": len(max_retries_escalations)
            },
            "opt_out_suppressed_count": len(opt_out_suppressed),
            "system_errors_count": len(system_errors),
            "breakdown_by_failure_type": type_breakdown
        }

        os.makedirs(self.outputs_dir, exist_ok=True)
        with open(self.metrics_file_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary

    def evaluate_benchmark_accuracy(self, classifier) -> Dict[str, Any]:
        """
        Evaluates classifier performance against the 20-row hand-labeled benchmark set.
        Explicitly reports the engine used (LLM vs Deterministic Fallback) to prevent circular grading claims.
        """
        benchmark_path = os.path.join(self.data_dir, "ground_truth_labels.csv")
        if not os.path.exists(benchmark_path):
            logger.warning(f"Benchmark file {benchmark_path} not found.")
            return {"error": "Benchmark dataset not found"}

        df = pd.read_csv(benchmark_path)
        total_samples = len(df)
        correct_predictions = 0
        predictions_log = []

        class_stats = {}
        engine_used_log = set()

        for _, row in df.iterrows():
            event = row.to_dict()
            ground_truth = event.get("ground_truth_category")
            
            pred = classifier.classify_failure(event)
            predicted_type = pred.get("failure_type")
            engine_name = pred.get("engine_used", "unknown")
            engine_used_log.add(engine_name)
            
            is_correct = (predicted_type == ground_truth)
            if is_correct:
                correct_predictions += 1

            if ground_truth not in class_stats:
                class_stats[ground_truth] = {"total": 0, "correct": 0}
            class_stats[ground_truth]["total"] += 1
            if is_correct:
                class_stats[ground_truth]["correct"] += 1

            predictions_log.append({
                "payment_id": event.get("payment_id"),
                "ground_truth": ground_truth,
                "predicted": predicted_type,
                "confidence": pred.get("confidence"),
                "is_correct": is_correct,
                "engine_used": engine_name,
                "reasoning": pred.get("reasoning")
            })

        accuracy_pct = (correct_predictions / total_samples * 100) if total_samples > 0 else 0.0
        primary_engine = list(engine_used_log)[0] if len(engine_used_log) == 1 else "mixed"

        if "baseline" in primary_engine:
            evaluation_type_note = "Evaluated using Deterministic Keyword & Error-Code Baseline Classifier (Offline Fallback mode, no LLM API key loaded)."
        else:
            evaluation_type_note = f"Evaluated using Live Semantic LLM Inferences ({primary_engine})."

        benchmark_results = {
            "engine_evaluated": primary_engine,
            "evaluation_type_note": evaluation_type_note,
            "sample_size": total_samples,
            "sample_size_note": "Evaluated on hand-labeled held-out test partition (20 rows)",
            "accuracy_pct": round(accuracy_pct, 2),
            "correct_count": correct_predictions,
            "total_count": total_samples,
            "per_class_accuracy": {
                k: round(v["correct"] / v["total"] * 100, 1) for k, v in class_stats.items()
            },
            "detailed_predictions": predictions_log
        }

        bench_out_path = os.path.join(self.outputs_dir, "benchmark_evaluation.json")
        with open(bench_out_path, "w", encoding="utf-8") as f:
            json.dump(benchmark_results, f, indent=2)

        return benchmark_results
