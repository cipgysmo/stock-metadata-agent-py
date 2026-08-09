"""Batch processing orchestrator with parallel execution."""

import concurrent.futures
import logging
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import QObject, Signal

from config.constants import (
    IMAGE_EXTENSIONS, SETTINGS_DIR, EMBEDDABLE_VIDEO_FORMATS, SIDECAR_VIDEO_FORMATS
)
from core.scanner import Scanner, MediaFile
from core.location.parser import LocationParser, Location
from core.location.gps import GPSValidator, GPSInfo
from core.metadata.writer import MetadataWriter
from core.metadata.sidecar import XmpSidecarWriter
from core.video.extractor import VideoFrameExtractor
from core.video.movement import MovementDetector
from core.quality.scorer import QualityValidator, QualityScore
from core.duplicate import DuplicateDetector, DuplicateGroup
from ai.client import AIClient
from ai.vision import VisionAnalyzer, VisionAnalysis
from ai.generator import MetadataGenerator, GeneratedMetadata
from db.memory import LocationMemory, LocationRecord

logger = logging.getLogger(__name__)


class _OrchestratorSignals(QObject):
    """Signal emitter for thread-safe UI updates from orchestrator."""
    progress_updated = Signal(int, int, str)
    file_result_ready = Signal(object)  # FileResult


class _WorkerSignals(QObject):
    """Signal emitter for thread-safe batch completion."""
    batch_finished = Signal(object)  # BatchReport
    batch_error = Signal(str)


@dataclass
class FileResult:
    """Result of processing a single file."""
    file_path: str
    success: bool = False
    title: str = ''
    description: str = ''
    keywords: list[str] = field(default_factory=list)
    top_keywords: list[str] = field(default_factory=list)
    content_type: str = 'Commercial'
    category: str = ''
    quality_score: int = 0
    issues: list[str] = field(default_factory=list)
    vision_analysis: VisionAnalysis = None
    warnings: list[str] = field(default_factory=list)
    duplicate_of: str = ''
    similarity_score: int = 0
    gps_inconsistent: bool = False
    needs_review: bool = False
    output_file: str = ''  # Path to written metadata file or sidecar

    def __post_init__(self):
        if self.vision_analysis is None:
            self.vision_analysis = VisionAnalysis()


@dataclass
class BatchReport:
    """Summary report for a batch processing run."""
    total_files: int = 0
    images_processed: int = 0
    videos_processed: int = 0
    successful: int = 0
    failed: int = 0
    cancelled: int = 0
    duplicates_found: int = 0
    similar_found: int = 0
    gps_inconsistencies: int = 0
    files_needing_review: int = 0
    commercial_warnings: int = 0
    average_quality: float = 0.0
    results: list[FileResult] = field(default_factory=list)
    total_time: float = 0.0
    avg_time_per_file: float = 0.0

    @property
    def quality_scores(self) -> list[int]:
        return [r.quality_score for r in self.results if r.quality_score > 0]

    def format_total_time(self) -> str:
        m, s = divmod(int(self.total_time), 60)
        if m:
            return f"{m}m {s}s"
        return f"{s}s"


# Thread-local storage for per-worker objects
class _WorkerContext(threading.local):
    def __init__(self):
        self.vision_client = None
        self.text_client = None


class BatchOrchestrator:
    """Orchestrates the full batch processing pipeline."""

    def __init__(self, settings):
        self.settings = settings
        self._abort = threading.Event()
        self._lock = threading.Lock()
        self._progress_callback: Callable = None
        self._file_callback: Callable = None
        # Signals for thread-safe UI updates
        self.signals = _OrchestratorSignals()
        # Semaphore to limit concurrent vision requests
        self._vision_semaphore = threading.Semaphore(3)
        # Semaphore to limit concurrent text requests
        self._text_semaphore = threading.Semaphore(3)

        # Shared components (thread-safe)
        self.location_parser = LocationParser()
        self.quality_validator = QualityValidator()
        self.location_memory = LocationMemory()

        # Per-worker state
        self._worker_context = _WorkerContext()

    def set_progress_callback(self, callback: Callable[[int, int, str], None]) -> None:
        """Set callback for progress updates: (current, total, message)."""
        from PySide6.QtCore import Qt
        self._progress_callback = callback
        # Also connect the signal with QueuedConnection for thread safety
        self.signals.progress_updated.connect(callback, Qt.ConnectionType.QueuedConnection)

    def set_file_callback(self, callback: Callable[[FileResult], None]) -> None:
        """Set callback for per-file results."""
        from PySide6.QtCore import Qt
        self._file_callback = callback
        # Also connect the signal with QueuedConnection for thread safety
        self.signals.file_result_ready.connect(callback, Qt.ConnectionType.QueuedConnection)

    def cancel(self) -> None:
        """Signal the batch to cancel."""
        self._abort.set()

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.location_memory:
            self.location_memory.close()

    def is_cancelled(self) -> bool:
        return self._abort.is_set()

    def run(self, root_path: str) -> BatchReport:
        """Run the full batch processing pipeline."""
        self._abort.clear()
        report = BatchReport()
        t0 = time.time()

        logger.info(f"Starting batch processing: {root_path}")

        # Phase 1: Scan
        self._report_progress(0, 0, "Scanning files...")
        scanner = Scanner(root_path)
        files = scanner.scan()

        if not files:
            logger.warning("No media files found")
            self._report_progress(0, 0, "No media files found")
            return report

        report.total_files = len(files)
        report.images_processed = sum(1 for f in files if f.file_type == 'image')
        report.videos_processed = sum(1 for f in files if f.file_type == 'video')

        logger.info(f"Found {report.images_processed} images, {report.videos_processed} videos")
        self._report_progress(0, report.total_files, f"Found {report.total_files} files — starting...")

        # Phase 2: Initialize duplicate detector
        duplicate_detector = DuplicateDetector(
            duplicate_threshold=self.settings.get('duplicate_threshold', 10),
            similar_threshold=self.settings.get('similar_threshold', 30),
        )

        # Phase 3: Process files in parallel
        max_workers = min(self.settings.max_workers, len(files))
        logger.info(f"Processing with {max_workers} workers")

        results: list[FileResult] = []

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='processor') as pool:
            futures = {
                pool.submit(self._process_file, f, duplicate_detector): f
                for f in files
            }

            # Polling loop — checks abort flag frequently instead of blocking on as_completed
            remaining = list(futures.keys())
            while remaining:
                if self._abort.is_set():
                    report.cancelled = len(remaining)
                    logger.info(f"Batch cancelled by user: {len(remaining)} files remaining")
                    for f in remaining:
                        f.cancel()
                    pool.shutdown(wait=False, cancel_futures=True)
                    break

                done = [f for f in remaining if f.done()]
                for f in done:
                    remaining.remove(f)

                for future in done:
                    file_info = futures[future]
                    try:
                        result = future.result()
                        with self._lock:
                            results.append(result)
                            if result.success:
                                report.successful += 1
                            else:
                                report.failed += 1
                            if result.duplicate_of:
                                if result.similarity_score <= duplicate_detector.duplicate_threshold:
                                    report.duplicates_found += 1
                                else:
                                    report.similar_found += 1
                            if result.gps_inconsistent:
                                report.gps_inconsistencies += 1
                            if result.needs_review:
                                report.files_needing_review += 1
                            if result.vision_analysis and (
                                result.vision_analysis.has_logos or
                                result.vision_analysis.needs_model_release or
                                result.vision_analysis.needs_property_release
                            ):
                                report.commercial_warnings += 1

                        # Callbacks
                        try:
                            self.signals.file_result_ready.emit(result)
                        except Exception as e:
                            logger.warning(f"File result signal error: {e}")

                        # Build progress message
                        fname = os.path.basename(file_info.path)
                        if not result.success and result.issues:
                            msg = f"FAIL {fname}: {result.issues[0][:50]}"
                        else:
                            msg = f"OK {fname}"
                        self._report_progress(len(results), report.total_files, msg)

                    except Exception as e:
                        logger.error(f"Error processing {file_info.path}: {e}")
                        with self._lock:
                            results.append(FileResult(
                                file_path=file_info.path,
                                success=False,
                                issues=[f"Processing failed: {e}"],
                            ))
                            report.failed += 1

                # Short sleep when no futures completed to avoid busy-waiting
                if not done:
                    time.sleep(0.05)

        # Phase 4: Generate full duplicate groups
        dup_groups = duplicate_detector.find_duplicates()
        for group in dup_groups:
            for similar in group.similar_files:
                for r in results:
                    if r.file_path == similar:
                        r.duplicate_of = group.representative
                        r.similarity_score = group.similarity_scores.get(similar, 0)

        report.results = results

        # Calculate average quality
        if report.quality_scores:
            report.average_quality = sum(report.quality_scores) / len(report.quality_scores)

        # Phase 5: Update location memory
        if self.settings.auto_learn_location:
            self._update_location_memory(report)

        # Timing — only count files that were actually processed
        processed = report.successful + report.failed
        report.total_time = time.time() - t0
        if processed > 0:
            report.avg_time_per_file = report.total_time / processed

        if report.cancelled > 0:
            logger.info(f"Batch cancelled: {report.successful} successful, {report.failed} failed, "
                        f"{report.cancelled} skipped, "
                        f"total: {report.total_time:.1f}s ({report.avg_time_per_file:.1f}s/file)")
        else:
            logger.info(f"Batch complete: {report.successful}/{report.total_files} successful, "
                        f"avg quality: {report.average_quality:.0f}, "
                        f"total: {report.total_time:.1f}s ({report.avg_time_per_file:.1f}s/file)")

        return report

    def _process_file(self, file_info: MediaFile,
                      dup_detector: DuplicateDetector) -> FileResult:
        """Process a single file through the full pipeline."""
        result = FileResult(file_path=file_info.path)
        fname = os.path.basename(file_info.path)
        timings = {}
        t0 = time.time()

        try:
             # Initialize per-file clients
            t = time.time()
            vision_client, text_client, fallback_client = self._get_clients()
            timings['clients'] = time.time() - t

            # Step 1: Parse folder location (fast, needed early)
            t = time.time()
            folder_location = self.location_parser.parse(file_info.folder_location)
            timings['location_parse'] = time.time() - t

            # Build minimal context for vision (folder location only)
            context = {'location_hint': folder_location.display_name}

            # Steps 2-3: Extract GPS + analyze with vision IN PARALLEL (independent)
            t = time.time()
            if file_info.file_type == 'image':
                # Run GPS extraction and vision analysis concurrently
                gps_result = [None]
                vision_result = [VisionAnalysis()]

                def _do_gps():
                    try:
                        gv = GPSValidator()
                        gps_result[0] = gv.extract_gps(file_info.path)
                    except Exception:
                        pass

                def _do_vision():
                    try:
                        if self._abort.is_set():
                            return
                        if not self._vision_semaphore.acquire(timeout=120):
                            raise TimeoutError("Vision semaphore timeout")
                        try:
                            vision_result[0] = self._analyze_image(file_info, vision_client, context)
                        finally:
                            self._vision_semaphore.release()
                    except Exception:
                        pass

                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pe:
                    pe.submit(_do_gps)
                    pe.submit(_do_vision)
                    pe.shutdown(wait=True)

                gps_info = gps_result[0]
                vision = vision_result[0]
                timings['gps'] = 0
                timings['vision'] = time.time() - t
            else:
                # Video: sequential (GPS + vision)
                gps_validator = GPSValidator()
                gps_info = gps_validator.extract_gps(file_info.path)
                timings['gps'] = time.time() - t

                t = time.time()
                vision = VisionAnalysis()
                if self._abort.is_set():
                    return result
                if not self._vision_semaphore.acquire(timeout=120):
                    raise TimeoutError("Vision semaphore timeout - server overloaded")
                try:
                    vision, movement = self._analyze_video(file_info, vision_client, context)
                finally:
                    self._vision_semaphore.release()
                timings['vision'] = time.time() - t

            # Post-parallel: build location from GPS + folder results
            if gps_info and gps_info.has_gps:
                effective_city = gps_info.exif_city or folder_location.city
                effective_region = gps_info.exif_region or gps_info.exif_state or folder_location.region
                effective_country = gps_info.exif_country or folder_location.country
                effective_sublocation = gps_info.exif_sublocation or ''
            else:
                effective_city = folder_location.city
                effective_region = folder_location.region
                effective_country = folder_location.country
                effective_sublocation = ''

            location = Location(
                city=effective_city,
                country=effective_country,
                region=effective_region,
                landmark=folder_location.landmark,
                sublocation=effective_sublocation,
            )

            # GPS validation
            if gps_info and gps_info.has_gps:
                gps_validator = GPSValidator()
                gps_check = gps_validator.validate(gps_info, location.country, location.city)
                if not gps_check.get('consistent', True):
                    result.gps_inconsistent = True
                    result.warnings.append(gps_check.get('message', 'GPS mismatch'))

            # Location memory lookup
            mem_record = None
            if location.city:
                mem_record = self.location_memory.lookup(location.city, location.country)
            if mem_record:
                context['known_landmarks'] = mem_record.ai_landmarks

            result.vision_analysis = vision

            # Step 7: Safety flags
            if vision.has_logos:
                result.warnings.append(f"Logos detected: {', '.join(vision.logos_detected)}")
                result.needs_review = True
            if vision.needs_model_release:
                result.warnings.append("Model release may be required")
                result.needs_review = True
            if vision.needs_property_release:
                result.warnings.append("Property release may be required")
                result.needs_review = True

            # Step 8: Generate metadata
            t = time.time()
            if self._abort.is_set():
                return result
            if not self._text_semaphore.acquire(timeout=120):
                raise TimeoutError("Text semaphore timeout - server overloaded")
            try:
                generator = MetadataGenerator(text_client, max_tokens=1500, fallback_client=fallback_client)
                # Extract date from EXIF for editorial content
                date_str = ''
                if gps_info and gps_info.raw_data:
                    for date_field in ('DateTimeOriginal', 'CreateDate', 'DateTimeDigitized'):
                        if date_field in gps_info.raw_data:
                            date_str = gps_info.raw_data[date_field][:10]
                            break
                metadata = generator.generate(vision, location,
                                              is_video=(file_info.file_type == 'video'),
                                              gps_info=gps_info,
                                              date_string=date_str)
            finally:
                self._text_semaphore.release()
            timings['metadata'] = time.time() - t

            result.title = metadata.title
            result.description = metadata.description
            result.content_type = metadata.content_type
            result.category = metadata.category
            result.keywords = metadata.keywords
            result.top_keywords = metadata.top_keywords

            # Merge technology keywords when technology-focused scene
            if vision.technology_focus and vision.technology_keywords:
                all_keywords = list(vision.technology_keywords)
                for kw in metadata.keywords:
                    kw_lower = kw.lower().strip()
                    if kw_lower and kw_lower not in [k.lower() for k in all_keywords]:
                        all_keywords.append(kw_lower)
                result.keywords = all_keywords
                result.top_keywords = result.keywords[:10]

            # Fix keyword count
            result.keywords = self._fix_keywords(result.keywords)
            result.top_keywords = result.keywords[:10]

            # Step 9: Validate
            validated_meta = GeneratedMetadata(
                title=result.title,
                description=result.description,
                keywords=result.keywords,
                top_keywords=result.top_keywords,
                content_type=result.content_type,
                category=result.category,
            )
            issues = self.quality_validator.validate(validated_meta)
            result.issues.extend(issues)

            # Step 10: Quality score
            quality = self.quality_validator.score(
                validated_meta,
                vision,
                location
            )
            result.quality_score = quality.overall
            result.issues.extend(quality.issues)

            # Step 11: Write metadata
            t = time.time()
            if self._abort.is_set():
                return result
            if result.title and result.description and result.keywords:
                self._write_metadata(file_info, result)
            timings['write'] = time.time() - t

            result.success = (
                result.title and
                result.description and
                len(result.keywords) >= 30
            )

            elapsed = time.time() - t0
            logger.info(f"[{fname}] Done in {elapsed:.1f}s "
                       f"(clients={timings['clients']:.2f}s, "
                       f"gps={timings['gps']:.2f}s, "
                       f"vision={timings['vision']:.2f}s, "
                       f"metadata={timings['metadata']:.2f}s, "
                       f"write={timings['write']:.2f}s)")

        except Exception as e:
            import traceback
            logger.error(f"Error processing {file_info.path}: {e}\n{traceback.format_exc()}")
            result.success = False
            result.issues.append(str(e))

        return result

    def _get_clients(self) -> tuple[AIClient, AIClient, AIClient | None]:
        """Get or create AI clients for the current thread."""
        import threading
        tid = threading.current_thread().name

        vision_client = AIClient(
            base_url=self.settings.vision_endpoint,
            api_key=self.settings.vision_api_key,
            model=self.settings.vision_model,
            timeout=120,
        )
        text_client = AIClient(
            base_url=self.settings.text_endpoint,
            api_key=self.settings.text_api_key,
            model=self.settings.text_model,
            timeout=120,
        )

        # Cloud fallback client
        fallback_client = None
        if self.settings.get('cloud_text_enabled', False):
            cloud_key = self.settings.get('cloud_text_api_key', '')
            if cloud_key:
                fallback_client = AIClient(
                    base_url=self.settings.get('cloud_text_endpoint', 'https://api.openai.com'),
                    api_key=cloud_key,
                    model=self.settings.get('cloud_text_model', 'gpt-4o-mini'),
                    timeout=60,
                )

        return vision_client, text_client, fallback_client

    def _analyze_image(self, file_info: MediaFile, vision_client: AIClient,
                       context: dict) -> VisionAnalysis:
        """Analyze an image file."""
        with open(file_info.path, 'rb') as f:
            image_data = f.read()

        mime_type = 'image/jpeg'
        if file_info.extension == '.png':
            mime_type = 'image/png'
        elif file_info.extension in ('.tiff', '.tif'):
            mime_type = 'image/tiff'

        analyzer = VisionAnalyzer(vision_client,
                                   image_resize=self.settings.get('image_resize_max', 1280))
        return analyzer.analyze_image(image_data, mime_type, context)

    def _analyze_video(self, file_info: MediaFile, vision_client: AIClient,
                       context: dict) -> tuple[VisionAnalysis, str]:
        """Analyze a video file. Returns (vision, movement)."""
        extractor = VideoFrameExtractor(max_width=self.settings.get('image_resize_max', 1280))
        frames = extractor.extract_frames(file_info.path)

        if not frames:
            return VisionAnalysis(is_video=True), 'Static Shot'

        # Detect movement
        detector = MovementDetector()
        movement = detector.detect(frames)

        # Analyze key frame (most representative)
        key_frame = frames[0]
        for f in frames:
            if f.is_key_frame:
                key_frame = f
                break

        analyzer = VisionAnalyzer(vision_client,
                                   image_resize=self.settings.get('image_resize_max', 1280))
        vision = analyzer.analyze_video_frame(
            key_frame.frame_data, context, is_key_frame=True
        )

        return vision, movement

    def _fix_keywords(self, keywords: list[str]) -> list[str]:
        """Ensure 30-35 unique keywords, clean pipe characters."""
        from config.constants import MAX_KEYWORD_COUNT, MIN_KEYWORD_COUNT
        # Split on pipes first — LLM sometimes outputs "a|b|c" instead of comma-separated
        expanded = []
        for kw in keywords:
            expanded.extend(kw.replace('|', ',').split(','))
        # Remove duplicates, preserve order
        seen = set()
        unique = []
        for kw in expanded:
            kw_lower = kw.lower().strip()
            if kw_lower and kw_lower not in seen:
                seen.add(kw_lower)
                unique.append(kw_lower)

        # Trim or pad to 30-35
        if len(unique) > MAX_KEYWORD_COUNT:
            return unique[:MAX_KEYWORD_COUNT]
        if len(unique) >= MIN_KEYWORD_COUNT:
            return unique

        # Pad with generic keywords if too few
        generic_pad = [
            'stock photography', 'stock photo', 'professional photography',
            'high quality', 'creative', 'art', 'concept', 'idea',
            'inspiration', 'visual', 'design', 'background', 'scene',
            'environment', 'outdoor', 'photograph', 'capture', 'shot',
        ]
        for g in generic_pad:
            if len(unique) >= MIN_KEYWORD_COUNT:
                break
            if g.lower() not in seen:
                unique.append(g.lower())
                seen.add(g.lower())

        return unique[:MAX_KEYWORD_COUNT]

    def _write_metadata(self, file_info: MediaFile, result: FileResult) -> None:
        """Write metadata to the file or create sidecar."""
        writer = MetadataWriter()

        if self.settings.output_format == 'embedded':
            success = writer.write(
                file_info.path, result.title, result.description, result.keywords
            )
            if success:
                result.output_file = file_info.path
            else:
                # Fallback to sidecar
                self._write_sidecar(file_info, result)
        else:
            self._write_sidecar(file_info, result)

    def _write_sidecar(self, file_info: MediaFile, result: FileResult) -> None:
        """Write metadata as XMP sidecar."""
        sidecar = XmpSidecarWriter()
        xmp_path = sidecar.write(
            file_info.path, result.title, result.description, result.keywords
        )
        if xmp_path:
            result.output_file = xmp_path

    def _update_location_memory(self, report: BatchReport) -> None:
        """Update location memory from batch results."""
        for result in report.results:
            if not result.vision_analysis:
                continue

            vision = result.vision_analysis
            if vision.city and vision.country:
                # Check if already known
                existing = self.location_memory.lookup(vision.city, vision.country)
                if not existing:
                    record = LocationRecord(
                        city=vision.city,
                        country=vision.country,
                        region=vision.region,
                        landmark=vision.landmark,
                        ai_landmarks=list(vision.visible_objects)[:5],
                        gps_samples=1,
                    )
                    self.location_memory.learn(record)
                    logger.debug(f"Learned new location: {vision.city}, {vision.country}")

    def _report_progress(self, current: int, total: int, message: str) -> None:
        """Report progress update."""
        try:
            self.signals.progress_updated.emit(current, total, message)
        except Exception as e:
            logger.warning(f"Progress signal error: {e}")
