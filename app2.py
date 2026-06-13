import json
from typing import List, Optional, TypedDict
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langgraph.graph import StateGraph, START, END

from langchain_groq import ChatGroq
from dotenv import load_dotenv
load_dotenv()

class TripState(TypedDict):
    user_message: str
    destination: Optional[str]
    days: Optional[int]
    budget: Optional[str]
    travelers: Optional[int]
    next_question: Optional[int]
    complete: bool
    response: Optional[str]



llm = ChatGroq(
    model="llama-3.3-70b-versatile"
)

REQUIRED_FIELDS = [
    "destination",
    "days",
    "budget",
    "travelers"
]

def extract_info(state:TripState):
    prompt = f"""
Extract travel information from user message.

Return only valid JSON.

Schema:
{{
    "destination": str | null,
    "days": int | null,
    "budget": str | null,
    "travelers": int | null
}}

User Message:
{state['user_message']}
"""
    result = llm.invoke([
        HumanMessage(content=prompt)
    ])

    content = result.content.strip()

    if content.startswith("```json"):
        content = content[7:]  # remove ```json

    if content.endswith("```"):
        content = content[:-3]  # remove closing ```

    content = content.strip()
    print(f"LLM Response: {content}")

    try:
        extracted = json.loads(content)
        print(
            "Extracted Information:",
            extracted
        )
    except Exception as e:
        print(f"Failed extraction: {e}")
        extracted = {}
    
    updated_state = dict(state)
    for key, value in extracted.items():
        if value is not None:
            updated_state[key] = value

    return updated_state

def check_missing_fields(state: TripState):
    questions = {
        "destination": "Where do you want to travel?",
        "days": "How many days do you want to travel?",
        "budget": "What is your budget for the trip?",
        "travelers": "How many travelers will be there?"
    }

    for field in REQUIRED_FIELDS:
        if not state.get(field):
            return {
                **state,
                "complete": False,
                "next_question": questions[field],
                "response": questions[field]
            }
    
    return {
        **state,
        "complete": True,
        "next_question": None,
        "response": "Thank you for the information! We are processing your travel plan."
    }


def plan_trip(state: TripState):
    return {
        **state,
        "response": "Trip planned successfully"
    }

def router(state: TripState):
    if state["complete"]:
        return "plan_trip_edge"
    return "ask_user_edge"

def ask_user(state: TripState):
    return state


builder = StateGraph(TripState)
builder.add_node("extract_info", extract_info)
builder.add_node("check_missing_fields", check_missing_fields)
builder.add_node("ask_user", ask_user)
builder.add_node("plan_trip", plan_trip)

builder.set_entry_point("extract_info")

builder.add_edge("extract_info", "check_missing_fields")

builder.add_conditional_edges("check_missing_fields", router,{
    "plan_trip_edge": "plan_trip",
    "ask_user_edge": "ask_user"
})

builder.add_edge("ask_user", END)
builder.add_edge("plan_trip", END)

graph = builder.compile()

state = {
    "destination":None,
    "days":None,
    "budget":None,
    "travelers":None,
    "next_question": None,
    "complete": False,
}



while True:
    user_input = input("Enter your travel request: ")
    state["user_message"] = user_input

    response = graph.invoke(state)

    print(f"AI: {response['response']}")

    state = response

    print(f"State at the end of run: {state}")
    if response["complete"]:
        break