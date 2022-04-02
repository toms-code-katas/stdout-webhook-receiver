import json

from webhook.receiver import AlarmHandler
from http.server import HTTPServer
from multiprocessing import Process
import os
import requests
import time
import unittest


def start_server(httpd):
    httpd.serve_forever()


class WebhookReceiverTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(os.path.dirname(__file__), 'sample_alert.json')) as json_file:
            cls._data = json.load(json_file)

        httpd = HTTPServer(('', 8080), AlarmHandler)
        cls._process = Process(target=start_server, args=(httpd,))
        cls._process.start()
        time.sleep(1)

    def test_simple_alert(self):
        r = requests.post('http://localhost:8080', json=json.dumps(WebhookReceiverTests._data))
        assert r.status_code == 200

    @classmethod
    def tearDownClass(cls):
        cls._process.kill()
