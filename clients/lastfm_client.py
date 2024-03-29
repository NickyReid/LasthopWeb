import os
import pytz
import requests
import multiprocessing
import logging

from clients import RetryException, retry
from dotenv import load_dotenv
from datetime import datetime, timedelta
from clients.firestore_client import FirestoreClient
from clients.monitoring_client import GoogleMonitoringClient, stats_profile

logger = logging.getLogger(__name__)


load_dotenv()
LAST_FM_API_KEY = os.getenv("LAST_FM_API_KEY")
LAST_FM_BASE_URL = "http://ws.audioscrobbler.com/2.0"
HEADERS = {"User-Agent": "LasthopWeb/1.0"}
ADD_ARTIST_TAGS = True
INCLUDE_THIS_YEAR = False


class LastfmClient:
    def __init__(self, lastfm_username: str, lastfm_join_date: datetime):
        self.username = lastfm_username
        self.join_date = lastfm_join_date.replace(tzinfo=pytz.UTC)
        self.api_key = LAST_FM_API_KEY
        today = datetime.utcnow()
        if INCLUDE_THIS_YEAR:
            self.stats_start_date = today
        else:
            if today.month == 2 and today.day == 29:  # Leap year
                self.stats_start_date = today.replace(year=today.year - 4)
            else:
                self.stats_start_date = today.replace(year=today.year - 1)
        logger.info(f"Stats start date for {lastfm_username}: {self.stats_start_date}")

    @classmethod
    @retry(RetryException, tries=3, delay=1, backoff=3, _logger=logger)
    def last_fm_api_query(cls, api_method: str, **args) -> dict:
        """
        A GET request to Last.fm API
        """
        params = [f"&{k.replace('_', '')}={v}" for k, v in args.items()]
        api_url = (
            f"{LAST_FM_BASE_URL}/?method={api_method}"
            f"&api_key={LAST_FM_API_KEY}"
            f"&format=json"
            f"{''.join(params)}"
        )

        try:
            response = requests.get(api_url, headers=HEADERS)
            if response.status_code in RetryException.retry_codes:
                raise RetryException(
                    f"WARNING:  {response.status_code} status code for {api_method}. {response.content}"
                )
            return response.json()

        except RetryException:
            GoogleMonitoringClient().increment_thread("retry-exception")
            raise
        except Exception:
            GoogleMonitoringClient().increment_thread("lastfm-exception")
            logger.exception(f"Unhandled exception for Last.fm {api_method}")

    def get_stats(self, tz_offset: int) -> (list, datetime):
        data = None
        date_cached = None
        artist_tags = None
        cached_data = FirestoreClient().get_user_data(self.username)
        if cached_data:
            date_cached = cached_data.get("date_cached")
            if date_cached and date_cached.date() == datetime.utcnow().date():
                logger.info(f"Data cached for {self.username} at {date_cached} -> Returning cached data")
                data = cached_data["data"]
                artist_tags = cached_data.get("artist_tags")

                # TODO remove eventually
                if data and data[0].get("scrobble_list"):
                    logger.info(f"Old cache")
                    data = None

        if not data:
            data = self.get_data_for_all_days()
            date_cached = datetime.utcnow()
            FirestoreClient().set_user_data(self.username, data, datetime.utcnow())
            FirestoreClient().increment_user_days_visited(self.username)
        summary = self.summarize_and_filter_for_timezone(data, tz_offset, artist_tags)
        return summary, date_cached.replace(tzinfo=pytz.UTC) - timedelta(minutes=tz_offset)

    @classmethod
    def get_lastfm_user_data(cls, username: str) -> dict:
        """
        Get the User's Last.fm profile information
        """
        logger.info(f"Getting last.fm user data for {username}")
        api_response = cls.last_fm_api_query(
            api_method="user.getinfo", username=username
        )
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

    @stats_profile
    def summarize_and_filter_for_timezone(self, data: list, tz_offset: int, artist_tags: dict = None) -> list:
        """
        Summarize the user's last.fm stats
        """
        logger.info(f"Summarizing data for {self.username} timezone offset = {tz_offset}...")
        result = []
        today = (datetime.utcnow()).replace(tzinfo=pytz.UTC) - timedelta(minutes=tz_offset)
        start_time = today.replace(hour=0).replace(minute=0).replace(
            second=0).replace(
            microsecond=0
        ) + timedelta(minutes=tz_offset)
        end_time = start_time + timedelta(hours=23, minutes=59, seconds=59, microseconds=999999)
        for line in data:
            data = line["data"]
            artist_scrobble_dict = {}
            scrobble_list = []
            start_time = start_time.replace(year=line["day"].year)
            end_time = end_time.replace(year=line["day"].year)

            for scrobble in data:
                timestamp = scrobble["timestamp"]
                if not timestamp:
                    continue

                scrobbled_date = datetime.fromtimestamp(int(timestamp), tz=pytz.UTC)

                if not (start_time <= scrobbled_date <= end_time):
                    continue

                artist = scrobble["artist"]
                track_name = scrobble["track_name"]

                track_date_dict = {
                    "track_name": track_name,
                    "date": scrobbled_date - timedelta(minutes=tz_offset),
                    "artist": artist,
                }
                if not artist_scrobble_dict.get(artist):
                    artist_scrobble_dict[artist] = {
                        "playcount": 1,
                        "tracks": [track_date_dict],
                    }
                else:
                    artist_scrobble_dict[artist]["playcount"] += 1
                    artist_scrobble_dict[artist]["tracks"].append(track_date_dict)
                scrobble_list.append(track_date_dict)
            if artist_scrobble_dict:
                artist_scrobble_list = []
                for artist, track_data in artist_scrobble_dict.items():
                    artist_scrobble_list.append(
                        {"artist": artist, "track_data": track_data}
                    )
                artist_scrobble_list = sorted(
                    artist_scrobble_list,
                    key=lambda d: d["track_data"]["playcount"],
                    reverse=True,
                )
                if ADD_ARTIST_TAGS:
                    top_artist_d = artist_scrobble_list[0]["artist"].lower()
                    if not artist_tags:
                        artist_tags = {}
                    if artist_tags.get(top_artist_d):
                        artist_scrobble_list[0]["tag"] = artist_tags[top_artist_d]
                    else:
                        top_tag = self.get_top_tag_for_artist(top_artist_d)
                        if top_tag:
                            artist_tags.update({top_artist_d: top_tag})
                            FirestoreClient().update_user_artist_tags(self.username, artist_tags)
                            artist_scrobble_list[0]["tag"] = top_tag
                result.append(
                    {
                        "day": start_time - timedelta(minutes=tz_offset),
                        "data": artist_scrobble_list,
                        "scrobble_list": scrobble_list,
                    }
                )
        sorted_result = sorted(result, key=lambda d: d["day"], reverse=True)
        return sorted_result

    @stats_profile
    def get_data_for_all_days(self) -> list:
        """
        Query last.fm for the user's scrobbles for each year
        """
        logger.info(f"Getting data from Last.fm for {self.username}...")
        days = self.get_list_of_dates()
        jobs = []
        queue = multiprocessing.Queue()
        for day in days:
            job = multiprocessing.Process(
                target=self.get_data_for_day, args=(day, queue)
            )
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

    def get_list_of_dates(self) -> [datetime]:
        """
        A list of dates for each year since the user's last.fm  join date
        :return:
        """
        date_to_process = self.stats_start_date
        days = []
        while date_to_process.date() >= self.join_date.date():
            days.append(date_to_process)
            if date_to_process.month == 2 and date_to_process.day == 29:  # Leap year
                date_to_process = date_to_process.replace(year=date_to_process.year - 4)
            else:
                date_to_process = date_to_process.replace(year=date_to_process.year - 1)
        return days

    def get_data_for_day(self, day: datetime, queue: multiprocessing.Queue):
        """
        Query last.fm for the user's scrobbles on a given day
        """
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

        result = {"day": day, "data": data}
        queue.put(result)

    def get_lastfm_tracks_for_day(self, date: datetime) -> list:
        lastfm_response = self.lastfm_api_get_tracks(date, 1)
        lastfm_tracks = lastfm_response.get("recenttracks", {}).get("track")
        num_pages = int(
            lastfm_response.get("recenttracks", {})
            .get("@attr", {})
            .get("totalPages", 0)
        )
        if num_pages > 1:
            for page_num in range(2, num_pages + 1):
                lastfm_response = self.lastfm_api_get_tracks(date, page_num)
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
        return lastfm_tracks or []

    @stats_profile
    def get_top_tag_for_artist(self, artist: str) -> str:
        firestore_client = FirestoreClient()
        top_tag = firestore_client.get_artist_tag(artist)
        if not top_tag:
            logger.info(f"Getting top tag for {artist}...")
            api_response = self.last_fm_api_query(
                api_method="artist.gettoptags", artist=artist
            )
            tag_list = api_response.get("toptags", {}).get("tag", [])
            for tag in tag_list:
                tag_name = tag.get("name")
                if "seen live" not in tag_name:
                    top_tag = tag_name
                    break
            if top_tag:
                firestore_client.set_artist_tag(artist, top_tag)
        return top_tag.lower() if top_tag else None

    def lastfm_api_get_tracks(self, date: datetime, page_num: int) -> dict:
        """
        Get data from Last.fm api
        :param date: Day for which to get data
        :param page_num: Page number.
        :return: JSON response from API.
        """
        date = date.replace(tzinfo=pytz.UTC)
        date_start = date - timedelta(hours=48)

        date_end = date + timedelta(hours=48)
        date_start_epoch = int(date_start.timestamp())
        date_end_epoch = int(date_end.timestamp())

        logger.info(f"Last.fm query start date: {date_start}")
        logger.info(f"Last.fm query end date: {date_end}")

        api_response = self.last_fm_api_query(
            api_method="user.getrecenttracks",
            username=self.username,
            _from=date_start_epoch,
            to=date_end_epoch,
            page=page_num,
        )
        return api_response
