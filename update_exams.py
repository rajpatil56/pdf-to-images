import os
import json
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# Optional Google GenAI SDK import for fallback
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

# API Keys & Antigravity Configuration from GitHub Secrets
ANTIGRAVITY_API_KEY = os.environ.get("ANTIGRAVITY_API_KEY", "").strip()
ANTIGRAVITY_BASE_URL = os.environ.get(
    "ANTIGRAVITY_BASE_URL",
    "https://api.antigravity.dev/v1/chat/completions"
).strip()
ANTIGRAVITY_MODEL = os.environ.get("ANTIGRAVITY_MODEL", "antigravity-default").strip()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if (genai and GEMINI_API_KEY) else None

# Set Indian Standard Time (IST)
ist = timezone(timedelta(hours=5, minutes=30))
now_ist = datetime.now(ist)
today_str = now_ist.strftime("%d %B %Y")
time_str = now_ist.strftime("%I:%M %p IST")

# All 100 exams grouped into 4 batches of 25 exams
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

def clean_json_response(raw_text):
    """Strips markdown code fences and parses a JSON array safely."""
    raw = raw_text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    start_idx = raw.find("[")
    end_idx = raw.rfind("]")
    if start_idx != -1 and end_idx != -1:
        raw = raw[start_idx:end_idx + 1]
    return json.loads(raw)

def fetch_live_rss_news(query):
    """Fetches free live Google News RSS headlines with a 5-second timeout."""
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}+exam+notification+india&hl=en-IN&gl=IN&ceid=IN:en"
    headlines = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            root = ET.fromstring(response.read())
            for item in root.findall('.//item')[:5]:
                title = item.find('title').text if item.find('title') is not None else ""
                headlines.append(f"- {title}")
    except Exception:
        pass
    return "\n".join(headlines)

def call_antigravity_api(prompt):
    """Calls Antigravity API (OpenAI-compatible /v1/chat/completions format)."""
    if not ANTIGRAVITY_API_KEY:
        return None, None

    antigravity_models = [
        ANTIGRAVITY_MODEL,
        "antigravity-agent",
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
        "claude-3-5-sonnet"
    ]

    for model_name in antigravity_models:
        try:
            payload = json.dumps({
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "You are an Indian government exam data API. Return ONLY a valid JSON array."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 8192
            }).encode("utf-8")

            req = urllib.request.Request(
                ANTIGRAVITY_BASE_URL,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {ANTIGRAVITY_API_KEY}",
                    "x-api-key": ANTIGRAVITY_API_KEY,
                    "User-Agent": "RojgaarNam-Updater/1.0"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=45) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                content = (
                    resp_data.get("choices", [{}])[0].get("message", {}).get("content")
                    or resp_data.get("text")
                    or resp_data.get("output")
                    or ""
                )
                parsed = clean_json_response(content)
                if isinstance(parsed, list) and len(parsed) > 0:
                    print(f"Batch generated via Antigravity ({model_name})")
                    return parsed, f"antigravity:{model_name}"
        except Exception as e:
            print(f"Antigravity ({model_name}) note: {e}")
            time.sleep(2)

    return None, None

def generate_batch(prompt):
    """Tries Antigravity API first, then falls back to Google Gemini 3.8 / 3.5 / 2.5 models."""
    # 1. Primary: Antigravity API
    ag_data, ag_model = call_antigravity_api(prompt)
    if ag_data:
        return ag_data, ag_model

    # 2. Fallback: Gemini SDK (with retry rounds for 503 spikes)
    if gemini_client:
        gemini_models = [
            "gemini-3.8-flash",
            "gemini-3.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite"
        ]
        for round_num in range(1, 5):
            for model_name in gemini_models:
                try:
                    response = gemini_client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            max_output_tokens=8192,
                            temperature=0.3,
                        ),
                    )
                    parsed = clean_json_response(response.text)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        print(f"Batch generated via Gemini ({model_name}) on round {round_num}")
                        return parsed, model_name
                except Exception as e:
                    print(f"[Round {round_num}/4] {model_name} note: {e}")
                    time.sleep(2)
            time.sleep(round_num * 4)

    return None, None

def update_all_100_exams():
    existing_exams = []
    if os.path.exists("exams-data.json"):
        try:
            with open("exams-data.json", "r", encoding="utf-8") as f:
                existing_exams = json.load(f).get("exams", [])
        except Exception:
            existing_exams = []

    all_exams = []
    active_model = "antigravity"

    for batch_idx, (batch_name, exam_list) in enumerate(EXAM_BATCHES.items()):
        print(f"Generating {batch_name} (25 exams)...")
        live_news = fetch_live_rss_news(batch_name.split(":")[1])

        prompt = f"""
Today is {today_str}.
Live news reference: {live_news}

Generate a valid JSON array for these exact 25 exams:
{json.dumps(exam_list)}

Each of the 25 objects in the JSON array MUST contain these exact keys:
- "id": Number from 1 to 25
- "exam_name": Exact name from the list
- "sector": MUST be one of: "Railways", "SSC", "Banking", "UPSC", "State PSC", "PSU/Tech", "Teaching", or "Entrance"
- "status": Current status as of {today_str} (e.g., "Apply Online", "CBT Scheduled", "Admit Card Out")
- "last_date": Last Date to Fill Form (e.g., "30 Nov 2026" or "TBA")
- "target_window": Timeline for 2026-2027
- "official_portal": Official domain (e.g., "rrbapply.gov.in", "ssc.gov.in", "upsconline.nic.in", "ibps.in")
- "apply_url": Full https:// URL (e.g., "https://www.rrbapply.gov.in/")
- "daily_tip": 1-sentence study or form-filling tip.

Return ONLY a valid JSON array.
"""
        batch_items, used_model = generate_batch(prompt)
        if batch_items:
            all_exams.extend(batch_items)
            active_model = used_model
        else:
            start_i = batch_idx * 25
            fallback_slice = existing_exams[start_i:start_i + 25]
            print(f"Using cached data for {batch_name} so
