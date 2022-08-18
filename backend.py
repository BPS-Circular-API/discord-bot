import configparser, discord, logging, requests
from discord.ext import commands

bot_version = "0.1.0"
intents = discord.Intents.none()
prefix = "!"
categories = ["ptm", "general", "exam"]
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

    embed_footer: str = config.get('discord', 'embed_footer')
    embed_color: int = int(config.get('discord', 'embed_color'), base=16)
    embed_title: str = config.get('discord', 'embed_title')



except Exception as err:
    print("Error reading the config.ini file. Error: " + str(err))
    exit()

# Initializing the logger
def colorlogger(name='moonball'):
    from colorlog import ColoredFormatter
    # disabler loggers
    for logger in logging.Logger.manager.loggerDict:
        logging.getLogger(logger).disabled = True
    logger = logging.getLogger(name)
    stream = logging.StreamHandler()
    LogFormat = "%(reset)s%(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s"
    stream.setFormatter(ColoredFormatter(LogFormat))
    logger.addHandler(stream)
    # Set logger level
    if log_level.upper() in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        logger.setLevel(log_level.upper())
    else:
        log.warning(f"Invalid log level {log_level}. Defaulting to INFO.")
        logger.setLevel("INFO")
    return logger # Return the logger

log = colorlogger()

"""
try:
    con = sqlite3.connect('./data/data.db')
except Exception as err:
    log.error("Error: Could not connect to data.db." + str(err))
    exit(1)
cur = con.cursor()
"""
client = commands.Bot(command_prefix=prefix, intents=intents, help_command=None, case_insensitive=True)  # Setting prefix



async def get_circular_list(category: str, receive: str = "all") -> list | None:
    url = "https://raj.moonball.io/bpsapi/v1/list/"
    if not category in ["ptm", "general", "exam"]:
        return None
    if not receive in ["all", "links", "titles"]:
        return None

    payload = {'category': category, "receive": receive}

    request = requests.get(url, json=payload)
    info = request.json()
    log.debug(info)
    return info


async def get_latest_circular(category: str) -> dict | None:
    url = "https://raj.moonball.io/bpsapi/v1/latest/"
    if not category in ["ptm", "general", "exam"]:
        return None

    payload = {'category': category}

    request = requests.get(url, json=payload)
    info = request.json()
    log.debug(info)
    return info