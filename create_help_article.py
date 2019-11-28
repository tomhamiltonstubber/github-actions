import argparse
import glob
import os
import random
import re
import string
from base64 import b64encode

import requests

from github import Github, GithubException

MD_IMAGE_REGEX = re.compile('(?:(!\[.*?\])\((.*?)\))')
BLOG_IMAGE_TMP = "{{ blog_image('%s') }}"
NEW_FILE_TEMPLATE = """
---
title: {title}
order: {order}
alt: {alt_tags}
related_posts:
  - {related_1}
  - {related_2}
---
{content}
"""


class HelpArticleCreator:
    def __init__(self, issue_number):
        github = Github(os.getenv('GITHUB_TOKEN'))
        self.repo = github.get_repo('tomhamiltonstubber/github-actions')
        self.issue = self.repo.get_issue(int(issue_number))
        self.branch_name = f'help-entry-{issue_number}'

    def run(self):
        self._get_create_branch()
        labels = [l.name for l in self.issue.labels]
        if 'new-page' in labels:
            self.create_new_page()
        elif 'documentation' in labels:
            self.create_new_entry()
        else:
            print('Not a help article.')
            return
        self._get_create_pr()

    def _random_str(self):
        return ''.join(random.choice(string.ascii_lowercase) for _ in range(6))

    def dl_images(self, page_name, body):
        image_urls = MD_IMAGE_REGEX.findall(body)
        img_paths = []
        for i, (alt, url) in enumerate(image_urls):
            img_path = f'theme/assets/assets/help/{page_name}-{i}.{url.split(".")[-1]}'
            r = requests.get(url, img_path)
            r.raise_for_status()
            img_paths.append(img_path)
            body = body.replace(f'{alt}({url})', BLOG_IMAGE_TMP % img_path.replace('/theme/assets', ''))
            self._add_to_git(file_path=img_path, content=r.content)
        print(f'Downloaded {len(image_urls)} images')
        return body, img_paths

    def create_new_entry(self):
        issue_content = self.issue.body
        try:
            page_name = re.search('Page:(.*)', issue_content).group(1).strip()
            title = re.search('Title:(.*)', issue_content).group(1).strip()
            body = re.search('Content:(.*)', issue_content, re.DOTALL).group(1).strip()
        except AttributeError as e:
            print('Error parsing template. %s' % e)
            return
        pages = glob.glob(f'pages/help/**/**/{page_name}.md', recursive=True)
        assert pages, f'Page "{page_name}" cannot be found.'
        page_path = pages[0]

        body, img_paths = self.dl_images(page_name, body)

        with open(page_path) as f:
            old_content = f.read()
        new_content = old_content + f'\n## {title}\n\n{body}'

        self._add_to_git(file_path=page_path, content=new_content)

    def get_attr(self, term, body, dotall=False):
        try:
            return re.search(term, body, flags=[re.DOTALL] if dotall else 0).group(1).strip()
        except AttributeError:
            print(f"Couldn't find term '{term}' in body")
            raise

    def create_new_page(self):
        issue_content = self.issue.body
        try:
            page_name = self.get_attr('Page:(.*)', issue_content)
            category = self.get_attr('Category:(.*)', issue_content)
            title = self.get_attr('Title:(.*)', issue_content)
            body = self.get_attr('Content:(.*)', issue_content, re.DOTALL)
            alt = self.get_attr('Alternative tags:(.*)', issue_content)
            related_1 = self.get_attr('Related Post 1:(.*)', issue_content)
            related_2 = self.get_attr('Related Post 2:(.*)', issue_content)
        except AttributeError as e:
            print('Error parsing template. %s' % e)
            return

        pages = glob.glob(f'pages/help/**/{category}/*')
        assert pages, f'Category {category} does not exist.'
        new_file_path = f'{pages[0].split(category)[0]}{category}{page_name}.md'

        body, img_paths = self.dl_images(page_name, body)

        new_content = NEW_FILE_TEMPLATE.format(
            title=title,
            alt=alt,
            related_1=related_1,
            related_2=related_2,
            content=body
        )

        self._add_to_git(file_path=new_file_path, content=new_content)

    def _get_create_branch(self):
        # Creating new branch if needs be
        try:
            self.repo.get_branch(self.branch_name)
        except GithubException as e:
            if e.args[1]['message'] == 'Branch not found':
                master_commit = self.repo.get_commit('master').commit
                self.repo.create_git_ref(f'refs/heads/{self.branch_name}', master_commit.sha)
            else:
                raise

    def _get_create_pr(self):
        try:
            self.repo.create_pull(title='Update Changelog', body='', base='master', head=self.branch_name)
        except GithubException as e:
            error = e.args[1]['errors'][0]
            if 'A pull request already exists' not in error['message']:
                raise
        else:
            print('Pull request created')

    def _add_to_git(self, content, file_path):
        file_path = file_path.lstrip('/')
        kwargs = dict(
            path=file_path,
            message=f'Help entry for issue {self.issue.number}',
            content=content,
            branch=self.branch_name,
        )
        try:
            kwargs['sha'] = self.repo.get_contents(file_path, ref=self.branch_name).sha
        except GithubException as e:  # File not in GIT yet.
            if not e.args[1]['message'] == 'Not Found':
                raise
            self.repo.create_file(**kwargs)
        else:
            self.repo.update_file(**kwargs)
        print(f'Added {file_path} to Git')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('issue', default='', type=str, help='The Issue number')
    kwargs, _ = parser.parse_known_args()
    HelpArticleCreator(kwargs.issue).run()
