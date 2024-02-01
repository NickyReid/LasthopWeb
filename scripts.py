import os
import spotipy
from clients.spotify_client import SpotifyClient
from clients.lastfm_client import LastfmClient
import sys
from datetime import datetime
import logging

logger = logging.getLogger()
# logger.level = logging.DEBUG
# stream_handler = logging.StreamHandler(sys.stdout)
# logger.addHandler(stream_handler)

# HOST = os.getenv("HOST")
# AUTH_SCOPE = "playlist-modify-private"
# auth_manager = spotipy.oauth2.SpotifyOAuth(scope=AUTH_SCOPE, redirect_uri="http://127.0.0.1:8000/")
# c = SpotifyClient(auth_manager=auth_manager, available_market="ZA")
#
#
# track_name = "Come With Me (Original Mix)"
# artist = "Nora En Pure"
# c.spotify_search(track_name=track_name, artist=artist)
def main():
    lastfm_username = "schiz0rr"
    lastfm_join_date = datetime(2006, 1, 12)
    lfm_client = LastfmClient(lastfm_username, lastfm_join_date)
    since = datetime(2024, 1, 1)
    data = lfm_client.get_scrobbles_since(since)


if __name__ == '__main__':
    main()