import logging

import pytz
from dotenv import load_dotenv
from datetime import datetime, timedelta
from clients.monitoring_client import GoogleMonitoringClient, stats_profile
from clients.firestore_client import FirestoreClient
from clients.spotify_client import SpotifyClient
from clients.lastfm_client import LastfmClient

logger = logging.getLogger(__name__)
load_dotenv()

firestore_client = FirestoreClient()
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
    user = firestore_client.get_user(username)
    if not user or not user.get("user_info"):
        lastfm_user_info = LastfmClient.get_lastfm_user_data(username)
        if lastfm_user_info and lastfm_user_info.get("username"):
            user = firestore_client.create_user(
                lastfm_user_info["username"], lastfm_user_info
            )
        else:
            logger.info(f"User {username} not found on lastfm")
    return user


def clear_stats(username: str):
    if username:
        firestore_client.clear_user_data(username)


@stats_profile
def get_stats(lastfm_user_data: dict, tz_offset: int, check_cache=True):
    data = None
    username = lastfm_user_data.get("username", "").lower()
    date_cached = None
    logger.debug(f"username:{username} check_cache:{check_cache} lastfm_user_data:{lastfm_user_data}")
    if username:
        if check_cache:
            cached_data = get_cached_stats(username)
            logger.debug(f"cached_data = {cached_data}")
            if cached_data:
                date_cached = cached_data.get("date_cached")
                if date_cached:
                    date_cached = date_cached.replace(tzinfo=pytz.UTC) - timedelta(minutes=tz_offset)
                    today = (datetime.utcnow() - timedelta(minutes=tz_offset)).date()
                    logger.debug(f"date_cached: {date_cached}")
                    logger.debug(f"today: {today}")
                    if date_cached.date() == today:
                        logger.info(
                            f"Data cached for {username} at {date_cached.date()} -> Returning cached data"
                        )
                        data = cached_data.get("data")
        if not data:
            lfm_client = LastfmClient(
                username, lastfm_user_data["join_date"], tz_offset
            )
            data = lfm_client.get_stats()
            date_cached = datetime.utcnow()

    years_of_data = len(data) if data else 0
    logger.info(f"Stats summary: {username} had {years_of_data} years of data")
    return data, date_cached


def get_cached_stats(username: str):
    return firestore_client.get_user_data(username)


@stats_profile
def make_playlist(
    spotify_client: SpotifyClient,
    lastfm_user_data: dict = None,
    data: dict = None,
    tz_offset: int = None,
    tz: str = None,
    playlist_tracks_per_year: int = None,
    playlist_order_recent_first: bool = True,
    playlist_repeat_artists: bool = False,
):
    if not data:
        data = get_cached_stats(lastfm_user_data["username"]).get("data")
    available_market = None  # TODO timezones to spotify available_markets
    if tz:
        logger.info(f"Client timezone: {tz}")
        if "johannesburg" in tz.lower():
            available_market = "ZA"
    return spotify_client.make_playlist(
        data, lastfm_user_data, tz_offset, available_market, playlist_tracks_per_year=playlist_tracks_per_year,
        playlist_order_recent_first=playlist_order_recent_first, playlist_repeat_artists=playlist_repeat_artists
    )
