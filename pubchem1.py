import os
import time
import requests
import xml.etree.ElementTree as ET

def fetch_all_pubchem_literature(search_word, output_file="paper_urls.txt"):
    print(f"📡 Querying NCBI/PubChem API for '{search_word}'...")
    
    # 1. Search Entrez database for the keyword to get all matching IDs
    esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pmc",            # Searching PubMed Central (Full-text literature)
        "term": search_word,
        "retmode": "json",
        "retmax": 5000          # Allows us to pull up to 5,000 document references at once
    }
    
    try:
        response = requests.get(esearch_url, params=params, timeout=30)
        if response.status_code != 200:
            print(f"❌ API Error: Status code {response.status_code}")
            return
            
        data = response.json()
        id_list = data.get("esearchresult", {}).get("idlist", [])
        total_count = data.get("esearchresult", {}).get("count", "0")
        
        print(f"📊 API reports {total_count} total documents found. Retrieved {len(id_list)} IDs successfully.")
        
        if not id_list:
            print("⚠️ No article IDs returned from the search term.")
            return

        # 2. Convert IDs to direct PubMed Central Landing URLs
        unique_urls = []
        for pmcid in id_list:
            # Construct standard landing page URLs for the papers
            url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/"
            unique_urls.append(url)

        # Save to text file
        with open(output_file, "w") as f:
            for url in unique_urls:
                f.write(f"{url}\n")
                
        print(f"💾 Success! Saved {len(unique_urls)} paper landing URLs directly to '{output_file}'")
        print("⚡ No browsers were crashed in the making of this file.")

    except Exception as e:
        print(f"❌ Network/Parsing Error: {e}")

if __name__ == "__main__":
    fetch_all_pubchem_literature(search_word="thermoset")