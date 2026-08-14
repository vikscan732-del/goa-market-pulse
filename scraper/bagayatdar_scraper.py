import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

URL = "https://goabagayatdar.com/pricing/"

headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://goabagayatdar.com/",
    "Connection": "keep-alive"
}

def is_supari_category(name):
    """Check if item belongs to the Supari / Betelnut / Khoka group to keep on top."""
    name_lower = name.lower()
    supari_keywords = ['supari', 'khoka', 'vench', 'khasod', 'tukada', 'chura']
    return any(k in name_lower for k in supari_keywords)

print("Scraping live prices from Goa Bagayatdar...")
response = requests.get(URL, headers=headers, timeout=120)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

# Extract the "Last Updated Date" if available on the page
date_text = "Today"
date_elem = soup.find(text=re.compile(r'Last Updated Date', re.IGNORECASE))
if date_elem:
    date_text = date_elem.strip()

table = soup.find("table")
raw_products = []

if table:
    rows = table.find_all("tr")
    for row in rows:
        cols = row.find_all(["th", "td"])
        if len(cols) < 2:
            continue

        name = cols[0].get_text(strip=True)
        price_raw = cols[1].get_text(strip=True)

        # Skip header rows
        if "Product Name" in name or "Price" in price_raw:
            continue

        # RULE 1: If price is '-', 'N/A', empty or doesn't contain digits, SKIP IT
        if not price_raw or '-' in price_raw and not any(char.isdigit() for char in price_raw):
            continue

        # Extract numerical prices (handles ranges like "14000 23000" or single price "402")
        numbers = re.findall(r'\d+(?:\.\d+)?', price_raw)
        if not numbers:
            continue

        if len(numbers) >= 2:
            display_price = f"{numbers[0]} - {numbers[1]}"
            sort_price = float(numbers[0])
        else:
            display_price = f"{numbers[0]}"
            sort_price = float(numbers[0])

        # Assign friendly emojis based on category
        icon = "📦"
        name_lower = name.lower()
        if is_supari_category(name):
            icon = "🥥"
        elif "miri" in name_lower or "pepper" in name_lower:
            icon = "🫒"
        elif "jayfal" in name_lower or "nutmeg" in name_lower:
            icon = "🌰"
        elif "tamalpatra" in name_lower or "dalchini" in name_lower:
            icon = "🌿"
        elif "kokum" in name_lower:
            icon = "🫐"
        elif "coconut" in name_lower or "naral" in name_lower:
            icon = "🥥"
        elif "cashew" in name_lower or "kaju" in name_lower:
            icon = "🥜"

        raw_products.append({
            "name": name,
            "price": display_price,
            "sort_price": sort_price,
            "is_supari": is_supari_category(name),
            "icon": icon
        })

# RULE 2: Sort so all Supari types appear at the TOP, followed by other items
supari_items = [p for p in raw_products if p["is_supari"]]
other_items = [p for p in raw_products if not p["is_supari"]]

final_products = supari_items + other_items

# Clean internal sorting keys
for p in final_products:
    del p["sort_price"]
    del p["is_supari"]

output_data = {
    "last_updated": date_text,
    "products": final_products
}

with open("bagayatdar_data.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=4, ensure_ascii=False)

print(f"Success! {len(final_products)} active products saved into bagayatdar_data.json.")
