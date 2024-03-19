import math
import sqlite3
import discord
import time
import discord.ext.pages
from discord.ext import commands
from backend import get_circular_list, console, embed_color, embed_footer, embed_title, categories, get_png, \
    search, owner_ids, DeleteButton, ConfirmButton, get_latest_circular, log, embed_url, FeedbackButton, \
    ignored_circulars, create_search_dropdown, discord_invite_url, invite_url
from discord import SlashCommandGroup

category_options = []
for i in categories:
    category_options.append(discord.OptionChoice(i.capitalize().strip(), value=i.strip().lower()))

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
        console.debug(category)

        if category != "all":
            raw_res = await get_circular_list(category)
        else:
            raw_res = []

            for cat in categories:  # TODO make this faster
                raw_res += await get_circular_list(cat)

            # Sort it based on circular ID
            raw_res.sort(key=lambda x: x['id'], reverse=True)

        # Remove ignored_circulars from the list
        raw_res = [i for i in raw_res if i['id'] not in ignored_circulars]

        # If there are no circulars
        if raw_res is None or raw_res == []:
            console.error(f"Got an empty list of circulars from the API. raw_less was None or []")
            await ctx.respond("There was a bit of an issue on our end. Please try again later.")

        page_list = []
        titles = []
        links = []

        loop_int = 1  # The variable which will be used to add numbers into the embed

        # Loop through the raw API output
        for item in raw_res:
            titles.append(f"**{loop_int}**. [{item['id']}]  `{item['title'].strip()}`")
            links.append(f"{item['link']}")
            loop_int += 1

        embed = discord.Embed(color=embed_color)
        if category != "all":
            embed.title = f"Circular List | `{category.capitalize()}`"
        else:
            embed.title = "Circular List | All Categories"

        embed.set_footer(text=embed_footer)
        embed.set_author(name=embed_title)

        count = 0

        for title, link in zip(titles, links):
            embed.add_field(name=title, value=link, inline=False) 
            count += 1

            # If the embed has reached 10 pages
            if count % 10 == 0:
                console.debug(f"[Commands] | {count}")
                embed.description = f"Format - `[ID] Circular Title`\nPage **{int(count / 10)}**\n"

                # Save the current embed to a list
                page_list.append(embed.copy())
                embed.clear_fields()

            # If this is the last, unfilled page
            elif count == len(titles):
                console.debug(f"[Commands] | {count}")
                embed.description = f"Format - `[ID] Circular Title`\nPage **{int(math.ceil(count / 10))}**\n"

                # Save the current embed to a list
                page_list.append(embed.copy())
                embed.clear_fields()

        # Remove the last embed of the list if it is empty
        if len(page_list[-1].fields) == 0:
            page_list.pop()

        # Give 20 seconds timeout per page (minimum timeout is 60 seconds)
        if (timeout := int(count / 10) * 20) < 60:
            timeout = 60

        paginator = discord.ext.pages.Paginator(
            pages=page_list, disable_on_timeout=True, timeout=timeout
        )
        await paginator.respond(ctx.interaction)
        console.debug(f"[Commands] | Search took {round(time.time() - start, 2)} seconds.")

    # TODO reaplce choices= with category_options_with_all 
    @circular.command(name="latest", description="Sends the latest circular in a particular category.")
    async def latest(self, ctx, category: discord.Option(choices=category_options)):
        await ctx.defer()
        start = time.time()

        author = await self.client.fetch_user(ctx.author.id)

        # Get the latest circular from the API
        raw_res = await get_latest_circular(category)
        title = raw_res['title']
        link = raw_res['link']
        id_ = raw_res['id']

        embed = discord.Embed(title=f"Latest Circular | {category.capitalize()}", color=embed_color, url=embed_url)
        embed.set_author(name=embed_title)
        embed.set_footer(text=embed_footer)
        embed.add_field(name="Title", value=f"`{title}`", inline=False)
        embed.add_field(name="Circular ID", value=f"`{id_}`", inline=False)
        embed.add_field(name="Download URL", value=link, inline=False)

        # Get the circular image and add it to the embed
        png_url = list(await get_png(link))
        embed.set_image(url=png_url[0])

        embed.description = f"Search took {round(time.time() - start, 2)} second(s). Requested by {author.mention}"
        embed_list = [embed]

        # If there is more than one page, create an embed with each page to create a image gallery 
        if len(png_url) != 1:
            for i in range(len(png_url)):
                # First page is there in main embed
                if i == 0:
                    continue
                # Only four pages max are supposed in a gallery
                if i > 3:
                    embed.add_field(
                        name="Note",
                        value=f"This circular has {len(png_url) - 4} more pages. Please visit the [link]({link}) to view them.",
                        inline=False
                    )
                    break

                _embed = discord.Embed(url=embed_url)
                _embed.set_image(url=png_url[i])
                embed_list.append(_embed.copy())

        # This part adds a .pdf file to the message
        # async with aiohttp.ClientSession() as session:  # creates session
        #     async with session.get(link) as resp:  # gets image from url
        #         img = await resp.read()  # reads image from response
        #         with io.BytesIO(img) as file:  # converts to file-like object
        #             file = discord.File(file, filename=f"{id_}.pdf")

        try:
            msg = await ctx.followup.send(embeds=embed_list)
        except discord.Forbidden:
            try:
                msg = await author.send(embeds=embed_list)
            except discord.Forbidden:
                console.warning(f"[Commands] | {author} has DMs disabled and can't respond to the command.")
                return
        await msg.edit(embeds=embed_list, view=DeleteButton(msg, author.id))

        console.debug(f"[Commands] | Search took {round(time.time() - start, 2)} second(s).")

    @circular.command(name="search", description="Searches for a circular with a title or id.")
    async def search(self, ctx, query: str):
        await ctx.defer()
        start = time.time()

        # Get the author object
        msg = None
        author = await self.client.fetch_user(ctx.author.id)

        # Create the embed
        embed = discord.Embed(title="Circular Search", color=embed_color, url=embed_url)
        embed.set_author(name=embed_title)
        embed.set_footer(text=embed_footer)

        # Search for the circular through the API
        searched: tuple | None = await search(query, amount=5)

        # If no circular is found
        if not searched:
            embed.add_field(
                name="Error",
                value="No circular found with that title or id. Maybe specify better search terms, "
                        "or find the circular you wanted from </circular list:1010911588703817808>.",
                inline=False
            )
            embed.color = discord.Color.red()

            await ctx.followup.send(embed=embed)
            return

        end = time.time()

        # If more than one result is found
        if len(searched) > 1:
            _embed = embed.copy()
            _embed.description = f"Select the circular you want to view using the dropdown. Requested by {author.mention}."

            options = [
                discord.SelectOption(
                    label=f"Circular ID: {i['id']}",
                    description=f"{i['title']}"
                ) for i in searched
            ]

            # Send the message with dropdown
            msg = await ctx.followup.send(embed=_embed)
            dropdown = await create_search_dropdown(options, msg, user_id=author.id)
            await msg.edit(embed=_embed, view=dropdown)

            # wait for the user to select an option
            await dropdown.wait()

            # If timeout occurs
            if dropdown.value is None:
                return

            circular_id = dropdown.value

            # circular_id is the circular id, find the circular from the id
            searched: dict = [i for i in searched if i['id'] == circular_id][0]

        # If only one result is found (perhaps the user searched by id)
        elif len(searched) == 1:
            searched: dict = searched[0]

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

        await msg.edit(embeds=embed_list, view=FeedbackButton(msg, author, query, searched))
        console.debug(f"[Commands] | Search took {round(time.time() - start, 2)} seconds.")

    # Admin commands
    @admin.command(
        name="setup",
        description="Set up the bot to notify when a new circular is posted.",
        guild_only=True
    )
    async def server_setup(self, ctx, channel: discord.TextChannel, message: str = None):
        await ctx.defer()

        # Make sure that this command is bring run in a guild
        try:
            guild = await self.client.fetch_guild(ctx.guild.id)
        except discord.NotFound:
            return await ctx.followup.send("You need to be in a server to use this command.")

        author = await guild.fetch_member(ctx.author.id)

        if not author.guild_permissions.manage_guild:  # Check if the author has admin permissions
            if author.id not in owner_ids:  # Check if the author is an owner
                await ctx.followup.send(
                    embed=discord.Embed(
                        title="Error!", 
                        description="You do not have permission to use this command!",
                        color=embed_color
                    )
                )
                return

        self.cur.execute("SELECT * FROM guild_notify WHERE guild_id = ?", (guild.id,))
        res = self.cur.fetchone()

        # If a channel is already set up
        if res:
            console.debug('[Commands] | ' + res)
            embed = discord.Embed(
                title="Server Setup",
                description=f"The server already has a notification configuration.",
                color=discord.Color.red()
                )
            embed.set_author(name=embed_title)
            embed.set_footer(text=embed_footer)
            embed.add_field(name="In Channel", value=f"<#{res[1]}>", inline=False)
            embed.add_field(
                name="To delete:",
                value=f"Use </circular admin delete:1010911588703817808> to delete this existing configuration!",
                inline=False
            )
            await ctx.followup.send(embed=embed)
            return

        if message:
            message = message.replace("<", "").replace(">", "").replace('"', "")  # Remove the <> and " from the message
            self.cur.execute(
                "INSERT INTO guild_notify (guild_id, channel_id, message) "
                "VALUES (?, ?, ?)", 
                (guild.id, channel.id, message)
                )

        else:
            self.cur.execute("INSERT INTO guild_notify (guild_id, channel_id) VALUES (?, ?)", (guild.id, channel.id))

        self.con.commit()

        embed = discord.Embed(
            title="Circular Notification Setup",
            description="I'll send a notification in this channel on a new circular being posted!",
            color=embed_color
        )
        embed.set_author(name=embed_title)
        embed.set_footer(text=embed_footer)

        if message:  # If the message is not None, add the message to the embed
            embed.add_field(name="Message", value=f"`{message}`", inline=False)

        try:
            await channel.send(embed=embed)

            embed.title = "Success!"
            embed.description = "The notification configuration for this server has successfully been added!"
            embed.add_field(name="Channel", value=f"{channel.mention}", inline=False)

            await ctx.followup.send(embed=embed)

        except discord.Forbidden:
            error_embed = discord.Embed(title="Error!", color=discord.Color.red(), url=embed_url)
            error_embed.set_footer(text=embed_footer)
            error_embed.description = f"I do not have permission to send messages in that channel! (<#{channel.id}>).\n" \
                                      f"Please give me permission to do so or set another channel."
            await ctx.followup.send(embed=error_embed)

            self.cur.execute(f"DELETE FROM guild_notify WHERE guild_id = ?", (guild.id,))
            return

    @admin.command(name="delete", description="Delete the server's circular notification configuration.")
    async def setup_delete(self, ctx):
        await ctx.defer()

        # Make sure that this command is being run in a guild
        try:
            guild = await self.client.fetch_guild(ctx.guild.id)
        except discord.NotFound:
            return await ctx.followup.send("You need to be in a server to use this command.")

        author = await guild.fetch_member(ctx.author.id)

        # Check if the user is a bot owner/has required permissions
        if not author.guild_permissions.manage_guild:
            if author.id not in owner_ids:
                return await ctx.followup.send(
                    embed=discord.Embed(
                        title="Error!",
                        description="You do not have permission to use this command!",
                        color=discord.Color.red(),
                    ).set_footer(text=embed_footer)
                )

        # Check if the guild is in the database
        self.cur.execute("SELECT * FROM guild_notify WHERE guild_id = ?", (guild.id,))
        res = self.cur.fetchone()

        if not res:
            embed = discord.Embed(
                title="Server Setup",
                description=f"The server has no existing notification configuration.", 
                color=embed_color
            )
            embed.set_author(name=embed_title)
            embed.set_footer(text=embed_footer)
            await ctx.followup.send(embed=embed)
            return

        self.cur.execute("DELETE FROM guild_notify WHERE guild_id = ?", (ctx.guild.id,))
        self.con.commit()  # Commit the changes to the database

        embed = discord.Embed(
            title="Success!",
            description="The configuration has successfully been deleted.", 
            color=embed_color
        )
        embed.set_author(name=embed_title)
        embed.set_footer(text=embed_footer)

        await ctx.followup.send(embed=embed)

    @commands.slash_command(name="invite", description="Get the invite link for the bot.")
    @circular.command(name="invite", description="Invite the bot to your server.")
    async def invite(self, ctx):
        embed = discord.Embed(
            title="Invite",
            description=f"Click the below button to add the bot to your server. "
                        f"Alternatively you can use this URL too.\n{invite_url}",
            color=embed_color
        )
        embed.set_author(name=embed_title)
        embed.set_footer(text=embed_footer)

        class InviteButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    label="Invite",
                    url=discord_invite_url,
                    style=discord.ButtonStyle.link
                )

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

    @circular.command(name="notifyme", description="Subscribe to DM notifications for new circulars")
    async def notifyme(self, ctx, message: str = None):
        await ctx.defer()

        embed = discord.Embed(title="", description="", color=embed_color)
        embed.set_author(name=embed_title)
        embed.set_footer(text=embed_footer)

        self.cur.execute("SELECT * FROM dm_notify WHERE user_id = ?", (ctx.author.id,))
        res = self.cur.fetchone()

        # If the user is already in the database => they are unsubscribing
        if res:  
            embed.title = "Unsubscribe"
            embed.description = "You are already subscribed to notifications. Do you want to unsubscribe?"

            # Send the embed and the confirmation button
            button = ConfirmButton(ctx.author.id)
            msg = await ctx.followup.send(embed=embed, view=button)
            await button.wait()

            if button.value is None:  # Timeout
                return

            elif not button.value:  # Cancel
                await ctx.followup.send("Cancelled.")
                return

            # Remove the user from the database
            self.cur.execute("DELETE FROM dm_notify WHERE user_id = ?", (ctx.author.id,))
            self.con.commit()

            embed.title = "Success!"
            embed.description = "You unsubscribed from notifications."
            await msg.edit(embed=embed, view=None)
            return


        # If the user is not there in the database => they are subscribing
        # Add them to the database
        if message:
            message = message.replace("<", "").replace(">", "").replace('"', "")
            self.cur.execute("INSERT INTO dm_notify (user_id, message) VALUES (?, ?)", (ctx.author.id, message))
        else:
            self.cur.execute("INSERT INTO dm_notify (user_id) VALUES (?)", (ctx.author.id,))
        self.con.commit()

        embed.title = "Success!"  # Set the title to Success
        embed.description = "You successfully subscribed to DM notifications! " \
                              "</circular notifyme:1010911588703817808> to unsubscribe."

        try:  # Try to send the user a DM
            await ctx.author.send(embed=embed)
            await ctx.followup.send(embed=embed)

        except discord.Forbidden:  # If the user has DMs disabled
            embed.description = "Error: I couldn't send you a DM. Please enable DMs from server members."
            embed.color = discord.Color.red()
            await ctx.followup.send(embed=embed)

def setup(client):
    client.add_cog(Commands(client))
