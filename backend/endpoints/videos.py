import os
from typing import Annotated

from fastapi import Body, File, HTTPException
from fastapi import Path as PathVar
from fastapi import Request, UploadFile, status
from fastapi.responses import FileResponse, Response

from decorators.auth import protected_route
from endpoints.responses.assets import VideoSchema
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from handler.asset_store import remove_video, store_screenshot, store_video
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_rom_visible
from handler.database import db_rom_handler, db_screenshot_handler, db_video_handler
from handler.filesystem import fs_asset_handler
from handler.filesystem.assets_handler import build_video_file_response
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import Video
from utils.media_types import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    is_allowed_image_file,
    is_allowed_video_file,
)
from utils.router import APIRouter
from utils.uploads import check_asset_upload_size, sanitize_asset_filename

router = APIRouter(
    prefix="/videos",
    tags=["videos"],
)

VIDEO_FILE_UPLOAD = File(..., description="Video file to upload.")
VIDEO_POSTER_UPLOAD = File(
    default=None,
    description="Poster image shown before the video plays.",
)


def _owned_video_or_404(id: int, user_id: int) -> Video:
    video = db_video_handler.get_video_by_id(id)
    if not video or video.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )
    return video


def _poster_filename(video_filename: str, poster: UploadFile) -> str:
    """The video's name plus the poster's extension, so `Video.screenshot`
    finds it by stem without colliding with a gallery screenshot."""
    ext = os.path.splitext(poster.filename or "")[1]
    poster_filename = sanitize_asset_filename(f"{video_filename}{ext}", "poster")
    if not is_allowed_image_file(poster_filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported poster image type. Allowed: "
                f"{', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}"
            ),
        )
    return poster_filename


@protected_route(router.post, "", [Scope.ASSETS_WRITE])
async def add_video(
    request: Request,
    rom_id: int,
    videoFile: UploadFile = VIDEO_FILE_UPLOAD,
    screenshotFile: UploadFile | None = VIDEO_POSTER_UPLOAD,
) -> VideoSchema:
    """Upload a per-user gallery video for a ROM, optionally with a poster.

    Stored under the user's asset folder and private until the owner shares
    it. Uploading under an existing name replaces that video.
    """
    check_asset_upload_size(videoFile, "Video file")
    check_asset_upload_size(screenshotFile, "Poster file")

    rom = db_rom_handler.get_rom(id=rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)

    assert_rom_visible(request, rom)

    if not videoFile.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video file has no filename",
        )

    video_filename = sanitize_asset_filename(videoFile.filename, "video")
    if not is_allowed_video_file(video_filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported video file type. Allowed: "
                f"{', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}"
            ),
        )
    poster_filename = (
        _poster_filename(video_filename, screenshotFile)
        if screenshotFile and screenshotFile.filename
        else ""
    )

    log.info(f"Uploading video {hl(video_filename)} to {hl(str(rom.name), color=BLUE)}")

    db_video = await store_video(request.user, rom, videoFile, video_filename)

    if screenshotFile and poster_filename:
        poster = await store_screenshot(
            request.user, rom, screenshotFile, poster_filename
        )
        if poster.is_public != db_video.is_public:
            db_screenshot_handler.update_screenshot(
                poster.id, {"is_public": db_video.is_public}
            )

    return VideoSchema.model_validate(db_video_handler.get_video_by_id(db_video.id))


@protected_route(
    router.get,
    "/{id}/content",
    [Scope.ASSETS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def download_video(
    request: Request,
    id: Annotated[int, PathVar(description="Video internal id.", ge=1)],
) -> FileResponse:
    """Stream a video. Owner can play any of their videos; everyone else only
    public ones."""
    video = db_video_handler.get_video_by_id(id)
    if not video or (video.user_id != request.user.id and not video.is_public):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    # Sharing must not override the hidden-ROM/platform policy.
    assert_rom_visible(request, video.rom, not_found_detail="Video not found")

    try:
        file_path = fs_asset_handler.validate_path(video.full_path)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        ) from None

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video file not found on disk",
        )

    return build_video_file_response(file_path, filename=video.file_name)


@protected_route(
    router.put,
    "/{id}",
    [Scope.ASSETS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def update_video(
    request: Request,
    id: Annotated[int, PathVar(description="Video internal id.", ge=1)],
    is_public: Annotated[bool, Body(embed=True)],
) -> VideoSchema:
    """Toggle a video's public/private visibility (owner only)."""
    video = _owned_video_or_404(id, request.user.id)

    updated = db_video_handler.update_video(id, {"is_public": is_public})

    # A shared video still shows its poster to other users.
    if video.screenshot and not video.screenshot.is_gallery:
        db_screenshot_handler.update_screenshot(
            video.screenshot.id, {"is_public": is_public}
        )

    return VideoSchema.model_validate(updated)


@protected_route(
    router.delete,
    "/{id}",
    [Scope.ASSETS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_video(
    request: Request,
    id: Annotated[int, PathVar(description="Video internal id.", ge=1)],
) -> Response:
    """Delete a video with its file and poster (owner only)."""
    video = _owned_video_or_404(id, request.user.id)

    await remove_video(video)
    log.info(f"Deleted video {hl(video.file_name)}")

    return Response()
