"""roulette -- split out of main.py."""

import asyncio
import discord
import json
import os
import random
from datetime import datetime
from legacy.app import (
    bot,
    tree,
)
from legacy.economy import (
    balance,
)
from legacy.helpers import (
    _footer,
    add_chips,
    get_chips,
)
from legacy.state import (
    ROULETTE_FILE,
)



# ─────────────────────────────────────────────
# РУЛЕТКА
# ─────────────────────────────────────────────

roulette_stats: dict = {}
roulette_cd: dict = {}

ROULETTE_MIN  = 10
ROULETTE_MAX  = 1000
ROULETTE_CD_S = 5

RED_NUMBERS   = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}


def _roulette_key(guild_id: int, user_id: int) -> str:
    return f"{guild_id}:{user_id}"


def save_roulette():
    try:
        data = {"stats": roulette_stats}
        with open(ROULETTE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"WARNING: Failed to save roulette: {e}")


def load_roulette():
    try:
        if not os.path.exists(ROULETTE_FILE):
            return
        with open(ROULETTE_FILE, "r", encoding="utf-8") as f:
            doc = json.load(f)
        roulette_stats.update(doc.get("stats", {}))
        print("OK: Roulette stats loaded from roulette.json")
    except Exception as e:
        print(f"WARNING: Failed to load roulette stats: {e}")


def _get_roulette_stats(guild_id: int, user_id: int) -> dict:
    key = _roulette_key(guild_id, user_id)
    if key not in roulette_stats:
        roulette_stats[key] = {"games": 0, "wins": 0, "loses": 0, "profit": 0}
    return roulette_stats[key]


def _update_roulette_stats(guild_id: int, user_id: int, won: bool, profit_delta: int):
    s = _get_roulette_stats(guild_id, user_id)
    s["games"]  += 1
    s["wins"]   += 1 if won else 0
    s["loses"]  += 0 if won else 1
    s["profit"] += profit_delta
    save_roulette()


def _spin() -> int:
    return random.randint(0, 36)


def _number_color(n: int) -> str:
    if n == 0:              return "зелёное"
    if n in RED_NUMBERS:   return "красное"
    return "чёрное"


def _color_emoji(color: str) -> str:
    return {"красное": "🔴", "чёрное": "⚫", "зелёное": "🟢"}.get(color, "⚪")


def _fmt_r(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _parse_bet(raw: str):
    low = raw.lower()
    if low in ("красное", "красный"):
        return ("color", "красное")
    if low in ("чёрное", "чёрный", "черное", "черный"):
        return ("color", "чёрное")
    try:
        n = int(raw)
        if 0 <= n <= 36:
            return ("number", n)
    except ValueError:
        pass
    return None


def _check_roulette_cd(guild_id: int, user_id: int) -> float:
    last = roulette_cd.get(guild_id, {}).get(user_id)
    if not last:
        return 0.0
    elapsed = (datetime.now() - last).total_seconds()
    return max(0.0, ROULETTE_CD_S - elapsed)


def _set_roulette_cd(guild_id: int, user_id: int):
    if guild_id not in roulette_cd:
        roulette_cd[guild_id] = {}
    roulette_cd[guild_id][user_id] = datetime.now()


@bot.command(name="рулетка")
async def roulette_cmd(ctx, bet_type: str = None, amount: str = None):
    guild_id = ctx.guild.id
    user_id  = ctx.author.id

    if not bet_type or not amount:
        embed = discord.Embed(
            title="🎰 Рулетка — Помощь",
            description=(
                "**Формат:** `!рулетка <ставка> <сумма>`\n\n"
                "**Ставки:**\n"
                "• `красное` — цвет x2\n"
                "• `чёрное` — цвет x2\n"
                "• `0-36` — число x35\n\n"
                f"**Мин. ставка:** {_fmt_r(ROULETTE_MIN)} 🎰\n"
                f"**Макс. ставка:** {_fmt_r(ROULETTE_MAX)} 🎰\n\n"
                "**Ставки в фишках** (обмен: `!обмен <сумма>`)\n\n"
                "**Примеры:**\n"
                "`!рулетка красное 100`\n"
                "`!рулетка 17 50`"
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="DIAMOND", icon_url=_footer(guild_id))
        return await ctx.send(embed=embed)

    cd_left = _check_roulette_cd(guild_id, user_id)
    if cd_left > 0:
        return await ctx.send(
            f"⏳ {ctx.author.mention}, подожди ещё **{cd_left:.1f} сек.** перед следующей ставкой.",
            delete_after=4,
        )

    parsed = _parse_bet(bet_type)
    if not parsed:
        return await ctx.send("❌ Неверный тип ставки. Укажи: `красное`, `чёрное` или число `0-36`.", delete_after=6)

    try:
        stake = int(amount.replace(" ", "").replace("_", ""))
    except ValueError:
        return await ctx.send("❌ Сумма должна быть целым числом.", delete_after=6)

    if stake < ROULETTE_MIN:
        return await ctx.send(f"❌ Минимальная ставка — **{_fmt_r(ROULETTE_MIN)}** 🎰", delete_after=6)
    if stake > ROULETTE_MAX:
        return await ctx.send(f"❌ Максимальная ставка — **{_fmt_r(ROULETTE_MAX)}** 🎰", delete_after=6)

    balance = get_chips(guild_id, user_id)
    if balance < stake:
        return await ctx.send(
            f"❌ Недостаточно фишек! Нужно **{_fmt_r(stake)}** 🎰, у вас **{_fmt_r(balance)}** 🎰\n"
            f"Обменяй алмазы на фишки: `!обмен <сумма>`",
            delete_after=8,
        )

    _set_roulette_cd(guild_id, user_id)

    anim_embed = discord.Embed(title="🎰 Крутим рулетку...", description="Подождите...", color=0xf1c40f)
    anim_embed.set_footer(text="DIAMOND", icon_url=_footer(guild_id))
    msg = await ctx.send(embed=anim_embed)

    for _ in range(3):
        fake_n = random.randint(0, 36)
        anim_embed.description = f"{_color_emoji(_number_color(fake_n))} **{fake_n}**..."
        await msg.edit(embed=anim_embed)
        await asyncio.sleep(0.8)

    result_n     = _spin()
    result_color = _number_color(result_n)
    color_emoji  = _color_emoji(result_color)

    bet_kind, bet_val = parsed
    if bet_kind == "color":
        won = (result_color == bet_val)
        bet_label = f"{_color_emoji(bet_val)} {bet_val}"
        payout    = stake * 2 if won else 0
    else:
        won = (result_n == bet_val)
        bet_label = f"🎯 число {bet_val}"
        payout    = stake * 35 if won else 0

    profit_delta = payout - stake
    add_chips(guild_id, user_id, profit_delta)
    _update_roulette_stats(guild_id, user_id, won, profit_delta)
    new_balance = get_chips(guild_id, user_id)

    result_color_embed = discord.Color.green() if won else discord.Color.red()
    result_title       = "🎉 ПОБЕДА!" if won else "💸 ПРОИГРЫШ"
    result_text        = f"**+{_fmt_r(payout)}** 🎰" if won else f"**-{_fmt_r(stake)}** 🎰"

    final_embed = discord.Embed(title=f"🎰 РУЛЕТКА — {result_title}", color=result_color_embed, timestamp=datetime.now())
    final_embed.add_field(name="Ставка",   value=f"**{_fmt_r(stake)}** 🎰 на {bet_label}", inline=True)
    final_embed.add_field(name="Выпало",   value=f"{color_emoji} **{result_n}** ({result_color})", inline=True)
    final_embed.add_field(name="Результат", value=result_text, inline=True)
    final_embed.add_field(name="Фишки",    value=f"**{_fmt_r(new_balance)}** 🎰", inline=False)
    final_embed.set_footer(text="DIAMOND", icon_url=_footer(guild_id))
    await msg.edit(embed=final_embed)


@tree.command(name="рулетка_топ", description="ТОП-10 игроков рулетки по профиту")
async def slash_roulette_top(interaction: discord.Interaction):
    guild_id = interaction.guild_id

    guild_entries = [
        (key, data)
        for key, data in roulette_stats.items()
        if key.startswith(f"{guild_id}:")
    ]

    if not guild_entries:
        return await interaction.response.send_message("🎰 Пока никто не играл!", ephemeral=True)

    guild_entries.sort(key=lambda x: x[1]["profit"], reverse=True)
    top10 = guild_entries[:10]

    medals = ["🥇", "🥈", "🥉"]
    lines  = []
    for i, (key, data) in enumerate(top10):
        user_id = int(key.split(":")[1])
        games   = data["games"]
        wins    = data["wins"]
        profit  = data["profit"]
        winrate = round((wins / games * 100)) if games > 0 else 0
        medal   = medals[i] if i < 3 else f"`{i+1}.`"
        profit_s = f"+{_fmt_r(profit)}" if profit >= 0 else f"-{_fmt_r(abs(profit))}"
        lines.append(
            f"{medal} <@{user_id}>\n"
            f"🎮 Игр: **{games}** • ✅ Побед: **{wins}** • 📈 WR: **{winrate}%**\n"
            f"💰 Профит: **{profit_s}** 💎\n"
        )

    embed = discord.Embed(
        title="🏆 ТОП РУЛЕТКИ",
        description="\n".join(lines),
        color=discord.Color.gold(),
        timestamp=datetime.now(),
    )
    embed.set_footer(text="DIAMOND", icon_url=_footer(guild_id))
    await interaction.response.send_message(embed=embed)


