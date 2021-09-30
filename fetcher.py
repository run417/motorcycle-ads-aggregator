import requests
import time
import logger

logger = logger.get_logger("Fetcher")


class Fetcher:
    def __init__(self, headers: dict, wait_seconds: int):
        self._headers = headers
        self._wait_seconds = wait_seconds
        self._request_count = 0

    def get(self, _url: str) -> requests.Response:
        logger.info(f"Sending request to url: {_url}")
        response = requests.get(_url, headers=self._headers)
        self._request_count += 1
        logger.info(f"Server responded with {response.status_code}")
        logger.info(f"Waiting for {self._wait_seconds} seconds")
        time.sleep(self._wait_seconds)
        return response

    def get_request_count(self)-> int:
        return self._request_count
