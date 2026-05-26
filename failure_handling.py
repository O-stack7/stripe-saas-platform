import stripe
import os
import sqlite3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def simulate_card_decline(tenant_id, decline_type="card_declined"):
	"""
	Simulate different card decline scenarios using Stripe test PaymentMethods.
	
	Decline types:
	- card_declined: generic card decline
	- insufficient_funds: customer has insufficient funds
	- expired_card: card has expired
	
	Note: Decline PaymentMethods cannot be attached to Customer objects.
	They are used directly in PaymentIntents without a customer parameter.
	"""
	# Map decline types to Stripe test PaymentMethod IDs
	decline_cards = {
		"card_declined": "pm_card_visa_chargeDeclined",
		"insufficient_funds": "pm_card_visa_chargeDeclinedInsufficientFunds",
		"expired_card": "pm_card_chargeDeclinedExpiredCard"
	}

	token = decline_cards.get(decline_type)

	if not token:
		print(f"Unknown decline type: {decline_type}")
		return None

	# Get tenant details from database
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		SELECT stripe_customer_id
		FROM tenants
		WHERE tenant_id = ?
	""", (tenant_id,))
	row = cursor.fetchone()
	conn.close()

	if not row:
		print(f"Tenant not found: {tenant_id}")
		return None

	print(f"\nSimulating {decline_type} for {tenant_id}")

	try:
		# Attempt payment with decline test card
		# No customer parameter — decline cards cannot be attached to customers
		payment_intent = stripe.PaymentIntent.create(
			amount=1000,
			currency="eur",
			payment_method=token,
			confirm=True,
			automatic_payment_methods={
				"enabled": True,
				"allow_redirects": "never"
			}
		)
		print(f"Payment status: {payment_intent.status}")

	except stripe.error.CardError as e:
		# Card was immediately declined — handle gracefully
		print(f"Card declined: {e.code}")
		print(f"Decline message: {e.user_message}")
		return e

def simulate_dunning_sequence(tenant_id):
	"""
	Simulate the full dunning workflow when a subscription payment fails.
	
	Dunning is the process of communicating with customers about failed
	payments and retrying until payment succeeds or subscription is cancelled.
	
	Stripe handles: automatic retries via Smart Retries
	Platform handles: tenant notifications, access management, database updates
	"""
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		SELECT stripe_customer_id, plan
		FROM tenants
		WHERE tenant_id = ?
	""", (tenant_id,))
	row = cursor.fetchone()
	conn.close()

	if not row:
		print(f"Tenant not found: {tenant_id}")
		return None

	stripe_customer_id, plan = row

	print(f"\nSimulating dunning sequence for {tenant_id}")
	print(f"Plan: {plan}")

	# Day 1 — Payment fails, platform notifies tenant
	print("\nDay 1 - Payment failed")
	print(f"Action: Email sent to tenant notifying of payment failure")
	print(f"Action: Account flagged as past_due in platform")

	# Update database to reflect past_due status
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		UPDATE tenants
		SET plan = 'past_due'
		WHERE tenant_id = ?
	""", (tenant_id,))
	conn.commit()
	conn.close()
	print(f"Database updated: {tenant_id} status set to past_due")

	# Day 3 — Stripe retries automatically via Smart Retries
	print("\nDay 3 - Stripe retries payment automatically via Smart Retries")
	print(f"Action: Platform waits for invoice.payment_failed or invoice.payment_succeeded webhook")

	# Day 7 — Second reminder
	print("\nDay 7 - Payment still outstanding")
	print(f"Action: Second reminder email sent to tenant")
	print(f"Action: Platform restricts access to non-essential features")

	# Day 14 — Final warning
	print("\nDay 14 - Final warning")
	print(f"Action: Final email sent — subscription will be cancelled in 7 days")

	# Day 21 — All retries exhausted, subscription cancelled
	print("\nDay 21 - All retries exhausted")
	print(f"Action: Stripe fires customer.subscription.deleted webhook")
	print(f"Action: Platform revokes tenant access completely")

	# Update database to reflect cancellation
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		UPDATE tenants
		SET plan = 'cancelled',
			stripe_subscription_id = NULL
		WHERE tenant_id = ?
	""", (tenant_id,))
	conn.commit()
	conn.close()
	print(f"Database updated: {tenant_id} status set to cancelled")

def simulate_3ds_payment(tenant_id):
	"""
	Simulate a payment requiring 3D Secure authentication.
	
	3DS is required for most European card payments under SCA regulations.
	When triggered, the PaymentIntent moves to requires_action state.
	
	In production:
	- Stripe.js handles the redirect to the bank's authentication page
	- Customer verifies identity with their bank
	- Outcome delivered via payment_intent.succeeded or
	  payment_intent.payment_failed webhook
	
	We set allow_redirects: never to force the requires_action state
	since we have no frontend to handle the redirect.
	"""
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		SELECT stripe_customer_id
		FROM tenants
		WHERE tenant_id = ?
	""", (tenant_id,))
	row = cursor.fetchone()
	conn.close()

	if not row:
		print(f"Tenant not found: {tenant_id}")
		return None

	stripe_customer_id = row[0]

	print(f"\nSimulating 3DS payment for {tenant_id}")

	try:
		payment_intent = stripe.PaymentIntent.create(
			amount=1000,
			currency="eur",
			payment_method="pm_card_threeDSecure2Required",
			confirm=True,
			automatic_payment_methods={
				"enabled": True,
				"allow_redirects": "never"  # forces requires_action without frontend
			}
		)

		if payment_intent.status == "succeeded":
			print(f"Payment succeeded immediately — no 3DS required")

		elif payment_intent.status == "requires_action":
			print(f"3DS authentication required")
			print(f"In production: Stripe.js redirects customer to authenticate with their bank")
			print(f"Platform action: wait for payment_intent.succeeded or payment_intent.payment_failed webhook")

	except stripe.error.CardError as e:
		# Card immediately declined before 3DS authentication
		print(f"Card immediately declined: {e.code}")
		print(f"Decline message: {e.user_message}")
		print(f"No 3DS attempted — card was rejected before authentication")

if __name__ == "__main__":
	# Test card decline scenarios
	simulate_card_decline("tenant_001", "card_declined")
	simulate_card_decline("tenant_001", "insufficient_funds")
	simulate_card_decline("tenant_001", "expired_card")

	# Test 3DS authentication
	simulate_3ds_payment("tenant_001")
