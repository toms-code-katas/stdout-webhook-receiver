import json

import logging
from multiprocessing import Process
import os
import requests
import sys
import time
import unittest
import webhook
from webhook.stdout_receiver import AlarmHandler


class StreamToLogger(object):
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''
        self.log_message = []

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            message = line.rstrip()
            self.log_message.append(message)
            self.logger.log(self.log_level, message)

    def flush(self):
        pass


class WebhookReceiverTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(os.path.dirname(__file__), 'sample_stdout_alert.json')) as json_file:
            cls._data = json.load(json_file)

        test_logger = logging.getLogger("WebhookReceiverTests")
        test_logger.setLevel(logging.DEBUG)
        test_logger.addHandler(logging.StreamHandler(sys.stdout))

        cls.test_logger = StreamToLogger(logger = test_logger, log_level=logging.DEBUG)
#        sys.stdout = cls.test_logger
        logger = logging.getLogger('stdout-receiver')
        logger.addHandler(logging.StreamHandler(cls.test_logger))
        logger.setLevel(logging.DEBUG)

        cls._process = Process(target=webhook.stdout_receiver.main)
        cls._process.start()

        time.sleep(1)

    def test_webhook_receiver(self):
        r = requests.post('http://localhost:8080', json=json.dumps(WebhookReceiverTests._data))
        assert r.status_code == 200
        messages = WebhookReceiverTests.test_logger.log_message
        print(messages)

    @classmethod
    def tearDownClass(cls):
        cls._process.kill()
