import requests
from bs4 import BeautifulSoup
import json
import re
import pdfplumber
import os
from datetime import datetime

# --- CONFIGURATION ---
BASE_URL = "https://www.goaelectricity.gov.in/general-information/tariff-and-other-charges/"
# This pattern matches the current main PDF page structure
PDF_PAGE_PATTERN = r"fppca-for-[\w-]+" 
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
DATA_FILE = "electricity_data.json"
TEMP_PDF = "temp_tariff.pdf"

# --- HELPER FUNCTIONS ---
def get_main_tariff_page_url():
    """Dynamically finds the current URL for the main FPPCA page on the Goa Electricity site."""
    print("🌐 Checking for the newest FPPCA page...")
    response = requests.get(BASE_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    
    links = soup.find_all("a", href=re.compile(PDF_PAGE_PATTERN, re.I))
    if links:
        # Sort or select logic might be needed; assumption: first link is newest.
        return links[0]["href"]
    return None

def find_pdf_link(page_url):
    """Finds the download link for the main PDF on a given FPPCA page."""
    print(f"📄 Checking {page_url} for a new PDF...")
    response = requests.get(page_url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Locate the Download button/link
    download_link = soup.find("a", class_=re.compile(r"download|btn|pdf", re.I)) or \
                    soup.find("a", text=re.compile(r"Download|PDF", re.I))
    
    if download_link and download_link["href"].lower().endswith('.pdf'):
        pdf_url = download_link["href"]
        if not pdf_url.startswith("http"):
            # Construct absolute URL if relative
            from urllib.parse import urljoin
            pdf_url = urljoin(page_url, pdf_url)
        return pdf_url
    return None

def download_pdf(url):
    """Downloads the PDF to a temporary file."""
    print(f"⬇️ Downloading PDF from: {url[:60]}...")
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()
    with open(TEMP_PDF, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print("✅ PDF Downloaded.")

def parse_domestic_agri_data(pdf_path, fppca_percent):
    """Reads PDF and extracts Domestic and Agriculture tables."""
    print("🔍 Parsing PDF data for DOMESTIC and AGRICULTURE...")
    fppca_factor = fppca_percent / 100
    all_slabs = []
    current_category = ""
    target_captured = False

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Clean up the row data
                    clean_row = [re.sub(r'\s+', ' ', (c or '').strip()) for c in row]
                    
                    if len(clean_row) < 3:
                        continue

                    # -- Category Parsing --
                    if "DOMESTIC" in clean_row[0].upper():
                        current_category = "Domestic"
                        target_captured = True
                    elif "AGRICULTURAL" in clean_row[0].upper():
                        current_category = "Agriculture"
                        target_captured = True
                    elif clean_row[0] and clean_row[0].isupper() and "LT" in clean_row[0]:
                        current_category = "Other LT"
                        target_captured = False # Stop for other categories

                    if not target_captured or current_category == "Other LT":
                        continue

                    # -- Row Parsing --
                    row_id = clean_row[1]
                    raw_name = clean_row[2]
                    raw_energy_charge = clean_row[3]

                    # Detect slab and extract prices
                    if re.match(r'[\d\-]+\s*units|Above\s*\d+\s*units|All\s*Units', raw_name, re.I):
                        # Extract the base energy charge number
                        base_price_match = re.search(r'₹?\s*(\d+\.\d+)', raw_energy_charge)
                        if base_price_match:
                            base_rate = float(base_price_match.group(1))
                            calculated_fppca = round(base_rate * fppca_factor, 2)
                            total_rate = round(base_rate + calculated_fppca, 2)

                            all_slabs.append({
                                "id": row_id,
                                "name": raw_name,
                                "type": current_category,
                                "base_rate": base_rate,
                                "fppca_base": calculated_fppca,
                                "total_rate": total_rate
                            })

    # Optional structure simplification logic can be added here.
    return all_slabs

def create_output_structure(all_slabs, period_text):
    """Sorts data into a specific structure for electricity_data.json."""
    
    dom_slabs = []
    current_dom_cat = None
    for s in all_slabs:
        if s["type"] == "Domestic":
            # LTDS categories detection based on row id structure
            if re.match(r'LTDS-I', s["id"]):
                if not current_dom_cat or current_dom_cat["category"] != "LTDS-I (Low Income Group)":
                    current_dom_cat = {
                      "category": "LTDS-I (Low Income Group)",
                      "desc": "≤250W Load, ≤100u/mo",
                      "slabs": []
                    }
                    dom_slabs.append(current_dom_cat)
                current_dom_cat["slabs"].append({"range": s["name"], "base_rate": s["base_rate"], "fppca": s["fppca_base"], "total_rate": s["total_rate"]})
            elif re.match(r'LTDS-II', s["id"]):
                if not current_dom_cat or current_dom_cat["category"] != "LTDS-II (Standard Domestic)":
                    current_dom_cat = {
                      "category": "LTDS-II (Standard Domestic)",
                      "desc": "General home appliances",
                      "slabs": []
                    }
                    dom_slabs.append(current_dom_cat)
                current_dom_cat["slabs"].append({"range": s["name"], "base_rate": s["base_rate"], "fppca": s["fppca_base"], "total_rate": s["total_rate"]})
            elif re.match(r'LTDS-III', s["id"]):
                if not current_dom_cat or current_dom_cat["category"] != "LTDS-III (Domestic Mixed)":
                    current_dom_cat = {
                      "category": "LTDS-III (Domestic Mixed)",
                      "desc": "Residential mixed loads",
                      "slabs": []
                    }
                    dom_slabs.append(current_dom_cat)
                current_dom_cat["slabs"].append({"range": s["name"], "base_rate": s["base_rate"], "fppca": s["fppca_base"], "total_rate": s["total_rate"]})

    agri_records = []
    # Simplified mapping; assumption on flat rates based on prompt's target structure.
    for s in all_slabs:
        if s["type"] == "Agriculture":
            if re.match(r'LTAS-I', s["id"]):
                agri_records.append({ "name": "LTAS-I (Pumps ≤ 10 kW)", "desc": "Small Pumps", "range": "Flat Rate", "base_rate": s["base_rate"], "fppca": s["fppca_base"], "total_rate": s["total_rate"], "icon": "🚜" })
            elif re.match(r'LTAS-II', s["id"]):
                agri_records.append({ "name": "LTAS-II (Pumps > 10 kW)", "desc": "Heavy Pumps", "range": "Flat Rate", "base_rate": s["base_rate"], "fppca": s["fppca_base"], "total_rate": s["total_rate"], "icon": "💧" })
            elif re.match(r'LTAS-III', s["id"]):
                agri_records.append({ "name": "LTAS-III (Agriculture Allied)", "desc": "Dairy / Poultry", "range": "Flat Rate", "base_rate": s["base_rate"], "fppca": s["fppca_base"], "total_rate": s["total_rate"], "icon": "🌾" })

    return {
        "tariff_period": period_text,
        "domestic": dom_slabs,
        "agriculture": agri_records
    }

# --- MAIN EXECUTION ---
def main():
    try:
        # Load existing data to check if an update is needed
        last_known_pdf = ""
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                last_known_pdf = data.get("source_pdf_url", "")

        # 1. Check for newest PDF
        new_pdf_url = ""
        fppca_period_raw = ""
        current_page_url = get_main_tariff_page_url()
        
        if current_page_url:
            # Extract month/year from the page URL (fppca-for-july-2026)
            url_match = re.search(r'fppca-for-(.*)', current_page_url)
            if url_match:
                fppca_period_raw = url_match.group(1).replace('-', ' ').title()
            
            new_pdf_url = find_pdf_link(current_page_url)

        # 2. Check if the PDF is actually new
        if new_pdf_url == last_known_pdf:
            print(f"🚫 No new FPPCA PDF found today ({fppca_period_raw}). Latest was: {new_pdf_url}")
            exit(0)

        if not new_pdf_url:
            print("❌ Unable to locate a valid PDF download link.")
            exit(0)

        print(f"✅ NEW FPPCA PDF detected for: {fppca_period_raw}")
        print(f"✅ PDF URL: {new_pdf_url}")

        # 3. Download
        download_pdf(new_pdf_url)

        # 4. Parse Month's FPPCA Percentage from page text
        # Redownload page to parse the percentage text
        fppca_percent = 0
        response = requests.get(current_page_url, headers={"User-Agent": USER_AGENT}, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")
        # Example target: "FPPCA Computation for May-26 ... levies 19.235%"
        # Looking for numbers like "\d+\.\d+%"
        perc_matches = soup.find_all(text=re.compile(r'(\d+(?:\.\d+)?)\s*%', re.I))
        if perc_matches:
            match = re.search(r'(\d+(?:\.\d+)?)\s*%', perc_matches[0], re.I)
            if match:
                fppca_percent = float(match.group(1))
        
        if fppca_percent <= 0:
            print("❌ Unable to determine this month's FPPCA percentage from page text.")
            exit(0)

        print(f"✅ Current FPPCA percentage detected as: {fppca_percent}%")

        # 5. Extract tables and calculate
        all_parsed_slabs = parse_domestic_agri_data(TEMP_PDF, fppca_percent)
        
        if not all_parsed_slabs:
            print("❌ No DOMESTIC or AGRICULTURE tariff data extracted from PDF.")
            exit(0)

        # 6. Format and Save
        formatted_data = create_output_structure(all_parsed_slabs, f"July Consumption / FPPCA {fppca_percent}%")
        # Store source info so we don't redownload again
        formatted_data["source_pdf_url"] = new_pdf_url
        formatted_data["fppca_percentage"] = fppca_percent

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(formatted_data, f, indent=2, ensure_ascii=False)

        print(f"🎉 SUCCESS! Updated {DATA_FILE} with data from the new PDF.")

    except Exception as e:
        print(f"❌ Automation Error: {e}")
    finally:
        # Cleanup temporary files
        if os.path.exists(TEMP_PDF):
            os.remove(TEMP_PDF)

if __name__ == "__main__":
    main()
