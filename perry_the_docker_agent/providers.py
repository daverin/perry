import logging
import os
import platform
import shlex
import subprocess
import sys
import time
from functools import lru_cache
from typing import Dict, Optional

import boto3
from perry_the_docker_agent.config.instance_config import PerryInstanceConfig

from .util import logger


@lru_cache()
def _get_ec2_client(region, *, profile_name: Optional[str]):
    session = boto3.Session(profile_name=profile_name)
    return session.client(
        "ec2",
        region_name=region,
    )


class AWSInstanceProvider:
    def __init__(
        self,
        *,
        username: str,
        instance_config: PerryInstanceConfig,
        bootstrap_command: str,
    ):
        self.username = username
        self.instance_config = instance_config
        self.bootstrap_command = bootstrap_command

    @property
    def _ec2_client(self):
        return _get_ec2_client(
            self.instance_config.region, profile_name=self.instance_config.aws_profile
        )

    def _search_for_instances(self) -> Dict:
        return self._ec2_client.describe_instances(
            InstanceIds=[self.instance_config.instance_id]
        )

    def _get_instance(self) -> Dict:
        reservations = self._search_for_instances()["Reservations"]
        valid_reservations = [
            reservation
            for reservation in reservations
            if len(reservation["Instances"]) == 1
            and reservation["Instances"][0]["State"]["Name"] != "terminated"
        ]

        if len(valid_reservations) == 0:
            raise Exception(
                "There are no valid reservations, did you create the instance?"
            )
        if len(valid_reservations) > 1:
            raise Exception(
                "There is more than one reservation found that matched, not sure what to do"
            )

        instances = valid_reservations[0]["Instances"]
        assert len(instances) == 1, f"{len(instances)} != 1"
        return instances[0]

    def get_ip(self) -> str:
        if not self.is_running():
            raise Exception("Instance is not running. start it with `rd start`")
        return self._get_instance()["PublicIpAddress"]

    def get_instance_id(self) -> str:
        return self._get_instance()["InstanceId"]

    def get_instance_state(self) -> str:
        return self._get_instance()["State"]["Name"]

    def is_running(self):
        return self.get_instance_state() == "running"

    def is_stopped(self):
        return self.get_instance_state() == "stopped"

    def start_instance(self):
        ret = self._ec2_client.start_instances(
            InstanceIds=[self.instance_config.instance_id]
        )
        self._wait_for_running_state()
        return ret

    def stop_instance(self):
        ret = self._ec2_client.stop_instances(
            InstanceIds=[self.instance_config.instance_id]
        )
        self._wait_for_stopped_state()
        return ret

    def _set_disable_api_termination(self, value: bool):
        return self._ec2_client.modify_instance_attribute(
            DisableApiTermination=dict(Value=value),
            InstanceId=self.instance_config.instance_id,
        )

    def enable_termination_protection(self):
        return self._set_disable_api_termination(True)

    def disable_termination_protection(self):
        return self._set_disable_api_termination(False)

    def is_termination_protection_enabled(self):
        return self._ec2_client.describe_instance_attribute(
            Attribute="disableApiTermination",
            InstanceId=self.instance_config.instance_id,
        )["DisableApiTermination"]["Value"]

    # flake8: noqa: E501
    def bootstrap_instance(self):
        logger.info("Bootstrapping instance, will take a few minutes")

        self.ssh_connect(
            ssh_key_path=self.instance_config.perry_key_path,
            ssh_cmd=self.bootstrap_command,
        )

    def _wait_for_running_state(self):
        return self._wait_for_state("running")

    def _wait_for_stopped_state(self):
        return self._wait_for_state("stopped")

    def _wait_for_state(self, desired_state):
        timeout = 120
        step = 5
        elapsed = 0

        while True:
            state = self.get_instance_state()

            if state == desired_state:
                break

            if elapsed >= timeout:
                raise RuntimeError(
                    f"Timed out while waiting for instance to reach {desired_state} state (still in {state})."
                )

            logger.info(f"Waiting for instance to reach {desired_state} state")
            time.sleep(step)
            elapsed += step

    def ssh_connect(
        self, *, ssh_key_path: str, ssh_cmd: str = None, options: str = None
    ):
        cmd = self._build_ssh_cmd(ssh_key_path, ssh_cmd, options)

        os.execvp(cmd[0], cmd)

    def ssh_run(self, *, ssh_key_path: str, ssh_cmd: str = None):
        cmd = self._build_ssh_cmd(ssh_key_path, ssh_cmd)
        return subprocess.run(cmd, check=True)

    def _build_ssh_cmd(self, ssh_key_path: str, ssh_cmd=None, options=None):
        ssh_cmd = ssh_cmd if ssh_cmd else ""
        options = options if options else ""

        cmd_s = (
            f"ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60"
            f" -i {ssh_key_path}"
            f" {options} {self.username}@{self.get_ip()} {ssh_cmd}"
        )

        logger.debug(
            "Running: %s",
            shlex.split(
                cmd_s,
                posix=platform.system() != "Windows",
            ),
        )
        return shlex.split(
            cmd_s,
            posix=platform.system() != "Windows",
        )
