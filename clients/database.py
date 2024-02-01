import json
import logging
import os
from copy import deepcopy
from datetime import datetime, date

from dateutil.parser import parse

import google
from google.cloud import firestore_v1 as firestore

logger = logging.getLogger(__name__)


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class BaseDbClient(metaclass=Singleton):
    def get_document(self, collection_name, document_id):
        raise NotImplementedError

    def set_document(self, collection_name, document_id, data, merge=True):
        raise NotImplementedError

    def get_collection(self, collection_name):
        raise NotImplementedError

    @staticmethod
    def strip_string(string):
        return str(string).strip().replace("/", "_").lower()


class FirestoreClient(BaseDbClient):

    def __init__(self):
        logger.info("Initializing FirestoreClient")
        creds, project, database_name = self._get_credentials_and_project()
        self.client = firestore.Client(
            project=project, credentials=creds, database=database_name
        )

    @staticmethod
    def _get_credentials_and_project():

        database_name = os.getenv("FIRESTORE_DB",  "(default)")
        creds, project = google.auth.default()
        return creds, project, database_name

    def get_document(self, collection_name: str, document_id: str):
        doc_ref = self.client.collection(collection_name).document(
            self.strip_string(document_id)
        )
        doc = doc_ref.get()
        return doc.to_dict() or {}

    def get_collection(self, collection_name: str):
        return {doc.id: doc.to_dict() for doc in self.client.collection(collection_name).stream()}

    def set_document(self, collection_name: str, document_id: str, data: dict, merge: bool=True):
        doc_ref = self.client.collection(collection_name).document(
            self.strip_string(document_id)
        )
        doc_ref.set(data, merge=merge)


class LocalFiles(BaseDbClient):
    def __init__(self):
        logger.info("Initializing LocalUserClient")
        self.local_dir = self.get_or_create_local_dir()

    @staticmethod
    def get_or_create_local_dir():
        local_dir = os.path.join(os.getcwd(), 'local_cache')
        if not os.path.exists(local_dir):
            os.makedirs(local_dir)
        return local_dir

    def _get_local_path(self, collection_name: str, doc_id: str):
        return os.path.join(self.local_dir, f'{collection_name}/{doc_id}.json')

    def get_document(self, collection_name: str, document_id: str):
        logger.debug(f"Getting document {document_id} from collection {collection_name}")
        local_path = self._get_local_path(collection_name, document_id)
        if not os.path.exists(local_path):
            return {}
        with open(local_path, 'r') as json_file:
            if os.stat(local_path).st_size == 0:
                return {}
            data = json.load(json_file) or {}
            data = self.deserialize(data)
            return data

    @staticmethod
    def deserialize(data):
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    data[key] = LocalFiles.deserialize(value)
                elif isinstance(value, list):
                    data[key] = [LocalFiles.deserialize(item) for item in value]
                else:
                    try:
                        data[key] = parse(value)
                    except (TypeError, ValueError):
                        pass
        elif isinstance(data, list):
            data = [LocalFiles.deserialize(item) for item in data]
        return data

    def set_document(self, collection_name: str, document_id: str, new_data: dict, merge: bool=True):
        logger.debug(f"Setting document {document_id} in collection {collection_name} {new_data}")
        local_path = self._get_local_path(collection_name, document_id)
        if not os.path.exists(local_path):
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
        if not os.path.exists(local_path):
            with open(local_path, 'w') as f:
                json.dump({}, f)

        data = self.get_document(collection_name, document_id) or {}
        data.update({k: v for k, v in new_data.items() if v is not None})
        data = self.serialize(deepcopy(data))
        with open(local_path, 'w') as f:
            json.dump(data, f)

    def serialize(self, data:dict):
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    data[key] = [self.serialize(item) for item in value]
                if isinstance(value, dict):
                    data[key] = self.serialize(value)
                if isinstance(value, (datetime, date)):
                    data[key] = value.isoformat()
        return data

    def get_collection(self, collection_name: str):
        logger.debug(f"Getting collection {collection_name}")
        collection_dir = os.path.join(self.local_dir, collection_name)
        if not os.path.exists(collection_dir):
            return []
        docs = {}
        for doc in os.listdir(collection_dir):
            with open(os.path.join(collection_dir, doc)) as json_file:
                docs[doc.replace(".json", "")] = json.load(json_file)
        return docs


def get_db_client():
    if 'GOOGLE_CLOUD_PROJECT' in os.environ:
        return FirestoreClient()
    else:
        return LocalFiles()
