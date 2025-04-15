import asyncio
import configparser
import sqlite3
from datetime import datetime
import discord
import logging
import aiohttp
import sys

from discord import Embed
from discord.ext import commands
from colorlog import ColoredFormatter
import requests
import mysql.connector

def get_db(storage_method_override=None) -> tuple:

    if storage_method_override is not None:
        if storage_method_override == "mysql":
            con = mysql.connector.connect(**mysql_config)
            cur = con.cursor(prepared=True)
        else:
            con = sqlite3.connect('./data/data.db')
            cur = con.cursor()

        return con, cur

    if storage_method == "mysql":
        con = mysql.connector.connect(**mysql_config)
        cur = con.cursor(prepared=True)
    else:
        con = sqlite3.connect('./data/data.db')
        cur = con.cursor()

    return con, cur


class SQLHandler(logging.Handler):
    """Custom logging handler that saves log messages to a database."""

    def __init__(self):
        super().__init__()

    def emit(self, record):
        """Insert a log record into the database."""
        if record.levelname.upper() == "DEBUG":
            return


        con, cur = get_db()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname
        message = self.format(record)
        filename = record.pathname  # Full file path
        function_name = record.funcName  # Function name
        line_number = record.lineno  # Line number
        thread_name = record.threadName  # Thread name
        process_id = record.process  # Process ID
        exception_info = record.exc_text if record.exc_info else None  # Exception details

        cur.execute(
            "INSERT INTO logs (timestamp, level, filename, function_name, line_number, thread_name, process_id, message, exception_info) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (timestamp, level, filename, function_name, line_number, thread_name, process_id, message, exception_info),
        )

        con.commit()
        con.close()

# Initializing the logger
def colorlogger(name='bps-circular-bot'):
    # disabler loggers
    # for logger in logging.Logger.manager.loggerDict:
    #    logging.getLogger(logger).disabled = True
    logger = logging.getLogger(name)
    log_format = "%(reset)s%(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s"

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter(log_format))

    # DB Handler
    db_handler = SQLHandler()
    db_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    logger.addHandler(console_handler)
    logger.addHandler(db_handler)

    return logger


console = colorlogger()

# Loading config.ini
config = configparser.RawConfigParser()

# Attempt to open the config file
try:
    config.read('./data/config.ini')
except Exception as e:
    print("Error reading the config.ini file. Error: " + str(e))
    sys.exit()

# Attempt to get all required variables
try:
    discord_token: str = config.get('secret', 'discord_token')
    log_level: str = config.get('main', 'log_level')
    owner_ids = config.get('main', 'owner_ids').strip().split(',')
    owner_guilds = config.get('main', 'owner_guilds').strip().split(',')
    base_api_url: str = config.get('main', 'base_api_url')
    fallback_api_url: str = config.get('main', 'fallback_api_url')
    backup_interval: int = config.getint('main', 'backup_interval')
    status_interval: int = config.getint('main', 'status_interval')
    circular_check_interval: int = config.getint('main', 'circular_check_interval')
    ignored_circulars = config.get('main', 'ignored_circulars').strip().split(',')
    statuses: str = config.get('main', 'statuses').strip()
    invite_url: str = config.get('main', 'invite_url').strip()
    discord_invite_url: str = config.get('main', 'discord_invite_url').strip()
    storage_method: str = config.get('main', 'storage_method').strip()

    embed_footer: str = config.get('discord', 'embed_footer')
    embed_color: int = int(config.get('discord', 'embed_color'), base=16)
    embed_title: str = config.get('discord', 'embed_title')
    embed_url: str = config.get('discord', 'embed_url')

    if storage_method == "mysql":
        mysql_config: dict = {
            'user': config.get('mysql', 'user'),
            'password': config.get('mysql', 'password'),
            'host': config.get('mysql', 'host'),
            'database': config.get('mysql', 'database'),
            'port': config.get('mysql', 'port'),
            'raise_on_warnings': False
        }
    else:
        mysql_config = {}
except Exception as err:
    console.critical("Error reading the config.ini file. Error: " + str(err))
    sys.exit()

# Log Level
if log_level.upper() in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
    console.setLevel(log_level.upper())
else:
    console.setLevel("INFO")
    console.warning(f"Invalid log level {log_level}. Defaulting to INFO.")

# Owners' IDs and Guilds
owner_ids = tuple([int(i) for i in owner_ids])
owner_guilds = tuple([int(i) for i in owner_guilds])

# Ignored Circulars
if ignored_circulars == ['']:
    ignored_circulars = tuple()
else:
    try:
        ignored_circulars = tuple([int(i) for i in ignored_circulars])
    except ValueError:
        console.warning("Could not form a list of ignored circulars. Is it correctly formatted in config.ini?")

# Base API URL
if base_api_url[-1] != "/":  # For some very bright people who don't know how to read
    base_api_url += "/"
if fallback_api_url[-1] != "/":
    fallback_api_url += "/"


# Bot discord presences
statuses: list = statuses.split(',')
for i in range(len(statuses)):
    statuses[i] = statuses[i].strip()
    statuses[i] = statuses[i].split('|')



async def send_async_api_request(url: str, params: dict = None, fallback=False) -> dict | None:
    timeout = aiohttp.ClientTimeout(total=5, connect=2)
    try:
        console.debug(f"Sending API request to {url} with params: {params}")
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    console.debug(f"Received successful response from {url}")
                    return data['data']
                elif resp.status == 422:
                    console.error(f"API returned status 422 for {url}. Params: {params}")
                else:
                    console.error(f"API returned status {resp.status} for {url}")
                    return None
    except asyncio.TimeoutError:
        if fallback:
            console.error(f"API request to {url} timed out. Fallback also timed out.")
            return None
        else:
            console.warning(f"API request to {url} timed out. Trying fallback API.")
            return await send_async_api_request(fallback_api_url + url.split(base_api_url)[1], params, True)
    except aiohttp.ClientError as e:
        if fallback:
            console.error(f"Error while connecting to the API at {url}. Error: {e}")
            return None
        else:
            console.warning(f"Error while connecting to the API at {url}. Trying fallback API. Error: {e}")
            return await send_async_api_request(fallback_api_url + url.split(base_api_url)[1], params, True)

def send_api_request(url: str, params: dict = None, fallback=False) -> dict | None:
    try:
        console.debug(f"Sending API request to {url} with params: {params}")
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        console.debug(f"Received successful response from {url}")
        return data['data']
    except requests.exceptions.Timeout:
        if fallback:
            console.error(f"API request to {url} timed out. Fallback also timed out.")
            return None
        else:
            console.warning(f"API request to {url} timed out. Trying fallback API.")
            return send_api_request(fallback_api_url + url.split(base_api_url)[1], params, True)
    except requests.exceptions.RequestException as e:
        if fallback:
            console.error(f"Error while connecting to the API at {url}. Error: {e}")
            return None
        else:
            console.warning(f"Error while connecting to the API at {url}. Trying fallback API. Error: {e}")
            return send_api_request(fallback_api_url + url.split(base_api_url)[1], params, True)


categories = send_api_request(base_api_url + "categories")
if categories is None:
    console.critical("Could not get categories from the API. Exiting.")
    sys.exit(1)



def init_database():
    # Check the database and verify if all required tables are there
    _con, _cur = get_db()

    # Create table DM Notify
    _cur.execute(
        "CREATE TABLE IF NOT EXISTS `dm_notify` (user_id BIGINT UNSIGNED NOT NULL, message TEXT "
        "DEFAULT 'A new Circular was just posted on the website!' )"
    )

    # Create table guild notify
    _cur.execute(
        """
        CREATE TABLE IF NOT EXISTS `guild_notify` (
            guild_id BIGINT UNSIGNED NOT NULL UNIQUE,
            channel_id BIGINT UNSIGNED UNIQUE,
            message TEXT DEFAULT 'There''s a new circular up on the website!'
        );
    """
    )

    _cur.execute(
        """
        CREATE TABLE IF NOT EXISTS `notif_msgs` ( 	
            circular_id	INT NOT NULL, 	
            type	TEXT NOT NULL, 	
            msg_id	BIGINT UNSIGNED NOT NULL UNIQUE, 	
            channel_id	BIGINT UNSIGNED, 	
            guild_id	BIGINT UNSIGNED 
        )
        """
    )

    sql = """
            CREATE TABLE IF NOT EXISTS `logs` (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp DATETIME NOT NULL,
                level VARCHAR(50) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                function_name VARCHAR(255) NOT NULL,
                line_number INT NOT NULL,
                thread_name VARCHAR(255) NOT NULL,
                process_id INT NOT NULL,
                message TEXT NOT NULL,
                exception_info TEXT NULL
            );
        """
    _cur.execute(sql)

    _con.commit()
    _con.close()

client = commands.Bot(help_command=None)

console.debug("Owner IDs: " + str(owner_ids))
console.debug("Owner Guilds: " + str(owner_guilds))
console.debug("Ignored Circulars: " + str(ignored_circulars))


async def get_circular_list(category: str) -> tuple | None:
    url = base_api_url + "list/" + category
    if category not in categories:
        raise ValueError(f"Invalid Category. `{category}` was passed in while `{categories}` are valid.")

    data = await send_async_api_request(url)
    return tuple(data)


async def get_latest_circular(category: str) -> dict | None:
    url = base_api_url + "latest/"

    # If the latest between all categories is requested
    if category == "all":
        latest_circular = []

        # Get the latest circulars of each category
        for category in categories:
            async with aiohttp.ClientSession(timeout=10) as session:
                data = await send_async_api_request(url + category)
                latest_circular.append(data)

        # Get the circular with the highest ID in the latest circulars of each category
        latest_circular = max(latest_circular, key=lambda element: element['id'])

    # If the latest circular of a valid category is requested
    elif category in categories:
        data = await send_async_api_request(url + category)
        latest_circular = data

    else:
        raise ValueError(f"Invalid Category. `{category}` was passed in while `{categories}` and `all` are valid.")

    console.debug(latest_circular)
    return latest_circular


async def get_png(download_url: str) -> tuple | None:
    url = base_api_url + "getpng"
    params = {'url': download_url}

    data = await send_async_api_request(url, params)
    return tuple(data)


async def search(query: str | int, amount: int = 3) -> tuple | None:
    url = base_api_url + "search"
    params = {'query': query, "amount": amount}

    data = await send_async_api_request(url, params)
    return tuple(data)


async def send_to_guilds(
        guilds: list, channels: list, messages: list, notif_msgs: dict, embed_list: tuple[discord.Embed],
        error_embed: discord.Embed, id_: int
):
    con, cur = get_db()
    embed = embed_list[0]
    for guild, channel, message in zip(guilds, channels, messages):  # For each guild in the database

        # Set the custom message if there is one
        console.debug(f"Message: {message}")
        embed.description = message

        # Try to fetch the guild and channel from the discord API
        try:
            guild = await client.fetch_guild(int(guild))
            channel = await guild.fetch_channel(int(channel))

        # If the channel or guild is not found (deleted)
        except discord.NotFound:
            if type(guild) is not int:
                guild = guild.id

            console.warning(
                f"Guild or channel not found. Guild: {guild}, Channel: {channel}. "
                "Seems like I was kicked from the server. Deleting from DB"
            )
            cur.execute(
                "DELETE FROM guild_notify WHERE guild_id = ? AND channel_id = ?",
                (guild, channel)
            )
            con.commit()
            continue

        except discord.Forbidden:  # TODO find out if this can even happen
            if type(guild) is not int:
                guild = guild.id

            console.warning(f"No permission to get guild/channel. Guild: {guild}, Channel: {channel}.")
            continue

        except Exception as e:
            console.error(f"Error: {e}")
            continue

        # Try to send the message
        try:
            _msg = await channel.send(embeds=list(embed_list))
            console.debug(f"Sent Circular Embed to {guild.id} | {channel.id}")

        # If the bot doesn't have permissions to post in the channel
        except discord.Forbidden:

            console.warning(
                    f"Couldn't send Circular to {guild.id}'s {channel.id} due to discord.Forbidden while attempting to send. "
                    f"Deleting from DB.1"
            )
            cur.execute(
                "DELETE FROM guild_notify WHERE guild_id = ? AND channel_id = ?",
                (guild.id, channel.id)
            )
            con.commit()
            continue

        except Exception as e:
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


async def send_to_users(user_ids: list, user_messages: list[str], notif_msgs: dict, embed_list: list[Embed],
                        id_: int):
    con, cur = get_db()
    embed = embed_list[0]

    for user_id, message in zip(user_ids, user_messages):

        try:
            user = await client.fetch_user(int(user_id))

        # If the user is not found (deleted)
        except discord.NotFound:
            console.warning(f"discord.NotFound while fetching user `{user_id}` to send notification to. Removed from database")

            cur.execute("DELETE FROM dm_notify WHERE user_id = ?", (user_id,))
            con.commit()
            continue

        # If there is any other error
        except Exception as e:
            console.error(f"Could get fetch a user {user_id}. Error: {e}")
            continue

        console.debug(f"[Listeners] | Message: {message}")
        embed.description = message

        # Try to send the embed
        try:
            _msg = await user.send(embeds=list(embed_list))  # Send the embed to the user
            console.debug(f"Successfully sent Circular in DMs to {user.name} ({user.display_name}) | {user.id}")

        # If their DMs are disabled/bot is blocked
        except discord.Forbidden:
            console.warning(
                f"Could not send Circular in DMs to {user.name} ({user.display_name}) | {user.id}. DMs are disabled. "
                f"Removed from database"
            )

            # Remove them from database
            cur.execute("DELETE FROM dm_notify WHERE user_id = ?", (user_id,))
            con.commit()
            continue

        except Exception as e:
            console.error(f"Couldn't send Circular Embed to User: {user_id}")
            console.error(e)
            continue

        try:
            notif_msgs["dm"].append((_msg.id, user.id))
            cur.execute("INSERT INTO notif_msgs (circular_id, msg_id, type, channel_id) "
                        "VALUES (?, ?, ?, ?)", (id_, _msg.id, "dm", user_id))
            con.commit()
        except Exception as e:
            console.error(f"Error: {e}")

    con.close()


def multi_page_embed_generator(png_urls: tuple, embed: discord.Embed, link: str):
    """
    If the circular has more than 1 page, this function will create duplicate discord embeds with different
    page images and add it to the embed_list.
    """
    embed_list = [embed]

    if len(png_urls) > 1:
        # Range starts from 1 because the first page is already added to the embed_list
        for i in range(1, len(png_urls)):
            # If the circular has more than 4 pages, only send the first 4
            # This is due to the discord embed limit of 4 images.
            if i > 3:
                embed_list[0].add_field(
                    name="Note",
                    value=f"This circular has {len(png_urls) - 4} more pages. Please visit the [link]({link}) to view them.",
                    inline=False
                )
                break

            temp_embed = discord.Embed(url=embed_url)
            temp_embed.set_image(url=png_urls[i])
            embed_list.append(temp_embed.copy())

    return embed_list


# Confirm Button Discord View
class ConfirmButton(discord.ui.View):
    def __init__(self, user_id):
        super().__init__()
        self.value = None
        self.user_id = user_id

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm_callback(self, button: discord.ui.Button, interaction: discord.Interaction):

        # If a different user tries to interact with the button
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This button is not for you", ephemeral=True)
            return

        # Set the view's value to True (for callback)
        self.value = True

        # Disable all buttons
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel_callback(self, button: discord.ui.Button, interaction: discord.Interaction):

        # If a different user tries to interact with the button
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This button is not for you", ephemeral=True)
            return

        # Set the view's value to False (for callback)
        self.value = False

        # Disable all buttons
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(view=self)
        self.stop()


# Delete Button Discord View
class DeleteButton(discord.ui.View):
    def __init__(self, msg, user_id: int = None, timeout: int = 60):
        super().__init__(timeout=timeout)

        self.msg = msg
        self.user_id = user_id

    # disable the delete button on timeout
    async def on_timeout(self):

        for child in self.children:
            child.disabled = True

        try:
            await self.msg.edit(view=self)
        except discord.NotFound:
            console.warning("DeleteButton couldn't perform msg.edit due to message not found")
        self.stop()

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.red)
    async def button_callback(self, button, interaction):
        # If user_id is passed, restrict button usage to that user
        if self.user_id:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This button is not for you", ephemeral=True)
                return

        await self.msg.delete()


# Feedback Button Discord View
class FeedbackButton(discord.ui.View):
    def __init__(self, msg, search_query, search_result, user_id: int = None):
        super().__init__(timeout=300)
        self.msg = msg
        self.user_id = user_id
        self.search_query = search_query
        self.search_result = search_result

    # disable the view on timeout
    async def on_timeout(self):

        for child in self.children:
            child.disabled = True

        await self.msg.edit(view=self)
        self.stop()

    @discord.ui.button(label="👍", style=discord.ButtonStyle.green)
    async def thumbs_up_button_callback(self, button, interaction):
        if self.user_id:
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("This button is not for you", ephemeral=True)

        con, cur = get_db()

        self.search_query = self.search_query.replace('"', "")
        cur.execute(
            f"INSERT INTO search_feedback VALUES (?, ?, ?, ?)",
            (interaction.user.id, self.msg.id, self.search_query, True)
        )

        con.commit()
        con.close()

        await interaction.response.send_message("Thanks for your feedback!", ephemeral=True)

        # Disable all buttons
        for child in self.children:
            child.disabled = True

        await self.msg.edit(view=self)
        self.stop()

    @discord.ui.button(label="👎", style=discord.ButtonStyle.red)
    async def thumbs_down_button_callback(self, button,
                                          interaction):  # Don't remove the unused argument, it's used by py-cord
        if self.user_id:
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("This button is not for you", ephemeral=True)

        self.search_query = self.search_query.replace('"', "")

        con, cur = get_db()

        cur.execute(
            f"INSERT INTO search_feedback VALUES (?, ?, ?, ?)",
            (interaction.user.id, self.msg.id, self.search_query, False)
        )

        con.commit()
        con.close()

        await interaction.response.send_message(
            "We're sorry to about hear that. Please let us know what went wrong! Feel free to DM <@837584356988944396>",
            ephemeral=True
        )

        for child in self.children:
            child.disabled = True

        await self.msg.edit(view=self)
        self.stop()


async def create_search_dropdown(options: list[discord.SelectOption], msg, user_id: int = None):
    class SearchDropdown(discord.ui.View):
        def __init__(self, msg):
            super().__init__(timeout=60)
            self.value = None
            self.msg = msg
            self.user_id = user_id

        @discord.ui.select(
            placeholder="Select a circular",
            min_values=1,
            max_values=1,
            options=options
        )
        async def select_callback(self, select, interaction):
            if self.user_id:
                if interaction.user.id != self.user_id:
                    return await interaction.response.send_message("This button is not for you", ephemeral=True)

            # Get the ID of the selected circular
            self.value = select.values[0][-4:]

            # Disable all views
            for child in self.children:
                child.disabled = True

            await interaction.response.edit_message(view=self)
            self.stop()

        async def on_timeout(self):

            for child in self.children:
                child.disabled = True

            embed = discord.Embed(color=discord.Color.red(), title=f"Circular Search | Timed out")
            embed.description = "Uh oh. Looks like you didn't pick the circular you wanted in time :("
            embed.set_footer(text=embed_footer)
            embed.set_author(name=embed_title)

            await self.msg.edit(view=self, embed=embed)
            self.stop()

    return SearchDropdown(msg)
