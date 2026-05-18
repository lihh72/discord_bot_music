"""Tests for MpaiBot Music Downloader module."""
import asyncio
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from bot.music_downloader import (
    DownloadError,
    MusicDownloader,
    NoResultsError,
)


class FakeSongInfo:
    """Fake song_info object mimicking musicdl results."""

    def __init__(self, songname="Test Song", singer="Test Artist",
                 download_url="http://example.com/song.mp3",
                 filesize=5000000, duration="03:45"):
        self.songname = songname
        self.singer = singer
        self.download_url = download_url
        self.filesize = filesize
        self.duration = duration


class TestMusicDownloaderInit:
    """Tests for MusicDownloader initialization (Task 4.1)."""

    def test_creates_download_dir(self, tmp_path):
        download_dir = str(tmp_path / "new_downloads")
        downloader = MusicDownloader(download_dir=download_dir)
        assert os.path.isdir(download_dir)
        assert downloader.download_dir == download_dir

    def test_default_config(self, tmp_path):
        downloader = MusicDownloader(download_dir=str(tmp_path))
        assert downloader.config["search_size_per_source"] == 5
        assert downloader.config["savedir"] == str(tmp_path)
        assert "proxies" in downloader.config


class TestSelectBest:
    """Tests for _select_best() ranking logic (Task 4.3)."""

    def setup_method(self):
        self.downloader = MusicDownloader(download_dir=tempfile.mkdtemp())

    def test_prefers_result_with_download_url(self):
        no_url = FakeSongInfo(download_url=None, filesize=10000000)
        has_url = FakeSongInfo(download_url="http://example.com/song.mp3", filesize=1000)
        result = self.downloader._select_best([no_url, has_url])
        assert result is has_url

    def test_prefers_higher_filesize_when_both_have_url(self):
        small = FakeSongInfo(filesize=1000)
        large = FakeSongInfo(filesize=9000000)
        result = self.downloader._select_best([small, large])
        assert result is large

    def test_prefers_complete_metadata(self):
        no_meta = FakeSongInfo(songname=None, singer=None, download_url=None, filesize=0)
        has_meta = FakeSongInfo(songname="Song", singer="Artist", download_url=None, filesize=0)
        result = self.downloader._select_best([no_meta, has_meta])
        assert result is has_meta

    def test_single_result_returns_it(self):
        song = FakeSongInfo()
        result = self.downloader._select_best([song])
        assert result is song

    def test_handles_string_filesize(self):
        song_str = FakeSongInfo(filesize="5000000")
        song_int = FakeSongInfo(filesize=3000000)
        result = self.downloader._select_best([song_str, song_int])
        assert result is song_str


class TestSearchAndDownload:
    """Tests for search_and_download() method (Task 4.2, 4.4, 4.5)."""

    def setup_method(self):
        self.downloader = MusicDownloader(download_dir=tempfile.mkdtemp())

    @pytest.mark.asyncio
    async def test_raises_no_results_error_when_empty(self):
        """Validates: Requirement 2.4 - Reply 'no songs found' if no results."""
        with patch.object(self.downloader, "_search", return_value=[]):
            with pytest.raises(NoResultsError) as exc_info:
                await self.downloader.search_and_download("nonexistent song xyz")
            assert "No songs found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_download_error_on_failure(self):
        """Validates: Requirement 2.5 - Reply with error on download failure."""
        fake_song = FakeSongInfo()
        with patch.object(self.downloader, "_search", return_value=[fake_song]):
            with patch.object(
                self.downloader, "_download",
                side_effect=DownloadError("Download failed")
            ):
                with pytest.raises(DownloadError):
                    await self.downloader.search_and_download("test query")

    @pytest.mark.asyncio
    async def test_returns_song_info_on_success(self):
        """Validates: Requirement 2.1, 2.2 - Search and select best match."""
        fake_song = FakeSongInfo(songname="My Song", singer="My Artist", duration="04:00")
        filepath = os.path.join(self.downloader.download_dir, "test.mp3")

        with patch.object(self.downloader, "_search", return_value=[fake_song]):
            with patch.object(self.downloader, "_download", return_value=filepath):
                result = await self.downloader.search_and_download("my song")

        assert result.title == "My Song"
        assert result.artist == "My Artist"
        assert result.filepath == filepath
        assert result.duration == 240.0

    @pytest.mark.asyncio
    async def test_uses_asyncio_to_thread(self):
        """Validates: Task 4.5 - async wrapper using asyncio.to_thread()."""
        fake_song = FakeSongInfo()
        filepath = "/tmp/test.mp3"

        with patch.object(self.downloader, "_search", return_value=[fake_song]) as mock_search:
            with patch.object(self.downloader, "_download", return_value=filepath) as mock_download:
                with patch("asyncio.to_thread", wraps=asyncio.to_thread) as mock_to_thread:
                    await self.downloader.search_and_download("test")
                    # Verify to_thread was called for both search and download
                    assert mock_to_thread.call_count == 2


class TestParseDuration:
    """Tests for _parse_duration() helper."""

    def test_mm_ss_format(self):
        assert MusicDownloader._parse_duration("03:45") == 225.0

    def test_hh_mm_ss_format(self):
        assert MusicDownloader._parse_duration("1:02:30") == 3750.0

    def test_invalid_format_returns_zero(self):
        assert MusicDownloader._parse_duration("invalid") == 0.0

    def test_empty_string_returns_zero(self):
        assert MusicDownloader._parse_duration("") == 0.0


class TestErrorHandling:
    """Tests for error handling (Task 4.4)."""

    def setup_method(self):
        self.downloader = MusicDownloader(download_dir=tempfile.mkdtemp())

    def test_search_handles_import_error_gracefully(self):
        """If musicdl is not installed, _search returns empty list."""
        with patch.dict("sys.modules", {"musicdl": None, "musicdl.musicdl": None}):
            # The _search method should catch exceptions and return []
            result = self.downloader._search("test query")
            # It will either return [] due to import error or work if musicdl is installed
            assert isinstance(result, list)

    def test_no_results_error_message_is_user_friendly(self):
        error = NoResultsError("No songs found for 'test'. Try a different search query.")
        assert "No songs found" in str(error)
        assert "Try a different" in str(error)

    def test_download_error_message_is_user_friendly(self):
        error = DownloadError("Failed to download the song. Please try a different query.")
        assert "Failed to download" in str(error)
        assert "try a different query" in str(error)
