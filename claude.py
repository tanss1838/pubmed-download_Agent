"""
PubChem Literature Download Agent
===================================
Searches PubChem + PubMed for papers related to a keyword,
then downloads the given number of PDFs (open-access via PMC / Unpaywall).

Usage:
    python pubchem_agent.py --keyword "thermoset polymers" --count 5
    python pubchem_agent.py --keyword "aspirin" --count 3 --output ./papers
"""

import argparse
import os
import time
import json
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
NCBI_BASE   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PMC_OA_BASE  = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
UNPAYWALL    = "https://api.unpaywall.org/v2"
CROSSREF     = "https://api.crossref.org/works"

# Put your email here — NCBI requires it for polite API use
EMAIL = "your_email@example.com"

HEADERS = {"User-Agent": f"PubChemAgent/1.0 ({EMAIL})"}

# ─────────────────────────────────────────────
# STEP 1: Search PubChem for compound CIDs
# ─────────────────────────────────────────────
def search_pubchem_cids(keyword: str, max_cids: int = 5) -> list[int]:
    """Search PubChem by keyword and return a list of compound CIDs."""
    print(f"\n🔍 Searching PubChem for: '{keyword}'")
    url = f"{PUBCHEM_BASE}/compound/name/{quote(keyword)}/cids/JSON"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            cids = r.json().get("IdentifierList", {}).get("CID", [])
            print(f"   Found {len(cids)} compound CID(s). Using top {min(len(cids), max_cids)}.")
            return cids[:max_cids]
        else:
            print(f"   PubChem compound search returned {r.status_code}. Trying as keyword fallback.")
            return []
    except Exception as e:
        print(f"   PubChem error: {e}")
        return []


# ─────────────────────────────────────────────
# STEP 2: Get PubMed IDs linked to those CIDs
# ─────────────────────────────────────────────
def get_pmids_from_cids(cids: list[int]) -> list[str]:
    """Get PubMed IDs associated with PubChem CIDs via xrefs."""
    pmids = set()
    for cid in cids:
        url = f"{PUBCHEM_BASE}/compound/cid/{cid}/xrefs/PubMedID/JSON"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                ids = r.json().get("InformationList", {}).get("Information", [])
                for item in ids:
                    for pmid in item.get("PubMedID", []):
                        pmids.add(str(pmid))
            time.sleep(0.3)  # be polite to the API
        except Exception as e:
            print(f"   Error fetching PMIDs for CID {cid}: {e}")
    return list(pmids)


# ─────────────────────────────────────────────
# STEP 3: Search PubMed directly by keyword (fallback / supplement)
# ─────────────────────────────────────────────
def search_pubmed(keyword: str, count: int) -> list[str]:
    """Search PubMed via E-utilities ESearch and return PMIDs."""
    print(f"\n📚 Searching PubMed for: '{keyword}'")
    url = (
        f"{NCBI_BASE}/esearch.fcgi"
        f"?db=pubmed&term={quote(keyword)}&retmax={count * 3}"
        f"&usehistory=n&retmode=json&email={EMAIL}"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        print(f"   PubMed returned {len(ids)} article ID(s).")
        return ids
    except Exception as e:
        print(f"   PubMed search error: {e}")
        return []


# ─────────────────────────────────────────────
# STEP 4: Fetch paper metadata (title, DOI, PMC ID)
# ─────────────────────────────────────────────
def fetch_paper_metadata(pmids: list[str]) -> list[dict]:
    """Fetch article metadata from PubMed via EFetch."""
    if not pmids:
        return []
    ids_str = ",".join(pmids[:50])
    url = (
        f"{NCBI_BASE}/efetch.fcgi"
        f"?db=pubmed&id={ids_str}&retmode=xml&email={EMAIL}"
    )
    papers = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        for article in root.findall(".//PubmedArticle"):
            paper = {}
            # Title
            title_el = article.find(".//ArticleTitle")
            paper["title"] = title_el.text if title_el is not None else "Unknown Title"

            # PMID
            pmid_el = article.find(".//PMID")
            paper["pmid"] = pmid_el.text if pmid_el is not None else ""

            # DOI
            doi_el = article.find(".//ELocationID[@EIdType='doi']")
            paper["doi"] = doi_el.text if doi_el is not None else ""

            # PMC ID
            pmc_el = article.find(".//ArticleId[@IdType='pmc']")
            paper["pmcid"] = pmc_el.text if pmc_el is not None else ""

            # Authors
            authors = []
            for author in article.findall(".//Author"):
                ln = author.find("LastName")
                fn = author.find("ForeName")
                if ln is not None:
                    name = ln.text
                    if fn is not None:
                        name += f" {fn.text}"
                    authors.append(name)
            paper["authors"] = authors[:3]  # first 3 authors

            # Year
            year_el = article.find(".//PubDate/Year")
            paper["year"] = year_el.text if year_el is not None else ""

            papers.append(paper)
    except Exception as e:
        print(f"   Metadata fetch error: {e}")
    return papers


# ─────────────────────────────────────────────
# STEP 5: Try to download PDF from PMC Open Access
# ─────────────────────────────────────────────
def try_pmc_pdf(pmcid: str, output_dir: Path, filename: str) -> bool:
    """Try to download PDF from PubMed Central Open Access."""
    if not pmcid:
        return False
    url = f"{PMC_OA_BASE}?id={pmcid}&format=pdf"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        root = ET.fromstring(r.content)
        pdf_link = root.find(".//link[@format='pdf']")
        if pdf_link is not None:
            pdf_url = pdf_link.get("href", "")
            if pdf_url.startswith("ftp://"):
                pdf_url = pdf_url.replace("ftp://", "https://", 1)
            pdf_r = requests.get(pdf_url, headers=HEADERS, timeout=60, stream=True)
            if pdf_r.status_code == 200 and "pdf" in pdf_r.headers.get("Content-Type", ""):
                path = output_dir / f"{filename}.pdf"
                with open(path, "wb") as f:
                    for chunk in pdf_r.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"   ✅ Downloaded via PMC: {path.name}")
                return True
    except Exception as e:
        pass
    return False


# ─────────────────────────────────────────────
# STEP 6: Try Unpaywall for open-access PDF
# ─────────────────────────────────────────────
def try_unpaywall_pdf(doi: str, output_dir: Path, filename: str) -> bool:
    """Try to find and download open-access PDF via Unpaywall."""
    if not doi:
        return False
    url = f"{UNPAYWALL}/{quote(doi)}?email={EMAIL}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            oa_url = data.get("best_oa_location", {})
            if oa_url:
                pdf_url = oa_url.get("url_for_pdf") or oa_url.get("url")
                if pdf_url:
                    pdf_r = requests.get(pdf_url, headers=HEADERS, timeout=60, stream=True)
                    ct = pdf_r.headers.get("Content-Type", "")
                    if pdf_r.status_code == 200 and "pdf" in ct:
                        path = output_dir / f"{filename}.pdf"
                        with open(path, "wb") as f:
                            for chunk in pdf_r.iter_content(chunk_size=8192):
                                f.write(chunk)
                        print(f"   ✅ Downloaded via Unpaywall: {path.name}")
                        return True
    except Exception as e:
        pass
    return False


# ─────────────────────────────────────────────
# STEP 7: Save a metadata JSON as fallback
# ─────────────────────────────────────────────
def save_metadata_json(paper: dict, output_dir: Path, filename: str):
    """Save paper metadata as JSON when PDF is not available."""
    path = output_dir / f"{filename}_metadata.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(paper, f, indent=2, ensure_ascii=False)
    print(f"   📄 PDF not available (paywalled). Saved metadata: {path.name}")


# ─────────────────────────────────────────────
# MAIN AGENT
# ─────────────────────────────────────────────
def run_agent(keyword: str, count: int, output_dir: str):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"  PubChem Literature Download Agent")
    print(f"  Keyword : {keyword}")
    print(f"  Target  : {count} paper(s)")
    print(f"  Output  : {output_path.resolve()}")
    print("=" * 60)

    # --- Collect PMIDs ---
    all_pmids = set()

    # From PubChem compound xrefs
    cids = search_pubchem_cids(keyword)
    if cids:
        cid_pmids = get_pmids_from_cids(cids)
        print(f"   PubChem xrefs → {len(cid_pmids)} PubMed ID(s)")
        all_pmids.update(cid_pmids)

    # From PubMed direct search (always supplement)
    pubmed_pmids = search_pubmed(keyword, count)
    all_pmids.update(pubmed_pmids)

    all_pmids = list(all_pmids)
    print(f"\n📋 Total unique PubMed articles found: {len(all_pmids)}")

    if not all_pmids:
        print("❌ No articles found. Try a different keyword.")
        return

    # --- Fetch metadata ---
    print(f"\n🗂  Fetching metadata for up to {len(all_pmids)} articles...")
    papers = fetch_paper_metadata(all_pmids)
    print(f"   Metadata fetched for {len(papers)} article(s).")

    # --- Download PDFs ---
    downloaded = 0
    skipped = 0
    results_log = []

    print(f"\n⬇️  Attempting to download {count} PDF(s)...\n")

    for i, paper in enumerate(papers):
        if downloaded >= count:
            break

        title = paper.get("title", "unknown")[:60]
        pmid  = paper.get("pmid", "")
        doi   = paper.get("doi", "")
        pmcid = paper.get("pmcid", "")

        print(f"[{i+1}] {title}...")
        print(f"     PMID={pmid}  DOI={doi}  PMCID={pmcid}")

        # Sanitize filename
        safe_name = f"paper_{pmid}" if pmid else f"paper_{i+1}"

        success = False

        # Try PMC first (most reliable for open access)
        if pmcid:
            success = try_pmc_pdf(pmcid, output_path, safe_name)

        # Try Unpaywall if PMC failed
        if not success and doi:
            success = try_unpaywall_pdf(doi, output_path, safe_name)

        if success:
            downloaded += 1
            paper["status"] = "downloaded"
        else:
            save_metadata_json(paper, output_path, safe_name)
            skipped += 1
            paper["status"] = "metadata_only"

        results_log.append(paper)
        time.sleep(0.5)  # polite delay

    # --- Summary ---
    print("\n" + "=" * 60)
    print(f"  ✅ PDFs downloaded   : {downloaded}")
    print(f"  📄 Metadata saved    : {skipped}")
    print(f"  📁 Output folder     : {output_path.resolve()}")
    print("=" * 60)

    # Save full results log
    log_path = output_path / "results_log.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(results_log, f, indent=2, ensure_ascii=False)
    print(f"\n📊 Full results log saved: {log_path.name}")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PubChem Literature Download Agent — search a keyword and download N PDFs."
    )
    parser.add_argument(
        "--keyword", "-k", required=True,
        help='Search keyword, e.g. "thermoset" or "aspirin synthesis"'
    )
    parser.add_argument(
        "--count", "-n", type=int, default=5,
        help="Number of PDFs to download (default: 5)"
    )
    parser.add_argument(
        "--output", "-o", default="./downloaded_papers",
        help="Output directory (default: ./downloaded_papers)"
    )
    parser.add_argument(
        "--email", "-e", default=EMAIL,
        help="Your email (required by NCBI for polite API use)"
    )

    args = parser.parse_args()
    EMAIL = args.email  # override global

    run_agent(
        keyword=args.keyword,
        count=args.count,
        output_dir=args.output
    )