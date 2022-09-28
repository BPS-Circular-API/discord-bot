import os
import sqlite3, discord, shutil, random, datetime, asyncio
from discord.ext import commands, tasks
from backend import log, embed_color, embed_footer, embed_title, get_png, backup_interval, DeleteButton, get_cached, set_cached, get_circular_list, amount_to_cache


class Listeners(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.con = sqlite3.connect('./data/data.db')
        self.cur = self.con.cursor()
        self.amount_to_cache = amount_to_cache



    @commands.Cog.listener()
    async def on_ready(self):
        log.info(f"Cog : Listeners.py loaded.")

        if not self.backup.is_running():
            if backup_interval >= 0.5:
                self.backup.start()

        global member_count
        member_count = -1

        self.get_member_count.start()
        if not self.get_member_count.is_running():
            self.get_member_count.start()

        if not self.check_for_circular.is_running():
            self.check_for_circular.start()

        while not member_count > -1:
            await asyncio.sleep(1)

        log.info(f"I am in {len(self.client.guilds)} guilds. They have {member_count} members.")
        self.random_status.start()


    @commands.Cog.listener()
    async def on_message(self, ctx):
        if (not ctx.author.bot) & (self.client.user.mentioned_in(ctx)) & (ctx.reference is None):
            embed = discord.Embed(title="Mention Message", description="Hello! Thanks for using this bot.", color=embed_color)
            embed.set_footer(text=embed_footer)
            embed.set_author(name=embed_title)
            embed.add_field(name="Prefix", value="This bot uses slash commands, which are prefixed with `/circular`", inline=False)
            embed.add_field(name="For help", value="Use </help:1017654494009491476>  to get a list of all the commands.", inline=False)
            try:
                msg = await ctx.reply(embed=embed)
                await msg.edit(embed=embed, view=DeleteButton(ctx, msg, author_only=False))
            except discord.Forbidden:
                log.warning(f"Missing permissions to send mention message in {ctx.channel.id} in {ctx.guild.id}")
            except Exception as e:
                log.error(f"Error sending mention message in {ctx.channel.id} in {ctx.guild.id} : {e}")


    """
    # This code is commented out since I'm trying to make an intent-less bot and this requires the members intent
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        log.info(f"I just joined a server: {guild.id}")
        guild = await self.client.fetch_guild(guild.id)
        embed = discord.Embed(title=f"Thanks for adding me!", description=f"Here's the command guide! An admin can ", color=embed_color)
        embed.add_field(name="Admin Guide", value="Please up the circular-reminder with `/circular admin setup` to receive notifications when new circulars are posted.", inline=False)
        embed.add_field(name="Command Guide", value=f"All the commands start with `/circular`, they're slash commands. ", inline=False)

        embed.set_footer(text=embed_footer)
        embed.set_author(name=embed_title)
        # find the first channel in the guild and send to it
        channels = guild.text_channels
        log.debug(channels)
        for channel in channels:
            log.debug(channel)
            try:
                await self.client.get_channel(channel[0]).send(embed=embed)
                break
            except discord.Forbidden:
                pass
    """


    @tasks.loop(seconds=60)
    async def random_status(self):
        rand_int = random.randint(0, 3)
        activities = (f"{member_count} Users!", f"{len(self.client.guilds)} Guilds!", f"/circular help", f"Made by Raj Dave#3215")
        types = (discord.ActivityType.watching, discord.ActivityType.watching, discord.ActivityType.playing, discord.ActivityType.playing)
        await self.client.change_presence(activity=discord.Activity(type=types[rand_int], name=activities[rand_int]))



    @tasks.loop(seconds=3600*24) # Run every 24 hours
    async def get_member_count(self):
        _member_count = 0
        for guild in self.client.guilds:
            guild = await self.client.fetch_guild(guild.id, with_counts=True)
            _member_count += guild.approximate_member_count
        global member_count
        member_count = _member_count
        log.debug(f"[Listeners] | Member Count: {member_count}")


    async def get_circulars(self, _cats, final_dict):
        for item in _cats:
            res = await get_circular_list(item)
            final_dict[item] = [res[i] for i in range(self.amount_to_cache)]

        set_cached(final_dict)


    @tasks.loop(seconds=3600)
    async def check_for_circular(self):
        log.info("Check for circular started")
        categories = ("ptm", "general", "exam")
        final_dict = {"general": [], "ptm": [], "exam": []}
        new_circular_categories = []
        new_circular_objects = []




        if self.amount_to_cache < 1:
            self.amount_to_cache = 1


        try:    # Try to get the cached data and make it a dict
            old_cached = dict(get_cached())

        except Exception as e:  # If it can't be gotten/can't be made into a dict (is None)
            log.error(f"Error getting cached circulars : {e}")
            await self.get_circulars(categories, final_dict)

            set_cached(final_dict)
            return


        if old_cached == {}:
            log.info("Cached is empty, setting it to the latest circular")
            await self.get_circulars(categories, final_dict)
            return
        else:
            log.info("Cache is not empty, checking for new circulars")




        for item in categories:
            res = await get_circular_list(item)
            final_dict[item] = [res[i] for i in range(self.amount_to_cache)]

        await self.get_circulars(categories, final_dict)

        log.debug('[Listeners] | ' + str(final_dict))
        log.debug('[Listeners] | ' + str(old_cached))

        for cat in categories:
            if not len(final_dict[cat]) == len(old_cached[cat]):
                await self.get_circulars(categories, final_dict)
                log.info("The length of the circulars in a category is different, updating cache")
                return

        if final_dict != old_cached:    # If the old and new dict are not the same
            log.info("There's a new circular posted!")

            for circular_cat in categories:
                for i in range(len(final_dict[circular_cat])):
                    if final_dict[circular_cat][i] not in old_cached[circular_cat]:
                        new_circular_categories.append(circular_cat)
                        new_circular_objects.append(final_dict[circular_cat][i])

            log.info(f"New circular: {new_circular_objects}")

            for i in range(len(new_circular_objects)):
                await self.notify(new_circular_categories[i], new_circular_objects[i])


        else:
            log.info("No new circulars")




    async def notify(self, _circular_category, _circular_obj):
        self.cur.execute("SELECT * FROM guild_notify")  # Get all the guilds that have enabled notifications
        guild_notify = self.cur.fetchall()

        guilds = [x[0] for x in guild_notify]
        channels = [x[1] for x in guild_notify]
        messages = [x[2] for x in guild_notify]

        self.cur.execute(f"SELECT * FROM dm_notify")    # Get the DM notify list
        users = self.cur.fetchall()

        user_id = [x[0] for x in users]
        user_message = [x[1] for x in users]
        del users, guild_notify # Delete the variables to save memory

        embed = discord.Embed(title=f"New Circular Alert!", color=embed_color)
        embed.set_footer(text=embed_footer)
        embed.set_author(name=embed_title)

        link = _circular_obj['link']   # Get the link of the new circular
        title = _circular_obj['title']  # Get the title of the new circular

        png_url = await get_png(link)  # Get the PNG of the circular

        error_embed = discord.Embed(title=f"Error!", description=f"Please make sure that I have the permission to send messages in the channel you set for notifications.", color=embed_color)
        error_embed.set_footer(text=embed_footer)   # Set the footer
        error_embed.set_author(name=embed_title)    # Set the author
        embed.set_image(url=png_url)  # Set the image to the attachment

        embed.add_field(name=f"{_circular_category.capitalize()} | {title}", value=link, inline=False)   # Add the field
        for guild, channel, message in zip(guilds, channels, messages): # For each guild in the database

            log.debug(f"[Listeners] | Message: {message}")
            embed.description = message  # Set the description of the embed to the message

            try:    # Try to get the channel and guild
                guild = await self.client.fetch_guild(int(guild))  # Get the guild object
                channel = await guild.fetch_channel(int(channel))  # Get the channel object

            except discord.NotFound:    # If the channel or guild is not found (deleted)
                log.warning(f"Guild or channel not found. Guild: {guild}, Channel: {channel}")
                self.cur.execute(f"DELETE FROM guild_notify WHERE guild_id = {guild} AND channel_id = {channel}")  # Delete the guild from the database
                self.con.commit()
                continue

            except discord.Forbidden:   # If the bot can not get the channel or guild
                log.warning(f"Could not get channel. Guild: {guild}, Channel: {channel}. Seems like I was kicked from the server.")
                self.cur.execute(f"DELETE FROM guild_notify WHERE guild_id = {guild} AND channel_id = {channel}")  # Delete the guild from the database
                self.con.commit()
                continue

            except Exception as e:  # If there is any other error
                log.error(f"Error: {e}")
                continue

            try:    # Try to send the message
                await channel.send(embed=embed)  # Send the embed
                log.info(f"Sent Circular Embed to {guild.id} | {channel.id}")

            except discord.Forbidden:   # If the bot doesn't have permission to send messages in the channel
                for _channel in guild.text_channels:    # Find a channel where it can send messages

                    try:    # Try to send the error embed
                        await _channel.send(embed=error_embed)  # Send the error embed
                        await _channel.send(embed=embed) # Send the circular embed
                        log.info(f"Sent Circular Embed and Error Embed to Fallback Channel in {guild.id} | {_channel.id}")
                        break   # Break the loop

                    except Exception as e:  # If it can't send the error embed
                        log.warning(f"Couldn't send Circular to a Fallback channel in {guild.id}'s {channel.id} | {e}")

            except Exception as e:  # If it can't send the circular embed
                log.error(f"Couldn't send Circular Embed to {guild.id}'s | {channel.id}. Not discord.Forbidden.")
                log.error(e)



        for user, message in zip(user_id, user_message):    # For each user in the database
            user = await self.client.fetch_user(int(user))  # Get the user object

            log.debug(f"[Listeners] | Message: {message}")
            embed.description = message

            try:    # Try to send the embed to the user
                await user.send(embed=embed) # Send the embed to the user
                log.info(f"Successfully sent Circular in DMs to {user.name}#{user.discriminator} | {user.id}")

            except discord.Forbidden:   # If the user has DMs disabled
                log.warning(f"Could not send Circular in DMs to {user.name}#{user.discriminator} | {user.id}. DMs are disabled.")

                # Delete the user from the database
                self.cur.execute(f"DELETE FROM dm_notify WHERE user_id = {user.id}")
                self.con.commit()
                log.info(f"Removed {user.name}#{user.discriminator} | {user.id} from the DM notify list.")

            except Exception as e:  # If the user has DMs disabled
                log.error(f"Couldn't send Circular Embed to User: {user.id}")
                log.error(e)


    @tasks.loop(minutes=backup_interval*60)
    async def backup(self):
        # Close the DB
        self.con.commit()
        self.con.close()

        now = datetime.datetime.now()
        date_time = now.strftime("%d-%m-%Y-%H-%M")

        if not os.path.exists('./data/backups/'):   # If the directory does not exist
            os.mkdir("./data/backups/")

        shutil.copyfile("./data/data.db", f"./data/backups/data-{date_time}.db")    # Copy the current file to the new directory
        log.info("Backed up data.db")

        # open DB
        self.con = sqlite3.connect("data.db")
        self.cur = self.con.cursor()



    @random_status.before_loop
    @check_for_circular.before_loop
    @backup.before_loop
    @get_member_count.before_loop
    async def before_my_task(self):
        await self.client.wait_until_ready()


def setup(client):
    client.add_cog(Listeners(client))
