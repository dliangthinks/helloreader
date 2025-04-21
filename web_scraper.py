import requests
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin

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
            'content_selector': '#content', # Primary content selector
            'next_link_text': '下一章',
            'prev_link_text': '上一章',
            'title_selector': 'h1',
            'encoding_fallback': 'gb2312',
            # Add original markers for fallback (Task 1.5 extension)
            'fallback_start_marker': '返回书页', 
            'fallback_end_marker': '快捷键' 
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

            # Force gb2312 encoding based on site knowledge
            response.encoding = self.config.get('encoding_fallback', 'gb2312') 
            logging.info(f"Forcing encoding: {response.encoding}")

            # # Basic encoding detection (Task 1.4) - Keep commented for now
            # if response.encoding:
            #     response.encoding = response.encoding
            #     logging.info(f"Detected encoding: {response.encoding}")
            # else:
            #      # Fallback if detection fails or header is missing
            #     response.encoding = self.config.get('encoding_fallback', 'utf-8')
            #     logging.info(f"Using fallback encoding: {response.encoding}")

            return response.text
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error fetching {url}: {e}")
            raise ScraperException(f"Failed to fetch content from {url}. Network error: {e}") from e
        except Exception as e:
            logging.error(f"Unexpected error fetching {url}: {e}")
            raise ScraperException(f"An unexpected error occurred while fetching {url}: {e}") from e


    def fetch_chapter(self, url):
        """Fetches, parses, and cleans content for a given chapter URL."""
        logging.info(f"Fetching chapter: {url}")
        html_content = self._fetch_html(url)
        soup = BeautifulSoup(html_content, 'html.parser')

        # Extract Title (Task 1.5 / 2.4 - partial prep)
        title_element = soup.select_one(self.config['title_selector'])
        title = title_element.get_text(strip=True) if title_element else "Title Not Found"

        # Extract Content (Task 1.6 - Modified with fallback)
        content_element = soup.select_one(self.config['content_selector'])
        content_html = None # Initialize variable for HTML content
        content_text = None # Initialize variable for text content (for fallback)

        if content_element:
            logging.info(f"Found content using selector: {self.config['content_selector']}")
            # Remove potential ads or unwanted elements within the content div if needed
            # Example: for ad_element in content_element.select('.ad'): ad_element.decompose()
            
            # --- Get inner HTML content --- 
            content_html = ''.join(str(tag) for tag in content_element.contents)
            content_html = content_html.strip()
            logging.debug(f"Extracted HTML content snippet: {content_html[:200]}...")
            # --- Keep text extraction as well, maybe useful later? ---
            # content_text = content_element.get_text(separator='\n', strip=True) 

        else:
            # Fallback to original text slicing logic (still extracts TEXT only)
            logging.warning(f"Content selector '{self.config['content_selector']}' not found. Attempting fallback slicing.")
            full_text = soup.get_text()
            # --- Remove DEBUG log --- 
            # logging.debug(f"repr() of full_text snippet BEFORE slicing:\n{repr(full_text[:500])}") 

            start_marker = self.config.get('fallback_start_marker')
            end_marker = self.config.get('fallback_end_marker')

            # -- Removed marker presence checks for now to focus on full_text --
            # start_marker_found = start_marker in full_text if start_marker else False
            # end_marker_found = end_marker in full_text if end_marker else False
            # logging.debug(f"Check for start marker '{start_marker}': {start_marker_found}")
            # logging.debug(f"Check for end marker '{end_marker}': {end_marker_found}")

            # --- Use original find logic directly --- 
            if start_marker and end_marker: # Check markers are configured
                start_index = full_text.find(start_marker)
                end_index = full_text.find(end_marker, start_index + len(start_marker) if start_index != -1 else 0)
                
                if start_index != -1 and end_index != -1: # Check position/order
                    # Fallback provides TEXT content
                    content_text = full_text[start_index + len(start_marker):end_index].strip()
                    # --- Remove DEBUG log --- 
                    # logging.debug(f"Fallback extracted text (repr snippet AFTER slicing): {repr(content_text[:300])}") 
                    logging.info("Successfully extracted content using fallback markers (TEXT only).")
                else:
                    logging.error(f"Fallback markers not found or in wrong order in full_text.")
                    # If markers fail, maybe grab body text as last resort? Or raise error.
                    content_text = soup.body.get_text(separator='\n', strip=True) if soup.body else ""
                    if not content_text:
                         # Log HTML before raising final error
                         logging.error(f"Failed to extract content. Logging start of HTML for {url}:\n{html_content[:1000]}") # Log first 1000 chars
                         failed_to_extract = True
                         raise ScraperException("Could not find main content using selector or fallback markers (TEXT only).")
            else:
                 # Error if markers aren't configured
                 logging.error(f"Fallback markers not configured.")
                 # Log HTML before raising final error
                 logging.error(f"Failed to extract content. Logging start of HTML for {url}:\n{html_content[:1000]}") # Log first 1000 chars
                 failed_to_extract = True
                 raise ScraperException("Content selector failed and fallback markers not configured.")

        # Extract Links (Task 1.3 & 1.5)
        next_page_url = None
        prev_page_url = None

        try:
            next_link = soup.find('a', string=self.config['next_link_text'])
            if next_link and next_link.get('href'):
                 # Use urljoin for robust URL construction
                next_page_url = urljoin(url, next_link['href'])
        except Exception as e:
             logging.warning(f"Could not parse next link: {e}")


        try:
            prev_link = soup.find('a', string=self.config['prev_link_text'])
            if prev_link and prev_link.get('href'):
                 # Use urljoin for robust URL construction
                prev_page_url = urljoin(url, prev_link['href'])
        except Exception as e:
             logging.warning(f"Could not parse previous link: {e}")

        logging.info(f"Successfully parsed content for: {title}")
        return {
            "title": title,
            "content_html": content_html, # Return HTML if found
            "content_text": content_text, # Return Text if found via fallback
            "next_page_url": next_page_url,
            "previous_page_url": prev_page_url
        }

# Example usage (optional, for testing)
# if __name__ == '__main__':
#     scraper = WebScraper()
#     try:
#         # Test URL
#         test_url = 'https://www.piaotia.com/html/6/6022/3885105.html'
#         data = scraper.fetch_chapter(test_url)
#         print(f"Title: {data['title']}")
#         print(f"Next URL: {data['next_page_url']}")
#         print(f"Prev URL: {data['previous_page_url']}")
#         print("\nContent snippet:")
#         print(data['content'][:500] + "...") # Print first 500 chars
#     except ScraperException as e:
#         print(f"Scraper Error: {e}")
#     except Exception as e:
#         print(f"General Error: {e}") 