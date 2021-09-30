import argparse

from time import perf_counter
from mysql.connector import connect, Error

argument_parser = argparse.ArgumentParser(allow_abbrev=False)
argument_parser.add_argument("-L", "--limit", metavar="integer",
                             type=int, help="limit the amount of ads fetched, 0 fetches all ads, cannot be negative")
argument_parser.add_argument("-N", "--new", action="store_true",
                             help="only fetch latest ads relative to local latest ad")
arguments = argument_parser.parse_args()
_limit = arguments.limit
_new = arguments.new
if _limit is not None and _limit < 0:
    argument_parser.error("limit cannot be negative")



start = perf_counter()

import logger
from fetcher import Fetcher
from sources.agent_factory import AgentFactory
from configuration import AppConfig

logger = logger.get_logger("Main")

config = AppConfig()
config.parse_config_file()

config.set_limit(_limit)
config.set_fetch_type(_new)

db_config = config.get_db_config()
sources = config.get_sources()

try:
    connection = connect(user=db_config["user"], password=db_config["pass"], host=db_config["host"], database=db_config["database"])
except Error as err:
    logger.critical(err)
    exit(1)

headers = config.get_request_headers()
logger.info(f"User set request headers {headers}")
wait_seconds = config.get_wait_seconds()

fetcher = Fetcher(headers=headers, wait_seconds=wait_seconds)
agentFactory = AgentFactory(connection, fetcher)

try:
    for source in sources:
        agent = agentFactory.make_agent(source)
        agent.run()
    logger.info(f"Total requests: {fetcher.get_request_count()}")
    logger.info(f"Finished in {perf_counter() - start:0.2f} seconds")
except KeyboardInterrupt as exc:
    logger.info(f"Finished in {perf_counter() - start:0.2f} seconds")
    logger.warning("User abort. Exiting...")
    exit(0)
