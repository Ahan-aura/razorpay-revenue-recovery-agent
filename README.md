# ⚡ Razorpay Autonomous Revenue Recovery Agent

### Razorpay AI Buildathon 2026 — AI Revenue Recovery Track

> **One-Sentence Pitch:** An autonomous, governed payment recovery agent that diagnoses failed Razorpay transactions, enforces deterministic stopping rules & safety gates, dispatches tailored recovery payment links via real Razorpay APIs, and verifies outcomes via cryptographic webhooks with complete auditability.

---

## 📑 Table of Contents
- [1. The Problem & Business Impact](#1-the-problem--business-impact)
- [2. System Architecture](#2-system-architecture)
- [3. Key Innovations & Loopholes Solved](#3-key-innovations--loopholes-solved)
- [4. Repository Structure](#4-repository-structure)
- [5. Quickstart & Installation](#5-quickstart--installation)
- [6. Live Benchmark & Evaluation Results](#6-live-benchmark--evaluation-results)
- [7. How We Address Judging Criteria](#7-how-we-address-judging-criteria)
- [8. 5-Minute Panel Pitch & Demo Script](#8-5-minute-panel-pitch--demo-script)

---

## 1. The Problem & Business Impact

Recurring subscription mandates and one-time checkout transactions fail frequently in the Indian payments ecosystem due to:
- **Insufficient balance** (temporary cash flow timing around salary cycles)
- **Expired cards & lapsed token validity**
- **Bank switch latency and NPCI gateway timeouts**
- **Revoked or limit-exceeded e-mandates**
- **Transient network errors & switch glitches**

### The Status Quo vs. Our Solution:
- **Standard approach:** Merchants either retry blindly (damaging bank reputation, wasting gateway fees, annoying customers) or abandon the payment (losing revenue and customer LTV).
- **Our Agent:** Diagnoses root causes, delegates action decisions to **deterministic rules** (keeping LLM out of money decisions), executes automated recovery via **Razorpay Payment Links**, and validates actual collections via **cryptographic webhooks**.

---

## 2. System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          1. DATA INGESTION                             │
│   synthetic_failures.csv & held-out ground_truth_labels.csv (20 rows)   │
│   payment_id | customer_id | amount | failure_code | error_description  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     2. CLASSIFICATION ENGINE                           │
│   Multi-backend Diagnostic Engine (Gemini / Claude / Baseline Rule)   │
│   Outputs: failure_type, confidence (0-1.0), diagnostic reasoning      │
│   Resilience: Exponential backoff retries + fallback wrapping          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  3. DETERMINISTIC POLICY & SAFETY GATES                │
│   Zero LLM hallucination for money decisions:                          │
│   ├── Gate 0: Idempotency check (prevents duplicate actions)           │
│   ├── Gate 1: Customer consent & opt-out suppression                   │
│   ├── Gate 2: Fraud block & instant human escalation                   │
│   ├── Gate 3: Confidence threshold gate (confidence < 0.70 -> review)  │
│   ├── Gate 4: Stopping rule (max 3 retries, 24h cooldown)              │
│   └── Gate 5: Root-cause recovery routing (salary cycle delay, link)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   4. ACTION EXECUTION & MESSAGING                      │
│   - Razorpay Python SDK: Creates recovery payment links (Cards/UPI)    │
│   - Message Generator: Contextual SMS & Email copy (English/Hinglish)  │
│   - Transparent Simulation mode when sandbox keys are unconfigured     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 5. AUDIT LOG & CRYPTOGRAPHIC WEBHOOKS                  │
│   - FastAPI Webhook listener for payment.captured / payment.failed     │
│   - Promotes outcomes to 'live_verified' (real webhook) or            │
│     'demo_verified' (local simulation endpoint)                        │
│   - Immutable structured audit log in outputs/audit_log.json           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 6. STREAMLIT INTERACTIVE DASHBOARD                     │
│   - Executive KPI cards with honest Dispatched vs. Verified split      │
│   - Interactive batch trigger and transaction deep-dive inspector      │
│   - Governed escalation panel and benchmark accuracy visualization     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Key Innovations & Loopholes Solved

| # | Addressed Loophole / Trap | Engineering Solution in Code |
|---|---|---|
| 1 | **Metric Inflation Trap** | **Strict Separation:** Distinguishes **Actions Dispatched** (payment links created) from **Confirmed Collections** (real webhooks). Zero inflated claims. |
| 2 | **Circular Benchmark Trap** | **Transparent Engine Tracking:** Explicitly logs whether evaluations ran on LLM semantic inference or deterministic baseline rules. |
| 3 | **Low-Confidence LLM Guesses** | **Confidence Gate:** Any classification with confidence $< 0.70$ is forced to `manual_review`. |
| 4 | **Double-Charging / Duplicate Links** | **Idempotency Gate:** Checks audit history before executing actions to prevent double-charging or duplicate links. |
| 5 | **API Downtime / System Crashes** | External calls wrapped in exponential backoff retry ($0.5s \times 2^n$) and logged as `system_error` without crashing. |
| 6 | **Unverified Regulation Citations** | Explicitly designed as conservative merchant policies (e.g., max 3 retries, 72h salary cycle delay). |
| 7 | **Secrets & PII Leaks** | Complete `.gitignore` guardrails, zero real PII (clean synthetic faker names/IDs). |
| 8 | **Customer Consent Compliance** | Respects `opt_out` flag and limits outbound recovery nudges to maximum 1 message per failure event. |
| 9 | **Fake Webhook Mislabeling** | Webhook simulator explicitly tags test events as `demo_verified` to distinguish from cryptographically signed live webhooks (`live_verified`). |

---

## 4. Repository Structure

```
recovery-agent/
├── README.md                 # Complete documentation and pitch guide
├── requirements.txt          # Python dependencies
├── .env.example              # Configuration template
├── .gitignore                # Secret and PII leakage prevention
├── data/
│   ├── synthetic_failures.csv      # 100-row realistic Indian failure dataset
│   └── ground_truth_labels.csv     # 20-row hand-labeled benchmark partition
├── src/
│   ├── __init__.py
│   ├── generate_data.py      # Synthetic dataset generator with NPCI/Bank codes
│   ├── classifier.py         # Multi-backend diagnostic engine (LLM & Rule baseline)
│   ├── policy_engine.py      # Deterministic decision rules & safety gates
│   ├── razorpay_client.py    # Razorpay SDK client with retry backoff
│   ├── message_generator.py  # Bilingual (English & Hinglish) recovery copy
│   ├── webhook_server.py     # FastAPI webhook receiver (live vs demo verification)
│   ├── executor.py           # End-to-end orchestration pipeline
│   ├── audit_log.py          # Structured audit trail manager
│   └── metrics.py            # KPI and benchmark metrics calculator
├── tests/
│   └── test_policy_engine.py # Comprehensive unit tests for policy gates
├── dashboard/
│   └── app.py                # Streamlit interactive dashboard
└── outputs/
    ├── audit_log.json        # Permanent action logs
    ├── metrics_summary.json  # Computed KPI metrics
    └── benchmark_evaluation.json # Held-out benchmark accuracy results
```

---

## 5. Quickstart & Installation

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/Ahan-aura/razorpay-revenue-recovery-agent.git
cd recovery-agent
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
*(Configure `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` for live LLM mode, and `RAZORPAY_KEY_ID` for live test API calls. If unconfigured, the agent operates in its resilient offline baseline mode.)*

### 3. Run Policy Engine Unit Tests
```bash
pytest tests/test_policy_engine.py
```

### 4. Run the Batch Recovery Pipeline
```bash
python src/executor.py --reset-logs
```

### 5. Launch the Streamlit Dashboard
```bash
streamlit run dashboard/app.py
```

### 6. (Optional) Run Webhook Server
```bash
python src/webhook_server.py
```

---

## 6. Live Benchmark & Evaluation Results

Tested on a dataset of **101 synthetic failed transactions** representing **₹168,889** in failed volume:

- **Recovery Actions Dispatched:** **₹135,747** across **84 Payment Links** (**80.4% Dispatch Rate**)
- **Live-Verified Webhook Collections:** ₹2,099 (2 webhooks verified prior to live checkout triggers)
- **Governed Escalations:** **8 Fraud Cases Blocked** and escalated to operations
- **Customer Consent Filter:** **9 Opted-out customer transactions suppressed** from outbound notifications
- **System Resilience:** **0 System Crashes** (handled via exponential backoff and error wrapping)
- **Held-Out Benchmark Accuracy:** **90.0%** (18/20 on hand-labeled test cases using `deterministic_keyword_baseline`).

## 7. How We Address Judging Criteria

| Criterion | How This Submission Addresses It |
|---|---|
| **Problem Taste** | Solves high-impact payment churn in the Indian ecosystem through tailored recovery pathways (salary cycle delays, payment links, re-mandates) rather than wasteful blind retries. |
| **Build Quality** | Modular design, full unit test suite, atomic audit trail logging, cryptographic webhook signature verification, and zero PII/secret leaks. |
| **AI Judgment** | **The LLM never makes financial execution decisions.** AI is used exclusively for linguistic error diagnosis and message drafting; all stopping rules and money actions are 100% deterministic code. |
| **Failure Recovery** | Two-tier resilience: System-level retry backoff for external APIs, and business-level stopping rules with human escalation for low confidence or fraud. |
| **Honesty & Transparency** | Strict separation of **Dispatched Actions** from **Confirmed Webhook Collections**, with transparent engine attribution in benchmark evaluations. |

---

## 8. 5-Minute Panel Pitch & Demo Script

1. **Problem Framing (0:00 - 0:45):**
   - *"Failed payments cost Indian subscription and e-commerce businesses millions in MRR every month. Today, merchants either retry blindly or abandon customers."*
2. **Solution & Architecture (0:45 - 2:00):**
   - *"We built an Autonomous Revenue Recovery Agent. It analyzes gateway failure logs using LLM diagnostics, but delegates every single action decision to deterministic policy rules."*
3. **Live Dashboard Walkthrough (2:00 - 3:30):**
   - Click **'Run Batch Pipeline Live'** in Streamlit. Show ₹135,747 in recovery actions dispatched across 84 eligible transactions (80.4% dispatch rate).
   - Trigger **'Simulate Customer Payment'** to demonstrate real-time promotion to `demo_verified` / `live_verified`.
   - Inspect single transaction showing the diagnostic reasoning, deterministic rule fired, and generated Hinglish SMS copy.
4. **Governed AI Judgment & Escalation (3:30 - 4:30):**
   - Open the **'AI Judgment & Escalation Panel'**.
   - *"Notice these 8 transactions: our agent detected high fraud risk. Instead of hallucinating an action or blindly charging, it stopped automated retries and escalated cleanly."*
5. **Conclusion & Q&A (4:30 - 5:00):**
   - Highlight the modular, transparent, production-ready codebase and honest metric reporting.
