"""Tests for dynamic stock list fetching."""

import json
import os
import pytest
import requests
from unittest.mock import Mock, patch, MagicMock

from src.stock_list_fetcher import (
    StockListFetcher,
    StockInfo,
    IDXProvider,
    StaticFileProvider,
    ConfigProvider,
    StockListCache,
    StockFilters,
    StockListFilter,
)


class TestStockInfo:
    """Tests for StockInfo dataclass."""

    def test_creation_minimal(self):
        stock = StockInfo(ticker="BBCA", name="Bank Central Asia")
        assert stock.ticker == "BBCA"
        assert stock.name == "Bank Central Asia"
        assert stock.sector is None
        assert stock.is_lq45 is None

    def test_creation_full(self):
        stock = StockInfo(
            ticker="BBCA",
            name="Bank Central Asia",
            sector="Financial Services",
            board="Main",
            is_lq45=True,
            is_idx30=True,
        )
        assert stock.is_lq45 is True
        assert stock.is_idx30 is True
        assert stock.sector == "Financial Services"

    def test_to_dict(self):
        stock = StockInfo(ticker="BBCA", name="BCA", sector="Finance")
        data = stock.to_dict()
        assert data["ticker"] == "BBCA"
        assert data["name"] == "BCA"
        assert data["sector"] == "Finance"

    def test_from_dict(self):
        data = {"ticker": "BBRI", "name": "BRI", "is_lq45": True}
        stock = StockInfo.from_dict(data)
        assert stock.ticker == "BBRI"
        assert stock.name == "BRI"
        assert stock.is_lq45 is True


class TestIDXProvider:
    """Tests for IDX API provider."""

    def test_name(self):
        provider = IDXProvider()
        assert provider.name == "idx"

    @patch("src.stock_list_fetcher.requests.get")
    def test_fetch_stocks_success(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"Code": "BBCA", "Name": "Bank Central Asia", "Sector": "Finance"},
                {"Code": "BBRI", "Name": "Bank Rakyat Indonesia", "Sector": "Finance"},
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        provider = IDXProvider()
        stocks = provider.fetch_stocks()

        assert len(stocks) == 2
        assert stocks[0].ticker == "BBCA"
        assert stocks[1].ticker == "BBRI"

    @patch("src.stock_list_fetcher.requests.get")
    def test_fetch_stocks_network_error(self, mock_get):
        mock_get.side_effect = Exception("Network error")

        provider = IDXProvider()
        with pytest.raises(Exception, match="Network error"):
            provider.fetch_stocks()

    @patch("src.stock_list_fetcher.requests.head")
    def test_is_available_success(self, mock_head):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response

        provider = IDXProvider()
        assert provider.is_available() is True

    @patch("src.stock_list_fetcher.requests.head")
    def test_is_available_failure(self, mock_head):
        mock_head.side_effect = requests.RequestException("Connection error")

        provider = IDXProvider()
        assert provider.is_available() is False


class TestStaticFileProvider:
    """Tests for static file provider."""

    def test_name(self):
        provider = StaticFileProvider()
        assert provider.name == "static"

    def test_fetch_from_json(self, tmp_path):
        test_file = tmp_path / "test_stocks.json"
        test_data = {
            "stocks": [
                {"ticker": "BBCA", "name": "BCA"},
                {"ticker": "BBRI", "name": "BRI"},
            ]
        }
        test_file.write_text(json.dumps(test_data))

        provider = StaticFileProvider(str(test_file))
        stocks = provider.fetch_stocks()

        assert len(stocks) == 2
        assert stocks[0].ticker == "BBCA"
        assert stocks[1].ticker == "BBRI"

    def test_is_available_missing_file(self):
        provider = StaticFileProvider("/nonexistent/file.json")
        assert provider.is_available() is False

    def test_is_available_existing_file(self, tmp_path):
        test_file = tmp_path / "test_stocks.json"
        test_file.write_text('{"stocks": []}')

        provider = StaticFileProvider(str(test_file))
        assert provider.is_available() is True


class TestConfigProvider:
    """Tests for config-based provider (backward compatibility)."""

    def test_name(self):
        provider = ConfigProvider({})
        assert provider.name == "config"

    def test_fetch_from_config(self):
        config = {"universe": {"tickers": ["BBCA", "BBRI", "BMRI"]}}

        provider = ConfigProvider(config)
        stocks = provider.fetch_stocks()

        assert len(stocks) == 3
        assert stocks[0].ticker == "BBCA"
        assert stocks[1].ticker == "BBRI"
        assert stocks[2].ticker == "BMRI"

    def test_fetch_validates_tickers(self):
        config = {"universe": {"tickers": ["BBCA", "invalid123", "AB", "BBRI"]}}

        provider = ConfigProvider(config)
        stocks = provider.fetch_stocks()

        # Only valid 4-letter alphabetic tickers should be returned
        assert len(stocks) == 2
        assert stocks[0].ticker == "BBCA"
        assert stocks[1].ticker == "BBRI"

    def test_is_available_with_tickers(self):
        config = {"universe": {"tickers": ["BBCA"]}}
        provider = ConfigProvider(config)
        assert provider.is_available() is True

    def test_is_available_without_tickers(self):
        config = {"universe": {"tickers": []}}
        provider = ConfigProvider(config)
        assert provider.is_available() is False


class TestStockListCache:
    """Tests for caching mechanism."""

    def test_save_and_load(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        cache = StockListCache(cache_file=str(cache_file), cache_ttl_hours=24)

        stocks = [
            StockInfo("BBCA", "BCA"),
            StockInfo("BBRI", "BRI"),
        ]
        cache.save(stocks, "test")

        loaded = cache.load()
        assert loaded is not None
        assert len(loaded) == 2
        assert loaded[0].ticker == "BBCA"

    def test_is_valid_with_fresh_cache(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        cache = StockListCache(cache_file=str(cache_file), cache_ttl_hours=24)

        stocks = [StockInfo("BBCA", "BCA")]
        cache.save(stocks, "test")

        assert cache.is_valid() is True

    def test_is_valid_with_no_cache(self, tmp_path):
        cache_file = tmp_path / "nonexistent.json"
        cache = StockListCache(cache_file=str(cache_file), cache_ttl_hours=24)

        assert cache.is_valid() is False

    def test_is_valid_with_expired_cache(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        cache = StockListCache(cache_file=str(cache_file), cache_ttl_hours=0)

        stocks = [StockInfo("BBCA", "BCA")]
        cache.save(stocks, "test")

        # With 0 hour TTL, cache is immediately expired
        assert cache.is_valid() is False


class TestStockListFilter:
    """Tests for stock filtering."""

    def test_filter_by_index_lq45(self):
        stocks = [
            StockInfo("BBCA", "BCA", is_lq45=True),
            StockInfo("XXXX", "Unknown", is_lq45=False),
            StockInfo("BBRI", "BRI", is_lq45=True),
        ]

        filter_obj = StockListFilter()
        filters = StockFilters(index_membership="LQ45")
        result = filter_obj.apply(stocks, filters)

        assert len(result) == 2
        assert all(s.is_lq45 for s in result)

    def test_filter_by_index_idx30(self):
        stocks = [
            StockInfo("BBCA", "BCA", is_idx30=True),
            StockInfo("XXXX", "Unknown", is_idx30=False),
            StockInfo("BBRI", "BRI", is_idx30=True),
        ]

        filter_obj = StockListFilter()
        filters = StockFilters(index_membership="IDX30")
        result = filter_obj.apply(stocks, filters)

        assert len(result) == 2
        assert all(s.is_idx30 for s in result)

    def test_filter_max_stocks(self):
        stocks = [StockInfo(f"STK{i:01d}", f"Stock {i}") for i in range(10)]

        filter_obj = StockListFilter()
        filters = StockFilters(max_stocks=5)
        result = filter_obj.apply(stocks, filters)

        assert len(result) == 5

    def test_filter_exclude_tickers(self):
        stocks = [
            StockInfo("BBCA", "BCA"),
            StockInfo("BBRI", "BRI"),
            StockInfo("BMRI", "Mandiri"),
        ]

        filter_obj = StockListFilter()
        filters = StockFilters(exclude_tickers=["BBRI"])
        result = filter_obj.apply(stocks, filters)

        assert len(result) == 2
        assert all(s.ticker != "BBRI" for s in result)

    def test_filter_by_sector(self):
        stocks = [
            StockInfo("BBCA", "BCA", sector="Finance"),
            StockInfo("ADRO", "Adaro", sector="Energy"),
            StockInfo("BBRI", "BRI", sector="Finance"),
        ]

        filter_obj = StockListFilter()
        filters = StockFilters(sectors=["Finance"])
        result = filter_obj.apply(stocks, filters)

        assert len(result) == 2
        assert all(s.sector == "Finance" for s in result)


class TestStockListFetcher:
    """Integration tests for main fetcher."""

    def test_fallback_to_config(self):
        """When other providers fail, should use config tickers."""
        config = {
            "universe": {
                "mode": "dynamic",
                "source_priority": ["config"],
                "cache_enabled": False,
                "tickers": ["BBCA", "BBRI"],
            }
        }

        fetcher = StockListFetcher(config)
        tickers = fetcher.fetch(use_cache=False)

        assert tickers == ["BBCA", "BBRI"]

    def test_static_provider_used(self, tmp_path):
        """Test that static file provider works."""
        test_file = tmp_path / "stocks.json"
        test_data = {
            "stocks": [
                {"ticker": "AAAA", "name": "Stock A"},
                {"ticker": "BBBB", "name": "Stock B"},
            ]
        }
        test_file.write_text(json.dumps(test_data))

        config = {
            "universe": {
                "mode": "dynamic",
                "source_priority": ["static", "config"],
                "static_file": str(test_file),
                "cache_enabled": False,
                "tickers": ["XXXX"],
            }
        }

        fetcher = StockListFetcher(config)
        tickers = fetcher.fetch(use_cache=False)

        assert tickers == ["AAAA", "BBBB"]

    def test_filters_applied(self):
        """Test that filters are applied to results."""
        config = {
            "universe": {
                "mode": "dynamic",
                "source_priority": ["config"],
                "cache_enabled": False,
                "max_stocks": 2,
                "tickers": ["BBCA", "BBRI", "BMRI", "BBNI"],
            }
        }

        fetcher = StockListFetcher(config)
        tickers = fetcher.fetch(use_cache=False)

        assert len(tickers) == 2

    def test_exclude_tickers_filter(self):
        """Test that exclude_tickers filter works."""
        config = {
            "universe": {
                "mode": "dynamic",
                "source_priority": ["config"],
                "cache_enabled": False,
                "exclude_tickers": ["BBRI"],
                "tickers": ["BBCA", "BBRI", "BMRI"],
            }
        }

        fetcher = StockListFetcher(config)
        tickers = fetcher.fetch(use_cache=False)

        assert "BBRI" not in tickers
        assert len(tickers) == 2

    @patch.object(IDXProvider, "fetch_stocks")
    @patch.object(IDXProvider, "is_available", return_value=True)
    def test_idx_provider_used_first(self, mock_available, mock_fetch):
        """Test that IDX provider is tried first when in priority."""
        mock_fetch.return_value = [
            StockInfo("AAAA", "Stock A"),
            StockInfo("BBBB", "Stock B"),
        ]

        config = {
            "universe": {
                "mode": "dynamic",
                "source_priority": ["idx", "config"],
                "cache_enabled": False,
                "tickers": ["XXXX"],
            }
        }

        fetcher = StockListFetcher(config)
        tickers = fetcher.fetch(use_cache=False)

        assert tickers == ["AAAA", "BBBB"]
        mock_fetch.assert_called_once()

    def test_cache_used_when_valid(self, tmp_path):
        """Test that cache is used when valid."""
        cache_file = tmp_path / "cache.json"
        cache_data = {
            "cached_at": "2026-01-22 10:00:00",
            "source": "test",
            "count": 2,
            "stocks": [
                {"ticker": "CCCC", "name": "Cached Stock C"},
                {"ticker": "DDDD", "name": "Cached Stock D"},
            ],
        }
        cache_file.write_text(json.dumps(cache_data))

        config = {
            "universe": {
                "mode": "dynamic",
                "source_priority": ["config"],
                "cache_enabled": True,
                "cache_ttl_hours": 24,
                "tickers": ["XXXX"],
            }
        }

        # Patch the cache file path
        fetcher = StockListFetcher(config)
        fetcher.cache.cache_file = str(cache_file)

        tickers = fetcher.fetch(use_cache=True)

        assert tickers == ["CCCC", "DDDD"]
