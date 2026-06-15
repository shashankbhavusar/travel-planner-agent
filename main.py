from supervisor import general_chat, supervisor
from travel_agent import travel_agent


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

        response = travel_agent(
            user_id=user_id,
            message=user_message
        )

        print(response)

        if response.get("trip_finished"):

            session["active_agent"] = None

    else:

        answer = general_chat(
            user_id,
            user_message
        )

        print(answer)

    sessions[user_id] = session