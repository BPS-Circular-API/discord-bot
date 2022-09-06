import discord, sqlite3, os
from discord.ext import commands
from backend import owner_ids, embed_title, embed_footer, embed_color, log, owner_guilds, get_png, ConfirmButton, DeleteButton


class Owners(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.con = sqlite3.connect('./data/data.db')
        self.cur = self.con.cursor()

    owners = discord.SlashCommandGroup("owners", "Bot owner commands.", guild_ids=owner_guilds)

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
        msg = await ctx.followup.send(embed=embed)
        await msg.edit(embed=embed, view=DeleteButton(ctx, msg))


    @owners.command(name="servers", description="List all servers the bot is in.")
    async def servers(self, ctx):
        if not ctx.author.id in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")
        await ctx.defer()
        embed = discord.Embed(title="Servers", description=f"I am in `{len(self.client.guilds)}` servers!", color=embed_color).set_footer(text=embed_footer).set_author(name=embed_title)
        for i in self.client.guilds:
            guild = await self.client.fetch_guild(i.id)
            embed.add_field(name=guild.name, value=i.id, inline=False)
        msg = await ctx.followup.send(embed=embed)
        await msg.edit(embed=embed, view=DeleteButton(ctx, msg))


    @owners.command(name="guild_notify", description="Notify all users in a server.")
    async def guild_notify(self, ctx, circular_name: str, url: str,
                     category: discord.Option(choices=[
                         discord.OptionChoice("General", value="general"),
                         discord.OptionChoice("PTM", value="ptm"),
                         discord.OptionChoice("Exam", value="exam")
                     ]),
                     debug_guild = None, debug_user = None):

        if not ctx.author.id in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")
        await ctx.defer()
        if debug_guild:
            log.debug(type(debug_guild))
            debug_guild = int(debug_guild)

        embed = discord.Embed(title=f"New Circular Alert!", color=embed_color)
        embed.set_footer(text=embed_footer)
        embed.set_author(name=embed_title)
        embed.add_field(name=f"{category.capitalize()} | {circular_name}", value=url,
                        inline=False)

        await get_png(url, circular_name)

        if debug_guild: # If a debug guild is specified, send the message to ONLY that guild.
            self.cur.execute(f"SELECT message FROM guild_notify WHERE guild_id = {debug_guild}")
            message = self.cur.fetchone()  # Get the reminder-message for the guild from the DB
            log.debug(f"Message: {message}")
            embed.description = message[0]  # Set the description of the embed to the message

            guild = await self.client.fetch_guild(int(debug_guild))
            self.cur.execute(f"SELECT channel_id FROM guild_notify WHERE guild_id = {guild.id}")
            channel_id = self.cur.fetchone()[0]  # Get the channel_id for the guild from the DB

            channel = await guild.fetch_channel(int(channel_id))
            file = discord.File(f"./{circular_name}.png", filename="image.png")
            embed.set_image(url="attachment://image.png")
            await channel.send(embed=embed, file=file)
            return await ctx.respond(f"Notified the `{debug_guild}` server.")

        elif debug_user: # If a debug user is specified, send the message to ONLY that user.
            self.cur.execute(f"SELECT message FROM remind WHERE user_id = {debug_user}")
            message = self.cur.fetchone()  # Get the reminder-message for the user from the DB
            log.debug(f"Message: {message}")
            embed.description = message[0]  # Set the description of the embed to the message

            user = await self.client.fetch_user(int(debug_user))
            file = discord.File(f"./{circular_name}.png", filename="image.png")
            embed.set_image(url="attachment://image.png")
            await user.send(embed=embed, file=file)
            return await ctx.respond(f"Notified the `{debug_user}` user.")

        else:
            button = ConfirmButton(ctx.author)
            file = discord.File(f"./{circular_name}.png", filename="image.png")
            embed.set_image(url="attachment://image.png")
            await ctx.followup.send(embed=embed, file=file, view=button)
            await button.wait()

            if button.value is None:  # Timeout
                await ctx.respond("Timed out.")
                return

            elif not button.value:  # Cancel
                await ctx.respond("Cancelled.")
                return

            self.cur.execute("SELECT * FROM guild_notify")
            guild_notify = self.cur.fetchall()
            guilds = [x[0] for x in guild_notify]
            channels = [x[1] for x in guild_notify]
            messages = [x[2] for x in guild_notify]

            self.cur.execute(f"SELECT * FROM dm_notify")
            users = self.cur.fetchall()
            user_id = [x[0] for x in users]
            user_message = [x[1] for x in users]
            del users, guild_notify

            embed = discord.Embed(title=f"New Circular Alert!", color=embed_color)
            embed.set_footer(text=embed_footer)
            embed.set_author(name=embed_title)

            await get_png(url, circular_name)

            error_embed = discord.Embed(title=f"Error!",
                                        description=f"Please make sure that I have the permission to send messages in the channel you set for notifications.",
                                        color=embed_color)
            error_embed.set_footer(text=embed_footer)
            error_embed.set_author(name=embed_title)
            embed.add_field(name=f"{category.capitalize()} | {circular_name}", value=url, inline=False)

            for guild, channel, message in zip(guilds, channels, messages):

                file = discord.File(f"./{circular_name}.png", filename="image.png")
                embed.set_image(url="attachment://image.png")

                log.debug(f"Message: {message}")
                embed.description = message  # Set the description of the embed to the message

                guild = self.client.get_guild(int(guild))
                channel = await guild.fetch_channel(int(channel))

                try:
                    await channel.send(embed=embed, file=file)
                    log.info(f"Sent Circular Embed to {guild.id} | {channel.id}")

                except discord.Forbidden:
                    for _channel in guild.text_channels:
                        try:
                            await _channel.send(embed=error_embed)
                            await _channel.send(embed=embed, file=file)
                            log.info(f"Sent Circular Embed and Error Embed to Fallback Channel in {guild.id} | {_channel.id}")
                            break

                        except Exception as e:
                            log.debug(f"Couldn't send Circular to a Fallback channel in {guild.id}'s {channel.id} | {e}")


                except Exception as e:
                    log.error(f"Couldn't send Circular Embed to {guild.id}'s | {channel.id}. Not discord.Forbidden.")
                    log.error(e)

            for user, message in zip(user_id, user_message):
                file = discord.File(f"./{circular_name}.png", filename="image.png")
                embed.set_image(url="attachment://image.png")

                user = await self.client.fetch_user(int(user))

                log.debug(f"Message: {message}")
                embed.description = message

                try:
                    await user.send(embed=embed, file=file)
                    log.info(f"Successfully sent Circular in DMs to {user.name}#{user.discriminator} | {user.id}")
                except Exception as e:
                    log.error(f"Couldn't send Circular Embed to User: {user.id}")
                    log.error(e)

            os.remove(f"./{circular_name}.png")



def setup(client):
    client.add_cog(Owners(client))