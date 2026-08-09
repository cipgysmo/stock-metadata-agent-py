"""XMP sidecar file generation for unsupported formats."""

import os
import logging

logger = logging.getLogger(__name__)


class XmpSidecarWriter:
    """Generates .xmp sidecar files when embedded metadata is not supported."""

    def write(self, file_path: str, title: str, description: str,
              keywords: list[str]) -> str | None:
        """Write an XMP sidecar file.

        Args:
            file_path: Path to the original media file
            title: Title/Headline
            description: Description/Caption
            keywords: List of keywords

        Returns:
            Path to the created .xmp file, or None on failure.
        """
        xmp_path = os.path.splitext(file_path)[0] + '.xmp'

        # Sanitize special characters for XML
        title = self._xml_escape(title)
        description = self._xml_escape(description)
        keywords_escaped = [self._xml_escape(k) for k in keywords]

        # Build keyword list as semicolon-separated for XMP
        keywords_str = '; '.join(keywords_escaped)

        xmp_content = f"""<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="StockMetadataAgent">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:Iptc4xmpCore="http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/"
    xmlns:xmp="http://ns.adobe.com/xap/1.0/">
   <dc:title>{title}</dc:title>
   <dc:description>{description}</dc:description>
   <dc:Subject>{keywords_str}</dc:Subject>
   <xmp:Rating>{0}</xmp:Rating>
   <Iptc4xmpCore:ObjectName>{title}</Iptc4xmpCore:ObjectName>
   <Iptc4xmpCore:CaptionAbstract>{description}</Iptc4xmpCore:CaptionAbstract>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""

        try:
            with open(xmp_path, 'w', encoding='utf-8') as f:
                f.write(xmp_content)
            logger.debug(f"XMP sidecar written: {xmp_path}")
            return xmp_path
        except IOError as e:
            logger.error(f"Failed to write XMP sidecar {xmp_path}: {e}")
            return None

    def _xml_escape(self, text: str) -> str:
        """Escape special XML characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))


# Video formats that support embedded metadata
EMBEDDABLE_VIDEO_FORMATS = {'.mov', '.mp4', '.m4v', '.mxf'}
# Video formats that need sidecar
SIDECAR_VIDEO_FORMATS = {'.avi', '.prores', '.hevc'}
