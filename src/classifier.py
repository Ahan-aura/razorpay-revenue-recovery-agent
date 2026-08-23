"""
LLM-Powered Failure Classification Engine for Razorpay Failed Payments
Classifies ambiguous payment gateway errors into standard recoverable categories
with confidence scoring and structured reasoning.

Supports:
1. Google Gemini (gemini-1.5-flash / gemini-1.5-pro)
2. Anthropic Claude (claude-3-haiku)
3. Deterministic Baseline Pattern Classifier (used as offline fallback / baseline benchmark)

Explicitly logs 'engine_used' so benchmark reporting is 100% transparent.
"""

import os
import re
import json
import time
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

VALID_FAILURE_TYPES = [
    "insufficient_funds",
    "expired_card",
    "bank_timeout",
    "mandate_declined",
    "technical_error",
    "fraud_suspected"
]

CLASSIFICATION_SYSTEM_PROMPT = """You are an expert Payment Gateway AI Diagnostics Agent for Razorpay.
Your job is to analyze failed payment error codes, gateway logs, customer metadata, and error descriptions.
You must classify the underlying root cause into EXACTLY ONE of the following 6 standardized categories:

1. 'insufficient_funds': Customer has low balance, exceeded debit account balance, or credit line insufficient.
2. 'expired_card': Card expired, expired validity date, or card replaced by bank.
3. 'bank_timeout': Gateway timeout, bank switch unresponsiveness, NPCI timeout, 45s latency drop.
4. 'mandate_declined': Recurring mandate revoked, debit cap exceeded, recurring schedule paused, or mandate inactive.
5. 'technical_error': Gateway switch 5xx, network socket reset, internal gateway glitch, SSL handshake error.
6. 'fraud_suspected': Velocity check triggered, high risk score, suspicious IP/card mismatch, fraud filter block.

You must respond ONLY with a valid JSON object matching this schema:
{
  "failure_type": "<one of the 6 categories above>",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<concise 1-2 sentence explanation of why this category applies>",
  "suggested_recovery_urgency": "<immediate | delayed_3d | escalate | none>"
}
Do NOT return any markdown wrapper other than standard json or raw json.
"""


class FailureClassifier:
    """
    Orchestrates payment failure classification with transparency between
    LLM semantic inference and deterministic baseline rule matching.
    """

    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or os.getenv("LLM_PROVIDER", "gemini").lower()
        self.gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.active_engine = "deterministic_keyword_baseline"
        self._init_client()

    def _init_client(self):
        """Initializes the active LLM client based on environment."""
        self.client = None
        try:
            if self.provider == "gemini" and self.gemini_key and not self.gemini_key.startswith("your_"):
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_key)
                
                # Support available modern Gemini models
                for model_name in ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-flash-latest", "gemini-2.5-flash"]:
                    try:
                        self.client = genai.GenerativeModel(model_name)
                        self.model_name = model_name
                        self.active_engine = f"llm_{model_name.replace('-', '_').replace('.', '_')}"
                        logger.info(f"Initialized Google Gemini LLM diagnostic engine ({model_name}).")
                        break
                    except Exception:
                        continue
            elif self.provider == "anthropic" and self.anthropic_key and not self.anthropic_key.startswith("your_"):
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.anthropic_key)
                self.active_engine = "llm_claude_3_haiku"
                logger.info("Initialized Anthropic Claude LLM diagnostic engine.")
            else:
                self.active_engine = "deterministic_keyword_baseline"
                logger.info("Operating in Deterministic Baseline Classifier mode (no active LLM key supplied).")
        except Exception as e:
            logger.warning(f"Could not initialize primary LLM provider {self.provider}: {e}. Operating in Baseline mode.")
            self.active_engine = "deterministic_keyword_baseline"

    def classify_failure(self, payment_event: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """
        Classifies a single failed payment event.
        Guarantees structured return format and explicitly returns 'engine_used'.
        """
        prompt = f"""Analyze this Razorpay payment failure event:
- Payment ID: {payment_event.get('payment_id', 'N/A')}
- Amount: ₹{payment_event.get('amount', 0)} ({payment_event.get('payment_type', 'one_time')})
- Failure Code: {payment_event.get('failure_code', 'UNKNOWN')}
- Error Reason: {payment_event.get('error_reason', 'UNKNOWN')}
- Error Description: {payment_event.get('error_description', 'No description')}
- Timestamp: {payment_event.get('timestamp', 'N/A')}
- Retry Count: {payment_event.get('retry_count', 0)}

Return strict JSON classification.
"""
        # If Real LLM is active
        if self.active_engine.startswith("llm_"):
            attempt = 0
            while attempt < max_retries:
                try:
                    if "gemini" in self.active_engine:
                        res = self._call_gemini(prompt)
                    else:
                        res = self._call_anthropic(prompt)
                    res["engine_used"] = self.active_engine
                    return res
                except Exception as e:
                    attempt += 1
                    err_str = str(e).lower()
                    if "429" in err_str or "quota" in err_str:
                        wait_time = 4.0 * attempt
                    else:
                        wait_time = 1.0 * (2 ** (attempt - 1))
                    logger.warning(f"LLM attempt {attempt} failed: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)

            logger.error(f"All LLM retries exhausted. Invoking baseline rule classifier fallback.")
            fallback = self._baseline_rule_classifier(payment_event)
            fallback["engine_used"] = "fallback_after_llm_timeout"
            return fallback

        # Deterministic Baseline Rule Classifier Mode
        baseline_res = self._baseline_rule_classifier(payment_event)
        baseline_res["engine_used"] = "deterministic_keyword_baseline"
        return baseline_res

    def _call_gemini(self, prompt: str) -> Dict[str, Any]:
        """Calls Google Gemini model."""
        response = self.client.generate_content(
            f"{CLASSIFICATION_SYSTEM_PROMPT}\n\n{prompt}",
            generation_config={"temperature": 0.1, "response_mime_type": "application/json"}
        )
        return self._clean_and_parse_json(response.text)

    def _call_anthropic(self, prompt: str) -> Dict[str, Any]:
        """Calls Anthropic Claude model."""
        message = self.client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            temperature=0.1,
            system=CLASSIFICATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        return self._clean_and_parse_json(message.content[0].text)

    def _clean_and_parse_json(self, raw_text: str) -> Dict[str, Any]:
        """Sanitizes LLM output and validates JSON structure."""
        text = raw_text.strip()
        text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        
        parsed = json.loads(text)
        if parsed.get("failure_type") not in VALID_FAILURE_TYPES:
            parsed["failure_type"] = "technical_error"
        
        confidence = float(parsed.get("confidence", 0.5))
        parsed["confidence"] = max(0.0, min(1.0, confidence))
        
        if "reasoning" not in parsed:
            parsed["reasoning"] = "Inferred via LLM diagnostic model."
            
        return parsed

    def _baseline_rule_classifier(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deterministic baseline classifier.
        Transparently labels its reasoning as rule-matched.
        """
        code = str(event.get("failure_code", "")).upper()
        reason = str(event.get("error_reason", "")).lower()
        desc = str(event.get("error_description", "")).lower()
        
        # 1. Fraud / Risk
        if "risk" in code or "fraud" in desc or "suspicious" in desc or "high_risk" in reason or "u16" in code or "59" in code:
            return {
                "failure_type": "fraud_suspected",
                "confidence": 0.95,
                "reasoning": "[Rule Baseline] Triggered by fraud/risk engine code or security velocity indicator.",
                "suggested_recovery_urgency": "escalate"
            }
        
        # 2. Expired Card
        if "card_expired" in code or "expired" in desc or "card_expired" in reason or "lapsed" in desc or "54" in code:
            return {
                "failure_type": "expired_card",
                "confidence": 0.96,
                "reasoning": "[Rule Baseline] Matched card validity lapse or ISO 8583 decline 54.",
                "suggested_recovery_urgency": "immediate"
            }
            
        # 3. Mandate Declined
        if "mandate" in code or "mandate" in desc or "mandate" in reason or "u69" in code or "u30" in code or "enach" in code:
            return {
                "failure_type": "mandate_declined",
                "confidence": 0.94,
                "reasoning": "[Rule Baseline] Matched NPCI mandate decline / eNACH standing instruction error.",
                "suggested_recovery_urgency": "immediate"
            }
            
        # 4. Bank Timeout
        if "timeout" in code or "timeout" in desc or "bank_timeout" in reason or "latency" in desc or "96" in code or "504" in code:
            return {
                "failure_type": "bank_timeout",
                "confidence": 0.92,
                "reasoning": "[Rule Baseline] Matched issuer/NPCI gateway response deadline timeout.",
                "suggested_recovery_urgency": "immediate"
            }
            
        # 5. Insufficient Funds
        if "insufficient" in desc or "balance" in desc or "funds" in desc or "114" in code or "51" in code or "low_balance" in code:
            return {
                "failure_type": "insufficient_funds",
                "confidence": 0.93,
                "reasoning": "[Rule Baseline] Matched low balance or NPCI decline 114 / Bank 51.",
                "suggested_recovery_urgency": "delayed_3d"
            }
            
        # 6. Technical error default
        return {
            "failure_type": "technical_error",
            "confidence": 0.75,
            "reasoning": "[Rule Baseline] Matched transient bank switch / network reset error.",
            "suggested_recovery_urgency": "immediate"
        }
