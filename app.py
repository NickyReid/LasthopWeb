import os
import logging

import pytz

import controller
from spotipy.oauth2 import SpotifyOauthError
from clients.spotify_client import SpotifyClient, SpotifyForbiddenException
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, session
from clients.monitoring_client import GoogleMonitoringClient

load_dotenv()
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app.secret_key = os.getenv("SESSION_SECRET_KEY")


@app.route("/", methods=["POST", "GET"])
def index():
    start_time = datetime.now()
    lastfm_user_data = None
    username = None
    message = None
    playlist_url = None
    stats = None
    tz_offset = None
    tz = None
    auth_url = None
    today = None
    try:
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

        if request.method == "GET":
            if request.args.get("code"):

                sp_oauth = SpotifyClient.get_auth_manager(session)
                session["access_token"] = sp_oauth.get_access_token(
                    request.args.get("code"), as_dict=False
                )

                if lastfm_user_data:
                    spotify_client = SpotifyClient(sp_oauth)
                    playlist_id, playlist_url = controller.make_playlist(
                        spotify_client=spotify_client,
                        lastfm_user_data=lastfm_user_data,
                        tz_offset=tz_offset,
                    )
                    session["playlist_url"] = playlist_url
                return redirect("/")
            elif request.args.get("clear"):
                controller.clear_stats(username)
                session.clear()
                return render_template("index.html")

        elif request.method == "POST":
            session.clear()
            playlist_url = None
            if request.form.get("tz_offset"):
                session["tz_offset"] = tz_offset = int(request.form["tz_offset"])
            if request.form.get("tz"):
                session["tz"] = tz = request.form["tz"]

            if request.form.get("username"):
                username = request.form["username"]
                session["username"] = username
                if tz:
                    logger.info(f"Timezone for {username}: {tz}")
                lastfm_user_data = controller.get_lastfm_user_info(username)
                session["lastfm_user_data"] = lastfm_user_data
                if lastfm_user_data and lastfm_user_data.get("username"):
                    username = session["username"] = lastfm_user_data["username"]

            make_playlist = request.form.get("make_playlist")
            if make_playlist:
                spotify_client = SpotifyClient(session)
                playlist_id, playlist_url = controller.make_playlist(
                    spotify_client=spotify_client,
                    lastfm_user_data=lastfm_user_data,
                    tz_offset=tz_offset,
                    tz=tz,
                )

        if username:
            if lastfm_user_data:
                stats = controller.get_stats(lastfm_user_data, tz_offset)
                if stats:
                    message = (
                        f"{username} has been on Last.fm since "
                        f"{datetime.strftime(lastfm_user_data.get('join_date').date(), '%-d %B %Y')}"
                    )
                else:
                    message = f"{username} has no listening data for today"
                today = datetime.utcnow().replace(tzinfo=pytz.UTC) - timedelta(
                    minutes=tz_offset
                )
                if not auth_url and not playlist_url:
                    sp_oauth = SpotifyClient.get_auth_manager(session)
                    auth_url = sp_oauth.get_authorize_url()
                    session["auth_url"] = auth_url
            else:
                message = f"{username} not found on Last.fm"
        logger.info(f"Total time: {(datetime.now() - start_time).seconds} seconds)")
    except SpotifyOauthError:
        session["access_token"] = None
        session["auth_url"] = None
        logger.exception(
            f"SpotifyOauthError Exception occurred. username:{username} lastfm_user_data:{lastfm_user_data} "
            f"tz:{tz} tz_offset:{tz_offset}"
        )
        message = "There was an error authorizing Spotify - Please try again"
        GoogleMonitoringClient().increment_thread("spotify-oath-exception")
    except SpotifyForbiddenException:
        session["access_token"] = None
        session["auth_url"] = None
        logger.exception(
            f"SpotifyForbiddenException Exception occurred. username:{username} lastfm_user_data:{lastfm_user_data}"
            f" tz:{tz} tz_offset:{tz_offset}"
        )
        message = "Please authorize Spotify to create a playlist"
    except:
        session["auth_url"] = None
        logger.exception(
            f"Unhandled Exception occurred. username:{username} lastfm_user_data:{lastfm_user_data} "
            f"tz:{tz} tz_offset:{tz_offset}"
        )
        message = "Something went wrong :("
        GoogleMonitoringClient().increment_thread("unhandled-exception")

    logger.info(f"Response message: {message} Referer:{request.referrer}")
    return render_template(
        "index.html",
        lastfm_user_data=lastfm_user_data,
        playlist_url=playlist_url,
        message=message,
        auth_url=auth_url,
        stats=stats,
        today=today,
    )
