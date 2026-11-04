"""economy -- split out of main.py."""

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
    add_chips,
    add_points,
    build_points_embed,
    declension,
    get_chips,
    get_points,
    is_admin_ctx,
    set_points,
)
from legacy.state import (
    message_counts,
    points_db,
    save_points,
    voice_join_times,
    voice_minutes,
)



# ─────────────────────────────────────────────
# 💰 БАЛЛЫ, WARN, МАГАЗИН — PREFIX-КОМАНДЫ
# ─────────────────────────────────────────────
@bot.command(name="баланс")
async def balance(ctx, пользователь: discord.Member = None):
    """!баланс [@пользователь] — показать баланс"""
    target = пользователь or ctx.author
    embed  = build_points_embed(ctx.guild.id, target.id)
    embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="обмен")
async def exchange_cmd(ctx, количество: int = None):
    """!обмен <количество> — обменять алмазы на фишки 1:1"""
    gid = ctx.guild.id
    if not количество or количество < 1:
        embed = discord.Embed(
            title="💱 Обмен алмазов на фишки",
            description=(
                "**Формат:** `!обмен <количество>`\n\n"
                "💎 Алмазы → 🎰 Фишки по курсу **1:1**\n"
                "Фишки используются только в рулетке.\n\n"
                "**Пример:** `!обмен 500`"
            ),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="DIAMOND", icon_url=_footer(gid))
        return await ctx.send(embed=embed)

    uid      = ctx.author.id
    diamonds = get_points(gid, uid)

    if diamonds < количество:
        return await ctx.send(
            f"❌ Недостаточно алмазов! Нужно **{количество:,}** 💎, у вас **{diamonds:,}** 💎".replace(",", " "),
            delete_after=8,
        )

    add_points(gid, uid, -количество)
    add_chips(gid, uid, количество)

    embed = discord.Embed(
        title="💱 Обмен выполнен!",
        description=(
            f"**{количество:,}** 💎 → **{количество:,}** 🎰\n\n"
            f"Алмазы: **{get_points(gid, uid):,}** 💎\n"
            f"Фишки: **{get_chips(gid, uid):,}** 🎰"
        ).replace(",", " "),
        color=discord.Color.green(),
        timestamp=datetime.now(),
    )
    embed.set_footer(text="DIAMOND", icon_url=_footer(gid))
    await ctx.send(embed=embed)


@bot.command(name="дать")
async def give_points_cmd(ctx, пользователь: discord.Member, количество: int):
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    """!дать @пользователь количество — выдать баллы"""
    if количество < 1:
        return await ctx.send("❌ Количество должно быть больше 0!", delete_after=5)
    add_points(ctx.guild.id, пользователь.id, количество)
    new_balance = get_points(ctx.guild.id, пользователь.id)
    embed = discord.Embed(
        title="💰 Баллы начислены!",
        description=f"{пользователь.mention} получил **{количество}** 💎\nНовый баланс: **{new_balance}** 💎",
        color=discord.Color.green(),
        timestamp=datetime.now(),
    )
    embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
    await ctx.send(embed=embed)


@bot.command(name="снять")
async def remove_points_cmd(ctx, пользователь: discord.Member, количество: int):
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    """!снять @пользователь количество — снять баллы"""
    if количество < 1:
        return await ctx.send("❌ Количество должно быть больше 0!", delete_after=5)
    current     = get_points(ctx.guild.id, пользователь.id)
    new_balance = max(0, current - количество)
    set_points(ctx.guild.id, пользователь.id, new_balance)
    embed = discord.Embed(
        title="💰 Баллы сняты!",
        description=f"У {пользователь.mention} снято **{количество}** 💎\nНовый баланс: **{new_balance}** 💎",
        color=discord.Color.orange(),
        timestamp=datetime.now(),
    )
    embed.set_footer(text="DIAMOND", icon_url=_footer(ctx.guild.id))
    await ctx.send(embed=embed)


class ResetPointsConfirmView(ui.View):
    def __init__(self, guild_id: int, author_id: int):
        super().__init__(timeout=30)
        self._guild_id  = guild_id
        self._author_id = author_id

    @ui.button(label="Да, обнулить всем", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self._author_id:
            return await interaction.response.send_message("❌ Эта кнопка не для тебя.", ephemeral=True)
        count = len(points_db.get(self._guild_id, {}))
        points_db[self._guild_id] = {}
        save_points()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"✅ Баллы обнулены у **{count}** {declension(count)}.",
            embed=None, view=self,
        )

    @ui.button(label="Отмена", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self._author_id:
            return await interaction.response.send_message("❌ Эта кнопка не для тебя.", ephemeral=True)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ Отменено.", embed=None, view=self)


@bot.command(name="обнулить_баллы")
async def reset_all_points_cmd(ctx):
    """!обнулить_баллы — сбросить баллы (алмазы) у всех на этом сервере в 0 (требует подтверждения)"""
    if not is_admin_ctx(ctx):
        return await ctx.message.delete()
    count = len(points_db.get(ctx.guild.id, {}))
    await ctx.send(
        f"⚠️ Точно обнулить баллы **{count}** {declension(count)}? Это действие необратимо.",
        view=ResetPointsConfirmView(ctx.guild.id, ctx.author.id),
    )


# ─────────────────────────────────────────────
# ТАБЛИЦА ЛИДЕРОВ
# ─────────────────────────────────────────────

@tree.command(name="топ", description="Таблица лидеров сервера")
@app_commands.describe(категория="Выбери категорию: баллы, сообщения или войс")
@app_commands.choices(категория=[
    app_commands.Choice(name="💎 Баллы",         value="points"),
    app_commands.Choice(name="💬 Сообщения",      value="messages"),
    app_commands.Choice(name="🎙 Минуты в войсе", value="voice"),
])
async def slash_top(interaction: discord.Interaction, категория: str = "points"):
    gid = interaction.guild_id

    if категория == "points":
        raw   = points_db.get(gid, {})
        title = "💎 Топ по баллам"
        label = "💎"
    elif категория == "messages":
        raw   = message_counts.get(gid, {})
        title = "💬 Топ по сообщениям"
        label = "сообщ."
    else:
        # Войс: сохранённые минуты + текущая сессия
        raw = dict(voice_minutes.get(gid, {}))
        for uid, join_t in voice_join_times.get(gid, {}).items():
            extra = int((datetime.now() - join_t).total_seconds() // 60)
            raw[uid] = raw.get(uid, 0) + extra
        title = "🎙 Топ по минутам в войсе"
        label = "мин."

    sorted_data = sorted(raw.items(), key=lambda x: x[1], reverse=True)[:10]

    if not sorted_data:
        return await interaction.response.send_message("📊 Данных пока нет.", ephemeral=True)

    medals = ["🥇", "🥈", "🥉"]
    lines  = []
    for i, (uid, val) in enumerate(sorted_data):
        medal = medals[i] if i < 3 else f"`{i+1}.`"
        lines.append(f"{medal} <@{uid}> — **{val:,}** {label}".replace(",", "."))

    embed = discord.Embed(
        title=title,
        description="\n".join(lines),
        color=discord.Color.gold(),
        timestamp=datetime.now(),
    )
    embed.set_footer(text="DIAMOND", icon_url=_footer(gid))
    await interaction.response.send_message(embed=embed)
