from sources.ikman.ikman_agent import IkmanAgent
from sources.ikman.ikman_parser import IkmanParser
from sources.ikman.ikman_storage import IkmanStorage
from sources.riyasewana.riyasewana_agent import RiyasewanaAgent
from sources.riyasewana.riyasewana_parser import RiyasewanaParser
from sources.riyasewana.riyasewana_storage import RiyasewanaStorage


class AgentFactory():
    def __init__(self, connection, fetcher):
        self._connection = connection
        self._fetcher = fetcher

    def make_agent(self, props):
        name = props["NAME"]
        if name == "ikman":
            ikmanStorage = IkmanStorage(self._connection)
            ikmanParser = IkmanParser()
            ikmanAgent = IkmanAgent(self._fetcher, ikmanParser, ikmanStorage, props)
            return ikmanAgent
        elif name == "riyasewana":
            riyasewanaStorage = RiyasewanaStorage(self._connection)
            riyasewanaParser = RiyasewanaParser()
            riyasewanaAgent = RiyasewanaAgent(self._fetcher, riyasewanaParser, riyasewanaStorage, props)
            return riyasewanaAgent
