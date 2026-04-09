import logging

import trafilatura

logger = logging.getLogger(__name__)

MIN_CONTENT_LENGTH = 100


class FullTextExtractor:
    """Extracts full article text from URLs using trafilatura."""

    def extract(self, url: str) -> str | None:
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                logger.warning("Failed to download: %s", url)
                return None

            text = trafilatura.extract(downloaded)
            if not text or len(text.strip()) < MIN_CONTENT_LENGTH:
                logger.warning("Extraction too short or empty: %s", url)
                return None

            return text
        except Exception:
            logger.warning("Extraction failed for %s", url, exc_info=True)
            return None
