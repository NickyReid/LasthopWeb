import hashlib
import logging
import os
from datetime import datetime

import pytz

from clients.database import get_db_client
from clients.monitoring_client import stats_profile, GoogleMonitoringClient

logger = logging.getLogger(__name__)

SHOPIFY_SEARCH_MAX_CACHE_AGE_HOURS = int(os.getenv("SHOPIFY_SEARCH_MAX_CACHE_AGE_HOURS") or 24)

class Cache:
    def __init__(self):
        self.db = get_db_client()

    def get_user(self, username):
        return self.db.get_document("users", username)

    def create_user(self, username, user_info):
        self.db.set_document("users", username, {"user_info": user_info,  "days_visited": 0})
        self.get_user_count()
        return self.get_user(username)

    @stats_profile
    def get_user_data(self, username):
        return self.db.get_document("users", username)

    def get_user_count(self):
        users = self.db.get_collection("users")
        user_count = len(users)
        if user_count:
            GoogleMonitoringClient().increment_thread("user-count", user_count)
        return user_count

    def update_user_artist_tags(self, username, artist_tags):
        self.db.set_document("users", username, {"artist_tags": artist_tags}, merge=True)

    def set_user_data(self, username, data, date_cached=None, tz_offset=0):
        self.db.set_document("users", username, {"data": data, "date_cached": date_cached, "tz_offset": tz_offset})

    @stats_profile
    def increment_user_days_visited(self, username):
        user = self.get_user(username)
        days_visited = user.get("days_visited", 1)
        days_visited += 1
        self.db.set_document("users", username, {"days_visited": days_visited}, merge=True)
        logger.info(f"{username} has visited {days_visited} times!")
        GoogleMonitoringClient().increment_thread("user-visits", days_visited)

    def clear_user_data(self, username):
        self.db.set_document("users", username, {"data": None, "date_cached": None})

    def set_artist_tag(self, artist: str, tag: str):
        self.db.set_document("artists", artist, {"tag": tag})
    def get_artist_tag(self, artist: str):
        return self.db.get_document("artists", artist).get("tag")

    def cache_spotify_search_result(self, search_query: str, available_market: str, search_result: dict):
        date_cached = datetime.utcnow()
        hash_key = hashlib.md5(f"{available_market}-{search_query}".encode()).hexdigest()
        self.db.set_document("spotify_search_cache", hash_key, {
            "search_query": search_query,
            "available_market": available_market,
            "search_result": search_result,
            "date_cached": date_cached,
        })


    def get_cached_spotify_search_result(self, search_query: str, available_market: str,
                                         max_age_hours: int = SHOPIFY_SEARCH_MAX_CACHE_AGE_HOURS):
        hash_key = hashlib.md5(f"{available_market}-{search_query}".encode()).hexdigest()
        doc = self.db.get_document("spotify_search_cache", hash_key).get("search_result")
        if doc:
            date_cached = doc.get("date_cached")
            cached_available_market = doc.get("available_market")
            cached_search_query = doc.get("search_query")
            if date_cached:
                cache_age_seconds = (datetime.utcnow().replace(tzinfo=pytz.utc) - date_cached.replace(
                    tzinfo=pytz.utc)).seconds
                if cache_age_seconds / 3600 <= max_age_hours:
                    if not cached_available_market == available_market:
                        logger.info(f"CACHE ERROR cached_available_market != available_market! "
                                    f"{cached_available_market} != {available_market}")
                        GoogleMonitoringClient().increment_thread("spotify-search-cache-error")
                    elif not cached_search_query == search_query:
                        logger.info(f"CACHE ERROR cached_search_query != search_query! "
                                    f"{cached_search_query} != {search_query}")
                        GoogleMonitoringClient().increment_thread("spotify-search-cache-error")
                    else:
                        logger.debug(
                            f"Returning cached Spotify search result for '{available_market} - {search_query}'...")
                        GoogleMonitoringClient().increment_thread("spotify-search-cache-hit")
                        return doc
                else:
                    logger.info(
                        f"Cache for '{available_market} - {search_query}' expired ({cache_age_seconds} seconds)")
                    GoogleMonitoringClient().increment_thread("spotify-search-cache-expired")
            else:
                logger.info(f"Cache for '{available_market} - {search_query}' has no date_cached")
                GoogleMonitoringClient().increment_thread("spotify-search-cache-no-date")
        else:
            logger.info(f"No cache for '{available_market} - {search_query}'")
            GoogleMonitoringClient().increment_thread("spotify-search-cache-miss")
