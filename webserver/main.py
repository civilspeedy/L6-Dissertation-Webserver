from flask import Flask, jsonify, make_response, request


from modules.Speaker import Speaker


app = Flask(__name__)
speaker = Speaker()


@app.route("/communicate", methods=["POST", "GET"])
def communicate():
    """The function for facilitating communication of the user and language model."""
    isNewChat = request.args.get("chatStatus")

    speaker.check_chat_status(isNewChat)

    message = request.args.get("message")
    print("User:", message)

    name = request.args.get("name")

    location = request.args.get("location")
    speaker.location_access = check_device_location(location)

    response = speaker.fulfil_request(
        weather_wants=speaker.what_does_user_want(message),
        user_message=message,
        name=name,
        user_location=location,
    )

    speaker.add_to_context(message=message, source="user", name=name)

    speaker.add_to_context(message=response, source="speaker", name="gemma-7b")

    print("LM:", response)
    return make_response(jsonify({"response": response}, 200))


def check_device_location(location):
    """Checks whether the user's device location has been provided.

    Parameters:
    - location (string): will either have a json wrapped in a string containing the user's device location or read as 'None'."

    Returns:
    - bool: a bool relating to whether the device location has been provided or not."""
    if location == "None":
        return False
    else:
        return True


def run_local():
    """Set flask up to run on local host."""
    app.run(debug=True)


def run_on_network():
    """Sets flask up to run on open port"""
    app.run(debug=True, host="0.0.0.0")


if __name__ == "__main__":
    run_on_network()
