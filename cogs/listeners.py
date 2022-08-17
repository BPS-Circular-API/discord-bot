import discord
from discord.ext import commands
from backend import log


class Listeners(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        log.info(f"Cog : Listeners.py loaded.")



def setup(client):
    client.add_cog(Listeners(client))
