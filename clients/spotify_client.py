import re
import os
import spotipy
import random
import logging

from dotenv import load_dotenv
from datetime import datetime, timedelta

from clients.monitoring_client import GoogleMonitoringClient
from clients.firestore_client import FirestoreClient

load_dotenv()
logger = logging.getLogger(__name__)

HOST = os.getenv("HOST")
AUTH_SCOPE = "playlist-modify-private"
ADD_TO_PLAYLIST_BATCH_LIMIT = 100
DEFAULT_PLAYLIST_LENGTH = 50
DEFAULT_TRACKS_PER_YEAR = 5
MAX_PLAYLIST_LENGTH = int(os.getenv("MAX_PLAYLIST_LENGTH")) or 120


class SpotifyForbiddenException(Exception):
    pass


class SpotifyClient:
    def __init__(self, auth_manager=None, session=None, available_market: str = None, tz_offset: int = None):
        if not auth_manager and not session:
            raise Exception("Auth manager or session required")
        if not auth_manager:
            auth_manager = self.get_auth_manager(session)
        self.auth_manager = auth_manager
        self.spotify_client = spotipy.Spotify(auth_manager=auth_manager)
        self.available_market = available_market
        self.tz_offset = tz_offset or 0
        self.firestore_client = FirestoreClient()

    @staticmethod
    def get_auth_manager(session):
        return spotipy.oauth2.SpotifyOAuth(
            redirect_uri=f"{HOST}/",
            scope=AUTH_SCOPE,
            cache_handler=spotipy.cache_handler.FlaskSessionCacheHandler(session),
        )

    @classmethod
    def get_max_tracks_per_year(cls, data: list) -> int:
        """
        The maximum number of tracks a user can add to a playlist per year.
        """
        most_artists_in_a_year = max([len(year['data']) for year in data])
        max_length = min(MAX_PLAYLIST_LENGTH / len(data), most_artists_in_a_year)
        return int(max_length)

    def make_playlist(
            self,
            data: list = None,
            lastfm_user_data: dict = None,
            playlist_tracks_per_year: int = None,
            playlist_order_recent_first: bool = True,
            playlist_repeat_artists: bool = False
    ) -> (str, str):
        """
        Make a Spotify playlist, search for tracks and add them to the playlist
        :param data: The user's last.fm stats
        :param lastfm_user_data: The user's last.fm user info
        :param playlist_tracks_per_year: Max number of tracks per year
        :param playlist_order_recent_first: Order by most recent year or not
        :param playlist_repeat_artists: Allow artists to appear more than once in the playlist
        :return: (playlist_id, playlist_url): Spotify playlist ID and URL
        """
        logger.info(f"Playlist options: user:{lastfm_user_data['username']}; "
                    f"playlist_tracks_per_year:{playlist_tracks_per_year}; "
                    f"playlist_order_recent_first:{playlist_order_recent_first}; "
                    f"playlist_repeat_artists:{playlist_repeat_artists}; "
                    f"available_market:{self.available_market}; tz_offset:{self.tz_offset}")
        playlist_tracks_per_year = playlist_tracks_per_year or DEFAULT_TRACKS_PER_YEAR
        if not data:
            logger.info(f"No data for {lastfm_user_data['username']}")
            return None, None
        start_time = datetime.now()
        logger.info(f"Making playlist for {lastfm_user_data['username']}")
        track_data = self.format_track_data(data, playlist_order_recent_first)
        if not track_data:
            return None, None
        try:
            tracks_to_add_to_playlist = self.search_for_tracks(track_data, playlist_tracks_per_year,
                                                               playlist_repeat_artists)
            if not tracks_to_add_to_playlist:
                logger.info(f"No tracks to add to this playlist")
                return None, None

            playlist_id, playlist_url = self.create_playlist(
                lastfm_user_data
            )
            track_count = len(tracks_to_add_to_playlist)

            self.batch_add_tracks_to_playlist(playlist_id=playlist_id, track_data=tracks_to_add_to_playlist)

            if playlist_url:
                logger.info(
                    f"Playlist for {lastfm_user_data['username']} created with {track_count} tracks {playlist_url} "
                    f"(took {(datetime.now() - start_time).seconds} seconds)"
                )
                GoogleMonitoringClient().increment_thread(
                    "playlist-length", track_count
                )
        except spotipy.exceptions.SpotifyException:
            GoogleMonitoringClient().increment_thread("spotify-forbidden-exception")
            logger.exception(f"Spotify exception")
            raise SpotifyForbiddenException
        return playlist_id, playlist_url

    def create_playlist(self, lastfm_user_data: dict = None) -> (str, str):
        """
        :param lastfm_user_data: The user's last.fm user info
        :return: (playlist_id, playlist_url): Spotify playlist ID and URL
        """
        user = self.spotify_client.current_user()
        user_id = user["id"]
        playlist_description = (
            "What were you listening to on this day in previous years?"
        )
        if lastfm_user_data:
            playlist_description += (
                f" {lastfm_user_data['username']}'s listening history on this day since "
                f"{lastfm_user_data['join_date'].year}"
            )

        playlist_title = f"Lasthop {(datetime.utcnow() - timedelta(minutes=self.tz_offset)).strftime('%b %-d')}"
        playlist = self.spotify_client.user_playlist_create(
            user_id,
            playlist_title,
            public=False,
            collaborative=False,
            description=playlist_description,
        )

        playlist_url = playlist.get("external_urls", {}).get("spotify")
        playlist_id = playlist.get("id")
        return playlist_id, playlist_url

    @staticmethod
    def format_track_data(data: list, playlist_order_recent_first: bool = True) -> dict:
        """
        Format the user's last.fm stats so a playlist can be created
        :param data: The user's last.fm stats
        :param playlist_order_recent_first: Order by most recent year or not
        :return:
        """
        result = {}
        if not playlist_order_recent_first:
            data.reverse()
        for year_data in data:
            day = year_data["day"]
            result[day] = []
            data = year_data["data"]
            for artist_data in data:
                artist_tracks_dict = {}
                artist = artist_data["artist"]
                tracks = artist_data["track_data"]["tracks"]
                for track_data in tracks:
                    track_name = track_data["track_name"].replace("'", "")
                    if artist_tracks_dict.get(artist):
                        artist_tracks_dict[artist].append(track_name)
                    else:
                        artist_tracks_dict[artist] = [track_name]
                if artist_tracks_dict:
                    artist_tracks_dict["playcount"] = len(artist_tracks_dict[artist])
                    result[day].append(
                        {
                            "artist": artist,
                            "tracks": artist_tracks_dict[artist],
                            "playcount": artist_tracks_dict["playcount"],
                        }
                    )
                    result[day] = sorted(
                        result[day], key=lambda d: d["playcount"], reverse=True
                    )
        return result

    def search_for_tracks(
            self, artist_tracks: dict, year_track_limit: int = None,
            playlist_repeat_artists: bool = False
    ) -> list:
        """
        Search for tracks and add them to the playlist
        :param artist_tracks: Formatted last.fm stats
        :param year_track_limit: Max number of tracks to add per year
        :param playlist_repeat_artists: Allow artists to appear more than once in the playlist
        :return: Tracks to be added to playlist
        """

        tracks_to_add_to_playlist = []
        added_artist_tracks = {}
        track_count = 0

        def _choose_track_for_artist(_artist: str, _tracks: list) -> str or None:
            """
            Given a list of tracks scrobbled for an artist, find one that can be be added to the playlist
            :return:
            """
            _tracks = list(set(_tracks)) if len(_tracks) > 1 else _tracks
            _tracks = [i for i in _tracks if i not in added_artist_tracks.get(_artist, [])]
            random.shuffle(_tracks)
            if not _tracks:
                return

            selected_track = _tracks[0]
            _found_track_uri = self.spotify_search(
                _artist, selected_track
            )
            if _found_track_uri:
                if _found_track_uri not in tracks_to_add_to_playlist:
                    tracks_to_add_to_playlist.append(_found_track_uri)
                    if added_artist_tracks.get(_artist):
                        added_artist_tracks[_artist].append(selected_track)
                    else:
                        added_artist_tracks[_artist] = [selected_track]
                else:
                    logger.info(f"DUPLICATE: '{selected_track}' by {_artist}")
            else:
                logger.info(f"NOT FOUND:'{selected_track}' by '{_artist}'\n")
                _found_track_uri = _choose_track_for_artist(_artist,  _tracks[1:])
            return _found_track_uri

        logger.info(
            f"Years of data = {len(artist_tracks)} -> Tracks per year: {year_track_limit} "
        )

        for year, artist_track_data in artist_tracks.items():
            tracks_added_this_year = 0

            for artist_dict in artist_track_data:
                if tracks_added_this_year >= year_track_limit:
                    break
                artist = artist_dict["artist"]
                if not playlist_repeat_artists and added_artist_tracks.get(artist):
                    logger.debug(f"Already added artist {artist}, skipping")
                    continue

                tracks = artist_dict["tracks"]
                found_track_uri = _choose_track_for_artist(artist, tracks)
                if found_track_uri:
                    tracks_added_this_year += 1
                else:
                    logger.info(f"NO TRACKS FOUND FOR ARTIST: {artist}\n")
                    # logger.info(f"Couldn't find any tracks for {artist}\n")

            logger.info(f"Tracks added for {year.year}: {tracks_added_this_year}/{len(artist_track_data)}\n")
            track_count += tracks_added_this_year
        logger.info(f"Total tracks to add to playlist: {len(tracks_to_add_to_playlist)} track_count: {track_count}")
        return tracks_to_add_to_playlist

    def batch_add_tracks_to_playlist(self, playlist_id: str, track_data: list):
        if len(track_data) > ADD_TO_PLAYLIST_BATCH_LIMIT:
            batch = track_data[:ADD_TO_PLAYLIST_BATCH_LIMIT]
            queue = track_data[ADD_TO_PLAYLIST_BATCH_LIMIT:]
        else:
            batch = track_data
            queue = None

        logger.info(f"Adding {len(batch)} tracks to playlist")
        self.spotify_client.playlist_add_items(playlist_id, batch)

        if queue:
            self.batch_add_tracks_to_playlist(playlist_id, track_data[ADD_TO_PLAYLIST_BATCH_LIMIT:])

    def spotify_search(self, artist: str, track_name: str) -> str:
        """
        Search Spotify for the track
        :return: Track URI if track is found
        """
        def _strip_search_term(search_term):
            if len(search_term) > 75:
                search_term = search_term[:75]
            search_term = search_term.lower().split("feat.")[0]
            search_term = search_term.lower().split("ft.")[0]
            search_term = search_term.lower().split("featuring")[0]
            for term in [" & ", " + ", "(album version)", "(original mix)"]:
                search_term = search_term.replace(term, " ")
            for char in ["(", ")", ".", "'"]:
                search_term = search_term.replace(char, "")
            search_term = search_term.strip()
            return search_term

        def _match_artist(_search_artist, _result_artist):
            _search_artist = _strip_search_term(_search_artist).replace(" and ", " ")
            _result_artist = _strip_search_term(_result_artist).replace(" and ", " ")
            logger.debug(f"_search_artist = {_search_artist}")
            logger.debug(f"_result_artist = {_result_artist}")
            logger.debug(f"= {_search_artist == _result_artist}")
            if _search_artist == _result_artist or _search_artist == _result_artist.split(",")[0]:
                return True
            return False

        def _incorrect_live_version(_search_track, _result_track):
            if "live" in _result_track.lower() and "live" not in _search_track.lower():
                return True
            return False

        track_name_search = _strip_search_term(track_name)
        artist_search = _strip_search_term(artist)
        logger.info(f"SEARCH   :'{track_name}' by '{artist}'")
        search_query = f"{track_name_search} {artist_search}"
        logger.debug(f"SEARCH QUERY: {search_query}")
        cached_result = self.firestore_client.get_cached_spotify_search_result(search_query=search_query,
                                                                               available_market=self.available_market)
        if cached_result:
            search_result = cached_result.get("search_result")
        else:
            search_params = {"q": "track:" + search_query, "type": "track"}
            if self.available_market:
                logger.debug(f"Spotify available_market:{self.available_market}")
                search_params.update({"market": self.available_market})
            search_result = self.spotify_client.search(**search_params)
            self.firestore_client.cache_spotify_search_result(search_query=search_query,
                                                              available_market=self.available_market,
                                                              search_result=search_result)
        logger.debug(f"Spotify search_result = {search_result}")
        try:
            found_item = None
            if search_result.get("tracks"):
                search_result = search_result["tracks"]
                if search_result.get("items"):
                    search_result = search_result["items"]
                    found_item = None
                    for item in search_result:
                        found_track_name = item["name"]
                        search_artists = item.get("artists")
                        for search_artist in search_artists:
                            search_artist_name = search_artist.get("name")
                            if _match_artist(search_artist_name, artist)\
                                    and not _incorrect_live_version(track_name_search, found_track_name):
                                found_item = item
                                logger.info(f"FOUND    :'{found_track_name}' by '{search_artist_name}'")
                                break
                        else:
                            continue
                        break

            if found_item:
                found_track_uri = found_item.get("uri")
                return found_track_uri
            # elif ("(" in track_name and ")" in track_name) or (
            #         "[" in track_name and "]" in track_name
            # ):
            #
            #     track_name_without_brackets = re.sub("[\(\[].*?[\)\]]", "", track_name)
            #     logger.debug(f"Searching for {track_name} without brackets")
            elif "[" in track_name and "]" in track_name:
                track_name_without_brackets = re.sub("[\[].*?[\]]", "", track_name)
                if track_name_without_brackets:
                    logger.debug(f"Searching for {track_name} without square brackets")
                    return self.spotify_search(
                        artist, track_name_without_brackets
                    )
        except Exception:
            GoogleMonitoringClient().increment_thread("spotify-exception")
            logger.exception(f"Unhandled Spotify search error: {search_result}")
