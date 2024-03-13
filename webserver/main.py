from flask import Flask, jsonify, make_response, request
from modules.Speaker import Speaker

app = Flask(__name__)


@app.route("/")
def hello():
    return "Test Message"


@app.route("/api/userMessage", methods=["GET", "POST"])
def user_message():
    string = request.args.get("string")
    print(string)
    if string == "":
        return make_response(jsonify({"result": "no input"}, 400))
    return make_response(jsonify({"result": "ok"}, 200))


if __name__ == "__main__":
    speaker = Speaker()
    speaker.talk()
