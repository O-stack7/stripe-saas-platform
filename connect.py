import stripe
import os
import sqlite3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def create_connect_account(tenant_id, email, company_name, country="US"):
	"""
	Create a Stripe Connect Express account for a tenant.
	
	Express accounts allow Stripe to handle KYC compliance and
	onboarding — the platform never touches sensitive identity data.
	
	1. Checks database first — returns existing account if already created
	2. Creates Express connected account via Stripe API
	3. Saves the connected account ID to the database
	
	In production: European accounts use country="DE" with test tokens
	DOB: 1901-01-01, Address: address_full_match, ID: 000000000
	"""
	# Check database first — avoid creating duplicate connected accounts
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		SELECT stripe_connect_id FROM tenants
		WHERE tenant_id = ?
	""", (tenant_id,))
	existing = cursor.fetchone()
	conn.close()

	if existing and existing[0]:
		print(f"Connected account already exists for {tenant_id}: {existing[0]}")
		return existing[0]

	# Create Express connected account
	# Express: Stripe handles KYC, onboarding, and compliance
	account = stripe.Account.create(
		type="express",
		country=country,
		email=email,
		capabilities={
			"card_payments": {"requested": True},
			"transfers": {"requested": True},
		},
		business_profile={
			"name": company_name
		},
		idempotency_key=f"{tenant_id}-create-connect-account-V4"
	)

	print(f"\nConnected account created: {account.id}")

	# Save connected account ID to database
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute("""
		UPDATE tenants
		SET stripe_connect_id = ?
		WHERE tenant_id = ?
	""", (account.id, tenant_id))
	conn.commit()
	conn.close()

	print(f"Connect ID saved for {tenant_id}")
	return account.id

def create_onboarding_link(account_id):
	"""
	Generate a Stripe-hosted onboarding link for a connected account.
	
	The tenant clicks this link to provide their business details,
	bank account, and identity verification directly to Stripe.
	The platform never handles sensitive financial data.
	
	refresh_url: where to redirect if the link expires
	return_url: where to redirect after successful onboarding
	"""
	link = stripe.AccountLink.create(
		account=account_id,
		refresh_url="http://localhost:5000/reauth",
		return_url="http://localhost:5000/return",
		type="account_onboarding"
	)

	print(f"\nOnboarding link: {link.url}")
	return link.url

if __name__ == "__main__":
	for tenant in [
		("tenant_001", "billing@acmecorp.com", "Acme Corp", "DE"),
		("tenant_002", "billing@globaltechltd.com", "GlobalTech Ltd", "DE"),
		("tenant_003", "billing@novasystems.com", "Nova Systems", "DE"),
		("tenant_004", "billing@eurotechgmbh.com", "EuroTech GmbH", "DE"),
	]:
		account_id = create_connect_account(tenant[0], tenant[1], tenant[2], tenant[3])
		create_onboarding_link(account_id)
