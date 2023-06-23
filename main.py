import re
import time
from datetime import datetime

from dhooks import Webhook, Embed

from API import Osu
from Config import WEBHOOK

Osu = Osu("")

hook = Webhook(WEBHOOK)

regex = r"^[^\n:]+:\s*\([^()\n]+\)\s*[vV][sS]\s*\([^()\n]+\)$"


def run():
    mplink = None

    try:
        with open('mplink', 'r') as f:
            lines = f.read()
        if lines != "":
            mplink = int(lines)
    except FileNotFoundError:
        with open('mplink', 'w') as f:
            f.write("")
    except Exception as e:
        hook.send(f"Error: {e}")

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
            elif mp.get("error") is None:
                print(f"{mplink} [Didn't Show Up]")
                mplink -= 1
                time.sleep(60)
                continue
            else:
                hook.send(f"{mplink} Error: {mp}")
                continue

        mp_name = mp["match"]["name"]
        print(mplink, mp_name)
        if re.match(regex, mp_name):
            if "ETX" in mp_name or "o!mm" in mp_name:
                continue
            if mp["match"]["end_time"] is None:
                while mp["match"]["end_time"] is None:
                    print(f"{mplink} [Not ended yet]")
                    time.sleep(60)
                    mp = Osu.getMpInfo(mplink)
            sendWebhook(mp)

        with open('mplink', 'w') as f:
            f.write(str(mplink))


def checkPlayer(mp):
    for user in mp["users"]:
        if user["country_code"] == "CN":
            return True
    return False


def sendWebhook(mp):
    map_played = 0
    for event in mp["events"]:
        if event.get("detail").get("type") == "other":
            map_played += 1
    if map_played == 0:
        return
    embed = Embed(
        description=f'[{map_played} map(s) played.](https://osu.ppy.sh/mp/{mp["match"]["id"]})',
        timestamp=datetime.strptime(mp["match"]["start_time"], "%Y-%m-%dT%H:%M:%S%z").strftime('%Y-%m-%d %H:%M:%S.%f')
    )

    embed.set_author(name=mp["match"]["name"], url=f'https://osu.ppy.sh/mp/{mp["match"]["id"]}')

    # MAX_FIELD_LENGTH = 1024
    ref_field = None
    if mp["events"][0]["detail"]["type"] == "match-created":
        ref_id = mp["events"][0]["user_id"]
    else:
        ref_id = 0
    for user in mp["users"]:
        if user["default_group"] != "bot":
            if user["id"] == ref_id:
                ref_field = f':flag_{user["country_code"].lower()}: [{user["username"]}](https://osu.ppy.sh/users/{ref_id})'
            else:
                user_field = f':flag_{user["country_code"].lower()}: [{user["username"]}](https://osu.ppy.sh/users/{user["id"]})\n'
                embed.add_field(name='', value=user_field, inline=False)
        #     print(len(field))
        #     if len(field) + len(user_field) > MAX_FIELD_LENGTH:
        #         embed.add_field(name='', value=field, inline=False)
        #         field = "" + user_field
        #     else:
        #         field += user_field
        #
        # embed.add_field(name='', value=field, inline=False)
    if ref_field:
        embed.add_field(name='Referee', value=ref_field, inline=False)

    embed.set_footer(text=mp["match"]["id"])

    hook.send(embed=embed)


if __name__ == '__main__':
    while True:
        try:
            run()
        except Exception as e:
            print(e)
            time.sleep(60)
