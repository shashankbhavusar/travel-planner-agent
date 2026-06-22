from agent.supervisor import general_chat, supervisor
from agent.travel_agent import travel_agent
from agent.supervisor_memory import save_conversation

sessions = {}
user_id = input("User ID: ")

while True:


    user_message = input("Message: ")

    session = sessions.get(
        user_id,
        {
            "active_agent": None
        }
    )

    decision = supervisor(
        user_message,
        session
    )

    if decision["route"] == "travel":

        result = travel_agent(
            user_id=user_id,
            message=user_message
        )

        save_conversation(
            user_id,
            user_message,
            result["response"]
        )

        # return result["response"]

        print(result)

        if result.get("trip_finished"):
            session["active_agent"] = None

    else:

        answer = general_chat(
            user_id,
            user_message
        )

        save_conversation(
            user_id,
            user_message,
            answer
        )

        # return answer

        print(answer)

    sessions[user_id] = session