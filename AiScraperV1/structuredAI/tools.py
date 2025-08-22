import logging
import json
from playwright.sync_api import Page, BrowserContext
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import os

logger = logging.getLogger(__name__)


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tool_manager import ToolManager


class ScreenshotElementTool(BaseTool):
    """A tool that takes a screenshot of a specific element."""

    name: str = "screenshot_element"
    description: str = (
        "Finds an element using a CSS selector and saves a screenshot of just that element to a file."
    )
    page: Page

    class ScreenshotArgs(BaseModel):
        selector: str = Field(
            description="A valid CSS selector for the element to screenshot."
        )
        filename: str = Field(
            description="The filename for the output image (e.g., 'privacy_policy.png')."
        )

    args_schema = ScreenshotArgs

    def _run(self, selector: str, filename: str):
        try:
            # Ensure the output directory exists
            output_dir = "screenshots"
            os.makedirs(output_dir, exist_ok=True)

            element = self.page.locator(selector).first
            path = os.path.join(output_dir, filename)

            element.screenshot(path=path)

            logger.info(f"Saved screenshot of element '{selector}' to '{path}'")
            return f"Successfully saved screenshot to '{path}'."
        except Exception as e:
            return f"Error: Could not screenshot element with selector '{selector}'. Reason: {e}"


class FindInteractiveElementsTool(BaseTool):
    """A tool that finds all interactive elements on the current page."""

    name: str = "find_interactive_elements"
    description: str = (
        "Returns a JSON list of all interactive elements (buttons, links, inputs, selects) "
        "on the current page, including their outer_html for selector creation."
    )
    page: Page

    def _run(self):
        try:
            elements = self.page.query_selector_all(
                "a, button, input:not([type=hidden]), select, textarea, [role='button']"
            )
            element_list = [
                {"outer_html": el.evaluate("element => element.outerHTML")}
                for el in elements
            ]
            return json.dumps(element_list, indent=2)
        except Exception as e:
            return f"Error finding elements: {e}"


class ExtractFullPageTextTool(BaseTool):
    """A tool that extracts the entire plain text content from the current page."""

    name: str = "extract_full_page_text"
    description: str = (
        "Extracts and returns the entire visible plain text content of the current web page. "
        "Useful for searching for specific text patterns or disclaimers."
    )
    page: Page

    def _run(self):
        try:
            # Evaluate JavaScript to get the innerText of the body
            full_text = self.page.evaluate("document.body.innerText")
            return full_text
        except Exception as e:
            return f"Error extracting full page text: {e}"


class CustomFillTool(BaseTool):
    """A tool that fills an input field with the given value."""

    name: str = "fill"
    description: str = "Fills an input field with the given value using a CSS selector."
    page: Page
    context: (
        BrowserContext  # Keep context here for consistency if needed in other methods
    )

    class FillArgs(BaseModel):
        selector: str = Field(
            description="A valid CSS selector for the input field to fill."
        )
        value: str = Field(description="The value to fill into the input field.")

    args_schema = FillArgs

    def _run(self, selector: str, value: str):
        try:
            self.page.fill(selector, value)
            return f"Successfully filled element with selector '{selector}' with value '{value}'."
        except Exception as e:
            return f"Error filling element with selector '{selector}': {e}"


class CustomClickTool(BaseTool):
    """A tool that clicks an element and signals the ToolManager if a new tab opens."""

    name: str = "click"
    description: str = "Clicks on an element with the given CSS selector."
    page: Page
    context: BrowserContext
    manager: "ToolManager"  # Reference to the manager to update all tools

    class ClickArgs(BaseModel):
        selector: str = Field(
            description="A valid CSS selector for the element to click."
        )

    args_schema = ClickArgs

    def _run(self, selector: str):
        try:
            current_page_count = len(self.context.pages)
            # Use page.click for robustness, adding a timeout
            self.page.click(selector, timeout=10000)
            self.page.wait_for_timeout(2500)  # Give page some time to react/load

            # Check for new tabs
            if len(self.context.pages) > current_page_count:
                logger.info("New tab detected! Updating manager...")
                # The new page is typically the last one created
                new_page = self.context.pages[-1]
                new_page.bring_to_front()  # Bring it to foreground if headless=False
                # Let the manager handle updating all tools
                self.manager.update_page_context(new_page)
                return "Successfully clicked element and switched to the new tab."
            else:
                return f"Successfully clicked element with selector: '{selector}'."
        except Exception as e:
            return f"Error clicking element with selector '{selector}': {e}"
