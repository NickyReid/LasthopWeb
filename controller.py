import logging
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

from clients.cache import Cache
# from clients.firestore_client import FirestoreClient
from clients.lastfm_client import LastfmClient
from clients.monitoring_client import GoogleMonitoringClient, stats_profile
from clients.spotify_client import SpotifyClient
from countries import spotify_available_countries, timezone_countries

logger = logging.getLogger(__name__)
load_dotenv()

# firestore_client = FirestoreClient()
cache = Cache()
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
    user = cache.get_user(username)
    if not user or not user.get("user_info"):
        lastfm_user_info = LastfmClient.get_lastfm_user_data(username)
        if lastfm_user_info and lastfm_user_info.get("username"):
            user = cache.create_user(
                lastfm_user_info["username"], lastfm_user_info
            )
        else:
            logger.info(f"User {username} not found on lastfm")
    return user


def clear_stats(username: str):
    if username:
        cache.clear_user_data(username)


@stats_profile
def get_stats(lastfm_user_data: dict, tz_offset: int):
    data = None
    date_cached = None
    username = lastfm_user_data.get("username", "").lower()
    logger.debug(f"username:{username} lastfm_user_data:{lastfm_user_data}")
    if username:
        lfm_client = LastfmClient(
            username, lastfm_user_data["join_date"], tz_offset
        )
        data, date_cached = lfm_client.get_stats()

    years_of_data = len(data) if data else 0
    logger.info(f"Stats summary: {username} had {years_of_data} years of data")
    return data, date_cached

def get_cached_stats(username: str):
    return cache.get_user_data(username)


@stats_profile
def make_playlist(
    spotify_client: SpotifyClient,
    lastfm_user_data: dict = None,
    playlist_tracks_per_year: int = None,
    playlist_order_recent_first: bool = True,
    playlist_repeat_artists: bool = False,
    playlist_skip_recent_time: str = None,
    tz_offset: int = 0,
):
    data, _ = get_stats(lastfm_user_data, tz_offset)
    playlist_skip_recent_time_start_date = False
    if playlist_skip_recent_time:
        if playlist_skip_recent_time.lower() == "year":
            playlist_skip_recent_time_start_date = datetime.utcnow() - relativedelta(years=1) + relativedelta(days=1)
        elif playlist_skip_recent_time.lower() == "6 months":
            playlist_skip_recent_time_start_date = datetime.utcnow() - relativedelta(months=6)
        elif playlist_skip_recent_time.lower() == "week":
            playlist_skip_recent_time_start_date = datetime.utcnow() - relativedelta(weeks=1)
        else:
            logger.warning(f"Unhandled playlist_skip_recent_time_start_date {playlist_skip_recent_time}")

    return spotify_client.make_playlist(
        data, lastfm_user_data, playlist_tracks_per_year=playlist_tracks_per_year,
        playlist_order_recent_first=playlist_order_recent_first, playlist_repeat_artists=playlist_repeat_artists,
        skip_recently_played_start_date=playlist_skip_recent_time_start_date
    )


def get_spotify_available_market_from_timezone(timezone: str) -> str:
    if timezone:
        timezone = timezone.replace("Calcutta", "Kolkata")
    country_code = timezone_countries.get(timezone)
    if spotify_available_countries.get(country_code):
        return country_code
    else:
        logger.info(f"No Spotify available market for {timezone}")
