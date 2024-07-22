import os
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel


class PerryConfig(BaseModel):
    # --- naming
    project_id: str = "new-project"

    # --- networking
    bind_address: str = "localhost"

    # --- ssh
    key_path: Optional[str]

    # -- labeling
    env_label: Optional[str]

    env_label_suffix: str = "s"
    separator: str = "-"

    # --- paths

    instance_config_path: Optional[str] = "./perry_instance_config.json"
    instance_pem_path: Optional[str]

    # --- unison properties
    ignore_dirs: List[str] = []
    local_port_forwards: Dict[str, Dict[str, str]] = {}
    remote_port_forwards: Dict[str, Dict[str, str]] = {}
    sync_paths: List[Path]

    # --- instance properties
    instance_username = "ubuntu"
    bootstrap_command = r"""
        set -x
        && sudo sysctl -w net.core.somaxconn=4096
        && sudo echo GRUB_CMDLINE_LINUX=\\"\"cdgroup_enable=memory swapaccount=1\\"\" | sudo tee -a /etc/default/grub.d/50-cloudimg-settings.cfg
        && sudo update-grub
        && sudo rm /var/lib/dpkg/lock
        && sudo dpkg --configure -a
        && sudo apt-get -y update
        && sudo apt-get -y install docker.io || true
        && sudo usermod -aG docker ubuntu  || true
        && sudo systemctl daemon-reload || true
        && sudo systemctl restart docker.service || true
        && sudo systemctl enable docker.service || true
        && "sudo sed -i -e '/GatewayPorts/ s/^.*$/GatewayPorts yes/' '/etc/ssh/sshd_config'"
        && sudo service sshd restart
        && wget -qO- https://github.com/bcpierce00/unison/releases/download/v2.52.1/unison-v2.52.1+ocaml-4.01.0+x86_64.linux.tar.gz | tar -xvz
        && sudo mv bin/* /usr/local/bin/
        && sudo reboot
    """

    @property
    def expanded_sync_dir(self) -> str:
        return os.path.expanduser("~")

    @property
    def expanded_sync_paths(self) -> List[str]:
        return [
            str(Path(os.path.expanduser(f)).absolute()).split(
                self.expanded_sync_dir + os.sep
            )[1]
            for f in self.sync_paths
        ]
