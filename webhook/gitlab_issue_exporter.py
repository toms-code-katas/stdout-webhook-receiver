"""
A handler for handling post requests and opening gitlab issues
"""
import datetime
import gitlab
import json
import logging
import os
import socketserver
import threading
import sys
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer

logging.basicConfig(
    level=logging.DEBUG,
    format='{"timestamp": "%(asctime)s", "alert": %(message)s}',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger('gitlab-issue-exporter')


class GitLabConnectionTestTimer(threading.Timer):
    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


class AlarmHandler(BaseHTTPRequestHandler):
    """
    A handler for handling post requests and opening gitlab issues
    """

    def __init__(self, request: bytes, client_address: tuple[str, int], server: socketserver.BaseServer) -> None:
        self.gitlab_url = os.getenv("GITLAB_URL", "https://gitlab.com")
        self.gitlab_project_id = os.getenv("GITLAB_PROJECT_ID", "38561817")
        self.gitlab_username = os.getenv("GITLAB_USERNAME", "gitlab-issue-exporter")
        self.grace_period = os.getenv("GRACE_PERIOD", 1)
        if os.path.isfile("/etc/gitlab-issue-exporter/token"):
            with open('/etc/gitlab-issue-exporter/token', 'r') as secret_file:
                self.gitlab_token = secret_file.read().rstrip()
        else:
            self.gitlab_token = os.getenv("GITLAB_TOKEN")

        self.gitlab = gitlab.Gitlab(self.gitlab_url, private_token=self.gitlab_token)
        self.gitlab_is_healthy = True

        self.t = GitLabConnectionTestTimer(60, self.check_gitlab_connection)
        self.t.start()

        super().__init__(request, client_address, server)

    def check_gitlab_connection(self):
        logger.debug(f"Checking connection to GitLab")
        response = self.gitlab.session.head(self.gitlab.url)
        if response.ok:
            logger.debug(f"Connection to GitLab is working")
            self.gitlab_is_healthy = True
        else:
            logger.error(f"Connection to GitLab is not working")
            self.gitlab_is_healthy = False

    # pylint: disable=C0103
    def do_POST(self):
        """

        :return:
        """

        data_as_string = self.rfile.read(int(self.headers['Content-Length'])).decode("utf-8")
        data = json.loads(data_as_string)

        if not data["status"] == "firing":
            logger.debug("Received alert state is not firing. Omit processing")
        elif not self.gitlab_is_healthy:
            logger.error("Connection to GitLab is not healthy. Alert is not processed")
        else:
            logger.debug("Received alert sate is firing. Start processing")

            project = self.gitlab.projects.get(self.gitlab_project_id, lazy=True)

            message = data["commonAnnotations"]["message"]

            related_issue = self.find_related_issue(message, project)
            if not related_issue:
                logger.debug(
                    f"No issue yet exists with title \"{message}\"."
                    f" Creating one")
                project.issues.create({'title': message,
                                       'description': data["commonAnnotations"]["description"]})
            else:
                issue_id = related_issue["iid"]
                already_created_notes = 0
                latest_creation_date = None
                full_issue = project.issues.get(issue_id)
                for note in full_issue.notes.list():
                    if self.gitlab_username == note.author["username"]:
                        already_created_notes += 1
                        creation_date = datetime.datetime.strptime(note.created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                        if not latest_creation_date:
                            latest_creation_date = creation_date
                        elif creation_date > latest_creation_date:
                            latest_creation_date = creation_date
                logger.debug(f"Found {already_created_notes} notes created by {self.gitlab_username}")
                if already_created_notes <= 9 and self.has_grace_period_elapsed(latest_creation_date):
                    logger.debug("Issue already exists. Adding note")
                    full_issue.notes.create({'body': f'`{datetime.datetime.utcnow()}`: Issue not yet resolved'})
                elif already_created_notes == 10:
                    logger.debug("Maximum number of notes reached for issue")
                    full_issue.notes.create({'body': f"`{datetime.datetime.utcnow()}`: Maximum number of notes"
                                                     f" reached for issue. Issue will no longer be updated"})
                else:
                    logger.debug("Maximum number of notes exceeded for issue. Omitting note creation")

        self.send_response(200)
        self.end_headers()

    def find_related_issue(self, title, project):
        for issue in project.search('issues', [title], as_list=False, order_by="created_at"):
            if issue["state"] == "opened":
                issue_id = issue['iid']
                logger.debug(f"Found already existing issue \"{issue_id}\", \"{issue['title']}\"")
                return issue

    def has_grace_period_elapsed(self, latest_creation_date):
        if not latest_creation_date:
            return True
        seconds_since_last_note = int((datetime.datetime.utcnow() - latest_creation_date).total_seconds())
        if seconds_since_last_note < self.grace_period:
            logger.debug(
                f"Seconds since last note creation {seconds_since_last_note} than smaller {self.grace_period}."
                f" Omit creation of note")
            return False
        return True


def main():
    httpd = HTTPServer(('', 8080), AlarmHandler)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
