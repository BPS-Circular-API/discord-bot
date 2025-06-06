import discord
import math
from discord.ext import commands
from backend import owner_ids, embed_title, embed_footer, embed_color, console, owner_guilds, get_png, ConfirmButton, \
    DeleteButton, search, embed_url, send_to_guilds, send_to_users, categories, get_db, multi_page_embed_generator

category_options = []
for i in categories:
    category_options.append(discord.OptionChoice(i.capitalize().strip(), value=i.strip().lower()))
del categories


class Owners(commands.Cog):
    def __init__(self, client):
        self.client = client

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

        con, cur = get_db()

        try:
            cur.execute(query)
        except Exception as e:
            await ctx.followup.send(embed=discord.Embed(title="Execute SQL", description=f"**Error!**\n{e}",
                                                        color=discord.colour.Color.red()).set_footer(
                text=embed_footer).set_author(name=embed_title), ephemeral=True)
            return

        res = cur.fetchall()

        if len(res) == 0:
            embed = discord.Embed(title="Execute SQL", description="**Success!**\nNo results found.",
                                  color=embed_color).set_footer(text=embed_footer).set_author(name=embed_title)
        else:
            embed = discord.Embed(title="Execute SQL", description="**Success!**\nResults found.",
                                  color=embed_color).set_footer(text=embed_footer).set_author(name=embed_title)

            for i in res:
                embed.add_field(name=str(i), value=str(i), inline=False)

        con.commit()

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
            debug_guild: str = None, debug_user: str = None
    ):

        if ctx.author.id not in owner_ids:  # Check if the user is a bot owner
            return await ctx.respond("You are not allowed to use this command.")

        await ctx.defer()
        con, cur = get_db()

        embed = discord.Embed(title=f"New Circular | **{category.capitalize()}** ", color=embed_color, url=embed_url)
        embed.set_footer(text=embed_footer)
        embed.set_author(name=embed_title)

        embed.add_field(name=f"[{id_}] `{circular_name}`", value=url, inline=False)

        if custom_message is not None:  # If the user has provided a custom message
            embed.add_field(name="Message from the Developer", value=custom_message, inline=False)

        png_urls = await get_png(url)  # Get the png from the url
        embed.set_image(url=png_urls[0])  # Set the image of the embed to the file

        notif_msgs = {"guild": [], "dm": []}
        embed_list = multi_page_embed_generator(png_urls=png_urls, embed=embed, link=url)

        if debug_guild:  # If a debug guild is specified, send the message to ONLY that guild.
            cur.execute("SELECT message FROM guild_notify WHERE guild_id = ?", (debug_guild,))
            message = cur.fetchone()  # Get the reminder-message for the guild from the DB
            console.debug(f"[Owners] | Message: {message}")

            if not message:  # If the message is not found
                message[0] = "A new circular is out!"  # Set the message to the default message

            embed.description = message[0]  # Set the description of the embed to the message

            guild = await self.client.fetch_guild(int(debug_guild))  # Get the guild object
            cur.execute("SELECT channel_id FROM guild_notify WHERE guild_id = ?", (guild.id,))
            channel_id = cur.fetchone()[0]  # Get the channel_id for the guild from the DB

            channel = await guild.fetch_channel(int(channel_id))  # Get the channel object

            await channel.send(embeds=embed_list)  # Send the embed
            return await ctx.respond(f"Notified the `{debug_guild}` server.")  # Respond to the user and return

        elif debug_user:  # If a debug user is specified, send the message to ONLY that user.
            cur.execute("SELECT message FROM dm_notify WHERE user_id = ?", (debug_user,))
            message = cur.fetchone()  # Get the reminder-message for the user from the DB
            console.debug(f"[Owners] | Message: {message}")

            if not message:
                message = "A new circular is out!"
            embed.description = message[0]  # Set the description of the embed to the message

            user = await self.client.fetch_user(int(debug_user))  # Get the user object

            await user.send(embeds=embed_list)  # Send the embed
            return await ctx.respond(f"Notified the `{debug_user}` user.")  # Respond to the user and return

        else:   # TODO this button is not for you
            button = ConfirmButton(ctx.author.id)  # Create a ConfirmButton object

            await ctx.followup.send(embeds=embed_list, view=button)
            await button.wait()  # Wait for the user to confirm

            if button.value is None:  # Timeout
                await ctx.respond("Timed out.")
                return

            elif not button.value:  # Cancel
                await ctx.respond("Cancelled.")
                return

            cur.execute("SELECT * FROM guild_notify")  # Get all the guilds from the database
            guild_notify = cur.fetchall()

            guilds = [x[0] for x in guild_notify]  # Get all the guild_id s from the database
            channels = [x[1] for x in guild_notify]  # Get all the channel_id s from the database
            messages = [x[2] for x in guild_notify]  # Get all the messages from the database

            cur.execute("SELECT * FROM dm_notify")  # Get all the users from the database
            users = cur.fetchall()  # Get all the user_id s from the database

            user_ids = [x[0] for x in users]
            user_messages = [x[1] for x in users]
            del users, guild_notify

            error_embed = discord.Embed(title=f"Error!",
                                        description="Please make sure that I have the permission "
                                                    "to send messages in the channel you set for notifications.",
                                        color=embed_color)
            error_embed.set_footer(text=embed_footer)
            error_embed.set_author(name=embed_title)

            match send_only_to:  # If it has been specified to send the notifications to only servers/dms
                case "dms":  # Send notifications to dms
                    await send_to_users(
                        user_ids=user_ids, user_messages=user_messages, notif_msgs=notif_msgs,
                        embed_list=embed_list, id_=id_
                    )

                case "servers":  # Send notifications to servers
                    await send_to_guilds(
                        guilds=guilds, channels=channels, messages=messages, notif_msgs=notif_msgs,
                        embed_list=embed_list, error_embed=error_embed, id_=id_
                    )

                case _:
                    await send_to_guilds(
                        guilds=guilds, channels=channels, messages=messages, notif_msgs=notif_msgs,
                        embed_list=embed_list, error_embed=error_embed, id_=id_
                    )
                    await send_to_users(
                        user_ids=user_ids, user_messages=user_messages, notif_msgs=notif_msgs,
                        embed_list=embed_list, id_=id_
                    )

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
        con, cur = get_db()

        if level == "all":
            level = None

        if category == "all":
            category = None

        # get logs from sql
        if level is None and category is None:
            cur.execute("SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?", (amount,))
        elif level is None:
            cur.execute("SELECT * FROM logs WHERE category = ? ORDER BY timestamp DESC LIMIT ?",
                             (category, amount))
        elif category is None:
            cur.execute("SELECT * FROM logs WHERE log_level = ? ORDER BY timestamp DESC LIMIT ?",
                             (level, amount))
        else:
            cur.execute("SELECT * FROM logs WHERE log_level = ? AND category = ? ORDER BY timestamp DESC LIMIT ?",
                             (level, category, amount))

        logs = cur.fetchall()

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
        con, cur = get_db()

        # Get the message ids of the circular embeds
        cur.execute("SELECT msg_id, channel_id FROM notif_msgs WHERE circular_id = ? AND type = 'dm'", (id_,))
        dm_msgs = cur.fetchall()
        cur.execute("SELECT msg_id, channel_id, guild_id FROM notif_msgs WHERE circular_id = ? AND type = 'guild'",
                         (id_,))
        guild_msgs = cur.fetchall()

        for msg in dm_msgs:
            try:
                user = await self.client.fetch_user(msg[1])
                message = await user.fetch_message(msg[0])
                msg_list.append(message)

            except discord.NotFound:
                console.warning(f"Could not find DM message with id {msg[0]}")
                cur.execute("DELETE FROM notif_msgs WHERE circular_id = ? AND msg_id = ?", (id_, msg[0]))
                con.commit()
                continue

            except discord.Forbidden:
                console.warning(f"Could not fetch DM message with id {msg[0]}")
                cur.execute("DELETE FROM notif_msgs WHERE circular_id = ? AND msg_id = ?", (id_, msg[0]))
                con.commit()
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
                cur.execute("DELETE FROM notif_msgs WHERE circular_id = ? AND msg_id = ?", (id_, msg[0]))
                continue

        match update_type:
            case "image":
                await ctx.respond("Updating images...")
                counter = 0

                circular_obj = (await search(id_))[0]
                png = await get_png(circular_obj['link'])

                embed_list = multi_page_embed_generator(png_urls=png, embed=msg_list[0].embeds[0], link=circular_obj['link'])

                # For each notification message that was sent
                for msg in msg_list:

                    # Modify all embeds to have the correct description
                    # TODO it might be possible to set each embed's description to a variable and modify that variable only
                    for embed in embed_list:
                        embed.description = msg.embeds[0].description

                    await msg.edit(embeds=embed_list)

                    counter += 1
                    if counter % 10 == 0:
                        await ctx.response.edit_original_message(f"Updating images... {counter}/{len(msg_list)}")

                await ctx.response.edit_original_message(f"Successfully updated {len(msg_list)} messages.")
                return

            case "delete":
                for msg in msg_list:
                    await msg.delete()
                cur.execute("DELETE FROM notif_msgs WHERE circular_id = ?", (id_,))
                con.commit()

            case "dev_message":
                for msg in msg_list:
                    current_embed = msg.embeds[0]
                    current_embed.add_field(name="Dev Message", value=dev_message)
                    await msg.edit(embed=current_embed)

        await ctx.respond(f"Successfully updated {len(msg_list)} messages.")



    #@owners.command(name="deletenotif", description="Edit a notification message.")
    async def delete_notif(self, ctx, id_: int,
                         delete_from: discord.Option(choices=[
                             discord.OptionChoice("Server", value="server"),
                             discord.OptionChoice("DM", value="dm"),

                         ]) = None,
                         most_recent_x: int = None,
                         ):

        if ctx.author.id not in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")
        await ctx.defer()

        msg_list = []
        con, cur = get_db()

        # Get the message ids of the circular embeds
        cur.execute("SELECT msg_id, channel_id FROM notif_msgs WHERE circular_id = ? AND type = 'dm'", (id_,))
        dm_msgs = cur.fetchall()
        cur.execute("SELECT msg_id, channel_id, guild_id FROM notif_msgs WHERE circular_id = ? AND type = 'guild'",
                         (id_,))
        guild_msgs = cur.fetchall()

        for msg in dm_msgs:
            if delete_from == "server":
                break
            try:
                user = await self.client.fetch_user(msg[1])
                message = await user.fetch_message(msg[0])
                msg_list.append(message)

            except discord.NotFound:
                console.warning(f"Could not find DM message with id {msg[0]}")
                cur.execute("DELETE FROM notif_msgs WHERE circular_id = ? AND msg_id = ?", (id_, msg[0]))
                con.commit()
                continue

            except discord.Forbidden:
                console.warning(f"Could not fetch DM message with id {msg[0]}")
                cur.execute("DELETE FROM notif_msgs WHERE circular_id = ? AND msg_id = ?", (id_, msg[0]))
                con.commit()
                continue

            except Exception as e:
                console.error(f"Could not fetch DM message with id {msg[0]}")
                console.error(e)
                continue

        for msg in guild_msgs:
            if delete_from == "dm":
                break
            try:
                guild = await self.client.fetch_guild(msg[2])
                channel = await guild.fetch_channel(msg[1])
                message = discord.utils.get(await channel.history(limit=100).flatten(), id=msg[0])
                msg_list.append(message)

            except discord.NotFound:
                console.warning(f"Could not find guild message with id {msg[0]}")
                cur.execute("DELETE FROM notif_msgs WHERE circular_id = ? AND msg_id = ?", (id_, msg[0]))
                con.commit()
                continue

        msg_list.reverse()

        counter = 0
        for msg in msg_list:
            if most_recent_x is not None:
                if counter >= most_recent_x:
                    break
            counter += 1


            await msg.delete()
            cur.execute("DELETE FROM notif_msgs WHERE circular_id = ?", (id_,))
            con.commit()


        await ctx.respond(f"Successfully deleted {counter} messages.")

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

    @owners.command()
    async def convert_data(self, ctx, conversion: discord.Option(choices=[
        discord.OptionChoice("SQLITE -> MYSQL", value="mysql"),
        discord.OptionChoice("MYSQL -> SQLITE", value="sqlite")
    ])):
        if ctx.author.id not in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")
        await ctx.defer()

        if conversion == "mysql":
            # Convert from SQLITE3 to MYSQL
            sqlite_con, sqlite_cur = get_db('sqlite3')
            mysql_con, mysql_cur = get_db('mysql')

            # Copy all tables from SQLITE DB to MYSQL
            sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [table[0] for table in sqlite_cur.fetchall()]

            for table in tables:
                sqlite_cur.execute(f"SELECT * FROM {table};")
                data = sqlite_cur.fetchall()

                mysql_cur.execute(f"INSERT INTO {table} ")


def setup(client):
    client.add_cog(Owners(client))
