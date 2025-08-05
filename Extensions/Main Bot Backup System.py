import discord
from discord.ext import commands
import json
import os
import asyncio
import aiohttp
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BackupBot:
    def __init__(self, token: str, name: str, client: discord.Client = None):
        self.token = token
        self.name = name
        self.client = client
        self.is_connected = False
        self.guilds = []
        self.task = None
        self.user_id = None

class BotUploadModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Upload Bot Tokens", timeout=300)
        self.cog = cog
        
        self.json_input = discord.ui.TextInput(
            label="Bot Tokens JSON",
            placeholder='{"bot1": "token1", "bot2": "token2"}',
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=True
        )
        self.add_item(self.json_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            bot_data = json.loads(self.json_input.value)
            
            if not isinstance(bot_data, dict):
                await interaction.response.send_message("❌ Invalid JSON format. Expected object with bot names and tokens.", ephemeral=True)
                return
            
            added_count = 0
            for bot_name, token in bot_data.items():
                if isinstance(token, str) and len(token) > 50:
                    self.cog.backup_bots[bot_name] = BackupBot(token, bot_name)
                    added_count += 1
            
            self.cog.save_bot_data()
            
            embed = discord.Embed(
                title="✅ Bots Added Successfully",
                description=f"Added {added_count} backup bots to the system.\n\n**Next Step:** Click 'Start All Bots' to activate them!",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except json.JSONDecodeError:
            await interaction.response.send_message("❌ Invalid JSON format. Please check your syntax.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in bot upload modal: {e}")
            await interaction.response.send_message("❌ An error occurred while processing the bot data.", ephemeral=True)

class BackupBotControlView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
    
    @discord.ui.button(label="Upload Bot Tokens", style=discord.ButtonStyle.primary, emoji="📤")
    async def upload_tokens(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BotUploadModal(self.cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Start All Bots", style=discord.ButtonStyle.success, emoji="🚀")
    async def start_all_bots(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.backup_bots:
            await interaction.response.send_message("❌ No backup bots configured. Please upload bot tokens first.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            title="🚀 Starting Backup Bots...",
            description="Please wait while I start all backup bots. This may take a moment.",
            color=discord.Color.yellow()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        started_count = 0
        failed_bots = []
        
        for bot_name, backup_bot in self.cog.backup_bots.items():
            try:
                if not backup_bot.is_connected:
                    success = await self.cog.start_backup_bot(backup_bot)
                    if success:
                        started_count += 1
                    else:
                        failed_bots.append(f"{bot_name} (failed to connect)")
                else:
                    started_count += 1
                    
            except Exception as e:
                failed_bots.append(f"{bot_name}: {str(e)[:40]}")
                logger.error(f"Failed to start {bot_name}: {e}")
        
        result_embed = discord.Embed(
            title="🤖 Bot Startup Results",
            color=discord.Color.green() if started_count > 0 else discord.Color.red()
        )
        
        result_embed.add_field(
            name="✅ Successfully Started",
            value=f"{started_count} bots",
            inline=True
        )
        
        if failed_bots:
            failed_text = "\n".join(failed_bots[:5])
            if len(failed_bots) > 5:
                failed_text += f"\n... and {len(failed_bots) - 5} more"
            
            result_embed.add_field(
                name="❌ Failed to Start",
                value=failed_text,
                inline=False
            )
        
        await interaction.followup.send(embed=result_embed, ephemeral=True)
    
    @discord.ui.button(label="Generate Bot Invites", style=discord.ButtonStyle.secondary, emoji="🔗")
    async def generate_invites(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.backup_bots:
            await interaction.response.send_message("❌ No backup bots configured. Please upload bot tokens first.", ephemeral=True)
            return
        
        connected_bots = [bot for bot in self.cog.backup_bots.values() if bot.is_connected and bot.user_id]
        if not connected_bots:
            await interaction.response.send_message("❌ No bots are currently online with valid user IDs. Please start the bots first.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get current bot prefix
        current_prefix = getattr(self.cog.bot, 'command_prefix', '!')
        if callable(current_prefix):
            try:
                current_prefix = current_prefix(self.cog.bot, interaction.message if hasattr(interaction, 'message') else None)
                if isinstance(current_prefix, list):
                    current_prefix = current_prefix[0]
            except:
                current_prefix = '!'
        
        embed = discord.Embed(
            title="🔗 Bot Invite Links",
            description="⚠️ **IMPORTANT: Read Before Inviting Bots!**",
            color=discord.Color.orange()
        )
        
        # Warning section
        embed.add_field(
            name="🛡️ Anti-Bot Protection Warning",
            value=f"**If your server has anti-bot protection, whitelist each bot BEFORE inviting:**\n"
                  f"```{current_prefix}whitelist_bot <bot_id>```\n"
                  f"**Bot IDs are listed next to each invite link below.**\n"
                  f"**Failure to whitelist may result in automatic kicks!**",
            inline=False
        )
        
        permissions = discord.Permissions(
            read_messages=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            use_external_emojis=True,
            add_reactions=True,
            connect=True,
            speak=True,
            manage_messages=True,
            manage_roles=True,
            kick_members=True,
            ban_members=True,
            administrator=False
        )
        
        invite_links = []
        whitelist_commands = []
        
        for bot_name, backup_bot in self.cog.backup_bots.items():
            if backup_bot.is_connected and backup_bot.user_id:
                invite_url = f"https://discord.com/api/oauth2/authorize?client_id={backup_bot.user_id}&permissions={permissions.value}&scope=bot"
                invite_links.append(f"**{bot_name}** (ID: `{backup_bot.user_id}`)\n[📥 Click to Invite]({invite_url})")
                whitelist_commands.append(f"{current_prefix}whitelist_bot {backup_bot.user_id}")
        
        if invite_links:
            chunks = [invite_links[i:i+8] for i in range(0, len(invite_links), 8)]
            for i, chunk in enumerate(chunks):
                embed.add_field(
                    name=f"🤖 Bot Invites {i+1}" if len(chunks) > 1 else "🤖 Bot Invites",
                    value="\n\n".join(chunk),
                    inline=False
                )
        
        # Quick whitelist commands section
        if whitelist_commands:
            whitelist_text = "\n".join(whitelist_commands[:10])
            if len(whitelist_commands) > 10:
                whitelist_text += f"\n... and {len(whitelist_commands) - 10} more"
            
            embed.add_field(
                name="⚡ Quick Whitelist Commands (Copy & Paste)",
                value=f"```\n{whitelist_text}\n```",
                inline=False
            )
        
        embed.add_field(
            name="📝 Step-by-Step Instructions",
            value="1. **First:** Run whitelist commands above (if needed)\n"
                  "2. **Then:** Click each invite link\n"
                  "3. Select your server from dropdown\n"
                  "4. Review permissions and click 'Authorize'\n"
                  "5. Complete captcha if required",
            inline=False
        )
        
        embed.add_field(
            name="🔍 Bot ID Usage",
            value="• Copy the Bot ID from next to each invite\n"
                  "• Use it in whitelist commands\n"
                  "• Bot IDs are also shown in bot status",
            inline=False
        )
        
        embed.set_footer(text=f"Current bot prefix: {current_prefix} | Whitelist before inviting!")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Bot Status", style=discord.ButtonStyle.secondary, emoji="📊")
    async def status_check(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🤖 Backup Bot Status",
            color=discord.Color.blue()
        )
        
        if not self.cog.backup_bots:
            embed.description = "No backup bots configured."
        else:
            connected = sum(1 for bot in self.cog.backup_bots.values() if bot.is_connected)
            total = len(self.cog.backup_bots)
            
            embed.add_field(
                name="📈 Overview",
                value=f"**Total Bots:** {total}\n**Connected:** {connected}\n**Offline:** {total - connected}",
                inline=False
            )
            
            bot_list = []
            for name, bot in list(self.cog.backup_bots.items())[:10]:
                if bot.is_connected:
                    guild_count = len(bot.client.guilds) if bot.client and bot.client.guilds else 0
                    bot_id = f"ID: `{bot.user_id}`" if bot.user_id else "No ID"
                    bot_list.append(f"🟢 **{name}** - Online ({guild_count} servers)\n    {bot_id}")
                else:
                    bot_list.append(f"🔴 **{name}** - Offline")
            
            if bot_list:
                embed.add_field(
                    name="🤖 Bot Details",
                    value="\n".join(bot_list),
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Stop All Bots", style=discord.ButtonStyle.danger, emoji="🛑")
    async def stop_all_bots(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.backup_bots:
            await interaction.response.send_message("❌ No backup bots configured.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        stopped_count = 0
        
        for backup_bot in self.cog.backup_bots.values():
            if backup_bot.client and backup_bot.is_connected:
                try:
                    await backup_bot.client.close()
                    backup_bot.is_connected = False
                    backup_bot.client = None
                    if backup_bot.task:
                        backup_bot.task.cancel()
                    stopped_count += 1
                except Exception as e:
                    logger.error(f"Error stopping bot {backup_bot.name}: {e}")
        
        embed = discord.Embed(
            title="🛑 Backup Bots Stopped",
            description=f"Successfully stopped {stopped_count} backup bots.",
            color=discord.Color.orange()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Leave This Server", style=discord.ButtonStyle.danger, emoji="🚪")
    async def leave_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.backup_bots:
            await interaction.response.send_message("❌ No backup bots configured.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        left_count = 0
        failed_bots = []
        
        for bot_name, backup_bot in self.cog.backup_bots.items():
            try:
                if backup_bot.client and backup_bot.is_connected:
                    guild = backup_bot.client.get_guild(interaction.guild.id)
                    if guild:
                        await guild.leave()
                        left_count += 1
                        await asyncio.sleep(1)
            except Exception as e:
                failed_bots.append(bot_name)
                logger.error(f"Failed to leave server with {bot_name}: {e}")
        
        embed = discord.Embed(
            title="🚪 Server Leave Results",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="✅ Successfully Left",
            value=f"{left_count} bots",
            inline=True
        )
        
        if failed_bots:
            embed.add_field(
                name="❌ Failed to Leave",
                value="\n".join(failed_bots[:10]),
                inline=True
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Clear All Bots", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def clear_bots(self, interaction: discord.Interaction, button: discord.ui.Button):
        for backup_bot in self.cog.backup_bots.values():
            if backup_bot.client:
                try:
                    await backup_bot.client.close()
                except:
                    pass
            if backup_bot.task:
                backup_bot.task.cancel()
        
        self.cog.backup_bots.clear()
        self.cog.save_bot_data()
        
        embed = discord.Embed(
            title="🗑️ All Bots Cleared",
            description="All backup bots have been disconnected and removed from the system.",
            color=discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class MainBotBackup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backup_bots: Dict[str, BackupBot] = {}
        self.data_file = "data/backup_bots.json"
        self.setup_directories()
        self.load_bot_data()
    
    def setup_directories(self):
        os.makedirs("data", exist_ok=True)
    
    def load_bot_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    for name, token in data.items():
                        self.backup_bots[name] = BackupBot(token, name)
            except Exception as e:
                logger.error(f"Error loading bot data: {e}")
    
    def save_bot_data(self):
        try:
            data = {name: bot.token for name, bot in self.backup_bots.items()}
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving bot data: {e}")
    
    async def start_backup_bot(self, backup_bot: BackupBot):
        try:
            if backup_bot.client and backup_bot.is_connected:
                return True
            
            if backup_bot.client:
                try:
                    await backup_bot.client.close()
                except:
                    pass
            
            intents = discord.Intents.default()
            intents.guilds = True
            intents.guild_messages = True
            backup_bot.client = discord.Client(intents=intents)
            
            @backup_bot.client.event
            async def on_ready():
                backup_bot.is_connected = True
                backup_bot.user_id = backup_bot.client.user.id
                backup_bot.guilds = list(backup_bot.client.guilds)
                logger.info(f"Backup bot {backup_bot.name} connected with {len(backup_bot.guilds)} guilds (ID: {backup_bot.user_id})")
            
            @backup_bot.client.event
            async def on_disconnect():
                backup_bot.is_connected = False
                logger.info(f"Backup bot {backup_bot.name} disconnected")
            
            @backup_bot.client.event
            async def on_guild_join(guild):
                backup_bot.guilds = list(backup_bot.client.guilds)
                logger.info(f"Bot {backup_bot.name} joined guild: {guild.name}")
            
            @backup_bot.client.event
            async def on_guild_remove(guild):
                backup_bot.guilds = list(backup_bot.client.guilds)
                logger.info(f"Bot {backup_bot.name} left guild: {guild.name}")
            
            backup_bot.task = asyncio.create_task(backup_bot.client.start(backup_bot.token))
            
            for i in range(15):
                await asyncio.sleep(1)
                if backup_bot.is_connected and backup_bot.user_id:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error starting backup bot {backup_bot.name}: {e}")
            backup_bot.is_connected = False
            return False
    
    @commands.command(name="extrabots", aliases=["backupbots", "botmanager"])
    @commands.has_permissions(administrator=True)
    async def extra_bots_panel(self, ctx):
        embed = discord.Embed(
            title="🤖 Backup Bot Management System",
            description="Manage your backup bots with ease using the interactive panel below.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📤 Upload Bot Tokens",
            value="Upload JSON with bot tokens",
            inline=True
        )
        
        embed.add_field(
            name="🚀 Start All Bots",
            value="Activate all configured bots",
            inline=True
        )
        
        embed.add_field(
            name="🔗 Generate Bot Invites",
            value="Get OAuth2 invite links with IDs",
            inline=True
        )
        
        embed.add_field(
            name="📊 Bot Status",
            value="View bot connection status",
            inline=True
        )
        
        embed.add_field(
            name="🛑 Stop All Bots",
            value="Disconnect all bots",
            inline=True
        )
        
        embed.add_field(
            name="🚪 Leave This Server",
            value="Make bots leave current server",
            inline=True
        )
        
        if self.backup_bots:
            connected = sum(1 for bot in self.backup_bots.values() if bot.is_connected)
            total = len(self.backup_bots)
            embed.add_field(
                name="📈 Current Status",
                value=f"**Total Bots:** {total}\n**Connected:** {connected}\n**Offline:** {total - connected}",
                inline=False
            )
        else:
            embed.add_field(
                name="📈 Current Status",
                value="No backup bots configured",
                inline=False
            )
        
        # Get current prefix
        current_prefix = getattr(self.bot, 'command_prefix', '!')
        if callable(current_prefix):
            try:
                current_prefix = current_prefix(self.bot, ctx.message)
                if isinstance(current_prefix, list):
                    current_prefix = current_prefix[0]
            except:
                current_prefix = '!'
        
        embed.set_footer(text=f"Current prefix: {current_prefix} | Remember to whitelist bots before inviting!")
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        
        view = BackupBotControlView(self)
        await ctx.send(embed=embed, view=view)
    
    @commands.command(name="startbots", aliases=["connectbots"])
    @commands.has_permissions(administrator=True)
    async def start_all_bots_command(self, ctx):
        if not self.backup_bots:
            await ctx.send("❌ No backup bots configured. Use `!extrabots` to add some.")
            return
        
        embed = discord.Embed(
            title="🔄 Starting Backup Bots...",
            description="Please wait while I connect all backup bots.",
            color=discord.Color.yellow()
        )
        
        message = await ctx.send(embed=embed)
        
        started_count = 0
        failed_bots = []
        
        for bot_name, backup_bot in self.backup_bots.items():
            try:
                if not backup_bot.is_connected:
                    success = await self.start_backup_bot(backup_bot)
                    if success:
                        started_count += 1
                    else:
                        failed_bots.append(f"{bot_name} (failed to connect)")
                else:
                    started_count += 1
                    
            except Exception as e:
                failed_bots.append(f"{bot_name}: {str(e)[:50]}")
                logger.error(f"Failed to start {bot_name}: {e}")
        
        embed = discord.Embed(
            title="🤖 Bot Startup Results",
            color=discord.Color.green() if started_count > 0 else discord.Color.red()
        )
        
        embed.add_field(
            name="✅ Successfully Started",
            value=f"{started_count} bots",
            inline=True
        )
        
        if failed_bots:
            failed_text = "\n".join(failed_bots[:5])
            if len(failed_bots) > 5:
                failed_text += f"\n... and {len(failed_bots) - 5} more"
            
            embed.add_field(
                name="❌ Failed to Start",
                value=failed_text,
                inline=False
            )
        
        await message.edit(embed=embed)
    
    @commands.command(name="botinvites", aliases=["invites"])
    @commands.has_permissions(administrator=True)
    async def generate_bot_invites_command(self, ctx):
        if not self.backup_bots:
            await ctx.send("❌ No backup bots configured.")
            return
        
        connected_bots = [bot for bot in self.backup_bots.values() if bot.is_connected and bot.user_id]
        if not connected_bots:
            await ctx.send("❌ No bots are currently online. Please start the bots first using `!startbots`.")
            return
        
        # Get current prefix
        current_prefix = getattr(self.bot, 'command_prefix', '!')
        if callable(current_prefix):
            try:
                current_prefix = current_prefix(self.bot, ctx.message)
                if isinstance(current_prefix, list):
                    current_prefix = current_prefix[0]
            except:
                current_prefix = '!'
        
        embed = discord.Embed(
            title="🔗 Bot Invite Links",
            description="⚠️ **IMPORTANT: Read Before Inviting Bots!**",
            color=discord.Color.orange()
        )
        
        # Warning section
        embed.add_field(
            name="🛡️ Anti-Bot Protection Warning",
            value=f"**If your server has anti-bot protection, whitelist each bot BEFORE inviting:**\n"
                  f"```{current_prefix}whitelist_bot <bot_id>```\n"
                  f"**Bot IDs are listed next to each invite link below.**\n"
                  f"**Failure to whitelist may result in automatic kicks!**",
            inline=False
        )
        
        permissions = discord.Permissions(
            read_messages=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            use_external_emojis=True,
            add_reactions=True,
            connect=True,
            speak=True,
            manage_messages=True,
            manage_roles=True,
            kick_members=True,
            ban_members=True,
            administrator=False
        )
        
        invite_links = []
        whitelist_commands = []
        
        for bot_name, backup_bot in self.backup_bots.items():
            if backup_bot.is_connected and backup_bot.user_id:
                invite_url = f"https://discord.com/api/oauth2/authorize?client_id={backup_bot.user_id}&permissions={permissions.value}&scope=bot"
                invite_links.append(f"**{bot_name}** (ID: `{backup_bot.user_id}`)\n[📥 Click to Invite]({invite_url})")
                whitelist_commands.append(f"{current_prefix}whitelist_bot {backup_bot.user_id}")
        
        if invite_links:
            chunks = [invite_links[i:i+8] for i in range(0, len(invite_links), 8)]
            for i, chunk in enumerate(chunks):
                embed.add_field(
                    name=f"🤖 Bot Invites {i+1}" if len(chunks) > 1 else "🤖 Bot Invites",
                    value="\n\n".join(chunk),
                    inline=False
                )
        
        # Quick whitelist commands section
        if whitelist_commands:
            whitelist_text = "\n".join(whitelist_commands[:10])
            if len(whitelist_commands) > 10:
                whitelist_text += f"\n... and {len(whitelist_commands) - 10} more"
            
            embed.add_field(
                name="⚡ Quick Whitelist Commands (Copy & Paste)",
                value=f"```\n{whitelist_text}\n```",
                inline=False
            )
        
        embed.add_field(
            name="📝 Step-by-Step Instructions",
            value="1. **First:** Run whitelist commands above (if needed)\n"
                  "2. **Then:** Click each invite link\n"
                  "3. Select your server from dropdown\n"
                  "4. Review permissions and click 'Authorize'\n"
                  "5. Complete captcha if required",
            inline=False
        )
        
        embed.set_footer(text=f"Current bot prefix: {current_prefix} | Whitelist before inviting!")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="stopbots", aliases=["disconnectbots"])
    @commands.has_permissions(administrator=True)
    async def stop_all_bots_command(self, ctx):
        if not self.backup_bots:
            await ctx.send("❌ No backup bots configured.")
            return
        
        stopped_count = 0
        
        for backup_bot in self.backup_bots.values():
            if backup_bot.client and backup_bot.is_connected:
                try:
                    await backup_bot.client.close()
                    backup_bot.is_connected = False
                    backup_bot.client = None
                    backup_bot.user_id = None
                    if backup_bot.task:
                        backup_bot.task.cancel()
                    stopped_count += 1
                except Exception as e:
                    logger.error(f"Error stopping bot {backup_bot.name}: {e}")
        
        embed = discord.Embed(
            title="🛑 Backup Bots Stopped",
            description=f"Successfully stopped {stopped_count} backup bots.",
            color=discord.Color.orange()
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="backupstatus", aliases=["bstatus"])
    @commands.has_permissions(administrator=True)
    async def backup_status_detailed(self, ctx):
        if not self.backup_bots:
            embed = discord.Embed(
                title="🤖 Backup Bot Status",
                description="No backup bots configured.",
                color=discord.Color.red()
            )
            await ctx.sen
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🤖 Detailed Backup Bot Status",
            color=discord.Color.blue()
        )
        
        connected = sum(1 for bot in self.backup_bots.values() if bot.is_connected)
        total = len(self.backup_bots)
        
        embed.add_field(
            name="📊 Overview",
            value=f"**Total Bots:** {total}\n**Connected:** {connected}\n**Offline:** {total - connected}",
            inline=False
        )
        
        online_bots = []
        offline_bots = []
        
        for name, bot in self.backup_bots.items():
            if bot.is_connected and bot.client:
                guild_count = len(bot.client.guilds) if bot.client.guilds else 0
                user_id = f"ID: `{bot.user_id}`" if bot.user_id else "No ID"
                online_bots.append(f"🟢 **{name}** - {guild_count} servers ({user_id})")
            else:
                offline_bots.append(f"🔴 **{name}** - Offline")
        
        if online_bots:
            embed.add_field(
                name="🟢 Online Bots",
                value="\n".join(online_bots[:10]),
                inline=False
            )
        
        if offline_bots:
            embed.add_field(
                name="🔴 Offline Bots",
                value="\n".join(offline_bots[:10]),
                inline=False
            )
        
        # Get current prefix
        current_prefix = getattr(self.bot, 'command_prefix', '!')
        if callable(current_prefix):
            try:
                current_prefix = current_prefix(self.bot, ctx.message)
                if isinstance(current_prefix, list):
                    current_prefix = current_prefix[0]
            except:
                current_prefix = '!'
        
        embed.set_footer(text=f"Use {current_prefix}extrabots for the interactive management panel")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="addbot")
    @commands.has_permissions(administrator=True)
    async def add_single_bot(self, ctx, name: str, token: str):
        if len(token) < 50:
            await ctx.send("❌ Invalid token format. Bot tokens are typically much longer.")
            return
        
        if name in self.backup_bots:
            await ctx.send(f"❌ A bot with the name '{name}' already exists.")
            return
        
        self.backup_bots[name] = BackupBot(token, name)
        self.save_bot_data()
        
        # Get current prefix
        current_prefix = getattr(self.bot, 'command_prefix', '!')
        if callable(current_prefix):
            try:
                current_prefix = current_prefix(self.bot, ctx.message)
                if isinstance(current_prefix, list):
                    current_prefix = current_prefix[0]
            except:
                current_prefix = '!'
        
        embed = discord.Embed(
            title="✅ Bot Added Successfully",
            description=f"Added backup bot: **{name}**",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Next Steps",
            value=f"• Use `{current_prefix}startbots` to connect all bots\n"
                  f"• Use `{current_prefix}botinvites` to get invite links\n"
                  f"• Use `{current_prefix}extrabots` for the management panel",
            inline=False
        )
        
        await ctx.send(embed=embed)
        
        try:
            await ctx.message.delete()
        except:
            pass
    
    @commands.command(name="removebot")
    @commands.has_permissions(administrator=True)
    async def remove_single_bot(self, ctx, name: str):
        if name not in self.backup_bots:
            await ctx.send(f"❌ No bot found with the name '{name}'.")
            return
        
        backup_bot = self.backup_bots[name]
        if backup_bot.client:
            try:
                await backup_bot.client.close()
            except:
                pass
        if backup_bot.task:
            backup_bot.task.cancel()
        
        del self.backup_bots[name]
        self.save_bot_data()
        
        embed = discord.Embed(
            title="🗑️ Bot Removed",
            description=f"Successfully removed backup bot: **{name}**",
            color=discord.Color.orange()
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="listbots")
    @commands.has_permissions(administrator=True)
    async def list_bots(self, ctx):
        if not self.backup_bots:
            await ctx.send("❌ No backup bots configured.")
            return
        
        embed = discord.Embed(
            title="📋 Configured Backup Bots",
            color=discord.Color.blue()
        )
        
        bot_list = []
        for i, (name, bot) in enumerate(self.backup_bots.items(), 1):
            status = "🟢 Online" if bot.is_connected else "🔴 Offline"
            user_id = f" (ID: `{bot.user_id}`)" if bot.user_id else ""
            bot_list.append(f"{i}. **{name}** - {status}{user_id}")
        
        chunk_size = 20
        for i in range(0, len(bot_list), chunk_size):
            chunk = bot_list[i:i + chunk_size]
            embed.add_field(
                name=f"Bots {i+1}-{min(i+chunk_size, len(bot_list))}",
                value="\n".join(chunk),
                inline=False
            )
        
        # Get current prefix
        current_prefix = getattr(self.bot, 'command_prefix', '!')
        if callable(current_prefix):
            try:
                current_prefix = current_prefix(self.bot, ctx.message)
                if isinstance(current_prefix, list):
                    current_prefix = current_prefix[0]
            except:
                current_prefix = '!'
        
        embed.set_footer(text=f"Use {current_prefix}botinvites to get invite links with IDs")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="whitelisthelp", aliases=["wlhelp"])
    @commands.has_permissions(administrator=True)
    async def whitelist_help(self, ctx):
        """Show help for whitelisting backup bots"""
        # Get current prefix
        current_prefix = getattr(self.bot, 'command_prefix', '!')
        if callable(current_prefix):
            try:
                current_prefix = current_prefix(self.bot, ctx.message)
                if isinstance(current_prefix, list):
                    current_prefix = current_prefix[0]
            except:
                current_prefix = '!'
        
        embed = discord.Embed(
            title="🛡️ Bot Whitelisting Guide",
            description="How to whitelist backup bots to prevent auto-kicks",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🔧 Common Whitelist Commands",
            value=f"```\n{current_prefix}whitelist_bot <bot_id>\n"
                  f"{current_prefix}whitelist add <bot_id>\n"
                  f"{current_prefix}antibot whitelist <bot_id>\n"
                  f"{current_prefix}security whitelist <bot_id>\n```",
            inline=False
        )
        
        embed.add_field(
            name="📝 How to Use",
            value="1. Get bot IDs from invite links or status\n"
                  "2. Run whitelist command BEFORE inviting\n"
                  "3. Then invite the bot using OAuth2 link\n"
                  "4. Bot should join without being kicked",
            inline=False
        )
        
        embed.add_field(
            name="🔍 Finding Bot IDs",
            value=f"• Use `{current_prefix}botinvites` - IDs shown next to links\n"
                  f"• Use `{current_prefix}bstatus` - IDs shown in status\n"
                  f"• Use `{current_prefix}listbots` - IDs shown for online bots",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Important Notes",
            value="• Different servers use different whitelist commands\n"
                  "• Some servers don't have anti-bot protection\n"
                  "• If unsure, try the most common: `whitelist_bot`\n"
                  "• Contact server admins if commands don't work",
            inline=False
        )
        
        if self.backup_bots:
            connected_bots = [bot for bot in self.backup_bots.values() if bot.is_connected and bot.user_id]
            if connected_bots:
                whitelist_commands = []
                for bot_name, backup_bot in self.backup_bots.items():
                    if backup_bot.is_connected and backup_bot.user_id:
                        whitelist_commands.append(f"{current_prefix}whitelist_bot {backup_bot.user_id}")
                
                if whitelist_commands:
                    commands_text = "\n".join(whitelist_commands[:8])
                    if len(whitelist_commands) > 8:
                        commands_text += f"\n... and {len(whitelist_commands) - 8} more"
                    
                    embed.add_field(
                        name="⚡ Ready-to-Use Commands",
                        value=f"```\n{commands_text}\n```",
                        inline=False
                    )
        
        embed.set_footer(text="Run these commands before inviting bots to prevent kicks!")
        
        await ctx.send(embed=embed)
    
    async def cog_unload(self):
        for backup_bot in self.backup_bots.values():
            if backup_bot.client:
                try:
                    await backup_bot.client.close()
                except:
                    pass
            if backup_bot.task:
                backup_bot.task.cancel()
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You need Administrator permissions to use backup bot commands.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

def setup(bot):
    cog = MainBotBackup(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog
