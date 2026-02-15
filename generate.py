#!/usr/bin/env python3
"""
generate.py — Downloads the ESMA MiCA CASP register CSV and generates
a self-contained index.html dashboard (vanilla HTML/CSS/JS, no dependencies).

Usage:
    python generate.py                     # downloads CSV from ESMA
    python generate.py --csv CASPS.csv     # uses local CSV file
"""

import csv
import io
import json
import sys
import argparse
from collections import Counter
from datetime import datetime

# === ESMA CSV URL ===
ESMA_CSV_URL = "https://www.esma.europa.eu/sites/default/files/2024-12/CASPS.csv"

COUNTRY_NAMES = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CY": "Cyprus",
    "CZ": "Czechia", "DE": "Germany", "DK": "Denmark", "EE": "Estonia",
    "EL": "Greece", "ES": "Spain", "FI": "Finland", "FR": "France",
    "GR": "Greece", "HR": "Croatia", "HU": "Hungary", "IE": "Ireland",
    "IS": "Iceland", "IT": "Italy", "LI": "Liechtenstein", "LT": "Lithuania",
    "LU": "Luxembourg", "LV": "Latvia", "MT": "Malta", "NL": "Netherlands",
    "NO": "Norway", "PL": "Poland", "PT": "Portugal", "RO": "Romania",
    "SE": "Sweden", "SI": "Slovenia", "SK": "Slovakia",
}

AUTHORITY_SHORT = {
    "AT": "FMA", "BE": "NBB", "BG": "FSC", "CY": "CySEC", "CZ": "CNB",
    "DE": "BaFin", "DK": "DFSA", "EE": "FSA", "ES": "CNMV", "FI": "FIN-FSA",
    "FR": "AMF", "GR": "HCMC", "HR": "HANFA", "HU": "MNB", "IE": "CBI",
    "IS": "FME", "IT": "CONSOB", "LI": "FMA LI", "LT": "Bank of Lithuania",
    "LU": "CSSF", "LV": "FKTK", "MT": "MFSA", "NL": "AFM", "NO": "Finanstilsynet",
    "PL": "KNF", "PT": "CMVM", "RO": "ASF", "SE": "Finansinspektionen",
    "SI": "ATVP", "SK": "NBS",
}


def download_csv(url):
    """Download CSV from ESMA."""
    import urllib.request
    print(f"Downloading CSV from {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    # Try UTF-8 BOM first
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    print(f"Downloaded {len(text)} bytes")
    return text


def parse_csv(text):
    """Parse CSV text into list of dicts."""
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        rows.append(row)
    return rows


def get_home_country(row):
    hs = row.get("ae_homeMemberState", "").strip()
    if not hs:
        hs = row.get("ae_lei_cou_code", "").strip()
    return hs


def parse_services(svc_str):
    """Parse service string and return normalized service labels."""
    services = []
    for s in svc_str.split("|"):
        s = s.strip().lower()
        if not s:
            continue
        if "custody" in s or "administration" in s:
            services.append("Custody & admin")
        elif "trading platform" in s or "operation" in s:
            services.append("Trading platform")
        elif "exchange" in s and "fund" in s:
            services.append("Exchange crypto/fiat")
        elif "exchange" in s and "other" in s:
            services.append("Exchange crypto/crypto")
        elif "execution" in s:
            services.append("Order execution")
        elif "placing" in s:
            services.append("Placing")
        elif "reception" in s or "transmission" in s:
            services.append("Reception & transmission")
        elif "advice" in s:
            services.append("Advice")
        elif "portfolio" in s:
            services.append("Portfolio mgmt")
        elif "transfer" in s:
            services.append("Transfer services")
    return list(set(services))  # deduplicate per row


def analyze_data(rows):
    """Analyze CSV rows and return dashboard data."""
    # Deduplicate by LEI
    seen_leis = set()
    unique_rows = []
    for r in rows:
        lei = r.get("ae_lei", "").strip()
        if lei and lei in seen_leis:
            continue
        if lei:
            seen_leis.add(lei)
        unique_rows.append(r)

    total = len(unique_rows)

    # Country counts
    country_counts = Counter()
    for r in unique_rows:
        hc = get_home_country(r)
        if hc:
            country_counts[hc] += 1

    country_data = []
    for code, count in country_counts.most_common():
        country_data.append({
            "code": code,
            "name": COUNTRY_NAMES.get(code, code),
            "count": count,
        })

    num_countries = len(country_counts)

    # NL analysis
    nl_home = [r for r in unique_rows if get_home_country(r) == "NL"]
    nl_crossborder = []
    for r in unique_rows:
        hc = get_home_country(r)
        if hc != "NL":
            svc_countries = r.get("ac_serviceCode_cou", "")
            # Split and check for NL
            codes = [c.strip() for c in svc_countries.replace("|", ",").split(",") if c.strip()]
            # Also try pipe-separated
            if not codes:
                codes = [c.strip() for c in svc_countries.split("|") if c.strip()]
            if "NL" in codes:
                nl_crossborder.append(r)

    nl_cb_origin = Counter()
    for r in nl_crossborder:
        hc = get_home_country(r)
        nl_cb_origin[hc] += 1

    nl_cb_origin_data = []
    for code, count in nl_cb_origin.most_common():
        nl_cb_origin_data.append({
            "code": code,
            "name": COUNTRY_NAMES.get(code, code),
            "count": count,
        })

    # NL home list
    nl_home_list = []
    for r in nl_home:
        commercial = r.get("ae_commercial_name", "").strip()
        entity = r.get("ae_lei_name", "").strip()
        # Clean up commercial name
        if "|" in commercial:
            commercial = commercial.split("|")[0].strip()
        if not commercial:
            commercial = entity
        nl_home_list.append({"name": commercial, "entity": entity})

    # Services
    svc_counts = Counter()
    for r in unique_rows:
        svcs = parse_services(r.get("ac_serviceCode", ""))
        for s in svcs:
            svc_counts[s] += 1

    svc_order = [
        "Custody & admin", "Transfer services", "Order execution",
        "Exchange crypto/fiat", "Exchange crypto/crypto",
        "Reception & transmission", "Portfolio mgmt", "Placing",
        "Advice", "Trading platform"
    ]
    services_data = []
    for s in svc_order:
        if s in svc_counts:
            services_data.append({"name": s, "count": svc_counts[s]})

    # Full directory
    directory = []
    for r in unique_rows:
        commercial = r.get("ae_commercial_name", "").strip()
        entity = r.get("ae_lei_name", "").strip()
        hc = get_home_country(r)
        if "|" in commercial:
            commercial = commercial.split("|")[0].strip()
        if not commercial:
            commercial = entity
        authority = AUTHORITY_SHORT.get(hc, hc)
        directory.append({
            "name": commercial,
            "entity": entity,
            "home": hc,
            "authority": authority,
        })

    # Sort directory by country then name
    directory.sort(key=lambda x: (x["home"], x["name"].lower()))

    # Top country
    top_country = country_data[0] if country_data else {"code": "?", "name": "?", "count": 0}

    return {
        "total": total,
        "num_countries": num_countries,
        "country_data": country_data,
        "nl_home_count": len(nl_home),
        "nl_cb_count": len(nl_crossborder),
        "nl_total": len(nl_home) + len(nl_crossborder),
        "nl_cb_origin": nl_cb_origin_data,
        "nl_home_list": nl_home_list,
        "services_data": services_data,
        "directory": directory,
        "top_country": top_country,
        "date": datetime.now().strftime("%d %B %Y"),
    }


def generate_html(data):
    """Generate the full dashboard HTML."""

    # Prepare JSON data for JS
    country_js = json.dumps([{"n": d["name"], "c": d["code"], "v": d["count"]} for d in data["country_data"]])
    nl_cb_js = json.dumps([{"n": d["name"], "v": d["count"]} for d in data["nl_cb_origin"]])
    nl_home_js = json.dumps([{"n": d["name"], "e": d["entity"]} for d in data["nl_home_list"]])
    svc_js = json.dumps([{"s": d["name"], "v": d["count"]} for d in data["services_data"]])
    dir_js = json.dumps([{"n": d["name"], "e": d["entity"], "h": d["home"], "a": d["authority"]} for d in data["directory"]])

    total = data["total"]
    num_countries = data["num_countries"]
    nl_home = data["nl_home_count"]
    nl_cb = data["nl_cb_count"]
    nl_total = data["nl_total"]
    top = data["top_country"]
    max_svc = data["services_data"][0]["count"] if data["services_data"] else 1
    top_svc = data["services_data"][0]["name"] if data["services_data"] else "?"
    bot_svc = data["services_data"][-1]["name"] if data["services_data"] else "?"
    bot_svc_count = data["services_data"][-1]["count"] if data["services_data"] else 0
    second_svc = data["services_data"][1]["name"] if len(data["services_data"]) > 1 else "?"
    second_svc_count = data["services_data"][1]["count"] if len(data["services_data"]) > 1 else 0
    date_str = data["date"]

    # Donut chart calculations
    circ = 515.2  # 2*PI*82
    top5 = data["country_data"][:5]
    top5_total = sum(d["count"] for d in top5)
    rest_count = total - top5_total
    donut_colors = ["#1A3C44", "#236E7D", "#528A97", "#6FA8B4", "#C47F3A", "#A3CDD6"]

    donut_circles = ""
    offset = 0
    for i, d in enumerate(top5):
        dash = round(d["count"] / total * circ, 1)
        donut_circles += f'            <circle class="donut-circle" cx="100" cy="100" r="82" stroke="{donut_colors[i]}" stroke-dasharray="{dash} {circ}" stroke-dashoffset="{-offset}"/>\n'
        offset += dash
    # Rest
    rest_dash = round(rest_count / total * circ, 1)
    donut_circles += f'            <circle class="donut-circle" cx="100" cy="100" r="82" stroke="{donut_colors[5]}" stroke-dasharray="{rest_dash} {circ}" stroke-dashoffset="{-offset}"/>\n'

    # Donut legend
    legend_items = ""
    for i, d in enumerate(top5):
        pct = round(d["count"] / total * 100)
        sub_text = f'{d["count"]} providers'
        if i == 3 and len(top5) > 4 and top5[3]["count"] == top5[4]["count"]:
            sub_text = f'{d["count"]} providers each'
            label = f'{top5[3]["name"]} & {top5[4]["name"]}'
        else:
            label = d["name"]

        # Skip 5th if merged with 4th
        if i == 4 and len(top5) > 4 and top5[3]["count"] == top5[4]["count"]:
            continue

        legend_items += f'''          <div class="pie-legend-item">
            <span class="pie-dot" style="background:{donut_colors[i]}"></span>
            <div style="flex:1"><div style="font-size:14px;font-weight:600;color:#1A3C44">{label}</div><div style="font-size:12px;color:#6B7280">{sub_text}</div></div>
            <div class="pie-pct" style="color:{donut_colors[i]}">{pct}%</div>
          </div>
'''

    rest_pct = round(rest_count / total * 100)
    rest_countries = num_countries - len(set(d["code"] for d in top5))
    legend_items += f'''          <div class="pie-legend-item">
            <span class="pie-dot" style="background:{donut_colors[5]}"></span>
            <div style="flex:1"><div style="font-size:14px;font-weight:600;color:#1A3C44">Other ({rest_countries} countries)</div><div style="font-size:12px;color:#6B7280">{rest_count} providers</div></div>
            <div class="pie-pct" style="color:{donut_colors[5]}">{rest_pct}%</div>
          </div>
'''

    nl_cb_origins_count = len(data["nl_cb_origin"])

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ESMA Register of Crypto-Asset Service Providers — Dashboard</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;600;700&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Source Sans 3', sans-serif; background: #fff; color: #1A3C44; }}
.hero {{ width: 100%; background: linear-gradient(135deg, #1A3C44 0%, #236E7D 50%, #2E9AAD 100%); padding: 48px 32px 40px; display: flex; justify-content: center; }}
.hero-inner {{ max-width: 920px; width: 100%; }}
.hero-tags {{ display: flex; gap: 8px; margin-bottom: 14px; }}
.hero-tag {{ font-size: 11px; font-weight: 600; color: #fff; background: rgba(255,255,255,0.15); padding: 3px 10px; border-radius: 4px; letter-spacing: 0.05em; text-transform: uppercase; }}
.hero h1 {{ font-size: 28px; font-weight: 700; color: #fff; margin: 0 0 8px 0; letter-spacing: -0.02em; line-height: 1.2; }}
.hero p {{ color: rgba(255,255,255,0.7); font-size: 15px; margin: 0; }}
.container {{ max-width: 920px; width: 100%; padding: 0 32px; margin: 0 auto; }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: -20px; position: relative; z-index: 1; }}
.kpi {{ background: #F4FAFB; border: 1px solid #D4EAEF; border-radius: 10px; padding: 16px 18px; }}
.kpi-label {{ font-size: 11px; color: #6B7280; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }}
.kpi-value {{ font-size: 24px; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }}
.kpi-sub {{ font-size: 12px; color: #6B7280; margin-top: 2px; }}
.tabs {{ display: flex; gap: 0; border-bottom: 1px solid #D4EAEF; margin-top: 32px; overflow-x: auto; }}
.tab-btn {{ padding: 10px 18px; border: none; cursor: pointer; font-size: 14px; font-family: inherit; font-weight: 600; white-space: nowrap; color: #6B7280; background: transparent; border-bottom: 2px solid transparent; margin-bottom: -1px; transition: all 0.15s; }}
.tab-btn.active {{ color: #236E7D; border-bottom-color: #236E7D; }}
.tab-btn:hover {{ color: #236E7D; }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}
.section {{ margin-top: 32px; }}
.section h2 {{ font-size: 17px; font-weight: 700; color: #1A3C44; margin: 0 0 14px 0; }}
.chart-box {{ background: #fff; border: 1px solid #D4EAEF; border-radius: 10px; padding: 20px; }}
.badge {{ display: inline-block; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px; letter-spacing: 0.02em; }}
table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.table-wrap {{ border: 1px solid #D4EAEF; border-radius: 10px; overflow: hidden; }}
thead tr {{ background: #F4FAFB; }}
th {{ text-align: left; padding: 12px 16px; font-weight: 600; color: #6B7280; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #D4EAEF; }}
td {{ padding: 10px 16px; }}
tbody tr {{ border-bottom: 1px solid #D4EAEF; }}
tbody tr:last-child {{ border-bottom: none; }}
.pie-section {{ background: #fff; border: 1px solid #D4EAEF; border-radius: 10px; padding: 24px; display: flex; align-items: center; gap: 40px; flex-wrap: wrap; }}
.pie-legend-item {{ display: flex; align-items: center; gap: 12px; padding: 10px 0; }}
.pie-legend-item:not(:last-child) {{ border-bottom: 1px solid #D4EAEF; }}
.pie-dot {{ width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }}
.pie-pct {{ font-size: 18px; font-weight: 700; font-variant-numeric: tabular-nums; }}
.bar-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
.bar-label {{ width: 120px; font-size: 13px; color: #1A3C44; text-align: right; flex-shrink: 0; }}
.bar-track {{ flex: 1; height: 24px; background: #F4FAFB; border-radius: 4px; overflow: hidden; }}
.bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.4s ease; }}
.bar-val {{ width: 36px; font-size: 13px; font-weight: 600; color: #1A3C44; text-align: right; }}
.vbar-container {{ display: flex; align-items: flex-end; gap: 4px; justify-content: center; height: 240px; padding: 0 4px; }}
.vbar-col {{ display: flex; flex-direction: column; align-items: center; gap: 4px; flex: 1; max-width: 52px; }}
.vbar-bar {{ width: 100%; border-radius: 4px 4px 0 0; transition: height 0.4s ease; min-height: 2px; }}
.vbar-label {{ font-size: 10px; color: #6B7280; text-align: center; line-height: 1.2; height: 28px; display: flex; align-items: center; }}
.vbar-val {{ font-size: 11px; font-weight: 600; color: #1A3C44; }}
.donut-wrap {{ width: 210px; height: 210px; flex-shrink: 0; position: relative; }}
.donut-svg {{ width: 100%; height: 100%; transform: rotate(-90deg); }}
.donut-circle {{ fill: none; stroke-width: 36; }}
.donut-center {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; }}
.donut-center-val {{ font-size: 28px; font-weight: 700; color: #1A3C44; }}
.donut-center-lbl {{ font-size: 11px; color: #6B7280; }}
.footer {{ margin-top: 40px; padding: 16px 0 32px; border-top: 1px solid #D4EAEF; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; }}
.footer span {{ font-size: 12px; }}
.grid-2 {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 16px; }}
.grid-3 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 16px; }}
.note {{ font-size: 13px; color: #6B7280; margin-top: 8px; }}
.search-box {{ margin-top: 16px; margin-bottom: 16px; }}
.search-box input {{ width: 100%; padding: 10px 14px; border: 1px solid #D4EAEF; border-radius: 8px; font-size: 14px; font-family: inherit; color: #1A3C44; outline: none; transition: border-color 0.2s; }}
.search-box input:focus {{ border-color: #236E7D; }}
.search-box input::placeholder {{ color: #A3CDD6; }}
@media (max-width: 700px) {{
  .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .grid-3 {{ grid-template-columns: 1fr; }}
  .pie-section {{ flex-direction: column; }}
  .hero h1 {{ font-size: 22px; }}
  .container {{ padding: 0 16px; }}
}}
</style>
</head>
<body>

<div class="hero">
  <div class="hero-inner">
    <div class="hero-tags">
      <span class="hero-tag">ESMA Register</span>
      <span class="hero-tag">MiCAR</span>
      <span class="hero-tag">EU-wide</span>
    </div>
    <h1>Register of Crypto-Asset Service Providers</h1>
    <p>Comprehensive overview of all authorised CASPs across the European Economic Area under MiCAR &middot; {total} providers across {num_countries} member states</p>
  </div>
</div>

<div class="container">
  <div class="kpi-grid">
    <div class="kpi"><div class="kpi-label">Total CASPs</div><div class="kpi-value" style="color:#1A3C44">{total}</div><div class="kpi-sub">unique authorised providers</div></div>
    <div class="kpi"><div class="kpi-label">Member States</div><div class="kpi-value" style="color:#236E7D">{num_countries}</div><div class="kpi-sub">home countries represented</div></div>
    <div class="kpi"><div class="kpi-label">Active in NL</div><div class="kpi-value" style="color:#528A97">{nl_total}</div><div class="kpi-sub">{nl_home} domestic + {nl_cb} cross-border</div></div>
    <div class="kpi"><div class="kpi-label">Top home country</div><div class="kpi-value" style="color:#C47F3A">{top["code"]}</div><div class="kpi-sub">{top["count"]} CASPs ({round(top["count"]/total*100)}%)</div></div>
  </div>

  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('overview')">Overview</button>
    <button class="tab-btn" onclick="switchTab('countries')">By Country</button>
    <button class="tab-btn" onclick="switchTab('nl')">Active in NL</button>
    <button class="tab-btn" onclick="switchTab('services')">Services</button>
    <button class="tab-btn" onclick="switchTab('directory')">Full Directory</button>
  </div>

  <!-- OVERVIEW -->
  <div id="tab-overview" class="tab-content active">
    <div class="section">
      <h2>Top home member states</h2>
      <div class="pie-section">
        <div class="donut-wrap">
          <svg class="donut-svg" viewBox="0 0 200 200">
{donut_circles}          </svg>
          <div class="donut-center"><div class="donut-center-val">{total}</div><div class="donut-center-lbl">total</div></div>
        </div>
        <div style="flex:1; min-width:260px">
{legend_items}        </div>
      </div>
    </div>
    <div class="section">
      <h2>CASPs by home member state (top 10)</h2>
      <div class="chart-box"><div class="vbar-container" id="country-chart"></div></div>
      <p class="note">{top["name"]} dominates with {top["count"]} authorised CASPs ({round(top["count"]/total*100)}%). Together the top 3 account for over half of all EU-authorised CASPs.</p>
    </div>
  </div>

  <!-- BY COUNTRY -->
  <div id="tab-countries" class="tab-content">
    <div class="section">
      <h2>All CASPs per home member state ({num_countries} countries)</h2>
      <div class="chart-box" id="full-country-chart"></div>
      <div class="grid-3">
        <div class="kpi"><div class="kpi-label">Largest hub</div><div class="kpi-value" style="color:#236E7D">{data["country_data"][0]["name"] if data["country_data"] else "?"}</div><div class="kpi-sub">{data["country_data"][0]["count"] if data["country_data"] else 0} CASPs</div></div>
        <div class="kpi"><div class="kpi-label">Second hub</div><div class="kpi-value" style="color:#528A97">{data["country_data"][1]["name"] if len(data["country_data"])>1 else "?"}</div><div class="kpi-sub">{data["country_data"][1]["count"] if len(data["country_data"])>1 else 0} CASPs</div></div>
        <div class="kpi"><div class="kpi-label">Third hub</div><div class="kpi-value" style="color:#C47F3A">{data["country_data"][2]["name"] if len(data["country_data"])>2 else "?"}</div><div class="kpi-sub">{data["country_data"][2]["count"] if len(data["country_data"])>2 else 0} CASPs</div></div>
      </div>
    </div>
  </div>

  <!-- ACTIVE IN NL -->
  <div id="tab-nl" class="tab-content">
    <div class="section">
      <h2>Cross-border CASPs passporting into the Netherlands ({nl_cb})</h2>
      <p style="font-size:14px;color:#6B7280;margin-bottom:16px">Providers authorised in other EU member states offering services in the Netherlands via Art. 65 MiCAR.</p>
      <div class="chart-box"><div class="vbar-container" id="nl-origin-chart"></div></div>
    </div>
    <div class="section">
      <h2>Dutch-authorised CASPs ({nl_home})</h2>
      <div class="table-wrap"><table><thead><tr><th>#</th><th>Name</th><th>Entity</th></tr></thead><tbody id="nl-home-tbody"></tbody></table></div>
    </div>
    <div class="grid-2">
      <div class="kpi"><div class="kpi-label">NL domestic</div><div class="kpi-value" style="color:#236E7D">{nl_home}</div><div class="kpi-sub">authorised by AFM</div></div>
      <div class="kpi"><div class="kpi-label">Cross-border into NL</div><div class="kpi-value" style="color:#528A97">{nl_cb}</div><div class="kpi-sub">from {nl_cb_origins_count} member states</div></div>
    </div>
  </div>

  <!-- SERVICES -->
  <div id="tab-services" class="tab-content">
    <div class="section">
      <h2>Crypto-asset services (Art. 3(1)(16) MiCAR)</h2>
      <p style="font-size:14px;color:#6B7280;margin-bottom:16px">Number of CASPs offering each service across the EU. Multiple services per provider possible.</p>
      <div class="chart-box" id="services-chart"></div>
      <div class="grid-3">
        <div class="kpi"><div class="kpi-label">Most offered</div><div class="kpi-value" style="color:#236E7D">{top_svc}</div><div class="kpi-sub">{max_svc} providers ({round(max_svc/total*100)}%)</div></div>
        <div class="kpi"><div class="kpi-label">Second most</div><div class="kpi-value" style="color:#528A97">{second_svc_count}</div><div class="kpi-sub">{second_svc}</div></div>
        <div class="kpi"><div class="kpi-label">Least offered</div><div class="kpi-value" style="color:#C47F3A">{bot_svc}</div><div class="kpi-sub">only {bot_svc_count} providers</div></div>
      </div>
    </div>
  </div>

  <!-- FULL DIRECTORY -->
  <div id="tab-directory" class="tab-content">
    <div class="section">
      <h2>Full CASP directory ({total} providers)</h2>
      <div class="search-box"><input type="text" id="dir-search" placeholder="Search by name, country or entity..." oninput="filterDirectory()"></div>
      <div class="table-wrap"><table><thead><tr><th>Trade name</th><th>Entity</th><th>Home</th><th>Authority</th></tr></thead><tbody id="dir-tbody"></tbody></table></div>
      <p class="note" id="dir-count">Showing {total} of {total} providers</p>
    </div>
  </div>

  <div class="footer">
    <span style="color:#6B7280">Source: ESMA Register of Crypto-Asset Service Providers (MiCAR)</span>
    <span style="color:#d1d5db">Auto-generated {date_str}</span>
  </div>
</div>

<script>
var countryData={country_js};
var nlCBOrigin={nl_cb_js};
var nlHome={nl_home_js};
var servicesData={svc_js};
var directory={dir_js};
var countryNames={json.dumps(COUNTRY_NAMES)};

function switchTab(name){{
  document.querySelectorAll('.tab-content').forEach(function(el){{el.classList.remove('active')}});
  document.querySelectorAll('.tab-btn').forEach(function(el){{el.classList.remove('active')}});
  document.getElementById('tab-'+name).classList.add('active');
  var map={{overview:'Overview',countries:'By Country',nl:'Active in NL',services:'Services',directory:'Full Directory'}};
  document.querySelectorAll('.tab-btn').forEach(function(b){{if(b.textContent===map[name])b.classList.add('active')}});
}}

// Overview bar chart (top 10)
var oc=document.getElementById('country-chart');
var maxC=countryData[0]?countryData[0].v:1;
countryData.slice(0,10).forEach(function(d){{
  var col=document.createElement('div');col.className='vbar-col';
  var pct=(d.v/maxC)*200;
  var color=d.c==='DE'?'#1A3C44':d.c==='NL'?'#236E7D':d.c==='FR'?'#528A97':'#6FA8B4';
  col.innerHTML='<div class="vbar-val">'+d.v+'</div><div class="vbar-bar" style="height:'+pct+'px;background:'+color+'"></div><div class="vbar-label">'+d.c+'</div>';
  oc.appendChild(col);
}});

// Full country bars
var fc=document.getElementById('full-country-chart');
countryData.forEach(function(d){{
  var row=document.createElement('div');row.className='bar-row';
  var pct=(d.v/maxC)*100;
  row.innerHTML='<div class="bar-label">'+d.n+'</div><div class="bar-track"><div class="bar-fill" style="width:'+pct+'%;background:#236E7D"></div></div><div class="bar-val">'+d.v+'</div>';
  fc.appendChild(row);
}});

// NL cross-border origin
var nc=document.getElementById('nl-origin-chart');
var maxNL=nlCBOrigin[0]?nlCBOrigin[0].v:1;
nlCBOrigin.forEach(function(d){{
  var col=document.createElement('div');col.className='vbar-col';
  var pct=(d.v/maxNL)*200;
  col.innerHTML='<div class="vbar-val">'+d.v+'</div><div class="vbar-bar" style="height:'+pct+'px;background:#528A97"></div><div class="vbar-label">'+d.n+'</div>';
  nc.appendChild(col);
}});

// NL home table
var tb1=document.getElementById('nl-home-tbody');
nlHome.forEach(function(c,i){{
  var tr=document.createElement('tr');
  tr.innerHTML='<td style="color:#6B7280;font-size:13px">'+(i+1)+'</td><td style="font-weight:600;color:#1A3C44">'+c.n+'</td><td style="color:#6B7280;font-size:13px">'+c.e+'</td>';
  tb1.appendChild(tr);
}});

// Services chart
var sc=document.getElementById('services-chart');
var maxS=servicesData[0]?servicesData[0].v:1;
servicesData.forEach(function(d){{
  var row=document.createElement('div');row.className='bar-row';
  var pct=(d.v/maxS)*100;
  row.innerHTML='<div class="bar-label">'+d.s+'</div><div class="bar-track"><div class="bar-fill" style="width:'+pct+'%;background:#236E7D"></div></div><div class="bar-val">'+d.v+'</div>';
  sc.appendChild(row);
}});

// Directory
var dt=document.getElementById('dir-tbody');
function renderDirectory(filter){{
  dt.innerHTML='';
  var f=filter?filter.toLowerCase():'';
  var count=0;
  directory.forEach(function(c){{
    if(f&&(c.n+c.e+c.h+(countryNames[c.h]||'')+c.a).toLowerCase().indexOf(f)===-1) return;
    count++;
    var tr=document.createElement('tr');
    tr.innerHTML='<td style="font-weight:600;color:#1A3C44">'+c.n+'</td><td style="color:#6B7280;font-size:13px">'+c.e+'</td><td><span class="badge" style="color:#236E7D;background:#236E7D14">'+c.h+'</span></td><td style="color:#6B7280;font-size:12px">'+c.a+'</td>';
    dt.appendChild(tr);
  }});
  document.getElementById('dir-count').textContent='Showing '+count+' of '+directory.length+' providers';
}}
renderDirectory('');
function filterDirectory(){{var v=document.getElementById('dir-search').value;renderDirectory(v);}}
</script>
</body>
</html>'''

    return html


def main():
    parser = argparse.ArgumentParser(description="Generate CASP dashboard from ESMA CSV")
    parser.add_argument("--csv", help="Path to local CSV file (skip download)")
    parser.add_argument("--output", default="index.html", help="Output HTML file path")
    args = parser.parse_args()

    if args.csv:
        print(f"Reading local CSV: {args.csv}")
        with open(args.csv, "r", encoding="utf-8-sig") as f:
            text = f.read()
    else:
        text = download_csv(ESMA_CSV_URL)

    rows = parse_csv(text)
    print(f"Parsed {len(rows)} rows")

    data = analyze_data(rows)
    print(f"Analysis: {data['total']} unique CASPs, {data['num_countries']} countries, {data['nl_total']} active in NL")

    html = generate_html(data)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard written to {args.output}")


if __name__ == "__main__":
    main()
