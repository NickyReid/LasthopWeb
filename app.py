import os
import spotipy

import controller
from spotify_client import SpotifyClient
import json
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, session
# from flask_session import Session

load_dotenv()
app = Flask(__name__)

# app.secret_key = os.urandom(64)
app.secret_key = os.getenv('SESSION_SECRET_KEY')
# app.config['SECRET_KEY'] = os.urandom(64)
# Session(app)


@app.route('/', methods=['POST', 'GET'])
def index():
    lastfm_user_data = None
    username = None
    message = None
    playlist_url = None
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    sp_oauth = spotipy.oauth2.SpotifyOAuth(redirect_uri=f"{os.getenv('HOST')}/",
                                           scope="playlist-modify-private", cache_handler=cache_handler)
    if "username" in session:
        username = session["username"]
    if "lastfm_user_data" in session:
        lastfm_user_data = session["lastfm_user_data"]

    if request.method == 'GET':
        if request.args.get("code"):
            session["token_info"] = sp_oauth.get_access_token(request.args.get("code"))
            return redirect('/')

    elif request.method == 'POST':
        if request.form.get("username"):
            username = request.form['username']
            session["username"] = username
            lastfm_user_data = controller.get_lastfm_user_data(username)
            session["lastfm_user_data"] = lastfm_user_data

        make_playlist = request.form.get('make_playlist')
        if make_playlist:
            if not sp_oauth.validate_token(sp_oauth.cache_handler.get_cached_token()):
                auth_url = sp_oauth.get_authorize_url()
                return render_template('authorize-spotify.html', auth_url=auth_url)

            else:
                spotify_client = SpotifyClient(sp_oauth)
                playlist_id, playlist_url = spotify_client.create_playlist()

    if username:
        if lastfm_user_data:
            message = f"{username} has been on Last.fm since {lastfm_user_data.get('join_date')}"


        else:
            message = f"{username} not found on Last.fm"
    return render_template('index.html', lastfm_user_data=lastfm_user_data, playlist_url=playlist_url, message=message)


if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)
