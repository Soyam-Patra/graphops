"""
Payment Gateway Service.
Handles token validation and card charging.
"""

def validate_token(token: str) -> bool:
    """Validates user payment token."""
    return bool(token and len(token) >= 8)

def check_account_balance(user_id: str) -> float:
    """Checks user balance."""
    return 1000.0

def charge_card(card_token: str, amount: float) -> dict:
    """Charges the payment card. Critical leaf function."""
    if not validate_token(card_token):
        raise ValueError("Invalid payment token")
    fee = amount * 0.02
    total = amount + fee
    return {"status": "CHARGED", "amount": total, "fee": fee}

def process_payment(user_id: str, card_token: str, amount: float) -> dict:
    """Direct caller of charge_card and balance checks."""
    balance = check_account_balance(user_id)
    if balance < amount:
        raise ValueError("Insufficient balance")
    return charge_card(card_token, amount)
