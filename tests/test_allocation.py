import unittest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.db.database import Base
from app.models.user import User
from app.models.wallet import Wallet
from app.models.ledger import LedgerTransaction, TransactionType
from app.models.purchase import Purchase, PurchaseStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.allocation import (
    allocate_subscription_credits,
    initialize_purchase,
    fulfill_purchase,
    AllocationIdempotencyError,
    AllocationError
)

class TestAllocationService(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:', connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        self.user = User(
            first_name="Test",
            last_name="User",
            email="test@example.com",
            hashed_password="pw",
            is_active=True
        )
        self.db.add(self.user)
        self.db.commit()

        self.wallet = Wallet(user_id=self.user.id)
        self.db.add(self.wallet)

        self.subscription = Subscription(
            user_id=self.user.id,
            plan_id="pro",
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc),
            current_period_end=datetime.datetime(2023, 2, 1, tzinfo=datetime.timezone.utc)
        )
        self.db.add(self.subscription)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_allocate_subscription_credits_success(self):
        tx = allocate_subscription_credits(
            self.db,
            subscription_id=self.subscription.id,
            user_id=self.user.id,
            plan_id="pro",
            period_start=self.subscription.current_period_start
        )
        self.db.commit()

        self.assertEqual(tx.amount, 40000)
        self.assertEqual(tx.transaction_type, TransactionType.SUBSCRIPTION_ALLOCATION)
        self.assertTrue(tx.reference_id.startswith("sub_alloc_"))

        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.subscription_balance, 40000)
        self.assertEqual(self.wallet.available_credits, 40000)

    def test_allocate_subscription_credits_idempotency(self):
        allocate_subscription_credits(
            self.db,
            subscription_id=self.subscription.id,
            user_id=self.user.id,
            plan_id="pro",
            period_start=self.subscription.current_period_start
        )
        self.db.commit()

        with self.assertRaises(AllocationIdempotencyError):
            allocate_subscription_credits(
                self.db,
                subscription_id=self.subscription.id,
                user_id=self.user.id,
                plan_id="pro",
                period_start=self.subscription.current_period_start
            )

        self.db.rollback()

        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.subscription_balance, 40000)

    def test_purchase_initialization(self):
        purchase = initialize_purchase(
            self.db,
            user_id=self.user.id,
            product_id="credit_medium",
            payment_provider="paystack",
            payment_reference="txn_12345"
        )
        self.db.commit()

        self.assertEqual(purchase.status, PurchaseStatus.PENDING)
        self.assertEqual(purchase.price_amount, 5000)
        self.assertEqual(purchase.credit_allocation, 20000)

        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.purchased_balance, 0)

        tx = self.db.query(LedgerTransaction).filter_by(transaction_type=TransactionType.PURCHASE).first()
        self.assertIsNone(tx)

    def test_successful_fulfillment(self):
        purchase = initialize_purchase(
            self.db,
            user_id=self.user.id,
            product_id="credit_medium",
            payment_provider="paystack",
            payment_reference="txn_123"
        )
        self.db.commit()

        fulfilled = fulfill_purchase(
            self.db,
            purchase_id=purchase.id,
            verified_amount=5000,
            verified_currency="NGN",
            provider_transaction_id="prov_123"
        )
        self.db.commit()

        self.assertEqual(fulfilled.status, PurchaseStatus.SUCCESS)
        self.assertIsNotNone(fulfilled.paid_at)
        self.assertEqual(fulfilled.provider_transaction_id, "prov_123")

        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.purchased_balance, 20000)

        tx = self.db.query(LedgerTransaction).filter_by(transaction_type=TransactionType.PURCHASE).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 20000)
        self.assertEqual(tx.reference_id, f"purchase_{purchase.id}")

    def test_already_successful_purchase(self):
        purchase = initialize_purchase(
            self.db,
            user_id=self.user.id,
            product_id="credit_medium",
            payment_provider="paystack",
            payment_reference="txn_123"
        )
        self.db.commit()

        fulfill_purchase(self.db, purchase.id)
        self.db.commit()

        with self.assertRaises(AllocationIdempotencyError):
            fulfill_purchase(self.db, purchase.id)

        self.db.rollback()

        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.purchased_balance, 20000)

        txs = self.db.query(LedgerTransaction).filter_by(transaction_type=TransactionType.PURCHASE).all()
        self.assertEqual(len(txs), 1)

    def test_amount_mismatch(self):
        purchase = initialize_purchase(
            self.db,
            user_id=self.user.id,
            product_id="credit_medium",
            payment_provider="paystack",
            payment_reference="txn_123"
        )
        self.db.commit()

        with self.assertRaises(AllocationError):
            fulfill_purchase(
                self.db,
                purchase_id=purchase.id,
                verified_amount=1000
            )

        self.db.rollback()
        self.db.refresh(purchase)
        self.assertEqual(purchase.status, PurchaseStatus.PENDING)

        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.purchased_balance, 0)

    def test_currency_mismatch(self):
        purchase = initialize_purchase(
            self.db,
            user_id=self.user.id,
            product_id="credit_medium",
            payment_provider="paystack",
            payment_reference="txn_123"
        )
        self.db.commit()

        with self.assertRaises(AllocationError):
            fulfill_purchase(
                self.db,
                purchase_id=purchase.id,
                verified_currency="USD"
            )

        self.db.rollback()
        self.db.refresh(purchase)
        self.assertEqual(purchase.status, PurchaseStatus.PENDING)

    def test_failed_purchase_cannot_be_fulfilled(self):
        purchase = initialize_purchase(
            self.db,
            user_id=self.user.id,
            product_id="credit_medium",
            payment_provider="paystack",
            payment_reference="txn_123"
        )
        purchase.status = PurchaseStatus.FAILED
        self.db.commit()

        with self.assertRaises(AllocationError):
            fulfill_purchase(self.db, purchase.id)

        self.db.rollback()
