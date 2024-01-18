import logging
from firebase_admin import firestore
from clients.monitoring_client import GoogleMonitoringClient

logger = logging.getLogger(__name__)


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class FirebaseClient(metaclass=Singleton):
    def __init__(self):
        self.client = firestore.client()

    def get_document(self, collection_name, document_id):
        doc_ref = self.client.collection(collection_name).document(document_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        else:
            return None

    @staticmethod
    def strip_string(string):
        return str(string).replace("/", "_").lower()

    def get_user(self, username):
        return self.get_document(
            collection_name="users", document_id=self.strip_string(username)
        )

    def create_user(self, username, user_info):
        doc_ref = self.client.collection("users").document(self.strip_string(username))
        doc_ref.set({"username": username, "user_info": user_info})
        self.get_user_count()
        return self.get_user(username)

    def get_user_data(self, username):
        doc_ref = self.client.collection("users").document(self.strip_string(username))
        doc = doc_ref.get()
        return doc.to_dict()

    def get_user_count(self):
        user_count = self.client.collection("users")
        count_query = user_count.count()
        query_result = count_query.get()
        if query_result:
            user_count = query_result[0][0].value
            if user_count:
                GoogleMonitoringClient().increment_thread("user-count", user_count)
        return user_count

    def set_user_data(self, username, data, date_cached=None):
        logger.debug(f"Caching data for {self.strip_string(username)}...")
        doc_ref = self.client.collection("users").document(self.strip_string(username))
        doc_ref.set({"data": data, "date_cached": date_cached}, merge=True)

    def clear_user_data(self, username):
        logger.debug(f"Clearing data for {self.strip_string(username)}...")
        doc_ref = self.client.collection("users").document(self.strip_string(username))
        doc_ref.update({"data": None, "date_cached": None})

    def set_artist_tag(self, artist: str, tag: str):
        logger.debug(
            f"Caching tag '{self.strip_string(tag)}' for {self.strip_string(artist)}..."
        )
        doc_ref = self.client.collection("artists").document(self.strip_string(artist))
        doc_ref.set({"tag": tag})

    def get_artist_tag(self, artist: str):
        logger.debug(f"Getting tag for {self.strip_string(artist)}...")
        doc_ref = self.client.collection("artists").document(self.strip_string(artist))
        doc = doc_ref.get()
        if doc.to_dict():
            return doc.to_dict().get("tag")
