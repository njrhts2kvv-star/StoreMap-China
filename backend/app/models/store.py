from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class Store(Base):
    __tablename__ = "store"
    __table_args__ = (
        Index("idx_store_brand", "brand_id"),
        Index("idx_store_mall", "mall_id"),
        Index("idx_store_region", "region_id"),
        Index("idx_store_business_area", "business_area_id"),
        Index("idx_store_city", "city_code"),
        Index("idx_store_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brand.id"))
    brand_slug: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mall_id: Mapped[Optional[int]] = mapped_column(ForeignKey("mall.id"), nullable=True)
    business_area_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("business_area.id"),
        nullable=True,
    )
    external_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String)
    name_raw: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    address_raw: Mapped[Optional[str]] = mapped_column(String)
    address_std: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    region_id: Mapped[Optional[int]] = mapped_column(ForeignKey("dim_region.id"), nullable=True)
    province_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    district_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    coord_system: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    coord_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    store_type_raw: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    store_type_std: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_street_store: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="open")
    opened_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    closed_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_crawl_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    business_hours: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    raw_source: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    brand = relationship("Brand", back_populates="stores")
    mall = relationship("Mall", back_populates="stores")
    region = relationship("Region", back_populates="stores")
    business_area = relationship("BusinessArea", back_populates="stores")
