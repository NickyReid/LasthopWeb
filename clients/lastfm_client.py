import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pytz
import requests
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

from clients import RetryException, retry
from clients.cache import Cache
from clients.monitoring_client import GoogleMonitoringClient, stats_profile

logger = logging.getLogger(__name__)


load_dotenv()
LAST_FM_API_KEY = os.getenv("LAST_FM_API_KEY")
LAST_FM_BASE_URL = "http://ws.audioscrobbler.com/2.0"
HEADERS = {"User-Agent": "LasthopWeb/1.0"}
ADD_ARTIST_TAGS = True
INCLUDE_THIS_YEAR = False
MAX_WORKERS = int(os.getenv("RECENT_TRACKS_WORKERS") or 20)


class LastfmClient:
    def __init__(self, lastfm_username: str, lastfm_join_date: datetime, tz_offset: int = 0):
        self.username = lastfm_username
        self.join_date = lastfm_join_date.replace(tzinfo=pytz.UTC)
        self.tz_offset = tz_offset
        self.api_key = LAST_FM_API_KEY
        self.cache = Cache()
        today = datetime.utcnow() - timedelta(minutes=tz_offset)
        if INCLUDE_THIS_YEAR:
            self.stats_start_date = today
        else:
            if today.month == 2 and today.day == 29:  # Leap year
                self.stats_start_date = today.replace(year=today.year - 4)
            else:
                self.stats_start_date = today.replace(year=today.year - 1)
        logger.info(f"Stats start date for {lastfm_username}: {self.stats_start_date} tz_offset: {tz_offset}")

    @classmethod
    @retry(RetryException, tries=3, delay=1, backoff=3, _logger=logger, randomize=True)
    def last_fm_api_query(cls, api_method: str, **args) -> dict:
        """
        A GET request to Last.fm API
        """
        params = [f"&{k.replace('_', '')}={v}" for k, v in args.items()]
        api_url = (
            f"{LAST_FM_BASE_URL}/?method={api_method}"
            f"&api_key={LAST_FM_API_KEY}"
            f"&format=json"
            f"&limit=200"
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

    def get_stats(self) -> (list, datetime):
        data = None
        date_cached = None
        artist_tags = None
        cached_data = self.cache.get_user_data(self.username)
        if cached_data:
            date_cached = cached_data.get("date_cached")
            if date_cached:
                tz_offset_cached = cached_data.get("tz_offset")
                date_cached_localized = (date_cached - timedelta(minutes=self.tz_offset)).replace(tzinfo=pytz.UTC)
                now_localized = (datetime.utcnow() - timedelta(minutes=self.tz_offset)).replace(tzinfo=pytz.UTC)
                logger.info(f"now_localized = {now_localized}; date_cached_localized = {date_cached_localized}")
                if date_cached_localized.date() == now_localized.date():
                    if self.tz_offset == tz_offset_cached:
                        logger.info(f"Data cached for {self.username} at {date_cached_localized} -> Data is for today")
                        data = cached_data["data"]
                        artist_tags = cached_data.get("artist_tags")
                    else:
                        logger.info(
                            f"Data cached for {self.username} at {date_cached} -> Data is not for this timezone")
                else:
                    logger.info(f"Data cached for {self.username} at {date_cached} -> Data is not for today")

        if not data:
            dates = self.get_list_of_year_dates()
            data = self.get_data_for_days(dates)
            date_cached = datetime.utcnow()
            self.cache.set_user_data(self.username, data, datetime.utcnow(), self.tz_offset)
            self.cache.increment_user_days_visited(self.username)
        summary = self.summarize_and_filter_for_timezone(data, artist_tags)
        return summary, date_cached.replace(tzinfo=pytz.UTC) - timedelta(minutes=self.tz_offset)

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
    def summarize_and_filter_for_timezone(self, data: list, artist_tags: dict = None) -> list:
        """
        Summarize the user's last.fm stats
        """
        logger.info(f"Summarizing data for {self.username} timezone offset = {self.tz_offset}...")
        result = []
        today = (datetime.utcnow()).replace(tzinfo=pytz.UTC) - timedelta(minutes=self.tz_offset)
        o_start_time = today.replace(hour=0).replace(minute=0).replace(
            second=0).replace(
            microsecond=0
        ) + timedelta(minutes=self.tz_offset)
        for line in data:
            start_time = o_start_time
            data = line["data"]
            artist_scrobble_dict = {}
            scrobble_list = []
            year_diff = abs(o_start_time.year - line["day"].year)
            try:
                start_time = o_start_time - relativedelta(years=year_diff)
                end_time = start_time + timedelta(hours=23, minutes=59, seconds=59, microseconds=999999)
            except ValueError:
                logger.exception(start_time)
                continue
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
                    "date": scrobbled_date - timedelta(minutes=self.tz_offset),
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
                            self.cache.update_user_artist_tags(self.username, artist_tags)
                            artist_scrobble_list[0]["tag"] = top_tag
                result.append(
                    {
                        "day": start_time - timedelta(minutes=self.tz_offset),
                        "data": artist_scrobble_list,
                        "scrobble_list": scrobble_list,
                    }
                )
        sorted_result = sorted(result, key=lambda d: d["day"], reverse=True)
        return sorted_result

    @stats_profile
    def get_data_for_days(self, list_of_dates: [datetime]) -> list:
        """
        Query last.fm for the user's scrobbles for each year
        """
        result = []
        if list_of_dates:
            logger.info(f"Getting data from Last.fm for {self.username}...")
            with ThreadPoolExecutor(max_workers=len(list_of_dates)) as executor:
                futures = []
                for day in list_of_dates:
                    futures.append(executor.submit(self.get_data_for_day, day))

                for future in futures:
                    result.append(future.result())

        return result

    def get_list_of_year_dates(self) -> [datetime]:
        """
        A list of dates for each year since the user's last.fm  join date
        """
        date_to_process = self.stats_start_date

        days = []
        while date_to_process.date() >= self.join_date.date():
            days.append(date_to_process)
            if date_to_process.month == 2 and date_to_process.day == 29:  # Leap year
                date_to_process = date_to_process - relativedelta(years=4)
            else:
                date_to_process = date_to_process - relativedelta(years=1)
        return days

    @staticmethod
    def recenttracks_response_summary(raw_data: []) -> []:
        data = []
        for line in raw_data:
            data_dict = {}
            artist = line.get("artist", {}).get("#text")
            title = line.get("name")
            data_dict["artist"] = artist
            data_dict["track_name"] = title
            data_dict["timestamp"] = line.get("date", {}).get("uts")
            data.append(data_dict)
        return data

    def get_data_for_day(self, day: datetime):
        """
        Query last.fm for the user's scrobbles on a given day
        """
        raw_data = self.get_lastfm_tracks_for_day(day)
        data = self.recenttracks_response_summary(raw_data)
        result = {"day": day, "data": data}
        return result

    def get_lastfm_tracks_for_day(self, date: datetime) -> list:
        logger.debug(f"Getting data from Last.fm for {self.username} date:{date}...")
        lastfm_response = self.lastfm_api_get_scrobbles(date, 1)
        lastfm_tracks = lastfm_response.get("recenttracks", {}).get("track")
        num_pages = int(
            lastfm_response.get("recenttracks", {})
            .get("@attr", {})
            .get("totalPages", 0)
        )
        if num_pages > 1:
            for page_num in range(2, num_pages + 1):
                lastfm_response = self.lastfm_api_get_scrobbles(date, page_num)
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
        top_tag = self.cache.get_artist_tag(artist)
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
                self.cache.set_artist_tag(artist, top_tag)
        return top_tag.lower() if top_tag else None

    def lastfm_api_get_scrobbles(self, date: datetime, page_num: int) -> dict:
        """
        Get data from Last.fm api
        :param date: Day for which to get data
        :param page_num: Page number.
        :return: JSON response from API.
        """
        date = (date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC)) + timedelta(minutes=self.tz_offset)
        date_start = date
        date_end = date + timedelta(hours=24)

        date_start_epoch = int(date_start.timestamp())
        date_end_epoch = int(date_end.timestamp())
        logger.info(f"Last.fm query date: {date}")
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

    @stats_profile
    def get_scrobble_hashes_since(self, start_date: datetime):
        """
        Get a set of hashes of scrobbles since start_date
        """
        date_start_epoch = int(start_date.timestamp())
        page_num = 1
        track_hashes, num_pages = self.get_recent_track_hashes_by_page(date_start_epoch, page_num)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            while num_pages > page_num:
                logger.debug(f"get_scrobble_hashes_since getting page {page_num} of {num_pages}")
                page_num = page_num + 1
                futures.append(executor.submit(self.get_recent_track_hashes_by_page,
                                               **{"date_start_epoch": date_start_epoch, "page_num": page_num}))

            for future in futures:
                track_hashes.update(future.result()[0])
        return track_hashes

    def get_recent_track_hashes_by_page(self, date_start_epoch: int, page_num: int) -> (set, int):
        api_response = self.last_fm_api_query(
            api_method="user.getrecenttracks",
            username=self.username,
            _from=date_start_epoch,
            page=page_num,
        )
        num_pages = int(
            api_response.get("recenttracks", {}).get("@attr", {}).get("totalPages", 0)
        )
        lastfm_tracks = api_response.get("recenttracks", {}).get("track", [])
        if lastfm_tracks:
            if isinstance(lastfm_tracks, dict):
                lastfm_tracks = [lastfm_tracks]

            if lastfm_tracks:
                if lastfm_tracks[0].get("@attr", {}).get("nowplaying", False):
                    del lastfm_tracks[0]

        track_hashes = set()
        for line in lastfm_tracks:
            hash_key = hash(f'{line.get("artist", {}).get("#text")}{line.get("name")}'.lower())
            track_hashes.add(hash_key)
        return track_hashes, num_pages
