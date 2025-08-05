import io
import discord
from discord.ext import commands
from discord import app_commands
import datetime
import asyncio
import json
import os
from typing import Optional, Dict, List, Union, Literal
import traceback
DEBUG_LOGGING = False     # Set to True to enable debug prints
DEBUG_EVENTS = False       # Set to True to print event triggers
DEBUG_CONFIG = False      # Set to True to print config operations
DEBUG_SEND = False     # Set to True to print log sending operations

def debug_print(category, message):
    
    if category == "logging" and DEBUG_LOGGING:
        print(f"[LOGGING DEBUG] {message}")
    elif category == "events" and DEBUG_EVENTS:
        print(f"[EVENTS DEBUG] {message}")
    elif category == "config" and DEBUG_CONFIG:
        print(f"[CONFIG DEBUG] {message}")
    elif category == "send" and DEBUG_SEND:
        print(f"[SEND DEBUG] {message}")

class LoggingConfigView(discord.ui.View):
    def __init__(self, bot, guild_id: int, log_type: str, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.guild_id = guild_id
        self.log_type = log_type
        self.config = self.bot.logging_manager.get_config(guild_id)
        
    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success)
    async def enable_logging(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You need administrator permissions to use this.", ephemeral=True)
            
        await interaction.response.send_message(f"Please select a channel for {self.log_type} logs.", ephemeral=True)
        
        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id and m.content.startswith("<#") and m.content.endswith(">")
            
        try:
            message = await self.bot.wait_for("message", check=check, timeout=60.0)
            channel_id = int(message.content.strip("<#>"))
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                return await interaction.followup.send("Invalid channel. Please try again.", ephemeral=True)
            self.config[self.log_type] = {
                "enabled": True,
                "channel_id": channel_id
            }
            
            self.bot.logging_manager.save_config(self.guild_id, self.config)
            debug_print("config", f"Updated config for guild {self.guild_id}, log type {self.log_type}: {self.config[self.log_type]}")
            
            await interaction.followup.send(f"{self.log_type} logging has been enabled in {channel.mention}!", ephemeral=True)
            
        except asyncio.TimeoutError:
            await interaction.followup.send("You took too long to respond. Please try again.", ephemeral=True)
        except Exception as e:
            debug_print("logging", f"Error in enable_logging: {str(e)}")
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
            
    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger)
    async def disable_logging(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You need administrator permissions to use this.", ephemeral=True)
            
        if self.log_type in self.config and self.config[self.log_type].get("enabled", False):
            self.config[self.log_type]["enabled"] = False
            self.bot.logging_manager.save_config(self.guild_id, self.config)
            debug_print("config", f"Disabled logging for guild {self.guild_id}, log type {self.log_type}")
            await interaction.response.send_message(f"{self.log_type} logging has been disabled.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{self.log_type} logging is already disabled.", ephemeral=True)
            
    @discord.ui.button(label="View Settings", style=discord.ButtonStyle.primary)
    async def view_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You need administrator permissions to use this.", ephemeral=True)
            
        if self.log_type in self.config and self.config[self.log_type].get("enabled", False):
            channel_id = self.config[self.log_type].get("channel_id")
            channel = interaction.guild.get_channel(channel_id)
            
            if channel:
                await interaction.response.send_message(f"{self.log_type} logging is enabled in {channel.mention}.", ephemeral=True)
            else:
                await interaction.response.send_message(f"{self.log_type} logging is enabled but the channel could not be found.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{self.log_type} logging is disabled.", ephemeral=True)

class LoggingManager:
    def __init__(self, bot):
        self.bot = bot
        self.config_dir = "data/logging"
        os.makedirs(self.config_dir, exist_ok=True)
        debug_print("logging", f"LoggingManager initialized with config directory: {self.config_dir}")
        
    def get_config(self, guild_id: int) -> dict:
        config_path = f"{self.config_dir}/{guild_id}.json"
        debug_print("config", f"Loading config from {config_path}")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                    debug_print("config", f"Loaded config for guild {guild_id}: {config}")
                    return config
            except Exception as e:
                debug_print("config", f"Error loading config for guild {guild_id}: {str(e)}")
                return {}
        debug_print("config", f"No config found for guild {guild_id}, returning empty dict")
        return {}
        
    def save_config(self, guild_id: int, config: dict):
        config_path = f"{self.config_dir}/{guild_id}.json"
        debug_print("config", f"Saving config to {config_path}: {config}")
        try:
            with open(config_path, "w") as f:
                json.dump(config, f, indent=4)
            debug_print("config", f"Config saved successfully for guild {guild_id}")
        except Exception as e:
            debug_print("config", f"Error saving config for guild {guild_id}: {str(e)}")
            
    def is_enabled(self, guild_id: int, log_type: str) -> bool:
        config = self.get_config(guild_id)
        enabled = log_type in config and config[log_type].get("enabled", False)
        debug_print("config", f"Checking if {log_type} logging is enabled for guild {guild_id}: {enabled}")
        return enabled
        
    def get_channel(self, guild_id: int, log_type: str) -> Optional[int]:
        config = self.get_config(guild_id)
        if log_type in config and config[log_type].get("enabled", False):
            channel_id = config[log_type].get("channel_id")
            debug_print("config", f"Channel ID for {log_type} logs in guild {guild_id}: {channel_id}")
            return channel_id
        debug_print("config", f"No channel configured for {log_type} logs in guild {guild_id}")
        return None

class AdvancedLogging(commands.Cog):
    
    
    def __init__(self, bot):
        self.bot = bot
        self.bot.logging_manager = LoggingManager(bot)
        self.log_types = {
            "message": "Message Logs",
            "voice": "Voice Channel Logs",
            "member": "Member Join/Leave Logs",
            "webhook": "Webhook Logs",
            "channel": "Channel Logs",
            "role": "Role Logs",
            "server": "Server Logs",
            "moderation": "Moderation Logs"
        }
        debug_print("logging", f"AdvancedLogging cog initialized with log types: {list(self.log_types.keys())}")
        self.bot.loop.create_task(self.check_webhook_audit_logs()) 

    def create_embed(self, title: str, description: str, color: int = 0x3498db, **kwargs) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.datetime.now()
        )
        
        for key, value in kwargs.items():
            if key == "fields":
                for field in value:
                    embed.add_field(name=field["name"], value=field["value"], inline=field.get("inline", True))
            elif key == "author":
                embed.set_author(name=value.get("name", ""), icon_url=value.get("icon_url", ""))
            elif key == "footer":
                embed.set_footer(text=f"{value} | Created by TheHolyOneZ")
            elif key == "thumbnail":
                embed.set_thumbnail(url=value)
            elif key == "image":
                embed.set_image(url=value)
                
        if "footer" not in kwargs:
            embed.set_footer(text="Advanced Logging System | Created by TheHolyOneZ")
            
        return embed
        
    async def send_log(self, guild_id: int, log_type: str, embed: discord.Embed) -> bool:
        debug_print("send", f"Attempting to send {log_type} log for guild {guild_id}")
        
        channel_id = self.bot.logging_manager.get_channel(guild_id, log_type)
        debug_print("send", f"Retrieved channel ID for {log_type} logs: {channel_id}")
        
        if not channel_id:
            debug_print("send", f"No channel configured for {log_type} logs in guild {guild_id}")
            return False
            
        channel = self.bot.get_channel(channel_id)
        debug_print("send", f"Retrieved channel object: {channel}")
        
        if not channel:
            debug_print("send", f"Could not find channel with ID {channel_id}")
            return False
            
        try:
            await channel.send(embed=embed)
            debug_print("send", f"Successfully sent {log_type} log to channel {channel.name}")
            return True
        except Exception as e:
            debug_print("send", f"Error sending log: {e}")
            traceback.print_exc()
            return False
            
    @commands.hybrid_group(name="logs", description="Configure the advanced logging system")
    @commands.has_permissions(administrator=True)
    async def logs(self, ctx):
        if ctx.invoked_subcommand is None:
            embed = self.create_embed(
                "Advanced Logging System",
                "Use the following commands to configure different log types:",
                fields=[
                    {"name": f"`{ctx.prefix}logs setup`", "value": "Interactive setup for all log types", "inline": False},
                    {"name": f"`{ctx.prefix}logs status`", "value": "View current logging configuration", "inline": False}
                ] + [
                    {"name": f"`{ctx.prefix}logs {log_type}`", "value": f"Configure {description}", "inline": False}
                    for log_type, description in self.log_types.items()
                ]
            )
            await ctx.send(embed=embed)
            
    @logs.command(name="setup", description="Interactive setup for all log types")
    @app_commands.describe(channel="Optional channel to use for all log types")
    async def logs_setup(self, ctx, channel: Optional[discord.TextChannel] = None):
        debug_print("logging", f"Setup command invoked by {ctx.author} in guild {ctx.guild.id}")
        embed = self.create_embed(
            "Advanced Logging Setup",
            "Select which log types you want to enable:",
            fields=[
                {"name": log_type.title(), "value": description, "inline": True}
                for log_type, description in self.log_types.items()
            ]
        )
        
        class SetupView(discord.ui.View):
            def __init__(self, cog, timeout=180):
                super().__init__(timeout=timeout)
                self.cog = cog
                self.selected_types = []
                options = [
                    discord.SelectOption(label=log_type.title(), description=description, value=log_type)
                    for log_type, description in cog.log_types.items()
                ]
                
                self.select = discord.ui.Select(
                    placeholder="Select log types to enable...",
                    min_values=0,
                    max_values=len(options),
                    options=options
                )
                self.select.callback = self.on_select
                self.add_item(self.select)
                
            async def on_select(self, interaction: discord.Interaction):
                self.selected_types = self.select.values
                debug_print("logging", f"Selected log types: {self.selected_types}")
                await interaction.response.defer()
                
            @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                if not self.selected_types:
                    return await interaction.response.send_message("You haven't selected any log types!", ephemeral=True)
                    
                config = self.cog.bot.logging_manager.get_config(interaction.guild.id)
                
                target_channel = channel
                if not target_channel:
                    await interaction.response.send_message("Please mention a channel to use for logging.", ephemeral=True)
                    
                    def check(m):
                        return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id and m.content.startswith("<#") and m.content.endswith(">")
                        
                    try:
                        message = await self.cog.bot.wait_for("message", check=check, timeout=60.0)
                        channel_id = int(message.content.strip("<#>"))
                        target_channel = interaction.guild.get_channel(channel_id)
                        
                        if not target_channel:
                            return await interaction.followup.send("Invalid channel. Setup cancelled.", ephemeral=True)
                    except asyncio.TimeoutError:
                        return await interaction.followup.send("You took too long to respond. Setup cancelled.", ephemeral=True)
                    except Exception as e:
                        debug_print("logging", f"Error in setup confirmation: {str(e)}")
                        return await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
                else:
                    await interaction.response.defer()
                for log_type in self.selected_types:
                    config[log_type] = {
                        "enabled": True,
                        "channel_id": target_channel.id
                    }
                
                self.cog.bot.logging_manager.save_config(interaction.guild.id, config)
                debug_print("config", f"Updated config for guild {interaction.guild.id} with selected types: {self.selected_types}")
                
                enabled_types = ", ".join([f"`{log_type}`" for log_type in self.selected_types])
                await interaction.followup.send(
                    embed=self.cog.create_embed(
                        "Logging Setup Complete",
                        f"The following log types have been enabled in {target_channel.mention}:\n{enabled_types}"
                    )
                )
                self.stop()
                
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.send_message("Setup cancelled.", ephemeral=True)
                self.stop()
                
        view = SetupView(self)
        await ctx.send(embed=embed, view=view)
        
    @logs.command(name="status", description="View current logging configuration")
    async def logs_status(self, ctx):
        debug_print("logging", f"Status command invoked by {ctx.author} in guild {ctx.guild.id}")
        config = self.bot.logging_manager.get_config(ctx.guild.id)
        
        fields = []
        for log_type, description in self.log_types.items():
            if log_type in config and config[log_type].get("enabled", False):
                channel_id = config[log_type].get("channel_id")
                channel = ctx.guild.get_channel(channel_id)
                
                if channel:
                    fields.append({
                        "name": description,
                        "value": f"✅ Enabled in {channel.mention}",
                        "inline": False
                    })
                else:
                    fields.append({
                        "name": description,
                        "value": "✅ Enabled (Channel not found)",
                        "inline": False
                    })
            else:
                fields.append({
                    "name": description,
                    "value": "❌ Disabled",
                    "inline": False
                })
                
        embed = self.create_embed(
            "Logging Configuration",
            f"Current logging setup for {ctx.guild.name}:",
            fields=fields
        )
        
        await ctx.send(embed=embed)
    @logs.command(name="message", description="Configure Message Logs")
    async def logs_message(self, ctx):
        debug_print("logging", f"Message logs config command invoked by {ctx.author} in guild {ctx.guild.id}")
        embed = self.create_embed(
            f"{self.log_types['message']} Configuration",
            f"Configure {self.log_types['message']} for your server.",
            footer=f"Log Type: message"
        )
        
        view = LoggingConfigView(self.bot, ctx.guild.id, "message")
        await ctx.send(embed=embed, view=view)

    @logs.command(name="voice", description="Configure Voice Channel Logs")
    async def logs_voice(self, ctx):
        debug_print("logging", f"Voice logs config command invoked by {ctx.author} in guild {ctx.guild.id}")
        embed = self.create_embed(
            f"{self.log_types['voice']} Configuration",
            f"Configure {self.log_types['voice']} for your server.",
            footer=f"Log Type: voice"
        )
        
        view = LoggingConfigView(self.bot, ctx.guild.id, "voice")
        await ctx.send(embed=embed, view=view)

    @logs.command(name="member", description="Configure Member Join/Leave Logs")
    async def logs_member(self, ctx):
        debug_print("logging", f"Member logs config command invoked by {ctx.author} in guild {ctx.guild.id}")
        embed = self.create_embed(
            f"{self.log_types['member']} Configuration",
            f"Configure {self.log_types['member']} for your server.",
            footer=f"Log Type: member"
        )
        
        view = LoggingConfigView(self.bot, ctx.guild.id, "member")
        await ctx.send(embed=embed, view=view)

    @logs.command(name="webhook", description="Configure Webhook Logs")
    async def logs_webhook(self, ctx):
        debug_print("logging", f"Webhook logs config command invoked by {ctx.author} in guild {ctx.guild.id}")
        embed = self.create_embed(
            f"{self.log_types['webhook']} Configuration",
            f"Configure {self.log_types['webhook']} for your server.",
            footer=f"Log Type: webhook"
        )
        
        view = LoggingConfigView(self.bot, ctx.guild.id, "webhook")
        await ctx.send(embed=embed, view=view)

    @logs.command(name="channel", description="Configure Channel Logs")
    async def logs_channel(self, ctx):
        debug_print("logging", f"Channel logs config command invoked by {ctx.author} in guild {ctx.guild.id}")
        embed = self.create_embed(
            f"{self.log_types['channel']} Configuration",
            f"Configure {self.log_types['channel']} for your server.",
            footer=f"Log Type: channel"
        )
        
        view = LoggingConfigView(self.bot, ctx.guild.id, "channel")
        await ctx.send(embed=embed, view=view)

    @logs.command(name="role", description="Configure Role Logs")
    async def logs_role(self, ctx):
        debug_print("logging", f"Role logs config command invoked by {ctx.author} in guild {ctx.guild.id}")
        embed = self.create_embed(
            f"{self.log_types['role']} Configuration",
            f"Configure {self.log_types['role']} for your server.",
            footer=f"Log Type: role"
        )
        
        view = LoggingConfigView(self.bot, ctx.guild.id, "role")
        await ctx.send(embed=embed, view=view)

    @logs.command(name="server", description="Configure Server Logs")
    async def logs_server(self, ctx):
        debug_print("logging", f"Server logs config command invoked by {ctx.author} in guild {ctx.guild.id}")
        embed = self.create_embed(
            f"{self.log_types['server']} Configuration",
            f"Configure {self.log_types['server']} for your server.",
            footer=f"Log Type: server"
        )
        
        view = LoggingConfigView(self.bot, ctx.guild.id, "server")
        await ctx.send(embed=embed, view=view)

    @logs.command(name="moderation", description="Configure Moderation Logs")
    async def logs_moderation(self, ctx):
        debug_print("logging", f"Moderation logs config command invoked by {ctx.author} in guild {ctx.guild.id}")
        embed = self.create_embed(
            f"{self.log_types['moderation']} Configuration",
            f"Configure {self.log_types['moderation']} for your server.",
            footer=f"Log Type: moderation"
        )
        
        view = LoggingConfigView(self.bot, ctx.guild.id, "moderation")
        await ctx.send(embed=embed, view=view)
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        debug_print("events", f"Message delete event triggered for message ID {message.id}")
        if message.author.bot or not message.guild:
            debug_print("events", "Skipping: Bot message or not in guild")
            return
            
        if not self.bot.logging_manager.is_enabled(message.guild.id, "message"):
            debug_print("events", f"Message logging not enabled for guild {message.guild.id}")
            return
            
        content = message.content
        if len(content) > 1024:
            content = content[:1021] + "..."
            
        embed = self.create_embed(
            "Message Deleted",
            f"A message was deleted in {message.channel.mention}",
            color=0xe74c3c,
            fields=[
                {"name": "Content", "value": content or "(No content)", "inline": False},
                {"name": "Author", "value": f"{message.author.mention} ({message.author.id})", "inline": True},
                {"name": "Channel", "value": message.channel.mention, "inline": True},
                {"name": "Created At", "value": f"<t:{int(message.created_at.timestamp())}:F>", "inline": True}
            ],
            footer="Message Logs"
        )
        if message.attachments:
            attachment_list = "\n".join([f"[{a.filename}]({a.url})" for a in message.attachments])
            embed.add_field(name="Attachments", value=attachment_list, inline=False)
            
        await self.send_log(message.guild.id, "message", embed)
        
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        debug_print("events", f"Message edit event triggered for message ID {before.id}")
        if before.author.bot or not before.guild:
            debug_print("events", "Skipping: Bot message or not in guild")
            return
            
        if not self.bot.logging_manager.is_enabled(before.guild.id, "message"):
            debug_print("events", f"Message logging not enabled for guild {before.guild.id}")
            return
        if before.content == after.content:
            debug_print("events", "Skipping: Content didn't change")
            return
            
        before_content = before.content
        if len(before_content) > 1024:
            before_content = before_content[:1021] + "..."
            
        after_content = after.content
        if len(after_content) > 1024:
            after_content = after_content[:1021] + "..."
            
        embed = self.create_embed(
            "Message Edited",
            f"A message was edited in {before.channel.mention} [Jump to Message]({after.jump_url})",
            color=0xf1c40f,
            fields=[
                {"name": "Before", "value": before_content or "(No content)", "inline": False},
                {"name": "After", "value": after_content or "(No content)", "inline": False},
                {"name": "Author", "value": f"{before.author.mention} ({before.author.id})", "inline": True},
                {"name": "Channel", "value": before.channel.mention, "inline": True},
                {"name": "Edited At", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
            ],
            footer="Message Logs"
        )
        
        await self.send_log(before.guild.id, "message", embed)
        
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        debug_print("events", f"Voice state update event triggered for member {member.id}")
        if member.bot or not member.guild:
            debug_print("events", "Skipping: Bot member or not in guild")
            return
            
        if not self.bot.logging_manager.is_enabled(member.guild.id, "voice"):
            debug_print("events", f"Voice logging not enabled for guild {member.guild.id}")
            return
        if before.channel is None and after.channel is not None:
            debug_print("events", f"Member {member.id} joined voice channel {after.channel.id}")
            embed = self.create_embed(
                "Voice Channel Joined",
                f"{member.mention} joined a voice channel",
                color=0x2ecc71,
                fields=[
                    {"name": "Member", "value": f"{member.mention} ({member.id})", "inline": True},
                    {"name": "Channel", "value": after.channel.mention, "inline": True},
                    {"name": "Time", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
                ],
                footer="Voice Logs"
            )
            await self.send_log(member.guild.id, "voice", embed)
        elif before.channel is not None and after.channel is None:
            debug_print("events", f"Member {member.id} left voice channel {before.channel.id}")
            embed = self.create_embed(
                "Voice Channel Left",
                f"{member.mention} left a voice channel",
                color=0xe74c3c,
                fields=[
                    {"name": "Member", "value": f"{member.mention} ({member.id})", "inline": True},
                    {"name": "Channel", "value": before.channel.mention, "inline": True},
                    {"name": "Time", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
                ],
                footer="Voice Logs"
            )
            await self.send_log(member.guild.id, "voice", embed)
        elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
            debug_print("events", f"Member {member.id} moved from voice channel {before.channel.id} to {after.channel.id}")
            embed = self.create_embed(
                "Voice Channel Moved",
                f"{member.mention} moved voice channels",
                color=0x3498db,
                fields=[
                    {"name": "Member", "value": f"{member.mention} ({member.id})", "inline": True},
                    {"name": "From", "value": before.channel.mention, "inline": True},
                    {"name": "To", "value": after.channel.mention, "inline": True},
                    {"name": "Time", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
                ],
                footer="Voice Logs"
            )
            await self.send_log(member.guild.id, "voice", embed)
        elif before.mute != after.mute or before.deaf != after.deaf:
            debug_print("events", f"Member {member.id} voice state changed: mute {before.mute}->{after.mute}, deaf {before.deaf}->{after.deaf}")
            changes = []
            if before.mute != after.mute:
                changes.append(f"Server Mute: {before.mute} → {after.mute}")
            if before.deaf != after.deaf:
                changes.append(f"Server Deaf: {before.deaf} → {after.deaf}")
                
            embed = self.create_embed(
                "Voice State Updated",
                f"{member.mention}'s voice state was updated",
                color=0x9b59b6,
                fields=[
                    {"name": "Member", "value": f"{member.mention} ({member.id})", "inline": True},
                    {"name": "Channel", "value": after.channel.mention, "inline": True},
                    {"name": "Changes", "value": "\n".join(changes), "inline": False},
                    {"name": "Time", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
                ],
                footer="Voice Logs"
            )
            await self.send_log(member.guild.id, "voice", embed)
            
    @commands.Cog.listener()
    async def on_member_join(self, member):
        debug_print("events", f"Member join event triggered for member {member.id}")
        if member.bot:
            debug_print("events", "Skipping: Bot member")
            return
            
        if not self.bot.logging_manager.is_enabled(member.guild.id, "member"):
            debug_print("events", f"Member logging not enabled for guild {member.guild.id}")
            return
            
        account_age = datetime.datetime.now(datetime.timezone.utc) - member.created_at
        account_age_str = f"{account_age.days} days"
        
        embed = self.create_embed(
            "Member Joined",
            f"{member.mention} joined the server",
            color=0x2ecc71,
            fields=[
                {"name": "Member", "value": f"{member.mention} ({member.id})", "inline": True},
                {"name": "Account Created", "value": f"<t:{int(member.created_at.timestamp())}:F>", "inline": True},
                {"name": "Account Age", "value": account_age_str, "inline": True}
            ],
            footer="Member Logs",
            thumbnail=member.display_avatar.url
        )
        
        await self.send_log(member.guild.id, "member", embed)
        
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        debug_print("events", f"Member remove event triggered for member {member.id}")
        if member.bot:
            debug_print("events", "Skipping: Bot member")
            return
            
        if not self.bot.logging_manager.is_enabled(member.guild.id, "member"):
            debug_print("events", f"Member logging not enabled for guild {member.guild.id}")
            return
            
        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        roles_str = ", ".join(roles) if roles else "None"
        
        embed = self.create_embed(
            "Member Left",
            f"{member} left the server",
            color=0xe74c3c,
            fields=[
                {"name": "Member", "value": f"{member} ({member.id})", "inline": True},
                {"name": "Joined At", "value": f"<t:{int(member.joined_at.timestamp()) if member.joined_at else 0}:F>", "inline": True},
                {"name": "Roles", "value": roles_str[:1024], "inline": False}
            ],
            footer="Member Logs",
            thumbnail=member.display_avatar.url
        )
        
        await self.send_log(member.guild.id, "member", embed)
        

    async def check_webhook_audit_logs(self):
        
        await self.bot.wait_until_ready()
        last_webhook_entry = {}
        
        while not self.bot.is_closed():
            try:
                for guild in self.bot.guilds:
                    if not self.bot.logging_manager.is_enabled(guild.id, "webhook"):
                        continue
                    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.webhook_create):
                        if guild.id in last_webhook_entry and entry.id <= last_webhook_entry.get(guild.id, 0):
                            continue
                        last_webhook_entry[guild.id] = entry.id
                        webhook = entry.target
                        channel = None
                        channel_mention = "Unknown Channel"
                        channel_id_str = ""
                        
                        try:
                            if hasattr(webhook, 'channel_id'):
                                channel = guild.get_channel(webhook.channel_id)
                                if channel:
                                    channel_mention = channel.mention
                                    channel_id_str = f"({channel.id})"
                        except Exception as e:
                            print(f"Error getting channel for webhook creation: {e}")
                            
                        embed = self.create_embed(
                            "Webhook Created",
                            f"A new webhook was created in {channel_mention}",
                            color=0x2ecc71,
                            fields=[
                                {"name": "Name", "value": webhook.name if hasattr(webhook, 'name') else "Unknown", "inline": True},
                                {"name": "Created By", "value": f"{entry.user.mention} ({entry.user.id})", "inline": True},
                                {"name": "Channel", "value": f"{channel_mention} {channel_id_str}", "inline": True},
                                {"name": "Time", "value": f"<t:{int(entry.created_at.timestamp())}:F>", "inline": True}
                            ],
                            footer="Webhook Logs"
                        )
                        await self.send_log(guild.id, "webhook", embed)
                        break  
                    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.webhook_delete):
                        if guild.id in last_webhook_entry and entry.id <= last_webhook_entry.get(guild.id, 0):
                            continue
                        last_webhook_entry[guild.id] = entry.id
                        webhook_name = "Unknown Webhook"
                        channel_mention = "Unknown Channel"
                        channel_id_str = ""
                        
                        try:
                            if hasattr(entry, 'target') and entry.target:
                                if hasattr(entry.target, 'name'):
                                    webhook_name = entry.target.name
                                if hasattr(entry, 'changes') and entry.changes:
                                    for change in entry.changes:
                                        if change.key == 'channel_id':
                                            channel_id = change.old
                                            channel = guild.get_channel(channel_id)
                                            if channel:
                                                channel_mention = channel.mention
                                                channel_id_str = f"({channel_id})"
                                            break
                        except Exception as e:
                            print(f"Error getting webhook deletion details: {e}")
                            
                        embed = self.create_embed(
                            "Webhook Deleted",
                            f"A webhook was deleted from {channel_mention}",
                            color=0xe74c3c,
                            fields=[
                                {"name": "Name", "value": webhook_name, "inline": True},
                                {"name": "Deleted By", "value": f"{entry.user.mention} ({entry.user.id})", "inline": True},
                                {"name": "Channel", "value": f"{channel_mention} {channel_id_str}", "inline": True},
                                {"name": "Time", "value": f"<t:{int(entry.created_at.timestamp())}:F>", "inline": True}
                            ],
                            footer="Webhook Logs"
                        )
                        await self.send_log(guild.id, "webhook", embed)
                        break  
                        
            except Exception as e:
                print(f"Error in webhook audit log check: {e}")
                traceback.print_exc()
            await asyncio.sleep(10)





    @commands.Cog.listener()
    async def on_message(self, message):
        debug_print("events", f"Message create event triggered for message {message.id}")
        if message.author.bot or not message.guild:
            debug_print("events", "Skipping: Bot message or not in guild")
            return
            
        if not self.bot.logging_manager.is_enabled(message.guild.id, "message"):
            debug_print("events", f"Message logging not enabled for guild {message.guild.id}")
            return
            
        content = message.content
        if len(content) > 1024:
            content = content[:1021] + "..."
            
        embed = self.create_embed(
            "Message Sent",
            f"A message was sent in {message.channel.mention} [Jump to Message]({message.jump_url})",
            color=0x2ecc71,  
            fields=[
                {"name": "Content", "value": content or "(No content)", "inline": False},
                {"name": "Author", "value": f"{message.author.mention} ({message.author.id})", "inline": True},
                {"name": "Channel", "value": message.channel.mention, "inline": True},
                {"name": "Created At", "value": f"<t:{int(message.created_at.timestamp())}:F>", "inline": True}
            ],
            footer="Message Logs"
        )
        if message.attachments:
            attachment_list = "\n".join([f"[{a.filename}]({a.url})" for a in message.attachments])
            embed.add_field(name="Attachments", value=attachment_list, inline=False)
            
        debug_print("send", f"Sending message creation log for message {message.id}")
        await self.send_log(message.guild.id, "message", embed)

            
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        debug_print("events", f"Channel create event triggered for channel {channel.id}")
        if not self.bot.logging_manager.is_enabled(channel.guild.id, "channel"):
            debug_print("events", f"Channel logging not enabled for guild {channel.guild.id}")
            return
            
        channel_type = str(channel.type).replace("_", " ").title()
        
        embed = self.create_embed(
            "Channel Created",
            f"A new channel was created",
            color=0x2ecc71,
            fields=[
                {"name": "Name", "value": channel.name, "inline": True},
                {"name": "ID", "value": str(channel.id), "inline": True},
                {"name": "Type", "value": channel_type, "inline": True},
                {"name": "Category", "value": channel.category.name if channel.category else "None", "inline": True},
                {"name": "Time", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
            ],
            footer="Channel Logs"
        )
        
        await self.send_log(channel.guild.id, "channel", embed)
        
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        debug_print("events", f"Channel delete event triggered for channel {channel.id}")
        if not self.bot.logging_manager.is_enabled(channel.guild.id, "channel"):
            debug_print("events", f"Channel logging not enabled for guild {channel.guild.id}")
            return
            
        channel_type = str(channel.type).replace("_", " ").title()
        
        embed = self.create_embed(
            "Channel Deleted",
            f"A channel was deleted",
            color=0xe74c3c,
            fields=[
                {"name": "Name", "value": channel.name, "inline": True},
                {"name": "ID", "value": str(channel.id), "inline": True},
                {"name": "Type", "value": channel_type, "inline": True},
                {"name": "Category", "value": channel.category.name if channel.category else "None", "inline": True},
                {"name": "Time", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
            ],
            footer="Channel Logs"
        )
        
        await self.send_log(channel.guild.id, "channel", embed)
        
    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        debug_print("events", f"Channel update event triggered for channel {before.id}")
        if not self.bot.logging_manager.is_enabled(before.guild.id, "channel"):
            debug_print("events", f"Channel logging not enabled for guild {before.guild.id}")
            return
            
        changes = []
        
        if before.name != after.name:
            changes.append(f"Name: {before.name} → {after.name}")
            
        if before.category != after.category:
            before_category = before.category.name if before.category else "None"
            after_category = after.category.name if after.category else "None"
            changes.append(f"Category: {before_category} → {after_category}")
            
        if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
            if before.topic != after.topic:
                before_topic = before.topic or "None"
                after_topic = after.topic or "None"
                changes.append(f"Topic: {before_topic[:100]}... → {after_topic[:100]}...")
                
            if before.slowmode_delay != after.slowmode_delay:
                changes.append(f"Slowmode: {before.slowmode_delay}s → {after.slowmode_delay}s")
                
        if not changes:
            debug_print("events", "Skipping: No significant changes")
            return  
            
        embed = self.create_embed(
            "Channel Updated",
            f"{after.mention} was updated",
            color=0xf1c40f,
            fields=[
                {"name": "Channel", "value": f"{after.mention} ({after.id})", "inline": True},
                {"name": "Changes", "value": "\n".join(changes), "inline": False},
                {"name": "Time", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
            ],
            footer="Channel Logs"
        )
        
        await self.send_log(before.guild.id, "channel", embed)
        
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        debug_print("events", f"Role create event triggered for role {role.id}")
        if not self.bot.logging_manager.is_enabled(role.guild.id, "role"):
            debug_print("events", f"Role logging not enabled for guild {role.guild.id}")
            return
            
        embed = self.create_embed(
            "Role Created",
            f"A new role was created",
            color=role.color,
            fields=[
                {"name": "Name", "value": role.name, "inline": True},
                {"name": "ID", "value": str(role.id), "inline": True},
                {"name": "Color", "value": str(role.color), "inline": True},
                {"name": "Hoisted", "value": str(role.hoist), "inline": True},
                {"name": "Mentionable", "value": str(role.mentionable), "inline": True},
                {"name": "Time", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
            ],
            footer="Role Logs"
        )
        
        await self.send_log(role.guild.id, "role", embed)
        
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        debug_print("events", f"Role delete event triggered for role {role.id}")
        if not self.bot.logging_manager.is_enabled(role.guild.id, "role"):
            debug_print("events", f"Role logging not enabled for guild {role.guild.id}")
            return
            
        embed = self.create_embed(
            "Role Deleted",
            f"A role was deleted",
            color=0xe74c3c,
            fields=[
                {"name": "Name", "value": role.name, "inline": True},
                {"name": "ID", "value": str(role.id), "inline": True},
                {"name": "Color", "value": str(role.color), "inline": True},
                {"name": "Hoisted", "value": str(role.hoist), "inline": True},
                {"name": "Mentionable", "value": str(role.mentionable), "inline": True},
                {"name": "Time", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
            ],
            footer="Role Logs"
        )
        
        await self.send_log(role.guild.id, "role", embed)
        
    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        debug_print("events", f"Role update event triggered for role {before.id}")
        if not self.bot.logging_manager.is_enabled(before.guild.id, "role"):
            debug_print("events", f"Role logging not enabled for guild {before.guild.id}")
            return
            
        changes = []
        
        if before.name != after.name:
            changes.append(f"Name: {before.name} → {after.name}")
            
        if before.color != after.color:
            changes.append(f"Color: {before.color} → {after.color}")
            
        if before.hoist != after.hoist:
            changes.append(f"Hoisted: {before.hoist} → {after.hoist}")
            
        if before.mentionable != after.mentionable:
            changes.append(f"Mentionable: {before.mentionable} → {after.mentionable}")
            
        if before.permissions != after.permissions:
            for perm, value in after.permissions:
                if getattr(before.permissions, perm) != value:
                    changes.append(f"Permission '{perm}': {getattr(before.permissions, perm)} → {value}")
                    
        if not changes:
            debug_print("events", "Skipping: No significant changes")
            return  
            
        embed = self.create_embed(
            "Role Updated",
            f"The role {after.mention} was updated",
            color=after.color,
            fields=[
                {"name": "Role", "value": f"{after.mention} ({after.id})", "inline": True},
                {"name": "Changes", "value": "\n".join(changes[:10]) + (f"\n... and {len(changes) - 10} more" if len(changes) > 10 else ""), "inline": False},
                {"name": "Time", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
            ],
            footer="Role Logs"
        )
        
        await self.send_log(before.guild.id, "role", embed)
        
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        debug_print("events", f"Member update event triggered for member {before.id}")
        if before.bot or not before.guild:
            debug_print("events", "Skipping: Bot member or not in guild")
            return
            
        if not self.bot.logging_manager.is_enabled(before.guild.id, "member"):
            debug_print("events", f"Member logging not enabled for guild {before.guild.id}")
            return
            
        changes = []
        if before.nick != after.nick:
            before_nick = before.nick or "None"
            after_nick = after.nick or "None"
            changes.append(f"Nickname: {before_nick} → {after_nick}")
        if before.roles != after.roles:
            added_roles = [role for role in after.roles if role not in before.roles]
            removed_roles = [role for role in before.roles if role not in after.roles]
            
            if added_roles:
                changes.append(f"Added Roles: {', '.join(role.mention for role in added_roles)}")
                
            if removed_roles:
                changes.append(f"Removed Roles: {', '.join(role.mention for role in removed_roles)}")
                
        if not changes:
            debug_print("events", "Skipping: No significant changes")
            return  
            
        embed = self.create_embed(
            "Member Updated",
            f"{after.mention} was updated",
            color=0x3498db,
            fields=[
                {"name": "Member", "value": f"{after.mention} ({after.id})", "inline": True},
                {"name": "Changes", "value": "\n".join(changes), "inline": False},
                {"name": "Time", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
            ],
            footer="Member Logs",
            thumbnail=after.display_avatar.url
        )
        
        await self.send_log(before.guild.id, "member", embed)
        
    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        debug_print("events", f"Guild update event triggered for guild {before.id}")
        if not self.bot.logging_manager.is_enabled(before.id, "server"):
            debug_print("events", f"Server logging not enabled for guild {before.id}")
            return
            
        changes = []
        
        if before.name != after.name:
            changes.append(f"Name: {before.name} → {after.name}")
            
        if before.description != after.description:
            before_desc = before.description or "None"
            after_desc = after.description or "None"
            changes.append(f"Description: {before_desc} → {after_desc}")
            
        if before.icon != after.icon:
            changes.append("Server icon was changed")
            
        if before.banner != after.banner:
            changes.append("Server banner was changed")
            
        if before.splash != after.splash:
            changes.append("Invite splash was changed")
            
        if before.discovery_splash != after.discovery_splash:
            changes.append("Discovery splash was changed")
            
        if before.owner_id != after.owner_id:
            changes.append(f"Owner: <@{before.owner_id}> → <@{after.owner_id}>")
            
        if before.verification_level != after.verification_level:
            changes.append(f"Verification Level: {before.verification_level} → {after.verification_level}")
            
        if before.explicit_content_filter != after.explicit_content_filter:
            changes.append(f"Content Filter: {before.explicit_content_filter} → {after.explicit_content_filter}")
            
        if before.default_notifications != after.default_notifications:
            changes.append(f"Default Notifications: {before.default_notifications} → {after.default_notifications}")
            
        if before.afk_channel != after.afk_channel:
            before_afk = before.afk_channel.name if before.afk_channel else "None"
            after_afk = after.afk_channel.name if after.afk_channel else "None"
            changes.append(f"AFK Channel: {before_afk} → {after_afk}")
            
        if before.afk_timeout != after.afk_timeout:
            changes.append(f"AFK Timeout: {before.afk_timeout} seconds → {after.afk_timeout} seconds")
            
        if not changes:
            debug_print("events", "Skipping: No significant changes")
            return  
            
        embed = self.create_embed(
            "Server Updated",
            f"{after.name} was updated",
            color=0xf1c40f,
            fields=[
                {"name": "Server", "value": f"{after.name} ({after.id})", "inline": True},
                {"name": "Changes", "value": "\n".join(changes), "inline": False},
                {"name": "Time", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
            ],
            footer="Server Logs",
            thumbnail=after.icon.url if after.icon else None
        )
        
        await self.send_log(before.id, "server", embed)
        
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        debug_print("events", f"Member ban event triggered for user {user.id} in guild {guild.id}")
        if user.bot:
            debug_print("events", "Skipping: Bot user")
            return
            
        if not self.bot.logging_manager.is_enabled(guild.id, "moderation"):
            debug_print("events", f"Moderation logging not enabled for guild {guild.id}")
            return
        try:
            ban_entry = await guild.fetch_ban(user)
            reason = ban_entry.reason or "No reason provided"
        except Exception as e:
            debug_print("events", f"Could not fetch ban reason: {e}")
            reason = "Could not fetch reason"
            
        embed = self.create_embed(
            "Member Banned",
            f"{user} was banned from the server",
            color=0xe74c3c,
            fields=[
                {"name": "User", "value": f"{user} ({user.id})", "inline": True},
                {"name": "Reason", "value": reason, "inline": False},
                {"name": "Time", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
            ],
            footer="Moderation Logs",
            thumbnail=user.display_avatar.url
        )
        
        await self.send_log(guild.id, "moderation", embed)
        
    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        debug_print("events", f"Member unban event triggered for user {user.id} in guild {guild.id}")
        if user.bot:
            debug_print("events", "Skipping: Bot user")
            return
            
        if not self.bot.logging_manager.is_enabled(guild.id, "moderation"):
            debug_print("events", f"Moderation logging not enabled for guild {guild.id}")
            return
            
        embed = self.create_embed(
            "Member Unbanned",
            f"{user} was unbanned from the server",
            color=0x2ecc71,
            fields=[
                {"name": "User", "value": f"{user} ({user.id})", "inline": True},
                {"name": "Time", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
            ],
            footer="Moderation Logs",
            thumbnail=user.display_avatar.url
        )
        
        await self.send_log(guild.id, "moderation", embed)
    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        debug_print("events", f"Bulk message delete event triggered for {len(messages)} messages")
        if not messages:
            debug_print("events", "Skipping: No messages")
            return
            
        guild = messages[0].guild
        if not guild:
            debug_print("events", "Skipping: Not in guild")
            return
            
        if not self.bot.logging_manager.is_enabled(guild.id, "message"):
            debug_print("events", f"Message logging not enabled for guild {guild.id}")
            return
            
        channel = messages[0].channel
        message_count = len(messages)
        
        embed = self.create_embed(
            "Bulk Messages Deleted",
            f"{message_count} messages were deleted in {channel.mention}",
            color=0xe74c3c,
            fields=[
                {"name": "Channel", "value": channel.mention, "inline": True},
                {"name": "Count", "value": str(message_count), "inline": True},
                {"name": "Time", "value": f"<t:{int(datetime.datetime.now().timestamp())}:F>", "inline": True}
            ],
            footer="Message Logs"
        )
        messages = sorted(messages, key=lambda m: m.created_at)
        content = "Deleted Messages Log\n\n"
        
        for message in messages:
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author = f"{message.author} ({message.author.id})"
            msg_content = message.content or "(No content)"
            attachments = ", ".join([a.url for a in message.attachments])
            
            content += f"[{timestamp}] {author}: {msg_content}\n"
            if attachments:
                content += f"Attachments: {attachments}\n"
            content += "\n"
        channel_id = self.bot.logging_manager.get_channel(guild.id, "message")
        if not channel_id:
            debug_print("events", f"No channel configured for message logs in guild {guild.id}")
            return
            
        channel = self.bot.get_channel(channel_id)
        if not channel:
            debug_print("events", f"Could not find channel with ID {channel_id}")
            return
            
        file = discord.File(
            fp=io.BytesIO(content.encode("utf-8")),
            filename="deleted_messages.txt"
        )
        
        try:
            await channel.send(embed=embed, file=file)
            debug_print("send", f"Successfully sent bulk delete log to channel {channel.name}")
        except Exception as e:
            debug_print("send", f"Error sending bulk delete log: {e}")
            try:
                await channel.send(embed=embed)
                debug_print("send", "Sent bulk delete log without file attachment")
            except Exception as e:
                debug_print("send", f"Failed to send bulk delete log even without file: {e}")


class LoggingTester(commands.Cog):
    
    
    def __init__(self, bot):
        self.bot = bot
        self.test_running = False
    
    @commands.command(name="testlogs")
    @commands.has_permissions(administrator=True)
    async def test_logs(self, ctx):
        
        if self.test_running:
            return await ctx.send("A test is already running. Please wait for it to complete.")
        
        self.test_running = True
        
        try:
            config = self.bot.logging_manager.get_config(ctx.guild.id)
            enabled_logs = []
            for log_type in ["message", "voice", "member", "webhook", "channel", "role", "server", "moderation"]:
                if log_type in config and config[log_type].get("enabled", True):
                    channel_id = config[log_type].get("channel_id")
                    channel = ctx.guild.get_channel(channel_id)
                    if channel:
                        enabled_logs.append((log_type, channel))
            
            if not enabled_logs:
                self.test_running = False
                return await ctx.send("No logging channels are set up. Please use `/logs setup` first.")
            status_message = await ctx.send("🔍 Starting logging system test...")
            test_category = await ctx.guild.create_category("Logging-Test", reason="Logging system test")
            await status_message.edit(content=f"{status_message.content}\n✅ Created test category")
            await asyncio.sleep(5)
            if any(log_type == "channel" for log_type, _ in enabled_logs):
                await status_message.edit(content=f"{status_message.content}\n🔄 Testing channel logs...")
                test_channel = await ctx.guild.create_text_channel("logging-test-channel", 
                                                                 category=test_category,
                                                                 reason="Logging system test")
                await asyncio.sleep(5)
                await test_channel.edit(topic="This is a test topic", reason="Logging system test")
                await asyncio.sleep(5)
                await test_channel.delete(reason="Logging system test")
                await asyncio.sleep(5)
                
                await status_message.edit(content=f"{status_message.content}\n✅ Channel logs tested")
            if any(log_type == "role" for log_type, _ in enabled_logs):
                await status_message.edit(content=f"{status_message.content}\n🔄 Testing role logs...")
                test_role = await ctx.guild.create_role(name="Logging-Test-Role", 
                                                      color=discord.Color.blue(),
                                                      reason="Logging system test")
                await asyncio.sleep(5)
                await test_role.edit(name="Logging-Test-Role-Updated", 
                                   color=discord.Color.red(),
                                   reason="Logging system test")
                await asyncio.sleep(5)
                await test_role.delete(reason="Logging system test")
                await asyncio.sleep(5)
                
                await status_message.edit(content=f"{status_message.content}\n✅ Role logs tested")
            if any(log_type == "message" for log_type, _ in enabled_logs):
                await status_message.edit(content=f"{status_message.content}\n🔄 Testing message logs...")
                test_msg_channel = await ctx.guild.create_text_channel("logging-test-messages", 
                                                                     category=test_category,
                                                                     reason="Logging system test")
                await asyncio.sleep(5)
                test_message = await test_msg_channel.send("This is a test message for logging")
                await asyncio.sleep(5)
                await test_message.edit(content="This is an edited test message for logging")
                await asyncio.sleep(5)
                await test_message.delete()
                await asyncio.sleep(5)
                messages = []
                for i in range(5):
                    msg = await test_msg_channel.send(f"Bulk delete test message {i+1}")
                    messages.append(msg)
                    await asyncio.sleep(1)
                
                await test_msg_channel.delete()
                await asyncio.sleep(5)
                
                await status_message.edit(content=f"{status_message.content}\n✅ Message logs tested")
            if any(log_type == "webhook" for log_type, _ in enabled_logs):
                await status_message.edit(content=f"{status_message.content}\n🔄 Testing webhook logs...")
                test_webhook_channel = await ctx.guild.create_text_channel("logging-test-webhooks", 
                                                                         category=test_category,
                                                                         reason="Logging system test")
                await asyncio.sleep(5)
                webhook = await test_webhook_channel.create_webhook(name="Test Webhook")
                await asyncio.sleep(5)
                await webhook.delete()
                await asyncio.sleep(5)
                
                await test_webhook_channel.delete()
                await asyncio.sleep(5)
                
                await status_message.edit(content=f"{status_message.content}\n✅ Webhook logs tested")
            if any(log_type == "server" for log_type, _ in enabled_logs):
                await status_message.edit(content=f"{status_message.content}\n🔄 Testing server logs (limited)...")
                old_name = ctx.guild.name
                if ctx.guild.owner_id == ctx.author.id:  
                    await ctx.guild.edit(name=f"{old_name} - Test")
                    await asyncio.sleep(5)
                    await ctx.guild.edit(name=old_name)
                    await asyncio.sleep(5)
                    await status_message.edit(content=f"{status_message.content}\n✅ Server logs tested")
                else:
                    await status_message.edit(content=f"{status_message.content}\n⚠️ Server logs test skipped (requires server owner)")
            if any(log_type == "moderation" for log_type, _ in enabled_logs):
                await status_message.edit(content=f"{status_message.content}\n🔄 Testing moderation logs...")
                test_ban_role = await ctx.guild.create_role(name="Logging-Test-Ban", reason="Logging system test")
                await asyncio.sleep(5)
                await status_message.edit(content=f"{status_message.content}\n⚠️ Moderation logs test skipped (requires actual user ban/unban)")
                
                await test_ban_role.delete()
                await asyncio.sleep(5)
            await test_category.delete(reason="Logging system test complete")
            await asyncio.sleep(5)
            await status_message.edit(content=f"{status_message.content}\n\n✅ Logging system test completed! Check your logging channels to see the results.")
            
        except Exception as e:
            await ctx.send(f"An error occurred during testing: {str(e)}")
            traceback.print_exc()
        finally:
            self.test_running = False
    
    @commands.command(name="testvoice")
    @commands.has_permissions(administrator=True)
    async def test_voice(self, ctx):
        
        if not self.bot.logging_manager.is_enabled(ctx.guild.id, "voice"):
            return await ctx.send("Voice logging is not enabled. Please enable it first with `/logs voice`.")
        category = await ctx.guild.create_category("Voice-Test", reason="Voice logging test")
        voice_channel = await ctx.guild.create_voice_channel("logging-test-voice", category=category, reason="Voice logging test")
        
        await ctx.send(
            f"Voice channel created: {voice_channel.mention}\n\n"
            f"To test voice logging:\n"
            f"1. Join the voice channel\n"
            f"2. Move to another voice channel\n"
            f"3. Leave the voice channel\n\n"
            f"When done, use `!cleanvoice` to remove the test channels."
        )
    
    @commands.command(name="cleanvoice")
    @commands.has_permissions(administrator=True)
    async def clean_voice(self, ctx):
        
        category = discord.utils.get(ctx.guild.categories, name="Voice-Test")
        if category:
            for channel in category.channels:
                await channel.delete(reason="Voice logging test cleanup")
            await category.delete(reason="Voice logging test cleanup")
            await ctx.send("Voice test channels cleaned up.")
        else:
            await ctx.send("No voice test category found.")

def setup(bot):
    debug_print("logging", "Loading AdvancedLogging cog...")
    cog = AdvancedLogging(bot)
    tester = LoggingTester(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    loop.create_task(bot.add_cog(tester))
    
    debug_print("logging", "AdvancedLogging cog and LoggingTester loaded successfully!")
    return cog

