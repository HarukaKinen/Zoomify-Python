import requests
from datetime import datetime, timedelta

from Config import *


class Osu:
    TOKEN = ""
    REQUEST_TIMEOUT = 30

    def __init__(self, token):
        self.EXPIRES = datetime.now()
        self.TOKEN = None
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

    def getToken(self):
        response = requests.post(
            "https://osu.ppy.sh/oauth/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "client_credentials",
                "scope": "public",
            },
            timeout=self.REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        self.EXPIRES = datetime.now() + timedelta(seconds=data["expires_in"])

        return data["access_token"]

    def getMpInfo(self, mplink, before=""):
        response = requests.get(
            f"https://osu.ppy.sh/api/v2/matches/{mplink}",
            params={"before": before},
            headers={"Authorization": f"Bearer {self.TOKEN}"},
            timeout=self.REQUEST_TIMEOUT,
        )
        # Preserve the API's JSON error bodies because main.py uses them to
        # distinguish missing matches and expired authentication.
        return response.json()

    def getLobby(self):
        response = requests.get(
            "https://osu.ppy.sh/api/v2/matches",
            headers={"Authorization": f"Bearer {self.TOKEN}"},
            timeout=self.REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
