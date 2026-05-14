"""
models/price.py — AgriGuard SQLAlchemy Database Models
=======================================================
Defines the database tables as Python classes using SQLAlchemy ORM.

Tables defined here:
  - Crop            → lookup: crops with category, unit, season info
  - Market          → lookup: markets with GPS coordinates and metadata
  - CropPrice       → core fact table: one price observation per crop/market/date
  - WeatherReading  → daily weather per market (from fetch_weather.py)
  - PriceForecast   → ML model output: predicted prices per crop/market
  - AgroInput       → counterfeit detection: registered agro-inputs (seeds/pesticides)

Design principles:
  - Every table has created_at / updated_at for full audit trail
  - Foreign keys enforce data integrity (no orphan prices)
  - Composite indexes on the columns queried most (date, market, crop)
  - Enums for all controlled vocabularies (regions, units, crop types)
  - MAAIF-compatible fields: source, quality, region, data provenance
  - Numeric(12,2) for all UGX money fields — never Float for currency

Changes from v1:
  - Added AgroInput table for counterfeit detection MVP feature
  - Added `price_trend` computed hint on CropPrice for dashboard use
  - Added `agro_zone` on Market (MAAIF agro-ecological zone)
  - Added `currency` field on CropPrice (future cross-border expansion)
  - Added `horizon_days` on PriceForecast (how far ahead the forecast is)
  - Renamed ambiguous `quality` → `data_quality` on CropPrice
  - Added `__repr__` polish and inline docstring examples throughout
  - init_db() now prints a richer summary table

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
    CheckConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column


# =============================================================================
# BASE CLASS
# =============================================================================

class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base. All models inherit from this.
    Base.metadata.create_all(engine) builds every table registered here.
    """
    pass


# =============================================================================
# ENUMS — controlled vocabularies
# Using (str, enum.Enum) so values serialise cleanly to JSON / Pydantic
# =============================================================================

class UgandaRegion(str, enum.Enum):
    """Uganda's main agricultural regions as defined by MAAIF."""
    CENTRAL   = "Central"
    NORTHERN  = "Northern"
    EASTERN   = "Eastern"
    WESTERN   = "Western"
    WEST_NILE = "West Nile"


class AgroEcologicalZone(str, enum.Enum):
    """
    MAAIF agro-ecological zones — important for crop suitability advice
    and for matching weather patterns to crop performance.
    """
    LAKE_VICTORIA_CRESCENT = "Lake Victoria Crescent"
    SOUTH_WESTERN_HIGHLANDS = "South Western Highlands"
    SOUTH_EASTERN_PLAIN     = "South Eastern Plain"
    NORTHERN_MOIST_FARMLAND = "Northern Moist Farmland"
    NORTH_EAST_DRY_LAND     = "North East Dry Land"
    WEST_NILE               = "West Nile"
    EASTERN_HILLS           = "Eastern Hills and Mountains"


class PriceUnit(str, enum.Enum):
    """
    Units in which crop prices are quoted in Ugandan markets.
    Uganda uses a mix — maize in 90 kg bags, tomatoes in crates, etc.
    """
    KG       = "kg"
    GRAM     = "gram"
    TONNE    = "tonne"
    BAG_90KG = "bag_90kg"   # Standard maize bag
    BAG_50KG = "bag_50kg"
    CRATE    = "crate"      # Tomatoes, cabbage
    BUNCH    = "bunch"      # Bananas (matooke)
    LITRE    = "litre"      # Milk, palm oil
    PIECE    = "piece"      # Eggs, avocados


class Currency(str, enum.Enum):
    """
    Currency of the price observation.
    UGX is the default; others needed for cross-border markets
    (e.g. Malaba, Busia, Mutukula border posts).
    """
    UGX = "UGX"   # Uganda Shilling
    KES = "KES"   # Kenya Shilling
    TZS = "TZS"   # Tanzania Shilling
    RWF = "RWF"   # Rwanda Franc
    USD = "USD"   # US Dollar (export markets)


class CropCategory(str, enum.Enum):
    """Broad crop categories aligned with MAAIF classification."""
    CEREAL      = "cereal"      # Maize, sorghum, millet, rice
    LEGUME      = "legume"      # Beans, groundnuts, soybeans
    ROOT_TUBER  = "root_tuber"  # Cassava, sweet potato, irish potato
    VEGETABLE   = "vegetable"   # Tomatoes, cabbage, onion
    FRUIT       = "fruit"       # Bananas, mango, avocado
    CASH_CROP   = "cash_crop"   # Coffee, tea, cotton, sugarcane
    OILSEED     = "oilseed"     # Simsim (sesame), sunflower
    LIVESTOCK   = "livestock"   # Milk, eggs (future expansion)


class DataSource(str, enum.Enum):
    """
    Provenance of each price data point.
    Required by MAAIF for data credibility assessment.
    """
    MAAIF_SURVEY  = "maaif_survey"    # Official MAAIF field survey
    FEWS_NET      = "fews_net"        # FEWS NET market monitoring
    WFP_VAM       = "wfp_vam"         # WFP Vulnerability Analysis
    MARKET_AGENT  = "market_agent"    # Local market agent report
    FARMER_REPORT = "farmer_report"   # Direct farmer submission (USSD/SMS)
    WEB_SCRAPE    = "web_scrape"      # Scraped from an online source
    MANUAL_ENTRY  = "manual_entry"    # Manually entered by admin
    SEED_DATA     = "seed_data"       # Seeded test/demo data


class DataQuality(str, enum.Enum):
    """
    Quality flag per price record — allows downstream filtering.
    The ML model should only train on VERIFIED and REPORTED rows.
    """
    VERIFIED  = "verified"   # Confirmed by secondary source
    REPORTED  = "reported"   # Single source, unverified
    ESTIMATED = "estimated"  # Derived or interpolated
    FLAGGED   = "flagged"    # Potentially erroneous, under review


class PriceTrend(str, enum.Enum):
    """
    Direction hint computed when a new price is inserted.
    Compared to the previous observation for the same crop/market.
    Used by the dashboard to show ↑ ↓ → arrows without extra queries.
    """
    RISING   = "rising"
    FALLING  = "falling"
    STABLE   = "stable"
    UNKNOWN  = "unknown"   # First observation, no previous to compare


class AgroInputCategory(str, enum.Enum):
    """Categories of agro-inputs subject to counterfeiting."""
    SEED       = "seed"
    FERTILIZER = "fertilizer"
    PESTICIDE  = "pesticide"
    HERBICIDE  = "herbicide"
    FUNGICIDE  = "fungicide"
    VETERINARY = "veterinary"


class VerificationStatus(str, enum.Enum):
    """Result of a counterfeit verification scan on an agro-input."""
    GENUINE    = "genuine"     # Matches registered product in DB
    COUNTERFEIT = "counterfeit" # Confirmed fake
    SUSPICIOUS = "suspicious"  # Anomalies detected, needs review
    UNKNOWN    = "unknown"     # Could not determine


# =============================================================================
# MIXIN — shared timestamp columns
# =============================================================================

class TimestampMixin:
    """
    Adds created_at and updated_at to every model.
    server_default uses DB-side NOW() — more reliable than Python time
    because it survives bulk imports that bypass the ORM layer.
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
# TABLE 1: Crop
# =============================================================================

class Crop(TimestampMixin, Base):
    """
    Reference table for every crop monitored by AgriGuard.

    One row per crop. CropPrice and PriceForecast rows reference this
    via crop_id — avoids storing "Maize" as a raw string in millions of rows.

    Example rows:
        id=1  name="Maize"        category=CEREAL     unit=BAG_90KG
        id=2  name="Beans"        category=LEGUME     unit=KG
        id=3  name="Tomatoes"     category=VEGETABLE  unit=CRATE
        id=4  name="Groundnuts"   category=OILSEED    unit=KG
        id=5  name="Robusta Coffee" category=CASH_CROP unit=KG
    """

    __tablename__ = "crops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        comment="Common crop name matching MAAIF terminology e.g. 'Maize', 'Irish Potatoes'",
    )

    local_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Local language name for USSD display e.g. 'Kasooli' (maize in Luganda)",
    )

    category: Mapped[CropCategory] = mapped_column(
        Enum(CropCategory),
        nullable=False,
        comment="Broad MAAIF crop category",
    )

    default_unit: Mapped[PriceUnit] = mapped_column(
        Enum(PriceUnit),
        nullable=False,
        comment="Standard pricing unit for this crop in Ugandan markets",
    )

    # Uganda has two growing seasons:
    # Season A — March to May (long rains)
    # Season B — August to November (short rains)
    # Prices typically spike just BEFORE harvest as stocks run low.
    season_a_harvest_month: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Typical Season A harvest month (1–12)",
    )
    season_b_harvest_month: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Typical Season B harvest month (1–12)",
    )

    # Shelf-life matters for price volatility modelling —
    # tomatoes spike and crash fast; maize is more stable.
    shelf_life_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Approximate post-harvest shelf life in days. Influences price volatility.",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="False = crop retired from monitoring",
    )

    # ORM relationships
    prices: Mapped[list["CropPrice"]] = relationship(
        "CropPrice", back_populates="crop", lazy="select"
    )
    forecasts: Mapped[list["PriceForecast"]] = relationship(
        "PriceForecast", back_populates="crop", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Crop id={self.id} name='{self.name}' category={self.category.value}>"


# =============================================================================
# TABLE 2: Market
# =============================================================================

class Market(TimestampMixin, Base):
    """
    Reference table for agricultural markets monitored by AgriGuard.

    GPS coordinates enable:
    - Attaching the nearest weather station to each market
    - Map visualisations in the farmer dashboard
    - Distance-based price spread analysis (arbitrage opportunities)

    Example rows:
        id=1  name="Owino"       district="Kampala Central"  region=CENTRAL
        id=2  name="Gulu Main"   district="Gulu"             region=NORTHERN
        id=3  name="Mbale"       district="Mbale"            region=EASTERN
        id=4  name="Mbarara"     district="Mbarara"          region=WESTERN
        id=5  name="Busia Border" district="Busia"           region=EASTERN
    """

    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        unique=True,
        comment="Full market name e.g. 'Owino Market', 'Gulu Main Market'",
    )

    district: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Uganda district the market is located in",
    )

    region: Mapped[UgandaRegion] = mapped_column(
        Enum(UgandaRegion),
        nullable=False,
        comment="MAAIF Uganda agricultural region",
    )

    agro_zone: Mapped[Optional[AgroEcologicalZone]] = mapped_column(
        Enum(AgroEcologicalZone),
        nullable=True,
        comment="MAAIF agro-ecological zone — informs crop suitability and climate patterns",
    )

    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="WGS84 latitude (negative values = south of equator)",
    )
    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="WGS84 longitude",
    )

    # Altitude matters — highland Kabale behaves very differently
    # from lowland Kampala in terms of temperature and crop types.
    elevation_m: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Elevation above sea level in metres",
    )

    market_days: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Active trading days e.g. 'Mon, Wed, Fri' or 'Daily'",
    )

    is_border_market: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True = cross-border market (Busia, Malaba, Mutukula, Katuna). "
                "Prices here are influenced by neighbouring-country rates.",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="False = market removed from monitoring",
    )

    # ORM relationships
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
        return (
            f"<Market id={self.id} name='{self.name}' "
            f"district='{self.district}' region={self.region.value}>"
        )


# =============================================================================
# TABLE 3: CropPrice  (CORE FACT TABLE)
# =============================================================================

class CropPrice(TimestampMixin, Base):
    """
    The central fact table of AgriGuard. Every price data point lives here.

    One row = one price observation:
      - On a specific date
      - For a specific crop  (FK → crops)
      - At a specific market (FK → markets)
      - In a specific unit and currency

    Why separate wholesale and retail?
      Wholesale ≈ what traders pay farmers (farmgate proxy)
      Retail    ≈ what consumers pay at the stall
      The spread reveals market efficiency and middlemen margins —
      exactly the information MAAIF and food security analysts need.

    price_per_kg_ugx:
      A normalised UGX/kg value computed at insert time by price_service.py.
      Allows direct ML comparison across crops priced in different units
      (e.g. comparing maize bags vs cassava kg).

    price_trend:
      Computed against the immediately preceding observation for the same
      crop × market combination. Stored here so the dashboard can render
      ↑ ↓ → indicators with zero extra queries.

    Uniqueness constraint:
      One row per (date, crop, market, unit, currency).
      Prevents accidental duplicate imports from the same CSV or MAAIF upload.
    """

    __tablename__ = "crop_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Core dimensions ──────────────────────────────────────────────────────

    price_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Date the price was observed or collected",
    )

    crop_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("crops.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="FK → crops.id",
    )

    market_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("markets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="FK → markets.id",
    )

    unit: Mapped[PriceUnit] = mapped_column(
        Enum(PriceUnit),
        nullable=False,
        comment="Unit the price is quoted in",
    )

    currency: Mapped[Currency] = mapped_column(
        Enum(Currency),
        nullable=False,
        default=Currency.UGX,
        comment="Currency of the price. UGX is the default. "
                "Non-UGX values arise at border markets.",
    )

    # ── Price values ─────────────────────────────────────────────────────────
    # Numeric(12,2) = up to 9,999,999,999.99 — safe for UGX amounts
    # NEVER use Float for monetary fields (binary rounding errors)

    wholesale_price: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Wholesale price per unit in the stated currency. "
                "NULL when not collected at this observation.",
    )

    retail_price: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Retail (consumer) price per unit in the stated currency.",
    )

    price_per_kg_ugx: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Normalised retail price per kg in UGX. "
                "Computed by price_service.py at insert time. "
                "Primary feature for ML cross-crop comparisons.",
    )

    # ── Dashboard hint ────────────────────────────────────────────────────────

    price_trend: Mapped[PriceTrend] = mapped_column(
        Enum(PriceTrend),
        nullable=False,
        default=PriceTrend.UNKNOWN,
        comment="Direction vs previous observation for this crop × market. "
                "Set by price_service.py at insert. Drives dashboard arrows.",
    )

    # ── Data provenance ───────────────────────────────────────────────────────

    data_source: Mapped[DataSource] = mapped_column(
        Enum(DataSource),
        nullable=False,
        default=DataSource.MANUAL_ENTRY,
        comment="Where this price record originated",
    )

    data_quality: Mapped[DataQuality] = mapped_column(
        Enum(DataQuality),
        nullable=False,
        default=DataQuality.REPORTED,
        comment="Confidence flag. ML model should only use VERIFIED + REPORTED.",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Free-text context e.g. 'Market flooded — limited supply' or "
                "'Price spike due to fuel shortage'",
    )

    # ── ORM relationships ─────────────────────────────────────────────────────

    crop: Mapped["Crop"] = relationship("Crop", back_populates="prices")
    market: Mapped["Market"] = relationship("Market", back_populates="prices")

    # ── Constraints & indexes ─────────────────────────────────────────────────

    __table_args__ = (
        UniqueConstraint(
            "price_date", "crop_id", "market_id", "unit", "currency",
            name="uq_price_date_crop_market_unit_currency",
        ),
        # Most common query: "all prices for crop X between date A and B"
        Index("ix_crop_prices_crop_date",   "crop_id",   "price_date"),
        # Market-level queries: "all prices at Kampala this month"
        Index("ix_crop_prices_market_date", "market_id", "price_date"),
        # Guard against negative prices being inserted
        CheckConstraint("wholesale_price  IS NULL OR wholesale_price  >= 0", name="ck_wholesale_non_negative"),
        CheckConstraint("retail_price     IS NULL OR retail_price     >= 0", name="ck_retail_non_negative"),
        CheckConstraint("price_per_kg_ugx IS NULL OR price_per_kg_ugx >= 0", name="ck_per_kg_non_negative"),
    )

    def __repr__(self) -> str:
        return (
            f"<CropPrice id={self.id} "
            f"date={self.price_date} "
            f"crop_id={self.crop_id} market_id={self.market_id} "
            f"retail={self.retail_price} {self.currency.value} "
            f"trend={self.price_trend.value}>"
        )


# =============================================================================
# TABLE 4: WeatherReading
# =============================================================================

class WeatherReading(TimestampMixin, Base):
    """
    Daily weather observations per market location.

    Populated by scripts/fetch_weather.py using Open-Meteo API.
    These rows are the primary external features for the ML price
    forecasting model in ml/training/train_forecast.py.

    Key insight: weather in week N predicts crop prices in week N+3 to N+6
    (one to two harvest cycles later, depending on the crop).

    water_balance_mm (derived key feature):
        = rainfall_mm − et0_evapotranspiration_mm
        Negative → drought stress → supply will fall → prices will rise
        Positive → good moisture  → healthy yield   → stable/lower prices

    is_forecast flag:
        True  → future forecast fetched from Open-Meteo (7–14 day horizon)
        False → historical actual observation
        The ML model trains on False rows and uses True rows for inference.
    """

    __tablename__ = "weather_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    reading_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Date of the weather observation or forecast",
    )

    market_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("markets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK → markets.id — weather is anchored to a market's GPS coordinates",
    )

    # Temperature
    temp_max_c: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Maximum daily temperature °C"
    )
    temp_min_c: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Minimum daily temperature °C"
    )
    temp_mean_c: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Mean daily temperature °C. Derived: (max + min) / 2."
    )

    # Rainfall
    rainfall_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Total precipitation mm/day"
    )
    precip_hours: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Hours of precipitation per day — proxy for rainfall intensity"
    )

    # Humidity
    humidity_max_pct: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Maximum relative humidity %"
    )
    humidity_min_pct: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Minimum relative humidity %"
    )

    # Wind
    wind_speed_max_kmh: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Maximum wind speed km/h"
    )

    # Evapotranspiration — FAO Penman-Monteith reference ET₀
    # Standard agronomic measure of atmospheric water demand
    et0_evapotranspiration_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="FAO-56 reference evapotranspiration ET₀ mm/day"
    )

    # KEY ML FEATURE: water balance = rainfall - ET₀
    # Positive = surplus moisture → good crop conditions
    # Negative = deficit / drought stress → supply-side price pressure
    water_balance_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Crop water balance: rainfall_mm − et0_mm. "
                "Primary ML feature linking weather to future price movements.",
    )

    is_forecast: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True = future forecast from Open-Meteo; False = historical actual. "
                "ML model trains on False rows only.",
    )

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
        kind = "forecast" if self.is_forecast else "actual"
        return (
            f"<WeatherReading id={self.id} "
            f"date={self.reading_date} market_id={self.market_id} "
            f"rain={self.rainfall_mm}mm balance={self.water_balance_mm}mm "
            f"[{kind}]>"
        )


# =============================================================================
# TABLE 5: PriceForecast
# =============================================================================

class PriceForecast(TimestampMixin, Base):
    """
    ML model price forecast outputs — pre-computed and cached here.

    Written by: ml/training/train_forecast.py
    Read by:    app/routers/forecasts.py  →  GET /api/v1/forecasts

    Why store forecasts in the DB rather than computing on the fly?
      - ML inference is expensive; pre-compute once, serve fast
      - Enables comparing model versions over time (audit trail)
      - MAAIF can pull historical forecasts vs actuals for accuracy reports
      - Powers push notifications: "Beans price likely to rise next week"

    Confidence interval (lower_bound_ugx, upper_bound_ugx):
      90% CI around the point forecast.
      Wide interval  = high uncertainty (sparse data, unusual weather)
      Narrow interval = confident prediction (stable seasonality, rich history)

    horizon_days:
      How many days ahead this forecast is for, from generated_at.
      Short horizon (1–7 days)  → higher confidence, operational decisions
      Long horizon (14–30 days) → lower confidence, strategic planning
    """

    __tablename__ = "price_forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    forecast_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="The future date this price prediction is for",
    )

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when this forecast was generated — for staleness checks",
    )

    horizon_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Days ahead from generated_at. "
                "Short (1–7): operational. Long (14–30): strategic.",
    )

    crop_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("crops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK → crops.id",
    )

    market_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("markets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK → markets.id",
    )

    unit: Mapped[PriceUnit] = mapped_column(
        Enum(PriceUnit),
        nullable=False,
    )

    # Point forecast — model's single best estimate
    predicted_price_ugx: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Predicted retail price in UGX per unit",
    )

    # 90% confidence interval
    lower_bound_ugx: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Lower bound of 90% prediction interval in UGX",
    )
    upper_bound_ugx: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Upper bound of 90% prediction interval in UGX",
    )

    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="v1.0",
        comment="Version tag of the ML model — enables A/B comparison over time",
    )

    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Model confidence 0.0–1.0. "
                "Below settings.min_forecast_confidence → mark as unreliable.",
    )

    # ORM relationships
    crop: Mapped["Crop"] = relationship("Crop", back_populates="forecasts")
    market: Mapped["Market"] = relationship("Market", back_populates="forecasts")

    __table_args__ = (
        UniqueConstraint(
            "forecast_date", "crop_id", "market_id", "unit", "model_version",
            name="uq_forecast_date_crop_market_model",
        ),
        Index("ix_forecasts_crop_date",   "crop_id",   "forecast_date"),
        Index("ix_forecasts_market_date", "market_id", "forecast_date"),
        CheckConstraint("confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
                        name="ck_confidence_score_range"),
    )

    def __repr__(self) -> str:
        conf = f"{self.confidence_score:.2f}" if self.confidence_score is not None else "n/a"
        return (
            f"<PriceForecast id={self.id} "
            f"date={self.forecast_date} "
            f"crop_id={self.crop_id} market_id={self.market_id} "
            f"predicted={self.predicted_price_ugx} UGX "
            f"model={self.model_version} confidence={conf}>"
        )


# =============================================================================
# TABLE 6: AgroInput  (NEW — Counterfeit Detection Feature)
# =============================================================================

class AgroInput(TimestampMixin, Base):
    """
    Registry of genuine agro-inputs for counterfeit verification.

    This table is the reference database for the counterfeit detection
    feature. When a farmer scans a product (barcode / QR / photo),
    the app queries this table to verify authenticity.

    How it works:
      1. AgriGuard partners with MAAIF and registered distributors to
         populate this table with genuine product records.
      2. Farmer scans product barcode via the mobile app.
      3. App calls GET /api/v1/agro-inputs/verify?barcode=XYZ
      4. Service layer compares against this table and returns
         VerificationStatus (GENUINE / COUNTERFEIT / SUSPICIOUS).

    Fields:
      - barcode / qr_code: primary lookup keys from a scan
      - batch_number:       links to distributor supply chain
      - manufacturer:       verified manufacturer name
      - registration_no:    MAAIF product registration number (required by law)
      - packaging_hash:     future use — hash of reference packaging image
                            for CV-based visual verification

    Example rows:
        name="UgaSeed Hybrid Maize SC403"  category=SEED
        name="Nile Urea 46%"               category=FERTILIZER
        name="Dursban 48EC"                category=PESTICIDE
    """

    __tablename__ = "agro_inputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Full product name e.g. 'UgaSeed Hybrid Maize SC403'",
    )

    category: Mapped[AgroInputCategory] = mapped_column(
        Enum(AgroInputCategory),
        nullable=False,
        comment="Type of agro-input",
    )

    manufacturer: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Verified manufacturer or registrant name",
    )

    # MAAIF requires all agro-inputs to carry a registration number
    maaif_registration_no: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        comment="MAAIF product registration number. Legal requirement in Uganda.",
    )

    # Primary scan keys — at least one should be present
    barcode: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
        comment="EAN/UPC barcode on genuine packaging",
    )

    qr_code: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        index=True,
        comment="QR code payload on genuine packaging",
    )

    batch_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Manufacturer batch/lot number — links to supply chain records",
    )

    # Computer vision support (future Phase 2)
    packaging_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA-256 hash of the reference packaging image. "
                "Used by the CV model to detect label tampering.",
    )

    # Country and distributor info
    country_of_origin: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Country where the product was manufactured",
    )

    authorised_distributors: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Comma-separated list of authorised Ugandan distributors",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="False = product recalled or registration revoked",
    )

    def __repr__(self) -> str:
        return (
            f"<AgroInput id={self.id} "
            f"name='{self.name}' "
            f"category={self.category.value} "
            f"maaif_reg='{self.maaif_registration_no}'>"
        )


# =============================================================================
# DATABASE INITIALISATION HELPER
# =============================================================================

_TABLES = [
    ("crops",            "Crop reference data"),
    ("markets",          "Market locations with GPS"),
    ("crop_prices",      "Core price observations (fact table)"),
    ("weather_readings", "Daily weather per market"),
    ("price_forecasts",  "ML model forecast outputs"),
    ("agro_inputs",      "Genuine agro-input registry (counterfeit detection)"),
]


def init_db(engine) -> None:
    """
    Creates all tables defined in this module.

    Call once at application startup (app/main.py) or run manually
    to set up a fresh database from scratch.

    Args:
        engine: SQLAlchemy engine from create_engine(settings.database_url)

    Usage:
        from sqlalchemy import create_engine
        from app.config import settings
        from app.models.price import init_db

        engine = create_engine(settings.database_url)
        init_db(engine)

    ⚠️  Production note:
        Use Alembic migrations (alembic upgrade head) instead of init_db()
        once the schema is live — Alembic handles incremental changes
        without dropping existing data. init_db() is fine for the MVP demo.
    """
    Base.metadata.create_all(bind=engine)

    print("\n✅  AgriGuard — database initialised successfully")
    print("─" * 48)
    for table_name, description in _TABLES:
        print(f"   ✓  {table_name:<24} {description}")
    print("─" * 48)
    print("   Next step: run scripts/load_data.py to seed crop + market data.\n")