import asyncio
import platform
import re
from playwright.async_api import Page
import os
import sys
import json
from threading import Thread
from typing import Dict,List, Any, Union
from constants import RECURSION_LIMIT
from pydantic import BaseModel, Field
from langgraph.prebuilt import ToolExecutor
from langchain.tools import StructuredTool
from playwright.async_api import async_playwright

sys.path.append(os.environ["PROJECT_ROOT"])
from state import AgentState, SystemMessage

from logger import get_logger

logging = get_logger()




async def navigate_url(state: AgentState, url: str):
    """
    Navigates to a given URL using Playwright.

    Args:
        state (AgentState): The current agent state.
        url (str): The target URL to navigate to.

    Returns:
        str: A confirmation message.
    """
    try:
        page: Page = state.get("page")
        if not page:
            logging.error("Page object is missing in state.")
            return "Error: Page object not found."

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"


        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        logging.info(f"Successfully navigated to {url}")
        # Call process_http_traffic function
        
        return f"Navigated to {url}"

    except Exception as e:
        logging.exception(f"Error navigating to {url}: {e}")
        return f"Error: Could not navigate to {url}"


class NavigateURL(BaseModel):
    """Model for navigating to a URL."""

    state: Any
    url: str

async def scroll(state: AgentState, direction: int, target: int | str):
    page = state["page"]
    scroll_amount = direction * 500 if target.upper() == "WINDOW" else direction * 400

    if target.upper() == "WINDOW":
        await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
    else:
        bbox = state["bboxes"][int(target)]
        await page.mouse.move(bbox["x"], bbox["y"])
        await page.mouse.wheel(0, scroll_amount)

    return f"Scrolled {direction} in {'window' if target.upper() == 'WINDOW' else 'element'}"


class Scroll(BaseModel):
    """Model for scrolling action."""
    
    state: Any
    direction: int
    target: Union[int, str]


async def wait(state: AgentState, *args):
    """
    Pauses execution for a predefined time.

    Args:
        state (AgentState): The current agent state.

    Returns:
        str: Confirmation message.
    """
    try:
        sleep_time = 2
        await asyncio.sleep(sleep_time)
        logging.info(f"Waited for {sleep_time}s.")
        return f"Waited for {sleep_time}s."

    except Exception as e:
        logging.exception("Error in wait function:", e)
        return "Error: Failed to execute wait."


async def go_back(state: AgentState, *args):
    """
    Navigates back to the previous page.

    Args:
        state (AgentState): The current agent state.

    Returns:
        str: Confirmation message with the new page URL.
    """
    try:
        page = state.get("page")
        if not page:
            logging.error("Page object is missing in state.")
            return "Error: Page object not found."

        await page.go_back()
        logging.info(f"Navigated back to {page.url}")
        return f"Navigated back a page to {page.url}"

    except Exception as e:
        logging.exception("Error in go_back function:", e)
        return "Error: Failed to navigate back."


class GoBack(BaseModel):
    """Model for navigating back a page."""
    
    state: Any



class MarkTaskComplete(BaseModel):
    """Model for marking a task as complete."""
    
    state: Any


async def press_enter(state: AgentState, *args):
    """
    Simulates pressing the Enter key.

    Args:
        state (AgentState): The current agent state.

    Returns:
        str: Confirmation message.
    """
    try:
        page: Page = state.get("page")
        if not page:
            logging.error("Page object is missing in state.")
            return "Error: Page object not found."

        await page.keyboard.press("Enter")
        logging.info("Pressed Enter key.")
        return "Pressed Enter key."

    except Exception as e:
        logging.exception("Error in press_enter function:", e)
        return "Error: Failed to press Enter."


class PressEnter(BaseModel):
    """Press the Enter key on the page."""
    state: Any

    
async def click(state: Dict[str, Any], bbox_id: int):
    """
    Simulates a mouse click at the given bounding box ID and records HTTP requests and responses.

    Args:
        state (dict): The current agent state.
        bbox_id (int): The bounding box index to click.

    Returns:
        str: Confirmation message or error.
    """
    try:
        page = state.get("page")
        if not page:
            logging.error("Page object is missing in state.")
            return "Error: Page object not found."

        bboxes = state.get("bboxes", [])
        if not isinstance(bboxes, list) or bbox_id >= len(bboxes):
            logging.error(f"No bounding box found for ID {bbox_id}.")
            return f"Error: No bounding box found for ID {bbox_id}."

        bbox = bboxes[bbox_id]  # Access by index
        x, y = bbox["x"], bbox["y"]



        try:
            await asyncio.wait_for(page.mouse.click(x, y), timeout=2)
        except asyncio.TimeoutError:
            logging.warning("Click operation timed out after 2 seconds.")
            return f"Error: Click operation at {x}, {y} timed out after 2 seconds."

        logging.info(f"Clicked at coordinates {x}, {y} (bbox_id={bbox_id}).")
        return f"Clicked on {bbox}."

    except Exception as e:
        logging.error(f"Error in click function: {e}", exc_info=True)
        return f"Error: Failed to click on bbox {bbox_id}."

class Click(BaseModel):
    """Model for clicking a bounding box."""
    bbox_id: int = Field(description="The bounding box to click.")
    state: Any


async def type_text(state: Dict[str, Any], bbox_id: int, text: str):
    """
    Simulates typing text into a specified bounding box.

    Args:
        state (Dict[str, Any]): The current agent state.
        bbox_id (int): The bounding box index where text should be typed.
        text (str): The text to type.

    Returns:
        str: Confirmation message or error.
    """
    try:
        logging.debug(f"Typing text: '{text}' at bbox {bbox_id}")

        # Validate bounding boxes
        bboxes = state.get("bboxes", [])
        if not bboxes:
            logging.error("No bounding boxes found in state.")
            return f"Failed to type '{text}' - No bounding boxes available."

        if not (0 <= bbox_id < len(bboxes)):
            logging.error(f"Invalid bbox_id: {bbox_id}. Available indices: {len(bboxes) - 1}")
            return f"Failed to type '{text}' - bbox_id {bbox_id} out of range."

        # Retrieve page and bounding box coordinates
        page = state.get("page")
        bbox = bboxes[bbox_id]
        x, y = bbox["x"], bbox["y"]

        async def perform_typing():
            try:
                # Click on the text field
                await page.mouse.click(x, y)

                # Select all text and delete
                select_all = "Meta+A" if platform.system() == "Darwin" else "Control+A"
                await page.keyboard.press(select_all)
                await page.keyboard.press("Backspace")

                # Type text
                await page.keyboard.type(text)

                logging.info(f"Successfully typed '{text}' at bbox {bbox_id}.")
                return f"Typed '{text}' at {bbox} and submitted."
            except asyncio.TimeoutError:
                logging.error("Typing operation timed out.")
                return f"Failed to type '{text}' due to timeout."

        return await asyncio.wait_for(perform_typing(), timeout=8)

    except asyncio.TimeoutError:
        logging.error(f"Typing operation exceeded 30 seconds timeout.")
        return f"Failed to type '{text}' due to a timeout error."
    except Exception as e:
        logging.error(f"Error occurred while typing text: {e}", exc_info=True)
        return f"Failed to type '{text}' due to an error."





class TypeText(BaseModel):
    """Model for typing text into a bounding box."""
    state: Any
    bbox_id: int
    text: str


class RecordHttpTraffic(BaseModel):
    """Model for recording HTTP traffic."""
    url: str
    state: Any


async def mark_task_complete(state: AgentState):
    """
    Marks a task as complete by setting the 'steps' key in state to 25.
    Should be called only when the complete output of the task is retrieved.
    
    Args:
        state (AgentState): The current agent state.
    
    Returns:
        str: Confirmation message.
    """
    try:
        # Set steps key to 25 to indicate task completion
        state["steps"] = RECURSION_LIMIT
        
        logging.info("Task marked as complete. Steps set to %d.", RECURSION_LIMIT)
        
        return "Task marked as complete."
    except Exception as e:
        logging.exception("Error in mark_task_complete function:", e)
        return "Error: Failed to mark task as complete."


class LogVisitedWebsiteInput(BaseModel):
    state: Any
    url: str
    summary: str  # Summary or key info extracted from the site
    title: str = ""
    timestamp: str = ""  # Optional: could be auto-generated if needed

async def log_visited_website(state: AgentState, url: str, summary: str, title: str = "", timestamp: str = "") -> str:
    try:
        existing_log = state.get("VISITED_WEBSITES") or "[]"
        try:
            visited_websites = json.loads(existing_log)
        except json.JSONDecodeError:
            visited_websites = []

        new_entry = {
            "url": url,
            "title": title,
            "summary": summary,
            "timestamp": timestamp
        }

        visited_websites.append(new_entry)

        state["VISITED_WEBSITES"] = json.dumps(visited_websites, indent=2)
        logging.info(f"Website logged: {url}")
        return f"Logged website: {url}"

    except Exception as e:
        logging.exception("Error logging visited website:", exc_info=e)
        return "Error: Failed to log visited website."
    
def construct_structured_tools(func_args_pairs: List):
    """
    Constructs structured tools from function-argument pairs.

    Args:
        func_args_pairs (List): List of tuples containing function, schema, name, and description.

    Returns:
        Tuple: List of structured tools and a ToolExecutor instance.
    """
    final_tools = []
    for func, schema, name, description in func_args_pairs:
        tool = StructuredTool.from_function(
            func=func,
            name=name,
            description=description,
            args_schema=schema,
            return_direct=False,
        )
        final_tools.append(tool)

    tool_executor = ToolExecutor(final_tools)

    logging.info("Structured tools successfully created.")
    return final_tools, tool_executor



# combined_tools = [click_tool, type_tool]
combined_tools, tool_executor = construct_structured_tools(
    [
        [click, Click, "Click", "Use this to click on an element"],
        [type_text, TypeText, "TypeText", "Type into an element on the page"],
        [press_enter, PressEnter, "PressEnter", "Press enter on the page"],
        [go_back, GoBack, "GoBack", "Go back to the previous page"],
        [
            scroll,
            Scroll,
            "Scroll",
            "Scroll on the page. Direction=1 is up and direction=2 is down. For scroll\
                                                                        on the entire page set target as WINDOW, for within element specify bbox",
        ],
        [
            navigate_url,
            NavigateURL,
            "NavigateURL",
            "Navigate directly to a URL on the web",
        ],
        [
            mark_task_complete,
            MarkTaskComplete,
            "MarkTaskComplete",
            "Mark the task as complete by setting steps to 25. Call this ONLY when the complete output of the task has been successfully retrieved",
        ],
        [
            log_visited_website,
            LogVisitedWebsiteInput,
            "LogVisitedWebsiteInput",
            "Log details about a visited website including its URL, title, summary of the content extracted, and timestamp. \
            This helps maintain a structured record in the state under VISITED_WEBSITES."
        ],
    ]
)


other_tools, other_tool_executor = construct_structured_tools(
    [
        [
            mark_task_complete,
            MarkTaskComplete,
            "MarkTaskComplete",
            "Mark the task as complete by setting steps to 25. Call this ONLY when the complete output of the task has been successfully retrieved",
        ],
        [
            log_visited_website,
            LogVisitedWebsiteInput,
            "LogVisitedWebsiteInput",
            "Log details about a visited website including its URL, title, summary of the content extracted, and timestamp. \
            This helps maintain a structured record in the state under VISITED_WEBSITES."
        ],
    ]
)