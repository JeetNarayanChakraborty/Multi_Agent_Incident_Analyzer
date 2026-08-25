import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

load_dotenv()

from tools import search_logs

# Initialize the Google Generative AI model
# Temerature should be 0, as only deterministic answers are expected from the model
llm = ChatGoogleGenerativeAI(
    model="gemini-3.7-flash", temperature=0, api_key=os.getenv("GOOGLE_API_KEY")
)

# Collect the tools into a list to be used by the agent
tool_available = [search_logs]

# Define the System Prompt
# This prompt is used to instruct the agent to perform scatter - gather
# as well as looping through the tools to find the root cause of the incident
telemetry_prompt = """
You are the Telemetry Analysis Agent, specializing in distributed system observability. 
Your objective is to investigate application logs using the search_logs tool to identify latency spikes, error cascades, and anomalies.

EXECUTION STRATEGY & DYNAMIC REASONING:
1. DYNAMIC INVESTIGATION: Analyze the incoming alert and use your internal logic to determine the exact service or time window to query.
2. CONTEXTUAL REASONING: When log output is retrieved, investigate the context. Differentiate between routine background noise and critical systemic failures (e.g., connection pool exhaustion vs. a standard transient timeout).
3. LOGICAL SYNTHESIS: Piece together the sequence of events. If multiple distinct errors are detected, reason through their causal relationship to identify the true upstream symptom.

CRITICAL RULES:
- Ground your reasoning strictly in the explicit data returned by your tool.
- Maintain 0% hallucination. Never invent log entries, error messages, or timestamps.
- Conclude by returning a clean, insightful, and logically structured summary of the core issues found, then stop.
"""

# LangGraph React Agent, automatically builds the state machine loop between LLM and tools
telemetry_agent_executor = create_agent(
    model=llm, tools=tool_available, system_prompt=telemetry_prompt
)


def run_triage(incident_message: str):
    """
    Entry point to trigger the agent.
    A recursion_limit of 15 is set to act as the circuit breaker.
    """
    print(f"--- INITIATING INCIDENT TRIAGE ---")
    print(f"Alert Received: {incident_message}\n")

    config = {"recursion_limit": 15}
    final_summary = ""

    # Execute the graph using the specialized telemetry agent
    try:
        for chunk in telemetry_agent_executor.stream(
            {"messages": [("user", incident_message)]}, config=config
        ):
            # Print the agent's internal reasoning and tool calls as they happen
            for key, value in chunk.items():
                if key == "agent":
                    # Capture the latest message to print the final summary at the end
                    final_summary = value["messages"][0].content

                    if value["messages"][0].tool_calls:
                        tool_calls = value["messages"][0].tool_calls
                        for tc in tool_calls:
                            print(
                                f"[Agent Decision] -> Dynamically Calling Tool: '{tc['name']}' with args: {tc['args']}"
                            )
                    else:
                        print(f"[Agent Reasoning] -> {value['messages'][0].content}")
                elif key == "tools":
                    print(f"[Tool Execution] -> Observation gathered.\n")

        # Output the final findings from the Telemetry Agent
        print("\n=== TELEMETRY AGENT FINAL SUMMARY ===")
        print(final_summary)

    except Exception as e:
        print(f"\n[CIRCUIT BREAKER TRIGGERED] Investigation halted: {str(e)}")
