import os

import discord, sqlite3
from discord.ext import commands
from backend import owner_ids, embed_title, embed_footer, embed_color, log, owner_guilds, get_png, ConfirmButton, DeleteButton, is_bot_owner


class Owners(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.con = sqlite3.connect('./data/data.db')
        self.cur = self.con.cursor()

    owners = discord.SlashCommandGroup("owners", "Bot owner commands.")

    @commands.Cog.listener()
    async def on_ready(self):
        log.info(f"Cog : Owners.py loaded.")

    @commands.check_any(is_bot_owner())
    @owners.command(name='reload', description='Reload a cog.')
    async def reload(self, ctx, cog: str):
        if not ctx.author.id in owner_ids:
            return await ctx.respond("You are not allowed to use this command.")

        self.client.unload_extension(f"cogs.{cog}")
        self.client.load_extension(f"cogs.{cog}")
        await ctx.respond(f"Reloaded {cog}.")


    @commands.check_any(is_bot_owner())
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


    @commands.check_any(is_bot_owner())
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


    @commands.check_any(is_bot_owner())
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

        await get_png(url, circular_name)

        file = discord.File(f"./{circular_name}.png", filename="image.png")
        embed.set_image(url="attachment://image.png")
        os.remove(f"./{circular_name}.png")

        if debug_guild: # If a debug guild is specified, send the message to ONLY that guild.
            self.cur.execute(f"SELECT message FROM guild_notify WHERE guild_id = {debug_guild}")
            message = self.cur.fetchone()  # Get the reminder-message for the guild from the DB
            log.debug(f"Message: {message}")
            embed.description = message[0]  # Set the description of the embed to the message
            embed.add_field(name=f"{category.capitalize()} | {circular_name}", value=url, inline=False)

            guild = await self.client.fetch_guild(int(debug_guild))
            self.cur.execute(f"SELECT channel_id FROM guild_notify WHERE guild_id = {guild.id}")
            channel_id = self.cur.fetchone()[0]  # Get the channel_id for the guild from the DB

            channel = await guild.fetch_channel(int(channel_id))
            await channel.send(embed=embed, file=file)
            return await ctx.respond(f"Notified the `{debug_guild}` server.")

        elif debug_user: # If a debug user is specified, send the message to ONLY that user.
            self.cur.execute(f"SELECT message FROM remind WHERE user_id = {debug_user}")
            message = self.cur.fetchone()  # Get the reminder-message for the user from the DB
            log.debug(f"Message: {message}")
            embed.description = message[0]  # Set the description of the embed to the message
            embed.add_field(name=f"{category.capitalize()} | {circular_name}", value=url, inline=False)

            user = await self.client.fetch_user(int(debug_user))
            await user.send(embed=embed, file=file)
            return await ctx.respond(f"Notified the `{debug_user}` user.")

        else:
            button = ConfirmButton(ctx.author)
            await ctx.followup.send(embed=embed, file=file, view=button)
            await button.wait()

            if button.value is None:  # Timeout
                await ctx.respond("Timed out.")
                return

            elif not button.value:  # Cancel
                await ctx.respond("Cancelled.")
                return


            self.cur.execute(f"SELECT channel_id FROM guild_notify")
            channels = self.cur.fetchall()
            self.cur.execute(f"SELECT guild_id FROM guild_notify")
            guilds = self.cur.fetchall()


            for guild, channel in zip(guilds, channels):
                self.cur.execute(f"SELECT message FROM guild_notify WHERE guild_id = {guild[0]}")
                message = self.cur.fetchone()  # Get the reminder-message for the guild from the DB
                log.debug(f"Message: {message}")
                embed.description = message[0]  # Set the description of the embed to the message
                guild = self.client.get_guild(int(guild[0]))
                channel = await guild.fetch_channel(int(channel[0]))

                await channel.send(embed=embed, file=file)


def setup(client):
    client.add_cog(Owners(client))