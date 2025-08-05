import discord
from discord.ext import commands
import asyncio
import json
import os
import re
from datetime import datetime

CONFIG_FILE = "data/dislink_config.json"
HUB_CONFIG_FILE = "data/dislink_hubs.json"


EMBED_COLOR_NEUTRAL = 0x2F3136
EMBED_COLOR_SUCCESS = 0x57F287
EMBED_COLOR_ERROR = 0xED4245
EMBED_COLOR_INFO = 0x3498DB

class HubManager:
    def __init__(self):
        self.hubs = {}
        self.server_links = {}
        self.load_config()
    
    def load_config(self):
        if os.path.exists(HUB_CONFIG_FILE):
            try:
                with open(HUB_CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.hubs = data.get('hubs', {})
                    self.server_links = data.get('server_links', {})
            except Exception as e:
                print(f"Error loading hub config: {e}")
                self.hubs = {}
                self.server_links = {}
    
    def save_config(self):
        data = {
            'hubs': self.hubs,
            'server_links': self.server_links
        }
        with open(HUB_CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    
    def create_hub(self, hub_id, name, description, owner_guild_id, is_public=True, 
                   filter_nsfw=True, filtered_words=None):

        if hub_id in self.hubs:
            return False
        
        self.hubs[hub_id] = {
            'name': name,
            'description': description,
            'owner_guild_id': owner_guild_id,
            'is_public': is_public,
            'created_at': datetime.now().isoformat(),
            'filter_nsfw': filter_nsfw,
            'filtered_words': filtered_words or [],
            'members': []
        }
        self.save_config()
        return True
    
    def delete_hub(self, hub_id):

        if hub_id not in self.hubs:
            return False
        

        for guild_id, link_data in list(self.server_links.items()):
            if link_data.get('hub_id') == hub_id:
                del self.server_links[guild_id]
        

        del self.hubs[hub_id]
        self.save_config()
        return True
    
    def join_hub(self, hub_id, guild_id, channel_id, display_name=None):

        if hub_id not in self.hubs:
            return False, "Hub does not exist"
        

        if str(guild_id) in self.server_links:
            return False, "Server is already linked to a hub"
        

        if str(guild_id) not in self.hubs[hub_id]['members']:
            self.hubs[hub_id]['members'].append(str(guild_id))
        

        self.server_links[str(guild_id)] = {
            'hub_id': hub_id,
            'channel_id': str(channel_id),
            'display_name': display_name or "Server",
            'joined_at': datetime.now().isoformat()
        }
        
        self.save_config()
        return True, "Successfully joined hub"
    
    def leave_hub(self, guild_id):

        guild_id_str = str(guild_id)
        if guild_id_str not in self.server_links:
            return False
        

        hub_id = self.server_links[guild_id_str]['hub_id']
        if hub_id in self.hubs and guild_id_str in self.hubs[hub_id]['members']:
            self.hubs[hub_id]['members'].remove(guild_id_str)
        

        del self.server_links[guild_id_str]
        self.save_config()
        return True
    
    def update_server_settings(self, guild_id, display_name=None, channel_id=None):

        guild_id_str = str(guild_id)
        if guild_id_str not in self.server_links:
            return False
        
        if display_name:
            self.server_links[guild_id_str]['display_name'] = display_name
        
        if channel_id:
            self.server_links[guild_id_str]['channel_id'] = str(channel_id)
        
        self.save_config()
        return True
    
    def update_hub_settings(self, hub_id, name=None, description=None, is_public=None, 
                           filter_nsfw=None, filtered_words=None):

        if hub_id not in self.hubs:
            return False
        
        if name:
            self.hubs[hub_id]['name'] = name
        
        if description:
            self.hubs[hub_id]['description'] = description
        
        if is_public is not None:
            self.hubs[hub_id]['is_public'] = is_public
        
        if filter_nsfw is not None:
            self.hubs[hub_id]['filter_nsfw'] = filter_nsfw
        
        if filtered_words is not None:
            self.hubs[hub_id]['filtered_words'] = filtered_words
        
        self.save_config()
        return True
    
    def get_hub_by_guild(self, guild_id):

        guild_id_str = str(guild_id)
        if guild_id_str not in self.server_links:
            return None
        
        hub_id = self.server_links[guild_id_str]['hub_id']
        if hub_id not in self.hubs:
            return None
        
        return hub_id, self.hubs[hub_id]
    
    def get_hub_members(self, hub_id):

        if hub_id not in self.hubs:
            return []
        
        members = []
        for guild_id in self.hubs[hub_id]['members']:
            if guild_id in self.server_links:
                members.append({
                    'guild_id': guild_id,
                    'channel_id': self.server_links[guild_id]['channel_id'],
                    'display_name': self.server_links[guild_id]['display_name']
                })
        
        return members
    
    def list_public_hubs(self):

        return {hub_id: hub for hub_id, hub in self.hubs.items() if hub['is_public']}
    
    def filter_message(self, message, hub_id):

        if hub_id not in self.hubs:
            return True, "Hub not found"
        
        hub = self.hubs[hub_id]
        

        if hub['filtered_words']:
            for word in hub['filtered_words']:
                if re.search(r'\b' + re.escape(word) + r'\b', message.content, re.IGNORECASE):
                    return True, f"Message contains filtered word: {word}"
        

        if hub['filter_nsfw'] and message.channel.is_nsfw():
            return True, "Messages from NSFW channels are filtered"
        
        return False, None


class DisLink(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hub_manager = HubManager()
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        
        guild_id = str(message.guild.id)
        

        if guild_id not in self.hub_manager.server_links:
            return
        

        if str(message.channel.id) != self.hub_manager.server_links[guild_id]['channel_id']:
            return
        

        hub_id = self.hub_manager.server_links[guild_id]['hub_id']
        

        should_filter, filter_reason = self.hub_manager.filter_message(message, hub_id)
        if should_filter:
            return
        

        server_name = self.hub_manager.server_links[guild_id]['display_name']
        

        hub_members = self.hub_manager.get_hub_members(hub_id)
        
        for member in hub_members:

            if member['guild_id'] == guild_id:
                continue
            
            try:
                target_guild = self.bot.get_guild(int(member['guild_id']))
                if not target_guild:
                    continue
                
                target_channel = target_guild.get_channel(int(member['channel_id']))
                if not target_channel:
                    continue
                

                embed = discord.Embed(
                    description=message.content,
                    color=EMBED_COLOR_NEUTRAL,
                    timestamp=message.created_at
                )
                
                embed.set_author(
                    name=f"{message.author.display_name} [{server_name}]",
                    icon_url=message.author.display_avatar.url
                )
                
                hub_name = self.hub_manager.hubs[hub_id]['name']
                embed.set_footer(text=f"DisLink | {hub_name} | ZygnalBot by TheHolyOneZ")
                

                if message.attachments:
                    embed.set_image(url=message.attachments[0].url)
                
                await target_channel.send(embed=embed)
            except Exception as e:
                print(f"Error forwarding message to {member['guild_id']}: {e}")
    
    @commands.group(name="dislink", invoke_without_command=True)
    @commands.has_permissions(manage_channels=True)
    async def dislink(self, ctx):

        embed = discord.Embed(
            title="DisLink - Global Server Hub",
            description="Connect your server to a global chat hub and communicate with other servers.",
            color=EMBED_COLOR_NEUTRAL
        )
        
        embed.add_field(
            name="Available Commands",
            value=(
                "• `!dislink create <name> <description>` - Create a new hub\n"
                "• `!dislink join <hub_id> [display_name]` - Join a hub\n"
                "• `!dislink leave` - Leave current hub\n"
                "• `!dislink list` - List available public hubs\n"
                "• `!dislink info` - Show info about current hub\n"
                "• `!dislink settings` - Manage hub settings\n"
                "• `!dislink filter <add/remove/list> [word]` - Manage word filters"
            ),
            inline=False
        )
        
        embed.set_footer(text="ZygnalBot by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @dislink.command(name="create")
    @commands.has_permissions(administrator=True)
    async def create_hub(self, ctx, name: str, *, description: str = "A global chat hub"):


        hub_id = f"hub_{ctx.guild.id}_{int(datetime.now().timestamp())}"
        
        success = self.hub_manager.create_hub(
            hub_id=hub_id,
            name=name,
            description=description,
            owner_guild_id=str(ctx.guild.id),
            is_public=True
        )
        
        if success:

            join_success, _ = self.hub_manager.join_hub(
                hub_id=hub_id,
                guild_id=ctx.guild.id,
                channel_id=ctx.channel.id,
                display_name=ctx.guild.name
            )
            
            embed = discord.Embed(
                title="DisLink - Hub Created",
                description=f"✅ Successfully created hub **{name}**!",
                color=EMBED_COLOR_SUCCESS
            )
            
            embed.add_field(name="Hub ID", value=f"`{hub_id}`", inline=False)
            embed.add_field(name="Description", value=description, inline=False)
            embed.add_field(
                name="Channel Linked", 
                value=f"This hub is now linked to {ctx.channel.mention}",
                inline=False
            )
            
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Error",
                description="❌ Failed to create hub. Please try again.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
    
    @dislink.command(name="join")
    @commands.has_permissions(manage_channels=True)
    async def join_hub(self, ctx, hub_id: str, *, display_name: str = None):

        if not display_name:
            display_name = ctx.guild.name
        
        success, message = self.hub_manager.join_hub(
            hub_id=hub_id,
            guild_id=ctx.guild.id,
            channel_id=ctx.channel.id,
            display_name=display_name
        )
        
        if success:
            hub = self.hub_manager.hubs[hub_id]
            embed = discord.Embed(
                title="DisLink - Hub Joined",
                description=f"✅ Successfully joined hub **{hub['name']}**!",
                color=EMBED_COLOR_SUCCESS
            )
            
            embed.add_field(name="Hub Description", value=hub['description'], inline=False)
            embed.add_field(
                name="Channel Linked", 
                value=f"This hub is now linked to {ctx.channel.mention}",
                inline=False
            )
            embed.add_field(
                name="Server Display Name", 
                value=f"Your server will appear as **[{display_name}]**",
                inline=False
            )
            
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Error",
                description=f"❌ {message}",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)

    
    @dislink.command(name="leave")
    @commands.has_permissions(manage_channels=True)
    async def leave_hub(self, ctx):

        hub_info = self.hub_manager.get_hub_by_guild(ctx.guild.id)
        
        if not hub_info:
            embed = discord.Embed(
                title="Error",
                description="❌ Your server is not connected to any hub.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        hub_id, hub = hub_info
        success = self.hub_manager.leave_hub(ctx.guild.id)
        
        if success:
            embed = discord.Embed(
                title="DisLink - Hub Left",
                description=f"✅ Successfully left hub **{hub['name']}**.",
                color=EMBED_COLOR_SUCCESS
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Error",
                description="❌ Failed to leave hub. Please try again.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
    
    @dislink.command(name="list")
    async def list_hubs(self, ctx):

        public_hubs = self.hub_manager.list_public_hubs()
        
        if not public_hubs:
            embed = discord.Embed(
                title="DisLink - Available Hubs",
                description="There are no public hubs available at the moment.",
                color=EMBED_COLOR_NEUTRAL
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="DisLink - Available Hubs",
            description="Here are the public hubs you can join:",
            color=EMBED_COLOR_NEUTRAL
        )
        
        for hub_id, hub in public_hubs.items():
            member_count = len(hub['members'])
            embed.add_field(
                name=f"{hub['name']} ({member_count} servers)",
                value=f"**ID:** `{hub_id}`\n**Description:** {hub['description']}",
                inline=False
            )
        
        embed.set_footer(text="Use !dislink join <hub_id> to join a hub | ZygnalBot by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @dislink.command(name="info")
    async def hub_info(self, ctx):

        hub_info = self.hub_manager.get_hub_by_guild(ctx.guild.id)
        
        if not hub_info:
            embed = discord.Embed(
                title="DisLink - Hub Info",
                description="Your server is not connected to any hub.",
                color=EMBED_COLOR_NEUTRAL
            )
            embed.add_field(
                name="Join a Hub",
                value="Use `!dislink list` to see available hubs or `!dislink create` to create your own.",
                inline=False
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        hub_id, hub = hub_info
        members = self.hub_manager.get_hub_members(hub_id)
        
        embed = discord.Embed(
            title=f"DisLink - {hub['name']}",
            description=hub['description'],
            color=EMBED_COLOR_INFO
        )
        

        embed.add_field(name="Hub ID", value=f"`{hub_id}`", inline=True)
        embed.add_field(name="Visibility", value="Public" if hub['is_public'] else "Private", inline=True)
        embed.add_field(name="NSFW Filter", value="Enabled" if hub['filter_nsfw'] else "Disabled", inline=True)
        

        member_list = "\n".join([f"• {member['display_name']}" for member in members])
        embed.add_field(
            name=f"Connected Servers ({len(members)})",
            value=member_list or "No servers connected",
            inline=False
        )
        

        if hub['filtered_words'] and (str(ctx.guild.id) == hub['owner_guild_id'] or ctx.author.guild_permissions.administrator):
            filtered_words = ", ".join(hub['filtered_words']) if hub['filtered_words'] else "None"
            embed.add_field(name="Filtered Words", value=filtered_words, inline=False)
        
        embed.set_footer(text="ZygnalBot by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @dislink.group(name="settings", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def hub_settings(self, ctx):

        hub_info = self.hub_manager.get_hub_by_guild(ctx.guild.id)
        
        if not hub_info:
            embed = discord.Embed(
                title="Error",
                description="❌ Your server is not connected to any hub.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        hub_id, hub = hub_info
        

        if str(ctx.guild.id) != hub['owner_guild_id']:
            embed = discord.Embed(
                title="Error",
                description="❌ Only the hub owner can change hub settings.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="DisLink - Hub Settings",
            description=f"Settings for hub **{hub['name']}**",
            color=EMBED_COLOR_NEUTRAL
        )
        
        embed.add_field(
            name="Available Settings",
            value=(
                "• `!dislink settings name <new_name>` - Change hub name\n"
                "• `!dislink settings description <new_description>` - Change hub description\n"
                "• `!dislink settings visibility <public/private>` - Change hub visibility\n"
                "• `!dislink settings nsfw <enable/disable>` - Toggle NSFW filter\n"
                "• `!dislink settings displayname <new_name>` - Change your server's display name"
            ),
            inline=False
        )
        
        embed.set_footer(text="ZygnalBot by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @hub_settings.command(name="name")
    @commands.has_permissions(administrator=True)
    async def settings_name(self, ctx, *, new_name: str):

        hub_info = self.hub_manager.get_hub_by_guild(ctx.guild.id)
        
        if not hub_info or str(ctx.guild.id) != hub_info[1]['owner_guild_id']:
            embed = discord.Embed(
                title="Error",
                description="❌ You don't have permission to change hub settings.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        hub_id, hub = hub_info
        success = self.hub_manager.update_hub_settings(hub_id, name=new_name)
        
        if success:
            embed = discord.Embed(
                title="DisLink - Settings Updated",
                description=f"✅ Hub name changed to **{new_name}**.",
                color=EMBED_COLOR_SUCCESS
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Error",
                description="❌ Failed to update hub settings.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
    
    @hub_settings.command(name="description")
    @commands.has_permissions(administrator=True)
    async def settings_description(self, ctx, *, new_description: str):

        hub_info = self.hub_manager.get_hub_by_guild(ctx.guild.id)
        
        if not hub_info or str(ctx.guild.id) != hub_info[1]['owner_guild_id']:
            embed = discord.Embed(
                title="Error",
                description="❌ You don't have permission to change hub settings.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        hub_id, hub = hub_info
        success = self.hub_manager.update_hub_settings(hub_id, description=new_description)
        
        if success:
            embed = discord.Embed(
                title="DisLink - Settings Updated",
                description=f"✅ Hub description updated.",
                color=EMBED_COLOR_SUCCESS
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Error",
                description="❌ Failed to update hub settings.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
    
    @hub_settings.command(name="visibility")
    @commands.has_permissions(administrator=True)
    async def settings_visibility(self, ctx, visibility: str):

        if visibility.lower() not in ['public', 'private']:
            await ctx.send("❌ Visibility must be either 'public' or 'private'.")
            return
        
        is_public = visibility.lower() == 'public'
        hub_info = self.hub_manager.get_hub_by_guild(ctx.guild.id)
        
        if not hub_info or str(ctx.guild.id) != hub_info[1]['owner_guild_id']:
            embed = discord.Embed(
                title="Error",
                description="❌ You don't have permission to change hub settings.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        hub_id, hub = hub_info
        success = self.hub_manager.update_hub_settings(hub_id, is_public=is_public)
        
        if success:
            embed = discord.Embed(
                title="DisLink - Settings Updated",
                description=f"✅ Hub visibility set to **{visibility}**.",
                color=EMBED_COLOR_SUCCESS
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Error",
                description="❌ Failed to update hub settings.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
    
    @hub_settings.command(name="nsfw")
    @commands.has_permissions(administrator=True)
    async def settings_nsfw(self, ctx, setting: str):

        if setting.lower() not in ['enable', 'disable']:
            await ctx.send("❌ Setting must be either 'enable' or 'disable'.")
            return
        
        filter_nsfw = setting.lower() == 'enable'
        hub_info = self.hub_manager.get_hub_by_guild(ctx.guild.id)
        
        if not hub_info or str(ctx.guild.id) != hub_info[1]['owner_guild_id']:
            embed = discord.Embed(
                title="Error",
                description="❌ You don't have permission to change hub settings.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        hub_id, hub = hub_info
        success = self.hub_manager.update_hub_settings(hub_id, filter_nsfw=filter_nsfw)
        
        if success:
            embed = discord.Embed(
                title="DisLink - Settings Updated",
                description=f"✅ NSFW filtering **{setting}d**.",
                color=EMBED_COLOR_SUCCESS
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Error",
                description="❌ Failed to update hub settings.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
    
    @hub_settings.command(name="displayname")
    @commands.has_permissions(manage_channels=True)
    async def settings_displayname(self, ctx, *, display_name: str):

        guild_id_str = str(ctx.guild.id)
        if guild_id_str not in self.hub_manager.server_links:
            embed = discord.Embed(
                title="Error",
                description="❌ Your server is not connected to any hub.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        success = self.hub_manager.update_server_settings(ctx.guild.id, display_name=display_name)
        
        if success:
            embed = discord.Embed(
                title="DisLink - Settings Updated",
                description=f"✅ Your server's display name changed to **{display_name}**.",
                color=EMBED_COLOR_SUCCESS
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Error",
                description="❌ Failed to update server settings.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
    
    @dislink.group(name="filter", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def word_filter(self, ctx):

        hub_info = self.hub_manager.get_hub_by_guild(ctx.guild.id)
        
        if not hub_info:
            embed = discord.Embed(
                title="Error",
                description="❌ Your server is not connected to any hub.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        hub_id, hub = hub_info
        

        if str(ctx.guild.id) != hub['owner_guild_id']:
            embed = discord.Embed(
                title="Error",
                description="❌ Only the hub owner can manage word filters.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="DisLink - Word Filter",
            description="Manage filtered words for your hub:",
            color=EMBED_COLOR_NEUTRAL
        )
        
        embed.add_field(
            name="Commands",
            value=(
                "• `!dislink filter add <word>` - Add a word to filter\n"
                "• `!dislink filter remove <word>` - Remove a filtered word\n"
                "• `!dislink filter list` - List all filtered words"
            ),
            inline=False
        )
        
        embed.set_footer(text="ZygnalBot by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @word_filter.command(name="add")
    @commands.has_permissions(administrator=True)
    async def filter_add(self, ctx, *, word: str):

        hub_info = self.hub_manager.get_hub_by_guild(ctx.guild.id)
        
        if not hub_info or str(ctx.guild.id) != hub_info[1]['owner_guild_id']:
            embed = discord.Embed(
                title="Error",
                description="❌ You don't have permission to manage word filters.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        hub_id, hub = hub_info
        

        filtered_words = hub['filtered_words'] if 'filtered_words' in hub else []
        

        if word.lower() in [w.lower() for w in filtered_words]:
            embed = discord.Embed(
                title="DisLink - Word Filter",
                description=f"⚠️ The word '{word}' is already in the filter list.",
                color=EMBED_COLOR_NEUTRAL
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        filtered_words.append(word.lower())
        success = self.hub_manager.update_hub_settings(hub_id, filtered_words=filtered_words)
        
        if success:
            embed = discord.Embed(
                title="DisLink - Word Filter",
                description=f"✅ Added '{word}' to the filter list.",
                color=EMBED_COLOR_SUCCESS
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Error",
                description="❌ Failed to update filter list.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
    
    @word_filter.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def filter_remove(self, ctx, *, word: str):

        hub_info = self.hub_manager.get_hub_by_guild(ctx.guild.id)
        
        if not hub_info or str(ctx.guild.id) != hub_info[1]['owner_guild_id']:
            embed = discord.Embed(
                title="Error",
                description="❌ You don't have permission to manage word filters.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        hub_id, hub = hub_info
        

        filtered_words = hub['filtered_words'] if 'filtered_words' in hub else []
        

        word_lower = word.lower()
        if word_lower not in [w.lower() for w in filtered_words]:
            embed = discord.Embed(
                title="DisLink - Word Filter",
                description=f"⚠️ The word '{word}' is not in the filter list.",
                color=EMBED_COLOR_NEUTRAL
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        

        filtered_words = [w for w in filtered_words if w.lower() != word_lower]
        success = self.hub_manager.update_hub_settings(hub_id, filtered_words=filtered_words)
        
        if success:
            embed = discord.Embed(
                title="DisLink - Word Filter",
                description=f"✅ Removed '{word}' from the filter list.",
                color=EMBED_COLOR_SUCCESS
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Error",
                description="❌ Failed to update filter list.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
    
    @word_filter.command(name="list")
    @commands.has_permissions(administrator=True)
    async def filter_list(self, ctx):

        hub_info = self.hub_manager.get_hub_by_guild(ctx.guild.id)
        
        if not hub_info:
            embed = discord.Embed(
                title="Error",
                description="❌ Your server is not connected to any hub.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        hub_id, hub = hub_info
        

        if str(ctx.guild.id) != hub['owner_guild_id'] and not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="Error",
                description="❌ Only the hub owner can view the filter list.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        filtered_words = hub.get('filtered_words', [])
        
        embed = discord.Embed(
            title=f"DisLink - Filtered Words for {hub['name']}",
            color=EMBED_COLOR_NEUTRAL
        )
        
        if filtered_words:
            embed.description = "The following words are filtered in this hub:\n\n• " + "\n• ".join(filtered_words)
        else:
            embed.description = "There are no filtered words for this hub."
        
        embed.set_footer(text="ZygnalBot by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @dislink.command(name="delete")
    @commands.has_permissions(administrator=True)
    async def delete_hub(self, ctx):

        hub_info = self.hub_manager.get_hub_by_guild(ctx.guild.id)
        
        if not hub_info:
            embed = discord.Embed(
                title="Error",
                description="❌ Your server is not connected to any hub.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        hub_id, hub = hub_info
        

        if str(ctx.guild.id) != hub['owner_guild_id']:
            embed = discord.Embed(
                title="Error",
                description="❌ Only the hub owner can delete the hub.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        

        embed = discord.Embed(
            title="DisLink - Delete Hub",
            description=f"⚠️ Are you sure you want to delete the hub **{hub['name']}**?\n\nThis will disconnect all servers and cannot be undone.",
            color=EMBED_COLOR_ERROR
        )
        embed.set_footer(text="Reply with 'yes' to confirm or 'no' to cancel | ZygnalBot by TheHolyOneZ")
        await ctx.send(embed=embed)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['yes', 'no']
        
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=30.0)
            
            if msg.content.lower() == 'yes':
                success = self.hub_manager.delete_hub(hub_id)
                
                if success:
                    embed = discord.Embed(
                        title="DisLink - Hub Deleted",
                        description=f"✅ The hub **{hub['name']}** has been deleted.",
                        color=EMBED_COLOR_SUCCESS
                    )
                    embed.set_footer(text="ZygnalBot by TheHolyOneZ")
                    await ctx.send(embed=embed)
                else:
                    embed = discord.Embed(
                        title="Error",
                        description="❌ Failed to delete hub. Please try again.",
                        color=EMBED_COLOR_ERROR
                    )
                    embed.set_footer(text="ZygnalBot by TheHolyOneZ")
                    await ctx.send(embed=embed)
            else:
                await ctx.send("Hub deletion cancelled.")
        except asyncio.TimeoutError:
            await ctx.send("Hub deletion cancelled due to timeout.")


def setup(bot):

    cog = DisLink(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog

