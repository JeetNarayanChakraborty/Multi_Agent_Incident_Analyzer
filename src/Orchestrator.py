import operator
from typing import Annotated, Sequence, TypedDict, Literal
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
import database_agent, git_agent, log_agent


# Defines the shared memory accessible by all agents
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_worker: str


# Enforces the LLM to output a precise routing decision
class Route(BaseModel):
    next_worker: Literal[
        "telemetry_agent", "database_agent", "code_agent", "FINISH"
    ] = Field(
        description="The next agent to route the investigation to. Select 'FINISH' ONLY when the incident report has been dispatched to GitHub."
    )


supervisor_prompt = """
You are the System Context Supervisor, orchestrating a distributed multi-agent incident response framework.
Your objective is to evaluate the global state of the investigation, deduce missing critical-path evidence, and autonomously route execution to the appropriate domain expert.

DOMAIN EXPERTS (WORKERS):
- 'telemetry_agent': Activate to retrieve and synthesize raw application logs. This is typically the entry point to isolate the symptom (e.g., connection timeouts, exceptions).
- 'database_agent': Activate to diagnose data-tier bottlenecks, including PostgreSQL transaction locks, unindexed queries, or connection pool exhaustion.
- 'code_agent': Activate to perform codebase forensics via semantic ORM mapping and to dispatch the final Root Cause Analysis (RCA) report.

DYNAMIC ROUTING & STATE EVALUATION RULES:
1. CONTEXTUAL STRATEGY: Analyze the conversation history. Do not rigidly cycle through agents. Route based on the specific technical evidence missing from the current state.
2. BLOCKING CONDITIONS: If a worker returns an error or insufficient data, do not halt. Re-evaluate the state and route to an alternative agent to gather cross-sectional evidence.
3. DEPENDENCY MANAGEMENT: Ensure the 'database_agent' or 'code_agent' is only called when there is sufficient upstream context (e.g., a specific service name or locked table name) to formulate a targeted query.
4. ZERO HALLUCINATION & NO CHAT: Do not output conversational text, ask questions, or invent evidence. Output only the exact routing string required.
5. COMPLETION CRITERIA: The investigation is only complete when a formalized RCA report has been successfully dispatched to the repository. Once the 'code_agent' explicitly confirms the GitHub issue creation, output exactly 'FINISH'.
"""


# Defines the supervisor node that evaluates the state and outputs the next routing decision
def supervisor_node(state: AgentState):
    """Evaluates the state and outputs the next routing decision."""
    from langchain_core.messages import SystemMessage

    messages = state["messages"]
    # Binds the Pydantic schema to the LLM
    router_llm = llm.with_structured_output(Route)

    # Prepends the supervisor instructions to the full context history
    prompt = [SystemMessage(content=supervisor_prompt)] + messages
    decision = router_llm.invoke(prompt)

    return {"next_worker": decision.next_worker}


# Executes the telemetry agent and returns the final output to a global memory
def telemetry_node(state: AgentState):
    """Executes the telemetry agent and appends the result to global memory."""
    # Assuming 'telemetry_agent' is initialized via create_agent
    result = log_agent.invoke({"messages": state["messages"]})
    final_output = result["messages"][-1].content
    return {
        "messages": [
            HumanMessage(
                content=f"Telemetry Findings: {final_output}", name="telemetry_agent"
            )
        ]
    }


# Executes the database agent and returns the final output to a global memory
def database_node(state: AgentState):
    """Executes the database agent and appends the result to global memory."""
    result = database_agent.invoke({"messages": state["messages"]})
    final_output = result["messages"][-1].content
    return {
        "messages": [
            HumanMessage(
                content=f"Database Findings: {final_output}", name="database_agent"
            )
        ]
    }


# Executes the code agent and returns the final output to a global memory
def code_node(state: AgentState):
    """Executes the code agent and appends the result to global memory."""
    result = git_agent.invoke({"messages": state["messages"]})
    final_output = result["messages"][-1].content
    return {
        "messages": [
            HumanMessage(
                content=f"Code/Report Findings: {final_output}", name="code_agent"
            )
        ]
    }


# Initializes the state machine with nodes and edges
workflow = StateGraph(AgentState)

# Add the independent nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("telemetry_agent", telemetry_node)
workflow.add_node("database_agent", database_node)
workflow.add_node("code_agent", code_node)


# Define the logic for dynamic routing
def route_next(state: AgentState):
    if state["next_worker"] == "FINISH":
        return END
    return state["next_worker"]


# Connect the edges
workflow.add_conditional_edges("Supervisor", route_next)

# Ensure workers always report back to the Supervisor
workflow.add_edge("telemetry_agent", "Supervisor")
workflow.add_edge("database_agent", "Supervisor")
workflow.add_edge("code_agent", "Supervisor")

# Set the starting point of the workflow
workflow.set_start(START, "Supervisor")

# Compile the multi-agent network
MAF = workflow.compile()
