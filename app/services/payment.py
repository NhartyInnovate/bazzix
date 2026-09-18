from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


class PaymentProviderError(Exception):
    """Base exception for all payment provider errors."""
    pass


class PaymentInitializationError(PaymentProviderError):
    """Raised when a payment transaction fails to initialize with the provider."""
    pass


class PaymentVerificationError(PaymentProviderError):
    """Raised when a payment transaction verification fails."""
    pass


class InvalidProviderResponseError(PaymentProviderError):
    """Raised when the provider returns an unexpected or unparseable response."""
    pass


@dataclass
class PaymentInitializationResult:
    """
    Provider-independent result of initializing a payment.
    """
    authorization_url: str
    provider_reference: str
    provider_transaction_id: Optional[str] = None


@dataclass
class PaymentVerificationResult:
    """
    Provider-independent result of verifying a payment.
    
    amount: The verified amount in whole currency units (e.g. NGN, not kobo).
    currency: The verified currency code (e.g. "NGN").
    """
    reference: str
    status: str  # "SUCCESS", "FAILED"
    amount: int
    currency: str
    provider_transaction_id: Optional[str] = None
    paid_at: Optional[datetime] = None


class PaymentProvider(ABC):
    """
    Abstract base class for all payment providers.
    
    IMPORTANT MONETARY SEMANTICS:
    The `amount` arguments and properties represent WHOLE currency units 
    (e.g., 1000 for ₦1,000 NGN). 
    The concrete provider implementation is strictly responsible for any 
    conversions to/from minor units (like kobo) required by the external API.
    """

    @abstractmethod
    def initialize_transaction(
        self, 
        amount: int, 
        currency: str, 
        email: str, 
        reference: str
    ) -> PaymentInitializationResult:
        """
        Initializes a payment transaction with the external provider.
        
        Args:
            amount: The amount in whole currency units (e.g. 1500 for NGN).
            currency: The ISO currency code (e.g. "NGN").
            email: The customer's email address.
            reference: The deterministic Bazzix reference for this intent.
            
        Returns:
            PaymentInitializationResult containing the checkout URL and reference.
            
        Raises:
            PaymentInitializationError: If the provider rejects the initialization.
        """
        pass

    @abstractmethod
    def verify_transaction(self, reference: str) -> PaymentVerificationResult:
        """
        Verifies the status of a payment transaction with the external provider.
        
        Args:
            reference: The provider/payment reference to verify.
            
        Returns:
            PaymentVerificationResult containing the verified status, amount, and currency.
            
        Raises:
            PaymentVerificationError: If the verification check itself fails (e.g. network error).
        """
        pass
