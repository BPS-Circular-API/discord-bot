import discord
from discord.ext import commands
from backend import get_circular_list, log, embed_color, embed_footer, embed_title

class Commands(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog : Commands.py loaded.")

    @commands.slash_command(name='list')
    async def list(self, ctx, category: str, receive: str = "all"):
        raw_res = await get_circular_list(category, receive)

        titles, unprocessed_links, links = [], [], []
        loop_int = 1
        for item in raw_res:

            titles.append(f"**{loop_int}**. `{item['title']}`")
            unprocessed_links.append(f"**{loop_int}**. {item['link']}")
            loop_int += 1

        # Remove the redundant download url parameter after ?download=xxxx
        for link in unprocessed_links:
            link = link.split(':')
            link = f"{link[0]}:{link[1]}"
            links.append(link)

        del unprocessed_links

        # Create and send Embed
        embed = discord.Embed(title=f"Circular List | {category.capitalize()}", color=embed_color, description=f"Here are the titles and direct Download URLs of the {category.capitalize()} circulars!")
        embed.set_author(name=embed_title)
        embed.set_footer(text=embed_footer)
        embed.add_field(name="Titles", value="\n".join(titles), inline=False)
        embed.add_field(name="Download URLs", value="\n".join(links), inline=False)

        await ctx.respond(embed=embed)



def setup(client):
    client.add_cog(Commands(client))