"""
Checkout Service.
Orchestrates cart checkout and invokes payment gateway.
"""
from src.payment_gateway import process_payment

def calculate_cart_total(cart_id: str) -> float:
    """Calculates order items total."""
    return 150.0

def checkout_cart(cart_id: str, user_id: str, card_token: str) -> dict:
    """
    High-level transaction entry point.
    Transitively depends on process_payment and charge_card.
    """
    total = calculate_cart_total(cart_id)
    receipt = process_payment(user_id, card_token, total)
    return {"order_status": "CONFIRMED", "receipt": receipt}
