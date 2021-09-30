import math

from requests import Response
from app_exceptions import IkmanListNotFound, IkmanNoPaginationData

import logger
from document_type import DocType

logger = logger.get_logger("ikman.parser")


class IkmanParser:

    def __init__(self):
        self._current_page_no = 0
        self._total_ads = 0
        self._ads_per_page = 0

        self._total_pages_approx = 0

        self._KEY_LIST = ["id", "status", "description", "date", "url", "title", "money", "deactivates", "contact_card",
                          "item_condition", "slug", "area", "location", "type", "info", "properties"]

    def parse(self, _response: Response, _type):
        _response_json = _response.json()
        if _type == DocType.LIST:
            if "ads" not in _response_json:
                raise IkmanListNotFound("No ad list found in response. Cannot parse further")
            self._set_pagination_data(_response_json)
            id_list = self._get_ad_id_list(_response_json["ads"])
            return id_list

        if _type == DocType.DETAIL:
            return self._get_ad_details(_response_json)

    def parse_list(self, _response):
        _response_json = _response.json()
        if "ads" not in _response_json:
            raise IkmanListNotFound("No ad list found in response. Cannot parse further")
        self._set_pagination_data(_response_json)
        id_list = self._get_ad_id_list(_response_json["ads"])
        return id_list

    def parse_detail(self, _response):
        _response_json = _response.json()
        return self._get_ad_details(_response_json)

    def get_total_pages(self):
        return self._total_pages_approx

    def _get_ad_id_list(self, _list: list) -> list:
        id_list = []
        for element in _list:
            id_list.append(element["id"])
        return id_list


    def _set_pagination_data(self, _response_json):
        if "paginationData" not in _response_json:
            raise IkmanNoPaginationData("Pagination data not found in response")
        pagination_data = _response_json["paginationData"]
        if self._current_page_no == 0:
            self._total_ads = pagination_data["total"]
            self._ads_per_page = pagination_data["pageSize"]
            self._total_pages_approx = math.ceil(self._total_ads / self._ads_per_page)
        if self._current_page_no > 0 and self._ads_per_page != pagination_data["pageSize"]:
            logger.warning("Page size altered between pages.")
        self._current_page_no = pagination_data["activePage"]
        logger.info(f"total ads: {self._total_ads}, total pages: {self._total_pages_approx}, active page: {self._current_page_no}")

    def _get_ad_details(self, _response_json: dict) -> list:
        """get ad details in a list from response dict (json)

        Depends on expected KEY_LIST constant. KEY_LIST contains all expected properties

        :param _response_json: dict
        :return: ad details
        """
        _ad = []
        _phones = []
        _properties = []
        """
            get details [ad list, phone tuple list, properties tuple list]
        """
        ad_json = _response_json["ad"]
        _ad_id = ad_json["id"]
        for key in self._KEY_LIST:
            if key not in ad_json:
                logger.info(f"Key - {key} not found in ad - {_ad_id}, substituting with None")
                _ad.append(None)
                continue
            if key == "properties":
                _properties.extend(self._get_properties_tuple(ad_json[key], ad_json["id"]))
            elif key == "money":  # money.amount
                _ad.append(ad_json[key]["amount"])
            elif key == "location":  # location.name
                _ad.append(ad_json[key]["name"])
            elif key == "area":  # area.name
                _ad.append((ad_json[key]["name"]))
            elif key == "contact_card":
                _phones.extend(self._get_phone_tuple(ad_json[key], ad_json["id"]))
            else:
                _ad.append(ad_json[key])
        # [(), [()], [()]]
        # [tuple, list of tuples, list of tuples]
        return [tuple(_ad), _phones, _properties]

    def _get_properties_tuple(self, properties: list, _ad_id: str) -> tuple:
        prop_list = []
        for prop in properties:
            prop_list.append((_ad_id, prop["key"], prop["value"]))
        return tuple(prop_list)

    def _get_phone_tuple(self, contact_card: dict, _ad_id: str) -> tuple:
        phone_list = []
        number_list = contact_card["phone_numbers"]
        if len(number_list) == 0:
            logger.info(f"No number listed for ad {_ad_id}")
            phone_list.append((_ad_id, contact_card["name"], None, None))
        for entry in number_list:
            phone_list.append((_ad_id, contact_card["name"], entry["number"], entry["verified"]))
        return tuple(phone_list)
