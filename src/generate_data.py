"""
Synthetic Data Generator for Razorpay Failed Payment Recovery Agent
Generates realistic failed payment datasets with rich Indian banking context,
NPCI response codes, switch error codes, and varied natural error descriptions.
Zero real PII used (clean synthetic data).
"""

import os
import random
import pandas as pd
from datetime import datetime, timedelta

# Rich archetypes with varied realistic Indian banking / NPCI error messages
FAILURE_ARCHETYPES = [
    {
        "true_category": "insufficient_funds",
        "templates": [
            {
                "failure_code": "BAD_REQUEST_ERROR",
                "error_reason": "payment_failed",
                "error_description": "Transaction failed: Customer account has insufficient funds/balance for debit."
            },
            {
                "failure_code": "NPCI_RESP_114",
                "error_reason": "account_balance_low",
                "error_description": "NPCI Debit decline: Available balance below requested transaction amount."
            },
            {
                "failure_code": "BANK_DEBIT_DECLINE_51",
                "error_reason": "insufficient_credit_limit",
                "error_description": "Issuer bank decline code 51: Insufficient funds in linked savings/current account."
            },
            {
                "failure_code": "PAYMENT_CANCELLED_LOW_BALANCE",
                "error_reason": "account_balance_unmet",
                "error_description": "Customer debit account lacked minimum clearing balance at scheduled time."
            }
        ],
        "payment_types": ["subscription", "one_time"],
        "weight": 0.30
    },
    {
        "true_category": "expired_card",
        "templates": [
            {
                "failure_code": "CARD_EXPIRED_ERROR",
                "error_reason": "card_expired",
                "error_description": "Card validity date has lapsed or card has been deactivated by the cardholder bank."
            },
            {
                "failure_code": "ISO_8583_DECLINE_54",
                "error_reason": "expired_card_token",
                "error_description": "Card tokenization expired. Issuer rejected debit due to card expiry MM/YY."
            },
            {
                "failure_code": "GATEWAY_CARD_INVALID",
                "error_reason": "card_validity_lapsed",
                "error_description": "Payment instrument invalid: Card valid-thru date has passed."
            }
        ],
        "payment_types": ["subscription", "one_time"],
        "weight": 0.18
    },
    {
        "true_category": "bank_timeout",
        "templates": [
            {
                "failure_code": "GATEWAY_ERROR",
                "error_reason": "bank_timeout",
                "error_description": "Issuer bank payment gateway did not respond within the 45-second timeout window."
            },
            {
                "failure_code": "NPCI_TIMEOUT_96",
                "error_reason": "npci_switch_unresponsive",
                "error_description": "NPCI UPI Switch timeout: Transaction timed out awaiting response from beneficiary bank."
            },
            {
                "failure_code": "HTTP_GATEWAY_TIMEOUT_504",
                "error_reason": "switch_latency_breached",
                "error_description": "Core banking system (CBS) response deadline exceeded during debit authentication."
            }
        ],
        "payment_types": ["subscription", "one_time"],
        "weight": 0.20
    },
    {
        "true_category": "mandate_declined",
        "templates": [
            {
                "failure_code": "MANDATE_DEBIT_DECLINED",
                "error_reason": "mandate_revoked_or_limit_exceeded",
                "error_description": "Recurring e-mandate declined by destination bank: Mandate limit exceeded or mandate inactive."
            },
            {
                "failure_code": "NPCI_UPI_MANDATE_U69",
                "error_reason": "mandate_paused_by_user",
                "error_description": "UPI Autopay mandate execution failed: Mandate paused or revoked by user in PSP app."
            },
            {
                "failure_code": "ENACH_DECLINE_U30",
                "error_reason": "standing_instruction_invalid",
                "error_description": "eNACH standing instruction rejected: Max per-transaction debit limit exceeded."
            }
        ],
        "payment_types": ["subscription"],
        "weight": 0.14
    },
    {
        "true_category": "technical_error",
        "templates": [
            {
                "failure_code": "INTERNAL_SERVER_ERROR",
                "error_reason": "switch_network_failure",
                "error_description": "Network switch connection reset during authentication handshake. Ephemeral gateway glitch."
            },
            {
                "failure_code": "BANK_SWITCH_91",
                "error_reason": "issuer_switch_inoperative",
                "error_description": "Issuer bank system down/inoperative during processing window."
            },
            {
                "failure_code": "TLS_HANDSHAKE_RESET",
                "error_reason": "socket_connection_closed",
                "error_description": "TCP connection reset by peer during 3DS challenge redirection."
            }
        ],
        "payment_types": ["subscription", "one_time"],
        "weight": 0.12
    },
    {
        "true_category": "fraud_suspected",
        "templates": [
            {
                "failure_code": "RISK_ENGINE_REJECTED",
                "error_reason": "high_risk_flagged",
                "error_description": "Transaction rejected by fraud detection engine: suspicious IP velocity and unusual payment pattern."
            },
            {
                "failure_code": "NPCI_SECURITY_DECLINE_U16",
                "error_reason": "risk_threshold_breach",
                "error_description": "Risk engine block: Rapid repeated checkout attempts from anomalous geographic location."
            },
            {
                "failure_code": "GATEWAY_FRAUD_BLOCK_59",
                "error_reason": "suspected_carding_attack",
                "error_description": "Security perimeter triggered: Velocity threshold breached on merchant endpoint."
            }
        ],
        "payment_types": ["one_time"],
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
        selected_category = random.choices(categories, weights=weights, k=1)[0]
        archetype = next(item for item in FAILURE_ARCHETYPES if item["true_category"] == selected_category)
        template = random.choice(archetype["templates"])

        payment_id = f"pay_syn_{i:04d}_{random.randint(1000, 9999)}"
        customer_id = f"CUST_{i:04d}"
        
        first_name = random.choice(SYNTHETIC_FIRST_NAMES)
        last_name = random.choice(SYNTHETIC_LAST_NAMES)
        customer_name = f"{first_name} {last_name}"
        customer_email = f"cust_{i:04d}@example.com"
        customer_contact = f"+9198{random.randint(10000000, 99999999)}"

        if selected_category == "mandate_declined" or "subscription" in archetype["payment_types"]:
            payment_type = random.choice(archetype["payment_types"])
        else:
            payment_type = "one_time"

        if payment_type == "subscription":
            amount = random.choice([299, 499, 799, 999, 1499, 1999, 2499])
        else:
            amount = random.choice([150, 350, 750, 1200, 2500, 3499, 4999])

        offset_minutes = random.randint(0, 48 * 60)
        timestamp = (base_time + timedelta(minutes=offset_minutes)).isoformat()
        opt_out = random.random() < 0.05

        records.append({
            "payment_id": payment_id,
            "customer_id": customer_id,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_contact": customer_contact,
            "amount": amount,
            "currency": "INR",
            "failure_code": template["failure_code"],
            "error_reason": template["error_reason"],
            "error_description": template["error_description"],
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

    full_path = os.path.join(data_dir, "synthetic_failures.csv")
    df.to_csv(full_path, index=False)
    print(f"[OK] Saved full synthetic dataset (100 rows) to {full_path}")

    # Extract 20-row balanced ground truth benchmark set
    benchmark_rows = []
    for cat in df["ground_truth_category"].unique():
        sub_df = df[df["ground_truth_category"] == cat]
        sample_count = max(2, min(len(sub_df), 4))
        benchmark_rows.append(sub_df.sample(n=sample_count, random_state=42))
    
    benchmark_df = pd.concat(benchmark_rows).reset_index(drop=True)
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
