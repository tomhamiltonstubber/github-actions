import argparse
import glob
import os
import re
from base64 import b64encode

import requests
import uuid

from github import Github, GithubException

MD_IMAGE_REGEX = re.compile('(?:!\[.*?\]\((.*?)\))')
BLOG_IMAGE_TMP = "{{ blog_image('%s') }}"


class HelpArticleCreator:
    def __init__(self, issue_number):
        github = Github(os.getenv('GITHUB_TOKEN'))
        self.tc = github.get_repo('tomhamiltonstubber/github-actions')
        self.issue = self.tc.get_issue(int(issue_number))
        self.branch_name = f'help-entry-{issue_number}'

    def run(self):
        self._get_create_branch()
        if 'new-page' in self.issue.labels:
            self.create_new_page()
        elif 'documentation' in self.issue.labels:
            self.create_new_entry()
        else:
            print('Not a help article.')

    def dl_images(self, page_name, body):
        image_urls = MD_IMAGE_REGEX.findall(body)
        img_paths = []
        for url in image_urls:
            img_path = f'/theme/assets/assets/help/{page_name}-{uuid.uuid4()}.{url.split(".", -1)}'
            r = requests.get(url, img_path)
            r.raise_for_status()
            with open(img_path, 'w+') as f:
                f.write(r.content)
            img_paths.append(img_path)

            body.replace(url, BLOG_IMAGE_TMP % img_path.replace('/theme/assets', ''))
            self._add_to_git(file_path=img_path, content=b64encode(r.content))
        print(f'Downloaded {len(image_urls)} images')
        return body, img_paths

    def create_new_entry(self):
        issue_content = self.issue.content
        try:
            page_name = re.search('Page:(.*)', issue_content).group(1).strip()
            title = re.search('Title:(.*)', issue_content).group(1).strip()
            body = re.search('Content:(.*)', issue_content, re.DOTALL).group(1).strip()
        except AttributeError:
            print('Error parsing template.')
            return
        pages = glob.glob(f'/pages/help/**/{page_name}.md')
        assert pages, f'Page "{page_name}" cannot be found.'
        page_path = pages[0]

        body, img_paths = self.dl_images(page_name, body)
        with open(page_path, 'w+') as f:
            f.write(f.read() + f'## {title}\n\n{body}')
        fil_obj_sha = self.tc.get_contents(page_path, ref=self.branch_name).sha
        self._add_to_git(file_path=page_path, content=body, sha=fil_obj_sha)
        return page_path, img_paths

    def create_new_page(self):
        pass

    def _get_create_branch(self):
        # Creating new branch if needs be
        try:
            self.tc.get_branch(self.branch_name)
        except GithubException as e:
            if e.args[1]['message'] == 'Branch not found':
                self.tc.create_git_ref(f'refs/heads/{self.branch_name}', self.tc.get_commit('master').commit.sha)
            else:
                raise

    def _add_to_git(self, content, file_path, sha=None):
        kwargs = dict(
            path=file_path,
            message='Update Change Log',
            content=content,
            branch=self.branch_name,
        )
        if sha:
            kwargs['sha'] = sha
        self.tc.update_file(**kwargs)
        print(f'Added {file_path} to Git')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('issue', default='', type=str, help='The Issue number')
    kwargs, _ = parser.parse_known_args()
    HelpArticleCreator(kwargs.issue).run()
