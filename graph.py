from langgraph.graph import StateGraph, END
from state import AgentState
from nodes import browser_node, execution_node, answer_node
from constants import RECURSION_LIMIT
import os, sys


from logger import get_logger
logger = get_logger()

class VisionGraph:
    """
    Represents a state graph for the Vision system, handling transitions between different processing nodes.
    """
    def __init__(self):
        """
        Initializes the VisionGraph with necessary nodes and edges.
        """
        self.graph: StateGraph = StateGraph(AgentState)
        self.__setup_nodes()
        self.__setup_edges()

    def __continue(self, state):
        """
        Determines the next node based on the current state.

        Args:
            state (dict): The current state of the graph execution.

        Returns:
            str: The next node name to transition to.
        """
        try:
            steps = state["steps"]
            
            if steps >= RECURSION_LIMIT:
                return "answer"

            if state.get("end", False):
                return "end"

            return "continue"
        except KeyError as e:
            logger.error(f"Key error in state processing: {e}")
            return "end"
        except Exception as e:
            logger.error(f"Unexpected error in __continue method: {e}")
            return "end"

    def __setup_nodes(self):
        """
        Sets up the nodes for the VisionGraph.
        """
        try:
            self.graph.add_node("browser_node", browser_node)
            self.graph.add_node("execution_node", execution_node)
            self.graph.add_node("answer_node", answer_node)

            self.graph.set_entry_point("browser_node")
        except Exception as e:
            logger.error(f"Error setting up nodes: {e}")

    def __setup_edges(self):
        """
        Defines the edges and conditions for transitioning between nodes.
        """
        try:
            self.graph.add_conditional_edges(
                "execution_node",
                self.__continue,
                {"end": END, "continue": "browser_node", "answer": "answer_node"},
            )

            # Remove the direct connection from execution_node to END
            self.graph.add_edge("browser_node", "execution_node")
            self.graph.add_edge("answer_node", END)  # Only transition to END from the answer_node
        except Exception as e:
            logger.error(f"Error setting up edges: {e}")

    def compile_graph(self):
        """
        Compiles the graph and returns the compiled object.

        Returns:
            CompiledGraph: The compiled state graph.
        """
        try:
            return self.graph.compile()
        except Exception as e:
            logger.error(f"Error compiling graph: {e}")
            return None
