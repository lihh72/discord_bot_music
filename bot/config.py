from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    COMMAND_PREFIX = "mpai!"
    DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "./downloads")
    LOG_FILE = os.getenv("LOG_FILE", "./mpaibot.log")
    IDLE_TIMEOUT = int(os.getenv("IDLE_TIMEOUT", "300"))  # 5 minutes
    FRAME_RATE = 20  # FPS for lyric video
    VIDEO_WIDTH = 1280
    VIDEO_HEIGHT = 720
    YTDLP_COOKIES_FILE = os.getenv("YTDLP_COOKIES_FILE", "")
    SPOTDL_PROXY = os.getenv("SPOTDL_PROXY", "")
