import discord
from discord.ext import commands
import asyncio
import json
import os


CONFIG_FILE = "channel_bindings.json"


EMBED_COLOR_NEUTRAL = 0x2F3136  
EMBED_COLOR_SUCCESS = 0x57F287  
EMBED_COLOR_ERROR = 0xED4245  


class ChannelBindingManager:
    def __init__(self):
        self.bindings = {}
        self.load_bindings()
   
    def load_bindings(self):
       
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.bindings = json.load(f)
            except:
                self.bindings = {}
   
    def save_bindings(self):
       
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.bindings, f, indent=4)
   
    def create_binding(self, source_guild_id, source_channel_id, target_guild_id, target_channel_id, two_way=False):
       
        source_key = f"{source_guild_id}:{source_channel_id}"
        target_key = f"{target_guild_id}:{target_channel_id}"
       
        if source_key not in self.bindings:
            self.bindings[source_key] = []
       
        binding_created = False
        if target_key not in self.bindings[source_key]:
            self.bindings[source_key].append(target_key)
            binding_created = True
       
        if two_way:
            if target_key not in self.bindings:
                self.bindings[target_key] = []
           
            if source_key not in self.bindings[target_key]:
                self.bindings[target_key].append(source_key)
                binding_created = True
       
        if binding_created:
            self.save_bindings()
            return True
        return False
   
    def remove_binding(self, source_guild_id, source_channel_id):
     
        source_key = f"{source_guild_id}:{source_channel_id}"
        binding_removed = False
       
        if source_key in self.bindings:
           
            target_keys = self.bindings[source_key].copy()
            del self.bindings[source_key]
            binding_removed = True
           
            for target_key in target_keys:
                if target_key in self.bindings and source_key in self.bindings[target_key]:
                    self.bindings[target_key].remove(source_key)
                    if not self.bindings[target_key]:  
                        del self.bindings[target_key]
       
        if binding_removed:
            self.save_bindings()
            return True
        return False


class DisShare(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.binding_manager = ChannelBindingManager()
   
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
       
        source_key = f"{message.guild.id}:{message.channel.id}"
        if source_key in self.binding_manager.bindings:
           
            for target_key in self.binding_manager.bindings[source_key]:
                guild_id, channel_id = map(int, target_key.split(':'))
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue
                   
                channel = guild.get_channel(channel_id)
                if not channel:
                    continue
               
                embed = discord.Embed(
                    description=message.content,
                    color=EMBED_COLOR_NEUTRAL,
                    timestamp=message.created_at
                )
                embed.set_author(
                    name=f"{message.author.display_name} (from {message.guild.name})",
                    icon_url=message.author.display_avatar.url
                )
                embed.set_footer(text=f"DisShare | Original message from #{message.channel.name} \n| ZygnalBot by TheHolyOneZ")
               
                if message.attachments:
                    embed.set_image(url=message.attachments[0].url)
               
                await channel.send(embed=embed)
   
    @commands.command(name="disshare")
    @commands.has_permissions(manage_channels=True)
    async def disshare(self, ctx, target_guild_id: int = None, target_channel_id: int = None, two_way: str = None):
        if not target_guild_id or not target_channel_id:
            embed = discord.Embed(
                title="DisShare - Channel Binding",
                description="Bind this channel with a channel in another server to share messages.",
                color=EMBED_COLOR_NEUTRAL
            )
            embed.add_field(
                name="Usage",
                value="!disshare <target_guild_id> <target_channel_id> [true]",
                inline=False
            )
            embed.add_field(
                name="Parameters",
                value="• `target_guild_id`: ID of the target server\n"
                      "• `target_channel_id`: ID of the target channel\n"
                      "• `true`: (Optional) Set to 'true' for two-way binding",
                inline=False
            )
            embed.add_field(
                name="Example",
                value="!disshare 123456789012345678 987654321098765432 true",
                inline=False
            )
            embed.add_field(
                name="Other Commands",
                value="!listbindings - List all bindings for this server\n!removebinding - Remove bindings for a channel",
                inline=False
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
       
        is_two_way = False
        if two_way and two_way.lower() == 'true':
            is_two_way = True
       
        target_guild = self.bot.get_guild(target_guild_id)
        if not target_guild:
            embed = discord.Embed(
                title="Error",
                description=f"❌ Could not find a server with ID {target_guild_id}. Make sure the bot is in that server.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
       
        target_channel = target_guild.get_channel(target_channel_id)
        if not target_channel or not isinstance(target_channel, discord.TextChannel):
            embed = discord.Embed(
                title="Error",
                description=f"❌ Could not find a text channel with ID {target_channel_id} in {target_guild.name}.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
       
        success = self.binding_manager.create_binding(
            ctx.guild.id, ctx.channel.id,
            target_guild_id, target_channel_id,
            is_two_way
        )
       
        if success:
            embed = discord.Embed(
                title="DisShare - Binding Created",
                description=f"✅ Channel binding created successfully!",
                color=EMBED_COLOR_SUCCESS
            )
            embed.add_field(
                name="Source Channel",
                value=f"#{ctx.channel.name} in {ctx.guild.name}",
                inline=True
            )
            embed.add_field(
                name="Target Channel",
                value=f"#{target_channel.name} in {target_guild.name}",
                inline=True
            )
            embed.add_field(
                name="Binding Type",
                value=f"{'Two-way ↔️' if is_two_way else 'One-way →'}",
                inline=False
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="DisShare - Binding Exists",
                description=f"⚠️ This binding already exists!",
                color=EMBED_COLOR_NEUTRAL
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
   
    @commands.command(name="listbindings")
    @commands.has_permissions(manage_channels=True)
    async def list_bindings(self, ctx):
       
        guild_id = ctx.guild.id
        found = False
        embed = discord.Embed(
            title="DisShare - Channel Bindings",
            description="List of all channel bindings for this server:",
            color=EMBED_COLOR_NEUTRAL
        )
       
        for source_key, targets in self.binding_manager.bindings.items():
            source_guild_id, source_channel_id = map(int, source_key.split(':'))
           
            if source_guild_id == guild_id:
                found = True
                source_channel = ctx.guild.get_channel(source_channel_id)
                if not source_channel:
                    continue
               
                target_list = []
                for target_key in targets:
                    target_guild_id, target_channel_id = map(int, target_key.split(':'))
                    target_guild = self.bot.get_guild(target_guild_id)
                    if not target_guild:
                        continue
                   
                    target_channel = target_guild.get_channel(target_channel_id)
                    if not target_channel:
                        continue
                   
                    is_two_way = False
                    reverse_key = target_key
                    if reverse_key in self.binding_manager.bindings:
                        if source_key in self.binding_manager.bindings[reverse_key]:
                            is_two_way = True
                   
                    target_list.append(f"• {target_channel.name} (in {target_guild.name}) {'↔️ Two-way' if is_two_way else '→ One-way'}")
               
                if target_list:
                    embed.add_field(
                        name=f"#{source_channel.name}",
                        value="\n".join(target_list),
                        inline=False
                    )
       
        if not found:
            embed.description = "No channel bindings found for this server."
       
        embed.set_footer(text="ZygnalBot by TheHolyOneZ")
        await ctx.send(embed=embed)
   
    @commands.command(name="removebinding")
    @commands.has_permissions(manage_channels=True)
    async def remove_binding(self, ctx, channel_id: int = None):
        if not channel_id:
            channel_id = ctx.channel.id
       
        channel = ctx.guild.get_channel(channel_id)
        if not channel:
            embed = discord.Embed(
                title="Error",
                description=f"❌ Could not find a channel with ID {channel_id} in this server.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
       
        success = self.binding_manager.remove_binding(ctx.guild.id, channel_id)
       
        if success:
            embed = discord.Embed(
                title="DisShare - Binding Removed",
                description=f"✅ All bindings for #{channel.name} have been removed.",
                color=EMBED_COLOR_SUCCESS
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="DisShare - No Bindings",
                description=f"⚠️ No bindings found for #{channel.name}!",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)


def setup(bot):
   
    cog = DisShare(bot)
   
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
   
    return cog
