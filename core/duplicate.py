"""Perceptual hash-based duplicate and similarity detection."""

import logging
from dataclasses import dataclass, field
from PIL import Image
from io import BytesIO
import imagehash

logger = logging.getLogger(__name__)


@dataclass
class DuplicateGroup:
    """A group of similar/duplicate files."""
    representative: str  # File path of the representative
    similar_files: list[str] = field(default_factory=list)
    similarity_scores: dict[str, int] = field(default_factory=dict)
    is_duplicate: bool = False  # True if very similar (distance < threshold)

    @property
    def count(self) -> int:
        return len(self.similar_files) + 1


class DuplicateDetector:
    """Detects duplicate and similar images using perceptual hashing."""

    def __init__(self, duplicate_threshold: int = 10, similar_threshold: int = 30,
                 hash_size: int = 16):
        self.duplicate_threshold = duplicate_threshold
        self.similar_threshold = similar_threshold
        self.hash_size = hash_size
        self._hashes: dict[str, imagehash.ImageHash] = {}

    def add(self, file_path: str, image_data: bytes) -> None:
        """Compute and store hash for a file."""
        try:
            img = Image.open(BytesIO(image_data))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            h = imagehash.phash(img, hash_size=self.hash_size)
            self._hashes[file_path] = h
        except Exception as e:
            logger.warning(f"Failed to hash {file_path}: {e}")

    def add_from_frame(self, file_path: str, frame_data: bytes) -> None:
        """Compute and store hash from a video frame."""
        self.add(file_path, frame_data)

    def find_duplicates(self) -> list[DuplicateGroup]:
        """Find all duplicate and similar groups.

        Returns:
            List of DuplicateGroup objects with similar files.
        """
        groups: dict[int, DuplicateGroup] = {}
        grouped: set[int] = set()

        paths = list(self._hashes.keys())
        for i in range(len(paths)):
            if i in grouped:
                continue

            path_i = paths[i]
            hash_i = self._hashes[path_i]

            similar: list[tuple[str, int]] = []
            for j in range(i + 1, len(paths)):
                if j in grouped:
                    continue

                path_j = paths[j]
                hash_j = self._hashes[path_j]

                distance = int(hash_i - hash_j)
                if distance <= self.similar_threshold:
                    similar.append((path_j, distance))

            if similar:
                group = DuplicateGroup(
                    representative=path_i,
                    similar_files=[s[0] for s in similar],
                    similarity_scores={s[0]: s[1] for s in similar},
                    is_duplicate=any(s[1] <= self.duplicate_threshold for s in similar),
                )
                groups[i] = group
                grouped.add(i)
                for s in similar:
                    idx = paths.index(s[0])
                    grouped.add(idx)

        return list(groups.values())

    def check_similar(self, file_path: str, image_data: bytes) -> list[tuple[str, int]]:
        """Check if a new file is similar to any previously seen files.

        Returns:
            List of (file_path, distance) tuples for similar files.
        """
        try:
            img = Image.open(BytesIO(image_data))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            h = imagehash.phash(img, hash_size=self.hash_size)
        except Exception as e:
            logger.warning(f"Failed to hash {file_path}: {e}")
            return []

        results = []
        for existing_path, existing_hash in self._hashes.items():
            distance = int(h - existing_hash)
            if distance <= self.similar_threshold:
                results.append((existing_path, distance))

        self._hashes[file_path] = h
        return results

    @property
    def total_hashed(self) -> int:
        return len(self._hashes)
