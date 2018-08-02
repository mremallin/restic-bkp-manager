#!/usr/bin/env python3

#
# This is a handy script to manage a bunch of restic repos and backups
#

import argparse
import json
import subprocess
import os
import logging

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
                logging.warning("Repo %s is missing field %s", repo.name, field)
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

def create_repo(repo):
    logging.info("Attempting to create backup repo %s", repo.name)
    os.environ["RESTIC_PASSWORD"] = repo.password
    result = subprocess.run(["restic", "-r", repo.name, "init"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ)
    if result.returncode:
        logging.error("Failed to create repository %s with returncode %s",
                      repo.name, result.returncode)
        logging.error(result.stderr.decode("utf-8"))
    logging.info(result.stdout.decode("utf-8"))

def backup_repo_exists(repo):
    logging.debug("Checking if repo %s exists", repo.name)
    os.environ["RESTIC_PASSWORD"] = repo.password
    result = subprocess.run(["restic", "-r", repo.name, "snapshots"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ)
    logging.debug(result.stderr.decode("utf-8"))
    if result.returncode and "Is there a repository at the following location" in result.stderr.decode("utf-8"):
        return False
    return True

def backup_repos(validated_config):
    for repo in validated_config['validated_repos']:
        if not backup_repo_exists(repo):
            create_repo(repo)
        logging.info("Backing up repo %s", repo.name)
        restic_args = "restic -r {repo_name} -v backup {repo_backup_path}".format(
            repo_name=repo.name, repo_backup_path=repo.backup_path)
        os.environ["RESTIC_PASSWORD"] = repo.password
        result = subprocess.run(restic_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                env=os.environ)
        if result.returncode:
            logging.error("Backup failed with returncode: %s", result.returncode)
            logging.error(result.stderr.decode("utf-8"))
        logging.info(result.stdout.decode("utf-8"))

def main():
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s:%(levelname)-8s: %(message)s')
    program_arguments = parseArguments()
    logging.info("Using config file located at: %s", program_arguments.config_file)
    with open(program_arguments.config_file) as config_file:
        loaded_config_file = json.load(config_file)
    validated_config = validate_config_file(loaded_config_file)
    backup_repos(validated_config)

if __name__ == "__main__":
    main()
