"""Settings management with JSON persistence."""

import json
import os
import logging
from typing import Any

from config.constants import DEFAULT_SETTINGS, SETTINGS_FILE, SETTINGS_DIR

logger = logging.getLogger(__name__)


class Settings:
    """Manages application settings with JSON persistence."""

    def __init__(self, path: str = SETTINGS_FILE):
        self._path = path
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load settings from disk, merging with defaults."""
        self._data = dict(DEFAULT_SETTINGS)
        if os.path.exists(self._path):
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                self._data.update(user_data)
                logger.info(f"Settings loaded from {self._path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Error loading settings: {e}")

    def save(self) -> None:
        """Persist settings to disk."""
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        logger.debug(f"Settings saved to {self._path}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value (does not persist until save())."""
        self._data[key] = value

    def update(self, data: dict[str, Any]) -> None:
        """Update multiple settings at once."""
        self._data.update(data)

    def to_dict(self) -> dict[str, Any]:
        """Return a copy of all settings."""
        return dict(self._data)

    def reset(self) -> None:
        """Reset to defaults without persisting."""
        self._data = dict(DEFAULT_SETTINGS)

    @property
    def vision_endpoint(self) -> str:
        return self._data.get('vision_endpoint', '')

    @property
    def vision_api_key(self) -> str:
        return self._data.get('vision_api_key', '')

    @property
    def vision_model(self) -> str:
        return self._data.get('vision_model', 'auto')

    @property
    def text_endpoint(self) -> str:
        return self._data.get('text_endpoint', '')

    @property
    def text_api_key(self) -> str:
        return self._data.get('text_api_key', '')

    @property
    def text_model(self) -> str:
        return self._data.get('text_model', '')

    @property
    def max_workers(self) -> int:
        return int(self._data.get('max_workers', 4))

    @property
    def output_format(self) -> str:
        return self._data.get('output_format', 'embedded')

    @property
    def target_agencies(self) -> list[str]:
        return self._data.get('target_agencies', ['adobe_stock'])

    @property
    def auto_learn_location(self) -> bool:
        return self._data.get('auto_learn_location', True)

    def validate_endpoints(self) -> list[str]:
        """Validate required settings. Returns list of missing fields."""
        missing = []
        if not self.vision_endpoint:
            missing.append('vision_endpoint')
        if not self.text_endpoint:
            missing.append('text_endpoint')
        if not self.text_model:
            missing.append('text_model')
        return missing
