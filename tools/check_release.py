#!/usr/bin/env python

import json
import os

import yaml

import koji

def get_brew_session():
    opts = {
        'no_ssl_verify': True,
    }
    return koji.ClientSession("https://brewhub.engineering.redhat.com/brewhub", opts=opts)

projects = {
    "assisted-service": {
        "regexp": '^assisted-installer-container-v',
        "deployment_key": "openshift/assisted-installer",
    },
    "assisted-installer-agent": {
        "regexp": '^assisted-installer-agent-container-v',
    "deployment_key": "openshift/assisted-installer-agent",
    },
    "assisted-service-reporter": {
        "regexp": '^assisted-installer-reporter-container-v',
        "deployment_key": "openshift/assisted-installer",
    },
}

class DownstreamChecker:

    def __init__(self, session):
        self._session = session

    def check_downstream_latest_build(self, regexp, commit_hash=None):
        query_opts = {'limit': 1, 'order': '-id'}
        builds = self._session.search(terms=regexp, type="build", matchType="regexp", queryOpts=query_opts)
        build_id = builds[0]['id']

        build_info = self._session.getBuild(build_id)
        task_id = self._get_task_id(build_info)
        logfile = self._session.downloadTaskOutput(task_id, "osbs-build.log")

        match_revision_pattern = f'upstream_commit="{commit_hash}"'
        if match_revision_pattern in str(logfile):
            return build_info['nvr']
        raise Exception(f"downstream not matching {commit_hash}")

    def _get_task_id(self, build_info):
        if "extra" not in build_info and not build_info["extra"]:
            raise Exception("Shouldn't be empty... is it build in progress?")
        if "container_koji_task_id" not in build_info["extra"]:
            raise Exception("Shouldn't be empty... what'sgoingon")
        return build_info['extra']['container_koji_task_id']

if __name__ == "__main__":
    downstream_checker = DownstreamChecker(get_brew_session())

    deployment_file_path = os.path.join(os.path.dirname(__file__), "../assisted-installer.yaml")
    with open(deployment_file_path, "r") as f:
        deployment = yaml.safe_load(f)

    for (project_name, project_info) in projects.items():
        try:
            downstream_checker.check_downstream_latest_build(
                project_info["regexp"],
                deployment[project_info["deployment_key"]]["revision"],
            )
        except Exception as e:
            print(e)
