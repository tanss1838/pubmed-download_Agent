import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

SEARCH_TERM = "thermoset"
NUM_PDFS = 5

DOWNLOAD_DIR = f"{SEARCH_TERM}_papers"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Search PMC
search_url = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    f"?db=pmc&term={SEARCH_TERM}&retmax=50&retmode=json"
)

pmc_ids = requests.get(search_url).json()["esearchresult"]["idlist"]

downloaded = 0

for pmc_id in pmc_ids:

    if downloaded >= NUM_PDFS:
        break

    article_url = f"https://pmc.ncbi.nlm.nih.gov/articles/PMC{pmc_id}/"

    try:
        print(f"\nChecking PMC{pmc_id}")

        html = requests.get(article_url, timeout=20).text
        soup = BeautifulSoup(html, "html.parser")

        pdf_url = None

        # Look for any href containing pdf
        for a in soup.find_all("a", href=True):
            href = a["href"]

            if ".pdf" in href.lower() or "/pdf/" in href.lower():
                pdf_url = urljoin(article_url, href)
                break

        if not pdf_url:
            print("PDF link not found")
            continue

        print("PDF:", pdf_url)

        r = requests.get(pdf_url, timeout=60)

        if "application/pdf" not in r.headers.get("Content-Type", ""):
            print("Not a PDF")
            continue

        filename = os.path.join(
            DOWNLOAD_DIR,
            f"PMC{pmc_id}.pdf"
        )

        with open(filename, "wb") as f:
            f.write(r.content)

        downloaded += 1
        print(f"Downloaded {downloaded}/{NUM_PDFS}")

    except Exception as e:
        print("Error:", e)

print(f"\nFinished. Downloaded {downloaded} PDFs.")