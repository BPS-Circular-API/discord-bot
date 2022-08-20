import discord, os
from backend import client, discord_token, log

@client.event
async def on_ready():
    print("Connected to Discord!")
    log.info(f"Bot is ready. Logged in as {client.user}")
    await client.change_presence(activity=discord.Game(name="/help"))


for file in os.listdir('./cogs'):
    if file.endswith('.py'):
        client.load_extension(f'cogs.{file[:-3]}')

client.run(discord_token)