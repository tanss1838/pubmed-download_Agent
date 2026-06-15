import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class PubChemBrowserAgent:
    def __init__(self, download_dir="thermoset_manual_pdfs"):
        # Setup absolute path for downloads so Chrome drops PDFs directly into your target folder
        self.download_dir = os.path.abspath(download_dir)
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
            
        self.setup_browser()

    def setup_browser(self):
        """Initializes a visible Chrome browser with tailored download behaviors"""
        options = webdriver.ChromeOptions()
        
        # Configure Chrome to auto-download PDFs instead of opening them in a built-in preview tab
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True 
        }
        options.add_experimental_option("prefs", prefs)
        
        # Start browser
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        self.wait = WebDriverWait(self.driver, 15)

    def run_agent(self, search_word="thermoset", target_count=5):
        try:
            print("=== Step 1 & 2: Opening PubChem and Searching ===")
            self.driver.get("https://pubchem.ncbi.nlm.nih.gov/")
            
            # Locate the main search input bar, type keyword, and press enter
            search_bar = self.wait.until(EC.presence_of_element_located((By.NAME, "term")))
            search_bar.send_keys(search_word)
            search_bar.send_keys(Keys.ENTER)
            
            print("=== Step 3: Navigating to Literature Results ===")
            # Give the search dashboard a few moments to populate tabs
            time.sleep(5)
            
            # Click on the 'Literature' link on the search results display interface
            try:
                literature_tab = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@data-action, 'literature') or contains(text(), 'Literature')]")))
                literature_tab.click()
                time.sleep(3)
            except Exception:
                print("[Info] Already viewing or parsing consolidated literature rows...")

            print("=== Step 4: Collecting Paper Links ===")
            # Extract links pointing out to PubMed or publisher landing portals
            links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'pubmed.ncbi.nlm.nih.gov') or contains(@href, 'pmc/articles')]")
            urls = [link.get_attribute("href") for link in links if link.get_attribute("href")]
            # Filter and deduplicate
            urls = list(set(urls))
            
            print(f"[Agent] Extracted {len(urls)} paper pathways to inspect.")
            
            saved_pdfs = 0
            
            # === Step 5: Open Papers to inspect them sequentially ===
            for index, paper_url in enumerate(urls):
                if saved_pdfs >= target_count:
                    break
                
                print(f"\n[Agent] Step 5: Checking target article [{index+1}]: {paper_url}")
                
                # Capture current browser window handle to return to it later
                main_window = self.driver.current_window_handle
                
                # Open paper link in a fresh, isolated background browser tab
                self.driver.execute_script(f"window.open('{paper_url}', '_blank');")
                # Switch control context to the new tab
                self.driver.switch_to.window(self.driver.window_handles[-1])
                time.sleep(4) # Allow structural page markup to load fully
                
                # === Step 6 & 7: Look for explicit PDF triggers and click if found ===
                pdf_keywords = ["PDF", "Download PDF", "Full Text PDF", "Download full text"]
                clicked = False
                
                for word in pdf_keywords:
                    try:
                        # Construct a dynamic case-insensitive XPath query to look for text strings matching the keywords
                        xpath_query = f"//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{word.lower()}') or contains(@title, '{word}')]"
                        pdf_button = self.driver.find_element(By.XPATH, xpath_query)
                        
                        if pdf_button.is_displayed():
                            print(f"[Found Button] Target match: '{word}'. Executing structural download action...")
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", pdf_button)
                            time.sleep(1)
                            pdf_button.click()
                            time.sleep(5) # Allow download buffer stream time to hit the directory
                            saved_pdfs += 1
                            clicked = True
                            break
                    except Exception:
                        continue
                
                if not clicked:
                    print("[Info] This particular journal structure did not reveal a direct layout download link.")
                
                # Close out the current working paper tab and resume position
                self.driver.close()
                self.driver.switch_to.window(main_window)
                
            print(f"\n=== Success! Downloaded {saved_pdfs}/{target_count} PDFs inside '{self.download_dir}' folder. ===")
            
        finally:
            print("\n[Agent] Task ended. Keeping browser session open for 10 seconds before shutdown...")
            time.sleep(10)
            self.driver.quit()

if __name__ == "__main__":
    agent = PubChemBrowserAgent()
    agent.run_agent(search_word="thermoset", target_count=5)