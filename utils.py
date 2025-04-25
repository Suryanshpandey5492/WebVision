import base64
import asyncio
import os, sys
import json
from langchain_core.runnables import chain as chain_decorator
from tools import tool_executor
from langgraph.prebuilt import ToolInvocation
from langchain_core.messages import ToolMessage




from logger import get_logger


logger = get_logger()

current_dir = os.getcwd()

# Build the path to the mark_page.js script
script_path = os.path.join(current_dir, "mark_page.js")

# Open and read the script
with open(script_path) as f:
    mark_page_script = f.read()

screenshot_list = []

async def mark_page(page) -> dict:
    """
    Injects a script into the page, executes `markPage()` to retrieve bounding boxes, 
    takes a screenshot and ensures cleanup by executing `unmarkPage()`.

    Args:
        page (Page): The Playwright page object to interact with.
        session_manager (SessionManager): Manages session ID.

    Returns:
        dict: A dictionary containing:
            - "img": Base64-encoded screenshot (or None on failure).
            - "bboxes": List of bounding boxes returned by `markPage()`.
    """

    # session_id = SID
    # logger.debug(f"Session ID: {session_id}")
    
    try:
        logger.debug("Injecting mark_page_script as an init script...")
        await page.add_init_script(mark_page_script)

        logger.debug("Waiting for page to load...")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_load_state("load")

        logger.debug("Executing mark_page_script...")
        await page.evaluate(f"""(function() {{ {mark_page_script} }})()""")

        logger.debug("Script loaded successfully.")
    except asyncio.TimeoutError:
        logger.error("Script evaluation timed out.")
    except Exception as e:
        logger.error(f"Error executing mark_page_script: {e}", exc_info=True)

    # Attempt to execute `markPage()` multiple times in case of failure
    bboxes = []
    for attempt in range(10):
        try:
            if page.is_closed():
                logger.error("Page is closed. Stopping markPage execution.")
                return {"img": None, "bboxes": []}

            logger.debug(f"Attempt {attempt+1}: Evaluating 'markPage()'...")
            bboxes = await page.evaluate("markPage()")
            if bboxes:
                break  # Success, exit loop
        except Exception as e:
            logger.error(f"Error executing 'markPage()' (attempt {attempt+1}): {e}", exc_info=True)
            await asyncio.sleep(0.5)  # Small delay before retrying
    else:
        logger.debug("Failed to execute 'markPage()' after 10 attempts.")

    # Attempt to take a screenshot
    logger.debug("Taking screenshot...")
    encoded_screenshot = None
    
    try:
        screenshot = await page.screenshot()
        encoded_screenshot = base64.b64encode(screenshot).decode()
        logger.info(f"Base64-encoded screenshot length: {len(encoded_screenshot)} characters")
        

    
    except Exception as e:
        logger.error(f"Error taking screenshot or uploading to S3: {e}", exc_info=True)
        screenshot = None

    # Attempt to execute `unmarkPage()` for cleanup
    logger.debug("Executing 'unmarkPage()' to clean up marks...")
    if not page.is_closed():
        for attempt in range(3):
            try:
                await page.wait_for_load_state("load")
                await page.evaluate('window.unmarkPage && window.unmarkPage();')
                logger.debug("Successfully executed 'unmarkPage()'.")
                break
            except Exception as e:
                logger.error(f"Error executing 'unmarkPage()' (attempt {attempt+1}): {e}")
                await asyncio.sleep(0.5)
    
    return {
        "img": encoded_screenshot,
        "bboxes": bboxes,
    }

async def process_tools(response, state):
    """
    Processes tool calls from the response and updates the state accordingly.
    
    Args:
        response (Any): The response object containing tool calls.
        state (Dict[str, Any]): The current state to be updated.

    Returns:
        Dict[str, Any]: The updated state after processing tool calls.
    """
    try:
        tool_calls = response.additional_kwargs.get("tool_calls", None)
        if not tool_calls:
            logger.debug(f"No tool calls found in response: {response}")
            return state

        for tool_call in tool_calls:
            try:
                raw_args = tool_call["function"]["arguments"]
                logger.debug(f"Received arguments for {tool_call['function']['name']}: {raw_args}")

                if isinstance(raw_args, str) and raw_args.strip().startswith("{"):
                    args = json.loads(raw_args)
                else:
                    logger.error(f"Invalid JSON format: {raw_args}")
                    continue  

                args["state"] = state

                if tool_call["function"]["name"] == "Response":
                    state["end"] = True
                    state["answer"] = args.get("final_answer")
                    state["errors"] = args.get("errors")
                    break  

                logger.debug(f"Executing {tool_call['function']['name']}")
                action = ToolInvocation(
                    tool=tool_call["function"]["name"],
                    tool_input=args,
                    id=tool_call["id"],
                )

                tool_response = await tool_executor.invoke(action)

                function_message = ToolMessage(
                    content=str(tool_response),
                    name=action.tool,
                    tool_call_id=tool_call["id"],
                )

                logger.debug(f"Execution results for {tool_call['function']['name']}: {function_message}")

            except json.JSONDecodeError as json_error:
                logger.error(f"Failed to decode JSON arguments: {json_error}", exc_info=True)
            except Exception as e:
                logger.error(f"Error processing tool call {tool_call['function']['name']}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Unexpected error while processing tools: {e}", exc_info=True)
    
    return state