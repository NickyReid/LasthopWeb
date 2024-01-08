from flask import Flask, render_template, request
from firebase_client import FirebaseClient

app = Flask(__name__)

firebase_client = FirebaseClient()


@app.route('/', methods=['POST', 'GET'])
def index():
    username = None
    user = None
    if request.method == 'POST':
        username = request.form['username']
        user = firebase_client.get_user(username)
    return render_template('index.html', username=username, user=user)


if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)
