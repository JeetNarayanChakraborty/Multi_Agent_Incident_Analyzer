import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

load_dotenv()

from tools import query_database

# Initialize the Google Generative AI model
# Temerature should be 0, as only deterministic answers are expected from the model
llm = ChatGoogleGenerativeAI(
    model="gemini-3.7-flash", temperature=0, api_key=os.getenv("GOOGLE_API_KEY")
)

# Collect the tools into a list to be used by the agent
tool_available = [query_database]

# Define the System Prompt
# This prompt is used to instruct the agent to perform scatter - gather
# as well as looping through the tools to find the root cause of the incident
database_prompt = """
You are the Database Investigation Agent, specializing in PostgreSQL performance troubleshooting and lock analysis.
Your objective is to use the query_database tool to diagnose connection exhaustion, long-running queries, and blocked transactions.

EXECUTION STRATEGY & DYNAMIC REASONING:
1. DYNAMIC INVESTIGATION: Analyze the provided context (such as an upstream error log or affected service) to dynamically formulate the appropriate diagnostic SQL query.
2. SAFE QUERY GENERATION: Construct and execute strictly read-only SQL queries. Focus on system catalog views (e.g., pg_stat_activity, pg_locks) or specific application tables to identify anomalies.
3. CONTEXTUAL REASONING: Interpret the raw database observations. Differentiate between normal active connections and stalled transactions holding exclusive locks or unindexed queries causing performance degradation.
4. LOGICAL SYNTHESIS: Correlate the database metrics and blocking PIDs to determine the exact database-level root cause.

CRITICAL RULES:
- Ground your reasoning strictly in the explicitly returned data from the query_database tool.
- Maintain 0% hallucination. Never invent database schemas, table names, lock states, or query results.
- Conclude by returning a clean, logically structured summary of the specific database anomalies found, then stop.
"""

# LangGraph React Agent, automatically builds the state machine loop between LLM and tools
database_agent_executor = create_agent(
    model=llm, tools=tool_available, system_prompt=database_prompt
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

    # Execute the graph using the specialized database agent
    try:
        for chunk in database_agent_executor.stream(
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

        # Output the final findings from the Database Agent
        print("\n=== DATABASE AGENT FINAL SUMMARY ===")
        print(final_summary)

    except Exception as e:
        print(f"\n[CIRCUIT BREAKER TRIGGERED] Investigation halted: {str(e)}")
