import sqlite3

def init_db():
	"""
	Initialise the platform database.
	Creates all required tables if they don't already exist.
	Run once during platform setup.
	"""
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()

	# Tenants table — stores all platform tenant data and Stripe mappings
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS tenants (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			tenant_id TEXT UNIQUE NOT NULL,
			company_name TEXT NOT NULL,
			email TEXT NOT NULL,
			stripe_customer_id TEXT NOT NULL,
			plan TEXT NOT NULL,
			stripe_price_id TEXT NOT NULL,
			stripe_connect_id TEXT,
			stripe_subscription_id TEXT,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)
	""")

	# Processed events table — used by webhook consumer for idempotency
	# Prevents the same Stripe event from being handled more than once
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS processed_events (
			event_id TEXT PRIMARY KEY,
			processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)
	""")

	conn.commit()
	conn.close()
	print("Database initialised successfully")

if __name__ == "__main__":
	init_db()
