"""`HIDE_NEW_ROMS_FROM_GROUPS` hides ROMs as they are added."""

from collections.abc import Iterator

import pytest
from tests.factories import make_rom

from handler.database import db_permission_handler, db_rom_handler
from handler.database import roms_handler as roms_handler_module
from handler.database.base_handler import sync_session
from models.permission import HiddenEntity, PermEntity, PermissionGroup
from models.platform import Platform


@pytest.fixture
def group_id(monkeypatch) -> Iterator[int]:
    with sync_session.begin() as session:
        group = PermissionGroup(name="Kids")
        session.add(group)
        session.flush()
        id_ = group.id
    monkeypatch.setattr(
        roms_handler_module, "HIDE_NEW_ROMS_FROM_GROUPS", frozenset({"Kids"})
    )
    yield id_
    with sync_session.begin() as session:
        session.query(HiddenEntity).filter_by(group_id=id_).delete()
        session.query(PermissionGroup).filter_by(id=id_).delete()


def _hidden(group_id: int) -> set[int]:
    return db_permission_handler.get_hidden_entity_ids(PermEntity.ROMS, None, group_id)


def test_a_new_rom_is_hidden(platform: Platform, group_id: int):
    rom = make_rom(platform, "new")

    assert _hidden(group_id) == {rom.id}


def test_a_rescan_does_not_hide_it_again(platform: Platform, group_id: int):
    rom = make_rom(platform, "new")
    db_permission_handler.remove_hidden_entity(
        PermEntity.ROMS, rom.id, group_id=group_id
    )

    db_rom_handler.add_rom(rom)  # noqa: TID251

    assert _hidden(group_id) == set()


def test_other_groups_are_untouched(platform: Platform, group_id: int):
    default_id = db_permission_handler.get_default_group_id()
    assert default_id is not None

    rom = make_rom(platform, "new")

    assert rom.id not in _hidden(default_id)


def test_an_unknown_group_does_not_stop_the_scan(
    platform: Platform, group_id: int, monkeypatch
):
    monkeypatch.setattr(
        roms_handler_module, "HIDE_NEW_ROMS_FROM_GROUPS", frozenset({"Kids", "Gone"})
    )

    rom = make_rom(platform, "new")

    assert _hidden(group_id) == {rom.id}


def test_off_by_default(platform: Platform, group_id: int, monkeypatch):
    monkeypatch.setattr(roms_handler_module, "HIDE_NEW_ROMS_FROM_GROUPS", frozenset())

    make_rom(platform, "new")

    assert _hidden(group_id) == set()
