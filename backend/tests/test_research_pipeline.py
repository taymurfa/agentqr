"""Unit tests for the /api/command research pipeline.

Cover the deterministic parts only — no DB, no yfinance, no network.
"""

import numpy as np
import pandas as pd
import pytest

from src.agents.research_pipeline import (
    parse_command,
    run_backtest,
    assess_risk,
    STRATEGY_TEMPLATES,
)


@pytest.fixture
def synthetic_prices() -> dict[str, pd.DataFrame]:
    np.random.seed(7)
    idx = pd.date_range("2022-01-03", periods=420, freq="B")
    out = {}
    for ticker in ["AAPL", "MSFT", "NVDA", "TSLA"]:
        rets = np.random.randn(len(idx)) * 0.015 + 0.0005
        close = 100 * np.exp(np.cumsum(rets))
        out[ticker] = pd.DataFrame({"Close": close}, index=idx)
    return out


def test_parse_command_default_universe():
    out = parse_command("research a momentum strategy")
    assert out["signal_type"] == "momentum"
    assert out["universe"] == ["AAPL", "MSFT", "NVDA", "TSLA"]
    assert out["years"] == 2


def test_parse_command_extracts_tickers_and_years():
    out = parse_command(
        "Research a momentum strategy for AAPL, MSFT, NVDA, and TSLA over the last 2 years."
    )
    assert out["signal_type"] == "momentum"
    assert out["universe"] == ["AAPL", "MSFT", "NVDA", "TSLA"]
    assert out["years"] == 2


def test_parse_command_mean_reversion():
    out = parse_command("mean reversion on GOOGL and AMD over 3 years")
    assert out["signal_type"] == "mean_reversion"
    assert out["universe"] == ["GOOGL", "AMD"]
    assert out["years"] == 3


def test_parse_command_volatility_breakout_alias():
    out = parse_command("vol breakout on QQQ")
    assert out["signal_type"] == "volatility_breakout"
    assert "QQQ" in out["universe"]


def test_backtest_returns_required_metrics(synthetic_prices):
    bt = run_backtest(synthetic_prices, "momentum", lookback=20, top_n=2)
    assert "error" not in bt
    required = {
        "cumulative_return",
        "annualized_return",
        "annualized_volatility",
        "sharpe_ratio",
        "max_drawdown",
        "win_rate",
        "avg_turnover",
        "trading_days",
        "equity_curve",
    }
    assert required.issubset(bt.keys())
    assert bt["trading_days"] > 100
    assert -100 <= bt["max_drawdown"] <= 0
    assert len(bt["equity_curve"]) > 0
    assert all("date" in p and "equity" in p for p in bt["equity_curve"])


def test_backtest_no_lookahead(synthetic_prices):
    # Yesterday's weights * today's returns means first lookback bars are zero/NaN.
    bt = run_backtest(synthetic_prices, "momentum", lookback=20, top_n=2)
    assert bt["trading_days"] == len(synthetic_prices["AAPL"]) - 20


def test_backtest_insufficient_history_errors():
    short = {"AAPL": pd.DataFrame({"Close": [100, 101, 102]}, index=pd.date_range("2024-01-01", periods=3))}
    bt = run_backtest(short, "momentum", lookback=20, top_n=1)
    assert "error" in bt


def test_assess_risk_rejects_insufficient_data():
    assert assess_risk({"error": "x"}, ["AAPL"]) == {
        "risk_status": "rejected",
        "risk_flags": ["insufficient_data"],
    }


def test_assess_risk_warns_on_negative_sharpe():
    bt = {
        "max_drawdown": -5.0,
        "annualized_volatility": 15.0,
        "sharpe_ratio": -0.2,
        "avg_turnover": 0.1,
    }
    r = assess_risk(bt, ["AAPL", "MSFT", "NVDA", "TSLA"])
    assert r["risk_status"] == "warning"
    assert any("negative_sharpe" in f for f in r["risk_flags"])


def test_assess_risk_approves_clean_backtest():
    bt = {
        "max_drawdown": -8.0,
        "annualized_volatility": 18.0,
        "sharpe_ratio": 1.2,
        "avg_turnover": 0.2,
    }
    r = assess_risk(bt, ["AAPL", "MSFT", "NVDA", "TSLA"])
    assert r["risk_status"] == "approved"
    assert r["risk_flags"] == []


def test_assess_risk_flags_short_sample():
    bt = {
        "max_drawdown": -3.0,
        "annualized_volatility": 15.0,
        "sharpe_ratio": 1.0,
        "avg_turnover": 0.2,
        "trading_days": 30,
    }
    r = assess_risk(bt, ["AAPL", "MSFT", "NVDA", "TSLA"])
    assert "short_sample_size" in r["risk_flags"]


def test_assess_risk_flags_concentration_single_name():
    bt = {
        "max_drawdown": -5.0,
        "annualized_volatility": 18.0,
        "sharpe_ratio": 1.1,
        "avg_turnover": 0.1,
    }
    r = assess_risk(bt, ["AAPL"])
    assert any("high_concentration" in f for f in r["risk_flags"])


def test_assess_risk_rejects_on_extreme_drawdown():
    bt = {
        "max_drawdown": -30.0,
        "annualized_volatility": 25.0,
        "sharpe_ratio": 0.5,
        "avg_turnover": 0.2,
    }
    r = assess_risk(bt, ["AAPL", "MSFT", "NVDA", "TSLA"])
    assert r["risk_status"] == "rejected"
