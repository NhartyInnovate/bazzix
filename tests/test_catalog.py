import unittest
from app.services.catalog import (
    SUBSCRIPTION_PLANS,
    CREDIT_PACKS,
    get_subscription_plan,
    get_credit_pack
)

class TestCatalog(unittest.TestCase):
    def test_all_subscription_plans_exist(self):
        plans = ["free", "starter", "pro", "power"]
        for p in plans:
            plan = get_subscription_plan(p)
            self.assertIsNotNone(plan)
            self.assertEqual(plan.id, p)
            self.assertTrue(plan.is_active)
            self.assertTrue(isinstance(plan.price_ngn, int))
            self.assertTrue(isinstance(plan.credits_per_month, int))
            
    def test_free_plan_details(self):
        plan = get_subscription_plan("free")
        self.assertEqual(plan.price_ngn, 0)
        self.assertEqual(plan.credits_per_month, 1000)

    def test_starter_plan_details(self):
        plan = get_subscription_plan("starter")
        self.assertEqual(plan.price_ngn, 2500)
        self.assertEqual(plan.credits_per_month, 10000)

    def test_all_credit_packs_exist(self):
        packs = ["credit_small", "credit_medium", "credit_large", "credit_mega"]
        for p in packs:
            pack = get_credit_pack(p)
            self.assertIsNotNone(pack)
            self.assertEqual(pack.id, p)
            self.assertTrue(pack.is_active)
            self.assertTrue(isinstance(pack.price_ngn, int))
            self.assertTrue(isinstance(pack.credit_amount, int))

    def test_small_pack_details(self):
        pack = get_credit_pack("credit_small")
        self.assertEqual(pack.price_ngn, 1500)
        self.assertEqual(pack.credit_amount, 5000)

    def test_mega_pack_details(self):
        pack = get_credit_pack("credit_mega")
        self.assertEqual(pack.price_ngn, 25000)
        self.assertEqual(pack.credit_amount, 150000)
