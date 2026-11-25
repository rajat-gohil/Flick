import os
import logging
import requests
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class ResendHTTPBackend(BaseEmailBackend):
    """
    Lightweight HTTP email backend for Resend (https://resend.com).
    Communicates via HTTPS (Port 443) which bypasses cloud provider SMTP port blocks
    (such as Render Free Tier blocking ports 25, 465, and 587).
    """

    def __init__(self, api_key=None, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = api_key or os.getenv("RESEND_API_KEY", "").strip()

    def send_messages(self, email_messages):
        if not self.api_key:
            logger.error("ResendHTTPBackend: RESEND_API_KEY environment variable is not set.")
            if not self.fail_silently:
                raise ValueError("RESEND_API_KEY environment variable is required.")
            return 0

        sent_count = 0
        for message in email_messages:
            from_email = message.from_email
            # Default to Resend verified test sender if using discoverflick@gmail.com without custom domain
            if "@gmail.com" in from_email and "onboarding@resend.dev" not in from_email:
                # If custom domain is not yet verified on Resend, Resend requires onboarding@resend.dev
                sender = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
            else:
                sender = from_email

            payload = {
                "from": sender,
                "to": list(message.to),
                "subject": message.subject,
                "text": message.body,
            }

            try:
                response = requests.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=8,
                )
                if response.status_code in (200, 201):
                    logger.info("Email successfully sent via Resend to %s", message.to)
                    sent_count += 1
                elif response.status_code == 403 and "testing emails" in response.text:
                    import re
                    match = re.search(r"testing emails to your own email address \(([^)]+)\)", response.text)
                    owner_email = match.group(1) if match else os.getenv("RESEND_OWNER_EMAIL", "discoverflick@gmail.com")
                    logger.warning(
                        "Resend unverified domain mode: Rerouting email for %s to verified account owner: %s",
                        message.to,
                        owner_email,
                    )
                    retry_payload = {
                        "from": sender,
                        "to": [owner_email],
                        "subject": f"[Flick Account: {', '.join(message.to)}] {message.subject}",
                        "text": (
                            f"--- RESEND TESTING SANDBOX MODE ---\n"
                            f"Target Account: {', '.join(message.to)}\n"
                            f"Forwarded to Resend verified owner ({owner_email}) because your custom domain is not yet verified on resend.com/domains.\n"
                            f"------------------------------------\n\n"
                            + message.body
                        ),
                    }
                    retry_resp = requests.post(
                        "https://api.resend.com/emails",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=retry_payload,
                        timeout=8,
                    )
                    if retry_resp.status_code in (200, 201):
                        logger.info("Email successfully delivered to Resend owner %s for %s", owner_email, message.to)
                        sent_count += 1
                    else:
                        logger.error("Resend owner fallback failed [%s]: %s", retry_resp.status_code, retry_resp.text)
                        if not self.fail_silently:
                            retry_resp.raise_for_status()
                else:
                    logger.error(
                        "Resend API error [%s]: %s",
                        response.status_code,
                        response.text,
                    )
                    if not self.fail_silently:
                        response.raise_for_status()
            except Exception as exc:
                logger.error("Failed to dispatch email via Resend API: %s", exc)
                if not self.fail_silently:
                    raise

        return sent_count
