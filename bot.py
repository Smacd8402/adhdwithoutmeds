"""
bot.py
Discord bot entrypoint. Slash commands for building and viewing a story board
as a visual mind map, one board per channel.

Run:  python bot.py
Env:  DISCORD_TOKEN must be set (see .env.example)
"""

import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from storyboard import Board

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# in-memory cache of loaded boards, keyed by channel id
_boards: dict[int, Board] = {}


def get_board(channel_id: int) -> Board | None:
    if channel_id in _boards:
        return _boards[channel_id]
    loaded = Board.load(channel_id)
    if loaded:
        _boards[channel_id] = loaded
    return loaded


def get_or_error(channel_id: int) -> Board:
    board = get_board(channel_id)
    if board is None:
        raise app_commands.AppCommandError(
            "There's no story board in this channel yet. Start one with `/storyboard start`."
        )
    return board


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} — slash commands synced.")


group = app_commands.Group(name="storyboard", description="Build and view a story mind map for this channel")


@group.command(name="start", description="Start a new story board in this channel (wipes any existing one)")
@app_commands.describe(title="The title / root idea of your story")
async def start(interaction: discord.Interaction, title: str):
    board = Board(interaction.channel_id)
    root = board.start(title, interaction.user.display_name)
    board.save()
    _boards[interaction.channel_id] = board
    await interaction.response.send_message(
        f"🆕 Started **{title}** as node **#{root.id}**. Add to it with `/storyboard add parent:{root.id} text:\"...\"`."
    )


@group.command(name="add", description="Add a story beat or a side-thought under an existing node")
@app_commands.describe(parent="ID of the node to attach this under", text="What happens / what you're thinking",
                        type="beat = story event, thought = note/idea")
@app_commands.choices(type=[
    app_commands.Choice(name="beat (story event)", value="beat"),
    app_commands.Choice(name="thought (note/idea)", value="thought"),
])
async def add(interaction: discord.Interaction, parent: int, text: str,
               type: app_commands.Choice[str] = None):
    board = get_or_error(interaction.channel_id)
    node_type = type.value if type else "beat"
    try:
        node = board.add(parent, text, node_type, interaction.user.display_name)
    except ValueError as e:
        await interaction.response.send_message(f"⚠️ {e}", ephemeral=True)
        return
    board.save()
    icon = "📌" if node_type == "beat" else "💭"
    await interaction.response.send_message(f"{icon} Added **#{node.id}** under #{parent}: {text}")


@group.command(name="edit", description="Edit the text of an existing node")
@app_commands.describe(id="Node ID to edit", text="New text")
async def edit(interaction: discord.Interaction, id: int, text: str):
    board = get_or_error(interaction.channel_id)
    try:
        board.edit(id, text)
    except ValueError as e:
        await interaction.response.send_message(f"⚠️ {e}", ephemeral=True)
        return
    board.save()
    await interaction.response.send_message(f"✏️ Updated **#{id}**.")


@group.command(name="remove", description="Remove a node (its children re-attach to its parent unless cascade=True)")
@app_commands.describe(id="Node ID to remove", cascade="Also delete everything underneath it")
async def remove(interaction: discord.Interaction, id: int, cascade: bool = False):
    board = get_or_error(interaction.channel_id)
    try:
        board.remove(id, cascade=cascade)
    except ValueError as e:
        await interaction.response.send_message(f"⚠️ {e}", ephemeral=True)
        return
    board.save()
    await interaction.response.send_message(f"🗑️ Removed **#{id}**{' and everything under it' if cascade else ''}.")


@group.command(name="show", description="Render the current story board as an image")
async def show(interaction: discord.Interaction):
    board = get_or_error(interaction.channel_id)
    await interaction.response.defer()
    try:
        path = board.render_image()
    except ValueError as e:
        await interaction.followup.send(f"⚠️ {e}")
        return
    await interaction.followup.send(file=discord.File(path))


@group.command(name="list", description="Show the board as a plain text outline (backup for /show)")
async def list_cmd(interaction: discord.Interaction):
    board = get_or_error(interaction.channel_id)
    text = board.as_text_tree()
    if len(text) > 1900:
        text = text[:1900] + "\n... (truncated, use /storyboard show for the full picture)"
    await interaction.response.send_message(f"**{board.title}**\n{text}")


@group.command(name="reset", description="Delete the story board for this channel entirely (admin only)")
async def reset(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message(
            "⚠️ You need the Manage Messages permission to reset a board.", ephemeral=True
        )
        return
    board = get_board(interaction.channel_id)
    if board:
        board.delete_file()
        _boards.pop(interaction.channel_id, None)
    await interaction.response.send_message("🧹 Story board cleared for this channel.")


bot.tree.add_command(group)

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Set DISCORD_TOKEN in your environment or .env file before running.")
    bot.run(TOKEN)
