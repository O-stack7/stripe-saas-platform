import stripe
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def create_products_and_prices():
	"""
	Create the platform's Product and pricing tiers in Stripe.
	Run once during initial platform setup.
	
	Creates:
	- One Product: SaaS Platform Subscription
	- Three Prices: Starter €29, Pro €79, Enterprise €199 (monthly)
	
	Returns the three Price IDs for storage in .env
	"""
	# Create the Product — represents what we are selling
	product = stripe.Product.create(
		name="SaaS Platform Subscription",
		metadata={"platform": "stripe-saas-platform"}
	)

	print(f"\nProduct created: {product.id}")

	# Create monthly recurring prices for each tier
	starter_price = stripe.Price.create(
		product=product.id,
		unit_amount=2900,  # €29.00 in cents
		currency="eur",
		recurring={"interval": "month"},
		metadata={"plan": "starter"}
	)

	pro_price = stripe.Price.create(
		product=product.id,
		unit_amount=7900,  # €79.00 in cents
		currency="eur",
		recurring={"interval": "month"},
		metadata={"plan": "pro"}
	)

	enterprise_price = stripe.Price.create(
		product=product.id,
		unit_amount=19900,  # €199.00 in cents
		currency="eur",
		recurring={"interval": "month"},
		metadata={"plan": "enterprise"}
	)

	print(f"Starter: {starter_price.id} — €{starter_price.unit_amount/100}/month")
	print(f"Pro: {pro_price.id} — €{pro_price.unit_amount/100}/month")
	print(f"Enterprise: {enterprise_price.id} — €{enterprise_price.unit_amount/100}/month")

	return starter_price.id, pro_price.id, enterprise_price.id

if __name__ == "__main__":
	create_products_and_prices()
