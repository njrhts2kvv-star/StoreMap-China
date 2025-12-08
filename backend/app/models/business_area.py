from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class BusinessArea(Base):
    __tablename__ = "business_area"
    __table_args__ = (
        Index("idx_business_area_city", "city_code"),
        Index("idx_business_area_district", "district_code"),
        Index("idx_business_area_name_city", "name", "city_code", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    amap_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    adcode: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    district_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    center_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    center_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    region_id: Mapped[Optional[int]] = mapped_column(ForeignKey("dim_region.id"), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    region = relationship("Region", back_populates="business_areas")
    stores = relationship("Store", back_populates="business_area")
    malls = relationship("Mall", back_populates="business_area")

