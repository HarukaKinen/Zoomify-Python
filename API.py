import time

import requests
from datetime import datetime, timedelta

from Config import *


class Osu:
    TOKEN = ""
    REQUEST_TIMEOUT = 30
    REQUEST_INTERVAL = 1.0

    def __init__(self, token):
        self.EXPIRES = datetime.now()
        self.TOKEN = None
        self._last_request_at = 0.0
        self.checkToken()

    def checkToken(self):
        if self.TOKEN is None:
            self.TOKEN = self.getToken()
        else:
            print("Token is not None")
            if self.EXPIRES < datetime.now():
                print("Token is expired")
                self.TOKEN = self.getToken()
            else:
                print("Token is not expired")

        return self.TOKEN

    def _wait_for_rate_limit(self):
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.REQUEST_INTERVAL - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _request(self, method, url, **kwargs):
        while True:
            self._wait_for_rate_limit()
            try:
                response = requests.request(
                    method,
                    url,
                    timeout=self.REQUEST_TIMEOUT,
                    **kwargs,
                )
            finally:
                self._last_request_at = time.monotonic()

            if response.status_code != 429:
                return response

            retry_after = response.headers.get("Retry-After", "60")
            try:
                wait_seconds = max(float(retry_after), self.REQUEST_INTERVAL)
            except (TypeError, ValueError):
                wait_seconds = 60.0

            print(f"Rate limited; retrying in {wait_seconds:g} seconds", flush=True)
            time.sleep(wait_seconds)

    def getToken(self):
        response = self._request(
            "POST",
            "https://osu.ppy.sh/oauth/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "client_credentials",
                "scope": "public",
            },
        )
        response.raise_for_status()
        data = response.json()
        self.EXPIRES = datetime.now() + timedelta(seconds=data["expires_in"])

        return data["access_token"]

    def getMpInfo(self, mplink, before=""):
        response = self._request(
            "GET",
            f"https://osu.ppy.sh/api/v2/matches/{mplink}",
            params={"before": before},
            headers={"Authorization": f"Bearer {self.TOKEN}"},
        )
        # Preserve the API's JSON error bodies because main.py uses them to
        # distinguish missing matches and expired authentication.
        return response.json()

    def getLobby(self):
        response = self._request(
            "GET",
            "https://osu.ppy.sh/api/v2/matches",
            headers={"Authorization": f"Bearer {self.TOKEN}"},
        )
        response.raise_for_status()
        return response.json()
