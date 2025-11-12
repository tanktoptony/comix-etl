from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    String,
    Integer,
    Date,
    Text,
    ForeignKey,
    DateTime,
    Boolean,
    BigInteger,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


# --- Core User ---

class User(Base):
    __tablename__ = "user"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)

    # "COLLECTOR" or "SELLER" – better than buyer/seller for your pitch
    role: Mapped[str] = mapped_column(String, default="COLLECTOR")

    # Relationships for library flows
    collections: Mapped[list["CollectionItem"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    wishlists: Mapped[list["WishlistItem"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


# --- Publisher / Series ---

class Publisher(Base):
    __tablename__ = "publisher"

    publisher_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    series: Mapped[list["Series"]] = relationship(back_populates="publisher")


class Series(Base):
    __tablename__ = "series"

    series_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)

    publisher_id: Mapped[Optional[int]] = mapped_column(ForeignKey("publisher.publisher_id"))
    start_year: Mapped[Optional[int]] = mapped_column(Integer)
    volume: Mapped[Optional[int]] = mapped_column(Integer)

    # external source linkage (e.g. Marvel series id)
    source_key: Mapped[Optional[str]] = mapped_column(Text)
    source_system: Mapped[Optional[str]] = mapped_column(Text)

    publisher: Mapped[Optional["Publisher"]] = relationship(back_populates="series")
    issues: Mapped[list["Issue"]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
    )

# --- Issue (enhanced for Marvel + UI) ---

class Issue(Base):
    __tablename__ = "issue"

    issue_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    series_id: Mapped[int] = mapped_column(ForeignKey("series.series_id"), nullable=False)

    # business identity
    issue_number: Mapped[Optional[str]] = mapped_column(Text)
    title: Mapped[Optional[str]] = mapped_column(Text)   # e.g. "Uncanny X-Men #266"

    # dates / pricing metadata
    release_date: Mapped[Optional[date]] = mapped_column(Date)      # display date
    price_cents: Mapped[Optional[int]] = mapped_column(Integer)
    isbn: Mapped[Optional[str]] = mapped_column(Text)
    upc: Mapped[Optional[str]] = mapped_column(Text)

    description: Mapped[Optional[str]] = mapped_column(Text)

    # display
    cover_url: Mapped[Optional[str]] = mapped_column(Text)

    # Marvel / external linkage
    marvel_series_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    marvel_comic_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, index=True)

    # richer metadata for browsing / variants
    onsale_date: Mapped[Optional[date]] = mapped_column(Date)
    is_variant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    variant_name: Mapped[Optional[str]] = mapped_column(Text)
    issue_order: Mapped[Optional[int]] = mapped_column(Integer)  # stable ordering within series

    series: Mapped["Series"] = relationship(back_populates="issues")

    # reverse relationships for collection/wishlist
    collections: Mapped[list["CollectionItem"]] = relationship(back_populates="issue")
    wishlists: Mapped[list["WishlistItem"]] = relationship(back_populates="issue")


# --- Collection & Wishlist ---

class CollectionItem(Base):
    __tablename__ = "collection_item"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.user_id"), primary_key=True
    )
    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issue.issue_id"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="collections")
    issue: Mapped["Issue"] = relationship(back_populates="collections")


class WishlistItem(Base):
    __tablename__ = "wishlist_item"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.user_id"), primary_key=True
    )
    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issue.issue_id"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="wishlists")
    issue: Mapped["Issue"] = relationship(back_populates="wishlists")


# --- Bootstrapping (keep for now; can move to a db module later) ---

from etl.db import get_engine  # if this is legacy, we can replace with a simple get_engine

engine = get_engine()
Base.metadata.create_all(bind=engine)
