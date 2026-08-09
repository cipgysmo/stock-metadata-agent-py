"""CSV export and agency formatting."""

import csv
import os
import logging
from core.orchestrator import FileResult

logger = logging.getLogger(__name__)

# Agency-specific formatting rules
AGENCY_FORMATS = {
    'adobe_stock': {
        'delimiter': ',',
        'keywords_sep': ',',
        'columns': ['filename', 'title', 'description', 'keywords'],
    },
    'shutterstock': {
        'delimiter': ',',
        'keywords_sep': ',',
        'columns': ['filename', 'title', 'description', 'keywords'],
    },
    'istock': {
        'delimiter': ',',
        'keywords_sep': ',',
        'columns': ['filename', 'title', 'description', 'keywords'],
    },
    'dreamstime': {
        'delimiter': ',',
        'keywords_sep': ',',
        'columns': ['filename', 'title', 'description', 'keywords'],
    },
    'depositphotos': {
        'delimiter': ',',
        'keywords_sep': ',',
        'columns': ['filename', 'title', 'description', 'keywords'],
    },
    'alamy': {
        'delimiter': ',',
        'keywords_sep': ',',
        'columns': ['filename', 'title', 'description', 'keywords'],
    },
}


class CsvExporter:
    """Exports batch results to CSV files."""

    def export_batch(self, results: list[FileResult], output_path: str,
                     agency: str = 'adobe_stock') -> str:
        """Export all results to a CSV file.

        Args:
            results: List of FileResult objects
            output_path: Path for the output CSV file
            agency: Target agency format

        Returns:
            Path to the created CSV file
        """
        fmt = AGENCY_FORMATS.get(agency, AGENCY_FORMATS['adobe_stock'])
        keywords_sep = fmt['keywords_sep']

        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=fmt['delimiter'])
            writer.writerow(['FileName', 'Title', 'Description', 'Keywords'])

            for result in results:
                if not result.success:
                    continue
                writer.writerow([
                    os.path.basename(result.file_path),
                    result.title,
                    result.description,
                    keywords_sep.join(result.keywords[:45]),
                ])

        logger.info(f"CSV exported: {output_path} ({sum(1 for r in results if r.success)} records)")
        return output_path

    def export_per_file(self, result: FileResult, output_dir: str) -> str | None:
        """Export a single result as an individual CSV file."""
        if not result.success:
            return None

        base_name = os.path.splitext(os.path.basename(result.file_path))[0]
        csv_path = os.path.join(output_dir, f"{base_name}.csv")

        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['FileName', 'Title', 'Description', 'Keywords'])
            writer.writerow([
                os.path.basename(result.file_path),
                result.title,
                result.description,
                ', '.join(result.keywords[:45]),
            ])

        return csv_path
