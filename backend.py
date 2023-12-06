import configparser
import sqlite3
import time
import discord
import logging
import aiohttp
import sys
from discord.ext import commands
from colorlog import ColoredFormatter
import requests

# Loading config.ini
config = configparser.ConfigParser()

try:
    config.read('data/config.ini')
except Exception as e:
    print("Error reading the config.ini file. Error: " + str(e))
    sys.exit()


# Initializing the logger
def colorlogger(name='bps-circular-bot'):
    # disabler loggers
    for logger in logging.Logger.manager.loggerDict:
        logging.getLogger(logger).disabled = True
    logger = logging.getLogger(name)
    stream = logging.StreamHandler()
    log_format = "%(reset)s%(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s"
    stream.setFormatter(ColoredFormatter(log_format))
    logger.addHandler(stream)
    return logger  # Return the logger


console = colorlogger()

try:
    discord_token: str = config.get('secret', 'discord_token')
    log_level: str = config.get('main', 'log_level')
    owner_ids = config.get('main', 'owner_ids').strip().split(',')
    owner_guilds = config.get('main', 'owner_guilds').strip().split(',')
    base_api_url: str = config.get('main', 'base_api_url')
    backup_interval: int = config.getint('main', 'backup_interval')
    status_interval: int = config.getint('main', 'status_interval')
    ignored_circulars = config.get('main', 'ignored_circulars').strip().split(',')
    statuses: str = config.get('main', 'statuses').strip()

    embed_footer: str = config.get('discord', 'embed_footer')
    embed_color: int = int(config.get('discord', 'embed_color'), base=16)
    embed_title: str = config.get('discord', 'embed_title')
    embed_url: str = config.get('discord', 'embed_url')


except Exception as err:
    console.critical("Error reading the config.ini file. Error: " + str(err))
    sys.exit()

if log_level.upper() in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
    console.setLevel(log_level.upper())
else:
    console.warning(f"Invalid log level {log_level}. Defaulting to INFO.")
    console.setLevel("INFO")

owner_ids = tuple([int(i) for i in owner_ids])
console.debug(owner_ids)

owner_guilds = tuple([int(i) for i in owner_guilds])
console.debug(owner_guilds)

if ignored_circulars == ['']:
    ignored_circulars = tuple()
else:
    ignored_circulars = tuple([int(i) for i in ignored_circulars])
console.debug(ignored_circulars)

if base_api_url[-1] != "/":  # For some very bright people who don't know how to read
    base_api_url += "/"

statuses: list = statuses.split(',')
for i in range(len(statuses)):
    statuses[i] = statuses[i].strip()
    statuses[i] = statuses[i].split('|')

try:
    json = requests.get(base_api_url + "categories", timeout=5000).json()
    if json['http_status'] == 200:
        categories = json['data']
    else:
        raise ConnectionError("Invalid API Response. API says there are no categories.")
except Exception as e:
    console.critical(f"Error while connecting to the API. Error: {e}")
    sys.exit()

client = commands.Bot(help_command=None)  # Setting prefix


async def get_circular_list(category: str) -> tuple or None:
    url = base_api_url + "list"
    if category not in categories:
        return None

    params = {'category': category}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                return tuple((await resp.json())['data'])
            elif resp.status == 500:
                console.error("The API returned 500 Internal Server Error. Please check the API logs.")
                return


async def get_latest_circular(category: str) -> dict or None:
    url = base_api_url + "latest"

    if category == "all":
        info = {}
        for i in categories:

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params={'category': i}) as resp:
                    if resp.status == 200:
                        info[i] = (await resp.json())['data']
                    elif resp.status == 500:
                        console.error("The API returned 500 Internal Server Error. Please check the API logs.")
                        return

    elif category in categories:

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params={'category': category}) as resp:
                if resp.status == 200:
                    info = (await resp.json())['data']
                elif resp.status == 500:
                    console.error("The API returned 500 Internal Server Error. Please check the API logs.")
                    return
                else:
                    return

    else:
        return

    console.debug(info)
    return info


async def get_png(download_url: str) -> list or None:
    url = base_api_url + "getpng"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params={'url': download_url}) as resp:
            if resp.status == 200:
                return list((await resp.json())['data'])
            elif resp.status == 500:
                console.error("The API returned 500 Internal Server Error. Please check the API logs.")
                return


async def search(query: str) -> tuple or None:
    url = base_api_url + "search"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params={'query': query, "amount": 3}) as resp:
            if resp.status == 200:
                return (await resp.json())['data']
            elif resp.status == 500:
                console.error("The API returned 500 Internal Server Error. Please check the API logs.")
                return


async def log(level, category, msg, *args):
    # Db Structure - type, msg, category, timestamp, level
    # categories = ["command", "listener", "backend", "etc"]
    current_time = int(time.time())
    if level.upper() not in ["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"]:
        level = "INFO"

    # join msg and args into one string
    if args:
        msg %= args
    msg.replace('"', "")

    # This code logs the message using the correct level's logger based on the level parameter
    match level.upper():
        case "DEBUG":
            console.debug(msg)
        case "INFO":
            console.info(msg)
        case "WARNING":
            console.warning(msg)
        case "ERROR":
            console.error(msg)
        case "CRITICAL":
            console.critical(msg)

    if category not in ["command", "notification", "listener", "backend", "etc"]:
        category = "etc"

    db = sqlite3.connect('./data/data.db')
    cursor = db.cursor()

    cursor.execute('INSERT INTO logs VALUES (?, ?, ?, ?)', (current_time, level, category, msg))
    db.commit()


async def send_to_guilds(guilds, channels, messages, notif_msgs, embed, embed_list, error_embed, id_):
    con = sqlite3.connect('./data/data.db')
    cur = con.cursor()

    for guild, channel, message in zip(guilds, channels, messages):  # For each guild in the database

        # Set the custom message if there is one
        console.debug(f"Message: {message}")
        embed.description = message  # Set the description of the embed to the message

        try:  # Try to fetch the guild and channel from the discord API
            guild = await client.fetch_guild(int(guild))  # Get the guild object
            channel = await guild.fetch_channel(int(channel))  # Get the channel object

        except discord.NotFound:  # If the channel or guild is not found (deleted)
            console.warning(f"Guild or channel not found. Guild: {guild}, Channel: {channel}")
            cur.execute("DELETE FROM guild_notify WHERE guild_id = ? AND channel_id = ?",
                        (guild, channel))
            con.commit()
            continue

        except discord.Forbidden:  # If the bot can not get the channel or guild
            console.warning(f"Could not get channel. Guild: {guild}, Channel: {channel}. "
                            "Seems like I was kicked from the server.")
            cur.execute("DELETE FROM guild_notify WHERE guild_id = ? AND channel_id = ?",
                        (guild.id, channel))
            con.commit()
            continue

        except Exception as e:  # If there is any other error
            console.error(f"Error: {e}")
            continue

        try:  # Try to send the message
            _msg = await channel.send(embeds=[embed.copy(), *embed_list])  # Send the embed
            console.debug(f"Sent Circular Embed to {guild.id} | {channel.id}")

        except discord.Forbidden:  # If the bot doesn't have permission to send messages in the channel
            for _channel in guild.text_channels:  # Find a channel where it can send messages

                try:  # Try to send the error embed
                    await _channel.send(embed=error_embed)  # Send the error embed
                    _msg = await _channel.send(embeds=[embed.copy(), *embed_list])  # Send the circular embed
                    console.warning(
                        f"Could not send message to {channel.id} in {guild.id}. Sent to {channel.id} instead.")
                    channel = _channel  # Set the channel to the new channel
                    break

                except discord.Forbidden:  # If the bot can't send messages in the channel
                    continue

            else:  # If it can't send the message in any channel
                console.error(f"Couldn't send Circular to {guild.id}'s {channel.id}")
                continue

        except Exception as e:  # If it can't send the circular embed
            console.error(
                f"Couldn't send Circular Embed to {guild.id}'s | {channel.id}. Not discord.Forbidden." + str(e))
            continue

        try:
            cur.execute("INSERT INTO notif_msgs (circular_id, msg_id, type, channel_id, guild_id) "
                        "VALUES (?, ?, ?, ?, ?)", (id_, _msg.id, "guild", channel.id, guild.id))
            con.commit()
            notif_msgs["guild"].append((_msg.id, channel.id, guild.id))
        except Exception as e:
            console.error(f"Error: {e}")

    con.close()


async def send_to_users(user_id, user_message, notif_msgs, embed, embed_list, id_):
    con = sqlite3.connect('./data/data.db')
    cur = con.cursor()
    for user, message in zip(user_id, user_message):  # For each user in the database

        try:  # Try to get the user
            user = await client.fetch_user(int(user))  # Get the user object

        except discord.NotFound:  # If the user is not found (deleted)
            console.warning(f"User not found. User: {user}")
            cur.execute("DELETE FROM dm_notify WHERE user_id = ?", (user.id,))
            con.commit()
            continue

        except Exception as e:  # If there is any other error
            console.error(f"Could get fetch a user {user}. Error: {e}")
            continue

        console.debug(f"[Listeners] | Message: {message}")
        embed.description = message

        try:  # Try to send the embed to the user
            _msg = await user.send(embeds=[embed.copy(), *embed_list])  # Send the embed to the user
            console.debug(f"Successfully sent Circular in DMs to {user.name}#{user.discriminator} | {user.id}")

        except discord.Forbidden:  # If the user has DMs disabled
            console.error(
                f"Could not send Circular in DMs to {user.name}#{user.discriminator} | {user.id}. DMs are disabled.")
            cur.execute("DELETE FROM dm_notify WHERE user_id = ?", (user.id,))
            con.commit()
            await log('info', 'listener',
                      f"Removed {user.name}#{user.discriminator} | {user.id} from the DM notify list.")
            continue

        except Exception as e:  # If the user has DMs disabled
            console.error(f"Couldn't send Circular Embed to User: {user.id}")
            console.error(e)
            continue

        try:
            notif_msgs["dm"].append((_msg.id, user.id))
            cur.execute("INSERT INTO notif_msgs (circular_id, msg_id, type, channel_id) "
                        "VALUES (?, ?, ?, ?)", (id_, _msg.id, "dm", user.id))
            con.commit()
        except Exception as e:
            console.error(f"Error: {e}")

    con.close()


# Confirm Button Discord View
class ConfirmButton(discord.ui.View):  # Confirm Button Class
    def __init__(self, author):
        super().__init__()
        self.value = None
        self.author = author

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not interaction.user.id == self.author.id:
            return await interaction.response.send_message("This button is not for you", ephemeral=True)

        self.value = True

        for child in self.children:  # Disable all buttons
            child.disabled = True

        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not interaction.user.id == self.author.id:
            return await interaction.response.send_message("This button is not for you", ephemeral=True)

        self.value = False

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(view=self)
        self.stop()


# Delete Button Discord View
class DeleteButton(discord.ui.View):
    def __init__(self, ctx, msg, author_only=True):
        super().__init__(timeout=300)
        self.msg = msg
        self.author = ctx.author
        self.author_only = author_only

    # disable the delete button on timeout
    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        await self.msg.edit(view=self)
        self.stop()

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.red)
    async def button_callback(self, button, interaction):  # Don't remove the unused argument, it's used by py-cord
        if self.author_only:
            if not interaction.user.id == self.author.id:
                return await interaction.response.send_message("This button is not for you", ephemeral=True)
        await self.msg.delete()


# Feedback Button Discord View
class FeedbackButton(discord.ui.View):
    def __init__(self, msg, author, search_query, search_result, author_only=True):
        super().__init__(timeout=300)
        self.msg = msg
        self.author = author
        self.author_only = author_only
        self.search_query = search_query
        self.search_result = search_result

    # disable the button on timeout
    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        await self.msg.edit(view=self)
        self.stop()

    @discord.ui.button(label="👍", style=discord.ButtonStyle.green)
    async def thumbs_up_button_callback(self, button,
                                        interaction):  # Don't remove the unused argument, it's used by py-cord
        if self.author_only:
            if interaction.user.id != self.author.id:
                return await interaction.response.send_message("This button is not for you", ephemeral=True)

        con = sqlite3.connect("./data/data.db")
        cur = con.cursor()
        self.search_query = self.search_query.replace('"', "")
        cur.execute(
            f"INSERT INTO search_feedback VALUES (?, ?, ?, ?)",
            (interaction.user.id, self.msg.id, self.search_query, True)
        )

        con.commit()
        con.close()

        await interaction.response.send_message("Thanks for your feedback!", ephemeral=True)

        for child in self.children:
            child.disabled = True
        await self.msg.edit(view=self)
        self.stop()

    @discord.ui.button(label="👎", style=discord.ButtonStyle.red)
    async def thumbs_down_button_callback(self, button,
                                          interaction):  # Don't remove the unused argument, it's used by py-cord
        if self.author_only:
            if not interaction.user.id == self.author.id:
                return await interaction.response.send_message("This button is not for you", ephemeral=True)

        con = sqlite3.connect("./data/data.db")
        cur = con.cursor()
        self.search_query = self.search_query.replace('"', "")
        cur.execute(
            f"INSERT INTO search_feedback VALUES (?, ?, ?, ?)",
            (interaction.user.id, self.msg.id, self.search_query, False)
        )
        con.commit()
        con.close()

        await interaction.response.send_message(
            "We're sorry to about hear that. Please let us know what went wrong! Feel free to DM <@837584356988944396>",
            ephemeral=True)

        for child in self.children:
            child.disabled = True
        await self.msg.edit(view=self)
        self.stop()


async def create_search_dropdown(options: list or tuple, msg):
    class SearchDropdown(discord.ui.View):
        def __init__(self, msg):
            super().__init__(timeout=60)
            self.value = None
            self.msg = msg

        @discord.ui.select(
            placeholder="Select a circular",
            min_values=1,
            max_values=1,
            options=options
        )
        async def select_callback(self, select, interaction):
            self.value = select.values[0][-4:]

            for child in self.children:
                child.disabled = True

            await interaction.response.edit_message(view=self)

            self.stop()

        async def on_timeout(self):
            for child in self.children:
                child.disabled = True
            await self.msg.edit(view=self)
            self.stop()

    return SearchDropdown(msg)
