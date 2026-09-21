import os
import re
import time
import traceback
from datetime import datetime, timedelta

from dhooks import Webhook, Embed

from API import Osu as OsuClient
from Config import WEBHOOK, ERROR_LOG

# Initialise inside run(), so a temporary OAuth/network failure at startup is
# handled by the outer restart loop instead of terminating the process.
Osu = None

hook = Webhook(WEBHOOK)

error_log = Webhook(ERROR_LOG)

regex = r"^[^\n:]+:\s*\([^()\n]+\)\s*[vV][sS]\s*\([^()\n]+\)$"


def report_error(message):
    """Report an error without allowing the reporter itself to stop the process."""
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    log_message = f"[{timestamp}] {message}"

    print(log_message, flush=True)
    try:
        with open("error.log", "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
    except Exception:
        print("Failed to write error.log", flush=True)
        traceback.print_exc()

    try:
        # Discord messages are limited to 2000 characters.
        error_log.send(log_message[-1900:])
    except Exception:
        print("Failed to send error webhook", flush=True)
        traceback.print_exc()


def read_mplink():
    try:
        with open("mplink", "r", encoding="utf-8") as f:
            value = f.read().strip()
        return int(value) if value else None
    except FileNotFoundError:
        write_mplink("")
        return None
    except Exception:
        report_error(f"Failed to read mplink; using latest lobby:\n{traceback.format_exc()}")
        return None


def write_mplink(value):
    """Atomically update the existing mplink state file."""
    temp_path = "mplink.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(str(value))
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, "mplink")


def run():
    global Osu

    if Osu is None:
        Osu = OsuClient("")

    mplink = read_mplink()

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
                report_error(f"{mplink} unexpected API response: {mp}")
                time.sleep(60)
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

        write_mplink(mplink)


def checkPlayer(mp):
    for user in mp["users"]:
        if user["country_code"] == "CN":
            return True
    return False


def sendWebhook(mp):
    event_list = mp.get("events") or []
    users_list = mp.get("users") or []
    if not event_list:
        return

    if event_list[0].get("id") != mp.get("first_event_id"):
        rsp = Osu.getMpInfo(mp["match"]["id"], mp["events"][0]["id"])
        event_list[:0] = rsp.get("events") or []

        usersid_list = [user["id"] for user in users_list]
        for user in rsp.get("users") or []:
            if user["id"] not in usersid_list:
                users_list.append(user)

    ref_id = 0
    map_played = 0
    winner = 0
    player_dict = {}
    for event in event_list:
        detail = event.get("detail") or {}
        game = event.get("game") or {}
        if detail.get("type") == "match-created":
            ref_id = event.get("user_id")
        if detail.get("type") == "other" and game:
            map_played += 1
            match_type = game.get("team_type")

            if match_type != "head-to-head":
                red_score = 0
                blue_score = 0
                for player in game.get("scores") or []:
                    score = player.get("score") or 0
                    player_match = player.get("match") or {}
                    team_name = player_match.get("team")
                    if score < 1000 or team_name not in ("red", "blue"):
                        continue
                    user_id = player.get("user_id")
                    team = 0 if team_name == "red" else 1

                    if team == 0:
                        red_score += score
                    else:
                        blue_score += score

                    player_dict[user_id] = team

                if red_score > blue_score:
                    winner = "red"
                else:
                    winner = "blue"
            else:
                for player in game.get("scores") or []:
                    if (player.get("score") or 0) < 1000:
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
        except KeyboardInterrupt:
            # Keep Ctrl+C and service-manager shutdown usable.
            raise
        except BaseException:
            # This is the last line of defence. Recreate the API client on the
            # next run in case its token/session state caused the failure.
            Osu = None

            # Reading the state file and reporting the error are both
            # protected so neither can kill us.
            try:
                with open("mplink", "r", encoding="utf-8") as f:
                    lines = f.read().strip()
            except Exception:
                lines = "unknown"

            report_error(
                f"mplink={lines or 'empty'} crashed; restarting in 60 seconds:\n"
                f"{traceback.format_exc()}"
            )
            time.sleep(60)
