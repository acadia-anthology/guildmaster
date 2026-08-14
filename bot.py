import os
import discord
from discord import app_commands

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
WELCOME_CHANNEL_ID = int(os.environ.get("WELCOME_CHANNEL_ID", "0"))

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

GUILD_COLOR = 0x2b2d31

WELCOME_EMBED_TITLE = "Welcome to the Archives!"
WELCOME_EMBED_DESCRIPTION = (
    "*A new recruit has stepped through the gates...* "
    "**Before you can join the guild, your name and class must be entered into the Archives.**\n\n"
    "Acadia and Jazzy are beyond excited to welcome you all to the TBR Guild Archives! "
    "They are officially kicking off **Campaign 1: The Sunken Depths** this Sunday! "
    "Until then, you are in the Orientation Hall so you can get settled, review the rules, "
    "and prepare for what's ahead."
)

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
        title=WELCOME_EMBED_TITLE,
        description=WELCOME_EMBED_DESCRIPTION,
        color=GUILD_COLOR,
    )
    for field in WELCOME_FIELDS:
        embed.add_field(name=field["name"], value=field["value"], inline=False)
    embed.set_footer(text=WELCOME_FOOTER)
    if member.guild.icon:
        embed.set_thumbnail(url=member.guild.icon.url)
    return embed


@client.event
async def on_ready():
    await tree.sync()
    print(f"Guild Master is online as {client.user}")


@client.event
async def on_member_join(member: discord.Member):
    if not WELCOME_CHANNEL_ID:
        return
    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if not channel:
        return
    embed = build_welcome_embed(member)
    await channel.send(content=member.mention, embed=embed)


@tree.command(name="welcome", description="Manually post the welcome message for a member.")
@app_commands.describe(member="The member to welcome")
async def welcome(interaction: discord.Interaction, member: discord.Member):
    embed = build_welcome_embed(member)
    await interaction.response.send_message(content=member.mention, embed=embed)


@tree.command(name="post", description="Post a plain message in a channel.")
@app_commands.describe(channel="Channel to post in", message="The message to post")
async def post(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    await channel.send(message)
    await interaction.response.send_message(f"✅ Posted in {channel.mention}.", ephemeral=True)


@tree.command(name="embed", description="Post an embed message in a channel.")
@app_commands.describe(
    channel="Channel to post in",
    title="Embed title",
    body="Embed body text",
    color="Hex color code (e.g. ff0000) — optional"
)
async def post_embed(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    title: str,
    body: str,
    color: str = ""
):
    try:
        embed_color = int(color.lstrip("#"), 16) if color else GUILD_COLOR
    except ValueError:
        embed_color = GUILD_COLOR

    embed = discord.Embed(title=title, description=body, color=embed_color)
    await channel.send(embed=embed)
    await interaction.response.send_message(f"✅ Embed posted in {channel.mention}.", ephemeral=True)


@tree.command(name="announce", description="Post an announcement embed with a bold header.")
@app_commands.describe(
    channel="Channel to post in",
    title="Announcement title",
    message="Announcement body"
)
async def announce(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    title: str,
    message: str
):
    embed = discord.Embed(title=f"📣 {title}", description=message, color=GUILD_COLOR)
    await channel.send(embed=embed)
    await interaction.response.send_message(f"✅ Announcement posted in {channel.mention}.", ephemeral=True)


client.run(DISCORD_TOKEN)
