import lastfm_client
import firebase_admin
from dotenv import load_dotenv
from datetime import datetime
from firebase_admin import credentials
from firebase_client import FirebaseClient
from spotify_client import SpotifyClient

load_dotenv()

cred = credentials.Certificate('service-acc.json')
firebase_admin.initialize_app(cred)

firebase_client = FirebaseClient()


def get_lastfm_user_data(username):
    if username:
        lastfm_user = lastfm_client.get_lastfm_user_data(username)
        if lastfm_user and lastfm_user.get("username"):
            lastfm_username = lastfm_user["username"]
            get_or_create_user(lastfm_username)
        return lastfm_user


def get_or_create_user(username):
    user = firebase_client.get_user(username)
    if user:
        return user
    else:
        lastfm_user = lastfm_client.get_lastfm_user_data(username)
        if lastfm_user and lastfm_user.get("username"):
            return firebase_client.create_user(lastfm_user["username"])
        else:
            print(f"User {username} not found on lastfm")


def get_stats(lastfm_user_data, tz_offset, cached=False):
    start_time = datetime.now()
    if cached:
        cached_data = get_cached_stats(lastfm_user_data["username"])
        if cached_data:
            return cached_data
    stats = lastfm_client.get_stats(lastfm_user_data, tz_offset)
    print(f"(took {(datetime.now() - start_time).seconds} seconds)")
    return stats


def get_cached_stats(username):
    return firebase_client.get_user_data(username)


def make_playlist(spotify_client: SpotifyClient, lastfm_user_data: dict = None, data: dict = None,
                  tz_offset: int = None, tz: str =None):
    if not data:
        data = get_cached_stats(lastfm_user_data["username"])
    available_market = None   # TODO timezones to spotify available_markets
    if tz:
        print(f"Client timezone: {tz}")
        if "johannesburg" in tz.lower():
            available_market = "ZA"
    return spotify_client.make_playlist(data, lastfm_user_data, tz_offset, available_market)
