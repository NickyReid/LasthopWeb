import logging

import pytz
from dotenv import load_dotenv
from datetime import datetime, timedelta
from clients.monitoring_client import GoogleMonitoringClient, stats_profile
from clients.firestore_client import FirestoreClient
from clients.spotify_client import SpotifyClient
from clients.lastfm_client import LastfmClient
from countries import spotify_available_countries, timezone_countries

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
def get_stats(lastfm_user_data: dict, tz_offset: int):
    data = None
    username = lastfm_user_data.get("username", "").lower()
    date_cached = None
    logger.debug(f"username:{username} lastfm_user_data:{lastfm_user_data}")
    if username:
        # if True:
        #     cached_data = get_cached_stats(username)
        #     if cached_data:
        #         date_cached = cached_data.get("date_cached")
        #         if date_cached:
        #             # logger.info(f"date_cached: {date_cached}")
        #             # date_cached = date_cached.replace(tzinfo=pytz.UTC) - timedelta(minutes=tz_offset)
        #             # today = (datetime.utcnow() - timedelta(minutes=tz_offset)).date()
        #             date_cached = date_cached.replace(tzinfo=pytz.UTC).date()
        #             today = datetime.utcnow().date()
        #             # logger.debug(f"date_cached adjusted: {date_cached}")
        #
        #             logger.info(f"today date: {today}")
        #             logger.info(f"date_cached date: {date_cached}")
        #             if date_cached == today:
        #                 logger.info(
        #                     f"Data cached for {username} at {date_cached} -> Returning cached data"
        #                 )
        #                 data = cached_data.get("data")
        if True:
            lfm_client = LastfmClient(
                username, lastfm_user_data["join_date"]
            )
            data, date_cached = lfm_client.get_stats(tz_offset=tz_offset)
            # date_cached = datetime.utcnow() - timedelta(minutes=tz_offset)
            # date_cached = datetime.utcnow()

    # data = filter_stats_for_timezone(data, tz_offset)
    years_of_data = len(data) if data else 0
    logger.info(f"Stats summary: {username} had {years_of_data} years of data")
    return data, date_cached


def filter_stats_for_timezone(stats: list, tz_offset: int) -> list:
    # print(stats)
    result = []
    # date = date.replace(tzinfo=pytz.UTC).replace(hour=0).replace(minute=0).replace(second=0).replace(
    #     microsecond=0
    # )
    start_time = datetime.utcnow().replace(tzinfo=pytz.UTC).replace(hour=0).replace(minute=0).replace(second=0).replace(
        microsecond=0
    ) + timedelta(minutes=tz_offset)
    print(f"start_time = {start_time}")
    end_time = start_time + timedelta(hours = 23, minutes = 59, seconds = 59, microseconds = 999999)
    print(f"end_time = {end_time}")

    for year_data in stats:
        print(year_data["data"])
        print()
        print()
        print()
        year_dict = {}
        filtered_data = []
        print(f"year_data['day'] = {year_data['day']}")
        start_time = start_time.replace(year=year_data["day"].year)
        end_time = end_time.replace(year=year_data["day"].year)
        filtered_track_data = {"track_data": {"tracks": []}}
        for item in year_data["data"]:
            artist = item["artist"]
            # filtered_tracks = []
            for track in item["track_data"]["tracks"]:
                # print(start_time)
                # print(track["date"])
                # print(end_time)
                if start_time <= track["date"] <= end_time:
                    filtered_track_data["track_data"]["tracks"].append(track)
                    # filtered_tracks.append(track)
            # if filtered_tracks:
            #     filtered_track_data["track_data"]["tracks"].append({
            #         "track_data": filtered_track_data
            #     })
        if filtered_track_data:
            result.append({
                "day": year_data["day"].replace(tzinfo=pytz.UTC) + timedelta(minutes=tz_offset),
                "data": filtered_track_data
            })
    print(result)
    return result


def get_cached_stats(username: str):
    return firestore_client.get_user_data(username)


@stats_profile
def make_playlist(
    spotify_client: SpotifyClient,
    lastfm_user_data: dict = None,
    playlist_tracks_per_year: int = None,
    playlist_order_recent_first: bool = True,
    playlist_repeat_artists: bool = False,
):
    data = get_cached_stats(lastfm_user_data["username"]).get("data")
    return spotify_client.make_playlist(
        data, lastfm_user_data, playlist_tracks_per_year=playlist_tracks_per_year,
        playlist_order_recent_first=playlist_order_recent_first, playlist_repeat_artists=playlist_repeat_artists
    )


def get_spotify_available_market_from_timezone(timezone: str) -> str:
    if timezone:
        timezone = timezone.replace("Calcutta", "Kolkata")
    country_code = timezone_countries.get(timezone)
    if spotify_available_countries.get(country_code):
        return country_code
    else:
        logger.info(f"No Spotify available market for {timezone}")
