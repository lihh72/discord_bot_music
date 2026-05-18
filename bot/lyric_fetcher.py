"""MpaiBot Lyric Fetcher - LRCLib API integration and LRC parser."""
import asyncio
import logging
import re
from dataclasses import dataclass
from typing import List, Optional

import aiohttp

logger = logging.getLogger("mpaibot")


@dataclass
class LyricLine:
    """Represents a single timestamped lyric line."""
    timestamp_ms: int  # Milliseconds from start
    text: str


class LyricFetcher:
    """Fetches and parses synced lyrics from LRCLib API."""

    API_URL = "https://lrclib.net/api/search"

    async def fetch_lyrics(self, title: str, artist: str) -> Optional[List[LyricLine]]:
        """Fetch synced lyrics from LRCLib.

        Searches for synced lyrics using song title and artist name.
        Returns parsed LyricLine list or None if not found.
        Completes within 5 seconds (timeout).

        Args:
            title: Song title to search for.
            artist: Artist name to search for.

        Returns:
            List of LyricLine objects if synced lyrics found, None otherwise.
        """
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                params = {"track_name": title, "artist_name": artist}
                async with session.get(self.API_URL, params=params) as resp:
                    if resp.status != 200:
                        logger.warning(
                            "LRCLib API returned status %d for '%s' by '%s'",
                            resp.status, title, artist
                        )
                        return None
                    data = await resp.json()
                    if not data:
                        logger.info("No lyrics found for '%s' by '%s'", title, artist)
                        return None
                    synced = data[0].get("syncedLyrics")
                    if not synced:
                        logger.info(
                            "No synced lyrics available for '%s' by '%s'", title, artist
                        )
                        return None
                    return self.parse_lrc(synced)
        except asyncio.TimeoutError:
            logger.error(
                "LRCLib API timeout for '%s' by '%s'", title, artist
            )
            return None
        except aiohttp.ClientError as e:
            logger.error(
                "LRCLib API client error for '%s' by '%s': %s", title, artist, e
            )
            return None
        except Exception as e:
            logger.error(
                "Unexpected error fetching lyrics for '%s' by '%s': %s",
                title, artist, e
            )
            return None

    def parse_lrc(self, lrc_text: str) -> List[LyricLine]:
        """Parse LRC format text into list of LyricLine objects.

        Parses timestamps in [mm:ss.xx] format and extracts lyric text.
        Lines without valid timestamps are skipped.

        Args:
            lrc_text: Raw LRC format text with timestamped lines.

        Returns:
            List of LyricLine objects sorted by timestamp.
        """
        lines = []
        for line in lrc_text.strip().split("\n"):
            match = re.match(r"\[(\d+):(\d+)\.(\d+)\](.*)", line)
            if match:
                minutes, seconds, centiseconds, text = match.groups()
                timestamp_ms = (
                    (int(minutes) * 60 + int(seconds)) * 1000
                    + int(centiseconds) * 10
                )
                lines.append(LyricLine(timestamp_ms=timestamp_ms, text=text.strip()))
        return lines

    def format_lrc(self, lyrics: List[LyricLine]) -> str:
        """Convert LyricLine list back to LRC format text.

        Formats each LyricLine into [mm:ss.xx] text format.
        This is the inverse of parse_lrc() for round-trip testing.

        Args:
            lyrics: List of LyricLine objects to format.

        Returns:
            LRC format text string.
        """
        lines = []
        for lyric in lyrics:
            total_ms = lyric.timestamp_ms
            minutes = total_ms // 60000
            remaining_ms = total_ms % 60000
            seconds = remaining_ms // 1000
            centiseconds = (remaining_ms % 1000) // 10
            lines.append(f"[{minutes:02d}:{seconds:02d}.{centiseconds:02d}] {lyric.text}")
        return "\n".join(lines)

