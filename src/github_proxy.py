"""Proxy for interacting with Github."""

import re

import boto3
from github import Github

import config
import lambdalogging

LOG = lambdalogging.getLogger(__name__)

SAR_APP_URL = ('https://serverlessrepo.aws.amazon.com/applications/arn:aws:serverlessrepo:us-east-1:277187709615:'
               'applications~github-codebuild-logs')
SAR_HOMEPAGE = 'https://aws.amazon.com/serverless/serverlessrepo/'

PR_COMMENT_TEMPLATE = """
### AWS CodeBuild CI Report

* Result: {}
* [Build Logs]({}) (available for {} days)

*Powered by [github-codebuild-logs]({}), available on the [AWS Serverless Application Repository]({})*
"""

CODEBUILD = boto3.client('codebuild')


class GithubProxy:
    """Encapsulate interactions with Github."""

    def __init__(self):
        """Initialize proxy."""
        pass

    def publish_pr_comment(self, build):
        """Publish PR comment with link to build logs."""
        pr_comment = PR_COMMENT_TEMPLATE.format(
            build.status,
            build.get_logs_url(),
            config.EXPIRATION_IN_DAYS,
            SAR_APP_URL,
            SAR_HOMEPAGE
        )

        # initialize client before logging to ensure GitHub attributes are populated
        gh_client = self._get_client()
        LOG.debug('Publishing PR Comment: repo=%s/%s, pr_id=%s, comment=%s',
                  self._github_owner, self._github_repo, build.get_pr_id(), pr_comment)

        repo = gh_client.get_user(self._github_owner).get_repo(self._github_repo)
        repo.get_pull(build.get_pr_id()).create_issue_comment(pr_comment)

    def _get_client(self):
        if not hasattr(self, '_client'):
            self._init_client()
        return self._client

    def _init_client(self):
        self._init_github_info()
        self._client = Github(self._github_token)

    def _init_github_info(self):
        response = CODEBUILD.batch_get_projects(
            names=[config.PROJECT_NAME]
        )

        project_details = response['projects'][0]
        if project_details['source']['type'] != 'GITHUB':
            raise RuntimeError(
                'AWS CodeBuild project {} source is not GITHUB. Project source must be of type GITHUB'.format(
                    config.PROJECT_NAME))

        if project_details['source']['auth']['type'] != 'OAUTH':
            raise RuntimeError('Could not get GitHub auth token from AWS CodeBuild project {}.'.format(
                config.PROJECT_NAME))

        self._github_token = project_details['source']['auth']['resource']

        github_location = project_details['source']['location']
        matches = re.search(r'github\.com\/(.+)\/(.+)\.git$', github_location)
        if not matches:
            raise RuntimeError(
                'Could not parse GitHub owner/repo name from AWS CodeBuild project {}. location={}'.format(
                    config.PROJECT_NAME, github_location))

        self._github_owner = matches.group(1)
        self._github_repo = matches.group(2)
