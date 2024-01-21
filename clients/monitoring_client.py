import time
import uuid
import logging

from threading import Thread
from google.cloud import monitoring_v3


def stats_profile(func):
    def timed(*args, **kwargs):
        ts = time.time()
        result = func(*args, **kwargs)
        te = time.time()
        time_taken = int(round((te - ts) * 1000, 1))
        if time_taken:
            GoogleMonitoringClient().time_series_thread(func.__name__, time_taken)
        print("Function", func.__name__, "time:", time_taken, "ms")
        print()
        return result

    return timed


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class GoogleMonitoringClient(metaclass=Singleton):
    def __init__(self):
        self.client = monitoring_v3.MetricServiceClient()
        self.project_name = "projects/fiery-azimuth-410611"

    def increment_thread(self, metric_type, value=1):
        t = Thread(
            target=self._increment,
            name="increment",
            args=(
                metric_type,
                value,
            ),
        )
        t.start()

    def time_series_thread(self, metric_type, time_taken):
        t = Thread(
            target=self._time_series,
            name="time_series",
            args=(metric_type, time_taken),
        )
        t.start()

    def _time_series(self, metric_type, time_taken):
        try:
            client = monitoring_v3.MetricServiceClient()
            series = monitoring_v3.TimeSeries()
            series.metric.type = f"custom.googleapis.com/{metric_type}"
            series.resource.type = "global"
            series.metric.labels["TestLabel"] = f"My Label Data{str(uuid.uuid4())}"
            end_time = time.time()
            end_time_seconds = int(end_time)
            end_time_nanos = int((end_time - end_time_seconds) * 10**9)
            interval = monitoring_v3.TimeInterval(
                {"end_time": {"seconds": end_time_seconds, "nanos": end_time_nanos}}
            )
            point = monitoring_v3.Point(
                {"interval": interval, "value": {"int64_value": time_taken}}
            )
            series.points = [point]
            client.create_time_series(name=self.project_name, time_series=[series])
        except:
            logging.exception(f"Error sending stats")

    def _increment(self, metric_type: str, value=1):
        client = monitoring_v3.MetricServiceClient()
        series = monitoring_v3.TimeSeries()
        series.metric.type = f"custom.googleapis.com/{metric_type}"
        series.resource.type = "global"
        series.metric.labels["TestLabel"] = f"My Label Data{str(uuid.uuid4())}"
        now = time.time()
        seconds = int(now)
        nanos = int((now - seconds) * 10**9)
        interval = monitoring_v3.TimeInterval(
            {"end_time": {"seconds": seconds, "nanos": nanos}}
        )
        point = monitoring_v3.Point(
            {"interval": interval, "value": {"int64_value": value}}
        )
        series.points = [point]
        client.create_time_series(name=self.project_name, time_series=[series])
