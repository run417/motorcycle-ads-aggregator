from __future__ import annotations

from typing import TYPE_CHECKING

import logger
from sources.agent import Agent
from requests.exceptions import HTTPError
from app_exceptions import RiyasewanaContentNotFound

if TYPE_CHECKING:
    from fetcher import Fetcher
    from riyasewana_parser import RiyasewanaParser
    from riyasewana_storage import RiyasewanaStorage

logger = logger.get_logger("riyasewana.agent")


class RiyasewanaAgent(Agent):
    def __init__(self, fetcher: Fetcher, parser: RiyasewanaParser, storage: RiyasewanaStorage, source_props: dict):
        self._fetcher = fetcher
        self._parser = parser
        self._storage = storage
        self._LIST_BASE_URL = source_props["LIST_URL"]
        self._FETCH_LIMIT = source_props["FETCH_LIMIT"]
        self._FETCH_TYPE = source_props["FETCH_TYPE"]
        self._MAX_FAILS = source_props["MAX_FAILS"]

        self._total_pages = 1
        self._page_count = 1

        self._fetch_queue = []

        self._failure_count = 0

        self._IS_FETCH_TYPE_NEW = False if self._FETCH_TYPE == "all" else True

    def run(self):
        logger.info("Running Riyasewana agent")
        logger.info(f"Fetch type: {'New ads' if self._IS_FETCH_TYPE_NEW else 'All ads'} - Limit={self._FETCH_LIMIT}")
        while self._has_next():
            logger.info(f"Fetch limit: {self._FETCH_LIMIT}")
            try:
                response = self._fetcher.get(self._gen_list_url())
                response.raise_for_status()
                self._fetch_queue = self._parser.parse_list(response)
            except HTTPError as hte:
                logger.warning(hte)
                self._handle_failure()
                self._inc_page_count()
                continue
            except RiyasewanaContentNotFound as ex:
                logger.warning(ex)
                self._handle_failure()
                self._inc_page_count()
                continue
            except AttributeError as ex:
                logger.exception(ex)
                self._handle_failure()
                self._inc_page_count()
                continue
            self._filter_list()
            self._get_details()
            self._inc_page_count()
        # save any leftover fetched ads in queue
        self._storage.save()
        logger.info(f"Finished running agent on source Riyasewana")

    def _handle_failure(self):
        self._failure_count += 1
        if self._failure_count > self._MAX_FAILS:
            logger.critical("Too many failures. Will not continue running agent")

    def _failure_status(self) -> bool:
        """returns false as a stop condition for the agent"""
        return self._failure_count <= self._MAX_FAILS

    def _gen_list_url(self) -> str:
        if self._page_count == 1:
            return self._LIST_BASE_URL
        return self._LIST_BASE_URL + "?page=" + str(self._page_count)

    def _inc_page_count(self):
        # should be called after the first list parse
        if self._page_count == 1:
            self._total_pages = self._get_total_pages()
        self._page_count += 1

    def _get_total_pages(self) -> int:
        _pages = self._parser.get_total_pages()
        if _pages == 0:
            # error occurred in initial page
            logger.warning("Total page count not available. Probable error parsing the initial page")
            self._handle_failure()
        return _pages

    def _get_details(self):
        for el in self._fetch_queue:

            if not self._failure_status():
                logger.warning("Stopping agent")
                break

            if not self._is_below_limit():
                logger.info("Fetch limit reached")
                break

            # el is a tuple (url, id)
            detail_url = el[0]
            ad_id = el[1]
            try:
                response = self._fetcher.get(detail_url)
                response.raise_for_status()
                ad_detail = self._parser.parse_detail(response)
            except HTTPError as hte:
                logger.warning(hte)
                self._handle_failure()
                continue
            except RiyasewanaContentNotFound as ex:
                logger.warning(ex)
                self._handle_failure()
                continue
            except AttributeError as ex:
                logger.exception(ex)
                self._handle_failure()
                continue
            ad_detail["ad_id"] = ad_id
            ad_detail["url"] = detail_url
            self._storage.queue(ad_detail)
        logger.info("Clearing fetch queue")
        self._fetch_queue.clear()

    def _filter_list(self):
        if self._IS_FETCH_TYPE_NEW:
            self._fetch_queue = self._storage.filter_list_new(self._fetch_queue)
        else:
            self._fetch_queue = self._storage.filter_list(self._fetch_queue)

    def _is_up_to_date(self) -> bool:
        if self._IS_FETCH_TYPE_NEW:
            return self._storage.is_up_to_date()

    def _is_below_limit(self) -> bool:
        if self._FETCH_LIMIT == 0:
            return True
        return self._storage.get_fetch_count() < self._FETCH_LIMIT

    def _has_next_page(self) -> bool:
        return self._total_pages >= self._page_count

    def _has_next(self) -> bool:
        if self._IS_FETCH_TYPE_NEW:
            if self._is_up_to_date():
                logger.info(f"All new ads fetched within limit {self._FETCH_LIMIT}")
            if not self._is_below_limit() and not self._is_up_to_date():
                logger.info("Limit reached before finding all new ads")
            if not self._has_next_page() and not self._is_up_to_date():
                logger.info("All fetched ads are new. However, latest local was not found in server.")
            return not self._is_up_to_date() and self._is_below_limit() and self._has_next_page() and self._failure_status()

        return self._is_below_limit() and self._has_next_page() and self._failure_status()
