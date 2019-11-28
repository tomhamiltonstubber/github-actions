import argparse
import os
import re

from github import Github


def run(issue_number):
    github = Github(os.getenv('GITHUB_TOKEN'))
    tc = github.get_repo('tutorcruncher/TutorCruncher')
    issue = tc.get_issue(issue_number)
    content = issue.body
    url = re.search('URL:(.*)$', content).strip()
    title = re.search('Title:(.*)$', content).strip()
    body = re.search('Content:(.*)$', content, re.DOTALL)
    print(url)
    print(title)
    print(body)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-issue', default='', type=str, help='The Issue number')
    kwargs, other = parser.parse_known_args()
    run(kwargs.issue)
