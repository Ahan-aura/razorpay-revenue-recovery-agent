"""
End-to-End Orchestration Pipeline for Failed Payment Recovery Agent
Orchestrates data ingestion, LLM classification, policy gating, Razorpay actions,
audit logging, and metric computation.
"""

import os
import sys
import argparse
import logging
import pandas as pd
from typing import Dict, Any, Optional

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.classifier import FailureClassifier
from src.policy_engine import PolicyEngine
from src.razorpay_client import RazorpayRecoveryClient
from src.message_generator import MessageGenerator
from src.audit_log import AuditLogger
from src.metrics import MetricsCalculator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("RecoveryPipeline")


class RecoveryAgentPipeline:
    """
    Coordinates the full recovery lifecycle for failed payments.
    """

    def __init__(
        self,
        llm_provider: Optional[str] = None,
        confidence_threshold: float = 0.70,
        output_dir: Optional[str] = None,
        data_dir: Optional[str] = None
    ):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = data_dir or os.path.join(base_dir, "data")
        self.output_dir = output_dir or os.path.join(base_dir, "outputs")

        self.classifier = FailureClassifier(provider=llm_provider)
        self.policy_engine = PolicyEngine(confidence_threshold=confidence_threshold)
        self.razorpay_client = RazorpayRecoveryClient()
        self.message_generator = MessageGenerator()
        self.audit_logger = AuditLogger(output_dir=self.output_dir)
        self.metrics_calculator = MetricsCalculator(outputs_dir=self.output_dir, data_dir=self.data_dir)

    def process_single_payment(self, payment_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the full recovery cycle for an individual failed payment event.
        """
        payment_id = payment_event.get("payment_id")
        audit_history = self.audit_logger.load_all_records()

        # Step 1: LLM Classification
        classification = self.classifier.classify_failure(payment_event)

        # Step 2: Policy & Safety Gate Evaluation
        policy_decision = self.policy_engine.evaluate_policy(
            payment_event=payment_event,
            classification_result=classification,
            audit_history=audit_history
        )

        execution_result = None
        messaging_result = None
        verification = "simulated"
        outcome = None

        # Step 3: Action Execution (if allowed by policy)
        if policy_decision.should_execute_api:
            # Action: Create Payment Link or Subscription simulation
            if policy_decision.action in ["create_payment_link", "retry_payment_link", "schedule_delayed_retry"]:
                execution_result = self.razorpay_client.create_recovery_payment_link(
                    amount_inr=float(payment_event.get("amount", 0)),
                    customer_id=payment_event.get("customer_id", "CUST_UNKNOWN"),
                    customer_name=payment_event.get("customer_name", "Valued Customer"),
                    customer_email=payment_event.get("customer_email", "user@example.com"),
                    customer_contact=payment_event.get("customer_contact", "+919800000000"),
                    reference_payment_id=payment_id,
                    description=f"Payment Recovery for {payment_id} ({classification.get('failure_type')})"
                )

                # Step 4: Generate contextual customer recovery message
                payment_link_url = execution_result.get("short_url")
                messaging_result = self.message_generator.generate_message(
                    customer_name=payment_event.get("customer_name", "Customer"),
                    amount=float(payment_event.get("amount", 0)),
                    failure_type=classification.get("failure_type"),
                    payment_link_url=payment_link_url,
                    language="english"
                )

                if execution_result.get("status") == "system_error":
                    outcome = "system_error"
                else:
                    outcome = "action_dispatched"
                    verification = "live_verified" if execution_result.get("mode") == "live_api" else "simulated"

        # Step 5: Log structured audit trail entry
        audit_entry = self.audit_logger.record_action(
            payment_event=payment_event,
            classification=classification,
            policy_decision=policy_decision.to_dict(),
            execution_result=execution_result,
            messaging_result=messaging_result,
            verification=verification,
            outcome=outcome
        )

        return audit_entry

    def run_batch(self, dataset_path: Optional[str] = None, limit: Optional[int] = None, reset_logs: bool = False) -> Dict[str, Any]:
        """
        Runs the full batch of failed payments through the recovery agent.
        """
        if reset_logs:
            self.audit_logger.clear_logs()

        target_file = dataset_path or os.path.join(self.data_dir, "synthetic_failures.csv")
        if not os.path.exists(target_file):
            raise FileNotFoundError(f"Dataset file not found: {target_file}")

        df = pd.read_csv(target_file)
        if limit:
            df = df.head(limit)

        records = df.to_dict(orient="records")
        logger.info(f"Starting batch recovery execution on {len(records)} failed payments...")

        processed_entries = []
        for idx, event in enumerate(records, start=1):
            entry = self.process_single_payment(event)
            processed_entries.append(entry)
            if idx % 20 == 0 or idx == len(records):
                logger.info(f"Processed {idx}/{len(records)} payments...")

        # Step 6: Compute performance metrics
        all_audit_logs = self.audit_logger.load_all_records()
        metrics = self.metrics_calculator.compute_metrics(all_audit_logs)

        # Step 7: Benchmark accuracy against held-out set
        benchmark_eval = self.metrics_calculator.evaluate_benchmark_accuracy(self.classifier)

        logger.info("Batch execution completed successfully.")
        return {
            "total_processed": len(processed_entries),
            "metrics": metrics,
            "benchmark_accuracy": benchmark_eval
        }


def main():
    parser = argparse.ArgumentParser(description="Razorpay Revenue Recovery Agent")
    parser.add_argument("--dataset", type=str, default=None, help="Path to input dataset CSV")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of rows to process")
    parser.add_argument("--reset-logs", action="store_true", help="Clear audit logs before running")
    parser.add_argument("--provider", type=str, default=None, help="LLM Provider: gemini, anthropic, or mock")
    args = parser.parse_args()

    pipeline = RecoveryAgentPipeline(llm_provider=args.provider)
    results = pipeline.run_batch(
        dataset_path=args.dataset,
        limit=args.limit,
        reset_logs=args.reset_logs
    )

    print("\n========================================================")
    print("      RAZORPAY RECOVERY AGENT — BATCH SUMMARY")
    print("========================================================")
    m = results["metrics"]
    print(f"Total Failed Volume:      Rs. {m['total_failed_volume_inr']:,.2f} ({m['total_records']} payments)")
    print(f"Total Recovered Volume:   Rs. {m['total_recovered_volume_inr']:,.2f}")
    print(f"Overall Recovery Rate:    {m['overall_recovery_rate_pct']}%")
    print(f" -> Live-Verified:        Rs. {m['live_verified']['amount_inr']:,.2f} ({m['live_verified']['count']} payments)")
    print(f" -> Simulated Recovery:   Rs. {m['simulated_recovery']['amount_inr']:,.2f} ({m['simulated_recovery']['count']} payments)")
    print(f"Total Escalated Cases:    {m['escalations']['total']} (Fraud: {m['escalations']['fraud_blocked']}, Low Conf: {m['escalations']['low_confidence_review']}, Max Retries: {m['escalations']['max_retries_exceeded']})")
    print(f"Opt-Out Suppressed:       {m['opt_out_suppressed_count']}")
    print(f"System Errors / Crashes:  {m['system_errors_count']}")
    
    b = results["benchmark_accuracy"]
    print(f"\nClassification Accuracy on Benchmark: {b.get('accuracy_pct', 0)}% (Sample: {b.get('sample_size')} hand-labeled rows)")
    print("========================================================\n")


if __name__ == "__main__":
    main()
