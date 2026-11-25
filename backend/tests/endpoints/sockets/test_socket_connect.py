from unittest.mock import AsyncMock, MagicMock

import pytest

from endpoints.sockets import logs
from handler.database import db_user_handler
from handler.socket_handler import SCAN_ROOM, socket_handler
from models.user import Role
from utils import auth as auth_utils


@pytest.fixture
def user(mocker):
    user = MagicMock(id=3, enabled=True, role=Role.USER)
    mocker.patch.object(db_user_handler, "get_user_by_username", return_value=user)
    return user


@pytest.fixture
def enter_room(mocker):
    mocker.patch.object(logs, "store_authenticated_user", AsyncMock())
    return mocker.patch.object(socket_handler.socket_server, "enter_room", AsyncMock())


@pytest.fixture
def bind(mocker):
    return mocker.patch.object(socket_handler, "bind_to_login_session", AsyncMock())


def _session(mocker, **session):
    mocker.patch.object(
        auth_utils, "get_session_from_environ", AsyncMock(return_value=session)
    )


async def test_ties_the_socket_to_its_login_session(mocker, user, enter_room, bind):
    _session(mocker, iss="romm:auth", sub="player", session_id="s1")

    await logs.connect("sid-1", {})

    enter_room.assert_awaited_once_with("sid-1", "user:3")
    bind.assert_awaited_once_with("sid-1", "s1")


@pytest.mark.parametrize("logs_disabled", [False, True])
async def test_an_admin_joins_the_scan_room(
    mocker, user, enter_room, bind, logs_disabled
):
    user.role = Role.ADMIN
    mocker.patch.object(logs, "DISABLE_LOGS_VIEWER", logs_disabled)
    _session(mocker, iss="romm:auth", sub="admin", session_id="s1")

    await logs.connect("sid-1", {})

    rooms = [call.args[1] for call in enter_room.await_args_list]
    assert rooms == ["user:3", SCAN_ROOM] + ([] if logs_disabled else [logs.ADMIN_ROOM])


async def test_an_anonymous_socket_joins_no_room(mocker, user, enter_room, bind):
    _session(mocker)

    await logs.connect("sid-1", {})

    enter_room.assert_not_awaited()


async def test_an_anonymous_socket_is_tied_to_nothing(mocker, user, enter_room, bind):
    _session(mocker)

    await logs.connect("sid-1", {})

    bind.assert_not_awaited()


async def test_disconnect_undoes_the_binding_and_the_activity(mocker):
    unbind = mocker.patch.object(
        socket_handler, "unbind_from_login_session", AsyncMock()
    )
    clear_activity = mocker.patch.object(logs, "activity_on_disconnect", AsyncMock())

    await logs.disconnect("sid-1")

    unbind.assert_awaited_once_with("sid-1")
    clear_activity.assert_awaited_once_with("sid-1")


def test_one_disconnect_handler_serves_the_whole_server():
    # A second registration would silently replace this one.
    assert socket_handler.socket_server.handlers["/"]["disconnect"] is logs.disconnect
