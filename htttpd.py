import argparse
import threading
import socket
import logging
import time
from datetime import datetime
from pathlib import Path
import os
import urllib.parse

from httpcls import HTTPStatus, HTTPRequest, HTTPResponse

BIND_ADDRESS = ('localhost', 8080)
BACKLOG_CONN = 1000
NUMBER_WORKERS = 5
DOCUMENT_ROOT = "/Users/user/PycharmProjects/otus_server"
SAFE_DIR = "/httptest"

HTTP_METHODS_ALLOWED = ['GET', 'HEAD']

CONTENT_TYPES_ALLOWED = {
    ".html": "text/html",
    ".js": "application/javascript",
    ".css": "text/css",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".swf": "application/x-shockwave-flash",
    ".txt": "text/plain",
}

logging.basicConfig(
    filename=None,
    level=logging.INFO,
    format='[%(asctime)s] %(levelname).1s %(message)s'
)

parser = argparse.ArgumentParser(description="Passing number of workers and document root")
parser.add_argument(
    "-w",
    dest="number_workers",
    help="Number of workers. If not specified use default script settings.",
)
parser.add_argument(
    "-d",
    dest="document_root",
    help="Path to document root. If not specified use default script settings.",
)


def read_request(conn):
    """ Read bytes by chunks received from a client.
            :param conn: client socket object
            :return: data
            """
    request_data = bytearray()
    headers_end = bytearray(b'\r\n\r\n')

    while True:
        data = conn.recv(1024)
        request_data += data
        if headers_end in data or not data:
            break

    return request_data


def check_safe_url(safe_dir, target_url):
    """ Checks that url is safe and targeting files within safe directory.
        :param safe_dir: path to directory with shared files
        :param target_url: url requested
        :return: Boolean
        """
    match = os.path.abspath(target_url)
    return safe_dir == os.path.commonpath([safe_dir, match])


def parse_request(conn, data):
    """ Parse request.
        :param data: data in bytes
        :return: HTTPRequest named tuple
        """

    request_line = str(data, "iso-8859-1").strip()
    parsed_data = request_line.split("\r\n")

    logging.info(
        f"Parsed request: {parsed_data}."
    )
    method, target, version = parsed_data[0].split()

    target = urllib.parse.unquote(target)

    return HTTPRequest(method=method, target=target)


def send_error(conn, status):
    now = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
    body = str(status).encode("utf-8")

    headers = (
        f"HTTP/1.1 {status}",
        f"Date: {now}",
        f"Content-Type: text/plain",
        f"Content-Length: {len(body)}",
        "Server: Otus-Python-HTTP-Server",
        "Connection: close"
    )

    raw_response = "\r\n".join(headers).encode("utf-8")
    raw_response += b"\r\n\r\n" + body
    conn.sendall(raw_response)
    conn.close()


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
        f"Content-Type: {response.content_type}",
        f"Content-Length: {response.content_length}",
        "Server: Otus-Python-HTTP-Server",
        "Connection: close"
    )

    raw_response = "\r\n".join(headers).encode("utf-8")
    raw_response += b"\r\n\r\n" + response.body

    logging.info(
        f"Response is ready to be send."
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
    data = read_request(conn)

    try:
        request = parse_request(conn, data)
        method = request.method
        target = request.target
    except ValueError:
        return send_error(conn, HTTPStatus.BAD_REQUEST)

    if request.method not in HTTP_METHODS_ALLOWED:
        return send_error(conn, HTTPStatus.METHOD_NOT_ALLOWED)

    # checks for directory traversal
    if not check_safe_url(SAFE_DIR, target):
        return send_error(conn, HTTPStatus.FORBIDDEN)

    target = target.partition("/")[-1].partition("?")[0]

    path = Path(os.path.join(document_root, target))

    path = Path(str(path).replace("%20", ' '))

    if path.is_dir():
        path /= "index.html"
    elif target.endswith("/"):
        return send_error(conn, HTTPStatus.NOT_FOUND)

    logging.info(
        f"Target path from the request: {path}."
    )

    if not path.is_file():
        return send_error(conn, HTTPStatus.NOT_FOUND)

    stat = path.stat()
    content_length = stat.st_size  # count the length of body
    body = b"" if method == "HEAD" else path.read_bytes()

    response = HTTPResponse(
        status=HTTPStatus.OK,
        body=body,
        content_type=CONTENT_TYPES_ALLOWED[path.suffix],
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


def wait_connection(server, id):
    """Waiting forever and accepting connection when incoming.
        :param server: listening socket object
        :param id: thread id
        :return: None
        """
    while True:
        client_socket, address = server.accept()
        logging.info(
            f"Thread-{id} has started to process connection from {address[0]}, {address[1]}."
        )
        handle_connection(client_socket, address, DOCUMENT_ROOT)

        logging.info(f"Thread-{id} has been stopped.")


def serve_forever(workers_number):
    """Open a listening TCP socket and creating new pool of threads/workers to wait for a connection .
        :param workers_number: Number of workers.
        :return: None
        """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(BIND_ADDRESS)
        server.listen(BACKLOG_CONN)
        logging.info(
            f"Server is running on http://{BIND_ADDRESS[0]}:{BIND_ADDRESS[1]}/ (Press CTRL+C to quit)"
        )

        for i in range(1, workers_number + 1):
            thread = threading.Thread(
                target=wait_connection, args=(server, i)
            )
            thread.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Server is stopping.")
            return None


if __name__ == "__main__":
    args = parser.parse_args()
    if args.document_root:
        DOCUMENT_ROOT = args.document_root
    if args.number_workers:
        NUMBER_WORKERS = int(args.number_workers)

    serve_forever(NUMBER_WORKERS)
