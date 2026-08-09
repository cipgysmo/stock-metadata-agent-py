"""Batch report generation."""

import os
from datetime import datetime
from core.orchestrator import BatchReport


class ReportGenerator:
    """Generates human-readable batch reports."""

    def generate_text(self, report: BatchReport) -> str:
        """Generate a plain text report."""
        lines = [
            "=" * 60,
            "  BATCH PROCESSING REPORT",
            f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            "",
            "SUMMARY",
            "-" * 40,
            f"Total files processed:    {report.total_files}",
            f"Images processed:         {report.images_processed}",
            f"Videos processed:         {report.videos_processed}",
            f"Successful:               {report.successful}",
            f"Failed:                   {report.failed}",
            f"Average quality score:    {report.average_quality:.1f}/100",
            "",
            "QUALITY METRICS",
            "-" * 40,
            f"Duplicates found:         {report.duplicates_found}",
            f"Similar files found:      {report.similar_found}",
            f"GPS inconsistencies:      {report.gps_inconsistencies}",
            f"Files needing review:     {report.files_needing_review}",
            f"Commercial warnings:      {report.commercial_warnings}",
            "",
        ]

        # Quality distribution
        if report.quality_scores:
            scores = report.quality_scores
            lines.append("QUALITY DISTRIBUTION")
            lines.append("-" * 40)
            ranges = [('Excellent (90+)', 90, 100), ('Good (70-89)', 70, 89),
                       ('Fair (50-69)', 50, 69), ('Poor (<50)', 0, 49)]
            for label, low, high in ranges:
                count = sum(1 for s in scores if low <= s <= high)
                if count:
                    lines.append(f"  {label}: {count}")
            lines.append("")

        # Failed files
        failed = [r for r in report.results if not r.success]
        if failed:
            lines.append("FAILED FILES")
            lines.append("-" * 40)
            for r in failed:
                name = os.path.basename(r.file_path)
                issues = '; '.join(r.issues[:3])
                lines.append(f"  {name}: {issues}")
            lines.append("")

        # Files needing review
        review = [r for r in report.results if r.needs_review]
        if review:
            lines.append("FILES NEEDING REVIEW")
            lines.append("-" * 40)
            for r in review:
                name = os.path.basename(r.file_path)
                warnings = '; '.join(r.warnings[:3])
                lines.append(f"  {name}: {warnings}")
            lines.append("")

        lines.append("=" * 60)
        return '\n'.join(lines)

    def generate_text_report(self, report: BatchReport) -> str:
        """Alias for generate_text."""
        return self.generate_text(report)

    def save(self, report: BatchReport, output_dir: str) -> str:
        """Save report to a text file."""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.join(output_dir, f"report_{timestamp}.txt")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.generate_text(report))
        return path
