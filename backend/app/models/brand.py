from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class Brand(Base):
    __tablename__ = "brand"
    __table_args__ = (Index("idx_brand_slug", "slug", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String, unique=True)
    name_cn: Mapped[str] = mapped_column(String)
    name_en: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tier: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    country_of_origin: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    official_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    store_locator_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    coord_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    data_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    stores = relationship("Store", back_populates="brand")
