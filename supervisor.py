from typing import Optional, TypedDict
import json
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv
    
from langchain_core.messages import (
    HumanMessage,
    AIMessage
)

from supervisor_memory import (
    load_messages,
    save_messages
)

load_dotenv()

class SupervisorState(TypedDict):
    user_id: str
    user_message: str
    active_agent: Optional[str]
    response: str

llm = ChatGroq(
    model="llama-3.3-70b-versatile"
)

def classify_intent(user_message: str):

    prompt = f"""
Classify the user message.

Return JSON only.

Schema:
{{
    "intent": "travel" | "general"
}}

User Message:
{user_message}
"""

    result = llm.invoke([
        HumanMessage(content=prompt)
    ])

    content = result.content.strip()

    if content.startswith("```json"):
        content = content[7:]

    if content.endswith("```"):
        content = content[:-3]

    try:
        return json.loads(content)
    except:
        return {"intent": "general"}


def general_chat(
    user_id: str,
    user_message: str
):

    messages = load_messages(user_id)

    history = []

    for msg in messages:

        if msg["type"] == "human":

            history.append(
                HumanMessage(
                    content=msg["content"]
                )
            )

        elif msg["type"] == "ai":

            history.append(
                AIMessage(
                    content=msg["content"]
                )
            )

    history = history[-20:]
    history.append(
        HumanMessage(
            content=user_message
        )
    )

    response = llm.invoke(history)

    messages.append(
        {
            "type": "human",
            "content": user_message
        }
    )

    messages.append(
        {
            "type": "ai",
            "content": response.content
        }
    )

    save_messages(
        user_id,
        messages
    )

    return response.content

def supervisor(user_message, session):

    active_agent = session.get("active_agent")

    # Travel session already running
    if active_agent == "travel":
        return {
            "route": "travel"
        }

    intent = classify_intent(user_message)

    if intent["intent"] == "travel":

        session["active_agent"] = "travel"

        return {
            "route": "travel"
        }

    return {
        "route": "general"
    }

# sessions = {}

# while True:

#     user_id = input("User ID: ")

#     user_message = input("Message: ")

#     session = sessions.get(
#         user_id,
#         {
#             "active_agent": None
#         }
#     )

#     decision = supervisor(
#         user_message,
#         session
#     )

#     if decision["route"] == "travel":

#         response = travel_agent(
#             user_id=user_id,
#             message=user_message
#         )

#         print(response)

#         if response.get("trip_finished"):

#             session["active_agent"] = None

#     else:

#         answer = general_chat(user_message)

#         print(answer)

#     sessions[user_id] = session