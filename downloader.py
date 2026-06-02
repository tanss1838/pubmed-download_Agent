import os
import time
import random
import requests
import xml.etree.ElementTree as ET

# ========================================================
# ⚙️ MANAGER CONTROL PANEL
# ========================================================
KEYWORD = "thermoset"  # Swap this out for any keyword anytime
COUNT = 20             # The number of papers you want to target
OUTPUT_DIR = "./downloaded_papers"
# ========================================================

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def get_pubmed_papers(keyword, limit):
    print(f"🔍 Searching PubMed Central (PMC) for free articles matching: '{keyword}'...")
    
    # Step 1: Query the NCBI search system for article IDs matching the keyword
    search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&term={keyword}&retmax={limit}&retmode=json"
    
    try:
        headers = {"User-Agent": "AcademicAgent/3.0 (mailto:yourworkemail@example.com)"}
        response = requests.get(search_url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"❌ PubMed search failed. Status code: {response.status_code}")
            return
            
        id_list = response.json().get("esearchresult", {}).get("idlist", [])
        if not id_list:
            print("⚠️ No matching free papers found on PubMed for this specific keyword.")
            return
            
        print(f"✅ Found {len(id_list)} open-access articles. Starting secure downloads...\n")
        
        # Step 2: Loop through the IDs and fetch the PDFs directly from the legitimate PMC servers
        downloaded = 0
        for i, pmcid in enumerate(id_list):
            print(f"--- Progress: {i+1}/{len(id_list)} ---")
            print(f"📥 Downloading Open-Access PMC ID: PMC{pmcid}...")
            
            # Direct official URL to get free PDFs from PubMed Central
            pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/"
            
            try:
                pdf_response = requests.get(pdf_url, headers=headers, timeout=20)
                
                # Check if we got an actual PDF file back (usually larger than 10KB)
                if pdf_response.status_code == 200 and len(pdf_response.content) > 10000:
                    file_path = os.path.join(OUTPUT_DIR, f"PubMed_PMC_{pmcid}.pdf")
                    with open(file_path, "wb") as f:
                        f.write(pdf_response.content)
                    print(f"✨ Successfully saved: PubMed_PMC_{pmcid}.pdf")
                    downloaded += 1
                else:
                    print(f"⚠️ Direct PDF download link restricted or pending for ID: PMC{pmcid}")
            except Exception as e:
                print(f"❌ Error downloading file: {e}")
                
            # Polite scraping delay to be friendly to government servers
            time.sleep(random.uniform(1.0, 2.5))
            
        print(f"\n🎉 Task complete! Successfully saved {downloaded}/{len(id_list)} papers to '{OUTPUT_DIR}'.")
        
    except Exception as e:
        print(f"❌ General network error connecting to PubMed: {e}")

if __name__ == "__main__":
    get_pubmed_papers(KEYWORD, COUNT)