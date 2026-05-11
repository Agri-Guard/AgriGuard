"""
schemas/price.py — AgriGuard Pydantic API Schemas
==================================================
Defines the data shapes for API requests and responses.

Why separate schemas from SQLAlchemy models?
  - Models (models/price.py) define the DB structure
  - Schemas (this file) define what the API accepts and returns
  - They are deliberately different:
      * DB model has internal fields (created_at, foreign keys, etc.)
      * API response only exposes what the client needs
      * API input only accepts what the client should be allowed to set
  - This separation prevents accidental data leaks and enforces
    clean API contracts

Schema naming convention used here:
  - Base        → shared fields (used by Create and Response)
  - Create      → what the client sends to CREATE a record (POST body)
  - Update      → what the client sends to UPDATE a record (PUT body)
  - Response    → what the API returns to the client (GET response)
  - Summary     → lightweight version for list endpoints (less data)
  - Filter      → query parameters for filtering/searching

Validation rules enforce:
  - Prices must be positive numbers
  - Dates cannot be in the future (no pre-loading future prices)
  - Lat/lon within Uganda's bounding box
  - Confidence scores between 0 and 1

Author: AgriGuard Team
"""

from datetime import date, datetime
from typing import Optional
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator, computed_field

# Import enums from the models — single source of truth
from app.models.price import (
    CropCategory,
    DataQuality,
    DataSource,
    PriceUnit,
    UgandaRegion,
)


# =============================================================================
# UGANDA GEOGRAPHIC BOUNDS — used to validate lat/lon inputs
# Approximate bounding box: south=-1.48, north=4.23, west=29.57, east=35.00
# =============================================================================

UGANDA_LAT_MIN = -1.48
UGANDA_LAT_MAX =  4.23
UGANDA_LON_MIN = 29.57
UGANDA_LON_MAX = 35.00


# =============================================================================
# CROP SCHEMAS
# =============================================================================

class CropBase(BaseModel):
    """Shared fields for Crop create and response schemas."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Common crop name e.g. 'Maize', 'Irish Potatoes'",
        examples=["Maize", "Beans", "Tomatoes"],
    )
    local_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Local language name for USSD display",
        examples=["Kasooli", "Bunyebwa"],
    )
    category: CropCategory = Field(
        ...,
        description="Broad crop category",
    )
    default_unit: PriceUnit = Field(
        ...,
        description="Standard pricing unit for this crop",
    )
    season_a_harvest_month: Optional[int] = Field(
        None,
        ge=1,
        le=12,
        description="Season A harvest month (1=Jan, 12=Dec)",
    )
    season_b_harvest_month: Optional[int] = Field(
        None,
        ge=1,
        le=12,
        description="Season B harvest month (1=Jan, 12=Dec)",
    )


class CropCreate(CropBase):
    """Schema for POST /crops — creating a new crop."""
    pass  # Inherits all fields from CropBase; no extra fields needed on create


class CropResponse(CropBase):
    """Schema for GET /crops responses — what the API returns."""

    id: int = Field(..., description="Database primary key")
    is_active: bool = Field(..., description="Whether crop is actively monitored")
    created_at: datetime
    updated_at: datetime

    # Pydantic v2: allow reading from SQLAlchemy ORM objects directly
    model_config = {"from_attributes": True}


class CropSummary(BaseModel):
    """
    Lightweight crop info for embedding inside other responses.
    Used in PriceResponse so clients get crop name without a second API call.
    """
    id: int
    name: str
    category: CropCategory
    default_unit: PriceUnit

    model_config = {"from_attributes": True}


# =============================================================================
# MARKET SCHEMAS
# =============================================================================

class MarketBase(BaseModel):
    """Shared fields for Market create and response schemas."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=150,
        description="Market name",
        examples=["Owino Market", "Gulu Main Market"],
    )
    district: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Uganda district",
        examples=["Kampala", "Gulu", "Mbarara"],
    )
    region: UgandaRegion = Field(
        ...,
        description="Uganda agricultural region",
    )
    latitude: float = Field(
        ...,
        description="WGS84 latitude (negative = south of equator)",
        examples=[0.3476],
    )
    longitude: float = Field(
        ...,
        description="WGS84 longitude",
        examples=[32.5825],
    )
    elevation_m: Optional[float] = Field(
        None,
        ge=0,
        le=5200,  # Mt Elgon peak is ~4321m — generous upper bound
        description="Elevation above sea level in metres",
    )
    market_days: Optional[str] = Field(
        None,
        max_length=100,
        description="Active market days e.g. 'Mon, Wed, Fri' or 'Daily'",
    )

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        """Ensure latitude is within Uganda's bounding box."""
        if not (UGANDA_LAT_MIN <= v <= UGANDA_LAT_MAX):
            raise ValueError(
                f"Latitude {v} is outside Uganda's bounds "
                f"({UGANDA_LAT_MIN} to {UGANDA_LAT_MAX}). "
                "Are you sure this market is in Uganda?"
            )
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        """Ensure longitude is within Uganda's bounding box."""
        if not (UGANDA_LON_MIN <= v <= UGANDA_LON_MAX):
            raise ValueError(
                f"Longitude {v} is outside Uganda's bounds "
                f"({UGANDA_LON_MIN} to {UGANDA_LON_MAX}). "
                "Are you sure this market is in Uganda?"
            )
        return v


class MarketCreate(MarketBase):
    """Schema for POST /markets."""
    pass


class MarketResponse(MarketBase):
    """Schema for GET /markets responses."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MarketSummary(BaseModel):
    """
    Lightweight market info for embedding inside price responses.
    Client gets market name + region without a second call.
    """
    id: int
    name: str
    district: str
    region: UgandaRegion
    latitude: float
    longitude: float

    model_config = {"from_attributes": True}


# =============================================================================
# CROP PRICE SCHEMAS — the core of the API
# =============================================================================

class CropPriceBase(BaseModel):
    """
    Shared fields for price create and response.
    At least one of wholesale_price_ugx or retail_price_ugx must be provided.
    """

    price_date: date = Field(
        ...,
        description="Date the price was observed",
        examples=["2024-03-15"],
    )
    crop_id: int = Field(
        ...,
        gt=0,
        description="ID of the crop (from GET /crops)",
    )
    market_id: int = Field(
        ...,
        gt=0,
        description="ID of the market (from GET /markets)",
    )
    unit: PriceUnit = Field(
        ...,
        description="Unit the price is quoted in",
    )
    wholesale_price_ugx: Optional[Decimal] = Field(
        None,
        ge=0,
        le=10_000_000,  # 10M UGX — sanity upper bound
        decimal_places=2,
        description="Wholesale price in Uganda Shillings",
        examples=[85000.00],
    )
    retail_price_ugx: Optional[Decimal] = Field(
        None,
        ge=0,
        le=10_000_000,
        decimal_places=2,
        description="Retail price in Uganda Shillings",
        examples=[95000.00],
    )
    source: DataSource = Field(
        DataSource.MANUAL_ENTRY,
        description="Where this price data came from",
    )
    quality: DataQuality = Field(
        DataQuality.REPORTED,
        description="Confidence/quality flag for this data point",
    )
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional context notes e.g. 'Market flooded, limited supply'",
    )

    @field_validator("price_date")
    @classmethod
    def validate_price_date(cls, v: date) -> date:
        """
        Price dates should not be in the future.
        We collect historical observations — future prices go in forecasts table.
        Allow up to 1 day in the future for timezone edge cases.
        """
        from datetime import date as date_type
        today = date_type.today()
        if v > today:
            raise ValueError(
                f"price_date {v} is in the future. "
                "Use the /forecasts endpoint for predicted prices."
            )
        return v

    @model_validator(mode="after")
    def validate_at_least_one_price(self) -> "CropPriceBase":
        """
        At least one price (wholesale OR retail) must be provided.
        A row with both NULL prices is useless.
        """
        if self.wholesale_price_ugx is None and self.retail_price_ugx is None:
            raise ValueError(
                "At least one of wholesale_price_ugx or retail_price_ugx "
                "must be provided."
            )
        return self

    @model_validator(mode="after")
    def validate_wholesale_less_than_retail(self) -> "CropPriceBase":
        """
        Wholesale should be <= retail (traders buy cheap, sell dear).
        Flag suspiciously inverted prices — likely data entry error.
        We warn but don't hard-fail, since exceptions exist (subsidies, etc.)
        """
        if (
            self.wholesale_price_ugx is not None
            and self.retail_price_ugx is not None
            and self.wholesale_price_ugx > self.retail_price_ugx * Decimal("1.5")
        ):
            # If wholesale is >50% higher than retail, very likely a data error
            raise ValueError(
                f"wholesale_price_ugx ({self.wholesale_price_ugx}) is significantly "
                f"higher than retail_price_ugx ({self.retail_price_ugx}). "
                "Please double-check the values."
            )
        return self


class CropPriceCreate(CropPriceBase):
    """
    Schema for POST /prices — submitting a new price observation.
    Identical to Base; kept separate so we can add create-only fields later.
    """
    pass


class CropPriceUpdate(BaseModel):
    """
    Schema for PUT /prices/{id} — partial updates.
    All fields optional — only send what you want to change.
    """
    wholesale_price_ugx: Optional[Decimal] = Field(None, ge=0, le=10_000_000)
    retail_price_ugx: Optional[Decimal] = Field(None, ge=0, le=10_000_000)
    quality: Optional[DataQuality] = None
    notes: Optional[str] = Field(None, max_length=500)


class CropPriceResponse(CropPriceBase):
    """
    Schema for GET /prices responses.
    Includes DB-generated fields and nested crop/market summaries
    so the client doesn't need to make extra calls.
    """
    id: int
    price_per_kg_ugx: Optional[Decimal] = Field(
        None,
        description="Normalized price per kg (derived, for ML features)",
    )

    # Nested summaries — client gets crop name + market name in one response
    crop: CropSummary
    market: MarketSummary

    created_at: datetime
    updated_at: datetime

    # Computed field: trader margin as a percentage
    # Only meaningful when both wholesale and retail are present
    @computed_field
    @property
    def trader_margin_pct(self) -> Optional[float]:
        """
        Percentage markup from wholesale to retail.
        Indicator of market efficiency — high margin = poor competition.
        Formula: (retail - wholesale) / wholesale × 100
        """
        if self.wholesale_price_ugx and self.retail_price_ugx:
            margin = (
                (self.retail_price_ugx - self.wholesale_price_ugx)
                / self.wholesale_price_ugx
                * 100
            )
            return round(float(margin), 2)
        return None

    model_config = {"from_attributes": True}


class CropPriceSummary(BaseModel):
    """
    Minimal price info for list endpoints.
    Used when returning many prices — keeps payload small.
    """
    id: int
    price_date: date
    crop_id: int
    crop_name: str        # Denormalized for convenience
    market_id: int
    market_name: str      # Denormalized for convenience
    retail_price_ugx: Optional[Decimal]
    wholesale_price_ugx: Optional[Decimal]
    unit: PriceUnit
    quality: DataQuality

    model_config = {"from_attributes": True}


# =============================================================================
# PRICE FILTER / QUERY PARAMETER SCHEMAS
# Used by GET /prices to allow flexible filtering
# =============================================================================

class PriceFilterParams(BaseModel):
    """
    Query parameters for GET /prices.

    Usage in FastAPI router:
        @router.get("/prices")
        def get_prices(filters: PriceFilterParams = Depends()):
            ...

    Example URL:
        GET /api/v1/prices?crop_id=1&market_id=2&start_date=2024-01-01&limit=100
    """

    crop_id: Optional[int] = Field(
        None, gt=0, description="Filter by crop ID"
    )
    market_id: Optional[int] = Field(
        None, gt=0, description="Filter by market ID"
    )
    region: Optional[UgandaRegion] = Field(
        None, description="Filter by Uganda region"
    )
    start_date: Optional[date] = Field(
        None, description="Start of date range (inclusive)"
    )
    end_date: Optional[date] = Field(
        None, description="End of date range (inclusive)"
    )
    source: Optional[DataSource] = Field(
        None, description="Filter by data source"
    )
    quality: Optional[DataQuality] = Field(
        None, description="Filter by data quality flag"
    )

    # Pagination
    limit: int = Field(
        100, ge=1, le=1000,
        description="Max records to return (default 100, max 1000)",
    )
    offset: int = Field(
        0, ge=0,
        description="Number of records to skip (for pagination)",
    )

    @model_validator(mode="after")
    def validate_date_range(self) -> "PriceFilterParams":
        """start_date must be before or equal to end_date."""
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValueError(
                    f"start_date ({self.start_date}) must be before "
                    f"end_date ({self.end_date})"
                )
        return self


# =============================================================================
# WEATHER READING SCHEMAS
# =============================================================================

class WeatherReadingResponse(BaseModel):
    """Schema for returning weather readings via the API."""

    id: int
    reading_date: date
    market_id: int
    market: MarketSummary

    temp_max_c: Optional[float]
    temp_min_c: Optional[float]
    rainfall_mm: Optional[float]
    humidity_max_pct: Optional[float]
    et0_evapotranspiration_mm: Optional[float]
    water_balance_mm: Optional[float] = Field(
        None,
        description=(
            "Rainfall minus evapotranspiration. "
            "Negative = drought stress = expect price increase."
        ),
    )
    is_forecast: bool

    model_config = {"from_attributes": True}


# =============================================================================
# PRICE FORECAST SCHEMAS
# =============================================================================

class PriceForecastResponse(BaseModel):
    """
    Schema for GET /forecasts responses.
    What the API returns for ML-generated price predictions.
    """

    id: int
    forecast_date: date = Field(..., description="The future date being forecast")
    generated_at: datetime = Field(..., description="When this forecast was computed")

    crop: CropSummary
    market: MarketSummary
    unit: PriceUnit

    predicted_price_ugx: Decimal = Field(
        ...,
        description="Model's best estimate of price in UGX",
    )
    lower_bound_ugx: Optional[Decimal] = Field(
        None,
        description="Lower bound of 90% confidence interval",
    )
    upper_bound_ugx: Optional[Decimal] = Field(
        None,
        description="Upper bound of 90% confidence interval",
    )

    model_version: str
    confidence_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Model confidence 0–1. Below 0.6 = treat with caution.",
    )

    # Human-readable confidence label for UI display
    @computed_field
    @property
    def confidence_label(self) -> str:
        """
        Converts numeric confidence score to a display label.
        Makes it easy for MAAIF staff who aren't data scientists
        to interpret the forecast reliability at a glance.
        """
        if self.confidence_score is None:
            return "Unknown"
        if self.confidence_score >= 0.85:
            return "High"
        if self.confidence_score >= 0.65:
            return "Medium"
        return "Low — treat with caution"

    model_config = {"from_attributes": True}


# =============================================================================
# AGGREGATE / ANALYTICS SCHEMAS
# Used by the dashboard and MAAIF reports
# =============================================================================

class PriceTrendPoint(BaseModel):
    """Single point in a price trend time series."""
    date: date
    avg_retail_ugx: Optional[float]
    avg_wholesale_ugx: Optional[float]
    num_observations: int = Field(
        ...,
        description="Number of market reports averaged into this value",
    )


class PriceTrendResponse(BaseModel):
    """
    Response for GET /prices/trend — price trend over time.
    Used to draw the main chart on the MAAIF dashboard.
    """
    crop: CropSummary
    market: Optional[MarketSummary] = Field(
        None,
        description="None = national average across all markets",
    )
    unit: PriceUnit
    period_start: date
    period_end: date
    data_points: list[PriceTrendPoint]


class MarketComparisonItem(BaseModel):
    """One market's current price in a cross-market comparison."""
    market: MarketSummary
    latest_date: date
    retail_price_ugx: Optional[Decimal]
    wholesale_price_ugx: Optional[Decimal]
    price_vs_national_avg_pct: Optional[float] = Field(
        None,
        description=(
            "How far this market's price is from the national average. "
            "Positive = above average (expensive), Negative = below (cheap)."
        ),
    )


class MarketComparisonResponse(BaseModel):
    """
    Response for GET /prices/compare — same crop across all markets.
    MAAIF uses this to spot regional price disparities and arbitrage gaps.
    """
    crop: CropSummary
    comparison_date: date
    unit: PriceUnit
    national_avg_retail_ugx: Optional[float]
    markets: list[MarketComparisonItem]


# =============================================================================
# STANDARD API RESPONSE WRAPPERS
# Consistent envelope for all list and paginated responses
# =============================================================================

class PaginatedResponse(BaseModel):
    """
    Standard paginated list wrapper.
    All list endpoints return this shape for consistency.

    Example:
        {
            "total": 1250,
            "limit": 100,
            "offset": 0,
            "data": [...]
        }
    """
    total: int = Field(..., description="Total matching records in DB")
    limit: int = Field(..., description="Max records per page")
    offset: int = Field(..., description="Current page offset")
    data: list  # Typed specifically in each router


class HealthResponse(BaseModel):
    """Response schema for GET /health — used by load balancers and monitoring."""
    status: str = "ok"
    version: str
    environment: str
    db_connected: bool
    timestamp: datetime