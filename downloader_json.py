import os
import time
import json
import requests
import xml.etree.ElementTree as ET

# ========================================================
# ⚙️ MANAGER CONTROL PANEL (STRICT PUBMED TO JSON)
# ========================================================
KEYWORD = "thermoset"  # Swap this out for any keyword anytime
COUNT = 3              # Keep it at 3 or 5 for your live presentation!
OUTPUT_DIR = "./downloaded_json_data"
# ========================================================

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def get_pubmed_json_data(keyword, limit):
    print(f"=========================================================")
    print(f"🤖 AGENT INITIALIZED: Official PubMed JSON Data Pipeline")
    print(f"🔍 Keyword Target: '{keyword}' | Count Target: {limit}")
    print(f"=========================================================\n")
    
    # Step 1: Search PubMed for matching Article IDs
    search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={keyword}&retmax={limit}&retmode=json"
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(search_url, headers=headers, timeout=15)
        id_list = response.json().get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            print("⚠️ No matching entries found on PubMed.")
            return
            
        print(f"✅ Found {len(id_list)} valid IDs. Fetching structured data streams...\n")
        
        # Step 2: Pull the full text summaries directly via the official XML gateway
        ids_joined = ",".join(id_list)
        fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={ids_joined}&retmode=xml"
        
        fetch_response = requests.get(fetch_url, headers=headers, timeout=20)
        
        if fetch_response.status_code != 200:
            print(f"❌ Failed to fetch data stream from NCBI system.")
            return
            
        root = ET.fromstring(fetch_response.content)
        
        downloaded = 0
        for article in root.findall('.//PubmedArticle'):
            if downloaded >= limit:
                break
                
            pmid = article.find('.//PMID').text
            title = article.find('.//ArticleTitle').text
            
            # Extract the Abstract text components
            abstract_elements = article.findall('.//AbstractText')
            abstract_text = " ".join([elem.text for elem in abstract_elements if elem.text])
            
            if not abstract_text:
                abstract_text = "Abstract text not explicitly detailed in data stream summary."
            
            print(f"--- Progress: {downloaded + 1}/{limit} ---")
            print(f"📥 Structuring JSON Object for ID: {pmid}...")
            
            # Create a clean, modern JSON data object
            paper_json_object = {
                "source": "PubMed",
                "pubmed_id": pmid,
                "title": title,
                "search_keyword": keyword,
                "abstract_summary": abstract_text
            }
            
            # Save it to your hard drive as a beautifully formatted .json file
            file_path = os.path.join(OUTPUT_DIR, f"PubMed_{pmid}.json")
            with open(file_path, "w", encoding="utf-8") as json_file:
                json.dump(paper_json_object, json_file, indent=4, ensure_ascii=False)
                
            print(f"✨ Successfully saved data profile: PubMed_{pmid}.json\n")
            downloaded += 1
            time.sleep(0.3)
            
        print(f"\n🎉 EXCLUSIVE TASK COMPLETE: Successfully saved {downloaded} raw JSON objects inside '{OUTPUT_DIR}'.")
        
    except Exception as e:
        print(f"❌ Core PubMed API Connection Failure: {e}")

if __name__ == "__main__":
    get_pubmed_json_data(KEYWORD, COUNT)
    