"""
Unit tests for Checkout and Payment Gateway.
"""
import unittest
from src.payment_gateway import validate_token, charge_card, process_payment
from src.checkout_service import checkout_cart

class TestPaymentSystem(unittest.TestCase):
    def test_validate_token(self):
        self.assertTrue(validate_token("tok_visa_valid_9988"))
        self.assertFalse(validate_token("short"))

    def test_charge_card(self):
        result = charge_card("tok_visa_valid_9988", 100.0)
        self.assertEqual(result["status"], "CHARGED")
        self.assertEqual(result["amount"], 102.0)

    def test_checkout_cart_end_to_end(self):
        res = checkout_cart("cart_991", "usr_442", "tok_visa_valid_9988")
        self.assertEqual(res["order_status"], "CONFIRMED")
        self.assertEqual(res["receipt"]["status"], "CHARGED")

if __name__ == "__main__":
    unittest.main()
