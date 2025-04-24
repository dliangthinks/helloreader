import requests
from bs4 import BeautifulSoup
import re

def fetch_and_extract_title(url):
    try:
        # Send a GET request to the URL
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
        response = requests.get(url, headers=headers)
        
        # Raise an exception for bad status codes
        response.raise_for_status()

        # Decode the content using gb2312 encoding
        content = response.content.decode('gb2312', errors='replace')

        # Parse the HTML content
        soup = BeautifulSoup(content, 'html.parser')

        # Find the H1 tag
        h1_tag = soup.find('h1')

        if h1_tag:
            print("H1 tag found. Content:")
            print(h1_tag)

            # Extract the parts from the H1 tag
            a_tag = h1_tag.find('a')
            if a_tag:
                book_url = a_tag.get('href', '').rstrip('.html')
                book_title = a_tag.text.strip()
                chapter_title = h1_tag.contents[-1].strip()

                print(f"\nExtracted information:")
                print(f"Book URL: {book_url}")
                print(f"Book Title: {book_title}")
                print(f"Chapter Title: {chapter_title}")
            else:
                print("No 'a' tag found within the H1 tag.")
        else:
            print("No H1 tag found.")

        # Print the first few lines of the parsed HTML for inspection
        print("\nFirst 200 characters of parsed HTML:")
        print(soup.prettify()[:200])

    except Exception as e:
        print(f"An error occurred: {str(e)}")

# URL to fetch and parse
url = "https://www.piaotia.com/html/6/6022/3885105.html"

# Run the function
fetch_and_extract_title(url)