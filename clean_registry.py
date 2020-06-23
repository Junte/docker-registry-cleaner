#!/usr/bin/env python

import json
import os
import re
from datetime import datetime

import yaml
from dxf import DXF
from requests import HTTPError

RULES_FILE = "/etc/cleaner/rules.yml"

registry_host = os.environ["REGISTRY_HOST"]
registry_user = os.environ["REGISTRY_USER"]
registry_pass = os.environ["REGISTRY_PASS"]
dry_run = os.environ.get("DRY_RUN", "false") == "true"

print("{0} Parameters {0}".format("*" * 5))
print("host: {0}".format(registry_host))
print("user: {0}".format(registry_user))
print("dry run: {0}".format(dry_run))


def _auth(dxf, response):
    dxf.authenticate(registry_user, registry_pass, response=response)


def _read_rules():
    with open(RULES_FILE) as file_ptr:
        return yaml.safe_load(file_ptr)


_rules = _read_rules()


def _fetch_tags(dxf):
    fetched_aliases = {}

    try:
        for alias in dxf.list_aliases(iterate=True, batch_size=100):
            if alias == "latest":
                continue

            manifest = dxf._request("get", "manifests/" + alias).json()
            created = max(
                datetime.strptime(
                    json.loads(history_item["v1Compatibility"])["created"][:-4],
                    # HACK return non standart date time 2020-06-21T17:07:19.099415601Z
                    "%Y-%m-%dT%H:%M:%S.%f",
                )
                for history_item in manifest["history"]
            )

            fetched_aliases[alias] = created
    except HTTPError as err:
        print("Error: {0}".format(err))

    return fetched_aliases


def _clean_tags(dxf, rule, tags):
    tags = sorted(tags.items(), key=lambda alias: alias[1], reverse=True)

    for tag, created in tags[rule["retain"] :]:
        if dry_run:
            print('"{0}" [{1:%Y-%m-%d %H:%M:%S}] will be deleted'.format(tag, created))
        else:
            dxf.del_alias(tag)
            print('"{0}" [{1:%Y-%m-%d %H:%M:%S}] was deleted'.format(tag, created))


def _clean_repository(repository):
    print('{0} Processing "{1}" {0}'.format("*" * 2, repository["name"]))

    dxf = DXF(registry_host, repository["name"], _auth)
    tags = _fetch_tags(dxf)
    tags_groups = []

    for tag_rule in repository["tags"]:
        pattern = re.compile(tag_rule["pattern"])

        matched = {}
        for tag, created in list(tags.items()):
            if pattern.match(tag):
                matched[tag] = created
                del tags[tag]

        if matched:
            tags_groups.append(
                {"rule": tag_rule, "tags": matched,}
            )

    for tag_group in tags_groups:
        _clean_tags(dxf, tag_group["rule"], tag_group["tags"])


for repository in _rules["repositories"]:
    _clean_repository(repository)

print("{0} done {0}".format("*" * 5))
