import asyncio
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
import mysql.connector


# Initializing the logger
def colorlogger(name='bps-circular-bot'):
    # disabler loggers
    # for logger in logging.Logger.manager.loggerDict:
    #    logging.getLogger(logger).disabled = True
    logger = logging.getLogger(name)
    stream = logging.StreamHandler()
    log_format = "%(reset)s%(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s"
    stream.setFormatter(ColoredFormatter(log_format))
    logger.addHandler(stream)
    return logger


console = colorlogger()

# Loading config.ini
config = configparser.RawConfigParser()

# Attempt to open the config file
try:
    config.read('data/config.ini')
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

# Bot discord presences
statuses: list = statuses.split(',')
for i in range(len(statuses)):
    statuses[i] = statuses[i].strip()
    statuses[i] = statuses[i].split('|')

try:
    response = requests.get(base_api_url + "categories", timeout=10)
    response.raise_for_status()  # Raise an error for HTTP status codes 4xx/5xx
    json = response.json()
    if json.get('http_status') == 200:
        categories = json['data']
    else:
        raise ConnectionError("Invalid API Response. HTTP status is not 200.")
except requests.exceptions.Timeout:
    console.critical("API request timed out after 10 seconds.")
    sys.exit(1)
except requests.exceptions.RequestException as e:
    console.critical(f"Error while connecting to the API. Error: {e}")
    sys.exit(1)


async def send_api_request(url: str, params: dict = None) -> dict | None:
    timeout = aiohttp.ClientTimeout(total=15, connect=5)
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
        console.error(f"API request to {url} timed out.")
        return None
    except aiohttp.ClientError as e:
        console.error(f"Error while connecting to the API at {url}. Error: {e}")
        return None



def get_db(storage_method_override: str = None) -> tuple:
    # if storage_method_override: # TODO FIX THIS
    #     storage_method = storage_method_override

    if storage_method == "mysql":
        con = mysql.connector.connect(**mysql_config)
        cur = con.cursor(prepared=True)
    else:
        con = sqlite3.connect('./data/data.db')
        cur = con.cursor()

    return con, cur


def init_database():
    # Check the database and verify if all required tables are there
    _con, _cur = get_db()

    # Create table cache
    # _cur.execute("CREATE TABLE IF NOT EXISTS `cache` (title TEXT, category TEXT, data BLOB)")

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

    # Create table logs
    _cur.execute(
        """
        CREATE TABLE IF NOT EXISTS `logs` (
            timestamp	INTEGER NOT NULL,
            log_level	TEXT DEFAULT 'debug',
            category	TEXT,
            msg	TEXT
        )
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
    _cur.execute(
        """
        CREATE TABLE IF NOT EXISTS `search_feedback` ( 	
            user_id 	BIGINT UNSIGNED, 	
            message_id	BIGINT UNSIGNED, 	
            search_query	TEXT, 	
            response	TEXT 
        )
        """
    )

    _con.commit()
    _con.close()


init_database()
client = commands.Bot(help_command=None)

console.debug("Owner IDs: " + str(owner_ids))
console.debug("Owner Guilds: " + str(owner_guilds))
console.debug("Ignored Circulars: " + str(ignored_circulars))


async def get_circular_list(category: str) -> tuple | None:
    url = base_api_url + "list/" + category
    if category not in categories:
        raise ValueError(f"Invalid Category. `{category}` was passed in while `{categories}` are valid.")

    data = await send_api_request(url)
    return tuple(data)


async def get_latest_circular(category: str) -> dict | None:
    url = base_api_url + "latest/"

    # If the latest between all categories is requested
    if category == "all":
        latest_circular = []

        # Get the latest circulars of each category
        for category in categories:
            async with aiohttp.ClientSession(timeout=10) as session:
                data = await send_api_request(url + category)
                latest_circular.append(data)

        # Get the circular with the highest ID in the latest circulars of each category
        latest_circular = max(latest_circular, key=lambda element: element['id'])

    # If the latest circular of a valid category is requested
    elif category in categories:
        data = await send_api_request(url + category)
        latest_circular = data

    else:
        raise ValueError(f"Invalid Category. `{category}` was passed in while `{categories}` and `all` are valid.")

    console.debug(latest_circular)
    return latest_circular


async def get_png(download_url: str) -> tuple | None:
    url = base_api_url + "getpng"
    params = {'url': download_url}

    data = await send_api_request(url, params)
    return tuple(data)


async def search(query: str | int, amount: int = 3) -> tuple | None:
    url = base_api_url + "search"
    params = {'query': query, "amount": amount}

    data = await send_api_request(url, params)
    return tuple(data)

async def log(level, category, msg, *args):
    # Db Structure - type, msg, category, timestamp, level
    # categories = ["command", "listener", "backend", "etc"]
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

    con, cur = get_db()

    cur.execute('INSERT INTO logs VALUES (?, ?, ?, ?)', (int(time.time()), level.upper(), category, msg))
    con.commit()


async def send_to_guilds(
        guilds: list, channels: list, messages: list, notif_msgs: dict, embed: discord.Embed, embed_list: list,
        error_embed: discord.Embed, id_: int
):
    con, cur = get_db()

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
                f"Guild or channel not found. Guild: {guild}, Channel: {channel}"
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
            _msg = await channel.send(embeds=[embed.copy(), *embed_list])
            console.debug(f"Sent Circular Embed to {guild.id} | {channel.id}")

        # If the bot doesn't have permissions to post in the channel
        except discord.Forbidden:
            # Find a channel where it can send messages
            # TODO: check if this is possible with no intents
            for _channel in guild.text_channels:

                try:
                    await _channel.send(embed=error_embed)
                    _msg = await _channel.send(embeds=[embed.copy(), *embed_list])

                    console.warning(
                        f"Could not send message to {channel.id} in {guild.id}. Sent to {channel.id} instead.")
                    channel = _channel  # Set the channel to the new channel
                    break

                except discord.Forbidden:  # If the bot can't send messages in the channel
                    continue

            else:  # If it can't send the message in any channel
                console.error(
                    f"Couldn't send Circular to {guild.id}'s {channel.id} due to discord.Forbidden while attempting to send.")
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


async def send_to_users(user_ids: list, user_messages: list, notif_msgs: dict, embed: discord.Embed, embed_list: list,
                        id_: int):
    con, cur = get_db()

    for user, message in zip(user_ids, user_messages):

        try:
            user = await client.fetch_user(int(user))

        # If the user is not found (deleted)
        except discord.NotFound:
            console.warning(f"User not found. User: {user}")
            await log('info', 'listener', f'Removed {user} from database due to discord.NotFound')
            cur.execute("DELETE FROM dm_notify WHERE user_id = ?", (user,))
            con.commit()
            continue

        # If there is any other error
        except Exception as e:
            console.error(f"Could get fetch a user {user}. Error: {e}")
            continue

        console.debug(f"[Listeners] | Message: {message}")
        embed.description = message

        # Try to send the embed
        try:
            _msg = await user.send(embeds=[embed.copy(), *embed_list])  # Send the embed to the user
            console.debug(f"Successfully sent Circular in DMs to {user.name} ({user.display_name}) | {user.id}")

        # If their DMs are disabled/bot is blocked
        except discord.Forbidden:
            console.error(
                f"Could not send Circular in DMs to {user.name} ({user.display_name}) | {user.id}. DMs are disabled.")
            await log('info', 'listener',
                      f"Removed {user.name} ({user.display_name}) | {user.id} from the DM notify list.")

            # Remove them from database
            cur.execute("DELETE FROM dm_notify WHERE user_id = ?", (user.id,))
            con.commit()

            continue

        except Exception as e:
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
