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
from typing import Annotated
from langgraph.graph.message import add_messages
from tools.flight import search_flights
from tools.tavily import tavily_search
from memory import checkpointer
load_dotenv()

class TripState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_message: str
    origin: Optional[str]
    destination: Optional[str]
    days: Optional[int]
    budget: Optional[str]
    travelers: Optional[int]
    next_question: Optional[int]
    complete: bool
    response: Optional[str]
    flight_info: str
    hotel_info: str



llm = ChatGroq(
    model="llama-3.3-70b-versatile"
)

REQUIRED_FIELDS = [
    "origin",
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
    "origin": str | null,
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
    
    updated_state["messages"] = (
        state.get("messages", [])
        + [HumanMessage(content=state["user_message"])]
    )

    return updated_state

def check_missing_fields(state: TripState):
    questions = {
        "origin": "Where are you departing from?",
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


def get_flight_info(state:TripState) -> TripState:
    flight_data = search_flights(state)
    return {
        **state,
        "flight_info": flight_data
    }

def get_hotels_info(state:TripState) -> TripState:
    query = f"Best hotels for {state['destination']} for {state['days']} days"
    hotels_data = tavily_search(query)
    return {
        **state,
        "hotel_info": hotels_data
    }

def get_itenary_info(state:TripState) -> TripState:
    prompt = f"""
    Create a travel itinerary.
    User Query:
    Origin: {state['origin']}
    Destination: {state['destination']}
    Days: {state['days']}
    Budget: {state['budget']}

    Flight Results:
    {state['flight_info']}

    Hotel Results:
    {state['hotel_info']}
    """
    
    response = llm.invoke([
        SystemMessage(
            content="You are an expert travel planner"
        ),
        HumanMessage(content=prompt)
    ])

    return {
        **state,
        "messages": state.get("messages", []) + [AIMessage(content=response.content)],
        "response": response.content,
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
builder.add_node("get_flight_info", get_flight_info)
builder.add_node("get_hotels_info", get_hotels_info)
builder.add_node("get_itenary_info", get_itenary_info)

builder.set_entry_point("extract_info")

builder.add_edge("extract_info", "check_missing_fields")

builder.add_conditional_edges("check_missing_fields", router,{
    "plan_trip_edge": "get_flight_info",
    "ask_user_edge": "ask_user"
})

builder.add_edge("get_flight_info", "get_hotels_info")
builder.add_edge("get_hotels_info", "get_itenary_info")

builder.add_edge("ask_user", END)
builder.add_edge("get_itenary_info", END)


graph = builder.compile(
    checkpointer=checkpointer
)

state = {
    "messages": [],
    "origin": None,
    "destination": None,
    "days": None,
    "budget": None,
    "travelers": None,
    "next_question": None,
    "complete": False,
    "response": None,
    "flight_info": None,
    "hotel_info": None
}

user_id = input("Enter User ID: ")

config = {
    "configurable": {
        "thread_id": user_id
    }
}

while True:
    user_input = input("Enter your travel request: ")

    response = graph.invoke(
        {
            "user_message": user_input
        },
        config=config
    )

    # print(f"AI: {response['response']}")
    snapshot = graph.get_state(config)

    print(snapshot.values)

    if response["complete"]:
        break