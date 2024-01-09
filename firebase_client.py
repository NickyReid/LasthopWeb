# import logging
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from datetime import datetime

# logger = logging.getLogger(__name__)


class FirebaseClient:
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

    def create_user(self, username):
        doc_ref = self.client.collection("users").document(username.lower())
        doc_ref.set({"username": username})
        return self.get_user(username)

    def get_user_data(self, username):
        doc_ref = self.client.collection("users").document(username.lower())
        doc = doc_ref.get()
        dat = doc.get("data")
        return dat

    def write_data_for_user(self, username, data):
        # logger.info(f"Caching data for {username}...")
        print(f"Caching data for {username}...")
        doc_ref = self.client.collection("users").document(username.lower())
        doc_ref.update({"data": data})

        # print(dat)
        # days_data = doc_ref.get("days_data")
        # ts = str(datetime.timestamp(day))
        # ts = int(float(ts))

        # date_string = datetime.strftime(datetime.now(), "%Y%m%d")
        #
        # day_data = doc_ref.document(date_string)
        # print(day_data.to_dict())
        # if not day_data:
        #     day_data.set(data)


    # defs

    # def get_or_create_document(self, collection_name, document_id, defaults=None):
    #     doc_ref = self.client.collection(collection_name).document(document_id)
    #     doc = doc_ref.get()
    #     if doc.exists:
    #         # Document already exists, return its data
    #         print(f"{document_id} exists")
    #         return doc.to_dict()
    #     else:
    #         # Document doesn't exist, create it with defaults if provided
    #         if defaults is not None:
    #             print(f"{document_id} doesn't exist - creating")
    #             doc_ref.set(defaults)
    #             return defaults
    #         else:
    #             print(f"{document_id} doesn't exist. ")
    #             # Or, you might choose to raise an exception or return a specific value
    #             return None



# db_client = FirebaseClient()
# user = "schiz0rr12"
# result = db_client.get_or_create_user(user)
# print(result)

# Example usage:
# collection_name = 'your_collection'
# document_id = 'your_document_id'
#
# # Try to get the document, create with defaults if not found
# result = get_or_create_document(collection_name, document_id, defaults={'field1': 'value1', 'field2': 'value2'})
# print(result)

# doc_ref = db.collection("users").document("schiz0rr")
## doc_ref = db.collection("users").document("schiz0rr")
# doc_ref.set({"username": "schiz0rr"})


