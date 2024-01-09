import os
import lastfm_client
from dotenv import load_dotenv
from firebase_admin import credentials
import firebase_admin
from firebase_client import FirebaseClient
from spotify_client import SpotifyClient


load_dotenv()

# SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
# SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
# GENIUS_ACCESS_TOKEN = os.getenv('GENIUS_ACCESS_TOKEN')

cred = credentials.Certificate('service-acc.json')
firebase_admin.initialize_app(cred)

firebase_client = FirebaseClient()


# def get_user(username):
#     return firebase_client.get_user(username)


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


def get_stats(lastfm_user_data, tz_offset):
    return lastfm_client.get_stats(lastfm_user_data, tz_offset)


def get_cached_stats(username):
    return firebase_client.get_user_data(username)


def make_playlist(spotify_client: SpotifyClient, lastfm_user_data=None, tz_offset=None, data=None):
    if not data:
        data = get_cached_stats(lastfm_user_data["username"])
    return spotify_client.make_playlist(data, lastfm_user_data)
