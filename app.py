import json
import os
import re
from typing import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)

from langchain_groq import ChatGroq

from tools.mongo_memory import MongoMemory
from tools.tavily import tavily_search
from tools.flight_service import search_flights
from dotenv import load_dotenv
load_dotenv()

agent_llm = ChatGroq(
    model="llama-3.3-70b-versatile"
)

SYSTEM_PROMPT = (
    "You are an expert travel planner. Extract useful travel details from the user request, build a high-quality itinerary, "
    "and provide a concise final travel recommendation. Always preserve the user's preferences, budget, dates, and destination."
)

class TravelPartnerState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], operator.add]
    conversation_history: list[AnyMessage]
    user_query: str
    trip_details: dict[str, str]
    flight_options: list[dict]
    hotel_options: list[dict]
    itinerary: str
    llm_calls: int
    errors: list[str]


def merge_state(state: TravelPartnerState, updates: TravelPartnerState) -> TravelPartnerState:
    merged = dict(state)
    merged.update({k: v for k, v in updates.items() if k not in ("messages", "conversation_history")})

    merged["messages"] = list(state.get("messages", [])) + list(updates.get("messages", []))
    merged["conversation_history"] = list(state.get("conversation_history", [])) + list(updates.get("conversation_history", []))
    merged["errors"] = list(state.get("errors", [])) + list(updates.get("errors", []))
    merged["llm_calls"] = state.get("llm_calls", 0) + updates.get("llm_calls", 0)
    return merged


def safe_parse_json(text: str) -> dict[str, str]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


def validate_environment() -> None:
    return


def extract_destination(user_query: str) -> str:
    match = re.search(r"to\s+([A-Za-z ]+)", user_query, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return user_query.strip()


def format_flight_options(flights: list[dict]) -> str:
    if not flights:
        return "No flight options were found."
    lines = []
    for index, flight in enumerate(flights, start=1):
        lines.append(
            f"{index}. {flight['airline']} from {flight['departure_airport']} to {flight['arrival_airport']} "
            f"({flight['departure_time']} → {flight['arrival_time']}) | {flight['duration']} | {flight['price']}"
        )
    return "\n".join(lines)


def format_hotel_options(hotels: list[dict]) -> str:
    if not hotels:
        return "No hotel options were found."
    lines = []
    for index, hotel in enumerate(hotels, start=1):
        lines.append(
            f"{index}. {hotel['name']} — {hotel['rating']} | {hotel['price']}\n"
            f"   {hotel['address']}\n"
            f"   {hotel['summary']}\n"
            f"   {hotel['url']}"
        )
    return "\n".join(lines)


def parse_trip_details(state: TravelPartnerState) -> TravelPartnerState:
    prompt = f"""
Extract travel details from the user request below.
Return only valid JSON with these keys: origin, destination, departure_date, return_date, travelers, preferences, budget.
Use an empty string for any value you cannot infer.

User request:
{state['user_query']}
"""

    response = agent_llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ])

    trip_details = safe_parse_json(response.content)
    if not trip_details:
        trip_details = {
            "origin": "",
            "destination": extract_destination(state["user_query"]),
            "departure_date": "",
            "return_date": "",
            "travelers": "",
            "preferences": "",
            "budget": "",
        }

    return merge_state(
        state,
        {
            "trip_details": trip_details,
            "messages": [AIMessage(content="Trip details are extracted and saved.")],
            "conversation_history": [response],
            "llm_calls": 1,
        },
    )


def get_flight_info(state: TravelPartnerState) -> TravelPartnerState:
    destination = state.get("trip_details", {}).get("destination") or state["user_query"]
    flight_options = search_flights(destination)
    message_text = (
        f"Fetched {len(flight_options)} flight option(s) for {destination}."
        if flight_options
        else f"No flight options found for {destination}."
    )

    return merge_state(
        state,
        {
            "flight_options": flight_options,
            "messages": [AIMessage(content=message_text)],
        },
    )


def get_hotels_info(state: TravelPartnerState) -> TravelPartnerState:
    destination = state.get("trip_details", {}).get("destination") or state["user_query"]
    preferences = state.get("trip_details", {}).get("preferences", "")
    hotel_query = f"Best hotels in {destination}"
    if preferences:
        hotel_query += f" for {preferences}"

    hotel_options = tavily_search(hotel_query)
    message_text = (
        f"Fetched {len(hotel_options)} hotel option(s) for {destination}."
        if hotel_options
        else f"No hotel options found for {destination}."
    )

    return merge_state(
        state,
        {
            "hotel_options": hotel_options,
            "messages": [AIMessage(content=message_text)],
        },
    )


def get_itenary_info(state: TravelPartnerState) -> TravelPartnerState:
    prompt = f"""
Create a travel itinerary based on the user query, flight options, and hotel options.
The itinerary should include:
- A summary of the trip plan
- Recommended flight option
- Recommended hotel option
- A day-by-day plan if travel dates are available
- Notes for the traveler based on preferences and budget

User request:
{state['user_query']}

Trip details:
{json.dumps(state.get('trip_details', {}), indent=2)}

Flight options:
{format_flight_options(state.get('flight_options', []))}

Hotel options:
{format_hotel_options(state.get('hotel_options', []))}
"""

    response = agent_llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])

    return merge_state(
        state,
        {
            "itinerary": response.content,
            "messages": [response],
            "conversation_history": [response],
            "llm_calls": 1,
        },
    )


def final_agent(state: TravelPartnerState) -> TravelPartnerState:
    final_prompt = f"""
You are an expert travel planner. Create the final response using the available trip details, flight options, hotel options, and itinerary.
Respond clearly and with practical recommendations.

User request:
{state['user_query']}

Trip details:
{json.dumps(state.get('trip_details', {}), indent=2)}

Flight options:
{format_flight_options(state.get('flight_options', []))}

Hotel options:
{format_hotel_options(state.get('hotel_options', []))}

Itinerary:
{state.get('itinerary', '')}
"""

    response = agent_llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=final_prompt),
    ])

    return merge_state(
        state,
        {
            "messages": [response],
            "conversation_history": [response],
            "llm_calls": 1,
        },
    )


graph = StateGraph(TravelPartnerState)

graph.add_node("parse_trip_details", parse_trip_details)
graph.add_node("flight_agent", get_flight_info)
graph.add_node("hotel_agent", get_hotels_info)
graph.add_node("itinerary_agent", get_itenary_info)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "parse_trip_details")
graph.add_edge("parse_trip_details", "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)

app = graph.compile()


if __name__ == "__main__":
    validate_environment()

    name = input("Enter your name: ")
    config = {
        "configurable": {
            "thread_id": name
        }
    }

    memory = MongoMemory(uri=os.getenv("MONGODB_URI"), db_name=os.getenv("MONGODB_DB", "travel_planner_agent"))
    stored_state = memory.load(name) if name else {}

    user_input = input("Enter travel request: ")
    conversation_history = stored_state.get("conversation_history", [])
    conversation_history.append(HumanMessage(content=user_input))

    initial_state = {
        "messages": [],
        "conversation_history": conversation_history,
        "user_query": user_input,
        "trip_details": stored_state.get("trip_details", {}),
        "flight_options": stored_state.get("flight_options", []),
        "hotel_options": stored_state.get("hotel_options", []),
        "itinerary": stored_state.get("itinerary", ""),
        "llm_calls": stored_state.get("llm_calls", 0),
        "errors": stored_state.get("errors", []),
    }

    result = app.invoke(initial_state, config=config)
    memory.save(name, result)

    print("\nFINAL RESPONSE:\n")
    for msg in result.get("messages", []):
        print(msg.content)

    if errors := result.get("errors"):
        print("\nWARNINGS:")
        for error in errors:
            print(f"- {error}")
