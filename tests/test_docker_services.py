# -*- coding: utf-8 -*-


import os
import mock
import pytest

from compose.project import NoSuchService

from pytest_docker import (
    DockerComposeExecutor,
    docker_services,
    Services,
)


COMPOSE_FILE = os.path.join(os.path.dirname(__file__), 'docker-compose.yml')


def test_docker_services():
    """Automatic teardown of all services."""
    # The fixture is a context-manager.
    gen = docker_services(
        COMPOSE_FILE,
        docker_compose_project_name='pytest123',
        docker_allow_fallback=False,
        docker_compose_project_dir='.'
    )
    services = next(gen)

    # check that the hello service is started
    project = services._docker_compose
    assert len(project.get_services()) == 1

    service = project.get_service('hello')
    container = service.get_container()
    assert container.is_running
    assert container.name == 'pytest123_hello_1'

    # Can request port for services.
    port = services.port_for('hello', 80)
    assert port == 32770

    # Next yield is last.
    with pytest.raises(StopIteration):
        print(next(gen))

    with pytest.raises(ValueError):
        service.get_container()


def test_docker_services_unused_port():
    """Complain loudly when the requested port is not used by the service."""
    gen = docker_services(
        COMPOSE_FILE,
        docker_compose_project_name='pytest123',
        docker_allow_fallback=False,
        docker_compose_project_dir='.'
    )
    services = next(gen)

    # Can request port for services.
    with pytest.raises(NoSuchService) as exc:
        print(services.port_for('abc', 123))
    assert str(exc.value) == 'No such service: abc'

    with pytest.raises(ValueError) as exc:
        print(services.port_for('hello', 123))
    assert str(exc.value) == 'Could not detect port for "hello:123".'

    # Next yield is last.
    with pytest.raises(StopIteration):
        print(next(gen))


def test_docker_services_failure():
    """Propagate failure to start service."""
    # The fixture is a context-manager.
    gen = docker_services(
        'compose.yml',
        docker_compose_project_name='pytest123',
        docker_allow_fallback=False,
        docker_compose_project_dir='.'
    )

    # Failure propagates with improved diagnostics.
    with pytest.raises(Exception) as exc:
        print(next(gen))
    assert "[Errno 2] No such file or directory: " in str(exc.value)


def test_wait_until_responsive_timeout():
    clock = mock.MagicMock()
    clock.side_effect = [0.0, 1.0, 2.0, 3.0]

    with mock.patch('time.sleep') as sleep:
        docker_compose = DockerComposeExecutor(
            compose_files=COMPOSE_FILE,
            compose_project_name="pytest123",
            compose_project_dir='.')
        services = Services(docker_compose)
        with pytest.raises(Exception) as exc:
            print(services.wait_until_responsive(
                check=lambda: False,
                timeout=3.0,
                pause=1.0,
                clock=clock,
            ))
        assert sleep.call_args_list == [
            mock.call(1.0),
            mock.call(1.0),
            mock.call(1.0),
        ]
    assert str(exc.value) == (
        'Timeout reached while waiting on service!'
    )


def test_get_port_docker_allow_fallback_docker_online():

    with mock.patch('subprocess.call') as check_output:
        check_output.side_effect = [b'']

        assert check_output.call_count == 0

        # The fixture is a context-manager.
        gen = docker_services(
            COMPOSE_FILE,
            docker_compose_project_name='pytest123',
            docker_allow_fallback=True,
            docker_compose_project_dir='.'
        )
        services = next(gen)
        assert isinstance(services, Services)

        assert check_output.call_count == 1

        # Can request port for services.
        port = services.port_for('hello', 80)
        assert port == 32770

        # Next yield is last.
        with pytest.raises(StopIteration):
            print(next(gen))


def test_get_port_docker_allow_fallback_docker_offline():

    with mock.patch('subprocess.call') as check_output:
        check_output.side_effect = [Exception('')]

        assert check_output.call_count == 0

        # The fixture is a context-manager.
        gen = docker_services(
            COMPOSE_FILE,
            docker_compose_project_name='pytest123',
            docker_allow_fallback=True,
            docker_compose_project_dir='.'
        )
        services = next(gen)
        assert isinstance(services, Services)

        assert check_output.call_count == 1

        # Can request port for services.
        port = services.port_for('hello', 80)
        assert port == 80

        # Next yield is last.
        with pytest.raises(StopIteration):
            print(next(gen))
