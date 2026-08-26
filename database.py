import requests
from datetime import datetime

DATABASE_URL = "https://beer-festival-app-a8018-default-rtdb.europe-west1.firebasedatabase.app"
FESTIVALS_ENDPOINT = f"{DATABASE_URL}/festivals.json"


def init_db():
    # No local setup needed — data lives in Firebase now, not on-device.
    pass


def add_festival(name, location, start_date, end_date, opening_time):
    payload = {
        "name": name,
        "location": location,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "opening_time": opening_time,
    }
    response = requests.post(FESTIVALS_ENDPOINT, json=payload, timeout=10)
    response.raise_for_status()


def get_all_festivals():
    response = requests.get(FESTIVALS_ENDPOINT, timeout=10)
    response.raise_for_status()
    data = response.json()

    festivals = []
    if data:
        for entry in data.values():
            festivals.append({
                "name": entry["name"],
                "location": entry["location"],
                "start_date": datetime.strptime(entry["start_date"], "%Y-%m-%d").date(),
                "end_date": datetime.strptime(entry["end_date"], "%Y-%m-%d").date(),
                "opening_time": entry["opening_time"],
            })

    festivals.sort(key=lambda f: f["start_date"])
    return festivals