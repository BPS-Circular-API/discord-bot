import discord, sqlite3
from discord.ext import commands
from backend import owner_ids, embed_title, embed_footer, embed_color, log

class Owners(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.con = sqlite3.connect('./data/data.db')
        self.cur = self.con.cursor()

    owners = discord.SlashCommandGroup("owners", "Bot owner commands.")

    @commands.Cog.listener()
    async def on_ready(self):
        log.info(f"Cog : Owners.py loaded.")


    @owners.command(name='reload', description='Reload a cog.')
    async def reload(self, ctx, cog: str):
        if not ctx.author.id in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")

        self.client.unload_extension(f"cogs.{cog}")
        self.client.load_extension(f"cogs.{cog}")
        await ctx.respond(f"Reloaded {cog}.")



    @owners.command(name="execsql", description="Execute a SQL query.")
    async def execsql(self, ctx, query):

        if not ctx.author.id in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")
        await ctx.defer()
        try:
            self.cur.execute(query)
        except Exception as e:
            await ctx.followup.send(embed=discord.Embed(title="Execute SQL", description=f"**Error!**\n{e}", color=discord.colour.Color.red()).set_footer(text=embed_footer).set_author(name=embed_title), ephemeral=True)
            return
        res = self.cur.fetchall()
        if len(res) == 0:
            embed = discord.Embed(title="Execute SQL", description="**Success!**\nNo results found.", color=embed_color).set_footer(text=embed_footer).set_author(name=embed_title)
        else:
            embed = discord.Embed(title="Execute SQL", description="**Success!**\nResults found.", color=embed_color).set_footer(text=embed_footer).set_author(name=embed_title)
            for i in res:
                embed.add_field(name=str(i), value=str(i), inline=False)
        self.con.commit()
        self.con.close()
        await ctx.followup.send(embed=embed, ephemeral=True)


    @owners.command(name="servers", description="List all servers the bot is in.")
    async def servers(self, ctx):
        if not ctx.author.id in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")
        await ctx.defer()
        embed = discord.Embed(title="Servers", description="**Servers**", color=embed_color).set_footer(text=embed_footer).set_author(name=embed_title)
        for guild in self.client.guilds:
            print(guild)
            guild = self.client.get_guild(guild)
            embed.add_field(name=guild.id, value="\u200b", inline=False)
        await ctx.followup.send(embed=embed, ephemeral=True)
    
    @owners.command(name="testjoin", description="Test join a server.")
    async def testjoin(self, ctx, server_id: str):
        if not ctx.author.id in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")
        await ctx.defer()
        try:
            await self.client.get_guild(int(server_id)).join()
        except Exception as e:
            await ctx.followup.send(embed=discord.Embed(title="Test Join", description=f"**Error!**\n{e}", color=discord.colour.Color.red()).set_footer(text=embed_footer).set_author(name=embed_title), ephemeral=True)
            return
        await ctx.followup.send(embed=discord.Embed(title="Test Join", description="**Success!**\nJoined server.", color=embed_color).set_footer(text=embed_footer).set_author(name=embed_title), ephemeral=True)


def setup(client):
    client.add_cog(Owners(client))