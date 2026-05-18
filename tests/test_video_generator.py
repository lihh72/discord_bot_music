"""Tests for VideoGenerator: unit tests and property-based tests for lyric sync."""
import io

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from PIL import Image

from bot.audio_streamer import SongInfo
from bot.lyric_fetcher import LyricLine
from bot.video_generator import VideoGenerator, find_current_line


# ============================================================================
# Unit Tests
# ============================================================================


class TestFindCurrentLine:
    """Unit tests for find_current_line() binary search."""

    def test_empty_lyrics_returns_negative_one(self):
        assert find_current_line([], 5000) == -1

    def test_before_first_lyric(self):
        lyrics = [LyricLine(timestamp_ms=1000, text="First")]
        assert find_current_line(lyrics, 500) == -1

    def test_exact_match_first_lyric(self):
        lyrics = [LyricLine(timestamp_ms=1000, text="First")]
        assert find_current_line(lyrics, 1000) == 0

    def test_between_two_lyrics(self):
        lyrics = [
            LyricLine(timestamp_ms=1000, text="First"),
            LyricLine(timestamp_ms=5000, text="Second"),
        ]
        assert find_current_line(lyrics, 3000) == 0

    def test_exact_match_second_lyric(self):
        lyrics = [
            LyricLine(timestamp_ms=1000, text="First"),
            LyricLine(timestamp_ms=5000, text="Second"),
        ]
        assert find_current_line(lyrics, 5000) == 1

    def test_after_last_lyric(self):
        lyrics = [
            LyricLine(timestamp_ms=1000, text="First"),
            LyricLine(timestamp_ms=5000, text="Second"),
            LyricLine(timestamp_ms=10000, text="Third"),
        ]
        assert find_current_line(lyrics, 99999) == 2

    def test_multiple_lyrics_mid_song(self):
        lyrics = [
            LyricLine(timestamp_ms=0, text="Intro"),
            LyricLine(timestamp_ms=3000, text="Line 1"),
            LyricLine(timestamp_ms=6000, text="Line 2"),
            LyricLine(timestamp_ms=9000, text="Line 3"),
            LyricLine(timestamp_ms=12000, text="Line 4"),
        ]
        assert find_current_line(lyrics, 7500) == 2

    def test_timestamp_zero(self):
        lyrics = [
            LyricLine(timestamp_ms=0, text="Start"),
            LyricLine(timestamp_ms=5000, text="Next"),
        ]
        assert find_current_line(lyrics, 0) == 0

    def test_single_lyric_after_timestamp(self):
        lyrics = [LyricLine(timestamp_ms=0, text="Only line")]
        assert find_current_line(lyrics, 50000) == 0


class TestVideoGeneratorFrames:
    """Unit tests for VideoGenerator frame generation."""

    def setup_method(self):
        self.generator = VideoGenerator(width=1280, height=720)
        self.song_info = SongInfo(
            title="Test Song", artist="Test Artist", filepath="/tmp/test.mp3", duration=180.0
        )

    def test_generate_frame_returns_valid_png(self):
        frame = self.generator.generate_frame("Hello World", None, self.song_info)
        # Verify it's valid PNG by opening with Pillow
        img = Image.open(io.BytesIO(frame))
        assert img.format == "PNG"
        assert img.size == (1280, 720)

    def test_generate_frame_with_next_line(self):
        frame = self.generator.generate_frame("Current", "Next line", self.song_info)
        img = Image.open(io.BytesIO(frame))
        assert img.format == "PNG"
        assert img.size == (1280, 720)

    def test_generate_frame_empty_current_line(self):
        frame = self.generator.generate_frame("", None, self.song_info)
        img = Image.open(io.BytesIO(frame))
        assert img.format == "PNG"

    def test_generate_static_frame_returns_valid_png(self):
        frame = self.generator.generate_static_frame(self.song_info)
        img = Image.open(io.BytesIO(frame))
        assert img.format == "PNG"
        assert img.size == (1280, 720)

    def test_generate_static_frame_different_song(self):
        other_song = SongInfo(
            title="Another Song", artist="Another Artist", filepath="/tmp/other.mp3", duration=240.0
        )
        frame = self.generator.generate_static_frame(other_song)
        img = Image.open(io.BytesIO(frame))
        assert img.format == "PNG"

    def test_custom_dimensions(self):
        gen = VideoGenerator(width=640, height=480)
        frame = gen.generate_frame("Test", None, self.song_info)
        img = Image.open(io.BytesIO(frame))
        assert img.size == (640, 480)


# ============================================================================
# Property-Based Tests (Hypothesis)
# ============================================================================


# Strategy for generating sorted lists of LyricLine objects (non-decreasing timestamps)
sorted_lyric_list_strategy = st.lists(
    st.integers(min_value=0, max_value=600000),  # timestamps up to 10 minutes
    min_size=1,
    max_size=100,
).map(
    lambda timestamps: [
        LyricLine(timestamp_ms=ts, text=f"Line at {ts}ms")
        for ts in sorted(timestamps)
    ]
)

# Strategy for timestamps that could be anywhere in the song range
timestamp_strategy = st.integers(min_value=0, max_value=700000)


class TestLyricSyncProperty:
    """Property test P4: For any timestamp T, the selected lyric line has the
    largest timestamp_ms that is <= T.

    **Validates: Requirements 5.2**
    """

    @given(lyrics=sorted_lyric_list_strategy, elapsed_ms=timestamp_strategy)
    @settings(max_examples=500)
    def test_find_current_line_selects_largest_timestamp_leq_t(self, lyrics, elapsed_ms):
        """P4: For any given playback timestamp T and a list of LyricLines,
        the selected current lyric line SHALL be the one with the largest
        timestamp_ms that is less than or equal to T.

        **Validates: Requirements 5.2**
        """
        result_idx = find_current_line(lyrics, elapsed_ms)

        if result_idx == -1:
            # No lyric has started yet: all timestamps must be > elapsed_ms
            for line in lyrics:
                assert line.timestamp_ms > elapsed_ms, (
                    f"find_current_line returned -1 but lyric at {line.timestamp_ms}ms "
                    f"should have been selected for elapsed_ms={elapsed_ms}"
                )
        else:
            # The selected line's timestamp must be <= elapsed_ms
            assert lyrics[result_idx].timestamp_ms <= elapsed_ms, (
                f"Selected line at index {result_idx} has timestamp "
                f"{lyrics[result_idx].timestamp_ms}ms which is > elapsed_ms={elapsed_ms}"
            )

            # No later line should also have timestamp <= elapsed_ms
            # (i.e., result_idx is the LARGEST index with timestamp <= T)
            for i in range(result_idx + 1, len(lyrics)):
                assert lyrics[i].timestamp_ms > elapsed_ms, (
                    f"Line at index {i} has timestamp {lyrics[i].timestamp_ms}ms <= "
                    f"elapsed_ms={elapsed_ms}, but find_current_line returned index {result_idx}"
                )

    @given(lyrics=sorted_lyric_list_strategy)
    @settings(max_examples=200)
    def test_find_current_line_at_exact_timestamps(self, lyrics):
        """For any lyric line, querying at its exact timestamp should select
        that line (or a later one with the same timestamp).

        **Validates: Requirements 5.2**
        """
        for i, line in enumerate(lyrics):
            result_idx = find_current_line(lyrics, line.timestamp_ms)
            # Result must be >= i (could be later if duplicate timestamps)
            assert result_idx >= i or lyrics[result_idx].timestamp_ms == line.timestamp_ms, (
                f"At timestamp {line.timestamp_ms}ms, expected index >= {i} "
                f"but got {result_idx}"
            )
            # The result's timestamp must equal the query timestamp
            # (since we're querying at an exact lyric timestamp)
            assert lyrics[result_idx].timestamp_ms == line.timestamp_ms

    @given(lyrics=sorted_lyric_list_strategy, elapsed_ms=timestamp_strategy)
    @settings(max_examples=200)
    def test_find_current_line_result_is_valid_index_or_negative_one(self, lyrics, elapsed_ms):
        """The result must be either -1 or a valid index into the lyrics list.

        **Validates: Requirements 5.2**
        """
        result_idx = find_current_line(lyrics, elapsed_ms)
        assert result_idx >= -1
        assert result_idx < len(lyrics)
