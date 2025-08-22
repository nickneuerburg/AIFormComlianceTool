import logging
from playwright.sync_api import Page, BrowserContext

# Import custom tools
from tools import (
    FindInteractiveElementsTool,
    CustomClickTool,
    ScreenshotElementTool,
    CustomFillTool,
    ExtractFullPageTextTool,
)

logger = logging.getLogger(__name__)


class ToolManager:

    # A class to create, hold, and manage the state of agent tools.

    def __init__(self, browser, context: BrowserContext, page: Page):
        self.browser = browser
        self.context = context
        self.page = page
        self.tools = self._create_tools()
        logger.info(
            f"ToolManager initialized with tools: {[t.name for t in self.tools]}"
        )

    def _create_tools(self):
        scanner_tool = FindInteractiveElementsTool(page=self.page)
        click_tool = CustomClickTool(page=self.page, context=self.context, manager=self)
        screenshot_tool = ScreenshotElementTool(page=self.page)
        fill_tool = CustomFillTool(page=self.page, context=self.context)
        extract_text_tool = ExtractFullPageTextTool(page=self.page)

        # Return a list of all custom tools.
        # If you need any tools from PlayWrightBrowserToolkit, merge them here.
        return [click_tool, fill_tool, scanner_tool, screenshot_tool, extract_text_tool]

    def update_page_context(self, new_page: Page):
        logger.info("ToolManager updating page context for all tools...")
        self.page = new_page

        for tool in self.tools:
            # Use a type guard (hasattr) to safely update the page attribute
            # only on the tools that actually have it.
            if hasattr(tool, "page"):
                tool.page = self.page  # type: ignore[attr-defined]
            # If a tool needs context, update it too
            if hasattr(tool, "context"):
                tool.context = self.context  # type: ignore[attr-defined]

        logger.info("All tools have been updated with the new page.")
