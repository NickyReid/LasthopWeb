import logging
from firebase_admin import firestore

logger = logging.getLogger(__name__)


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            # don't want __init__ to be called every time
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

    def get_user(self, username):
        return self.get_document(collection_name="users", document_id=username.lower())

    def create_user(self, username, user_info):
        doc_ref = self.client.collection("users").document(username.lower())
        doc_ref.set({"username": username, "user_info": user_info})
        return self.get_user(username)

    def get_user_data(self, username):
        doc_ref = self.client.collection("users").document(username.lower())
        doc = doc_ref.get()
        return doc.to_dict()
        # if doc.to_dict():
        #     return doc.to_dict().get("data")

    def set_user_data(self, username, data, date_cached=None):
        logger.debug(f"Caching data for {username}...")
        doc_ref = self.client.collection("users").document(username.lower())
        doc_ref.update({"data": data, "date_cached": date_cached})

    def set_artist_tag(self, artist: str, tag: str):
        logger.debug(f"Caching tag '{tag}' for {artist}...")
        doc_ref = self.client.collection("artists").document(artist.lower())
        # if not doc_ref:
        #     doc_ref =
        doc_ref.set({"tag": tag})

    def get_artist_tag(self, artist: str):
        logger.debug(f"Getting tag for {artist}...")
        doc_ref = self.client.collection("artists").document(artist.lower())
        doc = doc_ref.get()
        if doc.to_dict():
            return doc.to_dict().get("tag")

