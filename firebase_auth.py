import json
import os
import time
import requests

API_KEY = "YOUR_WEB_API_KEY"
DATABASE_URL = "https://beer-festival-app-a8018-default-rtdb.europe-west1.firebasedatabase.app"  # check this matches your console URL

SIGN_IN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"
REFRESH_URL = f"https://securetoken.googleapis.com/v1/token?key={API_KEY}"


class AuthError(Exception):
    pass


class FirebaseAuth:
    def __init__(self, storage_dir):
        # In Kivy, pass App.get_running_app().user_data_dir
        self._path = os.path.join(storage_dir, "auth.json")
        self.id_token = None
        self.refresh_token = None
        self.expires_at = 0
        self._load()

    def _load(self):
        try:
            with open(self._path) as f:
                data = json.load(f)
            self.refresh_token = data.get("refresh_token")
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save(self):
        with open(self._path, "w") as f:
            json.dump({"refresh_token": self.refresh_token}, f)

    def _store(self, id_token, refresh_token, expires_in):
        self.id_token = id_token
        self.refresh_token = refresh_token
        self.expires_at = time.time() + int(expires_in) - 60  # refresh a minute early
        self._save()

    def sign_in(self, email, password):
        r = requests.post(SIGN_IN_URL, json={
            "email": email, "password": password, "returnSecureToken": True
        }, timeout=10)
        if not r.ok:
            msg = r.json().get("error", {}).get("message", "UNKNOWN")
            raise AuthError(msg)
        d = r.json()
        self._store(d["idToken"], d["refreshToken"], d["expiresIn"])

    def has_saved_login(self):
        return bool(self.refresh_token)

    def get_token(self):
        """Return a valid ID token, refreshing it if needed."""
        if self.id_token and time.time() < self.expires_at:
            return self.id_token
        if not self.refresh_token:
            raise AuthError("NOT_SIGNED_IN")
        r = requests.post(REFRESH_URL, data={
            "grant_type": "refresh_token", "refresh_token": self.refresh_token
        }, timeout=10)
        if not r.ok:
            self.refresh_token = None
            self._save()
            raise AuthError("SESSION_EXPIRED")
        d = r.json()
        self._store(d["id_token"], d["refresh_token"], d["expires_in"])
        return self.id_token

    def sign_out(self):
        self.id_token = self.refresh_token = None
        self.expires_at = 0
        if os.path.exists(self._path):
            os.remove(self._path)