"""
Multitasking (DIAMOND) -- entry point.

The old 8.9k-line main.py now lives in legacy/ (one file per feature, behaviour
unchanged); the dashboard-era modules live in modules/ (cogs with a settings
schema, managed from the web panel). This file only wires them together.
"""

import os

from legacy.app import bot, tree  # noqa: F401  (tree registers the slash commands)

# Importing a legacy module registers its commands, views, events and loops on `bot`.
from legacy import (  # noqa: F401
    afk, cabinet, contracts, core_events, economy, events, feedback, obshak,
    private_vc, recruit, roster, roulette, settings_panel, shop, stats_gta,
    tickets, timers, voice_rewards, vzp_monitor, warns,
)

# Старый функционал в веб-панели (регистрирует модули панели поверх legacy-состояния)
import panel_modules  # noqa: F401

# Модули с настройками из веб-панели (modules/*.py)
MODULE_EXTENSIONS: list[str] = [
    "modules.server_logging",
    "modules.moderation",
    "modules.automod",
    "modules.anti_nuke",
    "modules.giveaways",
    "modules.automations",
    "modules.support_tickets",
    "modules.verification",
    "modules.autorole",
    "modules.reaction_roles",
    "modules.welcome",
    "modules.levels",
    "modules.suggestions",
    "modules.polls",
    "modules.reminders",
    "modules.birthdays",
    "modules.starboard",
    "modules.sticky",
    "modules.guards",
    "modules.roles_extra",
    "modules.voice_server",
    "modules.team",
    "modules.server_tools",
    "modules.community_tools",
    "modules.support_team",
]


async def _setup_hook():
    # Сначала модули: они регистрируют свои маршруты панели, а после старта сервера
    # новые маршруты добавить уже нельзя.
    for ext in MODULE_EXTENSIONS:
        try:
            await bot.load_extension(ext)
        except Exception as e:
            print(f"WARNING: модуль {ext} не загрузился: {e}")
    # Веб-панель живёт в event loop бота и на том же $PORT (GET /health отвечает "OK").
    try:
        from dashboard import server as dashboard_server
        await dashboard_server.start(bot)
    except Exception as e:  # панель не должна ронять бота
        print(f"WARNING: dashboard не запустился: {e}")


bot.setup_hook = _setup_hook

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
