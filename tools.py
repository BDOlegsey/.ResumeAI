from langchain.tools import tool
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from config import SELENIUM_HEADLESS
import logging
import time

logger = logging.getLogger(__name__)

@tool
def search_web_tool(employer_name: str, job_title: str) -> str:
    """
    Tool for the Search Agent to scrape information about an employer and job role.
    Uses Selenium to interact with the web like a human user.
    """
    logger.info(f"Starting web search for employer: {employer_name}, job: {job_title}")
    
    # Configure the browser options
    options = ChromeOptions() # Can be switched to FirefoxOptions() if needed
    if SELENIUM_HEADLESS:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = None
    try:
        # Initialize the driver
        driver = webdriver.Chrome(options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Example search logic (this is a simplified version)
        # In practice, you might need to search on LinkedIn, company websites, Glassdoor, etc.
        search_query = f"{employer_name} company overview"
        search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
        
        driver.get(search_url)
        time.sleep(2) # Allow page to load

        # Wait for and extract results (this is a basic example)
        # Real implementation needs robust selectors and error handling for different sites
        try:
            # Look for the first result snippet
            snippet_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='main'] .g .s > div > span"))
            )
            company_info = snippet_element.text
        except:
            company_info = "No specific company overview snippet found on Google."

        # For job-specific info, a more targeted search might be needed
        job_search_query = f"{job_title} at {employer_name} requirements"
        job_search_url = f"https://www.google.com/search?q={job_search_query.replace(' ', '+')}"
        driver.get(job_search_url)
        time.sleep(2)

        try:
            job_snippet_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='main'] .g .s > div > span"))
            )
            job_specific_info = job_snippet_element.text
        except:
            job_specific_info = "No specific job requirements snippet found on Google."
            
        # Attempt to find the company's official website link and scrape from there
        # This is complex and varies greatly between sites. A basic attempt on the search results page.
        try:
            official_site_link = driver.find_element(By.XPATH, "//div[@role='main']//a[contains(@href, '{}')]".format(employer_name.replace(' ', '')))
            if official_site_link:
                official_url = official_site_link.get_attribute('href')
                if official_url and employer_name.lower() in official_url.lower():
                    driver.get(official_url)
                    time.sleep(3) # Allow page to load
                    # Extract key info from the official site (e.g., About Us, Careers page)
                    # This requires custom logic per site and is highly variable.
                    # For now, append a note.
                    company_info += f"\n\nNote: Visited official site {official_url}, but specific content extraction requires custom logic per site."
        except:
            pass # Ignore errors if official site cannot be found or scraped simply


        logger.info(f"Completed web search for {employer_name}.")
        return f"Company Info:\n{company_info}\n\nJob Specific Info:\n{job_specific_info}"

    except Exception as e:
        logger.error(f"Error during web search for {employer_name}: {e}")
        return f"An error occurred while searching for information about {employer_name} and {job_title}: {str(e)}"
    finally:
        if driver:
            driver.quit()

# --- Tool Registration for LangGraph ---
# LangGraph typically expects tools to be passed in a specific format.
# We define a list of callable tools here.
TOOLS = [search_web_tool]