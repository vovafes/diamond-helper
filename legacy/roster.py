"""roster -- split out of main.py."""

import discord
from datetime import datetime
from discord import app_commands
from discord import ui
from legacy.app import (
    tree,
)
from legacy.helpers import (
    _footer,
    is_admin,
)
from legacy.state import (
    roster_settings,
    save_data,
)



# ═══════════════════════════════════════════════════════════════
# 📋 СИСТЕМА СОСТАВА СЕМЬИ (основной + академия)
# ═══════════════════════════════════════════════════════════════

def _chunk_lines(lines: list, chunk_size: int = 15) -> list[list]:
    if not lines:
        return [[]]
    return [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]


async def _collect_roster_members(guild: discord.Guild):
    """Собирает участников по ролям основного состава и академии."""
    cfg = roster_settings.get(guild.id, {})
    member_role_id = cfg.get("member_role_id")
    academy_role_id = cfg.get("academy_role_id")

    members_list = guild.members
    if len(members_list) < 2:
        try:
            members_list = [m async for m in guild.fetch_members(limit=None)]
        except Exception:
            members_list = guild.members

    main_members = []
    academy_members = []

    for member in members_list:
        if member.bot:
            continue
        role_ids = {r.id for r in member.roles}
        has_member = member_role_id and (member_role_id in role_ids)
        has_academy = academy_role_id and (academy_role_id in role_ids)
        if has_member:
            main_members.append(member)
        elif has_academy:
            academy_members.append(member)

    # Стабильный порядок: по display_name
    main_members.sort(key=lambda m: m.display_name.lower())
    academy_members.sort(key=lambda m: m.display_name.lower())
    return main_members, academy_members


def _roster_lines(members: list) -> list[str]:
    return [f"`{str(i).zfill(2)}.` {m.mention}" for i, m in enumerate(members, 1)]


def build_roster_embed(
    guild: discord.Guild,
    main_members: list,
    academy_members: list,
    page: str = "main",
    page_idx: int = 0,
) -> discord.Embed:
    """Красивый embed состава: страница main или academy."""
    main_lines = _roster_lines(main_members)
    acad_lines = _roster_lines(academy_members)
    main_pages = _chunk_lines(main_lines, 20)
    acad_pages = _chunk_lines(acad_lines, 20)

    if page == "academy":
        pages = acad_pages
        page_idx = max(0, min(page_idx, len(pages) - 1))
        body = "\n".join(pages[page_idx]) if pages[page_idx] else "*Пока никого*"
        embed = discord.Embed(
            title=f"🎓 Академия — {len(academy_members)}",
            description=body,
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
    else:
        pages = main_pages
        page_idx = max(0, min(page_idx, len(pages) - 1))
        body = "\n".join(pages[page_idx]) if pages[page_idx] else "*Пока никого*"
        embed = discord.Embed(
            title=f"🏅 Основной состав — {len(main_members)}",
            description=body,
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )

    total = len(main_members) + len(academy_members)
    embed.add_field(name="🏅 Основной", value=str(len(main_members)), inline=True)
    embed.add_field(name="🎓 Академия", value=str(len(academy_members)), inline=True)
    embed.add_field(name="📊 Всего", value=str(total), inline=True)
    if len(pages) > 1:
        embed.set_footer(
            text=f"DIAMOND • стр. {page_idx + 1}/{len(pages)} • Всего: {total}",
            icon_url=_footer(guild.id),
        )
    else:
        embed.set_footer(text=f"DIAMOND • Всего: {total}", icon_url=_footer(guild.id))
    return embed


class RosterView(ui.View):
    """Переключатель Основной / Академия + пагинация."""

    def __init__(
        self,
        guild: discord.Guild,
        main_members: list,
        academy_members: list,
        page: str = "main",
        page_idx: int = 0,
    ):
        super().__init__(timeout=180)
        self.guild = guild
        self.main_members = main_members
        self.academy_members = academy_members
        self.page = page
        self.page_idx = page_idx
        self._sync_buttons()

    def _page_count(self) -> int:
        lines = _roster_lines(
            self.main_members if self.page == "main" else self.academy_members
        )
        return max(1, len(_chunk_lines(lines, 20)))

    def _sync_buttons(self):
        for item in list(self.children):
            self.remove_item(item)

        main_btn = ui.Button(
            label=f"🏅 Основной ({len(self.main_members)})",
            style=discord.ButtonStyle.primary if self.page == "main" else discord.ButtonStyle.secondary,
            row=0,
        )
        acad_btn = ui.Button(
            label=f"🎓 Академия ({len(self.academy_members)})",
            style=discord.ButtonStyle.primary if self.page == "academy" else discord.ButtonStyle.secondary,
            row=0,
        )
        prev_btn = ui.Button(
            label="◀",
            style=discord.ButtonStyle.secondary,
            disabled=self.page_idx <= 0,
            row=1,
        )
        next_btn = ui.Button(
            label="▶",
            style=discord.ButtonStyle.secondary,
            disabled=self.page_idx >= self._page_count() - 1,
            row=1,
        )
        refresh_btn = ui.Button(label="🔄", style=discord.ButtonStyle.secondary, row=1)

        async def go_main(interaction: discord.Interaction):
            self.page = "main"
            self.page_idx = 0
            self._sync_buttons()
            await interaction.response.edit_message(embed=self.embed(), view=self)

        async def go_acad(interaction: discord.Interaction):
            self.page = "academy"
            self.page_idx = 0
            self._sync_buttons()
            await interaction.response.edit_message(embed=self.embed(), view=self)

        async def go_prev(interaction: discord.Interaction):
            self.page_idx = max(0, self.page_idx - 1)
            self._sync_buttons()
            await interaction.response.edit_message(embed=self.embed(), view=self)

        async def go_next(interaction: discord.Interaction):
            self.page_idx = min(self._page_count() - 1, self.page_idx + 1)
            self._sync_buttons()
            await interaction.response.edit_message(embed=self.embed(), view=self)

        async def do_refresh(interaction: discord.Interaction):
            self.main_members, self.academy_members = await _collect_roster_members(interaction.guild)
            self.page_idx = min(self.page_idx, self._page_count() - 1)
            self._sync_buttons()
            await interaction.response.edit_message(embed=self.embed(), view=self)

        main_btn.callback = go_main
        acad_btn.callback = go_acad
        prev_btn.callback = go_prev
        next_btn.callback = go_next
        refresh_btn.callback = do_refresh
        self.add_item(main_btn)
        self.add_item(acad_btn)
        self.add_item(prev_btn)
        self.add_item(next_btn)
        self.add_item(refresh_btn)

    def embed(self) -> discord.Embed:
        return build_roster_embed(
            self.guild, self.main_members, self.academy_members, self.page, self.page_idx
        )


async def _refresh_roster(guild: discord.Guild):
    """Обновляет закреплённую панель состава в настроенном канале."""
    cfg = roster_settings.get(guild.id, {})
    ch_id = cfg.get("channel_id")
    if not ch_id:
        return
    try:
        ch = guild.get_channel(ch_id)
        if not ch:
            return
        old_id = cfg.get("message_id")
        if old_id:
            try:
                await (await ch.fetch_message(old_id)).delete()
            except Exception:
                pass
        main_m, acad_m = await _collect_roster_members(guild)
        view = RosterView(guild, main_m, acad_m)
        msg = await ch.send(embed=view.embed(), view=view)
        cfg["message_id"] = msg.id
        save_data()
    except Exception:
        pass


@tree.command(name="состав_настройка", description="Настроить роли и канал панели состава")
@app_commands.describe(
    роль_участника="Роль основного состава",
    роль_академии="Роль академии",
    канал="Канал для живой панели (необязательно — только /состав)",
)
@app_commands.default_permissions(administrator=True)
async def slash_roster_setup(
    interaction: discord.Interaction,
    роль_участника: discord.Role,
    роль_академии: discord.Role,
    канал: discord.TextChannel = None,
):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав!", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    gid = interaction.guild_id
    cfg = roster_settings.setdefault(gid, {})
    cfg["member_role_id"] = роль_участника.id
    cfg["academy_role_id"] = роль_академии.id
    if канал:
        cfg["channel_id"] = канал.id
        await _refresh_roster(interaction.guild)
        await interaction.followup.send(
            f"✅ Состав настроен.\n"
            f"🏅 Основной: {роль_участника.mention}\n"
            f"🎓 Академия: {роль_академии.mention}\n"
            f"📢 Панель: {канал.mention}",
            ephemeral=True,
        )
    else:
        save_data()
        await interaction.followup.send(
            f"✅ Роли состава сохранены.\n"
            f"🏅 Основной: {роль_участника.mention}\n"
            f"🎓 Академия: {роль_академии.mention}\n"
            f"Панель канала не задана — используй `/состав` или укажи канал.",
            ephemeral=True,
        )


@tree.command(name="состав_обновить", description="Обновить панель состава в настроенном канале")
@app_commands.default_permissions(administrator=True)
async def slash_roster_refresh(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав!", ephemeral=True)
    cfg = roster_settings.get(interaction.guild_id, {})
    if not cfg.get("channel_id"):
        return await interaction.response.send_message(
            "❌ Канал панели не задан. Используй `/состав_настройка` с параметром канал.",
            ephemeral=True,
        )
    await interaction.response.defer(ephemeral=True)
    await _refresh_roster(interaction.guild)
    await interaction.followup.send("✅ Панель состава обновлена.", ephemeral=True)


@tree.command(name="состав", description="Показать состав семьи (основной + академия)")
async def slash_roster(interaction: discord.Interaction):
    cfg = roster_settings.get(interaction.guild_id, {})
    if not cfg.get("member_role_id") and not cfg.get("academy_role_id"):
        return await interaction.response.send_message(
            "❌ Состав ещё не настроен. Админ: `/состав_настройка`.",
            ephemeral=True,
        )
    await interaction.response.defer()
    main_m, acad_m = await _collect_roster_members(interaction.guild)
    view = RosterView(interaction.guild, main_m, acad_m)
    await interaction.followup.send(embed=view.embed(), view=view)
