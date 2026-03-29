"""Initial schema - fresh start

Revision ID: 001_initial
Revises: 
Create Date: 2026-03-29
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables from scratch."""
    
    # Drop existing tables if they exist (fresh start)
    op.execute("DROP TABLE IF EXISTS chats CASCADE")
    op.execute("DROP TABLE IF EXISTS messages CASCADE")
    op.execute("DROP TABLE IF EXISTS alerts CASCADE")
    op.execute("DROP TABLE IF EXISTS conversations CASCADE")
    op.execute("DROP TABLE IF EXISTS child_profiles CASCADE")
    op.execute("DROP TABLE IF EXISTS browsing_packets CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True, default=""),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('auth_provider', sa.String(length=50), nullable=True, default="email"),
        sa.Column('picture', sa.String(length=500), nullable=True, default=""),
        sa.Column('role', sa.String(length=50), nullable=True, default="parent"),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    
    # Create child_profiles table
    op.create_table('child_profiles',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('parent_id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_child_profiles_parent_id', 'child_profiles', ['parent_id'], unique=False)
    
    # Create conversations table
    op.create_table('conversations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('child_id', sa.String(length=50), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True, default="New Chat"),
        sa.Column('message_count', sa.Integer(), nullable=True, default=0),
        sa.Column('has_flags', sa.Boolean(), nullable=True, default=False),
        sa.Column('flag_count', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversations_user_id', 'conversations', ['user_id'], unique=False)
    op.create_index('ix_conversations_child_id', 'conversations', ['child_id'], unique=False)
    
    # Create messages table
    op.create_table('messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('conversation_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('blocked', sa.Boolean(), nullable=True, default=False),
        sa.Column('blocked_words', sa.JSON(), nullable=True),
        sa.Column('flagged_topics', sa.JSON(), nullable=True),
        sa.Column('thought', sa.Text(), nullable=True),
        sa.Column('safety_level', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_messages_conversation_id', 'messages', ['conversation_id'], unique=False)
    
    # Create alerts table
    op.create_table('alerts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('conversation_id', sa.String(length=36), nullable=True),
        sa.Column('message_id', sa.String(length=36), nullable=True),
        sa.Column('device_id', sa.String(length=100), nullable=True),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('child_message', sa.Text(), nullable=True),
        sa.Column('categories', sa.JSON(), nullable=True),
        sa.Column('fuzzy_matched', sa.JSON(), nullable=True),
        sa.Column('tab_type', sa.String(length=20), nullable=True),
        sa.Column('url', sa.String(length=2000), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=True, default=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alerts_conversation_id', 'alerts', ['conversation_id'], unique=False)
    op.create_index('ix_alerts_device_id', 'alerts', ['device_id'], unique=False)
    
    # Create browsing_packets table
    op.create_table('browsing_packets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('device_id', sa.String(length=100), nullable=False),
        sa.Column('timestamp', sa.String(length=50), nullable=False),
        sa.Column('tab_type', sa.String(length=20), nullable=True, default="normal"),
        sa.Column('url', sa.String(length=2000), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('packet_type', sa.String(length=50), nullable=False),
        sa.Column('search_query', sa.String(length=1000), nullable=True),
        sa.Column('search_engine', sa.String(length=100), nullable=True),
        sa.Column('profanity_flagged', sa.Boolean(), nullable=True, default=False),
        sa.Column('profanity_words', sa.JSON(), nullable=True),
        sa.Column('profanity_categories', sa.JSON(), nullable=True),
        sa.Column('fuzzy_matched', sa.JSON(), nullable=True),
        sa.Column('restricted_topics', sa.JSON(), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_browsing_packets_device_id', 'browsing_packets', ['device_id'], unique=False)
    op.create_index('ix_browsing_packets_domain', 'browsing_packets', ['domain'], unique=False)


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('browsing_packets')
    op.drop_table('alerts')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('child_profiles')
    op.drop_table('users')
