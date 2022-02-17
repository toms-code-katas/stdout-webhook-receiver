import json

from webhook.receiver import AlarmHandler
from http.server import HTTPServer
import _thread
import os
import requests
import time
import unittest


def start_server(httpd):
    httpd.serve_forever()


class WebhookReceiverTests(unittest.TestCase):

    data = None

    @staticmethod
    def setUpClass():
        with open(os.path.join(os.path.dirname(__file__), 'sample_request.json')) as json_file:
            WebhookReceiverTests.data = json.load(json_file)

        httpd = HTTPServer(('', 8080), AlarmHandler)
        _thread.start_new_thread(start_server, (httpd,))
        time.sleep(1)

    def test_webhook_receiver(self):
        r = requests.post('http://localhost:8080', json=json.dumps(WebhookReceiverTests.data))
        assert r.status_code == 200
