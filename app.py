import controller
from flask import Flask, render_template, request

app = Flask(__name__)


@app.route('/', methods=['POST', 'GET'])
def index():
    lastfm_user_data = None
    message = None
    if request.method == 'POST':
        username = request.form['username']
        if username:
            lastfm_user_data = controller.get_lastfm_user_data(username)
            if lastfm_user_data:
                message = f"{username} has been on Last.fm since {lastfm_user_data.get('join_date')}"
            else:
                message = f"{username} not found on Last.fm"
    return render_template('index.html', lastfm_user_data=lastfm_user_data, message=message)


if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)
