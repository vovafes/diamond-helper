"""app -- split out of main.py."""

import discord
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from discord.ext import commands
from dotenv import load_dotenv


MSK = timezone(timedelta(hours=3))  # Московское время (UTC+3)


def now_msk() -> datetime:
    """Текущее время по МСК."""
    return datetime.now(MSK).replace(tzinfo=None)

load_dotenv()
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
tree = bot.tree
