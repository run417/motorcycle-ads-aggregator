class RiyasewanaContentNotFound(Exception):
    """Raised when content to parse cannot be found. Critical Exception"""

    def __init__(self, msg):
        super(RiyasewanaContentNotFound, self).__init__(msg)


class IkmanListNotFound(Exception):
    """Raised when the ad list of a page is not found. Will not be able to get any ads of this page"""

    def __init__(self, msg):
        super(IkmanListNotFound, self).__init__(msg)


class IkmanNoPaginationData(Exception):
    """Raised when parsing fails and pagination information is not available"""

    def __init__(self, msg):
        super(IkmanNoPaginationData, self).__init__(msg)
