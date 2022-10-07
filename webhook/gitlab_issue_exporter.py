"""
A handler for handling post requests and opening gitlab issues
"""
# pylint: disable=C0115,C0116
import datetime
import json
import logging
import os
import socketserver
import threading
import sys
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
import gitlab
from gitlab.exceptions import GitlabError

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

    def __init__(self, request: bytes, client_address: tuple[str, int],
                 server: socketserver.BaseServer) -> None:
        gitlab_url = os.getenv("GITLAB_URL", "https://gitlab.com")
        gitlab_project_id = os.getenv("GITLAB_PROJECT_ID", "38561817")
        self.grace_period = int(os.getenv("GRACE_PERIOD", "1"))
        if os.path.isfile("/etc/gitlab-issue-exporter/username"):
            with open('/etc/gitlab-issue-exporter/username', 'r', encoding="utf-8") as secret_file:
                self.gitlab_username = secret_file.read().rstrip()
        else:
            self.gitlab_username = os.getenv("GITLAB_USERNAME", "gitlab-issue-exporter")
        gitlab_token = os.getenv("GITLAB_TOKEN", "")
        if os.path.isfile("/etc/gitlab-issue-exporter/token"):
            with open('/etc/gitlab-issue-exporter/token', 'r', encoding="utf-8") as secret_file:
                gitlab_token = secret_file.read().rstrip()

        self.gitlab = gitlab.Gitlab(gitlab_url, private_token=gitlab_token)
        self.project = self.gitlab.projects.get(gitlab_project_id, lazy=True)
        self.gitlab_is_healthy = True

        self.connection_test_timer = GitLabConnectionTestTimer(60, self.check_gitlab_connection)
        self.connection_test_timer.start()

        super().__init__(request, client_address, server)

    def check_gitlab_connection(self):
        logger.debug("Checking connection to GitLab")
        response = self.gitlab.session.head(self.gitlab.url)
        if response.ok:
            logger.debug("Connection to GitLab is working")
            self.gitlab_is_healthy = True
        else:
            logger.error("Connection to GitLab is not working")
            self.gitlab_is_healthy = False

    # pylint: disable=C0103
    def do_POST(self):
        """

        :return:
        """

        request_body = self.rfile.read(int(self.headers['Content-Length'])).decode("utf-8")
        alert = json.loads(request_body)

        if not alert["status"] == "firing":
            logger.debug("Received alert state is not firing. Omit processing")
        elif not self.gitlab_is_healthy:
            logger.error("Connection to GitLab is not healthy. Alert is not processed")
        else:
            logger.debug("Received alert sate is firing. Start processing")

            alert_message = alert["commonAnnotations"]["message"]

            related_issue = self.find_related_issue(alert_message)
            if not related_issue:
                self.create_related_issue(alert, alert_message)
            else:
                issue_id = related_issue["iid"]
                self.update_related_issue(issue_id)

        self.send_response(200)
        self.end_headers()

    def update_related_issue(self, issue_id):
        full_issue = self.project.issues.get(issue_id)

        already_created_notes, latest_creation_date = self.get_issue_metadata(full_issue)
        logger.debug("Found %s notes created by %s", already_created_notes, self.gitlab_username)

        if already_created_notes <= 9 and self.has_grace_period_elapsed(latest_creation_date):
            logger.debug("Issue already exists. Adding note")
            full_issue.notes.create(
                {'body': f'`{datetime.datetime.utcnow()}`: Issue not yet resolved'})
        elif already_created_notes == 10:
            logger.debug("Maximum number of notes reached for issue")
            full_issue.notes.create(
                {'body': f"`{datetime.datetime.utcnow()}`: Maximum number of notes"
                         f" reached for issue. Issue will no longer be updated"})
        else:
            logger.debug("Maximum number of notes exceeded for issue. Omitting note creation")

    def get_issue_metadata(self, full_issue):
        already_created_notes = 0
        latest_creation_date = None
        for note in full_issue.notes.list():
            if self.gitlab_username == note.author["username"]:
                already_created_notes += 1
                creation_date = datetime.datetime.strptime(note.created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                if not latest_creation_date:
                    latest_creation_date = creation_date
                elif creation_date > latest_creation_date:
                    latest_creation_date = creation_date
        return already_created_notes, latest_creation_date

    def create_related_issue(self, alert, alert_message):
        logger.debug(
            "No issue yet exists with title \"%s\"."
            " Creating one", alert_message)
        try:
            self.project.issues.create({'title': alert_message,
                                        'description': alert["commonAnnotations"]["description"]})
        except GitlabError as e:
            logger.error(
                "Could not create an issue for alert \"%s\": %s", alert_message, e)

    def find_related_issue(self, title):
        for issue in self.project.search('issues', [title], as_list=False, order_by="created_at"):
            if issue["state"] == "opened":
                issue_id = issue['iid']
                logger.debug("Found already existing issue \"%s\", \"%s\"", issue_id,
                             issue['title'])
                return issue
        return None

    def has_grace_period_elapsed(self, latest_creation_date):
        if not latest_creation_date:
            return True
        seconds_since_last_note = int(
            (datetime.datetime.utcnow() - latest_creation_date).total_seconds())
        if seconds_since_last_note < self.grace_period:
            logger.debug(
                "Seconds since last note creation %s"
                " than smaller %s."
                " Omit creation of note", seconds_since_last_note, self.grace_period)
            return False
        return True


def main():
    httpd = HTTPServer(('', 8080), AlarmHandler)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
