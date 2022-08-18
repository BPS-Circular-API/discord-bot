import discord
from discord.ext import commands
from backend import get_circular_list, log, embed_color, embed_footer, embed_title, categories, receives, get_latest_circular, search_circular
from discord import SlashCommandGroup

category_options = []
for i in categories:
    category_options.append(discord.OptionChoice(i.capitalize().strip(), value=i.strip().lower()))
del categories

receive_options = []
for i in receives:
    receive_options.append(discord.OptionChoice(i.capitalize().strip(), value=i.strip().lower()))
del receives


# create slash command group
circular = SlashCommandGroup("circular", "Circular related commands.")
admin = circular.create_subgroup("admin", "Admin commands for the bot")


class Commands(commands.Cog):
    def __init__(self, client):
        self.client = client


    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog : Commands.py loaded.")



    @circular.command(name='list', description='List all circulars in a particular category.')
    async def list(self, ctx, category: discord.Option(choices=category_options), receive: discord.Option(choices=receive_options)):
        await ctx.defer()
        raw_res = await get_circular_list(category, "all")

        titles, unprocessed_links, links = [], [], []   # Define 3 empty lists
        loop_int = 1    # The variable which will be used to add numbers into the embed

        # Loop through the raw API output
        for item in raw_res:
            titles.append(f"**{loop_int}**. `{item['title']}`")  # Add the title to the list
            unprocessed_links.append(f"**{loop_int}**. {item['link']}") # Add the link to the list
            loop_int += 1

        # Remove the redundant download url parameter after ?download=xxxx
        for link in unprocessed_links:
            link = link.split(':')
            link = f"{link[0]}:{link[1]}"
            links.append(link)

        del unprocessed_links

        title_string = "\n".join(titles)
        link_string = "\n".join(links)

        if receive == "all":
            output = f"Here is the result getting the {category.capitalize()} circulars!\n\n> **Titles** \n{title_string}\n\n> **Download URLs**\n{link_string}"
        elif receive == "titles":
            output = f"Here is the result getting the {category.capitalize()} circular titles!\n\n> **Titles** \n{title_string}"
        elif receive == "links":
            output = f"Here is the result getting the {category.capitalize()} circular download links!\n\n> **Download URLs**\n{link_string}"
        else:
            output = ""

        # split the output into chunks of 2000 characters
        if len(output) > 1999:
            # split the output into chunks of 2000 characters
            output = output.split('\n')

            n = 1999    # The total number of characters in each chunk

            final_list = ['']
            for out in output:
                if len(final_list[-1] + out) <= n:  # If the current chunk + the next chunk is less than 2000 characters
                    final_list[-1] += '\n' + out    # Add the next chunk to the current chunk
                else:
                    final_list.append(out)       # If the current chunk + the next chunk is greater than 2000 characters, add the next chunk to the list

            for i in final_list:
                await ctx.followup.send(i)
        else:
            await ctx.followup.send(output)



    @circular.command(name="latest", description="Sends the latest circular in a particular category.")
    async def latest(self, ctx, category: discord.Option(choices=category_options), receive: discord.Option(choices=receive_options)):
        await ctx.defer()
        raw_res = await get_latest_circular(category)
        title = raw_res['title']
        link = raw_res['link']
        embed = discord.Embed(title=title, url="https://raj.moonball.io/bpsapi/docs", description=f"Here is the latest circular from category `{category.capitalize()}`", color=embed_color)
        embed.set_author(name=embed_title)
        link = link.split(':')
        link = f"{link[0]}:{link[1]}"

        if receive == "all":
            embed.add_field(name="Title", value=title, inline=False)
            embed.add_field(name="Download URL", value=link, inline=False)
        elif receive == "titles":
            embed.add_field(name="Title", value=title, inline=False)
        elif receive == "links":
            embed.add_field(name="Download URL", value=link, inline=False)

        embed.set_footer(text=embed_footer)
        await ctx.followup.send(embed=embed)



    @circular.command(name="search", description="Searches for a particular circular in a particular category.")
    async def search(self, ctx, circular_title: str):
        await ctx.defer()
        raw_res = await search_circular(circular_title.strip())
        embed = discord.Embed(title="Circular Search", url="https://raj.moonball.io/bpsapi/docs", description=f"Here is the result searching for that circular! Keep in mind you need to input the exact name!", color=embed_color)
        embed.set_author(name=embed_title)
        embed.set_footer(text=embed_footer)
        if raw_res:
            embed.add_field(name="Title", value=f"`{circular_title}`", inline=False)
            embed.add_field(name="Download URL", value=str(raw_res), inline=False)
        else:
            embed.add_field(name="Title", value=f"`{circular_title}`", inline=False)
            embed.add_field(name="Download URL", value="No result found", inline=False)
        await ctx.followup.send(embed=embed)



def setup(client):
    client.add_cog(Commands(client))