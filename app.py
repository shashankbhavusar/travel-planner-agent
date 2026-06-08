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
from IPython.display import Image, display

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

    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state.get("conversation_history", [])) + [HumanMessage(content=prompt)]
    response = agent_llm.invoke(messages)

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

    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state.get("conversation_history", [])) + [HumanMessage(content=prompt)]
    response = agent_llm.invoke(messages)

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

    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state.get("conversation_history", [])) + [HumanMessage(content=final_prompt)]
    response = agent_llm.invoke(messages)

    return merge_state(
        state,
        {
            "messages": [response],
            "conversation_history": [response],
            "llm_calls": 1,
        },
    )


def intent_and_clarify(state: TravelPartnerState) -> TravelPartnerState:
    """Determine whether the user's query is a trip-planning request and whether clarification is needed.

    Returns partial state with:
    - `intent`: bool (is trip planning)
    - `missing`: list of missing fields
    - `clarify_question`: str if clarification is required
    - appends an assistant `AIMessage` to `messages` and `conversation_history` when asking for clarification
    """

    prompt = f"""
You are an intent classifier. Determine if the user's request is asking for travel planning help.

RULES:
1. If the query is NOT about travel/trip planning at all, set is_trip=false and provide a helpful message in 'clarify' explaining you only help with trip planning.
2. If the query IS about travel but is missing critical information (destination, departure_date, or return_date), set a 'clarify' message asking for those missing fields.
3. Only set clarify to an empty string if is_trip=true AND all critical fields are provided or can be inferred.

Return only valid JSON with keys: is_trip (true/false), missing (list of missing fields among: destination, departure_date, return_date, season, travelers), clarify (a clarifying question/message, or empty string).

User request:
{state.get('user_query', '')}
"""

    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state.get("conversation_history", [])) + [HumanMessage(content=prompt)]
    response = agent_llm.invoke(messages)

    parsed = safe_parse_json(response.content)
    is_trip = bool(parsed.get("is_trip")) if isinstance(parsed, dict) else False
    missing = parsed.get("missing") if isinstance(parsed, dict) else []
    clarify = parsed.get("clarify", "") if isinstance(parsed, dict) else ""

    # Enforce clarify logic: if not a trip query, always provide a clarify message
    if not is_trip and not clarify:
        clarify = "I can only help you plan trips. Please tell me about your trip: destination, travel dates, number of travelers, and any preferences."

    # If trip query but missing critical fields, ensure we ask for them
    if is_trip and not clarify and (not missing or any(f in missing for f in ["destination", "departure_date", "return_date"])):
        critical_missing = [f for f in missing if f in ["destination", "departure_date", "return_date"]]
        if critical_missing:
            clarify = f"To help plan your trip, I need: {', '.join(critical_missing)}. Could you provide these details?"

    messages = []
    conv = []
    if clarify:
        ask = AIMessage(content=clarify)
        messages.append(ask)
        conv.append(ask)
    else:
        messages.append(AIMessage(content="Proceeding with trip planning."))

    return merge_state(
        state,
        {
            "intent": is_trip,
            "missing": missing or [],
            "clarify_question": clarify,
            "messages": messages,
            "conversation_history": conv,
            "llm_calls": 1,
        },
    )


def decide_intent(state: TravelPartnerState) -> str:
    
    if (state.intent is False) or state.get("clarify_question"):
        return "go_back_to_user"
    return "go_to_trip_planning"

graph = StateGraph(TravelPartnerState)

graph.add_node("intent_node", intent_and_clarify)
graph.add_node("parse_trip_details", parse_trip_details)
# graph.add_node("validate_trip_details", validate_trip_details)
graph.add_node("flight_agent", get_flight_info)
graph.add_node("hotel_agent", get_hotels_info)
graph.add_node("itinerary_agent", get_itenary_info)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "intent_node")
graph.add_conditional_edges("intent_node", decide_intent, {
    "go_back_to_user": "intent_node",
    "go_to_trip_planning": "parse_trip_details",
}) 
graph.add_edge("parse_trip_details", "flight_agent")
# graph.add_conditional_edges("validate_trip_details", _validate_trip_route)
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)

app = graph.compile()

# display(Image(app.get_graph().draw_mermaid_png()))
with open("graph.png", "wb") as file:
    file.write(app.get_graph().draw_mermaid_png())

if __name__ == "__main__":

    name = input("Enter your name: ")
    config = {"configurable": {"thread_id": name}}

    memory = MongoMemory(uri=os.getenv("MONGODB_URI"), db_name=os.getenv("MONGODB_DB", "travel_planner_agent"))
    stored_state = memory.load(name) if name else {}

    # Load previous conversation history (deserialized by MongoMemory)
    conversation_history = list(stored_state.get("conversation_history", []))
    print(f"Loaded {len(conversation_history)} prior message(s) for '{name}'.")

    while True:
        user_input = input("\nEnter travel request (or type 'quit' to exit): ")
        if user_input.strip().lower() in ("quit", "exit"):
            print("Goodbye.")
            break

        # Append user's new message to conversation history
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

