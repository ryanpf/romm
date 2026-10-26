"""Add the videos table for per-user gallery videos

Revision ID: 0155_user_videos
Revises: 0154_ownerless_own_only
Create Date: 2026-10-26 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0155_user_videos"
down_revision = "0154_ownerless_own_only"
branch_labels = None
depends_on = None

# MariaDB and MySQL index foreign keys implicitly; PostgreSQL does not.
USER_ID_INDEX = "ix_videos_user_id"


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_name", sa.String(length=450), nullable=False),
        sa.Column("file_name_no_tags", sa.String(length=450), nullable=False),
        sa.Column("file_name_no_ext", sa.String(length=450), nullable=False),
        sa.Column("file_extension", sa.String(length=100), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "missing_from_fs",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_videos_rom_user", "videos", ["rom_id", "user_id"], if_not_exists=True
    )
    op.create_index("idx_videos_public", "videos", ["is_public"], if_not_exists=True)
    if is_postgresql(op.get_bind()):
        op.create_index(USER_ID_INDEX, "videos", ["user_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_table("videos", if_exists=True)
