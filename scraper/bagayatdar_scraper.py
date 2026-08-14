import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

# Optional Firebase integration: reads if FIREBASE_SERVICE_ACCOUNT secret is present
service_account_env = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
db = None

if service_account_env:
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        cred = credentials.Certificate(json.loads(service_account_env))
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase connected.")
    except Exception as e:
        print("Firebase init skipped/failed:", e)

URL = "https://goabagayatdar.com/pricing/"

headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://goabagayatdar.com/",
    "Connection": "keep-alive"
}

print("Fetching Goa Bagayatdar data...")
response = requests.get(URL, headers=headers, timeout=120)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")
table = soup.find("table")

products = []
today = datetime.now().strftime("%Y-%m-%d")

if table:
    rows = table.find_all("tr")
    for row in rows:
        cols = row.find_all(["th", "td"])
        if len(cols) < 2:
            continue

        name = cols[0].get_text(strip=True)
        price_text = cols[1].get_text(strip=True)

        clean = "".join(c for c in price_text if c.isdigit() or c == ".")
        try:
            price = float(clean)
        except:
            continue

        products.append({
            "name": name,
            "price": price,
            "change": 0,
            "changePercent": 0,
            "highest": price,
            "lowest": price
        })

print(f"Total Products Found: {len(products)}")

# Update local JSON file directly for GitHub Pages
output_data = {
    "last_updated": datetime.now().strftime("%d %b %Y, %I:%M %p"),
    "products": products
}

with open("bagayatdar_data.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=4, ensure_ascii=False)

print("bagayatdar_data.json generated successfully.")

# If Firebase is active, update collection
if db:
    for item in products:
        docs = list(db.collection("products").where("name", "==", item["name"]).limit(1).stream())
        current_price = item["price"]

        if docs:
            doc_ref = docs[0].reference
            old = docs[0].to_dict()
            history = [h for h in old.get("history", []) if h.get("date") != today]
            history.append({"date": today, "price": current_price})
            history = sorted(history, key=lambda x: x["date"])[-365:]

            prices = [x["price"] for x in history]
            yesterday = history[-2]["price"] if len(history) >= 2 else current_price
            change = round(current_price - yesterday, 2)
            change_percent = round((change / yesterday) * 100, 2) if yesterday != 0 else 0

            doc_ref.update({
                "price": current_price,
                "history": history,
                "highest": max(prices),
                "lowest": min(prices),
                "average": round(sum(prices) / len(prices), 2),
                "yesterdayPrice": yesterday,
                "change": change,
                "changePercent": change_percent,
                "updated": firestore.SERVER_TIMESTAMP
            })
    print("Firestore synced successfully.")
