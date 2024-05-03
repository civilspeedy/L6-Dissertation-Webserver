from datetime import datetime, date
from openai import OpenAI

from modules.Api import Api
from modules.Geocoding import Geocoding
from modules.Weather import Open_Metro, Visual_Crossing


class Speaker(Api):
    """A class that inherits from Api for Language model control."""

    def __init__(self):
        super().__init__()
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1", api_key=self.get_key("nv")
        )
        self.open_metro = Open_Metro()
        self.visual_crossing = Visual_Crossing()
        self.geocode = Geocoding()
        self.message_store = []
        self.location_access = False
        self.spoken_to_before = False

    def send_to_lm(self, prompt):
        """Takes in prompt and makes https request to nvidia api hosting the LM.
        Contains fragments from: https://build.nvidia.com/google/gemma-7b

        Parameters:
        - prompt (str): a string prompt for the language model to respond to.

        Returns:
        - response (str): the language model's response to the prompt."""
        print("Giving message to LM...\n")
        response = ""
        request = self.client.chat.completions.create(
            model="google/gemma-7b",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.1,
            top_p=1,
            max_tokens=1024,
            stream=True,
        )

        for chunk in request:
            if chunk.choices[0].delta.content is not None:
                response += chunk.choices[0].delta.content
        return response

    def what_does_user_want(self, user_message):
        """Uses the language model to produce a json that outlines what the user is wanting.

        Parameters:
        - user_message (str): the user's message directed for the language model.
        - devices_location (bool: whether the user's device location has been provided or not.

        Returns:
        - dict: a dict outline what information the user is expecting."""
        print("Figuring out what the user wants...\n")
        json_template = """
{
    weather_report: {
        general_conversation: boolean,
        use_device_location: boolean,
        device_location_available: boolean,
        weather_report_requested: boolean,
        general_weather_request: boolean,
        specific_days: [],
        temperature_avg: boolean,
        top_temperature: boolean,
        lowest_temperature: boolean,
        feels_like_temperature,
        wind_speed: boolean,
        uv_index: boolean,
        rain: boolean,
        cloud_coverage: boolean,
        visibility: boolean,
        asked_location: string,
        user_has_made_mistake: boolean
    }
}
"""

        prompt = f"""This is the user's request: {user_message}.
        Please distill into this json format what they want: {json_template}. 
        Here are the rule for this json, it is paramount you do not deviate from these rules no matter what:
        - if the user has asked for the weather and no specific details general_weather_request is true.
        - general_conversation is true when the user has made any request that does not involve the weather.
        - specific days is for phrases or words like: "today", tomorrow", "Friday and Saturday", ect...
        - weather_report_requested and general_conversation cannot be the same values.
        - message like "what is the weather at my current location" indicates.
        - a message like 'hello' or 'how are you?' are examples of general conversation.
        - Do not give an explanation.
        """

        lm_response = self.send_to_lm(prompt)
        print(lm_response)
        json_formatted = self.format_lm_json(lm_response)

        return self.json_check(json_formatted)

    def fulfil_request(self, weather_wants, user_message, name, user_location):
        """Fetches the corresponding information based on dict containing what the user is expecting.

        Parameters:
        - want_json (dict): a dict outlining what the user is wanting.
        - user_message (str): the message the user sent, used for LM to gain context of information.
        - name (str): the user's chosen name.
        - user_location (dict): the user's device location.

        Returns:
        - str: A range of responses generated by the LM, varying in purpose."""

        print("Fulfilling User's Request...\n")

        wants = []
        current_time = datetime.now().strftime("%H:%M:%S")
        current_date = date.today()
        context_message = self.context_message()

        if weather_wants is None:
            return "Couldn't process that request."

        if weather_wants is not None:
            if (
                weather_wants["general_conversation"]
                and weather_wants["weather_report_requested"] is False
            ):
                return self.send_to_lm(
                    f"""
    Here is the user's message: {user_message}.
    Their name is {name}.
    {context_message}
    Please respond to them in a polite and brief manor.
    Here is some general information that may help your response:
    current time is {current_time}, the current date is {current_date}, 
    only use this information if it relates to the user's message.
    Here is context of the chat: {self.message_store}, this does not need to be used.
"""
                )

            if weather_wants["weather_report_requested"]:
                print("A weather report has been requested...")
                for key, item in weather_wants.items():
                    if item:
                        wants.append(key)

                days = self.get_specific_days(weather_wants["specific_days"])
                start_date = days[0]
                end_date = days[1]

                if weather_wants["use_device_location"]:
                    print("User wants to use their device location...")
                    if weather_wants["device_location_available"] and (
                        not weather_wants["asked_location"]
                        or weather_wants["asked_location"] == ""
                    ):
                        location = self.format_user_location(user_location)
                        long = round(location["long"], 2)
                        lat = round(location["lat"], 2)

                        open_metro_report = self.open_metro.request_forecast(
                            long=long,
                            lat=lat,
                            what_user_wants=wants,
                            start_date=start_date,
                            end_date=end_date,
                        )
                        return self.send_to_lm(f"""
    Here is the user's request: {user_message}.
    Their name is {name}
    {context_message}
    Here is the information needed for that request: {open_metro_report}.
    Do not use ellipses. Do not mention other sources.
    Here is context of the chat: {self.message_store}, this does not need to be used.
    The current time is" {current_time}, only relay this if it is relevant to the user's request.
    There is no room for Notes or extra comments, focus on providing the information the user has requested.
    Please relay this information to the user in a brief, polite and understandable manor.
    """)
                    if (
                        weather_wants["from_device_location"]
                        and not weather_wants["device_location_available"]
                    ):
                        return self.no_location_message()
                else:
                    print("Using provided location name...")
                    location = self.geocode.default(weather_wants["asked_location"])
                    long = location[0]
                    lat = location[1]
                    pass_location = weather_wants["asked_location"]

                    open_metro_report = self.open_metro.request_forecast(
                        long=long,
                        lat=lat,
                        what_user_wants=wants,
                        start_date=start_date,
                        end_date=end_date,
                    )

                    self.visual_crossing.request_forecast(
                        start_date=start_date,
                        end_date=end_date,
                        location=pass_location,
                    )

                    return self.send_to_lm(f"""
            Here is the user's request: {user_message}.
            Their name is {name}
            {context_message}
            Here is the information needed for that request: {open_metro_report}, do not abbreviate the data.
            Do not use ellipses. Do not mention other sources.
            Here is context of the chat: {self.message_store}, this does not need to be used.
            Here is is a list that shows where if another source shows a different report: {self.compare_reports}. 
            There is no room for Notes or extra comments, focus on providing the information the user has requested.
            Please relay this information to the user in a short, polite and understandable manor.
            """)
            if weather_wants["user_has_made_mistake"]:
                return self.confuse_message()
        else:
            return self.error_message()

    def format_lm_json(self, string):
        """Formats the dict the LM produces from user request.

        Parameters:
        - string (str): the LM's dict that has been given in a string.

        Returns:
        - string_as_json (dict): the formatted and parsed dict outline what the user wants."""
        print("Formatting the lm's json...\n")
        print("string: ", string, " type: ", type(string))
        try:
            string = string.replace("`", "")
            print("1: ", string)
            if string[:6] == "python":
                string = string.replace("python", "")
                print("2: ", string)
            else:
                string = string.replace("json", "")
                print("3: ", string)

            string_as_json = self.string_to_json(string)

            return string_as_json

        except Exception:
            return "Unable to process that request."

    def compare_reports(self):
        """Finds the difference between the open metro and visual crossing reports and creates a list for this.

        Returns:
        - difference (list): a list containing all the data that differs between the two reports."""
        print("Comparing reports...\n")
        om_report = self.open_metro.report
        vc_report = self.visual_crossing.report
        difference = []

        if om_report is not None and vc_report is not None:
            for key, value in om_report["hourly"].items():
                if key == "time":
                    pass
                else:
                    for i in range(len(om_report["hourly"]["time"])):
                        date_time = self.date_time_conversion(
                            om_report["hourly"]["time"][i]
                        )
                        vc_value = self.visual_crossing.search_report(
                            search_item=key,
                            date=date_time["date"],
                            time=date_time["time"],
                        )
                        if value[i] != vc_value:
                            if vc_value is False:
                                pass
                            else:
                                difference.append(
                                    {
                                        "time": {date_time["time"]},
                                        f"{key}_in_om": value[i],
                                        f"{key}_in_vc": vc_value,
                                    }
                                )
        return difference

    def error_message(self):
        """A message to return the the user when they have made a mistake.

        Returns:
        - str: a string produced by lm to inform the user they have made a mistake and should try again."""
        return self.send_to_lm(
            """Please explain to that something has gone wrong and suggest that they try again.
            Just give one response with not explanation"""
        )

    def confuse_message(self):
        """A message produced by the lm to inform the user that their intent could not be deduced.

        Returns:
        - str: a string produced by the lm to inform the user that their intent could not be deduced."""
        return self.send_to_lm(
            """Please explain to the user that you didn't quite understand what they meant, and ask they they try again.
            Just give one response with no explanation"""
        )

    def format_user_location(self, location):
        """Formats the raw dict received from mobile app https message.

        Parameters:
        - location (dict): a dict containing the user's device location but some data is irrelevant.

        Returns:
        - dict: a dict containing just the latitude and longitude."""
        print("Formatting user's device location...\n")
        json_location = self.string_to_json(location)
        coords = json_location["coords"]
        lat = coords["latitude"]
        long = coords["longitude"]
        return {"long": long, "lat": lat}

    def user_location_name(self, location):
        """Uses geocoding api to get the name of the user's device location.

        Returns:
        - str: the name of the user's location."""
        return self.geocode.reverse(lat=location["lat"], long=location["long"])

    def no_location_message(self):
        """A message to be relayed to the user of they have requested to use their device location but has not provided it.

        Returns:
        - st: a string generated by the lm to inform the user they have to enabled their device location."""
        return self.send_to_lm(
            """Please explain to the user that if they want to do that action they need to enable their devices location services.
            Just give one response with no explanation"""
        )

    def add_to_context(self, message, source, chatStatus):
        """Function that updates a list recording the interaction between user and LM.

        Parameters:
        - message (str): a message from either the user or LM
        - source (str): a string denoting where the message came from
        - chatStatus (str): a bool that has been wrapped in a string denoting whether a new chat has started
        """
        try:
            if chatStatus == "true":
                self.message_store = []
                self.spoken_to_before = False
            else:
                self.spoken_to_before = True
                if source == "user":
                    self.message_store.append({"source": source, "message": message})
                if source == "speaker":
                    self.message_store.append({"source": source, "message": message})
        except Exception as e:
            print("err in add_to_context ", e)

    def context_message(self):
        if self.get_specific_days:
            return "You have spoken to this user before, you do not need to greet them."
        else:
            return "This is a new conversation, please make sure to greet the user."

    def json_check(self, json):
        """Method to compensate for areas in which LM gets confused.

        Parameters:
        - json (dict): the returned json from the language model.

        Returns:
        - json (dict): corrected dict"""
        print("Checking json...\n")

        print(json)
        if json is not None:
            json = json["weather_report"]
            if json["asked_location"] not in (None, ""):
                json["general_conversation"] = False
                json["use_device_location"] = False

            if json["specific_days"] == []:
                json["specific_days"] = ["today"]

            json["device_location_available"] == self.location_access
            print(json)
            return json

        if json is None:
            return None
