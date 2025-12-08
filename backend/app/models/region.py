from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class Region(Base):
    __tablename__ = "dim_region"
    __table_args__ = (
        Index("idx_region_city_code", "city_code"),
        Index("idx_region_district_code", "district_code"),
        Index("idx_region_level", "level"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String, default="CN")
    province_code: Mapped[str] = mapped_column(String)
    city_code: Mapped[str] = mapped_column(String)
    district_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    level: Mapped[str] = mapped_column(String)
    parent_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    province_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    district_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    short_city_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city_tier: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city_cluster: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    gdp: Mapped[Optional[float]] = mapped_column(nullable=True)
    population: Mapped[Optional[float]] = mapped_column(nullable=True)
    gdp_per_capita: Mapped[Optional[float]] = mapped_column(nullable=True)
    stats_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    malls = relationship("Mall", back_populates="region")
    stores = relationship("Store", back_populates="region")
    business_areas = relationship("BusinessArea", back_populates="region")
