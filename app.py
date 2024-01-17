import os
import spotipy
import logging

import controller
from clients.spotify_client import SpotifyClient
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, session


load_dotenv()
app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


app.secret_key = os.getenv('SESSION_SECRET_KEY')


@app.route('/', methods=['POST', 'GET'])
def index():
    start_time = datetime.now()
    lastfm_user_data = None
    username = None
    message = None
    playlist_url = None
    stats = None
    tz_offset = None
    tz = None
    use_cached_data = True  # TODO undo
    auth_url = None

    print(f"request.method  = {request.method}")

    if "username" in session:
        username = session["username"]
    if "lastfm_user_data" in session:
        lastfm_user_data = session["lastfm_user_data"]
    if "playlist_url" in session:
        playlist_url = session["playlist_url"]
    if "auth_url" in session:
        auth_url = session["auth_url"]
    if "tz_offset" in session:
        tz_offset = session["tz_offset"]
    if "tz" in session:
        tz = session["tz"]

    if request.method == 'GET':
        if request.args.get("code"):
            print(f'code={request.args.get("code")}')
            # sp_oauth = spotipy.oauth2.SpotifyOAuth(redirect_uri=f"{os.getenv('HOST')}/",
            #                                        scope="playlist-modify-private",
            #                                        cache_handler=spotipy.cache_handler.FlaskSessionCacheHandler(
            #                                            session))
            sp_oauth = SpotifyClient.get_auth_manager(session)
            session["access_token"] = sp_oauth.get_access_token(request.args.get("code"), as_dict=False)
            spotify_client = SpotifyClient(sp_oauth)
            playlist_id, playlist_url = controller.make_playlist(spotify_client=spotify_client,
                                                                 lastfm_user_data=lastfm_user_data,
                                                                 tz_offset=tz_offset)
            session["playlist_url"] = playlist_url
            return redirect('/')

    elif request.method == 'POST':
        if request.form.get("tz_offset"):
            session["tz_offset"] = tz_offset = int(request.form["tz_offset"])
        if request.form.get("tz"):
            session["tz"] = tz = request.form["tz"]

        if request.form.get("username"):
            username = request.form['username']
            session["username"] = username
            lastfm_user_data = controller.get_lastfm_user_info(username)
            session["lastfm_user_data"] = lastfm_user_data
            if lastfm_user_data and lastfm_user_data.get("username"):
                username = session["username"] = lastfm_user_data["username"]

        make_playlist = request.form.get('make_playlist')
        if make_playlist:
            spotify_client = SpotifyClient(session)
            playlist_id, playlist_url = controller.make_playlist(spotify_client=spotify_client,
                                                                 lastfm_user_data=lastfm_user_data,
                                                                 tz_offset=tz_offset,
                                                                 tz=tz)
    print(f"username = {username}")
    print(f"lastfm_user_data = {lastfm_user_data}")
    print(f"auth_url = {auth_url}")
    print(f"playlist_url = {playlist_url}")

    if username:
        if lastfm_user_data:
            message = f"{username} has been on Last.fm since " \
                      f"{datetime.strftime(lastfm_user_data.get('join_date').date(), '%-d %B %Y')}"
            stats = controller.get_stats(lastfm_user_data, tz_offset, check_cache=use_cached_data)

            # sp_oauth = spotipy.oauth2.SpotifyOAuth(redirect_uri=f"{os.getenv('HOST')}/",
            #                                        scope="playlist-modify-private",
            #                                        cache_handler=spotipy.cache_handler.FlaskSessionCacheHandler(session))
            if not auth_url and not playlist_url:

                sp_oauth = SpotifyClient.get_auth_manager(session)
                auth_url = sp_oauth.get_authorize_url()
                session["auth_url"] = auth_url
                # print(auth_url)
        else:
            message = f"{username} not found on Last.fm"
    logger.info(f"Total time: {(datetime.now() - start_time).seconds} seconds)")

    return render_template('index.html', lastfm_user_data=lastfm_user_data, playlist_url=playlist_url, message=message,
                           auth_url=auth_url, stats=stats)


# if __name__ == "__main__":
#     # import time
#     # import pytz
#     # os.environ['TZ'] = "UTC"
#     # time.tzset()
#     from waitress import serve
#     serve(app, host="0.0.0.0", port=8080)
#     app.run(host='0.0.0.0', port=8080, debug=False)
