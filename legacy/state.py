"""state -- split out of main.py."""

import json
import os
from datetime import datetime
from legacy.stats_gta import (
    stats_panels,
)

DEFAULT_TICKET_IMAGE = "https://i.imgur.com/71VIhBL.png"

# ─────────────────────────────────────────────
# ХРАНИЛИЩЕ
# ─────────────────────────────────────────────
DATA_FILE     = "data.json"
POINTS_FILE   = "points.json"
ROULETTE_FILE = "roulette.json"
CHIPS_FILE    = "chips.json"

# { message_id: { "title": str, "max": int, "slots": {slot_num: user_id|None},
#                 "image_url": str|None, "note": str|None, "channel_id": int,
#                 "thread_id": int|None, "thread_msg_id": int|None } }
event_lists: dict = {}

# { guild_id: { "message_id": int, "channel_id": int } }
afk_panels: dict = {}

# 📣 РОЛЬ ДЛЯ ТЕГА В РЕАКИ
# { guild_id: int (role_id) }
event_roles: dict = {}

# { guild_id: { user_id: { "reason": str, "return_time": str, "since": datetime } } }
afk_list: dict = {}

# { guild_id: { "message_id": int, "channel_id": int } }
inactive_panels: dict = {}

# { guild_id: { user_id: { "reason": str, "return_date": str, "since": datetime } } }
inactive_list: dict = {}

# 💰 БАЛЛЫ И ШТРАФЫ
# { guild_id: { user_id: int } }
points_db: dict = {}

# 🎰 ФИШКИ (только для рулетки)
# { guild_id: { user_id: int } }
chips_db: dict = {}

# { guild_id: { user_id: { "warns": int, "reason": str, "moderator": int } } }
warns_db: dict = {}

# { guild_id: { 1: role_id, 2: role_id, 3: role_id } }
warn_roles: dict = {}

# 🎖 КАБИНЕТ РЕКРУТА
# { guild_id: { user_id: { "approved": int, "rejected": int } } }
recruit_stats: dict = {}

# { guild_id: channel_id } — канал логов выдачи варнов рекрутами
warn_log_channels: dict = {}

# { guild_id: { user_id: { "channel_id": int, "message_id": int } } } — сообщение лога варна (удаляется при снятии)
warn_log_messages: dict = {}

# { guild_id: { "channel_id": int, "message_id": int, "text": str|None, "image_url": str|None } }
recruit_cabinet_panels: dict = {}

# 🛒 ПАНЕЛЬ МАГАЗИНА
# { guild_id: { "channel_id": int, "message_id": int } }
shop_panels: dict = {}

# 🛒 ЛОГИ МАГАЗИНА { guild_id: channel_id }
shop_log_channels: dict = {}

# 🛒 РОЛЬ ВЫДАЧИ ТОВАРОВ { guild_id: role_id }
shop_manager_roles: dict = {}

# 🎫 ПАНЕЛЬ ТИКЕТОВ
# { guild_id: { "panel_channel_id": int, "review_channel_id": int, "message_id": int } }
ticket_panels: dict = {}

# 🎫 ТЕКСТ ПАНЕЛИ ТИКЕТОВ { guild_id: { "title": str, "desc": str, "image": str } }
ticket_texts: dict = {}

# 🎫 СЧЁТЧИК ТИКЕТОВ { guild_id: int }
ticket_counters: dict = {}

# 📋 КАНАЛ ЛОГОВ ОТКАЗОВ { guild_id: channel_id }
reject_log_channels: dict = {}

# 🎨 БРЕНДИНГ { guild_id: { "footer_icon": str, "approve_gif": str, "afk_image": str } }
guild_branding: dict = {}

# 🎫 РОЛЬ ТИКЕТ-МЕНЕДЖЕРА (может одобрять/отклонять) { guild_id: role_id }
ticket_manager_roles: dict = {}

# 🎫 РОЛИ С ДОСТУПОМ К ТИКЕТУ (видят канал) { guild_id: [role_id, ...] }
ticket_viewer_roles: dict = {}

# 🎫 РОЛЬ ДЛЯ ТЕГА В ТИКЕТЕ { guild_id: role_id }
ticket_ping_role: dict = {}

# 🏎 РОЛЬ МП { guild_id: role_id }
mp_roles: dict = {}

# 🔫 РОЛЬ ВЗП { guild_id: role_id }
vzp_roles: dict = {}

# 🔫 ВТОРАЯ РОЛЬ ВЗП { guild_id: role_id }
vzp_roles2: dict = {}

# ⛏ РОЛЬ ВЗХ { guild_id: role_id }
vzh_roles: dict = {}

# ⛏ ВТОРАЯ РОЛЬ ВЗХ { guild_id: role_id }
vzh_roles2: dict = {}

# 🔫 ТРЕТЬЯ РОЛЬ ВЗП { guild_id: role_id }
vzp_roles3: dict = {}

# ⛏ ТРЕТЬЯ РОЛЬ ВЗХ { guild_id: role_id }
vzh_roles3: dict = {}

# 🎯 ТРЕТЬЯ РОЛЬ LIST/РЕАКИ { guild_id: role_id }
list_roles3: dict = {}

# 📅 РАСПИСАНИЕ ВЗХ ПО ФРАКЦИЯМ { guild_id: "banda" | "mafia" }
# Банды: Пн+Ср+Пт+Вс, Мафии: Вт+Чт+Сб+Вс — используется, чтобы !vzh 20:00
# правильно определял дату сбора, даже если создаётся за несколько дней до самого ВЗХ.
vzh_schedule_settings: dict = {}

# 🎯 ВТОРАЯ РОЛЬ LIST/РЕАКИ { guild_id: role_id }
list_roles2: dict = {}

# 💾 РЕЗЕРВНОЕ КОПИРОВАНИЕ ФАЙЛОВ ДАННЫХ
# { guild_id: { "channel_id": int, "interval_hours": int, "files": [str, ...], "last_backup": str|None } }
backup_settings: dict = {}

BACKUP_AVAILABLE_FILES = [
    "data.json", "points.json", "chips.json", "roulette.json",
]

# 🎯 РОЛИ ДОСТУПА К КОМАНДАМ СБОРОВ { guild_id: { "vzp": [role_id,...], "vzh": [...], "list": [...] } }
event_command_roles: dict = {}

# 🔒 ПРИВАТНЫЕ КОМНАТЫ
# { guild_id: { "create_channel_id": int, "category_id": int, "panel_channel_id": int } }
private_vc_settings: dict = {}

# { vc_channel_id: { "owner_id": int, "guild_id": int, "panel_msg_id": int|None, "panel_channel_id": int|None } }
private_vcs: dict = {}

# 🛒 ТОВАРЫ МАГАЗИНА per-guild
# { guild_id: { item_id: { "name": str, "price": int, "emoji": str, "description": str,
#               "action": "remove_warn"|"give_role"|"notify", "role_id": int|None } } }
guild_shop_items: dict = {}

# 🔑 РОЛЬ АДМИНИСТРАТОРА { guild_id: role_id }
admin_roles: dict = {}

# 🔑 ДОПОЛНИТЕЛЬНЫЕ РОЛИ АДМИНИСТРАТОРА { guild_id: [role_id, ...] }
extra_admin_roles: dict = {}

# 📄 КОНТРАКТЫ
# { guild_id: { "channel_id": int, "message_id": int, "text": str, "image_url": str|None } }
contract_settings: dict = {}

# { guild_id: role_id }
contract_roles: dict = {}

# { message_id: { "guild_id": int, "creator_id": int, "duration": str, "start": str,
#                 "channel_id": int, "participants": [user_id, ...] } }
active_contracts: dict = {}

# 📝 ФИДБЕКИ
# { guild_id: { "panel_channel_id": int, "panel_message_id": int,
#               "log_channel_id": int|None, "ping_role_id": int|None,
#               "text": str, "image_url": str|None } }
feedback_settings: dict = {}

# 🎙 НАЧИСЛЕНИЕ ЗА ГОЛОСОВЫЕ КАНАЛЫ
# { guild_id: { "categories": [cat_id, ...], "excluded_channels": [ch_id, ...], "amount": int } }
voice_reward_settings: dict = {}

# { guild_id: channel_id } — голосовой канал для обзвонов
interview_channels: dict = {}

# { ticket_text_channel_id: voice_channel_id } — войс для обзвона по заявке
ticket_voice_channels: dict = {}

# ⚔️ ВЗП МОНИТОРИНГ
# { guild_id: { "familyId", "familyName", "serverId", "alertChannelId",
#               "resultsChannelId", "mentionRoles", "mentionUsers",
#               "pollInterval", "monitoringEnabled" } }
vzp_monitor_config: dict = {}

# { guild_id: { event_id: "notified" | "completed" } }
vzp_processed_events: dict = {}

# { guild_id: float } — timestamp последней проверки
vzp_last_check: dict = {}

# 🪪 ЛИЧНЫЙ КАБИНЕТ
# { guild_id: { "channel_id": int, "message_id": int, "text": str|None, "image_url": str|None } }
cabinet_panels: dict = {}

# { guild_id: str }  — пригласительная ссылка
cabinet_invite_links: dict = {}

# 📊 СТАТИСТИКА УЧАСТНИКОВ
# { guild_id: { user_id: int } }
message_counts: dict = {}

# { guild_id: { user_id: int } }  — накопленные минуты в войсе
voice_minutes: dict = {}

# { guild_id: { user_id: datetime } }  — время входа в канал (in-memory, не сохраняется)
voice_join_times: dict = {}

# 💰 ОБЩАК
# { guild_id: { "channel_id": int, "message_id": int, "text": str|None, "image_url": str|None } }
obshak_panels: dict = {}

# { guild_id: channel_id }
obshak_log_channels: dict = {}

# { guild_id: role_id }  — роль для тега в логах общака
obshak_ping_roles: dict = {}

# { guild_id: [ { "user_id": int, "amount": int, "date": str (ISO) } ] }
obshak_deposits: dict = {}

# ─────────────────────────────────────────────
# 📋 СОСТАВ СЕМЬИ
# ─────────────────────────────────────────────
# { guild_id: { "member_role_id": int, "academy_role_id": int,
#               "access_role_ids": [int, ...], "channel_id": int, "message_id": int } }
roster_settings: dict = {}

# { guild_id: { user_id: { "in_org": bool, "faction": str|None } } }
roster_members: dict = {}


def save_data():
    """Сохраняет все данные на диск."""
    warns_serial = {}
    for g, users in warns_db.items():
        warns_serial[str(g)] = {}
        for u, info in users.items():
            warns_serial[str(g)][str(u)] = {
                k: (v.isoformat() if isinstance(v, datetime) else v)
                for k, v in info.items()
            }

    def _serialize_user_dict(src: dict) -> dict:
        out = {}
        for g, users in src.items():
            out[str(g)] = {}
            for u, info in users.items():
                out[str(g)][str(u)] = {
                    k: (v.isoformat() if isinstance(v, datetime) else v)
                    for k, v in info.items()
                }
        return out

    afk_list_serial              = _serialize_user_dict(afk_list)
    inactive_list_serial         = _serialize_user_dict(inactive_list)

    event_lists_serial = {}
    for mid, ev in event_lists.items():
        event_lists_serial[str(mid)] = {
            **{k: v for k, v in ev.items() if k != "slots"},
            "slots": {str(s): uid for s, uid in ev.get("slots", {}).items()},
        }

    data = {
        "points":        {str(g): {str(u): v for u, v in us.items()} for g, us in points_db.items()},
        "warns":         warns_serial,
        "event_roles":   {str(g): v for g, v in event_roles.items()},
        "ticket_panels":      {str(g): v for g, v in ticket_panels.items()},
        "ticket_counters":    {str(g): v for g, v in ticket_counters.items()},
        "reject_log_channels":  {str(g): v for g, v in reject_log_channels.items()},
        "guild_branding":        {str(g): v for g, v in guild_branding.items()},
        "ticket_manager_roles": {str(g): v for g, v in ticket_manager_roles.items()},
        "mp_roles":             {str(g): v for g, v in mp_roles.items()},
        "vzp_roles":            {str(g): v for g, v in vzp_roles.items()},
        "vzp_roles2":           {str(g): v for g, v in vzp_roles2.items()},
        "vzh_roles":            {str(g): v for g, v in vzh_roles.items()},
        "vzh_roles2":           {str(g): v for g, v in vzh_roles2.items()},
        "vzh_schedule_settings": {str(g): v for g, v in vzh_schedule_settings.items()},
        "list_roles2":          {str(g): v for g, v in list_roles2.items()},
        "vzp_roles3":           {str(g): v for g, v in vzp_roles3.items()},
        "vzh_roles3":           {str(g): v for g, v in vzh_roles3.items()},
        "list_roles3":          {str(g): v for g, v in list_roles3.items()},
        "warn_roles":           {str(g): {str(k): v for k, v in wr.items()} for g, wr in warn_roles.items()},
        "admin_roles":          {str(g): v for g, v in admin_roles.items()},
        "extra_admin_roles":    {str(g): v for g, v in extra_admin_roles.items()},
        "ticket_viewer_roles":  {str(g): v for g, v in ticket_viewer_roles.items()},
        "ticket_ping_role":     {str(g): v for g, v in ticket_ping_role.items()},
        "guild_shop_items":     {str(g): v for g, v in guild_shop_items.items()},
        "event_command_roles":  {str(g): v for g, v in event_command_roles.items()},
        "private_vc_settings":  {str(g): v for g, v in private_vc_settings.items()},
        "ticket_texts":         {str(g): v for g, v in ticket_texts.items()},
        "afk_list":             afk_list_serial,
        "afk_panels":           {str(g): v for g, v in afk_panels.items()},
        "inactive_list":        inactive_list_serial,
        "inactive_panels":      {str(g): v for g, v in inactive_panels.items()},
        "event_lists":          event_lists_serial,
        "shop_panels":          {str(g): v for g, v in shop_panels.items()},
        "shop_log_channels":    {str(g): v for g, v in shop_log_channels.items()},
        "shop_manager_roles":   {str(g): v for g, v in shop_manager_roles.items()},
        "contract_settings":    {str(g): v for g, v in contract_settings.items()},
        "contract_roles":       {str(g): v for g, v in contract_roles.items()},
        "active_contracts":     {str(mid): v for mid, v in active_contracts.items()},
        "feedback_settings":    {str(g): v for g, v in feedback_settings.items()},
        "obshak_panels":        {str(g): v for g, v in obshak_panels.items()},
        "obshak_log_channels":  {str(g): v for g, v in obshak_log_channels.items()},
        "obshak_ping_roles":    {str(g): v for g, v in obshak_ping_roles.items()},
        "obshak_deposits":      {str(g): v for g, v in obshak_deposits.items()},
        "roster_settings":      {str(g): v for g, v in roster_settings.items()},
        "roster_members":       {str(g): {str(u): v for u, v in um.items()} for g, um in roster_members.items()},
        "voice_reward_settings": {str(g): v for g, v in voice_reward_settings.items()},
        "interview_channels":       {str(g): v for g, v in interview_channels.items()},
        "ticket_voice_channels": {str(c): v for c, v in ticket_voice_channels.items()},
        "vzp_monitor_config":    {str(g): v for g, v in vzp_monitor_config.items()},
        "vzp_processed_events":  {str(g): v for g, v in vzp_processed_events.items()},
        "cabinet_panels":        {str(g): v for g, v in cabinet_panels.items()},
        "cabinet_invite_links":  {str(g): v for g, v in cabinet_invite_links.items()},
        "message_counts":        {str(g): {str(u): v for u, v in us.items()} for g, us in message_counts.items()},
        "voice_minutes":         {str(g): {str(u): v for u, v in us.items()} for g, us in voice_minutes.items()},
        "stats_panels":          {str(g): v for g, v in stats_panels.items()},
        "backup_settings":       {str(g): v for g, v in backup_settings.items()},
        "recruit_stats":         {str(g): {str(u): v for u, v in us.items()} for g, us in recruit_stats.items()},
        "warn_log_channels":     {str(g): v for g, v in warn_log_channels.items()},
        "warn_log_messages":     {str(g): {str(u): v for u, v in us.items()} for g, us in warn_log_messages.items()},
        "recruit_cabinet_panels": {str(g): v for g, v in recruit_cabinet_panels.items()},
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_points():
    """Сохраняет points_db в отдельный файл points.json."""
    data = {str(g): {str(u): v for u, v in us.items()} for g, us in points_db.items()}
    with open(POINTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_points():
    """Загружает points_db из points.json (если есть)."""
    if not os.path.exists(POINTS_FILE):
        return
    try:
        with open(POINTS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        points_db.clear()
        points_db.update({int(g): {int(u): v for u, v in us.items()} for g, us in raw.items()})
        print("OK: Points loaded from points.json")
    except Exception as e:
        print(f"WARNING: Failed to load points: {e}")


def save_chips():
    try:
        data = {
            "chips": {str(g): {str(u): v for u, v in us.items()} for g, us in chips_db.items()}
        }
        with open(CHIPS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"WARNING: Failed to save chips: {e}")


def load_chips():
    try:
        if not os.path.exists(CHIPS_FILE):
            return
        with open(CHIPS_FILE, "r", encoding="utf-8") as f:
            doc = json.load(f)
        for g, us in doc.get("chips", {}).items():
            chips_db[int(g)] = {int(u): v for u, v in us.items()}
        print("OK: Chips loaded from chips.json")
    except Exception as e:
        print(f"WARNING: Failed to load chips: {e}")


def load_data():
    """Загружает данные с диска при старте."""
    if not os.path.exists(DATA_FILE):
        return
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Баллы: загружаем из points.json (приоритет) или из data.json (миграция)
        if os.path.exists(POINTS_FILE):
            load_points()
        elif data.get("points"):
            points_db.clear()
            points_db.update({
                int(g): {int(u): v for u, v in us.items()}
                for g, us in data.get("points", {}).items()
            })
            save_points()  # мигрируем в отдельный файл
        for g, users in data.get("warns", {}).items():
            warns_db[int(g)] = {}
            for u, info in users.items():
                warns_db[int(g)][int(u)] = {
                    k: (datetime.fromisoformat(v) if k == "timestamp" and v else v)
                    for k, v in info.items()
                }
        for g, v in data.get("event_roles", {}).items():
            event_roles[int(g)] = v
        for g, v in data.get("ticket_panels", {}).items():
            ticket_panels[int(g)] = v
        for g, v in data.get("ticket_counters", {}).items():
            ticket_counters[int(g)] = v
        for g, v in data.get("reject_log_channels", {}).items():
            reject_log_channels[int(g)] = v
        for g, v in data.get("guild_branding", {}).items():
            guild_branding[int(g)] = v
        for g, v in data.get("ticket_manager_roles", {}).items():
            ticket_manager_roles[int(g)] = v
        for g, v in data.get("mp_roles", {}).items():
            mp_roles[int(g)] = v
        for g, v in data.get("vzp_roles", {}).items():
            vzp_roles[int(g)] = v
        for g, v in data.get("vzp_roles2", {}).items():
            vzp_roles2[int(g)] = v
        for g, v in data.get("vzh_roles", {}).items():
            vzh_roles[int(g)] = v
        for g, v in data.get("vzh_roles2", {}).items():
            vzh_roles2[int(g)] = v
        for g, v in data.get("vzh_schedule_settings", {}).items():
            vzh_schedule_settings[int(g)] = v
        for g, v in data.get("list_roles2", {}).items():
            list_roles2[int(g)] = v
        for g, v in data.get("vzp_roles3", {}).items():
            vzp_roles3[int(g)] = v
        for g, v in data.get("vzh_roles3", {}).items():
            vzh_roles3[int(g)] = v
        for g, v in data.get("list_roles3", {}).items():
            list_roles3[int(g)] = v
        for g, wr in data.get("warn_roles", {}).items():
            warn_roles[int(g)] = {int(k): v for k, v in wr.items()}
        for g, v in data.get("admin_roles", {}).items():
            admin_roles[int(g)] = v
        for g, v in data.get("extra_admin_roles", {}).items():
            extra_admin_roles[int(g)] = v
        for g, v in data.get("ticket_viewer_roles", {}).items():
            ticket_viewer_roles[int(g)] = v
        for g, v in data.get("ticket_ping_role", {}).items():
            ticket_ping_role[int(g)] = v
        for g, v in data.get("guild_shop_items", {}).items():
            guild_shop_items[int(g)] = v
        for g, v in data.get("event_command_roles", {}).items():
            event_command_roles[int(g)] = v
        # Migrate old Russian event_type keys → English
        _key_map = {"взп": "vzp", "реаки": "list"}
        for _gid in event_command_roles:
            for _old, _new in _key_map.items():
                if _old in event_command_roles[_gid]:
                    _vals = event_command_roles[_gid].pop(_old)
                    existing = event_command_roles[_gid].get(_new, [])
                    event_command_roles[_gid][_new] = list(set(existing + _vals))
            # Старый отдельный "reaki"-бакет (доступ_сбора с типом "реaки") — слить в "list"
            if "reaki" in event_command_roles[_gid]:
                _vals = event_command_roles[_gid].pop("reaki")
                existing = event_command_roles[_gid].get("list", [])
                event_command_roles[_gid]["list"] = list(set(existing + _vals))
        for g, v in data.get("private_vc_settings", {}).items():
            private_vc_settings[int(g)] = v
        for g, v in data.get("ticket_texts", {}).items():
            ticket_texts[int(g)] = v

        # АФК
        for g, users in data.get("afk_list", {}).items():
            afk_list[int(g)] = {}
            for u, info in users.items():
                afk_list[int(g)][int(u)] = {
                    k: (datetime.fromisoformat(v) if k == "since" and v else v)
                    for k, v in info.items()
                }
        for g, v in data.get("afk_panels", {}).items():
            afk_panels[int(g)] = v

        # Инактив
        for g, users in data.get("inactive_list", {}).items():
            inactive_list[int(g)] = {}
            for u, info in users.items():
                inactive_list[int(g)][int(u)] = {
                    k: (datetime.fromisoformat(v) if k == "since" and v else v)
                    for k, v in info.items()
                }
        for g, v in data.get("inactive_panels", {}).items():
            inactive_panels[int(g)] = v

        # Сборы
        for mid, ev in data.get("event_lists", {}).items():
            event_lists[int(mid)] = {
                **{k: v for k, v in ev.items() if k not in ("slots", "reserve")},
                "slots": {int(s): uid for s, uid in ev.get("slots", {}).items()},
                "reserve": [int(u) for u in ev.get("reserve", [])],
            }

        # Панель магазина
        for g, v in data.get("shop_panels", {}).items():
            shop_panels[int(g)] = v
        for g, v in data.get("shop_log_channels", {}).items():
            shop_log_channels[int(g)] = v
        for g, v in data.get("shop_manager_roles", {}).items():
            shop_manager_roles[int(g)] = v

        # Контракты
        for g, v in data.get("contract_settings", {}).items():
            contract_settings[int(g)] = v
        for g, v in data.get("contract_roles", {}).items():
            contract_roles[int(g)] = v
        for mid, v in data.get("active_contracts", {}).items():
            active_contracts[int(mid)] = v

        # Фидбеки
        for g, v in data.get("feedback_settings", {}).items():
            feedback_settings[int(g)] = v

        # Голосовые каналы — начисление
        for g, v in data.get("voice_reward_settings", {}).items():
            voice_reward_settings[int(g)] = v
        for g, v in data.get("interview_channels", {}).items():
            interview_channels[int(g)] = v
        for c, v in data.get("ticket_voice_channels", {}).items():
            ticket_voice_channels[int(c)] = int(v)
        for g, v in data.get("vzp_monitor_config", {}).items():
            vzp_monitor_config[int(g)] = v
        for g, v in data.get("vzp_processed_events", {}).items():
            vzp_processed_events[int(g)] = v

        # Личный кабинет
        for g, v in data.get("cabinet_panels", {}).items():
            cabinet_panels[int(g)] = v
        for g, v in data.get("cabinet_invite_links", {}).items():
            cabinet_invite_links[int(g)] = v

        # Статистика
        for g, us in data.get("message_counts", {}).items():
            message_counts[int(g)] = {int(u): v for u, v in us.items()}
        for g, us in data.get("voice_minutes", {}).items():
            voice_minutes[int(g)] = {int(u): v for u, v in us.items()}

        # Общак
        for g, v in data.get("obshak_panels", {}).items():
            obshak_panels[int(g)] = v
        for g, v in data.get("obshak_log_channels", {}).items():
            obshak_log_channels[int(g)] = v
        for g, v in data.get("obshak_ping_roles", {}).items():
            obshak_ping_roles[int(g)] = v
        for g, v in data.get("obshak_deposits", {}).items():
            obshak_deposits[int(g)] = v
        for g, v in data.get("roster_settings", {}).items():
            roster_settings[int(g)] = v
        for g, um in data.get("roster_members", {}).items():
            roster_members[int(g)] = {int(u): v for u, v in um.items()}

        # Панели статистики GTA5RP
        for g, v in data.get("stats_panels", {}).items():
            stats_panels[int(g)] = v
        for g, v in data.get("backup_settings", {}).items():
            backup_settings[int(g)] = v

        # Кабинет рекрута
        for g, us in data.get("recruit_stats", {}).items():
            recruit_stats[int(g)] = {int(u): v for u, v in us.items()}
        for g, v in data.get("warn_log_channels", {}).items():
            warn_log_channels[int(g)] = v
        for g, us in data.get("warn_log_messages", {}).items():
            warn_log_messages[int(g)] = {int(u): v for u, v in us.items()}
        for g, v in data.get("recruit_cabinet_panels", {}).items():
            recruit_cabinet_panels[int(g)] = v

        print("OK: Data loaded from data.json")
    except Exception as e:
        print(f"WARNING: Failed to load data: {e}")
