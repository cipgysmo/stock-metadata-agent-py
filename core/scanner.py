"""Recursive folder scanner for media files."""

import os
from dataclasses import dataclass
from typing import Generator
from config.constants import IMAGE_EXTENSIONS, SUPPORTED_EXTENSIONS


@dataclass
class MediaFile:
    """Represents a discovered media file."""
    path: str
    name: str
    folder_path: str
    file_type: str  # 'image' or 'video'
    extension: str
    size_bytes: int = 0
    folder_location: str = ''  # Derived location from folder path

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


class Scanner:
    """Recursively scans folders for supported media files."""

    def __init__(self, root_path: str):
        self.root_path = os.path.abspath(root_path)

    def scan(self) -> list[MediaFile]:
        """Scan root_path recursively and return all media files."""
        files = []
        for file_info in self._walk():
            files.append(file_info)
        return files

    def scan_iter(self) -> Generator[MediaFile, None, None]:
        """Generator version for memory-efficient scanning."""
        yield from self._walk()

    def _walk(self) -> Generator[MediaFile, None, None]:
        for dirpath, dirnames, filenames in os.walk(self.root_path):
            # Skip hidden dirs, virtual envs, caches
            dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in ('node_modules', '__pycache__', '.venv', 'venv')]
            for filename in sorted(filenames):
                ext = os.path.splitext(filename)[1].lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue

                full_path = os.path.join(dirpath, filename)

                # Determine file type
                file_type = 'image' if ext in IMAGE_EXTENSIONS else 'video'

                # Derive location from folder structure relative to root
                rel_dir = os.path.relpath(dirpath, self.root_path)
                folder_location = ''
                if rel_dir != '.':
                    folder_location = rel_dir.replace(os.sep, ' / ')

                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    size = 0

                yield MediaFile(
                    path=full_path,
                    name=filename,
                    folder_path=dirpath,
                    file_type=file_type,
                    extension=ext,
                    size_bytes=size,
                    folder_location=folder_location,
                )

    def get_stats(self) -> dict:
        """Get scanning statistics."""
        images = 0
        videos = 0
        total_size = 0
        for f in self._walk():
            if f.file_type == 'image':
                images += 1
            else:
                videos += 1
            total_size += f.size_bytes
        return {
            'images': images,
            'videos': videos,
            'total': images + videos,
            'total_size_mb': total_size / (1024 * 1024),
            'root_path': self.root_path,
        }

    def _classify(self, full_path: str) -> MediaFile | None:
        """Classify a single file path into a MediaFile."""
        ext = os.path.splitext(full_path)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return None
        filename = os.path.basename(full_path)
        folder_path = os.path.dirname(full_path)
        file_type = 'image' if ext in IMAGE_EXTENSIONS else 'video'
        try:
            size = os.path.getsize(full_path)
        except OSError:
            size = 0
        # Derive location from folder structure relative to root
        rel_dir = os.path.relpath(folder_path, self.root_path)
        folder_location = ''
        if rel_dir != '.':
            folder_location = rel_dir.replace(os.sep, ' / ')
        return MediaFile(
            path=full_path,
            name=filename,
            folder_path=folder_path,
            file_type=file_type,
            extension=ext,
            size_bytes=size,
            folder_location=folder_location,
        )
