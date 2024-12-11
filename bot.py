import os
import sys
import requests
from backend import client, discord_token, console, init_database, base_api_url
import discord

init_database()

@client.event
async def on_ready():
    print("Connected to Discord!")
    console.info(f"Bot is ready. Logged in as {client.user}")
    console.info(f"Latency with Discord: {round(client.latency * 1000, 2)}ms")
    console.info(f"Latency with BPS API: {requests.get(base_api_url).elapsed.total_seconds() * 1000:.2f}ms")

print("f")
for file in os.listdir('./cogs'):
    if file.endswith('.py'):
        print(file)
        client.load_extension(f'cogs.{file[:-3]}')

try:
    client.run(discord_token)
except discord.LoginFailure:
    console.critical("Invalid Discord Token. Please check your config file.")
    sys.exit()
except Exception as err:
    console.critical(f"Error while connecting to Discord. Error: {err}")
    sys.exit()
