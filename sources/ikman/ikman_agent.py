from __future__ import annotations

from typing import TYPE_CHECKING

from requests.exceptions import HTTPError
from app_exceptions import IkmanNoPaginationData, IkmanListNotFound

import logger
from document_type import DocType
from sources.agent import Agent


if TYPE_CHECKING:
    from ikman_storage import IkmanStorage
    from ikman_parser import IkmanParser
    from fetcher import Fetcher

logger = logger.get_logger("ikman.agent")


class IkmanAgent(Agent):
    def __init__(self, fetcher: Fetcher, parser: IkmanParser, storage: IkmanStorage, source_props: dict):
        self._fetcher = fetcher
        self._parser = parser
        self._storage = storage
        self._options = source_props
        self._LIST_BASE_URL = source_props["LIST_URL"]
        self._DET_BASE_URL = source_props["DET_URL"]
        self._FETCH_LIMIT = source_props["FETCH_LIMIT"]
        self._FETCH_TYPE = source_props["FETCH_TYPE"]
        self._MAX_FAILS = source_props["MAX_FAILS"]

        self._fetch_queue = []

        # used to generate page url. Different from whatever data the page itself provides e.g. activePage
        self._page_count = 1
        self._total_pages = 1

        self._failure_count = 0

        self._IS_FETCH_TYPE_NEW = False if self._FETCH_TYPE == "all" else True

    def run(self):
        logger.info(f"Running Ikman agent")
        logger.info(f"Fetch type: {'New ads' if self._IS_FETCH_TYPE_NEW else 'All ads'} - Limit={self._FETCH_LIMIT}")
        while self._has_next():
            logger.info(f"Fetch limit: {self._FETCH_LIMIT}")
            try:
                response = self._fetcher.get(self._gen_page_url())
                response.raise_for_status()
                self._set_id_list(self._parser.parse(response, DocType.LIST))
            except HTTPError as hte:
                logger.warning(hte)
                self._handle_failure()
                self._inc_page_count()
                continue
            except IkmanListNotFound as ex:
                logger.warning(ex)
                self._handle_failure()
                self._inc_page_count()
                continue
            except IkmanNoPaginationData as ex:
                logger.warning(ex)
                self._handle_failure()
                logger.critical("Stopping agent")
                break

            self._filter_list()
            self._get_details()
            self._inc_page_count()

        # save any leftover fetched ads in queue
        self._storage.save()
        logger.info(f"Finished running agent on source Ikman")

    def _gen_page_url(self) -> str:
        # get next page
        return self._LIST_BASE_URL + str(self._page_count)

    def _handle_failure(self):
        self._failure_count += 1
        if self._failure_count > self._MAX_FAILS:
            logger.critical("Too many failures. Will not continue running agent")

    def _failure_status(self) -> bool:
        """returns false as a stop condition for the agent"""
        return self._failure_count <= self._MAX_FAILS

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
        for __id in self._fetch_queue:
            if not self._failure_status():
                logger.warning("Stopping agent")
                break

            if not self._is_below_limit():
                logger.info("Fetch limit reached")
                break
            try:
                response = self._fetcher.get(self._DET_BASE_URL + __id)
                response.raise_for_status()
                self._storage.queue(self._parser.parse(response, DocType.DETAIL))
            except HTTPError as hte:
                logger.warning(hte)
                self._handle_failure()
                continue
            except IkmanNoPaginationData as ex:
                logger.warning(ex)
                self._handle_failure()
                continue
            except KeyError as ex:
                logger.exception(ex)
                self._handle_failure()
                continue
        logger.info("Clearing fetch queue list")
        self._fetch_queue.clear()

    def _set_id_list(self, _page_ids: list):
        self._fetch_queue = _page_ids

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
