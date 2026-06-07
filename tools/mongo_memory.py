import os
from datetime import datetime
from typing import Any

from langchain_core.messages import AnyMessage, HumanMessage, AIMessage, SystemMessage

try:
    from pymongo import MongoClient  # type: ignore[import]
except ImportError:  # pragma: no cover
    MongoClient = None


def _serialize_messages(messages: list[AnyMessage]) -> list[dict[str, str]]:
    serialized = []
    for message in messages:
        message_type = message.__class__.__name__
        serialized.append({
            "type": message_type,
            "content": message.content,
        })
    return serialized


def _deserialize_messages(items: list[dict[str, str]]) -> list[AnyMessage]:
    deserialized: list[AnyMessage] = []
    for item in items:
        if item["type"] == "HumanMessage":
            deserialized.append(HumanMessage(content=item["content"]))
        elif item["type"] == "AIMessage":
            deserialized.append(AIMessage(content=item["content"]))
        elif item["type"] == "SystemMessage":
            deserialized.append(SystemMessage(content=item["content"]))
        else:
            deserialized.append(HumanMessage(content=item["content"]))
    return deserialized


class MongoMemory:
    def __init__(self, uri: str | None = None, db_name: str = "travel-planer-agent", collection_name: str = "messages"):
        self.uri = uri or os.getenv("MONGODB_URI")
        self.db_name = db_name or os.getenv("MONGODB_DB", "travel-planer-agent")
        self.collection_name = collection_name
        self.enabled = bool(self.uri)

        if self.enabled and MongoClient is None:
            raise RuntimeError("pymongo is required for MongoDB memory support. Install it with 'pip install pymongo'.")

        self.client = MongoClient(self.uri) if self.enabled else None
        self.collection = self.client[self.db_name][self.collection_name] if self.enabled else None

    def load(self, thread_id: str) -> dict[str, Any]:
        if not self.enabled:
            return {}

        document = self.collection.find_one({"thread_id": thread_id})
        if not document:
            return {}

        state = document.get("state", {})
        if "conversation_history" in state:
            state["conversation_history"] = _deserialize_messages(state["conversation_history"])
        return state

    def save(self, thread_id: str, state: dict[str, Any]) -> None:
        if not self.enabled:
            return

        payload = {
            "thread_id": thread_id,
            "updated_at": datetime.utcnow(),
            "state": {
                "user_query": state.get("user_query", ""),
                "trip_details": state.get("trip_details", {}),
                "flight_options": state.get("flight_options", []),
                "hotel_options": state.get("hotel_options", []),
                "itinerary": state.get("itinerary", ""),
                "llm_calls": state.get("llm_calls", 0),
                "errors": state.get("errors", []),
                "conversation_history": _serialize_messages(state.get("conversation_history", [])),
            },
        }
        self.collection.update_one({"thread_id": thread_id}, {"$set": payload}, upsert=True)
