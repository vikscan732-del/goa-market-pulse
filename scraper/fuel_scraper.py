#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

TARGET_CITY = "Panjim"
TARGET_STATE = "Goa"

FUEL_PAGES = {
    "Petrol": {
        "url": "https://www.mypetrolprice.com/petrol-price-in-india.aspx",
        "category": "petrol",
        "unit": "Litre",
        "icon": "⛽",
        "default_price": 104.06
    },
    "Diesel": {
        "url": "https://www.mypetrolprice.com/diesel-price-in-india.aspx",
        "category": "diesel",
        "unit": "Litre",
        "icon": "🛢️",
        "default_price": 95.98
    },
    "CNG": {
        "url": "https://www.mypetrolprice.com/cng-price-in-india.aspx",
        "category": "cng",
        "unit": "kg",
        "icon": "🟢",
        "default_price": 86.50
    },
    "Auto Gas": {
        "url": "https://www.mypetrolprice.com/autogas-autolpg-price-in-india.aspx",
        "category": "cng",
        "unit": "Litre",
        "icon": "🔵",
        "default_price": 58.20
    },
    "LPG (Domestic)": {
        "url": "https://www.mypetrolprice.com/lpg-price-in-india.aspx",
        "category": "lpg",
        "unit": "14.2 kg cyl",
        "icon": "🔴",
        "default_price": 956.00
    }
}

def fetch_fuel_price(url, city, state):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        for h2 in soup.find_all("h2"):
            a_tag = h2.find("a")
            if a_tag and state.lower() in a_tag.text.lower():
                parent_div = h2.find_next_sibling("div", class_="txtC")
                if not parent_div:
                    continue
                for sf in parent_div.find_all("div", class_="SF"):
                    ch = sf.find("div", class_="CH")
                    if not ch:
                        continue
                    city_link = None
                    for a in ch.find_all("a"):
                        if "ChartAnchor" not in a.get("class", []):
                            city_link = a
                            break
                    if city_link and city.lower() in city_link.text.strip().lower():
                        price_div = sf.find("div", class_="txtC")
                        if price_div:
                            b_tag = price_div.find("b")
                            if b_tag:
                                price_text = b_tag.text.strip().replace("₹", "").strip()
                                change_text = price_div.text.strip().split("(")[-1].replace(")", "").strip()
                                try:
                                    price = float(price_text)
                                    clean_change = re.findall(r'[-+]?\d*\.\d+|\d+', change_text)
                                    change = float(clean_change[0]) if clean_change else 0.0
                                    
                                    # Detect sign
                                    if "-" in change_text and change > 0:
                                        change = -change
                                    
                                    change_percent = round((abs(change) / price) * 100, 2) if price > 0 else 0.0
                                    return {"price": price, "change": change, "changePercent": change_percent}
                                except ValueError:
                                    return None
        return None
    except Exception as e:
        print(f"⚠️ Error fetching {url}: {e}")
        return None

def main():
    print(f"⛽ Fetching daily Goa fuel rates for {TARGET_CITY} from MyPetrolPrice...")
    fuels_list = []

    for fuel_name, info in FUEL_PAGES.items():
        data = fetch_fuel_price(info["url"], TARGET_CITY, TARGET_STATE)
        
        if data and data.get("price"):
            price = data["price"]
            change = data.get("change", 0.0)
            change_percent = data.get("changePercent", 0.0)
        else:
            price = info["default_price"]
            change = 0.0
            change_percent = 0.0

        fuels_list.append({
            "name": f"{fuel_name} ({TARGET_CITY})",
            "category": info["category"],
            "price": price,
            "unit": info["unit"],
            "district": f"{TARGET_STATE} ({TARGET_CITY})",
            "icon": info["icon"],
            "change": change,
            "changePercent": change_percent
        })

    # Add standard Commercial LPG cylinder (19kg)
    fuels_list.append({
        "name": "Commercial LPG (19 kg)",
        "category": "lpg",
        "price": 2815.00,
        "unit": "19 kg cyl",
        "district": "All Goa (Hotels & Commercial)",
        "icon": "🔴",
        "change": 0.00,
        "changePercent": 0.0
    })

    now = datetime.now()
    output = {
        "last_updated": f"Today, {now.strftime('%I:%M %p')}",
        "city": TARGET_CITY,
        "state": TARGET_STATE,
        "fuels": fuels_list
    }

    # Save to fuel_data.json
    with open("fuel_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(fuels_list)} fuel records to fuel_data.json")

if __name__ == "__main__":
    main()
