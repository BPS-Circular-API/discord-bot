import sqlite3, discord
from discord.ext import commands, tasks
from backend import log, get_latest_circular_cached, embed_color, embed_footer, embed_title



class Listeners(commands.Cog):
    def __init__(self, client):
        self.cached_latest = {}
        self.old_cached_latest = {}
        self.client = client
        self.con = sqlite3.connect('./data/data.db')
        self.cur = self.con.cursor()
        self.new_circular_cat = []

    @commands.Cog.listener()
    async def on_ready(self):
        log.info(f"Cog : Listeners.py loaded.")
        self.check_for_circular.start()


    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        log.info(f"I just joined a server: {guild.id}")
        embed = discord.Embed(title=f"Thanks for adding me!", description=f"Here's the command guide! An admin can ", color=embed_color)
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



    @commands.slash_command()
    async def testnotify(self, ctx):
        self.new_circular_cat = "general"
        await self.notify()


    @tasks.loop(seconds=3600)
    async def check_for_circular(self):
        categories = ["ptm", "general", "exam"]
        self.old_cached_latest = self.cached_latest
        for cat in categories:
            latest = await get_latest_circular_cached(cat)
            self.cached_latest[cat] = latest

        log.debug(f"Current cached", self.cached_latest)
        log.debug(f"old cached", self.old_cached_latest)
        if self.cached_latest != self.old_cached_latest:
            log.info("new circular")
            # check which category has new circular
            for cat in categories:
                if self.cached_latest[cat] != self.old_cached_latest[cat]:
                    log.info(f"{cat} has new circular")
                    self.new_circular_cat = cat # Let's just HOPE that they will not upload multiple circulars to multiple categories within an hour
            await self.notify()




    async def notify(self):
        self.cur.execute(f"SELECT channel_id FROM notify")
        channels = self.cur.fetchall()
        self.cur.execute(f"SELECT guild_id FROM notify")
        guilds = self.cur.fetchall()
        embed = discord.Embed(title=f"New circular in {self.new_circular_cat}", color=embed_color)
        embed.set_footer(text=embed_footer)
        embed.set_author(name=embed_title)
        embed.add_field(name="Title", value=self.cached_latest[self.new_circular_cat], inline=False)
        # get and send to all channels of the respective guilds
        for guild in guilds:
            for channel in channels:
                if guild[0] == channel[0]:
                    await self.client.get_channel(channel[0]).send(embed=embed)


    @check_for_circular.before_loop
    async def before_my_task(self):
        await self.client.wait_until_ready()




def setup(client):
    client.add_cog(Listeners(client))
