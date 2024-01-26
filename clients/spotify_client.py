import re
import os
import spotipy
import random
import logging

from dotenv import load_dotenv
from datetime import datetime, timedelta

from clients.monitoring_client import GoogleMonitoringClient

load_dotenv()
logger = logging.getLogger(__name__)

HOST = os.getenv("HOST")
AUTH_SCOPE = "playlist-modify-private"
DEFAULT_PLAYLIST_LENGTH = 50
DEFAULT_TRACKS_PER_YEAR = 5
MAX_PLAYLIST_LENGTH = os.getenv("MAX_PLAYLIST_LENGTH") or 120


class SpotifyForbiddenException(Exception):
    pass


class SpotifyClient:
    def __init__(self, auth_manager=None, session=None):
        if not auth_manager and not session:
            raise Exception("Auth manager or session required")
        if not auth_manager:
            auth_manager = self.get_auth_manager(session)
        self.auth_manager = auth_manager
        self.spotify_client = spotipy.Spotify(auth_manager=auth_manager)

    @staticmethod
    def get_auth_manager(session):
        return spotipy.oauth2.SpotifyOAuth(
            redirect_uri=f"{os.getenv('HOST')}/",
            scope=AUTH_SCOPE,
            cache_handler=spotipy.cache_handler.FlaskSessionCacheHandler(session),
        )

    @classmethod
    def get_max_tracks_per_year(cls, data):
        most_artists_in_a_year = max([len(year['data']) for year in data])
        max_length = min(MAX_PLAYLIST_LENGTH / len(data), most_artists_in_a_year)
        return max_length

    def make_playlist(
        self,
        data: list = None,
        lastfm_user_data: dict = None,
        tz_offset: int = None,
        available_market: str = None,
        playlist_tracks_per_year: int = None,
        playlist_order_recent_first: bool = True,
        playlist_repeat_artists: bool = False,
    ):
        logger.info(f"Playlist options: playlist_tracks_per_year:{playlist_tracks_per_year}; "
                    f"playlist_order_recent_first:{playlist_order_recent_first}; "
                    f"playlist_repeat_artists:{playlist_repeat_artists}")
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
            playlist_id, playlist_url = self.create_playlist(
                lastfm_user_data, tz_offset
            )
            track_count = self.add_tracks_to_playlist(
                playlist_id, track_data, available_market, playlist_tracks_per_year, playlist_repeat_artists
            )
            if playlist_url:
                logger.info(
                    f"Playlist for {lastfm_user_data['username']} created with {track_count} tracks {playlist_url} "
                    f"(took {(datetime.now() - start_time).seconds} seconds)"
                )
                GoogleMonitoringClient().increment_thread(
                    "playlist-length", track_count
                )
        except spotipy.exceptions.SpotifyException:
            # TODO check status code
            GoogleMonitoringClient().increment_thread("spotify-forbidden-exception")
            logger.exception(f"Spotify exception")
            raise SpotifyForbiddenException
        return playlist_id, playlist_url

    def create_playlist(self, lastfm_user_data: dict = None, tz_offset: int = None):
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
        playlist_name = f"Lasthop {(datetime.utcnow() - timedelta(minutes=tz_offset)).strftime('%b %-d')}"
        playlist = self.spotify_client.user_playlist_create(
            user_id,
            playlist_name,
            public=False,
            collaborative=False,
            description=playlist_description,
        )
        playlist_url = playlist.get("external_urls", {}).get("spotify")
        playlist_id = playlist.get("id")
        return playlist_id, playlist_url

    @staticmethod
    def format_track_data(data: list, playlist_order_recent_first: bool = True):
        this_year = datetime.today().year
        result = {}
        if not playlist_order_recent_first:
            data.reverse()
        for year_data in data:
            day = year_data["day"]
            year = day.date().year
            if year == this_year:
                continue
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

    def add_tracks_to_playlist(
        self, playlist_id: int, artist_tracks: dict, available_market: str = None, year_track_limit: int = None,
            playlist_repeat_artists: bool = False
    ):
        logger.info(
            f"Years of data = {len(artist_tracks)} -> Tracks per year: {year_track_limit} "
        )
        added_artist_tracks = {}
        track_count = 0
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
                random.shuffle(tracks)
                tracks = list(set(tracks)) if len(tracks) > 1 else tracks
                tracks = [i for i in tracks if i not in added_artist_tracks.get(artist, [])]
                if not tracks:
                    continue
                selected_track = tracks[0]
                found_track_uri = self.spotify_search(
                    artist, selected_track, available_market
                )
                if found_track_uri:
                    self.add_track_to_playlist(
                        self.spotify_client,
                        playlist_id,
                        found_track_uri,
                        selected_track,
                        artist,
                    )
                    tracks_added_this_year += 1
                    if added_artist_tracks.get(artist):
                        added_artist_tracks[artist].append(selected_track)
                    else:
                        added_artist_tracks[artist] = [selected_track]

                else:
                    current_search = selected_track
                    for retry_track in tracks[1:]:
                        logger.info(
                            f"Couldn't find '{current_search}' by {artist}... Searching for '{retry_track}'"
                        )
                        current_search = retry_track
                        found_track_uri = self.spotify_search(
                            artist, retry_track, available_market
                        )
                        if found_track_uri:
                            self.add_track_to_playlist(
                                self.spotify_client,
                                playlist_id,
                                found_track_uri,
                                retry_track,
                                artist,
                            )
                            tracks_added_this_year += 1
                            if added_artist_tracks.get(artist):
                                added_artist_tracks[artist].append(retry_track)
                            else:
                                added_artist_tracks[artist] = [retry_track]
                            break
                if not found_track_uri:
                    logger.info(f"Couldn't find any tracks for {artist} :(")
            logger.info(f"Tracks added for {year.year}: {tracks_added_this_year}/{len(artist_track_data)}\n")
            track_count += tracks_added_this_year

        return track_count

    @staticmethod
    def add_track_to_playlist(
        spotify_client, playlist_id, track_uri, track_name, artist
    ):
        logger.info(f"Adding '{track_name}' by {artist}")
        spotify_client.playlist_add_items(playlist_id, [track_uri])

    def spotify_search(self, artist, track_name, available_market: str = None):
        track_name = track_name[:75] if len(track_name) > 75 else track_name
        track_name_search = track_name.replace("(", "").replace(")", "").lower().split("feat.")[0]
        artist_search = artist.replace("&", "").replace("(", "").replace(")", "").lower().split("feat.")[0]
        logger.debug(f"Searching for {track_name_search} - {artist_search}")
        search_params = {"q": "track:" + f"{track_name_search} + {artist_search}", "type": "track"}
        if available_market:
            search_params.update({"market": available_market.upper()})
        search_result = self.spotify_client.search(**search_params)
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
                            # TODO available markets config
                            if (
                                (
                                    search_artist_name.lower() in artist.lower()
                                    or artist.lower() in search_artist_name.lower()
                                )
                                and " - live" not in found_track_name.lower()
                                and "live at " not in found_track_name.lower()
                            ):
                                found_item = item
                                break
                        else:
                            continue
                        break

            if found_item:
                found_track_uri = found_item.get("uri")
                return found_track_uri
            elif ("(" in track_name and ")" in track_name) or (
                "[" in track_name and "]" in track_name
            ):

                track_name_without_brackets = re.sub("[\(\[].*?[\)\]]", "", track_name)
                logger.debug(f"Searching for {track_name} without brackets")
                return self.spotify_search(
                    artist, track_name_without_brackets, available_market
                )

        except Exception:
            GoogleMonitoringClient().increment_thread("spotify-exception")
            logger.exception(f"Unhandled Spotify search error: {search_result}")
