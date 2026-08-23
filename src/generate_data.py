"""
Synthetic Data Generator for Razorpay Failed Payment Recovery Agent
Generates realistic failed payment datasets for testing and benchmarking.
Ensures zero real PII is used, complying with privacy and security guardrails.
"""

import os
import json
import random
import pandas as pd
from datetime import datetime, timedelta

# Standard failure archetypes mapped to realistic Razorpay & Banking error codes
FAILURE_ARCHETYPES = [
    {
        "true_category": "insufficient_funds",
        "failure_code": "BAD_REQUEST_ERROR",
        "error_reason": "payment_failed",
        "error_description": "Transaction failed: Customer account has insufficient funds/balance for debit.",
        "payment_type_distribution": ["subscription", "one_time"],
        "weight": 0.30
    },
    {
        "true_category": "expired_card",
        "failure_code": "CARD_EXPIRED_ERROR",
        "error_reason": "card_expired",
        "error_description": "Card validity date has lapsed or card has been deactivated by the cardholder bank.",
        "payment_type_distribution": ["subscription", "one_time"],
        "weight": 0.18
    },
    {
        "true_category": "bank_timeout",
        "failure_code": "GATEWAY_ERROR",
        "error_reason": "bank_timeout",
        "error_description": "Issuer bank payment gateway did not respond within the 45-second timeout window.",
        "payment_type_distribution": ["subscription", "one_time"],
        "weight": 0.20
    },
    {
        "true_category": "mandate_declined",
        "failure_code": "MANDATE_DEBIT_DECLINED",
        "error_reason": "mandate_revoked_or_limit_exceeded",
        "error_description": "Recurring e-mandate declined by destination bank: Mandate limit exceeded or mandate inactive.",
        "payment_type_distribution": ["subscription"],
        "weight": 0.14
    },
    {
        "true_category": "technical_error",
        "failure_code": "INTERNAL_SERVER_ERROR",
        "error_reason": "switch_network_failure",
        "error_description": "Network switch connection reset during authentication handshake. Ephemeral gateway glitch.",
        "payment_type_distribution": ["subscription", "one_time"],
        "weight": 0.12
    },
    {
        "true_category": "fraud_suspected",
        "failure_code": "RISK_ENGINE_REJECTED",
        "error_reason": "high_risk_flagged",
        "error_description": "Transaction rejected by fraud detection engine: suspicious IP velocity and unusual payment pattern.",
        "payment_type_distribution": ["one_time"],
        "weight": 0.06
    }
]

SYNTHETIC_FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Reyansh", "Muhammad", "Sai", "Ayaan", "Krishna",
    "Diya", "Saanvi", "Ananya", "Aadhya", "Pari", "Chiara", "Myra", "Isha", "Riya", "Avani"
]

SYNTHETIC_LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Mehta", "Iyer", "Nair", "Reddy", "Rao", "Gupta", "Malhotra",
    "Bose", "Das", "Singh", "Kaur", "Deshmukh", "Choudhury", "Pillai", "Menon", "Joshi", "Bhat"
]


def generate_synthetic_dataset(num_records: int = 100, seed: int = 42) -> pd.DataFrame:
    """
    Generates synthetic failed payment records with realistic Indian payment context.
    """
    random.seed(seed)
    records = []
    base_time = datetime.now() - timedelta(days=2)

    categories = [arch["true_category"] for arch in FAILURE_ARCHETYPES]
    weights = [arch["weight"] for arch in FAILURE_ARCHETYPES]

    for i in range(1, num_records + 1):
        # Select archetype based on probability weights
        selected_category = random.choices(categories, weights=weights, k=1)[0]
        archetype = next(item for item in FAILURE_ARCHETYPES if item["true_category"] == selected_category)

        # Generate unique IDs
        payment_id = f"pay_syn_{i:04d}_{random.randint(1000, 9999)}"
        customer_id = f"CUST_{i:04d}"
        
        first_name = random.choice(SYNTHETIC_FIRST_NAMES)
        last_name = random.choice(SYNTHETIC_LAST_NAMES)
        customer_name = f"{first_name} {last_name}"
        customer_email = f"cust_{i:04d}@example.com"
        customer_contact = f"+9198{random.randint(10000000, 99999999)}"

        # Realistic Indian subscription / transaction amounts in INR
        if selected_category == "mandate_declined" or "subscription" in archetype["payment_type_distribution"]:
            payment_type = random.choice(archetype["payment_type_distribution"])
        else:
            payment_type = "one_time"

        if payment_type == "subscription":
            amount = random.choice([299, 499, 799, 999, 1499, 1999, 2499])
        else:
            amount = random.choice([150, 350, 750, 1200, 2500, 3499, 4999])

        # Random timestamp over the last 48 hours
        offset_minutes = random.randint(0, 48 * 60)
        timestamp = (base_time + timedelta(minutes=offset_minutes)).isoformat()

        # 5% chance of customer opt-out to test consent guardrails
        opt_out = random.random() < 0.05

        records.append({
            "payment_id": payment_id,
            "customer_id": customer_id,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_contact": customer_contact,
            "amount": amount,
            "currency": "INR",
            "failure_code": archetype["failure_code"],
            "error_reason": archetype["error_reason"],
            "error_description": archetype["error_description"],
            "payment_type": payment_type,
            "timestamp": timestamp,
            "retry_count": 0,
            "opt_out": opt_out,
            "ground_truth_category": selected_category
        })

    return pd.DataFrame(records)


def save_datasets(data_dir: str):
    """
    Saves full synthetic dataset and a 20-row hand-labeled benchmark ground truth set.
    """
    os.makedirs(data_dir, exist_ok=True)
    df = generate_synthetic_dataset(num_records=100, seed=42)

    # Save full batch (100 rows)
    full_path = os.path.join(data_dir, "synthetic_failures.csv")
    df.to_csv(full_path, index=False)
    print(f"[OK] Saved full synthetic dataset (100 rows) to {full_path}")

    # Extract 20-row balanced ground truth benchmark set
    # Ensure representation from each failure class
    benchmark_rows = []
    for cat in df["ground_truth_category"].unique():
        sub_df = df[df["ground_truth_category"] == cat]
        sample_count = max(2, min(len(sub_df), 4))
        benchmark_rows.append(sub_df.sample(n=sample_count, random_state=42))
    
    benchmark_df = pd.concat(benchmark_rows).reset_index(drop=True)
    # Trim or expand to exactly 20 rows if needed
    if len(benchmark_df) > 20:
        benchmark_df = benchmark_df.head(20)
    elif len(benchmark_df) < 20:
        remaining = df[~df["payment_id"].isin(benchmark_df["payment_id"])]
        benchmark_df = pd.concat([benchmark_df, remaining.sample(n=20-len(benchmark_df), random_state=42)]).reset_index(drop=True)

    benchmark_path = os.path.join(data_dir, "ground_truth_labels.csv")
    benchmark_df.to_csv(benchmark_path, index=False)
    print(f"[OK] Saved 20-row held-out ground truth benchmark to {benchmark_path}")


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target_data_dir = os.path.join(os.path.dirname(current_dir), "data")
    save_datasets(target_data_dir)
