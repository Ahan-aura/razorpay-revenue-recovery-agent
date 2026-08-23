"""
Benchmark Evaluation Runner for Live LLM Diagnostic Inference
Evaluates the held-out 20-row hand-labeled dataset using live Google Gemini model.
Maintains respectful pacing to stay within free-tier Rate Limits (RPM).
"""

import os
import sys
import time
import json
import logging
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Setup sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.classifier import FailureClassifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("LLMBenchmark")


def run_live_llm_benchmark():
    benchmark_path = os.path.join(BASE_DIR, "data", "ground_truth_labels.csv")
    output_path = os.path.join(BASE_DIR, "outputs", "benchmark_evaluation.json")

    if not os.path.exists(benchmark_path):
        logger.error(f"Benchmark file {benchmark_path} not found.")
        return

    df = pd.read_csv(benchmark_path)
    classifier = FailureClassifier()

    logger.info(f"Starting Live LLM benchmark evaluation on {len(df)} hand-labeled rows using: {classifier.active_engine}")

    predictions_log = []
    correct_count = 0
    class_stats = {}

    for idx, row in df.iterrows():
        event = row.to_dict()
        ground_truth = event.get("ground_truth_category")
        payment_id = event.get("payment_id")

        logger.info(f"[{idx+1}/{len(df)}] Classifying {payment_id} via Gemini...")
        
        # Real LLM inference
        pred = classifier.classify_failure(event)
        predicted_type = pred.get("failure_type")
        is_correct = (predicted_type == ground_truth)

        if is_correct:
            correct_count += 1

        if ground_truth not in class_stats:
            class_stats[ground_truth] = {"total": 0, "correct": 0}
        class_stats[ground_truth]["total"] += 1
        if is_correct:
            class_stats[ground_truth]["correct"] += 1

        predictions_log.append({
            "payment_id": payment_id,
            "ground_truth": ground_truth,
            "predicted": predicted_type,
            "confidence": pred.get("confidence"),
            "is_correct": is_correct,
            "engine_used": pred.get("engine_used"),
            "reasoning": pred.get("reasoning")
        })

        # Pacing to respect free-tier rate limits
        time.sleep(1.0)

    accuracy_pct = round((correct_count / len(df)) * 100, 1)
    engine_name = classifier.active_engine

    summary = {
        "engine_evaluated": engine_name,
        "evaluation_type_note": f"Evaluated using Live Semantic LLM Diagnostic Inferences ({engine_name}).",
        "sample_size": len(df),
        "sample_size_note": "Evaluated on hand-labeled held-out test partition (20 rows)",
        "accuracy_pct": accuracy_pct,
        "correct_count": correct_count,
        "total_count": len(df),
        "per_class_accuracy": {
            k: round(v["correct"] / v["total"] * 100, 1) for k, v in class_stats.items()
        },
        "detailed_predictions": predictions_log
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"[SUCCESS] Benchmark complete! Accuracy: {accuracy_pct}% ({correct_count}/{len(df)}) via {engine_name}")
    print(f"\n========================================================")
    print(f"      LIVE LLM BENCHMARK RESULTS ({engine_name})")
    print(f"========================================================")
    print(f"Accuracy:        {accuracy_pct}% ({correct_count}/{len(df)} correct)")
    print(f"Sample Size:     {len(df)} hand-labeled test cases")
    print(f"Engine:          {engine_name} (Live Google Gemini Inference)")
    print(f"========================================================\n")


if __name__ == "__main__":
    run_live_llm_benchmark()
