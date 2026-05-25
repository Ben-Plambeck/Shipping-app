from flask import Flask, request, jsonify
import requests
from requests_oauthlib import OAuth1

app = Flask(__name__)

CONSUMER_KEY = "592D427AFDE64D58A7884EFA700F10C7"
CONSUMER_SECRET = "3594251FFA854191915E121187D2E269"
TOKEN_VALUE = "3FA7803FF9F8473487AD1CA77FCCF4C0"
TOKEN_SECRET = "E3560584FCB04A0BA30B28EECE6F374C"
ORIGIN_ZIP = "93103"

auth = OAuth1(CONSUMER_KEY, CONSUMER_SECRET, TOKEN_VALUE, TOKEN_SECRET)

def get_bricklink_data(set_number):
    url = f"https://api.bricklink.com/api/store/v1/items/SET/{set_number}"
    r = requests.get(url, auth=auth)
    if r.status_code == 200:
        return r.json().get("data", {})
    return {}

@app.route("/", methods=["GET"])
def home():
    return "JMB Brick Co Shipping Rate App is running!"

@app.route("/rates", methods=["POST"])
def rates():
    data = request.json
    items = data.get("rate", {}).get("items", [])
    destination = data.get("rate", {}).get("destination", {})
    dest_zip = destination.get("postal_code", "90210")
    
    total_weight_oz = 0
    for item in items:
        sku = item.get("sku", "")
        set_number = "-".join(sku.split("-")[:2])
        bl_data = get_bricklink_data(set_number)
        weight_g = float(bl_data.get("weight", 0) or 0)
        weight_oz = (weight_g + 340) / 28.35
        total_weight_oz += weight_oz * item.get("quantity", 1)

    rates = [
        {
            "service_name": "USPS Ground Advantage",
            "service_code": "usps_ground",
            "total_price": max(899, int(total_weight_oz * 15)),
            "currency": "USD",
            "min_delivery_date": None,
            "max_delivery_date": None
        },
        {
            "service_name": "USPS Priority Mail",
            "service_code": "usps_priority",
            "total_price": max(1299, int(total_weight_oz * 22)),
            "currency": "USD",
            "min_delivery_date": None,
            "max_delivery_date": None
        }
    ]
    
    return jsonify({"rates": rates})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
