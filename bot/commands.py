"""MpaiBot Command Handler - Command registry and message routing."""
import logging

from bot.config import Config
from bot.audio_streamer import AudioStreamer
from bot.music_downloader import MusicDownloader, NoResultsError, DownloadError
from bot.lyric_fetcher import LyricFetcher
from bot.screen_share import ScreenShareStreamer
from bot.video_generator import VideoGenerator
from bot.queue_manager import QueueManager

logger = logging.getLogger("mpaibot")

# Module-level bot reference, set during initialization
_bot = None

# Module-level instances for shared components
_downloader = MusicDownloader()
_lyric_fetcher = LyricFetcher()

# Per-guild screen share streamers
_screen_streamers: dict = {}


def set_bot(bot):
    """Set the bot reference for use in command handlers."""
    global _bot
    _bot = bot


# --- Helper: auto-play next song callback ---

def _make_after_callback(guild_id, text_channel):
    """Create an after-playback callback that auto-plays the next song from queue.

    Validates: Requirement 3.6 - Auto-play next song when current finishes.
    """

    async def _after_callback(error):
        if error:
            logger.error("Playback error in guild %s: %s", guild_id, error)
            await text_channel.send(f"⚠️ Playback error: {error}")
            return

        # Stop any existing screen share
        if guild_id in _screen_streamers:
            await _screen_streamers[guild_id].stop_stream()
            del _screen_streamers[guild_id]

        queue = QueueManager.get_queue(guild_id)
        next_song = queue.next()

        if next_song is None:
            # Queue empty - idle timer will be reset by AudioStreamer internally
            logger.info("Queue empty for guild %s, waiting for new songs.", guild_id)
            return

        # Auto-play next song
        streamer = AudioStreamer.get_streamer(_bot, guild_id)

        try:
            await text_channel.send(f"🎵 Now playing: **{next_song.title}** - {next_song.artist}")

            # Play the next song with a new after callback
            after_cb = _make_after_callback(guild_id, text_channel)
            await streamer.play(next_song, after_callback=after_cb)

            # Fetch lyrics for the next song
            lyrics = await _lyric_fetcher.fetch_lyrics(next_song.title, next_song.artist)

            # Start screen share with lyrics
            if streamer.voice_client:
                video_gen = VideoGenerator()
                screen_streamer = ScreenShareStreamer(streamer.voice_client, video_gen)
                _screen_streamers[guild_id] = screen_streamer
                await screen_streamer.start_stream(
                    lyrics or [],
                    next_song,
                    streamer.get_elapsed_time,
                )

        except Exception as e:
            logger.error("Error auto-playing next song in guild %s: %s", guild_id, e)
            await text_channel.send(f"⚠️ Error playing next song: {e}")

    return _after_callback


# --- Command handlers ---

async def handle_play(message, args):
    """Handle the play command - full flow: join → search → download → stream → lyrics → screen share.

    Validates: Requirement 1.1 - Bot joins Commander's voice channel on mpai!play.
    Validates: Requirement 1.2 - Error if Commander not in voice channel.
    Validates: Requirement 2.1 - Search across available platforms.
    Validates: Requirement 6.1 - Add to queue if already playing.
    """
    guild = message.guild
    if guild is None:
        await message.channel.send("This command can only be used in a server.")
        return

    # Check if Commander is in a voice channel
    if not message.author.voice or not message.author.voice.channel:
        await message.channel.send(
            "❌ You must be in a voice channel to use this command. "
            "Please join a voice channel first."
        )
        return

    if not args:
        await message.channel.send("Please provide a song name or URL. Usage: `mpai!play <query>`")
        return

    voice_channel = message.author.voice.channel
    streamer = AudioStreamer.get_streamer(_bot, guild.id)

    # Connect to the Commander's voice channel if not already connected
    if not streamer.is_connected:
        try:
            await streamer.connect(voice_channel)
        except Exception as e:
            logger.error("Failed to connect to voice channel: %s", e)
            await message.channel.send(f"❌ Failed to join voice channel: {e}")
            return

    query = " ".join(args)

    # If already playing, add to queue
    if streamer.voice_client and (
        streamer.voice_client.is_playing() or streamer.voice_client.is_paused()
    ):
        # Search and download first, then add to queue
        await message.channel.send(f"🔍 Searching for: **{query}**...")
        try:
            song_info = await _downloader.search_and_download(query)
        except NoResultsError as e:
            await message.channel.send(f"❌ {e}")
            return
        except DownloadError as e:
            await message.channel.send(f"❌ {e}")
            return

        queue = QueueManager.get_queue(guild.id)
        if queue.add(song_info):
            await message.channel.send(
                f"📋 Added to queue (position {queue.size}): **{song_info.title}** - {song_info.artist}"
            )
        else:
            await message.channel.send("❌ Queue is full (max 50 songs).")
        return

    # --- Full play flow ---

    # Step 1: Send searching status
    await message.channel.send(f"🔍 Searching for: **{query}**...")

    # Step 2: Search and download
    try:
        await message.channel.send("⬇️ Downloading...")
        song_info = await _downloader.search_and_download(query)
    except NoResultsError as e:
        await message.channel.send(f"❌ {e}")
        return
    except DownloadError as e:
        await message.channel.send(f"❌ {e}")
        return

    # Step 3: Play audio
    try:
        after_cb = _make_after_callback(guild.id, message.channel)
        await streamer.play(song_info, after_callback=after_cb)
        await message.channel.send(f"🎵 Now playing: **{song_info.title}** - {song_info.artist}")
    except Exception as e:
        logger.error("Failed to play audio: %s", e)
        await message.channel.send(f"❌ Failed to play: {e}")
        return

    # Step 4: Fetch lyrics (non-blocking - don't fail the whole flow)
    lyrics = None
    try:
        lyrics = await _lyric_fetcher.fetch_lyrics(song_info.title, song_info.artist)
    except Exception as e:
        logger.warning("Failed to fetch lyrics: %s", e)

    # Step 5: Start screen share with lyrics
    try:
        if streamer.voice_client:
            video_gen = VideoGenerator()
            screen_streamer = ScreenShareStreamer(streamer.voice_client, video_gen)
            _screen_streamers[guild.id] = screen_streamer
            await screen_streamer.start_stream(
                lyrics or [],
                song_info,
                streamer.get_elapsed_time,
            )
    except Exception as e:
        logger.warning("Failed to start screen share: %s", e)


async def handle_pause(message, args):
    """Handle the pause command.

    Validates: Requirement 3.3 - pause command.
    """
    guild = message.guild
    if guild is None:
        await message.channel.send("This command can only be used in a server.")
        return

    streamer = AudioStreamer.get_streamer(_bot, guild.id)
    if streamer.pause():
        await message.channel.send("⏸️ Paused playback.")
    else:
        await message.channel.send("Nothing is currently playing.")


async def handle_resume(message, args):
    """Handle the resume command.

    Validates: Requirement 3.4 - resume command.
    """
    guild = message.guild
    if guild is None:
        await message.channel.send("This command can only be used in a server.")
        return

    streamer = AudioStreamer.get_streamer(_bot, guild.id)
    if streamer.resume():
        await message.channel.send("▶️ Resumed playback.")
    else:
        await message.channel.send("Nothing is currently paused.")


async def handle_skip(message, args):
    """Handle the skip command with queue integration.

    Validates: Requirement 3.5 - skip command (stop current, play next).
    When skip is called, stopping the voice client triggers the after_callback
    which handles auto-playing the next song from the queue.
    """
    guild = message.guild
    if guild is None:
        await message.channel.send("This command can only be used in a server.")
        return

    streamer = AudioStreamer.get_streamer(_bot, guild.id)
    if streamer.skip():
        await message.channel.send("⏭️ Skipped current song.")
    else:
        await message.channel.send("Nothing is currently playing to skip.")


async def handle_leave(message, args):
    """Handle the leave command - disconnect from voice channel.

    Validates: Requirement 1.4 - mpai!leave disconnects immediately.
    """
    guild = message.guild
    if guild is None:
        await message.channel.send("This command can only be used in a server.")
        return

    streamer = AudioStreamer.get_streamer(_bot, guild.id)
    if not streamer.is_connected:
        await message.channel.send("I'm not connected to any voice channel.")
        return

    # Stop screen share if active
    if guild.id in _screen_streamers:
        await _screen_streamers[guild.id].stop_stream()
        del _screen_streamers[guild.id]

    await streamer.disconnect()
    await message.channel.send("Disconnected from voice channel. 👋")


async def handle_queue(message, args):
    """Handle the queue command - display current queue contents.

    Validates: Requirement 6.2 - mpai!queue displays current queue with titles and positions.
    """
    guild = message.guild
    if guild is None:
        await message.channel.send("This command can only be used in a server.")
        return

    queue = QueueManager.get_queue(guild.id)
    songs = queue.get_list()

    if not songs:
        await message.channel.send("Queue is empty.")
        return

    lines = ["**🎵 Current Queue:**"]
    for i, song in enumerate(songs, start=1):
        lines.append(f"{i}. {song.title} - {song.artist}")

    await message.channel.send("\n".join(lines))


async def handle_clear(message, args):
    """Handle the clear command - clear the song queue.

    Validates: Requirement 6.3 - mpai!clear removes all songs from queue.
    """
    guild = message.guild
    if guild is None:
        await message.channel.send("This command can only be used in a server.")
        return

    queue = QueueManager.get_queue(guild.id)
    queue.clear()
    await message.channel.send("🗑️ Queue cleared.")


async def handle_nowplaying(message, args):
    """Handle the nowplaying command - show current song info and elapsed time.

    Validates: Requirement 7.4 - Display currently playing song title, artist, and elapsed time.
    """
    guild = message.guild
    if guild is None:
        await message.channel.send("This command can only be used in a server.")
        return

    streamer = AudioStreamer.get_streamer(_bot, guild.id)

    if streamer.current_song is None:
        await message.channel.send("Nothing is currently playing.")
        return

    song = streamer.current_song
    elapsed = streamer.get_elapsed_time()
    minutes = int(elapsed) // 60
    seconds = int(elapsed) % 60

    await message.channel.send(
        f"🎵 Now playing: **{song.title}** - {song.artist}\n"
        f"⏱️ Elapsed: {minutes:02d}:{seconds:02d}"
    )


async def handle_unknown(message, args):
    """Handle unknown commands by replying with a help message listing all available commands."""
    command_list = ", ".join(f"`{Config.COMMAND_PREFIX}{cmd}`" for cmd in COMMANDS.keys())
    help_text = (
        f"Unknown command. Available commands:\n{command_list}"
    )
    await message.channel.send(help_text)


# --- Command registry ---

COMMANDS = {
    "play": handle_play,
    "pause": handle_pause,
    "resume": handle_resume,
    "skip": handle_skip,
    "leave": handle_leave,
    "queue": handle_queue,
    "clear": handle_clear,
    "nowplaying": handle_nowplaying,
}


def parse_command(content: str):
    """Parse a message string and return (command_name, args) if it has the prefix.

    Returns None if the message does not start with the command prefix.
    """
    prefix = Config.COMMAND_PREFIX
    if not content.startswith(prefix):
        return None

    without_prefix = content[len(prefix):]
    parts = without_prefix.split()
    if not parts:
        return ("", [])

    command_name = parts[0].lower()
    args = parts[1:]
    return (command_name, args)


def get_handler(command_name: str):
    """Get the handler function for a command name.

    Returns handle_unknown if the command is not recognized.
    """
    return COMMANDS.get(command_name, handle_unknown)


async def on_message(message):
    """Process incoming messages and route commands.

    Ignores messages from bots and messages without the command prefix.
    """
    # Ignore messages from bots
    if message.author.bot:
        return

    parsed = parse_command(message.content)
    if parsed is None:
        return

    command_name, args = parsed
    handler = get_handler(command_name)
    logger.info("Command '%s' from %s with args: %s", command_name, message.author, args)
    await handler(message, args)
