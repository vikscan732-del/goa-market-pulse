import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

URL = "https://infralens.in/prices/goa"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def fix_text(text):
    """Fix encoding or broken text artifacts."""
    if not text:
        return ""
    try:
        return text.encode("latin1").decode("utf-8").strip()
    except Exception:
        return text.strip()

print("🚜 Downloading construction prices from Infralens Goa...")

try:
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")
    categories = []

    # Category icons mapping for visual appeal
    CATEGORY_ICONS = {
        "cement": "🧱",
        "steel": "🏗️",
        "sand": "⏳",
        "aggregate": "🪨",
        "brick": "🧱",
        "block": "🧱",
        "paint": "🎨",
        "wood": "🪵",
        "plumbing": "🚰",
        "electrical": "⚡"
    }

    for cat in soup.select(".cp-cat"):
        head = cat.select_one(".cp-cat-head")
        if not head:
            continue

        category_name = fix_text(head.get_text(" ", strip=True))
        
        # Determine icon
        icon = "🏗️"
        for k, v in CATEGORY_ICONS.items():
            if k in category_name.lower():
                icon = v
                break

        items = []
        for row in cat.select(".cp-price-row"):
            name_el = row.select_one(".cp-price-name")
            price_el = row.select_one(".cp-price-val span")
            unit_el = row.select_one(".cp-price-unit")

            raw_name = fix_text(name_el.get_text(strip=True)) if name_el else ""
            raw_price = fix_text(price_el.get_text(strip=True)) if price_el else ""
            raw_unit = fix_text(unit_el.get_text(strip=True)) if unit_el else ""

            if raw_name and raw_price:
                items.append({
                    "name": raw_name,
                    "price": raw_price,
                    "unit": raw_unit
                })

        if items:
            categories.append({
                "category": category_name,
                "icon": icon,
                "items": items
            })

    if len(categories) == 0:
        print("⚠️ No construction categories parsed. Keeping previous data file.")
        exit(0)

    # Save directly to construction_data.json in root for simple GitHub Pages loading
    now = datetime.now()
    output = {
        "last_updated": f"Today, {now.strftime('%I:%M %p')}",
        "total_categories": len(categories),
        "total_materials": sum(len(c["items"]) for c in categories),
        "categories": categories
    }

    with open("construction_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"✅ Successfully saved construction_data.json with {len(categories)} categories & {output['total_materials']} items.")

except Exception as e:
    print(f"❌ Error scraping construction prices: {e}")
