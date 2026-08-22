import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from src.tools import (
    search_logs,
    query_database,
    search_git_commits,
    dispatch_incident_report,
)

load_dotenv()

# Initialize the Google Generative AI model
# Temerature should be 0, as only deterministic answers are expected from the model
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash", temperature=0, api_key=os.getenv("GOOGLE_API_KEY")
)

# Collect the tools into a list to be used by the agent
tool_available = [
    search_logs,
    query_database,
    search_git_commits,
    dispatch_incident_report,
]

# Define the System Prompt
# This prompt is used to instruct the agent to perform scatter - gather
# as well as looping through the tools to find the root cause of the incident
system_prompt = """
You are an Autonomous Incident Response Agent responsible for dynamically triaging production latency spikes.
Your objective is to investigate the issue, correlate cross-platform evidence, determine the root cause, and dispatch a report.

EXECUTION STRATEGY & DYNAMIC REASONING:
1. DYNAMIC EXECUTION: Do not rigidly follow a set sequence of steps. In every loop, you must dynamically determine whether a parallel scatter-gather approach (calling multiple tools concurrently) or a single, focused tool call is required based on the current context and missing evidence.
2. LLM LOGIC & ZERO HALLUCINATION: Do not merely execute a static checklist. Use your internal LLM logic and reasoning capabilities dynamically to navigate the investigation. You must maintain strictly 0% hallucination—ground every single deduction exclusively in the explicit outputs returned by your tools.
3. CORRELATION & DEEP DIVE: Analyze the findings from your dynamic tool calls. If an anomaly is detected, deduce the missing link and dynamically select the next logical tool to trace the symptom back to its origin.
4. INVESTIGATION BOUNDARIES: 
   - LOWER BOUND: Evidence must be gathered and correlated from at least TWO distinct sources before formulating a conclusion. Do not escalate prematurely.
   - UPPER BOUND: The investigation must conclude efficiently within a maximum of 5 reasoning cycles.
5. SYNTHESIS & ESCALATION: Once the root cause is confidently established, or if a dead-end is reached at the upper boundary, call the final reporting tool exactly once to alert the human engineering team.

REPORTING DIRECTIVE:
When invoking the final reporting tool, the generated markdown body MUST follow this exact structure:

# 🚨 [INCIDENT RCA] High Latency on [Service Name]

## 1. Incident Summary
* **Impacted Service:** [Service Name]
* **Trigger Alert:** [Alert Details]
* **Root Cause:** [Dynamic summary of the verified issue and its origin]

## 2. Investigation Timeline & Evidence Chain
[Include a Markdown table correlating the distinct sources and the explicit observations found]

## 3. Suggested Immediate Mitigation (Restore Service)
Execute the following containment actions immediately:
1. **Terminate the Blocking Process/Query:**
   [Provide the exact mitigation command, if applicable]
2. **Roll Back or Revert:**
   [Provide the exact rollback target, if applicable]

CRITICAL RULES:
- Maintain 0% hallucination. Never invent telemetry, logs, table names, or commit hashes. 
- If the root cause cannot be fully determined within the iteration limit, generate the report using the partial evidence gathered so far.
- Once the final incident report is dispatched, the investigation is complete. Do not execute any further actions.
"""

# LangGraph React Agent, automatically builds the state machine loop between LLM and tools
agent_executor = create_agent(
    model=llm, tools=tool_available, state_modifier=system_prompt
)


def run_triage(incident_message: str):
    """
    Entry point to trigger the agent.
    A recursion_limit of 15 is set to act as the circuit breaker.
    Since each LLM thought and Tool execution counts as a step, 15 steps safely
    covers the maximum 5 dynamic reasoning cycles defined in the system prompt.
    """
    print(f"--- INITIATING INCIDENT TRIAGE ---")
    print(f"Alert Received: {incident_message}\n")

    config = {"recursion_limit": 15}

    # Execute the graph
    try:
        for chunk in agent_executor.stream(
            {"messages": [("user", incident_message)]}, config=config
        ):
            # Print the agent's internal reasoning and tool calls as they happen
            for key, value in chunk.items():
                if key == "agent":
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

    except Exception as e:
        print(f"\n[CIRCUIT BREAKER TRIGGERED] Investigation halted: {str(e)}")
