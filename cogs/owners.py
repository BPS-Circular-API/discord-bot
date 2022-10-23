import discord
import math
import sqlite3
from discord.ext import commands
from backend import owner_ids, embed_title, embed_footer, embed_color, console, owner_guilds, get_png, ConfirmButton, \
    DeleteButton, log


class Owners(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.con = sqlite3.connect('./data/data.db')
        self.cur = self.con.cursor()

    owners = discord.SlashCommandGroup("owners", "Bot owner commands.", guild_ids=owner_guilds)

    @commands.Cog.listener()
    async def on_ready(self):
        console.info(f"Cog : Owners.py loaded.")

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
    async def send_manual_notification(self, ctx, circular_name: str, url: str,
                                       category: discord.Option(choices=[
                                           discord.OptionChoice("General", value="general"),
                                           discord.OptionChoice("PTM", value="ptm"),
                                           discord.OptionChoice("Exam", value="exam")
                                       ]),
                                       custom_message: str = None,
                                       send_only_to: discord.Option(choices=[
                                           discord.OptionChoice("DMs", value="dms"),
                                           discord.OptionChoice("Servers", value="servers"),
                                       ]) = None,
                                       debug_guild=None, debug_user=None):

        if ctx.author.id not in owner_ids:  # Check if the user is a bot owner
            return await ctx.respond("You are not allowed to use this command.")
        await ctx.defer()

        embed = discord.Embed(title=f"New Circular Alert!", color=embed_color)  # Create the embed
        embed.set_footer(text=embed_footer)  # Set the footer
        embed.set_author(name=embed_title)  # Set the author

        if custom_message is not None:  # If the user has provided a custom message
            embed.add_field(name="Message from the Developer", value=custom_message, inline=False)

        embed.add_field(name=f"{category.capitalize()} | {circular_name}", value=url,
                        inline=False)  # Add the circular name and url field

        png_url = await get_png(url)  # Get the png from the url
        embed.set_image(url=png_url)  # Set the image of the embed to the file

        if debug_guild:  # If a debug guild is specified, send the message to ONLY that guild.
            self.cur.execute(  # Get the server message from the database
                f"SELECT message FROM guild_notify WHERE guild_id = {debug_guild}")
            message = self.cur.fetchone()  # Get the reminder-message for the guild from the DB
            console.debug(f"[Owners] | Message: {message}")

            if not message:  # If the message is not found
                message[0] = "A new circular is out!"  # Set the message to the default message
            embed.description = message[0]  # Set the description of the embed to the message

            guild = await self.client.fetch_guild(int(debug_guild))  # Get the guild object
            self.cur.execute(f"SELECT channel_id FROM guild_notify WHERE guild_id = {guild.id}")
            channel_id = self.cur.fetchone()[0]  # Get the channel_id for the guild from the DB

            channel = await guild.fetch_channel(int(channel_id))  # Get the channel object

            await channel.send(embed=embed)  # Send the embed
            return await ctx.respond(f"Notified the `{debug_guild}` server.")  # Respond to the user and return

        elif debug_user:  # If a debug user is specified, send the message to ONLY that user.
            self.cur.execute(f"SELECT message FROM dm_notify WHERE user_id = {debug_user}")
            message = self.cur.fetchone()  # Get the reminder-message for the user from the DB
            console.debug(f"[Owners] | Message: {message}")

            if not message:  # If the message is not found
                message = "A new circular is out!"  # Set the message to the default message
            embed.description = message[0]  # Set the description of the embed to the message

            user = await self.client.fetch_user(int(debug_user))  # Get the user object

            await user.send(embed=embed)  # Send the embed
            return await ctx.respond(f"Notified the `{debug_user}` user.")  # Respond to the user and return

        else:
            button = ConfirmButton(ctx.author)  # Create a ConfirmButton object

            await ctx.followup.send(embed=embed, view=button)  # Send the embed to the user for confirmation
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

            self.cur.execute(f"SELECT * FROM dm_notify")  # Get all the users from the database
            users = self.cur.fetchall()  # Get all the user_id s from the database

            user_id = [x[0] for x in users]  # Get all the user_id s from the database
            user_message = [x[1] for x in users]  # Get all the messages from the database
            del users, guild_notify  # Delete the variables to free up memory

            error_embed = discord.Embed(title=f"Error!",
                                        description=f"Please make sure that I have the permission to send messages in the channel you set for notifications.",
                                        color=embed_color)
            error_embed.set_footer(text=embed_footer)
            error_embed.set_author(name=embed_title)

            if send_only_to:  # If it has been specified to send the notifications to only servers/dms
                if send_only_to == "dms":  # Send notifications to dms

                    for user, message in zip(user_id, user_message):  # For each user in the database
                        user = await self.client.fetch_user(int(user))  # Get the user object

                        console.debug(f"[Owners] | Message: {message}")
                        embed.description = message  # Set the description of the embed to the message

                        try:  # Try to send the embed to the user
                            await user.send(embed=embed)  # Send the embed to the user
                            console.info(
                                f"Successfully sent Circular in DMs to {user.name}#{user.discriminator} | {user.id}")
                        except discord.Forbidden:  # If the bot is not allowed to send messages to the user
                            console.error(
                                f"Could not send Circular in DMs to {user.name}#{user.discriminator} | {user.id}")
                            # self.cur.execute(f"DELETE FROM dm_notify WHERE user_id = {user.id}")
                            # self.con.commit()

                        except Exception as e:  # If the user has DMs disabled
                            console.error(f"Couldn't send Circular Embed to User (not discord.Forbidden): {user.id}")
                            console.error(e)

                elif send_only_to == "servers":  # Send notifications to servers

                    for guild, channel, message in zip(guilds, channels, messages):  # For each guild in the database

                        console.debug(f"[Owners] | Message: {message}")
                        embed.description = message  # Set the description of the embed to the message

                        try:  # Try to send the embed to the guild
                            guild = await self.client.fetch_guild(int(guild))  # Get the guild object
                            channel = await guild.fetch_channel(int(channel))  # Get the channel object
                        except discord.NotFound:  # If the guild/channel is not found (deleted)
                            console.warning(f"Guild or channel not found. Guild: {guild}, Channel: {channel}")
                            self.cur.execute(
                                f"DELETE FROM guild_notify WHERE guild_id = {guild} AND channel_id = {channel}")  # Delete the guild from the database
                            self.con.commit()
                            continue
                        except discord.Forbidden:  # If the bot can not get the guild/channel
                            console.warning(
                                f"Could not get channel. Guild: {guild}, Channel: {channel}. Seems like I was kicked from the server.")
                            self.cur.execute(
                                f"DELETE FROM guild_notify WHERE guild_id = {guild} AND channel_id = {channel}")  # Delete the guild from the database
                            self.con.commit()
                            continue
                        except Exception as e:  # If there is some other error
                            console.error(f"Error: {e}")
                            continue

                        try:  # Try to send the message
                            await channel.send(embed=embed)  # Send the embed
                            console.info(f"Sent Circular Embed to {guild.id} | {channel.id}")

                        except discord.Forbidden:  # If the bot doesn't have permission to send messages in the channel
                            for _channel in guild.text_channels:  # Find a channel where it can send messages

                                try:  # Try to send the error embed
                                    await _channel.send(embed=error_embed)  # Send the error embed
                                    await _channel.send(embed=embed)  # Send the circular embed
                                    console.info(
                                        f"Sent Circular Embed and Error Embed to Fallback Channel in {guild.id} | {_channel.id}")
                                    break  # Break the loop

                                except Exception as e:  # If it can't send the error embed
                                    console.debug(
                                        f"[Owners] | Couldn't send Circular to a Fallback channel in {guild.id}'s {channel.id} | {e}")

                        except Exception as e:  # If it can't send the circular embed
                            console.error(
                                f"Couldn't send Circular Embed to {guild.id}'s | {channel.id}. Not discord.Forbidden.")
                            console.error(e)

            else:
                for guild, channel, message in zip(guilds, channels, messages):  # For each guild in the database

                    console.debug(f"[Owners] | Message: {message}")
                    embed.description = message  # Set the description of the embed to the message

                    try:  # Try to get the guild and channel
                        guild = await self.client.fetch_guild(int(guild))  # Get the guild object
                        channel = await guild.fetch_channel(int(channel))  # Get the channel object

                    except discord.NotFound:  # If the guild/channel is not found (deleted)
                        console.warning(f"Guild or channel not found. Guild: {guild}, Channel: {channel}")
                        self.cur.execute(
                            f"DELETE FROM guild_notify WHERE guild_id = {guild} AND channel_id = {channel}")  # Delete the guild from the database
                        self.con.commit()
                        continue

                    except discord.Forbidden:  # If the bot can not get the guild/channel
                        console.warning(
                            f"Could not get channel. Guild: {guild}, Channel: {channel}. Seems like I was kicked from the server.")
                        self.cur.execute(
                            f"DELETE FROM guild_notify WHERE guild_id = {guild} AND channel_id = {channel}")  # Delete the guild from the database
                        self.con.commit()
                        continue

                    except Exception as e:  # If there is some other error
                        console.error(f"Error: {e}")
                        continue

                    try:  # Try to send the message
                        await channel.send(embed=embed)  # Send the embed
                        console.info(f"Sent Circular Embed to {guild.id} | {channel.id}")

                    except discord.Forbidden:  # If the bot doesn't have permission to send messages in the channel
                        for _channel in guild.text_channels:  # Find a channel where it can send messages
                            try:  # Try to send the error embed
                                await _channel.send(embed=error_embed)  # Send the error embed
                                await _channel.send(embed=embed)  # Send the circular embed
                                console.info(
                                    f"Sent Circular Embed and Error Embed to Fallback Channel in {guild.id} | {_channel.id}")
                                break  # Break the loop

                            except Exception as e:  # If it can't send the error embed
                                console.debug(
                                    f"[Owners] | Couldn't send Circular to a Fallback channel in {guild.id}'s {channel.id} | {e}")

                    except Exception as e:  # If it can't send the circular embed
                        console.error(
                            f"Couldn't send Circular Embed to {guild.id}'s | {channel.id}. Not discord.Forbidden.")
                        console.error(e)

                for user, message in zip(user_id, user_message):  # For each user in the database
                    user = await self.client.fetch_user(int(user))  # Get the user object

                    console.debug(f"[Owners] | Message: {message}")
                    embed.description = message

                    try:  # Try to send the embed to the user
                        await user.send(embed=embed)  # Send the embed to the user
                        console.info(
                            f"Successfully sent Circular in DMs to {user.name}#{user.discriminator} | {user.id}")

                    except discord.Forbidden:  # If the user has DMs disabled
                        console.warning(
                            f"Could not send Circular in DMs to {user.name}#{user.discriminator} | {user.id}. DMs are disabled.")

                        self.cur.execute(f"DELETE FROM dm_notify WHERE user_id = {user.id}")
                        self.con.commit()

                        console.info(f"Removed {user.name}#{user.discriminator} | {user.id} from the DM notify list.")

                    except Exception as e:  # If the user has DMs disabled
                        console.error(f"Couldn't send Circular Embed to User: {user.id}")
                        console.error(e)











def setup(client):
    client.add_cog(Owners(client))
