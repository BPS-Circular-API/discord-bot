import discord
import math
import sqlite3
from discord.ext import commands
from backend import owner_ids, embed_title, embed_footer, embed_color, console, owner_guilds, get_png, ConfirmButton, \
    DeleteButton, log, search, embed_url, send_to_guilds, send_to_users, categories

category_options = []
for i in categories:
    category_options.append(discord.OptionChoice(i.capitalize().strip(), value=i.strip().lower()))
del categories


class Owners(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.con = sqlite3.connect('./data/data.db')
        self.cur = self.con.cursor()

    owners = discord.SlashCommandGroup("owners", "Bot owner commands.", guild_ids=owner_guilds)

    @commands.Cog.listener()
    async def on_ready(self):
        console.info(f"Cog : Owners.py loaded.")

    @owners.command(name='status', description='Change the bot status.')
    async def status(self, ctx, status: str, message: str):
        if ctx.author.id not in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")
        
        match status:
            case 'playing':
                await self.client.change_presence(activity=discord.Game(name=message))
            case 'streaming':
                await self.client.change_presence(activity=discord.Streaming(name=message, url='https://twitch.tv/'))
            case 'listening':
                await self.client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening,
                                                                            name=message))
            case 'watching':
                await self.client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,
                                                                            name=message))
            # TODO: stop the status changer loop

        await ctx.respond("Status changed.")

    @owners.command(name='reload', description='Reload a cog.')
    async def reload(self, ctx, cog: str):
        if ctx.author.id not in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")

        self.client.unload_extension(f"cogs.{cog}")
        self.client.load_extension(f"cogs.{cog}")
        await ctx.respond(f"Reloaded {cog}.")

    @owners.command(name="execsql", description="Execute a SQL query.")
    async def execsql(self, ctx, query):
        if ctx.author.id not in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")
        await ctx.defer()

        try:
            self.cur.execute(query)
        except Exception as e:
            await ctx.followup.send(embed=discord.Embed(title="Execute SQL", description=f"**Error!**\n{e}",
                                                        color=discord.colour.Color.red()).set_footer(
                text=embed_footer).set_author(name=embed_title), ephemeral=True)
            return
        
        res = self.cur.fetchall()

        if len(res) == 0:
            embed = discord.Embed(title="Execute SQL", description="**Success!**\nNo results found.",
                                  color=embed_color).set_footer(text=embed_footer).set_author(name=embed_title)
        else:
            embed = discord.Embed(title="Execute SQL", description="**Success!**\nResults found.",
                                  color=embed_color).set_footer(text=embed_footer).set_author(name=embed_title)
            
            for i in res:
                embed.add_field(name=str(i), value=str(i), inline=False)

        self.con.commit()

        msg = await ctx.followup.send(embed=embed)
        await msg.edit(embed=embed, view=DeleteButton(ctx, msg))

    @owners.command(name="servers", description="List all servers the bot is in.")
    async def servers(self, ctx):
        if ctx.author.id not in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")
        
        await ctx.defer()

        embed = discord.Embed(title="Servers", description=f"I am in `{len(self.client.guilds)}` servers!",
                              color=embed_color).set_footer(text=embed_footer).set_author(name=embed_title)
        count = 0
        page_list = []

        for i in self.client.guilds:
            guild = await self.client.fetch_guild(i.id)
            embed.add_field(name=guild.name, value=i.id, inline=False)
            count += 1

            if count % 10 == 0:  # If the count is divisible by 10 (It has reached 10 fields)
                console.debug("[Owners] | ", count)
                embed.description = f"Page {int(count / 10)}"  # Set the description of the embed
                page_list.append(embed.copy())  # Create a copy of the embed and add it to the list
                embed.clear_fields()  # Clear the fields of the embed

            elif count == len(self.client.guilds):
                console.debug("[Owners] | ", count)
                embed.description = f"Page {int(math.ceil(count / 10))}"  # Set the description of the embed
                page_list.append(embed.copy())
                embed.clear_fields()

        if len(page_list[-1].fields) == 0:
            page_list.pop()
        console.debug('[Owners] |', page_list)

        paginator = discord.ext.pages.Paginator(
            pages=page_list, disable_on_timeout=True, timeout=60
        )
        await paginator.respond(ctx.interaction, ephemeral=True)

    @owners.command(name="manualnotify", description="Notify all users in a server.")
    async def send_manual_notification(
        self, ctx, circular_name: str, url: str, id_: int, category: discord.Option(choices=category_options),
        custom_message: str = None, 
        send_only_to: discord.Option(
            choices=[
                    discord.OptionChoice("DMs", value="dms"),
                    discord.OptionChoice("Servers", value="servers"),
            ]
        ) = None,
        debug_guild: int = None, debug_user: int = None
    ):

        if ctx.author.id not in owner_ids:  # Check if the user is a bot owner
            return await ctx.respond("You are not allowed to use this command.")
        
        await ctx.defer()

        embed = discord.Embed(title=f"New Circular | **{category.capitalize()}** ", color=embed_color, url=embed_url)
        embed.set_footer(text=embed_footer)
        embed.set_author(name=embed_title)

        embed.add_field(name=f"[{id_}] `{circular_name}`", value=url, inline=False)

        if custom_message is not None:  # If the user has provided a custom message
            embed.add_field(name="Message from the Developer", value=custom_message, inline=False)

        png_url = await get_png(url)  # Get the png from the url
        embed.set_image(url=png_url[0])  # Set the image of the embed to the file

        embed_list = []
        notif_msgs = {"guild": [], "dm": []}

        if len(png_url) != 1:  # If there is more than a single page in the circular
            for i in range(len(png_url)):
                if i == 0:
                    continue
                elif i > 3:
                    embed.add_field(
                        name="Note",
                        value=f"This circular has {len(png_url) - 4} more pages. Please visit the [link]({url}) to view them.",
                        inline=False
                    )
                    break
                temp_embed = discord.Embed(url=embed_url)  # Create a new embed
                temp_embed.set_image(url=png_url[i])
                embed_list.append(temp_embed.copy())

        if debug_guild:  # If a debug guild is specified, send the message to ONLY that guild.
            self.cur.execute("SELECT message FROM guild_notify WHERE guild_id = ?", (debug_guild,))
            message = self.cur.fetchone()  # Get the reminder-message for the guild from the DB
            console.debug(f"[Owners] | Message: {message}")

            if not message:  # If the message is not found
                message[0] = "A new circular is out!"  # Set the message to the default message

            embed.description = message[0]  # Set the description of the embed to the message

            guild = await self.client.fetch_guild(int(debug_guild))  # Get the guild object
            self.cur.execute("SELECT channel_id FROM guild_notify WHERE guild_id = ?", (guild.id,))
            channel_id = self.cur.fetchone()[0]  # Get the channel_id for the guild from the DB

            channel = await guild.fetch_channel(int(channel_id))  # Get the channel object

            await channel.send(embeds=[embed.copy(), *embed_list])  # Send the embed
            return await ctx.respond(f"Notified the `{debug_guild}` server.")  # Respond to the user and return

        elif debug_user:  # If a debug user is specified, send the message to ONLY that user.
            self.cur.execute("SELECT message FROM dm_notify WHERE user_id = ?", (debug_user,))
            message = self.cur.fetchone()  # Get the reminder-message for the user from the DB
            console.debug(f"[Owners] | Message: {message}")

            if not message:
                message = "A new circular is out!"
            embed.description = message[0]  # Set the description of the embed to the message

            user = await self.client.fetch_user(int(debug_user))  # Get the user object

            await user.send(embeds=[embed.copy(), *embed_list])  # Send the embed
            return await ctx.respond(f"Notified the `{debug_user}` user.")  # Respond to the user and return

        else:
            button = ConfirmButton(ctx.author)  # Create a ConfirmButton object

            await ctx.followup.send(embeds=[embed.copy(), *embed_list], view=button)
            await button.wait()  # Wait for the user to confirm

            if button.value is None:  # Timeout
                await ctx.respond("Timed out.")
                return

            elif not button.value:  # Cancel
                await ctx.respond("Cancelled.")
                return

            self.cur.execute("SELECT * FROM guild_notify")  # Get all the guilds from the database
            guild_notify = self.cur.fetchall()

            guilds = [x[0] for x in guild_notify]  # Get all the guild_id s from the database
            channels = [x[1] for x in guild_notify]  # Get all the channel_id s from the database
            messages = [x[2] for x in guild_notify]  # Get all the messages from the database

            self.cur.execute("SELECT * FROM dm_notify")  # Get all the users from the database
            users = self.cur.fetchall()  # Get all the user_id s from the database

            user_ids = [x[0] for x in users]  # Get all the user_id s from the database
            user_messages = [x[1] for x in users]  # Get all the messages from the database
            del users, guild_notify  # Delete the variables to free up memory

            error_embed = discord.Embed(title=f"Error!",
                                        description="Please make sure that I have the permission "
                                                    "to send messages in the channel you set for notifications.",
                                        color=embed_color)
            error_embed.set_footer(text=embed_footer)
            error_embed.set_author(name=embed_title)

            match send_only_to:  # If it has been specified to send the notifications to only servers/dms
                case "dms":  # Send notifications to dms
                    await send_to_users(
                        user_ids=user_ids, user_messages=user_messages, notif_msgs=notif_msgs, embed=embed, embed_list=embed_list, id_=id_
                    )

                case "servers":  # Send notifications to servers
                    await send_to_guilds(
                        guilds=guilds, channels=channels, messages=messages, notif_msgs=notif_msgs, embed=embed,
                        embed_list=embed_list, error_embed=error_embed, id_=id_
                    )

                case _:
                    await send_to_guilds(
                        guilds=guilds, channels=channels, messages=messages, notif_msgs=notif_msgs, embed=embed,
                        embed_list=embed_list, error_embed=error_embed, id_=id_
                    )
                    await send_to_users(user_ids, user_messages, notif_msgs, embed, embed_list, id_)

            console.info(f"Sent Circular to {len(notif_msgs['dm'])} users and {len(notif_msgs['guild'])} guilds.")

    @owners.command(name="logs", description="Get bot logs.")
    async def get_logs(self, ctx,
                       level: discord.Option(choices=[
                           discord.OptionChoice("All", value="all"),
                           discord.OptionChoice("Debug", value="debug"),
                           discord.OptionChoice("Info", value="info"),
                           discord.OptionChoice("Warning", value="warning"),
                           discord.OptionChoice("Error", value="error"),
                           discord.OptionChoice("Critical", value="critical")
                       ]),

                       category: discord.Option(choices=[
                           discord.OptionChoice("All", value="all"),
                           discord.OptionChoice("Command", value="command"),
                           discord.OptionChoice("Listener", value="listener"),
                           discord.OptionChoice("Backend", value="backend"),
                           discord.OptionChoice("Etc", value="etc")
                       ]),
                       amount: int):

        if ctx.author.id not in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")
        await ctx.defer()

        if level == "all":
            level = None

        if category == "all":
            category = None

        # get logs from sql
        if level is None and category is None:
            self.cur.execute("SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?", (amount,))
        elif level is None:
            self.cur.execute("SELECT * FROM logs WHERE category = ? ORDER BY timestamp DESC LIMIT ?",
                             (category, amount))
        elif category is None:
            self.cur.execute("SELECT * FROM logs WHERE log_level = ? ORDER BY timestamp DESC LIMIT ?",
                             (level, amount))
        else:
            self.cur.execute("SELECT * FROM logs WHERE log_level = ? AND category = ? ORDER BY timestamp DESC LIMIT ?",
                             (level, category, amount))

        logs = self.cur.fetchall()

        if not logs:
            return await ctx.respond("No logs found.", ephemeral=True)

        embed = discord.Embed(title="Logs", color=embed_color)
        embed.set_footer(text=embed_footer)
        embed.set_author(name=embed_title)

        pages = []
        i = 1
        # Log format: (timestamp, log_level, category, message)
        for _log in logs:
            embed.add_field(name=f"**{i}** <t:{_log[0]}:f>", value=f"```{_log[3]}```", inline=False)
            i += 1

            if i % 10 == 0:
                pages.append(embed.copy())
                embed.clear_fields()
            elif i == len(logs):
                pages.append(embed.copy())
                embed.clear_fields()

        # send paginated logs
        paginator = discord.ext.pages.Paginator(
            pages=pages, disable_on_timeout=True, timeout=120
        )
        await paginator.respond(ctx.interaction, ephemeral=True)

    @owners.command(name="setmessage", description="Set a message for the next circular embed.")
    async def set_message(self, ctx, message: str):
        if ctx.author.id not in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")
        await ctx.defer()

        self.cur.execute("SELECT * FROM cache where title = 'circular_message'")
        circular_message = self.cur.fetchone()

        if circular_message is None:
            self.cur.execute("INSERT INTO cache VALUES ('circular_message', 'None', ?)", (message,))
        else:
            self.cur.execute("UPDATE cache SET data = ? WHERE title = 'circular_message'", (message,))
        self.con.commit()

        await ctx.respond("Successfully set the message for the next circular embed.")

    @owners.command(name="editnotif", description="Edit a notification message.")
    async def edit_notif(self, ctx, id_: int,
                         update_type: discord.Option(choices=[
                             discord.OptionChoice("Reload Image", value="image"),
                             discord.OptionChoice("Delete", value="delete"),
                             discord.OptionChoice("Set Dev Message", value="dev_message")
                         ]),
                         dev_message: str = None
                         ):

        if ctx.author.id not in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")
        await ctx.defer()

        msg_list = []

        # Get the message ids of the circular embeds
        self.cur.execute("SELECT msg_id, channel_id FROM notif_msgs WHERE circular_id = ? AND type = 'dm'", (id_,))
        dm_msgs = self.cur.fetchall()
        self.cur.execute("SELECT msg_id, channel_id, guild_id FROM notif_msgs WHERE circular_id = ? AND type = 'guild'",
                         (id_,))
        guild_msgs = self.cur.fetchall()

        for msg in dm_msgs:
            try:
                user = await self.client.fetch_user(msg[1])
                message = await user.fetch_message(msg[0])
                msg_list.append(message)

            except discord.NotFound:
                console.warning(f"Could not find DM message with id {msg[0]}")
                self.cur.execute("DELETE FROM notif_msgs WHERE circular_id = ? AND msg_id = ?", (id_, msg[0]))
                self.con.commit()
                continue

            except discord.Forbidden:
                console.warning(f"Could not fetch DM message with id {msg[0]}")
                self.cur.execute("DELETE FROM notif_msgs WHERE circular_id = ? AND msg_id = ?", (id_, msg[0]))
                self.con.commit()
                continue

            except Exception as e:
                console.error(f"Could not fetch DM message with id {msg[0]}")
                console.error(e)
                continue

        for msg in guild_msgs:
            try:
                guild = await self.client.fetch_guild(msg[2])
                channel = await guild.fetch_channel(msg[1])
                message = discord.utils.get(await channel.history(limit=100).flatten(), id=msg[0])
                msg_list.append(message)

            except discord.NotFound:
                console.warning(f"Could not find guild message with id {msg[0]}")
                self.cur.execute("DELETE FROM notif_msgs WHERE circular_id = ? AND msg_id = ?", (id_, msg[0]))
                continue

        match update_type:
            case "image":

                for msg in msg_list:
                    current_embed = msg.embeds[0]
                    embed_list = []

                    data = await search(id_)
                    png = await get_png(data['link'])

                    if png is None:
                        await ctx.respond("Error, png is None")
                        return

                    current_embed.set_image(url=png[0])

                    if len(png) != 1:
                        for i in range(png):
                            if i == 0:
                                continue
                            if i > 3:
                                break

                            temp_embed = discord.Embed(url=embed_url)
                            temp_embed.set_image(url=png[i])
                            embed_list.append(temp_embed.copy())

                    await msg.edit(embeds=[current_embed, *embed_list])

            case "delete":
                for msg in msg_list:
                    await msg.delete()
                self.cur.execute("DELETE FROM notif_msgs WHERE circular_id = ?", (id_,))
                self.con.commit()

            case "dev_message":
                for msg in msg_list:
                    current_embed = msg.embeds[0]
                    current_embed.add_field(name="Dev Message", value=dev_message)
                    await msg.edit(embed=current_embed)

        await ctx.respond("Successfully updated the messages.")

    @owners.command()
    async def send_msg(self, ctx, user_id: str, msg: str):
        if ctx.author.id not in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")
        await ctx.defer()

        user = await self.client.fetch_user(int(user_id))
        embed_ = discord.Embed(title="Message from the Developer", description=msg.replace(" nl ", "\n"))
        embed_.set_footer(text=embed_footer)
        await user.send(embed=embed_)
        await ctx.respond("Successfully sent the message.")


def setup(client):
    client.add_cog(Owners(client))
