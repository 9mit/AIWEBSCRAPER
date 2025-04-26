# scrape.py (Revised - Remove split_dom_content)
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import logging # Added for potential debugging

logger = logging.getLogger(__name__)

def scrape_website(url: str) -> str:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage") # Often needed in headless environments
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36") # Add user agent

    # Ensure chromedriver path is robust
    try:
        driver = Chrome(
            service=Service(executable_path="./chromedriver.exe"),
            options=options
        )
        driver.set_page_load_timeout(30) # Add timeout
    except Exception as e:
        logger.error(f"Failed to initialize Chrome Driver: {e}")
        raise RuntimeError(f"Failed to initialize Chrome Driver. Is chromedriver.exe in the correct path and executable? Error: {e}") from e

    try:
        logger.info(f"Attempting to scrape URL: {url}")
        driver.get(url)
        # Increased sleep might be needed for JS-heavy sites, but can be slow.
        # Consider WebDriverWait for specific elements if possible for dynamic content.
        time.sleep(5) # Slightly increased sleep
        page_source = driver.page_source
        logger.info(f"Successfully retrieved page source, length: {len(page_source)}")
        return page_source
    except Exception as e:
        logger.error(f"Error during scraping URL {url}: {e}")
        raise RuntimeError(f"Failed to scrape URL '{url}'. Error: {e}") from e
    finally:
        driver.quit()

def extract_body_content(html: str) -> str:
    if not html:
        logger.warning("HTML content is empty, cannot extract body.")
        return ""
    soup = BeautifulSoup(html, 'html.parser')
    return str(soup.body) if soup.body else ""

def clean_body_content(body_html: str) -> str:
    if not body_html:
        logger.warning("Body HTML is empty, cannot clean.")
        return ""
    soup = BeautifulSoup(body_html, 'html.parser')
    # Remove unwanted tags more aggressively
    for tag in soup(['script', 'style', 'meta', 'link', 'header', 'footer', 'nav', 'aside', 'form', 'button', 'iframe', 'noscript']):
        tag.decompose()
    # Get text, separated by newlines, strip whitespace, remove excessive blank lines
    text = soup.get_text(separator='\n', strip=True)
    cleaned_text = '\n'.join(line for line in text.splitlines() if line.strip())
    logger.info(f"Cleaned text length: {len(cleaned_text)}")
    return cleaned_text

# Removed split_dom_content function