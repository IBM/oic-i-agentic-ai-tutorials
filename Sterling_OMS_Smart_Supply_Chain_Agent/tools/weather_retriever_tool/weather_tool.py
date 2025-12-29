from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import requests
from urllib.parse import quote
from datetime import datetime

@tool(name="weather_tool", description="Retrieve weather information for a given city using Open-Meteo API, with fallback.", permission=ToolPermission.READ_ONLY)
def weather_tool(city_name: str) -> str:
    """
    Retrieve weather information for a given city using the Open-Meteo API.

    Args:
        city_name (str): The name of the city for which to retrieve weather data.

    Returns:
        str: A string containing the weather information for the specified city.
    """
    try:
        def get_coordinates(city):
            encoded = quote(city)
            url = f"https://nominatim.openstreetmap.org/search?q={encoded}&format=json"
            headers = {'User-Agent': 'MyWeatherApp/1.0'}
            resp = requests.get(url, headers=headers)
            data = resp.json()
            return data[0]['lat'], data[0]['lon']

        def get_open_meteo_weather(city):
            lat, lon = get_coordinates(city)
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            resp = requests.get(url, timeout=20)
            weather_data = resp.json().get("current_weather", {})
            if weather_data:
                return (
                    f"Current temperature in {city} is {weather_data['temperature']}°C, "
                    f"with wind speed of {weather_data['windspeed']} m/s and it is "
                    f"{'day' if weather_data['is_day'] == 1 else 'night'} time."
                )
            else:
                raise Exception("Weather data not found.")

        def get_fallback_weather(city):
            encoded = quote(city)
            url = f"https://wttr.in/{encoded}?format=j1"
            headers = {"User-Agent": "FallbackWeatherClient"}
            resp = requests.get(url, headers=headers)
            data = resp.json().get("current_condition", [{}])[0]
            return (
                f"(Fallback) Current temperature in {city} is {data.get('temp_C', '?')}°C, "
                f"with wind speed of {data.get('windspeedKmph', '?')} km/h "
                f"and weather condition is {data.get('weatherDesc', [{}])[0].get('value', 'unknown')}."
            )

        try:
            return get_open_meteo_weather(city_name)
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] Fallback triggered due to: {e}")
            return get_fallback_weather(city_name)

    except Exception as e:
        return f"An error occurred while retrieving weather: {str(e)}"
