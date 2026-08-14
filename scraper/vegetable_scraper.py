import os
import re
import json
from datetime import datetime
import requests
from PIL import Image
import pytesseract

API_URL = "https://europe-west3-storyviewer-7a64d.cloudfunctions.net/getInstagramData"
PAYLOAD = {
    "data": {
        "endpoint": "/v1.2/posts",
        "params": {
            "username_or_id_or_url": "gshclgoa"
        }
    }
}
HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "User-Agent": "okhttp/4.10.0"
}
IMAGE_FILENAME = "latest_price.jpg"

def find_image_urls(obj):
    """Recursively traverse the JSON to find any valid image URL."""
    urls = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and v.startswith("http") and any(ext in v.lower() for ext in [".jpg", ".jpeg", ".png", "cdninstagram", "fbcdn"]):
                urls.append(v)
            else:
                urls.extend(find_image_urls(v))
    elif isinstance(obj, list):
        for item in obj:
            urls.extend(find_image_urls(item))
    return urls

print("📡 Fetching latest Instagram post from @gshclgoa...")

try:
    response = requests.post(API_URL, json=PAYLOAD, headers=HEADERS, timeout=30)
    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        res_data = response.json()
        
        # Save raw response for debug inspection if needed
        with open("latest_post.json", "w", encoding="utf-8") as f:
            json.dump(res_data, f, indent=2, ensure_ascii=False)

        found_urls = find_image_urls(res_data)
        
        if found_urls:
            image_url = found_urls[0]
            print(f"📸 Found image URL: {image_url[:80]}...")
            img_res = requests.get(image_url, timeout=30)
            if img_res.status_code == 200:
                with open(IMAGE_FILENAME, "wb") as img_file:
                    img_file.write(img_res.content)
                print(f"✅ Successfully downloaded {IMAGE_FILENAME}")
        else:
            print("⚠️ No valid image URLs found in the JSON payload.")
    else:
        print(f"⚠️ Instagram API failed with response: {response.text[:200]}")
except Exception as e:
    print(f"⚠️ Network error while fetching Instagram post: {e}")

# -------------------------------------------------------------
# 2. RUN OCR ON DOWNLOADED IMAGE
# -------------------------------------------------------------
if not os.path.exists(IMAGE_FILENAME):
    print(f"❌ '{IMAGE_FILENAME}' not found. Cannot proceed with OCR.")
    exit(0)

print("\n🔍 Running OCR...")
img = Image.open(IMAGE_FILENAME)

text = pytesseract.image_to_string(
    img,
    lang="eng",
    config="--oem 3 --psm 6"
)

print("\n========== RAW OCR TEXT ==========")
print(text)

# -------------------------------------------------------------
# 3. TYPO FIXES & EMOJIS
# -------------------------------------------------------------
FIXES = {
    "Carot": "Carrot",
    "Chilly": "Chilli",
    "Chili": "Chilli",
    "Cl beans": "Cluster Beans",
    "CI beans": "Cluster Beans",
    "F beans": "French Beans",
    "Flowers/pc": "Cauliflower",
    "Flower/pc": "Cauliflower",
    "Bhindi": "Bhendi",
    "Capsicum": "Capsicum",
    "Onion": "Onion",
    "Potato": "Potato",
    "Tomato": "Tomato",
    "Brinjal": "Brinjal",
    "Cabbage": "Cabbage"
}

EMOJI = {
    "Bhendi": "🌿",
    "Cabbage": "🥬",
    "Carrot": "🥕",
    "Cauliflower": "🥦",
    "Cluster Beans": "🫛",
    "French Beans": "🫛",
    "Chilli": "🌶️",
    "Onion": "🧅",
    "Potato": "🥔",
    "Tomato": "🍅",
    "Brinjal": "🍆",
    "Cucumber": "🥒",
    "Pumpkin": "🎃",
    "Bottle Gourd": "🥒",
    "Green Peas": "🫛",
    "Beetroot": "🫜",
    "Radish": "🫜",
    "Spinach": "🥬",
    "Coriander": "🌿",
    "Ginger": "🫚",
    "Garlic": "🧄",
    "Sweet Potato": "🍠",
    "Capsicum": "🫑",
    "Lemon": "🍋",
    "Banana": "🍌"
}

# -------------------------------------------------------------
# 4. PARSE VEGETABLES & PRICES
# -------------------------------------------------------------
parsed_veggies = []

for line in text.splitlines():
    line = line.strip()
    if not line or "GSHCL" in line.upper():
        continue

    line = line.replace("•", "").replace("*", "").replace("—", "-")

    match = re.search(r"(.+?)\s*[-:]\s*(\d{1,3})$", line)
    if not match:
        continue

    name = match.group(1).strip()
    try:
        price = int(match.group(2))
    except ValueError:
        continue

    for wrong, correct in FIXES.items():
        if name.lower() == wrong.lower():
            name = correct
            break

    unit = "pc" if "cauliflower" in name.lower() or "flower" in name.lower() else "kg"

    parsed_veggies.append({
        "name": name,
        "price": price,
        "unit": unit,
        "market": "GSHCL Goa",
        "icon": EMOJI.get(name, "🥬")
    })

if not parsed_veggies:
    print("⚠️ No vegetable prices extracted. Keeping previous data files.")
    exit(0)

# Sort alphabetically
parsed_veggies.sort(key=lambda x: x["name"])

# -------------------------------------------------------------
# 5. CALCULATE PRICE HISTORY & CHANGES
# -------------------------------------------------------------
today = datetime.now().strftime("%Y-%m-%d")
history_file = "history.json"
history = {}

if os.path.exists(history_file):
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
    except:
        history = {}

final_vegetables = []

for veg in parsed_veggies:
    v_name = veg["name"]
    v_price = veg["price"]

    if v_name not in history:
        history[v_name] = []

    yesterday_price = v_price
    if len(history[v_name]) >= 1:
        yesterday_price = history[v_name][-1]["price"]

    change = v_price - yesterday_price
    change_pct = round((change / yesterday_price) * 100, 1) if yesterday_price > 0 else 0

    veg["change"] = change
    veg["changePercent"] = change_pct
    final_vegetables.append(veg)

    # Update today's date
    found = False
    for entry in history[v_name]:
        if entry.get("date") == today:
            entry["price"] = v_price
            found = True
            break
    if not found:
        history[v_name].append({"date": today, "price": v_price})

with open(history_file, "w", encoding="utf-8") as f:
    json.dump(history, f, indent=2, ensure_ascii=False)

# -------------------------------------------------------------
# 6. WRITE TO vegetables_data.json
# -------------------------------------------------------------
now = datetime.now()
output_data = {
    "last_updated": f"GSHCL {now.strftime('%d %b')}, Today",
    "vegetables": final_vegetables
}

with open("vegetables_data.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=2, ensure_ascii=False)

print(f"\n🎉 Successfully parsed and saved {len(final_vegetables)} vegetables into vegetables_data.json!")
