from firebase_admin import firestore


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

    def create_user(self, username, user_info):
        doc_ref = self.client.collection("users").document(username.lower())
        doc_ref.set({"username": username, "user_info": user_info})
        return self.get_user(username)

    def get_user_data(self, username):
        doc_ref = self.client.collection("users").document(username.lower())
        doc = doc_ref.get()
        # dat = doc.get("data")
        return doc.to_dict()

    def set_user_data(self, username, data, date_cached=None):
        print(f"Caching data for {username}...")
        doc_ref = self.client.collection("users").document(username.lower())
        doc_ref.update({"data": data, "date_cached": date_cached})
