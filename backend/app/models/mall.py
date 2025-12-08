from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class Mall(Base):
    __tablename__ = "mall"
    __table_args__ = (
        Index("idx_mall_code", "mall_code", unique=True),
        Index("idx_mall_city", "city_code"),
        Index("idx_mall_region", "region_id"),
        Index("idx_mall_business_area", "business_area_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mall_code: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String)
    original_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    region_id: Mapped[Optional[int]] = mapped_column(ForeignKey("dim_region.id"), nullable=True)
    business_area_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("business_area.id"),
        nullable=True,
    )
    province_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    district_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    amap_poi_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mall_category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mall_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    store_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    region = relationship("Region", back_populates="malls")
    stores = relationship("Store", back_populates="mall")
    business_area = relationship("BusinessArea", back_populates="malls")
