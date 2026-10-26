from io import BytesIO

import pytest
from fastapi import status
from tests.factories import make_screenshot, make_video

from handler.database import db_screenshot_handler, db_video_handler
from handler.database.base_handler import sync_session
from models.assets import Video
from models.permission import HiddenEntity, PermEntity
from models.platform import Platform
from models.rom import Rom
from models.user import User

pytestmark = pytest.mark.usefixtures("_isolated_assets_dir")

VIDEO_BYTES = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 4


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _hide(entity: PermEntity, entity_id: int, user_id: int) -> None:
    with sync_session.begin() as s:
        s.add(HiddenEntity(entity=entity, entity_id=entity_id, user_id=user_id))


def _upload(client, token: str, rom: Rom, *, poster: bool = False, name="clip.mp4"):
    files = {"videoFile": (name, BytesIO(VIDEO_BYTES), "video/mp4")}
    if poster:
        files["screenshotFile"] = ("poster.jpg", BytesIO(b"\xff\xd8jpeg"), "image/jpeg")
    return client.post(
        f"/api/videos?rom_id={rom.id}", files=files, headers=_auth(token)
    )


def _stored_video(rom: Rom, user: User, name: str = "clip.mp4", **overrides) -> Video:
    """A video row with its file on disk, where the upload route would put it."""
    from handler.filesystem import fs_asset_handler

    video = make_video(
        rom,
        user,
        name,
        file_path=fs_asset_handler.build_videos_file_path(
            user=user, platform_fs_slug=rom.platform_slug, rom_id=rom.id
        ),
        file_size_bytes=len(VIDEO_BYTES),
        **overrides,
    )
    path = fs_asset_handler.base_path / video.full_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(VIDEO_BYTES)
    return video


# ---------- POST /api/videos ----------


def test_upload_video_is_private(client, access_token: str, rom: Rom, admin_user: User):
    response = _upload(client, access_token, rom)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["file_name"] == "clip.mp4"
    assert data["file_size_bytes"] == len(VIDEO_BYTES)
    assert data["is_public"] is False
    assert data["screenshot"] is None
    assert data["file_path"].endswith(f"/videos/{rom.platform_slug}/{rom.id}")


def test_upload_with_poster_binds_it_by_stem(client, access_token: str, rom: Rom):
    response = _upload(client, access_token, rom, poster=True)

    assert response.status_code == status.HTTP_200_OK
    poster = response.json()["screenshot"]
    assert poster["file_name"] == "clip.mp4.jpg"
    # A poster is not a gallery screenshot of its own.
    assert poster["is_gallery"] is False


def test_upload_under_the_same_name_replaces_the_video(
    client, access_token: str, rom: Rom, admin_user: User
):
    first = _upload(client, access_token, rom).json()
    second = _upload(client, access_token, rom, poster=True).json()

    assert second["id"] == first["id"]
    assert second["screenshot"] is not None
    assert len(db_video_handler.get_rom_gallery_videos(rom.id, admin_user.id)) == 1


def test_upload_rejects_a_non_video(client, access_token: str, rom: Rom):
    response = _upload(client, access_token, rom, name="clip.exe")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unsupported video file type" in response.json()["detail"]


def test_upload_rejects_a_non_image_poster(client, access_token: str, rom: Rom):
    response = client.post(
        f"/api/videos?rom_id={rom.id}",
        files={
            "videoFile": ("clip.mp4", BytesIO(VIDEO_BYTES), "video/mp4"),
            "screenshotFile": ("poster.html", BytesIO(b"<script>"), "text/html"),
        },
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert db_video_handler.get_rom_gallery_videos(rom.id, 0) == []


def test_hidden_rom_masks_video_upload(
    client, viewer_access_token: str, viewer_user: User, rom: Rom
):
    _hide(PermEntity.ROMS, rom.id, viewer_user.id)

    response = _upload(client, viewer_access_token, rom)

    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------- GET /api/videos/{id}/content ----------


def test_owner_streams_own_video_inline(
    client, access_token: str, admin_user: User, rom: Rom
):
    video = _stored_video(rom, admin_user)

    response = client.get(
        f"/api/videos/{video.id}/content", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.content == VIDEO_BYTES
    assert response.headers["content-type"] == "video/mp4"
    assert response.headers["content-disposition"].startswith("inline")
    assert response.headers["x-content-type-options"] == "nosniff"


def test_video_content_answers_range_requests(
    client, access_token: str, admin_user: User, rom: Rom
):
    video = _stored_video(rom, admin_user)

    response = client.get(
        f"/api/videos/{video.id}/content",
        headers={**_auth(access_token), "Range": "bytes=100-199"},
    )

    assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
    assert response.content == VIDEO_BYTES[100:200]


def test_other_user_cannot_stream_private_video(
    client, viewer_access_token: str, admin_user: User, rom: Rom
):
    video = _stored_video(rom, admin_user)

    response = client.get(
        f"/api/videos/{video.id}/content", headers=_auth(viewer_access_token)
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_other_user_streams_public_video(
    client, viewer_access_token: str, admin_user: User, rom: Rom
):
    video = _stored_video(rom, admin_user, is_public=True)

    response = client.get(
        f"/api/videos/{video.id}/content", headers=_auth(viewer_access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.content == VIDEO_BYTES


def test_hidden_platform_masks_public_video(
    client,
    viewer_access_token: str,
    viewer_user: User,
    admin_user: User,
    rom: Rom,
    platform: Platform,
):
    video = _stored_video(rom, admin_user, is_public=True)
    _hide(PermEntity.PLATFORMS, platform.id, viewer_user.id)

    response = client.get(
        f"/api/videos/{video.id}/content", headers=_auth(viewer_access_token)
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_video_missing_on_disk_is_404(
    client, access_token: str, admin_user: User, rom: Rom
):
    video = make_video(rom, admin_user, "gone.mp4", file_size_bytes=1)

    response = client.get(
        f"/api/videos/{video.id}/content", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------- PUT /api/videos/{id} ----------


def test_sharing_a_video_shares_its_poster(client, access_token: str, rom: Rom):
    uploaded = _upload(client, access_token, rom, poster=True).json()

    response = client.put(
        f"/api/videos/{uploaded['id']}",
        json={"is_public": True},
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["is_public"] is True
    poster = db_screenshot_handler.get_screenshot_by_id(uploaded["screenshot"]["id"])
    assert poster is not None and poster.is_public is True


def test_update_visibility_other_user_returns_404(
    client, access_token: str, rom: Rom, editor_user: User
):
    others = make_video(rom, editor_user, "other.mp4", file_size_bytes=1)

    response = client.put(
        f"/api/videos/{others.id}",
        json={"is_public": True},
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------- DELETE /api/videos/{id} ----------


def test_delete_video_removes_file_and_poster(
    client, access_token: str, rom: Rom, _isolated_assets_dir
):
    uploaded = _upload(client, access_token, rom, poster=True).json()
    video_file = _isolated_assets_dir / uploaded["full_path"]
    assert video_file.is_file()

    response = client.delete(
        f"/api/videos/{uploaded['id']}", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert db_video_handler.get_video_by_id(uploaded["id"]) is None
    assert (
        db_screenshot_handler.get_screenshot_by_id(uploaded["screenshot"]["id"]) is None
    )
    assert not video_file.exists()


def test_delete_keeps_a_gallery_screenshot_sharing_the_stem(
    client, access_token: str, rom: Rom, admin_user: User
):
    gallery = make_screenshot(
        rom, admin_user, "clip.mp4.png", file_size_bytes=1, is_gallery=True
    )
    video = _stored_video(rom, admin_user)

    client.delete(f"/api/videos/{video.id}", headers=_auth(access_token))

    assert db_screenshot_handler.get_screenshot_by_id(gallery.id) is not None


def test_delete_video_other_user_returns_404(
    client, access_token: str, rom: Rom, editor_user: User
):
    others = make_video(rom, editor_user, "other.mp4", file_size_bytes=1)

    response = client.delete(f"/api/videos/{others.id}", headers=_auth(access_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert db_video_handler.get_video_by_id(others.id) is not None


# ---------- GET /api/roms/{id} ----------


def test_rom_lists_own_and_others_public_videos(
    client, access_token: str, rom: Rom, admin_user: User, editor_user: User
):
    mine = make_video(rom, admin_user, "mine.mp4", file_size_bytes=1)
    public = make_video(rom, editor_user, "pub.mp4", file_size_bytes=1, is_public=True)
    make_video(rom, editor_user, "priv.mp4", file_size_bytes=1)

    data = client.get(f"/api/roms/{rom.id}", headers=_auth(access_token)).json()

    assert [v["id"] for v in data["user_videos"]] == [mine.id]
    community = {v["id"]: v for v in data["all_user_videos"]}
    assert set(community) == {mine.id, public.id}
    assert community[public.id]["username"] == editor_user.username
    assert community[mine.id]["download_path"].startswith(
        f"/api/videos/{mine.id}/content"
    )
