"""Video frame extraction using ffmpeg."""

import json
import os
import subprocess
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExtractedFrame:
    """An extracted video frame with metadata."""
    frame_data: bytes
    timestamp: float  # seconds
    width: int
    height: int
    is_key_frame: bool = False


class VideoFrameExtractor:
    """Extracts frames from videos using ffmpeg."""

    def __init__(self, ffmpeg_path: str = 'ffmpeg', max_width: int = 1280):
        self._ffmpeg = ffmpeg_path
        self.max_width = max_width

    def extract_frames(self, video_path: str, num_frames: int = None) -> list[ExtractedFrame]:
        """Extract evenly-spaced frames from a video.

        Args:
            video_path: Path to the video file
            num_frames: Number of frames to extract (auto-calculated if None)

        Returns:
            List of ExtractedFrame objects
        """
        duration = self._get_duration(video_path)
        if duration <= 0:
            logger.warning(f"Could not determine duration of {video_path}")
            return []

        if num_frames is None:
            num_frames = self._calculate_frame_count(duration)

        frames = []
        timestamps = self._spread_timestamps(duration, num_frames)

        for i, ts in enumerate(timestamps):
            frame_data = self._extract_at_timestamp(video_path, ts)
            if frame_data:
                # Decode frame to get dimensions
                from PIL import Image
                from io import BytesIO
                try:
                    img = Image.open(BytesIO(frame_data))
                    is_key = (i == 0) or (ts > 20 and i == num_frames // 2)
                    frames.append(ExtractedFrame(
                        frame_data=frame_data,
                        timestamp=ts,
                        width=img.width,
                        height=img.height,
                        is_key_frame=is_key,
                    ))
                except Exception as e:
                    logger.warning(f"Failed to decode frame at {ts:.1f}s: {e}")

        logger.info(f"Extracted {len(frames)} frames from {os.path.basename(video_path)} ({duration:.1f}s)")
        return frames

    def extract_thumbnail(self, video_path: str, max_size: int = 256) -> bytes | None:
        """Extract a single thumbnail frame from a video at ~35% mark."""
        duration = self._get_duration(video_path)
        if duration <= 0:
            return None

        ts = duration * 0.35 if duration > 10 else duration * 0.5
        try:
            cmd = [
                self._ffmpeg, '-v', 'error',
                '-ss', str(ts),
                '-i', video_path,
                '-vframes', '1',
                '-vf', f'scale={max_size}:-2:flags=lanczos',
                '-q:v', '3',
                '-f', 'image2',
                'pipe:1'
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=15)
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except Exception as e:
            logger.warning(f"Thumbnail extraction failed for {video_path}: {e}")
        return None

    def extract_keyframe(self, video_path: str) -> ExtractedFrame | None:
        """Extract the most representative keyframe from a video."""
        duration = self._get_duration(video_path)
        if duration <= 0:
            return None

        # For videos > 20s, extract from middle section
        if duration > 20:
            ts = duration * 0.35  # ~35% mark often has best composition
        else:
            ts = duration * 0.5

        frame_data = self._extract_at_timestamp(video_path, ts)
        if not frame_data:
            return None

        from PIL import Image
        from io import BytesIO
        img = Image.open(BytesIO(frame_data))

        return ExtractedFrame(
            frame_data=frame_data,
            timestamp=ts,
            width=img.width,
            height=img.height,
            is_key_frame=True,
        )

    def _get_duration(self, video_path: str) -> float:
        """Get video duration in seconds."""
        # Try ffprobe JSON output first (most robust)
        try:
            ffprobe = self._ffmpeg.replace('ffmpeg', 'ffprobe', 1)
            cmd = [ffprobe, '-v', 'quiet', '-print_format', 'json',
                   '-show_format', video_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout:
                info = json.loads(result.stdout)
                duration = info.get('format', {}).get('duration')
                if duration and duration.lower() not in ('nan', 'N/A', ''):
                    return float(duration)
        except Exception as e:
            logger.debug(f"ffprobe JSON failed for {video_path}: {e}")

        # Fallback: ffmpeg format duration
        try:
            cmd = [self._ffmpeg, '-v', 'error', '-show_entries', 'format=duration',
                   '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return 0.0
            raw = result.stdout.strip()
            if not raw or raw.lower() in ('nan', 'N/A', ''):
                return 0.0
            return float(raw)
        except Exception:
            pass

        # Last resort: try stream duration
        try:
            ffprobe = self._ffmpeg.replace('ffmpeg', 'ffprobe', 1)
            cmd = [ffprobe, '-v', 'quiet', '-print_format', 'json',
                   '-show_streams', '-select_streams', 'v:0', video_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout:
                info = json.loads(result.stdout)
                duration = info.get('streams', [{}])[0].get('duration')
                if duration and duration.lower() not in ('nan', 'N/A', ''):
                    return float(duration)
        except Exception:
            pass

        logger.error(f"Could not determine duration of {video_path}")
        return 0.0

    def _calculate_frame_count(self, duration: float) -> int:
        """Calculate optimal frame count based on video duration."""
        if duration <= 5:
            return 1
        elif duration <= 10:
            return 2
        elif duration <= 20:
            return 3
        elif duration <= 60:
            return 5
        else:
            return 7

    def _spread_timestamps(self, duration: float, count: int) -> list[float]:
        """Calculate evenly-spaced timestamps across the video."""
        if count <= 0:
            return []
        if count == 1:
            return [duration * 0.5]

        # Spread timestamps evenly, avoiding very start and end
        margin = min(duration * 0.02, 2.0)  # 2% margin or 2s, whichever less
        effective_duration = duration - 2 * margin
        step = effective_duration / (count - 1) if count > 1 else 0

        timestamps = []
        for i in range(count):
            ts = margin + (i * step)
            timestamps.append(ts)

        return timestamps

    def _extract_at_timestamp(self, video_path: str, timestamp: float) -> bytes | None:
        """Extract a single frame at a specific timestamp."""
        try:
            cmd = [
                self._ffmpeg, '-v', 'error',
                '-ss', str(timestamp),
                '-i', video_path,
                '-vframes', '1',
                '-vf', f'scale={self.max_width}:-2:flags=lanczos',
                '-q:v', '2',
                '-f', 'image2',
                'pipe:1'
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode == 0 and result.stdout:
                return result.stdout
            return None
        except subprocess.TimeoutExpired:
            logger.warning(f"Frame extraction timed out at {timestamp:.1f}s")
            return None
        except Exception as e:
            logger.error(f"Failed to extract frame at {timestamp:.1f}s: {e}")
            return None
