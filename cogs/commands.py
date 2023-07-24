import math
import sqlite3
import discord
import time
import discord.ext.pages
from discord.ext import commands
from backend import get_circular_list, console, embed_color, embed_footer, embed_title, categories, get_png, \
    search, owner_ids, DeleteButton, ConfirmButton, get_latest_circular, log, embed_url, FeedbackButton, \
    ignored_circulars, create_search_dropdown
from discord import SlashCommandGroup

category_options = []
for i in categories:
    category_options.append(discord.OptionChoice(i.capitalize().strip(), value=i.strip().lower()))
del categories

category_options_with_all = category_options.copy()
category_options_with_all.insert(0, discord.OptionChoice("All", value="all"))


class Commands(commands.Cog):
    def __init__(self, client):
        self.con = sqlite3.connect('./data/data.db')
        self.cur = self.con.cursor()
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        console.info("Cog : Commands.py loaded.")

    # Create slash command groups
    circular = SlashCommandGroup("circular", "Circular related commands.")
    admin = circular.create_subgroup("admin", "Admin commands for the bot.")

    @circular.command(name='list', description='List all circulars in a particular category.')
    async def list_(self, ctx, category: discord.Option(choices=category_options_with_all)):
        await ctx.defer()
        start = time.time()

        if category != "all":
            raw_res = await get_circular_list(category)  # Get the list of circulars from API
        else:
            raw_res = []

            for i in category_options:  # TODO make this faster
                raw_res += await get_circular_list(i.value)

            raw_res.sort(key=lambda x: x['id'], reverse=True)

        raw_res = [i for i in raw_res if i['id'] not in ignored_circulars]

        if raw_res is None:
            await ctx.respond("There was a bit of an issue on our end. Please try again later.")

        titles, links = [], []  # Define 2 empty lists
        loop_int = 1  # The variable which will be used to add numbers into the embed

        # Loop through the raw API output
        for item in raw_res:
            titles.append(f"**{loop_int}**. [{item['id']}]  `{item['title'].strip()}`")  # Add the title to the list
            links.append(f"{item['link']}")  # Add the link to the list
            loop_int += 1

        embed = discord.Embed(color=embed_color, title=f"Circular List | `{category.capitalize()}`")  # Create the embed
        embed.set_footer(text=embed_footer)  # Set the footer
        embed.set_author(name=embed_title)  # Set the author

        page_list = []  # Create an empty list

        count = 0
        for title, link in zip(titles, links):  # Loop through the titles and links
            embed.add_field(name=title, value=link, inline=False)  # Add a field to the embed
            count += 1
            if count % 10 == 0:  # If the count is divisible by 10 (It has reached 10 fields)
                console.debug(f"[Commands] | {count}")
                embed.description = f"Format - `[ID] Circular Title`\nPage **{int(count / 10)}**\n"
                page_list.append(embed.copy())  # Create a copy of the embed and add it to the list
                embed.clear_fields()  # Clear the fields of the embed
            elif count == len(titles):
                console.debug(f"[Commands] | {count}")
                embed.description = f"Format - `[ID] Circular Title`\nPage **{int(math.ceil(count / 10))}**\n"
                page_list.append(embed.copy())
                embed.clear_fields()

        # Remove the last element of the list if it is empty
        if len(page_list[-1].fields) == 0:
            page_list.pop()

        paginator = discord.ext.pages.Paginator(
            pages=page_list, disable_on_timeout=True, timeout=120
        )
        await paginator.respond(ctx.interaction)
        console.debug(f"[Commands] | Search took {round(time.time() - start, 2)} seconds.")

    @circular.command(name="latest", description="Sends the latest circular in a particular category.")
    async def latest(self, ctx, category: discord.Option(choices=category_options)):
        await ctx.defer()  # Defer the interaction
        start = time.time()

        author = await self.client.fetch_user(ctx.author.id)  # Fetch the user object

        raw_res = await get_latest_circular(category, cached=False)  # Get the latest circular from API
        title = raw_res['title']  # Get the title
        link = raw_res['link']  # Get the link
        id_ = raw_res['id']  # Get the id

        embed = discord.Embed(title=f"Latest Circular | {category.capitalize()}", color=embed_color, url=embed_url)
        embed.set_author(name=embed_title)  # Set the author
        embed.add_field(name="Title", value=f"`{title}`", inline=False)  # Add the title field
        embed.add_field(name="Circular ID", value=f"`{id_}`", inline=False)  # Add the id field
        embed.add_field(name="Download URL", value=link, inline=False)  # Add the download url field
        embed.set_footer(text=embed_footer)  # Set the footer

        png_url = list(await get_png(link))  # Get the png file from the download url
        embed.set_image(url=png_url[0])  # Set the image to the embed
        embed.description = f"Search took {round(time.time() - start, 2)} second(s). Requested by {author.mention}"
        embed_list = [embed]

        if len(png_url) != 1:
            for i in range(len(png_url)):
                if i == 0:
                    continue
                if i > 3:
                    break
                temp_embed = discord.Embed(url=embed_url)  # Create a new embed
                temp_embed.set_image(url=png_url[i])
                embed_list.append(temp_embed.copy())

        # This part adds a .pdf file to the message
        # async with aiohttp.ClientSession() as session:  # creates session
        #     async with session.get(link) as resp:  # gets image from url
        #         img = await resp.read()  # reads image from response
        #         with io.BytesIO(img) as file:  # converts to file-like object
        #             file = discord.File(file, filename=f"{id_}.pdf")

        msg = await ctx.followup.send(embeds=embed_list)
        await msg.edit(embeds=embed_list, view=DeleteButton(ctx, msg))

        console.debug(f"[Commands] | Search took {round(time.time() - start, 2)} second(s).")

    @circular.command(name="search", description="Searches for a circular with a title or id.")
    async def search(self, ctx, query: str):
        await ctx.defer()
        start = time.time()

        msg = None
        author = await self.client.fetch_user(ctx.author.id)  # Fetch the user object
        searched: tuple = tuple(await search(query))  # Search for the circular from the backend function

        embed = discord.Embed(title="Circular Search", color=embed_color, url=embed_url)  # Create an embed
        embed.set_author(name=embed_title)  # Set the author
        embed.set_footer(text=embed_footer)  # Set the footer

        if searched is None:
            embed.add_field(name="Error",
                            value="No circular found with that title or id. Maybe specify better search terms, "
                                  "or find the circular you wanted from </circular list:1010911588703817808>.",
                            inline=False)
            await ctx.followup.send(embed=embed)
            return

        end = time.time()

        if len(searched) > 1:
            _embed = embed.copy()
            _embed.description = f"Select the circular you want to view using the dropdown. Requested by {author.mention}."

            options = [
                discord.SelectOption(
                    label=f"Circular ID: {i['id']}",
                    description=f"{i['title']}"
                ) for i in searched
            ]

            msg = await ctx.followup.send(embed=_embed)
            dropdown = await create_search_dropdown(options, msg)
            await msg.edit(embed=_embed, view=dropdown)

            # wait for the user to select an option
            await dropdown.wait()

            if dropdown.value is None:  # Timeout
                return

            res = dropdown.value  # Get the value of the dropdown

            # res is the circular id, find the circular from the id
            for i in searched:
                if i['id'] == res:
                    searched = i
                    break

            if type(searched) == int:
                return
        elif len(searched) == 1:
            searched: dict = searched[0]
        else:
            embed.add_field(name="Error",
                            value="No circular found with that title or id. Maybe specify better search terms, "
                                  "or find the circular you wanted from </circular list:1010911588703817808>.",
                            inline=False)
            await ctx.followup.send(embed=embed)
            return

        title = searched['title']  # Get the title
        link = searched['link']  # Get the link
        id_ = searched['id']  # Get the id

        embed.add_field(name="Title", value=f"`{title}`", inline=False)
        embed.add_field(name="Circular ID", value=f"`{id_}`", inline=False)
        embed.add_field(name="Download URL", value=link, inline=False)

        png_url = await get_png(link)  # Get the png file from the download url
        embed.set_image(url=png_url[0])  # Set the image to the embed
        embed.description = f"Search took {round(end - start, 2)} seconds. Requested by {author.mention}."

        embed_list = [embed]
        console.debug(png_url)

        if len(png_url) != 1:
            for i in range(len(png_url)):
                if i == 0:
                    continue
                elif i > 3:
                    break
                temp_embed = discord.Embed(url=embed_url)  # Create a new embed
                temp_embed.set_image(url=png_url[i])
                embed_list.append(temp_embed.copy())

        if msg is None:
            msg = await ctx.followup.send(embeds=embed_list)
        else:
            await msg.edit(embeds=embed_list)

        await msg.edit(embeds=embed_list, view=FeedbackButton(msg, author, circular_title, searched))
        console.debug(f"[Commands] | Search took {round(time.time() - start, 2)} seconds.")

    # Admin commands
    @admin.command(
        name="setup",
        description="Set up the bot to notify when a new circular is posted.",
        guild_only=True
    )
    async def server_setup(self, ctx, channel: discord.TextChannel, message: str = None):
        await ctx.defer()

        try:
            guild = await self.client.fetch_guild(ctx.guild.id)  # Fetch the guild object
        except discord.NotFound:
            return await ctx.followup.send("You need to be in a server to use this command.")

        author = await guild.fetch_member(ctx.author.id)  # Fetch the member object

        if not author.guild_permissions.administrator:  # Check if the author has admin permissions
            if author.id not in owner_ids:  # Check if the author is an owner
                await ctx.followup.send(
                    embed=discord.Embed(title="Error!", description="You do not have permission to use this command!",
                                        color=embed_color)
                )
                return

        self.cur.execute("SELECT * FROM guild_notify WHERE guild_id = ?", (guild.id,))
        res = self.cur.fetchone()

        if res:  # If the guild is in the database
            console.debug('[Commands] | ', res)
            e_embed = discord.Embed(title="Server Setup",
                                    description=f"The server has an already existing notification configuration!",
                                    color=embed_color)
            e_embed.set_author(name=embed_title)
            e_embed.set_footer(text=embed_footer)
            e_embed.add_field(name="Channel", value=f"`{res[1]}`", inline=False)
            e_embed.add_field(name="Message", value=f"`{res[2]}`", inline=True)
            e_embed.add_field(name="To delete!",
                              value=f"Use </circular admin delete:1010911588703817808> "
                                    f"to delete this existing configuration!",
                              inline=False)
            await ctx.followup.send(embed=e_embed)
            return

        if message:  # If the message is not None
            message = message.replace("<", "").replace(">", "").replace('"', "")  # Remove the <> and " from the message
            self.cur.execute("INSERT INTO guild_notify (guild_id, channel_id, message) "
                             "VALUES (?, ?, ?)", (guild.id, channel.id, message))
        else:  # If the message is None
            self.cur.execute("INSERT INTO guild_notify (guild_id, channel_id) VALUES (?, ?)", (guild.id, channel.id))

        self.con.commit()  # Commit the changes to the database

        c_embed = discord.Embed(title="Circular Notification Setup!",
                                description="I'll send a notification in this channel on a new circular being posted!",
                                color=embed_color)
        c_embed.set_author(name=embed_title)
        c_embed.set_footer(text=embed_footer)

        if message:  # If the message is not None, add the message to the embed
            c_embed.add_field(name="Message", value=f"`{message}`", inline=False)

        try:
            await channel.send(embed=c_embed)

            c_embed.title = "Success!"
            c_embed.description = "The notification configuration for this server has successfully been added!"
            c_embed.add_field(name="Channel", value=f"{channel.mention}", inline=False)

            await ctx.followup.send(embed=c_embed)

        except discord.Forbidden:
            error_embed = discord.Embed(title="Error!", color=discord.Color.red(), url=embed_url)
            error_embed.set_footer(text=embed_footer)
            error_embed.description = f"I do not have permission to send messages in that channel! (<#{channel.id}>).\n" \
                                      f"Please give me permission to send messages in that channel, " \
                                      f"or use another channel."

            await ctx.followup.send(embed=error_embed)
            return

    @admin.command(name="delete", description="Delete the server's circular notification configuration.")
    async def delete(self, ctx):
        await ctx.defer()

        try:
            guild = await self.client.fetch_guild(ctx.guild.id)
        except discord.NotFound:
            return await ctx.followup.send("You need to be in a server to use this command.")
        author = await guild.fetch_member(ctx.author.id)

        if not author.guild_permissions.administrator:  # Check if the author has admin permissions
            if author.id not in owner_ids:  # Check if the author is a bot over (overridden)
                return await ctx.followup.send(
                    embed=discord.Embed(
                        title="Error!",
                        description="You do not have permission to use this command!",
                        color=embed_color,
                    ).set_footer(text=embed_footer)
                )

        # Check if the guild is in the database
        self.cur.execute("SELECT * FROM guild_notify WHERE guild_id = ?", (guild.id,))
        res = self.cur.fetchone()

        if not res:
            e_embed = discord.Embed(title="Server Setup",
                                    description=f"The server has no notification configuration!", color=embed_color)
            e_embed.set_author(name=embed_title)
            e_embed.set_footer(text=embed_footer)
            await ctx.followup.send(embed=e_embed)
            return

        self.cur.execute("DELETE FROM guild_notify WHERE guild_id = ?", (ctx.guild.id,))
        self.con.commit()  # Commit the changes to the database

        d_embed = discord.Embed(title="Success!",
                                description="The configuration has successfully been deleted.", color=embed_color)
        d_embed.set_author(name=embed_title)
        d_embed.set_footer(text=embed_footer)

        await ctx.followup.send(embed=d_embed)

    @commands.slash_command(name="invite", description="Get the invite link for the bot.")
    @circular.command(name="invite", description="Invite the bot to your server.")
    async def invite(self, ctx):
        embed = discord.Embed(title="Invite",
                              description=f"Click the below button to add the bot to your server. "
                                          f"Alternatively you can use this URL too.\n "
                                          f"https://bpsapi.rajtech.me/r/discord-bot-invite", color=embed_color)
        embed.set_author(name=embed_title)
        embed.set_footer(text=embed_footer)

        class InviteButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label="Invite",
                                 url="https://discord.com/api/oauth2/authorize?client_id="
                                     "1009533262533767258&permissions=16&scope=bot%20applications.commands",
                                 style=discord.ButtonStyle.link)

        view = discord.ui.View()
        view.add_item(InviteButton())
        await ctx.respond(embed=embed, view=view)

    @commands.slash_command(name="help", description="Shows the help menu.")
    @circular.command(name="help", description="Shows the help message for the circular commands.")
    async def help(self, ctx):
        await ctx.defer()

        embed = discord.Embed(title="Circular Commands", description="Here is the list of commands for the circulars.",
                              color=embed_color)
        embed.set_author(name=embed_title)
        embed.set_footer(text=embed_footer)
        embed.add_field(name="</circular list:1010911588703817808>",
                        value="List all circulars in a particular category.", inline=False)
        embed.add_field(name="</circular latest:1010911588703817808>",
                        value="Sends the latest circular, the download URL and a the preview of a particular category.",
                        inline=False)
        embed.add_field(name="</circular search:1010911588703817808>",
                        value="Searches for a circular from input and gives preview and circular details", inline=False)
        embed.add_field(name="</circular notifyme:1010911588703817808>",
                        value="Notify you in DMs whenever a new circular is posted.", inline=False)
        embed.add_field(name="</circular admin setup:1010911588703817808>",
                        value="Set up a channel to send a notification when a new circular is posted", inline=False)
        embed.add_field(name="</circular admin delete:1010911588703817808>",
                        value="Delete the server's circular notification configuration", inline=False)
        embed.add_field(name="</circular invite:1010911588703817808>",
                        value="Invite the bot to your server", inline=False)
        await ctx.followup.send(embed=embed)

    @circular.command(name="notifyme", description="Subscribe to DM notifications for the new circulars")
    async def notifyme(self, ctx, message: str = None):
        await ctx.defer()

        r_embed = discord.Embed(title="", description="", color=embed_color)  # Create the embed
        r_embed.set_author(name=embed_title)
        r_embed.set_footer(text=embed_footer)

        self.cur.execute("SELECT * FROM dm_notify WHERE user_id = ?", (ctx.author.id,))
        res = self.cur.fetchone()
        if res:  # If the user is already in the database
            r_embed.title = "Unsubscribe"  # Set the title to Unsubscribe
            r_embed.description = "You are already subscribed to notifications. Do you want to unsubscribe?"
            button = ConfirmButton(ctx.author)

            msg = await ctx.followup.send(embed=r_embed, view=button)  # Send the embed and the button to the user
            await button.wait()  # Wait for the user to click the button

            if button.value is None:  # Timeout
                await ctx.followup.send("Timed out.")
                return

            elif not button.value:  # Cancel
                await ctx.followup.send("Cancelled.")
                return

            self.cur.execute("DELETE FROM dm_notify WHERE user_id = ?", (ctx.author.id,))
            self.con.commit()  # Commit the changes to the database

            r_embed.title = "Unsubscribed"
            r_embed.description = "You have been unsubscribed from notifications."
            await msg.edit(embed=r_embed)  # Edit the message to show that the user has been unsubscribed
            return

        if message:  # If the message is not None, add the message to the embed
            message = message.replace("<", "").replace(">", "").replace('"', "")
            self.cur.execute("INSERT INTO dm_notify (user_id, message) VALUES (?, ?)", (ctx.author.id, message))
        else:  # If the message is None, add the default message to the embed
            self.cur.execute("INSERT INTO dm_notify (user_id) VALUES (?)", (ctx.author.id,))
        self.con.commit()

        r_embed.title = "Success!"  # Set the title to Success
        r_embed.description = "You successfully subscribed to DM notifications! " \
                              "</circular notifyme:1010911588703817808> to unsubscribe."

        try:  # Try to send the user a DM
            await ctx.author.send(embed=r_embed)  # Send the embed to the user in DMs

        except discord.Forbidden:  # If the user has DMs disabled
            r_embed.description = "Error: I couldn't send you a DM. Please enable DMs from server members."
            await ctx.followup.send(embed=r_embed)

        else:  # If the user has DMs enabled
            await ctx.followup.send(embed=r_embed)


def setup(client):
    client.add_cog(Commands(client))
