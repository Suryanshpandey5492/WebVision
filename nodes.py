from langchain_openai import AzureChatOpenAI
from pydantic import BaseModel, Field
from tools import combined_tools, other_tools
from langchain_core.messages import HumanMessage, SystemMessage
import asyncio
import os
import sys
from dotenv import load_dotenv
import datetime
from shared_state import set_response

from state import AgentState
from utils import mark_page, process_tools
from prompt import chat_prompt_template, answer_prompt_template, tools_prompt_template, insights_template
from logger import get_logger

# Initialize logger
logger = get_logger()

# Set up environment paths
sys.path.append(os.environ["PROJECT_ROOT"])
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")

# Initialize Azure OpenAI LLM instance
llm = AzureChatOpenAI(
    azure_deployment="pinewheel-4o",
    api_version="2024-05-01-preview",
    temperature=0,
    max_retries=2,
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

from typing import Optional
from pydantic import BaseModel, Field

class Response(BaseModel):
    """
    Response model for the final output.

    Attributes:
        final_answer (str): The final response generated.
        errors (Optional[str]): Any errors encountered during execution.
    """
    final_answer: str = Field(
        description="Provide a comprehensive and clear response to the original query, explaining any steps taken and findings discovered"
    )
    errors: Optional[str] = Field(
        default=None,
        description="Detail any errors encountered during execution, including potential causes and workarounds if applicable"
    )


# Append Response tool to the tools list
combined_tools.append(Response)
other_tools.append(Response)
# Bind tools to the model
model = chat_prompt_template | llm.bind_tools(combined_tools)

# Define execution chain
chain =  chat_prompt_template | llm.bind_tools(combined_tools)

tool_model = tools_prompt_template | llm.bind_tools(other_tools)

tool_chain = tools_prompt_template | llm.bind_tools(other_tools)


async def browser_node(state: AgentState) -> AgentState:
    """
    Handles the browser state and extracts relevant page data.

    Args:
        state (AgentState): The current agent state.
    
    Returns:
        AgentState: Updated state with extracted page data.
    """
    try:
        state["steps"] += 1
        page = state.get("page")

        if not page:
            logger.error("Browser object not set")
            state["errors"] = "Browser object not initialized correctly. Please check configuration."
            return state

        # Wait for page to be completely loaded before proceeding
        logger.info("Waiting for page to be completely loaded...")
        await state["page"].wait_for_load_state("domcontentloaded")
        


        # Extract and mark relevant page data asynchronously
        marked_data = await mark_page(page)

        state.update({
            "bboxes": marked_data.get("bboxes", []),
            "img": marked_data.get("img"),
        })

    except KeyError as e:
        logger.error(f"KeyError encountered: {e}", exc_info=True)
        state["errors"] = f"Missing key in state: {e}"
    except TypeError as e:
        logger.error(f"TypeError encountered: {e}", exc_info=True)
        state["errors"] = f"Type error while processing page: {e}"
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        state["errors"] = f"Error while processing page content: {e}"

    return state

async def execution_node(state: AgentState) -> AgentState:
    """
    Executes the AI model and processes results efficiently.
    Stores model response as thoughts in the state.
    """
    try:
        state["steps"] += 1

        if not isinstance(state.get("thoughts"), str):
            state["thoughts"] = ""

        if not state.get("task"):
            logger.error("No task provided to execution_node")
            state["errors"] = "No task description was provided. Please specify what you want to accomplish on this page."
            return state
        
        enhanced_task = {
            "task": state.get("task"),
            "img": state.get("img"),
            "history": state.get("history", ""),
            "bboxes": state.get("bboxes", []),
            "profile_info": state.get("profile_info", "None"),
            "insights": state.get("insights", ""),
            "thoughts": state.get("thoughts", ""),
            "VISITED_WEBSITES": state.get("VISITED_WEBSITES", "")
        }

        # Step 1: Run main chain after tool_chain
        logger.debug("Calling main chain with enhanced task")

        response = await asyncio.to_thread(
            chain.invoke,
            enhanced_task,
        )

        if not response:
            logger.error("Empty response received from model")
            state["errors"] = "Model returned an empty response. Please try again with a more specific task."
            return state

        logger.debug(f"Main chain response: {response}")

        if state["thoughts"]:
            state["thoughts"] += "\n\n----- Final Thought from Main Chain -----\n\n"

        state["thoughts"] += str(response)

        # Step 2: Process tools from main chain response
        state = await process_tools(response, state)

        # Step 3: Create a page observation
        observation_text = ""
        try:
            await state["page"].wait_for_load_state("domcontentloaded")
            raw_text = await state["page"].inner_text("body")
            observation_text = raw_text.strip()
            logger.debug(f"Full page text extracted (length {len(observation_text)} characters)")
        except Exception as e:
            observation_text = "Could not extract page content due to: " + str(e)

        system_prompt = insights_template

        user_prompt = f"""📝 **Task**: {state.get("task")}
            📄 **Extracted Page Text**:
            {observation_text}
                    """

        messages = [
            SystemMessage(content=system_prompt.strip()),
            HumanMessage(content=user_prompt.strip())
        ]

        # Generate insight
        insight = await asyncio.to_thread(
            llm.invoke, messages
        )
        logger.debug(f"Insight generated: {insight}")

        if not insight:
            logger.error("Model returned an empty response")
            state["errors"] = "The model could not generate a response based on the page content."
            return state

        if "insights" not in state or not isinstance(state["insights"], str):
            state["insights"] = ""

        if state["insights"]:
            state["insights"] += "\n\n===== Next Insight =====\n\n"

        state["insights"] += str(insight)
        logger.debug("Insight added to state")

        # Prepare enhanced task input for tool_chain and main chain


        # Step 4: Run tool_chain first

        logger.debug("Calling tool_chain with enhanced task and observation")

        tool_response = await asyncio.to_thread(
            tool_chain.invoke,
            enhanced_task,
        )

        logger.debug(f"Tool chain response: {tool_response}")

        if tool_response:
            # Process tools from tool_chain
            state = await process_tools(tool_response, state)
        else:
            logger.warning("Tool chain did not return a response")

        


    except KeyError as e:
        logger.error(f"KeyError encountered: {e}", exc_info=True)
        state["errors"] = f"Missing required information: {e}"
    except TypeError as e:
        logger.error(f"TypeError encountered: {e}", exc_info=True)
        state["errors"] = f"Type error while processing task: {e}"
    except asyncio.CancelledError:
        logger.warning("execution_node task was cancelled")
        state["errors"] = "Task was cancelled by the system or user"
    except Exception as e:
        logger.error(f"Unexpected error in execution_node: {e}", exc_info=True)
        state["errors"] = f"Unexpected error while executing task: {e}"

    return state

async def answer_node(state: AgentState) -> AgentState:
    """
    Generates the final answer after reaching recursion depth.
    Incorporates insights collected during execution and analyzes images when generating the final answer.
    
    Args:
        state (AgentState): The current agent state.
        
    Returns:
        AgentState: Updated state with the final response.
    """
    try:
        logger.debug("Generating final answer after recursion depth")
        
        task_content = state.get("task")
        logger.debug(f"Task content: {task_content}")
        insights = state.get("insights", "")
        logger.debug(f"Insights collected: {insights}")
        
        if not task_content or not isinstance(task_content, list) or not task_content[0].content:
            logger.error("Invalid or missing task content in state")
            state["errors"] = "Could not generate final answer due to missing task information"
            return state
        
        
        # Call LLM with structured output
        response = await asyncio.to_thread(
            (answer_prompt_template | llm.with_structured_output(Response)).invoke,
            {
                "task": state.get("task"),
                "img": state.get("img"),
                "history": state.get("history", ""),
                "bboxes": state.get("bboxes", []),
                "profile_info": state.get("profile_info", "None"),
                "page_load_status": state.get("page_load_status", "unknown"),
                "thoughts" : state.get("thoughts", ""),
                "insights": state.get("insights", ""),
                "VISITED_WEBSITES": state.get("VISITED_WEBSITES", ""),
            }
        )

        set_response(response)
        
        logger.debug(f"Final response: {response}")
        
        state.update({
            "end": True,
            "answer": response.final_answer,
            "errors": response.errors,
        })
        
    except KeyError as e:
        logger.error(f"KeyError encountered: {e}", exc_info=True)
        state["errors"] = f"Error accessing required information: {e}"
    except TypeError as e:
        logger.error(f"TypeError encountered: {e}", exc_info=True)
        state["errors"] = f"Type error while generating final answer: {e}"
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        state["errors"] = f"Error generating final answer: {e}"
    
    return state