import os
import discord
import shutil
import random
import datetime
import asyncio
import pybpsapi
from discord.ext import commands, tasks
from backend import console, embed_color, embed_footer, embed_title, get_png, backup_interval, DeleteButton, \
    status_interval, log, embed_url, base_api_url, send_to_guilds, send_to_users, categories, statuses, \
    circular_check_interval, get_db, mysql_config, storage_method


class Listeners(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.con, self.cur = get_db()
        self.member_count = -1

        self.mention_embed = discord.Embed(
            title="Mention Message",
            description="Hello! Thanks for using this bot.",
            color=embed_color
        )
        self.mention_embed.set_footer(text=embed_footer)
        self.mention_embed.set_author(name=embed_title)
        self.mention_embed.add_field(
            name="Prefix",
            value="This bot uses slash commands, which are prefixed with `/circular`",
            inline=False
        )
        self.mention_embed.add_field(
            name="For help",
            value="Use </help:1017654494009491476> to get a list of all the commands.",
            inline=False
        )

        # Create a circular checker group and add all checkers of all categories to it
        self.group = pybpsapi.CircularCheckerGroup()

        if storage_method == 'sqlite':
            circular_checkers = [
                pybpsapi.CircularChecker(
                    cat, cache_method='sqlite', db_name='data', db_path='./data', db_table='cache', url=base_api_url
                ) for cat in categories
            ]
        else:
            circular_checkers = [
                pybpsapi.CircularChecker(
                    cat, cache_method='mysql',
                    db_name=mysql_config['database'],
                    db_table='cache',
                    db_port=mysql_config['port'],
                    db_password=mysql_config['password'],
                    db_host=mysql_config['host'],
                    db_user=mysql_config['user'],
                    url=base_api_url
                ) for cat in categories
            ]

        for checker in circular_checkers:
            self.group.add(checker)

    @commands.Cog.listener()
    async def on_ready(self):
        console.info(f"Cog : Listeners.py loaded.")

        try:
            if not self.get_member_count.is_running():
                self.get_member_count.start()

            if not self.check_for_circular.is_running():
                self.check_for_circular.start()

            if not self.random_status.is_running():
                self.random_status.start()

            if not self.backup.is_running():
                if backup_interval >= 0.5:
                    self.backup.start()

            while not self.member_count > -1:
                await asyncio.sleep(1)

        except Exception as e:
            console.warning(e)

        console.info(f"I am in {len(self.client.guilds)} guilds. They have {self.member_count} members.")

    @commands.Cog.listener()
    async def on_message(self, ctx):
        # Ignore if message is from a bot or a reply
        if (not ctx.author.bot) & (self.client.user.mentioned_in(ctx)) & (ctx.reference is None):
            # Ignore if it's a @everyone or @here
            if ctx.mention_everyone:
                return

            try:
                msg = await ctx.reply(embed=self.mention_embed)
                await msg.edit(embed=self.mention_embed, view=DeleteButton(msg, ctx.author.id))
                await log('info', 'command',
                          f"Sent mention message to {ctx.author.name} ({ctx.author.display_name}) | {ctx.author.id}")

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

        # statuses format: ['type|activity', 'type|activity', 'type|activity']
        activities = [item[1] for item in statuses]

        types = [
            discord.ActivityType.playing if item[0] == 'playing' else
            discord.ActivityType.streaming if item[0] == 'streaming' else
            discord.ActivityType.listening if item[0] == 'listening' else
            discord.ActivityType.watching if item[0] == 'watching' else
            discord.ActivityType.playing for item in statuses
        ]

        # replace {xyz} with variable xyz, etc
        for i in range(len(activities)):
            activities[i] = activities[i].replace('{guilds}', str(len(self.client.guilds)))
            activities[i] = activities[i].replace('{members}', str(self.member_count))

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

    @tasks.loop(seconds=circular_check_interval * 60)
    async def check_for_circular(self):
        # Check for new circulars
        new_circular_objects = self.group.check()

        if (new_circulars := sum(i for i in map(len, new_circular_objects.values()))) > 0:
            console.info(f"Found {new_circulars} new circulars.")
        else:
            console.debug(f"No new circulars found.")
            return

        console.debug(f"New Circulars: {new_circular_objects}")

        # If there are more than 19 new circulars, skip notification (bug idk how to fix)
        if sum((i for i in map(len, new_circular_objects.values()))) > 19:
            console.warning(f"[Listeners] | More than 19 new circulars found. Skipping notification.")
            return

        # if there are actually any new circulars, notify
        if sum((i for i in map(len, new_circular_objects.values()))) > 0:
            for cat in new_circular_objects:
                if cat:
                    for obj in new_circular_objects[cat]:
                        # Check if the circular is already there in the database

                        try:
                            await self.notify(cat, obj)
                        except Exception as err:
                            console.error(err)
                            await log('error', 'listener', f"Error in notifying about circular {obj['id']}: {err}")

        else:
            console.debug(f"[Listeners] | No new circulars found.")

    async def notify(self, _circular_category, _circular_obj):
        # Gather all guilds
        self.cur.execute("SELECT * FROM guild_notify")
        guild_notify = self.cur.fetchall()

        guilds = [x[0] for x in guild_notify]
        channels = [x[1] for x in guild_notify]
        messages = [x[2] for x in guild_notify]

        # Gather all DMs
        self.cur.execute("SELECT * FROM dm_notify")
        users = self.cur.fetchall()

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

        if not png_url:
            await log('error', 'listener', f"Error in getting circular image for {id_}. It is None.")
            return

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

        embed_list = []

        # If the circular has more than 1 page
        if len(png_url) > 1:
            for i in range(len(png_url)):
                # The first image is already there in the main embed
                if i == 0:
                    continue

                # If the circular has more than 4 pages, only send the first 4
                # This is due to the discord embed limit of 4 images.
                elif i > 3:
                    embed.add_field(
                        name="Note",
                        value=f"This circular has {len(png_url) - 4} more pages. Please visit the [link]({link}) to view them.",
                        inline=False
                    )
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
        elif isinstance(error, discord.errors.ApplicationCommandInvokeError):
            return
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
