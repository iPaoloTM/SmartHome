from flask import Flask, request, jsonify
from flask_cors import CORS
import random
import os
import pandas as pd
import openai
import time
import csv
import tiktoken
import pymongo
import requests
from bson.objectid import ObjectId
from llama_index.core.tools import FunctionTool
from llama_index.core.tools import QueryEngineTool
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import ReActAgent
from llama_index.core.callbacks import CallbackManager, LlamaDebugHandler, TokenCountingHandler
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

mongo_client = pymongo.MongoClient("mongodb+srv://admin:admin@cluster1.y61e7.mongodb.net/?retryWrites=true&w=majority&appName=Cluster1")
db = mongo_client["db"]

# Ensure the environment variable for OpenAI API key is set correctly
os.environ["OPENAI_API_KEY"] = "<INSERT_YOUR_KEY>"

# Load data and setup tools
#data_file = "./energy_readings.csv"
#if not os.path.exists(data_file):
#    raise FileNotFoundError(f"Required data file not found: {data_file}")

df = pd.read_csv(data_file)

# Callback manager and debug handlers
llama_debug = LlamaDebugHandler(print_trace_on_end=True)
token_counter = TokenCountingHandler(tokenizer=tiktoken.encoding_for_model("gpt-4").encode)
callback_manager = CallbackManager([llama_debug, token_counter])

# LLM configuration
llm = OpenAI(model="gpt-4")

# System prompt for the agent
SYST_PROMPT = '''
You are a helpful smart home assistant, based in Linz, Upper Austria, that provides information based on sensor data, makes sense out of it, and suggests actions to save energy if possible.
When asked for sensor readings, provide data from every tool you have, including energy and air quality.

Your goal is to suggest tips on how to save energy based on external conditions.
For example:
- get the data  about temperature to check the AC is really needed
- check if there is sun in order to turn on Washing machine or Drying to use solar energy
- make sure lights are not consuming too much if there is still sunlight
And other behavioral changes are up to you, just always inform the user

Only give 1 tips at a time, based on current readings about energy and environmental data.
Tips should vary from:
- lowering AC (based on outside temperature data)
- open the window (based on outdoor data)
- turn on washing machine when there is sun (if solar panel are there)
- turn off the most energy intensive household appliance
- be creative!
'''

@app.route('/get_weather_forecast/<city>', methods=['GET'])
def get_weather_forecast(city):
    """
    Retrieves the 16-day daily weather forecast for a given city using the Weatherbit API.

    Args:
        city (str): The city for which to retrieve the weather forecast (e.g., "Linz,Austria").
        api_key (str): Your Weatherbit API key.

    Returns:
        dict: A dictionary containing the weather forecast data.
    """

    url = f"https://api.weatherbit.io/v2.0/forecast/daily?city={city}&key=326567c425e54f6f9c2b64bbcacc162b"

    try:
        # Send GET request to the Weatherbit API
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad status codes

        # Parse the JSON response
        weather_data = response.json()

        # Extract relevant information
        city_name = weather_data.get("city_name")
        forecast_data = weather_data.get("data", [])

        # Format the forecast data
        formatted_forecast = {
            "city": city_name,
            "forecasts": []
        }

        for day in forecast_data:
            daily_forecast = {
                "date": day.get("valid_date"),
                "temp": day.get("temp"),
                "max_temp": day.get("max_temp"),
                "min_temp": day.get("min_temp"),
                "weather_description": day.get("weather", {}).get("description"),
                "wind_speed": day.get("wind_spd"),
                "precipitation": day.get("precip"),
                "humidity": day.get("rh"),
                "uv_index": day.get("uv"),
                "sunrise": day.get("sunrise_ts"),
                "sunset": day.get("sunset_ts")
            }
            formatted_forecast["forecasts"].append(daily_forecast)

        return formatted_forecast

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching weather data: {e}")
        return None


@app.route('/get_roof_data', methods=['GET'])
def get_roof_data():
    """
    API endpoint to retrieve data from MongoDB roof_data collections.
    Roof data includes data from solar radiation, wind speed, temperature, etc.
    """

    try:
        collection = db["roof_data"]

        # Get distinct measurements
        measurements = collection.distinct("measurement")

        # Initialize result dictionary
        result = {}

        for measurement in measurements:
            # Find all unique values and units for the current measurement
            values_cursor = collection.find({"measurement": measurement}, {"value": 1, "_id": 0})
            units_doc = collection.find_one({"measurement": measurement}, {"units": 1, "_id": 0})

            # Extract values and units
            value_list = [doc["value"] for doc in values_cursor]
            # Limit the list to at most 10 elements
            value_list = value_list[:10]
            unit = units_doc.get("units", "Unknown") if units_doc else "Unknown"

            # Add to result dictionary
            result[measurement] = {
                "values": value_list,
                "unit": unit
            }

        if not result:
            return jsonify({"message": "No data found"}), 404

        print(result)

        return str(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/get_room_data', methods=['GET'])
def get_room_data():
    """
    API endpoint to retrieve all documents from the MongoDB room_data collection.
    Room data includes data from air pressure, air quality, percentage of O2, CO2, CO, NO2, pressure, sound etc
    """

    try:
        # Select the collection
        collection = db["room_data"]

        # Retrieve all documents from the collection
        documents = list(collection.find({}, {'_id': 0}))  # Exclude the MongoDB _id field from the output

        if not documents:
            return jsonify({"message": "No data found"}), 404

        # Initialize the result dictionary
        result = {}

        for doc in documents:
            # Use DeviceID as the key for each room
            room_id = doc.get("DeviceID")

            # Initialize measurement dictionary for the current room
            room_data = {}
            count=0

            for key, value in doc.items():
                if count >= 10:
                    break
                if key != "DeviceID" and key != "Status" and key != "TypPS" and key != "timestamp":
                    # Store the measurements and their values
                    room_data[key] = value
                    count += 1

            # Add to result dictionary
            result[room_id] = room_data

        print(result)

        return str(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_energy_data', methods=['GET'])
def get_energy_data():
    """
    API endpoint to retrieve time series measurements from MongoDB energy_data collection.
    """

    try:
        # Select the collection
        collection = db["energy_data"]

        # Retrieve all documents from the collection
        documents = list(collection.find({}, {'_id': 0}))  # Exclude the MongoDB _id field from the output

        if not documents:
            return jsonify({"message": "No data found"}), 404

        # Initialize the result dictionary
        result = {}

        for doc in documents:
            # Extract name and measurements from the document
            name = doc.get("name")
            measurements = doc.get("consumption", [])

            # Store the measurements in the result dictionary
            result[name] = {
                "consumption": measurements
            }

        print(result)

        return str(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/chat', methods=['POST'])
def chat():
    query = request.form.get('query')
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400

    try:
        # Start timing the response time
        start_time = time.time()

        # Chat with the agent
        response = agent.chat(query)

        # End timing and calculate elapsed time
        elapsed_time = round(time.time() - start_time, 2)

        return jsonify({
            "result": response.response,
            "tokens": token_counter.total_llm_token_count,
            "time": elapsed_time
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/signup', methods=['POST'])
def signup():
    collection = db['subscribers']
    try:
        # Get the email from the request
        data = request.get_json()
        email = data.get('email')

        # Check if email was provided
        if not email:
            return jsonify({'error': 'Email is required'}), 400

        # Insert the email into MongoDB
        result = collection.insert_one({'email': email})

        # Return success response
        return jsonify({'message': 'Signup successful', 'inserted_id': str(result.inserted_id)}), 200

    except Exception as e:
        # Return error response
        return jsonify({'error': str(e)}), 500

# Tool setup
get_weather_forecast_tool = FunctionTool.from_defaults(fn=get_weather_forecast)
get_roof_data_tool = FunctionTool.from_defaults(fn=get_roof_data)
get_room_data_tool = FunctionTool.from_defaults(fn=get_room_data)
get_energy_data_tool = FunctionTool.from_defaults(fn=get_energy_data)

# ReAct agent setup with the sensor tool and the new RAG tool
agent = ReActAgent.from_tools(
    name="SmartHomeAssistant",
    tools=[get_weather_forecast_tool, get_roof_data_tool, get_room_data_tool, get_energy_data_tool],
    llm=llm,
    verbose=True,
    callback_manager=callback_manager,
    context=SYST_PROMPT,
    max_iterations=100
)

if __name__ == '__main__':
    app.run(debug=True)
