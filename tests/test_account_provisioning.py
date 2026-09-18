import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.user import User
from app.crud.user import create_user, get_user_by_email
from app.schemas.user import UserCreate
from app.models.wallet import Wallet
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.ledger import LedgerTransaction, TransactionType
from app.services.account_provisioning import provision_new_user_account


class TestAccountProvisioning(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:', connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_new_user_registration_provisions_account(self):
        user_in = UserCreate(
            first_name="Test",
            last_name="User",
            email="provision1@example.com",
            password="password12345"
        )
        user = create_user(self.db, user_in)
        self.assertIsNotNone(user.id)

        # Check Wallet
        wallet = self.db.query(Wallet).filter(Wallet.user_id == user.id).first()
        self.assertIsNotNone(wallet)
        self.assertEqual(wallet.subscription_balance, 1000)
        self.assertEqual(wallet.purchased_balance, 0)
        self.assertEqual(wallet.reserved_balance, 0)
        self.assertEqual(wallet.available_credits, 1000)

        # Check Subscription
        sub = self.db.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).first()
        self.assertIsNotNone(sub)
        self.assertEqual(sub.plan_id, "free")

        # Check Ledger
        ledger = self.db.query(LedgerTransaction).filter(
            LedgerTransaction.wallet_id == wallet.id,
            LedgerTransaction.transaction_type == TransactionType.SUBSCRIPTION_ALLOCATION
        ).all()
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0].amount, 1000)

    def test_provisioning_idempotency(self):
        user_in = UserCreate(
            first_name="Test",
            last_name="User",
            email="provision2@example.com",
            password="password12345"
        )
        user = create_user(self.db, user_in)
        self.assertIsNotNone(user.id)

        # Call provisioning again on the same user
        provision_new_user_account(self.db, user.id)
        self.db.commit()
        self.db.expire_all()

        # Verify no duplication
        wallets = self.db.query(Wallet).filter(Wallet.user_id == user.id).all()
        ledgers = self.db.query(LedgerTransaction).filter(
            LedgerTransaction.wallet_id == wallets[0].id,
            LedgerTransaction.transaction_type == TransactionType.SUBSCRIPTION_ALLOCATION
        ).all()
        self.assertEqual(wallets[0].subscription_balance, 1000)

        subs = self.db.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).all()
        self.assertEqual(len(subs), 1)

        ledgers = self.db.query(LedgerTransaction).filter(
            LedgerTransaction.wallet_id == wallets[0].id,
            LedgerTransaction.transaction_type == TransactionType.SUBSCRIPTION_ALLOCATION
        ).all()
        self.assertEqual(len(ledgers), 1)

    def test_provisioning_failure_rolls_back_registration(self):
        import app.crud.user as crud_user
        
        # We need a way to mock the account provisioning failure during create_user
        # We can temporarily swap the function in the module where create_user imports it
        
        original_create_user = create_user
        
        def fail_provisioning(*args, **kwargs):
            raise ValueError("Simulated provisioning failure")
            
        import app.services.account_provisioning as account_provisioning
        original_provision = account_provisioning.provision_new_user_account
        account_provisioning.provision_new_user_account = fail_provisioning
        
        try:
            user_in = UserCreate(
                first_name="Test",
                last_name="User",
                email="provision3@example.com",
                password="password12345"
            )
            
            with self.assertRaises(ValueError) as ctx:
                original_create_user(self.db, user_in)
            self.assertEqual(str(ctx.exception), "Simulated provisioning failure")
            
            self.db.rollback() # Normally done by caller / FastAPI Depends
            
            # Registration should have been rolled back
            user = get_user_by_email(self.db, "provision3@example.com")
            self.assertIsNone(user)
        finally:
            account_provisioning.provision_new_user_account = original_provision

    def test_provisioning_integrity_error_rolls_back_registration(self):
        from sqlalchemy.exc import IntegrityError
        import app.crud.user as crud_user
        
        original_create_user = create_user
        
        def fail_provisioning_with_integrity_error(*args, **kwargs):
            raise IntegrityError("Simulated integrity error", params=None, orig=None)
            
        import app.services.account_provisioning as account_provisioning
        original_provision = account_provisioning.provision_new_user_account
        account_provisioning.provision_new_user_account = fail_provisioning_with_integrity_error
        
        try:
            user_in = UserCreate(
                first_name="Test",
                last_name="User",
                email="provision4@example.com",
                password="password12345"
            )
            
            with self.assertRaises(IntegrityError):
                original_create_user(self.db, user_in)
            
            self.db.rollback() # Typically done by caller
            
            # Verify nothing is left in the database
            user = get_user_by_email(self.db, "provision4@example.com")
            self.assertIsNone(user)
            
            # Since user wasn't created, we don't have an ID, but we can verify tables are empty or don't have this user's stuff
            # Because the DB might have rows from other tests if not rolled back, we can just check there are no users with this email
            
        finally:
            account_provisioning.provision_new_user_account = original_provision

if __name__ == "__main__":
    unittest.main()
