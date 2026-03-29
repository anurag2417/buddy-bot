"""
SQLAlchemy Models for BuddyBot
All tables for users, conversations, messages, alerts, child profiles, and browsing data
"""
from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database import Base
import uuid
from datetime import datetime, timezone


def generate_uuid():
    return str(uuid.uuid4())


def generate_user_id():
    return f"user_{uuid.uuid4().hex[:12]}"


def generate_child_id():
    return f"child_{uuid.uuid4().hex[:12]}"


class User(Base):
    __tablename__ = 'users'
    
    id = Column(String(50), primary_key=True, default=generate_user_id)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(50), default="")
    password_hash = Column(String(255), nullable=True)  # Null for Google auth users
    auth_provider = Column(String(50), default="email")  # "email" or "google"
    picture = Column(String(500), default="")
    role = Column(String(50), default="parent")
    extension_installed = Column(Boolean, default=False)  # Track if extension is installed
    extension_device_id = Column(String(100), nullable=True)  # Device ID from extension
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    children = relationship("ChildProfile", back_populates="parent", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")


class ChildProfile(Base):
    __tablename__ = 'child_profiles'
    
    id = Column(String(50), primary_key=True, default=generate_child_id)
    parent_id = Column(String(50), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    parent = relationship("User", back_populates="children")


class Conversation(Base):
    __tablename__ = 'conversations'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(50), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    child_id = Column(String(50), nullable=True, index=True)
    title = Column(String(255), default="New Chat")
    message_count = Column(Integer, default=0)
    has_flags = Column(Boolean, default=False)
    flag_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = 'messages'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    text = Column(Text, nullable=False)
    blocked = Column(Boolean, default=False)
    blocked_words = Column(JSON, nullable=True)
    flagged_topics = Column(JSON, nullable=True)
    thought = Column(Text, nullable=True)  # AI's internal reasoning
    safety_level = Column(String(20), nullable=True)  # SAFE, CAUTION, ALERT
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class Alert(Base):
    __tablename__ = 'alerts'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey('conversations.id', ondelete='SET NULL'), nullable=True, index=True)
    message_id = Column(String(36), nullable=True)
    device_id = Column(String(100), nullable=True, index=True)
    type = Column(String(50), nullable=False)  # "profanity", "restricted_topic", "browsing_alert"
    severity = Column(String(20), nullable=False)  # "high", "medium", "low"
    details = Column(Text, nullable=True)
    child_message = Column(Text, nullable=True)
    categories = Column(JSON, nullable=True)
    fuzzy_matched = Column(JSON, nullable=True)
    tab_type = Column(String(20), nullable=True)
    url = Column(String(2000), nullable=True)
    source = Column(String(50), nullable=True)  # "chat" or "extension"
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    conversation = relationship("Conversation", back_populates="alerts")


class BrowsingPacket(Base):
    __tablename__ = 'browsing_packets'
    
    id = Column(String(36), primary_key=True)
    device_id = Column(String(100), nullable=False, index=True)
    timestamp = Column(String(50), nullable=False)
    tab_type = Column(String(20), default="normal")  # "normal" or "incognito"
    url = Column(String(2000), nullable=False)
    domain = Column(String(255), nullable=False, index=True)
    title = Column(String(500), nullable=True)
    packet_type = Column(String(50), nullable=False)  # "search_query" or "url_visit"
    search_query = Column(String(1000), nullable=True)
    search_engine = Column(String(100), nullable=True)
    profanity_flagged = Column(Boolean, default=False)
    profanity_words = Column(JSON, nullable=True)
    profanity_categories = Column(JSON, nullable=True)
    fuzzy_matched = Column(JSON, nullable=True)
    restricted_topics = Column(JSON, nullable=True)
    synced_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
