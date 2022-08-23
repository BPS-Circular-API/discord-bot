import asyncio
import configparser, discord, logging, requests
# from rank_bm25 import BM25Okapi
import os

from discord.ext import commands
import pypdfium2 as pdfium


bot_version = "0.1.0"
# indents for guilds and channels
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
    owner_ids: list = config.get('main', 'owner-ids').strip().split(',')

    embed_footer: str = config.get('discord', 'embed_footer')
    embed_color: int = int(config.get('discord', 'embed_color'), base=16)
    embed_title: str = config.get('discord', 'embed_title')
    embed_url: str = config.get('discord', 'embed_url')



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


owner_ids = [int(i) for i in owner_ids]
log.debug(str(owner_ids))

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
    url = "https://bpsapi.rajtech.me/v1/list/"
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
    url = "https://bpsapi.rajtech.me/v1/latest/"
    if not category in ["ptm", "general", "exam"]:
        return None

    payload = {'category': category}

    request = requests.get(url, json=payload)
    info = request.json()
    log.debug(info)
    return info



async def get_circular_url(circular_name: str) -> dict | None:
    url = "https://bpsapi.rajtech.me/v1/search/"
    if not circular_name:
        return None

    payload = {'title': circular_name}

    request = requests.get(url, json=payload)
    info = request.json()
    log.debug(info)
    return info



async def get_latest_circular_cached(category: str) -> dict | None:
    url = "https://bpsapi.rajtech.me/v1/cached-latest/"
    if not category in ["ptm", "general", "exam"]:
        return None

    payload = {'category': category}

    request = requests.get(url, json=payload)
    info = request.json()
    log.debug(info)
    return info


async def get_png(download_url, file_name: str):
    windows_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36'}
    pdf_file = requests.get(download_url, headers=windows_headers)

    with open(f"./{file_name}.pdf", "wb") as f:
        f.write(pdf_file.content)

    pdf = pdfium.PdfDocument(f"./{file_name}.pdf")
    page = pdf[0]
    pil_image = page.render_topil(
        scale=2,
        rotation=0,
        crop=(0, 0, 0, 0),
        colour=(255, 255, 255, 255),
        annotations=True,
        greyscale=False,
        optimise_mode=pdfium.OptimiseMode.NONE,
    )
    pil_image.save(f"./{file_name}.png")
    os.remove(f"./{file_name}.pdf")

    return f"./{file_name}.png"




async def search(title):
    url = "https://bpsapi.rajtech.me/v1/search/"
    if not title:
        return None

    payload = {'title': title}

    request = requests.get(url, json=payload)
    info = request.json()
    log.debug(info)
    return info
