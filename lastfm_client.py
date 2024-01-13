import os
import pytz
import requests
import multiprocessing

from dotenv import load_dotenv
from datetime import datetime, timedelta
from firebase_client import FirebaseClient


load_dotenv()
LAST_FM_API_KEY = os.getenv('LAST_FM_API_KEY')
LAST_FM_BASE_URL = "http://ws.audioscrobbler.com/2.0"
HEADERS = {'User-Agent': "LasthopWeb/1.0"}
STATS_START_DATE = datetime.utcnow()


def get_lastfm_user_data(username):
    """
    Get the User's Last.fm profile information
    :return: Dict with user's username, join date, real name and total number of tracks played
    """
    api_url = (
        f"{LAST_FM_BASE_URL}/?method=user.getinfo"
        f"&user={username}"
        f"&api_key={LAST_FM_API_KEY}"
        f"&format=json"
    )
    api_response = requests.get(api_url, headers=HEADERS).json()

    if not api_response.get("user"):
        return {}
    return {
        "username": api_response["user"]["name"],
        "join_date": datetime.fromtimestamp(
            float(api_response["user"].get("registered").get("unixtime"))
        ),
        "real_name": api_response["user"].get("realname"),
        "total_tracks": int(api_response["user"].get("playcount")),
    }


class DataCompiler:
    def __init__(self, lastfm_username, lastfm_join_date, tz_offset=0):
        self.username = lastfm_username
        self.join_date = lastfm_join_date.replace(tzinfo=pytz.UTC)
        self.api_key = LAST_FM_API_KEY
        self.stats_start_date = STATS_START_DATE.replace(tzinfo=pytz.UTC) - timedelta(minutes=tz_offset)
        self.tz_offset = tz_offset or 0

    def summarize_data(self, data):
        print(f"Summarizing data for {self.username}...")
        result = []
        for line in data:
            day = (line["day"] - timedelta(minutes=self.tz_offset)).replace(tzinfo=None)
            data = line["data"]
            artist_scrobble_dict = {}
            scrobble_list = []
            for scrobble in data:
                artist = scrobble["artist"]
                track_name = scrobble["track_name"]
                timestamp = scrobble["timestamp"]
                if not timestamp:  # Don't add currently playing track to stats
                    continue
                date = (datetime.fromtimestamp(int(timestamp), tz=pytz.UTC) - timedelta(minutes=self.tz_offset))
                track_date_dict = {"track_name": track_name, "date": date, "artist": artist}
                if not artist_scrobble_dict.get(artist):
                    artist_scrobble_dict[artist] = {
                        "playcount": 1, "tracks": [track_date_dict]
                    }
                else:
                    artist_scrobble_dict[artist]["playcount"] += 1
                    artist_scrobble_dict[artist]["tracks"].append(track_date_dict)
                scrobble_list.append(track_date_dict)
            artist_scrobble_list = []
            for artist, track_data in artist_scrobble_dict.items():
                artist_scrobble_list.append({"artist": artist, "track_data": track_data})
            artist_scrobble_list = sorted(artist_scrobble_list, key=lambda d: d["track_data"]["playcount"], reverse=True)
            top_artist_d = artist_scrobble_list[0]["artist"]
            top_tag = self.get_top_tag_for_artist(top_artist_d)
            if top_tag:
                artist_scrobble_list[0]["tag"] = top_tag
            result.append({"day": day, "data": artist_scrobble_list, "scrobble_list": scrobble_list})
        sorted_result = sorted(result, key=lambda d: d["day"], reverse=True)
        return sorted_result

    def get_data_for_all_days(self):
        print(f"Getting data from Last.fm for {self.username}...")
        days = self.get_list_of_dates()
        jobs = []
        queue = multiprocessing.Queue()
        for day in days:
            job = multiprocessing.Process(target=self.get_data_for_day, args=(day, queue))
            jobs.append(job)
            job.start()

        result = []
        job_count = 0
        while job_count < len(jobs):
            day_data = queue.get()
            if day_data:
                job_count += 1
                if day_data.get("data"):
                    result.append(day_data)

        for job in jobs:
            job.join()
        return result

    def get_list_of_dates(self):
        date_to_process = self.stats_start_date
        days = []
        while date_to_process.date() >= self.join_date.date():
            days.append(date_to_process)
            date_to_process = date_to_process.replace(year=date_to_process.year - 1)
        return days

    def get_data_for_day(self, day, queue):
        raw_data = self.get_lastfm_tracks_for_day(day)
        data = []
        for line in raw_data:
            data_dict = {}
            artist = line.get("artist", {}).get("#text")
            title = line.get("name")
            if "[Live]" in title.lower():
                title = title.replace("[Live]", "")
            elif "(Live)" in title.lower():
                title = title.replace("(Live)", "")
            elif "[live]" in title.lower():
                title = title.replace("[live]", "")
            elif "(live)" in title.lower():
                title = title.replace("(live)", "")

            data_dict["artist"] = artist
            data_dict["track_name"] = title
            data_dict["timestamp"] = line.get("date", {}).get("uts")
            data_dict["time_text"] = line.get("date", {}).get("#text")
            data.append(data_dict)
        if True:
            result = {"day": day, "data": data}
            queue.put(result)

    def get_lastfm_tracks_for_day(self, date: datetime) -> list:
        """
        Get and format Last.fm data into a list of dictionaries.
        :param date: Day for which to get data
        :return: List of track information dictionaries
        """
        lastfm_response = self.lastfm_api_query(date, 1)
        lastfm_tracks = lastfm_response.get("recenttracks", {}).get("track")
        num_pages = int(lastfm_response.get("recenttracks", {}).get("@attr", {}).get("totalPages", 0))
        if num_pages > 1:
            for page_num in range(2, num_pages + 1):
                lastfm_response = self.lastfm_api_query(date, page_num)
                lastfm_tracks.extend(
                    lastfm_response.get("recenttracks", {}).get("track")
                )
        if lastfm_tracks:
            if isinstance(lastfm_tracks, dict):
                lastfm_tracks = [lastfm_tracks]

            if lastfm_tracks and len(lastfm_tracks) > 0:
                #  Remove currently playing song from past results
                if (
                    lastfm_tracks[0].get("@attr", {}).get("nowplaying", False)
                    and date.date() != datetime.today().date()
                ):
                    del lastfm_tracks[0]
                #  Remove duplicated playing song from current results
                elif (
                    lastfm_tracks[0].get("@attr", {}).get("nowplaying", False)
                    and date.date() == datetime.today().date()
                    and len(lastfm_tracks) > 1
                    and lastfm_tracks[0].get("name") == lastfm_tracks[1].get("name")
                ):
                    del lastfm_tracks[0]
        return lastfm_tracks

    @staticmethod
    def get_top_tag_for_artist(artist: str) -> str:
        print(f"Getting top tag for {artist}...")
        top_tag = None
        api_url = (
            f"{LAST_FM_BASE_URL}/?method=artist.gettoptags"
            f"&artist={artist}&"
            f"api_key=8257fbe241e266367f27e30b0e866aba&"
            f"autocorrect=1&"
            f"&format=json"
        )
        response = requests.get(api_url, headers=HEADERS).json()
        tag_list = response.get("toptags", {}).get("tag", [])
        for tag in tag_list:
            tag_name = tag.get("name")
            if "seen live" not in tag_name:
                top_tag = tag_name
                break
        return top_tag

    def lastfm_api_query(self, date: datetime, page_num: int) -> dict:
        """
        Get data from Last.fm api
        :param date: Day for which to get data
        :param page_num: Page number.
        :return: JSON response from API.
        """
        date_start = (
            date.replace(hour=0)
            .replace(minute=0)
            .replace(second=0)
            .replace(microsecond=0) + timedelta(minutes=self.tz_offset)
        )
        date_start_epoch = int(date_start.timestamp())
        date_end = date_start + timedelta(hours=23, minutes=59, seconds=59, microseconds=999999)
        date_end_epoch = int(
            date_end.timestamp()
        )
        api_url = (
            f"{LAST_FM_BASE_URL}/?method=user.getrecenttracks"
            f"&user={self.username}&"
            f"api_key=8257fbe241e266367f27e30b0e866aba&"
            f"&from={date_start_epoch}"
            f"&to={date_end_epoch}"
            f"&limit=200"
            f"&page={page_num}"
            f"&format=json"
        )
        response = requests.get(api_url, headers=HEADERS).json()
        return response


def get_stats(lastfm_user_data, tz_offset):
    data_compiler = DataCompiler(
        lastfm_user_data["username"], lastfm_user_data["join_date"], tz_offset
    )
    data_for_all_days = data_compiler.get_data_for_all_days()
    summary = data_compiler.summarize_data(data_for_all_days)
    firebase_client = FirebaseClient()
    firebase_client.set_user_data(lastfm_user_data["username"], summary)
    return summary

