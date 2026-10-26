from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from decorators.database import INJECTED_SESSION, begin_session
from models.assets import Video
from models.base import with_file_name_parts

from .base_handler import DBBaseHandler


class DBVideosHandler(DBBaseHandler):
    @begin_session
    def add_video(
        self,
        video: Video,
        session: Session = INJECTED_SESSION,
    ) -> Video:
        return session.merge(video)

    @begin_session
    def get_video(
        self,
        *,
        rom_id: int,
        user_id: int,
        file_name: str,
        session: Session = INJECTED_SESSION,
    ) -> Video | None:
        return session.scalars(
            select(Video)
            .filter_by(rom_id=rom_id, user_id=user_id, file_name=file_name)
            .limit(1)
        ).first()

    @begin_session
    def get_video_by_id(
        self,
        id: int,
        session: Session = INJECTED_SESSION,
    ) -> Video | None:
        return session.get(Video, id)

    @begin_session
    def get_rom_gallery_videos(
        self,
        rom_id: int,
        user_id: int,
        session: Session = INJECTED_SESSION,
    ) -> Sequence[Video]:
        """A ROM's videos the user sees: their own plus other users' public ones."""
        return session.scalars(
            select(Video)
            .filter(
                Video.rom_id == rom_id,
                or_(Video.user_id == user_id, Video.is_public),
            )
            .order_by(Video.created_at.desc())
        ).all()

    @begin_session
    def update_video(
        self,
        id: int,
        data: dict[str, Any],
        session: Session = INJECTED_SESSION,
    ) -> Video:
        session.execute(
            update(Video)
            .where(Video.id == id)
            .values(**with_file_name_parts(data))
            .execution_options(synchronize_session="evaluate")
        )
        return session.scalars(select(Video).filter_by(id=id)).one()

    @begin_session
    def delete_video(
        self,
        id: int,
        session: Session = INJECTED_SESSION,
    ) -> None:
        session.execute(
            delete(Video)
            .where(Video.id == id)
            .execution_options(synchronize_session="evaluate")
        )
