import time
import logging
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class MOINewsClient:
    def __init__(self, base_url: str = "https://www.moi.gov.eg/News/GetNews", retries: int = 3, backoff_factor: float = 1.0):
        self.base_url = base_url
        self.details_url = "https://www.moi.gov.eg/News/GetDetails"
        self.session = requests.Session()
        
        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.moi.gov.eg/"
        }

    def fetch_page(self, section_id: int = 3, page_index: int = 1) -> dict | None:
        params = {
            "sectionId": section_id,
            "pageIndex": page_index
        }
        try:
            response = self.session.get(self.base_url, params=params, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch page {page_index}: {e}")
            return None

    def scrape_full_article_text(self, news_id: str, section_id: int = 3) -> str:
        """Scrapes full news content strictly targeting article text containers."""
        params = {
            "newsId": news_id,
            "sectionId": section_id
        }
        try:
            response = self.session.get(self.details_url, params=params, headers=self.headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Remove header, footer, forms, and navigation menus entirely
                for unneeded in soup(["header", "footer", "nav", "script", "style", "form", "ul", "ol"]):
                    unneeded.decompose()

                extracted_texts = []
                
                # Target paragraphs in the page
                for p in soup.find_all("p"):
                    text = p.get_text(strip=True)
                    # Exclude UI/Login/System strings
                    ignore_keywords = [
                        "إنشاء حساب", "تسجيل الدخول", "نسيت كلمة المرور", 
                        "الرقم القومي", "حقوق محفوظة", "تكنولوجيا المعلومات"
                    ]
                    
                    if text and len(text) > 25 and not any(kw in text for kw in ignore_keywords):
                        if text not in extracted_texts:
                            extracted_texts.append(text)

                return " ".join(extracted_texts)
            return ""
        except Exception as e:
            logging.error(f"Failed to scrape article text for newsId {news_id}: {e}")
            return ""

    def fetch_all_news(self, section_id: int = 3, start_page: int = 1, max_pages: int = None, delay: float = 0.5):
        current_page = start_page
        
        while True:
            logging.info(f"Fetching news page {current_page}...")
            data = self.fetch_page(section_id=section_id, page_index=current_page)
            
            if not data or "results" not in data or not data["results"]:
                logging.info("No more results or error encountered. Stopping.")
                break

            results = data.get("results", [])
            pager = data.get("pager", {})
            total_count = pager.get("totalCount", 0)
            page_size = pager.get("pageSize", 8)
            
            total_pages = (total_count + page_size - 1) // page_size if page_size else 1
            
            yield results

            if max_pages and current_page >= max_pages:
                logging.info(f"Reached requested max_pages limit: {max_pages}")
                break

            if current_page >= total_pages:
                logging.info("Reached the last available page.")
                break

            current_page += 1
            time.sleep(delay)