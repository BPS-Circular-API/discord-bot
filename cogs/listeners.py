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

        log.debug(self.cached_latest)
        log.debug(self.old_cached_latest)
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
