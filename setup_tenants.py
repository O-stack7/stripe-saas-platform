import stripe
import os
import sqlite3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def create_tenant(tenant_id, company_name, email, plan):
	"""
	Onboard a new tenant to the platform.
	
	1. Checks database first — returns existing customer if already onboarded
	2. Creates a Stripe Customer object with tenant metadata
	3. Persists the tenant-to-Stripe mapping in the local database
	
	This prevents duplicate Stripe Customers if called multiple times
	for the same tenant (beyond the 24hr idempotency key window).
	"""
	# Map plan names to Stripe Price IDs from .env
	price_map = {
		"starter": os.getenv("STARTER_PRICE_ID"),
		"pro": os.getenv("PRO_PRICE_ID"),
		"enterprise": os.getenv("ENTERPRISE_PRICE_ID")
	}

	stripe_price_id = price_map.get(plan)

	if not stripe_price_id:
		print(f"Invalid plan: {plan}")
		return None

	# Check database first — avoid creating duplicate Stripe Customers
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		SELECT stripe_customer_id FROM tenants
		WHERE tenant_id = ?
	""", (tenant_id,))
	existing = cursor.fetchone()
	conn.close()

	if existing:
		print(f"Tenant already exists: {tenant_id} — {existing[0]}")
		return existing[0]

	# Create Stripe Customer with metadata tagging tenant details
	customer = stripe.Customer.create(
		name=company_name,
		email=email,
		metadata={
			"tenant_id": tenant_id,
			"plan": plan
		},
		idempotency_key=f"{tenant_id}-create-customer"
	)

	print(f"\nCustomer created: {customer.id}")

	# Persist tenant-to-Stripe mapping in local database
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		INSERT OR IGNORE INTO tenants
		(tenant_id, company_name, email, stripe_customer_id, plan, stripe_price_id)
		VALUES (?, ?, ?, ?, ?, ?)
	""", (tenant_id, company_name, email, customer.id, plan, stripe_price_id))

	conn.commit()
	conn.close()

	print(f"Tenant saved: {tenant_id} - {company_name} - {plan}")
	return customer.id

if __name__ == "__main__":
	create_tenant("tenant_001", "Acme Corp", "billing@acmecorp.com", "pro")
	create_tenant("tenant_002", "GlobalTech Ltd", "billing@globaltechltd.com", "starter")
	create_tenant("tenant_003", "Nova Systems", "billing@novasystems.com", "enterprise")
	create_tenant("tenant_004", "EuroTech GmbH", "billing@eurotechgmbh.com", "starter")
