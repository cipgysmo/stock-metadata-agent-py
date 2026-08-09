"""Metadata quality scoring and validation."""

import logging
from dataclasses import dataclass

from ai.generator import GeneratedMetadata
from ai.vision import VisionAnalysis
from config.constants import (
    BANNED_WORDS,
    MAX_KEYWORD_COUNT,
    MAX_TITLE_LENGTH,
    MIN_KEYWORD_COUNT,
    MIN_TITLE_LENGTH,
)
from core.location.parser import Location

logger = logging.getLogger(__name__)


@dataclass
class QualityScore:
    """Detailed quality score for generated metadata."""
    overall: int = 0
    title_quality: int = 0
    keyword_quality: int = 0
    commercial_value: int = 0
    issues: list[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


class QualityValidator:
    """Validates and scores generated metadata."""

    def validate(self, metadata: GeneratedMetadata) -> list[str]:
        """Validate against the universal spec."""
        issues = []

        # Title/description checks
        if not metadata.title:
            issues.append("Title is empty")
        else:
            tl = len(metadata.title)
            # Only enforce hard max; 180 is a target the model struggles with
            if tl > MAX_TITLE_LENGTH:
                issues.append(f"Title too long: {tl} chars (max {MAX_TITLE_LENGTH})")
            if tl > MAX_TITLE_LENGTH:
                issues.append(f"Title too long: {tl} chars (max {MAX_TITLE_LENGTH})")
            # Must end on period
            if not metadata.title.endswith('.'):
                issues.append("Title does not end on a period")
            # Banned words
            title_lower = metadata.title.lower()
            found = [w for w in BANNED_WORDS if w in title_lower]
            if found:
                issues.append(f"Banned words: {', '.join(found)}")

        # Description should match title
        if metadata.title and metadata.description and metadata.title != metadata.description:
            issues.append("Description differs from title")

        if not metadata.description:
            issues.append("Description is empty")

        # Keyword checks
        if not metadata.keywords:
            issues.append("No keywords generated")
        else:
            kw_len = len(metadata.keywords)
            if kw_len < MIN_KEYWORD_COUNT:
                issues.append(f"Too few keywords: {kw_len} (min {MIN_KEYWORD_COUNT})")
            if kw_len > MAX_KEYWORD_COUNT:
                issues.append(f"Too many keywords: {kw_len} (max {MAX_KEYWORD_COUNT})")
            # Duplicates
            seen = set()
            dups = []
            for k in metadata.keywords:
                kl = k.lower()
                if kl in seen:
                    dups.append(k)
                seen.add(kl)
            if dups:
                issues.append(f"Duplicate keywords: {', '.join(dups[:5])}")

        if not metadata.category:
            issues.append("No category selected")

        return issues

    def score(self, metadata: GeneratedMetadata, vision: VisionAnalysis,
              location: Location) -> QualityScore:
        score = QualityScore()

        # 1. Title quality (35%)
        score.title_quality = self._score_title(metadata, vision, location)

        # 2. Keyword quality (35%)
        score.keyword_quality = self._score_keywords(metadata, vision)

        # 3. Commercial value (30%)
        score.commercial_value = self._score_commercial_value(vision)

        score.overall = (
            score.title_quality * 35
            + score.keyword_quality * 35
            + score.commercial_value * 30
        ) // 100

        return score

    def _score_title(self, metadata: GeneratedMetadata, vision: VisionAnalysis,
                     location: Location) -> int:
        if not metadata.title:
            return 0
        title = metadata.title
        tl = len(title)
        score = 50

        # Length (180-200 ideal)
        if MIN_TITLE_LENGTH <= tl <= MAX_TITLE_LENGTH:
            score += 25
        elif tl < MIN_TITLE_LENGTH:
            score -= 20
        elif tl > MAX_TITLE_LENGTH:
            score -= 10

        # Ends on period
        if title.endswith('.'):
            score += 10

        # Banned words
        if any(w in title.lower() for w in BANNED_WORDS):
            score -= 20

        # Subject relevance
        if vision.main_subject:
            main_words = set(vision.main_subject.lower().split())
            title_words = set(title.lower().split())
            if main_words & title_words:
                score += 10

        # Location when appropriate
        if location.city and location.city.lower() in title.lower():
            score += 5

        return max(0, min(score, 100))

    def _score_keywords(self, metadata: GeneratedMetadata, vision: VisionAnalysis) -> int:
        if not metadata.keywords:
            return 0
        keywords = metadata.keywords
        score = 50

        # Count check
        if MIN_KEYWORD_COUNT <= len(keywords) <= MAX_KEYWORD_COUNT:
            score += 25
        elif len(keywords) > MAX_KEYWORD_COUNT:
            score -= 10

        # Unique check
        unique = set(k.lower() for k in keywords)
        if len(unique) != len(keywords):
            score -= 15

        # Subject in top keywords
        top10 = keywords[:10]
        main_lower = vision.main_subject.lower() if vision.main_subject else ''
        if main_lower:
            main_words = set(main_lower.split())
            top_words = set(' '.join(top10).split())
            overlap = main_words & top_words
            score += min(len(overlap) * 5, 15)

        # Multi-word ratio
        multi = sum(1 for kw in keywords if ' ' in kw)
        ratio = multi / len(keywords) if keywords else 0
        if 0.15 <= ratio <= 0.5:
            score += 10

        return max(0, min(score, 100))

    def _score_commercial_value(self, vision: VisionAnalysis) -> int:
        score = 50
        if vision.has_logos:
            score -= 20
        if vision.needs_model_release:
            score -= 15
        if vision.needs_property_release:
            score -= 10
        if vision.editorial_only:
            score -= 15
        if vision.commercial_concepts:
            score += min(len(vision.commercial_concepts) * 3, 15)
        return max(0, min(score, 100))
