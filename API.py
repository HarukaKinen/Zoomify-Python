import requests

from Config import *


class Osu:
    TOKEN = ""

    def __init__(self, token):
        self.TOKEN = self.checkToken()

    def checkToken(self):
        if self.TOKEN == "":
            return self.getToken()

    def getToken(self):
        return requests.post(
            "https://osu.ppy.sh/oauth/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "client_credentials",
                "scope": "public",
            }
        ).json()["access_token"]

    def getMpInfo(self, mplink):
        return requests.get(f"https://osu.ppy.sh/api/v2/matches/{mplink}",
                            headers={"Authorization": f"Bearer {self.TOKEN}"}, data={}).json()

    def getLobby(self):
        return requests.get(f"https://osu.ppy.sh/api/v2/matches",
                            headers={"Authorization": f"Bearer {self.TOKEN}"}, data={}).json()
