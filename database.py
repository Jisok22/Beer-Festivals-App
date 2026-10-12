import json
import os
import time
from datetime import datetime

import requests

DATABASE_URL = "https://beer-festival-app-a8018-default-rtdb.europe-west1.firebasedatabase.app"
FESTIVALS_ENDPOINT = f"{DATABASE_URL}/festivals.json"
RESOURCES_ENDPOINT = f"{DATABASE_URL}/resources.json"

WEB_API_KEY = "AIzaSyBajf-s8X55lJ-GV2ro6mOFCx2kwLfPv7c"
SIGN_IN_ENDPOINT = (
    f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={WEB_API_KEY}"
)
REFRESH_ENDPOINT = f"https://securetoken.googleapis.com/v1/token?key={WEB_API_KEY}"

_AUTH_FILE_NAME = "auth.json"
_auth_path = None          # set by init_db(); None means "don't persist the login"
_id_token = None
_refresh_token = None
_token_expires_at = 0

_AUTH_MESSAGES = {
    "INVALID_LOGIN_CREDENTIALS": "Email or password not recognised.",
    "EMAIL_NOT_FOUND": "Email or password not recognised.",
    "INVALID_PASSWORD": "Email or password not recognised.",
    "INVALID_EMAIL": "That doesn't look like a valid email address.",
    "USER_DISABLED": "This account has been disabled.",
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Please try again later.",
}


class FirebaseError(Exception):
    """Raised whenever a Firebase request fails — network issue, auth
    issue, or Firebase itself returning an error. Callers can catch
    this specifically rather than a bare Exception."""
    pass


class AuthRequiredError(FirebaseError):
    """Raised when there is no valid login. The UI should catch this and
    show the login popup."""
    pass


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def _save_login():
    if not _auth_path:
        return
    try:
        with open(_auth_path, "w") as f:
            json.dump({"refresh_token": _refresh_token}, f)
    except OSError:
        pass  # not being able to remember the login isn't fatal


def _load_login():
    global _refresh_token
    if not _auth_path:
        return
    try:
        with open(_auth_path) as f:
            _refresh_token = json.load(f).get("refresh_token")
    except (OSError, json.JSONDecodeError):
        _refresh_token = None


def _store_tokens(id_token, refresh_token, expires_in):
    global _id_token, _refresh_token, _token_expires_at
    _id_token = id_token
    _refresh_token = refresh_token
    _token_expires_at = time.time() + int(expires_in) - 60  # refresh a minute early
    _save_login()


def _error_code(response):
    try:
        message = response.json().get("error", {}).get("message", "UNKNOWN")
    except ValueError:
        return "UNKNOWN"
    return message.split(" ")[0]  # e.g. "TOO_MANY_ATTEMPTS_TRY_LATER : Access to..."


def has_saved_login():
    """True if a previous login is available (it may still need refreshing)."""
    return bool(_refresh_token)


def sign_in(email, password):
    """Sign in with an email/password account created in the Firebase console."""
    try:
        response = requests.post(
            SIGN_IN_ENDPOINT,
            json={
                "email": email.strip(),
                "password": password,
                "returnSecureToken": True,
            },
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        raise FirebaseError("Could not reach Firebase. Check your connection.") from e

    if not response.ok:
        code = _error_code(response)
        raise FirebaseError(_AUTH_MESSAGES.get(code, f"Sign-in failed ({code})."))

    data = response.json()
    _store_tokens(data["idToken"], data["refreshToken"], data["expiresIn"])


def sign_out():
    global _id_token, _refresh_token, _token_expires_at
    _id_token = None
    _refresh_token = None
    _token_expires_at = 0
    if _auth_path and os.path.exists(_auth_path):
        try:
            os.remove(_auth_path)
        except OSError:
            pass


def _get_id_token():
    """Returns a valid ID token, refreshing it from the saved refresh token
    when needed. Raises AuthRequiredError if the user has to sign in."""
    if _id_token and time.time() < _token_expires_at:
        return _id_token

    if not _refresh_token:
        raise AuthRequiredError("Please sign in.")

    try:
        response = requests.post(
            REFRESH_ENDPOINT,
            data={"grant_type": "refresh_token", "refresh_token": _refresh_token},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        raise FirebaseError("Could not reach Firebase. Check your connection.") from e

    if not response.ok:
        if 400 <= response.status_code < 500:
            # Refresh token rejected (account removed/disabled, password changed)
            sign_out()
            raise AuthRequiredError("Your session has expired. Please sign in again.")
        raise FirebaseError(f"Could not refresh login (server returned {response.status_code}).")

    data = response.json()
    _store_tokens(data["id_token"], data["refresh_token"], data["expires_in"])
    return _id_token


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _db_request(method, url, action, **kwargs):
    """Makes an authenticated request to the Realtime Database. Error messages
    deliberately avoid the URL, because it contains the auth token."""
    token = _get_id_token()
    try:
        response = requests.request(
            method, url, params={"auth": token}, timeout=10, **kwargs
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        if status == 401:
            raise FirebaseError(
                f"Could not {action}: permission denied. "
                "Is this account allowed to use the app?"
            ) from e
        raise FirebaseError(f"Could not {action} (server returned {status}).") from e
    except requests.exceptions.RequestException as e:
        raise FirebaseError(f"Could not {action}: network problem.") from e
    return response


def _festival_payload(
    name, location, start_date, end_date, opening_time,
    closing_time, varies_by_day, day_times, website,
):
    return {
        "name": name,
        "location": location,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "opening_time": opening_time,
        "closing_time": closing_time,
        "varies_by_day": varies_by_day,
        "day_times": day_times or {},
        "website": website,
    }


def init_db(storage_dir=None):
    """Call once at startup. Pass App.user_data_dir so the login is
    remembered between runs."""
    global _auth_path
    if storage_dir:
        _auth_path = os.path.join(storage_dir, _AUTH_FILE_NAME)
        _load_login()


# ---------------------------------------------------------------------------
# Festivals
# ---------------------------------------------------------------------------

def add_festival(
    name,
    location,
    start_date,
    end_date,
    opening_time,
    closing_time,
    varies_by_day,
    day_times=None,
    website="",
):
    payload = _festival_payload(
        name, location, start_date, end_date, opening_time,
        closing_time, varies_by_day, day_times, website,
    )
    _db_request("POST", FESTIVALS_ENDPOINT, "save festival", json=payload)


def update_festival(
    festival_id,
    name,
    location,
    start_date,
    end_date,
    opening_time,
    closing_time,
    varies_by_day,
    day_times=None,
    website="",
):
    payload = _festival_payload(
        name, location, start_date, end_date, opening_time,
        closing_time, varies_by_day, day_times, website,
    )
    _db_request(
        "PUT", f"{DATABASE_URL}/festivals/{festival_id}.json",
        "update festival", json=payload,
    )


def delete_festival(festival_id):
    _db_request(
        "DELETE", f"{DATABASE_URL}/festivals/{festival_id}.json", "delete festival"
    )


def get_all_festivals():
    response = _db_request("GET", FESTIVALS_ENDPOINT, "load festivals")
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
                "day_times": entry.get("day_times", {}),
                "website": entry.get("website", ""),
            })

    festivals.sort(key=lambda f: f["start_date"])
    return festivals


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

def add_resource(name, url):
    _db_request(
        "POST", RESOURCES_ENDPOINT, "save resource", json={"name": name, "url": url}
    )


def update_resource(resource_id, name, url):
    _db_request(
        "PUT", f"{DATABASE_URL}/resources/{resource_id}.json",
        "update resource", json={"name": name, "url": url},
    )


def delete_resource(resource_id):
    _db_request(
        "DELETE", f"{DATABASE_URL}/resources/{resource_id}.json", "delete resource"
    )


def get_all_resources():
    response = _db_request("GET", RESOURCES_ENDPOINT, "load resources")
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