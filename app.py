from flask import Flask, request, jsonify
import requests
from requests_oauthlib import OAuth1
import json
import os
app = Flask(__name__)

# Load dimensions cache
cache_path = os.path.join(os.path.dirname(__file__), "dims_cache.json")
with open(cache_path) as f:
    DIMS_CACHE = json.load(f)
print(f"Loaded {len(DIMS_CACHE)} sets from cache")
CONSUMER_KEY = "592D427AFDE64D58A7884EFA700F10C7"
CONSUMER_SECRET = "3594251FFA854191915E121187D2E269"
TOKEN_VALUE = "C786B85CEC0849C69589676DBC1DEF46"
TOKEN_SECRET = "895C0A261C6740B0A62DCB46D47DAA2C"
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
def calculate_rate(weight_g, dim_x_cm, dim_y_cm, dim_z_cm):
    weight_lb = weight_g / 453.592
    if dim_x_cm and dim_y_cm and dim_z_cm:
        dim_x_in = dim_x_cm / 2.54
        dim_y_in = dim_y_cm / 2.54
        dim_z_in = dim_z_cm / 2.54
        dim_weight_lb = (dim_x_in * dim_y_in * dim_z_in) / 139
        billable_lb = max(weight_lb, dim_weight_lb)
    else:
        billable_lb = weight_lb
    if billable_lb <= 1:
        ground = 899
    elif billable_lb <= 2:
        ground = 1099
    elif billable_lb <= 5:
        ground = 1299 + int((billable_lb - 2) * 150)
    elif billable_lb <= 10:
        ground = 1749 + int((billable_lb - 5) * 200)
    elif billable_lb <= 20:
        ground = 2749 + int((billable_lb - 10) * 250)
    else:
        ground = 5249 + int((billable_lb - 20) * 300)
    priority = int(ground * 1.6)
    return ground, priority
@app.route("/", methods=["GET"])
def home():
    return "JMB Brick Co Shipping Rate App is running!"
@app.route("/rates", methods=["POST"])
def rates():
    data = request.json
    print("RECEIVED:", data)
    items = data.get("rate", {}).get("items", [])
    total_weight_g = 0
    max_dim_x = 0
    max_dim_y = 0
    max_dim_z = 0
    for item in items:
        sku = item.get("sku", "")
        set_number = "-".join(sku.split("-")[:2])
        bl_data = get_bricklink_data(set_number)
        shopify_weight_g = float(item.get("grams", 0) or 0)
        dim_x = float(bl_data.get("dim_x", 0) or 0)
        dim_y = float(bl_data.get("dim_y", 0) or 0)
        dim_z = float(bl_data.get("dim_z", 0) or 0)
        qty = item.get("quantity", 1)
        total_weight_g += shopify_weight_g * qty
        max_dim_x = max(max_dim_x, dim_x)
        max_dim_y = max(max_dim_y, dim_y)
        max_dim_z = max(max_dim_z, dim_z)
    ground, priority = calculate_rate(total_weight_g, max_dim_x, max_dim_y, max_dim_z)
    return jsonify({"rates": [
        {"service_name": "USPS Ground Advantage", "service_code": "usps_ground", "total_price": ground, "currency": "USD", "min_delivery_date": None, "max_delivery_date": None},
        {"service_name": "USPS Priority Mail", "service_code": "usps_priority", "total_price": priority, "currency": "USD", "min_delivery_date": None, "max_delivery_date": None}
    ]})
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
