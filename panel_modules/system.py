"""Panel modules: system settings (branding, admin roles, backups)."""

import discord

from core import modules
from legacy.state import (
    BACKUP_AVAILABLE_FILES, admin_roles, backup_settings, extra_admin_roles, guild_branding, save_data,
)
from legacy.timers import send_backup_now
from panel_modules.common import bot, put, spawn

reg = modules.register


# ── Брендинг ────────────────────────────────────────────────────────────────

def _brand_load(gid):
    b = guild_branding.get(gid) or {}
    return {"footer_icon": b.get("footer_icon") or "", "approve_gif": b.get("approve_gif") or "", "afk_image": b.get("afk_image") or ""}


def _brand_save(gid, cfg):
    put(guild_branding, gid, {k: (cfg[k] or "").strip() for k in ("footer_icon", "approve_gif", "afk_image") if (cfg[k] or "").strip()})
    save_data()


reg(modules.Module(
    key="branding", title="Брендинг", icon="🖼", category="system", toggleable=False,
    description="Картинки в сообщениях бота. Пусто — стандартные.",
    fields=[
        {"key": "footer_icon", "label": "Иконка в футере", "type": "text", "default": "", "help": "Прямая ссылка на картинку"},
        {"key": "approve_gif", "label": "GIF при одобрении заявки", "type": "text", "default": ""},
        {"key": "afk_image", "label": "Картинка панели АФК", "type": "text", "default": ""},
    ],
    loader=_brand_load, saver=_brand_save,
))


# ── Администраторы бота ─────────────────────────────────────────────────────

def _admin_load(gid):
    return {"admin_role": admin_roles.get(gid), "extra_roles": extra_admin_roles.get(gid, [])}


def _admin_save(gid, cfg):
    put(admin_roles, gid, cfg["admin_role"])
    put(extra_admin_roles, gid, cfg["extra_roles"])
    save_data()


reg(modules.Module(
    key="admin_access", title="Администраторы бота", icon="🔑", category="system", toggleable=False,
    description="Кто может пользоваться админ-командами бота (помимо администраторов Discord).",
    fields=[
        {"key": "admin_role", "label": "Главная админ-роль", "type": "role", "default": None},
        {"key": "extra_roles", "label": "Дополнительные админ-роли", "type": "roles", "default": []},
    ],
    loader=_admin_load, saver=_admin_save,
))


# ── Бэкапы ──────────────────────────────────────────────────────────────────

INTERVALS = [1, 3, 6, 12, 24, 48]


def _backup_load(gid):
    b = backup_settings.get(gid, {})
    return {"channel": b.get("channel_id"), "interval": str(b.get("interval_hours", 1)), "files": b.get("files", []),
            "last": b.get("last_backup") or "ещё не было"}


def _backup_save(gid, cfg):
    b = backup_settings.setdefault(gid, {})
    b["channel_id"], b["interval_hours"], b["files"] = cfg["channel"], int(cfg["interval"]), cfg["files"]
    save_data()


async def _backup_now(ctx, p):
    if not await send_backup_now(ctx.guild):
        raise modules.ValidationError("Не вышло: выберите канал и хотя бы один файл (и сохраните)")
    return "Бэкап отправлен в канал"


reg(modules.Module(
    key="backup", title="Резервные копии", icon="💾", category="system", toggleable=False,
    description="Бот по расписанию отправляет выбранные файлы данных в канал.",
    fields=[
        {"key": "channel", "label": "Канал для бэкапов", "type": "channel", "kind": "text", "default": None},
        {"key": "interval", "label": "Период", "type": "select", "default": "1",
         "options": [{"value": str(h), "label": f"каждые {h} ч."} for h in INTERVALS]},
        {"key": "files", "label": "Файлы", "type": "multiselect", "default": [],
         "options": list(BACKUP_AVAILABLE_FILES)},
        {"key": "last", "label": "Последний бэкап", "type": "text", "default": "", "readonly": True},
    ],
    loader=_backup_load, saver=_backup_save,
    actions=[modules.Action("now", "Сделать бэкап сейчас", _backup_now)],
))
