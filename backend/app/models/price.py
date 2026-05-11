"""
models/price.py — AgriGuard SQLAlchemy Database Models
=======================================================
Defines the database tables as Python classes using SQLAlchemy ORM.

Tables defined here:
  - CropPrice       → core table: one row per crop/market/date price observation
  - Market          → lookup table: markets with GPS coordinates and metadata
  - Crop            → lookup table: crops with type, season, unit info
  - WeatherReading  → daily weather per market (from fetch_weather.py)
  - PriceForecast   → ML model output: predicted prices per crop/market

Design principles:
  - Every table has created_at / updated_at for audit trail
  - Foreign keys enforce data integrity (no orphan prices)
  - Indexes on the columns you'll query most (date, market, crop)
  - Enums for controlled vocabularies (regions, units, crop types)
  - MAAIF-specific fields included (source, data quality flag)

Usage:
    from app.models.price import CropPrice, Market, Crop, Base
    from app.config import settings
    from sqlalchemy import create_engine

    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)   # creates all tables

Author: AgriGuard Team
"""

import enum
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column


# =============================================================================
# BASE CLASS — all models inherit from this
# =============================================================================

class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base. All models inherit from this.
    Provides the metadata registry that create_all() uses to build tables.
    """
    pass


# =============================================================================
# ENUMS — controlled vocabularies for key fields
# These prevent typos like "Kampalla" or "kampala" getting into the DB
# =============================================================================

class UgandaRegion(str, enum.Enum):
    """Uganda's four main agricultural regions as recognised by MAAIF."""
    CENTRAL   = "Central"
    NORTHERN  = "Northern"
    EASTERN   = "Eastern"
    WESTERN   = "Western"
    WEST_NILE = "West Nile"


class PriceUnit(str, enum.Enum):
    """
    Units in which crop prices are quoted.
    Uganda uses a mix — maize in 90kg bags, tomatoes in crates, etc.
    """
    KG           = "kg"
    GRAM         = "gram"
    TONNE        = "tonne"
    BAG_90KG     = "bag_90kg"       # Standard maize bag
    BAG_50KG     = "bag_50kg"
    CRATE        = "crate"          # Tomatoes, cabbage
    BUNCH        = "bunch"          # Bananas (matooke)
    LITRE        = "litre"          # Milk, palm oil
    PIECE        = "piece"          # Eggs, avocados


class CropCategory(str, enum.Enum):
    """Broad crop categories used in MAAIF classification."""
    CEREAL       = "cereal"         # Maize, sorghum, millet, rice
    LEGUME       = "legume"         # Beans, groundnuts, soybeans
    ROOT_TUBER   = "root_tuber"     # Cassava, sweet potato, irish potato
    VEGETABLE    = "vegetable"      # Tomatoes, cabbage, onion
    FRUIT        = "fruit"          # Bananas, mango, avocado
    CASH_CROP    = "cash_crop"      # Coffee, tea, cotton, sugarcane
    OILSEED      = "oilseed"        # Simsim (sesame), sunflower
    LIVESTOCK    = "livestock"      # Milk, eggs (for future expansion)


class DataSource(str, enum.Enum):
    """
    Where the price data came from.
    Important for MAAIF — they need to know provenance of each data point.
    """
    MAAIF_SURVEY    = "maaif_survey"      # Official MAAIF field survey
    FEWS_NET        = "fews_net"          # FEWS NET market monitoring
    WFP_VAM         = "wfp_vam"           # WFP Vulnerability Analysis
    MARKET_AGENT    = "market_agent"      # Local market agent report
    FARMER_REPORT   = "farmer_report"     # Direct farmer submission (USSD)
    WEB_SCRAPE      = "web_scrape"        # Scraped from online source
    MANUAL_ENTRY    = "manual_entry"      # Manually entered by admin
    SEED_DATA       = "seed_data"         # Seeded test/demo data


class DataQuality(str, enum.Enum):
    """
    Quality flag for each price record.
    Allows downstream filtering of unreliable data points.
    """
    VERIFIED    = "verified"      # Confirmed by secondary source
    REPORTED    = "reported"      # Single source, unverified
    ESTIMATED   = "estimated"     # Derived/interpolated
    FLAGGED     = "flagged"       # Potentially erroneous, under review


# =============================================================================
# MIXINS — reusable column sets
# =============================================================================

class TimestampMixin:
    """
    Adds created_at and updated_at to any model.
    server_default uses DB-side NOW() — more reliable than Python time.
    onupdate automatically updates updated_at on every row change.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Row creation timestamp (UTC)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Last modification timestamp (UTC)",
    )


# =============================================================================
# TABLE 1: Crop — lookup table for crop metadata
# =============================================================================

class Crop(TimestampMixin, Base):
    """
    Reference table for crops monitored by AgriGuard.

    One row per crop. CropPrice rows point back here via foreign key.
    This avoids storing "Maize" as a raw string in every price row —
    instead we store crop_id=1, and Maize lives here once.

    Example rows:
        id=1, name="Maize",       category=CEREAL,   default_unit=BAG_90KG
        id=2, name="Beans",       category=LEGUME,   default_unit=KG
        id=3, name="Tomatoes",    category=VEGETABLE, default_unit=CRATE
        id=4, name="Groundnuts",  category=OILSEED,  default_unit=KG
    """

    __tablename__ = "crops"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # Full common name used in Uganda (match MAAIF terminology exactly)
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        comment="Common crop name e.g. 'Maize', 'Irish Potatoes'",
    )

    # Optional local language name (useful for USSD display to farmers)
    local_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Local language name e.g. Luganda, Acholi",
    )

    category: Mapped[CropCategory] = mapped_column(
        Enum(CropCategory),
        nullable=False,
        comment="Broad crop category for grouping",
    )

    # The unit prices are most commonly quoted in for this crop
    default_unit: Mapped[PriceUnit] = mapped_column(
        Enum(PriceUnit),
        nullable=False,
        comment="Standard pricing unit for this crop in Ugandan markets",
    )

    # Growing season info — useful for forecasting (prices spike pre-harvest)
    # Uganda has two seasons: Mar-May (Season A) and Aug-Nov (Season B)
    season_a_harvest_month: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Typical Season A harvest month (1-12)",
    )
    season_b_harvest_month: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Typical Season B harvest month (1-12)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="False = crop retired from monitoring",
    )

    # Relationships — SQLAlchemy will load these lazily by default
    prices: Mapped[list["CropPrice"]] = relationship(
        "CropPrice", back_populates="crop", lazy="select"
    )
    forecasts: Mapped[list["PriceForecast"]] = relationship(
        "PriceForecast", back_populates="crop", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Crop id={self.id} name='{self.name}' category={self.category}>"


# =============================================================================
# TABLE 2: Market — lookup table for market locations
# =============================================================================

class Market(TimestampMixin, Base):
    """
    Reference table for agricultural markets monitored by AgriGuard.

    Stores GPS coordinates so we can:
    - Link weather data to the nearest market
    - Show markets on a map in the dashboard
    - Calculate distance-based price differentials

    Example rows:
        id=1, name="Owino",    district="Kampala",  region=CENTRAL
        id=2, name="Gulu Main", district="Gulu",   region=NORTHERN
        id=3, name="Mbale",    district="Mbale",    region=EASTERN
    """

    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        unique=True,
        comment="Market name e.g. 'Owino Market', 'Gulu Main Market'",
    )

    district: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Uganda district the market is in",
    )

    region: Mapped[UgandaRegion] = mapped_column(
        Enum(UgandaRegion),
        nullable=False,
        comment="Uganda agricultural region",
    )

    # GPS coordinates — required for weather correlation
    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="WGS84 latitude (negative = south of equator)",
    )
    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="WGS84 longitude",
    )

    # Altitude matters for temperature — highland markets like Kabale
    # behave differently from lowland Kampala
    elevation_m: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Elevation above sea level in metres",
    )

    # Market operational info
    market_days: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Days market is active e.g. 'Mon, Wed, Fri' or 'Daily'",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="False = market no longer monitored",
    )

    # Relationships
    prices: Mapped[list["CropPrice"]] = relationship(
        "CropPrice", back_populates="market", lazy="select"
    )
    weather_readings: Mapped[list["WeatherReading"]] = relationship(
        "WeatherReading", back_populates="market", lazy="select"
    )
    forecasts: Mapped[list["PriceForecast"]] = relationship(
        "PriceForecast", back_populates="market", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Market id={self.id} name='{self.name}' district='{self.district}'>"


# =============================================================================
# TABLE 3: CropPrice — CORE TABLE
# One row = one price observation for one crop at one market on one date
# =============================================================================

class CropPrice(TimestampMixin, Base):
    """
    The central fact table of AgriGuard.

    Every price data point lives here. This is what MAAIF cares about most.

    A "price observation" is:
      - On a specific date
      - For a specific crop (FK → crops)
      - At a specific market (FK → markets)
      - With a wholesale and/or retail price in UGX

    Why separate wholesale and retail?
      - Wholesale = what traders pay farmers (farmgate proxy)
      - Retail = what consumers pay
      - The spread tells you about market efficiency and trader margins
      - MAAIF tracks both for food security analysis

    Uniqueness constraint:
      - One row per (date, crop, market, unit) combination
      - Prevents accidental duplicate imports from the same CSV
    """

    __tablename__ = "crop_prices"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # ----- CORE DIMENSIONS (the "what, where, when") -----

    price_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,    # Indexed — we query by date range constantly
        comment="Date this price was observed/collected",
    )

    crop_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("crops.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="FK to crops table",
    )

    market_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("markets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="FK to markets table",
    )

    unit: Mapped[PriceUnit] = mapped_column(
        Enum(PriceUnit),
        nullable=False,
        comment="Unit the price is quoted in",
    )

    # ----- PRICE VALUES (in Uganda Shillings — UGX) -----
    # Using Numeric(12,2) — up to 9,999,999,999.99 UGX
    # Float would introduce rounding errors in financial data

    wholesale_price_ugx: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Wholesale price in UGX per unit. NULL if not collected.",
    )

    retail_price_ugx: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Retail price in UGX per unit. NULL if not collected.",
    )

    # Convenience: price per kg normalized (for cross-crop comparisons)
    # Calculated at insert time by the service layer, not stored raw
    price_per_kg_ugx: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Normalized price per kg in UGX. Derived field for ML features.",
    )

    # ----- DATA PROVENANCE -----

    source: Mapped[DataSource] = mapped_column(
        Enum(DataSource),
        nullable=False,
        default=DataSource.MANUAL_ENTRY,
        comment="Where this price data came from",
    )

    quality: Mapped[DataQuality] = mapped_column(
        Enum(DataQuality),
        nullable=False,
        default=DataQuality.REPORTED,
        comment="Data quality/confidence flag",
    )

    # Free-text notes — e.g. "Market flooded, limited supply" or
    # "Price spike due to fuel shortage"
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional context notes from the data collector",
    )

    # ----- RELATIONSHIPS -----

    crop: Mapped["Crop"] = relationship("Crop", back_populates="prices")
    market: Mapped["Market"] = relationship("Market", back_populates="prices")

    # ----- CONSTRAINTS & INDEXES -----

    __table_args__ = (
        # Prevent duplicate entries for the same crop/market/date/unit combo
        UniqueConstraint(
            "price_date", "crop_id", "market_id", "unit",
            name="uq_price_date_crop_market_unit",
        ),
        # Composite index for the most common query pattern:
        # "give me all prices for crop X between date A and date B"
        Index("ix_crop_prices_crop_date", "crop_id", "price_date"),
        # Composite index for market-level queries:
        # "show all prices at Kampala market this month"
        Index("ix_crop_prices_market_date", "market_id", "price_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<CropPrice id={self.id} "
            f"date={self.price_date} "
            f"crop_id={self.crop_id} "
            f"market_id={self.market_id} "
            f"retail={self.retail_price_ugx} UGX>"
        )


# =============================================================================
# TABLE 4: WeatherReading — daily weather per market
# Populated by fetch_weather.py → load_data.py
# =============================================================================

class WeatherReading(TimestampMixin, Base):
    """
    Daily weather observations per market location.

    These are the input features for the ML price forecasting model.
    The key insight: weather in week N predicts crop prices in week N+4
    (roughly one harvest cycle later).

    Key derived field — water_balance_mm:
        = rainfall_mm - et0_evapotranspiration_mm
        Negative value = drought stress → expect supply drop → price rise
        Positive value = good moisture → healthy crop → stable/lower prices
    """

    __tablename__ = "weather_readings"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    reading_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Date of the weather observation",
    )

    market_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("markets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to markets — weather is tied to market location",
    )

    # Temperature
    temp_max_c: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Max daily temperature °C"
    )
    temp_min_c: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Min daily temperature °C"
    )

    # Rainfall
    rainfall_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Total precipitation mm/day"
    )
    precip_hours: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Hours of precipitation (intensity proxy)"
    )

    # Humidity
    humidity_max_pct: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Max relative humidity %"
    )
    humidity_min_pct: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Min relative humidity %"
    )

    # Wind
    wind_speed_max_kmh: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Max wind speed km/h"
    )

    # Evapotranspiration — FAO Penman-Monteith reference ET
    # The standard agronomic measure of atmospheric water demand
    et0_evapotranspiration_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="FAO reference evapotranspiration mm/day"
    )

    # Derived crop stress indicator
    # Positive = water surplus, Negative = deficit (drought stress)
    water_balance_mm: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="rainfall_mm - et0_mm. Key ML feature for price forecasting.",
    )

    # Is this a forecast or actual observation?
    is_forecast: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True = future forecast from Open-Meteo, False = historical actual",
    )

    # Relationships
    market: Mapped["Market"] = relationship(
        "Market", back_populates="weather_readings"
    )

    __table_args__ = (
        UniqueConstraint(
            "reading_date", "market_id", "is_forecast",
            name="uq_weather_date_market_forecast",
        ),
        Index("ix_weather_market_date", "market_id", "reading_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<WeatherReading id={self.id} "
            f"date={self.reading_date} "
            f"market_id={self.market_id} "
            f"rain={self.rainfall_mm}mm "
            f"balance={self.water_balance_mm}mm>"
        )


# =============================================================================
# TABLE 5: PriceForecast — ML model predictions
# Written by the forecast service, read by the /forecasts API router
# =============================================================================

class PriceForecast(TimestampMixin, Base):
    """
    Stores ML model price forecast outputs.

    Each row is a predicted price for a specific crop/market/future date,
    generated by the model in ml/training/train_forecast.py.

    Why store forecasts in the DB instead of computing on the fly?
      - Forecasts are expensive to compute (run ML inference)
      - Pre-computing and caching in DB means fast API responses
      - Allows comparing model versions over time
      - MAAIF can pull historical forecasts vs actuals for accuracy reporting

    Confidence interval (lower_bound, upper_bound):
      - 90% confidence interval around the point forecast
      - Tells MAAIF how certain the model is
      - Wide interval = uncertain (bad weather data, thin history)
      - Narrow interval = confident (stable pattern, rich history)
    """

    __tablename__ = "price_forecasts"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    forecast_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="The future date this forecast is for",
    )

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When this forecast was generated (for staleness checks)",
    )

    crop_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("crops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    market_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("markets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    unit: Mapped[PriceUnit] = mapped_column(
        Enum(PriceUnit),
        nullable=False,
    )

    # Point forecast — the model's best single estimate
    predicted_price_ugx: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Predicted retail price in UGX",
    )

    # 90% confidence interval
    lower_bound_ugx: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Lower bound of 90% confidence interval",
    )
    upper_bound_ugx: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Upper bound of 90% confidence interval",
    )

    # Model metadata — important for reproducibility and MAAIF reporting
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="v1.0",
        comment="Version tag of the ML model that generated this forecast",
    )

    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Model confidence 0.0–1.0. Below settings.min_forecast_confidence = unreliable.",
    )

    # Relationships
    crop: Mapped["Crop"] = relationship("Crop", back_populates="forecasts")
    market: Mapped["Market"] = relationship("Market", back_populates="forecasts")

    __table_args__ = (
        UniqueConstraint(
            "forecast_date", "crop_id", "market_id", "unit", "model_version",
            name="uq_forecast_date_crop_market_model",
        ),
        Index("ix_forecasts_crop_date", "crop_id", "forecast_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<PriceForecast id={self.id} "
            f"date={self.forecast_date} "
            f"crop_id={self.crop_id} "
            f"market_id={self.market_id} "
            f"predicted={self.predicted_price_ugx} UGX "
            f"confidence={self.confidence_score:.2f}>"
        )


# =============================================================================
# DATABASE INITIALISATION HELPER
# =============================================================================

def init_db(engine) -> None:
    """
    Creates all tables defined in this file.

    Call this once at application startup (in main.py) or
    run it manually to set up a fresh database.

    Args:
        engine: SQLAlchemy engine from create_engine(settings.database_url)

    Usage:
        from sqlalchemy import create_engine
        from app.config import settings
        from app.models.price import init_db

        engine = create_engine(settings.database_url)
        init_db(engine)
        print("Tables created.")

    Note: In production, use Alembic migrations instead of init_db().
    Alembic handles schema changes safely without dropping existing data.
    For the MVP demo, init_db() is fine.
    """
    Base.metadata.create_all(bind=engine)
    print("✅ AgriGuard database tables created successfully.")
    print("   Tables: crops, markets, crop_prices, weather_readings, price_forecasts")