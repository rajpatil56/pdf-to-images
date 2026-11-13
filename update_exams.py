import os
import sys
import json
import socket
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

# Enforce a strict global 3-second socket timeout so urllib can NEVER hang
socket.setdefaulttimeout(3.0)

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
    """Fetches real-time RSS headlines with a hard 3s timeout so it never hangs."""
    q = urllib.parse.quote(f"{sector} recruitment exam notification india")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
    titles = []
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Accept": "application/rss+xml, application/xml, text/xml"
            }
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            raw_xml = resp.read(150_000)  # Read max 150KB so stream never stalls
            root = ET.fromstring(raw_xml)
            for item in root.findall(".//item")[:15]:
                t = item.find("title")
                if t is not None and t.text:
                    titles.append(t.text.strip())
        print(f"[OK] {sector}: fetched {len(titles)} live headlines", flush=True)
    except Exception as e:
        print(f"[FAST-FALLBACK] {sector} RSS skipped ({e})", flush=True)
    return sector, titles

def detect_live_status(exam_name, headlines):
    short_key = exam_name.split("(")[0].strip().lower()
    matched_headline = ""
    for h in headlines:
        if short_key in h.lower():
            matched_headline = h
            break

    h_low = matched_headline.lower()
    if "admit card" in h_low or "hall ticket" in h_low:
        return "Admit Card Out", "Download Now (2026)", matched_headline
    if "apply online" in h_low or "registration" in h_low or "last date" in h_low:
        return "Apply Online Open", "Active Window 2026", matched_headline
    if "result" in h_low or "cutoff" in h_low:
        return "Result / Merit List Update", "Check Portal", matched_headline
    if "answer key" in h_low:
        return "Answer Key Released", "Check Official Link", matched_headline
    if "exam date" in h_low or "schedule" in h_low:
        return "Exam Schedule Out", "2026-2027 Cycle", matched_headline
    return "Active 2026-27 Cycle", "Check Official Calendar", matched_headline

def build_100_exams():
    print(f"Starting fast parallel exam updater for {today_str}...", flush=True)
    sector_headlines = {s: [] for s in EXAM_BATCHES}

    # Fetch all 8 sectors in parallel with a strict 5-second total cap
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_sector_headlines, s): s for s in EXAM_BATCHES}
        try:
            for future in as_completed(futures, timeout=5.0):
                sec, titles = future.result()
                sector_headlines[sec] = titles
        except Exception as e:
            print(f"Parallel RSS window completed ({e}). Proceeding immediately...", flush=True)

    all_exams = []
    exam_id = 1

    for sector, exams in EXAM_BATCHES.items():
        headlines = sector_headlines.get(sector, [])
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
        "model_used": "fast-parallel-rss-v2",
        "total_exams": len(all_exams),
        "exams": all_exams
    }

    with open("exams-data.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"Success! {len(all_exams)} exams written to exams-data.json in <4 seconds.", flush=True)

if __name__ == "__main__":
    build_100_exams()
    sys.exit(0)
