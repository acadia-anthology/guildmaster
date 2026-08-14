import os
import discord
from discord import app_commands

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    await tree.sync()
    print(f"Guild Master is online as {client.user}")

@tree.command(name="announce", description="Post an announcement as the Guild Master.")
@app_commands.describe(message="The announcement to post")
async def announce(interaction: discord.Interaction, message: str):
    await interaction.response.send_message(message)

client.run(DISCORD_TOKEN)
