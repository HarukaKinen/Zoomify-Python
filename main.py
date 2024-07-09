import re
import time
from datetime import datetime, timedelta, timezone

from dhooks import Webhook, Embed

from API import Osu
from Config import WEBHOOK, ERROR_LOG

Osu = Osu("")

hook = Webhook(WEBHOOK)

error_log = Webhook(ERROR_LOG)

regex = r"^[^\n:]+:\s*\([^()\n]+\)\s*[vV][sS]\s*\([^()\n]+\)$"


def run():
    mplink = None

    try:
        with open("mplink", "r") as f:
            lines = f.read()
        if lines != "":
            mplink = int(lines)
    except FileNotFoundError:
        with open("mplink", "w") as f:
            f.write("")
    except Exception as e:
        error_log.send(f"Error: {e}")

    if mplink is None:
        mplink = Osu.getLobby().get("cursor").get("match_id")

    while True:
        mplink += 1
        mp = Osu.getMpInfo(mplink)

        if len(mp) == 1:
            if mp.get("authentication") == "basic":
                if Osu.EXPIRES < datetime.now():
                    print(f"{mplink} [Token Expired]")
                    Osu.checkToken()
                    mplink -= 1
                else:
                    print(f"{mplink} [No Permission]")
                continue
            elif mp.get("error") == "Specified LegacyMatch\\LegacyMatch couldn't be found.":
                print(f"{mplink} [Didn't Show Up]")
                mplink -= 1
                time.sleep(60)
                continue
            elif mp.get("error") is None:
                print(f"{mplink} [Didn't Show Up]")
                mplink -= 1
                time.sleep(60)
                continue
            else:
                error_log.send(f"{mplink} Error: {mp}")
                continue

        mp_name = mp["match"]["name"]
        print(mplink, mp_name)
        if re.match(regex, mp_name):
            if "ETX" in mp_name or "o!mm" in mp_name:
                continue
            if mp["match"]["end_time"] is None:
                while mp["match"]["end_time"] is None:
                    start_time = datetime.strptime(
                        mp["match"]["start_time"], "%Y-%m-%dT%H:%M:%S%z"
                    )
                    if start_time + timedelta(
                        seconds=86400
                    ) < datetime.now().astimezone(start_time.tzinfo):
                        print(f"{mplink} [Inactive Lobby]")
                        mp = Osu.getMpInfo(mplink)
                        break
                    else:
                        print(f"{mplink} [Not ended yet]")
                        time.sleep(60)
                        mp = Osu.getMpInfo(mplink)
            sendWebhook(mp)

        with open("mplink", "w") as f:
            f.write(str(mplink))


def checkPlayer(mp):
    for user in mp["users"]:
        if user["country_code"] == "CN":
            return True
    return False


def sendWebhook(mp):
    event_list = mp["events"]
    users_list = mp["users"]
    if mp["events"][0]["id"] != mp["first_event_id"]:
        rsp = Osu.getMpInfo(mp["match"]["id"], mp["events"][0]["id"])
        event_list[:0] = rsp["events"]

        usersid_list = [user["id"] for user in users_list]
        for user in rsp["users"]:
            if user["id"] not in usersid_list:
                users_list.append(user)

    ref_id = 0
    map_played = 0
    winner = 0
    player_dict = {}
    for event in event_list:
        if event.get("detail").get("type") == "match-created":
            ref_id = event.get("user_id")
        if event.get("detail").get("type") == "other":
            map_played += 1
            match_type = event.get("game").get("team_type")

            if match_type != "head-to-head":
                red_score = 0
                blue_score = 0
                for player in event.get("game").get("scores"):
                    if player["score"] < 1000:
                        continue
                    user_id = player.get("user_id")
                    team = 0 if player.get("match")["team"] == "red" else 1

                    if team == 0:
                        red_score += player["score"]
                    else:
                        blue_score += player["score"]

                    player_dict[user_id] = team

                if red_score > blue_score:
                    winner = "red"
                else:
                    winner = "blue"
            else:
                for player in event.get("game").get("scores"):
                    if player["score"] < 1000:
                        continue
                    player_dict[player.get("user_id")] = -1

    if map_played == 0:
        return

    if match_type != "team-vs":
        description = (
            f'[{map_played} map(s) played](https://osu.ppy.sh/mp/{mp["match"]["id"]})'
        )
    else:
        description = f'[{map_played} map(s) played](https://osu.ppy.sh/mp/{mp["match"]["id"]}), Team {winner.capitalize()} Won.'
    embed = Embed(
        description=description,
        timestamp=datetime.strptime(
            mp["match"]["start_time"], "%Y-%m-%dT%H:%M:%S%z"
        ).strftime("%Y-%m-%d %H:%M:%S.%f"),
    )

    embed.set_author(
        name=mp["match"]["name"], url=f'https://osu.ppy.sh/mp/{mp["match"]["id"]}'
    )

    # MAX_FIELD_LENGTH = 1024
    red_field = ""
    blue_field = ""
    h2h_field = ""
    ref_field = ""
    for user in users_list:
        if user["default_group"] != "bot":
            if player_dict.get(user["id"]) == -1:
                h2h_field += f':flag_{user["country_code"].lower()}: [{user["username"]}](https://osu.ppy.sh/users/{user["id"]})\n'
            else:
                if player_dict.get(user["id"]) == 0:
                    red_field += f':flag_{user["country_code"].lower()}: [{user["username"]}](https://osu.ppy.sh/users/{user["id"]})\n'
                elif player_dict.get(user["id"]) == 1:
                    blue_field += f':flag_{user["country_code"].lower()}: [{user["username"]}](https://osu.ppy.sh/users/{user["id"]})\n'

        if user["id"] == ref_id:
            ref_field = f':flag_{user["country_code"].lower()}: [{user["username"]}](https://osu.ppy.sh/users/{user["id"]})\n'
        #     print(len(field))
        #     if len(field) + len(user_field) > MAX_FIELD_LENGTH:
        #         embed.add_field(name='', value=field, inline=False)
        #         field = "" + user_field
        #     else:
        #         field += user_field
        #
        # embed.add_field(name='', value=field, inline=False)

    if h2h_field != "":
        if len(h2h_field) > 1024:
            player_count = len(h2h_field.split("\n"))
            h2h_field = f"{player_count} players in Lobby\n"
        embed.add_field(
            name=":white_circle: Head To Head", value=h2h_field, inline=False
        )
    if red_field != "":
        if len(red_field) > 1024:
            player_count = len(red_field.split("\n"))
            red_field = f"{player_count} players in Team Red\n"
        embed.add_field(name=":red_circle: Team Red", value=red_field, inline=False)
    if blue_field != "":
        if len(blue_field) > 1024:
            player_count = len(blue_field.split("\n"))
            blue_field = f"{player_count} players in Team Blue\n"
        embed.add_field(name=":blue_circle: Team Blue", value=blue_field, inline=False)

    if ref_field != "":
        embed.add_field(name="Referee", value=ref_field, inline=False)

    embed.set_footer(text=mp["match"]["id"])

    hook.send(embed=embed)


if __name__ == "__main__":
    while True:
        try:
            run()
        except Exception as e:
            with open('mplink', 'r') as f:
                lines = f.read()
            if lines != "":
                error_log.send(f"`{lines}` Error: {e}")
            else:
                error_log.send(f"Error: {e}")
            time.sleep(60)
