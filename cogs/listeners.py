import asyncio
import random
import sqlite3, discord
from discord.ext import commands, tasks
from backend import log, get_latest_circular_cached, embed_color, embed_footer, embed_title, get_png


class Listeners(commands.Cog):
    def __init__(self, client):
        self.cached_latest = {}
        self.old_cached_latest = {}
        self.client = client
        self.con = sqlite3.connect('./data/data.db')
        self.cur = self.con.cursor()
        self.new_circular_cat = ""



    @commands.Cog.listener()
    async def on_ready(self):
        log.info(f"Cog : Listeners.py loaded.")
        self.get_member_count.start()
        self.check_for_circular.start()
        await asyncio.sleep(2)
        self.random_status.start()

    @commands.Cog.listener()
    async def on_message(self, message):
        if (not message.author.bot) & (self.client.user.mentioned_in(message)) & (message.reference is None):
            embed = discord.Embed(title="Mention Message", description="Hello! Thanks for using this bot.", color=embed_color)
            embed.set_footer(text=embed_footer)
            embed.set_author(name=embed_title)
            embed.add_field(name="Prefix", value="This bot uses slash commands, which are prefixed with `/circular`", inline=False)
            embed.add_field(name="For help", value="Use `/circular help` to get a list of all the commands.", inline=False)
            await message.reply(embed=embed)



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
        activities = [f"{member_count} Users!", f"{len(self.client.guilds)} Guilds!", f"/circular help", f"Made by Raj Dave#3215"]
        types = [discord.ActivityType.watching, discord.ActivityType.watching, discord.ActivityType.playing, discord.ActivityType.playing]
        await self.client.change_presence(activity=discord.Activity(type=types[rand_int], name=activities[rand_int]))



    @tasks.loop(seconds=3600*24) # Run every 24 hours
    async def get_member_count(self):
        global member_count
        member_count = 0
        for guild in self.client.guilds:
            guild = await self.client.fetch_guild(guild.id, with_counts=True)
            member_count += guild.approximate_member_count
        log.debug(f"Member Count: {member_count}")



    @tasks.loop(seconds=3600)
    async def check_for_circular(self):
        categories = ["ptm", "general", "exam"]
        if self.old_cached_latest == {}:    # If the bot just started and there is no older cached
            self.old_cached_latest = await get_latest_circular_cached("all")
        else:   # If cached exists
            self.old_cached_latest = self.cached_latest

        self.cached_latest = await get_latest_circular_cached("all")
        if self.cached_latest != self.old_cached_latest:    # If the cached circular list is different from the current one
            log.info("There's a new circular posted!")
            for cat in categories:  # Check which category has a new circular
                if self.cached_latest[cat] != self.old_cached_latest[cat]:
                    log.info(f"{cat} has new circular")
                    self.new_circular_cat = cat # Let's just HOPE that they will not upload multiple circulars to multiple categories within an hour
            await self.notify() # notify each server



    async def notify(self):
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

        # Remove redundant part of URL
        link = str(self.cached_latest[self.new_circular_cat]['link'])   # Get the link of the new circular
        link = link.split(':')  # Split the link by :
        link = f"{link[0]}:{link[1]}"  # Get the first two parts of the link
        title = self.cached_latest[self.new_circular_cat]['title']  # Get the title of the new circular

        png_url = await get_png(link)  # Get the PNG of the circular

        error_embed = discord.Embed(title=f"Error!", description=f"Please make sure that I have the permission to send messages in the channel you set for notifications.", color=embed_color)
        error_embed.set_footer(text=embed_footer)   # Set the footer
        error_embed.set_author(name=embed_title)    # Set the author
        embed.set_image(url=png_url)  # Set the image to the attachment

        embed.add_field(name=f"{self.new_circular_cat.capitalize()} | {title}", value=link, inline=False)   # Add the field
        for guild, channel, message in zip(guilds, channels, messages): # For each guild in the database

            log.debug(f"Message: {message}")
            embed.description = message  # Set the description of the embed to the message
            try:
                guild = self.client.fetch_guild(int(guild))   # Get the guild object
                channel = await guild.fetch_channel(int(channel))   # Get the channel object
            except discord.NotFound:
                log.warning(f"Guild or channel not found. Guild: {guild}, Channel: {channel}")
                self.cur.execute(f"DELETE FROM guild_notify WHERE guild_id = {guild} AND channel_id = {channel}")  # Delete the guild from the database
                self.con.commit()
                continue
            except discord.Forbidden:
                log.warning(f"Could not get channel. Guild: {guild}, Channel: {channel}. Seems like I was kicked from the server.")
                self.cur.execute(f"DELETE FROM guild_notify WHERE guild_id = {guild} AND channel_id = {channel}")  # Delete the guild from the database
                self.con.commit()
                continue
            except Exception as e:
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
                        log.debug(f"Couldn't send Circular to a Fallback channel in {guild.id}'s {channel.id} | {e}")

            except Exception as e:  # If it can't send the circular embed
                log.error(f"Couldn't send Circular Embed to {guild.id}'s | {channel.id}. Not discord.Forbidden.")
                log.error(e)



        for user, message in zip(user_id, user_message):    # For each user in the database
            user = await self.client.fetch_user(int(user))  # Get the user object

            log.debug(f"Message: {message}")
            embed.description = message

            try:    # Try to send the embed to the user
                await user.send(embed=embed) # Send the embed to the user
                log.info(f"Successfully sent Circular in DMs to {user.name}#{user.discriminator} | {user.id}")
            except Exception as e:  # If the user has DMs disabled
                log.error(f"Couldn't send Circular Embed to User: {user.id}")
                log.error(e)






    @random_status.before_loop
    @check_for_circular.before_loop
    @get_member_count.before_loop
    async def before_my_task(self):
        await self.client.wait_until_ready()


def setup(client):
    client.add_cog(Listeners(client))
