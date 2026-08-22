import os
import json
import discord
from discord import app_commands

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
CONFIG_PATH = os.environ.get("CONFIG_PATH", "config.json")
SYNC_GUILD_IDS = [g.strip() for g in os.environ.get("SYNC_GUILD_IDS", "").split(",") if g.strip()]


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f)


_config = load_config()
welcome_channel_id = _config.get("welcome_channel_id", 0)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

GUILD_COLOR = 0x2b2d31

WELCOME_FIELDS = [
    {
        "name": "📜 CONSULT THE LEDGER",
        "value": "Please review [Rules of the Guild](#).",
    },
    {
        "name": "🏷️ CLAIM YOUR GUILD NAME",
        "value": "Reply below with the name the Guild will know you by.",
    },
    {
        "name": "⚔️ CLAIM YOUR CLASS",
        "value": (
            "Each class will have its own unique abilities in serving the guild on your adventure. "
            "Classes cannot be changed during campaigns. You may select from the following, choose wisely:\n\n"
            "🗡️ **Mercenary** — A fighter that will deal direct enemy damage.\n"
            "🔮 **Wizard** — A magician that will have the gift of foresight.\n"
            "🗝️ **Thief** — A master of stealth that will find hidden items.\n"
            "💛 **Healer** — A master in all things health.\n"
            "🗡️ **Assasin** — A clever attacker that will stalk its prey.\n"
            "🛡️ **Paladin** — A safeguard to protect against risky ventures."
        ),
    },
    {
        "name": "✔️ PREPARE FOR THE HUNT",
        "value": (
            "Once a Wayfinder records your name and class, the Archives will open and you'll gain access "
            "to your current campaign. TBR GA is a cooperative RPG reading realm. Log pages, audiobooks, "
            "and completed reads to battle powerful Guardians, uncover relics, earn gold, collect loot, "
            "and help the Guild conquer campaign challenges that will lead you deeper into the secret "
            "levels of the archives!"
        ),
    },
]

WELCOME_FOOTER = "Choose your name. Enter the Archives. Join the hunt."


def build_welcome_embed(member: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title="Welcome to the Archives!",
        description=(
            "*A new recruit has stepped through the gates...* "
            "**Before you can join the guild, your name and class must be entered into the Archives.**\n\n"
            "Acadia and Jazzy are beyond excited to welcome you all to the TBR Guild Archives! "
            "They are officially kicking off **Campaign 1: The Sunken Depths** this Sunday! "
            "Until then, you are in the Orientation Hall so you can get settled, review the rules, "
            "and prepare for what's ahead."
        ),
        color=GUILD_COLOR,
    )
    for field in WELCOME_FIELDS:
        embed.add_field(name=field["name"], value=field["value"], inline=False)
    embed.set_footer(text=WELCOME_FOOTER)
    if member.guild.icon:
        embed.set_thumbnail(url=member.guild.icon.url)
    return embed


class PostModal(discord.ui.Modal, title="Post a Message"):
    message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.paragraph,
        placeholder="Write your message here...",
        required=True,
        max_length=2000,
    )

    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self._channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        await self._channel.send(str(self.message))
        await interaction.response.send_message(f"✅ Posted in {self._channel.mention}.", ephemeral=True)


class EmbedModal(discord.ui.Modal, title="Post an Embed"):
    content = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.paragraph,
        placeholder="Write your embed message here. Use \\n for new lines.",
        required=True,
        max_length=4000,
    )

    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self._channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(description=str(self.content), color=GUILD_COLOR)
        await self._channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Embed posted in {self._channel.mention}.", ephemeral=True)


class EditModal(discord.ui.Modal, title="Edit Message"):
    def __init__(self, message: discord.Message, is_embed: bool):
        super().__init__()
        self._message = message
        self._is_embed = is_embed
        current_text = message.embeds[0].description if is_embed else message.content
        self.content = discord.ui.TextInput(
            label="Message",
            style=discord.TextStyle.paragraph,
            default=current_text or "",
            required=True,
            max_length=4000 if is_embed else 2000,
        )
        self.add_item(self.content)

    async def on_submit(self, interaction: discord.Interaction):
        if self._is_embed:
            embed = self._message.embeds[0]
            embed.description = str(self.content)
            await self._message.edit(embed=embed)
        else:
            await self._message.edit(content=str(self.content))
        await interaction.response.send_message("✅ Message updated.", ephemeral=True)


@client.event
async def on_ready():
    for guild_id in SYNC_GUILD_IDS:
        guild = discord.Object(id=int(guild_id))
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
    await tree.sync()
    print(f"Guild Master is online as {client.user}")


@client.event
async def on_member_join(member: discord.Member):
    if not welcome_channel_id:
        return
    channel = member.guild.get_channel(welcome_channel_id)
    if not channel:
        return
    embed = build_welcome_embed(member)
    await channel.send(content=member.mention, embed=embed)


@tree.command(name="gm-welcome", description="Manually post the welcome message for a member.")
@app_commands.describe(member="The member to welcome")
async def gm_welcome(interaction: discord.Interaction, member: discord.Member):
    embed = build_welcome_embed(member)
    await interaction.response.send_message(content=member.mention, embed=embed)


@tree.command(name="gm-setwelcome", description="Set the channel where new member welcome messages are posted.")
@app_commands.describe(channel="Channel to post welcome messages in")
@app_commands.checks.has_permissions(manage_guild=True)
async def gm_setwelcome(interaction: discord.Interaction, channel: discord.TextChannel):
    global welcome_channel_id
    welcome_channel_id = channel.id
    _config["welcome_channel_id"] = channel.id
    save_config(_config)
    await interaction.response.send_message(
        f"✅ Welcome messages will now be posted in {channel.mention}.", ephemeral=True
    )


@gm_setwelcome.error
async def gm_setwelcome_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ You need **Manage Server** permission to do that.", ephemeral=True
        )
    else:
        raise error


@tree.command(name="gm-post", description="Post a plain text message in a channel.")
@app_commands.describe(channel="Channel to post in")
async def gm_post(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.send_modal(PostModal(channel))


@tree.command(name="gm-embed", description="Post an embed message in a channel.")
@app_commands.describe(channel="Channel to post in")
async def gm_embed(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.send_modal(EmbedModal(channel))


@tree.command(name="gm-edit", description="Edit a message the bot previously posted.")
@app_commands.describe(channel="Channel the message is in", message_id="The ID of the message to edit")
async def gm_edit(interaction: discord.Interaction, channel: discord.TextChannel, message_id: str):
    try:
        msg_id = int(message_id)
    except ValueError:
        await interaction.response.send_message("❌ That doesn't look like a valid message ID.", ephemeral=True)
        return

    try:
        message = await channel.fetch_message(msg_id)
    except discord.NotFound:
        await interaction.response.send_message("❌ Couldn't find that message in that channel.", ephemeral=True)
        return
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to read that channel.", ephemeral=True)
        return

    if message.author.id != client.user.id:
        await interaction.response.send_message("❌ I can only edit messages I posted myself.", ephemeral=True)
        return

    await interaction.response.send_modal(EditModal(message, is_embed=bool(message.embeds)))


client.run(DISCORD_TOKEN)
