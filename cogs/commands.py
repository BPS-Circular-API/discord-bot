import discord
from discord.ext import commands
from backend import get_circular_list, log, embed_color, embed_footer, embed_title, categories, receives, get_latest_circular

category_options = []
for i in categories:
    category_options.append(discord.OptionChoice(i.capitalize().strip(), value=i.strip().lower()))
del categories

receive_options = []
for i in receives:
    receive_options.append(discord.OptionChoice(i.capitalize().strip(), value=i.strip().lower()))
del receives




class Commands(commands.Cog):
    def __init__(self, client):
        self.client = client


    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog : Commands.py loaded.")

    @commands.slash_command(name='list')
    async def list(self, ctx, category: discord.Option(choices=category_options), receive: discord.Option(choices=receive_options)):
        await ctx.respond("*Loading, please wait!*", ephemeral=True)
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

            n = 1999

            final_list = ['']
            for out in output:
                if len(final_list[-1] + out) <= n:
                    final_list[-1] += '\n' + out
                else:
                    final_list.append(out)

            for i in final_list:
                await ctx.send(i)
        else:
            await ctx.send(output)


    @commands.slash_command()
    async def latest(self, ctx, category: discord.Option(choices=category_options), receive: discord.Option(choices=receive_options)):
        raw_res = await get_latest_circular(category)
        print(raw_res)
        title = raw_res['title']
        link = raw_res['link']
        embed = discord.Embed(title=title, url="https://raj.moonball.io/bpsapi/docs", description=f"Here is the latest circular from category {category.capitalize()}", color=embed_color)
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
        await ctx.respond(embed=embed)



def setup(client):
    client.add_cog(Commands(client))