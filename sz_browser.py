"""
SubZero Browser Automation (sz_browser.py)
═══════════════════════════════════════════
Selenium + Microsoft Edge WebDriver wrapper.
Lazy-initialized — browser only starts on first use.
"""

import os
import tempfile
from pathlib import Path
from datetime import datetime

try:
    from selenium import webdriver
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException, NoSuchElementException,
        WebDriverException, ElementNotInteractableException,
    )
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False

SCREENSHOTS_DIR = Path.home() / ".subzero" / "screenshots"


class SeleniumBrowser:
    """Persistent browser session using Edge WebDriver."""

    def __init__(self, headless: bool = False):
        if not HAS_SELENIUM:
            raise RuntimeError(
                "Selenium not installed. Run: pip install selenium"
            )
        self.headless = headless
        self._driver = None

    def _ensure_driver(self):
        """Lazy-init: create driver on first use."""
        if self._driver is not None:
            return
        options = EdgeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1280,900")
        # Suppress logging noise
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_argument("--log-level=3")

        try:
            # Try using Edge with auto-managed driver
            self._driver = webdriver.Edge(options=options)
        except WebDriverException:
            # Fallback: try Chrome if Edge fails
            try:
                from selenium.webdriver.chrome.options import Options as ChromeOptions
                chrome_opts = ChromeOptions()
                if self.headless:
                    chrome_opts.add_argument("--headless=new")
                chrome_opts.add_argument("--disable-gpu")
                chrome_opts.add_argument("--no-sandbox")
                chrome_opts.add_argument("--window-size=1280,900")
                chrome_opts.add_experimental_option("excludeSwitches", ["enable-logging"])
                self._driver = webdriver.Chrome(options=chrome_opts)
            except Exception as e:
                raise RuntimeError(
                    f"Could not start browser. Make sure Edge or Chrome is installed.\n"
                    f"Error: {e}"
                )

    def open(self, url: str):
        """Navigate to a URL."""
        self._ensure_driver()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self._driver.get(url)

    def title(self) -> str:
        """Get current page title."""
        if self._driver:
            return self._driver.title
        return ""

    def current_url(self) -> str:
        """Get current URL."""
        if self._driver:
            return self._driver.current_url
        return ""

    def click(self, selector: str):
        """Click an element by CSS selector."""
        self._ensure_driver()
        el = self._find(selector)
        el.click()

    def type_text(self, selector: str, text: str, clear: bool = True):
        """Type text into an input element."""
        self._ensure_driver()
        el = self._find(selector)
        if clear:
            el.clear()
        el.send_keys(text)

    def submit(self, selector: str):
        """Submit a form by pressing Enter on an element."""
        self._ensure_driver()
        el = self._find(selector)
        el.send_keys(Keys.RETURN)

    def read(self, selector: str = "") -> str:
        """Read text content from page or specific element."""
        self._ensure_driver()
        if selector:
            try:
                el = self._find(selector)
                return el.text
            except Exception:
                return f"Element not found: {selector}"
        else:
            return self._driver.find_element(By.TAG_NAME, "body").text

    def screenshot(self) -> str:
        """Take a screenshot and return the file path."""
        self._ensure_driver()
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = SCREENSHOTS_DIR / f"screenshot_{ts}.png"
        self._driver.save_screenshot(str(path))
        return str(path)

    def wait_for(self, selector: str, timeout: int = 10):
        """Wait for an element to be present."""
        self._ensure_driver()
        by, value = self._parse_selector(selector)
        WebDriverWait(self._driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    def execute_js(self, script: str) -> any:
        """Execute JavaScript in the browser."""
        self._ensure_driver()
        return self._driver.execute_script(script)

    def get_page_source(self) -> str:
        """Get the full HTML source of the current page."""
        if self._driver:
            return self._driver.page_source
        return ""

    def close(self):
        """Close the browser."""
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def _find(self, selector: str):
        """Find element using CSS selector or smart detection."""
        by, value = self._parse_selector(selector)
        try:
            return self._driver.find_element(by, value)
        except NoSuchElementException:
            raise RuntimeError(f"Element not found: {selector}")

    def _parse_selector(self, selector: str):
        """Parse selector string to (By, value) tuple.
        
        Supports:
          - CSS selectors (default): "#id", ".class", "tag", etc.
          - XPath: starts with "/" or "//"
          - Text: starts with "text=" for link text
          - Name: starts with "name="
          - ID shortcut: starts with "#"
        """
        selector = selector.strip()
        if selector.startswith("//") or selector.startswith("/"):
            return By.XPATH, selector
        elif selector.startswith("text="):
            return By.PARTIAL_LINK_TEXT, selector[5:]
        elif selector.startswith("name="):
            return By.NAME, selector[5:]
        else:
            return By.CSS_SELECTOR, selector

    def __del__(self):
        self.close()
