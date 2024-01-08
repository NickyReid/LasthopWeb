import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
LAST_FM_API_KEY = os.getenv('LAST_FM_API_KEY')


def get_lastfm_user_data(username):
    """
    Get the User's Last.fm profile information
    :return: Dict with user's username, join date, real name and total number of tracks played
    """
    api_url = (
        f"http://ws.audioscrobbler.com/2.0/?method=user.getinfo"
        f"&user={username}"
        f"&api_key={LAST_FM_API_KEY}"
        f"&format=json"
    )
    api_response = requests.get(api_url).json()

    if not api_response.get("user"):
        return

    return {
        "username": username,
        "join_date": datetime.fromtimestamp(
            float(api_response.get("user").get("registered").get("unixtime"))
        ),
        "real_name": api_response.get("user").get("realname"),
        "total_tracks": int(api_response.get("user").get("playcount")),
    }
