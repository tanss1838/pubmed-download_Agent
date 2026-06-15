import requests
import time
import sys
import json

def search_pubchem_compounds(chemical, max_cids=20, delay=0.5):
    """
    Search for PubChem Compound IDs (CIDs) related to a chemical term.
    Returns a list of CIDs.
    """
    print(f"  Searching for CIDs related to '{chemical}'...")
    
    # Try different search strategies
    search_methods = [
        f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{chemical}/cids/JSON",
        f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{chemical}/cids/JSON?list_return=flat"
    ]
    
    for url in search_methods:
        time.sleep(delay)
        try:
            print(f"    Trying: {url}")
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                cids = data.get('IdentifierList', {}).get('CID', [])
                if cids:
                    print(f"    Found {len(cids)} CIDs. Taking first {max_cids}.")
                    return cids[:max_cids]
                else:
                    print(f"    No CIDs found in response")
            elif response.status_code == 404:
                print(f"    Compound not found (404)")
            else:
                print(f"    Search failed with status {response.status_code}")
        except Exception as e:
            print(f"    Error searching: {e}")
    
    # If no CIDs found, try substance search as fallback
    print(f"  Trying substance search as fallback...")
    try:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/substance/name/{chemical}/cids/JSON"
        time.sleep(delay)
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            cids = data.get('IdentifierList', {}).get('CID', [])
            if cids:
                print(f"    Found {len(cids)} CIDs via substance search.")
                return cids[:max_cids]
    except Exception as e:
        print(f"    Substance search failed: {e}")
    
    return []

def get_literature_for_cid(cid, delay=0.5):
    """
    Retrieve literature citations (PubMed IDs) for a given PubChem CID.
    """
    print(f"  Fetching literature for CID {cid}...")
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON"
    time.sleep(delay)
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            pmids = []
            
            # Print structure for debugging
            print(f"    Response keys: {list(data.keys()) if data else 'None'}")
            
            if 'Record' in data and 'Section' in data['Record']:
                for section in data['Record']['Section']:
                    if section.get('TOCHeading') == 'Literature':
                        print(f"    Found Literature section")
                        for subsection in section.get('Section', []):
                            if subsection.get('TOCHeading') == 'PubMed Central':
                                print(f"    Found PubMed Central subsection")
                                for info in subsection.get('Information', []):
                                    val = info.get('Value', '')
                                    if 'PMID:' in val:
                                        pmid = val.split('PMID:')[1].strip().split()[0]
                                        pmids.append(pmid)
                                        print(f"    Found PMID: {pmid}")
                        break
            else:
                print(f"    No Record or Section found in response")
            
            if not pmids:
                print(f"    No literature found for CID {cid}")
            return pmids
        else:
            print(f"    Literature fetch failed with status {response.status_code}")
            return []
    except Exception as e:
        print(f"    Error fetching literature: {e}")
        return []

def find_articles_from_pubchem(search_term, target_count=10):
    """
    Main function for the PubChem agent.
    """
    print(f"\n--- PubChem Agent: Searching for '{search_term}' ---")
    
    # Try multiple search strategies
    cids = search_pubchem_compounds(search_term)
    
    if not cids:
        print("  No compounds found. Try using a specific compound name (e.g., 'aspirin', 'glucose') rather than a material class.")
        return []
    
    all_pmids = []
    for cid in cids:
        if len(all_pmids) >= target_count:
            break
        pmids = get_literature_for_cid(cid)
        for pmid in pmids:
            if pmid not in all_pmids:
                all_pmids.append(pmid)
                print(f"    Added new PubMed ID: {pmid}")
        print(f"    Total unique PMIDs so far: {len(all_pmids)}")
    
    return all_pmids[:target_count]

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python pubchem_lit_finder.py '<search_term>' <target_count>")
        sys.exit(1)
    
    term = sys.argv[1]
    try:
        count = int(sys.argv[2])
    except ValueError:
        print("Target count must be an integer.")
        sys.exit(1)
    
    found_pmids = find_articles_from_pubchem(term, count)
    print(f"\nFinal list of Article IDs: {found_pmids}")
    print(f"Total articles found: {len(found_pmids)}")
    
    # Exit with error if no articles found
    if not found_pmids:
        sys.exit(1)