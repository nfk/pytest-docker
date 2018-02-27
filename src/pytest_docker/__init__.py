# -*- coding: utf-8 -*-


import attr
import os
import pytest
import re
import subprocess
import time
import timeit

from compose.cli.main import TopLevelCommand
from compose.cli.main import project_from_options
from inspect import getdoc
from docopt import docopt


@pytest.fixture(scope='session')
def docker_ip():
    """Determine IP address for TCP connections to Docker containers."""

    # When talking to the Docker daemon via a UNIX socket, route all TCP
    # traffic to docker containers via the TCP loopback interface.
    docker_host = os.environ.get('DOCKER_HOST', '').strip()
    if not docker_host:
        return '127.0.0.1'

    match = re.match('^tcp://(.+?):\d+$', docker_host)
    if not match:
        raise ValueError(
            'Invalid value for DOCKER_HOST: "%s".' % (docker_host,)
        )
    return match.group(1)


@attr.s(frozen=True)
class Services(object):
    """."""

    _docker_compose = attr.ib()
    _docker_allow_fallback = attr.ib(default=False)

    def port_for(self, service, port, protocol='tcp'):
        """Get the effective bind port for a service."""

        # Return the container port if we run in no Docker mode.
        if self._docker_allow_fallback:
            return port

        docker_service = self._docker_compose.get_service(service)
        container = docker_service.get_container()

        docker_port = '{}/{}'.format(port, protocol)
        ports = container.ports.get(docker_port)
        if ports is None or len(ports) != 1:
            raise ValueError(
                'Could not detect port for "%s:%d".' % (service, port)
            )

        return int(ports[0]['HostPort'])

    def wait_until_responsive(self, check, timeout, pause,
                              clock=timeit.default_timer):
        """Wait until a service is responsive."""

        ref = clock()
        now = ref
        while (now - ref) < timeout:
            if check():
                return
            time.sleep(pause)
            now = clock()

        raise Exception(
            'Timeout reached while waiting on service!'
        )


def str_to_list(arg):
    if isinstance(arg, (list, tuple)):
        return arg
    return [arg]


@attr.s(frozen=True)
class DockerComposeExecutor(object):
    _compose_files = attr.ib(convert=str_to_list)
    _compose_project_name = attr.ib()
    _compose_project_dir = attr.ib()

    def as_dict_options(self):
        return {
            '--file': self._compose_files,
            '--project-dir': self._compose_project_dir,
            '--project-name': self._compose_project_name
        }

    def defaults_opts(self, command):
        """ Retrieve all options with default value of docker compose command
        """
        cmd_help = getdoc(getattr(TopLevelCommand, command))
        return docopt(cmd_help, [])


@pytest.fixture(scope='session')
def docker_compose_file(pytestconfig):
    """Get the docker-compose.yml absolute path.

    Override this fixture in your tests if you need a custom location.

    """
    return os.path.join(
        str(pytestconfig.rootdir),
        'tests',
        'docker-compose.yml'
    )


@pytest.fixture(scope='session')
def docker_compose_project_dir(pytestconfig):
    """Get the docker compose project directory absolute path.

    Override this fixture in your tests if you need a custom location.

    """
    return os.path.join(
        str(pytestconfig.rootdir),
        'tests'
    )


@pytest.fixture(scope='session')
def docker_compose_project_name():
    """ Generate a project name using the current process' PID.

    Override this fixture in your tests if you need a particular project name.
    """
    return "pytest{}".format(os.getpid())


@pytest.fixture(scope='session')
def docker_allow_fallback():
    """Return if want to run against localhost when docker is not available.

    Override this fixture to return `True` if you want the ability to
    run without docker.

    """
    return False


@pytest.fixture(scope='session')
def docker_services(
    docker_compose_file, docker_allow_fallback, docker_compose_project_name,
    docker_compose_project_dir
):
    """Ensure all Docker-based services are up and running."""

    docker_compose = DockerComposeExecutor(
        docker_compose_file,
        docker_compose_project_name,
        docker_compose_project_dir
    )

    # If we allowed to run without Docker, check it's presence
    if docker_allow_fallback is True:
        try:
            with open(os.devnull, 'w') as devnull:
                subprocess.call(['docker', 'ps'],
                                stdout=devnull, stderr=devnull)
        except Exception:
            yield Services(None, docker_allow_fallback=True)
            return

    project = project_from_options(
        docker_compose._compose_project_dir,
        options=docker_compose.as_dict_options()
    )
    cmd = TopLevelCommand(project)

    # Spawn containers.
    up_options = docker_compose.defaults_opts('up')
    up_options['-d'] = True
    up_options['--build'] = True
    cmd.up(up_options)

    # Let test(s) run.
    yield Services(project)

    # Clean up.
    down_option = docker_compose.defaults_opts('down')
    down_option['-v'] = True
    cmd.down(down_option)


__all__ = (
    'docker_compose_file',
    'docker_compose_project_dir',
    'docker_ip',
    'docker_services',
)
