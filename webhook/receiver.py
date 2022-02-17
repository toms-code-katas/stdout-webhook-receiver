"""
A simple handler for handling post requests and logging json to stdout
"""
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
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
    A simple handler for handling post requests and logging json to stdout
    """

    # pylint: disable=C0103
    def do_POST(self):
        """

        :return:
        """
        self.send_response(200)
        self.end_headers()
        data = self.rfile.read(int(self.headers['Content-Length']))
        logger.debug(data.decode("utf-8"))


if __name__ == '__main__':
    httpd = HTTPServer(('', 8080), AlarmHandler)
    httpd.serve_forever()
