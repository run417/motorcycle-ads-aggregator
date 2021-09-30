from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup, SoupStrainer

import logger
from app_exceptions import RiyasewanaContentNotFound

if TYPE_CHECKING:
    from requests import Response

logger = logger.get_logger("riyasewana.parser")


class RiyasewanaParser():

    def __init__(self):
        self._ID_PATTERN = re.compile("[^-]+$")
        self._DATE_PATTERN = re.compile("(?<=\son\\s)(.*)(?=,)")
        self._NAME_PATTERN = re.compile("(?<=Posted\\sby\\s)(.*)(?=\\son)")
        self._LOCATION_PATTERN = re.compile("[^, ]+$")
        self._TOTAL_PAGES_PATTERN = re.compile("(?=...)\\d{3}(?=\\sNext)")
        self._TOTAL_ADS_PATTENS = re.compile("(?<=\\sof\\s)\\d+(?=\sSearch\\s)")

        self._active_page = 0
        self._total_pages = 0
        self._total_ads = 0

    def parse_list(self, _response: Response) -> list:
        """

        :param _response:
        :return: list of tuples. each tuple contains two string elements. url and id
        """
        content = _response.content
        strainer = SoupStrainer(id="content")
        soup = BeautifulSoup(content, "html.parser", parse_only=strainer)

        if len(soup.contents) == 0:
            raise RiyasewanaContentNotFound(
                "Search list results not found. ID 'content' not found Cannot parse page further")

        self._active_page = int(soup.find(class_="current").text)

        pagination = soup.find(class_="pagination").text
        self._total_pages = int(self._TOTAL_PAGES_PATTERN.search(pagination).group())

        result_summary = soup.find(class_="results").text
        self._total_ads = int(self._TOTAL_ADS_PATTENS.search(result_summary).group())
        result_list = soup.find("ul").contents
        href_list = []
        for a in result_list:
            try:
                url = a.contents[0].a.get("href")
            except AttributeError as exc:
                logger.info(exc)
                continue
            ad_id = self._ID_PATTERN.search(url).group()
            href_list.append((url, ad_id))
        # return [href_list[0]]
        return href_list

    def parse_detail(self, _response: Response) -> dict:
        ad_details = {}
        content = _response.content
        strainer = SoupStrainer(id="content")
        soup = BeautifulSoup(content, "html.parser", parse_only=strainer)

        if len(soup.contents) == 0:
            raise RiyasewanaContentNotFound("Ad details not found. ID 'content' not found")

        ad_details["title"] = soup.h1.text
        subheading = soup.h2.text
        ad_details["name"] = self._NAME_PATTERN.search(subheading).group()
        ad_details["location"] = self._LOCATION_PATTERN.search(subheading).group()
        datetime_str = self._DATE_PATTERN.search(subheading).group()
        ad_details["date"] = self._get_iso_datetime_str(datetime_str)
        table = soup.table.contents

        KEY_LIST = ["contact", "price", "make", "model", "yom", "mileage (km)", "engine (cc)", "start type", "details"]

        for key in KEY_LIST:
            ad_details[key] = ""

        for tr in table:
            if tr.name == "tr" and len(tr.contents) > 0:
                count = 0
                for td in tr.contents:
                    if td.text.lower() in ad_details:
                        ad_details[td.text.lower()] = tr.contents[count + 1].text
                    count += 1
        return ad_details

    def get_total_pages(self):
        return self._total_pages

    def _get_iso_datetime_str(self, _datetime_str) -> str:
        return datetime.strptime(_datetime_str, "%Y-%m-%d %I:%M %p").isoformat()
