import requests
from datetime import datetime, timedelta

from Config import *


class Osu:
    TOKEN = ""

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
        r = requests.post(
            "https://osu.ppy.sh/oauth/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "client_credentials",
                "scope": "public",
            }
        ).json()
        self.EXPIRES = datetime.now() + timedelta(seconds=r["expires_in"])

        return r["access_token"]

    def getMpInfo(self, mplink):
        return requests.get(f"https://osu.ppy.sh/api/v2/matches/{mplink}",
                            headers={"Authorization": f"Bearer {self.TOKEN}"}, data={}).json()

    def getLobby(self):
        return requests.get(f"https://osu.ppy.sh/api/v2/matches",
                            headers={"Authorization": f"Bearer {self.TOKEN}"}, data={}).json()
