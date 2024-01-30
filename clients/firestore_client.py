import logging
import os
import hashlib
import google
from datetime import datetime

import pytz
from dotenv import load_dotenv

from google.cloud import firestore_v1 as firestore
from clients.monitoring_client import GoogleMonitoringClient, stats_profile

load_dotenv()
logger = logging.getLogger(__name__)

SHOPIFY_SEARCH_MAX_CACHE_AGE_HOURS = int(os.getenv("SHOPIFY_SEARCH_MAX_CACHE_AGE_HOURS") or 24)


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class FirestoreClient(metaclass=Singleton):
    def __init__(self):
        creds, project, database_name = self._get_credentials_and_project()
        self.client = firestore.Client(
            project=project, credentials=creds, database=database_name
        )

    @staticmethod
    def _get_credentials_and_project():
        if "prod" not in os.getenv("ENVIRONMENT", "").lower():
            database_name = "development"
        else:
            database_name = "(default)"
        creds, project = google.auth.default()
        return creds, project, database_name

    def get_document(self, collection_name, document_id):
        try:
            doc_ref = self.client.collection(collection_name).document(document_id)
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict()
            else:
                return None
        except:
            GoogleMonitoringClient().increment_thread("firestore-exception")
            logger.exception(f"Exception occurred in firestore client on get_document")

    @staticmethod
    def strip_string(string):
        return str(string).strip().replace("/", "_").lower()

    def get_user(self, username):
        try:
            return self.get_document(
                collection_name="users", document_id=self.strip_string(username)
            )
        except:
            GoogleMonitoringClient().increment_thread("firestore-exception")
            logger.exception(f"Exception occurred in firestore client on get_user")

    def create_user(self, username, user_info):
        try:
            doc_ref = self.client.collection("users").document(
                self.strip_string(username)
            )
            doc_ref.set({"username": username, "user_info": user_info, "days_visited": 0})
            self.get_user_count()
            return self.get_user(username)
        except:
            GoogleMonitoringClient().increment_thread("firestore-exception")
            logger.exception(f"Exception occurred in firestore client on create_user")

    @stats_profile
    def get_user_data(self, username):
        try:
            doc_ref = self.client.collection("users").document(
                self.strip_string(username)
            )
            doc = doc_ref.get()
            return doc.to_dict()
        except:
            GoogleMonitoringClient().increment_thread("firestore-exception")
            logger.exception(f"Exception occurred in firestore client on get_user_data")

    def get_user_count(self):
        try:
            user_count = self.client.collection("users")
            count_query = user_count.count()
            query_result = count_query.get()
            if query_result:
                user_count = query_result[0][0].value
                if user_count:
                    GoogleMonitoringClient().increment_thread("user-count", user_count)
            return user_count
        except:
            GoogleMonitoringClient().increment_thread("firestore-exception")
            logger.exception(
                f"Exception occurred in firestore client on get_user_count"
            )

    def set_user_data(self, username, data, date_cached=None):
        try:
            logger.debug(f"Caching data for {self.strip_string(username)}...")
            doc_ref = self.client.collection("users").document(
                self.strip_string(username)
            )
            doc_ref.set({"data": data, "date_cached": date_cached}, merge=True)
        except:
            GoogleMonitoringClient().increment_thread("firestore-exception")
            logger.exception(f"Exception occurred in firestore client on set_user_data")

    @stats_profile
    def increment_user_days_visited(self, username):
        try:
            doc_ref = self.client.collection("users").document(
                self.strip_string(username)
            )
            doc = doc_ref.get()
            doc = doc.to_dict()
            days_visited = doc.get("days_visited", 1)
            days_visited += 1
            doc_ref.set({"days_visited": days_visited}, merge=True)
            logger.info(f"{username} has visited {days_visited} times!")
            GoogleMonitoringClient().increment_thread("user-visits", days_visited)
        except:
            GoogleMonitoringClient().increment_thread("firestore-exception")
            logger.exception(f"Exception occurred in firestore client on increment_user_days_visited")

    def clear_user_data(self, username):
        try:
            logger.debug(f"Clearing data for {self.strip_string(username)}...")
            doc_ref = self.client.collection("users").document(
                self.strip_string(username)
            )
            doc_ref.update({"data": None, "date_cached": None})
        except:
            GoogleMonitoringClient().increment_thread("firestore-exception")
            logger.exception(
                f"Exception occurred in firestore client on clear_user_data"
            )

    def set_artist_tag(self, artist: str, tag: str):
        try:
            logger.debug(
                f"Caching tag '{self.strip_string(tag)}' for {self.strip_string(artist)}..."
            )
            doc_ref = self.client.collection("artists").document(
                self.strip_string(artist)
            )
            doc_ref.set({"tag": tag})
        except:
            GoogleMonitoringClient().increment_thread("firestore-exception")
            logger.exception(
                f"Exception occurred in firestore client on set_artist_tag"
            )

    def get_artist_tag(self, artist: str):
        try:
            logger.debug(f"Getting tag for {self.strip_string(artist)}...")
            doc_ref = self.client.collection("artists").document(
                self.strip_string(artist)
            )
            doc = doc_ref.get()
            if doc.to_dict():
                return doc.to_dict().get("tag")
        except:
            GoogleMonitoringClient().increment_thread("firestore-exception")
            logger.exception(
                f"Exception occurred in firestore client on get_artist_tag for {artist}"
            )

    def cache_spotify_search_result(self, search_query: str, available_market: str, search_result: dict):
        try:
            date_cached = datetime.utcnow()
            hash_key = hashlib.md5(f"{available_market}-{search_query}".encode()).hexdigest()
            logger.debug(
                f"Caching Spotify search result for {hash_key} - '{available_market} - {search_query}'..."
            )
            doc_ref = self.client.collection("spotify_search_cache").document(hash_key)
            doc_ref.set({
                "search_query": search_query,
                "available_market": available_market,
                "search_result": search_result,
                "date_cached": date_cached,
            })
        except:
            GoogleMonitoringClient().increment_thread("firestore-exception")
            logger.exception(
                f"Exception occurred in firestore client on cache_spotify_search_result"
            )

    def get_cached_spotify_search_result(self, search_query: str, available_market: str,
                                         max_age_hours: int = SHOPIFY_SEARCH_MAX_CACHE_AGE_HOURS):
        try:
            hash_key = hashlib.md5(f"{available_market}-{search_query}".encode()).hexdigest()
            logger.debug(f"Getting Spotify search result for {hash_key} - '{available_market} - {search_query}'...")
            doc_ref = self.client.collection("spotify_search_cache").document(hash_key)
            doc = doc_ref.get()
            if doc.to_dict():
                date_cached = doc.to_dict().get("date_cached")
                cached_available_market = doc.to_dict().get("available_market")
                cached_search_query = doc.to_dict().get("search_query")
                if date_cached:
                    cache_age_seconds = (datetime.utcnow().replace(tzinfo=pytz.utc) - date_cached.replace(tzinfo=pytz.utc)).seconds
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
                            return doc.to_dict()
                    else:
                        logger.info(f"Cache for '{available_market} - {search_query}' expired ({cache_age_seconds} seconds)")
                        GoogleMonitoringClient().increment_thread("spotify-search-cache-expired")

            else:
                logger.debug(
                    f"No cached Spotify search result for '{available_market} - {search_query}'...")

                GoogleMonitoringClient().increment_thread("spotify-search-cache-miss")
        except:
            GoogleMonitoringClient().increment_thread("firestore-exception")
            logger.exception(
                f"Exception occurred in firestore client on get_cached_spotify_search_result"
            )
