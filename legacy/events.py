"""events -- split out of main.py."""

import discord
import io
import re
from discord import app_commands
from discord import ui
from legacy.app import (
    bot,
    now_msk,
    tree,
)
from legacy.helpers import (
    _footer,
    build_event_embed,
    can_manage_event_message,
    can_run_event,
    get_vzh_faction,
    is_admin,
    is_admin_ctx,
    next_vzh_datetime,
)
from legacy.state import (
    event_command_roles,
    event_lists,
    event_roles,
    list_roles2,
    list_roles3,
    mp_roles,
    save_data,
    vzh_roles,
    vzh_roles2,
    vzh_roles3,
    vzp_roles,
    vzp_roles2,
    vzp_roles3,
)



def build_thread_list(title: str, max_count: int, slots: dict, reserve: list | None = None) -> str:
    filled = sum(1 for v in slots.values() if v is not None)
    lines  = [f"**📋 Список: {title} ({filled}/{max_count})**\n"]
    for i in range(1, max_count + 1):
        uid = slots.get(i)
        lines.append(f"`{str(i).zfill(2)}.` {'<@' + str(uid) + '>' if uid else 'свободно'}")
    reserve = reserve or []
    lines.append(f"\n**🪑 Резерв ({len(reserve)}):**")
    if reserve:
        for i, uid in enumerate(reserve, 1):
            lines.append(f"`R{str(i).zfill(2)}.` <@{uid}>")
    else:
        lines.append("*пусто*")
    return "\n".join(lines)


class KickModal(ui.Modal, title="Кикнуть из списка"):
    user_id = ui.TextInput(
        label="ID пользователя",
        placeholder="Вставь Discord ID (например: 123456789012345678)",
        min_length=17,
        max_length=20,
    )

    def __init__(self, message_id: int):
        super().__init__()
        self.message_id = message_id

    async def on_submit(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Нет прав!", ephemeral=True)

        try:
            target_id = int(str(self.user_id).strip())
        except ValueError:
            return await interaction.response.send_message("❌ Некорректный ID!", ephemeral=True)

        data = event_lists.get(self.message_id)
        if not data:
            return await interaction.response.send_message("❌ Сбор не найден!", ephemeral=True)

        slots = data["slots"]
        reserve = data.setdefault("reserve", [])
        removed_from = None
        for slot_num, uid in slots.items():
            if uid == target_id:
                slots[slot_num] = None
                removed_from = f"слота **{slot_num}**"
                break
        if removed_from is None and target_id in reserve:
            reserve.remove(target_id)
            removed_from = "резерва"

        if removed_from is None:
            return await interaction.response.send_message(
                f"❌ Пользователь `{target_id}` не найден в списке!", ephemeral=True
            )

        save_data()
        try:
            channel = bot.get_channel(data["channel_id"])
            orig_msg = await channel.fetch_message(self.message_id)
            embed = build_event_embed(
                interaction.guild_id, data["title"], data["max"], slots,
                data.get("image_url"), data.get("note"),
                event_time=data.get("event_time"), closed=data.get("closed", False),
                reserve=reserve,
                join_mode=data.get("cmd") in ("list", "vzh"),
            )
            view = event_view(self.message_id)
            await orig_msg.edit(embed=embed, view=view)
        except Exception:
            pass

        await update_thread_list(self.message_id)
        return await interaction.response.send_message(
            f"✅ <@{target_id}> убран из {removed_from}", ephemeral=True
        )


class KickButton(ui.Button):
    def __init__(self, message_id: int):
        super().__init__(
            label="Кикнуть",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            custom_id=f"kick_from_list_{message_id}",
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Только для администраторов!", ephemeral=True)
        await interaction.response.send_modal(KickModal(self.message_id))


class CloseListButton(ui.Button):
    def __init__(self, message_id: int, is_closed: bool):
        super().__init__(
            label="🔓 Открыть список" if is_closed else "🔒 Закрыть список",
            style=discord.ButtonStyle.secondary if is_closed else discord.ButtonStyle.danger,
            custom_id=f"close_list_{message_id}",
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Только для администраторов!", ephemeral=True)

        data = event_lists.get(self.message_id)
        if not data:
            return await interaction.response.send_message("❌ Сбор не найден!", ephemeral=True)

        data["closed"] = not data.get("closed", False)
        save_data()

        try:
            channel = bot.get_channel(data["channel_id"])
            orig_msg = await channel.fetch_message(self.message_id)
            embed = build_event_embed(
                interaction.guild_id, data["title"], data["max"], data["slots"],
                data.get("image_url"), data.get("note"),
                event_time=data.get("event_time"), closed=data["closed"],
                reserve=data.get("reserve", []),
                join_mode=data.get("cmd") in ("list", "vzh"),
            )
            view = event_view(self.message_id)
            await orig_msg.edit(embed=embed, view=view)
        except Exception:
            pass

        await update_thread_list(self.message_id)
        status = "закрыт 🔒" if data["closed"] else "открыт 🔓"
        await interaction.response.send_message(f"✅ Список **{status}**!", ephemeral=True)


class PromoteFromReserveModal(ui.Modal, title="Убрать с резерва в основу"):
    user_id = ui.TextInput(
        label="ID пользователя",
        placeholder="Вставь Discord ID (например: 123456789012345678)",
        min_length=17,
        max_length=20,
    )

    def __init__(self, message_id: int):
        super().__init__()
        self.message_id = message_id

    async def on_submit(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Нет прав!", ephemeral=True)

        try:
            target_id = int(str(self.user_id).strip())
        except ValueError:
            return await interaction.response.send_message("❌ Некорректный ID!", ephemeral=True)

        data = event_lists.get(self.message_id)
        if not data:
            return await interaction.response.send_message("❌ Сбор не найден!", ephemeral=True)

        slots = data["slots"]
        reserve = data.setdefault("reserve", [])
        if target_id not in reserve:
            return await interaction.response.send_message(
                f"❌ Пользователь `{target_id}` не найден в резерве!", ephemeral=True
            )

        free_slot = None
        for i in range(1, data["max"] + 1):
            if slots.get(i) is None:
                free_slot = i
                break

        if free_slot is None:
            return await interaction.response.send_message(
                "❌ Нет свободных слотов в основе!", ephemeral=True
            )

        reserve.remove(target_id)
        slots[free_slot] = target_id
        save_data()

        try:
            channel = bot.get_channel(data["channel_id"])
            orig_msg = await channel.fetch_message(self.message_id)
            embed = build_event_embed(
                interaction.guild_id, data["title"], data["max"], slots,
                data.get("image_url"), data.get("note"),
                event_time=data.get("event_time"), closed=data.get("closed", False),
                reserve=reserve,
                join_mode=data.get("cmd") in ("list", "vzh"),
            )
            view = event_view(self.message_id)
            await orig_msg.edit(embed=embed, view=view)
        except Exception:
            pass

        await update_thread_list(self.message_id)
        return await interaction.response.send_message(
            f"✅ <@{target_id}> перенесён из резерва в слот **{free_slot}**", ephemeral=True
        )


class PromoteFromReserveButton(ui.Button):
    def __init__(self, message_id: int):
        super().__init__(
            label="Убрать с резерва в основу",
            emoji="⬆️",
            style=discord.ButtonStyle.primary,
            custom_id=f"promote_from_reserve_{message_id}",
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Только для администраторов!", ephemeral=True)
        await interaction.response.send_modal(PromoteFromReserveModal(self.message_id))


class ThreadListView(ui.View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.add_item(KickButton(message_id))
        self.add_item(PromoteFromReserveButton(message_id))
        data = event_lists.get(message_id)
        self.add_item(CloseListButton(message_id, (data or {}).get("closed", False)))


async def update_thread_list(message_id: int):
    data = event_lists.get(message_id)
    if not data or not data.get("thread_msg_id"):
        return
    try:
        thread = bot.get_channel(data["thread_id"])
        if not thread:
            return
        msg = await thread.fetch_message(data["thread_msg_id"])
        await msg.edit(
            content=build_thread_list(
                data["title"], data["max"], data["slots"], data.get("reserve", [])
            ),
            view=ThreadListView(message_id),
        )
    except Exception:
        pass


def _find_event_by_thread(thread_id: int):
    """Находит сбор по ID его треда с обсуждением."""
    for mid, data in event_lists.items():
        if data.get("thread_id") == thread_id:
            return mid, data
    return None, None


async def _handle_thread_slot_pick(message: discord.Message):
    """Альтернатива кнопкам: если написать номер слота в треде сбора — занимает/освобождает его."""
    content = message.content.strip()
    if not content.isdigit():
        return

    message_id, data = _find_event_by_thread(message.channel.id)
    if not data:
        return
    if data.get("closed"):
        return

    slot_num  = int(content)
    max_count = data.get("max", 0)
    if not (1 <= slot_num <= max_count):
        return

    user_id = message.author.id
    slots   = data["slots"]
    reserve = data.setdefault("reserve", [])

    if slots.get(slot_num) == user_id:
        slots[slot_num] = None
        reply = f"❌ {message.author.mention} покинул(а) слот **{slot_num}**"
    elif slots.get(slot_num) is not None:
        try:
            await message.channel.send(f"❌ Слот **{slot_num}** уже занят!", delete_after=6)
        except Exception:
            pass
        return
    else:
        for s, uid in list(slots.items()):
            if uid == user_id:
                slots[s] = None
        if user_id in reserve:
            reserve.remove(user_id)
        slots[slot_num] = user_id
        reply = f"✅ {message.author.mention} занял(а) слот **{slot_num}**!"

    save_data()
    try:
        channel  = bot.get_channel(data["channel_id"])
        orig_msg = await channel.fetch_message(message_id)
        embed = build_event_embed(
            message.guild.id, data["title"], data["max"], slots,
            data.get("image_url"), data.get("note"),
            event_time=data.get("event_time"), closed=data.get("closed", False),
            reserve=reserve,
            join_mode=data.get("cmd") in ("list", "vzh"),
        )
        view = event_view(message_id)
        await orig_msg.edit(embed=embed, view=view)
    except Exception:
        pass

    await update_thread_list(message_id)
    try:
        await message.channel.send(reply, delete_after=6)
    except Exception:
        pass


# ─────────────────────────────────────────────
# СБОР — СЛОТЫ
# ─────────────────────────────────────────────
class SlotButton(ui.Button):
    def __init__(self, slot_num: int, message_id: int, taken_by: int | None, row: int | None = None):
        super().__init__(
            label=str(slot_num),
            style=discord.ButtonStyle.danger if taken_by else discord.ButtonStyle.success,
            custom_id=f"slot_{message_id}_{slot_num}",
            row=row,
        )
        self.slot_num = slot_num
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        data = event_lists.get(self.message_id)
        if not data:
            return await interaction.response.send_message("❌ Сбор уже недоступен!", ephemeral=True)

        if data.get("closed"):
            return await interaction.response.send_message("🔒 Список закрыт!", ephemeral=True)

        user_id = interaction.user.id
        slots   = data["slots"]

        reserve = data.setdefault("reserve", [])
        if slots.get(self.slot_num) == user_id:
            # Покинуть слот
            slots[self.slot_num] = None
            msg_text = f"❌ Вы покинули слот **{self.slot_num}**"
        elif slots.get(self.slot_num) is not None:
            return await interaction.response.send_message(
                f"❌ Слот **{self.slot_num}** уже занят!", ephemeral=True
            )
        else:
            # Освободить предыдущий слот если есть
            for s, uid in slots.items():
                if uid == user_id:
                    slots[s] = None
                    break
            if user_id in reserve:
                reserve.remove(user_id)
            slots[self.slot_num] = user_id
            msg_text = f"✅ Вы заняли слот **{self.slot_num}**!"

        save_data()
        new_view = event_view(self.message_id)
        embed    = build_event_embed(
            interaction.guild_id, data["title"], data["max"], slots,
            data.get("image_url"), data.get("note"),
            event_time=data.get("event_time"), closed=data.get("closed", False),
            reserve=reserve,
            join_mode=data.get("cmd") in ("list", "vzh"),
        )
        await interaction.response.defer()
        await interaction.message.edit(embed=embed, view=new_view)
        await update_thread_list(self.message_id)
        await interaction.followup.send(msg_text, ephemeral=True)


class ReserveButton(ui.Button):
    """Кнопка записи в резерв (запасной список)."""
    def __init__(self, message_id: int):
        super().__init__(
            label="Резерв",
            emoji="🪑",
            style=discord.ButtonStyle.secondary,
            custom_id=f"reserve_{message_id}",
            row=2,
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        data = event_lists.get(self.message_id)
        if not data:
            return await interaction.response.send_message("❌ Сбор уже недоступен!", ephemeral=True)
        if data.get("closed"):
            return await interaction.response.send_message("🔒 Список закрыт!", ephemeral=True)

        user_id = interaction.user.id
        slots = data["slots"]
        reserve = data.setdefault("reserve", [])

        if user_id in reserve:
            reserve.remove(user_id)
            msg_text = "❌ Вы покинули **резерв**"
        else:
            for s, uid in list(slots.items()):
                if uid == user_id:
                    slots[s] = None
            if user_id not in reserve:
                reserve.append(user_id)
            msg_text = "✅ Вы записались в **резерв**!"

        save_data()
        embed = build_event_embed(
            interaction.guild_id, data["title"], data["max"], slots,
            data.get("image_url"), data.get("note"),
            event_time=data.get("event_time"), closed=data.get("closed", False),
            reserve=reserve,
            join_mode=data.get("cmd") in ("list", "vzh"),
        )
        view = event_view(self.message_id)
        await interaction.response.defer()
        await interaction.message.edit(embed=embed, view=view)
        await update_thread_list(self.message_id)
        await interaction.followup.send(msg_text, ephemeral=True)


class DeleteImageButton(ui.Button):
    """Кнопка-корзина: удаляет прикреплённое к сбору фото из эмбеда."""
    def __init__(self, message_id: int):
        super().__init__(
            emoji="🗑️",
            style=discord.ButtonStyle.secondary,
            custom_id=f"delimg_{message_id}",
            row=4,
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        data = event_lists.get(self.message_id)
        if not data:
            return await interaction.response.send_message("❌ Сбор уже недоступен!", ephemeral=True)
        if not data.get("image_url"):
            return await interaction.response.send_message("❌ Фото уже удалено.", ephemeral=True)
        if not can_manage_event_message(interaction, data):
            return await interaction.response.send_message("❌ Недостаточно прав для удаления фото!", ephemeral=True)

        data["image_url"] = None
        save_data()

        embed = build_event_embed(
            interaction.guild_id, data["title"], data["max"], data["slots"],
            None, data.get("note"),
            event_time=data.get("event_time"), closed=data.get("closed", False),
            reserve=data.get("reserve", []),
            join_mode=data.get("cmd") in ("list", "vzh"),
        )
        view = event_view(self.message_id)
        await interaction.response.edit_message(embed=embed, view=view, attachments=[])


class PrevPageButton(ui.Button):
    def __init__(self, message_id: int, page: int):
        super().__init__(
            emoji="◀",
            style=discord.ButtonStyle.blurple,
            custom_id=f"prevpage_{message_id}",
            disabled=(page <= 0),
            row=2,
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        data = event_lists.get(self.message_id)
        if not data:
            return await interaction.response.send_message("❌ Сбор уже недоступен!", ephemeral=True)
        data["page"] = max(0, data.get("page", 0) - 1)
        save_data()
        await interaction.response.edit_message(view=PaginatedEventView(self.message_id))


class NextPageButton(ui.Button):
    def __init__(self, message_id: int, page: int, total_pages: int):
        super().__init__(
            emoji="▶",
            style=discord.ButtonStyle.blurple,
            custom_id=f"nextpage_{message_id}",
            disabled=(page >= total_pages - 1),
            row=2,
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        data = event_lists.get(self.message_id)
        if not data:
            return await interaction.response.send_message("❌ Сбор уже недоступен!", ephemeral=True)
        max_count = data.get("max", 0)
        total_pages = max(1, (max_count + PaginatedEventView.PAGE_SIZE - 1) // PaginatedEventView.PAGE_SIZE)
        data["page"] = min(total_pages - 1, data.get("page", 0) + 1)
        save_data()
        await interaction.response.edit_message(view=PaginatedEventView(self.message_id))


class PageIndicatorButton(ui.Button):
    """Неактивная кнопка-индикатор текущей страницы."""
    def __init__(self, message_id: int, page: int, total_pages: int):
        super().__init__(
            label=f"{page + 1}/{total_pages}",
            style=discord.ButtonStyle.secondary,
            custom_id=f"pageindicator_{message_id}",
            disabled=True,
            row=2,
        )


class PaginatedEventView(ui.View):
    """Кнопки-слоты постранично (по PAGE_SIZE шт.), с навигацией ◀ ▶."""
    PAGE_SIZE = 10

    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.message_id = message_id
        data = event_lists.get(message_id)
        if not data:
            return
        slots     = data.get("slots", {})
        max_count = data.get("max", 0)
        has_image = bool(data.get("image_url"))

        total_pages = max(1, (max_count + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        page = max(0, min(data.get("page", 0), total_pages - 1))
        data["page"] = page

        start = page * self.PAGE_SIZE + 1
        end   = min(max_count, start + self.PAGE_SIZE - 1)
        for i in range(start, end + 1):
            local_i = i - start
            self.add_item(SlotButton(i, message_id, slots.get(i), row=local_i // 5))

        if total_pages > 1:
            self.add_item(PrevPageButton(message_id, page))
            self.add_item(PageIndicatorButton(message_id, page, total_pages))
            self.add_item(NextPageButton(message_id, page, total_pages))
        self.add_item(ReserveButton(message_id))
        if has_image:
            self.add_item(DeleteImageButton(message_id))


class JoinButton(ui.Button):
    """Одна кнопка ✅ «Записаться» — используется для !list."""
    def __init__(self, message_id: int):
        super().__init__(
            label="Записаться",
            emoji="✅",
            style=discord.ButtonStyle.success,
            custom_id=f"join_{message_id}",
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        data = event_lists.get(self.message_id)
        if not data:
            return await interaction.response.send_message("❌ Сбор недоступен!", ephemeral=True)
        if data.get("closed"):
            return await interaction.response.send_message("🔒 Список закрыт!", ephemeral=True)

        user_id = interaction.user.id
        slots   = data["slots"]
        reserve = data.setdefault("reserve", [])

        for slot_num, uid in slots.items():
            if uid == user_id:
                slots[slot_num] = None
                save_data()
                embed = build_event_embed(
                    interaction.guild_id, data["title"], data["max"], slots,
                    data.get("image_url"), data.get("note"), join_mode=True,
                    event_time=data.get("event_time"), closed=data.get("closed", False),
                    reserve=reserve,
                )
                view = JoinEventView(self.message_id)
                await interaction.response.defer()
                await interaction.message.edit(embed=embed, view=view)
                await update_thread_list(self.message_id)
                await interaction.followup.send("❌ Вы покинули сбор", ephemeral=True)
                return

        for i in range(1, data["max"] + 1):
            if slots.get(i) is None:
                if user_id in reserve:
                    reserve.remove(user_id)
                slots[i] = user_id
                save_data()
                embed = build_event_embed(
                    interaction.guild_id, data["title"], data["max"], slots,
                    data.get("image_url"), data.get("note"), join_mode=True,
                    event_time=data.get("event_time"), closed=data.get("closed", False),
                    reserve=reserve,
                )
                view = JoinEventView(self.message_id)
                await interaction.response.defer()
                await interaction.message.edit(embed=embed, view=view)
                await update_thread_list(self.message_id)
                await interaction.followup.send("✅ Вы записались в сбор!", ephemeral=True)
                return

        await interaction.response.send_message(
            "❌ Все места заняты! Запишись в **🪑 Резерв**.", ephemeral=True
        )


class JoinEventView(ui.View):
    """View с кнопкой ✅ «Записаться» и резервом — используется для !list."""
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.add_item(JoinButton(message_id))
        self.add_item(ReserveButton(message_id))
        data = event_lists.get(message_id)
        if data and data.get("image_url"):
            self.add_item(DeleteImageButton(message_id))


def event_view(message_id: int) -> ui.View:
    """Выбирает вид кнопок сбора: одна «Записаться» для !list, слоты — для остальных."""
    data = event_lists.get(message_id)
    if data and data.get("cmd") in ("list", "vzh"):
        return JoinEventView(message_id)
    return PaginatedEventView(message_id)




# ─────────────────────────────────────────────
# СЛЭШ-КОМАНДЫ
# ─────────────────────────────────────────────
@bot.command(name="роль_реаки")
async def set_event_role(ctx, роль: discord.Role):
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    """!роль_реаки @роль — настроить роль для тега при !vzp и !list"""
    event_roles[ctx.guild.id] = роль.id
    save_data()
    embed = discord.Embed(
        title="✅ Роль настроена",
        description=f"При каждом `!vzp` и `!list` будет тегаться {роль.mention}",
        color=discord.Color.green(),
    )
    embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
    await ctx.send(embed=embed, delete_after=10)
    await ctx.message.delete()


async def _create_event_message(channel, guild, title: str, max_count: int, image_file=None, image_ref: str | None = None, content: str | None = None, event_time: str = None, cmd: str | None = None, event_datetime: str | None = None):
    """Создаёт сбор: эмбед + тред. Кнопки-слоты идут постранично по 10 шт."""
    if not (1 <= max_count <= 100):
        await channel.send("❌ Количество слотов: от 1 до 100!", delete_after=5)
        return

    slots = {i: None for i in range(1, max_count + 1)}
    join_mode = (cmd in ("list", "vzh"))

    embed = build_event_embed(guild.id, title, max_count, slots, image_ref, event_time=event_time, join_mode=join_mode)

    if image_file:
        msg = await channel.send(content=content, embed=embed, file=image_file)
    else:
        msg = await channel.send(content=content, embed=embed)

    # Для последующих редактирований используем URL из вложения сообщения (стабильнее)
    if image_ref and msg.attachments:
        image_ref = msg.attachments[0].url
        embed.set_image(url=image_ref)

    event_lists[msg.id] = {
        "title": title, "max": max_count, "page": 0,
        "slots": slots, "reserve": [], "image_url": image_ref, "note": None,
        "channel_id": channel.id, "thread_id": None, "thread_msg_id": None,
        "event_time": event_time, "closed": False, "cmd": cmd,
        "created_at": now_msk().isoformat(), "reminded": False,
        "event_datetime": event_datetime,
    }

    view = event_view(msg.id)
    await msg.edit(embed=embed, view=view)

    # Тред с живым списком
    try:
        hint = (
            "✅ Записаться · 🪑 Резерв — запасной список\n"
            "Или напиши номер слота (например `23`) прямо в этом треде, чтобы занять его."
            if join_mode else
            "Кнопка слота · 🪑 Резерв — запасной список\n"
            "Или напиши номер слота (например `23`) прямо в этом треде, чтобы занять его."
        )
        thread = await msg.create_thread(name=f"💬 {title}", auto_archive_duration=1440)
        thread_embed = discord.Embed(
            description=f"📋 Обсуждение сбора **{title}**\n{hint}",
            color=discord.Color.blurple(),
        )
        thread_embed.set_footer(text="DIAMOND", icon_url=_footer(guild.id))
        await thread.send(embed=thread_embed)
        list_msg = await thread.send(
            build_thread_list(title, max_count, slots, []),
            view=ThreadListView(msg.id),
        )
        event_lists[msg.id]["thread_id"]     = thread.id
        event_lists[msg.id]["thread_msg_id"] = list_msg.id
    except Exception:
        pass
    save_data()


# ─────────────────────────────────────────────
# PREFIX-КОМАНДЫ СБОРОВ
# ─────────────────────────────────────────────
async def _extract_event_image(ctx) -> tuple[discord.File | None, str | None]:
    """Достаёт вложенное к сообщению фото и готовит его для встраивания в эмбед сбора."""
    if not ctx.message.attachments:
        return None, None
    att = ctx.message.attachments[0]
    try:
        img_bytes = await att.read()
        ext       = att.filename.rsplit(".", 1)[-1].lower() if "." in att.filename else "png"
        safe_name = f"event_image.{ext}"
        return discord.File(io.BytesIO(img_bytes), filename=safe_name), f"attachment://{safe_name}"
    except Exception:
        return None, None


def _extract_event_time(название: str, default_title: str) -> tuple[str | None, str]:
    """Вытаскивает ЧЧ:ММ из начала названия сбора, если оно там указано."""
    m = re.match(r'^(\d{1,2}:\d{2})\s*(.*)', название)
    if not m:
        return None, название
    return m.group(1), (m.group(2).strip() or default_title)


def _event_mentions(guild: discord.Guild, role_ids: list) -> str | None:
    """Собирает упоминания ролей для тега в сообщении сбора."""
    mentions = []
    for rid in role_ids:
        if not rid:
            continue
        r = guild.get_role(rid)
        if r:
            mentions.append(r.mention)
    return " ".join(mentions) if mentions else None


@bot.command(name="vzp")
async def взп_cmd(ctx, количество: int = 10, *, название: str = "ВЗП"):
    """!vzp [количество] [название] — сбор с фото (от лица бота)"""
    if not can_run_event(ctx, "vzp"):
        return await ctx.message.delete()

    image_file, image_ref = await _extract_event_image(ctx)

    try:
        await ctx.message.delete()
    except Exception:
        pass

    # Тег: роль ВЗП + роль МП + доп. роль
    content = _event_mentions(ctx.guild, [
        vzp_roles.get(ctx.guild.id),
        mp_roles.get(ctx.guild.id),
        vzp_roles2.get(ctx.guild.id),
        vzp_roles3.get(ctx.guild.id),
    ])

    event_time, название = _extract_event_time(название, "ВЗП")

    await _create_event_message(ctx.channel, ctx.guild, название, количество, image_file, image_ref, content=content, event_time=event_time, cmd="vzp")


@bot.command(name="vzh")
async def взх_cmd(ctx, *, args: str = ""):
    """!vzh <ЧЧ:ММ> [количество] [название] — сбор ВЗХ; за 30 минут до времени всем занявшим слот придёт напоминание в ЛС"""
    if not can_run_event(ctx, "vzh"):
        return await ctx.message.delete()

    event_time = None
    количество = 10
    название = "ВЗХ"
    m = re.match(r'^(\d{1,2}:\d{2})(?:\s+(\d+))?(?:\s+(.*))?$', args.strip())
    if m:
        event_time = m.group(1)
        if m.group(2):
            количество = int(m.group(2))
        if m.group(3) and m.group(3).strip():
            название = m.group(3).strip()

    if not event_time:
        try:
            await ctx.message.delete()
        except Exception:
            pass
        return await ctx.send(
            "⚠️ Укажи время сбора первым: `!vzh 18:30 [количество] [название]`",
            delete_after=8,
        )

    image_file, image_ref = await _extract_event_image(ctx)

    try:
        await ctx.message.delete()
    except Exception:
        pass

    content = _event_mentions(ctx.guild, [
        vzh_roles.get(ctx.guild.id),
        vzh_roles2.get(ctx.guild.id),
        vzh_roles3.get(ctx.guild.id),
    ])

    hour, minute = map(int, event_time.split(":"))
    faction = get_vzh_faction(ctx.guild.id)
    event_datetime = next_vzh_datetime(now_msk(), hour, minute, faction).isoformat()

    await _create_event_message(ctx.channel, ctx.guild, название, количество, image_file, image_ref, content=content, event_time=event_time, cmd="vzh", event_datetime=event_datetime)


@bot.command(name="роль_взп")
async def set_vzp_role(ctx, роль: discord.Role):
    """!роль_взп @роль — настроить роль ВЗП для тега в !vzp"""
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    vzp_roles[ctx.guild.id] = роль.id
    save_data()
    embed = discord.Embed(
        title="✅ Роль ВЗП настроена",
        description=f"В `!vzp` будет тегаться {роль.mention}",
        color=discord.Color.green(),
    )
    embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
    await ctx.send(embed=embed, delete_after=10)
    await ctx.message.delete()


@bot.command(name="роль_мп")
async def set_mp_role(ctx, роль: discord.Role):
    """!роль_мп @роль — настроить роль МП для тега в !vzp"""
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    mp_roles[ctx.guild.id] = роль.id
    save_data()
    embed = discord.Embed(
        title="✅ Роль МП настроена",
        description=f"В `!vzp` будет тегаться {роль.mention}",
        color=discord.Color.green(),
    )
    embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
    await ctx.send(embed=embed, delete_after=10)
    await ctx.message.delete()


@bot.command(name="роль_взп2")
async def set_vzp_role2(ctx, роль: discord.Role = None):
    """!роль_взп2 [@роль] — доп. роль для тега в !vzp; без роли — сбросить настройку"""
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    if роль is None:
        vzp_roles2.pop(ctx.guild.id, None)
        save_data()
        embed = discord.Embed(title="✅ Доп. роль ВЗП сброшена", description="В `!vzp` больше не будет тегаться доп. роль.", color=discord.Color.orange())
    else:
        vzp_roles2[ctx.guild.id] = роль.id
        save_data()
        embed = discord.Embed(
            title="✅ Доп. роль ВЗП настроена",
            description=f"В `!vzp` дополнительно будет тегаться {роль.mention}",
            color=discord.Color.green(),
        )
    embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
    await ctx.send(embed=embed, delete_after=10)
    await ctx.message.delete()


@bot.command(name="роль_взх")
async def set_vzh_role(ctx, роль: discord.Role):
    """!роль_взх @роль — настроить роль ВЗХ для тега в !vzh"""
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    vzh_roles[ctx.guild.id] = роль.id
    save_data()
    embed = discord.Embed(
        title="✅ Роль ВЗХ настроена",
        description=f"В `!vzh` будет тегаться {роль.mention}",
        color=discord.Color.green(),
    )
    embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
    await ctx.send(embed=embed, delete_after=10)
    await ctx.message.delete()


@bot.command(name="роль_взх2")
async def set_vzh_role2(ctx, роль: discord.Role = None):
    """!роль_взх2 [@роль] — доп. роль для тега в !vzh; без роли — сбросить настройку"""
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    if роль is None:
        vzh_roles2.pop(ctx.guild.id, None)
        save_data()
        embed = discord.Embed(title="✅ Доп. роль ВЗХ сброшена", description="В `!vzh` больше не будет тегаться доп. роль.", color=discord.Color.orange())
    else:
        vzh_roles2[ctx.guild.id] = роль.id
        save_data()
        embed = discord.Embed(
            title="✅ Доп. роль ВЗХ настроена",
            description=f"В `!vzh` дополнительно будет тегаться {роль.mention}",
            color=discord.Color.green(),
        )
    embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
    await ctx.send(embed=embed, delete_after=10)
    await ctx.message.delete()


@bot.command(name="роль_реаки2")
async def set_event_role2(ctx, роль: discord.Role = None):
    """!роль_реаки2 [@роль] — доп. роль для тега в !list; без роли — сбросить настройку"""
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    if роль is None:
        list_roles2.pop(ctx.guild.id, None)
        save_data()
        embed = discord.Embed(title="✅ Доп. роль list сброшена", description="В `!list` больше не будет тегаться доп. роль.", color=discord.Color.orange())
    else:
        list_roles2[ctx.guild.id] = роль.id
        save_data()
        embed = discord.Embed(
            title="✅ Доп. роль list настроена",
            description=f"В `!list` дополнительно будет тегаться {роль.mention}",
            color=discord.Color.green(),
        )
    embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
    await ctx.send(embed=embed, delete_after=10)
    await ctx.message.delete()


@bot.command(name="роль_взп3")
async def set_vzp_role3(ctx, роль: discord.Role = None):
    """!роль_взп3 [@роль] — третья роль для тега в !vzp; без роли — сбросить настройку"""
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    if роль is None:
        vzp_roles3.pop(ctx.guild.id, None)
        save_data()
        embed = discord.Embed(title="✅ Третья роль ВЗП сброшена", description="В `!vzp` больше не будет тегаться третья роль.", color=discord.Color.orange())
    else:
        vzp_roles3[ctx.guild.id] = роль.id
        save_data()
        embed = discord.Embed(
            title="✅ Третья роль ВЗП настроена",
            description=f"В `!vzp` дополнительно будет тегаться {роль.mention}",
            color=discord.Color.green(),
        )
    embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
    await ctx.send(embed=embed, delete_after=10)
    await ctx.message.delete()


@bot.command(name="роль_взх3")
async def set_vzh_role3(ctx, роль: discord.Role = None):
    """!роль_взх3 [@роль] — третья роль для тега в !vzh; без роли — сбросить настройку"""
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    if роль is None:
        vzh_roles3.pop(ctx.guild.id, None)
        save_data()
        embed = discord.Embed(title="✅ Третья роль ВЗХ сброшена", description="В `!vzh` больше не будет тегаться третья роль.", color=discord.Color.orange())
    else:
        vzh_roles3[ctx.guild.id] = роль.id
        save_data()
        embed = discord.Embed(
            title="✅ Третья роль ВЗХ настроена",
            description=f"В `!vzh` дополнительно будет тегаться {роль.mention}",
            color=discord.Color.green(),
        )
    embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
    await ctx.send(embed=embed, delete_after=10)
    await ctx.message.delete()


@bot.command(name="роль_реаки3")
async def set_event_role3(ctx, роль: discord.Role = None):
    """!роль_реаки3 [@роль] — третья роль для тега в !list; без роли — сбросить настройку"""
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    if роль is None:
        list_roles3.pop(ctx.guild.id, None)
        save_data()
        embed = discord.Embed(title="✅ Третья роль list сброшена", description="В `!list` больше не будет тегаться третья роль.", color=discord.Color.orange())
    else:
        list_roles3[ctx.guild.id] = роль.id
        save_data()
        embed = discord.Embed(
            title="✅ Третья роль list настроена",
            description=f"В `!list` дополнительно будет тегаться {роль.mention}",
            color=discord.Color.green(),
        )
    embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
    await ctx.send(embed=embed, delete_after=10)
    await ctx.message.delete()


@tree.command(name="доступ_сбора", description="Добавить роль с доступом к команде сбора")
@app_commands.describe(
    тип="Тип сбора: взп, мп или реаки",
    роль="Роль, которая получит доступ к команде"
)
@app_commands.choices(тип=[
    app_commands.Choice(name="vzp", value="vzp"),
    app_commands.Choice(name="reaki", value="list"),
    app_commands.Choice(name="vzh", value="vzh"),
])
async def slash_event_access_add(interaction: discord.Interaction, тип: str, роль: discord.Role):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав!", ephemeral=True)
    gid = interaction.guild_id
    if gid not in event_command_roles:
        event_command_roles[gid] = {}
    if тип not in event_command_roles[gid]:
        event_command_roles[gid][тип] = []
    if роль.id not in event_command_roles[gid][тип]:
        event_command_roles[gid][тип].append(роль.id)
    save_data()
    roles_list = ", ".join(f"<@&{rid}>" for rid in event_command_roles[gid][тип])
    await interaction.response.send_message(
        f"✅ {роль.mention} теперь может использовать `!{тип}`\nВсе роли с доступом: {roles_list}",
        ephemeral=True,
    )


@tree.command(name="убрать_доступ_сбора", description="Убрать роль из доступа к команде сбора")
@app_commands.describe(
    тип="Тип сбора: взп, мп или реаки",
    роль="Роль, которую убрать"
)
@app_commands.choices(тип=[
    app_commands.Choice(name="vzp", value="vzp"),
    app_commands.Choice(name="reaki", value="list"),
    app_commands.Choice(name="vzh", value="vzh"),
])
async def slash_event_access_remove(interaction: discord.Interaction, тип: str, роль: discord.Role):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав!", ephemeral=True)
    gid = interaction.guild_id
    allowed = event_command_roles.get(gid, {}).get(тип, [])
    if роль.id not in allowed:
        return await interaction.response.send_message(f"❌ {роль.mention} и так не в списке для `!{тип}`.", ephemeral=True)
    allowed.remove(роль.id)
    save_data()
    await interaction.response.send_message(f"✅ {роль.mention} убрана из доступа к `!{тип}`.", ephemeral=True)


@bot.command(name="list")
async def реаки_cmd(ctx, количество: int = 10, *, название: str = "Реакции"):
    """!list [количество] [название] — сбор на мероприятие (от лица бота)"""
    if not can_run_event(ctx, "list"):
        return await ctx.message.delete()

    image_file, image_ref = await _extract_event_image(ctx)

    try:
        await ctx.message.delete()
    except Exception:
        pass

    content = _event_mentions(ctx.guild, [
        event_roles.get(ctx.guild.id),
        list_roles2.get(ctx.guild.id),
        list_roles3.get(ctx.guild.id),
    ])

    event_time, название = _extract_event_time(название, "Реакции")

    await _create_event_message(ctx.channel, ctx.guild, название, количество, image_file, image_ref, content=content, event_time=event_time, cmd="list")


@bot.command(name="spisok")
async def spisok_cmd(ctx):
    """!spisok — ответом (reply) на своё сообщение собирает список тех, кто поставил реакцию"""
    if not can_run_event(ctx, "list"):
        return await ctx.message.delete()

    ref = ctx.message.reference
    if not ref or not ref.message_id:
        return await ctx.send("❌ Используй эту команду **ответом** (reply) на сообщение с реакциями!", delete_after=8)

    try:
        target = ref.cached_message or await ctx.channel.fetch_message(ref.message_id)
    except Exception:
        return await ctx.send("❌ Не удалось найти исходное сообщение.", delete_after=8)

    try:
        await ctx.message.delete()
    except Exception:
        pass

    users = set()
    for reaction in target.reactions:
        async for user in reaction.users():
            if not user.bot:
                users.add(user.id)

    if not users:
        return await ctx.send("❌ На это сообщение ещё никто не отреагировал.", delete_after=8)

    sorted_ids = sorted(users)
    lines = [f"`{str(i).zfill(2)}.` <@{uid}>" for i, uid in enumerate(sorted_ids, 1)]
    text = "📋 **Список отреагировавших**\n" + "\n".join(lines) + f"\n\n**Всего: {len(sorted_ids)}**"
    await ctx.send(text)


# ─────────────────────────────────────────────
# СЛЭШ-КОМАНДЫ СБОРОВ (/vzp, /reaki)
# ─────────────────────────────────────────────

@tree.command(name="vzp", description="Создать сбор ВЗП (тегает роли ВЗП, МП и доп. роли)")
@app_commands.describe(
    количество="Количество слотов (по умолчанию 10)",
    название="Название сбора (по умолчанию ВЗП)",
    время="Время сбора (например 20:30)",
)
async def slash_vzp(interaction: discord.Interaction, количество: int = 10, название: str = "ВЗП", время: str = None):
    if not can_run_event_slash(interaction, "vzp"):
        return await interaction.response.send_message("❌ Недостаточно прав!", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    content = _event_mentions(interaction.guild, [
        vzp_roles.get(interaction.guild_id),
        mp_roles.get(interaction.guild_id),
        vzp_roles2.get(interaction.guild_id),
        vzp_roles3.get(interaction.guild_id),
    ])
    await _create_event_message(interaction.channel, interaction.guild, название, количество, content=content, event_time=время, cmd="vzp")
    await interaction.followup.send("✅ Сбор ВЗП создан!", ephemeral=True)


@tree.command(name="reaki", description="Создать сбор реакций (тегает роль реаки и доп. роли)")
@app_commands.describe(
    количество="Количество слотов (по умолчанию 10)",
    название="Название сбора (по умолчанию Реакции)",
    время="Время сбора (например 20:30)",
)
async def slash_reaki(interaction: discord.Interaction, количество: int = 10, название: str = "Реакции", время: str = None):
    if not can_run_event_slash(interaction, "list"):
        return await interaction.response.send_message("❌ Недостаточно прав!", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    content = _event_mentions(interaction.guild, [
        event_roles.get(interaction.guild_id),
        list_roles2.get(interaction.guild_id),
        list_roles3.get(interaction.guild_id),
    ])
    await _create_event_message(interaction.channel, interaction.guild, название, количество, content=content, event_time=время, cmd="list")
    await interaction.followup.send("✅ Сбор реакций создан!", ephemeral=True)


def can_run_event_slash(interaction: discord.Interaction, event_type: str) -> bool:
    """Проверка доступа к слэш-командам сборов."""
    if is_admin(interaction):
        return True
    allowed = event_command_roles.get(interaction.guild_id, {}).get(event_type, [])
    member = interaction.user
    if not isinstance(member, discord.Member):
        return False
    return any(r.id in allowed for r in member.roles)


@bot.command(name="замена")
async def замена_cmd(ctx, кого: int, на_кого: int = 0):
    """!замена <айди_кого> <айди_на_кого> — заменить участника в слоте (0 = убрать). Используется в треде сбора."""
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()

    # Найти сбор по thread_id
    thread_id = ctx.channel.id
    msg_id = None
    for mid, data in event_lists.items():
        if data.get("thread_id") == thread_id:
            msg_id = mid
            break

    if msg_id is None:
        return await ctx.send("❌ Эта команда используется только в треде сбора!", delete_after=6)

    data  = event_lists[msg_id]
    slots = data["slots"]

    # Найти слот кого
    target_slot = None
    for slot_num, uid in slots.items():
        if uid == кого:
            target_slot = slot_num
            break

    if target_slot is None:
        return await ctx.send(f"❌ Пользователь `{кого}` не найден ни в одном слоте!", delete_after=6)

    # Если на_кого уже занимает другой слот — освободить его
    if на_кого:
        for slot_num, uid in slots.items():
            if uid == на_кого:
                slots[slot_num] = None
                break

    slots[target_slot] = на_кого if на_кого else None

    # Обновить эмбед
    try:
        channel = bot.get_channel(data["channel_id"])
        msg = await channel.fetch_message(msg_id)
        embed = build_event_embed(
            ctx.guild.id, data["title"], data["max"], slots,
            data.get("image_url"), data.get("note"),
            event_time=data.get("event_time"), closed=data.get("closed", False),
            reserve=data.get("reserve", []),
            join_mode=data.get("cmd") in ("list", "vzh"),
        )
        view = event_view(msg_id)
        await msg.edit(embed=embed, view=view)
    except Exception:
        pass

    await update_thread_list(msg_id)

    if на_кого:
        await ctx.send(f"✅ Слот **{target_slot}**: <@{кого}> → <@{на_кого}>", delete_after=10)
    else:
        await ctx.send(f"✅ Слот **{target_slot}**: <@{кого}> убран", delete_after=10)
    await ctx.message.delete()
