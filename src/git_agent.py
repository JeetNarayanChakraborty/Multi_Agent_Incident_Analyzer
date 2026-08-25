import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

load_dotenv()

from tools import dispatch_incident_report, search_git_commits

# Initialize the Google Generative AI model
# Temerature should be 0, as only deterministic answers are expected from the model
llm = ChatGoogleGenerativeAI(
    model="gemini-3.7-flash", temperature=0, api_key=os.getenv("GOOGLE_API_KEY")
)

# Collect the tools into a list to be used by the agent
tool_available = [search_git_commits, dispatch_incident_report]

# Define the System Prompt
# This prompt is used to instruct the agent to perform scatter - gather
# as well as looping through the tools to find the root cause of the incident
code_prompt = """
You are the Code Analysis and Reporting Agent, specializing in codebase forensics and incident escalation.
Your objective is to use the search_git_commits tool to locate offending pull requests and the dispatch_incident_report tool to publish the final Root Cause Analysis (RCA).

EXECUTION STRATEGY & DYNAMIC REASONING:
1. DYNAMIC FORENSICS: Analyze the provided context (such as a locked database table name or a specific application error) to formulate the correct search parameters for the repository.
2. SEMANTIC ORM MAPPING: If a database table is implicated (e.g., 'orders'), pass the raw table name directly to the commit search tool to automatically map it to the corresponding Spring Data JPA repository and discover recent modifications.
3. SYNTHESIS & ESCALATION: Correlate the codebase findings with the upstream symptoms. Draft a comprehensive markdown report detailing the impacted service, the verified root cause, and the evidence chain.
4. FINAL DISPATCH: Invoke the dispatch_incident_report tool exactly once with the synthesized markdown body to alert the engineering team.

CRITICAL RULES:
- Ground your reasoning strictly in the explicitly returned data from the tool outputs.
- Maintain 0% hallucination. Never invent commit hashes, pull request numbers, file paths, or repository structures.
- The investigation concludes immediately after the incident report is successfully dispatched to GitHub.
"""

# LangGraph React Agent, automatically builds the state machine loop between LLM and tools
code_agent_executor = create_agent(
    model=llm, tools=tool_available, system_prompt=code_prompt
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

    # Execute the graph using the specialized code agent
    try:
        for chunk in code_agent_executor.stream(
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

        # Output the final findings and confirmation from the Code Agent
        print("\n=== CODE AGENT FINAL SUMMARY ===")
        print(final_summary)

    except Exception as e:
        print(f"\n[CIRCUIT BREAKER TRIGGERED] Investigation halted: {str(e)}")
