# HelloReader

A simple cross-platform desktop application built with the Toga GUI framework for reading web novel chapters directly from their URLs.

## Features

*   **Web Content Fetching:** Loads chapter content from a provided URL.
*   **Chapter Navigation:** Buttons to load the "Next Page" and "Previous Page" based on links found on the current page.
*   **Readable Display:** Presents the extracted main content in a clean, scrollable view.
*   **Dark/Light Theme:** Toggle between dark and light themes for comfortable reading. Theme preference is saved.
*   **URL Input:** Load chapters by entering a URL via a dedicated dialog box ("Load URL" button).
*   **Bookmarking:**
    *   Automatically saves the last successfully loaded chapter URL.
    *   Automatically loads the bookmarked URL when the application starts.
    *   Manually load the bookmarked URL using the "Load Last Page" button.
*   **Configurable Scraping (Basic):** The `web_scraper.py` file contains logic to extract content, currently tailored for sites like `piaotia.com` using specific HTML markers (`<br>` after `<h1>` as start, `</div>` as end). Handles `gbk` encoding.

## Technology Stack

*   **GUI Framework:** [Toga](https://toga.readthedocs.io/)
*   **HTTP Requests:** [Requests](https://requests.readthedocs.io/)
*   **HTML Parsing:** [Beautiful Soup 4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
*   **Configuration:** JSON (standard library)
*   **Language:** Python 3




## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd HelloReader
    ```
2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # On Windows
    # .\venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

Once the setup is complete, run the application from the project's root directory:

```bash
python helloreader.py
```

## Configuration

The application uses a `helloreader_config.json` file (created in the same directory as the script) to store preferences:

*   `theme`: Stores the last selected theme ("dark" or "light").
*   `last_url`: Stores the URL of the last successfully loaded chapter.

This file is loaded on startup and saved when the theme is changed or a new chapter is loaded successfully.

## Web Scraping Notes

The current web scraping logic in `web_scraper.py` uses a specific strategy (finding content between `<br>` after `<h1>` and the next `</div>`) tailored for the structure observed on `piaotia.com`. This logic might need significant adjustments to work correctly on websites with different HTML structures. The scraper also assumes `gbk` encoding.



## Trajectory

 The project evolved through different technical approaches: basic HTML generation, wxPython GUI, and finally Toga GUI. 

 ### `v4`
- **Framework:** Toga
- **Functionality:**
    - Creates a desktop application using the Toga GUI toolkit.
    - Provides an input field for a starting URL.
    - Fetches content from the provided URL (defaults to a specific `piaotia.com` URL).
    - Uses `requests` and `BeautifulSoup` for web scraping.
    - Decodes content using `gb2312`.
    - Cleans HTML content by removing ads and extracting text between specific markers ("返回书页" and "快捷键").
    - Displays the cleaned content within a `toga.WebView`.
    - Extracts 'Next Page' and 'Previous Page' links from the source HTML.
    - Provides 'Next Page' and 'Previous Page' buttons in the UI to navigate chapters.
- **Status:** Appears to be the most recent and functional version among the reader applications.

### `v3`
- **Framework:** wxPython
- **Functionality:**
    - Creates a desktop application using the wxPython GUI toolkit.
    - Uses `wx.html2.WebView` to display content.
    - Fetches, cleans (similar logic to `working toga` but slightly different end marker "返回顶部"), and displays content from a hardcoded `piaotia.com` URL.
    - Provides a 'Next Page' button in the UI.
    - Lacks 'Previous Page' functionality and URL input compared to `working toga`.
- **Status:** An alternative implementation using wxPython, likely preceding the Toga version.

### `Reader v2`
- **Framework:** None (Generates HTML, uses web browser)
- **Functionality:**
    - Fetches and cleans content from a hardcoded `piaotia.com` URL.
    - Improved cleaning compared to V1 (using start/end markers).
    - Generates an HTML file (`content.html`) with the content and basic styling (dark mode).
    - Adds a 'Next Page' button to the generated HTML.
    - Opens the generated HTML file in the default web browser using the `webbrowser` module.
- **Status:** An intermediate version, moving display logic to HTML/browser but without a dedicated GUI framework.

### `Reader v1`
- **Framework:** None (Generates HTML, uses web browser)
- **Functionality:**
    - The earliest version. Fetches and cleans content from a hardcoded `piaotia.com` URL.
    - Basic cleaning (removes some elements).
    - Generates an HTML file (`content.html`) with the content.
    - Implements 'Next Page' navigation via JavaScript listening for the Right Arrow key within the browser.
    - Opens the generated HTML file in the default web browser.
- **Status:** Initial proof-of-concept.