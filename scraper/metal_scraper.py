#!/usr/bin/env python3
import requests
import json
from datetime import datetime

API_KEY = "goldapi-b6db8a5fa9851cec87ced073b8636dc9-io"
HEADERS = {
    "x-access-token": API_KEY,
    "Content-Type": "application/json"
}

def get_metal_prices(symbol):
    """Fetch full price data for a metal from GoldAPI."""
    # GoldAPI endpoint format: /api/{symbol}/INR or /api/price/{symbol}/INR
    url = f"https://www.goldapi.io/api/{symbol}/INR"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            url_alt = f"https://www.goldapi.io/api/price/{symbol}/INR"
            r = requests.get(url_alt, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"❌ Error fetching {symbol}: {e}")
        return None

def main():
    print("🪙 Scraping live Gold and Silver prices from GoldAPI...")
    
    gold_data = get_metal_prices("XAU")
    silver_data = get_metal_prices("XAG")

    now = datetime.now()
    output = {
        "last_updated": f"Today, {now.strftime('%I:%M %p')}",
        "updated_iso": now.isoformat(),
        "gold": {},
        "silver": {}
    }

    if gold_data:
        g_gram = gold_data.get("price_gram_24k") or gold_data.get("price_per_unit", {}).get("gram", 0)
        if not g_gram and gold_data.get("price"):
            g_gram = gold_data.get("price") / 31.1034768
            
        g_22k = gold_data.get("price_gram_22k") or (g_gram * 22 / 24)
        g_18k = gold_data.get("price_gram_18k") or (g_gram * 18 / 24)

        output["gold"] = {
            "symbol": "XAU",
            "ounce_price": round(gold_data.get("price", 0), 2),
            "gram_price": round(g_gram, 2),
            "karats": {
                "24k": round(g_gram, 2),
                "22k": round(g_22k, 2),
                "18k": round(g_18k, 2)
            }
        }
        print(f"✅ Gold (24K): ₹{g_gram:,.2f}/g | 22K: ₹{g_22k:,.2f}/g")

    if silver_data:
        s_gram = silver_data.get("price_gram_24k") or silver_data.get("price_per_unit", {}).get("gram", 0)
        if not s_gram and silver_data.get("price"):
            s_gram = silver_data.get("price") / 31.1034768

        output["silver"] = {
            "symbol": "XAG",
            "ounce_price": round(silver_data.get("price", 0), 2),
            "gram_price": round(s_gram, 2),
            "karats": {
                "24k": round(s_gram, 2),
                "22k": round(s_gram * 22 / 24, 2),
                "18k": round(s_gram * 18 / 24, 2)
            }
        }
        print(f"✅ Silver: ₹{s_gram:,.2f}/g (10g: ₹{s_gram * 10:,.2f})")

    with open("metals_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("🎉 Saved metals_data.json successfully.")

if __name__ == "__main__":
    main()
