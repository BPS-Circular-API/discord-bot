import os
import sys
from backend import client, discord_token, console
import discord


@client.event
async def on_ready():
    print("Connected to Discord!")
    console.info(f"Bot is ready. Logged in as {client.user}")
    console.info(f"Latency with Discord: {round(client.latency * 1000, 2)}ms")
    #console.info(f"Latency with bps API: {}")


for file in os.listdir('./cogs'):
    if file.endswith('.py'):
        client.load_extension(f'cogs.{file[:-3]}')

try:
    client.run(discord_token)
except discord.LoginFailure:
    console.critical("Invalid Discord Token. Please check your config file.")
    sys.exit()
except Exception as err:
    console.critical(f"Error while connecting to Discord. Error: {err}")
    sys.exit()
