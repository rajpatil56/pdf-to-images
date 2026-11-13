import os
import json
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types

# Initialize client with the GEMINI_API_KEY from GitHub Secrets
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# Set Indian Standard Time (IST)
ist = timezone(timedelta(hours=5, minutes=30))
today_str = datetime.now(ist).strftime("%d %B %Y")

# All 100 exams grouped into 4 batches of 25 exams (Uses only 4 RPD out of 500 RPD)
EXAM_BATCHES = {
    "Batch 1: SSC, Railways & UPSC": [
        "SSC CGL", "SSC CHSL", "SSC MTS & Havaldar", "SSC GD Constable", "SSC CPO",
        "SSC JE", "SSC Stenographer", "SSC Selection Post", "SSC JHT", "Delhi Police Constable",
        "RRB NTPC Graduate", "RRB NTPC Undergraduate", "RRB Group D", "RRB ALP", "RRB Technician",
        "RRB JE", "RPF SI", "RPF Constable", "DFCCIL", "Metro Rail (DMRC/MahaMetro)",
        "UPSC CSE (IAS/IPS)", "UPSC IFoS", "UPSC ESE (IES)", "UPSC CDS", "UPSC NDA & NA"
    ],
    "Batch 2: UPSC Central, Banking & Insurance": [
        "UPSC CAPF AC", "UPSC EPFO", "UPSC CMS", "UPSC Geo-Scientist", "UPSC IES/ISS",
        "SBI PO", "SBI Clerk", "IBPS PO", "IBPS Clerk", "IBPS SO",
        "IBPS RRB PO", "IBPS RRB Clerk", "RBI Grade B", "RBI Assistant", "NABARD Grade A",
        "SEBI Grade A", "SIDBI Grade A", "IBPS RRB Scale-II/III", "NHB Assistant Manager", "State Co-op Bank",
        "LIC AAO", "LIC Assistant", "LIC ADO", "NIACL AO & Assistant", "EPFO SSA"
    ],
    "Batch 3: Defence, State PSC & Technical PSUs": [
        "AFCAT", "Army Agniveer", "Air Force Agniveer Vayu", "Navy Agniveer SSR/MR", "Indian Coast Guard Navik",
        "IB ACIO", "IB Security Assistant", "State Police SI (PSI/Daroga)", "State Police Constable", "Territorial Army Officer",
        "State PCS (MPSC/UPPSC/BPSC)", "MPSC Group B & C", "Talathi / Patwari / Lekhpal", "UPSSSC PET / CET", "State High Court ASO/Clerk",
        "Zilla Parishad (ZP) Exams", "State Forest Guard", "FCI AG-III & Manager", "ESIC UDC & MTS", "NVS / EMRS Non-Teaching",
        "GATE", "ISRO Scientist/Engineer", "DRDO Scientist B & CEPTAM", "BARC Scientific Officer", "NIC Scientist B (NIELIT)"
    ],
    "Batch 4: Engineering PSUs, Teaching & Entrance Exams": [
        "AAI ATC Junior Executive", "Maharatna PSU Non-GATE (HPCL/BEL)", "State Electricity Board (MSEDCL AE/JE)", "CPWD / State PWD JE/AE", "CSIR CASE SO/ASO",
        "UGC NET / JRF", "CSIR NET", "CTET", "State TET / MAHA TET", "KVS PRT/TGT/PGT",
        "DSSSB Teachers & DASS", "B.Ed CET (MAH/UP)", "UIIC AO/Assistant", "NICL AO", "State Judiciary (PCS-J)",
        "JEE Main & Advanced", "NEET UG", "State Engg CET (MHT-CET/KCET)", "CUET UG & PG", "CAT",
        "XAT / SNAP / CMAT / MAH-MBA-CET", "CLAT & AILET", "CA / CS / CMA", "NIMCET", "BITSAT & IISER IAT"
    ]
}

def fetch_live_rss_news(query):
    """Fetches free live Google News RSS headlines for real-time exam context."""
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}+exam+notification+india&hl=en-IN&gl=IN&ceid=IN:en"
    headlines = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            root = ET.fromstring(response.read())
            for item in root.findall('.//item')[:10]:
                title = item.find('title').text if item.find('title') is not None else ""
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
                headlines.append(f"- {title} ({pub_date})")
    except Exception as e:
        print(f"RSS fetch warning: {e}")
    return "\n".join(headlines)

def generate_batch(prompt):
    """Calls Gemini Flash-Lite with automatic model fallback if an alias changes."""
    models_to_try = ["gemini-2.5-flash-lite", "gemini-3.5-flash-lite", "gemini-2.5-flash"]
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=8192,
                    temperature=0.4,
                ),
            )
            return json.loads(response.text.strip()), model_name
        except Exception as e:
            print(f"Model {model_name} attempt note: {e}. Trying next...")
            time.sleep(2)
    raise RuntimeError("All model attempts failed. Check your GEMINI_API_KEY.")

def update_all_100_exams():
    all_exams = []
    active_model = "gemini-2.5-flash-lite"

    for batch_name, exam_list in EXAM_BATCHES.items():
        print(f"Generating {batch_name} (25 exams)...")
        live_news = fetch_live_rss_news(batch_name.split(":")[1])

        prompt = f"""
Today is {today_str}.
Live Indian exam news headlines for reference:
{live_news}

Generate an updated JSON array for these exact 25 exams:
{json.dumps(exam_list)}

Each of the 25 objects in the JSON array MUST contain these exact keys:
- "id": Number from 1 to 25
- "exam_name": Exact name from the list
- "sector": MUST be one of these exact strings so website filters work: "Railways", "SSC", "Banking", "UPSC", "State PSC", "PSU/Tech", "Teaching", or "Entrance"
- "status": Current status as of {today_str} (e.g., "Apply Online", "CBT Scheduled Dec/Jan", "Admit Card Soon", "Notification Expected", "Annual Cycle")
- "target_window": Exam or application timeline for 2026-2027
- "daily_tip": A fresh, original, practical 1-sentence study or exam-strategy tip for students.

Return ONLY a valid JSON array containing all 25 objects.
"""
        batch_items, active_model = generate_batch(prompt)
        all_exams.extend(batch_items)

        # Wait 6 seconds between calls to stay well below the 15 RPM limit
        time.sleep(6)

    # Number all 100 exams cleanly from 1 to 100
    for idx, exam in enumerate(all_exams, start=1):
        exam["id"] = idx

    output_data = {
        "last_updated": f"{today_str}, 06:00 AM IST",
        "model_used": active_model,
        "total_exams": len(all_exams),
        "exams": all_exams
    }

    with open("exams-data.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"Success! {len(all_exams)} exams written to exams-data.json using {active_model}.")

if __name__ == "__main__":
    update_all_100_exams()
