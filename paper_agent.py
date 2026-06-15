import os
import time
import requests
import pandas as pd

from Bio import Entrez
from bs4 import BeautifulSoup
from tqdm import tqdm


# ==========================================================
# CONFIG
# ==========================================================

EMAIL = "your_email@example.com"

Entrez.email = EMAIL

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# ==========================================================
# PUBMED SEARCH
# ==========================================================

def search_pubmed(keyword, max_results=100):

    handle = Entrez.esearch(
        db="pubmed",
        term=keyword,
        retmax=max_results,
        sort="relevance"
    )

    record = Entrez.read(handle)
    handle.close()

    return record["IdList"]


# ==========================================================
# FETCH DETAILS
# ==========================================================

def fetch_articles(pmids):

    ids = ",".join(pmids)

    handle = Entrez.efetch(
        db="pubmed",
        id=ids,
        rettype="xml",
        retmode="xml"
    )

    records = Entrez.read(handle)
    handle.close()

    return records["PubmedArticle"]


# ==========================================================
# PMID -> PMC
# ==========================================================

def get_pmc_id(pmid):

    try:

        handle = Entrez.elink(
            dbfrom="pubmed",
            db="pmc",
            id=pmid
        )

        record = Entrez.read(handle)
        handle.close()

        if len(record[0]["LinkSetDb"]) > 0:

            return record[0]["LinkSetDb"][0]["Link"][0]["Id"]

    except:
        pass

    return None


# ==========================================================
# FIND ACTUAL PDF URL
# ==========================================================

def get_pdf_url(pmc_id):

    try:

        article_url = (
            f"https://pmc.ncbi.nlm.nih.gov/articles/PMC{pmc_id}/"
        )

        r = requests.get(
            article_url,
            headers=HEADERS,
            timeout=30
        )

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        for a in soup.find_all("a"):

            href = a.get("href", "")

            if ".pdf" in href.lower():

                if href.startswith("/"):

                    return (
                        "https://pmc.ncbi.nlm.nih.gov"
                        + href
                    )

                return href

    except Exception as e:

        print(
            f"PDF URL error: {e}"
        )

    return None


# ==========================================================
# DOWNLOAD PDF
# ==========================================================

def download_pdf(pdf_url, save_path):

    try:

        r = requests.get(
            pdf_url,
            headers=HEADERS,
            stream=True,
            timeout=60
        )

        if r.status_code != 200:

            return False

        content_type = r.headers.get(
            "Content-Type",
            ""
        )

        if "pdf" not in content_type.lower():

            print(
                f"Skipped (not PDF): {content_type}"
            )

            return False

        with open(save_path, "wb") as f:

            for chunk in r.iter_content(
                chunk_size=8192
            ):
                f.write(chunk)

        with open(save_path, "rb") as f:

            signature = f.read(5)

        if signature != b"%PDF-":

            print(
                "Invalid PDF signature"
            )

            os.remove(save_path)

            return False

        return True

    except Exception as e:

        print(
            f"Download error: {e}"
        )

        return False


# ==========================================================
# METADATA
# ==========================================================

def extract_metadata(article):

    try:
        pmid = str(
            article["MedlineCitation"]["PMID"]
        )
    except:
        pmid = ""

    try:
        title = str(
            article["MedlineCitation"]
            ["Article"]
            ["ArticleTitle"]
        )
    except:
        title = ""

    try:
        journal = str(
            article["MedlineCitation"]
            ["Article"]
            ["Journal"]
            ["Title"]
        )
    except:
        journal = ""

    try:
        year = str(
            article["MedlineCitation"]
            ["Article"]
            ["Journal"]
            ["JournalIssue"]
            ["PubDate"]
            ["Year"]
        )
    except:
        year = ""

    return {
        "PMID": pmid,
        "Title": title,
        "Journal": journal,
        "Year": year
    }


# ==========================================================
# MAIN AGENT
# ==========================================================

def download_papers(
    keyword,
    count
):

    folder = keyword.replace(
        " ",
        "_"
    )

    os.makedirs(
        folder,
        exist_ok=True
    )

    print(
        f"\nSearching PubMed for '{keyword}'"
    )

    pmids = search_pubmed(
        keyword,
        max_results=count * 20
    )

    print(
        f"Found {len(pmids)} records"
    )

    articles = fetch_articles(pmids)

    metadata = []

    downloaded = 0

    for article in tqdm(articles):

        if downloaded >= count:
            break

        info = extract_metadata(article)

        pmid = info["PMID"]

        pmc_id = get_pmc_id(pmid)

        if not pmc_id:
            continue

        pdf_url = get_pdf_url(pmc_id)

        if not pdf_url:
            continue

        filename = (
            f"PubMed_PMC_{pmc_id}.pdf"
        )

        save_path = os.path.join(
            folder,
            filename
        )

        success = download_pdf(
            pdf_url,
            save_path
        )

        if success:

            info["PMC_ID"] = pmc_id
            info["PDF"] = filename

            metadata.append(info)

            downloaded += 1

            print(
                f"Downloaded {downloaded}/{count}"
            )

        time.sleep(0.34)

    csv_file = os.path.join(
        folder,
        "metadata.csv"
    )

    pd.DataFrame(
        metadata
    ).to_csv(
        csv_file,
        index=False
    )

    print("\nDONE")
    print(
        f"Downloaded PDFs: {downloaded}"
    )
    print(
        f"Metadata file: {csv_file}"
    )


# ==========================================================
# ENTRY
# ==========================================================

if __name__ == "__main__":

    keyword = input(
        "Keyword: "
    ).strip()

    count = int(
        input(
            "Number of PDFs: "
        )
    )

    download_papers(
        keyword,
        count
    )