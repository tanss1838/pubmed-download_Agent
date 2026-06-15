"""
PubMed & PubChem Data Fetcher
-------------------------------
Queries PubMed (papers) and PubChem (compounds) using official free APIs.
No authentication required. No scraping. No Sci-Hub.

Usage:
    python pubmed_pubchem_fetcher.py --keyword "cancer immunotherapy" --count 10 --source pubmed
    python pubmed_pubchem_fetcher.py --keyword "aspirin" --count 5 --source pubchem
    python pubmed_pubchem_fetcher.py --keyword "diabetes" --count 8 --source both
"""

import argparse
import json
import time
import csv
import os
import sys
from datetime import datetime

try:
    import requests
except ImportError:
    print("Missing dependency. Run: pip install requests")
    sys.exit(1)


# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────

PUBMED_BASE   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PUBCHEM_BASE  = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# NCBI recommends max 3 requests/sec without an API key.
# Get a free key at: https://www.ncbi.nlm.nih.gov/account/
# Set it here or as env var NCBI_API_KEY for 10 req/sec.
NCBI_API_KEY  = os.environ.get("NCBI_API_KEY", "")

DELAY         = 0.34  # seconds between requests (safe without API key)


# ─────────────────────────────────────────────
#  PUBMED
# ─────────────────────────────────────────────

def pubmed_search(keyword: str, count: int) -> list[str]:
    """Search PubMed and return a list of PMIDs."""
    print(f"\n[PubMed] Searching for: '{keyword}' (limit: {count})")
    params = {
        "db":       "pubmed",
        "term":     keyword,
        "retmax":   count,
        "retmode":  "json",
        "sort":     "relevance",
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    r = requests.get(f"{PUBMED_BASE}/esearch.fcgi", params=params, timeout=15)
    r.raise_for_status()
    pmids = r.json()["esearchresult"]["idlist"]
    print(f"[PubMed] Found {len(pmids)} PMIDs.")
    return pmids


def pubmed_fetch_details(pmids: list[str]) -> list[dict]:
    """Fetch title, abstract, authors, journal, year, DOI for each PMID."""
    if not pmids:
        return []

    print(f"[PubMed] Fetching details for {len(pmids)} records...")
    params = {
        "db":      "pubmed",
        "id":      ",".join(pmids),
        "retmode": "json",
        "rettype": "abstract",
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    time.sleep(DELAY)
    r = requests.get(f"{PUBMED_BASE}/efetch.fcgi", params=params, timeout=30)
    r.raise_for_status()

    # Use ESummary for clean JSON metadata
    time.sleep(DELAY)
    params2 = {
        "db":      "pubmed",
        "id":      ",".join(pmids),
        "retmode": "json",
    }
    if NCBI_API_KEY:
        params2["api_key"] = NCBI_API_KEY

    r2 = requests.get(f"{PUBMED_BASE}/esummary.fcgi", params=params2, timeout=30)
    r2.raise_for_status()
    summaries = r2.json().get("result", {})

    records = []
    for pmid in pmids:
        s = summaries.get(pmid, {})
        if not s:
            continue

        # Extract DOI from articleids list
        doi = ""
        for id_obj in s.get("articleids", []):
            if id_obj.get("idtype") == "doi":
                doi = id_obj.get("value", "")
                break

        authors = ", ".join(
            a.get("name", "") for a in s.get("authors", [])[:3]
        )
        if len(s.get("authors", [])) > 3:
            authors += " et al."

        records.append({
            "PMID":        pmid,
            "Title":       s.get("title", "N/A"),
            "Authors":     authors,
            "Journal":     s.get("source", "N/A"),
            "Year":        s.get("pubdate", "N/A")[:4],
            "DOI":         doi,
            "DOI_Link":    f"https://doi.org/{doi}" if doi else "N/A",
            "PubMed_Link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })

    return records


def run_pubmed(keyword: str, count: int) -> list[dict]:
    pmids   = pubmed_search(keyword, count)
    records = pubmed_fetch_details(pmids)
    return records


# ─────────────────────────────────────────────
#  PUBCHEM
# ─────────────────────────────────────────────

def pubchem_search(keyword: str, count: int) -> list[str]:
    """Search PubChem compounds by keyword, return CID list."""
    print(f"\n[PubChem] Searching for: '{keyword}' (limit: {count})")
    url = f"{PUBCHEM_BASE}/compound/name/{requests.utils.quote(keyword)}/cids/JSON"
    time.sleep(DELAY)
    r = requests.get(url, timeout=15)

    if r.status_code == 404:
        print(f"[PubChem] No compounds found for '{keyword}'.")
        return []

    r.raise_for_status()
    cids = r.json().get("IdentifierList", {}).get("CID", [])
    cids = [str(c) for c in cids[:count]]
    print(f"[PubChem] Found {len(cids)} CIDs.")
    return cids


def pubchem_fetch_details(cids: list[str]) -> list[dict]:
    """Fetch compound properties for each CID."""
    if not cids:
        return []

    print(f"[PubChem] Fetching details for {len(cids)} compounds...")
    properties = "IUPACName,MolecularFormula,MolecularWeight,CanonicalSMILES,InChIKey"
    url = (
        f"{PUBCHEM_BASE}/compound/cid/"
        f"{','.join(cids)}/property/{properties}/JSON"
    )
    time.sleep(DELAY)
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    props_list = r.json().get("PropertyTable", {}).get("Properties", [])
    records = []
    for p in props_list:
        cid = str(p.get("CID", ""))
        records.append({
            "CID":               cid,
            "IUPAC_Name":        p.get("IUPACName", "N/A"),
            "Molecular_Formula": p.get("MolecularFormula", "N/A"),
            "Molecular_Weight":  p.get("MolecularWeight", "N/A"),
            "SMILES":            p.get("CanonicalSMILES", "N/A"),
            "InChIKey":          p.get("InChIKey", "N/A"),
            "PubChem_Link":      f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
        })
    return records


def run_pubchem(keyword: str, count: int) -> list[dict]:
    cids    = pubchem_search(keyword, count)
    records = pubchem_fetch_details(cids)
    return records


# ─────────────────────────────────────────────
#  OUTPUT
# ─────────────────────────────────────────────

def save_results(records: list[dict], label: str, keyword: str):
    if not records:
        print(f"[{label}] No records to save.")
        return

    safe_kw   = keyword.replace(" ", "_")[:30]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"{label.lower()}_{safe_kw}_{timestamp}.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

    print(f"[{label}] Saved {len(records)} records → {filename}")


def print_preview(records: list[dict], label: str, n: int = 3):
    print(f"\n── {label} Preview (first {min(n, len(records))}) ──")
    for rec in records[:n]:
        for k, v in rec.items():
            print(f"  {k:<22}: {v}")
        print()


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fetch papers from PubMed and/or compounds from PubChem."
    )
    parser.add_argument("--keyword", required=True,  help="Search keyword")
    parser.add_argument("--count",   type=int, default=10, help="Number of results (default: 10)")
    parser.add_argument(
        "--source",
        choices=["pubmed", "pubchem", "both"],
        default="both",
        help="Which database to query (default: both)",
    )
    args = parser.parse_args()

    print("=" * 55)
    print(f"  Keyword : {args.keyword}")
    print(f"  Count   : {args.count}")
    print(f"  Source  : {args.source}")
    print("=" * 55)

    if args.source in ("pubmed", "both"):
        pm_records = run_pubmed(args.keyword, args.count)
        print_preview(pm_records, "PubMed")
        save_results(pm_records, "PubMed", args.keyword)

    if args.source in ("pubchem", "both"):
        pc_records = run_pubchem(args.keyword, args.count)
        print_preview(pc_records, "PubChem")
        save_results(pc_records, "PubChem", args.keyword)

    print("\nDone.")


if __name__ == "__main__":
    main()