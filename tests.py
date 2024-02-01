import logging
import math
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, Mock

from clients import lastfm_client
from clients import spotify_client

ADD_TO_PLAYLIST_BATCH_LIMIT = 10
logger = logging.getLogger()
logger.level = logging.DEBUG
stream_handler = logging.StreamHandler(sys.stdout)
logger.addHandler(stream_handler)


class TestSpotifyClient(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestSpotifyClient, self).__init__(*args, **kwargs)
        mock_auth_manager = Mock()
        self.sp = spotify_client.SpotifyClient(auth_manager=mock_auth_manager)
        mock_spotify_client = Mock()
        mock_spotify_client.playlist_add_items = MagicMock()
        self.sp.spotify_client = mock_spotify_client()

    def test_batch_add_tracks_to_playlist_limit_1(self):
        spotify_client.ADD_TO_PLAYLIST_BATCH_LIMIT = 1
        playlist_id = "123"
        mock_track_data = [
            {"track_name": "song", "artist": "The Beatles", "track_uri": "123"},
            {"track_name": "song2", "artist": "The Beatles", "track_uri": "123"},
            {"track_name": "song3", "artist": "The Beatles", "track_uri": "123"},
            {"track_name": "song4", "artist": "The Beatles", "track_uri": "123"},
            {"track_name": "song5", "artist": "The Beatles", "track_uri": "123"},
        ]

        mock_track_data_length = len(mock_track_data)
        self.sp.batch_add_tracks_to_playlist(playlist_id, mock_track_data)
        self.assertEqual(self.sp.spotify_client.playlist_add_items.call_count, mock_track_data_length)

    def test_batch_add_tracks_to_playlist_limit_10(self):
        spotify_client.ADD_TO_PLAYLIST_BATCH_LIMIT = 10
        mock_auth_manager = Mock()
        sp = spotify_client.SpotifyClient(auth_manager=mock_auth_manager)
        mock_spotify_client = Mock()
        mock_spotify_client.playlist_add_items = MagicMock(return_value=3)
        sp.spotify_client = mock_spotify_client()
        playlist_id = "123"

        mock_track_data = [
            {"track_name": "song", "artist": "The Beatles", "track_uri": "123"},
            {"track_name": "song2", "artist": "The Beatles", "track_uri": "1234"},
            {"track_name": "song3", "artist": "The Beatles", "track_uri": "1235"},
            {"track_name": "song4", "artist": "The Beatles", "track_uri": "1236"},
            {"track_name": "song5", "artist": "The Beatles", "track_uri": "1237"},
        ]

        sp.batch_add_tracks_to_playlist(playlist_id, mock_track_data)
        self.assertEqual(sp.spotify_client.playlist_add_items.call_count, 1)

    def test_batch_add_tracks_to_playlist_limit_2(self):
        mock_auth_manager = Mock()
        sp = spotify_client.SpotifyClient(auth_manager=mock_auth_manager)
        mock_spotify_client = Mock()
        mock_spotify_client.playlist_add_items = MagicMock(return_value=3)
        sp.spotify_client = mock_spotify_client()
        playlist_id = "123"

        mock_track_data = []
        track_count = 501
        for i in range(track_count):
            mock_track_data.append({"track_name": f"song{i}", "artist": f"The Beatles{i}", "track_uri": f"123{i}"},)
        mock_track_data_length = len(mock_track_data)
        batches = math.ceil(mock_track_data_length / spotify_client.ADD_TO_PLAYLIST_BATCH_LIMIT)
        sp.batch_add_tracks_to_playlist(playlist_id, mock_track_data)
        self.assertEqual(sp.spotify_client.playlist_add_items.call_count, batches)


class TestLastfmClient(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestLastfmClient, self).__init__(*args, **kwargs)
        lastfm_username = "schiz0rr"
        lastfm_join_date = datetime(2006, 1, 12)
        self.lfm_client = lastfm_client.LastfmClient(lastfm_username, lastfm_join_date)

    def test_get_list_of_year_dates(self):
        self.lfm_client.join_date = datetime(2006, 12, 1)
        self.lfm_client.stats_start_date = datetime(2023, 12, 25)
        year_dates = self.lfm_client.get_list_of_year_dates()
        self.assertEqual(len(year_dates), 18)

    def test_get_list_of_year_dates_join_date_anniversary(self):
        self.lfm_client.join_date = datetime(2006, 12, 1)
        self.lfm_client.stats_start_date = datetime(2023, 12, 1)
        year_dates = self.lfm_client.get_list_of_year_dates()
        self.assertEqual(len(year_dates), 18)

    def test_get_list_of_year_dates_leap_year(self):
        self.lfm_client.join_date = datetime(2006, 12, 1)
        self.lfm_client.stats_start_date = datetime(2024, 2, 29)
        year_dates = self.lfm_client.get_list_of_year_dates()
        self.assertEqual(len(year_dates), 5)
