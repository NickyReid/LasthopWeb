import lastfm_client
from dotenv import load_dotenv
from firebase_admin import credentials
import firebase_admin
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
    if cached:
        cached_data = get_cached_stats(lastfm_user_data["username"])
        if cached_data:
            return cached_data
    return lastfm_client.get_stats(lastfm_user_data, tz_offset)


def get_cached_stats(username):
    return firebase_client.get_user_data(username)


def make_playlist(spotify_client: SpotifyClient, lastfm_user_data=None, data=None):
    if not data:
        data = get_cached_stats(lastfm_user_data["username"])
    return spotify_client.make_playlist(data, lastfm_user_data)
