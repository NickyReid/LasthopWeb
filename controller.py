import logging
import firebase_admin

from dotenv import load_dotenv
from datetime import datetime, timedelta
from firebase_admin import credentials
from clients.monitoring_client import GoogleMonitoringClient, stats_profile
from clients.firebase_client import FirebaseClient
from clients.spotify_client import SpotifyClient
from clients.lastfm_client import LastfmClient

logger = logging.getLogger(__name__)
load_dotenv()

cred = credentials.Certificate("service-acc.json")
firebase_admin.initialize_app(cred)

firebase_client = FirebaseClient()
monitoring_client = GoogleMonitoringClient()


def get_lastfm_user_info(username: str):
    start_time = datetime.now()
    user_info = None
    user = get_or_create_user(username)
    if user:
        user_info = user.get("user_info")
    logger.info(
        f"(get_lastfm_user_info took {(datetime.now() - start_time).seconds} seconds)"
    )
    return user_info


def get_or_create_user(username: str):
    user = firebase_client.get_user(username)
    if not user or not user.get("user_info"):
        lastfm_user_info = LastfmClient.get_lastfm_user_data(username)
        if lastfm_user_info and lastfm_user_info.get("username"):
            user = firebase_client.create_user(
                lastfm_user_info["username"], lastfm_user_info
            )
        else:
            logger.info(f"User {username} not found on lastfm")
    return user


def clear_stats(username: str):
    if username:
        firebase_client.clear_user_data(username)


@stats_profile
def get_stats(lastfm_user_data: dict, tz_offset: int, check_cache=True):
    # start_time = datetime.now()
    data = None
    username = lastfm_user_data.get("username", "").lower()
    if username:
        if check_cache:
            cached_data = get_cached_stats(username)
            if cached_data:
                date_cached = cached_data.get("date_cached")
                if (
                    date_cached
                    and date_cached.date()
                    == (datetime.utcnow() - timedelta(minutes=tz_offset)).date()
                ):
                    logger.info(
                        f"Data cached for {username} at {date_cached.date()} -> Returning cached data"
                    )
                    data = cached_data.get("data")
        if not data:
            lfm_client = LastfmClient(
                username, lastfm_user_data["join_date"], tz_offset
            )
            data = lfm_client.get_stats()
    years_of_data = len(data) if data else 0
    logger.info(f"Stats summary: {username} had {years_of_data} years of data")
    # logger.info(f"(get_stats took {(datetime.now() - start_time).seconds} seconds)")
    return data


def get_cached_stats(username: str):
    return firebase_client.get_user_data(username)


@stats_profile
def make_playlist(
    spotify_client: SpotifyClient,
    lastfm_user_data: dict = None,
    data: dict = None,
    tz_offset: int = None,
    tz: str = None,
):
    if not data:
        data = get_cached_stats(lastfm_user_data["username"]).get("data")
    available_market = None  # TODO timezones to spotify available_markets
    if tz:
        logger.info(f"Client timezone: {tz}")
        if "johannesburg" in tz.lower():
            available_market = "ZA"
    return spotify_client.make_playlist(
        data, lastfm_user_data, tz_offset, available_market
    )
