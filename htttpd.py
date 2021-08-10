import threading
import socket
import logging
from datetime import datetime
from pathlib import Path
import os

from httpcls import HTTPStatus, HTTPRequest, HTTPResponse

BIND_ADDRESS = ('localhost', 8080)
BACKLOG_CONN = 10
DOCUMENT_ROOT = "/Users/user/PycharmProjects/otus_server/httptest/dir2"


logging.basicConfig(
    filename=None,
    level=logging.INFO,
    format='[%(asctime)s] %(levelname).1s %(message)s'
)

HTTP_METHODS_ALLOWED = ['GET', 'HEAD']


class HTTPException(Exception):
    pass


def parse_request(conn):
    """ Read bytes by chunks received from a client and parse
        request.
        :param conn: client socket object
        :return: HTTPRequest named tuple
        """

    request_data = bytearray()

    while True:
        data = conn.recv(1024)
        if not data:
            break
        request_data += data

    request_line = str(request_data, "iso-8859-1").strip()

    parsed_data = request_line.split("\r\n")

    logging.info(
        f"Parsed request: {parsed_data}."
    )

    method, target, version = parsed_data[0].split()

    return HTTPRequest(method=method, target=target)


def send_response(conn, response):
    """Send response to the client.
        :param conn: client socket object
        :param response: HTTPResponse named tuple
        :return: None
        """
    now = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")

    headers = (
        f"HTTP/1.1 {response.status}",
        f"Date: {now}",
        "Content-Type: text/html; charset=utf-8",
        f"Content-Length: {response.content_length}",
        "Server: Otus-Python-HTTP-Server",
        "Connection: close",
    )

    raw_response = "\r\n".join(headers).encode("utf-8")
    raw_response += b"\r\n" + response.body

    logging.info(
        f"Response is ready to be send: {raw_response}."
    )

    conn.sendall(raw_response)
    logging.info(
        f"Response has been successfully send."
    )


def handle_connection(conn, address, document_root):
    """Process request from a client, prepare and send response in the new thread.
        :param conn: client socket object
        :param address: client ip address
        :param document_root: working public directory
        :return: None
        """

    logging.info(
        f"Start to process request from {address[0]}, {address[1]}."
    )

    request = parse_request(conn)
    method = request.method
    target = request.target

    if request.method not in HTTP_METHODS_ALLOWED:
        raise HTTPException(HTTPStatus.METHOD_NOT_ALLOWED)

    target = target.partition("/")[-1].partition("?")[0]

    path = Path(os.path.join(document_root, target))

    if path.is_dir():
        path /= "index.html"

    logging.info(
        f"Target path from the request: {path}."
    )

    if not path.is_file():
        raise HTTPException(HTTPStatus.NOT_FOUND)

    stat = path.stat()
    content_length = stat.st_size
    body = b"" if method == "HEAD" else path.read_bytes()

    response = HTTPResponse(
        status=HTTPStatus.OK,
        body=body,
        content_type=path.suffix,
        content_length=content_length,
    )

    logging.info(
        f"Prepared response: {HTTPResponse}."
    )

    send_response(conn, response)
    conn.close()
    logging.info(
        "Closing the connection."
    )


def serve_forever():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(BIND_ADDRESS)
        server.listen(BACKLOG_CONN)
        logging.info(
            f"Server is running on http://{BIND_ADDRESS[0]}:{BIND_ADDRESS[1]}/ (Press CTRL+C to quit)"
        )

        while True:
            client_socket, address = server.accept()
            client_handler = threading.Thread(
                target=handle_connection,
                args=(client_socket, address, DOCUMENT_ROOT)
            )
            client_handler.daemon = True
            logging.info(
                f"New thread has been started to process connection from {address[0]}, {address[1]}."
            )
            client_handler.start()


if __name__ == "__main__":
    serve_forever()
