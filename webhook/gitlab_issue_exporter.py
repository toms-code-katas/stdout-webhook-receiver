"""
A handler for handling post requests and opening gitlab issues
"""
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
import json
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format='{"timestamp": "%(asctime)s", "alert": %(message)s}',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger('webhook-receiver')


class AlarmHandler(BaseHTTPRequestHandler):
    """
    A handler for handling post requests and opening gitlab issues
    """

    # pylint: disable=C0103
    def do_POST(self):
        """

        :return:
        """
        self.send_response(200)
        self.end_headers()

        data_as_string = self.rfile.read(int(self.headers['Content-Length'])).decode("utf-8")
        data = json.loads(data_as_string)
        logger.debug(data)


def main():
    httpd = HTTPServer(('', 8080), AlarmHandler)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
