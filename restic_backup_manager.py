#!/usr/bin/env python3

#
# This is a handy script to manage a bunch of restic repos and backups
#

import argparse
import json
import subprocess
import os

from collections import namedtuple

BackupRepo = namedtuple("BackupRepo", ['name', 'backup_path', 'password'])

def parseArguments():
    parser = argparse.ArgumentParser(description="Automate backups with restic")
    parser.add_argument('config_file',
                        help="Configuration file to instruct restic with")
    return parser.parse_args()

def validate_repos_section(config_file_repos):
    repo_list = []
    for repo in config_file_repos:
        skip_repo = False
        for field in ['name', 'backup_path', 'password']:
            if field not in repo:
                print("Repo is missing", field, repo)
                skip_repo = True
                break
        if skip_repo:
            continue
        repo_list.append(BackupRepo(repo['name'], repo['backup_path'], repo['password']))

    return repo_list

def validate_config_file(config_file_json):
    validated_config = {
        "validated_repos" : validate_repos_section(config_file_json['repos'])
    }
    return validated_config

def backup_repos(validated_config):
    for repo in validated_config['validated_repos']:
        print("Backing up repo:", repo.name)
        restic_args = "restic -r {repo_name} -v backup {repo_backup_path}".format(
            repo_name=repo.name, repo_backup_path=repo.backup_path)
        os.environ["RESTIC_PASSWORD"] = repo.password
        result = subprocess.run(restic_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                env=os.environ)
        if result.returncode:
            print("Backup failed with returncode:", result.returncode)
            print(result.stderr.decode("utf-8"))
        print(result.stdout.decode("utf-8"))

def main():
    program_arguments = parseArguments()
    print("Using config file located at:", program_arguments.config_file)
    with open(program_arguments.config_file) as config_file:
        loaded_config_file = json.load(config_file)
    validated_config = validate_config_file(loaded_config_file)
    backup_repos(validated_config)

if __name__ == "__main__":
    main()
