"""Constants for the Stock Metadata Agent."""

# Video formats that support embedded metadata
EMBEDDABLE_VIDEO_FORMATS = {'.mov', '.mp4', '.m4v', '.mxf'}
# Video formats that need sidecar
SIDECAR_VIDEO_FORMATS = {'.avi', '.prores', '.hevc'}

# Supported image formats
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif'}

# Supported video formats
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.m4v', '.avi', '.mxf', '.prores', '.hevc'}

# All supported extensions
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

# Agency-specific limits
AGENCY_LIMITS = {
    'adobe_stock': {'max_title': 200, 'max_description': 2000, 'max_keywords': 49},
    'shutterstock': {'max_title': 250, 'max_description': 20000, 'max_keywords': 50},
    'istock': {'max_title': 200, 'max_description': 2000, 'max_keywords': 60},
    'dreamstime': {'max_title': 150, 'max_description': 2000, 'max_keywords': 60},
    'depositphotos': {'max_title': 200, 'max_description': 2000, 'max_keywords': 50},
    'alamy': {'max_title': 200, 'max_description': 5000, 'max_keywords': 100},
}

# Universal metadata limits (strictest across all platforms)
MIN_TITLE_LENGTH = 180  # Target, not enforced (model can't count reliably)
MAX_TITLE_LENGTH = 200  # Hard cap, enforced
MAX_DESCRIPTION_LENGTH = 2000
MIN_KEYWORD_COUNT = 30
MAX_KEYWORD_COUNT = 35
TOP_KEYWORD_COUNT = 10

# Banned words in titles/descriptions
BANNED_WORDS = {
    'stunning', 'amazing', 'beautiful', 'gorgeous', 'breathtaking',
    'incredible', 'magnificent', 'spectacular', 'wonderful', 'fantastic',
    'perfect', 'superb', 'excellent', 'outstanding', 'remarkable',
    'jaw-dropping', 'mind-blowing', 'breathtaking', 'jaw-dropping',
}

# Banned keywords (zero value on stock sites)
BANNED_KEYWORDS = {
    'stock photography', 'stock photo', 'stock images', 'stock image',
    'stock footage', 'professional photography', 'professional photo',
    'high quality', 'high resolution', 'high definition',
    'royalty free', 'copyrighted', 'for sale', 'commercial use',
    'editorial use', 'premium quality',
    'creative', 'art', 'concept', 'idea', 'inspiration',
    'visual', 'design', 'background', 'scene', 'environment',
    'outdoor', 'indoor', 'photograph', 'capture', 'shot',
    'view', 'panorama', 'perspective', 'composition',
    'atmosphere', 'mood', 'tone', 'style', 'aesthetic',
}

# Photo categories for classification
PHOTO_CATEGORIES = [
    'Aerial', 'Landscape', 'Cityscape', 'Seascape', 'Architecture',
    'Nature', 'Travel', 'Harbor', 'Beach', 'Mountain', 'Sunset',
    'Forest', 'River', 'Lake', 'Historical Site',
    'Renewable Energy', 'Solar Farm', 'Wind Farm', 'Data Center',
    'Industrial', 'Infrastructure', 'Telecommunications', 'Power Generation'
]

# Visible objects to detect
DETECTABLE_OBJECTS = [
    'Boats', 'Cars', 'Buildings', 'Coastlines', 'Oyster Farms',
    'Beaches', 'Castles', 'Churches', 'Bridges', 'Roads',
    'Forests', 'Mountains', 'Waterfalls', 'Monuments', 'Landmarks',
    'Solar Panels', 'Wind Turbines', 'Server Racks', 'Electrical Substation',
    'Telecom Towers', 'Power Lines', 'Pipelines', 'Battery Storage',
    'Desalination Plant', 'Manufacturing Equipment'
]

# Video movement types
VIDEO_MOVEMENTS = [
    'Drone Footage', 'Aerial Footage', 'Orbit Shot', 'Flyover',
    'Tracking Shot', 'Push In', 'Pull Back', 'Timelapse',
    'Hyperlapse', 'Static Shot', 'Cinematic Movement'
]

# Default settings
DEFAULT_SETTINGS = {
    'vision_endpoint': 'http://127.0.0.1:8000',
    'vision_api_key': '',
    'vision_model': 'Qwen2.5-VL-3B-Instruct-8bit',
    'text_endpoint': 'http://127.0.0.1:8000',
    'text_api_key': '',
    'text_model': 'Qwen2.5-VL-7B-Instruct-4bit',
    'cloud_text_enabled': False,
    'cloud_text_endpoint': 'https://api.openai.com',
    'cloud_text_api_key': '',
    'cloud_text_model': 'gpt-4o-mini',
    'max_workers': 2,
    'output_format': 'embedded',
    'export_csv': True,
    'export_sidecar': False,
    'target_agencies': ['adobe_stock', 'shutterstock', 'istock', 'dreamstime', 'depositphotos', 'alamy'],
    'auto_learn_location': True,
    'image_resize_max': 1280,
    'video_frames_min': 3,
    'video_frames_max': 7,
    'duplicate_threshold': 10,
    'similar_threshold': 30,
}

# Settings file path (user home)
import os
SETTINGS_DIR = os.path.expanduser('~/.stock-metadata-agent')
SETTINGS_FILE = os.path.join(SETTINGS_DIR, 'settings.json')
MEMORY_DB_FILE = os.path.join(SETTINGS_DIR, 'location_memory.db')
