import os
import sqlite3
import discord
import shutil
import random
import datetime
import asyncio
import pybpsapi
from discord.ext import commands, tasks
from backend import console, embed_color, embed_footer, embed_title, get_png, backup_interval, DeleteButton, \
    status_interval, log, embed_url, base_api_url, send_to_guilds, \
    send_to_users, categories


class Listeners(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.con = sqlite3.connect('./data/data.db')
        self.cur = self.con.cursor()
        self.member_count = -1

        self.group = pybpsapi.CircularCheckerGroup()
        for thing in [pybpsapi.CircularChecker(
                cat, cache_method='database', db_name='data', db_path='./data', db_table='cache', url=base_api_url
        ) for cat in categories]:
            self.group.add(thing)

    @commands.Cog.listener()
    async def on_ready(self):
        console.info(f"Cog : Listeners.py loaded.")

        if not self.get_member_count.is_running():
            self.get_member_count.start()

        if not self.check_for_circular.is_running():
            self.check_for_circular.start()

        if not self.backup.is_running():
            if backup_interval >= 0.5:
                self.backup.start()

        while not self.member_count > -1:
            await asyncio.sleep(1)

        console.info(f"I am in {len(self.client.guilds)} guilds. They have {self.member_count} members.")
        self.random_status.start()

    @commands.Cog.listener()
    async def on_message(self, ctx):
        # Ignore if message is from a bot or a reply
        if (not ctx.author.bot) & (self.client.user.mentioned_in(ctx)) & (ctx.reference is None):
            if ctx.mention_everyone:
                return

            embed = discord.Embed(title="Mention Message", description="Hello! Thanks for using this bot.",
                                  color=embed_color)
            embed.set_footer(text=embed_footer)
            embed.set_author(name=embed_title)
            embed.add_field(name="Prefix", value="This bot uses slash commands, which are prefixed with `/circular`",
                            inline=False)
            embed.add_field(name="For help", value="Use </help:1017654494009491476> to get a list of all the commands.",
                            inline=False)

            try:
                msg = await ctx.reply(embed=embed)
                await msg.edit(embed=embed, view=DeleteButton(ctx, msg, author_only=False))
                await log('info', 'command',
                          f"Sent mention message to {ctx.author.name}#{ctx.author.discriminator} ({ctx.author.id})")

            except discord.Forbidden:  # If the bot doesn't have permission to send messages
                await log('warning', 'command',
                          f"Missing permissions to send mention message in {ctx.channel.id} in {ctx.guild.id}")

            except Exception as e:
                await log('warning', 'command',
                          f"Error in sending mention message in {ctx.channel.id} in {ctx.guild.id} : {e}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await log('info', 'listener', f"Joined guild {guild.id}")

    @tasks.loop(seconds=status_interval * 60)
    async def random_status(self):
        activities = (
            f"{self.member_count} Users!",
            f"{len(self.client.guilds)} Guilds!",
            "/circular help",
            "Made by Raj Dave#3215",
            "Fully Open Source!",
        )

        types = (
            discord.ActivityType.watching,
            discord.ActivityType.watching,
            discord.ActivityType.playing,
            discord.ActivityType.playing,
            discord.ActivityType.playing,
        )

        # Choose a random activity
        rand_int = random.randint(0, len(activities) - 1)

        try:
            # Change the status
            await self.client.change_presence(
                activity=discord.Activity(type=types[rand_int], name=activities[rand_int])
            )
        except Exception as e:
            await log('warning', 'listener', f"Error in changing status : {e}")
        console.debug(f"Changed status to {activities[rand_int]}")

    @tasks.loop(seconds=3600 * 24)  # Run every 24 hours
    async def get_member_count(self):
        _member_count = 0

        for guild in self.client.guilds:
            guild = await self.client.fetch_guild(guild.id, with_counts=True)
            _member_count += guild.approximate_member_count

        self.member_count = _member_count
        console.debug(f"[Listeners] | Member Count: {self.member_count}")

    @tasks.loop(seconds=3600)
    async def check_for_circular(self):
        # Check for new circulars
        new_circular_objects = self.group.check()

        if (new_circulars := sum(i for i in map(len, new_circular_objects.values()))) > 0:
            console.info(f"Found {new_circulars} new circulars.")
        else:
            console.debug(f"No new circulars found.")
            return
        console.debug(f"New Circulars: {new_circular_objects}")

        # If there are more than 19 new circulars, skip notification (bug)
        if sum((i for i in map(len, new_circular_objects.values()))) > 19:
            console.warning(f"[Listeners] | More than 19 new circulars found. Skipping notification.")
            return

        # if there are actually any new circulars, notify
        if sum((i for i in map(len, new_circular_objects.values()))) > 0:
            for cat in new_circular_objects:
                if cat:
                    for obj in new_circular_objects[cat]:
                        try:
                            await self.notify(cat, obj)
                        except Exception as err:
                            console.error(err)
                            await log('error', 'listener', f"Error in notifying about circular {obj['id']}: {err}")

        else:
            console.debug(f"[Listeners] | No new circulars found.")

    async def notify(self, _circular_category, _circular_obj):
        # Gather all the guilds
        self.cur.execute("SELECT * FROM guild_notify")
        guild_notify = self.cur.fetchall()

        guilds = [x[0] for x in guild_notify]
        channels = [x[1] for x in guild_notify]
        messages = [x[2] for x in guild_notify]

        # Gather all the DMs
        self.cur.execute("SELECT * FROM dm_notify")
        users = self.cur.fetchall()

        # Make the lists
        user_ids = [x[0] for x in users]
        user_messages = [x[1] for x in users]
        del users, guild_notify

        # Create an empty dict for logging
        notif_msgs = {"guild": [], "dm": []}

        # Get the circular info and prepare the embed
        link: str = _circular_obj['link']
        title: str = _circular_obj['title']
        id_ = _circular_obj['id']

        # Get the circular image
        png_url = await get_png(link)

        # Create the error embed
        error_embed = discord.Embed(title=f"Error!", color=embed_color)
        error_embed.description = "Please make sure that I have the adequate permissions to send messages in the " \
                                  "channel you set for notifications."
        error_embed.set_footer(text=embed_footer)
        error_embed.set_author(name=embed_title)  # Set the footer and author

        # Create the main embed
        embed = discord.Embed(title=f"New Circular | **{_circular_category.capitalize()}**", color=embed_color,
                              url=embed_url)
        embed.set_footer(text=embed_footer)
        embed.set_author(name=embed_title)
        embed.set_image(url=png_url[0])  # Set the image to the attachment
        embed.add_field(name=f"[{id_}]  `{title.strip()}`", value=link, inline=False)

        # If there is a custom message set by the bot dev, add it to the embed
        self.cur.execute("SELECT data FROM cache WHERE title = 'circular_message'")  # Get the circular message
        circular_message = self.cur.fetchone()

        # If there is a circular dev message, add it to the embed
        if circular_message:
            embed.add_field(name="Message from the Developer", value=circular_message[0], inline=False)
            self.cur.execute("DELETE FROM cache WHERE title = 'circular_message'")  # Delete the circular message
            self.con.commit()

        embed_list = []

        # If the circular has more than 1 page
        if len(png_url) > 1:
            for i in range(len(png_url)):
                if i == 0:
                    continue

                # If the circular has more than 4 pages, only send the first 4
                # This is due to the discord embed limit of 4 images.
                elif i > 3:
                    # embed.add_field(name="Note", value=f"This circular has {len(png_url) - 4} more pages .", inline=False)
                    break

                temp_embed = discord.Embed(url=embed_url)
                temp_embed.set_image(url=png_url[i])
                embed_list.append(temp_embed.copy())

        # Gather all guilds/users and send the embed
        await send_to_guilds(guilds, channels, messages, notif_msgs, embed, embed_list, error_embed, id_)
        await send_to_users(user_ids, user_messages, notif_msgs, embed, embed_list, id_)

        await log(
            'info', "listener",
            f"Notified {len(notif_msgs['guild'])} guilds and {len(notif_msgs['dm'])} "
            f"users about the new circular. ({id_})"
        )

    @tasks.loop(minutes=backup_interval * 60)
    async def backup(self):
        now = datetime.datetime.now()
        date_time = now.strftime("%d-%m-%Y-%H-%M")

        # If the directory doesn't exist, create it
        if not os.path.exists('./data/backups/'):
            os.mkdir("./data/backups/")

        # Copy the current db to the new directory
        shutil.copyfile("./data/data.db",
                        f"./data/backups/data-{date_time}.db")
        await log('info', "etc", f"Backed up the database to ./data/backups/data-{date_time}.db")

    @commands.Cog.listener()
    async def on_application_command_error(self, ctx: discord.ApplicationContext, error: Exception):
        if isinstance(error, discord.errors.Forbidden):
            await ctx.respond("I don't have the permission to do that!")
        # elif isinstance(error, discord.errors.ApplicationCommandInvokeError):
        #     pass
        else:
            console.error(error)
            raise error

    @commands.Cog.listener()
    async def on_application_command(self, ctx: discord.ApplicationContext):
        await log('info', "command", f"{ctx.author} ({ctx.author.id}) used the command /{ctx.command.qualified_name}")

    @random_status.before_loop
    @check_for_circular.before_loop
    @backup.before_loop
    @get_member_count.before_loop
    async def before_my_task(self):
        await self.client.wait_until_ready()


def setup(client):
    client.add_cog(Listeners(client))
