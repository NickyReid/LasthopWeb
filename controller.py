import os
import lastfm_client
from dotenv import load_dotenv
from firebase_client import FirebaseClient


load_dotenv()

SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
GENIUS_ACCESS_TOKEN = os.getenv('GENIUS_ACCESS_TOKEN')


firebase_client = FirebaseClient()


def get_user(username):
    return firebase_client.get_user(username)


def get_lastfm_user_data(username):
    if username:
        lastfm_user = lastfm_client.get_lastfm_user_data(username)
        if lastfm_user:
            get_or_create_user(username)
        return lastfm_user


def get_or_create_user(username):
    user = get_user(username)
    if user:
        return user
    else:
        lastfm_user = lastfm_client.get_lastfm_user_data(username)
        if lastfm_user:
            print(lastfm_user)
            return firebase_client.create_user(username)
        else:
            print(f"User {username} not found on lastfm")

