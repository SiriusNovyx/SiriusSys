import discord
from discord.ext import commands
import asyncio

class AdvancedServerStatsUI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_names = {}
        self.update_stats_task = None
        self.update_interval = 120  

    async def create_or_get_channel(self, guild, name):
        for channel in guild.voice_channels:
            if channel.name.startswith(name):
                return channel
        return await guild.create_voice_channel(name)

    async def update_stats(self):
        for guild in self.bot.guilds:
            total_members = sum(1 for member in guild.members if not member.bot)
            bot_count = sum(1 for member in guild.members if member.bot)
            online_count = sum(1 for member in guild.members if member.status != discord.Status.offline)
            boost_count = guild.premium_subscription_count

            stats = {
                "Members": total_members,
                "Bots": bot_count,
                "Online": online_count,
                "Boosts": boost_count
            }

            for key, value in stats.items():
                channel = await self.create_or_get_channel(guild, f"{key}: {value}")
                self.channel_names[key] = channel
                new_name = f"{key}: {value}"
                if channel.name != new_name:
                    await channel.edit(name=new_name)

    @commands.command(name="setupstats")
    async def setup_stats(self, ctx):
        
        embed = discord.Embed(
            title="🔧 Server Stats Setup",
            description="Customize your server statistics display!",
            color=discord.Color.purple()
        )
        embed.add_field(name="Modes", value="1️⃣ Voice Channels\n2️⃣ Embed Display\n3️⃣ Modal Setup\n4️⃣ Dashboard", inline=False)
        embed.add_field(name="🔄 Refresh Interval", value="Use `!setinterval <seconds>` to change update frequency.", inline=False)
        embed.set_footer(text="React with the corresponding emoji to choose a mode.")
        message = await ctx.send(embed=embed)
        await message.add_reaction("1️⃣")
        await message.add_reaction("2️⃣")
        await message.add_reaction("3️⃣")
        await message.add_reaction("4️⃣")

        def check(reaction, user):
            return user == ctx.author and reaction.message.id == message.id and str(reaction.emoji) in ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
            if str(reaction.emoji) == "1️⃣":
                if not self.update_stats_task:
                    self.update_stats_task = asyncio.get_event_loop().create_task(self.auto_update())
                await ctx.send("✅ Voice channels setup complete and will update periodically!")
            elif str(reaction.emoji) == "2️⃣":
                stats_embed = discord.Embed(title="📊 Server Statistics", color=discord.Color.green())
                stats_embed.add_field(name="Total Members", value=len(ctx.guild.members), inline=True)
                stats_embed.add_field(name="Bot Count", value=sum(member.bot for member in ctx.guild.members), inline=True)
                stats_embed.add_field(name="Online Members", value=sum(1 for member in ctx.guild.members if member.status != discord.Status.offline), inline=True)
                stats_embed.add_field(name="Boost Count", value=ctx.guild.premium_subscription_count, inline=True)
                stats_embed.set_thumbnail(url=ctx.guild.icon.url)
                await ctx.send(embed=stats_embed)
            elif str(reaction.emoji) == "3️⃣":
                modal_embed = discord.Embed(title="📝 Modal-based setup is coming soon!", color=discord.Color.orange())
                await ctx.send(embed=modal_embed)
            elif str(reaction.emoji) == "4️⃣":
                await ctx.send("🚀 A web-based dashboard for server stats is in development!")
        except asyncio.TimeoutError:
            await ctx.send("❌ Setup timed out. Please run the command again.")

    @commands.command(name="setinterval")
    async def set_update_interval(self, ctx, seconds: int):
        
        if seconds < 30:
            await ctx.send("⚠️ Minimum allowed interval is 30 seconds!")
            return
        self.update_interval = seconds
        await ctx.send(f"✅ Update interval set to {seconds} seconds.")

    async def auto_update(self):
        while True:
            await self.update_stats()
            await asyncio.sleep(self.update_interval)

    def cog_unload(self):
        if self.update_stats_task:
            self.update_stats_task.cancel()


def setup(bot):
    cog = AdvancedServerStatsUI(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    return cog
