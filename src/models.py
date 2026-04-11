from typing import Optional, List
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    BigInteger, String, Integer, Text, ForeignKey, TIMESTAMP, 
    Boolean, Enum, ARRAY, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from .database import Base

class SessionStatus(str, PyEnum):
    PROPOSED = "PROPOSED"
    SCHEDULED = "SCHEDULED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"

class RSVPStatus(str, PyEnum):
    YES = "YES"
    MAYBE = "MAYBE"
    NO = "NO"

class ReminderStatus(str, PyEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"

class GuildConfig(Base):
    __tablename__ = "guild_configs"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    admin_role_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    organizer_role_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    player_role_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    default_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    default_timezone: Mapped[str] = mapped_column(String, default="UTC")

class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(50)) # Unique per guild? Composite index needed
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dm_id: Mapped[int] = mapped_column(BigInteger)
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    role_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    default_reminders: Mapped[Optional[str]] = mapped_column(String, default="24h, 1h") # Comma separated list of relative times

    sessions: Mapped[List["Session"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Store options as related table or JSON? Related table is cleaner for voting
    selected_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.PROPOSED)
    quorum: Mapped[int] = mapped_column(Integer, default=3)
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True) # If specifically overridden
    reminders_config: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Override default
    
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    campaign: Mapped["Campaign"] = relationship(back_populates="sessions")
    options: Mapped[List["SessionOption"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    rsvps: Mapped[List["SessionRSVP"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    reminders: Mapped[List["ReminderJob"]] = relationship(back_populates="session", cascade="all, delete-orphan")

class SessionOption(Base):
    __tablename__ = "session_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    start_time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    
    session: Mapped["Session"] = relationship(back_populates="options")
    # RSVPs might link here too if we want per-option voting

class SessionRSVP(Base):
    __tablename__ = "session_rsvps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    user_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[RSVPStatus] = mapped_column(Enum(RSVPStatus))
    
    # If voting for a specific option (e.g. "I can make option A but not B")
    # For MVP, maybe just "Yes" means "Any proposed time" or we only allow one proposal at a time?
    # User requirement says "times as ...", implying multiple.
    # Complex multi-time voting needs a robust model.
    # Let's add option_id. If null, it applies to the 'selected_time' or general availability?
    # Actually, standard D&D bots often do: "Here are 3 times, vote for which ones you can make".
    # So RSVP creates a link between User and Option.
    # For simplicity in this MVP + specific requirement "RSVP buttons: Yes/Maybe/No", 
    # usually this implies a single time proposal per "Session" object, OR the View has a dropdown?
    # Let's assume 1 Session = 1 Event. If they want to poll for times, that might be a different flow.
    # Wait, "/session propose ... times as '...'" implies multiple.
    # So we probably need to Vote ON OPTIONS.
    # But later "RSVP buttons: Yes/Maybe/No" suggests a simple global RSVP.
    # I will support multiple options, but maybe the RSVP is per-session for now if it's "Selected",
    # or per-option if "Proposed".
    # Let's add `option_id` to RSVP to be safe.
    
    option_id: Mapped[Optional[int]] = mapped_column(ForeignKey("session_options.id"), nullable=True)
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    session: Mapped["Session"] = relationship(back_populates="rsvps")
    option: Mapped[Optional["SessionOption"]] = relationship()

class ReminderJob(Base):
    __tablename__ = "reminder_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    remind_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    status: Mapped[ReminderStatus] = mapped_column(Enum(ReminderStatus), default=ReminderStatus.PENDING)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text)
    
    session: Mapped["Session"] = relationship(back_populates="reminders")

class UserConfig(Base):
    __tablename__ = "user_configs"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timezone: Mapped[str] = mapped_column(String, default="UTC")
