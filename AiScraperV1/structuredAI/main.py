import logging
import os
import sys
import csv
import re
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from langchain_google_genai import ChatGoogleGenerativeAI
from datetime import datetime

from agent_runner import run_fsm_agent
from tool_manager import ToolManager
from tools import CustomClickTool

CustomClickTool.model_rebuild()

load_dotenv()
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- LLM Setup ---
try:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.1,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )
except Exception as e:
    logger.error(f"Failed to initialize Google Gemini LLM: {e}")
    sys.exit(1)


# --- Verification Results Structure ---
class VerificationResults:
    def __init__(self):
        self.url = ""
        self.privacy_policy_found = False
        self.tos_found = False
        self.dmca_found = False
        self.disclaimer_found = False
        self.form_filled = False
        self.raw_output_summary = "No summary provided."
        self.agent_thoughts = "No detailed thoughts recorded."

    def to_dict(self):
        return {
            "url": self.url,
            "privacy_policy_found": self.privacy_policy_found,
            "tos_found": self.tos_found,
            "dmca_found": self.dmca_found,
            "disclaimer_found": self.disclaimer_found,
            "form_filled": self.form_filled,
            "raw_output_summary": self.raw_output_summary,
            "agent_thoughts": self.agent_thoughts,
        }


def parse_agent_output_to_results(
    agent_output: str, agent_thoughts: str
) -> VerificationResults:
    """
    Parses the agent's final structured report into a VerificationResults object.
    """
    results = VerificationResults()
    results.raw_output_summary = agent_output
    results.agent_thoughts = agent_thoughts

    output_lower = agent_output.lower()

    # Look for the explicit "Found" or "Not Found"
    results.privacy_policy_found = "privacy policy: found" in output_lower
    results.tos_found = (
        "terms of service: found" in output_lower or "terms: found" in output_lower
    )
    results.dmca_found = (
        "do not sell: found" in output_lower
        or "dns: found" in output_lower
        or "dmca: found" in output_lower
    )
    results.disclaimer_found = "tcpa disclaimer: found" in output_lower

    # The form was "filled" if the agent had to navigate to find the TCPA
    if results.disclaimer_found and (
        results.privacy_policy_found or results.tos_found or results.dmca_found
    ):
        results.form_filled = True

    return results


# --- Main Execution Block ---
def main_run():
    input_csv_path = "input_urls.csv"
    output_csv_path = (
        f"verification_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

    urls_to_test = []
    try:
        with open(input_csv_path, mode="r", newline="", encoding="utf-8") as infile:
            reader = csv.DictReader(infile)
            if not reader.fieldnames or "URL" not in reader.fieldnames:
                raise ValueError(
                    f"Input CSV '{input_csv_path}' must have a 'URL' column."
                )
            urls_to_test = [row["URL"] for row in reader]
        if not urls_to_test:
            logger.warning(f"No URLs found in '{input_csv_path}'. Exiting.")
            return
    except FileNotFoundError:
        logger.error(f"Input CSV file not found: '{input_csv_path}'.")
        sys.exit(1)

    all_results = []

    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=False, timeout=60000)
            context = browser.new_context()

            for url in urls_to_test:
                logger.info(f"\n{'='*70}\nProcessing URL: {url}\n{'='*70}")
                page = None
                try:
                    page = context.new_page()
                    page.goto(url, timeout=60000)

                    tool_manager = ToolManager(browser, context, page)
                    for tool in tool_manager.tools:
                        if hasattr(tool, "manager"):
                            tool.manager = tool_manager

                    final_output_str, agent_thoughts_str = run_fsm_agent(
                        llm, tool_manager
                    )

                    if not isinstance(final_output_str, str):
                        final_output_str = str(final_output_str)

                    parsed_results = parse_agent_output_to_results(
                        final_output_str, agent_thoughts_str
                    )
                    parsed_results.url = url
                    all_results.append(parsed_results.to_dict())

                except Exception as e:
                    logger.error(f"Failed to process URL {url}: {e}", exc_info=True)
                    all_results.append(
                        {"url": url, "raw_output_summary": f"CRITICAL_FAILURE: {e}"}
                    )
                finally:
                    if page:
                        page.close()

        except Exception as e:
            logger.error(
                f"A critical error occurred during the browser session: {e}",
                exc_info=True,
            )
        finally:
            if browser:
                browser.close()
                logger.info("Browser closed.")

    if all_results:
        fieldnames = list(VerificationResults().to_dict().keys())
        try:
            with open(
                output_csv_path, mode="w", newline="", encoding="utf-8"
            ) as outfile:
                writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_results)
            logger.info(f"Verification results saved to '{output_csv_path}'.")
        except Exception as e:
            logger.error(f"Error writing output CSV: {e}", exc_info=True)
    else:
        logger.warning("No results were generated to write to CSV.")


if __name__ == "__main__":
    main_run()
