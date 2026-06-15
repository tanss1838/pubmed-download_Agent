import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class PubChemFinalDownloader:
    def __init__(self, download_dir="pubchem_downloads"):
        self.download_dir = os.path.abspath(download_dir)
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

        chrome_options = Options()
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.wait = WebDriverWait(self.driver, 20)
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        print(f"📁 Target download directory: {self.download_dir}")

    def download_papers(self, search_word, count=1):
        try:
            # 1. Search PubChem
            print("🌐 Opening PubChem...")
            self.driver.get("https://pubchem.ncbi.nlm.nih.gov/")
            time.sleep(3)

            print(f"🔍 Searching for '{search_word}'...")
            search_input = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='text']")))
            search_input.send_keys(search_word)
            search_input.send_keys(Keys.RETURN)
            time.sleep(6)

            # 2. Click Literature Tab
            print("📑 Switching view to the Literature Tab...")
            lit_tab_button = self.wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Literature')]/ancestor::div[@data-collection='literature' or contains(@class,'tab')] | //*[text()='Literature']")))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", lit_tab_button)
            time.sleep(2)
            self.driver.execute_script("arguments[0].click();", lit_tab_button)
            print("✅ Clicked Literature Tab successfully.")
            time.sleep(8) 

            # 3. Click the Specific Article Link
            print("🎯 Finding the specific paper link element...")
            paper_xpath = "//a[contains(., 'Recycling of Thermoset Materials')] | //*[contains(text(), 'Recycling of Thermoset Materials')]/ancestor::a"
            target_paper = self.wait.until(EC.presence_of_element_located((By.XPATH, paper_xpath)))
            
            backup_url = target_paper.get_attribute("href")
            print(f"🏃 Navigating to paper landing page...")
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_paper)
            time.sleep(1)
            self.driver.execute_script("arguments[0].click();", target_paper)
            
            time.sleep(3)
            if "query=" in self.driver.current_url and backup_url:
                self.driver.get(backup_url)
                
            time.sleep(8) 

            # 4. Target and Click the exact Blue PDF Button from your screenshot
            try:
                print("📥 Locating the blue 'PDF' download button...")
                
                # This XPATH maps precisely to the blue button circled in your screenshot
                pdf_xpath = "//a[contains(@class, 'int-box-link') and contains(., 'PDF')] | //a[contains(@class, 'pdf-link')] | //a[contains(., 'PDF (')] "
                pdf_btn = self.wait.until(EC.presence_of_element_located((By.XPATH, pdf_xpath)))
                
                pdf_download_url = pdf_btn.get_attribute("href")
                
                if pdf_download_url:
                    if pdf_download_url.startswith('/'):
                        # Resolve path correctly if it is a relative PMC domain link
                        pdf_download_url = "https://www.ncbi.nlm.nih.gov" + pdf_download_url
                        
                    print(f"📥 Found PDF stream: {pdf_download_url}")
                    response = requests.get(pdf_download_url, headers=self.headers, timeout=20)
                    
                    if response.status_code == 200:
                        file_name = f"Paper_1_{search_word}.pdf"
                        full_path = os.path.join(self.download_dir, file_name)
                        
                        with open(full_path, "wb") as f:
                            f.write(response.content)
                        print(f"✅ SUCCESS! File downloaded and saved: {file_name}")
                    else:
                        print(f"❌ Network file stream rejected (Status {response.status_code})")
            except Exception as e:
                print(f"❌ Could not trigger the PDF button on the landing page: {e}")

        except Exception as e:
            print(f"❌ Automation Error: {e}")

        finally:
            print(f"\n🏁 Finished. Check your folder here: {self.download_dir}")
            self.driver.quit()

if __name__ == "__main__":
    agent = PubChemFinalDownloader()
    agent.download_papers(search_word="thermoset", count=5)