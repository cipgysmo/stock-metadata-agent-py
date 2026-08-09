"""Folder-based location parsing."""

import os
import re
from dataclasses import dataclass


@dataclass
class Location:
    """Structured location data derived from folder paths."""
    country: str = ''
    region: str = ''
    city: str = ''
    landmark: str = ''
    sublocation: str = ''
    raw_path: str = ''
    components: list[str] = None

    def __post_init__(self):
        if self.components is None:
            self.components = []

    @property
    def display_name(self) -> str:
        """Human-readable location string."""
        parts = [p for p in [self.city, self.region, self.country] if p]
        return ', '.join(parts) if parts else self.raw_path

    @property
    def primary_keyword(self) -> str:
        """The most specific location term for keyword generation."""
        return self.city or self.region or self.country

    @property
    def is_complete(self) -> bool:
        return bool(self.country and self.city)


class LocationParser:
    """Parses location information from folder paths.

    Supports patterns like:
    - France/Brittany/Cancale
    - France - Brittany - Cancale
    - Germany\\Bavaria\\Munich
    """

    # Known country/region mappings for validation
    KNOWN_COUNTRIES = {
        'france', 'germany', 'united kingdom', 'uk', 'spain', 'italy',
        'portugal', 'netherlands', 'belgium', 'switzerland', 'austria',
        'czech republic', 'poland', 'norway', 'sweden', 'denmark',
        'finland', 'iceland', 'greece', 'turkey', 'usa', 'usa',
        'united states', 'canada', 'mexico', 'brazil', 'argentina',
        'japan', 'china', 'india', 'australia', 'new zealand',
        'south africa', 'kenya', 'morocco', 'egypt', 'russia',
        'croatia', 'serbia', 'romania', 'hungary', 'slovenia',
        'estonia', 'latvia', 'lithuania', 'ireland', 'malta',
        'cyprus', 'bulgaria', 'albania', 'north macedonia',
        'bosnia', 'montenegro', 'slovenia', 'georgia', 'armenia',
    }

    KNOWN_REGIONS = {
        'brittany', 'bretagne', 'bavaria', 'baden-wurttemberg',
        'basque country', 'catalonia', 'andalusia', 'tuscany',
        'lombardy', 'sicily', 'sardinia', 'normandy', 'provence',
        'corse', 'corsica', 'saxony', 'hesse', 'north rhine',
        'lower saxony', 'rhineland', 'schleswig', 'thuringia',
        'mecklenburg', 'brandenburg', 'berlin', 'hamburg', 'bremen',
        'styria', 'tyrol', 'carinthia', 'salzburg', 'vienna',
        'scotland', 'wales', 'england', 'cornwall', 'devon',
        'yorkshire', 'london', 'new york', 'california', 'texas',
        'alaska', 'hawaii', 'colorado', 'utah', 'arizona',
        'washington', 'oregon', 'maine', 'vermont', 'new hampshire',
        'massachusetts', 'connecticut', 'rhode island',
        'ontario', 'quebec', 'british columbia', 'alberta',
        'queensland', 'new south wales', 'vicitoria', 'tasmania',
    }

    def parse(self, folder_path: str, root_path: str = '') -> Location:
        """Parse location from a folder path.

        Args:
            folder_path: Relative path from root (e.g., 'France/Brittany/Cancale')
            root_path: Unused, kept for API compatibility

        Returns:
            Location object with parsed components
        """
        raw = folder_path

        # Normalize separators
        normalized = folder_path.replace('\\', '/').replace(' - ', '/')

        # Split into components
        components = [c.strip() for c in normalized.split('/') if c.strip()]

        if not components:
            return Location(raw_path=raw, components=[])

        loc = Location(raw_path=raw, components=components)

        # Try to identify country, region, city from components
        # Strategy: country is first, city is last, region is in between
        self._identify_components(loc, components)

        return loc

    def _identify_components(self, loc: Location, components: list[str]) -> None:
        """Identify country/region/city from path components."""
        if len(components) == 1:
            loc.city = components[0]
            return

        # Check if first component is a known country
        first_lower = components[0].lower()
        if first_lower in self.KNOWN_COUNTRIES:
            loc.country = self._normalize_name(components[0])
            if len(components) >= 3:
                # Middle components are regions
                loc.region = self._normalize_name(' / '.join(components[1:-1]))
                loc.city = self._normalize_name(components[-1])
            elif len(components) == 2:
                loc.city = self._normalize_name(components[1])
                # Check if second component is a region instead
                if components[1].lower() in self.KNOWN_REGIONS:
                    loc.region = loc.city
                    loc.city = ''
        else:
            # No known country - treat last component as city
            loc.city = self._normalize_name(components[-1])
            if len(components) >= 2:
                loc.region = self._normalize_name(components[-2])
            if len(components) >= 3:
                loc.country = self._normalize_name(components[0])

        # Check if the last component might be a landmark
        if len(components) >= 3:
            last = components[-1].lower()
            landmark_indicators = ['cathedral', 'castle', 'bridge', 'tower',
                                    'museum', 'palace', 'fort', 'abbey',
                                    'monastery', 'monument', 'park', 'square']
            if any(ind in last for ind in landmark_indicators):
                loc.landmark = self._normalize_name(components[-1])

    def _normalize_name(self, name: str) -> str:
        """Normalize a place name to title case."""
        words = name.lower().split()
        # Capitalize first letter of each word
        return ' '.join(w.capitalize() for w in words if w)

    def get_location_variations(self, loc: Location) -> list[str]:
        """Generate keyword-safe location variations.

        Example: ['Cancale', 'Cancale France', 'Cancale Brittany', 'Cancale Harbor']
        """
        variations = []
        if not loc.city:
            return variations

        base = loc.city
        variations.append(base)

        if loc.region:
            variations.append(f"{base} {loc.region}")
        if loc.country:
            variations.append(f"{base} {loc.country}")
        if loc.region and loc.country:
            variations.append(f"{base} {loc.region} {loc.country}")
        if loc.landmark:
            variations.append(f"{base} {loc.landmark}")

        return variations
