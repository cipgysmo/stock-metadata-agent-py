"""Camera movement detection from video frame analysis."""

import logging
import cv2
import numpy as np
from core.video.extractor import ExtractedFrame

logger = logging.getLogger(__name__)


class MovementDetector:
    """Detects camera movement from a sequence of extracted frames."""

    def __init__(self, min_frame_count: int = 2):
        self.min_frame_count = min_frame_count

    def detect(self, frames: list[ExtractedFrame]) -> str:
        """Detect the dominant camera movement from frames.

        Returns:
            Movement type string (e.g., 'Drone Footage', 'Static Shot')
        """
        if len(frames) < self.min_frame_count:
            return 'Static Shot'

        movements = self._analyze_frame_sequences(frames)
        return self._classify_movement(movements)

    def _analyze_frame_sequences(self, frames: list[ExtractedFrame]) -> dict:
        """Analyze frame sequences to detect movement patterns."""
        metrics = {
            'horizontal_shift': 0.0,
            'vertical_shift': 0.0,
            'zoom_change': 0.0,
            'rotation_change': 0.0,
            'similarity_scores': [],
            'total_frames': len(frames),
        }

        for i in range(len(frames) - 1):
            frame1 = self._frame_to_array(frames[i])
            frame2 = self._frame_to_array(frames[i + 1])

            if frame1 is None or frame2 is None:
                continue

            # Resize to common size for comparison
            size = (160, 90)
            f1 = cv2.resize(frame1, size)
            f2 = cv2.resize(frame2, size)

            # Convert to grayscale
            g1 = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
            g2 = cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY)

            # Compute optical flow for shift detection
            flow = self._compute_flow(g1, g2)
            if flow is not None:
                metrics['horizontal_shift'] += abs(np.mean(flow[:, :, 0]))
                metrics['vertical_shift'] += abs(np.mean(flow[:, :, 1]))

            # Compute similarity
            score = self._compute_similarity(g1, g2)
            metrics['similarity_scores'].append(score)

        # Normalize by number of comparisons
        comparisons = max(len(frames) - 1, 1)
        metrics['horizontal_shift'] /= comparisons
        metrics['vertical_shift'] /= comparisons

        return metrics

    def _classify_movement(self, metrics: dict) -> str:
        """Classify movement type from analyzed metrics."""
        h_shift = metrics['horizontal_shift']
        v_shift = metrics['vertical_shift']
        avg_similarity = (sum(metrics['similarity_scores']) / len(metrics['similarity_scores']
                             ) if metrics['similarity_scores'] else 1.0)
        total = h_shift + v_shift

        # Very similar frames with slight changes = timelapse
        if avg_similarity > 0.85 and total < 2.0:
            return 'Timelapse'

        # High vertical shift suggests aerial/drone
        if v_shift > h_shift * 1.5 and v_shift > 5.0:
            return 'Aerial Footage'

        # Combined significant movement
        if total > 10.0:
            if v_shift > h_shift:
                return 'Flyover'
            else:
                return 'Drone Footage'

        # Moderate movement with direction
        if total > 5.0:
            if abs(h_shift - v_shift) < 3.0:
                return 'Tracking Shot'
            elif h_shift > v_shift:
                return 'Tracking Shot'
            else:
                return 'Push In'

        # Slight movement
        if total > 2.0:
            return 'Cinematic Movement'

        return 'Static Shot'

    def _frame_to_array(self, frame: ExtractedFrame) -> np.ndarray | None:
        """Convert frame bytes to OpenCV array."""
        try:
            from PIL import Image
            from io import BytesIO
            img = Image.open(BytesIO(frame.frame_data))
            arr = np.array(img)
            # PIL loads as RGB, convert to BGR for OpenCV
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.warning(f"Failed to convert frame: {e}")
            return None

    def _compute_flow(self, gray1: np.ndarray, gray2: np.ndarray) -> np.ndarray | None:
        """Compute sparse optical flow between two frames."""
        try:
            # Use Farneback dense flow for robustness
            flow = cv2.calcOpticalFlowFarneback(
                gray1, gray2, None, 0.5, 3, 15, 3, 5, 1.2, 0
            )
            return flow
        except cv2.error:
            return None

    def _compute_similarity(self, gray1: np.ndarray, gray2: np.ndarray) -> float:
        """Compute similarity between two grayscale frames."""
        try:
            # Structural similarity
            score, _ = cv2.createTemplateMatching(cv2.TM_CCOEFF_NORMED).match(gray1, gray2)
            # Simpler: correlation
            corr = np.corrcoef(gray1.flatten(), gray2.flatten())[0, 1]
            return float(corr)
        except Exception:
            return 0.0
