import os
import time
import csv
import json
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class PubChemBrowserAgent:
    def __init__(self, download_dir="pubchem_downloads", log_callback=None):
        self.download_dir = os.path.abspath(download_dir)
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
        self.log_callback = log_callback
        self.driver = None

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        try:
            print(formatted)
        except UnicodeEncodeError:
            # Fallback for Windows consoles that don't support UTF-8 prints
            print(formatted.encode("ascii", "ignore").decode("ascii"))
        if self.log_callback:
            self.log_callback(formatted)

    def init_driver(self):
        self.log("🔧 Initializing Chrome Driver with background download preferences...")
        chrome_options = Options()
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,  # Force direct background download of PDF streams
            "profile.default_content_setting_values.automatic_downloads": 1  # Bypass Chrome multi-download block prompt
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.wait = WebDriverWait(self.driver, 20)
        self.log("✅ Chrome Driver successfully initialized.")

    def fetch_paper_metadata(self, pmcid):
        """Fetch clean paper details from Europe PMC API in a single HTTP request."""
        try:
            url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={pmcid}&format=json"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                results = data.get("resultList", {}).get("result", [])
                if results:
                    res = results[0]
                    return {
                        "pmcid": pmcid,
                        "title": res.get("title", "N/A"),
                        "authors": res.get("authorString", "N/A"),
                        "journal": res.get("journalTitle", "N/A"),
                        "year": res.get("pubYear", "N/A"),
                        "doi": res.get("doi", "N/A"),
                        "url": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
                    }
        except Exception as e:
            self.log(f"⚠️ Metadata fetch warning for {pmcid}: {e}")
        
        return {
            "pmcid": pmcid,
            "title": f"PMC Article {pmcid}",
            "authors": "N/A",
            "journal": "N/A",
            "year": "N/A",
            "doi": "N/A",
            "url": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
        }

    def download_papers(self, search_word, count=3):
        metadata_records = []
        try:
            self.init_driver()
            
            # Step 1: Open PubChem
            self.log("🌐 Opening PubChem homepage (https://pubchem.ncbi.nlm.nih.gov)...")
            self.driver.get("https://pubchem.ncbi.nlm.nih.gov/")
            time.sleep(3)

            # Step 2: Search for the given keyword
            self.log(f"🔍 Searching for keyword: '{search_word}'...")
            search_input = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='text']")))
            search_input.clear()
            search_input.send_keys(search_word)
            search_input.send_keys(Keys.RETURN)
            
            self.log("⏳ Waiting for search results to render...")
            time.sleep(6)

            # Step 3: Switch to the 'Literature' section tab
            self.log("📑 Navigating to the 'Literature' section tab...")
            lit_xpath = "//*[contains(text(), 'Literature')]/ancestor::div[@data-collection='literature' or contains(@class,'tab')] | //*[text()='Literature']"
            lit_tab_button = self.wait.until(EC.presence_of_element_located((By.XPATH, lit_xpath)))
            
            # Scroll and click
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", lit_tab_button)
            time.sleep(2)
            self.driver.execute_script("arguments[0].click();", lit_tab_button)
            self.log("✅ Successfully switched to Literature tab. Waiting for records to populate...")
            time.sleep(8)

            # Step 4: Extract paper URLs
            self.log("🔗 Scraping article landing page links from the list...")
            
            # Find all links on the page
            elements = self.driver.find_elements(By.TAG_NAME, "a")
            
            paper_urls = []
            for el in elements:
                try:
                    href = el.get_attribute("href")
                    if href and href not in paper_urls:
                        # Filter for PMC or PubMed landing pages
                        if "pmc/articles/PMC" in href or "pubmed.ncbi.nlm.nih.gov/" in href:
                            paper_urls.append(href)
                            if len(paper_urls) >= count:
                                break
                except:
                    continue
                            
            self.log(f"🎯 Gathered {len(paper_urls)} target paper URLs. Starting downloads...")

            # Step 5: Visit landing pages and download PDFs
            for idx, url in enumerate(paper_urls, 1):
                # Canonicalize subdomain to keep cookies aligned with PDF downloads
                if "www.ncbi.nlm.nih.gov/pmc/" in url:
                    url = url.replace("www.ncbi.nlm.nih.gov/pmc/", "pmc.ncbi.nlm.nih.gov/")
                    
                self.log(f"⏳ [{idx}/{len(paper_urls)}] Loading landing page: {url}")
                self.driver.get(url)
                time.sleep(5)
                
                pmcid = None
                # Check if it is a PMC page
                if "pmc/articles/PMC" in url or "PMC" in url:
                    # Extract PMC ID from URL
                    parts = url.split("PMC")
                    if len(parts) > 1:
                        pmcid = "PMC" + parts[1].replace("/", "").split("?")[0].split("#")[0]
                
                # If it's PubMed, try to find a link to PMC on the page
                elif "pubmed.ncbi.nlm.nih.gov/" in url:
                    self.log("ℹ️ PubMed record detected. Scanning page for linked PMC open-access article...")
                    pmc_links = [a.get_attribute("href") for a in self.driver.find_elements(By.TAG_NAME, "a") if a.get_attribute("href") and "pmc/articles/" in a.get_attribute("href")]
                    if pmc_links:
                        pmc_url = pmc_links[0]
                        self.log(f"🔗 PMC link found: {pmc_url}. Navigating...")
                        self.driver.get(pmc_url)
                        time.sleep(5)
                        parts = pmc_url.split("PMC")
                        if len(parts) > 1:
                            pmcid = "PMC" + parts[1].replace("/", "").split("?")[0].split("#")[0]
                    else:
                        self.log("❌ No PMC link found on this PubMed page. Skipping.")
                        continue
                
                if not pmcid:
                    self.log("❌ Could not extract PMC ID for this article. Skipping.")
                    continue
                
                self.log(f"📂 Resolved PMC ID: {pmcid}. Fetching metadata...")
                meta = self.fetch_paper_metadata(pmcid)
                
                # Scan page for PDF download links
                self.log("🔍 Scanning page for PDF download button...")
                a_elements = [a for a in self.driver.find_elements(By.TAG_NAME, 'a') if 'pdf' in (a.get_attribute('href') or '').lower() or 'pdf' in a.text.lower()]
                
                pdf_url = None
                for el in a_elements:
                    href = el.get_attribute("href")
                    if href and "pdf" in href.lower() and pmcid in href:
                        pdf_url = href
                        break
                
                if not pdf_url and a_elements:
                    # Fallback to any PDF link on the page
                    for el in a_elements:
                        href = el.get_attribute("href")
                        if href and "pdf" in href.lower():
                            pdf_url = href
                            break
                            
                if pdf_url:
                    self.log(f"📥 Found PDF download link: {pdf_url}")
                    
                    # Resolve filename and clean up existing copy to ensure fresh detection
                    expected_filename = pdf_url.split("/")[-1].split("?")[0]
                    target_file_path = os.path.join(self.download_dir, expected_filename)
                    if expected_filename.endswith(".pdf") and os.path.exists(target_file_path):
                        try:
                            os.remove(target_file_path)
                            self.log(f"🗑️ Cleaned up existing copy of {expected_filename} for fresh download.")
                        except Exception as e:
                            self.log(f"⚠️ Warning: Could not delete existing file: {e}")
                            
                    self.log("🚀 Navigating directly to PDF URL to initiate background download...")
                    
                    # Store folder contents to detect new file
                    initial_files = set(os.listdir(self.download_dir))
                    
                    # Direct navigate triggers download stream
                    self.driver.get(pdf_url)
                    
                    # Wait for download completion (polling download folder)
                    downloaded_filename = None
                    self.log("⏳ Waiting up to 20 seconds for the download stream to complete...")
                    
                    for _ in range(10):
                        time.sleep(2)
                        current_files = set(os.listdir(self.download_dir))
                        new_files = current_files - initial_files
                        # Filter out temp/crdownload files Chrome uses
                        finished_files = [f for f in new_files if not f.endswith('.crdownload') and not f.endswith('.tmp')]
                        if finished_files:
                            downloaded_filename = finished_files[0]
                            break
                            
                    if downloaded_filename:
                        self.log(f"✅ Download complete! File saved as: {downloaded_filename}")
                        meta["pdf_filename"] = downloaded_filename
                        metadata_records.append(meta)
                    else:
                        # Fallback check: check if any pdf file was added
                        current_files = set(os.listdir(self.download_dir))
                        new_files = current_files - initial_files
                        if new_files:
                            # Might have finished right as the loop ended
                            downloaded_filename = list(new_files)[0]
                            self.log(f"✅ Download complete (delayed detection)! File: {downloaded_filename}")
                            meta["pdf_filename"] = downloaded_filename
                            metadata_records.append(meta)
                        else:
                            self.log("⚠️ Download timed out or failed to write to folder.")
                else:
                    self.log("❌ No PDF link could be found or resolved on the landing page.")

            # Save metadata summaries in the download directory
            if metadata_records:
                self.save_metadata(metadata_records, search_word)

        except Exception as e:
            self.log(f"❌ Critical Agent Error: {e}")
        finally:
            if self.driver:
                self.log("🏁 Closing browser session...")
                self.driver.quit()
                self.log("👋 Browser session closed.")
                
        return metadata_records

    def save_metadata(self, records, keyword):
        self.log("📦 Writing metadata summaries...")
        
        # Save JSON
        json_path = os.path.join(self.download_dir, "metadata.json")
        existing_data = []
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except:
                pass
                
        # Append new records (avoid duplicates by PMC ID)
        existing_pmcids = {r.get("pmcid") for r in existing_data}
        for rec in records:
            if rec["pmcid"] not in existing_pmcids:
                rec["search_keyword"] = keyword
                rec["download_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                existing_data.append(rec)
                
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2)
            
        # Save CSV
        csv_path = os.path.join(self.download_dir, "metadata.csv")
        if existing_data:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=existing_data[0].keys())
                writer.writeheader()
                writer.writerows(existing_data)
                
        self.log(f"💾 Saved metadata summary files to: {self.download_dir}")
