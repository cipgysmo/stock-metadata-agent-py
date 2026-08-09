"""Unit tests for Stock Metadata Agent."""

import json
import os
import tempfile
import shutil
import unittest
from io import BytesIO
from PIL import Image

from config.constants import (
    IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, SUPPORTED_EXTENSIONS,
    MAX_TITLE_LENGTH, MAX_DESCRIPTION_LENGTH,
    MIN_TITLE_LENGTH, MIN_KEYWORD_COUNT, MAX_KEYWORD_COUNT,
)
from config.settings import Settings
from core.scanner import Scanner, MediaFile
from core.location.parser import LocationParser, Location
from core.location.gps import GPSInfo
from core.quality.scorer import QualityValidator, QualityScore
from core.duplicate import DuplicateDetector
from core.report import ReportGenerator
from ai.vision import VisionAnalysis
from ai.generator import GeneratedMetadata
from db.memory import LocationMemory, LocationRecord


class TestConstants(unittest.TestCase):
    """Test constants are properly defined."""

    def test_image_extensions(self):
        self.assertIn('.jpg', IMAGE_EXTENSIONS)
        self.assertIn('.jpeg', IMAGE_EXTENSIONS)
        self.assertIn('.png', IMAGE_EXTENSIONS)
        self.assertIn('.tiff', IMAGE_EXTENSIONS)

    def test_video_extensions(self):
        self.assertIn('.mp4', VIDEO_EXTENSIONS)
        self.assertIn('.mov', VIDEO_EXTENSIONS)
        self.assertIn('.avi', VIDEO_EXTENSIONS)

    def test_supported_extensions(self):
        self.assertEqual(SUPPORTED_EXTENSIONS, IMAGE_EXTENSIONS | VIDEO_EXTENSIONS)

    def test_limits(self):
        self.assertEqual(MIN_TITLE_LENGTH, 180)  # target
        self.assertEqual(MAX_TITLE_LENGTH, 200)  # hard cap
        self.assertEqual(MAX_DESCRIPTION_LENGTH, 2000)
        self.assertEqual(MIN_KEYWORD_COUNT, 30)
        self.assertEqual(MAX_KEYWORD_COUNT, 35)


class TestSettings(unittest.TestCase):
    """Test settings persistence."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.settings_file = os.path.join(self.tmpdir, 'test_settings.json')

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_load_defaults(self):
        s = Settings(self.settings_file)
        self.assertEqual(s.get('max_workers'), 2)
        self.assertEqual(s.get('output_format'), 'embedded')

    def test_save_and_load(self):
        s = Settings(self.settings_file)
        s.set('text_endpoint', 'http://test:1234')
        s.save()

        s2 = Settings(self.settings_file)
        self.assertEqual(s2.get('text_endpoint'), 'http://test:1234')

    def test_properties(self):
        s = Settings(self.settings_file)
        s.set('vision_endpoint', 'http://localhost:8000')
        s.set('text_model', 'llama-3.2-3b')
        self.assertEqual(s.vision_endpoint, 'http://localhost:8000')
        self.assertEqual(s.text_model, 'llama-3.2-3b')

    def test_validate_endpoints(self):
        s = Settings(self.settings_file)
        s.set('vision_endpoint', '')
        s.set('text_endpoint', '')
        s.set('text_model', '')
        missing = s.validate_endpoints()
        self.assertIn('vision_endpoint', missing)
        self.assertIn('text_endpoint', missing)
        self.assertIn('text_model', missing)

    def test_validate_ok(self):
        s = Settings(self.settings_file)
        s.set('vision_endpoint', 'http://localhost:8000')
        s.set('text_endpoint', 'http://remote:3000')
        s.set('text_model', 'some-model')
        missing = s.validate_endpoints()
        self.assertEqual(missing, [])


class TestScanner(unittest.TestCase):
    """Test file scanner."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create test files
        for name in ['photo1.jpg', 'photo2.png', 'video1.mp4', 'readme.txt']:
            path = os.path.join(self.tmpdir, name)
            with open(path, 'wb') as f:
                f.write(b'test content')

        # Create subfolder
        subdir = os.path.join(self.tmpdir, 'France', 'Brittany')
        os.makedirs(subdir)
        with open(os.path.join(subdir, 'photo3.jpg'), 'wb') as f:
            f.write(b'test content')

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_scan_finds_media(self):
        scanner = Scanner(self.tmpdir)
        files = scanner.scan()
        # Should find 3 images + 1 video = 4 (readme.txt excluded)
        self.assertEqual(len(files), 4)

    def test_scan_ignores_unsupported(self):
        scanner = Scanner(self.tmpdir)
        files = scanner.scan()
        for f in files:
            self.assertIn(f.extension, SUPPORTED_EXTENSIONS)

    def test_scan_subfolder(self):
        scanner = Scanner(self.tmpdir)
        files = scanner.scan()
        subfolder_files = [f for f in files if 'Brittany' in f.folder_path]
        self.assertEqual(len(subfolder_files), 1)
        self.assertEqual(subfolder_files[0].folder_location, 'France / Brittany')

    def test_scan_iter(self):
        scanner = Scanner(self.tmpdir)
        files = list(scanner.scan_iter())
        self.assertEqual(len(files), 4)

    def test_stats(self):
        scanner = Scanner(self.tmpdir)
        stats = scanner.get_stats()
        self.assertEqual(stats['images'], 3)
        self.assertEqual(stats['videos'], 1)
        self.assertEqual(stats['total'], 4)


class TestLocationParser(unittest.TestCase):
    """Test location parsing."""

    def setUp(self):
        self.parser = LocationParser()

    def test_slash_separated(self):
        loc = self.parser.parse('France/Brittany/Cancale')
        self.assertEqual(loc.country, 'France')
        self.assertEqual(loc.region, 'Brittany')
        self.assertEqual(loc.city, 'Cancale')

    def test_dash_separated(self):
        loc = self.parser.parse('France - Brittany - Cancale')
        self.assertEqual(loc.country, 'France')
        self.assertEqual(loc.region, 'Brittany')
        self.assertEqual(loc.city, 'Cancale')

    def test_single_component(self):
        loc = self.parser.parse('London')
        self.assertEqual(loc.city, 'London')
        self.assertEqual(loc.country, '')

    def test_two_components(self):
        loc = self.parser.parse('London England')
        # Without known country match, treats as single component
        self.assertEqual(loc.city, 'London England')

    def test_display_name(self):
        loc = self.parser.parse('France/Brittany/Cancale')
        display = loc.display_name
        self.assertIn('Cancale', display)
        self.assertIn('Brittany', display)
        self.assertIn('France', display)

    def test_primary_keyword(self):
        loc = self.parser.parse('France/Brittany/Cancale')
        self.assertEqual(loc.primary_keyword, 'Cancale')

    def test_variations(self):
        loc = self.parser.parse('France/Brittany/Cancale')
        variations = self.parser.get_location_variations(loc)
        self.assertIn('Cancale', variations)
        self.assertIn('Cancale Brittany', variations)
        self.assertIn('Cancale France', variations)
        self.assertGreaterEqual(len(variations), 3)

    def test_is_complete(self):
        loc = self.parser.parse('France/Brittany/Cancale')
        self.assertTrue(loc.is_complete)

    def test_incomplete(self):
        loc = self.parser.parse('Somewhere')
        self.assertFalse(loc.is_complete)

    def test_empty_path(self):
        loc = self.parser.parse('')
        self.assertEqual(loc.city, '')
        self.assertEqual(loc.country, '')


class TestVisionAnalysis(unittest.TestCase):
    """Test VisionAnalysis dataclass."""

    def test_defaults(self):
        analysis = VisionAnalysis()
        self.assertFalse(analysis.is_video)
        self.assertFalse(analysis.has_logos)
        self.assertTrue(analysis.is_safe_for_commercial)

    def test_safety_flags(self):
        analysis = VisionAnalysis(has_logos=True)
        self.assertFalse(analysis.is_safe_for_commercial)

        analysis2 = VisionAnalysis(needs_model_release=True)
        self.assertFalse(analysis2.is_safe_for_commercial)


class TestGeneratedMetadata(unittest.TestCase):
    """Test GeneratedMetadata dataclass."""

    def test_valid(self):
        t = 'A young woman works on a laptop at a wooden desk in a bright modern home office surrounded by potted tropical houseplants and warm natural sunlight streaming through a large window.'  # 181
        meta = GeneratedMetadata(
            title=t,
            description=t,
            keywords=[f'kw{i}' for i in range(30)]
        )
        self.assertTrue(meta.is_valid)

    def test_invalid_keywords_count(self):
        t = 'A young woman works on a laptop at a wooden desk in a bright modern home office surrounded by potted tropical houseplants and warm natural sunlight streaming through a large window.'  # 181
        meta = GeneratedMetadata(
            title=t,
            description=t,
            keywords=[f'kw{i}' for i in range(20)]
        )
        self.assertFalse(meta.is_valid)

    def test_empty(self):
        meta = GeneratedMetadata()
        self.assertFalse(meta.is_valid)


class TestQualityValidator(unittest.TestCase):
    """Test quality scoring and validation."""

    def setUp(self):
        self.validator = QualityValidator()
        # A valid 180-200 char title
        self.valid_title = 'A young woman works on a laptop at a wooden desk in a bright modern home office surrounded by potted tropical houseplants and warm natural sunlight streaming through a large window.'  # 181

    def test_validate_good_metadata(self):
        meta = GeneratedMetadata(
            title=self.valid_title,
            description=self.valid_title,
            keywords=[f'kw{i}' for i in range(30)],
            category='Lifestyle',
        )
        issues = self.validator.validate(meta)
        self.assertEqual(issues, [])

    def test_validate_title_too_long(self):
        meta = GeneratedMetadata(
            title='A' * 201 + '.',
            description='A' * 201 + '.',
            keywords=[f'kw{i}' for i in range(30)],
            category='Test',
        )
        issues = self.validator.validate(meta)
        self.assertTrue(any('long' in i.lower() for i in issues))

    def test_validate_title_too_short(self):
        meta = GeneratedMetadata(
            title='Short title.',
            description='Short title.',
            keywords=[f'kw{i}' for i in range(30)],
            category='Test',
        )
        issues = self.validator.validate(meta)
        # Short titles are warned, not rejected (model can't count reliably)
        self.assertFalse(any('short' in i.lower() for i in issues))

    def test_validate_title_no_period(self):
        meta = GeneratedMetadata(
            title='A young woman works on a laptop at a wooden desk in a bright modern home office surrounded by potted houseplants and warm natural light',
            description='A young woman works on a laptop at a wooden desk in a bright modern home office surrounded by potted houseplants and warm natural light',
            keywords=[f'kw{i}' for i in range(30)],
            category='Test',
        )
        issues = self.validator.validate(meta)
        self.assertTrue(any('period' in i.lower() for i in issues))

    def test_validate_wrong_keyword_count(self):
        meta = GeneratedMetadata(
            title=self.valid_title,
            description=self.valid_title,
            keywords=['a'] * 20,
            category='Test',
        )
        issues = self.validator.validate(meta)
        self.assertTrue(any('few' in i.lower() for i in issues))

    def test_validate_duplicate_keywords(self):
        meta = GeneratedMetadata(
            title=self.valid_title,
            description=self.valid_title,
            keywords=['duplicate'] * 30,
            category='Test',
        )
        issues = self.validator.validate(meta)
        self.assertTrue(any('duplicate' in i.lower() for i in issues))

    def test_score_with_location(self):
        vision = VisionAnalysis(
            country='France', city='Cancale', main_subject='harbor'
        )
        location = Location(city='Cancale', country='France', region='Brittany')
        t = 'Aerial view of Cancale harbor in Brittany, France, showing the picturesque fishing port with colorful boats moored in the sheltered bay along the rugged coastline.'  # 159 chars
        t = 'Aerial view of Cancale harbor in Brittany, France, showing the picturesque fishing port with colorful boats moored in the sheltered bay along the rugged Atlantic coastline.'  # 180 chars
        meta = GeneratedMetadata(
            title=t,
            description=t,
            keywords=['cancale', 'cancale france', 'cancale brittany', 'harbor'] +
                      [f'kw{i}' for i in range(41)]
        )
        score = self.validator.score(meta, vision, location)
        self.assertGreater(score.overall, 0)
        self.assertLessEqual(score.overall, 100)


class TestDuplicateDetector(unittest.TestCase):
    """Test perceptual hash duplicate detection."""

    def _make_image(self, color=(255, 0, 0)):
        img = Image.new('RGB', (100, 100), color)
        buf = BytesIO()
        img.save(buf, format='JPEG')
        return buf.getvalue()

    def test_same_image_duplicate(self):
        detector = DuplicateDetector(duplicate_threshold=10)
        img_data = self._make_image((255, 0, 0))
        detector.add('file1.jpg', img_data)
        detector.add('file2.jpg', img_data)

        results = detector.check_similar('file3.jpg', img_data)
        self.assertEqual(len(results), 2)
        for path, dist in results:
            self.assertLessEqual(dist, 10)

    def test_different_image_not_duplicate(self):
        detector = DuplicateDetector(duplicate_threshold=10)
        # Create images with different patterns, not just color
        img1 = Image.new('RGB', (100, 100), (255, 0, 0))
        # Draw a pattern on img2 to make it perceptually different
        img2 = Image.new('RGB', (100, 100), (0, 0, 0))
        for x in range(0, 100, 10):
            for y in range(0, 100, 10):
                if (x // 10 + y // 10) % 2 == 0:
                    pixels = img2.load()
                    for px in range(x, min(x+10, 100)):
                        for py in range(y, min(y+10, 100)):
                            pixels[px, py] = (255, 255, 255)

        buf1 = BytesIO()
        buf2 = BytesIO()
        img1.save(buf1, format='JPEG')
        img2.save(buf2, format='JPEG')

        detector.add('solid.jpg', buf1.getvalue())
        detector.add('pattern.jpg', buf2.getvalue())

        groups = detector.find_duplicates()
        # Solid color vs checkerboard should be very different
        self.assertEqual(len(groups), 0)

    def test_total_hashed(self):
        detector = DuplicateDetector()
        img_data = self._make_image()
        detector.add('f1.jpg', img_data)
        detector.add('f2.jpg', img_data)
        self.assertEqual(detector.total_hashed, 2)


class TestLocationMemory(unittest.TestCase):
    """Test SQLite location memory."""

    def setUp(self):
        self.db_path = os.path.join(tempfile.mkdtemp(), 'test_memory.db')
        self.memory = LocationMemory(self.db_path)

    def tearDown(self):
        self.memory.close()
        tmpdir = os.path.dirname(self.db_path)
        shutil.rmtree(tmpdir)

    def test_learn_new_location(self):
        record = LocationRecord(
            city='Cancale', country='France', region='Brittany'
        )
        is_new = self.memory.learn(record)
        self.assertTrue(is_new)

    def test_lookup_existing(self):
        record = LocationRecord(
            city='Munich', country='Germany', region='Bavaria'
        )
        self.memory.learn(record)
        found = self.memory.lookup('Munich', 'Germany')
        self.assertIsNotNone(found)
        self.assertEqual(found.city, 'munich')

    def test_update_existing(self):
        record1 = LocationRecord(city='Paris', country='France')
        self.memory.learn(record1)

        record2 = LocationRecord(
            city='Paris', country='France', region='Ile-de-France'
        )
        is_new = self.memory.learn(record2)
        self.assertFalse(is_new)

        found = self.memory.lookup('Paris', 'France')
        self.assertEqual(found.region, 'Ile-de-France')

    def test_search(self):
        self.memory.learn(LocationRecord(city='London', country='UK'))
        self.memory.learn(LocationRecord(city='Berlin', country='Germany'))

        results = self.memory.search('lond')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].city, 'london')

    def test_merge_aliases(self):
        r1 = LocationRecord(city='Paris', country='France', aliases=['Paris France'])
        self.memory.learn(r1)

        r2 = LocationRecord(city='Paris', country='France', aliases=['Ville Lumiere'])
        self.memory.learn(r2)

        found = self.memory.lookup('Paris', 'France')
        self.assertIn('paris france', [a.lower() for a in found.aliases])
        self.assertIn('ville lumiere', [a.lower() for a in found.aliases])


class TestReportGenerator(unittest.TestCase):
    """Test batch report generation."""

    def test_empty_report(self):
        from core.orchestrator import BatchReport
        report = BatchReport()
        gen = ReportGenerator()
        text = gen.generate_text(report)
        self.assertIn('BATCH PROCESSING REPORT', text)
        self.assertIn('0', text)

    def test_populated_report(self):
        from core.orchestrator import BatchReport
        report = BatchReport(
            total_files=10,
            images_processed=8,
            videos_processed=2,
            successful=9,
            failed=1,
            average_quality=85.5,
            duplicates_found=2,
            similar_found=3,
            gps_inconsistencies=1,
            files_needing_review=1,
            commercial_warnings=2,
        )
        report._QualityScore__scores = [90, 80, 75, 85, 95]

        gen = ReportGenerator()
        text = gen.generate_text(report)
        self.assertIn('10', text)
        self.assertIn('8', text)
        self.assertIn('85.5', text)

    def test_save_report(self):
        from core.orchestrator import BatchReport
        report = BatchReport(total_files=5, successful=5)
        gen = ReportGenerator()

        outdir = tempfile.mkdtemp()
        try:
            path = gen.save(report, outdir)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn('BATCH PROCESSING REPORT', content)
        finally:
            shutil.rmtree(outdir)


class TestCsvExporter(unittest.TestCase):
    """Test CSV export."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_export_batch(self):
        from core.orchestrator import FileResult
        results = [
            FileResult(
                file_path='/tmp/test1.jpg', success=True,
                title='Test Title 1', description='Test Desc 1',
                keywords=[f'kw{i}' for i in range(30)], quality_score=90,
            ),
            FileResult(
                file_path='/tmp/test2.jpg', success=True,
                title='Test Title 2', description='Test Desc 2',
                keywords=[f'kw{i}' for i in range(30)], quality_score=85,
            ),
        ]

        from export.csv import CsvExporter
        exporter = CsvExporter()
        csv_path = os.path.join(self.tmpdir, 'export.csv')
        exporter.export_batch(results, csv_path)

        self.assertTrue(os.path.exists(csv_path))
        with open(csv_path, encoding='utf-8-sig') as f:
            content = f.read()
        self.assertIn('Test Title 1', content)
        self.assertIn('Test Title 2', content)


if __name__ == '__main__':
    unittest.main()
