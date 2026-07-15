"""
Travel Agency Finder - FREE Version with Simple JSON Output
Using OpenStreetMap APIs (No API Key Required)
Outputs data in the exact format you specified
"""

import csv
import json
import time
import zipfile
import io
import re
from typing import List, Dict, Optional, Tuple
from math import radians, sin, cos, sqrt, atan2
import requests

# ==================== CONFIGURATION ====================

COUNTRIES = {
    # "United States": "US",
    # "Brazil": "BR",
    "United Kingdom": "GB",
    # "Australia": "AU",
    # "Canada": "CA",
    # "Germany": "DE",
    # "France": "FR",
    # "Japan": "JP",
    # "Singapore": "SG",
    # "Malaysia": "MY",
    # "Bangladesh": "BD",
    # "India": "IN",
    # "Thailand": "TH",
}

# Search radius in meters
SEARCH_RADIUS = 10000  # 10km

# Maximum number of postal codes to check per country
MAX_POSTAL_CODES_PER_COUNTRY = 5

# Rate limiting (seconds between API calls - IMPORTANT for OSM)
RATE_LIMIT = 1.5  # Increased for better rate limiting

# User agent for OSM API (REQUIRED)
USER_AGENT = "TravelAgencyFinder/1.0 (contact@example.com)"

# ==================== POSTAL CODE FORMATTING ====================

def format_postal_code(postal_code: str, country_code: str) -> str:
    """
    Format postal codes based on country-specific rules
    """
    postal_code = postal_code.strip().upper()

    # UK postal codes (need space between outward and inward codes)
    if country_code == "GB":
        # UK format: AA9A 9AA, A9A 9AA, A9 9AA, A99 9AA, AA9 9AA, AA99 9AA
        # Remove any existing spaces first
        code = postal_code.replace(" ", "")

        # Try to format with space
        if len(code) >= 3:
            # Common UK patterns
            if len(code) == 4:
                # e.g., M1 1AA
                formatted = f"{code[:2]} {code[2:]}"
            elif len(code) == 5:
                # e.g., M1 1AA becomes M1 1AA (already has space)
                # e.g., M1 1A
                if code[1].isdigit():
                    formatted = f"{code[:2]} {code[2:]}"
                else:
                    formatted = f"{code[:3]} {code[3:]}"
            elif len(code) == 6:
                # e.g., M1 1AA, SW1A 1AA
                if code[1].isdigit():
                    formatted = f"{code[:2]} {code[2:]}"
                else:
                    formatted = f"{code[:3]} {code[3:]}"
            elif len(code) == 7:
                # e.g., SW1A 1AA
                formatted = f"{code[:3]} {code[3:]}"
            else:
                formatted = postal_code
        else:
            formatted = postal_code

        return formatted

    # Other countries - keep as is
    return postal_code

# ==================== OPENSTREETMAP API FUNCTIONS ====================

def geocode_postal_code(postal_code: str, country_code: str) -> Optional[Tuple[float, float]]:
    """
    Get coordinates from postal code using Nominatim with multiple strategies
    """
    # Format the postal code first
    formatted_code = format_postal_code(postal_code, country_code)

    # Try multiple search strategies
    search_strategies = [
        # Strategy 1: Exact postal code with country
        {
            "postalcode": formatted_code,
            "countrycodes": country_code.lower(),
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
        },
        # Strategy 2: Only postal code (without country filter)
        {
            "postalcode": formatted_code,
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
        },
        # Strategy 3: Search by postal code and country name
        {
            "q": f"{formatted_code} {country_code}",
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
        },
        # Strategy 4: Try without country code for UK
        {
            "postalcode": formatted_code.replace(" ", ""),
            "countrycodes": country_code.lower(),
            "format": "json",
            "limit": 1,
        },
        # Strategy 5: Try with city name (fallback)
        {
            "q": f"{formatted_code}",
            "format": "json",
            "limit": 1,
        }
    ]

    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": USER_AGENT}

    for strategy_idx, params in enumerate(search_strategies):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    if strategy_idx > 0:
                        print(f"      ✅ Found using strategy {strategy_idx + 1}")
                    return lat, lon

            time.sleep(0.5)  # Small delay between strategies

        except Exception as e:
            continue

    return None

def search_osm_agencies(lat: float, lon: float, radius: int = SEARCH_RADIUS) -> List[Dict]:
    """
    Search for travel agencies using OpenStreetMap Overpass API
    """
    # Overpass QL query - searches for travel agencies
    query = f"""
    [out:json][timeout:60];
    (
      node["shop"="travel_agency"](around:{radius},{lat},{lon});
      node["office"="travel_agency"](around:{radius},{lat},{lon});
      node["amenity"="travel_agency"](around:{radius},{lat},{lon});
      node["tourism"="travel_agency"](around:{radius},{lat},{lon});
      node["shop"="travel"](around:{radius},{lat},{lon});
      node["office"="tour_operator"](around:{radius},{lat},{lon});
      node["tourism"="tourist_information"](around:{radius},{lat},{lon});
      way["shop"="travel_agency"](around:{radius},{lat},{lon});
      way["office"="travel_agency"](around:{radius},{lat},{lon});
      way["amenity"="travel_agency"](around:{radius},{lat},{lon});
      way["tourism"="travel_agency"](around:{radius},{lat},{lon});
      relation["shop"="travel_agency"](around:{radius},{lat},{lon});
      relation["office"="travel_agency"](around:{radius},{lat},{lon});
      relation["amenity"="travel_agency"](around:{radius},{lat},{lon});
      relation["tourism"="travel_agency"](around:{radius},{lat},{lon});
    );
    out body center;
    """

    url = "https://overpass-api.de/api/interpreter"
    params = {"data": query}

    try:
        response = requests.post(url, data=params, timeout=60)

        if response.status_code == 200:
            data = response.json()
            agencies = []

            for element in data.get("elements", []):
                agency = process_osm_element(element, lat, lon)
                if agency:
                    agencies.append(agency)

            return agencies
        else:
            print(f"      ⚠️  Overpass API error: {response.status_code}")
            return []

    except requests.exceptions.Timeout:
        print(f"      ⚠️  Overpass API timeout - trying again...")
        time.sleep(5)
        return []
    except Exception as e:
        print(f"      ❌ Overpass API error: {e}")
        return []

def process_osm_element(element: Dict, search_lat: float, search_lon: float) -> Optional[Dict]:
    """
    Process an OSM element into the exact format you requested
    """
    tags = element.get("tags", {})

    # Check if it's actually a travel agency
    shop_type = tags.get("shop", "")
    office_type = tags.get("office", "")
    amenity_type = tags.get("amenity", "")
    tourism_type = tags.get("tourism", "")

    is_travel_agency = (
        shop_type == "travel_agency" or
        office_type == "travel_agency" or
        amenity_type == "travel_agency" or
        tourism_type == "travel_agency" or
        "travel" in str(tags.get("name", "")).lower() or
        "tour" in str(tags.get("name", "")).lower() or
        shop_type == "travel" or
        office_type == "tour_operator" or
        tourism_type == "tourist_information"
    )

    if not is_travel_agency:
        return None

    # Get name
    name = tags.get("name", "")
    if not name:
        name = tags.get("name:en", "") or tags.get("brand", "") or "Unnamed Travel Agency"

    # Get coordinates
    if "center" in element:
        lat = float(element["center"].get("lat", 0))
        lon = float(element["center"].get("lon", 0))
    else:
        lat = float(element.get("lat", 0))
        lon = float(element.get("lon", 0))

    # If coordinates are 0,0, try to get from geometry
    if lat == 0 and lon == 0:
        if "geometry" in element and element["geometry"]:
            if element["geometry"]:
                lat = float(element["geometry"][0].get("lat", 0))
                lon = float(element["geometry"][0].get("lon", 0))

    # Get address components
    street = tags.get("addr:street", "")
    housenumber = tags.get("addr:housenumber", "")
    city = tags.get("addr:city", "")
    state = tags.get("addr:state", "")
    country = tags.get("addr:country", "")
    postal_code = tags.get("addr:postcode", "")

    # Build street address
    if housenumber and street:
        full_street = f"{housenumber} {street}"
    elif street:
        full_street = street
    else:
        full_street = ""

    # Get contact information
    phone = tags.get("phone", "") or tags.get("contact:phone", "")
    website = tags.get("website", "") or tags.get("contact:website", "") or tags.get("url", "")

    # Clean phone number
    if phone:
        phone = re.sub(r'\s+', '', phone)

    # Get categories
    categories = ["Travel agency"]
    if shop_type and shop_type != "travel_agency":
        categories.append(shop_type.replace("_", " ").title())
    if office_type and office_type != "travel_agency":
        categories.append(office_type.replace("_", " ").title())

    # Limit to first 5 categories
    categories = categories[:5]

    # Generate Google Maps URL with coordinates
    url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"

    # Build the agency object
    agency = {
        "title": name,
        "totalScore": 0,
        "reviewsCount": 0,
        "street": full_street,
        "city": city if city else "",
        "state": state if state else "",
        "countryCode": country if country else "",
        "website": website,
        "phone": phone,
        "categories": categories,
        "url": url,
        "categoryName": "Travel agency",
        "_location": {
            "latitude": lat,
            "longitude": lon,
            "postalCode": postal_code if postal_code else ""
        }
    }

    return agency

# ==================== DATA FETCHING FUNCTIONS ====================

def fetch_postal_codes(country_code: str, country_name: str) -> List[str]:
    """
    Fetch postal codes from GeoNames (free)
    """
    url = f"http://download.geonames.org/export/zip/{country_code}.zip"

    try:
        print(f"  📥 Downloading postal codes for {country_name}...")
        response = requests.get(url, timeout=60)

        if response.status_code != 200:
            print(f"  ⚠️  No postal data available for {country_name}")
            return []

        z = zipfile.ZipFile(io.BytesIO(response.content))
        postal_codes = []

        with z.open(f"{country_code}.txt") as f:
            for line in io.TextIOWrapper(f, encoding="utf-8"):
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 2:
                    postal_code = parts[1].strip()
                    if postal_code:
                        postal_codes.append(postal_code)

        # Remove duplicates while preserving order
        seen = set()
        unique_postal_codes = []
        for code in postal_codes:
            if code not in seen:
                seen.add(code)
                unique_postal_codes.append(code)

        print(f"  ✅ Found {len(unique_postal_codes)} postal codes")
        return unique_postal_codes

    except Exception as e:
        print(f"  ❌ Error fetching postal codes: {e}")
        return []

def clean_agency_data(agency: Dict) -> Dict:
    """
    Clean and validate agency data
    """
    for key in ["street", "city", "state", "countryCode", "website", "phone"]:
        if agency.get(key) == "" or agency.get(key) == "N/A":
            agency[key] = ""

    if isinstance(agency.get("categories"), str):
        agency["categories"] = [agency["categories"]]

    if not agency["title"]:
        agency["title"] = "Travel Agency"

    return agency

# ==================== MAIN FUNCTION ====================

def main():
    """Main function to fetch and save travel agency data"""

    print("=" * 70)
    print("🌍 TRAVEL AGENCY FINDER - FREE VERSION")
    print("Using OpenStreetMap APIs (No API Key Required)")
    print("=" * 70)
    print("\n⚠️  NOTE: OSM has rate limits (1 request/second)")
    print("   Please be patient while fetching data...\n")

    all_agencies = []
    agencies_with_location = []
    stats = {}
    all_errors = []

    for country_name, country_code in COUNTRIES.items():
        print(f"\n📍 Processing: {country_name} ({country_code})")
        print("-" * 50)

        postal_codes = fetch_postal_codes(country_code, country_name)

        if not postal_codes:
            print(f"  ⚠️  Skipping {country_name} - no postal codes found")
            all_errors.append(f"{country_name}: No postal codes available")
            continue

        postal_codes = postal_codes[:MAX_POSTAL_CODES_PER_COUNTRY]
        print(f"  📍 Checking {len(postal_codes)} postal codes")

        country_agencies = []
        country_agencies_with_location = []
        country_errors = []

        for idx, postal_code in enumerate(postal_codes, 1):
            print(f"\n  🏙️  [{idx}/{len(postal_codes)}] Processing postal code: {postal_code}")

            # Show formatted version for UK
            if country_code == "GB":
                formatted = format_postal_code(postal_code, country_code)
                if formatted != postal_code:
                    print(f"    📝 Formatted as: {formatted}")

            coords = geocode_postal_code(postal_code, country_code)

            if not coords:
                print(f"    ❌ Could not geocode postal code: {postal_code}")
                country_errors.append(f"Postal code {postal_code}: Geocoding failed")
                time.sleep(RATE_LIMIT)
                continue

            lat, lon = coords
            print(f"    📍 Coordinates: {lat:.4f}, {lon:.4f}")

            print(f"    🔍 Searching for travel agencies within {SEARCH_RADIUS/1000}km...")
            agencies = search_osm_agencies(lat, lon)

            if agencies:
                for agency in agencies:
                    cleaned_agency = clean_agency_data(agency)
                    country_agencies.append(cleaned_agency)

                    agency_with_loc = cleaned_agency.copy()
                    agency_with_loc["latitude"] = agency["_location"]["latitude"]
                    agency_with_loc["longitude"] = agency["_location"]["longitude"]
                    agency_with_loc["postalCode"] = agency["_location"]["postalCode"]
                    del agency_with_loc["_location"]
                    country_agencies_with_location.append(agency_with_loc)

                print(f"    ✅ Found {len(agencies)} travel agencies")

                for i, agency in enumerate(agencies[:3], 1):
                    print(f"      {i}. {agency['title']}")
                    if agency["street"]:
                        print(f"         📍 {agency['street']}, {agency['city']}")
                    if agency["phone"]:
                        print(f"         📞 {agency['phone']}")
            else:
                print(f"    ℹ️  No travel agencies found near this location")

            time.sleep(RATE_LIMIT)

        all_agencies.extend(country_agencies)
        agencies_with_location.extend(country_agencies_with_location)
        stats[country_name] = {
            "postal_codes_checked": len(postal_codes),
            "agencies_found": len(country_agencies)
        }

        if country_errors:
            all_errors.extend(country_errors)

        print(f"\n  ✅ {country_name}: Found {len(country_agencies)} travel agencies")

    # Remove duplicate agencies
    unique_agencies = []
    seen = set()
    for agency in all_agencies:
        key = f"{agency['title']}_{agency['street']}_{agency['city']}"
        if key not in seen:
            seen.add(key)
            unique_agencies.append(agency)

    unique_with_location = []
    seen = set()
    for agency in agencies_with_location:
        key = f"{agency['title']}_{agency['street']}_{agency['city']}"
        if key not in seen:
            seen.add(key)
            unique_with_location.append(agency)

    # ==================== SAVE RESULTS ====================

    clean_output = {
        "agencies": unique_agencies
    }

    with open("travel_agencies.json", "w", encoding="utf-8") as f:
        json.dump(clean_output, f, ensure_ascii=False, indent=2)

    location_output = {
        "metadata": {
            "totalAgencies": len(unique_with_location),
            "countriesSearched": list(COUNTRIES.keys()),
            "statistics": stats,
            "apiUsed": "OpenStreetMap (Nominatim + Overpass)",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "errors": all_errors
        },
        "agencies": unique_with_location
    }

    with open("travel_agencies_with_location.json", "w", encoding="utf-8") as f:
        json.dump(location_output, f, ensure_ascii=False, indent=2)

    if unique_with_location:
        csv_fields = [
            "title", "totalScore", "reviewsCount",
            "street", "city", "state", "countryCode",
            "latitude", "longitude", "postalCode",
            "website", "phone", "categories", "url", "categoryName"
        ]

        with open("travel_agencies.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields)
            writer.writeheader()
            for agency in unique_with_location:
                row = {
                    "title": agency["title"],
                    "totalScore": agency["totalScore"],
                    "reviewsCount": agency["reviewsCount"],
                    "street": agency["street"],
                    "city": agency["city"],
                    "state": agency["state"],
                    "countryCode": agency["countryCode"],
                    "latitude": agency.get("latitude", ""),
                    "longitude": agency.get("longitude", ""),
                    "postalCode": agency.get("postalCode", ""),
                    "website": agency["website"],
                    "phone": agency["phone"],
                    "categories": ", ".join(agency["categories"]),
                    "url": agency["url"],
                    "categoryName": agency["categoryName"]
                }
                writer.writerow(row)

    # ==================== PRINT SUMMARY ====================

    print("\n" + "=" * 70)
    print("📊 FINAL SUMMARY")
    print("=" * 70)

    print(f"\n✅ Total Travel Agencies Found: {len(unique_agencies)}")
    print(f"\n📈 Statistics by Country:")
    for country, stat in stats.items():
        print(f"  • {country}: {stat['agencies_found']} agencies (checked {stat['postal_codes_checked']} postal codes)")

    if all_errors:
        print(f"\n⚠️  Errors encountered: {len(all_errors)}")
        for error in all_errors[:5]:
            print(f"  • {error}")
        if len(all_errors) > 5:
            print(f"  • ... and {len(all_errors) - 5} more errors")

    print(f"\n💾 Results saved to:")
    print(f"  • JSON (clean): travel_agencies.json")
    print(f"  • JSON (with location): travel_agencies_with_location.json")
    print(f"  • CSV:  travel_agencies.csv")

    if unique_agencies:
        print(f"\n📋 Sample Agencies Found:")
        for idx, agency in enumerate(unique_agencies[:3], 1):
            print(f"\n  {idx}. {agency['title']}")
            if agency["street"]:
                print(f"     📍 Address: {agency['street']}, {agency['city']}, {agency['state']}")
            print(f"     🌐 {agency['url']}")
            if agency["phone"]:
                print(f"     📞 Phone: {agency['phone']}")
            if agency["website"]:
                print(f"     💻 Website: {agency['website']}")
    else:
        print("\n⚠️  No agencies found. Try increasing MAX_POSTAL_CODES_PER_COUNTRY or SEARCH_RADIUS")

    print("\n" + "=" * 70)
    print("✅ Process completed!")
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()