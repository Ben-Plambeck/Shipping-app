from flask import Flask, request, jsonify
import requests
from requests_oauthlib import OAuth1
import json
import os

app = Flask(__name__)

SHOP = os.environ.get("SHOPIFY_SHOP", "jmb-brick-co.myshopify.com")
SHIPPO_API_KEY = os.environ.get("SHIPPO_API_KEY")

ORIGIN = {
    "name": "JMB Brick Co",
    "street1": "130 S Patterson Ave Unit 135",
    "city": "Goleta",
    "state": "CA",
    "zip": "93116",
    "country": "US",
    "phone": "8056965288"
}

# Load dimensions cache
cache_path = os.path.join(os.path.dirname(__file__), "dims_cache.json")
with open(cache_path) as f:
    DIMS_CACHE = json.load(f)
print(f"Loaded {len(DIMS_CACHE)} sets from cache")

CONSUMER_KEY    = os.environ.get("BL_CONSUMER_KEY",    "592D427AFDE64D58A7884EFA700F10C7")
CONSUMER_SECRET = os.environ.get("BL_CONSUMER_SECRET", "3594251FFA854191915E121187D2E269")
TOKEN_VALUE     = os.environ.get("BL_TOKEN_VALUE",     "C786B85CEC0849C69589676DBC1DEF46")
TOKEN_SECRET    = os.environ.get("BL_TOKEN_SECRET",    "895C0A261C6740B0A62DCB46D47DAA2C")
auth = OAuth1(CONSUMER_KEY, CONSUMER_SECRET, TOKEN_VALUE, TOKEN_SECRET)

def get_bricklink_data(set_number):
    if set_number in DIMS_CACHE:
        return DIMS_CACHE[set_number]
    try:
        url = f"https://api.bricklink.com/api/store/v1/items/SET/{set_number}"
        r = requests.get(url, auth=auth, timeout=5)
        if r.status_code == 200:
            return r.json().get("data", {})
    except:
        pass
    return {}

def get_shippo_rates(weight_g, dim_x_cm, dim_y_cm, dim_z_cm, to_zip, to_country="US"):
    length = max(float(dim_x_cm or 0), 6.0)
    width  = max(float(dim_y_cm or 0), 4.0)
    height = max(float(dim_z_cm or 0), 2.0)
    weight = max(float(weight_g or 0), 100.0)

    headers = {
        "Authorization": f"ShippoToken {SHIPPO_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "address_from": ORIGIN,
        "address_to": {
            "zip": to_zip,
            "country": to_country
        },
        "parcels": [{
            "length": str(round(length, 2)),
            "width":  str(round(width, 2)),
            "height": str(round(height, 2)),
            "distance_unit": "cm",
            "weight": str(round(weight, 2)),
            "mass_unit": "g"
        }],
        "async": False
    }

    print(f"Shippo request: weight={weight}g, dims={length}x{width}x{height}cm, to={to_zip}")

    try:
        r = requests.post(
            "https://api.goshippo.com/shipments/",
            headers=headers,
            json=payload,
            timeout=10
        )
        print(f"Shippo response status: {r.status_code}")

        if r.status_code != 200:
            print(f"Shippo error: {r.text}")
            return None

        rates = r.json().get("rates", [])
        print(f"Got {len(rates)} rates from Shippo")

        result = {}
        for rate in rates:
            service = rate.get("servicelevel", {}).get("token", "")
            price_cents = int(float(rate.get("amount", 0)) * 100)
            print(f"Rate found: {service} = ${rate.get('amount')}")

            if "ground_advantage" in service or "groundadvantage" in service:
                result["ground"] = price_cents
                result["ground_name"] = rate.get("servicelevel", {}).get("name", "USPS Ground Advantage")
            elif service == "usps_priority":
                result["priority"] = price_cents
                result["priority_name"] = rate.get("servicelevel", {}).get("name", "USPS Priority Mail")

        print(f"Parsed rates: {result}")
        return result

    except Exception as e:
        print(f"Shippo exception: {e}")
        return None

@app.route("/", methods=["GET"])
def home():
    return "JMB Brick Co Shipping Rate App is running!"

@app.route("/rates", methods=["POST"])
def rates():
    data = request.json
    print("RECEIVED:", data)

    rate_data    = data.get("rate", {})
    items        = rate_data.get("items", [])
    destination  = rate_data.get("destination", {})
    to_zip       = destination.get("postal_code", "90210")
    to_country   = destination.get("country", "US")

    total_weight_g = 0
    max_dim_x = 0
    max_dim_y = 0
    max_dim_z = 0

    for item in items:
        sku        = item.get("sku", "")
        set_number = "-".join(sku.split("-")[:2])
        bl_data    = get_bricklink_data(set_number)

        shopify_weight_g = float(item.get("grams", 0) or 0)
        dim_x = float(bl_data.get("dim_x", 0) or 0)
        dim_y = float(bl_data.get("dim_y", 0) or 0)
        dim_z = float(bl_data.get("dim_z", 0) or 0)
        qty   = item.get("quantity", 1)

        total_weight_g += shopify_weight_g * qty
        max_dim_x = max(max_dim_x, dim_x)
        max_dim_y = max(max_dim_y, dim_y)
        max_dim_z = max(max_dim_z, dim_z)

    shippo_rates = get_shippo_rates(
        total_weight_g, max_dim_x, max_dim_y, max_dim_z,
        to_zip, to_country
    )

    if shippo_rates:
        rate_list = []
        if "ground" in shippo_rates:
            rate_list.append({
                "service_name": shippo_rates.get("ground_name", "USPS Ground Advantage"),
                "service_code": "usps_ground",
                "total_price":  shippo_rates["ground"],
                "currency":     "USD",
                "min_delivery_date": None,
                "max_delivery_date": None
            })
        if "priority" in shippo_rates:
            rate_list.append({
                "service_name": shippo_rates.get("priority_name", "USPS Priority Mail"),
                "service_code": "usps_priority",
                "total_price":  shippo_rates["priority"],
                "currency":     "USD",
                "min_delivery_date": None,
                "max_delivery_date": None
            })
        return jsonify({"rates": rate_list})

    else:
        print("Shippo failed, using fallback rate")
        return jsonify({"rates": [{
            "service_name": "USPS Ground Advantage",
            "service_code": "usps_ground",
            "total_price":  1099,
            "currency":     "USD",
            "min_delivery_date": None,
            "max_delivery_date": None
        }]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
