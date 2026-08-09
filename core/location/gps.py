"""EXIF GPS validation and comparison with folder-derived location."""

import subprocess
import logging
from dataclasses import dataclass
from config.constants import SETTINGS_DIR

logger = logging.getLogger(__name__)


@dataclass
class GPSInfo:
    """GPS information extracted from file metadata."""
    latitude: float = 0.0
    longitude: float = 0.0
    has_gps: bool = False
    altitude: float = 0.0
    raw_data: dict = None
    # Location names from EXIF (IPTC/XMP)
    exif_city: str = ''
    exif_state: str = ''
    exif_country: str = ''
    exif_sublocation: str = ''
    exif_region: str = ''

    def __post_init__(self):
        if self.raw_data is None:
            self.raw_data = {}

    @property
    def has_exif_location(self) -> bool:
        """Check if any EXIF location names are present."""
        return bool(self.exif_city or self.exif_country or self.exif_state or self.exif_sublocation)


class GPSValidator:
    """Validates EXIF GPS coordinates against folder-derived locations."""

    def __init__(self, exiftool_path: str = ''):
        self._exiftool_path = exiftool_path or self._find_exiftool()

    def _find_exiftool(self) -> str:
        """Find exiftool binary, checking bundled location first."""
        # Check bundled exiftool
        bundled = None
        if __import__('sys').platform == 'win32':
            bundled = __import__('os').path.join(SETTINGS_DIR, 'exiftool', 'exiftool.exe')
        else:
            bundled = __import__('os').path.join(SETTINGS_DIR, 'exiftool', 'exiftool')

        if bundled and __import__('os').path.exists(bundled):
            return bundled

        # Fall back to system exiftool
        return 'exiftool'

    def extract_gps(self, file_path: str) -> GPSInfo:
        """Extract GPS coordinates and location names from a file using exiftool."""
        try:
            result = subprocess.run(
                [self._exiftool_path, '-json', '-GPSLatitude', '-GPSLongitude',
                 '-GPSAltitude', '-City', '-State', '-Province', '-Country',
                 '-CountryCode', '-Sublocation', '-Region', '-n', file_path],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                logger.debug(f"exiftool error for {file_path}: {result.stderr}")
                return GPSInfo()

            import json
            data = json.loads(result.stdout)
            if not data:
                return GPSInfo()

            info = data[0]
            lat = float(info.get('GPSLatitude', 0) or 0)
            lon = float(info.get('GPSLongitude', 0) or 0)
            alt = float(info.get('GPSAltitude', 0) or 0)
            has_gps = abs(lat) > 0.0 or abs(lon) > 0.0

            # Extract location names from EXIF/IPTC
            exif_city = (info.get('City', '') or '').strip()
            exif_sublocation = (info.get('Sublocation', '') or '').strip()
            exif_state = (info.get('State', '') or info.get('Province', '') or '').strip()
            exif_country = (info.get('Country', '') or '').strip()
            exif_region = (info.get('Region', '') or '').strip()

            return GPSInfo(
                latitude=lat,
                longitude=lon,
                altitude=alt,
                has_gps=has_gps,
                raw_data=info,
                exif_city=exif_city,
                exif_state=exif_state,
                exif_country=exif_country,
                exif_sublocation=exif_sublocation,
                exif_region=exif_region,
            )
        except subprocess.TimeoutExpired:
            logger.warning(f"exiftool timed out for {file_path}")
            return GPSInfo()
        except Exception as e:
            logger.warning(f"Error extracting GPS from {file_path}: {e}")
            return GPSInfo()

    def validate(self, gps: GPSInfo, folder_country: str, folder_city: str) -> dict:
        """Validate GPS against folder-derived location.

        Returns dict with validation result and details.
        """
        result = {
            'gps_available': gps.has_gps,
            'folder_location': f"{folder_city}, {folder_country}" if folder_city else folder_country,
            'consistent': True,
            'message': '',
        }

        if not gps.has_gps:
            result['consistent'] = True
            result['message'] = 'No GPS data in file'
            return result

        # Basic validation: if GPS coordinates are zero or very close to origin
        if abs(gps.latitude) < 0.001 and abs(gps.longitude) < 0.001:
            result['consistent'] = True
            result['message'] = 'GPS coordinates are near-zero (likely invalid)'
            return result

        # For full validation, we'd reverse-geocode the coordinates
        # This is a lightweight check; full geocoding can be added later
        result['message'] = 'GPS present (full geocoding validation requires network)'

        return result
