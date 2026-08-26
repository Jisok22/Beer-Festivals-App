import requests
from datetime import datetime

DATABASE_URL = "https://beer-festival-app-a8018-default-rtdb.europe-west1.firebasedatabase.app"
FESTIVALS_ENDPOINT = f"{DATABASE_URL}/festivals.json"
RESOURCES_ENDPOINT = f"{DATABASE_URL}/resources.json"

WEB_API_KEY = "AIzaSyBajf-s8X55lJ-GV2ro6mOFCx2kwLfPv7c"
AUTH_ENDPOINT = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={WEB_API_KEY}"

_id_token = None


class FirebaseError(Exception):
    """Raised whenever a Firebase request fails — network issue, auth
    issue, or Firebase itself returning an error. Callers can catch
    this specifically rather than a bare Exception."""
    pass


def _get_id_token():
    """Signs in anonymously (once per app run) and caches the token
    for subsequent requests."""
    global _id_token
    if _id_token is None:
        try:
            response = requests.post(
                AUTH_ENDPOINT, json={"returnSecureToken": True}, timeout=10
            )
            response.raise_for_status()
            _id_token = response.json()["idToken"]
        except requests.exceptions.RequestException as e:
            raise FirebaseError(f"Could not sign in to Firebase: {e}") from e
    return _id_token


def init_db():
    # No local setup needed — data lives in Firebase now, not on-device.
    pass


def add_festival(
    name, location, start_date, end_date, opening_time, closing_time, varies_by_day, website=""
):
    payload = {
        "name": name,
        "location": location,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "opening_time": opening_time,
        "closing_time": closing_time,
        "varies_by_day": varies_by_day,
        "website": website,
    }
    token = _get_id_token()
    try:
        response = requests.post(
            FESTIVALS_ENDPOINT,
            params={"auth": token},
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise FirebaseError(f"Could not save festival: {e}") from e


def update_festival(
    festival_id,
    name,
    location,
    start_date,
    end_date,
    opening_time,
    closing_time,
    varies_by_day,
    website="",
):
    payload = {
        "name": name,
        "location": location,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "opening_time": opening_time,
        "closing_time": closing_time,
        "varies_by_day": varies_by_day,
        "website": website,
    }
    token = _get_id_token()
    try:
        response = requests.put(
            f"{DATABASE_URL}/festivals/{festival_id}.json",
            params={"auth": token},
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise FirebaseError(f"Could not update festival: {e}") from e


def delete_festival(festival_id):
    token = _get_id_token()
    try:
        response = requests.delete(
            f"{DATABASE_URL}/festivals/{festival_id}.json",
            params={"auth": token},
            timeout=10,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise FirebaseError(f"Could not delete festival: {e}") from e


def get_all_festivals():
    token = _get_id_token()
    try:
        response = requests.get(
            FESTIVALS_ENDPOINT,
            params={"auth": token},
            timeout=10,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise FirebaseError(f"Could not load festivals: {e}") from e

    data = response.json()

    festivals = []
    if data:
        for key, entry in data.items():
            festivals.append({
                "id": key,
                "name": entry["name"],
                "location": entry["location"],
                "start_date": datetime.strptime(entry["start_date"], "%Y-%m-%d").date(),
                "end_date": datetime.strptime(entry["end_date"], "%Y-%m-%d").date(),
                "opening_time": entry["opening_time"],
                "closing_time": entry.get("closing_time", ""),
                "varies_by_day": entry.get("varies_by_day", False),
                "website": entry.get("website", ""),
            })

    festivals.sort(key=lambda f: f["start_date"])
    return festivals


def add_resource(name, url):
    payload = {"name": name, "url": url}
    token = _get_id_token()
    try:
        response = requests.post(
            RESOURCES_ENDPOINT,
            params={"auth": token},
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise FirebaseError(f"Could not save resource: {e}") from e


def update_resource(resource_id, name, url):
    payload = {"name": name, "url": url}
    token = _get_id_token()
    try:
        response = requests.put(
            f"{DATABASE_URL}/resources/{resource_id}.json",
            params={"auth": token},
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise FirebaseError(f"Could not update resource: {e}") from e


def delete_resource(resource_id):
    token = _get_id_token()
    try:
        response = requests.delete(
            f"{DATABASE_URL}/resources/{resource_id}.json",
            params={"auth": token},
            timeout=10,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise FirebaseError(f"Could not delete resource: {e}") from e


def get_all_resources():
    token = _get_id_token()
    try:
        response = requests.get(
            RESOURCES_ENDPOINT,
            params={"auth": token},
            timeout=10,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise FirebaseError(f"Could not load resources: {e}") from e

    data = response.json()

    resources = []
    if data:
        for key, entry in data.items():
            resources.append({
                "id": key,
                "name": entry["name"],
                "url": entry["url"],
            })

    resources.sort(key=lambda r: r["name"].lower())
    return resources