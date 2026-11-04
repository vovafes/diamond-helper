"""warns -- split out of main.py."""

import discord
from datetime import datetime
from discord import app_commands
from discord import ui
from legacy.app import (
    bot,
    tree,
)
from legacy.helpers import (
    _footer,
    add_points,
    get_points,
    get_warns,
    is_admin_ctx,
    remove_warn,
    set_warn,
)
from legacy.state import (
    guild_shop_items,
    save_data,
    warn_roles,
    warns_db,
)



@bot.command(name="warn")
async def warn_user(ctx, пользователь: discord.Member, количество: int, *, причина: str):
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    """!warn @пользователь <1-3> причина — выдать варн"""
    if количество not in (1, 2, 3):
        return await ctx.send("❌ Укажи количество варнов: 1, 2 или 3. Пример: `!warn @user 2 причина`", delete_after=6)

    set_warn(ctx.guild.id, пользователь.id, количество, причина, ctx.author.id)

    # Убрать все старые варн-роли и назначить новую
    guild_warn_roles = warn_roles.get(ctx.guild.id, {})
    roles_to_remove = [ctx.guild.get_role(rid) for rid in guild_warn_roles.values() if ctx.guild.get_role(rid)]
    new_role = ctx.guild.get_role(guild_warn_roles.get(количество))
    try:
        await пользователь.remove_roles(*[r for r in roles_to_remove if r], reason="Обновление варн-роли")
        if new_role:
            await пользователь.add_roles(new_role, reason=f"Warn {количество}/3")
    except Exception:
        pass

    embed = discord.Embed(
        title="⚠️ WARN",
        description=f"{пользователь.mention} получил warn!",
        color=discord.Color.red(),
        timestamp=datetime.now(),
    )
    embed.add_field(name="Причина", value=причина, inline=False)
    embed.add_field(name="Модератор", value=ctx.author.mention, inline=True)
    embed.add_field(name="Варны", value=f"**{количество}/3**", inline=True)
    if new_role:
        embed.add_field(name="Роль", value=new_role.mention, inline=True)
    embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
    await ctx.send(embed=embed)

    try:
        dm_embed = discord.Embed(
            title="⚠️ Вы получили warn",
            description=f"**Причина:** {причина}\n**Варны:** {количество}/3",
            color=discord.Color.red(),
            timestamp=datetime.now(),
        )
        dm_embed.add_field(name="Модератор", value=ctx.author.mention)
        dm_embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
        await пользователь.send(embed=dm_embed)
    except Exception:
        pass

    try:
        await ctx.message.delete()
    except Exception:
        pass


@bot.command(name="unwarn")
async def admin_remove_warn(ctx, пользователь: discord.Member):
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    """!снять_варн @пользователь — снять варн"""
    if remove_warn(ctx.guild.id, пользователь.id):
        # Убрать все варн-роли
        guild_warn_roles = warn_roles.get(ctx.guild.id, {})
        roles_to_remove = [ctx.guild.get_role(rid) for rid in guild_warn_roles.values() if ctx.guild.get_role(rid)]
        try:
            await пользователь.remove_roles(*[r for r in roles_to_remove if r], reason="Снятие варна")
        except Exception:
            pass
        embed = discord.Embed(
            title="✅ Warn снят",
            description=f"У {пользователь.mention} снят warn",
            color=discord.Color.green(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ У пользователя нет warn'ов!", delete_after=5)

    try:
        await ctx.message.delete()
    except Exception:
        pass


@bot.command(name="clear", aliases=["очистить", "purge"])
async def clear_messages_cmd(ctx, количество: int, пользователь: discord.Member = None):
    """!clear <количество> [@пользователь] — удалить последние N сообщений в канале (опционально только от пользователя)"""
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    if количество < 1 or количество > 100:
        return await ctx.send("❌ Укажи число от 1 до 100.", delete_after=6)

    try:
        await ctx.message.delete()
    except Exception:
        pass

    def _check(m):
        return пользователь is None or m.author.id == пользователь.id

    deleted = await ctx.channel.purge(limit=количество, check=_check)
    notice = await ctx.send(f"🧹 Удалено сообщений: **{len(deleted)}**")
    await notice.delete(delay=5)


@bot.command(name="роль_варн")
async def set_warn_role(ctx, номер: int, роль: discord.Role):
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    """!роль_варн <1-3> @роль — привязать роль к уровню варна"""
    if номер not in (1, 2, 3):
        return await ctx.send("❌ Укажи номер 1, 2 или 3. Пример: `!роль_варн 1 @Варн1/3`", delete_after=6)
    if ctx.guild.id not in warn_roles:
        warn_roles[ctx.guild.id] = {}
    warn_roles[ctx.guild.id][номер] = роль.id
    save_data()
    embed = discord.Embed(
        title="✅ Варн-роль настроена",
        description=f"Варн **{номер}/3** → {роль.mention}",
        color=discord.Color.green(),
    )
    embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
    await ctx.send(embed=embed)
    await ctx.message.delete()


@bot.command(name="warnlist")
async def warnlist(ctx):
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    """!warnlist — список всех участников с варнами"""
    await ctx.send(embed=_build_warnlist_embed(ctx.guild))
    await ctx.message.delete()


# ─────────────────────────────────────────────
# HELP — список всех команд (авто-собирается из зарегистрированных команд)
# ─────────────────────────────────────────────

HELP_PER_PAGE = 12


def _all_help_entries() -> list[tuple[str, str]]:
    entries = []
    for cmd in sorted(bot.commands, key=lambda c: c.name):
        if cmd.hidden or cmd.name in ("help",):
            continue
        sig  = f"!{cmd.name} {cmd.signature}".strip()
        desc = (cmd.help or "").strip() or "—"
        entries.append((sig, desc))
    for cmd in sorted(tree.get_commands(), key=lambda c: c.name):
        if not isinstance(cmd, app_commands.Command):
            continue
        entries.append((f"/{cmd.name}", cmd.description or "—"))
    return entries


def _build_help_embed(entries: list[tuple[str, str]], page: int, total_pages: int) -> discord.Embed:
    embed = discord.Embed(
        title="📖 Команды бота",
        color=0x2b2d31,
    )
    start = (page - 1) * HELP_PER_PAGE
    for sig, desc in entries[start:start + HELP_PER_PAGE]:
        embed.add_field(name=sig, value=desc, inline=False)
    embed.set_footer(text=f"DIAMOND • Страница {page}/{total_pages} • Всего команд: {len(entries)}")
    return embed


class HelpPaginationView(ui.View):
    def __init__(self, entries: list[tuple[str, str]], page: int = 1):
        super().__init__(timeout=180)
        self._entries = entries
        self._page    = page
        total_pages   = max(1, -(-len(entries) // HELP_PER_PAGE))

        prev_btn = ui.Button(label="◀", style=discord.ButtonStyle.secondary, disabled=(page <= 1))
        async def _prev(inter):
            await inter.response.edit_message(
                embed=_build_help_embed(self._entries, self._page - 1, total_pages),
                view=HelpPaginationView(self._entries, self._page - 1),
            )
        prev_btn.callback = _prev
        self.add_item(prev_btn)

        next_btn = ui.Button(label="▶", style=discord.ButtonStyle.secondary, disabled=(page >= total_pages))
        async def _next(inter):
            await inter.response.edit_message(
                embed=_build_help_embed(self._entries, self._page + 1, total_pages),
                view=HelpPaginationView(self._entries, self._page + 1),
            )
        next_btn.callback = _next
        self.add_item(next_btn)


@bot.command(name="help")
async def help_cmd(ctx):
    """!help — список всех команд бота (префикс и слэш)"""
    entries     = _all_help_entries()
    total_pages = max(1, -(-len(entries) // HELP_PER_PAGE))
    await ctx.send(embed=_build_help_embed(entries, 1, total_pages), view=HelpPaginationView(entries, 1))


@tree.command(name="help", description="Список всех команд бота")
async def slash_help(interaction: discord.Interaction):
    entries     = _all_help_entries()
    total_pages = max(1, -(-len(entries) // HELP_PER_PAGE))
    await interaction.response.send_message(
        embed=_build_help_embed(entries, 1, total_pages), view=HelpPaginationView(entries, 1), ephemeral=True,
    )


def _build_warnlist_embed(guild: discord.Guild) -> discord.Embed:
    """Общий билдер эмбеда со списком всех варнов — используется в !warnlist и в кабинете рекрута."""
    guild_warns = warns_db.get(guild.id, {})
    active = {uid: d for uid, d in guild_warns.items() if d.get("warns", 0) > 0}

    embed = discord.Embed(
        title="⚠️ Список участников с варнами",
        color=discord.Color.red(),
        timestamp=datetime.now(),
    )
    embed.set_footer(text=f"DIAMOND • Всего: {len(active)}", icon_url=_footer(guild.id))

    if not active:
        embed.description = "✅ Ни у кого нет варнов!"
        return embed

    lines = []
    for i, (uid, d) in enumerate(active.items(), 1):
        lines.append(
            f"**{i}.** <@{uid}> — **{d['warns']}/3** варн(а)\n"
            f"└ Причина: {d['reason']} | Модератор: <@{d['moderator']}>"
        )
    embed.description = "\n\n".join(lines)
    return embed


def _find_remove_warn_shop_item(guild_id: int):
    """Первый настроенный товар магазина с действием remove_warn (для самоснятия варна за баллы)."""
    for item_id, item in guild_shop_items.get(guild_id, {}).items():
        if item.get("action") == "remove_warn":
            return item_id, item
    return None, None


class SelfRemoveWarnView(ui.View):
    """Кнопка самостоятельного снятия варна за баллы (цена берётся из товара магазина remove_warn)."""
    def __init__(self, author_id: int, price: int):
        super().__init__(timeout=60)
        self._author_id = author_id
        self.children[0].label = f"🗑 Снять варн за {price} 💎"

    @ui.button(label="🗑 Снять варн", style=discord.ButtonStyle.danger)
    async def remove(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self._author_id:
            return await interaction.response.send_message("❌ Эта кнопка не для тебя.", ephemeral=True)
        guild_id = interaction.guild_id
        user_id  = interaction.user.id

        item_id, item = _find_remove_warn_shop_item(guild_id)
        warn_data = get_warns(guild_id, user_id)
        if not item or not warn_data:
            button.disabled = True
            await interaction.response.edit_message(view=self)
            return await interaction.followup.send("❌ Снятие варна сейчас недоступно.", ephemeral=True)

        price  = item["price"]
        points = get_points(guild_id, user_id)
        if points < price:
            return await interaction.response.send_message(
                f"❌ Недостаточно баллов! Нужно **{price}** 💎, у тебя **{points}** 💎", ephemeral=True,
            )

        guild_warn_roles = warn_roles.get(guild_id, {})
        old_count = warn_data["warns"]
        new_count = old_count - 1
        roles_to_remove = [interaction.guild.get_role(rid) for rid in guild_warn_roles.values()]
        try:
            await interaction.user.remove_roles(*[r for r in roles_to_remove if r], reason="Самоснятие варна")
        except Exception:
            pass
        if new_count <= 0:
            remove_warn(guild_id, user_id)
            desc = f"Твой последний варн снят!\nСписано **{price}** 💎"
        else:
            set_warn(guild_id, user_id, new_count, warn_data.get("reason", ""), warn_data.get("moderator", 0))
            new_role = interaction.guild.get_role(guild_warn_roles.get(new_count))
            if new_role:
                try:
                    await interaction.user.add_roles(new_role, reason=f"Самоснятие варна ({new_count}/3)")
                except Exception:
                    pass
            desc = f"Варн снят! Теперь у тебя **{new_count}/3**\nСписано **{price}** 💎"
        add_points(guild_id, user_id, -price)

        button.disabled = True
        await interaction.response.edit_message(view=self)
        embed = discord.Embed(title="✅ Варн снят!", description=desc, color=discord.Color.green(), timestamp=datetime.now())
        embed.set_footer(text="DIAMOND", icon_url=_footer(guild_id))
        await interaction.followup.send(embed=embed, ephemeral=True)
