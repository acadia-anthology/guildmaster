import os
import json
import re
import traceback
from typing import Literal, Union
import discord
from discord import app_commands

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
CONFIG_PATH = os.environ.get("CONFIG_PATH", "config.json")
SYNC_GUILD_IDS = [g.strip() for g in os.environ.get("SYNC_GUILD_IDS", "").split(",") if g.strip()]
COMMANDS_CHANNEL_ID = 1513883581414375605


async def resolve_channel_arg(interaction: discord.Interaction, channel_arg: str):
    """Resolve a channel/thread from a pasted ID or #mention.

    The native channel-picker only shows threads the invoking user has
    joined, so admins can't target threads they were never added to.
    Resolving by ID sidesteps that entirely.
    """
    raw = channel_arg.strip()
    if raw.startswith("<#") and raw.endswith(">"):
        raw = raw[2:-1]
    try:
        channel_id = int(raw)
    except ValueError:
        return None

    channel = interaction.guild.get_channel_or_thread(channel_id)
    if channel:
        return channel
    try:
        return await interaction.guild.fetch_channel(channel_id)
    except (discord.NotFound, discord.Forbidden):
        return None


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

GUILD_COLOR = 0x3ff34d

EMOJI_MAP: dict[str, discord.Emoji] = {}
EMOJI_TAG_PATTERN = re.compile(r"<a?:(\w+):\d+>")
SHORTCODE_PATTERN = re.compile(r":(\w+):")


def deresolve_emojis(text: str) -> str:
    return EMOJI_TAG_PATTERN.sub(lambda m: f":{m.group(1)}:", text)


def resolve_emojis(text: str) -> str:
    # Protect already-resolved <:name:id> tags first, since they contain a
    # :name: substring that would otherwise get matched and re-expanded.
    protected = []

    def stash(match: re.Match) -> str:
        protected.append(match.group(0))
        return f"\x00{len(protected) - 1}\x00"

    text = EMOJI_TAG_PATTERN.sub(stash, text)

    def replace(match: re.Match) -> str:
        emoji = EMOJI_MAP.get(match.group(1))
        if not emoji:
            return match.group(0)
        prefix = "a" if emoji.animated else ""
        return f"<{prefix}:{emoji.name}:{emoji.id}>"

    text = SHORTCODE_PATTERN.sub(replace, text)

    for i, tag in enumerate(protected):
        text = text.replace(f"\x00{i}\x00", tag)

    return text

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

    def __init__(self, channel: Union[discord.TextChannel, discord.Thread]):
        super().__init__()
        self._channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        await self._channel.send(resolve_emojis(str(self.message)))
        await interaction.response.send_message(f"✅ Posted in {self._channel.mention}.", ephemeral=True)


class EmbedModal(discord.ui.Modal, title="Post an Embed"):
    content = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.paragraph,
        placeholder="Write your embed message here. Use \\n for new lines.",
        required=True,
        max_length=4000,
    )
    color = discord.ui.TextInput(
        label="Color (hex, optional)",
        placeholder="3ff34d — leave blank for the default",
        required=False,
        max_length=6,
    )

    def __init__(self, channel: Union[discord.TextChannel, discord.Thread], role: discord.Role = None):
        super().__init__()
        self._channel = channel
        self._role = role

    async def on_submit(self, interaction: discord.Interaction):
        try:
            embed_color = int(str(self.color).lstrip("#"), 16) if str(self.color) else GUILD_COLOR
        except ValueError:
            embed_color = GUILD_COLOR
        embed = discord.Embed(description=resolve_emojis(str(self.content)), color=embed_color)
        await self._channel.send(content=self._role.mention if self._role else None, embed=embed)
        await interaction.response.send_message(f"✅ Embed posted in {self._channel.mention}.", ephemeral=True)


class ForumPostModal(discord.ui.Modal, title="Post a Forum Thread"):
    thread_title = discord.ui.TextInput(
        label="Thread Title",
        placeholder="Title for the new thread",
        required=True,
        max_length=100,
    )
    content = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.paragraph,
        placeholder="Write the thread's opening message here.",
        required=True,
        max_length=4000,
    )

    def __init__(
        self,
        channel: discord.ForumChannel,
        image: discord.Attachment = None,
        post_type: Literal["embed", "text"] = "embed",
    ):
        super().__init__()
        self._channel = channel
        self._image = image
        self._post_type = post_type

    async def on_submit(self, interaction: discord.Interaction):
        text = resolve_emojis(str(self.content))
        file = await self._image.to_file() if self._image else None

        kwargs = {"name": str(self.thread_title)}
        if self._post_type == "embed":
            embed = discord.Embed(description=text, color=GUILD_COLOR)
            if file:
                embed.set_image(url=f"attachment://{file.filename}")
            kwargs["embed"] = embed
        else:
            kwargs["content"] = text
        if file:
            kwargs["file"] = file

        await self._channel.create_thread(**kwargs)
        await interaction.response.send_message(f"✅ Thread posted in {self._channel.mention}.", ephemeral=True)


class EditModal(discord.ui.Modal, title="Edit Message"):
    def __init__(self, message: discord.Message, is_embed: bool):
        super().__init__()
        self._message = message
        self._is_embed = is_embed
        current_text = message.embeds[0].description if is_embed else message.content
        current_text = deresolve_emojis(current_text or "")
        max_len = 4000 if is_embed else 2000
        current_text = current_text[:max_len]
        self.content = discord.ui.TextInput(
            label=f"Message ({len(current_text)}/{max_len})",
            style=discord.TextStyle.paragraph,
            default=current_text,
            required=True,
            max_length=max_len,
        )
        self.add_item(self.content)

    async def on_submit(self, interaction: discord.Interaction):
        if self._is_embed:
            embed = self._message.embeds[0]
            embed.description = resolve_emojis(str(self.content))
            await self._message.edit(embed=embed)
        else:
            await self._message.edit(content=resolve_emojis(str(self.content)))
        await interaction.response.send_message("✅ Message updated.", ephemeral=True)


@client.event
async def on_ready():
    global EMOJI_MAP
    try:
        app_emojis = await client.fetch_application_emojis()
        EMOJI_MAP = {emoji.name: emoji for emoji in app_emojis}
        print(f"Loaded {len(EMOJI_MAP)} application emojis: {sorted(EMOJI_MAP)}")
    except Exception:
        print("Failed to fetch application emojis:")
        traceback.print_exc()

    try:
        for guild_id in SYNC_GUILD_IDS:
            guild = discord.Object(id=int(guild_id))
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)

        if SYNC_GUILD_IDS:
            tree.clear_commands(guild=None)
        await tree.sync()
        print(f"Guild Master is online as {client.user}")
    except Exception:
        print("Failed during command sync:")
        traceback.print_exc()

    commands_channel = client.get_channel(COMMANDS_CHANNEL_ID)
    if commands_channel:
        try:
            await commands_channel.send("✅ The Guildmaster is back online.")
        except Exception:
            print("Failed to send online notice:")
            traceback.print_exc()
    else:
        print(f"Could not find commands channel with ID {COMMANDS_CHANNEL_ID}")


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


@tree.command(name="gm-post", description="Post a plain text message in a channel or thread.")
@app_commands.describe(channel="Channel/thread mention or ID to post in")
async def gm_post(interaction: discord.Interaction, channel: str):
    target = await resolve_channel_arg(interaction, channel)
    if target is None:
        await interaction.response.send_message("❌ Couldn't find that channel or thread.", ephemeral=True)
        return
    await interaction.response.send_modal(PostModal(target))


@tree.command(name="gm-embed", description="Post an embed message in a channel or thread.")
@app_commands.describe(
    channel="Channel/thread mention or ID to post in",
    role="Role to tag alongside the embed (optional)",
)
async def gm_embed(interaction: discord.Interaction, channel: str, role: discord.Role = None):
    target = await resolve_channel_arg(interaction, channel)
    if target is None:
        await interaction.response.send_message("❌ Couldn't find that channel or thread.", ephemeral=True)
        return
    await interaction.response.send_modal(EmbedModal(target, role))


@tree.command(name="gm-help", description="List all Guild Master commands.")
async def gm_help(interaction: discord.Interaction):
    embed = discord.Embed(title="Guild Master Commands", color=GUILD_COLOR)
    for command in sorted(tree.get_commands(), key=lambda c: c.name):
        embed.add_field(name=f"/{command.name}", value=command.description or "No description", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="gm-emojis", description="List all emojis registered to the bot's application.")
async def gm_emojis(interaction: discord.Interaction):
    await interaction.response.defer()

    global EMOJI_MAP
    try:
        app_emojis = await client.fetch_application_emojis()
        EMOJI_MAP = {emoji.name: emoji for emoji in app_emojis}

        if not app_emojis:
            await interaction.followup.send("No emojis registered yet.", ephemeral=True)
            return

        lines = [f"{emoji} `{emoji.name}`" for emoji in sorted(app_emojis, key=lambda e: e.name)]

        # Chunk into fields (max 1024 chars each), then group a few fields
        # per embed to stay well under Discord's 6000-char total-embed cap.
        fields = []
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 1 > 1024:
                fields.append(chunk)
                chunk = ""
            chunk += line + "\n"
        if chunk:
            fields.append(chunk)

        embeds = []
        for i in range(0, len(fields), 4):
            embed = discord.Embed(color=GUILD_COLOR)
            if i == 0:
                embed.title = f"Registered Emojis ({len(lines)})"
            for j, field_value in enumerate(fields[i:i + 4], start=i + 1):
                embed.add_field(name=f"Emojis {j}", value=field_value, inline=False)
            embeds.append(embed)

        # Discord allows up to 10 embeds per message.
        for i in range(0, len(embeds), 10):
            await interaction.followup.send(embeds=embeds[i:i + 10])
    except Exception as exc:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Failed to list emojis: {exc}", ephemeral=True)


@tree.command(name="gm-emoji-upload", description="Upload a new emoji to the bot's application.")
@app_commands.describe(name="Emoji name (2-32 characters)", image="Image file (PNG, JPG, or GIF)")
async def gm_emoji_upload(interaction: discord.Interaction, name: str, image: discord.Attachment):
    await interaction.response.defer(ephemeral=True)
    image_bytes = await image.read()
    try:
        emoji = await client.create_application_emoji(name=name, image=image_bytes)
    except discord.HTTPException as exc:
        await interaction.followup.send(f"❌ Failed to upload emoji: {exc}", ephemeral=True)
        return

    EMOJI_MAP[emoji.name] = emoji
    await interaction.followup.send(f"✅ Uploaded {emoji} as `:{emoji.name}:`.", ephemeral=True)


@tree.command(name="gm-forum", description="Post a new thread in a forum channel.")
@app_commands.describe(
    channel="Forum channel to post in",
    image="Image to attach to the thread (optional)",
    post_type="Post as an embed or plain text",
)
async def gm_forum(
    interaction: discord.Interaction,
    channel: discord.ForumChannel,
    image: discord.Attachment = None,
    post_type: Literal["embed", "text"] = "embed",
):
    await interaction.response.send_modal(ForumPostModal(channel, image, post_type))


@tree.command(name="gm-edit", description="Edit a message the bot previously posted.")
@app_commands.describe(
    channel="Channel/thread mention or ID the message is in",
    message_id="The ID of the message to edit",
)
async def gm_edit(interaction: discord.Interaction, channel: str, message_id: str):
    try:
        msg_id = int(message_id)
    except ValueError:
        await interaction.response.send_message("❌ That doesn't look like a valid message ID.", ephemeral=True)
        return

    channel = await resolve_channel_arg(interaction, channel)
    if channel is None:
        await interaction.response.send_message("❌ Couldn't find that channel or thread.", ephemeral=True)
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
