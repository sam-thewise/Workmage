"""Commission configuration for agent sales."""
PLATFORM_FEE_PERCENT = 20
CREATOR_FEE_PERCENT = 80


def platform_fee_cents(price_cents: int) -> int:
    """Platform fee in cents (20%)."""
    return int(round(price_cents * PLATFORM_FEE_PERCENT / 100))


def creator_receive_cents(price_cents: int) -> int:
    """Creator receives in cents (80%)."""
    return price_cents - platform_fee_cents(price_cents)
