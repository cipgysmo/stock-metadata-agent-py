"""Metadata generation using text model."""

import json
import logging
import re
import time
from dataclasses import dataclass, field

from ai.client import AIClient
from ai.vision import VisionAnalysis
from config.constants import (
    BANNED_KEYWORDS,
    MAX_KEYWORD_COUNT,
    MAX_TITLE_LENGTH,
    MIN_TITLE_LENGTH,
    TOP_KEYWORD_COUNT,
)
from core.location.gps import GPSInfo
from core.location.parser import Location

logger = logging.getLogger(__name__)


@dataclass
class GeneratedMetadata:
    """Generated metadata for a stock asset."""
    title: str = ''
    description: str = ''
    keywords: list[str] = field(default_factory=list)
    top_keywords: list[str] = field(default_factory=list)
    content_type: str = 'Commercial'
    category: str = ''
    raw_response: str = ''
    quality_score: int = 0

    @property
    def is_valid(self) -> bool:
        return bool(
            self.title
            and self.description
            and len(self.title) <= MAX_TITLE_LENGTH
            and 10 <= len(self.keywords) <= MAX_KEYWORD_COUNT
        )


METADATA_SYSTEM_PROMPT = r"""You are an expert stock photo metadata specialist. Generate metadata for one image that works on Shutterstock, Adobe Stock, Getty/iStock, Alamy, and other platforms simultaneously.

Output ONLY a JSON object with these fields:
- "content_type": "Commercial" or "Editorial"
- "title": 180-200 character caption, ends on a complete sentence
- "description": exact copy of the title field
- "keywords": ordered list of 10-40 keywords
- "top_keywords": the 10 most important keywords from the list
- "category": single best-fit category

 TITLE/DESCRIPTION RULES (180-200 chars, SAME text for both):
 - Write one or two complete sentences. Must end on a period. Never truncate mid-sentence.
 - Length must be between 180 and 200 characters. Check carefully.
 - Lead with primary subject and action, then setting, then secondary detail or concept.
 - Do NOT repeat the same phrase just to reach the character count. Every added clause must contribute real, accurate information.
 - If editorial, lead with dateline: "City, Country - Month DD, YYYY: [factual sentence expanded to length]."
 - For COMMERCIAL content: the title MUST be a natural flowing sentence. NEVER use dashes (-), hyphens, colons, semicolons, or pipes. Only use periods (.) and commas (,). No special characters (&, %, #, emoji). No ALL CAPS.
 - Banned words: stunning, amazing, beautiful, breathtaking, incredible, magnificent, spectacular, wonderful, perfect, superb, excellent, outstanding. No camera settings, brand names, real names, links.

 KEYWORD RULES (10-40, ordered by priority, NO FILLER):
 - Tier 1 (first 15-20): literal subject terms — what is physically in the frame
 - Tier 2 (next 10-15): context terms — location type, time of day, composition, demographics
 - Tier 3 (last 5-10): conceptual/emotional terms — what the image represents
  - **SINGLE-WORD FIRST**: Always use single-word keywords whenever possible. "red car" should be two keywords: "red" AND "car". Only use multi-word keywords for proper names that must stay together ("New York City", "Mont Saint-Michel").
  - **NO SPECIAL CHARACTERS**: Keywords must be plain words only. NEVER use underscores, hyphens, spaces, or any special characters. "wind_farm" is invalid — use two keywords: "wind" AND "farm".
 - Max 3 keywords sharing the same root word. No filler.
 - Every keyword must be literally accurate to the image.
 - QUALITY OVER QUANTITY: Only include keywords that are actually relevant. Better to have 20 accurate keywords than 35 padded with spam. Stop when you've exhausted truly relevant terms.
 - BANNED keywords (NEVER include): stock photography, stock photo, stock images, stock footage, professional photography, professional photo, high quality, high resolution, high definition, royalty free, copyrighted, for sale, commercial use, editorial use, premium quality, creative, concept, visual, design, background, scene, photograph, capture, shot, perspective, composition, tone, aesthetic.

LOCATION RULES:
- If the scene has identifiable geographic features (landmark, landscape), include location.
- For generic scenes without identifiable location (isolated tech, generic interiors), do NOT mention a location.

CATEGORY: Pick one best-fit from:
Aerial, Landscape, Cityscape, Seascape, Architecture, Nature, Travel, People, Business, Technology, Food, Animals, Transportation, Sports, Health, Science, Culture, Religion, Art, Abstract, Background, Lifestyle, Education, Family, Love, Holiday, Vintage, Industrial, Energy, Construction, Medical.

Output ONLY valid JSON. No reasoning, no markdown, no explanation."""


class MetadataGenerator:
    """Generates title, description, and keywords using a text model."""

    def __init__(self, client: AIClient, max_tokens: int = 2000, timeout: int = 120,
                 fallback_client: AIClient | None = None):
        self.client = client
        self.fallback_client = fallback_client
        self.max_tokens = max_tokens
        self.timeout = timeout

    def generate(
        self,
        vision: VisionAnalysis,
        location: Location,
        is_video: bool = False,
        movement: str = '',
        gps_info: GPSInfo | None = None,
        date_string: str = '',
        content_type_override: str = '',
    ) -> GeneratedMetadata:
        """Generate metadata from vision analysis and location context."""
        location_context = self._build_location_context(location, vision, gps_info)
        visual_context = self._build_visual_context(vision, is_video, movement)
        include_location = vision.landmark or self._has_landscape_features(vision)

        tech_kw = ', '.join(vision.technology_keywords) if vision.technology_keywords else ''
        tech_line = f"Technology: {tech_kw}\n" if vision.technology_focus else ''

        date_line = f"Date: {date_string}\n" if date_string else ''

        # Editorial hint: controlled by override if set, otherwise by vision detection
        editorial_hint = ''
        if content_type_override == 'editorial':
            editorial_hint = (
                "IMPORTANT: This is EDITORIAL content. Set content_type to 'Editorial'. "
                "Include date + location in title/description.\n"
            )
        elif content_type_override == 'commercial':
            pass  # Suppress editorial hint even if vision detects it
        elif vision.has_logos or vision.editorial_only:
            editorial_hint = (
                "IMPORTANT: Visible logos or editorial content. Set content_type to 'Editorial'. "
                "Include date + location in title/description.\n"
            )

        if include_location:
            user_text = (
                f"Analyze this {'video' if is_video else 'photo'} and generate metadata:\n"
                f"{editorial_hint}"
                f"This scene has identifiable geographic features. Include location.\n"
                f"{tech_line}"
                f"Subject: {visual_context}\n"
                f"Location: {location_context}\n"
                f"{date_line}"
                f"Output valid JSON only."
            )
        else:
            user_text = (
                f"Analyze this {'video' if is_video else 'photo'} and generate metadata:\n"
                f"{editorial_hint}"
                f"No identifiable geographic features. Do NOT mention a location. Focus on the subject.\n"
                f"{tech_line}"
                f"Subject: {visual_context}\n"
                f"{date_line}"
                f"Output valid JSON only."
            )

        messages = [
            {'role': 'system', 'content': METADATA_SYSTEM_PROMPT},
            {'role': 'user', 'content': user_text},
        ]

        max_retries = 3
        last_error = None
        t0 = time.time()

        for attempt in range(max_retries):
            if time.time() - t0 > self.timeout:
                logger.error(f"Hard timeout ({self.timeout}s)")
                return GeneratedMetadata(raw_response=f"ERROR: timeout")

            if attempt > 0:
                time.sleep(2 * attempt)

            try:
                response = self.client.chat_completion(
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=0.1,
                )
                content = self._extract_content(response)
                metadata = self._parse_response(content)

                if metadata.title or metadata.keywords:
                    if content_type_override:
                        metadata.content_type = (content_type_override or '').title()
                    metadata.title = self._enforce_title(metadata.title or '', vision, location, metadata.content_type or 'Commercial', gps_info)
                    metadata.description = metadata.title
                    metadata.keywords = self._reorder_keywords(metadata.keywords, vision, location, gps_info)
                    return metadata

                logger.debug(f"Retry {attempt + 1}/{max_retries}: empty")
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}", exc_info=True)

        # Local model failed — try cloud fallback
        if self.fallback_client:
            logger.info("Local text model failed, trying cloud fallback...")
            try:
                response = self.fallback_client.chat_completion(
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=0.1,
                )
                content = self._extract_content(response)
                metadata = self._parse_response(content)
                if metadata and (metadata.title or metadata.keywords):
                    if content_type_override:
                        metadata.content_type = (content_type_override or '').title()
                    metadata.title = self._enforce_title(metadata.title or '', vision, location, metadata.content_type or 'Commercial', gps_info)
                    metadata.description = metadata.title
                    metadata.keywords = self._reorder_keywords(metadata.keywords, vision, location, gps_info)
                    logger.info("Cloud fallback succeeded")
                    return metadata
            except Exception as e:
                logger.warning(f"Cloud fallback also failed: {e}")

        logger.warning(f"Failed after {max_retries} retries: {last_error}")
        return GeneratedMetadata(raw_response=f"ERROR: {last_error}")

    # ── context builders ──

    def _build_location_context(
        self, location: Location, vision: VisionAnalysis, gps_info: GPSInfo | None = None,
    ) -> str:
        lines = []
        country = (gps_info.exif_country if gps_info else '') or vision.country or location.country
        if country:
            lines.append(f"Country: {country}")
        exif_state = ''
        if gps_info:
            exif_state = gps_info.exif_state or gps_info.exif_region
        region = exif_state or vision.region or location.region
        if region:
            lines.append(f"Region: {region}")
        city = (gps_info.exif_city if gps_info else '') or vision.city or location.city
        if city:
            lines.append(f"City: {city}")
        if location.sublocation:
            lines.append(f"Sublocation: {location.sublocation}")
        if vision.landmark or location.landmark:
            lines.append(f"Landmark: {vision.landmark or location.landmark}")
        if gps_info and gps_info.has_gps:
            lines.append(f"GPS: {gps_info.latitude:.4f}, {gps_info.longitude:.4f}")
        return '\n'.join(lines) if lines else "(No location available)"

    def _build_visual_context(self, vision: VisionAnalysis, is_video: bool, movement: str = '') -> str:
        lines = []
        if vision.main_subject:
            lines.append(f"Main Subject: {vision.main_subject}")
        if vision.secondary_subject:
            lines.append(f"Secondary Subject: {vision.secondary_subject}")
        if vision.environment:
            lines.append(f"Environment: {vision.environment}")
        if vision.weather:
            lines.append(f"Weather: {vision.weather}")
        if vision.season:
            lines.append(f"Season: {vision.season}")
        if vision.time_of_day:
            lines.append(f"Time of Day: {vision.time_of_day}")
        if vision.visible_objects:
            lines.append(f"Visible Objects: {', '.join(vision.visible_objects)}")
        if vision.commercial_concepts:
            lines.append(f"Concepts: {', '.join(vision.commercial_concepts)}")
        if vision.technology_focus and vision.technology_keywords:
            lines.append(f"Technology: {', '.join(vision.technology_keywords)}")
        if is_video:
            if vision.camera_movement:
                lines.append(f"Camera Movement: {vision.camera_movement}")
            if vision.dominant_scene:
                lines.append(f"Dominant Scene: {vision.dominant_scene}")
            if movement:
                lines.append(f"Detected Movement: {movement}")
        if vision.has_people:
            lines.append(f"People: {vision.people_count} visible")
        if vision.has_logos:
            lines.append(f"Logos: {', '.join(vision.logos_detected)}")
        return '\n'.join(lines) if lines else "(No visual context)"

    def _has_landscape_features(self, vision: VisionAnalysis) -> bool:
        indicators = {
            'hill', 'hills', 'mountain', 'mountains', 'valley', 'valleys',
            'ridge', 'plateau', 'desert', 'dune', 'dunes', 'canyon',
            'cliff', 'cliffs', 'coast', 'ocean', 'sea', 'lake',
            'river', 'forest', 'meadow', 'field', 'fields', 'plain',
            'plains', 'volcano', 'glacier', 'waterfall', 'island',
            'peninsula', 'snow-capped', 'snowy',
        }
        for text in (vision.environment, vision.main_subject,
                      vision.secondary_subject, vision.landmark,
                      vision.photo_category):
            if text:
                for feature in indicators:
                    if feature in text.lower():
                        return True
        for obj in vision.visible_objects:
            for feature in indicators:
                if feature in obj.lower():
                    return True
        return False

    # ── parsing ──

    def _extract_content(self, response: dict) -> str:
        choices = response.get('choices', [])
        if not choices:
            raise ValueError("No choices")
        return choices[0].get('message', {}).get('content', '')

    def _parse_response(self, content: str) -> GeneratedMetadata:
        metadata = GeneratedMetadata(raw_response=content)

        cleaned = content.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[-1] if '\n' in cleaned else cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            data = self._repair_json(cleaned)
            if not data:
                return metadata

        if not data:
            return metadata

        # Title: raw from AI, enforced later with vision context
        title = data.get('title', '').strip()
        metadata.title = title
        metadata.description = title

        # Keywords: 30-35, ordered
        raw_kw = data.get('keywords', [])
        if isinstance(raw_kw, str):
            raw_kw = [k.strip() for k in raw_kw.split(',')]
        # Split on both comma and pipe — LLM sometimes outputs pipe-separated keywords
        expanded = []
        for k in raw_kw:
            expanded.extend(str(k).replace('|', ',').split(','))
        keywords = [k.strip().lower() for k in expanded if k.strip().lower()]
        # Sanitize underscores: "wind_farm" → "wind farm" (keep as expression)
        keywords = [k.replace('_', ' ') for k in keywords]
        # Split multi-word keywords into single words (keep proper names intact)
        keywords = self._split_multichword_keywords(keywords)
        keywords = self._deduplicate_keywords(keywords)
        keywords = [k for k in keywords if k not in BANNED_KEYWORDS]
        keywords = self._fix_keyword_count(keywords)
        metadata.keywords = keywords
        metadata.top_keywords = keywords[:TOP_KEYWORD_COUNT]

        metadata.content_type = data.get('content_type', 'Commercial')
        metadata.category = data.get('category', '').strip()

        return metadata

    def _split_multichword_keywords(self, keywords: list[str]) -> list[str]:
        """Split multi-word keywords into single words, keeping the original phrase."""
        stop_words = {'a', 'an', 'the', 'in', 'on', 'at', 'by', 'for', 'of', 'with', 'from', 'and', 'or'}
        result: list[str] = []
        for kw in keywords:
            result.append(kw)  # Keep original
            if ' ' in kw:
                words = [w.lower() for w in kw.split() if w.lower() not in stop_words]
                result.extend(words)
        return result

    def _enforce_title(self, title: str, vision: VisionAnalysis, location: Location, content_type: str = 'Commercial', gps_info: GPSInfo | None = None) -> str:
        """Ensure 180-200 chars. Truncates over 200 at word boundary. Expands under 180 using factual vision/location data."""
        if not title:
            return title

        title = title.strip()
        # Commercial titles: replace dashes/hyphens with commas for flowing sentence
        if content_type != 'Editorial':
            title = title.replace(' - ', ', ').replace(' — ', ', ').replace('–', ',')
            title = re.sub(r'\s+[-–—]\s+', ', ', title)
        if not title.endswith('.'):
            title += '.'
        title = title.strip()

        # Truncate if over 200
        if len(title) > MAX_TITLE_LENGTH:
            cut = title.rfind(' ', 0, MAX_TITLE_LENGTH)
            if cut > 0:
                title = title[:cut]
            else:
                title = title[:MAX_TITLE_LENGTH - 1]  # leave room for period
            # Ensure ends with period
            title = title.rstrip('.') + '.'
            return title

        # Expand if under 180 using factual clauses from vision/location to form one flowing sentence
        if len(title) < MIN_TITLE_LENGTH:
            clauses = []
            if vision.time_of_day and vision.time_of_day.lower() not in ('unknown', 'day', 'all'):
                clauses.append(f"captured during the {vision.time_of_day}")
            if vision.weather and vision.weather.lower() not in ('unknown', 'clear', 'sunny'):
                clauses.append(f"bathed in {vision.weather} light")
            if vision.season and vision.season.lower() not in ('unknown', 'all'):
                clauses.append(f"highlighting the {vision.season} atmosphere")
            if vision.environment:
                clauses.append(f"set against a {vision.environment}")
            if vision.secondary_subject:
                clauses.append(f"accompanied by {vision.secondary_subject} in the frame")
            if location.city and location.country:
                clauses.append(f"located in {location.city}, {location.country}")
            elif location.city:
                clauses.append(f"located in {location.city}")
            if vision.commercial_concepts:
                for c in vision.commercial_concepts[:2]:
                    clauses.append(f"evoking the concept of {c}")
            if vision.visible_objects:
                for obj in vision.visible_objects[:2]:
                    clauses.append(f"featuring {obj} in the composition")

            base = title.rstrip('.')
            for clause in clauses:
                if len(base) >= MIN_TITLE_LENGTH:
                    break
                candidate = base + f", {clause}"
                if len(candidate) <= MAX_TITLE_LENGTH - 1:  # -1 for final period
                    base = candidate
            title = base + "."

        # Sentence-case: only first letter capitalized, rest lowercase (preserve proper nouns)
        proper_nouns = self._collect_proper_nouns(vision, location, gps_info)
        title = self._sentence_case(title, proper_nouns)

        return title

    def _collect_proper_nouns(
        self, vision: VisionAnalysis, location: Location, gps_info: GPSInfo | None = None,
    ) -> list[str]:
        """Collect known proper nouns from vision/location data to preserve capitalization."""
        nouns: list[str] = []
        city = (gps_info.exif_city if gps_info else '') or vision.city or location.city
        if city:
            nouns.append(city)
        country = (gps_info.exif_country if gps_info else '') or vision.country or location.country
        if country:
            nouns.append(country)
        region = ((gps_info.exif_state or gps_info.exif_region) if gps_info else '') or vision.region or location.region
        if region:
            nouns.append(region)
        landmark = vision.landmark or location.landmark
        if landmark:
            nouns.append(landmark)
        sublocation = (gps_info.exif_sublocation if gps_info else '') or location.sublocation
        if sublocation:
            nouns.append(sublocation)
        return nouns

    def _sentence_case(self, title: str, proper_nouns: list[str] | None = None) -> str:
        """Convert title to sentence case: first letter capitalized, all others lowercase, preserving proper nouns."""
        if not title:
            return title or ''
        # Strip trailing period, process, then re-add
        has_period = title.endswith('.')
        title = title.rstrip('.')
        # Split on periods for multi-sentence handling
        sentences = [s.strip() for s in title.split('.') if s.strip()]
        result = []
        for sent in sentences:
            sent_lower = sent.lower()
            # Restore proper nouns to title case
            if proper_nouns:
                for noun in proper_nouns:
                    noun_lower = noun.lower()
                    if noun_lower in sent_lower:
                        # Replace all occurrences of the lowercase noun with title case
                        sent_lower = sent_lower.replace(noun_lower, noun)
            if sent_lower:
                sent_lower = sent_lower[0].upper() + sent_lower[1:]
            result.append(sent_lower)
        out = '. '.join(result)
        if has_period:
            out += '.'
        return out

    def _reorder_keywords(
        self, keywords: list[str], vision: VisionAnalysis, location: Location, gps_info: GPSInfo | None = None,
    ) -> list[str]:
        """Move high-priority keywords (landmark, city, country, subject) to the front."""
        if not keywords:
            return keywords

        kw_lower = [k.lower() for k in keywords]
        pinned: list[str] = []
        pinned_set: set[str] = set()
        used_indices: set[int] = set()

        # Build priority terms from vision/location/GPS
        priority_terms: list[str] = []
        if vision.landmark:
            priority_terms.append(vision.landmark.lower())
            for word in vision.landmark.split():
                if len(word) > 2:
                    priority_terms.append(word.lower())
        city = (gps_info.exif_city if gps_info else '') or vision.city or location.city
        if city:
            priority_terms.append(city.lower())
        country = (gps_info.exif_country if gps_info else '') or vision.country or location.country
        if country:
            priority_terms.append(country.lower())
        region = ((gps_info.exif_state or gps_info.exif_region) if gps_info else '') or vision.region or location.region
        if region:
            priority_terms.append(region.lower())
        if vision.main_subject:
            priority_terms.append(vision.main_subject.lower())
            for word in vision.main_subject.split():
                if len(word) > 2:
                    priority_terms.append(word.lower())

        # Pin matching keywords in priority order
        for term in priority_terms:
            for i, kw in enumerate(kw_lower):
                if i in used_indices or kw in pinned_set:
                    continue
                if term in kw or kw in term:
                    pinned.append(keywords[i])
                    pinned_set.add(kw)
                    used_indices.add(i)
                    break

        # Remaining keywords keep their original order
        rest = [k for j, k in enumerate(keywords) if j not in used_indices]

        return pinned + rest

    def _deduplicate_keywords(self, keywords: list[str]) -> list[str]:
        if not keywords:
            return keywords
        root_groups: dict[str, list[str]] = {}
        other: list[str] = []
        for kw in keywords:
            words = kw.split()
            root = words[0].lower().rstrip('s') if words else kw
            if len(root) > 2:
                root_groups.setdefault(root, []).append(kw)
            else:
                other.append(kw)
        result = []
        for group in root_groups.values():
            result.extend(group[:3])
        result.extend(other)
        return result

    def _fix_keyword_count(self, keywords: list[str]) -> list[str]:
        """Just enforce the maximum count. No padding."""
        if len(keywords) > MAX_KEYWORD_COUNT:
            return keywords[:MAX_KEYWORD_COUNT]
        return keywords

    def _repair_json(self, text: str) -> dict | None:
        data = {}
        title_m = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        desc_m = re.search(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if title_m:
            data['title'] = title_m.group(1)
        if desc_m:
            data['description'] = desc_m.group(1)

        kw_start = text.find('"keywords"')
        if kw_start != -1:
            arr_start = text.find('[', kw_start)
            if arr_start != -1:
                kw_section = text[arr_start + 1:]
                for close_pos in [100, 200, 500, 1000, len(kw_section)]:
                    test = kw_section if close_pos >= len(kw_section) else kw_section[:close_pos] + '[]'
                    try:
                        parsed = json.loads(test)
                        if isinstance(parsed, list):
                            skip = {'title', 'description', 'keywords', 'id', 'object', 'role'}
                            data['keywords'] = [k for k in parsed if isinstance(k, str) and k.lower() not in skip]
                            break
                    except (json.JSONDecodeError, ValueError):
                        continue
                if 'keywords' not in data:
                    skip = {'title', 'description', 'keywords', 'id', 'object', 'role'}
                    data['keywords'] = [k for k in re.findall(r'"((?:[^"\\]|\\.)*)"', kw_section) if k.lower() not in skip]

        cat_m = re.search(r'"category"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if cat_m:
            data['category'] = cat_m.group(1)
        ct_m = re.search(r'"content_type"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if ct_m:
            data['content_type'] = ct_m.group(1)

        return data if data else None
