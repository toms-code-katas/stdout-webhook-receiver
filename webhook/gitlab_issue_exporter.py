"""
A handler for handling post requests and opening gitlab issues
"""
import gitlab
import os
import socketserver
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

logger = logging.getLogger('gitlab-issue-exporter')


class AlarmHandler(BaseHTTPRequestHandler):
    """
    A handler for handling post requests and opening gitlab issues
    """

    def __init__(self, request: bytes, client_address: tuple[str, int], server: socketserver.BaseServer) -> None:
        self.gitlab_url = os.getenv("GITLAB_URL", "https://gitlab.com")
        self.gitlab_project_id = os.getenv("GITLAB_PROJECT_ID", "38561817")
        if os.path.isfile("/etc/gitlab-issue-exporter/token"):
            with open('/etc/gitlab-issue-exporter/token', 'r') as secret_file:
                self.gitlab_token = secret_file.read().rstrip()
        else:
            self.gitlab_token = os.getenv("GITLAB_TOKEN")
        super().__init__(request, client_address, server)

    # pylint: disable=C0103
    def do_POST(self):
        """

        :return:
        """

        data_as_string = self.rfile.read(int(self.headers['Content-Length'])).decode("utf-8")
        data = json.loads(data_as_string)

        if not data["status"] == "firing":
            logger.debug("Received alert state is not firing. Omit processing")
        else:
            logger.debug("Received alert sate is firing. Start processing")

            gl = gitlab.Gitlab(self.gitlab_url, private_token=self.gitlab_token)
            project = gl.projects.get(self.gitlab_project_id, lazy=True)

            environment = data["commonLabels"]["platform_environment"]
            deployment = data["commonLabels"]["deployment"]

            for issue in project.search('issues', [deployment, environment], as_list=False):
                print(issue)

        self.send_response(200)
        self.end_headers()


def main():
    httpd = HTTPServer(('', 8080), AlarmHandler)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
