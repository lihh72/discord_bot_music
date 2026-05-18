"""Tests for LyricFetcher: unit tests and property-based tests for LRC parsing."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from bot.lyric_fetcher import LyricFetcher, LyricLine


# ============================================================================
# Unit Tests
# ============================================================================


class TestParseLrc:
    """Unit tests for parse_lrc() method."""

    def setup_method(self):
        self.fetcher = LyricFetcher()

    def test_parse_single_line(self):
        lrc_text = "[01:23.45] Hello world"
        result = self.fetcher.parse_lrc(lrc_text)
        assert len(result) == 1
        assert result[0].timestamp_ms == 83450
        assert result[0].text == "Hello world"

    def test_parse_multiple_lines(self):
        lrc_text = "[00:00.00] First line\n[00:05.50] Second line\n[01:00.00] Third line"
        result = self.fetcher.parse_lrc(lrc_text)
        assert len(result) == 3
        assert result[0].timestamp_ms == 0
        assert result[0].text == "First line"
        assert result[1].timestamp_ms == 5500
        assert result[1].text == "Second line"
        assert result[2].timestamp_ms == 60000
        assert result[2].text == "Third line"

    def test_parse_empty_string(self):
        result = self.fetcher.parse_lrc("")
        assert result == []

    def test_parse_no_valid_lines(self):
        lrc_text = "This is not LRC format\nNeither is this"
        result = self.fetcher.parse_lrc(lrc_text)
        assert result == []

    def test_parse_mixed_valid_invalid(self):
        lrc_text = "[00:10.00] Valid line\nInvalid line\n[00:20.00] Another valid"
        result = self.fetcher.parse_lrc(lrc_text)
        assert len(result) == 2
        assert result[0].text == "Valid line"
        assert result[1].text == "Another valid"

    def test_parse_zero_timestamp(self):
        lrc_text = "[00:00.00] Start"
        result = self.fetcher.parse_lrc(lrc_text)
        assert result[0].timestamp_ms == 0

    def test_parse_large_timestamp(self):
        lrc_text = "[99:59.99] End"
        result = self.fetcher.parse_lrc(lrc_text)
        assert result[0].timestamp_ms == (99 * 60 + 59) * 1000 + 99 * 10

    def test_parse_strips_whitespace_from_text(self):
        lrc_text = "[00:01.00]   spaced text   "
        result = self.fetcher.parse_lrc(lrc_text)
        assert result[0].text == "spaced text"

    def test_parse_empty_text_after_timestamp(self):
        lrc_text = "[00:05.00] "
        result = self.fetcher.parse_lrc(lrc_text)
        assert len(result) == 1
        assert result[0].text == ""


class TestFormatLrc:
    """Unit tests for format_lrc() method."""

    def setup_method(self):
        self.fetcher = LyricFetcher()

    def test_format_single_line(self):
        lyrics = [LyricLine(timestamp_ms=83450, text="Hello world")]
        result = self.fetcher.format_lrc(lyrics)
        assert result == "[01:23.45] Hello world"

    def test_format_multiple_lines(self):
        lyrics = [
            LyricLine(timestamp_ms=0, text="First"),
            LyricLine(timestamp_ms=5500, text="Second"),
            LyricLine(timestamp_ms=60000, text="Third"),
        ]
        result = self.fetcher.format_lrc(lyrics)
        expected = "[00:00.00] First\n[00:05.50] Second\n[01:00.00] Third"
        assert result == expected

    def test_format_empty_list(self):
        result = self.fetcher.format_lrc([])
        assert result == ""

    def test_format_zero_timestamp(self):
        lyrics = [LyricLine(timestamp_ms=0, text="Start")]
        result = self.fetcher.format_lrc(lyrics)
        assert result == "[00:00.00] Start"


class TestFetchLyrics:
    """Unit tests for fetch_lyrics() method."""

    def setup_method(self):
        self.fetcher = LyricFetcher()

    @pytest.mark.asyncio
    async def test_fetch_lyrics_success(self):
        mock_response_data = [
            {
                "syncedLyrics": "[00:00.00] Hello\n[00:05.00] World"
            }
        ]
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response_data)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await self.fetcher.fetch_lyrics("Test Song", "Test Artist")

        assert result is not None
        assert len(result) == 2
        assert result[0].text == "Hello"
        assert result[1].text == "World"

    @pytest.mark.asyncio
    async def test_fetch_lyrics_not_found(self):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=[])
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await self.fetcher.fetch_lyrics("Unknown", "Unknown")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_lyrics_api_error(self):
        mock_resp = AsyncMock()
        mock_resp.status = 500
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await self.fetcher.fetch_lyrics("Song", "Artist")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_lyrics_no_synced_lyrics(self):
        mock_response_data = [
            {
                "plainLyrics": "Hello\nWorld",
                "syncedLyrics": None
            }
        ]
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response_data)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await self.fetcher.fetch_lyrics("Song", "Artist")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_lyrics_timeout(self):
        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=asyncio.TimeoutError())
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await self.fetcher.fetch_lyrics("Song", "Artist")

        assert result is None


# ============================================================================
# Property-Based Tests (Hypothesis)
# ============================================================================


# Strategy for generating valid LyricLine objects
lyric_line_strategy = st.builds(
    LyricLine,
    timestamp_ms=st.integers(min_value=0, max_value=5999990),  # Up to 99:59.99
    text=st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),  # Exclude surrogates
            blacklist_characters="\n\r\x00[]",
        ),
        min_size=0,
        max_size=100,
    ).map(str.strip),
)

# Strategy for generating lists of LyricLine objects
lyric_list_strategy = st.lists(lyric_line_strategy, min_size=0, max_size=50)


# Strategy for generating valid LRC text with non-decreasing timestamps
def lrc_text_strategy():
    """Generate valid LRC text with non-decreasing timestamps."""
    return st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=99),   # minutes
            st.integers(min_value=0, max_value=59),   # seconds
            st.integers(min_value=0, max_value=99),   # centiseconds
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs",),
                    blacklist_characters="\n\r\x00[]",
                ),
                min_size=0,
                max_size=50,
            ).map(str.strip),
        ),
        min_size=1,
        max_size=30,
    ).map(_build_sorted_lrc)


def _build_sorted_lrc(entries):
    """Build LRC text from entries, sorting by timestamp to ensure non-decreasing order."""
    # Sort entries by timestamp to guarantee non-decreasing order
    sorted_entries = sorted(entries, key=lambda e: (e[0] * 60 + e[1]) * 1000 + e[2] * 10)
    lines = []
    for minutes, seconds, centiseconds, text in sorted_entries:
        lines.append(f"[{minutes:02d}:{seconds:02d}.{centiseconds:02d}] {text}")
    return "\n".join(lines)


class TestLrcRoundTrip:
    """Property test P2: parse(format(lyrics)) == lyrics.

    **Validates: Requirements 4.2**
    """

    def setup_method(self):
        self.fetcher = LyricFetcher()

    @given(lyrics=lyric_list_strategy)
    @settings(max_examples=200)
    def test_round_trip_parse_format(self, lyrics):
        """P2: For any valid list of LyricLine objects,
        format_lrc(lyrics) -> parse_lrc(text) produces an equivalent list.

        **Validates: Requirements 4.2**
        """
        # Ensure timestamps are within representable range for format
        # (centiseconds precision means we lose sub-10ms precision)
        normalized = [
            LyricLine(
                timestamp_ms=(lyric.timestamp_ms // 10) * 10,
                text=lyric.text,
            )
            for lyric in lyrics
        ]

        formatted = self.fetcher.format_lrc(normalized)
        parsed = self.fetcher.parse_lrc(formatted)

        assert len(parsed) == len(normalized)
        for original, roundtripped in zip(normalized, parsed):
            assert original.timestamp_ms == roundtripped.timestamp_ms
            assert original.text == roundtripped.text


class TestLrcTimestampOrdering:
    """Property test P3: parsed output has non-decreasing timestamps.

    **Validates: Requirements 4.2**
    """

    def setup_method(self):
        self.fetcher = LyricFetcher()

    @given(lrc_text=lrc_text_strategy())
    @settings(max_examples=200)
    def test_parsed_timestamps_non_decreasing(self, lrc_text):
        """P3: For any valid LRC text, the parsed output has timestamps
        in non-decreasing order.

        **Validates: Requirements 4.2**
        """
        parsed = self.fetcher.parse_lrc(lrc_text)

        # Verify timestamps are non-decreasing
        for i in range(1, len(parsed)):
            assert parsed[i].timestamp_ms >= parsed[i - 1].timestamp_ms, (
                f"Timestamp at index {i} ({parsed[i].timestamp_ms}) is less than "
                f"timestamp at index {i-1} ({parsed[i-1].timestamp_ms})"
            )
