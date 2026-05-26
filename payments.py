import stripe
import os
import sqlite3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def get_tenant(tenant_id):
    """
    Retrieve tenant details from the local database.
    Returns stripe_customer_id, stripe_connect_id, and plan.
    """
    conn = sqlite3.connect("platform.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT stripe_customer_id, stripe_connect_id, plan
        FROM tenants
        WHERE tenant_id = ?
    """, (tenant_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def process_payment(tenant_id, amount, currency="eur"):
    """
    Process a destination charge for a tenant's customer payment.
    
    - Collects the full amount from the customer
    - Deducts a 10% platform fee
    - Routes the remainder to the tenant's connected account
    
    Amount should be in the smallest currency unit (e.g. cents)
    """
    # Get tenant details from database
    tenant = get_tenant(tenant_id)

    if not tenant:
        print(f"Tenant not found: {tenant_id}")
        return None

    stripe_customer_id, stripe_connect_id, plan = tenant

    # Calculate platform fee (10% of total amount)
    platform_fee = int(amount * 0.10)

    print(f"\nProcessing payment for {tenant_id}")
    print(f"Amount: €{amount/100}")
    print(f"Platform fee: €{platform_fee/100}")
    print(f"Tenant receives: €{(amount - platform_fee)/100}")

    # Create PaymentIntent with destination charge
    # pm_card_visa is a Stripe test PaymentMethod — replace with real
    # payment method in production
    payment_intent = stripe.PaymentIntent.create(
        amount=amount,
        customer=stripe_customer_id,
        currency=currency,
        payment_method="pm_card_visa",
        confirm=True,
        transfer_data={
            "destination": stripe_connect_id,  # tenant's connected account
        },
        application_fee_amount=platform_fee,  # platform's cut
        idempotency_key=f"{tenant_id}-payment-{amount}-v4",
        automatic_payment_methods={
            "enabled": True,
            "allow_redirects": "never"  # required for server-side confirmation
        }
    )

    print(f"\nPayment status: {payment_intent.status}")
    print(f"Payment ID: {payment_intent.id}")
    return payment_intent

if __name__ == "__main__":
    # Test payment for EuroTech GmbH — EUR to EUR, no conversion fee
    process_payment("tenant_004", 10000)
