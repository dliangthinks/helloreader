import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
import html # For escaping content
import logging
import json # For config persistence
import os # For config path
import asyncio # Needed for async dialog handling

# Import the scraper and its exception class
from web_scraper import WebScraper, ScraperException

# Define the HTML template structure - Base
HTML_TEMPLATE = """
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ /* Double braces for literal CSS brace */
            font-family: 'Songti SC', 'PingFang SC', sans-serif;
            background-color: {background_color}; /* Single braces for placeholder */
            color: {text_color}; /* Single braces for placeholder */
            font-size: 2.0em; 
            line-height: 1.6;
            margin: 20px;
        }} /* Double braces for literal CSS brace */
        #content {{ /* Double braces for literal CSS brace */
            white-space: pre-wrap; 
        }} /* Double braces for literal CSS brace */
    </style>
</head>
<body>
    <!-- H1 removed as title is in window bar -->
    <div id="content">{content}</div> /* Single braces for placeholder */
</body>
</html>
"""

# Config file path - Changed to local directory
CONFIG_FILE = 'helloreader_config.json'

# Default URL for testing
DEFAULT_TEST_URL = "https://www.piaotia.com/html/0/757/11485522.html"

# --- Custom URL Input Dialog ---
class UrlInputDialog(toga.Window):
    def __init__(self, app):
        super().__init__(title="Enter URL", resizable=False, size=(400, 150), closable=True)
        self.future = toga.App.app.loop.create_future()

        self.textinput = toga.TextInput(placeholder="https://example.com")
        self.ok_button = toga.Button("Load", on_press=self.on_accept)
        self.cancel_button = toga.Button("Cancel", on_press=self.on_cancel)

        button_box = toga.Box(
            children=[self.cancel_button, self.ok_button],
            style=Pack(direction=ROW, padding_right=5)
        )

        main_box = toga.Box(
            children=[
                toga.Label("Enter the URL to load:", style=Pack(padding=(10, 5))),
                self.textinput,
                toga.Box(style=Pack(flex=1)), # Spacer
                button_box
            ],
            style=Pack(direction=COLUMN, padding=10)
        )
        self.content = main_box

    def on_accept(self, widget, **kwargs):
        value = self.textinput.value.strip()
        if value:
            self.future.set_result(value)
            self.close()
        else:
            # Optionally show an error within the dialog or just ignore
            pass

    def on_cancel(self, widget, **kwargs):
        self.future.set_result(None) # Indicate cancellation
        self.close()

    # Override default close handler to ensure future is resolved
    def on_close(self, **kwargs):
        if not self.future.done():
            self.future.set_result(None)
        return True # Allow window to close

    def __await__(self):
        return self.future.__await__()


class HelloReader(toga.App):
    def __init__(self, formal_name, app_id):
        super().__init__(formal_name, app_id)
        self.scraper = WebScraper() # Instantiate the scraper
        self.current_url = None
        self.next_page_url = None
        self.previous_page_url = None
        self.last_scraped_data = None # Store last successful scrape
        self.current_theme = 'dark' # Default theme
        self.bookmarked_url = None # Store loaded bookmark
        self.load_config() # Load theme and bookmark

    def load_config(self):
        """Loads theme and last URL preference from config file."""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.current_theme = config.get('theme', 'dark')
                    self.bookmarked_url = config.get('last_url', None)
                    logging.info(f"Loaded config: theme={self.current_theme}, last_url={self.bookmarked_url}")
            else:
                logging.info("Config file not found. Using defaults.")
        except Exception as e:
            logging.warning(f"Could not load config file {CONFIG_FILE}: {e}")
            # Ensure defaults are set even if loading fails
            self.current_theme = self.current_theme or 'dark'
            self.bookmarked_url = self.bookmarked_url or None

    def save_config(self):
        """Saves current theme and last URL preference to config file."""
        try:
            # Only save last_url if current_url is set (meaning a page was successfully loaded)
            url_to_save = self.current_url if self.current_url else self.bookmarked_url
            config = {
                'theme': self.current_theme,
                'last_url': url_to_save
            }
            # Ensure config is only saved if url_to_save is not None
            if url_to_save:
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(config, f)
                logging.info(f"Saved config: {config}")
            else:
                logging.info("Skipping save, no valid URL to save.")
        except Exception as e:
            logging.warning(f"Could not save config file {CONFIG_FILE}: {e}")

    def startup(self):
        print("--- HelloReader startup initiated ---")
        # --- UI Elements --- 
        main_box = toga.Box(style=Pack(direction=COLUMN))

        # WebView for content display
        self.webview = toga.WebView(style=Pack(flex=1))

        # --- Navigation Buttons --- 
        self.previous_button = toga.Button("Previous Page", on_press=self.load_previous_page, enabled=False, style=Pack(margin=5))
        self.next_button = toga.Button("Next Page", on_press=self.load_next_page, enabled=False, style=Pack(margin=5))
        
        # Set initial theme icon
        initial_theme_icon = '🌙' if self.current_theme == 'dark' else '☀️'
        self.theme_button = toga.Button(initial_theme_icon, on_press=self.toggle_theme, style=Pack(margin=5))
        
        
        # Moved Load URL button here - triggers popup
        self.load_url_button = toga.Button("Load URL", on_press=self.handle_load_button, style=Pack(margin=5))
        
        spacer1 = toga.Box(style=Pack(flex=1))
        spacer2 = toga.Box(style=Pack(flex=1))
        button_box = toga.Box(style=Pack(direction=ROW, margin=5))
        button_box.add(self.previous_button)
        button_box.add(spacer1)
        button_box.add(self.theme_button) 
        button_box.add(self.load_url_button) # Added Load URL button here
        button_box.add(spacer2)
        button_box.add(self.next_button)

        # --- Assemble the main layout --- 
        main_box.add(self.webview) # Add WebView here
        main_box.add(button_box)

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box

        # --- Auto-load bookmarked URL if available ---
        if self.bookmarked_url:
            print(f"--- Scheduling auto-load for bookmarked URL: {self.bookmarked_url} ---")
            # Use add_background_task to run after startup completes
            self.add_background_task(self.load_bookmarked_url_background)
        else:
            print("--- No bookmark found, not auto-loading ---")

        print("--- Content set, attempting to show window ---")
        self.main_window.show()
        print("--- main_window.show() called ---")

    # Separate method to be run in background for auto-load
    async def load_bookmarked_url_background(self, widget, **kwargs):
        print(f"--- Background task: Loading {self.bookmarked_url} ---")
        self.load_url_and_update_ui(self.bookmarked_url)

    def format_html_content(self, data, theme='dark'):
        """Formats the fetched data into an HTML string with theme."""
        # Basic theming
        bg_color = "#121212" if theme == 'dark' else "#FFFFFF"
        text_color = "#FFFFFF" if theme == 'dark' else "#000000"

        # Prioritize HTML content if available
        final_content = data.get('content_html')
        is_html = True

        if final_content is None:
            # Fallback to text content if HTML wasn't extracted
            is_html = False
            plain_text = data.get('content_text', '')
            # --- New Fallback Logic: Add breaks based on observed pattern ---
            # Replace the sequence of non-breaking spaces with HTML breaks
            processed_text = plain_text.replace('\xa0\xa0\xa0\xa0', '<br><br>')
            # Maybe also replace single non-breaking spaces with regular spaces?
            processed_text = processed_text.replace('\xa0', ' ')
            final_content = processed_text

            logging.debug("Using processed text content with added <br> tags.")
        else:
             logging.debug("Using pre-formatted HTML content.")

        # Escape title separately
        title_text = html.escape(data.get('title', 'No Title'))
        
        # Use the HTML template
        return HTML_TEMPLATE.format(
            title=title_text,
            content=final_content, # Insert raw HTML or formatted text
            background_color=bg_color,
            text_color=text_color
        )

    def update_ui_with_content(self, data):
        """Updates the WebView and navigation buttons."""
        self.last_scraped_data = data # Store data for theme toggle
        self.next_page_url = data.get("next_page_url")
        self.previous_page_url = data.get("previous_page_url")
        self.current_url = data.get("_base_url") # Update current URL based on loaded data
        self.main_window.title = data.get("title", self.formal_name) # Update window title
        
        # Format and set content using the current theme
        html_content = self.format_html_content(data, theme=self.current_theme)
        self.webview.set_content(self.current_url, html_content) 

        # Update button states
        self.next_button.enabled = bool(self.next_page_url)
        self.previous_button.enabled = bool(self.previous_page_url)

        # Auto-save the successfully loaded URL as the bookmark
        self.bookmarked_url = self.current_url # Update bookmark reference
        self.save_config() 

    def load_url_and_update_ui(self, url):
        """Handles the process of fetching and displaying content for a URL."""
        if not url:
            # Don't show dialog if called during startup auto-load
            if hasattr(self, 'main_window') and self.main_window.visible:
                 self.main_window.dialog(toga.InfoDialog("Input Required", "URL cannot be empty."))
            else:
                logging.warning("load_url_and_update_ui called with empty URL.")
            return

        # Update internal state immediately
        temp_url = url # Store url requested, self.current_url updated on success
        self.main_window.title = f"Loading: {temp_url}..."
        self.next_button.enabled = False
        self.previous_button.enabled = False

        try:
            # Consider making this async if UI hangs
            scraped_data = self.scraper.fetch_chapter(temp_url)
            if scraped_data:
                scraped_data['_base_url'] = temp_url # Ensure the URL used is stored
                self.update_ui_with_content(scraped_data) # This sets self.current_url on success
            else:
                # Check if window exists before showing dialog
                if hasattr(self, 'main_window') and self.main_window.visible:
                    self.main_window.dialog(toga.ErrorDialog("Error", f"Failed to retrieve content (no data) from:\n{temp_url}"))
                self.main_window.title = self.formal_name
                # Don't clear self.current_url here, keep the last successful one

        except ScraperException as e:
            if hasattr(self, 'main_window') and self.main_window.visible:
                self.main_window.dialog(toga.ErrorDialog("Scraping Error", str(e)))
            self.main_window.title = self.formal_name
        except Exception as e:
            logging.exception("Unexpected error during page load:") # Log traceback
            if hasattr(self, 'main_window') and self.main_window.visible:
                self.main_window.dialog(toga.ErrorDialog("Unexpected Error", f"An unexpected error occurred: {str(e)}"))
            self.main_window.title = self.formal_name

    def toggle_theme(self, widget=None):
        """Toggles the theme and updates the display."""
        self.current_theme = 'light' if self.current_theme == 'dark' else 'dark'
        logging.info(f"Toggling theme to: {self.current_theme}")
        
        # Update button icon
        new_theme_icon = '🌙' if self.current_theme == 'dark' else '☀️'
        self.theme_button.text = new_theme_icon

        # Re-render content with the new theme if content exists
        if self.last_scraped_data and self.current_url:
            html_content = self.format_html_content(self.last_scraped_data, theme=self.current_theme)
            # Use the stored URL as the base for set_content
            base_url_for_webview = self.last_scraped_data.get('_base_url', self.current_url)
            self.webview.set_content(base_url_for_webview, html_content)
            logging.debug("WebView content updated with new theme.")
        else:
            logging.debug("No content loaded, theme toggle only changes preference.")
        
        # Save the new preference
        self.save_config()

    # --- New Async Handler for Load URL Button ---
    async def handle_load_button(self, widget):
        """Shows the URL input dialog and loads the entered URL."""
        print("--- handle_load_button triggered ---")
        dialog = UrlInputDialog(self)
        dialog.show()
        print("--- URL dialog shown, awaiting result ---")
        url = await dialog
        print(f"--- Dialog result: {url} ---")
        if url:
            print(f"--- Loading URL from dialog: {url} ---")
            self.load_url_and_update_ui(url)
        else:
            print("--- URL dialog cancelled or empty ---")

    def load_next_page(self, widget):
        """Loads the next page content."""
        if self.next_page_url:
            self.load_url_and_update_ui(self.next_page_url)
        else:
            self.main_window.dialog(toga.InfoDialog("Info", "No next page URL found."))

    def load_previous_page(self, widget):
        """Loads the previous page content."""
        if self.previous_page_url:
            self.load_url_and_update_ui(self.previous_page_url)
        else:
            self.main_window.dialog(toga.InfoDialog("Info", "No previous page URL found."))

    def handle_load_bookmark(self, widget):
        """Loads the last saved bookmark URL."""
        if self.bookmarked_url:
            self.load_url_and_update_ui(self.bookmarked_url)
        else:
            self.main_window.dialog(toga.InfoDialog("Info", "No bookmark saved yet."))

def main():
    print("--- main() called ---")
    # Provide formal_name and app_id explicitly
    app = HelloReader(
        formal_name="Hello Reader", 
        app_id="com.example.helloreader" # Use reverse domain notation
    )
    print("--- HelloReader instance created, returning app ---")
    return app

# Add the standard main execution block
if __name__ == '__main__':
    # Set logging level to DEBUG to see detailed scraper logs
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(module)s] %(message)s')
    print("--- Script executed directly (__name__ == '__main__') --- Logging level: DEBUG ---")
    hello_reader_app = main()
    print("--- Starting Toga main loop ---")
    hello_reader_app.main_loop() # Start the application event loop
    print("--- Toga main loop exited ---") # This will print when the app closes