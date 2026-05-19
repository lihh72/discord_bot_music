"""MpaiBot Music Downloader - Uses spotDL for search and download with cache."""
import asyncio
import logging
import os
import re
import glob
from typing import Optional

from bot.audio_streamer import SongInfo
from bot.config import Config

logger = logging.getLogger("mpaibot")


class DownloadError(Exception):
    """Raised when a music download fails."""
    pass


class NoResultsError(Exception):
    """Raised when no search results are found."""
    pass


class MusicDownloader:
    """Downloads music using spotDL with local file cache.

    - If file already exists in downloads folder, uses it directly (instant).
    - Otherwise downloads via spotDL (Spotify metadata + YouTube audio).
    """

    def __init__(self, download_dir: Optional[str] = None):
        self.download_dir = download_dir or Config.DOWNLOAD_DIR
        os.makedirs(self.download_dir, exist_ok=True)

    async def search_and_download(self, query: str) -> SongInfo:
        """Search and download a song. Uses cache if file already exists."""
        return await asyncio.to_thread(self._download_sync, query)

    def _download_sync(self, query: str) -> SongInfo:
        """Synchronous spotDL download with cache handling."""
        import subprocess

        # Build spotdl command — use --overwrite skip to leverage cache
        cmd = [
            'spotdl', 'download', query,
            '--output', self.download_dir,
            '--format', 'mp3',
            '--bitrate', '192k',
            '--overwrite', 'skip',
            '--audio-providers', 'piped,soundcloud,youtube-music',
            '--print-errors',
        ]

        # Add cookies if available
        cookies_file = getattr(Config, 'YTDLP_COOKIES_FILE', '')
        if cookies_file and os.path.isfile(cookies_file):
            cmd.extend(['--cookie-file', cookies_file])
            logger.info("🍪 Cookies loaded: %s", cookies_file)

        # Add proxy if configured (for VPS/datacenter IPs blocked by YouTube)
        proxy = getattr(Config, 'SPOTDL_PROXY', '')
        if proxy:
            cmd.extend(['--proxy', proxy])
            logger.info("🌐 Proxy configured: %s", proxy.split('@')[-1] if '@' in proxy else proxy)

        logger.info("Running: %s", ' '.join(cmd))

        # Track files before download
        existing_files = set(self._list_audio_files())

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.download_dir,
            )

            output_lines = []
            skipped_file = None

            for line in process.stdout:
                line = line.rstrip()
                if not line:
                    continue
                output_lines.append(line)
                logger.info("spotdl: %s", line)

                # Detect "Skipping X - Y (file already exists)" pattern
                # This means the file is cached — extract the filename
                skip_match = re.search(
                    r'Skipping\s+(.+?)\s+\(file already exists\)', line
                )
                if skip_match:
                    skipped_name = skip_match.group(1).strip()
                    skipped_file = self._find_cached_file(skipped_name)

            process.wait(timeout=60)
            returncode = process.returncode
            full_output = '\n'.join(output_lines)

        except subprocess.TimeoutExpired:
            process.kill()
            raise DownloadError("Download timed out (60s). Try again.")
        except FileNotFoundError:
            raise DownloadError("spotdl not found. Run: pip install spotdl")

        # Determine the filepath
        filepath = None

        # Case 1: File was skipped (already cached) — use cached file
        if skipped_file and os.path.isfile(skipped_file):
            filepath = skipped_file
            logger.info("📦 Using cached file: %s", filepath)

        # Case 2: New file was downloaded
        if not filepath:
            current_files = set(self._list_audio_files())
            new_files = current_files - existing_files
            if new_files:
                filepath = list(new_files)[0]
                logger.info("⬇️ New download: %s", filepath)

        # Case 3: Neither — check errors
        if not filepath:
            if 'No results found' in full_output:
                raise NoResultsError(f"No songs found for '{query}'.")
            if returncode != 0:
                raise DownloadError(f"spotdl error: {full_output[-200:]}")
            raise DownloadError("No audio file found after download.")

        # Extract metadata from filename (spotdl: "Artist - Title.mp3")
        filename = os.path.basename(filepath)
        name_without_ext = os.path.splitext(filename)[0]

        if ' - ' in name_without_ext:
            artist, title = name_without_ext.split(' - ', 1)
        else:
            title = name_without_ext
            artist = 'Unknown'

        duration = self._get_duration(filepath)

        logger.info("✅ Ready: '%s' by '%s' [%.0fs] -> %s", title, artist, duration, filepath)
        return SongInfo(title=title, artist=artist, filepath=filepath, duration=duration)

    def _find_cached_file(self, name: str) -> Optional[str]:
        """Find a cached audio file matching the given name."""
        # spotDL names files as "Artist - Title.mp3"
        for ext in ('.mp3', '.m4a', '.flac', '.opus', '.ogg'):
            candidate = os.path.join(self.download_dir, f"{name}{ext}")
            if os.path.isfile(candidate):
                return candidate
        # Fuzzy match: search for files containing the name
        for f in os.listdir(self.download_dir):
            if name.lower() in f.lower() and self._is_audio(f):
                return os.path.join(self.download_dir, f)
        return None

    def _list_audio_files(self) -> list:
        """List all audio files in download directory."""
        if not os.path.isdir(self.download_dir):
            return []
        return [
            os.path.join(self.download_dir, f)
            for f in os.listdir(self.download_dir)
            if self._is_audio(f)
        ]

    def _is_audio(self, filename: str) -> bool:
        """Check if filename has an audio extension."""
        return filename.lower().endswith(('.mp3', '.m4a', '.flac', '.opus', '.ogg', '.wav'))

    def _get_duration(self, filepath: str) -> float:
        """Get audio duration in seconds using mutagen."""
        try:
            from mutagen import File as MutagenFile
            audio = MutagenFile(filepath)
            if audio and audio.info:
                return float(audio.info.length)
        except Exception:
            pass
        return 0.0
