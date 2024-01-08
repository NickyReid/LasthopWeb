import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore


class FirebaseClient:
    def __init__(self):
        cred = credentials.Certificate('service-acc.json')
        app = firebase_admin.initialize_app(cred)
        self.client = firestore.client()

    def get_document(self, collection_name, document_id):
        doc_ref = self.client.collection(collection_name).document(document_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        else:
            return None

    def get_or_create_document(self, collection_name, document_id, defaults=None):
        doc_ref = self.client.collection(collection_name).document(document_id)
        doc = doc_ref.get()
        if doc.exists:
            # Document already exists, return its data
            print(f"{document_id} exists")
            return doc.to_dict()
        else:
            # Document doesn't exist, create it with defaults if provided
            if defaults is not None:
                print(f"{document_id} doesn't exist - creating")
                doc_ref.set(defaults)
                return defaults
            else:
                print(f"{document_id} doesn't exist. ")
                # Or, you might choose to raise an exception or return a specific value
                return None

    def get_or_create_user(self, username):
        return self.get_or_create_document(collection_name="users", document_id=username, defaults={"username": username})

    def get_user(self, username):
        return self.get_document(collection_name="users", document_id=username)


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


