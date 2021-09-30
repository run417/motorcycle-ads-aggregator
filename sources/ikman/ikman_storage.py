from __future__ import annotations

from typing import TYPE_CHECKING

import logger

if TYPE_CHECKING:
    from mysql.connector import MySQLConnection

logger = logger.get_logger("ikman.storage")


class IkmanStorage:
    FROM_SERVER = 1
    FROM_LOCAL = 0

    GET_LOCAL_ADS_QUERY: str = f"SELECT ad_id FROM ad ORDER BY datetime DESC"
    SAVE_AD_QUERY: str = "INSERT INTO ad(ad_id, status, description, datetime, url, title, money, deactivates, " \
                         "item_condition, slug, area, location, type, info) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, " \
                         "%s, %s, %s, %s, %s, %s) "
    SAVE_PHONE_QUERY: str = "INSERT INTO phone(ad_id, name, number, verified) VALUES(%s, %s, %s, %s)"
    SAVE_PROPERTIES_QUERY: str = "INSERT INTO properties(ad_id, prop_key, prop_value) VALUES(%s, %s, %s)"

    def __init__(self, connection: MySQLConnection):
        self._QUEUE_LIMIT = 10
        self._connection = connection
        self._local = {}
        self._latest = []
        self._get_all_local()

        self._fetched = {}  # ads fetched in this session also in local. (_fetched mod queue_size is not in local)
        self._queue_count = 0
        self._total_saved = 0
        self._discarded_count = 0
        self._ad_tuple_list = []
        self._phone_tuple_list = []
        self._properties_tuple_list = []

        self._fetched_all_latest = False

    def save(self):
        if self._queue_count == 0:
            logger.info("No ads in save queue")
            return
        logger.info("Start saving to database")
        with self._connection.cursor() as cursor:
            cursor.executemany(IkmanStorage.SAVE_AD_QUERY, self._ad_tuple_list)
            if cursor.rowcount != len(self._ad_tuple_list):
                logger.warning("some ads were not saved!")
            cursor.executemany(IkmanStorage.SAVE_PHONE_QUERY, self._phone_tuple_list)
            if cursor.rowcount != len(self._phone_tuple_list):
                logger.warning("some phone data were not saved!")
            cursor.executemany(IkmanStorage.SAVE_PROPERTIES_QUERY, self._properties_tuple_list)
            if cursor.rowcount != len(self._properties_tuple_list):
                logger.warning("some properties were not saved!")
            self._connection.commit()
        self._total_saved += self._queue_count
        logger.info(f"Ads fetched: {len(self._fetched)}, Discarded: {self._discarded_count}")
        logger.info(f"Saved {self._queue_count} ads. Total saved: {self._total_saved}")

        self._clear_queue()

    def _clear_queue(self):
        logger.info("Clearing save queue")
        self._ad_tuple_list.clear()
        self._phone_tuple_list.clear()
        self._properties_tuple_list.clear()
        self._queue_count = 0

    def queue(self, __fetched):
        """Place fetched ad in queue.
        The ad will be saved later when queue reaches a specific size or when Agent finishes running

        :param __fetched: a list of three items [ad info tuple, [list of phone tuples], [list of properties tuples]]
        :return:
        """
        self._ad_tuple_list.append(__fetched[0])
        self._phone_tuple_list.extend(__fetched[1])
        self._properties_tuple_list.extend(__fetched[2])
        self._fetched[__fetched[0][0]] = IkmanStorage.FROM_SERVER
        self._queue_count += 1
        logger.info(f"queueing ad {__fetched[0][0]},save queue size: {self._queue_count}/{self._QUEUE_LIMIT}")

        if self._queue_count == self._QUEUE_LIMIT:
            self.save()

    def get_fetch_count(self) -> int:
        return len(self._fetched)

    def filter_list(self, _list):
        """removes fetched ads from list and returns other in a list

        :param _list: a list of strings - ad ids
        :return:
        """
        logger.info("Filtering fetch queue")
        discarded_ads = []
        _filtered = []
        for _id in _list:
            if _id not in self._local and _id not in self._fetched:
                _filtered.append(_id)
            else:
                self._discarded_count += 1
                discarded_ads.append((_id, "local" if _id in self._local else "fetched"))

        logger.info(f"Discarded ads in this page: {len(discarded_ads)}, {discarded_ads}")
        logger.info(f"Ads available in this page: {len(_filtered)}")
        return _filtered

    def filter_list_new(self, _list) -> list:
        """removes fetched ads and older ads than the latest ad and returns list

        :param _list: a list of tuples. Each tuple has two elements (url: str, ad_id: str)
        :return:
        """

        logger.info("Filtering new ads in fetch queue")
        _filtered = []
        logger.info(f"latest: {self._latest}")

        if len(self._latest) == 0:
            logger.info("No latest ads to compare. Switching fetch type to all within limit")
            return self.filter_list(_list)

        discarded_ads = []
        count = 0
        for _id in _list:
            count += 1
            if _id in self._latest:
                logger.info(f"Matched {_id} in {self._latest}, position in list: {count} (1-index based)")
                logger.info(f"Found {len(_filtered) + len(self._fetched)} new ads")
                self._found_all_latest()
                break
            if _id not in self._local and _id not in self._fetched:
                _filtered.append(_id)
            else:
                logger.info(f"{_id} is in local. Bumped ad?")
                # at this point there shouldn't be any ads in filtered list.
                # if there is then the top ad is bumped up or something
                # the ad that hit here is in local but not latest local ad
                self._discarded_count += 1
                discarded_ads.append((_id, "local" if _id in self._local else "fetched"))

        logger.info(f"Discarded ads in this page: {len(discarded_ads)}, {discarded_ads}")
        logger.info(f"Ads available in this page: {len(_filtered)}")
        return _filtered

    def _found_all_latest(self):
        logger.info("Latest local found in server")
        self._fetched_all_latest = True

    def is_up_to_date(self) -> bool:
        return self._fetched_all_latest

    def _get_all_local(self):
        with self._connection.cursor() as cursor:
            cursor.execute(IkmanStorage.GET_LOCAL_ADS_QUERY)
            # local ads is list of tuples. Each tuple contains a single element i.e ad_id
            local_ads: list = cursor.fetchall()

            count = 0
            # convert list into dict
            for local_ad in local_ads:
                if count < 3:
                    self._latest.append(local_ad[0])
                    count += 1
                self._local[local_ad[0]] = IkmanStorage.FROM_LOCAL
            logger.info(f"Queried latest {len(local_ads)} ads from local storage")

            if len(self._local) == 0:
                logger.info("No local ads")
