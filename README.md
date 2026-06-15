# PubChem Literature PDF Downloader Agent

## Overview

This project is an AI-powered literature downloader that automates the process of finding and downloading research papers from PubChem.

Given a search keyword and a target number of papers, the agent:

1. Searches PubChem for the specified keyword.
2. Opens the Literature section.
3. Extracts literature links.
4. Visits each publication page.
5. Locates available PDF download buttons.
6. Downloads PDFs automatically.
7. Continues until the requested number of PDFs have been downloaded.

---

## Example

Input:

```python
keyword = "thermoset"
pdf_count = 20
```

Output:

```text
downloads/
├── paper_1.pdf
├── paper_2.pdf
├── paper_3.pdf
...
├── paper_20.pdf
```

---

## Features

* Automated PubChem search
* Literature extraction
* Automatic navigation to publication websites
* PDF detection and downloading
* Folder creation and management
* Duplicate avoidance
* Configurable download count
* Support for multiple publishers

---

## Workflow

```text
PubChem
   ↓
Search Keyword
   ↓
Literature Results
   ↓
Open Publication
   ↓
Find PDF Button
   ↓
Download PDF
   ↓
Repeat Until Target Count Reached
```

---

## Technologies Used

* Python
* Selenium
* Chrome WebDriver
* Requests
* BeautifulSoup4

---

## Installation

Clone the repository:

```bash
git clone https://github.com/yourusername/pubchem-literature-downloader.git

cd pubchem-literature-downloader
```

Install dependencies:

```bash
pip install selenium
pip install webdriver-manager
pip install requests
pip install beautifulsoup4
```

---

## Usage

Run the script:

```bash
python main.py
```

Provide:

```text
Keyword: thermoset
Number of PDFs: 20
```

The downloaded PDFs will be stored in a dedicated folder.

---

## Current Status

Work in Progress (WIP)

Completed:

* PubChem search automation
* Literature result extraction
* Selenium browser automation

In Development:

* Publisher-specific PDF detection
* Automatic PDF downloads
* Retry mechanisms
* Metadata export

---

## Challenges

Different publishers use different download mechanisms:

* PubMed Central (PMC)
* Springer
* MDPI
* Elsevier
* Wiley
* ACS Publications
* Nature

The agent uses publisher-specific strategies to locate PDF download links.

---

## Future Improvements

* Multi-threaded downloading
* AI-based paper relevance ranking
* Citation export
* DOI extraction
* Metadata storage in CSV/Excel
* GUI application
* Headless mode support

---

## Disclaimer

This tool downloads only PDFs that are publicly accessible and available through publisher websites. Users are responsible for complying with publisher terms of service and copyright policies.
