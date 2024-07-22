from typing import Annotated, Optional

import typer
from perry_the_docker_agent.config.instance_config import PerryInstanceConfig
from perry_the_docker_agent.config.perry_config import PerryConfig
from perry_the_docker_agent.core import RemoteDockerClient
from rich import print
from yaml import safe_load

app = typer.Typer(pretty_exceptions_enable=False)


@app.command()
def start(ctx: typer.Context):
    """Start the remote agent instance"""
    client: RemoteDockerClient = ctx.obj
    print(client.start_instance())
    client.use_remote_context()


@app.command()
def sync(ctx: typer.Context):
    """Sync the given directories with the remote instance"""
    client: RemoteDockerClient = ctx.obj
    client.sync()


@app.command()
def bootstrap(ctx: typer.Context):
    """Connect to the remote agent via SSH"""
    client: RemoteDockerClient = ctx.obj
    client.bootstrap()


@app.command()
def ssh(
    ctx: typer.Context,
    *,
    command: Annotated[Optional[str], typer.Argument(help="ssh command")] = None,
    options: Annotated[Optional[str], typer.Option(help="ssh options")] = None
):
    """Connect to the remote agent via SSH"""
    client: RemoteDockerClient = ctx.obj
    client.ssh_connect(ssh_cmd=command, options=options)


@app.command()
def stop(ctx: typer.Context):
    """Stop the remote agent instance"""
    client: RemoteDockerClient = ctx.obj
    print(client.stop_instance())
    client.use_default_context()


@app.command()
def tunnel(ctx: typer.Context):
    """
    Create a SSH tunnel to the remote instance to connect
    with the docker agent and containers
    """
    client: RemoteDockerClient = ctx.obj
    client.start_tunnel()


@app.callback()
def entry(
    ctx: typer.Context,
    config_path: str = typer.Option(
        "./perry_config.yml",
        help="Path of the perry config",
    ),
):
    loaded_yaml = safe_load(open(config_path))

    config = PerryConfig.parse_obj(loaded_yaml)

    instance_config = PerryInstanceConfig.parse_file(config.instance_config_path)

    ctx.obj = RemoteDockerClient.from_config(config, instance_config)


if __name__ == "__main__":
    app()
