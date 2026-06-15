from memory import supervisor_collection


def load_messages(user_id: str):

    doc = supervisor_collection.find_one(
        {"user_id": user_id}
    )

    if doc:
        return doc.get("messages", [])

    return []


def save_messages(user_id: str, messages):

    supervisor_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "messages": messages
            }
        },
        upsert=True
    )