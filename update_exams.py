import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# Set Indian Standard Time (IST)
ist = timezone(timedelta(hours=5, minutes=30))
now_ist = datetime.now(ist)
today_str = now_ist.strftime("%d %B %Y")
time_str = now_ist.strftime("%I:%M %p IST")
day_of_year = now_ist.timetuple().tm_yday

EXAM_BATCHES = {
    "SSC": [
        "SSC CGL", "SSC CHSL", "SSC MTS & Havaldar", "SSC GD Constable", "SSC CPO",
        "SSC JE", "SSC Stenographer", "SSC Selection Post", "SSC JHT", "Delhi Police Constable"
    ],
    "Railways": [
        "RRB NTPC Graduate", "RRB NTPC Undergraduate", "RRB Group D", "RRB ALP", "RRB Technician",
        "RRB JE", "RPF SI", "RPF Constable", "DFCCIL", "Metro Rail (DMRC/MahaMetro)"
    ],
    "UPSC": [
        "UPSC CSE (IAS/IPS)", "UPSC IFoS", "UPSC ESE (IES)", "UPSC CDS", "UPSC NDA & NA",
        "UPSC CAPF AC", "UPSC EPFO", "UPSC CMS", "UPSC Geo-Scientist", "UPSC IES/ISS",
        "AFCAT", "IB ACIO", "IB Security Assistant", "Territorial Army Officer", "CSIR CASE SO/ASO"
    ],
    "Banking": [
        "SBI PO", "SBI Clerk", "IBPS PO", "IBPS Clerk", "IBPS SO",
        "IBPS RRB PO", "IBPS RRB Clerk", "RBI Grade B", "RBI Assistant", "NABARD Grade A",
        "SEBI Grade A", "SIDBI Grade A", "IBPS RRB Scale-II/III", "NHB Assistant Manager", "State Co-op Bank",
        "LIC AAO", "LIC Assistant", "LIC ADO", "NIACL AO & Assistant", "EPFO SSA",
        "FCI AG-III & Manager", "ESIC UDC & MTS", "UIIC AO/Assistant", "NICL AO"
    ],
    "State PSC": [
        "State Police SI (PSI/Daroga)", "State Police Constable", "State PCS (MPSC/UPPSC/BPSC)",
        "MPSC Group B & C", "Talathi / Patwari / Lekhpal", "UPSSSC PET / CET",
        "State High Court ASO/Clerk", "Zilla Parishad (ZP) Exams", "State Forest Guard", "State Judiciary (PCS-J)"
    ],
    "PSU/Tech": [
        "Army Agniveer", "Air Force Agniveer Vayu", "Navy Agniveer SSR/MR", "Indian Coast Guard Navik",
        "GATE", "ISRO Scientist/Engineer", "DRDO Scientist B & CEPTAM", "BARC Scientific Officer",
        "NIC Scientist B (NIELIT)", "AAI ATC Junior Executive", "Maharatna PSU Non-GATE (HPCL/BEL)",
        "State Electricity Board (MSEDCL AE/JE)", "CPWD / State PWD JE/AE", "CSIR NET"
    ],
    "Teaching": [
        "NVS / EMRS Non-Teaching", "UGC NET / JRF", "CTET", "State TET / MAHA TET",
        "KVS PRT/TGT/PGT", "DSSSB Teachers & DASS"
    ],
    "Entrance": [
        "B.Ed CET (MAH/UP)", "JEE Main & Advanced", "NEET UG", "State Engg CET (MHT-CET/KCET)",
        "CUET UG & PG", "CAT", "XAT / SNAP / CMAT / MAH-MBA-CET", "CLAT & AILET",
        "CA / CS / CMA", "NIMCET", "BITSAT & IISER IAT"
    ]
}

PORTAL_MAP = {
    "SSC": ("ssc.gov.in", "https://ssc.gov.in/"),
    "Railways": ("rrbapply.gov.in", "https://www.rrbapply.gov.in/"),
    "UPSC": ("upsconline.nic.in", "https://upsconline.nic.in/"),
    "Banking": ("ibps.in", "https://www.ibps.in/"),
    "State PSC": ("mpsc.gov.in", "https://mpsc.gov.in/"),
    "PSU/Tech": ("ncs.gov.in", "https://www.ncs.gov.in/"),
    "Teaching": ("ctet.nic.in", "https://ctet.nic.in/"),
    "Entrance": ("nta.ac.in", "https://www.nta.ac.in/")
}

TIPS_POOL = [
    "Solve at least one full-length previous year mock test under timed conditions today.",
    "Keep scanned copies of your photograph, signature, and category certificate ready before the portal rush.",
    "Focus 40 minutes today on high-weightage current affairs and static GK from the last 6 months.",
    "Review your weak areas from recent mock tests and revise core formula sheets.",
    "Check the official portal early to avoid last-day server slowdowns during form submission.",
    "Practice sectional speed drills in quantitative aptitude and logical reasoning to clear cutoffs."
]

def fetch_sector_headlines(sector):
    """Fetches real-time Google News RSS headlines for the sector in <1 second."""
    q = urllib.parse.quote(f"{sector} recruitment exam notification apply online india")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
    titles = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            root = ET.fromstring(resp.read())
            for item in root.findall(".//item")[:20]:
                t = item.find("title").text if item.find("title") is not None else ""
                titles.append(t)
    except Exception as e:
        print(f"RSS warning for {sector}: {e}")
    return titles

def detect_live_status(exam_name, headlines):
    """Detects live exam status from real news headlines or returns active cycle status."""
    short_key = exam_name.split("(")[0].strip().lower()
    matched_headline = ""
    for h in headlines:
        if short_key in h.lower():
            matched_headline = h
            break

    h_low = matched_headline.lower()
    if "admit card" in h_low or "hall ticket" in h_low:
        status, window = "Admit Card Out", "Download Now (2026)"
    elif "apply online" in h_low or "registration" in h_low or "last date" in h_low:
        status, window = "Apply Online Open", "Active Window 2026"
    elif "result" in h_low or "cutoff" in h_low:
        status, window = "Result / Merit List Update", "Check Portal"
    elif "answer key" in h_low:
        status, window = "Answer Key Released", "Check Official Link"
    elif "exam date" in h_low or "schedule" in h_low:
        status, window = "Exam Schedule Out", "2026-2027 Cycle"
    else:
        status, window = "Active 2026-27 Cycle", "Check Official Calendar"

    return status, window, matched_headline

def build_100_exams():
    all_exams = []
    exam_id = 1

    for sector, exams in EXAM_BATCHES.items():
        print(f"Fetching live RSS feed for {sector}...")
        headlines = fetch_sector_headlines(sector)
        default_portal, default_url = PORTAL_MAP.get(sector, ("ncs.gov.in", "https://www.ncs.gov.in/"))

        for exam_name in exams:
            status, window, headline = detect_live_status(exam_name, headlines)
            tip_idx = (exam_id + day_of_year) % len(TIPS_POOL)
            base_tip = TIPS_POOL[tip_idx]
            if headline:
                clean_news = headline.split(" - ")[0]
                daily_tip = f"Latest Update: {clean_news}. {base_tip}"
            else:
                daily_tip = f"Prepare systematically for {exam_name}: {base_tip}"

            all_exams.append({
                "id": exam_id,
                "exam_name": exam_name,
                "sector": sector,
                "status": status,
                "last_date": window,
                "target_window": "2026-2027 Session",
                "official_portal": default_portal,
                "apply_url": default_url,
                "daily_tip": daily_tip
            })
            exam_id += 1

    output_data = {
        "last_updated": f"{today_str}, {time_str}",
        "model_used": "live-rss-scraper-v1",
        "total_exams": len(all_exams),
        "exams": all_exams
    }

    with open("exams-data.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"Success! {len(all_exams)} exams updated in exams-data.json with zero API keys.")

if __name__ == "__main__":
    build_100_exams()
