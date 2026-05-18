"""MpaiBot Music Downloader - Hybrid: yt-dlp for URLs, musicdl for text search."""
import asyncio
import logging
import os
from typing import List, Optional

from bot.audio_streamer import SongInfo
from bot.config import Config

logger = logging.getLogger("mpaibot")


class DownloadError(Exception):
    """Raised when a music download fails."""
    pass


class NoResultsError(Exception):
    """Raised when no search results are found."""
    pass


def _is_url(query: str) -> bool:
    """Check if query is a URL."""
    return query.startswith("http://") or query.startswith("https://")


class MusicDownloader:
    """Hybrid music downloader.

    - YouTube/URL: uses yt-dlp (fast, 5-10 seconds)
    - Text search: uses yt-dlp ytsearch (fast) with musicdl as fallback
    """

    def __init__(self, download_dir: Optional[str] = None):
        self.download_dir = download_dir or Config.DOWNLOAD_DIR
        os.makedirs(self.download_dir, exist_ok=True)

    async def search_and_download(self, query: str) -> SongInfo:
        """Search and download music.

        For URLs: downloads directly via yt-dlp (fast).
        For text: searches YouTube via yt-dlp ytsearch, falls back to musicdl.
        """
        if _is_url(query):
            return await self._download_with_ytdlp(query)
        else:
            # Try yt-dlp YouTube search first (fast)
            try:
                return await self._download_with_ytdlp(f"ytsearch:{query}")
            except (NoResultsError, DownloadError) as e:
                logger.warning("yt-dlp search failed, trying musicdl: %s", e)
            # Fallback to musicdl (slower but more sources)
            return await self._download_with_musicdl(query)

    # --- yt-dlp (fast path for URLs and YouTube search) ---

    async def _download_with_ytdlp(self, query: str) -> SongInfo:
        """Download via yt-dlp. Supports URLs and ytsearch: prefix."""
        import yt_dlp
        from bot.config import Config

        # Resolve cookies file: env var first, fallback to cookies.txt in project root
        cookies_file = Config.YTDLP_COOKIES_FILE
        if not cookies_file:
            cookies_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cookies.txt')

        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
            'outtmpl': os.path.join(self.download_dir, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
        }

        # Add cookies if file exists and log confirmation
        if cookies_file and os.path.isfile(cookies_file):
            ydl_opts['cookiefile'] = cookies_file
            logger.info("🍪 Cookies loaded: %s", cookies_file)
        else:
            logger.info("ℹ️ No cookies file found (proceeding without cookies)")

        def _do_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=True)
                if info is None:
                    raise NoResultsError(f"No results for '{query}'.")
                if 'entries' in info:
                    entries = info['entries']
                    if not entries:
                        raise NoResultsError(f"No results for '{query}'.")
                    info = entries[0]
                return info

        try:
            info = await asyncio.to_thread(_do_download)
        except NoResultsError:
            raise
        except Exception as e:
            logger.error("yt-dlp failed for '%s': %s", query, e)
            raise DownloadError(f"Download failed: {e}")

        title = info.get('title', 'Unknown')
        artist = info.get('artist') or info.get('uploader') or 'Unknown'
        duration = float(info.get('duration', 0) or 0)

        # Find downloaded file
        filepath = self._find_latest_audio()
        if not filepath:
            raise DownloadError("Download completed but file not found.")

        logger.info("yt-dlp OK: '%s' by '%s' -> %s", title, artist, filepath)
        return SongInfo(title=title, artist=artist, filepath=filepath, duration=duration)

    # --- musicdl (fallback for broader search) ---

    async def _download_with_musicdl(self, query: str) -> SongInfo:
        """Search and download via musicdl library."""
        return await asyncio.to_thread(self._musicdl_sync, query)

    def _musicdl_sync(self, query: str) -> SongInfo:
        """Synchronous musicdl search+download (runs in thread)."""
        from musicdl import musicdl

        music_sources = ['NeteaseMusicClient', 'KuwoMusicClient', 'MiguMusicClient']
        init_cfg = {src: {'work_dir': self.download_dir, 'search_size_per_source': 2} for src in music_sources}

        try:
            client = musicdl.MusicClient(
                music_sources=music_sources,
                init_music_clients_cfg=init_cfg,
            )
            search_results = client.search(keyword=query)

            # Flatten results
            all_songs = []
            if isinstance(search_results, dict):
                for songs in search_results.values():
                    if songs:
                        all_songs.extend(songs)

            if not all_songs:
                raise NoResultsError(f"No songs found for '{query}'.")

            best = all_songs[0]
            client.download(song_infos=[best])

            filepath = self._find_latest_audio()
            if not filepath:
                raise DownloadError("musicdl download completed but file not found.")

            title = getattr(best, 'song_name', None) or getattr(best, 'songname', 'Unknown')
            artist = getattr(best, 'singers', None) or getattr(best, 'singer', 'Unknown')
            duration_s = getattr(best, 'duration_s', 0) or 0

            return SongInfo(title=str(title), artist=str(artist), filepath=filepath, duration=float(duration_s))

        except (NoResultsError, DownloadError):
            raise
        except Exception as e:
            logger.error("musicdl failed for '%s': %s", query, e)
            raise DownloadError(f"musicdl failed: {e}")

    # --- Helpers ---

    def _find_latest_audio(self) -> Optional[str]:
        """Find most recently modified audio file in download dir."""
        if not os.path.isdir(self.download_dir):
            return None
        exts = ('.mp3', '.m4a', '.flac', '.opus', '.ogg', '.wav', '.aac')
        files = [
            os.path.join(self.download_dir, f)
            for f in os.listdir(self.download_dir)
            if os.path.isfile(os.path.join(self.download_dir, f)) and f.lower().endswith(exts)
        ]
        return max(files, key=os.path.getmtime) if files else None
