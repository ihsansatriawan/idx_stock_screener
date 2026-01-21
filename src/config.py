"""Configuration loader and validator for IDX Stock Screener."""

import os
from typing import Dict, Tuple
import yaml


def load_config(path: str = "config.yaml") -> dict:
    """
    Load configuration from YAML file.

    Args:
        path: Path to config file (default: config.yaml)

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML is malformed
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Please copy config.yaml.example to config.yaml and edit with your settings."
        )

    try:
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Error parsing config.yaml: {e}")

    return config


def validate_config(config: dict) -> Tuple[bool, str]:
    """
    Validate configuration has all required fields with valid values.

    Args:
        config: Configuration dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check Google Sheets settings
    if config.get('google_sheets', {}).get('enabled'):
        gs = config.get('google_sheets', {})

        if not gs.get('sheet_id'):
            return False, "google_sheets.sheet_id is required when Google Sheets is enabled"

        if 'YOUR_GOOGLE_SHEET_ID_HERE' in gs.get('sheet_id', ''):
            return False, "Please replace YOUR_GOOGLE_SHEET_ID_HERE with your actual Google Sheet ID"

        creds_path = gs.get('credentials_path', '')
        if not creds_path:
            return False, "google_sheets.credentials_path is required"

    # Check universe
    tickers = config.get('universe', {}).get('tickers', [])
    if not tickers:
        return False, "universe.tickers cannot be empty"

    if not isinstance(tickers, list):
        return False, "universe.tickers must be a list"

    if len(tickers) != 20:
        return False, f"universe.tickers should have 20 stocks (found {len(tickers)})"

    # Check risk management
    max_sl = config.get('risk', {}).get('max_sl_percent')
    if max_sl is None:
        return False, "risk.max_sl_percent is required"

    if not isinstance(max_sl, (int, float)) or max_sl <= 0 or max_sl > 5:
        return False, f"risk.max_sl_percent must be between 0 and 5 (found {max_sl})"

    min_rr = config.get('risk', {}).get('min_rr_ratio')
    if min_rr is None:
        return False, "risk.min_rr_ratio is required"

    if not isinstance(min_rr, (int, float)) or min_rr < 1.0:
        return False, f"risk.min_rr_ratio must be >= 1.0 (found {min_rr})"

    # Check technical indicator parameters
    required_paths = [
        ('technical', 'supertrend', 'period'),
        ('technical', 'supertrend', 'multiplier'),
        ('technical', 'rsi', 'period'),
        ('technical', 'bollinger_bands', 'period'),
        ('technical', 'macd', 'fast'),
        ('technical', 'macd', 'slow'),
        ('technical', 'ema', 'periods'),
    ]

    for path_parts in required_paths:
        current = config
        for part in path_parts:
            if part not in current:
                path_str = '.'.join(path_parts)
                return False, f"Required config field missing: {path_str}"
            current = current[part]

    return True, ""


def get_nested(config: dict, *keys, default=None):
    """
    Safely get nested config value.

    Args:
        config: Configuration dictionary
        *keys: Keys to traverse
        default: Default value if key not found

    Returns:
        Value at nested key or default

    Example:
        get_nested(config, 'technical', 'supertrend', 'period')
    """
    current = config
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current
