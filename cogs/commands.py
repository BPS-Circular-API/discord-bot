import os
import sqlite3, discord
from discord.ext import commands
from backend import get_circular_list, log, embed_color, embed_footer, embed_title, categories, receives, get_latest_circular, get_png, search
from discord import SlashCommandGroup

category_options = []
for i in categories:
    category_options.append(discord.OptionChoice(i.capitalize().strip(), value=i.strip().lower()))
del categories


receive_options = []
for i in receives:
    receive_options.append(discord.OptionChoice(i.capitalize().strip(), value=i.strip().lower()))
del receives




class Commands(commands.Cog):
    def __init__(self, client):
        self.con = sqlite3.connect('./data/data.db')
        self.cur = self.con.cursor()
        self.client = client


    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog : Commands.py loaded.")

    # create slash command group
    circular = SlashCommandGroup("circular", "Circular related commands.")
    admin = circular.create_subgroup("admin", "Admin commands for the bot")

    @circular.command(name='list', description='List all circulars in a particular category.')
    async def list(self, ctx, category: discord.Option(choices=category_options), receive: discord.Option(choices=receive_options)):
        await ctx.defer()
        raw_res = await get_circular_list(category, "all")

        titles, unprocessed_links, links = [], [], []   # Define 3 empty lists
        loop_int = 1    # The variable which will be used to add numbers into the embed

        # Loop through the raw API output
        for item in raw_res:
            titles.append(f"**{loop_int}**. `{item['title']}`")  # Add the title to the list
            unprocessed_links.append(f"{item['link']}") # Add the link to the list
            loop_int += 1

        # Remove the redundant download url parameter after ?download=xxxx
        for link in unprocessed_links:
            link = link.split(':')
            link = f"{link[0]}:{link[1]}"
            links.append(link)

        del unprocessed_links
        embed = discord.Embed(title=f"Here is the result getting the `{category.capitalize()}` circulars!", color=embed_color)
        embed.set_footer(text=embed_footer)
        embed.set_author(name=embed_title)

        if receive == "all":
            for title, link in zip(titles, links):
                embed.add_field(name=title, value=link, inline=False)
        elif receive == "titles":
            for title in titles:
                embed.add_field(name=title, value="\u200b", inline=False)
        elif receive == "links":
            for link in links:
                embed.add_field(name="\u200b", value=link, inline=False)
        await ctx.followup.send(embed=embed)


    @circular.command(name="latest", description="Sends the latest circular in a particular category.")
    async def latest(self, ctx, category: discord.Option(choices=category_options)):
        await ctx.defer()
        raw_res = await get_latest_circular(category)
        title = raw_res['title']
        link = raw_res['link']
        embed = discord.Embed(title=f"Latest Circular | {category.capitalize()}", color=embed_color)
        embed.set_author(name=embed_title)
        link = link.split(':')
        link = f"{link[0]}:{link[1]}"


        embed.add_field(name="Title", value=f"`{title}`", inline=False)
        embed.add_field(name="Download URL", value=link, inline=False)
        embed.set_footer(text=embed_footer)

        await get_png(link, title)

        file = discord.File(f"./{title}.png", filename="image.png")
        embed.set_image(url="attachment://image.png")
        await ctx.followup.send(embed=embed, file=file)
        os.remove(f"./{title}.png")


    @circular.command(name="search", description="Searches for a particular circular in a particular category.")
    async def search(self, ctx, circular_title: str):
        await ctx.defer()
        searched = await search(circular_title)
        title = searched[0]
        link = searched[1]
        embed = discord.Embed(title="Circular Search", color=embed_color)
        embed.set_author(name=embed_title)
        embed.set_footer(text=embed_footer)
        embed.add_field(name="Title", value=f"`{title}`", inline=False)
        embed.add_field(name="Download URL", value=link, inline=False)

        print(searched)
    
        await get_png(link, title)

        file = discord.File(f"./{title}.png", filename="image.png")
        embed.set_image(url="attachment://image.png")
        await ctx.followup.send(embed=embed, file=file)





    # Admin commands
    @admin.command(name="setup", description="Set up the bot to notify the user when a circular is available in a channel.")
    async def server_setup(self, ctx, channel: discord.TextChannel, message: str = None):
        await ctx.defer()
        log.debug(f"Got a server setup request from {ctx.author.name}")
        self.cur.execute(f"SELECT * FROM notify WHERE guild_id = {ctx.guild.id}")   # Check if the guild is already in the database
        res = self.cur.fetchone()

        if res:
            log.debug(res)
            e_embed = discord.Embed(title="Server Setup", description=f"The server has an already existing reminder configuration!", color=embed_color)
            e_embed.set_author(name=embed_title)
            e_embed.set_footer(text=embed_footer)
            e_embed.add_field(name="Channel", value=f"`{res[1]}`", inline=False)
            e_embed.add_field(name="Message", value=f"`{res[2]}`", inline=True)
            e_embed.add_field(name="To delete!", value=f"Use `/circular admin delete` to delete this existing configuration!", inline=False)
            await ctx.followup.send(embed=e_embed)
            return

        if message:
            message = message.replace("<", "").replace(">", "").replace('"', "") # Remove the <> and " from the message
            self.cur.execute(f'INSERT INTO notify (guild_id, channel_id, message) VALUES ({ctx.guild.id}, {channel.id}, "{message}");')
        else:
            self.cur.execute(f"INSERT INTO notify (guild_id, channel_id) VALUES ({ctx.guild.id}, {channel.id});")
        self.con.commit()
        c_embed = discord.Embed(title="Success!", description="The reminder configuration for this server has successfully been added!", color=embed_color)
        c_embed.set_author(name=embed_title)
        c_embed.set_footer(text=embed_footer)
        c_embed.add_field(name="Channel", value=f"{channel.mention}", inline=False)
        if message:
            c_embed.add_field(name="Message", value=f"`{message}`", inline=False)
        await ctx.followup.send(embed=c_embed)




    @admin.command(name="delete", description="Delete the server's circular reminder configuration.")
    async def delete(self, ctx):
        await ctx.defer()
        self.cur.execute(f"SELECT * FROM notify WHERE guild_id = {ctx.guild.id}")
        res = self.cur.fetchone()
        if not res:
            e_embed = discord.Embed(title="Server Setup", description=f"The server has no reminder configuration!", color=embed_color)
            e_embed.set_author(name=embed_title)
            e_embed.set_footer(text=embed_footer)
            await ctx.followup.send(embed=e_embed)
            return
        self.cur.execute(f"DELETE FROM notify WHERE guild_id = {ctx.guild.id}")
        self.con.commit()
        d_embed = discord.Embed(title="Success!", description="The bot has successfully been set up to remind, in this server.", color=embed_color)
        d_embed.set_author(name=embed_title)
        d_embed.set_footer(text=embed_footer)
        await ctx.followup.send(embed=d_embed)


    @circular.command(name="help", description="Shows the help message for the circular commands.")
    async def help(self, ctx):
        await ctx.defer()
        embed = discord.Embed(title="Circular Commands", description="Here is the list of commands for the circulars.", color=embed_color)
        embed.set_author(name=embed_title)
        embed.set_footer(text=embed_footer)
        embed.add_field(name="/circular list", value="List all circulars in a particular category.", inline=False)
        embed.add_field(name="/circular latest", value="Sends the latest circular, the download URL and a the preview of a particular category.", inline=False)
        embed.add_field(name="/circular search", value="Searches for a circular from input and gives preview and circular details", inline=False)
        await ctx.followup.send(embed=embed)
        # add embed image



def setup(client):
    client.add_cog(Commands(client))