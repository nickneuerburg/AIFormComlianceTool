import logging
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain.agents import AgentExecutor, create_structured_chat_agent


logger = logging.getLogger(__name__)


def create_web_agent(llm, tools):
    """
    Creates the agent executor with a prompt structure that separates
    the agent's role from the user's task, forcing tool use.
    """

    prompt = ChatPromptTemplate.from_messages(
        [
            # 1. High level instruction for the agent.
            SystemMessagePromptTemplate.from_template(
                "You are an expert web automation assistant. You must use the tools provided to you to complete the user's request. "
                "Your final answer should be a concise summary of findings, including 'VERIFICATION_COMPLETE' when you are done. "
                "Ensure all your intermediate thoughts are textual descriptions, and use JSON for tool calls."
            ),
            # 2. State specific prompt
            HumanMessagePromptTemplate.from_template("{input}"),
            # 3. This is where the history of tool calls will go.
            #    The AgentExecutor will format intermediate steps into messages for this.
            MessagesPlaceholder(variable_name="agent_scratchpad"),
            # 4. CRITICAL: These placeholders are implicitly filled by create_structured_chat_agent
            #    when you provide it with the tools list. They MUST be present in the prompt.
            MessagesPlaceholder(variable_name="tools"),
            MessagesPlaceholder(variable_name="tool_names"),
        ]
    )

    # Use create_structured_chat_agent directly.
    agent = create_structured_chat_agent(llm, tools, prompt)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=60,  # Increased for complex forms
    )
