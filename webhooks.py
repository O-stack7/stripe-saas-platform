import stripe
import os
import sqlite3
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

# Initialise Flask web application
app = Flask(__name__)

def is_event_processed(event_id):
	"""
	Check if a webhook event has already been processed.
	Uses the processed_events table for idempotency.
	Returns True if already processed, False if new.
	"""
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute(
		"SELECT event_id FROM processed_events WHERE event_id = ?",
		(event_id,)
	)
	exists = cursor.fetchone() is not None
	conn.close()
	return exists

def mark_event_processed(event_id):
	"""
	Record a webhook event ID as processed in the database.
	Prevents duplicate processing if Stripe retries delivery.
	"""
	conn = sqlite3.connect("platform.db")
	cursor = conn.cursor()
	cursor.execute(
		"INSERT OR IGNORE INTO processed_events (event_id) VALUES (?)",
		(event_id,)
	)
	conn.commit()
	conn.close()

@app.route("/webhook", methods=["POST"])
def webhook():
	"""
	Main webhook endpoint. Receives all Stripe events.

	1. Verifies the event signature to confirm it came from Stripe
	2. Checks idempotency — skips already processed events
	3. Routes event to the appropriate handler
	4. Always returns 200 so Stripe knows the event was received
	"""
	payload = request.data
	sig_header = request.headers.get("Stripe-Signature")

	# Verify the event came from Stripe using webhook secret
	try:
		event = stripe.Webhook.construct_event(
			payload, sig_header, webhook_secret
		)
	except ValueError:
		print("Invalid payload")
		return jsonify({"error": "Invalid payload"}), 400
	except stripe.error.SignatureVerificationError:
		print("Invalid signature")
		return jsonify({"error": "Invalid signature"}), 403

	# Idempotency check — skip if already processed
	if is_event_processed(event["id"]):
		print(f"Event already processed: {event['id']}")
		return jsonify({"status": "already processed"}), 200

	# Mark event as processed before handling
	mark_event_processed(event["id"])

	# Route event to appropriate handler
	if event["type"] == "invoice.payment_succeeded":
		handle_payment_succeeded(event["data"]["object"])
	elif event["type"] == "invoice.payment_failed":
		handle_payment_failed(event["data"]["object"])
	elif event["type"] == "customer.subscription.deleted":
		handle_subscription_cancelled(event["data"]["object"])
	elif event["type"] == "charge.failed" and event.get("account"):
		handle_connect_payment_failed(event)

	return jsonify({"status": "success"}), 200

def handle_payment_succeeded(invoice):
	"""
	Handle successful subscription payment.
	In production: confirm tenant access, update billing records.
	"""
	customer_id = invoice["customer"]
	print(f"\nPayment succeeded for customer: {customer_id}")
	print(f"Amount paid: {invoice['currency'].upper()} {invoice['amount_paid']/100}")

def handle_payment_failed(invoice):
	"""
	Handle failed subscription payment.
	In production: notify tenant, flag account as past_due,
	begin dunning sequence.
	"""
	customer_id = invoice["customer"]
	print(f"\nPayment failed for customer: {customer_id}")
	print(f"Amount due: {invoice['currency'].upper()} {invoice['amount_due']/100}")
	print(f"Action required: notify tenant to update payment method")

def handle_subscription_cancelled(subscription):
	"""
	Handle subscription cancellation after all retries exhausted.
	In production: revoke tenant access, send cancellation notice.
	"""
	customer_id = subscription["customer"]
	print(f"\nSubscription cancelled for customer: {customer_id}")
	print("Action required: revoke tenant platform access")

def handle_connect_payment_failed(event):
	"""
	Handle failed charge on a tenant's connected account.
	Fires when a tenant's customer payment fails.
	In production: notify tenant to investigate and follow up
	with their customer.
	"""
	account_id = event.get("account")
	charge = event["data"]["object"]
	amount = charge["amount"] / 100
	currency = charge["currency"].upper()

	print(f"\nConnect payment failed")
	print(f"Connected account: {account_id}")
	print(f"Amount: {currency} {amount}")
	print(f"Failure message: {charge.get('failure_message', 'Unknown')}")
	print(f"Action: notify tenant to investigate failed charge")

if __name__ == "__main__":
	# Start Flask development server on port 4242
	app.run(port=4242, debug=True)
