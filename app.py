import os
from typing import TypedDict, Annotated
import operator

# import psycopg
from langgraph.graph import StateGraph, START, END
# from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)

from langchain_groq import ChatGroq

from agent.tools.tavily import tavily_search
from agent.tools.flight import search_flights
from dotenv import load_dotenv
load_dotenv()

agent_llm = ChatGroq(
    model="llama-3.3-70b-versatile"
)

class TravelPartnerState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    flight_info: str
    tavily_info: str
    user_query: str
    itinerary: str
    llm_calls: int

def get_flight_info(state:TravelPartnerState) -> TravelPartnerState:
    query = state["user_query"]
    flight_data = search_flights(query)
    return {
        "flight_info": flight_data,
        "messages": [AIMessage(content=f"Flight info is fetched successfully")]
    }

def get_hotels_info(state:TravelPartnerState) -> TravelPartnerState:
    query = f"Best hotels for {state['user_query']}"
    hotels_data = tavily_search(query)
    return {
        "tavily_info": hotels_data,
        "messages": [AIMessage(content=f"Hotels info is fetched successfully")]
    }

def get_itenary_info(state:TravelPartnerState) -> TravelPartnerState:
    prompt = f"""
    Create a travel itinerary.
    User Query:
    {state['user_query']}

    Flight Results:
    {state['flight_info']}

    Hotel Results:
    {state['tavily_info']}
    """
    
    response = agent_llm.invoke([
        SystemMessage(
            content="You are an expert travel planner"
        ),
        HumanMessage(content=prompt)
    ])

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

def final_agent(state: TravelPartnerState) -> TravelPartnerState:

    final_prompt = f"""
    Generate final travel response.

    Flights:
    {state['flight_info']}

    Hotels:
    {state['tavily_info']}

    Itinerary:
    {state['itinerary']}
    """

    response = agent_llm.invoke([
        HumanMessage(content=final_prompt)
    ])

    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

graph = StateGraph(TravelPartnerState)

graph.add_node("flight_agent", get_flight_info)
graph.add_node("hotel_agent", get_hotels_info)
graph.add_node("itinerary_agent", get_itenary_info)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)

app = graph.compile()


if __name__ == "__main__":
    name = input("Enter your name: ")
    config = {
        "configurable": {
            "thread_id": name
        }
    }

    user_input = input("Enter travel request: ")

    result = app.invoke(
        {
            "messages": [
                HumanMessage(content=user_input)
            ],
            "flight_info": "",
            "tavily_info": "",
            "user_query": user_input,
            "itinerary": "",
            "llm_calls": 0
        },
        config=config
    )

    print("\nFINAL RESPONSE:\n")

    for msg in result["messages"]:
        print(msg.content)
