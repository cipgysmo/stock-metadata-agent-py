"""Metadata writing via exiftool for IPTC/XMP embedding."""

import os
import subprocess
import logging
from config.constants import SETTINGS_DIR

logger = logging.getLogger(__name__)

# Module-level cache for exiftool path
_CACHED_EXIFTOOL_PATH = None


def _find_and_cache_exiftool() -> str:
    """Find exiftool and cache the result."""
    global _CACHED_EXIFTOOL_PATH
    if _CACHED_EXIFTOOL_PATH:
        return _CACHED_EXIFTOOL_PATH

    import sys
    platform = sys.platform
    exe = 'exiftool.exe' if platform == 'win32' else 'exiftool'

    # Determine base directory (handles PyInstaller bundled app)
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    bundled_paths = [
        os.path.join(base_dir, '..', 'resources', f'exiftool-{platform}', exe),
        os.path.join(base_dir, '..', '..', 'resources', f'exiftool-{platform}', exe),
        os.path.join(base_dir, '..', 'resources', 'exiftool-mac', exe),
        os.path.join(base_dir, '..', '..', 'resources', 'exiftool-mac', exe),
        os.path.join(base_dir, '..', 'resources', 'exiftool-win', exe),
        os.path.join(base_dir, '..', '..', 'resources', 'exiftool-win', exe),
        os.path.join(SETTINGS_DIR, 'exiftool', exe),
        os.path.join('resources', f'exiftool-{platform}', exe),
        os.path.join('resources', 'exiftool-mac', exe),
        os.path.join('resources', 'exiftool-win', exe),
    ]
    for path in bundled_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            _CACHED_EXIFTOOL_PATH = abs_path
            return abs_path

    _CACHED_EXIFTOOL_PATH = 'exiftool'
    return 'exiftool'


class MetadataWriter:
    """Writes metadata to files using exiftool."""

    def __init__(self, exiftool_path: str = ''):
        self._exiftool = exiftool_path or _find_and_cache_exiftool()
        logger.info(f"MetadataWriter using exiftool: {self._exiftool}")

    def _find_exiftool(self) -> str:
        """Find exiftool: bundled first, then system."""
        import sys
        platform = sys.platform

        exe = 'exiftool.exe' if platform == 'win32' else 'exiftool'

        # Determine base directory (handles PyInstaller bundled app)
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        # Check bundled locations in priority order
        bundled_paths = [
            # In resources subdir of project (1 and 2 levels up)
            os.path.join(base_dir, '..', 'resources', f'exiftool-{platform}', exe),
            os.path.join(base_dir, '..', '..', 'resources', f'exiftool-{platform}', exe),
            os.path.join(base_dir, '..', 'resources', 'exiftool-mac', exe),
            os.path.join(base_dir, '..', '..', 'resources', 'exiftool-mac', exe),
            os.path.join(base_dir, '..', 'resources', 'exiftool-win', exe),
            os.path.join(base_dir, '..', '..', 'resources', 'exiftool-win', exe),
            # In settings dir
            os.path.join(SETTINGS_DIR, 'exiftool', exe),
            # In resources relative to cwd
            os.path.join('resources', f'exiftool-{platform}', exe),
            os.path.join('resources', 'exiftool-mac', exe),
            os.path.join('resources', 'exiftool-win', exe),
        ]
        for path in bundled_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                return abs_path

        # Fall back to system exiftool
        return 'exiftool'

    def write(self, file_path: str, title: str, description: str,
              keywords: list[str], overwrite: bool = True) -> bool:
        """Write IPTC and XMP metadata to a file.

        Args:
            file_path: Path to the media file
            title: Title/Headline
            description: Description/Caption
            keywords: List of keywords
            overwrite: Whether to overwrite existing metadata

        Returns:
            True if successful, False otherwise
        """
        cmd = [self._exiftool, '-overwrite_original' if overwrite else '',
               file_path]

        # IPTC fields
        cmd.extend(['-ObjectName=' + title])
        cmd.extend(['-Headline=' + title])
        cmd.extend(['-Caption-Abstract=' + description])

        # Clear existing IPTC Keywords, then add new ones
        cmd.extend(['-Keywords='])
        for kw in keywords:
            cmd.extend([f'-Keywords={kw}'])

        # XMP fields - use composite tags (dc:Title/dc:description don't work on fresh files)
        cmd.extend(['-Title=' + title])
        cmd.extend(['-Description=' + description])

        # Clear existing XMP Subject, then add new ones
        cmd.extend(['-Subject='])
        for kw in keywords:
            cmd.extend([f'-Subject={kw}'])

        # Remove empty string from command
        cmd = [arg for arg in cmd if arg]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                logger.debug(f"Metadata written to {file_path}")
                return self._verify_write(file_path, keywords)
            else:
                logger.error(f"exiftool error for {file_path}: {result.stderr[:500]}")
                return False
        except subprocess.TimeoutExpired:
            logger.error(f"exiftool timed out for {file_path}")
            return False
        except FileNotFoundError:
            logger.error(f"exiftool not found: {self._exiftool}")
            return False
        except Exception as e:
            logger.error(f"Error writing metadata to {file_path}: {e}")
            return False

    def _verify_write(self, file_path: str, expected_keywords: list[str]) -> bool:
        """Read back metadata to verify it was written correctly."""
        try:
            cmd = [self._exiftool, '-Keywords', '-Subject',
                   '-Headline', '-Caption-Abstract', '-s3', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.warning(f"Could not verify metadata for {file_path}")
                return True
            output = result.stdout.strip()
            if not output:
                logger.warning(f"No metadata read back from {file_path}")
                return False
            lines = output.split('\n')
            if len(lines) < 4:
                logger.warning(f"Incomplete metadata in {file_path}: {output}")
                return False
            return True
        except Exception as e:
            logger.warning(f"Verification failed for {file_path}: {e}")
            return True

    def write_keywords_only(self, file_path: str, keywords: list[str]) -> bool:
        """Write only keywords, preserving existing metadata."""
        cmd = [self._exiftool, '-overwrite_original', file_path]
        cmd.extend(['-Keywords='])
        for kw in keywords:
            cmd.extend([f'-Keywords={kw}'])
        cmd.extend(['-Subject='])
        for kw in keywords:
            cmd.extend([f'-Subject={kw}'])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                return False
            return self._verify_write(file_path, keywords)
        except Exception as e:
            logger.error(f"Error writing keywords to {file_path}: {e}")
            return False
