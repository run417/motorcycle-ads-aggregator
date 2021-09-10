# main.py

import json
import logging
import math
import pprint
import re
import sys
import time
import os

import requests
from mysql.connector import connect, Error

UTC_TIMESTAMP = int(time.time())


if not os.path.exists('logs'):
    os.makedirs('logs')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(levelname)s:%(lineno)d:%(asctime)s - %(message)s")

stream_handler = logging.StreamHandler(sys.stderr)
stream_handler.setFormatter(formatter)

file_handler = logging.FileHandler(filename=f"logs{os.sep}warnings-{UTC_TIMESTAMP}.log")
file_handler.setLevel(logging.WARNING)
file_handler.setFormatter(formatter)

script_log_file_handler = logging.FileHandler(filename=f"logs{os.sep}execution-{UTC_TIMESTAMP}.log")
script_log_file_handler.setLevel(logging.DEBUG)
script_log_file_handler.setFormatter(formatter)

stream_handler.setLevel(logging.INFO)
logger.addHandler(stream_handler)
logger.addHandler(file_handler)
logger.addHandler(script_log_file_handler)

CONFIG_FILE = "config.json"

AD_LIST_BASE_URL = "https://ikman.lk/data/serp?sort=date&order=desc&category=402&page="
AD_DETAIL_BASE_URL = "http://api-gateway-v2.e5.ikman.prod-sg.apex.saltside.net/v1/ads/"

RE_ARGUMENT_PATTERN = re.compile("^--limit=\\d+$")

WAIT_SECONDS = 3
HTTP_SUCCESS = 200
MAX_FAILS = 2

# dummy values for dict values
# dicts are only used as ad existence check i.e availability lookup
FROM_LOCAL = 0
FROM_SERVER = 1

KEY_LIST = ["id", "status", "description", "date", "url", "title", "money", "deactivates", "contact_card",
            "item_condition", "slug", "area", "location", "type", "info", "properties"]

DEFAULT_LIMIT = 10
FETCH_LIMIT = DEFAULT_LIMIT

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36"
ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8," \
         "application/signed-exchange;v=b3;q=0.9 "
PROXIES = {}

try:
    with open(CONFIG_FILE) as file:
        config = json.load(file)
        if "FETCH_LIMIT" in config:
            FETCH_LIMIT = int(config["FETCH_LIMIT"])
            logger.info(f"Fetch limit={FETCH_LIMIT} found in configuration")
        if "PROXIES" in config:
            if "HTTP" in config["PROXIES"]:
                PROXIES["http"] = config["PROXIES"]["HTTP"]
            if "HTTPS" in config["PROXIES"]:
                PROXIES["https"] = config["PROXIES"]["HTTPS"]
        if "USER_AGENT" in config and config["USER_AGENT"] != "":
            USER_AGENT = config["USER_AGENT"]
        USERNAME = config["USERNAME"]
        PASSWORD = config["PASSWORD"]
        HOSTNAME = config["HOSTNAME"]
        DATABASE_NAME = config["DATABASE_NAME"]
        if "WAIT_SECONDS" in config:
            WAIT_SECONDS = int(config["WAIT_SECONDS"])
        if "MAX_FAILS" in config:
            MAX_FAILS = int(config['MAX_FAILS'])
except Exception as ex:
    logger.exception(ex)
    exit(1)

# get limit from arguments
if len(sys.argv) > 1:
    arg = sys.argv[1].strip()
    match = RE_ARGUMENT_PATTERN.match(arg)
    if match:
        FETCH_LIMIT = int(arg[8:])  # the 8 constant is the number of characters in --limit=
        logger.info(f"Overriding previous value to fetch limit={FETCH_LIMIT}")
    else:
        print("Usage: aggregator --limit=n # where n >= 0")
        logger.critical("invalid argument specified")
        exit(1)

GET_LATEST_LOCAL_ADS_QUERY = f"SELECT ad_id FROM ad ORDER BY datetime DESC"
INSERT_AD_QUERY = "INSERT INTO ad(ad_id, status, description, datetime, url, title, money, deactivates," \
                  "item_condition, slug, area, location, type, info) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s," \
                  "%s, %s, %s, %s)"
INSERT_PHONE_QUERY = "INSERT INTO phone(ad_id, name, number, verified) VALUES(%s, %s, %s, %s)"
INSERT_PROPERTIES_QUERY = "INSERT INTO properties(ad_id, prop_key, prop_value) VALUES(%s, %s, %s)"

logger.info(f"user_agent: {USER_AGENT}")
logger.info(f"proxies: {PROXIES}")
logger.info(f"wait seconds: {WAIT_SECONDS}")
logger.info(f"max fails: {MAX_FAILS}")


def get_properties_tuple(properties: list, _ad_id: str) -> tuple:
    prop_list = []
    for prop in properties:
        prop_list.append((_ad_id, prop["key"], prop["value"]))
    return tuple(prop_list)


def get_phone_tuple(contact_card: dict, _ad_id: str) -> tuple:
    phone_list = []
    number_list = contact_card["phone_numbers"]
    if len(number_list) == 0:
        logger.info(f"No number listed for ad {_ad_id}")
        phone_list.append((_ad_id, contact_card["name"], None, None))
    for entry in number_list:
        phone_list.append((_ad_id, contact_card["name"], entry["number"], entry["verified"]))
    return tuple(phone_list)


latest_local_ads_list = []
connection = None
try:
    connection = connect(host=HOSTNAME, user=USERNAME, password=PASSWORD, database=DATABASE_NAME)
    logger.info(f"Connection made to {DATABASE_NAME}")
    with connection.cursor(dictionary=True) as cursor:
        cursor.execute(GET_LATEST_LOCAL_ADS_QUERY)
        latest_local_ads_list = cursor.fetchall()
except Error as e:
    logger.critical(e)
    exit(1)

latest_local_ads = {}
for local_ad in latest_local_ads_list:
    latest_local_ads[local_ad["ad_id"]] = FROM_LOCAL
logger.info(f"Queried latest {len(latest_local_ads_list)} ads from local storage")


if latest_local_ads is None:
    logger.info("No local ads")

"""
ad keys - 
    1. id, 
    2. status,
    3. description, 
    4. date, 
    5. url, 
    6. title, 
    7. money.amount, 
    8. deactivates, 
    9. item_condition, 
    10. slug, 
    11. area.name,
    12. location.name
    13. type
    14. info
"""

# tuple list
ad_tuple_list = []
# tuple list
properties_tuple_list = []
# tuple list
phone_tuple_list = []

total_ads = 0
ads_per_page = 0
pages_approx = 1  # pages estimate should be 1
current_page = 0

ad_detail_request_count = 0
ad_list_request_count = 0

ads_fetched = {}
pages_fetched = 0

page_count = 1
ids_of_ads_to_fetch = []
saved_to_local_count = 0

referer = "www.google.com"

# url = "http://httpbin.org/ip"
headers = {"Accept": ACCEPT, "User-Agent": USER_AGENT, "Referer": referer}

# response = requests.get(url, headers=headers, proxies=PROXIES)
# pprint.pprint(response.json())
# exit(1)
ad_fetch_failure_count = 0
ad_list_fetch_failure_count = 0
retry_list = []

while len(ads_fetched) < FETCH_LIMIT and page_count <= pages_approx:
    try:
        # get the ad list
        ad_list_url = AD_LIST_BASE_URL + str(page_count)
        logger.info(f"Requesting ad list page with url: {ad_list_url}")
        response = requests.get(ad_list_url, headers=headers)
        ad_list_request_count += 1
        logger.info(f"Server responded with {response.status_code}")
        logger.info(f"Waiting for {WAIT_SECONDS} seconds")
        time.sleep(WAIT_SECONDS)

        if response.status_code == HTTP_SUCCESS:
            response_json = response.json()
            pagination_data = response_json["paginationData"]

            logger.info(f"Page {page_count} fetched successfully")

            # set the values from first fetched page only
            if current_page == 0:
                total_ads = pagination_data["total"]
                ads_per_page = pagination_data["pageSize"]
                pages_approx = math.ceil(total_ads / ads_per_page)

            current_page = pagination_data["activePage"]
            pages_fetched += 1
            page_count += 1

            logger.info(f"Total Ads at script start: {total_ads}")
            logger.info(f"Ads per page: {ads_per_page}")
            logger.info(f"Pages estimate: {pages_approx}")
            logger.info(f"Pages fetched: {pages_fetched}")
            logger.info(f"Current page: {current_page}")

            if "ads" not in response_json:
                raise Exception("No ad list found in response. Cannot parse further")
            fetched_ad_list = response_json["ads"]

            if len(fetched_ad_list) == 0:
                logger.info("This page does not contain any ads")
                if page_count > pages_approx:
                    logger.info("No more ad list pages to fetch")
                    continue

            # clear ad_id_list of ads from previous pages if any
            ids_of_ads_to_fetch.clear()
            logger.info(f"Retry has {len(retry_list)} ads")

            # put all ids in the ad search-list in list
            for ad in fetched_ad_list:
                ad_id = ad["id"]
                # if ad_id in latest_local_ads:
                #     ads_fetched[ad_id] = FROM_LOCAL

                if ad_id not in latest_local_ads and ad_id not in ads_fetched:
                    ids_of_ads_to_fetch.append(ad_id)
                else:
                    logger.info(f"{ad_id} does not need to be fetched. "
                                f"Is ad in latest local ads? {ad_id in latest_local_ads}. "
                                f"Is ad in fetched ads? {ad_id in ads_fetched}")

            logger.info(f"number of ads to be fetched from list: {len(ids_of_ads_to_fetch)}")

            if len(ids_of_ads_to_fetch) == 0:
                logger.info("All ads in this page are already fetched.")

            # pprint.pprint(ids_of_ads_to_fetch)
            if len(retry_list) > 0:
                logger.info(f"Adding ad ids in retry list to the ad fetch list")
                ids_of_ads_to_fetch.extend(retry_list)

            # fetch ad details for each ad_id
            for ad_id in ids_of_ads_to_fetch:
                logger.info(f"Fetch limit: {FETCH_LIMIT}, Ads fetched so far: {len(ads_fetched)}")
                if len(ads_fetched) >= FETCH_LIMIT:
                    break

                temp_ad = []
                # fetch ad with id
                ad_url = AD_DETAIL_BASE_URL + ad_id
                logger.info(f"Requesting ad details with url: {ad_url}")
                response = requests.get(ad_url, headers={"User-Agent": USER_AGENT, "referer": referer})
                ad_detail_request_count += 1
                logger.info(f"Responded with status {response.status_code}")
                logger.info(f"Waiting for {WAIT_SECONDS} seconds")
                time.sleep(WAIT_SECONDS)
                if response.status_code == HTTP_SUCCESS:
                    ad_json = response.json()
                    ad = ad_json["ad"]
                    for key in KEY_LIST:
                        if key not in ad:
                            logger.info(f"Key - {key} not found in ad - {ad_id}, substituting with None")
                            temp_ad.append(None)
                            continue
                        if key == "properties":
                            properties_tuple_list.extend(get_properties_tuple(ad[key], ad["id"]))
                        elif key == "money":  # money.amount
                            temp_ad.append(ad[key]["amount"])
                        elif key == "location":  # location.name
                            temp_ad.append(ad[key]["name"])
                        elif key == "area":  # area.name
                            temp_ad.append((ad[key]["name"]))
                        elif key == "contact_card":
                            phone_tuple_list.extend(get_phone_tuple(ad[key], ad["id"]))
                        else:
                            temp_ad.append(ad[key])

                    print(temp_ad)
                    ad_tuple_list.append(tuple(temp_ad))
                    ads_fetched[ad["id"]] = FROM_SERVER  # only the key matters
                    logger.info(f"Fetched {ad_id} successfully")
                else:
                    logger.critical(f"Failed to fetch ad {ad_id} with status {response.status_code}")

                    if ad_id in retry_list:
                        logger.info("Ad is already in retry list, removing from retry list")
                        retry_list.remove(ad_id)
                    elif len(retry_list) < MAX_FAILS:
                        logger.info("Adding failed ad id to retry list")
                        retry_list.append(ad_id)
                    elif len(retry_list) >= MAX_FAILS:
                        logger.info(f"Too many ads failed. Not adding to retry list")

                    continue

            # save in database
            with connection.cursor() as cursor:
                if len(ad_tuple_list) == 0:
                    logger.info("No ads to insert into the database")
                    continue

                logger.info("Inserting data into database")
                cursor.executemany(INSERT_AD_QUERY, ad_tuple_list)

                saved_to_local_count += cursor.rowcount
                ad_row_count = cursor.rowcount

                cursor.executemany(INSERT_PHONE_QUERY, phone_tuple_list)
                phone_row_count = cursor.rowcount

                cursor.executemany(INSERT_PROPERTIES_QUERY, properties_tuple_list)
                properties_row_count = cursor.rowcount

                connection.commit()

                # pprint.pprint(ad_tuple_list)
                pprint.pprint(phone_tuple_list)
                # pprint.pprint(properties_tuple_list)

                if ad_row_count == len(ad_tuple_list):
                    ad_tuple_list.clear()
                else:
                    logger.warning("Some ads were not saved!")
                    logger.warning(f"Affected row count: {ad_row_count}, In memory: {len(ad_tuple_list)}")

                if phone_row_count == len(phone_tuple_list):
                    phone_tuple_list.clear()
                else:
                    logger.warning("Some phone data were not saved!")

                if properties_row_count == len(properties_tuple_list):
                    properties_tuple_list.clear()
                else:
                    logger.warning("Some ad property data were not saved!")

                phone_tuple_list.clear()
                properties_tuple_list.clear()

                logger.info(f"Saved {saved_to_local_count} ad to local storage since script start")
        else:
            logger.warning(f"Failed to fetch ad list page {ad_list_url} with status {response.status_code}")
            ad_list_fetch_failure_count += 1
            if ad_list_fetch_failure_count == MAX_FAILS:
                logger.critical(f"Failed to fetch ad list {ad_list_fetch_failure_count} times. Trying the next page...")
                page_count += 1
                continue
            logger.warning(f"Retrying request {ad_list_url}")
            continue

    except (requests.RequestException,
            requests.ConnectionError,
            requests.HTTPError,
            requests.TooManyRedirects) as req_exc:
        logger.exception(req_exc)
        break
    except KeyError as key_exc:
        logger.exception(key_exc)
        break
    except Error as mysql_exc:
        logger.exception(mysql_exc)
        break
    except KeyboardInterrupt as kbdInt:
        logger.critical("User interrupt. Exiting...")
        break
    except Exception as exc:
        logger.exception(exc)
        continue

logger.info(f"Made {ad_list_request_count} ad list requests and {ad_detail_request_count} ad detail requests")
logger.info(f"exiting after fetching {len(ads_fetched)} ads")
