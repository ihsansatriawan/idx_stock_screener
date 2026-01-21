"""Dynamic stock list fetching from multiple sources for IDX stocks."""

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any

import requests

from src.logger import get_logger

logger = get_logger()


@dataclass
class StockInfo:
    """Stock information from data source."""
    ticker: str
    name: str
    sector: Optional[str] = None
    board: Optional[str] = None
    market_cap: Optional[float] = None
    listing_date: Optional[str] = None
    is_lq45: Optional[bool] = None
    is_idx30: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StockInfo':
        """Create from dictionary."""
        return cls(
            ticker=data.get('ticker', ''),
            name=data.get('name', ''),
            sector=data.get('sector'),
            board=data.get('board'),
            market_cap=data.get('market_cap'),
            listing_date=data.get('listing_date'),
            is_lq45=data.get('is_lq45'),
            is_idx30=data.get('is_idx30'),
        )


class StockListProvider(ABC):
    """Abstract base class for stock list data sources."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @abstractmethod
    def fetch_stocks(self) -> List[StockInfo]:
        """Fetch stock list from source. Raises on failure."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and reachable."""
        pass


class IDXProvider(StockListProvider):
    """Fetches stock list from IDX official API (idx.co.id)."""

    BASE_URL = "https://www.idx.co.id/primary/StockData/GetSecuritiesStock"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.idx.co.id/en/market-data/stocks-data/stock-list/',
    }

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "idx"

    def fetch_stocks(self) -> List[StockInfo]:
        """
        Fetch all stocks from IDX API with pagination.

        Returns:
            List of StockInfo objects

        Raises:
            Exception: If API call fails
        """
        stocks = []
        start = 0
        length = 100

        while True:
            params = {
                'start': start,
                'length': length,
                'code': '',
                'sector': '',
                'board': '',
            }

            try:
                response = requests.get(
                    self.BASE_URL,
                    params=params,
                    headers=self.HEADERS,
                    timeout=self.timeout
                )
                response.raise_for_status()
                data = response.json()

                records = data.get('data', [])
                if not records:
                    break

                for record in records:
                    stock = StockInfo(
                        ticker=record.get('Code', '').strip().upper(),
                        name=record.get('Name', ''),
                        sector=record.get('Sector', ''),
                        board=record.get('Board', ''),
                        listing_date=record.get('ListingDate'),
                    )
                    if stock.ticker:
                        stocks.append(stock)

                if len(records) < length:
                    break

                start += length
                time.sleep(0.5)  # Rate limiting

            except requests.RequestException as e:
                if stocks:
                    logger.warning(f"IDX API pagination stopped: {e}")
                    break
                raise

        logger.info(f"IDX API returned {len(stocks)} stocks")
        return stocks

    def is_available(self) -> bool:
        """Check if IDX API is reachable."""
        try:
            response = requests.head(
                "https://www.idx.co.id",
                timeout=5,
                headers=self.HEADERS
            )
            return response.status_code < 500
        except requests.RequestException:
            return False


class StaticFileProvider(StockListProvider):
    """Loads stock list from local JSON file."""

    def __init__(self, file_path: str = "data/idx_stocks.json"):
        self.file_path = file_path

    @property
    def name(self) -> str:
        return "static"

    def fetch_stocks(self) -> List[StockInfo]:
        """
        Load stock list from JSON file.

        Returns:
            List of StockInfo objects

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If JSON is invalid
        """
        with open(self.file_path, 'r') as f:
            data = json.load(f)

        stocks = []
        for record in data.get('stocks', []):
            stock = StockInfo.from_dict(record)
            if stock.ticker:
                stocks.append(stock)

        logger.info(f"Static file loaded {len(stocks)} stocks from {self.file_path}")
        return stocks

    def is_available(self) -> bool:
        """Check if static file exists."""
        return os.path.exists(self.file_path)


class ConfigProvider(StockListProvider):
    """Uses hardcoded tickers from config.yaml (backward compatibility)."""

    def __init__(self, config: dict):
        self.config = config

    @property
    def name(self) -> str:
        return "config"

    def fetch_stocks(self) -> List[StockInfo]:
        """
        Convert config tickers to StockInfo objects.

        Returns:
            List of StockInfo objects
        """
        tickers = self.config.get('universe', {}).get('tickers', [])
        stocks = []

        for ticker in tickers:
            ticker = ticker.strip().upper()
            if ticker and ticker.isalpha() and len(ticker) == 4:
                stocks.append(StockInfo(ticker=ticker, name=ticker))

        logger.info(f"Config provider loaded {len(stocks)} tickers")
        return stocks

    def is_available(self) -> bool:
        """Check if config has tickers."""
        tickers = self.config.get('universe', {}).get('tickers', [])
        return bool(tickers)


class StockListCache:
    """File-based cache for stock lists."""

    def __init__(self, cache_file: str = "data/stock_list_cache.json", cache_ttl_hours: int = 24):
        self.cache_file = cache_file
        self.cache_ttl = cache_ttl_hours * 3600

    def is_valid(self) -> bool:
        """Check if cache exists and is not expired."""
        if not os.path.exists(self.cache_file):
            return False

        cache_time = os.path.getmtime(self.cache_file)
        age = time.time() - cache_time
        return age < self.cache_ttl

    def load(self) -> Optional[List[StockInfo]]:
        """Load cached stock list."""
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)

            stocks = [StockInfo.from_dict(s) for s in data.get('stocks', [])]
            logger.debug(f"Cache loaded {len(stocks)} stocks")
            return stocks
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Cache load failed: {e}")
            return None

    def save(self, stocks: List[StockInfo], source: str):
        """Save stock list to cache with metadata."""
        os.makedirs(os.path.dirname(self.cache_file) or '.', exist_ok=True)

        data = {
            'cached_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'source': source,
            'count': len(stocks),
            'stocks': [s.to_dict() for s in stocks],
        }

        with open(self.cache_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.debug(f"Cache saved {len(stocks)} stocks from {source}")


@dataclass
class StockFilters:
    """Filters to apply to stock list."""
    index_membership: Optional[str] = None
    sectors: Optional[List[str]] = None
    boards: Optional[List[str]] = None
    min_market_cap: Optional[float] = None
    max_stocks: Optional[int] = None
    exclude_tickers: Optional[List[str]] = None


class StockListFilter:
    """Applies filters to stock list."""

    def apply(self, stocks: List[StockInfo], filters: StockFilters) -> List[StockInfo]:
        """Apply all configured filters."""
        result = stocks

        if filters.index_membership:
            result = self._filter_by_index(result, filters.index_membership)

        if filters.sectors:
            result = [s for s in result if s.sector in filters.sectors]

        if filters.boards:
            result = [s for s in result if s.board in filters.boards]

        if filters.min_market_cap:
            result = [s for s in result if s.market_cap and s.market_cap >= filters.min_market_cap]

        if filters.exclude_tickers:
            exclude_set = set(t.upper() for t in filters.exclude_tickers)
            result = [s for s in result if s.ticker not in exclude_set]

        if filters.max_stocks and len(result) > filters.max_stocks:
            result = result[:filters.max_stocks]

        return result

    def _filter_by_index(self, stocks: List[StockInfo], index: str) -> List[StockInfo]:
        """Filter stocks by index membership."""
        index_upper = index.upper()

        if index_upper == 'LQ45':
            return [s for s in stocks if s.is_lq45]
        elif index_upper == 'IDX30':
            return [s for s in stocks if s.is_idx30]
        else:
            logger.warning(f"Unknown index filter: {index}")
            return stocks


class StockListFetcher:
    """
    Main class for fetching dynamic stock universe.
    Manages providers, caching, and filtering.
    """

    def __init__(self, config: dict):
        self.config = config
        self.universe_config = config.get('universe', {})

        cache_ttl = self.universe_config.get('cache_ttl_hours', 24)
        self.cache = StockListCache(cache_ttl_hours=cache_ttl)
        self.filter = StockListFilter()
        self.providers = self._init_providers()

    def _init_providers(self) -> List[StockListProvider]:
        """Initialize providers in priority order from config."""
        provider_priority = self.universe_config.get('source_priority', ['config'])
        providers = []

        for name in provider_priority:
            if name == 'idx':
                providers.append(IDXProvider())
            elif name == 'static':
                file_path = self.universe_config.get('static_file', 'data/idx_stocks.json')
                providers.append(StaticFileProvider(file_path))
            elif name == 'config':
                providers.append(ConfigProvider(self.config))

        if not providers:
            providers.append(ConfigProvider(self.config))

        return providers

    def fetch(self, use_cache: bool = True) -> List[str]:
        """
        Fetch stock list with caching and fallback.

        Args:
            use_cache: Whether to use cached data if valid

        Returns:
            List of validated ticker symbols (without .JK suffix)

        Raises:
            RuntimeError: If all providers fail
        """
        cache_enabled = self.universe_config.get('cache_enabled', True)

        if use_cache and cache_enabled and self.cache.is_valid():
            logger.info("Loading stock list from cache")
            stocks = self.cache.load()
            if stocks:
                return self._apply_filters_and_validate(stocks)

        for provider in self.providers:
            if not provider.is_available():
                logger.debug(f"Provider {provider.name} not available, skipping")
                continue

            try:
                logger.info(f"Fetching stock list from {provider.name}")
                stocks = provider.fetch_stocks()

                if stocks:
                    if cache_enabled:
                        self.cache.save(stocks, provider.name)
                    return self._apply_filters_and_validate(stocks)

            except Exception as e:
                logger.warning(f"Provider {provider.name} failed: {e}")
                continue

        raise RuntimeError(
            "Failed to fetch stock list from any provider. "
            "Check network connectivity or add tickers to config.yaml"
        )

    def _apply_filters_and_validate(self, stocks: List[StockInfo]) -> List[str]:
        """Apply filters and return validated ticker list."""
        filters = StockFilters(
            index_membership=self.universe_config.get('index_filter'),
            sectors=self.universe_config.get('sector_filter'),
            max_stocks=self.universe_config.get('max_stocks'),
            exclude_tickers=self.universe_config.get('exclude_tickers', []),
        )

        filtered = self.filter.apply(stocks, filters)

        tickers = []
        for stock in filtered:
            ticker = stock.ticker.strip().upper()
            if len(ticker) == 4 and ticker.isalpha():
                tickers.append(ticker)
            else:
                logger.warning(f"Invalid ticker format: {ticker}, skipping")

        logger.info(f"Filtered to {len(tickers)} valid tickers")
        return tickers
