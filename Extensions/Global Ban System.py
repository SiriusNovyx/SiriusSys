import discord
from discord.ext import commands, tasks
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging
import io
import re
from jsonschema import validate, ValidationError

logger = logging.getLogger(__name__)


TEMPLATE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "maxLength": 256},
        "description": {"type": "string", "maxLength": 4000},
        "color": {"type": "integer", "minimum": 0, "maximum": 16777215}
    },
    "required": ["title", "description", "color"],
    "additionalProperties": False
}

FULL_TEMPLATE_SCHEMA = {
    "type": "object",
    "properties": {
        "global_ban_dm_template": TEMPLATE_SCHEMA,
        "examples": {
            "type": "object",
            "patternProperties": {
                ".*": TEMPLATE_SCHEMA
            }
        }
    },
    "additionalProperties": True
}

class CustomizeView(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.current_settings = cog.config["settings"]["embed_settings"].copy()
    
    @discord.ui.button(label="📝 Edit Title", style=discord.ButtonStyle.primary, row=0)
    async def edit_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use these buttons!", ephemeral=True)
            return
        
        modal = TitleModal(self.cog, self.current_settings)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.success:
            self.current_settings["title"] = modal.new_title
            await self.update_embed(interaction)
    
    @discord.ui.button(label="📄 Edit Description", style=discord.ButtonStyle.primary, row=0)
    async def edit_description(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use these buttons!", ephemeral=True)
            return
        
        modal = DescriptionModal(self.cog, self.current_settings)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.success:
            self.current_settings["description"] = modal.new_description
            await self.update_embed(interaction)
    
    @discord.ui.button(label="🎨 Edit Color", style=discord.ButtonStyle.primary, row=0)
    async def edit_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use these buttons!", ephemeral=True)
            return
        
        modal = ColorModal(self.cog, self.current_settings)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.success:
            self.current_settings["color"] = modal.new_color
            await self.update_embed(interaction)
    
    @discord.ui.button(label="👁️ Preview", style=discord.ButtonStyle.secondary, row=1)
    async def preview_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use these buttons!", ephemeral=True)
            return
        
        preview_embed = self.create_preview_embed()
        await interaction.response.send_message("📋 **Preview of Global Ban DM:**", embed=preview_embed, ephemeral=True)
    
    @discord.ui.button(label="💾 Save Changes", style=discord.ButtonStyle.success, row=1)
    async def save_changes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use these buttons!", ephemeral=True)
            return
        
        self.cog.config["settings"]["embed_settings"] = self.current_settings.copy()
        self.cog.save_config()
        
        embed = discord.Embed(
            title="✅ Settings Saved",
            description="Global ban DM customization has been saved successfully!",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made by TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()
    
    @discord.ui.button(label="📤 Export JSON", style=discord.ButtonStyle.secondary, row=2)
    async def export_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use these buttons!", ephemeral=True)
            return
        
        json_data = {
            "global_ban_dm_template": {
                "title": self.current_settings["title"],
                "description": self.current_settings["description"],
                "color": self.current_settings["color"],
                "variables": {
                    "user": "User mention (@User)",
                    "username": "User's display name",
                    "user_id": "User's Discord ID",
                    "bot_name": "Bot's name",
                    "server": "Server name they tried to join",
                    "guild": "Same as server",
                    "reason": "Ban reason",
                    "ban_date": "Date originally banned (YYYY-MM-DD)",
                    "expires": "Expiration date or 'Never'",
                    "banned_by": "Who issued the ban (@User)"
                },
                "examples": {
                    "gaming_server": {
                        "title": "🎮 {username}, Access Denied!",
                        "description": "Hey {username}! You tried to join **{server}** but you're globally banned from {bot_name}.\n\n**Reason:** {reason}\n**Banned by:** {banned_by}\n**Date:** {ban_date}",
                        "color": 15158332
                    },
                    "professional": {
                        "title": "🚫 Global Ban Notification",
                        "description": "User {username} (ID: {user_id}),\n\nYou have been denied access to {server} due to a global ban in the {bot_name} network.\n\nViolation: {reason}\nIssued: {ban_date}\nExpires: {expires}",
                        "color": 16711680
                    },
                    "friendly": {
                        "title": "😔 Oops! You can't join {server}",
                        "description": "Hi {username}! Unfortunately, you can't join {server} because you have a global ban.\n\n💔 **Why?** {reason}\n📅 **When?** {ban_date}\n⏰ **Until?** {expires}\n\nIf you think this is a mistake, please contact the server administrators.",
                        "color": 16776960
                    },
                    "minimal": {
                        "title": "🚫 Banned",
                        "description": "You are globally banned from {bot_name}. Reason: {reason}",
                        "color": 16711680
                    },
                    "detailed": {
                        "title": "🚫 Global Ban - Access Denied",
                        "description": "**User:** {username} ({user_id})\n**Server Attempted:** {server}\n**Bot Network:** {bot_name}\n\n**Ban Details:**\n• **Reason:** {reason}\n• **Issued:** {ban_date}\n• **Expires:** {expires}\n• **Banned By:** {banned_by}\n\nThis is an automated message from the global ban system.",
                        "color": 16711680
                    }
                }
            }
        }
        
        json_str = json.dumps(json_data, indent=2)
        file = discord.File(io.StringIO(json_str), filename="global_ban_template.json")
        
        await interaction.response.send_message(
            "📤 **JSON Template Exported!**\n\nThis file contains your current settings plus examples. You can modify it and import it back!",
            file=file,
            ephemeral=True
        )
    
    @discord.ui.button(label="📥 Import JSON", style=discord.ButtonStyle.secondary, row=2)
    async def import_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use these buttons!", ephemeral=True)
            return
        
        modal = JSONImportModal(self.cog, self.current_settings)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.success:
            self.current_settings = modal.new_settings
            await self.update_embed(interaction)
    
    @discord.ui.button(label="🔄 Reset to Default", style=discord.ButtonStyle.danger, row=2)
    async def reset_default(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use these buttons!", ephemeral=True)
            return
        
        self.current_settings = {
            "title": "🚫 Global Ban Notice",
            "description": "You have been globally banned from servers using {bot_name}",
            "color": 0xFF0000
        }
        await self.update_embed(interaction)
    
    def create_main_embed(self):
        embed = discord.Embed(
            title="🎨 Global Ban DM Customizer",
            description="Customize the message sent to globally banned users",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="📝 Current Title",
            value=f"```{self.current_settings['title']}```",
            inline=False
        )
        
        embed.add_field(
            name="📄 Current Description",
            value=f"```{self.current_settings['description'][:1000]}{'...' if len(self.current_settings['description']) > 1000 else ''}```",
            inline=False
        )
        
        embed.add_field(
            name="🎨 Current Color",
            value=f"#{self.current_settings['color']:06x}",
            inline=True
        )
        
        embed.add_field(
            name="📊 Available Variables",
            value="`{user}` `{username}` `{user_id}` `{bot_name}` `{server}` `{guild}` `{reason}` `{ban_date}` `{expires}` `{banned_by}`",
            inline=False
        )
        
        embed.set_footer(text="Made by TheHolyOneZ • Use buttons below to customize")
        return embed
    
    def create_preview_embed(self):
        sample_data = {
            "user": self.ctx.author.mention,
            "username": self.ctx.author.name,
            "user_id": str(self.ctx.author.id),
            "bot_name": self.cog.bot.user.name,
            "server": self.ctx.guild.name if self.ctx.guild else "Sample Server",
            "guild": self.ctx.guild.name if self.ctx.guild else "Sample Server",
            "reason": "Sample ban reason for preview",
            "ban_date": "2024-01-01",
            "expires": "Never",
            "banned_by": self.ctx.author.mention
        }
        
        try:
            formatted_title = self.current_settings["title"].format(**sample_data)
            formatted_description = self.current_settings["description"].format(**sample_data)
        except KeyError as e:
            formatted_title = f"❌ Error: Missing variable {e}"
            formatted_description = "Please fix the variable error above"
        
        preview_embed = discord.Embed(
            title=formatted_title,
            description=formatted_description,
            color=self.current_settings["color"]
        )
        
        preview_embed.add_field(name="Reason", value=sample_data["reason"], inline=False)
        preview_embed.add_field(name="Server Attempted", value=sample_data["server"], inline=True)
        preview_embed.add_field(name="Duration", value="Permanent", inline=True)
        preview_embed.set_footer(text="Made by TheHolyOneZ")
        
        return preview_embed
    
    async def update_embed(self, interaction):
        embed = self.create_main_embed()
        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        
        try:
            embed = discord.Embed(
                title="⏰ Customizer Timed Out",
                description="The customization session has expired. Use the command again to continue editing.",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await self.ctx.edit_original_response(embed=embed, view=self)
        except:
            pass

class TitleModal(discord.ui.Modal):
    def __init__(self, cog, current_settings):
        super().__init__(title="📝 Edit DM Title")
        self.cog = cog
        self.current_settings = current_settings
        self.success = False
        
        self.title_input = discord.ui.TextInput(
            label="Title",
            placeholder="Enter the embed title (max 256 characters)",
            default=current_settings["title"],
            max_length=256,
            style=discord.TextStyle.short
        )
        self.add_item(self.title_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.new_title = self.title_input.value
        self.success = True
        await interaction.response.send_message("✅ Title updated!", ephemeral=True)

class DescriptionModal(discord.ui.Modal):
    def __init__(self, cog, current_settings):
        super().__init__(title="📄 Edit DM Description")
        self.cog = cog
        self.current_settings = current_settings
        self.success = False
        
        self.description_input = discord.ui.TextInput(
            label="Description",
            placeholder="Enter the embed description (max 4000 characters)\nUse variables like {username}, {reason}, etc.",
            default=current_settings["description"],
            max_length=4000,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.description_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.new_description = self.description_input.value
        self.success = True
        await interaction.response.send_message("✅ Description updated!", ephemeral=True)

class ColorModal(discord.ui.Modal):
    def __init__(self, cog, current_settings):
        super().__init__(title="🎨 Edit DM Color")
        self.cog = cog
        self.current_settings = current_settings
        self.success = False
        
        self.color_input = discord.ui.TextInput(
            label="Color (Hex)",
            placeholder="Enter hex color (e.g., #FF0000, FF0000, 0xFF0000)",
            default=f"#{current_settings['color']:06x}",
            max_length=10,
            style=discord.TextStyle.short
        )
        self.add_item(self.color_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        color_str = self.color_input.value.strip()
        
        try:
            if color_str.startswith('#'):
                color_int = int(color_str[1:], 16)
            elif color_str.startswith('0x'):
                color_int = int(color_str, 16)
            else:
                color_int = int(color_str, 16)
            
            if color_int > 0xFFFFFF:
                raise ValueError("Color value too large")
            
            self.new_color = color_int
            self.success = True
            await interaction.response.send_message("✅ Color updated!", ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid color format! Use hex format like #FF0000, FF0000, or 0xFF0000",
                ephemeral=True
            )

class JSONImportModal(discord.ui.Modal):
    def __init__(self, cog, current_settings):
        super().__init__(title="📥 Import JSON Template")
        self.cog = cog
        self.current_settings = current_settings
        self.success = False
        
        self.json_input = discord.ui.TextInput(
            label="JSON Template",
            placeholder='Paste your JSON here or use a template name like "gaming_server", "professional", "friendly"',
            max_length=4000,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.json_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        json_str = self.json_input.value.strip()
        

        templates = {
            "gaming_server": {
                "title": "🎮 {username}, Access Denied!",
                "description": "Hey {username}! You tried to join **{server}** but you're globally banned from {bot_name}.\n\n**Reason:** {reason}\n**Banned by:** {banned_by}\n**Date:** {ban_date}",
                "color": 15158332
            },
            "professional": {
                "title": "🚫 Global Ban Notification",
                "description": "User {username} (ID: {user_id}),\n\nYou have been denied access to {server} due to a global ban in the {bot_name} network.\n\nViolation: {reason}\nIssued: {ban_date}\nExpires: {expires}",
                "color": 16711680
            },
            "friendly": {
                "title": "😔 Oops! You can't join {server}",
                "description": "Hi {username}! Unfortunately, you can't join {server} because you have a global ban.\n\n💔 **Why?** {reason}\n📅 **When?** {ban_date}\n⏰ **Until?** {expires}\n\nIf you think this is a mistake, please contact the server administrators.",
                "color": 16776960
            },
            "minimal": {
                "title": "🚫 Banned",
                "description": "You are globally banned from {bot_name}. Reason: {reason}",
                "color": 16711680
            },
            "detailed": {
                "title": "🚫 Global Ban - Access Denied",
                "description": "**User:** {username} ({user_id})\n**Server Attempted:** {server}\n**Bot Network:** {bot_name}\n\n**Ban Details:**\n• **Reason:** {reason}\n• **Issued:** {ban_date}\n• **Expires:** {expires}\n• **Banned By:** {banned_by}\n\nThis is an automated message from the global ban system.",
                "color": 16711680
            },
            "corporate": {
                "title": "🏢 Network Access Violation",
                "description": "**NOTICE:** Access to {server} has been denied.\n\n**User Account:** {username} (ID: {user_id})\n**Network:** {bot_name}\n**Violation Code:** {reason}\n**Enforcement Date:** {ban_date}\n**Expiration:** {expires}\n\nFor appeals or inquiries, contact network administrators.",
                "color": 3447003
            },
            "casual": {
                "title": "😎 Whoops, can't let you in!",
                "description": "Hey {username}! 👋\n\nLooks like you're on the naughty list for {bot_name} servers. You tried to join {server} but...\n\n🚫 **What happened?** {reason}\n📅 **When?** {ban_date}\n⏰ **Until when?** {expires}\n\nChill out and maybe try again later! ✌️",
                "color": 16776960
            }
        }
        
        if json_str.lower() in templates:
            self.new_settings = templates[json_str.lower()]
            self.success = True
            await interaction.response.send_message(f"✅ Applied template: {json_str}", ephemeral=True)
            return
        

        try:
            data = json.loads(json_str)
            

            if "global_ban_dm_template" in data:
                template_data = data["global_ban_dm_template"]
            elif "title" in data and "description" in data:
                template_data = data
            else:
                raise ValueError("Invalid JSON structure - must contain 'title', 'description', and 'color' fields")
            

            required_fields = ["title", "description", "color"]
            missing_fields = [field for field in required_fields if field not in template_data]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            

            if not isinstance(template_data["title"], str) or len(template_data["title"]) > 256:
                raise ValueError("Title must be a string with max 256 characters")
            
            if not isinstance(template_data["description"], str) or len(template_data["description"]) > 4000:
                raise ValueError("Description must be a string with max 4000 characters")
            

            color = template_data["color"]
            if isinstance(color, str):
                if color.startswith('#'):
                    color = int(color[1:], 16)
                elif color.startswith('0x'):
                    color = int(color, 16)
                else:
                    color = int(color, 16)
            elif not isinstance(color, int):
                raise ValueError("Color must be hex string or integer")
            
            if color < 0 or color > 0xFFFFFF:
                raise ValueError("Color value must be between 0 and 16777215 (0xFFFFFF)")
            
            self.new_settings = {
                "title": str(template_data["title"]),
                "description": str(template_data["description"]),
                "color": color
            }
            self.success = True
            await interaction.response.send_message("✅ JSON template imported successfully!", ephemeral=True)
            
        except json.JSONDecodeError:
            await interaction.response.send_message(
                "❌ Invalid JSON format! Please check your syntax.\n\n**Available templates:** gaming_server, professional, friendly, minimal, detailed, corporate, casual",
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(f"❌ JSON Error: {e}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Unexpected error: {e}", ephemeral=True)

class GlobalBanSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/global_bans.json"
        self.config = self.load_config()
        self.rate_limiter = {}
        self.user_rate_limiter = {}
        self.check_interval = 60
        self.global_ban_check.start()
        
    def load_config(self):
        
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            config = {}
        except json.JSONDecodeError:
            logger.error("Invalid JSON in config file, creating new config")
            config = {}
        

        default_config = {
            "global_bans": {},
            "settings": {
                "check_mode": "on_join",
                "check_interval": 60,
                "embed_settings": {
                    "title": "🚫 Global Ban Notice",
                    "description": "You have been globally banned from servers using {bot_name}",
                    "color": 0xFF0000
                },
                "log_webhook": None,
                "authorized_users": [],
                "rate_limit_settings": {
                    "guild_cooldown": 5,
                    "user_cooldown": 30,
                    "max_bans_per_minute": 10
                },
                "auto_cleanup": {
                    "enabled": True,
                    "cleanup_expired": True,
                    "cleanup_interval": 3600
                }
            }
        }
        

        def deep_merge(default, current):
            
            result = current.copy()
            for key, value in default.items():
                if key not in result:
                    result[key] = value
                elif isinstance(value, dict) and isinstance(result.get(key), dict):
                    result[key] = deep_merge(value, result[key])
            return result
        
        config = deep_merge(default_config, config)
        

        self.save_config_data(config)
        
        return config
    
    def save_config(self):
        
        self.save_config_data(self.config)
    
    def save_config_data(self, config):
        
        import os
        os.makedirs("data", exist_ok=True)
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4, default=str)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def check_rate_limits(self, guild_id: int, user_id: int) -> tuple[bool, str]:
        
        current_time = datetime.utcnow()
        settings = self.config["settings"]["rate_limit_settings"]
        

        if guild_id in self.rate_limiter:
            time_diff = (current_time - self.rate_limiter[guild_id]).total_seconds()
            if time_diff < settings["guild_cooldown"]:
                return False, f"Guild rate limited for {settings['guild_cooldown'] - int(time_diff)} more seconds"
        

        if user_id in self.user_rate_limiter:
            time_diff = (current_time - self.user_rate_limiter[user_id]).total_seconds()
            if time_diff < settings["user_cooldown"]:
                return False, f"User rate limited for {settings['user_cooldown'] - int(time_diff)} more seconds"
        
        return True, "OK"
    
    def update_rate_limits(self, guild_id: int, user_id: int):
        
        current_time = datetime.utcnow()
        self.rate_limiter[guild_id] = current_time
        self.user_rate_limiter[user_id] = current_time
    
    async def is_authorized(self, ctx) -> bool:
        

        if ctx.author.id == self.bot.owner_id:
            return True
        

        if ctx.guild and ctx.author.id == ctx.guild.owner_id:
            return True
        

        if ctx.guild and ctx.author.guild_permissions.administrator:
            return True
        

        if ctx.guild and ctx.author.guild_permissions.manage_guild:
            return True
        

        if ctx.author.id in self.config["settings"]["authorized_users"]:
            return True
        
        return False
    
    def get_prefix(self, ctx):
        
        if hasattr(self.bot, 'command_prefix'):
            if callable(self.bot.command_prefix):
                return self.bot.command_prefix(self.bot, ctx.message)
            return self.bot.command_prefix
        return "!"
    
    @commands.group(name="globalban", aliases=["gb"], invoke_without_command=True)
    async def globalban_group(self, ctx):
        
        prefix = self.get_prefix(ctx)
        
        embed = discord.Embed(
            title="🌐 Global Ban System",
            description="Cross-server ban management system",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="📋 Management Commands",
            value=(
                f"`{prefix}gb add <user_id> <reason> [duration]` - Add global ban\n"
                f"`{prefix}gb remove <user_id>` - Remove global ban\n"
                f"`{prefix}gb list` - View all global bans\n"
                f"`{prefix}gb check <user_id>` - Check ban status"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Configuration Commands",
            value=(
                f"`{prefix}gb settings` - View system settings\n"
                f"`{prefix}gb customize` - Interactive DM customizer\n"
                f"`{prefix}gb stats` - View statistics\n"
                f"`{prefix}gb authorize <user_id>` - Authorize user"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎨 Customization Features",
            value=(
                "• Interactive button-based customizer\n"
                "• JSON template import/export\n"
                "• Pre-made templates\n"
                "• Variable support\n"
                "• Live preview"
            ),
            inline=False
        )
        

        is_auth = await self.is_authorized(ctx)
        auth_status = "✅ Authorized" if is_auth else "❌ Not Authorized"
        
        auth_reasons = []
        if ctx.author.id == self.bot.owner_id:
            auth_reasons.append("Bot Owner")
        if ctx.guild and ctx.author.id == ctx.guild.owner_id:
            auth_reasons.append("Guild Owner")
        if ctx.guild and ctx.author.guild_permissions.administrator:
            auth_reasons.append("Administrator")
        if ctx.guild and ctx.author.guild_permissions.manage_guild:
            auth_reasons.append("Manage Server")
        if ctx.author.id in self.config["settings"]["authorized_users"]:
            auth_reasons.append("Manually Authorized")
        
        embed.add_field(
            name="🔐 Your Access Level",
            value=f"{auth_status}" + (f" ({', '.join(auth_reasons)})" if auth_reasons else ""),
            inline=False
        )
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @globalban_group.command(name="customize")
    async def customize_dm_embed(self, ctx):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to customize DM settings.\n\n**Required Permissions:**\n• Bot Owner\n• Guild Owner\n• Administrator\n• Manage Server\n• Manually Authorized",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        view = CustomizeView(self, ctx)
        embed = view.create_main_embed()
        
        await ctx.send(embed=embed, view=view)
    
    @globalban_group.command(name="templates")
    async def show_templates(self, ctx):
        
        embed = discord.Embed(
            title="📋 Available Templates",
            description="Pre-made templates you can use in the customizer",
            color=discord.Color.blue()
        )
        
        templates = {
            "gaming_server": "🎮 Gaming-focused with casual tone",
            "professional": "💼 Professional and formal",
            "friendly": "😊 Friendly and apologetic tone",
            "minimal": "📝 Simple and to the point",
            "detailed": "📊 Comprehensive with all details",
            "corporate": "🏢 Corporate/business style",
            "casual": "😎 Very casual and relaxed"
        }
        
        for name, description in templates.items():
            embed.add_field(
                name=f"`{name}`",
                value=description,
                inline=True
            )
        
        embed.add_field(
            name="📥 How to Use",
            value="1. Use `!gb customize`\n2. Click 'Import JSON'\n3. Type a template name\n4. Preview and save!",
            inline=False
        )
        
        embed.add_field(
            name="🔧 Custom JSON",
            value="You can also create your own JSON templates with the structure:\n```json\n{\n  \"title\": \"Your title with {variables}\",\n  \"description\": \"Your description\",\n  \"color\": 16711680\n}\n```",
            inline=False
        )
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @globalban_group.command(name="add")
    async def add_global_ban(self, ctx, user_id: int, *, reason_and_duration: str):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to use global ban commands.\n\n**Required Permissions:**\n• Bot Owner\n• Guild Owner\n• Administrator\n• Manage Server\n• Manually Authorized",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        

        guild_id = ctx.guild.id if ctx.guild else 0
        can_proceed, rate_msg = self.check_rate_limits(guild_id, ctx.author.id)
        if not can_proceed:
            embed = discord.Embed(
                title="⏰ Rate Limited",
                description=rate_msg,
                color=discord.Color.orange()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        

        parts = reason_and_duration.split()
        duration = None
        reason = reason_and_duration
        

        if parts and any(char in parts[-1] for char in ['d', 'h', 'm', 's', 'w']):
            duration_str = parts[-1]
            reason = ' '.join(parts[:-1])
            duration = self.parse_duration(duration_str)
        

        reason = self.sanitize_reason(reason)
        

        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            user = None
        

        ban_data = {
            "user_id": user_id,
            "reason": reason,
            "banned_by": ctx.author.id,
            "banned_by_guild": ctx.guild.id if ctx.guild else None,
            "banned_at": datetime.utcnow().isoformat(),
            "expires_at": duration.isoformat() if duration else None,
            "username": user.name if user else "Unknown User",
            "active": True
        }
        
        self.config["global_bans"][str(user_id)] = ban_data
        self.save_config()
        

        self.update_rate_limits(guild_id, ctx.author.id)
        

        embed = discord.Embed(
            title="✅ Global Ban Added",
            description=f"User has been added to the global ban list",
            color=discord.Color.green()
        )
        
        embed.add_field(name="User", value=f"{user.name if user else 'Unknown'} ({user_id})", inline=True)
        embed.add_field(name="Banned By", value=ctx.author.mention, inline=True)
        embed.add_field(name="Guild", value=ctx.guild.name if ctx.guild else "DM", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        
        if duration:
            embed.add_field(name="Expires", value=duration.strftime('%Y-%m-%d %H:%M:%S UTC'), inline=True)
        else:
            embed.add_field(name="Duration", value="Permanent", inline=True)
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
        

        await self.log_action("Global Ban Added", ban_data, ctx.guild)
    
    @globalban_group.command(name="remove")
    async def remove_global_ban(self, ctx, user_id: int):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to use global ban commands.\n\n**Required Permissions:**\n• Bot Owner\n• Guild Owner\n• Administrator\n• Manage Server\n• Manually Authorized",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if str(user_id) not in self.config["global_bans"]:
            embed = discord.Embed(
                title="❌ Not Found",
                description="User is not in the global ban list.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        ban_data = self.config["global_bans"][str(user_id)]
        del self.config["global_bans"][str(user_id)]
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Global Ban Removed",
            description=f"User {ban_data['username']} ({user_id}) has been removed from the global ban list.",
            color=discord.Color.green()
        )
        embed.add_field(name="Removed By", value=ctx.author.mention, inline=True)
        embed.add_field(name="Guild", value=ctx.guild.name if ctx.guild else "DM", inline=True)
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
        
        await self.log_action("Global Ban Removed", ban_data, ctx.guild)
    
    @globalban_group.command(name="list")
    async def list_global_bans(self, ctx):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to use global ban commands.\n\n**Required Permissions:**\n• Bot Owner\n• Guild Owner\n• Administrator\n• Manage Server\n• Manually Authorized",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        global_bans = self.config["global_bans"]
        
        if not global_bans:
            embed = discord.Embed(
                title="📋 Global Ban List",
                description="No users are currently globally banned.",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="📋 Global Ban List",
            description=f"Total globally banned users: {len(global_bans)}",
            color=discord.Color.red()
        )
        
        active_bans = []
        expired_bans = []
        
        for user_id, ban_data in list(global_bans.items())[:10]:
            status = "🔴 Active"
            if ban_data.get("expires_at"):
                try:
                    expires_at = datetime.fromisoformat(ban_data["expires_at"])
                    if datetime.utcnow() > expires_at:
                        status = "🟡 Expired"
                        expired_bans.append(ban_data)
                    else:
                        active_bans.append(ban_data)
                except:
                    active_bans.append(ban_data)
            else:
                active_bans.append(ban_data)
            
            ban_info = f"**{ban_data['username']}** ({user_id})\n"
            ban_info += f"Reason: {ban_data['reason'][:50]}{'...' if len(ban_data['reason']) > 50 else ''}\n"
            ban_info += f"Status: {status}\n"
            ban_info += f"Banned by: <@{ban_data['banned_by']}>"
            
            embed.add_field(name=f"User {user_id}", value=ban_info, inline=True)
        
        if len(global_bans) > 10:
            embed.add_field(name="...", value=f"And {len(global_bans) - 10} more bans", inline=False)
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @globalban_group.command(name="check")
    async def check_ban_status(self, ctx, user_id: int):
        

        ban_data = self.config["global_bans"].get(str(user_id))
        
        if not ban_data or not ban_data.get("active", True):
            embed = discord.Embed(
                title="✅ Not Banned",
                description=f"User {user_id} is not globally banned.",
                color=discord.Color.green()
            )
        else:

            if ban_data.get("expires_at"):
                try:
                    expires_at = datetime.fromisoformat(ban_data["expires_at"])
                    if datetime.utcnow() > expires_at:
                        embed = discord.Embed(
                            title="🟡 Ban Expired",
                            description=f"User {ban_data['username']} ({user_id}) had a global ban that has expired.",
                            color=discord.Color.gold()
                        )
                        embed.add_field(name="Expired At", value=ban_data["expires_at"], inline=True)
                        embed.set_footer(text="Made by TheHolyOneZ")
                        await ctx.send(embed=embed)
                        return
                except:
                    pass
            
            embed = discord.Embed(
                title="🚫 Globally Banned",
                description=f"User {ban_data['username']} ({user_id}) is globally banned.",
                color=discord.Color.red()
            )
            
            embed.add_field(name="Reason", value=ban_data["reason"], inline=False)
            embed.add_field(name="Banned By", value=f"<@{ban_data['banned_by']}>", inline=True)
            embed.add_field(name="Banned At", value=ban_data["banned_at"][:10], inline=True)
            
            if ban_data.get("expires_at"):
                embed.add_field(name="Expires", value=ban_data["expires_at"][:10], inline=True)
            else:
                embed.add_field(name="Duration", value="Permanent", inline=True)
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @globalban_group.command(name="settings")
    async def configure_settings(self, ctx):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to use global ban commands.\n\n**Required Permissions:**\n• Bot Owner\n• Guild Owner\n• Administrator\n• Manage Server\n• Manually Authorized",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        settings = self.config["settings"]
        rate_settings = settings["rate_limit_settings"]
        prefix = self.get_prefix(ctx)
        
        embed = discord.Embed(
            title="⚙️ Global Ban Settings",
            description="Current system configuration",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Check Mode", value=settings["check_mode"], inline=True)
        embed.add_field(name="Check Interval", value=f"{settings['check_interval']} seconds", inline=True)
        embed.add_field(name="Authorized Users", value=len(settings["authorized_users"]), inline=True)
        
        embed.add_field(name="Webhook Logging", value="✅ Enabled" if settings["log_webhook"] else "❌ Disabled", inline=True)
        embed.add_field(name="Total Global Bans", value=len(self.config["global_bans"]), inline=True)
        embed.add_field(name="Protected Servers", value=len(self.bot.guilds), inline=True)
        
        embed.add_field(
            name="Rate Limiting",
            value=f"Guild: {rate_settings['guild_cooldown']}s\nUser: {rate_settings['user_cooldown']}s\nMax/min: {rate_settings['max_bans_per_minute']}",
            inline=True
        )
        
        embed.add_field(
            name="Auto Cleanup",
            value="✅ Enabled" if settings["auto_cleanup"]["enabled"] else "❌ Disabled",
            inline=True
        )
        
        embed.add_field(
            name="Configuration Commands",
            value=(
                f"`{prefix}gb authorize <user_id>` - Add authorized user\n"
                f"`{prefix}gb unauthorize <user_id>` - Remove authorized user\n"
                f"`{prefix}gb webhook <url>` - Set logging webhook\n"
                f"`{prefix}gb checkmode <mode>` - Set check mode\n"
                f"`{prefix}gb interval <seconds>` - Set check interval\n"
                f"`{prefix}gb ratelimit` - Configure rate limits"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Customization Commands",
            value=(
                f"`{prefix}gb customize` - Interactive DM customizer\n"
                f"`{prefix}gb templates` - View available templates\n"
                f"`{prefix}gb preview` - Preview current DM"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Check Modes",
            value="• `on_join` - Check only when users join\n• `periodic` - Check all members periodically\n• `both` - Check on join AND periodically",
            inline=False
        )
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    
    @globalban_group.command(name="stats")
    async def view_statistics(self, ctx):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to use global ban commands.\n\n**Required Permissions:**\n• Bot Owner\n• Guild Owner\n• Administrator\n• Manage Server\n• Manually Authorized",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        global_bans = self.config["global_bans"]
        
        total_bans = len(global_bans)
        active_bans = 0
        expired_bans = 0
        permanent_bans = 0
        temporary_bans = 0
        
        for ban_data in global_bans.values():
            if ban_data.get("expires_at"):
                temporary_bans += 1
                try:
                    expires_at = datetime.fromisoformat(ban_data["expires_at"])
                    if datetime.utcnow() > expires_at:
                        expired_bans += 1
                    else:
                        active_bans += 1
                except:
                    active_bans += 1
            else:
                permanent_bans += 1
                active_bans += 1
        
        embed = discord.Embed(
            title="📊 Global Ban Statistics",
            description="System usage statistics",
            color=discord.Color.gold()
        )
        
        embed.add_field(name="Total Bans", value=total_bans, inline=True)
        embed.add_field(name="Active Bans", value=active_bans, inline=True)
        embed.add_field(name="Expired Bans", value=expired_bans, inline=True)
        
        embed.add_field(name="Permanent Bans", value=permanent_bans, inline=True)
        embed.add_field(name="Temporary Bans", value=temporary_bans, inline=True)
        embed.add_field(name="Protected Servers", value=len(self.bot.guilds), inline=True)
        
        embed.add_field(name="Authorized Users", value=len(self.config["settings"]["authorized_users"]), inline=True)
        embed.add_field(name="Check Mode", value=self.config["settings"]["check_mode"], inline=True)
        embed.add_field(name="Webhook Logging", value="✅" if self.config["settings"]["log_webhook"] else "❌", inline=True)
        
        recent_bans = 0
        for ban_data in global_bans.values():
            try:
                banned_at = datetime.fromisoformat(ban_data["banned_at"])
                if (datetime.utcnow() - banned_at).days <= 7:
                    recent_bans += 1
            except:
                continue
        
        embed.add_field(name="Recent Bans (7 days)", value=recent_bans, inline=True)
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @globalban_group.command(name="preview")
    async def preview_current_dm(self, ctx):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to preview DM settings.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        settings = self.config["settings"]["embed_settings"]
        

        sample_data = {
            "user": ctx.author.mention,
            "username": ctx.author.name,
            "user_id": str(ctx.author.id),
            "bot_name": self.bot.user.name,
            "server": ctx.guild.name if ctx.guild else "Sample Server",
            "guild": ctx.guild.name if ctx.guild else "Sample Server",
            "reason": "Sample ban reason for preview",
            "ban_date": "2024-01-01",
            "expires": "Never",
            "banned_by": ctx.author.mention
        }
        

        try:
            formatted_title = settings["title"].format(**sample_data)
            formatted_description = settings["description"].format(**sample_data)
        except KeyError as e:
            embed = discord.Embed(
                title="❌ Preview Error",
                description=f"Invalid variable in template: {e}",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Available Variables",
                value=", ".join([f"`{{{var}}}`" for var in sample_data.keys()]),
                inline=False
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        

        preview_embed = discord.Embed(
            title=formatted_title,
            description=formatted_description,
            color=settings["color"]
        )
        
        preview_embed.add_field(name="Reason", value=sample_data["reason"], inline=False)
        preview_embed.add_field(name="Server Attempted", value=sample_data["server"], inline=True)
        preview_embed.add_field(name="Duration", value="Permanent", inline=True)
        preview_embed.set_footer(text="Made by TheHolyOneZ")
        

        explanation_embed = discord.Embed(
            title="📋 Current DM Preview",
            description="This is how the DM currently looks when sent to globally banned users:",
            color=discord.Color.blue()
        )
        explanation_embed.set_footer(text="Made by TheHolyOneZ")
        
        await ctx.send(embed=explanation_embed)
        await ctx.send(embed=preview_embed)
    
    @globalban_group.command(name="authorize")
    async def authorize_user(self, ctx, user_id: int):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to authorize users.\n\n**Required Permissions:**\n• Bot Owner\n• Guild Owner\n• Administrator\n• Manage Server\n• Manually Authorized",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if user_id not in self.config["settings"]["authorized_users"]:
            self.config["settings"]["authorized_users"].append(user_id)
            self.save_config()
            
            try:
                user = await self.bot.fetch_user(user_id)
                username = user.name
            except:
                username = "Unknown User"
            
            embed = discord.Embed(
                title="✅ User Authorized",
                description=f"User {username} ({user_id}) has been authorized to use global ban commands.",
                color=discord.Color.green()
            )
            embed.add_field(name="Authorized By", value=ctx.author.mention, inline=True)
            embed.add_field(name="Guild", value=ctx.guild.name if ctx.guild else "DM", inline=True)
        else:
            embed = discord.Embed(
                title="ℹ️ Already Authorized",
                description=f"User {user_id} is already authorized.",
                color=discord.Color.blue()
            )
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @globalban_group.command(name="unauthorize")
    async def unauthorize_user(self, ctx, user_id: int):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to unauthorize users.\n\n**Required Permissions:**\n• Bot Owner\n• Guild Owner\n• Administrator\n• Manage Server\n• Manually Authorized",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if user_id in self.config["settings"]["authorized_users"]:
            self.config["settings"]["authorized_users"].remove(user_id)
            self.save_config()
            
            try:
                user = await self.bot.fetch_user(user_id)
                username = user.name
            except:
                username = "Unknown User"
            
            embed = discord.Embed(
                title="✅ Authorization Removed",
                description=f"User {username} ({user_id}) is no longer authorized to use global ban commands.",
                color=discord.Color.green()
            )
            embed.add_field(name="Removed By", value=ctx.author.mention, inline=True)
            embed.add_field(name="Guild", value=ctx.guild.name if ctx.guild else "DM", inline=True)
        else:
            embed = discord.Embed(
                title="ℹ️ Not Authorized",
                description=f"User {user_id} is not currently authorized.",
                color=discord.Color.blue()
            )
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @globalban_group.command(name="webhook")
    async def set_webhook(self, ctx, webhook_url: str = None):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to configure webhooks.\n\n**Required Permissions:**\n• Bot Owner\n• Guild Owner\n• Administrator\n• Manage Server\n• Manually Authorized",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if webhook_url is None:

            self.config["settings"]["log_webhook"] = None
            self.save_config()
            
            embed = discord.Embed(
                title="✅ Webhook Removed",
                description="Logging webhook has been removed.",
                color=discord.Color.green()
            )
        else:

            try:
                async with aiohttp.ClientSession() as session:
                    webhook = discord.Webhook.from_url(webhook_url, session=session)
                    test_embed = discord.Embed(
                        title="🧪 Webhook Test",
                        description="Global ban logging webhook configured successfully!",
                        color=discord.Color.green()
                    )
                    test_embed.add_field(name="Configured By", value=ctx.author.mention, inline=True)
                    test_embed.add_field(name="Guild", value=ctx.guild.name if ctx.guild else "DM", inline=True)
                    test_embed.set_footer(text="Made by TheHolyOneZ")
                    await webhook.send(embed=test_embed)
                
                self.config["settings"]["log_webhook"] = webhook_url
                self.save_config()
                
                embed = discord.Embed(
                    title="✅ Webhook Configured",
                    description="Logging webhook has been set and tested successfully.",
                    color=discord.Color.green()
                )
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Webhook Error",
                    description=f"Failed to configure webhook: {str(e)}",
                    color=discord.Color.red()
                )
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)

    @globalban_group.command(name="checkmode")
    async def set_check_mode(self, ctx, mode: str):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to configure check mode.\n\n**Required Permissions:**\n• Bot Owner\n• Guild Owner\n• Administrator\n• Manage Server\n• Manually Authorized",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        valid_modes = ["on_join", "periodic", "both"]
        
        if mode.lower() not in valid_modes:
            embed = discord.Embed(
                title="❌ Invalid Mode",
                description=f"Valid modes are: {', '.join(valid_modes)}",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Mode Descriptions",
                value="• `on_join` - Check only when users join\n• `periodic` - Check all members periodically\n• `both` - Check on join AND periodically",
                inline=False
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        self.config["settings"]["check_mode"] = mode.lower()
        self.save_config()
        

        if hasattr(self, 'global_ban_check'):
            self.global_ban_check.cancel()
            self.global_ban_check.start()
        
        embed = discord.Embed(
            title="✅ Check Mode Updated",
            description=f"Global ban check mode set to: **{mode.lower()}**",
            color=discord.Color.green()
        )
        
        mode_descriptions = {
            "on_join": "Users will be checked only when they join a server",
            "periodic": "All server members will be checked periodically",
            "both": "Users will be checked on join AND periodically"
        }
        
        embed.add_field(name="Description", value=mode_descriptions[mode.lower()], inline=False)
        embed.add_field(name="Updated By", value=ctx.author.mention, inline=True)
        embed.add_field(name="Guild", value=ctx.guild.name if ctx.guild else "DM", inline=True)
        

        if mode.lower() in ["periodic", "both"]:
            current_interval = self.config["settings"]["check_interval"]
            embed.add_field(
                name="Current Check Interval", 
                value=f"{current_interval} seconds\nUse `!gb interval <seconds>` to change", 
                inline=False
            )
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @globalban_group.command(name="interval")
    async def set_check_interval(self, ctx, seconds: int):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to configure check interval.\n\n**Required Permissions:**\n• Bot Owner\n• Guild Owner\n• Administrator\n• Manage Server\n• Manually Authorized",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if seconds < 30:
            embed = discord.Embed(
                title="❌ Invalid Interval",
                description="Check interval must be at least 30 seconds to avoid rate limiting.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if seconds > 3600:
            embed = discord.Embed(
                title="❌ Invalid Interval",
                description="Check interval cannot exceed 1 hour (3600 seconds).",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        old_interval = self.config["settings"]["check_interval"]
        self.config["settings"]["check_interval"] = seconds
        self.save_config()
        

        if hasattr(self, 'global_ban_check'):
            self.global_ban_check.cancel()
            self.global_ban_check.change_interval(seconds=seconds)
            self.global_ban_check.start()
        
        embed = discord.Embed(
            title="✅ Check Interval Updated",
            description=f"Periodic check interval changed from {old_interval}s to {seconds}s",
            color=discord.Color.green()
        )
        
        embed.add_field(name="New Interval", value=f"{seconds} seconds", inline=True)
        embed.add_field(name="Updated By", value=ctx.author.mention, inline=True)
        embed.add_field(name="Guild", value=ctx.guild.name if ctx.guild else "DM", inline=True)
        

        if seconds < 300:
            embed.add_field(
                name="⚠️ Performance Warning",
                value="Short intervals may impact bot performance with many servers.",
                inline=False
            )
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @globalban_group.group(name="ratelimit", invoke_without_command=True)
    async def ratelimit_group(self, ctx):
        
        await self.configure_rate_limits(ctx)
    
    @ratelimit_group.command(name="guild")
    async def set_guild_cooldown(self, ctx, seconds: int):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to configure rate limits.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if seconds < 1 or seconds > 300:
            embed = discord.Embed(
                title="❌ Invalid Value",
                description="Guild cooldown must be between 1 and 300 seconds.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        self.config["settings"]["rate_limit_settings"]["guild_cooldown"] = seconds
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Guild Cooldown Updated",
            description=f"Guild cooldown set to {seconds} seconds.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @ratelimit_group.command(name="user")
    async def set_user_cooldown(self, ctx, seconds: int):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to configure rate limits.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if seconds < 1 or seconds > 3600:
            embed = discord.Embed(
                title="❌ Invalid Value",
                description="User cooldown must be between 1 and 3600 seconds.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        self.config["settings"]["rate_limit_settings"]["user_cooldown"] = seconds
        self.save_config()
        
        embed = discord.Embed(
            title="✅ User Cooldown Updated",
            description=f"User cooldown set to {seconds} seconds.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @ratelimit_group.command(name="max")
    async def set_max_bans(self, ctx, count: int):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to configure rate limits.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if count < 1 or count > 100:
            embed = discord.Embed(
                title="❌ Invalid Value",
                description="Max bans per minute must be between 1 and 100.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        self.config["settings"]["rate_limit_settings"]["max_bans_per_minute"] = count
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Max Bans Updated",
            description=f"Maximum bans per minute set to {count}.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @tasks.loop(seconds=60)
    async def global_ban_check(self):
        
        if self.config["settings"]["check_mode"] in ["periodic", "both"]:
            for guild in self.bot.guilds:
                try:
                    for member in guild.members:
                        if await self.is_globally_banned(member.id):
                            await self.check_and_ban_user(member)
                            await asyncio.sleep(1)
                    await asyncio.sleep(5)
                except Exception as e:
                    logger.error(f"Error checking guild {guild.name}: {e}")
                    continue
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        
        if self.config["settings"]["check_mode"] in ["on_join", "both"]:
            await self.check_and_ban_user(member)
    
    async def check_and_ban_user(self, member):
        
        ban_data = self.config["global_bans"].get(str(member.id))
        
        if not ban_data or not ban_data.get("active", True):
            return
        

        if ban_data.get("expires_at"):
            try:
                expires_at = datetime.fromisoformat(ban_data["expires_at"])
                if datetime.utcnow() > expires_at:
                    ban_data["active"] = False
                    self.save_config()
                    return
            except:
                pass
        

        guild_id = member.guild.id
        current_time = datetime.utcnow()
        
        if guild_id in self.rate_limiter:
            if current_time - self.rate_limiter[guild_id] < timedelta(seconds=5):
                return
        
        self.rate_limiter[guild_id] = current_time
        
        try:

            await self.send_ban_dm(member, ban_data)
            

            await member.ban(reason=f"Global Ban: {ban_data['reason']}")
            

            await self.log_ban_attempt(member, ban_data)
            
        except discord.Forbidden:
            logger.warning(f"Cannot ban {member} in {member.guild.name} - insufficient permissions")
        except Exception as e:
            logger.error(f"Error banning globally banned user {member}: {e}")
    
    async def send_ban_dm(self, member, ban_data):
        
        settings = self.config["settings"]["embed_settings"]
        

        variables = {
            "user": member.mention,
            "username": member.name,
            "user_id": str(member.id),
            "bot_name": self.bot.user.name,
            "server": member.guild.name,
            "guild": member.guild.name,
            "reason": ban_data["reason"],
            "ban_date": ban_data["banned_at"][:10],
            "expires": ban_data.get("expires_at", "Never")[:10] if ban_data.get("expires_at") else "Never",
            "banned_by": f"<@{ban_data['banned_by']}>"
        }
        
        try:

            formatted_title = settings["title"].format(**variables)
            formatted_description = settings["description"].format(**variables)
        except KeyError as e:

            logger.warning(f"Error formatting DM embed: Missing variable {e}")
            formatted_title = settings["title"]
            formatted_description = settings["description"].replace("{bot_name}", self.bot.user.name)
        except Exception as e:

            logger.error(f"Error formatting DM embed: {e}")
            formatted_title = "🚫 Global Ban Notice"
            formatted_description = f"You have been globally banned from servers using {self.bot.user.name}"
        

        embed = discord.Embed(
            title=formatted_title,
            description=formatted_description,
            color=settings["color"]
        )
        

        embed.add_field(name="Reason", value=ban_data["reason"], inline=False)
        embed.add_field(name="Server Attempted", value=member.guild.name, inline=True)
        embed.add_field(name="Your User ID", value=str(member.id), inline=True)
        

        if ban_data.get("expires_at"):
            try:
                expires_at = datetime.fromisoformat(ban_data["expires_at"])
                embed.add_field(name="Ban Expires", value=expires_at.strftime('%Y-%m-%d %H:%M:%S UTC'), inline=True)
            except:
                embed.add_field(name="Ban Expires", value=ban_data["expires_at"][:10], inline=True)
        else:
            embed.add_field(name="Duration", value="Permanent", inline=True)
        

        embed.add_field(name="Originally Banned", value=ban_data["banned_at"][:10], inline=True)
        embed.add_field(name="Banned By", value=f"<@{ban_data['banned_by']}>", inline=True)
        

        embed.set_footer(text=f"Made by TheHolyOneZ • {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        

        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
        
        try:
            await member.send(embed=embed)
            logger.info(f"Sent global ban DM to {member.name} ({member.id})")
        except discord.Forbidden:
            logger.warning(f"Could not send DM to {member.name} ({member.id}) - DMs disabled")
        except discord.HTTPException as e:
            logger.error(f"Failed to send DM to {member.name} ({member.id}): {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending DM to {member.name} ({member.id}): {e}")
    
    async def log_action(self, action: str, ban_data: dict, guild):
        
        webhook_url = self.config["settings"].get("log_webhook")
        if not webhook_url:
            return
        
        embed = discord.Embed(
            title=f"🌐 {action}",
            color=discord.Color.orange()
        )
        
        embed.add_field(name="User", value=f"{ban_data['username']} ({ban_data['user_id']})", inline=True)
        embed.add_field(name="Guild", value=guild.name if guild else "DM", inline=True)
        embed.add_field(name="Action By", value=f"<@{ban_data['banned_by']}>", inline=True)
        embed.add_field(name="Reason", value=ban_data["reason"], inline=False)
        
        if ban_data.get("expires_at"):
            embed.add_field(name="Expires", value=ban_data["expires_at"][:10], inline=True)
        else:
            embed.add_field(name="Duration", value="Permanent", inline=True)
        
        embed.set_footer(text="Made by TheHolyOneZ")
        
        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(webhook_url, session=session)
                await webhook.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send webhook log: {e}")
    
    async def log_ban_attempt(self, member, ban_data):
        
        webhook_url = self.config["settings"].get("log_webhook")
        if not webhook_url:
            return
        
        embed = discord.Embed(
            title="🚫 Global Ban Executed",
            description=f"Globally banned user attempted to join {member.guild.name}",
            color=discord.Color.red()
        )
        
        embed.add_field(name="User", value=f"{member.name} ({member.id})", inline=True)
        embed.add_field(name="Server", value=member.guild.name, inline=True)
        embed.add_field(name="Member Count", value=len(member.guild.members), inline=True)
        embed.add_field(name="Reason", value=ban_data["reason"], inline=False)
        embed.add_field(name="Originally Banned By", value=f"<@{ban_data['banned_by']}>", inline=True)
        embed.add_field(name="Ban Date", value=ban_data["banned_at"][:10], inline=True)
        
        if ban_data.get("expires_at"):
            embed.add_field(name="Expires", value=ban_data["expires_at"][:10], inline=True)
        else:
            embed.add_field(name="Duration", value="Permanent", inline=True)
        
        embed.set_footer(text="Made by TheHolyOneZ")
        
        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(webhook_url, session=session)
                await webhook.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send ban attempt log: {e}")
    
    def parse_duration(self, duration_str: str) -> Optional[datetime]:
        
        total_seconds = 0
        current_number = ""
        
        time_units = {'w': 604800, 'd': 86400, 'h': 3600, 'm': 60, 's': 1}
        
        for char in duration_str.lower():
            if char.isdigit():
                current_number += char
            elif char in time_units:
                if current_number:
                    total_seconds += int(current_number) * time_units[char]
                    current_number = ""
        
        if total_seconds > 0:
            return datetime.utcnow() + timedelta(seconds=total_seconds)
        return None
    
    def sanitize_reason(self, reason: str) -> str:
        
        if not reason or len(reason.strip()) == 0:
            return "No reason provided"
        

        reason = ' '.join(reason.split())
        

        if len(reason) > 500:
            reason = reason[:497] + "..."
        

        harmful_patterns = [
            r'@everyone',
            r'@here',
            r'<@&\d+>',
            r'discord\.gg/\w+',
            r'https?://[^\s]+',
        ]
        
        for pattern in harmful_patterns:
            reason = re.sub(pattern, '[REMOVED]', reason, flags=re.IGNORECASE)
        
        return reason
    
    async def is_globally_banned(self, user_id: int) -> bool:
        
        ban_data = self.config["global_bans"].get(str(user_id))
        if not ban_data or not ban_data.get("active", True):
            return False
        

        if ban_data.get("expires_at"):
            try:
                expires_at = datetime.fromisoformat(ban_data["expires_at"])
                if datetime.utcnow() > expires_at:
                    ban_data["active"] = False
                    self.save_config()
                    return False
            except:
                pass
        
        return True
    
    @global_ban_check.before_loop
    async def before_global_ban_check(self):
        
        await self.bot.wait_until_ready()
    
    @tasks.loop(hours=1)
    async def cleanup_expired_bans(self):
        
        if not self.config["settings"]["auto_cleanup"]["enabled"]:
            return
        
        if not self.config["settings"]["auto_cleanup"]["cleanup_expired"]:
            return
        
        expired_count = 0
        current_time = datetime.utcnow()
        
        for user_id, ban_data in list(self.config["global_bans"].items()):
            if ban_data.get("expires_at"):
                try:
                    expires_at = datetime.fromisoformat(ban_data["expires_at"])
                    if current_time > expires_at:
                        ban_data["active"] = False
                        expired_count += 1
                except:
                    continue
        
        if expired_count > 0:
            self.save_config()
            logger.info(f"Cleaned up {expired_count} expired global bans")
    
    @cleanup_expired_bans.before_loop
    async def before_cleanup_expired_bans(self):
        
        await self.bot.wait_until_ready()
    
    def cog_unload(self):
        
        self.global_ban_check.cancel()
        if hasattr(self, 'cleanup_expired_bans'):
            self.cleanup_expired_bans.cancel()

async def setup(bot):
    
    await bot.add_cog(GlobalBanSystem(bot))

def setup(bot):
    
    cog = GlobalBanSystem(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    return cog



@commands.Cog.listener()
async def on_command_error(self, ctx, error):
    
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ Missing Permissions",
            description="You don't have the required permissions to use this command.",
            color=discord.Color.red()
        )
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    elif isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            title="❌ Invalid Argument",
            description="Please check your command arguments and try again.",
            color=discord.Color.red()
        )
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    elif isinstance(error, commands.CommandOnCooldown):
        embed = discord.Embed(
            title="⏰ Command on Cooldown",
            description=f"Please wait {error.retry_after:.1f} seconds before using this command again.",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)



    @globalban_group.command(name="import")
    async def import_bans(self, ctx, *, json_data: str = None):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to import bans.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if not json_data:
            embed = discord.Embed(
                title="📥 Import Global Bans",
                description="Import global bans from JSON data",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Usage",
                value=f"`{self.get_prefix(ctx)}gb import <json_data>`",
                inline=False
            )
            embed.add_field(
                name="JSON Format",
                value="```json\n{\n  \"user_id\": {\n    \"reason\": \"Ban reason\",\n    \"banned_by\": 123456789,\n    \"expires_at\": \"2024-12-31T23:59:59\"\n  }\n}\n```",
                inline=False
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        try:
            import_data = json.loads(json_data)
            imported_count = 0
            
            for user_id, ban_info in import_data.items():
                if not isinstance(ban_info, dict):
                    continue
                

                if "reason" not in ban_info:
                    continue
                
                ban_data = {
                    "user_id": int(user_id),
                    "reason": self.sanitize_reason(ban_info["reason"]),
                    "banned_by": ban_info.get("banned_by", ctx.author.id),
                    "banned_by_guild": ctx.guild.id if ctx.guild else None,
                    "banned_at": ban_info.get("banned_at", datetime.utcnow().isoformat()),
                    "expires_at": ban_info.get("expires_at"),
                    "username": ban_info.get("username", "Imported User"),
                    "active": ban_info.get("active", True)
                }
                
                self.config["global_bans"][str(user_id)] = ban_data
                imported_count += 1
            
            self.save_config()
            
            embed = discord.Embed(
                title="✅ Import Successful",
                description=f"Successfully imported {imported_count} global bans.",
                color=discord.Color.green()
            )
            embed.add_field(name="Imported By", value=ctx.author.mention, inline=True)
            embed.add_field(name="Guild", value=ctx.guild.name if ctx.guild else "DM", inline=True)
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            
        except json.JSONDecodeError:
            embed = discord.Embed(
                title="❌ Invalid JSON",
                description="The provided JSON data is invalid. Please check the format.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Import Error",
                description=f"An error occurred during import: {str(e)}",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)

    @globalban_group.command(name="export")
    async def export_bans(self, ctx):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to export bans.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if not self.config["global_bans"]:
            embed = discord.Embed(
                title="📤 No Bans to Export",
                description="There are no global bans to export.",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        try:
            export_data = {
                "exported_at": datetime.utcnow().isoformat(),
                "exported_by": ctx.author.id,
                "total_bans": len(self.config["global_bans"]),
                "bans": self.config["global_bans"]
            }
            
            json_str = json.dumps(export_data, indent=2)
            file = discord.File(io.StringIO(json_str), filename=f"global_bans_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
            
            embed = discord.Embed(
                title="📤 Export Complete",
                description=f"Exported {len(self.config['global_bans'])} global bans.",
                color=discord.Color.green()
            )
            embed.add_field(name="Exported By", value=ctx.author.mention, inline=True)
            embed.add_field(name="Guild", value=ctx.guild.name if ctx.guild else "DM", inline=True)
            embed.set_footer(text="Made by TheHolyOneZ")
            
            await ctx.send(embed=embed, file=file)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Export Error",
                description=f"An error occurred during export: {str(e)}",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)

    @globalban_group.command(name="cleanup")
    async def manual_cleanup(self, ctx):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to run cleanup.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        expired_count = 0
        current_time = datetime.utcnow()
        
        for user_id, ban_data in list(self.config["global_bans"].items()):
            if ban_data.get("expires_at"):
                try:
                    expires_at = datetime.fromisoformat(ban_data["expires_at"])
                    if current_time > expires_at:
                        ban_data["active"] = False
                        expired_count += 1
                except:
                    continue
        
        if expired_count > 0:
            self.save_config()
        
        embed = discord.Embed(
            title="🧹 Cleanup Complete",
            description=f"Cleaned up {expired_count} expired global bans.",
            color=discord.Color.green()
        )
        embed.add_field(name="Cleaned By", value=ctx.author.mention, inline=True)
        embed.add_field(name="Guild", value=ctx.guild.name if ctx.guild else "DM", inline=True)
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)

    @globalban_group.command(name="search")
    async def search_bans(self, ctx, *, query: str):
        
        if not await self.is_authorized(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to search bans.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        query = query.lower()
        matches = []
        
        for user_id, ban_data in self.config["global_bans"].items():
            if (query in ban_data.get("username", "").lower() or 
                query in ban_data.get("reason", "").lower() or
                query in str(user_id)):
                matches.append((user_id, ban_data))
        
        if not matches:
            embed = discord.Embed(
                title="🔍 No Results",
                description=f"No global bans found matching: `{query}`",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🔍 Search Results",
            description=f"Found {len(matches)} matches for: `{query}`",
            color=discord.Color.blue()
        )
        
        for user_id, ban_data in matches[:10]:
            status = "🔴 Active"
            if ban_data.get("expires_at"):
                try:
                    expires_at = datetime.fromisoformat(ban_data["expires_at"])
                    if datetime.utcnow() > expires_at:
                        status = "🟡 Expired"
                except:
                    pass
            
            ban_info = f"**{ban_data['username']}** ({user_id})\n"
            ban_info += f"Reason: {ban_data['reason'][:50]}{'...' if len(ban_data['reason']) > 50 else ''}\n"
            ban_info += f"Status: {status}"
            
            embed.add_field(name=f"Match {matches.index((user_id, ban_data)) + 1}", value=ban_info, inline=True)
        
        if len(matches) > 10:
            embed.add_field(name="...", value=f"And {len(matches) - 10} more matches", inline=False)
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)

    @globalban_group.command(name="info")
    async def ban_info(self, ctx, user_id: int):
        
        ban_data = self.config["global_bans"].get(str(user_id))
        
        if not ban_data:
            embed = discord.Embed(
                title="❌ Not Found",
                description=f"User {user_id} is not globally banned.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        

        status = "🔴 Active"
        if ban_data.get("expires_at"):
            try:
                expires_at = datetime.fromisoformat(ban_data["expires_at"])
                if datetime.utcnow() > expires_at:
                    status = "🟡 Expired"
            except:
                pass
        
        embed = discord.Embed(
            title="📋 Global Ban Information",
            description=f"Details for user {ban_data['username']} ({user_id})",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Username", value=ban_data['username'], inline=True)
        embed.add_field(name="User ID", value=user_id, inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        
        embed.add_field(name="Reason", value=ban_data['reason'], inline=False)
        
        embed.add_field(name="Banned By", value=f"<@{ban_data['banned_by']}>", inline=True)
        embed.add_field(name="Banned At", value=ban_data['banned_at'][:19].replace('T', ' '), inline=True)
        
        if ban_data.get("banned_by_guild"):
            try:
                guild = self.bot.get_guild(ban_data["banned_by_guild"])
                guild_name = guild.name if guild else f"Guild ID: {ban_data['banned_by_guild']}"
                embed.add_field(name="Banned From Guild", value=guild_name, inline=True)
            except:
                embed.add_field(name="Banned From Guild", value=f"Guild ID: {ban_data['banned_by_guild']}", inline=True)
        
        if ban_data.get("expires_at"):
            embed.add_field(name="Expires At", value=ban_data["expires_at"][:19].replace('T', ' '), inline=True)
        else:
            embed.add_field(name="Duration", value="Permanent", inline=True)
        
        embed.add_field(name="Active", value="✅ Yes" if ban_data.get("active", True) else "❌ No", inline=True)
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)

import re

def get_ban_statistics(self):
    
    global_bans = self.config["global_bans"]
    stats = {
        "total": len(global_bans),
        "active": 0,
        "expired": 0,
        "permanent": 0,
        "temporary": 0,
        "recent_7d": 0,
        "recent_30d": 0,
        "by_reason": {},
        "by_admin": {}
    }
    
    current_time = datetime.utcnow()
    week_ago = current_time - timedelta(days=7)
    month_ago = current_time - timedelta(days=30)
    
    for ban_data in global_bans.values():

        if ban_data.get("expires_at"):
            stats["temporary"] += 1
            try:
                expires_at = datetime.fromisoformat(ban_data["expires_at"])
                if current_time > expires_at:
                    stats["expired"] += 1
                else:
                    stats["active"] += 1
            except:
                stats["active"] += 1
        else:
            stats["permanent"] += 1
            stats["active"] += 1
        

        try:
            banned_at = datetime.fromisoformat(ban_data["banned_at"])
            if banned_at > week_ago:
                stats["recent_7d"] += 1
            if banned_at > month_ago:
                stats["recent_30d"] += 1
        except:
            pass
        

        reason_key = ban_data["reason"].split()[0].lower() if ban_data["reason"] else "unknown"
        stats["by_reason"][reason_key] = stats["by_reason"].get(reason_key, 0) + 1
        

        admin_id = str(ban_data["banned_by"])
        stats["by_admin"][admin_id] = stats["by_admin"].get(admin_id, 0) + 1
    
    return stats

def check_rate_limits(self, guild_id: int, user_id: int) -> tuple[bool, str]:
    
    current_time = datetime.utcnow()
    settings = self.config["settings"]["rate_limit_settings"]
    

    if not hasattr(self, 'rate_limit_tracker'):
        self.rate_limit_tracker = {
            "guild_cooldowns": {},
            "user_cooldowns": {},
            "minute_counter": {"count": 0, "reset_time": current_time + timedelta(minutes=1)}
        }
    
    tracker = self.rate_limit_tracker
    

    if current_time > tracker["minute_counter"]["reset_time"]:
        tracker["minute_counter"] = {"count": 0, "reset_time": current_time + timedelta(minutes=1)}
    
    if tracker["minute_counter"]["count"] >= settings["max_bans_per_minute"]:
        return False, f"Rate limit exceeded: Maximum {settings['max_bans_per_minute']} bans per minute"
    

    if guild_id in tracker["guild_cooldowns"]:
        time_diff = (current_time - tracker["guild_cooldowns"][guild_id]).total_seconds()
        if time_diff < settings["guild_cooldown"]:
            return False, f"Guild cooldown: {settings['guild_cooldown'] - time_diff:.1f} seconds remaining"
    

    if user_id in tracker["user_cooldowns"]:
        time_diff = (current_time - tracker["user_cooldowns"][user_id]).total_seconds()
        if time_diff < settings["user_cooldown"]:
            return False, f"User cooldown: {settings['user_cooldown'] - time_diff:.1f} seconds remaining"
    
    return True, "OK"

def update_rate_limits(self, guild_id: int, user_id: int):
    
    current_time = datetime.utcnow()
    
    if not hasattr(self, 'rate_limit_tracker'):
        self.rate_limit_tracker = {
            "guild_cooldowns": {},
            "user_cooldowns": {},
            "minute_counter": {"count": 0, "reset_time": current_time + timedelta(minutes=1)}
        }
    
    tracker = self.rate_limit_tracker
    

    tracker["guild_cooldowns"][guild_id] = current_time
    tracker["user_cooldowns"][user_id] = current_time
    tracker["minute_counter"]["count"] += 1


GlobalBanSystem.get_ban_statistics = get_ban_statistics
GlobalBanSystem.check_rate_limits = check_rate_limits
GlobalBanSystem.update_rate_limits = update_rate_limits


def enhanced_load_config(self):
    
    try:
        with open(self.config_file, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {}
    

    default_config = {
        "global_bans": {},
        "settings": {
            "check_mode": "on_join",
            "check_interval": 60,
            "embed_settings": {
                "title": "🚫 Global Ban Notice",
                "description": "You have been globally banned from servers using {bot_name}.\n\n**Reason:** {reason}\n**Server:** {server}\n**Banned by:** {banned_by}",
                "color": 0xFF0000
            },
            "log_webhook": None,
            "authorized_users": [],
            "rate_limit_settings": {
                "guild_cooldown": 30,
                "user_cooldown": 300,
                "max_bans_per_minute": 10
            },
            "auto_cleanup": {
                "enabled": True,
                "cleanup_expired": True,
                "cleanup_interval": 3600
            },
            "security": {
                "max_reason_length": 500,
                "allow_urls_in_reason": False,
                "sanitize_mentions": True
            }
        }
    }
    

    def merge_dict(default, loaded):
        for key, value in default.items():
            if key not in loaded:
                loaded[key] = value
            elif isinstance(value, dict) and isinstance(loaded[key], dict):
                merge_dict(value, loaded[key])
    
    merge_dict(default_config, config)
    return config


GlobalBanSystem.load_config = enhanced_load_config


ADDITIONAL_TEMPLATES = {
    "corporate": {
        "title": "🏢 Access Restriction Notice",
        "description": "**NOTICE:** User {username} (ID: {user_id})\n\nAccess to {server} has been restricted due to a global security policy violation.\n\n**Violation Details:**\n• **Type:** {reason}\n• **Date:** {ban_date}\n• **Authority:** {banned_by}\n• **Network:** {bot_name}\n\nThis restriction is enforced across all affiliated servers.",
        "color": 0x2F3136
    },
    "casual": {
        "title": "😅 Whoops! Can't join {server}",
        "description": "Hey {username}! 👋\n\nLooks like you can't join {server} right now because of a global ban. Don't worry, it happens! 🤷‍♂️\n\n**What happened?** {reason}\n**When?** {ban_date}\n**Who decided?** {banned_by}\n\nIf you think this is a mistake, just reach out to the server admins! 😊",
        "color": 0xFFA500
    },
    "security": {
        "title": "🔒 Security Alert - Access Denied",
        "description": "**SECURITY NOTICE**\n\nUser: {username} ({user_id})\nTarget Server: {server}\nSecurity Network: {bot_name}\n\n**VIOLATION RECORD:**\n```\nReason: {reason}\nDate: {ban_date}\nExpires: {expires}\nIssued By: {banned_by}\n```\n\n**STATUS:** ACCESS DENIED\n**ACTION:** Automatic ban enforcement active",
        "color": 0x8B0000
    }
}


original_on_submit = JSONImportModal.on_submit

async def enhanced_on_submit(self, interaction: discord.Interaction):
    
    json_str = self.json_input.value.strip()
    

    all_templates = {
        "gaming_server": {
            "title": "🎮 {username}, Access Denied!",
            "description": "Hey {username}! You tried to join **{server}** but you're globally banned from {bot_name}.\n\n**Reason:** {reason}\n**Banned by:** {banned_by}\n**Date:** {ban_date}",
            "color": 15158332
        },
        "professional": {
            "title": "🚫 Global Ban Notification",
            "description": "User {username} (ID: {user_id}),\n\nYou have been denied access to {server} due to a global ban in the {bot_name} network.\n\nViolation: {reason}\nIssued: {ban_date}\nExpires: {expires}",
            "color": 16711680
        },
        "friendly": {
            "title": "😔 Oops! You can't join {server}",
            "description": "Hi {username}! Unfortunately, you can't join {server} because you have a global ban.\n\n💔 **Why?** {reason}\n📅 **When?** {ban_date}\n⏰ **Until?** {expires}\n\nIf you think this is a mistake, please contact the server administrators.",
            "color": 16776960
        },
        "minimal": {
            "title": "🚫 Banned",
            "description": "You are globally banned from {bot_name}. Reason: {reason}",
            "color": 16711680
        },
        "detailed": {
            "title": "🚫 Global Ban - Access Denied",
            "description": "**User:** {username} ({user_id})\n**Server Attempted:** {server}\n**Bot Network:** {bot_name}\n\n**Ban Details:**\n• **Reason:** {reason}\n• **Issued:** {ban_date}\n• **Expires:** {expires}\n• **Banned By:** {banned_by}\n\nThis is an automated message from the global ban system.",
            "color": 16711680
        },
        **ADDITIONAL_TEMPLATES
    }
    
    if json_str.lower() in all_templates:
        self.new_settings = all_templates[json_str.lower()]
        self.success = True
        await interaction.response.send_message(f"✅ Applied template: {json_str}", ephemeral=True)
        return
    

    await original_on_submit(self, interaction)


JSONImportModal.on_submit = enhanced_on_submit


@commands.Cog.listener()
async def on_ready(self):
    
    logger.info("Global Ban System initialized")
    logger.info(f"Loaded {len(self.config['global_bans'])} global bans")
    logger.info(f"Check mode: {self.config['settings']['check_mode']}")
    logger.info(f"Protecting {len(self.bot.guilds)} servers")


GlobalBanSystem.on_ready = on_ready


__version__ = "2.1.0 | Not Fully Tested Report bugs to the official support website: zygnalbot.com/support/"
__author__ = "TheHolyOneZ"
__description__ = "Advanced Global Ban System with customizable DMs and comprehensive management"


def get_cog_info():
    
    return {
        "name": "Global Ban System",
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "commands": [
            "globalban", "gb"
        ],
        "features": [
            "Cross-server ban management",
            "Customizable DM notifications",
            "JSON template system",
            "Rate limiting",
            "Webhook logging",
            "Automatic cleanup",
            "Advanced authorization"
        ]
    }


if __name__ == "__main__":
    print(f"Global Ban System v{__version__} by {__author__}")
    print("This is a Discord bot extension and should be loaded by a bot framework.")
    print("")
    print("ZygnalBot Is a good One! zygnalbot.com")
    print(f"Bye - {__author__}")
