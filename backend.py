import configparser, discord, logging, requests, pickle
from discord.ext import commands
from colorlog import ColoredFormatter

categories = ["general", "exam", "ptm"]
receives = ["all", "links", "titles"]

# Loading config.ini
config = configparser.ConfigParser()

try:
   config.read('data/config.ini')
except Exception as e:
    print("Error reading the config.ini file. Error: " + str(e))
    exit()


try:
    discord_token: str = config.get('secret', 'discord-token')
    log_level: str = config.get('main', 'log-level')
    owner_ids = config.get('main', 'owner-ids').strip().split(',')
    owner_guilds = config.get('main', 'owner-guilds').strip().split(',')
    base_api_url: str = config.get('main', 'base_api_url')
    backup_interval: int = config.getint('main', 'backup_interval')
    amount_to_cache: int = config.getint('main', 'amount_to_cache')

    embed_footer: str = config.get('discord', 'embed_footer')
    embed_color: int = int(config.get('discord', 'embed_color'), base=16)
    embed_title: str = config.get('discord', 'embed_title')
    embed_url: str = config.get('discord', 'embed_url')

except Exception as err:
    print("Error reading the config.ini file. Error: " + str(err))
    owner_guilds = owner_ids = []
    exit()



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
    # Set logger level
    if log_level.upper() in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        logger.setLevel(log_level.upper())
    else:
        log.warning(f"Invalid log level {log_level}. Defaulting to INFO.")
        logger.setLevel("INFO")
    return logger # Return the logger

log = colorlogger()


owner_ids = tuple([int(i) for i in owner_ids])
log.debug(owner_ids)

owner_guilds = tuple([int(i) for i in owner_guilds])
log.debug(owner_guilds)


client = commands.Bot(help_command=None)  # Setting prefix



async def get_circular_list(category: str) -> tuple | None:
    url = base_api_url + "list"
    if not category in ["ptm", "general", "exam"]:
        return None

    params = {'category': category}

    request = requests.get(url, params=params)
    log.debug(request.json())
    if int(request.json()['http_status']) == 500:
        log.error("The API returned 500 Internal Server Error. Please check the API logs.")
        return
    return tuple(request.json()['data'])



async def get_latest_circular(category: str, cached=False) -> dict | None:
    url = base_api_url + "latest" if not cached else base_api_url + "cached-latest"

    if category == "all":
        info = {}
        for i in categories:
            params = {'category': i}
            request = requests.get(url, params=params)
            res = request.json()
            info[i] = res['data']
    elif category in ['ptm', 'general', 'exam']:
        params = {'category': category}
        request = requests.get(url, params=params)
        try:
            info = request.json()['data']
        except Exception as errr:
            log.error(f"Error in get_latest_circular: {errr}")
            return
        if int(request.json()['http_status']) == 500:
            log.error("The API returned 500 Internal Server Error. Please check the API logs.")
            return
    else:
        return

    log.debug(info)
    return info




async def get_png(download_url: str) -> str | None:
    url = base_api_url + "getpng"
    params = {'url': download_url}

    request = requests.get(url, params=params)
    log.debug(request.json())

    if int(request.json()['http_status']) == 500:
        log.error("The API returned 500 Internal Server Error. Please check the API logs.")
        return
    return str(request.json()['data'])



async def search(title:  str) -> dict | None:
    url = base_api_url + "search"

    params = {'title': title}

    request = requests.get(url, params=params)
    log.debug(request.json())

    if int(request.json()['http_status']) == 500:
        log.error("The API returned 500 Internal Server Error. Please check the API logs.")
        return
    return request.json()['data']


def get_cached():
    # get dict from data/temp.pickle
    with open("./data/temp.pickle", "rb") as f:
        return pickle.load(f)


def set_cached(obj):
    # set dict to data/temp.pickle
    with open("./data/temp.pickle", "wb") as f:
        pickle.dump(obj, f)


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
    async def button_callback(self, button, interaction): # Don't remove the unused argument, it's used by py-cord
        if self.author_only:
            if not interaction.user.id == self.author.id:
                return await interaction.response.send_message("This button is not for you", ephemeral=True)
        await self.msg.delete()
