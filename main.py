import os
from dotenv import load_dotenv
from database import init_db
from setup_products import create_products_and_prices
from setup_tenants import create_tenant
from connect import create_connect_account, create_onboarding_link

# Load environment variables from .env file
load_dotenv()

def main():
	"""
	Platform entry point — runs automated setup and guides manual steps.
	
	Automated steps (run sequentially):
	1. Initialise database
	2. Create Stripe Product and pricing tiers
	3. Onboard tenants as Stripe Customers
	
	Manual steps (instructions provided):
	4. Complete Connect account onboarding via browser
	5. Enroll tenants on subscriptions
	6. Start webhook consumer
	7. Test failure handling
	"""
	print("=" * 50)
	print("Multi-Tenant SaaS Billing Platform")
	print("=" * 50)

	# Step 1 — Initialise database schema
	print("\nStep 1: Initialising database...")
	init_db()

	# Step 2 — Create Product and pricing tiers in Stripe
	# Save returned Price IDs to .env file
	print("\nStep 2: Setting up products and prices...")
	create_products_and_prices()

	# Step 3 — Onboard tenants as Stripe Customers
	# Database check prevents duplicates on subsequent runs
	print("\nStep 3: Onboarding tenants...")
	create_tenant("tenant_001", "Acme Corp", "billing@acmecorp.com", "pro")
	create_tenant("tenant_002", "GlobalTech Ltd", "billing@globaltechltd.com", "starter")
	create_tenant("tenant_003", "Nova Systems", "billing@novasystems.com", "enterprise")
	create_tenant("tenant_004", "EuroTech GmbH", "billing@eurotechgmbh.com", "starter")

	# Step 4 — Connect accounts require manual onboarding via browser
	print("\nStep 4: Setting up Connect accounts...")
	print("Run: python connect.py")
	print("Complete onboarding via the generated links")
	print("Test tokens: DOB 1901-01-01, Address: address_full_match, ID: 000000000")

	# Step 5 — Subscriptions require Connect onboarding to be complete first
	print("\nStep 5: Subscriptions")
	print("Run: python subscriptions.py")

	# Step 6 — Webhook consumer requires a continuously running server
	print("\nStep 6: Webhooks")
	print("Terminal 1: stripe listen --forward-to localhost:5000/webhook --forward-connect-to localhost:5000/webhook")
	print("Terminal 2: python webhooks.py")

	# Step 7 — Failure handling simulation
	print("\nStep 7: Failure handling")
	print("Run: python failure_handling.py")

	print("\n" + "=" * 50)
	print("Platform setup complete!")
	print("=" * 50)

if __name__ == "__main__":
	main()
