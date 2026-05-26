import stripe
import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def get_tenant(tenant_id):
	"""
	Retrieve tenant details from the local database.
	Returns stripe_customer_id, stripe_price_id, and plan.
	"""
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		SELECT stripe_customer_id, stripe_price_id, plan
		FROM tenants
		WHERE tenant_id = ?
	""", (tenant_id,))
	row = cursor.fetchone()
	conn.close()
	return row

def attach_payment_method(customer_id):
	"""
	Attach a test payment method to a Stripe Customer.
	Sets it as the default for future subscription charges.
	
	In production: customer provides card details via Stripe.js
	on the frontend. The backend receives and attaches the
	resulting PaymentMethod ID.
	"""
	# Attach pm_card_visa test PaymentMethod to customer
	payment_method = stripe.PaymentMethod.attach(
		"pm_card_visa",
		customer=customer_id,
	)

	# Set as default payment method for invoices
	stripe.Customer.modify(
		customer_id,
		invoice_settings={
			"default_payment_method": payment_method.id
		}
	)

	print(f"Payment method attached: {payment_method.id}")
	return payment_method.id

def create_subscription(tenant_id):
	"""
	Enroll a tenant on their assigned subscription plan.
	
	1. Attaches a payment method to the customer
	2. Creates a Stripe Subscription linked to their Price
	3. Saves the subscription ID to the database
	
	Once created, Stripe automatically generates invoices and
	collects payment on each billing cycle.
	"""
	tenant = get_tenant(tenant_id)

	if not tenant:
		print(f"Tenant not found: {tenant_id}")
		return None

	stripe_customer_id, stripe_price_id, plan = tenant

	# Attach payment method before creating subscription
	attach_payment_method(stripe_customer_id)

	# Create subscription linked to tenant's assigned Price
	subscription = stripe.Subscription.create(
		customer=stripe_customer_id,
		items=[{"price": stripe_price_id}],
		idempotency_key=f"{tenant_id}-subscription-v1"
	)

	# Save subscription ID to database
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		UPDATE tenants
		SET stripe_subscription_id = ?
		WHERE tenant_id = ?
	""", (subscription.id, tenant_id))
	conn.commit()
	conn.close()

	print(f"\nSubscription created for {tenant_id}")
	print(f"Plan: {plan}")
	print(f"Status: {subscription.status}")
	print(f"Subscription ID: {subscription.id}")
	return subscription

def get_upcoming_invoice(tenant_id):
	"""
	Retrieve the upcoming invoice for a tenant's subscription.
	Shows what the tenant will be charged at end of current billing cycle.
	"""
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		SELECT stripe_subscription_id, plan
		FROM tenants
		WHERE tenant_id = ?
	""", (tenant_id,))
	row = cursor.fetchone()
	conn.close()

	if not row:
		print(f"Tenant not found: {tenant_id}")
		return None

	stripe_subscription_id, plan = row

	invoice = stripe.Invoice.create_preview(
		subscription=stripe_subscription_id
	)

	# Convert Unix timestamps to readable dates
	period_start = datetime.fromtimestamp(invoice.period_start).strftime("%d %B %Y")
	period_end = datetime.fromtimestamp(invoice.period_end).strftime("%d %B %Y")

	print(f"\nUpcoming invoice for {tenant_id}")
	print(f"Plan: {plan}")
	print(f"Amount due: {invoice.currency.upper()} {invoice.amount_due/100}")
	print(f"Period start: {period_start}")
	print(f"Period end: {period_end}")

	return invoice

def upgrade_plan(tenant_id, new_plan):
	"""
	Upgrade a tenant to a higher pricing tier mid-cycle.
	
	Uses proration_behavior="always_invoice" to immediately charge
	the prorated difference between old and new plan prices.
	Both Stripe and the local database are updated.
	"""
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		SELECT stripe_subscription_id, plan
		FROM tenants
		WHERE tenant_id = ?
	""", (tenant_id,))
	row = cursor.fetchone()
	conn.close()

	if not row:
		print(f"Tenant not found: {tenant_id}")
		return None

	stripe_subscription_id, current_plan = row

	# Map new plan name to Stripe Price ID
	price_map = {
		"starter": os.getenv("STARTER_PRICE_ID"),
		"pro": os.getenv("PRO_PRICE_ID"),
		"enterprise": os.getenv("ENTERPRISE_PRICE_ID")
	}

	new_price_id = price_map.get(new_plan)

	if not new_price_id:
		print(f"Invalid plan: {new_plan}")
		return None

	# Retrieve subscription to get the subscription item ID
	subscription = stripe.Subscription.retrieve(stripe_subscription_id)
	subscription_item_id = subscription["items"]["data"][0].id

	# Update subscription with new price — prorate immediately
	updated_subscription = stripe.Subscription.modify(
		stripe_subscription_id,
		items=[{
			"id": subscription_item_id,
			"price": new_price_id
		}],
		proration_behavior="always_invoice"  # charge difference immediately
	)

	# Update database to reflect new plan — always update Stripe first
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		UPDATE tenants
		SET plan = ?, stripe_price_id = ?
		WHERE tenant_id = ?
	""", (new_plan, new_price_id, tenant_id))
	conn.commit()
	conn.close()

	print(f"\n{tenant_id} upgraded from {current_plan} to {new_plan}")
	return updated_subscription

def cancel_subscription(tenant_id):
	"""
	Cancel a tenant's subscription immediately.
	
	Updates both Stripe and the local database.
	The Stripe Customer object is preserved — tenant can resubscribe later.
	"""
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		SELECT stripe_subscription_id, plan
		FROM tenants
		WHERE tenant_id = ?
	""", (tenant_id,))
	row = cursor.fetchone()
	conn.close()

	if not row:
		print(f"Tenant not found: {tenant_id}")
		return None

	stripe_subscription_id, plan = row

	# Check if subscription exists before attempting cancellation
	if not stripe_subscription_id:
		print(f"No active subscription found for {tenant_id}")
		return None

	# Cancel subscription in Stripe
	cancelled_subscription = stripe.Subscription.cancel(
		stripe_subscription_id
	)

	# Update database — always update Stripe first
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		UPDATE tenants
		SET stripe_subscription_id = NULL,
			plan = 'cancelled'
		WHERE tenant_id = ?
	""", (tenant_id,))
	conn.commit()
	conn.close()

	print(f"\nSubscription cancelled for {tenant_id}")
	print(f"Previous plan: {plan}")
	print(f"Status: {cancelled_subscription.status}")
	return cancelled_subscription

if __name__ == "__main__":
	create_subscription("tenant_001")
	create_subscription("tenant_002")
	create_subscription("tenant_003")
	create_subscription("tenant_004")
	upgrade_plan("tenant_002", "pro")
	cancel_subscription("tenant_003")
	get_upcoming_invoice("tenant_001")
