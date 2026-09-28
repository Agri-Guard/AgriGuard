import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers import forecasts as f
from backend.app.services.aliases import resolve_series

client = TestClient(app)


def _df(rows):
    df = pd.DataFrame(rows, columns=["date", "commodity", "market", "price"])
    df["date"] = pd.to_datetime(df["date"])
    return df


DF = _df(
    [("2026-01-01", "Maize", "Owino", 1000), ("2026-02-01", "Maize", "Owino", 1100),
     ("2026-01-01", "Maize", "Lira", 500),
     ("2026-01-01", "Maize (White)", "Mbarara", 900), ("2026-02-01", "Maize (White)", "Mbarara", 950),
     ("2026-01-01", "Beans", "Mbarara", 3000)]
)


def test_exact_match_wins_and_is_not_aliased():
    r = resolve_series(DF, "Maize", "Lira")
    assert r.market == "Lira" and r.aliased is False


def test_kampala_resolves_to_owino():
    r = resolve_series(DF, "Maize", "Kampala")
    assert r.market == "Owino" and r.aliased is True and len(r.subset) == 2


def test_maize_resolves_to_white_maize_in_mbarara():
    r = resolve_series(DF, "maize", "mbarara")
    assert r.commodity == "Maize (White)" and r.market == "Mbarara"


def test_freshest_variant_wins_over_discontinued_exact_name():
    df = _df([("2022-05-01", "Maize", "Owino", 1249), ("2022-04-01", "Maize", "Owino", 1200),
              ("2026-03-01", "Maize (White)", "Owino", 2100), ("2026-02-01", "Maize (White)", "Owino", 2000)])
    r = resolve_series(df, "Maize", "Kampala")
    assert r.commodity == "Maize (White)" and r.market == "Owino" and r.aliased is True


def test_ties_go_to_typed_name():
    df = _df([("2026-03-01", "Maize", "Lira", 500), ("2026-03-01", "Maize (White)", "Lira", 600)])
    assert resolve_series(df, "Maize", "Lira").commodity == "Maize"


def test_no_match_returns_none_rather_than_another_market():
    assert resolve_series(DF, "Maize", "Gulu") is None
    assert resolve_series(DF, "Cassava", "Kampala") is None


def test_resolve_subset_flags_true_fallback():
    r = f._resolve_subset(DF, "Maize", "Gulu")
    assert r.kind == "fallback" and "NOT a Gulu forecast" in r.note


def test_resolve_subset_alias_kind_has_note():
    r = f._resolve_subset(DF, "Maize", "Kampala")
    assert r.kind == "alias" and r.market == "Owino" and r.note


def test_resolve_subset_exact_has_no_note():
    r = f._resolve_subset(DF, "Maize", "Lira")
    assert r.kind == "exact" and r.note is None


# ---- need the real WFP CSV to be found by your app (see note below) ---------

def test_forecast_endpoint_mbarara_maize_is_really_mbarara():
    body = client.get("/forecasts/Maize", params={"market": "Mbarara", "horizon": 7}).json()
    assert body["market"] == "Mbarara" and body["market_fallback"] is False


def test_forecast_endpoint_flags_real_fallback():
    body = client.get("/forecasts/Maize", params={"market": "Nowhereville", "horizon": 7}).json()
    assert body["market_fallback"] is True
    assert "NOT a Nowhereville forecast" in body["market_note"]


def test_compare_skips_fallback_markets_instead_of_duplicating():
    body = client.get("/forecasts/compare/Maize",
                      params={"markets": "Mbarara,Nowhereville,Elsewhere", "horizon": 7}).json()
    assert [r["market"] for r in body["results"]] == ["Mbarara"]
    assert set(body["skipped_markets"]) == {"Nowhereville", "Elsewhere"}


def test_ussd_maize_kampala_returns_price_not_2022():
    r = client.get("/ussd/simulate", params={"text": "1*Maize*1"})
    assert r.text.startswith("END Maize | Kampala") and "Price: UGX" in r.text
    assert "2022" not in r.text


def test_ussd_maize_mbarara_returns_price():
    assert "Price: UGX" in client.get("/ussd/simulate", params={"text": "1*Maize*2"}).text