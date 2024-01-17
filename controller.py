import logging
import firebase_admin


from dotenv import load_dotenv
from datetime import datetime
from firebase_admin import credentials
from clients.firebase_client import FirebaseClient
from clients.spotify_client import SpotifyClient
from clients.lastfm_client import LastfmClient

logger = logging.getLogger(__name__)
load_dotenv()

cred = credentials.Certificate('service-acc.json')
firebase_admin.initialize_app(cred)

firebase_client = FirebaseClient()


def get_lastfm_user_info(username):
    start_time = datetime.now()
    user_info = None
    user = get_or_create_user(username)
    if user:
        user_info = user.get("user_info")
    logger.info(f"(get_lastfm_user_info took {(datetime.now() - start_time).seconds} seconds)")
    return user_info


def get_or_create_user(username):
    user = firebase_client.get_user(username)

    if not user or not user.get("user_info"):
        lastfm_user_info = LastfmClient.get_lastfm_user_data(username)
        if lastfm_user_info and lastfm_user_info.get("username"):
            user = firebase_client.create_user(lastfm_user_info["username"], lastfm_user_info)
        else:
            logger.info(f"User {username} not found on lastfm")
    return user


def get_stats(lastfm_user_data, tz_offset, check_cache=False):
    start_time = datetime.now()
    data = None
    if check_cache:
        cached_data = get_cached_stats(lastfm_user_data["username"])
        print(f"len(cached_data) = {len(cached_data)}")
        if cached_data:
            date_cached = cached_data.get("date_cached")
            if date_cached and date_cached.date() == datetime.utcnow().date():
                logger.info(f"Data cached {date_cached.date()} -> Returning cached data")
                data = cached_data.get("data")
                # print(data)
    if not data:
        lfm_client = LastfmClient(lastfm_user_data["username"], lastfm_user_data["join_date"], tz_offset)
        data = lfm_client.get_stats()
    logger.info(f"(get_stats took {(datetime.now() - start_time).seconds} seconds)")
    return data


def get_cached_stats(username):
    return firebase_client.get_user_data(username)


def make_playlist(spotify_client: SpotifyClient, lastfm_user_data: dict = None, data: dict = None,
                  tz_offset: int = None, tz: str =None):
    if not data:
        data = get_cached_stats(lastfm_user_data["username"]).get("data")
    available_market = None   # TODO timezones to spotify available_markets
    if tz:
        logger.info(f"Client timezone: {tz}")
        if "johannesburg" in tz.lower():
            available_market = "ZA"
    return spotify_client.make_playlist(data, lastfm_user_data, tz_offset, available_market)
