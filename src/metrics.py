"""
Metrics and Performance Evaluation Layer
Computes revenue recovery rates, classification accuracy on benchmark data,
and honest breakdown of live-verified vs. simulated outcomes.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """
    Analyzes audit logs and benchmark datasets to compute key performance indicators.
    """

    def __init__(self, outputs_dir: Optional[str] = None, data_dir: Optional[str] = None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.outputs_dir = outputs_dir or os.path.join(base_dir, "outputs")
        self.data_dir = data_dir or os.path.join(base_dir, "data")
        self.metrics_file_path = os.path.join(self.outputs_dir, "metrics_summary.json")

    def compute_metrics(self, audit_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates comprehensive summary metrics from audit log entries.
        """
        if not audit_records:
            return {
                "total_records": 0,
                "total_failed_volume_inr": 0,
                "total_recovered_volume_inr": 0,
                "overall_recovery_rate_pct": 0.0,
                "live_verified": {"count": 0, "amount_inr": 0},
                "simulated_recovery": {"count": 0, "amount_inr": 0},
                "escalations": {"total": 0, "fraud": 0, "low_confidence": 0, "max_retries": 0},
                "opt_out_suppressed": 0,
                "system_errors": 0,
                "breakdown_by_failure_type": {}
            }

        total_records = len(audit_records)
        total_failed_volume = sum(r.get("amount", 0) for r in audit_records)

        live_verified_records = [r for r in audit_records if r.get("verification") == "live_verified" and r.get("outcome") == "recovered"]
        live_verified_amount = sum(r.get("amount", 0) for r in live_verified_records)

        simulated_records = [r for r in audit_records if r.get("outcome") in ["action_dispatched", "recovered"] and r.get("verification") == "simulated"]
        simulated_amount = sum(r.get("amount", 0) for r in simulated_records)

        total_recovered_volume = live_verified_amount + simulated_amount
        recovery_rate_pct = (total_recovered_volume / total_failed_volume * 100) if total_failed_volume > 0 else 0.0

        # Escalations breakdown
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
            "total_recovered_volume_inr": round(total_recovered_volume, 2),
            "overall_recovery_rate_pct": round(recovery_rate_pct, 2),
            
            # Honest Split (Loophole 2 fix)
            "live_verified": {
                "count": len(live_verified_records),
                "amount_inr": round(live_verified_amount, 2),
                "percentage_of_total": round((live_verified_amount / total_failed_volume * 100) if total_failed_volume else 0, 2)
            },
            "simulated_recovery": {
                "count": len(simulated_records),
                "amount_inr": round(simulated_amount, 2),
                "percentage_of_total": round((simulated_amount / total_failed_volume * 100) if total_failed_volume else 0, 2)
            },
            
            # Governance & Safety Gate Metrics
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

        # Save to outputs
        os.makedirs(self.outputs_dir, exist_ok=True)
        with open(self.metrics_file_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary

    def evaluate_benchmark_accuracy(self, classifier) -> Dict[str, Any]:
        """
        Evaluates classifier performance against the 20-row hand-labeled benchmark set.
        Returns accuracy, sample size disclaimer, and per-class breakdown.
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

        for _, row in df.iterrows():
            event = row.to_dict()
            ground_truth = event.get("ground_truth_category")
            
            # Predict using classifier
            pred = classifier.classify_failure(event)
            predicted_type = pred.get("failure_type")
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
                "reasoning": pred.get("reasoning")
            })

        accuracy_pct = (correct_predictions / total_samples * 100) if total_samples > 0 else 0.0

        benchmark_results = {
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

        # Save benchmark evaluation summary
        bench_out_path = os.path.join(self.outputs_dir, "benchmark_evaluation.json")
        with open(bench_out_path, "w", encoding="utf-8") as f:
            json.dump(benchmark_results, f, indent=2)

        return benchmark_results
