![Lines of Code](https://img.shields.io/tokei/lines/github/BPS-Circular-API/discord-bot?style=for-the-badge)
![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11-blue?style=for-the-badge)
![CodeFactor Grade](https://img.shields.io/codefactor/grade/github/BPS-Circular-API/discord-bot?style=for-the-badge)
---

# BPS Circular Discord Bot
The official BPS Circular API Discord Bot is a bot that allows you to get the latest circulars from the BPS Circular API. It is written in Python using the `py-cord` library. It uses my own [BPS Circular API](https://github.com/BPS-Circular-API/api)

It uses my own BPS Circular API to get the latest circulars.

## Project Directory

```
├───data
│   ├───data.db
│   └───config.ini
├───cogs
│   ├───commands.py
│   ├───listeners.py
│   └───owners.py
├───main.py
├───backend.py
├───requirements.txt
├───README.md
```
- main.py contains the basic discord bot, backend.py contains all bakcend functions that communicate with the API and all reusable code.
- cogs/commands.py contains all of the user-comamnds. they use the backend functions.
- cogs/listeners.py contains event listeners and background tasks.
- cogs/owners.py contains commands to be used only by bot owners.
- data/config.ini is the main configuration file for this bot.
- data/data.db stores all the bot's data.

## Uses 

Here is what the bot can do - https://bpsapi.rajtech.me/docs/discord-bot/using-the-bot/features

## Documentation ###

The documentation for the bot can be found [here](https://bpsapi.rajtech.me/docs/category/discord-bot).

---
