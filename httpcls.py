from collections import namedtuple
import enum


class HTTPStatus(enum.Enum):
    OK = 200, "OK"
    BAD_REQUEST = 400, "Bad Request"
    FORBIDDEN = 403, "Forbidden"
    NOT_FOUND = 404, "Not Found"
    METHOD_NOT_ALLOWED = 405, "Method Not Allowed"
    REQUEST_TIMEOUT = 408, "Request Timeout"

    def __str__(self):
        code, message = self.value
        return f"{code} {message}"


HTTPRequest = namedtuple("HTTPRequest", ["method", "target"])
HTTPResponse = namedtuple("HTTPResponse", ["status", "body", "content_type", "content_length"])
