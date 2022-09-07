import sqlite3, discord
from discord.ext import commands
from backend import get_circular_list, log, embed_color, embed_footer, embed_title, categories, receives, \
    get_latest_circular, get_png, search, owner_ids, DeleteButton, ConfirmButton
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
    async def list(self, ctx, category: discord.Option(choices=category_options)):
        await ctx.defer()

        guild = await self.client.fetch_guild(ctx.guild.id) # Fetch the guild object
        author = await self.client.fetch_user(ctx.author.id)    # Fetch the user object
        log.info(f"{author.id} in {guild.id} is requesting a list of circulars in {category}.")
        raw_res = await get_circular_list(category, "all")  # Get the list of circulars from API

        titles, unprocessed_links, links = [], [], []   # Define 3 empty lists
        loop_int = 1    # The variable which will be used to add numbers into the embed

        # Loop through the raw API output
        for item in raw_res:
            titles.append(f"**{loop_int}**. `{item['title']}`")  # Add the title to the list
            unprocessed_links.append(f"{item['link']}") # Add the link to the list
            loop_int += 1

        # Remove the redundant download url parameter after ?download=xxxx
        for link in unprocessed_links:  # Loop through the unprocessed links
            link = link.split(':')  # Split the link by :
            link = f"{link[0]}:{link[1]}"   # Join the first 2 parts of the link
            links.append(link)  # Add the link to the list

        del unprocessed_links   # Delete the unprocessed links list
        embed = discord.Embed(title=f"Here is the result getting the `{category.capitalize()}` circulars!", color=embed_color)  # Create the embed
        embed.set_footer(text=embed_footer) # Set the footer
        embed.set_author(name=embed_title)  # Set the author


        for title, link in zip(titles, links):  # Loop through the titles and links
            embed.add_field(name=title, value=link, inline=False)   # Add a field to the embed

        msg = await ctx.followup.send(embed=embed)  # Send the embed
        await msg.edit(embed=embed, view=DeleteButton(ctx, msg))    # Edit the embed and add the delete button


    @circular.command(name="latest", description="Sends the latest circular in a particular category.")
    async def latest(self, ctx, category: discord.Option(choices=category_options)):
        await ctx.defer()

        guild = await self.client.fetch_guild(ctx.guild.id) # Fetch the guild object
        author = await self.client.fetch_user(ctx.author.id)    # Fetch the user object
        log.info(f"{author.id} in {guild.id} is requesting the latest circular in {category}.")

        raw_res = await get_latest_circular(category)   # Get the latest circular from API
        title = raw_res['title']    # Get the title
        link = raw_res['link']  # Get the link
        link = link.split(':')  # Split the link by :
        link = f"{link[0]}:{link[1]}"   # Join the first 2 parts of the link

        embed = discord.Embed(title=f"Latest Circular | {category.capitalize()}", color=embed_color)    # Create the embed
        embed.set_author(name=embed_title)  # Set the author
        embed.add_field(name="Title", value=f"`{title}`", inline=False)  # Add the title field
        embed.add_field(name="Download URL", value=link, inline=False)  # Add the download url field
        embed.set_footer(text=embed_footer) # Set the footer

        png_url = await get_png(link)  # Get the png file from the download url
        embed.set_image(url=png_url)   # Set the image to the embed

        msg = await ctx.followup.send(embed=embed)   # Send the embed
        await msg.edit(embed=embed, view=DeleteButton(ctx, msg))    # Edit the embed and add the delete button



    @circular.command(name="search", description="Searches for a particular circular in a particular category.")
    async def search(self, ctx, circular_title: str):
        await ctx.defer()

        guild = await self.client.fetch_guild(ctx.guild.id) # Fetch the guild object
        author = await self.client.fetch_user(ctx.author.id)    # Fetch the user object

        log.info(f"{author.id} in {guild.id} is searching for {circular_title}")
        searched = await search(circular_title) # Search for the circular from the backend function

        title = searched[0] # Get the title
        link = searched[1]  # Get the link

        embed = discord.Embed(title="Circular Search", color=embed_color)   # Create an embed
        embed.set_author(name=embed_title)  # Set the author
        embed.set_footer(text=embed_footer) # Set the footer
        embed.add_field(name="Title", value=f"`{title}`", inline=False)
        embed.add_field(name="Download URL", value=link, inline=False)

        png_url = await get_png(link)  # Get the png file from the download url
        embed.set_image(url=png_url)   # Set the image to the embed

        msg = await ctx.followup.send(embed=embed)   # Send the embed
        await msg.edit(embed=embed, view=DeleteButton(ctx, msg))    # Edit the embed and add the delete button





    # Admin commands
    @admin.command(name="setup", description="Set up the bot to guild_notify the user when a circular is available in a channel.")
    async def server_setup(self, ctx, channel: discord.TextChannel, message: str = None):
        await ctx.defer()

        guild = await self.client.fetch_guild(ctx.guild.id) # Fetch the guild object
        author = await guild.fetch_member(ctx.author.id)   # Fetch the member object

        log.info(f"{author.id} in {guild.id} is setting up the bot in {channel.name}.")

        if not author.guild_permissions.administrator:  # Check if the author has admin permissions
            if not author.id in owner_ids:  # Check if the author is an owner
                await ctx.followup.send(embed=discord.Embed(title="Error!", description="You do not have permission to use this command!", color=embed_color))
                return

        self.cur.execute(f"SELECT * FROM guild_notify WHERE guild_id = {guild.id}")   # Check if the guild is already in the database
        res = self.cur.fetchone()

        if res: # If the guild is in the database
            log.debug(res)
            e_embed = discord.Embed(title="Server Setup", description=f"The server has an already existing reminder configuration!", color=embed_color)
            e_embed.set_author(name=embed_title)
            e_embed.set_footer(text=embed_footer)
            e_embed.add_field(name="Channel", value=f"`{res[1]}`", inline=False)
            e_embed.add_field(name="Message", value=f"`{res[2]}`", inline=True)
            e_embed.add_field(name="To delete!", value=f"Use `/circular admin delete` to delete this existing configuration!", inline=False)
            await ctx.followup.send(embed=e_embed)
            return

        if message: # If the message is not None
            message = message.replace("<", "").replace(">", "").replace('"', "") # Remove the <> and " from the message
            self.cur.execute(f'INSERT INTO guild_notify (guild_id, channel_id, message) VALUES ({guild.id}, {channel.id}, "{message}");')
        else:   # If the message is None
            self.cur.execute(f"INSERT INTO guild_notify (guild_id, channel_id) VALUES ({guild.id}, {channel.id});")

        self.con.commit()   # Commit the changes to the database

        c_embed = discord.Embed(title="Success!", description="The reminder configuration for this server has successfully been added!", color=embed_color)
        c_embed.set_author(name=embed_title)
        c_embed.set_footer(text=embed_footer)
        c_embed.add_field(name="Channel", value=f"{channel.mention}", inline=False)

        if message: # If the message is not None, add the message to the embed
            c_embed.add_field(name="Message", value=f"`{message}`", inline=False)

        await ctx.followup.send(embed=c_embed) # Send the embed to the user
        c_embed.title = "Circular Notification"
        c_embed.description = "I will now remind when a circular is available, in this channel!"
        await channel.send(embed=c_embed)




    @admin.command(name="delete", description="Delete the server's circular reminder configuration.")
    async def delete(self, ctx):
        await ctx.defer()
        log.info(f"{ctx.author.id} in {ctx.guild.id} is deleting the reminder configuration.")

        guild = await self.client.fetch_guild(ctx.guild.id) # Get the guild from the discord API
        author = await guild.fetch_member(ctx.author.id)
        if not author.guild_permissions.administrator:
            if not author.id in owner_ids:
                await ctx.followup.send(embed=discord.Embed(title="Error!", description="You do not have permission to use this command!", color=embed_color))
                return

        self.cur.execute(f"SELECT * FROM guild_notify WHERE guild_id = {ctx.guild.id}")   # Check if the guild is already in the database
        res = self.cur.fetchone()   # Get the result from the database

        if not res: # If the guild is not in the database
            e_embed = discord.Embed(title="Server Setup", description=f"The server has no reminder configuration!", color=embed_color)
            e_embed.set_author(name=embed_title)
            e_embed.set_footer(text=embed_footer)
            await ctx.followup.send(embed=e_embed)
            return

        self.cur.execute(f"DELETE FROM guild_notify WHERE guild_id = {ctx.guild.id}") # Delete the guild from the database
        self.con.commit()   # Commit the changes to the database

        d_embed = discord.Embed(title="Success!", description="The reminder has successfully been deleted.", color=embed_color)
        d_embed.set_author(name=embed_title)
        d_embed.set_footer(text=embed_footer)

        await ctx.followup.send(embed=d_embed)


    @circular.command(name="invite", description="Invite the bot to your server.")
    async def invite(self, ctx):
        embed = discord.Embed(title="Invite", description=f"Use this link to invite the bot to your server:\n https://bpsapi.rajtech.me/r/discord-bot-invite", color=embed_color)
        embed.set_author(name=embed_title)
        embed.set_footer(text=embed_footer)
        await ctx.respond(embed=embed)


    @circular.command(name="help", description="Shows the help message for the circular commands.")
    async def help(self, ctx):
        await ctx.defer()
        embed = discord.Embed(title="Circular Commands", description="Here is the list of commands for the circulars.", color=embed_color)
        embed.set_author(name=embed_title)
        embed.set_footer(text=embed_footer)
        embed.add_field(name="/circular list", value="List all circulars in a particular category.", inline=False)
        embed.add_field(name="/circular latest", value="Sends the latest circular, the download URL and a the preview of a particular category.", inline=False)
        embed.add_field(name="/circular search", value="Searches for a circular from input and gives preview and circular details", inline=False)
        embed.add_field(name="/circular admin setup", value="Set up a channel to remind in, when a new circular is posted", inline=False)
        embed.add_field(name="/circular admin delete", value="Delete the server's circular reminder configuration", inline=False)
        await ctx.followup.send(embed=embed)



    @circular.command(name="remindme", description="Subscribe to DM reminders for the latest circular.")
    async def remindme(self, ctx, message: str = None):
        await ctx.defer()

        r_embed = discord.Embed(title="", description="", color=embed_color)    # Create the embed
        r_embed.set_author(name=embed_title)
        r_embed.set_footer(text=embed_footer)

        self.cur.execute(f"SELECT * FROM dm_notify WHERE user_id = {ctx.user.id}")
        res = self.cur.fetchone()
        if res: # If the user is already in the database
            r_embed.title = "Unsubscribe"   # Set the title to Unsubscribe
            r_embed.description = "You are already subscribed to reminders. Do you want to unsubscribe?"
            button = ConfirmButton(ctx.author)

            msg = await ctx.followup.send(embed=r_embed, view=button)   # Send the embed and the button to the user
            await button.wait() # Wait for the user to click the button

            if button.value is None:  # Timeout
                await ctx.followup.send("Timed out.")
                return

            elif not button.value:  # Cancel
                await ctx.followup.send("Cancelled.")
                return

            self.cur.execute(f"DELETE FROM dm_notify WHERE user_id = {ctx.user.id}")    # Delete the user from the database
            self.con.commit()   # Commit the changes to the database

            r_embed.title = "Unsubscribed"
            r_embed.description = "You have been unsubscribed from reminders."
            log.info(f"{ctx.author.id} in {ctx.guild.id} is un-subscribing from DM reminders.")
            await msg.edit(embed=r_embed)   # Edit the message to show that the user has been unsubscribed
            return

        if message: # If the message is not None, add the message to the embed
            message = message.replace("<", "").replace(">", "").replace('"', "")    # Remove the <, > and " from the message
            self.cur.execute(f"INSERT INTO dm_notify (user_id, message) VALUES ({ctx.user.id}, '{message}');")  # Add the user to the database
        else:   # If the message is None, add the default message to the embed
            self.cur.execute(f"INSERT INTO dm_notify (user_id) VALUES ({ctx.user.id});")
        self.con.commit()

        r_embed.title = "Success!"
        log.info(f"{ctx.author.id} in {ctx.guild.id} is subscribing to DM reminders.")
        r_embed.description = "You successfully subscribed to DM reminders! `/circular remindme` to unsubscribe."

        await ctx.followup.send(embed=r_embed)




def setup(client):
    client.add_cog(Commands(client))