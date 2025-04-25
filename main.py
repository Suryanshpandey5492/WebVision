import asyncio
from typing import Any
from langchain_core.messages import HumanMessage
from playwright.async_api import async_playwright
from langgraph.errors import GraphRecursionError
import os, sys, uuid
from graph import VisionGraph
from constants import GRAPH_RECURSION_LIMIT
import time
from playwright.async_api import Error
from shared_state import get_response
project_root = os.environ["PROJECT_ROOT"]

BROWSER_TYPE = "chromium"  # Experiment with "chromium" or "firefox"
HEADLESS_MODE = True  # Use headless for faster execution

sys.path.append(f"{project_root}")

from logger import get_logger

logger = get_logger()

with open(f"{os.environ['PROJECT_ROOT']}/mark_page.js") as f:
    mark_page_script = f.read()
class WebVision:
    """
    WebVision class for managing Playwright sessions and executing tasks using a vision graph.

    Attributes:
        session_id (str): Unique session identifier.
        customer_id (str): Customer identifier.
        session_dao (Any): Session data access object.
        nonce (str): Unique identifier for the execution run.
        graph (VisionGraph): Compiled vision graph for processing tasks.
        answer (Any): The final answer obtained from executing the task.
    """
    
    def __init__(self, session_id: str, customer_id: str, session_dao: Any, push_update: Any):
        """
        Initializes the WebVision instance.

        Args:
            session_id (str): Unique session identifier.
            customer_id (str): Unique customer identifier.
            session_dao (Any): Data access object for managing session data.
            push_update (Any): Mechanism to push updates.
        """
        start_time = time.perf_counter()
        logger.debug("[INIT] Initializing WebVision")
        
        try:
            self.graph = VisionGraph().compile_graph()
            self.answer = None
            self.session_id = session_id
            self.nonce = uuid.uuid4().hex  # Unique identifier for this run
            self.session_dao = session_dao
            self.push_update = push_update
        except Exception as e:
            logger.error(f"[INIT] Error during initialization: {e}", exc_info=True)
            raise
        
        end_time = time.perf_counter()
        logger.debug(f"[INIT] WebVision initialized in {end_time - start_time:.4f} seconds")

    async def __run(self, task: str):
        """
        Executes the given task using the compiled vision graph.

        Args:
            task (str): The task description to be processed.
        """
        logger.debug(f"[TASK] Starting __run for task: {task}")
        task_start_time = time.perf_counter()
        
        inputs = {
            "task": [HumanMessage(content=task)],
            "page": self.page,
            "nonce": self.nonce,
            "session_dao": self.session_dao,
            "push_update": self.push_update,
            "steps": 1,
        }
        
        try:
            cur_state = None
            async for output in self.graph.with_config(
                {"run_name": "LLM with Tools", "recursion_limit": GRAPH_RECURSION_LIMIT}
            ).astream(inputs):
                step_time = time.perf_counter()
                for key, value in output.items():
                    truncated_value = str(value)[:500] + '...' if len(str(value)) > 500 else str(value)
                    logger.debug(f"[GRAPH] Output from node '{key}' (truncated): {truncated_value}")
                    cur_state = value
                logger.debug(f"[GRAPH] Step execution time: {time.perf_counter() - step_time:.4f} seconds")
            
            logger.debug("[GRAPH] Graph execution completed")
            self.answer = cur_state.get("answer")
            
        except GraphRecursionError:
            logger.error("[ERROR] Graph recursion depth reached, terminating execution")
            if cur_state:
                logger.error(f"[HISTORY] History till now: {cur_state.get('history')}")
            
            recursion_fix_time = time.perf_counter()
            cur_state = self.graph.run_step("answer_node")
            logger.debug(f"[RECOVERY] Recursion fix execution time: {time.perf_counter() - recursion_fix_time:.4f} seconds")
            
            self.answer = cur_state.get("answer")
            
        except Exception as e:
            logger.error(f"[ERROR] Unexpected error in agent graph: {e}", exc_info=True)
            self.answer = None
            
        task_end_time = time.perf_counter()
        logger.debug(f"[TASK] __run execution time: {task_end_time - task_start_time:.4f} seconds")

    async def run(self, task: str):
        """
        Starts a Playwright session and executes the specified task.

        Args:
            task (str): The task description to be executed.

        Returns:
            Any: The answer obtained from executing the task.
        """
        logger.debug("[SESSION] Starting Playwright session")
        session_start_time = time.perf_counter()
        
        try:
            async with async_playwright() as playwright:
                browser_start_time = time.perf_counter()
                
                # Ensure Playwright initializes correctly
                if not playwright:
                    raise RuntimeError("[PLAYWRIGHT] Failed to initialize Playwright.")

                # Launch browser with error handling
                try:
                    self.browser = await playwright.firefox.launch(headless=False)
                except Exception as e:
                    logger.error(f"[BROWSER] Failed to launch Firefox: {e}")
                    return None

                logger.debug(f"[BROWSER] Launch time: {time.perf_counter() - browser_start_time:.4f} seconds")

                self.page = await self.browser.new_page()

                # Inject script before navigation
                await self.page.add_init_script(mark_page_script)

                page_nav_start_time = time.perf_counter()
                await self.page.goto("https://duckduckgo.com/")
                # await self.page.goto("https://www.google.com")
                logger.debug(f"[NAVIGATION] Page navigation time: {time.perf_counter() - page_nav_start_time:.4f} seconds")

                # Execute the task
                self.answer = await self.__run(task)

        except Exception as e:
            logger.error(f"[SESSION] Error during Playwright execution: {e}", exc_info=True)
            self.answer = None

        finally:
            # Ensure browser cleanup
            if self.browser:
                try:
                    await self.browser.close()
                    logger.debug("[BROWSER] Successfully closed.")
                except Error as e:
                    logger.warning(f"[BROWSER] Browser already closed or connection lost: {e}")
                except Exception as close_error:
                    logger.warning(f"[BROWSER] Unexpected error while closing: {close_error}", exc_info=True)

            session_end_time = time.perf_counter()
            logger.debug(f"[SESSION] Total Playwright session time: {session_end_time - session_start_time:.4f} seconds")

        return self.answer



if __name__ == "__main__":
    logger.debug("[MAIN] Starting WebVision execution")
    main_start_time = time.perf_counter()
    
    web_vision = WebVision("1234", "123", lambda a: a, lambda b: b)
    result = asyncio.run(
        web_vision.run(
            "stock prize of apple inc."
    
        )
    )
    final_response=get_response()
    logger.debug(f"[MAIN] Result: {final_response}")
    logger.debug("[MAIN] Starting WebVision execution")
    main_end_time = time.perf_counter()
    logger.debug(f"[MAIN] Total execution time: {main_end_time - main_start_time:.4f} seconds")