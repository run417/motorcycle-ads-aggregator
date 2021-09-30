import json

import logger

logger = logger.get_logger("app.config")


class AppConfig:
    def __init__(self):
        self._CONFIG_FILE = "config.json"
        self._CONFIG_SOURCES = []
        self._MAX_FAILS = 2
        self._PROXIES = {}
        self._DEFAULT_FETCH_LIMIT = 10
        self._DEFAULT_FETCH_TYPE = "all"
        self._ARG_FETCH_LIMIT = -1
        self._ARG_FETCH_TYPE = ""
        self._WAIT_SECONDS = 5
        self._DB_USER = ""
        self._DB_PASS = ""
        self._DB_HOST = ""
        self._DB_NAME = ""

        self._DEFAULT_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36"

        self._USER_AGENT = self._DEFAULT_USER_AGENT
        self._ACCEPT_HEADER = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp," \
                              "image/apng,*/*;q=0.8, application/signed-exchange;v=b3;q=0.9 "

        self._REFERER = "www.google.com"

        self._default_sources = {
            "ikman": {
                "NAME": "ikman",
                "LIST_URL": "https://ikman.lk/data/serp?sort=date&order=desc&category=402&page=",
                "DET_URL": "http://api-gateway-v2.e5.ikman.prod-sg.apex.saltside.net/v1/ads/",
                "FETCH_LIMIT": self._DEFAULT_FETCH_LIMIT,
                "FETCH_TYPE": self._DEFAULT_FETCH_TYPE,
                "MAX_FAILS": self._MAX_FAILS
            },
            "riyasewana": {
                "NAME": "riyasewana",
                "LIST_URL": "https://riyasewana.com/search/motorcycles",
                "FETCH_LIMIT": self._DEFAULT_FETCH_LIMIT,
                "FETCH_TYPE": self._DEFAULT_FETCH_TYPE,
                "MAX_FAILS": self._MAX_FAILS
            },
        }

    def parse_config_file(self):
        try:
            with open(self._CONFIG_FILE) as file:
                config = json.load(file)
                if "PROXIES" in config:
                    if "HTTP" in config["PROXIES"]:
                        self._PROXIES["http"] = config["PROXIES"]["HTTP"]
                    if "HTTPS" in config["PROXIES"]:
                        self._PROXIES["https"] = config["PROXIES"]["HTTPS"]
                if "USER_AGENT" in config and config["USER_AGENT"] != "":
                    self._USER_AGENT = config["USER_AGENT"]
                self._DB_USER = config["USERNAME"]
                self._DB_PASS = config["PASSWORD"]
                self._DB_HOST = config["HOSTNAME"]
                self._DB_NAME = config["DATABASE_NAME"]
                if "WAIT_SECONDS" in config:
                    self._WAIT_SECONDS = int(config["WAIT_SECONDS"])
                if "MAX_FAILS" in config:
                    self._MAX_FAILS = int(config['MAX_FAILS'])
                if "SOURCES" in config and type(config["SOURCES"]) is list:
                    self._CONFIG_SOURCES = config["SOURCES"]
        except Exception as ex:
            logger.exception(ex)
            exit(1)

    def set_limit(self, limit: int):
        if limit is not None:
            logger.info(f"Setting fetch limit {limit} from arguments")
            self._ARG_FETCH_LIMIT = limit

    def set_fetch_type(self, _type):
        if _type:
            logger.info(f"Setting fetch type new from arguments")
            self._ARG_FETCH_TYPE = "new"

    def get_db_config(self):
        return {"user": self._DB_USER, "pass": self._DB_PASS, "host": self._DB_HOST, "database": self._DB_NAME}

    def get_sources(self) -> list:
        # get ikman and riyasewana sources with options
        # defaults
        # config overrides defaults
        # cli arguments overrides configs and defaults
        sources = []
        for source in self._CONFIG_SOURCES:
            if "name" in source and source["name"] in self._default_sources:
                name = source["name"]
                if "limit" in source:
                    try:
                        limit = int(source["limit"])
                        if limit >= 0:
                            self._default_sources[name]["FETCH_LIMIT"] = limit
                        else:
                            logger.warning(f"Fetch limit cannot be negative, will use default limit")
                    except:
                        logger.warning(
                            f"Limit value should be number, provided '{source['limit']}', will use default limit")
                else:
                    logger.warning(f"Fetch limit not found for source: {source['name']}, using default limit")
                if "fetch_type" in source:
                    if source["fetch_type"] == "new" or source["fetch_type"] == "all":
                        self._default_sources[name]["FETCH_TYPE"] = source["fetch_type"]
                    else:
                        logger.warning(
                            f"Fetch should be 'new' or 'all' provided {source['fetch_type']}, will use default type")
                else:
                    logger.warning(f"Fetch type not found for source: {source['name']}, using default type")
                sources.append(self._default_sources[name])
            elif "name" in source:
                logger.warning(f" Unknown source '{source['name']}'")
        if self._ARG_FETCH_LIMIT != -1:
            for source_name in self._default_sources:
                self._default_sources[source_name]["FETCH_LIMIT"] = self._ARG_FETCH_LIMIT
        if self._ARG_FETCH_TYPE != "":
            for source_name in self._default_sources:
                self._default_sources[source_name]["FETCH_TYPE"] = self._ARG_FETCH_TYPE
        for source_name in self._default_sources:
            self._default_sources[source_name]["MAX_FAILS"] = self._MAX_FAILS
        if len(sources) == 0:
            logger.critical(f"No sources found")
        return sources

    def get_wait_seconds(self) -> int:
        return self._WAIT_SECONDS

    def get_user_agent(self) -> str:
        return self._USER_AGENT

    def get_request_headers(self) -> dict:
        return {
            "Accept": self._ACCEPT_HEADER,
            "User-Agent": self._USER_AGENT,
            "Referer": self._REFERER
        }
