from __future__ import annotations
from sqlalchemy import (
    String,
    Integer,
    Date,
    Text,
    ForeignKey,
    DateTime,
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

class User(Base):
    __tablename__ = "user"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    display_name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="buyer")  # "buyer" or "seller"


class Listing(Base):
    __tablename__ = "listing"

    listing_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    issue_id: Mapped[int] = mapped_column(ForeignKey("issue.issue_id"))
    seller_id: Mapped[int] = mapped_column(ForeignKey("user.user_id"))

    grade_label: Mapped[str | None] = mapped_column(String)    # "CGC 9.6 Slabbed"
    condition_notes: Mapped[str | None] = mapped_column(Text)  # "Sharp corners, white pages"
    asking_price_cents: Mapped[int] = mapped_column(Integer)   # 120000 = $1200.00
    quantity_available: Mapped[int] = mapped_column(Integer, default=1)


class CartItem(Base):
    __tablename__ = "cart_item"

    cart_item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("user.user_id"))
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.listing_id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)


class Order(Base):
    __tablename__ = "order"

    order_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("user.user_id"))
    total_cents: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[DateTime | None] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(String, default="PLACED")  # later: PAID, SHIPPED, etc.


class OrderItem(Base):
    __tablename__ = "order_item"

    order_item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("order.order_id"))
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.listing_id"))

    issue_title: Mapped[str | None] = mapped_column(Text)
    issue_number: Mapped[str | None] = mapped_column(String)
    grade_label: Mapped[str | None] = mapped_column(String)
    price_cents: Mapped[int] = mapped_column(Integer)

class Publisher(Base):
    __tablename__ = "publisher"

    publisher_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    series: Mapped[list["Series"]] = relationship(back_populates="publisher")

class Series(Base):
    __tablename__ = "series"

    series_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    publisher_id: Mapped[int | None] = mapped_column(ForeignKey("publisher.publisher_id"))
    start_year: Mapped[int | None] = mapped_column(Integer)
    volume: Mapped[int | None] = mapped_column(Integer)

    # which external system did this series come from?
    source_key: Mapped[str | None] = mapped_column(Text)        # e.g. marvel series id
    source_system: Mapped[str | None] = mapped_column(Text)     # e.g. "marvel"

    publisher: Mapped["Publisher"] = relationship(back_populates="series")
    issues: Mapped[list["Issue"]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan"
    )

class Creator(Base):
    __tablename__ = "creator"

    creator_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)

class Issue(Base):
    __tablename__ = "issue"

    issue_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    series_id: Mapped[int] = mapped_column(ForeignKey("series.series_id"))

    # business identity
    issue_number: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)   # <- add this so we can show "Uncanny X-Men #266"

    # dates/pricing metadata
    release_date: Mapped[Date | None] = mapped_column(Date)  # <- rename of cover_date for clarity
    price_cents: Mapped[int | None] = mapped_column(Integer)
    isbn: Mapped[str | None] = mapped_column(Text)
    upc: Mapped[str | None] = mapped_column(Text)

    description: Mapped[str | None] = mapped_column(Text)

    # display
    cover_url: Mapped[str | None] = mapped_column(Text)  # <- we need this to render cover art

    series: Mapped["Series"] = relationship(back_populates="issues")

class IssueCreator(Base):
    __tablename__ = "issue_creator"

    issue_id: Mapped[int] = mapped_column(ForeignKey("issue.issue_id"), primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creator.creator_id"), primary_key=True)
    role: Mapped[str] = mapped_column(String, primary_key=True)

class EtlRun(Base):
    __tablename__ = "etl_run"

    run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_system: Mapped[str | None] = mapped_column(String)

    started_at: Mapped[DateTime | None] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)

    records_read: Mapped[int | None] = mapped_column(Integer)
    records_loaded: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)

from etl.db import get_engine

# Create tables if they don't exist yet
engine = get_engine()
Base.metadata.create_all(bind=engine)
