import logging

import httpx
import trafilatura

logger = logging.getLogger(__name__)

MIN_CONTENT_LENGTH = 100
MAX_CONTENT_LENGTH = 100_000  # ~100KB cap to prevent OOM on malicious pages
USER_AGENT = "Mozilla/5.0 (compatible; NewsBriefer/1.0)"
DOWNLOAD_TIMEOUT = 20


class FullTextExtractor:
    """Extracts full article text from URLs using trafilatura."""

    def extract(self, url: str) -> str | None:
        try:
            # Use httpx with a proper user-agent to avoid blocks (e.g. CBC),
            # then hand the HTML to trafilatura for content extraction.
            response = httpx.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=DOWNLOAD_TIMEOUT,
                follow_redirects=True,
            )
            response.raise_for_status()
            downloaded = response.text
            if not downloaded:
                logger.warning("Failed to download: %s", url)
                return None

            text = trafilatura.extract(downloaded)
            if not text or len(text.strip()) < MIN_CONTENT_LENGTH:
                logger.warning("Extraction too short or empty: %s", url)
                return None

            if len(text) > MAX_CONTENT_LENGTH:
                text = text[:MAX_CONTENT_LENGTH]

            return text
        except Exception:
            logger.warning("Extraction failed for %s", url, exc_info=True)
            return None
