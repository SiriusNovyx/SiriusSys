import discord
from discord.ext import commands
import aiohttp
import random
import asyncio

class Memes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.meme_sources = [
            "https://meme-api.com/gimme",
            "https://meme-api.com/gimme/dankmemes",
            "https://meme-api.com/gimme/funny",
            "https://meme-api.com/gimme/ProgrammerHumor",
            "https://meme-api.com/gimme/memes"
        ]

    @commands.hybrid_command(name="meme", description="Shows a random meme")
    async def meme(self, ctx: commands.Context):
       
        url = random.choice(self.meme_sources)
        await self.send_meme(ctx, url)

    @commands.hybrid_command(name="meme_list", description="Shows a list of available meme categories")
    async def meme_list(self, ctx: commands.Context):
        
        categories = ", ".join([source.split("/")[-1] for source in self.meme_sources])
        await ctx.send(f"Available meme categories: {categories}")

    @commands.hybrid_command(name="meme_help", description="Shows help on how to use meme commands")
    async def meme_help(self, ctx: commands.Context):
       
        prefix = await self.bot.get_prefix(ctx.message)

        help_embed = discord.Embed(
            title="Meme Command Help",
            description="Here is how you can use the meme commands:",
            color=discord.Color.blurple()
        )
        help_embed.add_field(
            name=f"{prefix}meme",
            value="Shows a random meme from various sources.",
            inline=False
        )
        help_embed.add_field(
            name=f"{prefix}meme_list",
            value="Lists all available meme categories.",
            inline=False
        )
        help_embed.add_field(
            name=f"{prefix}meme_help",
            value="Shows this help message.",
            inline=False
        )
        help_embed.set_footer(text="Made By TheHolyOneZ")

        await ctx.send(embed=help_embed)

    async def send_meme(self, ctx, url):
        async with aiohttp.ClientSession() as session:
            prefix = await self.bot.get_prefix(ctx.message)
            async with session.get(url) as response:
                if response.status != 200:
                    return await ctx.send("😢 Couldn't load a meme.")

                data = await response.json()

                image_url = data.get("url", "")
                if not image_url:
                    return await ctx.send("⚠️ No image found in the response!")

                image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp")
                if not image_url.lower().endswith(image_extensions):
                    return await ctx.send("⚠️ The loaded meme wasn't an image.")

                embed = discord.Embed(color=discord.Color.blurple())
                embed.set_image(url=image_url)
                embed.set_footer(text=f"You can also use {prefix}meme_help.")

                await ctx.send(embed=embed)

def setup(bot):
    cog = Memes(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    return cog
