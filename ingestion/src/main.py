import os
import sys
import json
import re

# Add project root directory to system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api_client import MOINewsClient


def clean_text(text: str) -> str:
    """Cleans raw text by removing HTML whitespace artifacts and normalizing spaces."""
    if not text:
        return ""
    cleaned = re.sub(r"&nbsp;|\t|\r|\n", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def main():
    client = MOINewsClient()
    all_articles = []
    
    # Process page 1 (8 articles) for test run
    for page_results in client.fetch_all_news(section_id=3, start_page=1, max_pages=1, delay=1.0):
        for item in page_results:
            news_id = item.get("newsId")
            print(f"Scraping full article content for ID: {news_id}...")
            
            # Scrape full text from the HTML details page
            raw_full_text = client.scrape_full_article_text(news_id=news_id, section_id=3)
            cleaned_full_text = clean_text(raw_full_text)
            
            # Fallback to API brief if scraping yields empty result
            final_content = cleaned_full_text if cleaned_full_text else clean_text(item.get("details"))
            
            cleaned_item = {
                "news_id": news_id,
                "title": clean_text(item.get("title")),
                "brief": clean_text(item.get("details")),
                "full_content": final_content,
                "date_published": item.get("datePublished"),
                "published_date_str": item.get("timeSpan"),
                "image_url": item.get("imagePathLarge")
            }
            all_articles.append(cleaned_item)

    # Save output to data directory
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "sample_news.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    print(f"\nSUCCESS: Successfully processed {len(all_articles)} articles with full scraped content!")
    print(f"File saved to: {output_path}")


if __name__ == "__main__":
    main()