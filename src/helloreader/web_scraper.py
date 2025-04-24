import requests
from bs4 import BeautifulSoup, NavigableString
import logging
from urllib.parse import urljoin
# import re # No longer needed for this approach

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ScraperException(Exception):
    """Custom exception for scraper errors."""
    pass

class WebScraper:
    """Handles fetching and parsing web content for the reader."""

    def __init__(self):
        # Initial configuration for piaotia.com (Task 1.5)
        # TODO: Move this to an external config file later
        self.config = {
            'base_url': 'https://www.piaotia.com/', # Needed for urljoin
            'content_selector': '#shop', # Primary content selector - CHANGED from #content
            'next_link_text': '下一章',
            'prev_link_text': '上一章',
            'title_selector': 'h1',
            'encoding_fallback': 'gbk', # CHANGED from gb2312 to gbk
            # Disable fallback markers temporarily as they were likely based on #content
            'fallback_start_marker': None, 
            'fallback_end_marker': None 
        }
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }

    def _fetch_html(self, url):
        """Fetches HTML content from a URL with error handling."""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            # Force GBK encoding - covers more chars than gb2312
            response.encoding = self.config.get('encoding_fallback', 'gbk') 
            logging.info(f"Fetched {url}, forced encoding: {response.encoding}")
            return response.text
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error fetching {url}: {e}")
            raise ScraperException(f"Failed to fetch content from {url}. Network error: {e}") from e
        except Exception as e:
            logging.error(f"Unexpected error fetching {url}: {e}")
            raise ScraperException(f"An unexpected error occurred while fetching {url}: {e}") from e


    def fetch_chapter(self, url):
        """Fetches content using title/link selectors and EXACT text slicing for main content."""
        logging.info(f"Fetching chapter: {url}")
        html_content_raw = self._fetch_html(url) # Get the raw HTML string
        soup = BeautifulSoup(html_content_raw, 'html.parser') # Use BS4 for title/links

        # 1. Extract Title using BS4
        title_element = soup.select_one(self.config['title_selector']) # Usually h1
        title = title_element.get_text(strip=True) if title_element else "Title Not Found"
        logging.info(f"Extracted Title: {title}")

        # --- Content Extraction using EXACT Text Slicing --- 
        content_html = None
        start_marker = "<br>" # Exact marker
        end_marker = "</div>" # Exact marker
        
        try:
            # Find end of H1 tag to start search after it
            h1_end_index = -1
            search_start_pos = 0 # Position in raw HTML to start searching for markers
            if title_element:
                title_html_str = str(title_element) # Get H1 tag as string
                h1_start_index_in_raw = html_content_raw.find(title_html_str)
                if h1_start_index_in_raw != -1:
                     h1_end_index = h1_start_index_in_raw + len(title_html_str)
                     search_start_pos = h1_end_index
                     logging.debug(f"Found H1 tag. Starting search for exact '{start_marker}' after index {search_start_pos}")
                else:
                    logging.warning("Could not find H1 tag string in raw HTML. Searching for markers from start.")
                    search_start_pos = 0
            else:
                 logging.warning("Could not find H1 element via BS4. Searching for markers from start.")
                 search_start_pos = 0

            # Find the first exact <br> *after* search_start_pos
            start_marker_found_at = html_content_raw.find(start_marker, search_start_pos)
            
            if start_marker_found_at != -1:
                slice_start_index = start_marker_found_at + len(start_marker) # Position *after* the found <br> tag
                logging.info(f"Found exact start marker '{start_marker}' at index {start_marker_found_at}. Content slice starts after index {slice_start_index}.")
                
                # Find the first exact </div> *after* the start marker's end position (slice_start_index)
                slice_end_index = html_content_raw.find(end_marker, slice_start_index)
                
                if slice_end_index != -1:
                    logging.info(f"Found exact end marker '{end_marker}' at index {slice_end_index}. Content slice ends before index {slice_end_index}.")
                    
                    # Extract the slice
                    content_html = html_content_raw[slice_start_index:slice_end_index]
                    
                    # Basic cleanup
                    content_html = content_html.strip()
                    content_html = content_html.replace("&nbsp;", " ") 
                    
                    logging.info(f"Successfully extracted content ({len(content_html)} chars) using exact text slicing.")
                else:
                    logging.warning(f"Could not find exact end marker '{end_marker}' after index {slice_start_index}.")
            else:
                logging.warning(f"Could not find exact start marker '{start_marker}' after index {search_start_pos}.")

        except Exception as e:
            logging.error(f"Error during exact text slicing content extraction: {e}", exc_info=True)

        # Fallback / Error Handling
        if not content_html:
             logging.error(f"Failed to extract content using exact text slicing for {url}. Setting empty content.")
             content_html = "[Content extraction failed]"

        # --- End Content Extraction Logic --- 

        # Extract Links using BS4 (Keep existing logic)
        next_page_url = None
        prev_page_url = None
        try:
            next_link = soup.find('a', string=self.config['next_link_text'])
            if next_link and next_link.get('href'):
                next_page_url = urljoin(url, next_link['href'])
            prev_link = soup.find('a', string=self.config['prev_link_text'])
            if prev_link and prev_link.get('href'):
                prev_page_url = urljoin(url, prev_link['href'])
            logging.info(f"Prev URL: {prev_page_url}, Next URL: {next_page_url}")
        except Exception as e:
             logging.warning(f"Could not parse next/previous links: {e}")

        return {
            "title": title,
            "content_html": content_html, # HTML content slice or error message
            "next_page_url": next_page_url,
            "previous_page_url": prev_page_url
        }

# Example usage (optional, for testing)
# if __name__ == '__main__':
#     scraper = WebScraper()
#     try:
#         # Test URL - use one that matches the expected structure
#         test_url = 'https://www.piaotia.com/html/0/757/11484092.html' # Example URL
#         logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(module)s] %(message)s')
#         data = scraper.fetch_chapter(test_url)
#         print(f"\n--- Results for: {test_url} ---")
#         print(f"Title: {data['title']}")
#         print(f"Next URL: {data['next_page_url']}")
#         print(f"Prev URL: {data['previous_page_url']}")
#         print("\nContent snippet:")
#         # Ensure content is treated as string for slicing
#         content_display = data.get('content_html', '')
#         print(content_display[:1000] + ("..." if len(content_display) > 1000 else ""))
#     except ScraperException as e:
#         print(f"Scraper Error: {e}")
#     except Exception as e:
#         print(f"General Error: {e}") 