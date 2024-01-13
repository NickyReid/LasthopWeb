import re
import os
import math
import spotipy
import random

from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

HOST = os.getenv('HOST')
PLAYLIST_SIZE_VAR = 70


class SpotifyClient:
    def __init__(self, auth_manager):
        self.spotify_client = spotipy.Spotify(auth_manager=auth_manager)

    def make_playlist(self, data: dict = None, lastfm_user_data: dict = None, tz_offset: int = None,
                      available_market: str = None):
        if not data:
            print(f"No data for {lastfm_user_data['username']}")
            return None, None
        start_time = datetime.now()
        print(f"Making Playlist")
        track_data = self.format_track_data(data)
        if not track_data:
            return None, None

        playlist_id, playlist_url = self.create_playlist(lastfm_user_data, tz_offset)
        self.search_for_tracks(playlist_id, track_data, available_market)
        if playlist_url:
            print(f"Playlist created {playlist_url} (took {(datetime.now() - start_time).seconds} seconds)")
        return playlist_id, playlist_url

    def create_playlist(self, lastfm_user_data: dict = None, tz_offset: int = None):
        user = self.spotify_client.current_user()
        user_id = user["id"]
        playlist_description = "What were you listening to on this day in previous years?"
        if lastfm_user_data:
            playlist_description += f" {lastfm_user_data['username']}'s listening history on this day since " \
                                    f"{lastfm_user_data['join_date'].year}"
        playlist_name = f"Lasthop {(datetime.utcnow() - timedelta(minutes=tz_offset)).strftime('%b %-d')}"
        playlist = self.spotify_client.user_playlist_create(user_id, playlist_name, public=False, collaborative=False,
                                                            description=playlist_description)
        playlist_url = playlist.get("external_urls", {}).get("spotify")
        playlist_id = playlist.get("id")
        return playlist_id, playlist_url

    def format_track_data(self, data: dict):
        this_year = datetime.today().year
        result = {}
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
                    result[day].append({"artist": artist, "tracks": artist_tracks_dict[artist],
                                        "playcount": artist_tracks_dict["playcount"]})
                    result[day] = sorted(result[day], key=lambda d: d["playcount"], reverse=True)
        return result

    def search_for_tracks(self, playlist_id: int, artist_tracks: dict, available_market: str = None):
        tracks_per_year = (math.ceil(PLAYLIST_SIZE_VAR / len(artist_tracks))) * 2
        print(f"Years of data = {len(artist_tracks)} -> Tracks per year = {tracks_per_year}")
        added_artists = []
        for year, artist_track_data in artist_tracks.items():
            tracks_added_this_year = 0
            for artist_dict in artist_track_data:
                if tracks_added_this_year >= tracks_per_year:
                    break
                artist = artist_dict["artist"]
                if artist in added_artists:
                    continue
                tracks = artist_dict["tracks"]
                random.shuffle(tracks)
                tracks = list(set(tracks)) if len(tracks) > 1 else tracks
                selected_track = tracks[0]
                found_track_uri = self.spotify_search(artist, selected_track, available_market)
                if found_track_uri:
                    self.add_track_to_playlist(self.spotify_client, playlist_id, found_track_uri, selected_track,
                                               artist)
                    tracks_added_this_year += 1
                    added_artists.append(artist)
                else:
                    current_search = selected_track
                    for retry_track in tracks[1:]:
                        print(f"Couldn't find '{current_search}' by {artist}... Searching for '{retry_track}'")
                        current_search = retry_track
                        found_track_uri = self.spotify_search(artist, retry_track, available_market)
                        if found_track_uri:
                            self.add_track_to_playlist(self.spotify_client, playlist_id, found_track_uri, retry_track,
                                                       artist)
                            tracks_added_this_year += 1
                            added_artists.append(artist)
                            break
                if not found_track_uri:
                    print(f"Couldn't find any tracks for {artist} :(")
            print(f"Tracks added for {year.year}: {tracks_added_this_year}")
            print()

    def add_track_to_playlist(self, spotify_client, playlist_id, track_uri, track_name, artist):
        print(f"Adding '{track_name}' by {artist}")
        spotify_client.playlist_add_items(playlist_id, [track_uri])

    def spotify_search(self, artist, track_name, available_market: str = None):
        search_params = {"q": "track:" + f"{track_name} + {artist}", "type": "track"}
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
                        album = item.get("album")
                        found_track_name = item["name"]
                        search_artists = album.get("artists")
                        for search_artist in search_artists:
                            search_artist_name = search_artist.get("name")
                            # TODO available markets config
                            if (search_artist_name.lower() in artist.lower()
                                or artist.lower() in search_artist_name.lower()) \
                                    and " - live" not in found_track_name.lower() \
                                    and "live at " not in found_track_name.lower():
                                found_item = item
                                break
                        else:
                            continue
                        break

            if found_item:
                found_track_uri = found_item.get("uri")
                return found_track_uri
            elif ("(" in track_name and ")" in track_name) or ("[" in track_name and "]" in track_name):
                track_name_without_brackets = re.sub("[\(\[].*?[\)\]]", "", track_name)
                return self.spotify_search(artist, track_name_without_brackets, available_market)

        except Exception as e:
            print(f"Error: {e} {search_result}")

