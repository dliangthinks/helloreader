import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, HIDDEN, VISIBLE
import html # For escaping content
import logging
import json # For config persistence
import os # For config path
import asyncio # Needed for async dialog handling
from pathlib import Path # Add this import

# Import the scraper and its exception class
from .web_scraper import WebScraper, ScraperException

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
            font-size: {font_size:.1f}em; 
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

# Config file name (will be joined with app data path)
CONFIG_FILENAME = 'helloreader_config.json'

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
        
        super().__init__(formal_name=formal_name, app_id=app_id)
        self.scraper = WebScraper() # Instantiate the scraper
        self.current_url = None
        self.next_page_url = None
        self.previous_page_url = None
        self.last_scraped_data = None # Store last successful scrape
        self.current_theme = 'dark' # Default theme
        self.bookmarked_url = None # Store loaded bookmark
        self.current_font_size = 2.0 # Set default before load_config
        # self.load_config() # Load theme and bookmark

    @property
    def config_path(self) -> Path:
        """Returns the platform-specific path to the config file."""
        # self.paths.data is the correct location for user config/data
        return self.paths.data / CONFIG_FILENAME

    def load_config(self):
        """Loads theme and last URL preference from config file."""
        try:
            config_path = self.config_path
            if config_path.exists():
                with config_path.open('r') as f:
                    config = json.load(f)
                    self.current_theme = config.get('theme', 'dark')
                    self.bookmarked_url = config.get('last_url', None)
                    # Load font size, defaulting to the initial value
                    self.current_font_size = float(config.get('font_size', self.current_font_size))
                    logging.info(f"Loaded config from {config_path}: theme={self.current_theme}, last_url={self.bookmarked_url}")
            else:
                logging.info(f"Config file not found at {config_path}. Using defaults.")
        except Exception as e:
            logging.warning(f"Could not load config file {self.config_path}: {e}")
            # Ensure defaults are set even if loading fails
            self.current_theme = self.current_theme or 'dark'
            self.bookmarked_url = self.bookmarked_url or None

    def save_config(self):
        """Saves current theme and last URL preference to config file."""
        config_path = self.config_path
        try:
            # Only save last_url if current_url is set (meaning a page was successfully loaded)
            url_to_save = self.current_url if self.current_url else self.bookmarked_url
            config = {
                'theme': self.current_theme,
                'last_url': url_to_save,
                'font_size': self.current_font_size
            }
            # Ensure config is only saved if url_to_save is not None
            if url_to_save:
                # Ensure the data directory exists
                config_path.parent.mkdir(parents=True, exist_ok=True)
                with config_path.open('w') as f:
                    json.dump(config, f)
                logging.info(f"Saved config to {config_path}: {config}")
            else:
                logging.info("Skipping save, no valid URL to save.")
        except Exception as e:
            logging.warning(f"Could not save config file {config_path}: {e}")

    def startup(self):
        # Load config first to get the bookmarked URL
        # This also loads font size preference
        self.load_config()

        print("--- HelloReader startup initiated ---")
        # --- UI Elements --- 
        main_box = toga.Box(style=Pack(direction=COLUMN))

        # Store main_box as instance variable for theming
        self.main_box = main_box

        # WebView for content display
        self.webview = toga.WebView(style=Pack(flex=1))

# --- Navigation Buttons ---
        # Remove style=Pack(margin=5) from individual buttons
        self.previous_button = toga.Button("Previous Page", on_press=self.load_previous_page, enabled=False)
        self.next_button = toga.Button("Next Page", on_press=self.load_next_page, enabled=False)

        # Set initial theme icon
        initial_theme_icon = '🌙' if self.current_theme == 'dark' else '☀️'
        # Remove style=Pack(margin=5)
        self.theme_button = toga.Button(initial_theme_icon, on_press=self.toggle_theme)

        spacer1 = toga.Box(style=Pack(flex=1))
        spacer2 = toga.Box(style=Pack(flex=1))

        # Apply PADDING to the container box instead of margin
        # This creates space around the elements *inside* this box
        nav_button_box = toga.Box(style=Pack(direction=ROW, padding=5)) # Renamed for clarity

        # Add the buttons (now without individual margin styles) to the container
        nav_button_box.add(self.previous_button)
        nav_button_box.add(spacer1)
        nav_button_box.add(self.theme_button)
        # Add new icon button to toggle URL input visibility
        # Changed from icon to text button
        self.show_url_input_button = toga.Button(
            "➕", # Heavy Plus Sign glyph
            on_press=self.toggle_url_input_visibility,
            style=Pack(width=40, color="#FFFFFF") # Set text color for contrast
        )
        # Font size button
        self.show_font_size_button = toga.Button(
           "Size",
           on_press=self.toggle_font_size_visibility,
           style=Pack(width=40) # Fixed width
        )
        nav_button_box.add(self.show_url_input_button)
        nav_button_box.add(self.show_font_size_button) # Add size button
        nav_button_box.add(spacer2)
        nav_button_box.add(self.next_button)

        # --- New URL Input Elements ---
        self.url_input = toga.TextInput(placeholder="Enter URL here...", style=Pack(flex=1, padding_right=5))
        self.confirm_load_button = toga.Button("Load", on_press=self.confirm_load_url, style=Pack(width=60))
        # Use display='none' to hide and reclaim space
        self.url_input_box = toga.Box(style=Pack(direction=ROW, padding=5))
        self.url_input_box.add(self.url_input)
        self.url_input_box.add(self.confirm_load_button)

        # --- Font Size Slider Box (initially hidden) ---
        self.current_font_size = 2.0 # Default size, might be overwritten by load_config

        self.font_size_slider = toga.Slider(
            range=(1.0, 4.0), # e.g., 1em to 4em
            # Value will be set after load_config
            on_change=self.handle_font_size_change,
            style=Pack(flex=1)
        )
        # Optional: Label to show current size
        self.font_size_label = toga.Label(f"{self.current_font_size:.1f}em", style=Pack(width=50, padding_left=5))

        self.font_size_box = toga.Box(style=Pack(direction=ROW, padding=5)) # Don't set display here
        self.font_size_box.add(self.font_size_slider)
        self.font_size_box.add(self.font_size_label)

        # Store nav_button_box for theming
        self.nav_button_box = nav_button_box

        # --- Assemble the main layout ---
        self.main_box.add(self.webview) # Add WebView here
        # Don't add url_input_box here initially
        # Don't add font_size_box here initially
        self.main_box.add(self.nav_button_box) # Add the navigation button container

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.main_box

        # Update slider value *after* loading config
        self.font_size_slider.value = self.current_font_size
        self.font_size_label.text = f"{self.current_font_size:.1f}em"

        # Apply initial theme to visible containers
        self._apply_theme_to_containers()

        # --- Auto-load bookmarked URL or default test URL if available ---
        initial_url = None
        if self.bookmarked_url:
            initial_url = self.bookmarked_url
            print(f"--- Found bookmarked URL: {initial_url} ---")
        elif DEFAULT_TEST_URL:
            initial_url = DEFAULT_TEST_URL
            print(f"--- No bookmark, using default test URL: {initial_url} ---")
        else:
            print("--- No bookmark or default URL found, not auto-loading --- ")

        if initial_url:
            print(f"--- Scheduling background load for: {initial_url} ---")
            # Store the URL to be loaded by the on_running handler
            self.initial_url_to_load = initial_url
        else:
            self.initial_url_to_load = None # Ensure it's defined

        print("--- Content set, attempting to show window ---")
        self.main_window.show()
        print("--- main_window.show() called ---")

    async def on_running(self):
        """Called by Toga after startup, once the event loop is running."""
        print("--- on_running triggered ---")
        if self.initial_url_to_load:
            print(f"--- Loading initial URL via on_running: {self.initial_url_to_load} ---")
            self.load_url_and_update_ui(self.initial_url_to_load)
        else:
            print("--- No initial URL to load in on_running ---")

    def format_html_content(self, data, theme='dark', font_size=2.0):
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
            text_color=text_color,
            font_size=font_size
        )

    def update_ui_with_content(self, data):
        """Updates the WebView and navigation buttons."""
        self.last_scraped_data = data # Store data for theme toggle
        self.next_page_url = data.get("next_page_url")
        self.previous_page_url = data.get("previous_page_url")
        # Update current URL *only* if different from what was requested
        # Prevents issues if redirects happened, but keeps user's input if direct load
        requested_url = data.get("_base_url")
        if requested_url and self.current_url != requested_url:
            self.current_url = requested_url
        # If self.current_url wasn't set yet (first load), set it.
        elif not self.current_url:
            self.current_url = requested_url

        self.main_window.title = data.get("title", self.formal_name) # Update window title
        
        # Update webview via the style helper
        self._update_webview_style()

        # Update button states
        self.next_button.enabled = bool(self.next_page_url)
        self.previous_button.enabled = bool(self.previous_page_url)

        # Hide the URL input box after successful load
        if self.url_input_box.parent: # If it's currently shown
            self.main_box.remove(self.url_input_box)

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
            # Ensure URL input is visible on error
            if not self.url_input_box.parent: # If it's not currently shown
                self.main_box.insert(1, self.url_input_box)
                # Always set dark background when showing
                self.url_input_box.style.background_color = "#121212"

            if hasattr(self, 'main_window') and self.main_window.visible:
                self.main_window.dialog(toga.ErrorDialog("Scraping Error", str(e)))
            self.main_window.title = self.formal_name
        except Exception as e:
            # Ensure URL input is visible on error
            if not self.url_input_box.parent: # If it's not currently shown
                self.main_box.insert(1, self.url_input_box)
                # Always set dark background when showing
                self.url_input_box.style.background_color = "#121212"

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
        
        # Apply theme to container backgrounds
        self._apply_theme_to_containers()

        # Save the new preference
        self.save_config()

    def _apply_theme_to_containers(self):
        """Applies the current theme's background color to relevant container boxes."""
        bg_color = "#121212" if self.current_theme == 'dark' else "#FFFFFF"
        text_color = "#FFFFFF" if self.current_theme == 'dark' else "#000000"
        try:
            # Check if boxes exist before styling (might be called early)
            if hasattr(self, 'main_box'):
                self.main_box.style.background_color = bg_color
            # url_input_box should always stay dark, styled when added
            if hasattr(self, 'nav_button_box'):
                self.nav_button_box.style.background_color = bg_color
            logging.debug(f"Applied background color {bg_color} to containers.")
        except Exception as e:
            logging.warning(f"Could not apply theme background: {e}")

    def confirm_load_url(self, widget):
        """Handler for the 'Load' button next to the URL input."""
        # This is called by the text button *inside* the url_input_box
        url = self.url_input.value.strip()
        print(f"--- Loading URL from input: {url} ---")
        if url:
            self.load_url_and_update_ui(url)
            # Hiding is now done within update_ui_with_content on success
        else:
            # Maybe show an info dialog if the input is empty?
            print("--- URL input is empty, doing nothing ---")
            # Example: await self.main_window.dialog(toga.InfoDialog("Input Needed", "Please enter a URL."))
            # Requires making this method async and handling potential errors

    def toggle_url_input_visibility(self, widget):
        """Toggles the visibility of the URL input box."""
        print("--- Toggling URL input visibility ---")
        # Toggle by adding/removing the box from the main layout
        if self.url_input_box.parent: # If it has a parent, it's visible
            print("--- Hiding URL input box ---")
            self.main_box.remove(self.url_input_box)
        else:
            print("--- Showing URL input box ---")
            # Insert between webview (index 0) and nav_button_box (index 1 after insert)
            self.main_box.insert(1, self.url_input_box)
            # Apply theme background when showing
            # Always set dark background when showing
            self.url_input_box.style.background_color = "#121212"
            # Don't focus automatically

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

    def toggle_font_size_visibility(self, widget):
        """Toggles the visibility of the font size slider box."""
        print("--- Toggling font size visibility ---")
        # Ensure only one control box is visible at a time (optional, but good UX)
        if self.url_input_box.parent:
            self.main_box.remove(self.url_input_box)

        if self.font_size_box.parent: # If it's visible, hide it
            print("--- Hiding font size box ---")
            self.main_box.remove(self.font_size_box)
        else: # If it's hidden, show it
            print("--- Showing font size box ---")
            # Insert between webview (index 0) and nav_button_box (index 1 after insert)
            self.main_box.insert(1, self.font_size_box)
            # Always set dark background when showing
            self.font_size_box.style.background_color = "#121212"
            # Update slider in case config loaded a different value or it wasn't updated yet
            self.font_size_slider.value = self.current_font_size
            self.font_size_label.text = f"{self.current_font_size:.1f}em"

    def handle_font_size_change(self, slider):
        """Handles changes from the font size slider."""
        new_size = slider.value
        # Optional: Check if size actually changed to avoid redundant updates
        if abs(new_size - self.current_font_size) > 0.05: # Check with tolerance
            self.current_font_size = new_size
            self.font_size_label.text = f"{self.current_font_size:.1f}em"
            print(f"--- Font size changed to: {self.current_font_size:.1f}em ---")
            self._update_webview_style() # Update the webview immediately
            self.save_config() # Save the new preference

    def _update_webview_style(self):
        """Helper to re-format and update WebView content with current style."""
        if self.last_scraped_data and self.current_url:
            print(f"--- Updating WebView style: theme={self.current_theme}, size={self.current_font_size:.1f}em ---")
            html_content = self.format_html_content(
                self.last_scraped_data,
                theme=self.current_theme,
                font_size=self.current_font_size
            )
            # Use the stored URL as the base for set_content
            base_url_for_webview = self.last_scraped_data.get('_base_url', self.current_url)
            self.webview.set_content(base_url_for_webview, html_content)
        else:
            logging.debug("_update_webview_style called but no content loaded.")

def main():
    print("--- main() called ---")
    # Provide formal_name and app_id explicitly
    app = HelloReader(
        formal_name="Hello Reader",
        app_id="me.dliangthinks.helloreader" # Use correct reverse domain notation
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