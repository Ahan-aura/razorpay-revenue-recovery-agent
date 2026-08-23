"""
AI Customer Recovery Message Generator
Drafts polite, failure-tailored, and bilingual (English & Hinglish) recovery notifications.
Adheres strictly to transactional messaging consent rules (max 1 message per failure event).
"""

from typing import Dict, Any, Optional
import os


class MessageGenerator:
    """
    Generates tailored WhatsApp/SMS/Email payment recovery nudges.
    """

    def generate_message(
        self,
        customer_name: str,
        amount: float,
        failure_type: str,
        payment_link_url: Optional[str] = None,
        language: str = "english"
    ) -> Dict[str, str]:
        """
        Generates context-aware recovery copy in English or Hinglish.
        """
        first_name = customer_name.split()[0] if customer_name else "Customer"
        link_str = payment_link_url or "https://rzp.io/i/recovery"

        if language == "hinglish":
            return self._generate_hinglish(first_name, amount, failure_type, link_str)
        else:
            return self._generate_english(first_name, amount, failure_type, link_str)

    def _generate_english(
        self,
        first_name: str,
        amount: float,
        failure_type: str,
        link_str: str
    ) -> Dict[str, str]:
        if failure_type == "expired_card":
            sms = f"Hi {first_name}, your recent payment of Rs. {amount:,.0f} could not be processed as your card has expired. Update your payment method securely here: {link_str}"
            email_subject = "Action Required: Update payment method for your subscription"
            email_body = (
                f"Dear {first_name},\n\n"
                f"We noticed that your latest payment of Rs. {amount:,.0f} could not be completed because your card on file has expired.\n"
                f"To prevent any disruption to your service, please click the secure Razorpay link below to update your payment details or use UPI/NetBanking:\n\n"
                f"👉 {link_str}\n\n"
                f"Thank you,\nCustomer Support Team"
            )
        elif failure_type == "insufficient_funds":
            sms = f"Hi {first_name}, your payment of Rs. {amount:,.0f} didn't go through due to a balance issue. We will retry in 3 days, or you can pay now: {link_str}"
            email_subject = "Payment reminder: Your pending transaction"
            email_body = (
                f"Dear {first_name},\n\n"
                f"Your payment of Rs. {amount:,.0f} was unsuccessful due to insufficient account balance.\n"
                f"We will automatically re-attempt the charge in 3 days. If you prefer to complete the payment immediately via an alternate account or UPI, please use this link:\n\n"
                f"👉 {link_str}\n\n"
                f"Best regards,\nCustomer Support Team"
            )
        elif failure_type == "bank_timeout" or failure_type == "technical_error":
            sms = f"Hi {first_name}, your payment of Rs. {amount:,.0f} timed out due to bank network latency. Complete it seamlessly with one click: {link_str}"
            email_subject = "Payment retry: Complete your transaction"
            email_body = (
                f"Dear {first_name},\n\n"
                f"Your payment of Rs. {amount:,.0f} experienced a temporary bank network switch timeout.\n"
                f"No funds were deducted. You can complete your transaction securely via this instant link:\n\n"
                f"👉 {link_str}\n\n"
                f"Warm regards,\nSupport Team"
            )
        elif failure_type == "mandate_declined":
            sms = f"Hi {first_name}, your recurring mandate for Rs. {amount:,.0f} was declined by your bank. Re-authorize your payment here: {link_str}"
            email_subject = "Mandate Re-authorization Needed"
            email_body = (
                f"Dear {first_name},\n\n"
                f"Your recurring subscription mandate of Rs. {amount:,.0f} was declined by your issuer bank.\n"
                f"Please authorize a fresh payment or update your mandate using our secure portal:\n\n"
                f"👉 {link_str}\n\n"
                f"Thank you,\nAccount Management Team"
            )
        else:
            sms = f"Hi {first_name}, your pending payment of Rs. {amount:,.0f} can be completed here: {link_str}"
            email_subject = "Complete your pending payment"
            email_body = f"Hi {first_name},\n\nPlease complete your pending payment of Rs. {amount:,.0f} at: {link_str}"

        return {"channel_sms": sms, "email_subject": email_subject, "email_body": email_body}

    def _generate_hinglish(
        self,
        first_name: str,
        amount: float,
        failure_type: str,
        link_str: str
    ) -> Dict[str, str]:
        if failure_type == "expired_card":
            sms = f"Namaste {first_name}! Aapka Rs. {amount:,.0f} ka payment complete nahi ho paya kyunki card expire ho gaya hai. Naya card ya UPI se complete karein: {link_str}"
            email_subject = "Important: Aapka payment method update karein"
            email_body = (
                f"Namaste {first_name},\n\n"
                f"Aapka Rs. {amount:,.0f} ka payment process nahi ho saka kyunki registered card ki validity expire ho chuki hai.\n"
                f"Bina kisi service interruption ke transaction complete karne ke liye neeche diye gaye Razorpay link par click karein:\n\n"
                f"👉 {link_str}\n\n"
                f"Dhanyawaad,\nSupport Team"
            )
        elif failure_type == "insufficient_funds":
            sms = f"Namaste {first_name}, aapka Rs. {amount:,.0f} ka payment low balance ki wajah se fail hua. Hum 3 din mein auto-retry karenge, ya abhi pay karein: {link_str}"
            email_subject = "Payment reminder: Pending subscription"
            email_body = (
                f"Namaste {first_name},\n\n"
                f"Aapke account se Rs. {amount:,.0f} ka payment balance kam hone ke kaaran complete nahi ho paya.\n"
                f"Hum is transaction ko 3 din baad dobara auto-retry karenge. Agar aap kisi aur bank ya UPI se abhi pay karna chahte hain toh yahan click karein:\n\n"
                f"👉 {link_str}\n\n"
                f"Dhanyawaad,\nCustomer Care"
            )
        else:
            sms = f"Namaste {first_name}, bank switch timeout ke kaaran Rs. {amount:,.0f} ka payment complete nahi hua. Quick pay link: {link_str}"
            email_subject = "Payment retry link"
            email_body = f"Namaste {first_name},\n\nBank technical issue ke kaaran Rs. {amount:,.0f} debit nahi hua. Transaction complete karne ke liye: {link_str}"

        return {"channel_sms": sms, "email_subject": email_subject, "email_body": email_body}
