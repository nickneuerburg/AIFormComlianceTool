import logging
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, BaseMessage

from prompts import PROMPTS
from tool_manager import ToolManager

logger = logging.getLogger(__name__)


def run_fsm_agent(llm, tool_manager: ToolManager):
    current_state = "FOOTER_ANALYSIS"
    max_steps_per_state = 35  # Increased for multi-step states
    final_output = "Agent did not finish."

    llm_with_tools = llm.bind_tools(tool_manager.tools)
    tool_map = {tool.name: tool for tool in tool_manager.tools}

    message_history: list[BaseMessage] = []  # Ensure it's always defined

    while current_state != "FINISHED":
        logger.info(f"--- Entering State: {current_state} ---")
        prompt_template = PROMPTS[current_state]

        message_history: list[BaseMessage] = [HumanMessage(content=prompt_template)]

        for i in range(max_steps_per_state):
            logger.info(f"Step {i+1} in state '{current_state}'")

            ai_response = llm_with_tools.invoke(message_history)
            message_history.append(ai_response)

            if not ai_response.tool_calls:
                logger.warning(
                    "LLM did not request a tool. Analyzing its final content for state transition..."
                )
                final_content = ai_response.content

                if "Finished with footer analysis." in final_content:
                    current_state = "FORM_NAVIGATION"
                    break
                # New condition: If TCPA is found early jump straight to the final report.
                elif (
                    "TCPA Found" in final_content
                    or "Finished with form navigation" in final_content
                ):
                    current_state = "DISCLAIMER_VERIFICATION"
                    break
                elif "VERIFICATION_COMPLETE" in final_content:
                    final_output = final_content
                    current_state = "FINISHED"
                    break

                else:
                    logger.warning(
                        f"No tool call and no state transition signal. Agent is stuck in state {current_state}."
                    )
                    final_output = f"Agent got stuck in state {current_state}. Final content: {final_content}"
                    current_state = "FINISHED"
                    break

            for tool_call in ai_response.tool_calls:
                tool_to_call = tool_map.get(tool_call["name"])
                if not tool_to_call:
                    observation = f"Error: Tool '{tool_call['name']}' not found."
                else:
                    logger.info(
                        f"Invoking tool: {tool_call['name']} with args: {tool_call['args']}"
                    )
                    observation = tool_to_call.invoke(tool_call["args"])

                logger.info(f"Tool Observation: {observation}")

                message_history.append(
                    ToolMessage(content=str(observation), tool_call_id=tool_call["id"])
                )
        else:
            logger.warning(f"Max steps reached for state '{current_state}'.")
            final_output = f"Agent reached max steps in state {current_state}."
            current_state = "FINISHED"

    full_thought_history = "\n\n".join(str(m) for m in message_history)
    return final_output, full_thought_history
