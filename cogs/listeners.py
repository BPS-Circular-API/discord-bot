import os
import random
import sqlite3, discord
from discord.ext import commands, tasks
from backend import log, get_latest_circular_cached, embed_color, embed_footer, embed_title, get_png


class Listeners(commands.Cog):
    def __init__(self, client):
        self.cached_latest = {}
        self.old_cached_latest = {}
        self.client = client
        self.con = sqlite3.connect('./data/data.db')
        self.cur = self.con.cursor()
        self.new_circular_cat = ""

    @commands.Cog.listener()
    async def on_ready(self):
        log.info(f"Cog : Listeners.py loaded.")
        self.check_for_circular.start()
        self.random_status.start()


    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        log.info(f"I just joined a server: {guild.id}")
        guild = await self.client.fetch_guild(guild.id)
        embed = discord.Embed(title=f"Thanks for adding me!", description=f"Here's the command guide! An admin can ", color=embed_color)
        embed.add_field(name="Admin Guide", value="Please up the circular-reminder with `/circular admin setup` to receive notifications when new circulars are posted.", inline=False)
        embed.add_field(name="Command Guide", value=f"All the commands start with `/circular`, they're slash commands. ", inline=False)

        embed.set_footer(text=embed_footer)
        embed.set_author(name=embed_title)
        # find the first channel in the guild and send to it
        channels = guild.text_channels
        log.debug(channels)
        for channel in channels:
            log.debug(channel)
            try:
                await self.client.get_channel(channel[0]).send(embed=embed)
                break
            except discord.Forbidden:
                pass


    @tasks.loop(seconds=60)
    async def random_status(self):
        random_number = random.randint(0, 6)
        if random_number == 0:
            await self.client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{len(self.client.users)} Users!"))
        elif random_number == 1:
            await self.client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{len(self.client.guilds)} Guilds!"))
        elif random_number == 2:
            await self.client.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=f"/circular help"))
        elif random_number == 3:
            await self.client.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=f"/circular admin setup"))
        elif random_number == 4:
            await self.client.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=f"I'm Open Source!"))
        elif random_number == 5:
            await self.client.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=f"Made by `Raj Dave#3215`"))
        elif random_number == 6:
            await self.client.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=f"/circular invite"))







    @tasks.loop(seconds=3600)
    async def check_for_circular(self):
        categories = ["ptm", "general", "exam"]
        if self.old_cached_latest == {}:    # If the bot just started and there is no older cached
            self.old_cached_latest = await get_latest_circular_cached("all")
        else:   # If cached exists
            self.old_cached_latest = self.cached_latest

        self.cached_latest = await get_latest_circular_cached("all")
        if self.cached_latest != self.old_cached_latest:    # If the cached circular list is different from the current one
            log.info("There's a new circular posted!")
            for cat in categories:  # Check which category has a new circular
                if self.cached_latest[cat] != self.old_cached_latest[cat]:
                    log.info(f"{cat} has new circular")
                    self.new_circular_cat = cat # Let's just HOPE that they will not upload multiple circulars to multiple categories within an hour
            await self.notify() # notify each server




    async def notify(self):
        self.cur.execute(f"SELECT channel_id FROM notify")
        channels = self.cur.fetchall()
        self.cur.execute(f"SELECT guild_id FROM notify")
        guilds = self.cur.fetchall()
        embed = discord.Embed(title=f"New Circular Alert!", color=embed_color)
        embed.set_footer(text=embed_footer)
        embed.set_author(name=embed_title)
        link = str(self.cached_latest[self.new_circular_cat]['link'])
        link = link.split(':')
        link = f"{link[0]}:{link[1]}"
        title = self.cached_latest[self.new_circular_cat]['title']
        await get_png(link, title)

        file = discord.File(f"./{title}.png", filename="image.png")
        embed.set_image(url="attachment://image.png")
        os.remove(f"./{title}.png")

        embed.add_field(name=f"{self.new_circular_cat.capitalize()} | {title}", value=link, inline=False)
        for guild, channel in zip(guilds, channels):
            guild = self.client.get_guild(int(guild[0]))
            channel = await guild.fetch_channel(int(channel[0]))
            await channel.send(embed=embed, file=file)


    @random_status.before_loop
    @check_for_circular.before_loop
    async def before_my_task(self):
        await self.client.wait_until_ready()


def setup(client):
    client.add_cog(Listeners(client))
