import re
import requests
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.config import settings
from app.services.payment import (
    PaymentProvider,
    PaymentInitializationResult,
    PaymentVerificationResult,
    PaymentInitializationError,
    PaymentVerificationError,
    InvalidProviderResponseError
)


class PaystackProvider(PaymentProvider):
    BASE_URL = "https://api.paystack.co"
    TIMEOUT = 10.0

    def __init__(self, secret_key: str = None):
        # Allow passing the key explicitly for testing, or fallback to settings
        self.secret_key = secret_key or settings.PAYSTACK_SECRET_KEY
        if not self.secret_key:
            raise ValueError("PAYSTACK_SECRET_KEY is not configured.")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    def _validate_amount(self, amount: Any) -> int:
        if not isinstance(amount, int):
            raise ValueError("Amount must be an integer.")
        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")
        return amount

    def _validate_reference(self, reference: str) -> None:
        if not re.match(r'^[-a-zA-Z0-9.=]+$', reference):
            raise ValueError("Invalid reference format. Only alphanumeric characters, '-', '.', and '=' are allowed.")

    def initialize_transaction(
        self, 
        amount: int, 
        currency: str, 
        email: str, 
        reference: str,
        callback_url: str = None
    ) -> PaymentInitializationResult:
        try:
            amount = self._validate_amount(amount)
            self._validate_reference(reference)
        except ValueError as e:
            raise PaymentInitializationError(str(e))

        if currency.upper() != "NGN":
            raise PaymentInitializationError("PaystackProvider currently only supports NGN currency.")

        # Convert to subunit (kobo)
        kobo_amount = int(amount * 100)

        payload = {
            "email": email,
            "amount": kobo_amount,
            "currency": currency,
            "reference": reference
        }
        if callback_url:
            payload["callback_url"] = callback_url

        try:
            response = requests.post(
                f"{self.BASE_URL}/transaction/initialize",
                json=payload,
                headers=self._get_headers(),
                timeout=self.TIMEOUT
            )
        except requests.RequestException as e:
            raise PaymentInitializationError("Network error during initialization.") from e

        if not response.ok:
            # Do not leak raw response content directly if it might contain secrets, though Paystack usually doesn't.
            raise PaymentInitializationError(f"Provider rejected request with status {response.status_code}.")

        try:
            data = response.json()
            if not data.get("status"):
                raise InvalidProviderResponseError("Provider returned unsuccessful status in payload.")
            
            paystack_data = data.get("data", {})
            auth_url = paystack_data.get("authorization_url")
            ref = paystack_data.get("reference")
            
            if not auth_url or not ref:
                raise InvalidProviderResponseError("Missing required fields in provider response.")
                
        except ValueError:
            raise InvalidProviderResponseError("Provider returned malformed JSON.")

        return PaymentInitializationResult(
            authorization_url=auth_url,
            provider_reference=ref,
            provider_transaction_id=None  # Initialization doesn't reliably return the ID
        )

    def verify_transaction(self, reference: str) -> PaymentVerificationResult:
        try:
            self._validate_reference(reference)
        except ValueError as e:
            raise PaymentVerificationError(str(e))

        try:
            response = requests.get(
                f"{self.BASE_URL}/transaction/verify/{reference}",
                headers=self._get_headers(),
                timeout=self.TIMEOUT
            )
        except requests.RequestException as e:
            raise PaymentVerificationError("Network error during verification.") from e

        if not response.ok:
            raise PaymentVerificationError(f"Provider rejected verification with status {response.status_code}.")

        try:
            data = response.json()
            if not data.get("status"):
                raise InvalidProviderResponseError("Provider returned unsuccessful status in verification payload.")
                
            paystack_data = data.get("data")
            if not paystack_data:
                raise InvalidProviderResponseError("Missing data field in provider response.")
                
            status = paystack_data.get("status")
            if not status:
                raise InvalidProviderResponseError("Missing transaction status in provider response.")
                
            ref = paystack_data.get("reference")
            kobo_amount = paystack_data.get("amount")
            currency = paystack_data.get("currency")
            tx_id = paystack_data.get("id")
            
            if kobo_amount is None or not currency or not ref:
                raise InvalidProviderResponseError("Missing critical transaction details in provider response.")

            # Parse paid_at if available
            paid_at_str = paystack_data.get("paid_at")
            paid_at_dt = None
            if paid_at_str:
                try:
                    # Example format: 2023-01-01T12:00:00.000Z
                    paid_at_dt = datetime.strptime(paid_at_str.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S.%f%z")
                except ValueError:
                    # Try without fractional seconds
                    try:
                        paid_at_dt = datetime.strptime(paid_at_str.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
                    except ValueError:
                        pass # Leave as None if unparseable to avoid crashing on timestamps

            # Convert from minor unit (kobo) to whole unit
            whole_amount = kobo_amount // 100

            return PaymentVerificationResult(
                reference=ref,
                status=status,
                amount=whole_amount,
                currency=currency,
                provider_transaction_id=str(tx_id) if tx_id else None,
                paid_at=paid_at_dt
            )
        except ValueError:
            raise InvalidProviderResponseError("Provider returned malformed JSON during verification.")

