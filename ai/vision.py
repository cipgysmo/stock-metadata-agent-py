"""Vision model integration for image/video analysis."""

import logging
import json
import time
from dataclasses import dataclass, field, asdict
from config.constants import PHOTO_CATEGORIES, DETECTABLE_OBJECTS, VIDEO_MOVEMENTS
from ai.client import AIClient

logger = logging.getLogger(__name__)


@dataclass
class VisionAnalysis:
    """Structured results from vision model analysis."""
    # Location
    country: str = ''
    region: str = ''
    city: str = ''
    landmark: str = ''

    # Subject
    main_subject: str = ''
    secondary_subject: str = ''
    commercial_concepts: list[str] = field(default_factory=list)

    # Environment
    environment: str = ''
    weather: str = ''
    season: str = ''
    time_of_day: str = ''

    # Classification
    photo_category: str = ''
    visible_objects: list[str] = field(default_factory=list)

    # Technology focus
    technology_focus: bool = False
    technology_keywords: list[str] = field(default_factory=list)

    # Video-specific
    is_video: bool = False
    camera_movement: str = ''
    dominant_scene: str = ''

    # Safety
    has_logos: bool = False
    logos_detected: list[str] = field(default_factory=list)
    has_people: bool = False
    people_count: int = 0
    needs_model_release: bool = False
    needs_property_release: bool = False
    editorial_only: bool = False

    # Raw AI response for debugging
    raw_response: str = ''

    @property
    def is_safe_for_commercial(self) -> bool:
        """Check if content is safe for commercial use without releases."""
        return not self.has_logos and not self.needs_model_release and not self.needs_property_release


VISION_SYSTEM_PROMPT = """You are an expert visual analyst for a stock photography metadata system. Analyze the provided image and return a JSON object with EXACTLY these fields:

{{
    "country": "Country name or empty string",
    "region": "Region/state or empty string",
    "city": "City/town name or empty string",
    "landmark": "Specific landmark name or empty string",
    "main_subject": "The primary subject of the image",
    "secondary_subject": "Secondary subject or empty string",
    "commercial_concepts": ["up to 5 commercial concepts like luxury, freedom, isolation"],
    "environment": "Overall environment setting",
    "weather": "Weather conditions visible",
    "season": "Season (spring/summer/autumn/winter/unknown)",
    "time_of_day": "Time of day (dawn/morning/midday/afternoon/sunset/night/unknown)",
    "photo_category": "One of: {categories}",
    "visible_objects": ["list all visible objects, landmarks, features"],
    "technology_focus": false,
    "technology_keywords": [],
    "has_logos": false,
    "logos_detected": [],
    "has_people": false,
    "people_count": 0,
    "needs_model_release": false,
    "needs_property_release": false,
    "editorial_only": false
}}

Rules:
- Be specific and accurate. Do not guess.
- Only include what you can actually see.
- For has_logos: detect ANY brand logos, trademarks, or company names.
- For has_people: detect recognizable people (faces clearly visible).
- For needs_model_release: true if people are clearly identifiable.
- For needs_property_release: true if unique private buildings or interiors.
- For technology_focus: true if the image is primarily about technology, infrastructure, or industrial subjects with no clear geographic landmark (e.g., solar panel farms, wind turbines, data centers, power plants, server racks, electrical substations, telecommunications equipment, manufacturing plants, pipelines, desalination plants, battery storage, etc.). When technology_focus is true, also provide 5-10 specific technology keywords in technology_keywords.
- Return ONLY valid JSON, no markdown, no explanation."""

VIDEO_VISION_SYSTEM_PROMPT = """You are an expert visual analyst for stock footage. Analyze this video frame and return JSON with these fields:

{{
    "country": "Country name or empty string",
    "region": "Region or empty string",
    "city": "City/town or empty string",
    "landmark": "Specific landmark or empty string",
    "main_subject": "Primary subject",
    "secondary_subject": "Secondary subject or empty string",
    "commercial_concepts": ["up to 5 commercial concepts"],
    "environment": "Environment setting",
    "weather": "Weather conditions",
    "season": "Season",
    "time_of_day": "Time of day",
    "photo_category": "One of: {categories}",
    "visible_objects": ["all visible objects, features"],
    "camera_movement": "One of: {movements}",
    "dominant_scene": "Description of the dominant scene",
    "is_video": true,
    "has_logos": false,
    "logos_detected": [],
    "has_people": false,
    "people_count": 0,
    "needs_model_release": false,
    "needs_property_release": false,
    "editorial_only": false
}}

Rules:
- Detect camera movement from the frame composition and motion blur.
- For drone/aerial footage, identify altitude perspective.
- Return ONLY valid JSON."""


class VisionAnalyzer:
    """Analyzes images and video frames using a vision model."""

    def __init__(self, client: AIClient, image_resize: int = 1280, timeout: int = 120):
        self.client = client
        self.image_resize = image_resize
        self.timeout = timeout

    def analyze_image(self, image_data: bytes, mime_type: str = 'image/jpeg',
                      context: dict = None) -> VisionAnalysis:
        """Analyze an image using the vision model.

        Args:
            image_data: Raw image bytes
            mime_type: MIME type of the image
            context: Optional context dict with location hints
        """
        categories_str = ', '.join(PHOTO_CATEGORIES)
        system_prompt = VISION_SYSTEM_PROMPT.format(categories=categories_str)

        user_text = "Analyze this image for stock photography metadata."
        if context:
            location_hint = context.get('location_hint', '')
            if location_hint:
                user_text += f" The photo was taken in: {location_hint}."

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_text},
        ]

        try:
            t0 = time.time()
            response = self.client.vision_completion(
                messages=messages,
                image_data=image_data,
                mime_type=mime_type,
                max_tokens=2048,
                temperature=0.3,
                image_size=self.image_resize,
            )
            elapsed = time.time() - t0
            logger.info(f"Vision completion took {elapsed:.1f}s")
            content = self._extract_content(response)
            return self._parse_response(content, is_video=False)
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return VisionAnalysis(raw_response=f"ERROR: {e}")

    def analyze_video_frame(self, frame_data: bytes, context: dict = None,
                            is_key_frame: bool = True) -> VisionAnalysis:
        """Analyze a video frame using the vision model."""
        categories_str = ', '.join(PHOTO_CATEGORIES)
        movements_str = ', '.join(VIDEO_MOVEMENTS)
        system_prompt = VIDEO_VISION_SYSTEM_PROMPT.format(
            categories=categories_str,
            movements=movements_str
        )

        user_text = "Analyze this video frame for stock footage metadata."
        if context:
            location_hint = context.get('location_hint', '')
            if location_hint:
                user_text += f" The footage was taken in: {location_hint}."
        if is_key_frame:
            user_text += " This is the most commercially relevant frame."

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_text},
        ]

        try:
            response = self.client.vision_completion(
                messages=messages,
                image_data=frame_data,
                mime_type='image/jpeg',
                max_tokens=2048,
                temperature=0.3,
                image_size=self.image_resize,
            )
            content = self._extract_content(response)
            return self._parse_response(content, is_video=True)
        except Exception as e:
            logger.error(f"Video frame analysis failed: {e}")
            return VisionAnalysis(raw_response=f"ERROR: {e}")

    def _extract_content(self, response: dict) -> str:
        """Extract the content string from an API response."""
        choices = response.get('choices', [])
        if not choices:
            raise ValueError("No choices in response")
        message = choices[0].get('message', {})
        return message.get('content', '')

    def _parse_response(self, content: str, is_video: bool = False) -> VisionAnalysis:
        """Parse JSON response into VisionAnalysis."""
        analysis = VisionAnalysis(is_video=is_video, raw_response=content)

        # Clean up markdown code fences
        cleaned = content.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[-1] if '\n' in cleaned else cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse vision JSON: {e}")
            return analysis

        # Map fields
        analysis.country = data.get('country', '')
        analysis.region = data.get('region', '')
        analysis.city = data.get('city', '')
        analysis.landmark = data.get('landmark', '')
        analysis.main_subject = data.get('main_subject', '')
        analysis.secondary_subject = data.get('secondary_subject', '')
        analysis.commercial_concepts = data.get('commercial_concepts', [])
        analysis.environment = data.get('environment', '')
        analysis.weather = data.get('weather', '')
        analysis.season = data.get('season', '')
        analysis.time_of_day = data.get('time_of_day', '')
        analysis.photo_category = data.get('photo_category', '')
        analysis.visible_objects = data.get('visible_objects', [])
        analysis.technology_focus = data.get('technology_focus', False)
        analysis.technology_keywords = data.get('technology_keywords', [])
        analysis.has_logos = data.get('has_logos', False)
        analysis.logos_detected = data.get('logos_detected', [])
        analysis.has_people = data.get('has_people', False)
        analysis.people_count = data.get('people_count', 0)
        analysis.needs_model_release = data.get('needs_model_release', False)
        analysis.needs_property_release = data.get('needs_property_release', False)
        analysis.editorial_only = data.get('editorial_only', False)

        if is_video:
            analysis.camera_movement = data.get('camera_movement', '')
            analysis.dominant_scene = data.get('dominant_scene', '')

        return analysis
