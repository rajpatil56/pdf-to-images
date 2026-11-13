import os
import sys
import re
import json
import socket
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

# Enforce a strict global 3-second socket timeout so urllib never hangs
socket.setdefaulttimeout(3.0)

# Set Indian Standard Time (IST)
ist = timezone(timedelta(hours=5, minutes=30))
now_ist = datetime.now(ist)
today_str = now_ist.strftime("%d %B %Y")
time_str = now_ist.strftime("%I:%M %p IST")
day_of_year = now_ist.timetuple().tm_yday

# Master 100-Exam Calendar Database:
# Format: "Exam Name": (Sector, Status, Last Date to Fill Form, Exam Schedule Window, Official Portal, Apply URL)
EXAM_CALENDAR_DB = {
    # --- SSC (10) ---
    "SSC CGL": ("SSC", "Tier-II Exam Scheduled", "Closed (Next: Jun 2027)", "Jan - Feb 2027", "ssc.gov.in", "https://ssc.gov.in/"),
    "SSC CHSL": ("SSC", "Tier-II Schedule Out", "Closed (Next: May 2027)", "Jan 2027", "ssc.gov.in", "https://ssc.gov.in/"),
    "SSC MTS & Havaldar": ("SSC", "CBT Exam Ongoing", "Closed (Next: Jul 2027)", "Nov - Dec 2026", "ssc.gov.in", "https://ssc.gov.in/"),
    "SSC GD Constable": ("SSC", "Apply Online / CBT Prep", "14 Nov 2026", "Jan - Feb 2027", "ssc.gov.in", "https://ssc.gov.in/"),
    "SSC CPO": ("SSC", "Paper-II Scheduled", "Closed (Next: May 2027)", "Dec 2026", "ssc.gov.in", "https://ssc.gov.in/"),
    "SSC JE": ("SSC", "Paper-II Result / Cycle", "18 Nov 2026", "May - Jun 2027", "ssc.gov.in", "https://ssc.gov.in/"),
    "SSC Stenographer": ("SSC", "CBT Exam / Skill Test", "25 Nov 2026", "Dec 2026 - Jan 2027", "ssc.gov.in", "https://ssc.gov.in/"),
    "SSC Selection Post": ("SSC", "Phase-XIII Notification", "15 Apr 2027", "Jun - Jul 2027", "ssc.gov.in", "https://ssc.gov.in/"),
    "SSC JHT": ("SSC", "Paper-II Descriptive", "Closed (Next: Aug 2027)", "Dec 2026", "ssc.gov.in", "https://ssc.gov.in/"),
    "Delhi Police Constable": ("SSC", "Online Form Expected", "30 Sep 2027", "Nov - Dec 2027", "ssc.gov.in", "https://ssc.gov.in/"),

    # --- RAILWAYS (10) ---
    "RRB NTPC Graduate": ("Railways", "CEN 05/2026 Form / CBT", "20 Nov 2026", "Dec 2026 - Jan 2027", "rrbapply.gov.in", "https://www.rrbapply.gov.in/"),
    "RRB NTPC Undergraduate": ("Railways", "CEN 07/2026 Apply Online", "27 Nov 2026", "Jan - Feb 2027", "rrbapply.gov.in", "https://www.rrbapply.gov.in/"),
    "RRB Group D": ("Railways", "Level-1 Notification Out", "15 Dec 2026", "Feb - Mar 2027", "rrbapply.gov.in", "https://www.rrbapply.gov.in/"),
    "RRB ALP": ("Railways", "CBT-1 & CBT-2 Cycle", "Closed (Admit Card Out)", "Nov - Dec 2026", "rrbapply.gov.in", "https://www.rrbapply.gov.in/"),
    "RRB Technician": ("Railways", "CEN Technician CBT", "Closed (Admit Card Out)", "Dec 2026", "rrbapply.gov.in", "https://www.rrbapply.gov.in/"),
    "RRB JE": ("Railways", "CBT-1 Admit Card Soon", "Closed (CBT-1 in Dec)", "16 - 18 Dec 2026", "rrbapply.gov.in", "https://www.rrbapply.gov.in/"),
    "RPF SI": ("Railways", "CBT Admit Card Out", "Closed (Exam in Dec)", "02 - 12 Dec 2026", "rrbapply.gov.in", "https://www.rrbapply.gov.in/"),
    "RPF Constable": ("Railways", "CBT Exam Scheduled", "Closed (CBT in Jan)", "Jan - Feb 2027", "rrbapply.gov.in", "https://www.rrbapply.gov.in/"),
    "DFCCIL": ("Railways", "Executive / MTS Form", "28 Jan 2027", "Mar - Apr 2027", "dfccil.com", "https://dfccil.com/"),
    "Metro Rail (DMRC/MahaMetro)": ("PSU/Tech", "JE / Station Controller", "10 Dec 2026", "Jan - Feb 2027", "mahametro.org", "https://www.mahametro.org/"),

    # --- UPSC & CENTRAL DEFENCE (15) ---
    "UPSC CSE (IAS/IPS)": ("UPSC", "2027 Notification Soon", "11 Feb 2027 (Form Closes)", "23 May 2027 (Prelims)", "upsconline.nic.in", "https://upsconline.nic.in/"),
    "UPSC IFoS": ("UPSC", "2027 Notification Soon", "11 Feb 2027 (Form Closes)", "23 May 2027 (Prelims)", "upsconline.nic.in", "https://upsconline.nic.in/"),
    "UPSC ESE (IES)": ("UPSC", "Prelims Scheduled", "22 Nov 2026", "08 Feb 2027 (Prelims)", "upsconline.nic.in", "https://upsconline.nic.in/"),
    "UPSC CDS": ("UPSC", "CDS-I 2027 Apply Online", "31 Dec 2026", "13 Apr 2027", "upsconline.nic.in", "https://upsconline.nic.in/"),
    "UPSC NDA & NA": ("UPSC", "NDA-I 2027 Apply Online", "31 Dec 2026", "13 Apr 2027", "upsconline.nic.in", "https://upsconline.nic.in/"),
    "UPSC CAPF AC": ("UPSC", "2027 Cycle Notification", "13 May 2027", "03 Aug 2027", "upsconline.nic.in", "https://upsconline.nic.in/"),
    "UPSC EPFO": ("UPSC", "EO/AO & APFC Form", "15 Mar 2027", "Jun 2027", "upsconline.nic.in", "https://upsconline.nic.in/"),
    "UPSC CMS": ("UPSC", "Medical Services Form", "11 Mar 2027", "20 Jul 2027", "upsconline.nic.in", "https://upsconline.nic.in/"),
    "UPSC Geo-Scientist": ("UPSC", "Prelims Admit Card Soon", "Closed (Exam Feb 2027)", "09 Feb 2027", "upsconline.nic.in", "https://upsconline.nic.in/"),
    "UPSC IES/ISS": ("UPSC", "2027 Form Window", "04 Mar 2027", "20 Jun 2027", "upsconline.nic.in", "https://upsconline.nic.in/"),
    "AFCAT": ("UPSC", "AFCAT 01/2027 Apply Online", "30 Dec 2026", "22 - 24 Feb 2027", "afcat.cdac.in", "https://afcat.cdac.in/"),
    "IB ACIO": ("UPSC", "Grade-II Executive Form", "20 Jan 2027", "Mar 2027", "mha.gov.in", "https://www.mha.gov.in/"),
    "IB Security Assistant": ("UPSC", "SA / MTS Recruitment", "15 Feb 2027", "Apr 2027", "mha.gov.in", "https://www.mha.gov.in/"),
    "Territorial Army Officer": ("UPSC", "TA PIB Online Form", "20 Nov 2026", "Dec 2026", "jointerritorialarmy.gov.in", "https://www.jointerritorialarmy.gov.in/"),
    "CSIR CASE SO/ASO": ("UPSC", "Stage-II / Final Merit", "10 Feb 2027", "Apr 2027", "csir.res.in", "https://www.csir.res.in/"),

    # --- BANKING & INSURANCE (23) ---
    "SBI PO": ("Banking", "Apply Online Open", "19 Jan 2027", "08 & 15 Mar 2027 (Prelims)", "sbi.co.in/careers", "https://sbi.co.in/web/careers"),
    "SBI Clerk": ("Banking", "Junior Associates Form", "07 Jan 2027", "Feb 2027 (Prelims)", "sbi.co.in/careers", "https://sbi.co.in/web/careers"),
    "IBPS PO": ("Banking", "Mains Exam Scheduled", "Closed (Mains 30 Nov)", "30 Nov 2026 (Mains)", "ibps.in", "https://www.ibps.in/"),
    "IBPS Clerk": ("Banking", "Mains Result / Cycle", "Closed (Next: Jul 2027)", "Jan - Apr 2027", "ibps.in", "https://www.ibps.in/"),
    "IBPS SO": ("Banking", "Mains Admit Card Out", "Closed (Mains 14 Dec)", "14 Dec 2026 (Mains)", "ibps.in", "https://www.ibps.in/"),
    "IBPS RRB PO": ("Banking", "Interview Call Letter", "Closed (Interviews Now)", "Nov - Dec 2026", "ibps.in", "https://www.ibps.in/"),
    "IBPS RRB Clerk": ("Banking", "Provisional Allotment", "Closed (Next: Jun 2027)", "01 Jan 2027 (Allotment)", "ibps.in", "https://www.ibps.in/"),
    "RBI Grade B": ("Banking", "Phase-II / 2027 Cycle", "25 Apr 2027", "Jun - Jul 2027", "opportunities.rbi.org.in", "https://opportunities.rbi.org.in/"),
    "RBI Assistant": ("Banking", "Online Registration Soon", "15 Dec 2026", "Jan - Feb 2027", "opportunities.rbi.org.in", "https://opportunities.rbi.org.in/"),
    "NABARD Grade A": ("Banking", "RDBS Notification Cycle", "18 Aug 2027", "Sep - Oct 2027", "nabard.org", "https://www.nabard.org/careers.aspx"),
    "SEBI Grade A": ("Banking", "Assistant Manager Form", "30 Mar 2027", "May 2027", "sebi.gov.in", "https://www.sebi.gov.in/"),
    "SIDBI Grade A": ("Banking", "Apply Online Active", "02 Dec 2026", "Dec 2026 - Jan 2027", "sidbi.in", "https://www.sidbi.in/en/careers"),
    "IBPS RRB Scale-II/III": ("Banking", "Interview Phase", "Closed (Interviews Dec)", "Dec 2026", "ibps.in", "https://www.ibps.in/"),
    "NHB Assistant Manager": ("Banking", "Scale-I Form Window", "12 Feb 2027", "Mar 2027", "nhb.org.in", "https://nhb.org.in/"),
    "State Co-op Bank": ("Banking", "MStCB / District Bank", "10 Dec 2026", "Jan 2027", "ibps.in", "https://www.mscbank.com/careers"),
    "LIC AAO": ("Banking", "Notification Expected", "10 Feb 2027", "Mar - Apr 2027", "licindia.in", "https://licindia.in/bottom-links/careers"),
    "LIC Assistant": ("Banking", "Clerical Recruitment", "25 Feb 2027", "Apr 2027", "licindia.in", "https://licindia.in/bottom-links/careers"),
    "LIC ADO": ("Banking", "Apprentice Dev Officer", "15 Mar 2027", "May 2027", "licindia.in", "https://licindia.in/bottom-links/careers"),
    "NIACL AO & Assistant": ("Banking", "Apply Online / Mains", "05 Feb 2027", "Mar 2027", "newindia.co.in", "https://www.newindia.co.in/portal/readMore/Recruitment"),
    "EPFO SSA": ("Banking", "Social Security Asst", "28 Mar 2027", "May 2027", "epfindia.gov.in", "https://www.epfindia.gov.in/"),
    "FCI AG-III & Manager": ("Banking", "Category-II & III Form", "22 Dec 2026", "Feb 2027", "fci.gov.in", "https://fci.gov.in/"),
    "ESIC UDC & MTS": ("Banking", "Bumper Vacancy Form", "18 Jan 2027", "Mar 2027", "esic.gov.in", "https://www.esic.gov.in/recruitments"),
    "UIIC AO/Assistant": ("Banking", "Apply Online Open", "25 Nov 2026", "Dec 2026 - Jan 2027", "uiic.co.in", "https://uiic.co.in/en/careers/recruitment"),
    "NICL AO": ("Banking", "Administrative Officer", "30 Jan 2027", "Mar 2027", "nationalinsurance.nic.co.in", "https://nationalinsurance.nic.co.in/en/recruitments"),

    # --- STATE PSC & POLICE (10) ---
    "State Police SI (PSI/Daroga)": ("State PSC", "Online Form / Physical", "15 Dec 2026", "Jan - Feb 2027", "mpsc.gov.in", "https://mpsc.gov.in/"),
    "State Police Constable": ("State PSC", "Ground & Written Test", "10 Jan 2027", "Feb - Mar 2027", "mahapolice.gov.in", "https://www.mahapolice.gov.in/"),
    "State PCS (MPSC/UPPSC/BPSC)": ("State PSC", "Prelims Scheduled", "Closed (Exam Dec 2026)", "01 - 22 Dec 2026", "mpsc.gov.in", "https://mpsc.gov.in/"),
    "MPSC Group B & C": ("State PSC", "Combine Prelims Cycle", "14 Nov 2026", "05 Jan & 02 Feb 2027", "mpsc.gov.in", "https://mpsc.gov.in/"),
    "Talathi / Patwari / Lekhpal": ("State PSC", "Revenue Dept Recruitment", "28 Feb 2027", "Apr - May 2027", "mahabhumi.gov.in", "https://mahabhumi.gov.in/"),
    "UPSSSC PET / CET": ("State PSC", "Annual Eligibility Test", "30 Aug 2027", "Oct 2027", "upsssc.gov.in", "https://upsssc.gov.in/"),
    "State High Court ASO/Clerk": ("State PSC", "Bombay HC Clerk/Peon", "18 Dec 2026", "Jan - Feb 2027", "bombayhighcourt.nic.in", "https://bombayhighcourt.nic.in/recruitment.php"),
    "Zilla Parishad (ZP) Exams": ("State PSC", "Gramsevak / Arogya Form", "20 Jan 2027", "Feb - Mar 2027", "rdd.maharashtra.gov.in", "https://rdd.maharashtra.gov.in/"),
    "State Forest Guard": ("State PSC", "Vanrakshak Recruitment", "15 Feb 2027", "Apr 2027", "mahaforest.gov.in", "https://mahaforest.gov.in/"),
    "State Judiciary (PCS-J)": ("State PSC", "Civil Judge Prelims", "25 Jan 2027", "Mar 2027", "mpsc.gov.in", "https://mpsc.gov.in/"),

    # --- PSU / TECH / DEFENCE (14) ---
    "Army Agniveer": ("PSU/Tech", "CEE Online Registration", "25 Mar 2027", "Apr - May 2027", "joinindianarmy.nic.in", "https://joinindianarmy.nic.in/"),
    "Air Force Agniveer Vayu": ("PSU/Tech", "Intake 01/2027 Form", "27 Jan 2027", "Mar 2027", "agnipathvayu.cdac.in", "https://agnipathvayu.cdac.in/"),
    "Navy Agniveer SSR/MR": ("PSU/Tech", "Batch 02/2027 Form", "10 Dec 2026", "Jan - Feb 2027", "joinindiannavy.gov.in", "https://www.joinindiannavy.gov.in/"),
    "Indian Coast Guard Navik": ("PSU/Tech", "CGEPT GD/DB Form", "05 Dec 2026", "Jan 2027", "joinindiancoastguard.cdac.in", "https://joinindiancoastguard.cdac.in/"),
    "GATE": ("PSU/Tech", "Admit Card on 02 Jan", "Closed (Exam Feb 2027)", "01, 02, 15, 16 Feb 2027", "gate2026.iitg.ac.in", "https://gate.iitkgp.ac.in/"),
    "ISRO Scientist/Engineer": ("PSU/Tech", "ICRB Recruitment Form", "19 Dec 2026", "Feb 2027", "isro.gov.in/Careers.html", "https://www.isro.gov.in/Careers.html"),
    "DRDO Scientist B & CEPTAM": ("PSU/Tech", "RAC / CEPTAM-11 Form", "15 Jan 2027", "Mar 2027", "drdo.gov.in/careers", "https://www.drdo.gov.in/drdo/careers"),
    "BARC Scientific Officer": ("PSU/Tech", "OCES / DGFS 2027 Apply", "26 Jan 2027", "08 - 09 Mar 2027", "barconlineexam.in", "https://www.barconlineexam.in/"),
    "NIC Scientist B (NIELIT)": ("PSU/Tech", "Scientific Officer Form", "20 Feb 2027", "Apr 2027", "calicut.nielit.in", "https://recruitment-delhi.nielit.gov.in/"),
    "AAI ATC Junior Executive": ("PSU/Tech", "Air Traffic Control Form", "10 Jan 2027", "Feb - Mar 2027", "aai.aero", "https://www.aai.aero/en/careers/recruitment"),
    "Maharatna PSU Non-GATE (HPCL/BEL)": ("PSU/Tech", "Probationary Engineer", "30 Nov 2026", "Jan 2027", "bel-india.in", "https://bel-india.in/careers/"),
    "State Electricity Board (MSEDCL AE/JE)": ("PSU/Tech", "Mahavitaran Vidyut Sahayak", "20 Dec 2026", "Jan - Feb 2027", "mahadiscom.in", "https://www.mahadiscom.in/en/home/"),
    "CPWD / State PWD JE/AE": ("PSU/Tech", "WCD / PWD Engineering", "15 Jan 2027", "Feb - Mar 2027", "mahapwd.gov.in", "https://mahapwd.gov.in/"),
    "CSIR NET": ("PSU/Tech", "Dec Session Apply Online", "30 Dec 2026", "16 - 28 Feb 2027", "csirnet.nta.ac.in", "https://csirnet.nta.ac.in/"),

    # --- TEACHING (6) ---
    "NVS / EMRS Non-Teaching": ("Teaching", "JSA / Lab Attendant Form", "15 Jan 2027", "Mar 2027", "navodaya.gov.in", "https://navodaya.gov.in/"),
    "UGC NET / JRF": ("Teaching", "Dec Cycle Apply Online", "11 Dec 2026", "01 - 19 Jan 2027", "ugcnet.nta.ac.in", "https://ugcnet.nta.ac.in/"),
    "CTET": ("Teaching", "Admit Card / Dec Exam", "Closed (Exam 14 Dec)", "14 Dec 2026", "ctet.nic.in", "https://ctet.nic.in/"),
    "State TET / MAHA TET": ("Teaching", "MAHA TET / TAIT Cycle", "10 Jan 2027", "Feb 2027", "mahatet.in", "https://mahatet.in/"),
    "KVS PRT/TGT/PGT": ("Teaching", "Direct Recruitment Cycle", "28 Feb 2027", "Apr - May 2027", "kvsangathan.nic.in", "https://kvsangathan.nic.in/"),
    "DSSSB Teachers & DASS": ("Teaching", "PGT / TGT Online Form", "07 Feb 2027", "Mar - Apr 2027", "dsssbonline.nic.in", "https://dsssbonline.nic.in/"),

    # --- ENTRANCE EXAMS (11) ---
    "B.Ed CET (MAH/UP)": ("Entrance", "MAH B.Ed CET Registration", "28 Jan 2027", "24 - 26 Mar 2027", "cetcell.mahacet.org", "https://cetcell.mahacet.org/"),
    "JEE Main & Advanced": ("Entrance", "Session-1 Apply Online", "22 Nov 2026 (11:50 PM)", "22 - 31 Jan 2027", "jeemain.nta.nic.in", "https://jeemain.nta.nic.in/"),
    "NEET UG": ("Entrance", "2027 Registration Soon", "07 Mar 2027", "04 May 2027", "neet.nta.nic.in", "https://neet.nta.nic.in/"),
    "State Engg CET (MHT-CET/KCET)": ("Entrance", "MHT-CET 2027 Apply Online", "15 Feb 2027 (Without Late Fee)", "09 - 27 Apr 2027", "cetcell.mahacet.org", "https://cetcell.mahacet.org/"),
    "CUET UG & PG": ("Entrance", "CUET PG Form Open", "02 Feb 2027 (PG) / Mar (UG)", "13 - 31 Mar 2027", "nta.ac.in", "https://exams.nta.ac.in/CUET-UG/"),
    "CAT": ("Entrance", "Admit Card Downloaded", "Closed (Exam 24 Nov)", "24 Nov 2026", "iimcat.ac.in", "https://iimcat.ac.in/"),
    "XAT / SNAP / CMAT / MAH-MBA-CET": ("Entrance", "XAT & MBA-CET Apply Open", "30 Nov 2026 (XAT) / 25 Jan (CET)", "05 Jan & 15 Mar 2027", "xatonline.in", "https://cetcell.mahacet.org/"),
    "CLAT & AILET": ("Entrance", "Admit Card Released", "Closed (Exam 01 Dec)", "01 Dec 2026", "consortiumofnlus.ac.in", "https://consortiumofnlus.ac.in/"),
    "CA / CS / CMA": ("Entrance", "Jan/May 2027 Exam Form", "23 Nov 2026", "Jan 2027", "eservices.icai.org", "https://eservices.icai.org/"),
    "NIMCET": ("Entrance", "NIT MCA Registration", "15 Apr 2027", "Jun 2027", "nimcet.admissions.nic.in", "https://nimcet.admissions.nic.in/"),
    "BITSAT & IISER IAT": ("Entrance", "Session-1 Application", "18 Apr 2027", "May 2027", "bitsadmission.com", "https://www.bitsadmission.com/")
}

TIPS_POOL = [
    "Complete your online form registration at least 3 days before the Last Date to avoid payment gateway timeouts.",
    "Verify that your uploaded passport photo and signature strictly match the official pixel and KB size limits.",
    "Solve at least one full-length previous year CBT paper under timed conditions today.",
    "Focus 45 minutes today on high-weightage current affairs and static GK from the last 6 months.",
    "Download and save a PDF copy of your submitted application form and fee receipt for document verification.",
    "Practice sectional speed drills in quantitative aptitude and logical reasoning to clear the cutoff comfortably."
]

DATE_REGEX = re.compile(
    r"\b(\d{1,2}\s+(?:Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|September|Oct|October|Nov|November|Dec|December)(?:\s+202[6-7])?)\b",
    re.IGNORECASE
)

def fetch_sector_headlines(sector):
    """Fetches real-time RSS headlines with a hard 3s timeout so it never hangs."""
    q = urllib.parse.quote(f"{sector} exam recruitment apply online last date 2026 2027 india")
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
            raw_xml = resp.read(150_000)
            root = ET.fromstring(raw_xml)
            for item in root.findall(".//item")[:20]:
                t = item.find("title")
                if t is not None and t.text:
                    titles.append(t.text.strip())
        print(f"[OK] {sector}: fetched {len(titles)} live headlines", flush=True)
    except Exception as e:
        print(f"[FAST-FALLBACK] {sector} RSS skipped ({e})", flush=True)
    return sector, titles

def enrich_with_live_news(exam_name, default_status, default_last_date, headlines):
    """Checks if today's live news mentions a new date or status for this exam."""
    short_key = exam_name.split("(")[0].strip().lower()
    matched_headline = ""
    for h in headlines:
        if short_key in h.lower():
            matched_headline = h
            break

    if not matched_headline:
        return default_status, default_last_date, ""

    h_low = matched_headline.lower()
    status = default_status
    last_date = default_last_date

    # Extract specific date if mentioned in the live news headline
    date_match = DATE_REGEX.search(matched_headline)
    if date_match and ("last date" in h_low or "apply" in h_low or "deadline" in h_low or "extend" in h_low):
        extracted = date_match.group(1)
        if "202" not in extracted:
            extracted += " 2026"
        last_date = f"{extracted} (Live Update)"

    if "admit card" in h_low or "hall ticket" in h_low:
        status = "Admit Card Out"
    elif "apply online" in h_low or "registration" in h_low:
        status = "Apply Online Open"
    elif "result" in h_low:
        status = "Result / Merit Update"
    elif "answer key" in h_low:
        status = "Answer Key Out"

    return status, last_date, matched_headline

def build_100_exams():
    print(f"Starting 100-Exam Calendar + Live RSS Updater for {today_str}...", flush=True)
    sectors = sorted(list({v[0] for v in EXAM_CALENDAR_DB.values()}))
    sector_headlines = {s: [] for s in sectors}

    # Fetch all sectors in parallel (max 4 seconds)
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_sector_headlines, s): s for s in sectors}
        try:
            for future in as_completed(futures, timeout=4.5):
                sec, titles = future.result()
                sector_headlines[sec] = titles
        except Exception as e:
            print(f"Parallel RSS window completed ({e}).", flush=True)

    all_exams = []
    for exam_id, (exam_name, info) in enumerate(EXAM_CALENDAR_DB.items(), start=1):
        sector, def_status, def_last_date, target_window, portal, apply_url = info
        headlines = sector_headlines.get(sector, [])

        status, last_date, headline = enrich_with_live_news(
            exam_name, def_status, def_last_date, headlines
        )

        tip_idx = (exam_id + day_of_year) % len(TIPS_POOL)
        base_tip = TIPS_POOL[tip_idx]
        if headline:
            clean_news = headline.split(" - ")[0]
            daily_tip = f"Latest News: {clean_news}. {base_tip}"
        else:
            daily_tip = f"{exam_name} ({target_window}): {base_tip}"

        all_exams.append({
            "id": exam_id,
            "exam_name": exam_name,
            "sector": sector,
            "status": status,
            "last_date": last_date,
            "target_window": target_window,
            "official_portal": portal,
            "apply_url": apply_url,
            "daily_tip": daily_tip
        })

    output_data = {
        "last_updated": f"{today_str}, {time_str}",
        "model_used": "calendar-db-plus-live-rss-v3",
        "total_exams": len(all_exams),
        "exams": all_exams
    }

    with open("exams-data.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"Success! {len(all_exams)} exams written with exact Last Dates & Portals.", flush=True)

if __name__ == "__main__":
    build_100_exams()
    sys.exit(0)
