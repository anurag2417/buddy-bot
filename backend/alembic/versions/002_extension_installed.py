"""Add extension_installed to users

Revision ID: 002_extension_installed
Revises: 001_initial
Create Date: 2026-03-29
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_extension_installed'
down_revision: Union[str, Sequence[str], None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add extension tracking columns to users table."""
    op.add_column('users', sa.Column('extension_installed', sa.Boolean(), nullable=True, default=False))
    op.add_column('users', sa.Column('extension_device_id', sa.String(length=100), nullable=True))
    
    # Set default value for existing rows
    op.execute("UPDATE users SET extension_installed = false WHERE extension_installed IS NULL")


def downgrade() -> None:
    """Remove extension tracking columns."""
    op.drop_column('users', 'extension_device_id')
    op.drop_column('users', 'extension_installed')
