from memory import supervisor_collection
from datetime import datetime


def load_messages(user_id: str):

    doc = supervisor_collection.find_one(
        {"user_id": user_id}
    )

    if doc:
        return doc.get("messages", [])

    return []


def save_messages(
    user_id: str,
    messages: list
):

    supervisor_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "messages": messages
            }
        },
        upsert=True
    )


def save_conversation(
    user_id: str,
    user_message: str,
    ai_response: str
):

    messages = load_messages(user_id)

    now = datetime.utcnow().isoformat() + 'Z'

    messages.append({
        "type": "human",
        "content": user_message,
        "created_at": now
    })

    messages.append({
        "type": "ai",
        "content": ai_response,
        "created_at": now
    })

    messages = messages[-100:]

    save_messages(
        user_id,
        messages
    )