import logging
import os

import google
from google.cloud import firestore_v1 as firestore
from clients.monitoring_client import GoogleMonitoringClient

logger = logging.getLogger(__name__)


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
            GoogleMonitoringClient().increment_thread("firestore-exceptiom")
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
            GoogleMonitoringClient().increment_thread("firestore-exceptiom")
            logger.exception(f"Exception occurred in firestore client on get_user")

    def create_user(self, username, user_info):
        try:
            doc_ref = self.client.collection("users").document(
                self.strip_string(username)
            )
            doc_ref.set({"username": username, "user_info": user_info})
            self.get_user_count()
            return self.get_user(username)
        except:
            GoogleMonitoringClient().increment_thread("firestore-exceptiom")
            logger.exception(f"Exception occurred in firestore client on create_user")

    def get_user_data(self, username):
        try:
            doc_ref = self.client.collection("users").document(
                self.strip_string(username)
            )
            doc = doc_ref.get()
            return doc.to_dict()
        except:
            GoogleMonitoringClient().increment_thread("firestore-exceptiom")
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
            GoogleMonitoringClient().increment_thread("firestore-exceptiom")
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
            GoogleMonitoringClient().increment_thread("firestore-exceptiom")
            logger.exception(f"Exception occurred in firestore client on set_user_data")

    def clear_user_data(self, username):
        try:
            logger.debug(f"Clearing data for {self.strip_string(username)}...")
            doc_ref = self.client.collection("users").document(
                self.strip_string(username)
            )
            doc_ref.update({"data": None, "date_cached": None})
        except:
            GoogleMonitoringClient().increment_thread("firestore-exceptiom")
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
            GoogleMonitoringClient().increment_thread("firestore-exceptiom")
            logger.exception(
                f"Exception occurred in firestore client on get_artist_tag for {artist}"
            )
