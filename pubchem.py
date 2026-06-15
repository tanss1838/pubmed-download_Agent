import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class PubChemBrowserAgent:
    def __init__(self, download_dir="pubchem_downloads"):
        self.download_dir = os.path.abspath(download_dir)
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

        chrome_options = Options()
        # Keep the browser open so you can watch it pass the human checks
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True  # Forces background download
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.wait = WebDriverWait(self.driver, 20)
        print(f"📁 Saving files directly to: {self.download_dir}")

    def download_papers(self, search_word, count=10):
        try:
            # Step 1: Open PubChem
            print("🌐 Opening PubChem...")
            self.driver.get("https://pubchem.ncbi.nlm.nih.gov/")
            time.sleep(3)

            # Step 2: Search for 'thermoset'
            print(f"🔍 Searching for '{search_word}'...")
            search_input = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='text']")))
            search_input.send_keys(search_word)
            search_input.send_keys(Keys.RETURN)
            time.sleep(5)

            # Step 3: Safely switch to the 'Literature' tab using Javascript
            print("📑 Switching to the Literature Tab...")
            # Locate the exact tab element from your screenshot
            lit_tab = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-collection='literature']")))
            
            # Scroll down to it so Chrome can see it clearly
            self.driver.execute_script("arguments[0].scrollIntoView(true);", lit_tab)
            time.sleep(1)
            # Use direct JS click to prevent the GetHandleVerifier crash
            self.driver.execute_script("arguments[0].click();", lit_tab)
            print("✅ Successfully clicked Literature tab!")
            time.sleep(5)

            # Step 4: Collect the paper URLs
            print("🔗 Gathering individual paper links...")
            links = self.driver.find_elements(By.CSS_SELECTOR, "a.match-title, .result-item a")
            paper_urls = []
            
            for link in links:
                href = link.get_attribute("href")
                if href and href not in paper_urls and ("ncbi.nlm.nih.gov" in href or "doi.org" in href):
                    paper_urls.append(href)
                    if len(paper_urls) >= count:
                        break

            print(f"🎯 Found {len(paper_urls)} target papers. Starting downloads...")

            # Step 5: Visit each page and click the prominent blue PDF button
            for idx, url in enumerate(paper_urls, 1):
                print(f"\n⏳ [{idx}/{len(paper_urls)}] Opening page: {url}")
                self.driver.get(url)
                time.sleep(5) # Wait for page layout to build

                try:
                    # Target the blue "PDF" download button on the right side panel
                    pdf_btn = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.download-link, a[class*='pdf-link'], .actions-links-list a[href*='pdf'], a.pdf")))
                    
                    print("📥 PDF Button found! Triggering download...")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", pdf_btn)
                    self.driver.execute_script("arguments[0].click();", pdf_btn)
                    
                    # Essential 10-second wait for anti-bot check and file streaming
                    print("⏳ Waiting 10 seconds for verification check and download to finish...")
                    time.sleep(10)
                except Exception:
                    print("❌ No direct blue PDF button found on this specific landing page. Skipping.")

        except Exception as e:
            print(f"❌ Automation Error: {e}")

        finally:
            print("\n🏁 Session closed. Check your folder!")
            self.driver.quit()

if __name__ == "__main__":
    agent = PubChemBrowserAgent()
    agent.download_papers(search_word="thermoset", count=10)