import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class SafeBatchPDFDownloader:
    def __init__(self, download_dir="pubchem_downloads"):
        # Create the downloads folder if it doesn't exist
        self.download_dir = os.path.abspath(download_dir)
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
            
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        self.driver = None
        self.wait = None
        self.start_browser()

    def start_browser(self):
        """Starts or restarts the Chrome browser engine cleanly."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        print("\n⚙️ Initializing isolated Chrome background worker...")
        chrome_options = Options()
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--headless=new")  # Keeps it invisible and lightweight
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.wait = WebDriverWait(self.driver, 12)

    def process_queue(self, url_file="paper_urls.txt"):
        if not os.path.exists(url_file):
            print(f"❌ Error: Could not find '{url_file}'. Please ensure Step 1 ran correctly.")
            return

        with open(url_file, "r") as f:
            urls = [line.strip() for line in f if line.strip()]

        print(f"🚀 Found {len(urls)} URLs in queue. Starting batch download processing...")
        
        success_count = 0
        
        for index, target_url in enumerate(urls):
            # Name files cleanly based on their position index
            file_name = f"Paper_{index + 1}.pdf"
            full_path = os.path.join(self.download_dir, file_name)

            # CRITICAL: Skip tracking if file already exists locally
            if os.path.exists(full_path):
                continue

            # Refresh the Chrome engine every 50 loops to clear out hidden RAM leaks
            if index > 0 and index % 50 == 0:
                print(f"\n♻️ Completed 50 items. Flushing browser memory cache...")
                self.start_browser()

            print(f"📥 Processing [{index + 1}/{len(urls)}] -> {target_url}")
            try:
                self.driver.get(target_url)
                time.sleep(2.5) # Allow dynamic landing page structures to load

                # Dynamic XPATH to capture the blue PDF download buttons on NCBI / PMC landing structures
                pdf_xpath = (
                    "//a[contains(@class, 'int-box-link') and contains(., 'PDF')]"
                    " | //a[contains(@class, 'pdf-link')]"
                    " | //a[contains(., 'PDF (')]"
                    " | //a[span[contains(text(), 'PDF')]]"
                    " | //a[contains(@href, '.pdf')]"
                )
                
                pdf_btn = self.wait.until(EC.presence_of_element_located((By.XPATH, pdf_xpath)))
                pdf_download_url = pdf_btn.get_attribute("href")
                
                if pdf_download_url:
                    # Fix relative system URLs if they lack domains
                    if pdf_download_url.startswith('/'):
                        base_domain = "https://www.ncbi.nlm.nih.gov"
                        pdf_download_url = base_domain + pdf_download_url
                        
                    # Request the raw file data block
                    response = requests.get(pdf_download_url, headers=self.headers, timeout=20)
                    if response.status_code == 200:
                        with open(full_path, "wb") as f:
                            f.write(response.content)
                        print(f"   ✅ Saved successfully as {file_name}")
                        success_count += 1
                    else:
                        print(f"   ❌ HTTP Error: Stream rejected with status {response.status_code}")
            except Exception:
                print(f"   ⚠️ Skipping: PDF download link layout structured differently or restricted.")
                continue

        if self.driver:
            self.driver.quit()
        print(f"\n🏁 Finished! Successfully added {success_count} new PDFs to your collection folder.")

if __name__ == "__main__":
    downloader = SafeBatchPDFDownloader()
    downloader.process_queue()