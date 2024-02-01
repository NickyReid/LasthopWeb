import random
import time
from functools import wraps


class RetryException(Exception):
    retry_codes = [429, 500, 502, 503, 504]
    pass


def retry(exception_to_check, tries=4, delay=0, backoff=0, _logger=None, randomize=False):
    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            remaining_tries, wait = tries, delay
            while remaining_tries > 1:
                try:
                    return f(*args, **kwargs)
                except exception_to_check:
                    msg = "%s, Retrying in %d seconds..." % (
                        str(exception_to_check),
                        wait,
                    )
                    if _logger:
                        _logger.exception(msg)
                    else:
                        print(msg)
                    if randomize:
                        wait += random.random()
                        print(f"Waiting for {wait} seconds")
                    time.sleep(wait)
                    remaining_tries -= 1
                    wait *= backoff
            return f(*args, **kwargs)

        return f_retry

    return deco_retry
