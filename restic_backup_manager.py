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

def validate_config_section(config_file_configs):
    config_dict = {}
    for config_item in config_file_configs:
        if config_item in ['keep-daily', 'keep-weekly', 'keep-monthly', 'keep-yearly', 'keep-last', 'b2-account-id', 'b2-account-key']:
            config_dict[config_item] = config_file_configs[config_item]
        else:
            logging.warning("Unknown configuration item %s", config_item)
    return config_dict

def validate_config_file(config_file_json):
    if "repos" not in config_file_json:
        logging.error("No repos to backup!")
        exit()
    validated_config = {
        "validated_repos" : validate_repos_section(config_file_json['repos']),
    }
    if "config" in config_file_json:
        validated_config["validated_config"] = validate_config_section(config_file_json['config'])
    return validated_config

def setup_environment_config(validated_config):
    for config, item in validated_config.items():
        if "b2-account-id" in config:
            os.environ["B2_ACCOUNT_ID"] = str(item)
            logging.debug("Added B2_ACCOUNT_ID")
        elif "b2-account-key" in config:
            os.environ["B2_ACCOUNT_KEY"] = str(item)
            logging.debug("Added B2_ACCOUNT_KEY")

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
    if result.returncode and "Is there a repository at the following location" in result.stderr.decode("utf-8"):
        return False
    return True

def forget_old_snapshots(repo, validated_config):
    if "validated_config" not in validated_config:
        logging.info("No configuration for forgetting old snapshots. Skipping...")
        return
    restic_args = ["restic", "-r", repo.name, "forget", "--prune"]
    for config, key in validated_config["validated_config"].items():
        logging.debug("Getting snapshot policy config %s %s", config, str(key))
        if "keep-weekly" in config:
            restic_args.extend(["--keep-weekly", str(key)])
        elif "keep-daily" in config:
            restic_args.extend(["--keep-daily", str(key)])
        elif "keep-monthly" in config:
            restic_args.extend(["--keep-monthly", str(key)])
        elif "keep-yearly" in config:
            restic_args.extend(["--keep-yearly", str(key)])
        elif "keep-last" in config:
            restic_args.extend(["--keep-last", str(key)])
    logging.debug("Calling restic: %s", restic_args)
    os.environ["RESTIC_PASSWORD"] = repo.password
    result = subprocess.run(restic_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ)
    if result.returncode:
        logging.error("Forget failed with returncode: %s", result.returncode)
        logging.error(result.stderr.decode("utf-8"))
    logging.info(result.stdout.decode("utf-8"))

def backup_repos(validated_config):
    for repo in validated_config['validated_repos']:
        if not backup_repo_exists(repo):
            create_repo(repo)
        logging.info("Backing up repo %s", repo.name)
        os.environ["RESTIC_PASSWORD"] = repo.password
        restic_args = ["restic", "-r", repo.name, "backup", repo.backup_path]
        result = subprocess.run(restic_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ)
        if result.returncode:
            logging.error("Backup failed with returncode: %s", result.returncode)
            logging.error(result.stderr.decode("utf-8"))
        logging.info(result.stdout.decode("utf-8"))

        forget_old_snapshots(repo, validated_config)

def main():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s:%(levelname)-8s: %(message)s')
    program_arguments = parseArguments()
    logging.info("Using config file located at: %s", program_arguments.config_file)
    with open(program_arguments.config_file) as config_file:
        loaded_config_file = json.load(config_file)
    validated_config = validate_config_file(loaded_config_file)
    setup_environment_config(validated_config['validated_config'])
    backup_repos(validated_config)

if __name__ == "__main__":
    main()
