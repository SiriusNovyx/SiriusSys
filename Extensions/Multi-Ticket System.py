import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime
import asyncio
import pytz
import uuid
from typing import Dict, List, Optional, Union, Any
import logging
from PIL import Image, ImageDraw, ImageFont
import html
import csv
import io

logger = logging.getLogger('multi_ticket')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='multi_ticket.log', encoding='utf-8', mode='a')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

class TicketCategory:
    def __init__(self, name: str, description: str, color: int, emoji: str, 
                 custom_fields: List[Dict[str, Any]] = None, 
                 required_roles: List[int] = None,
                 auto_tags: List[str] = None,
                 custom_welcome: str = None,
                 priority_level: int = 0):
        self.name = name
        self.description = description
        self.color = color
        self.emoji = emoji
        self.custom_fields = custom_fields or []
        self.required_roles = required_roles or []
        self.auto_tags = auto_tags or []
        self.custom_welcome = custom_welcome
        self.priority_level = priority_level

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "emoji": self.emoji,
            "custom_fields": self.custom_fields,
            "required_roles": self.required_roles,
            "auto_tags": self.auto_tags,
            "custom_welcome": self.custom_welcome,
            "priority_level": self.priority_level
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data["name"],
            description=data["description"],
            color=data["color"],
            emoji=data["emoji"],
            custom_fields=data.get("custom_fields", []),
            required_roles=data.get("required_roles", []),
            auto_tags=data.get("auto_tags", []),
            custom_welcome=data.get("custom_welcome"),
            priority_level=data.get("priority_level", 0)
        )

class TicketConfig:
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.ticket_channel_id = None
        self.transcript_channel_id = None
        self.support_role_ids = []
        self.admin_role_ids = []
        self.categories = []
        self.allow_anonymous = True
        self.ticket_counter = 0
        self.custom_footer = "Made by TheHolyoneZ"
        self.custom_banner_url = ""
        self.active_tickets = {}
        self.closed_tickets = {}
        self.ticket_category_id = None  
        self.ticket_logs_enabled = True
        self.ticket_naming_format = "ticket-{number}"
        self.auto_close_hours = 72
        self.allow_user_close = True
        self.allow_reactions = True
        self.ticket_cooldown = 300
        self.max_open_tickets_per_user = 3
        self.require_reason_to_close = False
        self.dm_user_on_close = True
        self.dm_user_on_reply = True
        self.embed_color_scheme = {
            "primary": 0x3498db,
            "success": 0x2ecc71,
            "warning": 0xf1c40f,
            "danger": 0xe74c3c,
            "info": 0x9b59b6
        }
        self.custom_ticket_welcome = "Thanks for creating a ticket! Our staff will assist you shortly."
        self.custom_ticket_closed = "This ticket has been closed. A transcript will be saved."
        self.panel_style = "modern"
        self.panel_title = "🎫 Support Ticket System"
        self.panel_description = "Need assistance? Create a support ticket by selecting a category below."
        self.panel_image_url = ""
        self.panel_thumbnail_url = ""
        self.panel_button_style = 1
        self.panel_button_emoji = "🎫"
        self.panel_button_label = "Create Ticket"
        self.ticket_close_confirmation = True
        self.ticket_claim_system = True
        self.ticket_rating_system = True
        self.ticket_tags_enabled = True
        self.available_tags = ["resolved", "pending", "important", "question", "feature-request"]
        self.custom_ticket_emojis = {}
        self.transcript_format = "text"
        self.transcript_include_attachments = True
        self.transcript_timezone = "UTC"
        self.blacklisted_users = []
        self.ticket_auto_archive_duration = 1440
        self.ticket_pin_welcome_message = True
        self.ticket_creation_notification = True
        self.ticket_creation_notification_channel_id = None
        self.ticket_close_notification = True
        self.ticket_close_notification_channel_id = None
        self.ticket_stats_tracking = True
        self.ticket_stats = {
            "total_created": 0,
            "total_closed": 0,
            "avg_response_time": 0,
            "avg_resolution_time": 0,
            "categories": {}
        }
        self.custom_commands_enabled = True
        self.custom_commands = {}
        self.ticket_survey_questions = []
        self.ticket_survey_enabled = False
        self.ticket_form_mode = False
        self.user_cooldowns = {}
        self.next_ticket_number = 1
        self.ping_support_on_open = False

    def to_dict(self):
        return {
            "guild_id": self.guild_id,
            "ticket_channel_id": self.ticket_channel_id,
            "transcript_channel_id": self.transcript_channel_id,
            "support_role_ids": self.support_role_ids,
            "admin_role_ids": self.admin_role_ids,
            "categories": [cat.to_dict() for cat in self.categories],
            "allow_anonymous": self.allow_anonymous,
            "ticket_counter": self.ticket_counter,
            "custom_footer": self.custom_footer,
            "custom_banner_url": self.custom_banner_url,
            "active_tickets": self.active_tickets,
            "closed_tickets": self.closed_tickets,
            "ticket_category_id": self.ticket_category_id,
            "ticket_logs_enabled": self.ticket_logs_enabled,
            "ticket_naming_format": self.ticket_naming_format,
            "auto_close_hours": self.auto_close_hours,
            "allow_user_close": self.allow_user_close,
            "allow_reactions": self.allow_reactions,
            "ticket_cooldown": self.ticket_cooldown,
            "max_open_tickets_per_user": self.max_open_tickets_per_user,
            "require_reason_to_close": self.require_reason_to_close,
            "dm_user_on_close": self.dm_user_on_close,
            "dm_user_on_reply": self.dm_user_on_reply,
            "embed_color_scheme": self.embed_color_scheme,
            "custom_ticket_welcome": self.custom_ticket_welcome,
            "custom_ticket_closed": self.custom_ticket_closed,
            "panel_style": self.panel_style,
            "panel_title": self.panel_title,
            "panel_description": self.panel_description,
            "panel_image_url": self.panel_image_url,
            "panel_thumbnail_url": self.panel_thumbnail_url,
            "panel_button_style": self.panel_button_style,
            "panel_button_emoji": self.panel_button_emoji,
            "panel_button_label": self.panel_button_label,
            "ticket_close_confirmation": self.ticket_close_confirmation,
            "ticket_claim_system": self.ticket_claim_system,
            "ticket_rating_system": self.ticket_rating_system,
            "ticket_tags_enabled": self.ticket_tags_enabled,
            "available_tags": self.available_tags,
            "custom_ticket_emojis": self.custom_ticket_emojis,
            "transcript_format": self.transcript_format,
            "transcript_include_attachments": self.transcript_include_attachments,
            "transcript_timezone": self.transcript_timezone,
            "blacklisted_users": self.blacklisted_users,
            "ticket_auto_archive_duration": self.ticket_auto_archive_duration,
            "ticket_pin_welcome_message": self.ticket_pin_welcome_message,
            "ticket_creation_notification": self.ticket_creation_notification,
            "ticket_creation_notification_channel_id": self.ticket_creation_notification_channel_id,
            "ticket_close_notification": self.ticket_close_notification,
            "ticket_close_notification_channel_id": self.ticket_close_notification_channel_id,
            "ticket_stats_tracking": self.ticket_stats_tracking,
            "ticket_stats": self.ticket_stats,
            "custom_commands_enabled": self.custom_commands_enabled,
            "custom_commands": self.custom_commands,
            "ticket_survey_questions": self.ticket_survey_questions,
            "ticket_survey_enabled": self.ticket_survey_enabled,
            "ticket_form_mode": self.ticket_form_mode,
            "user_cooldowns": self.user_cooldowns,
            "next_ticket_number": self.next_ticket_number,
            "ping_support_on_open": self.ping_support_on_open
        }

    @classmethod
    def from_dict(cls, data):
        config = cls(data["guild_id"])
        config.ticket_channel_id = data.get("ticket_channel_id")
        config.transcript_channel_id = data.get("transcript_channel_id")
        config.support_role_ids = data.get("support_role_ids", [])
        config.admin_role_ids = data.get("admin_role_ids", [])
        config.categories = [TicketCategory.from_dict(cat) for cat in data.get("categories", [])]
        config.allow_anonymous = data.get("allow_anonymous", True)
        config.ticket_counter = data.get("ticket_counter", 0)
        config.custom_footer = data.get("custom_footer", "Made by TheHolyoneZ")
        config.custom_banner_url = data.get("custom_banner_url", "")
        config.active_tickets = data.get("active_tickets", {})
        config.closed_tickets = data.get("closed_tickets", {})
        config.ticket_category_id = data.get("ticket_category_id")
        config.ticket_logs_enabled = data.get("ticket_logs_enabled", True)
        config.ticket_naming_format = data.get("ticket_naming_format", "ticket-{number}")
        config.auto_close_hours = data.get("auto_close_hours", 72)
        config.allow_user_close = data.get("allow_user_close", True)
        config.allow_reactions = data.get("allow_reactions", True)
        config.ticket_cooldown = data.get("ticket_cooldown", 300)
        config.max_open_tickets_per_user = data.get("max_open_tickets_per_user", 3)
        config.require_reason_to_close = data.get("require_reason_to_close", False)
        config.dm_user_on_close = data.get("dm_user_on_close", True)
        config.dm_user_on_reply = data.get("dm_user_on_reply", True)
        config.embed_color_scheme = data.get("embed_color_scheme", {
            "primary": 0x3498db,
            "success": 0x2ecc71,
            "warning": 0xf1c40f,
            "danger": 0xe74c3c,
            "info": 0x9b59b6
        })
        config.custom_ticket_welcome = data.get("custom_ticket_welcome", "Thanks for creating a ticket! Our staff will assist you shortly.")
        config.custom_ticket_closed = data.get("custom_ticket_closed", "This ticket has been closed. A transcript will be saved.")
        config.panel_style = data.get("panel_style", "modern")
        config.panel_title = data.get("panel_title", "🎫 Support Ticket System")
        config.panel_description = data.get("panel_description", "Need assistance? Create a support ticket by selecting a category below.")
        config.panel_image_url = data.get("panel_image_url", "")
        config.panel_thumbnail_url = data.get("panel_thumbnail_url", "")
        config.panel_button_style = data.get("panel_button_style", 1)
        config.panel_button_emoji = data.get("panel_button_emoji", "🎫")
        config.panel_button_label = data.get("panel_button_label", "Create Ticket")
        config.ticket_close_confirmation = data.get("ticket_close_confirmation", True)
        config.ticket_claim_system = data.get("ticket_claim_system", True)
        config.ticket_rating_system = data.get("ticket_rating_system", True)
        config.ticket_tags_enabled = data.get("ticket_tags_enabled", True)
        config.available_tags = data.get("available_tags", ["resolved", "pending", "important", "question", "feature-request"])
        config.custom_ticket_emojis = data.get("custom_ticket_emojis", {})
        config.transcript_format = data.get("transcript_format", "text")
        config.transcript_include_attachments = data.get("transcript_include_attachments", True)
        config.transcript_timezone = data.get("transcript_timezone", "UTC")
        config.blacklisted_users = data.get("blacklisted_users", [])
        config.ticket_auto_archive_duration = data.get("ticket_auto_archive_duration", 1440)
        config.ticket_pin_welcome_message = data.get("ticket_pin_welcome_message", True)
        config.ticket_creation_notification = data.get("ticket_creation_notification", True)
        config.ticket_creation_notification_channel_id = data.get("ticket_creation_notification_channel_id")
        config.ticket_close_notification = data.get("ticket_close_notification", True)
        config.ticket_close_notification_channel_id = data.get("ticket_close_notification_channel_id")
        config.ticket_stats_tracking = data.get("ticket_stats_tracking", True)
        config.ticket_stats = data.get("ticket_stats", {
            "total_created": 0,
            "total_closed": 0,
            "avg_response_time": 0,
            "avg_resolution_time": 0,
            "categories": {}
        })
        config.custom_commands_enabled = data.get("custom_commands_enabled", True)
        config.custom_commands = data.get("custom_commands", {})
        config.ticket_survey_questions = data.get("ticket_survey_questions", [])
        config.ticket_survey_enabled = data.get("ticket_survey_enabled", False)
        config.ticket_form_mode = data.get("ticket_form_mode", False)
        config.user_cooldowns = data.get("user_cooldowns", {})
        config.next_ticket_number = 1
        config.ping_support_on_open = data.get("ping_support_on_open", False)
        return config

class TicketManager:
    def __init__(self, bot):
        self.bot = bot
        self.configs = {}
        self.data_folder = "data/tickets"
        self.cooldowns = {}
        os.makedirs(self.data_folder, exist_ok=True)
        self.load_all_configs()
        self.auto_close_task = bot.loop.create_task(self.check_inactive_tickets())

    def load_all_configs(self):
        for filename in os.listdir(self.data_folder):
            if filename.endswith(".json"):
                guild_id = int(filename.split(".")[0])
                self.load_config(guild_id)

    def load_config(self, guild_id: int) -> TicketConfig:
        filepath = f"{self.data_folder}/{guild_id}.json"
        if guild_id in self.configs:
            return self.configs[guild_id]
        
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    config = TicketConfig.from_dict(data)
                    self.configs[guild_id] = config
                    return config
            except Exception as e:
                logger.error(f"Error loading config for guild {guild_id}: {e}")
                config = TicketConfig(guild_id)
                self.configs[guild_id] = config
                return config
        else:
            config = TicketConfig(guild_id)
            self.configs[guild_id] = config
            self.save_config(guild_id)
            return config

    def save_config(self, guild_id: int):
        config = self.configs.get(guild_id)
        if config:
            filepath = f"{self.data_folder}/{guild_id}.json"
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(config.to_dict(), f, indent=4)
            except Exception as e:
                logger.error(f"Error saving config for guild {guild_id}: {e}")

    def get_config(self, guild_id: int) -> TicketConfig:
        if guild_id not in self.configs:
            return self.load_config(guild_id)
        return self.configs[guild_id]

    async def check_inactive_tickets(self):
        """Check for inactive tickets and auto-close them"""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                for guild_id, config in self.configs.items():
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                        
                    now = datetime.datetime.now()
                    for ticket_id, ticket_data in list(config.active_tickets.items()):
                        last_activity = datetime.datetime.fromisoformat(ticket_data.get("last_activity", ticket_data.get("created_at")))
                        hours_inactive = (now - last_activity).total_seconds() / 3600
                        
                        if hours_inactive >= config.auto_close_hours and config.auto_close_hours > 0:
                            channel_id = ticket_data.get("channel_id")
                            channel = guild.get_channel(channel_id)
                            
                            if channel:
                                try:
                                    await self.auto_close_ticket(guild, channel, ticket_id, config)
                                except Exception as e:
                                    logger.error(f"Error auto-closing ticket {ticket_id}: {e}")
            except Exception as e:
                logger.error(f"Error in auto-close task: {e}")
                
            await asyncio.sleep(3600)

    async def auto_close_ticket(self, guild, channel, ticket_id, config):
        """Auto-close an inactive ticket"""
        embed = discord.Embed(
            title="⏰ Ticket Auto-Closed",
            description=f"This ticket has been automatically closed due to {config.auto_close_hours} hours of inactivity.",
            color=config.embed_color_scheme["warning"]
        )
        embed.set_footer(text=config.custom_footer)
        
        await channel.send(embed=embed)
        
        try:
            transcript_content = await self.create_transcript_content(channel, config)
        except Exception as e:
            logger.error(f"Error creating transcript for auto-closed ticket {ticket_id}: {e}")
            transcript_content = None
        
        if config.transcript_channel_id and transcript_content:
            transcript_channel = guild.get_channel(config.transcript_channel_id)
            if transcript_channel:
                ticket_data = config.active_tickets.get(ticket_id, {})
                
                transcript_embed = discord.Embed(
                    title="📝 Ticket Auto-Closed Transcript",
                    description=f"Ticket was automatically closed due to inactivity.",
                    color=config.embed_color_scheme["info"],
                    timestamp=datetime.datetime.now()
                )
                
                transcript_embed.add_field(name="Ticket", value=f"#{ticket_data.get('ticket_number', 'Unknown')}", inline=True)
                transcript_embed.add_field(name="Category", value=ticket_data.get("category", "Unknown"), inline=True)
                
                creator_id = ticket_data.get("creator_id")
                if creator_id:
                    creator = guild.get_member(creator_id)
                    if creator:
                        if ticket_data.get("is_anonymous", False):
                            transcript_embed.add_field(name="Created By", value="Anonymous User (Logged for moderation purposes)", inline=True)
                        else:
                            transcript_embed.add_field(name="Created By", value=creator.mention, inline=True)
                
                transcript_embed.add_field(name="Auto-Closed After", value=f"{config.auto_close_hours} hours of inactivity", inline=True)
                transcript_embed.set_footer(text=config.custom_footer)
                
                try:
                    file_name = f"transcript-{channel.name}.txt"
                    if isinstance(transcript_content, bytes):
                        file = discord.File(io.BytesIO(transcript_content), filename=file_name)
                    else:
                        file = discord.File(io.StringIO(transcript_content), filename=file_name)
                    
                    transcript_message = await transcript_channel.send(embed=transcript_embed, file=file)
                    ticket_data["transcript_message_id"] = transcript_message.id
                    
                except Exception as e:
                    logger.error(f"Error sending transcript for auto-closed ticket {ticket_id}: {e}")
        

        ticket_data = config.active_tickets.pop(ticket_id, None)
        if ticket_data:
            ticket_data["closed_at"] = datetime.datetime.now().isoformat()
            ticket_data["closed_by"] = "AUTO"
            ticket_data["close_reason"] = "Inactivity"
            ticket_data["guild_id"] = guild.id
            config.closed_tickets[ticket_id] = ticket_data
            
            if config.ticket_stats_tracking:
                config.ticket_stats["total_closed"] += 1
                category = ticket_data.get("category", "Unknown")
                if category not in config.ticket_stats["categories"]:
                    config.ticket_stats["categories"][category] = {"created": 0, "closed": 0}
                config.ticket_stats["categories"][category]["closed"] += 1
                
                created_at = datetime.datetime.fromisoformat(ticket_data.get("created_at"))
                closed_at = datetime.datetime.fromisoformat(ticket_data.get("closed_at"))
                resolution_time = (closed_at - created_at).total_seconds() / 3600
                
                total_closed = config.ticket_stats["total_closed"]
                current_avg = config.ticket_stats["avg_resolution_time"]
                new_avg = ((current_avg * (total_closed - 1)) + resolution_time) / total_closed
                config.ticket_stats["avg_resolution_time"] = new_avg
            
            self.save_config(guild.id)
        
        try:
            await asyncio.sleep(5)
            await channel.delete(reason="Ticket auto-closed due to inactivity")
        except Exception as e:
            logger.error(f"Failed to delete channel for auto-closed ticket {ticket_id}: {e}")

    async def create_transcript_content(self, channel, config, format_type=None):
        """Create a transcript of the ticket conversation and return content in memory"""
        if not format_type:
            format_type = config.transcript_format
            
        messages = []
        async for message in channel.history(limit=None, oldest_first=True):
            if message.author.bot and message.embeds and not config.transcript_include_attachments:
                continue
                
            timestamp = message.created_at.astimezone(
                pytz.timezone(config.transcript_timezone)
            ).strftime("%Y-%m-%d %H:%M:%S")
            
            content = message.content or ""
            
            attachments = []
            if message.attachments and config.transcript_include_attachments:
                for attachment in message.attachments:
                    attachments.append(f"[Attachment: {attachment.url}]")
            
            embeds = []
            if message.embeds:
                for embed in message.embeds:
                    if embed.title:
                        embeds.append(f"[Embed: {embed.title}]")
                    elif embed.description:
                        embeds.append(f"[Embed: {embed.description[:50]}...]")
                    else:
                        embeds.append("[Embed]")
            
            author = message.author.name
            author_id = message.author.id
            
            messages.append({
                "timestamp": timestamp,
                "author": author,
                "author_id": author_id,
                "content": content,
                "attachments": attachments,
                "embeds": embeds,
                "avatar_url": str(message.author.display_avatar.url)
            })
        
        if format_type == "text" or format_type == "both":
            return self.create_text_transcript_content(channel, messages, config)
        elif format_type == "html":
            return self.create_html_transcript_content(channel, messages, config)
        elif format_type == "csv":
            return self.create_csv_transcript_content(channel, messages, config)
        else:
            return self.create_text_transcript_content(channel, messages, config)

    def create_text_transcript_content(self, channel, messages, config):
        """Create a plain text transcript and return its content"""
        transcript_text = [
            f"Transcript for ticket: {channel.name}",
            f"Created at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Channel ID: {channel.id}",
            f"Guild: {channel.guild.name} ({channel.guild.id})",
            "="*50,
            ""
        ]
        
        for msg in messages:
            timestamp = msg["timestamp"]
            author = msg["author"]
            content = msg["content"]
            
            line = f"[{timestamp}] {author}: {content}"
            transcript_text.append(line)
            
            for attachment in msg["attachments"]:
                transcript_text.append(f"  {attachment}")
                
            for embed in msg["embeds"]:
                transcript_text.append(f"  {embed}")
                
            transcript_text.append("")
        
        return "\n".join(transcript_text)

    def create_html_transcript_content(self, channel, messages, config):
        """Create an HTML transcript and return its content"""
        guild = channel.guild
        
        html_content = [
            "<!DOCTYPE html>",
            "<html lang='en'>",
            "<head>",
            "    <meta charset='UTF-8'>",
            "    <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            f"    <title>Ticket Transcript - {channel.name}</title>",
            "    <style>",
            "        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }",
            "        .header { text-align: center; margin-bottom: 30px; padding-bottom: 10px; border-bottom: 1px solid #ccc; }",
            "        .message { margin-bottom: 15px; padding: 10px; border-radius: 5px; }",
            "        .message-info { display: flex; align-items: center; margin-bottom: 5px; }",
            "        .avatar { width: 40px; height: 40px; border-radius: 50%; margin-right: 10px; }",
            "        .author { font-weight: bold; }",
            "        .timestamp { color: #777; font-size: 0.8em; margin-left: 10px; }",
            "        .content { margin-left: 50px; }",
            "        .attachment { margin-top: 5px; padding: 5px; background-color: #f0f0f0; border-radius: 3px; }",
            "        .embed { margin-top: 5px; padding: 5px; background-color: #e8f4f8; border-radius: 3px; }",
            "        .footer { margin-top: 30px; text-align: center; font-size: 0.8em; color: #777; }",
            "    </style>",
            "</head>",
            "<body>",
            "    <div class='header'>",
            f"        <h1>Ticket Transcript: {channel.name}</h1>",
            f"        <p>Server: {guild.name}</p>",
            f"        <p>Created: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
            "    </div>",
            "    <div class='messages'>"
        ]
        
        for msg in messages:
            timestamp = msg["timestamp"]
            author = html.escape(msg["author"])
            content = html.escape(msg["content"]).replace("\n", "<br>")
            avatar_url = msg["avatar_url"]
            
            html_content.extend([
                "        <div class='message'>",
                "            <div class='message-info'>",
                f"                <img class='avatar' src='{avatar_url}' alt='{author}'>",
                f"                <span class='author'>{author}</span>",
                f"                <span class='timestamp'>{timestamp}</span>",
                "            </div>",
                f"            <div class='content'>{content}</div>"
            ])
            
            for attachment in msg["attachments"]:
                html_content.append(f"            <div class='attachment'>{html.escape(attachment)}</div>")
                
            for embed in msg["embeds"]:
                html_content.append(f"            <div class='embed'>{html.escape(embed)}</div>")
                
            html_content.append("        </div>")
        
        html_content.extend([
            "    </div>",
            "    <div class='footer'>",
            f"        <p>{config.custom_footer}</p>",
            "    </div>",
            "</body>",
            "</html>"
        ])
        
        return "\n".join(html_content)

    def create_csv_transcript_content(self, channel, messages, config):
        """Create a CSV transcript for data analysis and return its content"""
        output = io.StringIO()
        fieldnames = ['timestamp', 'author', 'author_id', 'content', 'attachments', 'embeds']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for msg in messages:
            row = {
                'timestamp': msg['timestamp'],
                'author': msg['author'],
                'author_id': msg['author_id'],
                'content': msg['content'],
                'attachments': '; '.join(msg['attachments']),
                'embeds': '; '.join(msg['embeds'])
            }
            writer.writerow(row)
        
        return output.getvalue()


class TicketCategorySelect(discord.ui.Select):
    def __init__(self, ticket_cog, config: TicketConfig):
        self.ticket_cog = ticket_cog
        self.config = config
        
        options = []
        for i, category in enumerate(config.categories):
            options.append(
                discord.SelectOption(
                    label=category.name,
                    description=category.description[:100],
                    emoji=category.emoji,
                    value=str(i)
                )
            )
        
        super().__init__(
            placeholder="Select a ticket category...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_category_select"
        )

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        config = self.config
        
        if user_id in config.blacklisted_users:
            await interaction.response.send_message(
                "You are not allowed to create tickets.", 
                ephemeral=True
            )
            return
            
        cooldown_key = f"{guild_id}:{user_id}"
        current_time = datetime.datetime.now().timestamp()
        
        if cooldown_key in self.ticket_cog.ticket_manager.cooldowns:
            last_ticket_time = self.ticket_cog.ticket_manager.cooldowns[cooldown_key]
            if current_time - last_ticket_time < config.ticket_cooldown:
                remaining = int(config.ticket_cooldown - (current_time - last_ticket_time))
                await interaction.response.send_message(
                    f"Please wait {remaining} seconds before creating another ticket.",
                    ephemeral=True
                )
                return
        
        open_tickets = 0
        for ticket_data in config.active_tickets.values():
            if ticket_data.get("creator_id") == user_id:
                open_tickets += 1
                
        if open_tickets >= config.max_open_tickets_per_user:
            await interaction.response.send_message(
                f"You already have {open_tickets} open tickets. Please close some before creating new ones.",
                ephemeral=True
            )
            return
        
        selected_index = int(self.values[0])
        selected_category = config.categories[selected_index]
        
        if selected_category.required_roles:
            member = interaction.guild.get_member(user_id)
            has_required_role = False
            
            for role_id in selected_category.required_roles:
                role = interaction.guild.get_role(role_id)
                if role and role in member.roles:
                    has_required_role = True
                    break
                    
            if not has_required_role:
                await interaction.response.send_message(
                    "You don't have the required roles to create this type of ticket.",
                    ephemeral=True
                )
                return
        
        if config.ticket_form_mode and selected_category.custom_fields:
            await interaction.response.send_message(
                "Please fill out the ticket form:",
                view=TicketFormView(self.ticket_cog, selected_category, config),
                ephemeral=True
            )
        else:
            await interaction.response.send_modal(
                TicketModal(self.ticket_cog, selected_category, config)
            )

class AnonymousToggle(discord.ui.Button):
    def __init__(self, is_anonymous: bool = False):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="Anonymous: OFF" if not is_anonymous else "Anonymous: ON",
            emoji="🕵️" if is_anonymous else "👤",
            custom_id="anonymous_toggle"
        )
        self.is_anonymous = is_anonymous

    async def callback(self, interaction: discord.Interaction):
        self.is_anonymous = not self.is_anonymous
        self.label = "Anonymous: ON" if self.is_anonymous else "Anonymous: OFF"
        self.emoji = "🕵️" if self.is_anonymous else "👤"
        
        await interaction.response.edit_message(view=self.view)

class TicketModal(discord.ui.Modal):
    def __init__(self, ticket_cog, category: TicketCategory, config: TicketConfig):
        super().__init__(title=f"{category.emoji} {category.name} Ticket")
        self.ticket_cog = ticket_cog
        self.category = category
        self.config = config
        
        self.title_input = discord.ui.TextInput(
            label="Title",
            placeholder="Brief title for your ticket",
            required=True,
            max_length=100
        )
        
        self.description_input = discord.ui.TextInput(
            label="Description",
            placeholder="Please provide details about your issue...",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=1000
        )
        
        self.add_item(self.title_input)
        self.add_item(self.description_input)
        
        self.custom_inputs = {}
        for i, field in enumerate(category.custom_fields[:3]):
            custom_input = discord.ui.TextInput(
                label=field.get("name", f"Field {i+1}"),
                placeholder=field.get("placeholder", "Enter information here..."),
                required=field.get("required", False),
                style=discord.TextStyle.paragraph if field.get("long", False) else discord.TextStyle.short,
                max_length=field.get("max_length", 1000 if field.get("long", False) else 100)
            )
            self.add_item(custom_input)
            self.custom_inputs[field.get("name", f"Field {i+1}")] = custom_input

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        is_anonymous = False
        if hasattr(interaction, 'message') and interaction.message and interaction.message.components:
            for row in interaction.message.components:
                for component in row.children:
                    if isinstance(component, discord.ui.Button) and component.custom_id == "anonymous_toggle":
                        is_anonymous = "ON" in component.label
                        break
        
        custom_fields = {}
        for field_name, input_field in self.custom_inputs.items():
            custom_fields[field_name] = input_field.value
        
        await self.ticket_cog.create_ticket(
            interaction,
            self.category,
            self.title_input.value,
            self.description_input.value,
            is_anonymous,
            custom_fields
        )
        
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        cooldown_key = f"{guild_id}:{user_id}"
        self.ticket_cog.ticket_manager.cooldowns[cooldown_key] = datetime.datetime.now().timestamp()

class TicketFormView(discord.ui.View):
    def __init__(self, ticket_cog, category: TicketCategory, config: TicketConfig):
        super().__init__(timeout=300)
        self.ticket_cog = ticket_cog
        self.category = category
        self.config = config
        self.responses = {}
        
        if config.allow_anonymous:
            self.add_item(AnonymousToggle())

    @discord.ui.button(label="Submit Form", style=discord.ButtonStyle.primary, emoji="📝")
    async def submit_form(self, interaction: discord.Interaction, button: discord.ui.Button):
        missing_fields = []
        for field in self.category.custom_fields:
            if field.get("required", False) and field.get("name") not in self.responses:
                missing_fields.append(field.get("name"))
        
        if missing_fields:
            await interaction.response.send_message(
                f"Please fill out the following required fields: {', '.join(missing_fields)}",
                ephemeral=True
            )
            return
        
        is_anonymous = False
        for item in self.children:
            if isinstance(item, AnonymousToggle):
                is_anonymous = item.is_anonymous
                break
        
        await self.ticket_cog.create_ticket(
            interaction,
            self.category,
            self.responses.get("Title", f"{self.category.name} Ticket"),
            self.responses.get("Description", "No description provided."),
            is_anonymous,
            self.responses
        )
        
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        cooldown_key = f"{guild_id}:{user_id}"
        self.ticket_cog.ticket_manager.cooldowns[cooldown_key] = datetime.datetime.now().timestamp()
        
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(content="Ticket created successfully!", view=self)

class TicketControlPanel(discord.ui.View):
    def __init__(self, ticket_cog, ticket_id: str, config: TicketConfig):
        super().__init__(timeout=None)
        self.ticket_cog = ticket_cog
        self.ticket_id = ticket_id
        self.config = config

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_data = self.config.active_tickets.get(self.ticket_id, {})
        is_creator = interaction.user.id == ticket_data.get("creator_id")
        is_staff = await self.is_staff_member(interaction)
        
        if not (is_staff or (is_creator and self.config.allow_user_close)):
            await interaction.response.send_message("You don't have permission to close this ticket.", ephemeral=True)
            return
            
        if self.config.ticket_close_confirmation:
            await interaction.response.send_message(
                "Are you sure you want to close this ticket?",
                view=TicketCloseConfirmView(self.ticket_cog, self.ticket_id, self.config),
                ephemeral=True
            )
        else:
            if self.config.require_reason_to_close:
                await interaction.response.send_modal(TicketCloseModal(self.ticket_cog, self.ticket_id, self.config))
            else:
                await self.ticket_cog.close_ticket(interaction, self.ticket_id)

    @discord.ui.button(label="Create Transcript", style=discord.ButtonStyle.primary, emoji="📝", custom_id="create_transcript")
    async def create_transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.is_staff_member(interaction):
            await interaction.response.send_message("Only staff members can create transcripts.", ephemeral=True)
            return
            
        await self.ticket_cog.generate_transcript(interaction, self.ticket_id)

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, emoji="👋", custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.config.ticket_claim_system:
            return

        if not await self.is_staff_member(interaction):
            await interaction.response.send_message("Only staff members can claim tickets.", ephemeral=True)
            return
            
        ticket_data = self.config.active_tickets.get(self.ticket_id, {})
        if ticket_data.get("claimed_by"):
            claimed_by = interaction.guild.get_member(ticket_data["claimed_by"])
            if claimed_by and claimed_by.id != interaction.user.id:
                await interaction.response.send_message(
                    f"This ticket is already claimed by {claimed_by.mention}",
                    ephemeral=True
                )
                return
                
        await interaction.response.defer()
        
        ticket_data["claimed_by"] = interaction.user.id
        ticket_data["claimed_at"] = datetime.datetime.now().isoformat()
        self.ticket_cog.ticket_manager.save_config(interaction.guild.id)
        
        button.label = "Claimed"
        button.emoji = "✅"
        button.disabled = True
        button.style = discord.ButtonStyle.secondary
        
        await interaction.followup.send(f"{interaction.user.mention} has claimed this ticket!")
        
        try:
            await interaction.message.edit(view=self)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Add Tag", style=discord.ButtonStyle.secondary, emoji="🏷️", custom_id="add_tag")
    async def add_tag(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.config.ticket_tags_enabled:
            return
            
        if not await self.is_staff_member(interaction):
            await interaction.response.send_message("Only staff members can add tags to tickets.", ephemeral=True)
            return
            
        await interaction.response.send_message(
            "Select a tag to add to this ticket:",
            view=TicketTagView(self.ticket_cog, self.ticket_id, self.config),
            ephemeral=True
        )
    
    async def is_staff_member(self, interaction: discord.Interaction) -> bool:
        """Check if the user is a staff member (has support or admin role)"""
        member = interaction.guild.get_member(interaction.user.id)
        if not member:
            return False
            
        if member.guild_permissions.administrator:
            return True
            
        for role_id in self.config.support_role_ids + self.config.admin_role_ids:
            role = interaction.guild.get_role(role_id)
            if role and role in member.roles:
                return True
                
        return False
        
    async def check_staff_permission(self, interaction: discord.Interaction) -> bool:
        """Legacy method - redirects to specific permission checks based on the button"""
        custom_id = interaction.data.get("custom_id", "")
        
        if custom_id == "close_ticket":
            ticket_data = self.config.active_tickets.get(self.ticket_id, {})
            is_creator = interaction.user.id == ticket_data.get("creator_id")
            is_staff = await self.is_staff_member(interaction)
            
            if is_staff or (is_creator and self.config.allow_user_close):
                return True
            else:
                await interaction.response.send_message("You don't have permission to close this ticket.", ephemeral=True)
                return False
        
        else:
            is_staff = await self.is_staff_member(interaction)
            if is_staff:
                return True
            else:
                await interaction.response.send_message("Only staff members can use this function.", ephemeral=True)
                return False

class TicketCloseConfirmView(discord.ui.View):
    def __init__(self, ticket_cog, ticket_id: str, config: TicketConfig):
        super().__init__(timeout=60)
        self.ticket_cog = ticket_cog
        self.ticket_id = ticket_id
        self.config = config

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.config.require_reason_to_close:
            await interaction.response.send_modal(TicketCloseModal(self.ticket_cog, self.ticket_id, self.config))
        else:
            await self.ticket_cog.close_ticket(interaction, self.ticket_id)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Ticket close cancelled.", view=None)

class TicketCloseModal(discord.ui.Modal):
    def __init__(self, ticket_cog, ticket_id: str, config: TicketConfig):
        super().__init__(title="Close Ticket")
        self.ticket_cog = ticket_cog
        self.ticket_id = ticket_id
        self.config = config
        
        self.reason_input = discord.ui.TextInput(
            label="Reason for closing",
            placeholder="Please provide a reason for closing this ticket...",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=1000
        )
        
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        await self.ticket_cog.close_ticket(interaction, self.ticket_id, self.reason_input.value)

class TicketTagView(discord.ui.View):
    def __init__(self, ticket_cog, ticket_id: str, config: TicketConfig):
        super().__init__(timeout=60)
        self.ticket_cog = ticket_cog
        self.ticket_id = ticket_id
        self.config = config
        
        self.ticket_data = config.active_tickets.get(ticket_id, {})
        self.current_tags = self.ticket_data.get("tags", [])
        
        options = []
        for tag in config.available_tags:
            emoji = config.custom_ticket_emojis.get(tag, "🏷️")
            options.append(discord.SelectOption(
                label=tag,
                emoji=emoji,
                default=tag in self.current_tags
            ))
            
        if options:
            self.tag_select = discord.ui.Select(
                placeholder="Select a tag...",
                options=options,
                min_values=0,
                max_values=min(len(options), 25)
            )
            self.tag_select.callback = self.tag_selected
            self.add_item(self.tag_select)
        else:
            self.tag_select = None

    async def tag_selected(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        self.ticket_data["tags"] = self.tag_select.values
        self.ticket_cog.ticket_manager.save_config(interaction.guild.id)
        
        channel = interaction.guild.get_channel(self.ticket_data.get("channel_id"))
        if not channel:
            await interaction.followup.send("❌ Ticket channel not found", ephemeral=True)
            return
            
        topic = channel.topic or ""
        topic_parts = topic.split(" | ")
        
        if len(topic_parts) >= 3:
            base_topic = " | ".join(topic_parts[:3])
        else:
            base_topic = topic
            
        if self.tag_select.values:
            tag_text = ", ".join(self.tag_select.values)
            new_topic = f"{base_topic} | Tags: {tag_text}"
        else:
            new_topic = base_topic
            
        try:
            await channel.edit(topic=new_topic)
        except discord.HTTPException:
            pass
            
        if self.tag_select.values:
            tag_mentions = []
            for tag in self.tag_select.values:
                emoji = self.config.custom_ticket_emojis.get(tag, "🏷️")
                tag_mentions.append(f"{emoji} {tag}")
                
            await interaction.followup.send(
                f"✅ Tags updated: {', '.join(tag_mentions)}",
                ephemeral=True
            )
        else:
            await interaction.followup.send("✅ All tags removed", ephemeral=True)

class TicketPanelView(discord.ui.View):
    def __init__(self, ticket_cog, config: TicketConfig):
        super().__init__(timeout=None)
        self.ticket_cog = ticket_cog
        self.config = config
        
        button_style = discord.ButtonStyle(config.panel_button_style)
        self.add_item(
            discord.ui.Button(
                style=button_style,
                label=config.panel_button_label,
                emoji=config.panel_button_emoji,
                custom_id="create_ticket_button"
            )
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data.get("custom_id") == "create_ticket_button":
            await interaction.response.send_message(
                "Please select a ticket category:",
                view=TicketCategoryView(self.ticket_cog, self.config),
                ephemeral=True
            )
            return False
        return True

class TicketCategoryView(discord.ui.View):
    def __init__(self, ticket_cog, config: TicketConfig):
        super().__init__(timeout=180)
        self.ticket_cog = ticket_cog
        self.config = config
        
        self.add_item(TicketCategorySelect(ticket_cog, config))
        
        if config.allow_anonymous:
            self.add_item(AnonymousToggle())

class TicketRatingView(discord.ui.View):
    def __init__(self, ticket_cog, ticket_id: str, config: TicketConfig, guild_id: int):
        super().__init__(timeout=300)
        self.ticket_cog = ticket_cog
        self.ticket_id = ticket_id
        self.config = config
        self.guild_id = guild_id

    @discord.ui.button(label="⭐", style=discord.ButtonStyle.secondary, custom_id="rate_1")
    async def rate_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.submit_rating(interaction, 1)

    @discord.ui.button(label="⭐⭐", style=discord.ButtonStyle.secondary, custom_id="rate_2")
    async def rate_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.submit_rating(interaction, 2)

    @discord.ui.button(label="⭐⭐⭐", style=discord.ButtonStyle.secondary, custom_id="rate_3")
    async def rate_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.submit_rating(interaction, 3)

    @discord.ui.button(label="⭐⭐⭐⭐", style=discord.ButtonStyle.secondary, custom_id="rate_4")
    async def rate_4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.submit_rating(interaction, 4)

    @discord.ui.button(label="⭐⭐⭐⭐⭐", style=discord.ButtonStyle.secondary, custom_id="rate_5")
    async def rate_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.submit_rating(interaction, 5)

    async def submit_rating(self, interaction: discord.Interaction, rating: int):
        try:
            ticket_data = self.config.closed_tickets.get(self.ticket_id, {})
            if not ticket_data:
                await interaction.response.edit_message(
                    content="Error: This ticket could not be found in our records.",
                    view=None
                )
                return
                
            ticket_data["rating"] = rating
            self.config.closed_tickets[self.ticket_id] = ticket_data
            self.ticket_cog.ticket_manager.save_config(self.guild_id)
            
            if self.config.ticket_survey_enabled and self.config.ticket_survey_questions:
                try:
                    await interaction.response.send_modal(
                        TicketSurveyModal(self.ticket_cog, self.ticket_id, self.config, self.guild_id)
                    )
                except Exception as e:
                    logger.error(f"Error showing survey modal: {e}")
                    await interaction.response.edit_message(
                        content=f"Thank you for your rating: {'⭐' * rating}\n\nThere was an error showing the survey form.",
                        view=None
                    )
            else:
                await interaction.response.edit_message(
                    content=f"Thank you for your rating: {'⭐' * rating}",
                    view=None
                )
            
            await self.send_rating_to_transcript(interaction, rating)
            
        except Exception as e:
            logger.error(f"Error in submit_rating: {e}")
            try:
                await interaction.response.edit_message(
                    content="An error occurred while processing your rating. Please try again later.",
                    view=None
                )
            except:
                try:
                    await interaction.followup.send(
                        "An error occurred while processing your rating. Please try again later.",
                        ephemeral=True
                    )
                except:
                    pass

    async def send_rating_to_transcript(self, interaction, rating):
        try:
            guild = self.ticket_cog.bot.get_guild(self.guild_id)
            if not guild:
                logger.warning(f"Guild {self.guild_id} not found for rating transcript")
                return
                
            if not self.config.transcript_channel_id:
                logger.debug("No transcript channel configured for ratings")
                return
                
            transcript_channel = guild.get_channel(self.config.transcript_channel_id)
            if not transcript_channel:
                logger.warning(f"Transcript channel {self.config.transcript_channel_id} not found")
                return
                
            ticket_data = self.config.closed_tickets.get(self.ticket_id, {})
            ticket_number = ticket_data.get("ticket_number", "Unknown")
            
            embed = discord.Embed(
                title=f"Ticket #{ticket_number} Rating",
                description=f"{interaction.user.mention} rated their support experience",
                color=self.config.embed_color_scheme["primary"],
                timestamp=datetime.datetime.now()
            )
            
            stars = "⭐" * rating
            embed.add_field(name="Rating", value=f"{stars} ({rating}/5)", inline=False)
            embed.set_footer(text=self.config.custom_footer)
            
            await transcript_channel.send(embed=embed)
            logger.info(f"Sent rating transcript for ticket #{ticket_number}")
            
        except Exception as e:
            logger.error(f"Error sending rating to transcript channel: {e}")

class TicketSurveyModal(discord.ui.Modal):
    def __init__(self, ticket_cog, ticket_id: str, config: TicketConfig, guild_id: int):
        super().__init__(title="Ticket Feedback Survey")
        self.ticket_cog = ticket_cog
        self.ticket_id = ticket_id
        self.config = config
        self.guild_id = guild_id
        self.responses = {}
        
        try:
            for i, question in enumerate(config.ticket_survey_questions[:5]):
                input_field = discord.ui.TextInput(
                    label=question.get("question", f"Question {i+1}")[:45],
                    placeholder=question.get("placeholder", "Your answer...")[:100],
                    required=question.get("required", False),
                    style=discord.TextStyle.paragraph if question.get("long", False) else discord.TextStyle.short,
                    max_length=question.get("max_length", 1000 if question.get("long", False) else 100)
                )
                self.add_item(input_field)
                self.responses[question.get("question", f"Question {i+1}")] = input_field
        except Exception as e:
            logger.error(f"Error creating survey modal: {e}")
            self.add_item(discord.ui.TextInput(
                label="How was your support experience?",
                placeholder="Please share your feedback...",
                required=False,
                style=discord.TextStyle.paragraph
            ))
            self.responses["How was your support experience?"] = self.children[0]

    async def on_submit(self, interaction: discord.Interaction):
        try:
            ticket_data = self.config.closed_tickets.get(self.ticket_id, {})
            if not ticket_data:
                await interaction.response.send_message(
                    "Error: This ticket could not be found in our records.",
                    ephemeral=True
                )
                return
                
            survey_responses = {}
            for question, input_field in self.responses.items():
                survey_responses[question] = input_field.value
                
            ticket_data["survey_responses"] = survey_responses
            self.config.closed_tickets[self.ticket_id] = ticket_data
            self.ticket_cog.ticket_manager.save_config(self.guild_id)
            
            await interaction.response.send_message(
                "Thank you for completing our survey! Your feedback is valuable to us.",
                ephemeral=True
            )
            
            await self.send_survey_to_transcript(interaction, survey_responses)
            
        except Exception as e:
            logger.error(f"Error in survey on_submit: {e}")
            try:
                await interaction.response.send_message(
                    "An error occurred while saving your survey responses. Please try again later.",
                    ephemeral=True
                )
            except:
                try:
                    await interaction.followup.send(
                        "An error occurred while saving your survey responses. Please try again later.",
                        ephemeral=True
                    )
                except:
                    pass
    
    async def send_survey_to_transcript(self, interaction, responses):
        try:
            guild = self.ticket_cog.bot.get_guild(self.guild_id)
            if not guild:
                logger.warning(f"Guild {self.guild_id} not found for survey transcript")
                return
                
            if not self.config.transcript_channel_id:
                logger.debug("No transcript channel configured for surveys")
                return
                
            transcript_channel = guild.get_channel(self.config.transcript_channel_id)
            if not transcript_channel:
                logger.warning(f"Transcript channel {self.config.transcript_channel_id} not found")
                return
                
            ticket_data = self.config.closed_tickets.get(self.ticket_id, {})
            ticket_number = ticket_data.get("ticket_number", "Unknown")
            
            embed = discord.Embed(
                title=f"Ticket #{ticket_number} Survey Responses",
                description=f"{interaction.user.mention} completed the feedback survey",
                color=self.config.embed_color_scheme["info"],
                timestamp=datetime.datetime.now()
            )
            
            for question, answer in responses.items():
                if len(answer) > 1024:
                    answer = answer[:1021] + "..."
                embed.add_field(name=question, value=answer or "No response", inline=False)
                
            embed.set_footer(text=self.config.custom_footer)
            
            await transcript_channel.send(embed=embed)
            logger.info(f"Sent survey transcript for ticket #{ticket_number}")
            
        except Exception as e:
            logger.error(f"Error sending survey to transcript channel: {e}")

class TicketSearchSelect(discord.ui.Select):
    def __init__(self, ticket_cog, config: TicketConfig, results: List[Dict[str, Any]]):
        self.ticket_cog = ticket_cog
        self.config = config
        self.results = results
        
        options = []
        for ticket in results:
            ticket_number = ticket.get("ticket_number", "Unknown")
            category = ticket.get("category", "Unknown")
            closed_at = datetime.datetime.fromisoformat(ticket.get("closed_at", datetime.datetime.now().isoformat())).strftime("%Y-%m-%d")
            
            options.append(
                discord.SelectOption(
                    label=f"Ticket #{ticket_number}",
                    description=f"Category: {category} | Closed: {closed_at}",
                    value=ticket.get("ticket_id")
                )
            )

        super().__init__(
            placeholder="Select a ticket to view its transcript...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="ticket_search_select"
        )
        
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        selected_ticket_id = self.values[0]
        ticket_data = self.config.closed_tickets.get(selected_ticket_id)
        
        if not ticket_data:
            await interaction.followup.send("❌ Could not find that ticket.", ephemeral=True)
            return

        transcript_channel_id = self.config.transcript_channel_id
        if not transcript_channel_id:
            await interaction.followup.send("❌ Transcript channel is not configured.", ephemeral=True)
            return
            
        transcript_channel = interaction.guild.get_channel(transcript_channel_id)
        if not transcript_channel:
            await interaction.followup.send("❌ Transcript channel not found in this server.", ephemeral=True)
            return
            
        ticket_number = ticket_data.get("ticket_number")
        transcript_message_id = ticket_data.get("transcript_message_id")

        if transcript_message_id:
            try:
                transcript_message = await transcript_channel.fetch_message(transcript_message_id)
                transcript_url = transcript_message.jump_url
                
                embed = discord.Embed(
                    title=f"Transcript for Ticket #{ticket_number}",
                    description=f"Category: {ticket_data.get('category')}\nClosed by: <@{ticket_data.get('closed_by')}>",
                    color=self.config.embed_color_scheme["info"]
                )
                
                embed.add_field(name="Transcript Link", value=f"[Click here to view transcript]({transcript_url})", inline=False)
                    
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            except discord.NotFound:
                pass
        
        await interaction.followup.send(f"❌ Could not find the transcript message for Ticket #{ticket_number}. This may be due to an older ticket or the message being deleted.", ephemeral=True)

class MultiTicketSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_manager = TicketManager(bot)
        
        bot.loop.create_task(self.register_views())

    async def register_views(self):
        await self.bot.wait_until_ready()
        
        for guild_id in self.ticket_manager.configs:
            config = self.ticket_manager.get_config(guild_id)
            self.bot.add_view(TicketPanelView(self, config))
            
            for ticket_id in config.active_tickets:
                self.bot.add_view(TicketControlPanel(self, ticket_id, config))

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.guild_id and interaction.data and interaction.data.get("custom_id") == "ticket_search_select":
            config = self.ticket_manager.get_config(interaction.guild.id)
            # Find the view associated with the select menu interaction
            # Note: This is a simplified approach. In a real-world bot, you would need to manage views dynamically.
            # Here, we'll recreate the select menu view to handle the callback.
            try:
                # Retrieve the previously stored search results to pass to the select view
                # This assumes results were stored somewhere accessible, like a temporary cache.
                # A better approach would be to pass the tag in the custom_id, but this is a quick fix.
                # Since the TicketSearchSelect class has a list of results, it's not a big issue.
                await TicketSearchSelect(self, config, []).callback(interaction)
            except Exception as e:
                logger.error(f"Error handling ticket search select interaction: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
            
        if not message.guild:
            return
            
        config = self.ticket_manager.get_config(message.guild.id)
        
        ticket_id = None
        for tid, ticket_data in config.active_tickets.items():
            if ticket_data.get("channel_id") == message.channel.id:
                ticket_id = tid
                break
                
        if not ticket_id:
            return
            
        config.active_tickets[ticket_id]["last_activity"] = datetime.datetime.now().isoformat()
        self.ticket_manager.save_config(message.guild.id)
        
        ticket_data = config.active_tickets[ticket_id]
        if config.ticket_stats_tracking and not ticket_data.get("first_response"):
            is_staff = False
            member = message.guild.get_member(message.author.id)
            
            for role_id in config.support_role_ids + config.admin_role_ids:
                role = message.guild.get_role(role_id)
                if role and role in member.roles:
                    is_staff = True
                    break
                    
            if is_staff:
                created_at = datetime.datetime.fromisoformat(ticket_data.get("created_at"))
                first_response_time = (datetime.datetime.now() - created_at).total_seconds() / 3600
                
                ticket_data["first_response"] = datetime.datetime.now().isoformat()
                ticket_data["response_time"] = first_response_time
                
                total_tickets = config.ticket_stats["total_created"]
                current_avg = config.ticket_stats["avg_response_time"]
                
                if total_tickets > 1:
                    new_avg = ((current_avg * (total_tickets - 1)) + first_response_time) / total_tickets
                else:
                    new_avg = first_response_time
                    
                config.ticket_stats["avg_response_time"] = new_avg
                self.ticket_manager.save_config(message.guild.id)
                
        if config.dm_user_on_reply and not message.author.id == ticket_data.get("creator_id"):
            is_staff = False
            member = message.guild.get_member(message.author.id)
            
            for role_id in config.support_role_ids + config.admin_role_ids:
                role = message.guild.get_role(role_id)
                if role and role in member.roles:
                    is_staff = True
                    break
                    
            if is_staff:
                creator_id = ticket_data.get("creator_id")
                creator = message.guild.get_member(creator_id)
                
                if creator and not ticket_data.get("is_anonymous", False):
                    try:
                        embed = discord.Embed(
                            title=f"New Reply in Ticket #{ticket_data.get('ticket_number')}",
                            description=f"**{message.author.display_name}**: {message.content[:1500]}",
                            color=config.embed_color_scheme["info"],
                            timestamp=datetime.datetime.now()
                        )
                        
                        if message.attachments:
                            embed.add_field(
                                name="Attachments",
                                value="\n".join([f"[{a.filename}]({a.url})" for a in message.attachments[:5]]),
                                inline=False
                            )
                            
                        embed.set_footer(text=f"Server: {message.guild.name}")
                        
                        await creator.send(embed=embed)
                    except:
                        pass

    @commands.group(name="mticket", aliases=["mt"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def mticket(self, ctx):
        """Multi-ticket system management commands"""
        embed = discord.Embed(
            title="🎫 Multi-Ticket System",
            description="A fully customizable ticket system for your server.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Setup Commands",
            value=(
                "`!mticket setup` - Interactive setup wizard\n"
                "`!mticket panel` - Create a ticket panel\n"
                "`!mticket category` - Manage ticket categories\n"
                "`!mticket settings` - Configure system settings\n"
                "`!mticket roles` - Manage support and admin roles"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Management Commands",
            value=(
                "`!mticket stats` - View ticket statistics\n"
                "`!mticket blacklist` - Manage user blacklist\n"
                "`!mticket tags` - Manage available tags\n"
                "`!mticket search` - Search for tickets by tags\n"
                "`!mticket export` - Export ticket data\n"
                "`!mticket survey` - Configure feedback survey"
            ),
            inline=False
        )
        
        embed.set_footer(text="Made by TheHolyoneZ")
        await ctx.send(embed=embed)

    @mticket.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_wizard(self, ctx):
        """Interactive setup wizard for the ticket system"""
        config = self.ticket_manager.get_config(ctx.guild.id)
        
        config.categories = []

        embed = discord.Embed(
            title="🎫 Ticket System Setup Wizard",
            description="Let's set up your ticket system! I'll ask you a series of questions to configure everything.",
            color=discord.Color.blue()
        )
        
        await ctx.send(embed=embed)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
            
        await ctx.send("**Step 1:** In which channel should the ticket panel be displayed? Please mention the channel (#channel)")
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            if msg.channel_mentions:
                config.ticket_channel_id = msg.channel_mentions[0].id
                await ctx.send(f"✅ Ticket panel channel set to {msg.channel_mentions[0].mention}")
            else:
                await ctx.send("❌ No channel mentioned. Please run the setup again and mention a channel.")
                return
        except asyncio.TimeoutError:
            await ctx.send("Setup wizard timed out. Please try again.")
            return
            
        await ctx.send("**Step 2:** In which channel should ticket transcripts be sent? Please mention the channel (#channel)")
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            if msg.channel_mentions:
                config.transcript_channel_id = msg.channel_mentions[0].id
                await ctx.send(f"✅ Transcript channel set to {msg.channel_mentions[0].mention}")
            else:
                await ctx.send("❌ No channel mentioned. Using the same channel as the ticket panel.")
                config.transcript_channel_id = config.ticket_channel_id
        except asyncio.TimeoutError:
            await ctx.send("Setup wizard timed out. Please try again.")
            return
            
        await ctx.send("**Step 3:** Which roles should have access to tickets? Please mention the roles (@role)")
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            if msg.role_mentions:
                config.support_role_ids = [role.id for role in msg.role_mentions]
                role_mentions = ", ".join([role.mention for role in msg.role_mentions])
                await ctx.send(f"✅ Support roles set to: {role_mentions}")
            else:
                await ctx.send("❌ No roles mentioned. Please make sure to set up roles later with `!mticket roles`")
        except asyncio.TimeoutError:
            await ctx.send("Setup wizard timed out. Please try again.")
            return
            
        await ctx.send("**Step 4:** In which category should tickets be created? Please enter the category name or ID")
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            category = None
            try:
                category_id = int(msg.content)
                category = ctx.guild.get_channel(category_id)
            except ValueError:
                for c in ctx.guild.categories:
                    if c.name.lower() == msg.content.lower():
                        category = c
                        break
            if category:
                config.ticket_category_id = category.id
                await ctx.send(f"✅ Tickets will be created in category: {category.name}")
            else:
                await ctx.send("❌ Category not found. Creating a new category called 'Tickets'")
                new_category = await ctx.guild.create_category("Tickets")
                config.ticket_category_id = new_category.id
        except asyncio.TimeoutError:
            await ctx.send("Setup wizard timed out. Please try again.")
            return
            
        await ctx.send("**Step 5:** How many ticket categories would you like to create? (Enter a number)")
        try:
            num_categories_msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit(), timeout=60)
            num_categories = int(num_categories_msg.content)
        except asyncio.TimeoutError:
            await ctx.send("Setup wizard timed out. No custom categories will be created.")
            num_categories = 0
        except ValueError:
            await ctx.send("❌ Invalid number. No custom categories will be created.")
            num_categories = 0
        
        for i in range(num_categories):
            await ctx.send(f"**Category {i+1} of {num_categories}:**\nEnter the name for this category (e.g., `Bug Report`):")
            try:
                name_msg = await self.bot.wait_for('message', check=check, timeout=60)
                name = name_msg.content
        
                await ctx.send(f"Enter an emoji for '{name}' (e.g., `🐛`):")
                emoji_msg = await self.bot.wait_for('message', check=check, timeout=60)
                emoji = emoji_msg.content
        
                await ctx.send(f"Enter a description for '{name}':")
                desc_msg = await self.bot.wait_for('message', check=check, timeout=60)
                description = desc_msg.content
        
                await ctx.send(f"Enter a hex color code for '{name}' (e.g., `#FF0000`) or type `default`:")
                color_msg = await self.bot.wait_for('message', check=check, timeout=60)
                if color_msg.content.lower() == 'default':
                    color = 0x3498db
                else:
                    try:
                        color = int(color_msg.content.replace("#", ""), 16)
                    except ValueError:
                        await ctx.send("❌ Invalid hex code. Using default color.")
                        color = 0x3498db
        
                new_category = TicketCategory(name=name, description=description, color=color, emoji=emoji)
                config.categories.append(new_category)
                await ctx.send(f"✅ Added category: {emoji} **{name}**")
            except asyncio.TimeoutError:
                await ctx.send("Timed out. Skipping this category.")
        
        await ctx.send("**Step 6:** What title would you like for your ticket panel? (Type 'default' to use the default)")
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            if msg.content.lower() != "default":
                config.panel_title = msg.content
            await ctx.send(f"✅ Panel title set to: {config.panel_title}")
        except asyncio.TimeoutError:
            await ctx.send("Setup wizard timed out. Please try again.")
            return
            
        await ctx.send("**Step 7:** What description would you like for your ticket panel? (Type 'default' to use the default)")
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            if msg.content.lower() != "default":
                config.panel_description = msg.content
            await ctx.send(f"✅ Panel description set")
        except asyncio.TimeoutError:
            await ctx.send("Setup wizard timed out. Please try again.")
            return
            
        await ctx.send("**Step 8:** Choose a panel style: `modern`, `classic`, `minimal`, or `custom`")
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            style = msg.content.lower()
            if style in ["modern", "classic", "minimal", "custom"]:
                config.panel_style = style
                await ctx.send(f"✅ Panel style set to: {style}")
            else:
                await ctx.send("❌ Invalid style. Using 'modern' as default.")
                config.panel_style = "modern"
        except asyncio.TimeoutError:
            await ctx.send("Setup wizard timed out. Please try again.")
            return
            
        self.ticket_manager.save_config(ctx.guild.id)
        
        await ctx.send("✅ Setup complete! Creating your ticket panel now...")
        await self.create_panel(ctx)

    @mticket.command(name="panel")
    @commands.has_permissions(administrator=True)
    async def create_panel(self, ctx):
        """Create a ticket panel in the configured channel"""
        config = self.ticket_manager.get_config(ctx.guild.id)
        
        if not config.ticket_channel_id:
            await ctx.send("❌ Ticket channel not configured. Please run `!mticket setup` first.")
            return
            
        channel = ctx.guild.get_channel(config.ticket_channel_id)
        if not channel:
            await ctx.send("❌ Configured ticket channel not found. Please run `!mticket setup` again.")
            return
            
        embed = discord.Embed(
            title=config.panel_title,
            description=config.panel_description,
            color=discord.Color.blue() if config.panel_style == "modern" else (
                discord.Color.gold() if config.panel_style == "classic" else discord.Color.light_grey()
            )
        )
        
        if config.panel_style != "minimal":
            categories_text = []
            for category in config.categories:
                categories_text.append(f"{category.emoji} **{category.name}** - {category.description}")
            
            if categories_text:
                embed.add_field(
                    name="Available Categories",
                    value="\n".join(categories_text),
                    inline=False
                )
        
        if config.panel_image_url:
            embed.set_image(url=config.panel_image_url)
            
        if config.panel_thumbnail_url:
            embed.set_thumbnail(url=config.panel_thumbnail_url)
            
        embed.set_footer(text=config.custom_footer)
        
        view = TicketPanelView(self, config)
        
        await channel.send(embed=embed, view=view)
        await ctx.send("✅ Ticket panel created successfully!")

    @mticket.group(name="category", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def category_group(self, ctx):
        """Manage ticket categories"""
        config = self.ticket_manager.get_config(ctx.guild.id)
        
        embed = discord.Embed(
            title="🎫 Ticket Categories",
            description="Here are your current ticket categories:",
            color=discord.Color.blue()
        )
        
        for i, category in enumerate(config.categories):
            embed.add_field(
                name=f"{i+1}. {category.emoji} {category.name}",
                value=f"Description: {category.description}\nCustom Fields: {len(category.custom_fields)}",
                inline=False
            )
            
        embed.set_footer(text="Use !mticket category add/edit/remove to manage categories")
        await ctx.send(embed=embed)

    @category_group.command(name="add")
    @commands.has_permissions(administrator=True)
    async def add_category(self, ctx):
        """Add a new ticket category"""
        config = self.ticket_manager.get_config(ctx.guild.id)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
            
        await ctx.send("What should the category name be?")
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            name = msg.content
        except asyncio.TimeoutError:
            await ctx.send("Timed out. Please try again.")
            return
            
        await ctx.send("Enter a description for this category:")
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            description = msg.content
        except asyncio.TimeoutError:
            await ctx.send("Timed out. Please try again.")
            return
            
        await ctx.send("What emoji should represent this category? (e.g. 🎮, 🛠️, 🚨)")
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            emoji = msg.content
        except asyncio.TimeoutError:
            await ctx.send("Timed out. Using ❓ as default emoji.")
            emoji = "❓"
            
        await ctx.send("What color should this category use? (Enter a hex code like #FF0000 or 'default')")
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            if msg.content.lower() == "default":
                color = 0x3498db
            else:
                try:
                    color = int(msg.content.replace("#", ""), 16)
                except ValueError:
                    await ctx.send("Invalid hex code. Using default color.")
                    color = 0x3498db
        except asyncio.TimeoutError:
            await ctx.send("Timed out. Using default color.")
            color = 0x3498db
            
        new_category = TicketCategory(
            name=name,
            description=description,
            color=color,
            emoji=emoji
        )
        
        config.categories.append(new_category)
        self.ticket_manager.save_config(ctx.guild.id)
        
        await ctx.send(f"✅ Added new category: {emoji} **{name}**")
        
        await ctx.send("Would you like to add custom fields to this category? (yes/no)")
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            if msg.content.lower() in ["yes", "y"]:
                await self.add_custom_fields(ctx, len(config.categories) - 1)
        except asyncio.TimeoutError:
            await ctx.send("Timed out. No custom fields added.")

    async def add_custom_fields(self, ctx, category_index):
        """Add custom fields to a category"""
        config = self.ticket_manager.get_config(ctx.guild.id)
        category = config.categories[category_index]
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
            
        fields_added = 0
        max_fields = 5
        
        while fields_added < max_fields:
            await ctx.send(f"Enter a name for field #{fields_added+1} (or 'done' to finish):")
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60)
                if msg.content.lower() == "done":
                    break
                    
                field_name = msg.content
                
                await ctx.send(f"Enter a placeholder for field '{field_name}':")
                msg = await self.bot.wait_for('message', check=check, timeout=60)
                placeholder = msg.content
                
                await ctx.send(f"Is this field required? (yes/no)")
                msg = await self.bot.wait_for('message', check=check, timeout=60)
                required = msg.content.lower() in ["yes", "y"]
                
                await ctx.send(f"Should this be a long text field? (yes/no)")
                msg = await self.bot.wait_for('message', check=check, timeout=60)
                long = msg.content.lower() in ["yes", "y"]
                
                category.custom_fields.append({
                    "name": field_name,
                    "placeholder": placeholder,
                    "required": required,
                    "long": long,
                    "max_length": 1000 if long else 100
                })
                
                fields_added += 1
                await ctx.send(f"✅ Added field: {field_name}")
                
            except asyncio.TimeoutError:
                await ctx.send("Timed out. Saving fields added so far.")
                break
                
        self.ticket_manager.save_config(ctx.guild.id)
        await ctx.send(f"✅ Added {fields_added} custom fields to category {category.name}")

    @category_group.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def remove_category(self, ctx, index: int):
        """Remove a ticket category by its index"""
        config = self.ticket_manager.get_config(ctx.guild.id)
        
        if index < 1 or index > len(config.categories):
            await ctx.send(f"❌ Invalid index. Please use a number between 1 and {len(config.categories)}")
            return
            
        category = config.categories[index-1]
        config.categories.pop(index-1)
        self.ticket_manager.save_config(ctx.guild.id)
        
        await ctx.send(f"✅ Removed category: {category.emoji} **{category.name}**")

    @category_group.command(name="edit")
    @commands.has_permissions(administrator=True)
    async def edit_category(self, ctx, index: int):
        """Edit a ticket category by its index"""
        config = self.ticket_manager.get_config(ctx.guild.id)
        
        if index < 1 or index > len(config.categories):
            await ctx.send(f"❌ Invalid index. Please use a number between 1 and {len(config.categories)}")
            return
            
        category = config.categories[index-1]
        
        embed = discord.Embed(
            title=f"Editing Category: {category.emoji} {category.name}",
            description="Choose what you want to edit:",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="1️⃣ Name", value=category.name, inline=True)
        embed.add_field(name="2️⃣ Description", value=category.description, inline=True)
        embed.add_field(name="3️⃣ Emoji", value=category.emoji, inline=True)
        embed.add_field(name="4️⃣ Color", value=f"#{category.color:06x}", inline=True)
        embed.add_field(name="5️⃣ Custom Fields", value=f"{len(category.custom_fields)} fields", inline=True)
        embed.add_field(name="6️⃣ Required Roles", value=f"{len(category.required_roles)} roles", inline=True)
        
        await ctx.send(embed=embed)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content in "123456"
            
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            option = int(msg.content)
            
            if option == 1:
                await ctx.send("Enter the new name:")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                category.name = msg.content
                await ctx.send(f"✅ Name updated to: {category.name}")
                
            elif option == 2:
                await ctx.send("Enter the new description:")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                category.description = msg.content
                await ctx.send(f"✅ Description updated")
                
            elif option == 3:
                await ctx.send("Enter the new emoji:")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                category.emoji = msg.content
                await ctx.send(f"✅ Emoji updated to: {category.emoji}")
                
            elif option == 4:
                await ctx.send("Enter the new color (hex code like #FF0000):")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                try:
                    category.color = int(msg.content.replace("#", ""), 16)
                    await ctx.send(f"✅ Color updated to: #{category.color:06x}")
                except ValueError:
                    await ctx.send("❌ Invalid hex code. Color not updated.")
                    
            elif option == 5:
                await ctx.send("Do you want to add new fields or clear existing ones? (add/clear)")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                
                if msg.content.lower() == "clear":
                    category.custom_fields = []
                    await ctx.send("✅ All custom fields cleared")
                elif msg.content.lower() == "add":
                    await self.add_custom_fields(ctx, index-1)
                else:
                    await ctx.send("❌ Invalid option")
                    
            elif option == 6:
                await ctx.send("Mention the roles that should be required to use this category (or 'clear' to remove all):")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                
                if msg.content.lower() == "clear":
                    category.required_roles = []
                    await ctx.send("✅ Required roles cleared")
                elif msg.role_mentions:
                    category.required_roles = [role.id for role in msg.role_mentions]
                    role_mentions = ", ".join([role.mention for role in msg.role_mentions])
                    await ctx.send(f"✅ Required roles updated to: {role_mentions}")
                else:
                    await ctx.send("❌ No roles mentioned")
            
            self.ticket_manager.save_config(ctx.guild.id)
            
        except asyncio.TimeoutError:
            await ctx.send("Timed out. No changes made.")

    @mticket.command(name="settings")
    @commands.has_permissions(administrator=True)
    async def settings_command(self, ctx):
        """Configure ticket system settings"""
        config = self.ticket_manager.get_config(ctx.guild.id)
        
        embed = discord.Embed(
            title="🎫 Ticket System Settings",
            description="Choose a setting to configure:",
            color=discord.Color.blue()
        )
        
        settings = [
            "1️⃣ Ticket Cooldown",
            "2️⃣ Max Open Tickets Per User",
            "3️⃣ Auto-Close Hours",
            "4️⃣ Allow Anonymous Tickets",
            "5️⃣ Require Reason To Close",
            "6️⃣ Ticket Close Confirmation",
            "7️⃣ Ticket Claim System",
            "8️⃣ DM User On Reply",
            "9️⃣ Transcript Format",
            "🔟 Custom Footer"
        ]
        
        values = [
            f"{config.ticket_cooldown} seconds",
            str(config.max_open_tickets_per_user),
            f"{config.auto_close_hours} hours",
            "Enabled" if config.allow_anonymous else "Disabled",
            "Enabled" if config.require_reason_to_close else "Disabled",
            "Enabled" if config.ticket_close_confirmation else "Disabled",
            "Enabled" if config.ticket_claim_system else "Disabled",
            "Enabled" if config.dm_user_on_reply else "Disabled",
            config.transcript_format,
            config.custom_footer[:20] + "..." if len(config.custom_footer) > 20 else config.custom_footer
        ]
        
        for i in range(len(settings)):
            embed.add_field(name=settings[i], value=values[i], inline=True)
            
        await ctx.send(embed=embed)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
            
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            option = int(msg.content)
            
            if option == 1:
                await ctx.send("Enter the new ticket cooldown in seconds:")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                try:
                    config.ticket_cooldown = int(msg.content)
                    await ctx.send(f"✅ Ticket cooldown set to {config.ticket_cooldown} seconds")
                except ValueError:
                    await ctx.send("❌ Invalid number")
                    
            elif option == 2:
                await ctx.send("Enter the maximum number of open tickets per user:")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                try:
                    config.max_open_tickets_per_user = int(msg.content)
                    await ctx.send(f"✅ Max open tickets set to {config.max_open_tickets_per_user}")
                except ValueError:
                    await ctx.send("❌ Invalid number")
                    
            elif option == 3:
                await ctx.send("Enter the number of hours of inactivity before auto-closing tickets (0 to disable):")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                try:
                    config.auto_close_hours = float(msg.content)
                    if config.auto_close_hours == 0:
                        await ctx.send("✅ Auto-close disabled")
                    else:
                        await ctx.send(f"✅ Auto-close set to {config.auto_close_hours} hours of inactivity")
                except ValueError:
                    await ctx.send("❌ Invalid number")
                    
            elif option == 4:
                await ctx.send("Allow anonymous tickets? (yes/no)")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                config.allow_anonymous = msg.content.lower() in ["yes", "y"]
                await ctx.send(f"✅ Anonymous tickets {'enabled' if config.allow_anonymous else 'disabled'}")
                
            elif option == 5:
                await ctx.send("Require a reason when closing tickets? (yes/no)")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                config.require_reason_to_close = msg.content.lower() in ["yes", "y"]
                await ctx.send(f"✅ Require reason to close {'enabled' if config.require_reason_to_close else 'disabled'}")
                
            elif option == 6:
                await ctx.send("Require confirmation when closing tickets? (yes/no)")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                config.ticket_close_confirmation = msg.content.lower() in ["yes", "y"]
                await ctx.send(f"✅ Ticket close confirmation {'enabled' if config.ticket_close_confirmation else 'disabled'}")
                
            elif option == 7:
                await ctx.send("Enable ticket claim system? (yes/no)")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                config.ticket_claim_system = msg.content.lower() in ["yes", "y"]
                await ctx.send(f"✅ Ticket claim system {'enabled' if config.ticket_claim_system else 'disabled'}")
                
            elif option == 8:
                await ctx.send("DM users when staff reply to their tickets? (yes/no)")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                config.dm_user_on_reply = msg.content.lower() in ["yes", "y"]
                await ctx.send(f"✅ DM on reply {'enabled' if config.dm_user_on_reply else 'disabled'}")
                
            elif option == 9:
                await ctx.send("Choose transcript format: `text`, `html`, `csv`, or `both` (text and html)")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                if msg.content.lower() in ["text", "html", "csv", "both"]:
                    config.transcript_format = msg.content.lower()
                    await ctx.send(f"✅ Transcript format set to {config.transcript_format}")
                else:
                    await ctx.send("❌ Invalid format. Using 'text' as default.")
                    config.transcript_format = "text"
                    
            elif option == 10:
                await ctx.send("Enter a custom footer for ticket embeds:")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                config.custom_footer = msg.content
                await ctx.send(f"✅ Custom footer updated")
                
            self.ticket_manager.save_config(ctx.guild.id)
            
        except asyncio.TimeoutError:
            await ctx.send("Timed out. No changes made.")

    @mticket.command(name="roles")
    @commands.has_permissions(administrator=True)
    async def roles_command(self, ctx):
        """Manage support and admin roles"""
        config = self.ticket_manager.get_config(ctx.guild.id)
        
        embed = discord.Embed(
            title="🎫 Ticket System Roles",
            description="Configure which roles can access and manage tickets",
            color=discord.Color.blue()
        )
        
        support_roles = []
        for role_id in config.support_role_ids:
            role = ctx.guild.get_role(role_id)
            if role:
                support_roles.append(role.mention)
                
        embed.add_field(
            name="Support Roles",
            value="\n".join(support_roles) if support_roles else "None",
            inline=False
        )
        
        admin_roles = []
        for role_id in config.admin_role_ids:
            role = ctx.guild.get_role(role_id)
            if role:
                admin_roles.append(role.mention)
                
        embed.add_field(
            name="Admin Roles",
            value="\n".join(admin_roles) if admin_roles else "None",
            inline=False
        )
        
        embed.add_field(
            name="Options",
            value="1️⃣ Set Support Roles\n2️⃣ Set Admin Roles",
            inline=False
        )
        
        await ctx.send(embed=embed)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content in ["1", "2"]
            
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            option = int(msg.content)
            
            if option == 1:
                await ctx.send("Mention all roles that should have support access to tickets:")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                
                if msg.role_mentions:
                    config.support_role_ids = [role.id for role in msg.role_mentions]
                    role_mentions = ", ".join([role.mention for role in msg.role_mentions])
                    await ctx.send(f"✅ Support roles updated to: {role_mentions}")
                else:
                    await ctx.send("❌ No roles mentioned. Support roles not updated.")
                    
            elif option == 2:
                await ctx.send("Mention all roles that should have admin access to tickets:")
                msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                
                if msg.role_mentions:
                    config.admin_role_ids = [role.id for role in msg.role_mentions]
                    role_mentions = ", ".join([role.mention for role in msg.role_mentions])
                    await ctx.send(f"✅ Admin roles updated to: {role_mentions}")
                else:
                    await ctx.send("❌ No roles mentioned. Admin roles not updated.")
                    
            self.ticket_manager.save_config(ctx.guild.id)
            
        except asyncio.TimeoutError:
            await ctx.send("Timed out. No changes made.")

    @mticket.command(name="stats")
    @commands.has_permissions(administrator=True)
    async def stats_command(self, ctx):
        """View ticket statistics"""
        config = self.ticket_manager.get_config(ctx.guild.id)
        
        embed = discord.Embed(
            title="🎫 Ticket System Statistics",
            description="Overview of your ticket system usage",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📊 General Stats",
            value=(
                f"Total Tickets Created: {config.ticket_stats['total_created']}\n"
                f"Total Tickets Closed: {config.ticket_stats['total_closed']}\n"
                f"Currently Open Tickets: {len(config.active_tickets)}"
            ),
            inline=False
        )
        
        avg_response = config.ticket_stats.get("avg_response_time", 0)
        avg_resolution = config.ticket_stats.get("avg_resolution_time", 0)
        
        embed.add_field(
            name="⏱️ Response Times",
            value=(
                f"Average First Response: {avg_response:.2f} hours\n"
                f"Average Resolution Time: {avg_resolution:.2f} hours"
            ),
            inline=False
        )
        
        category_counts = {}
        for ticket_data in config.closed_tickets.values():
            category = ticket_data.get("category", "Unknown")
            category_counts[category] = category_counts.get(category, 0) + 1
            
        if category_counts:
            category_text = []
            for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                category_text.append(f"{category}: {count} tickets")
                
            embed.add_field(
                name="📁 Category Breakdown",
                value="\n".join(category_text[:10]),
                inline=False
            )
            
        ratings = [data.get("rating", 0) for data in config.closed_tickets.values() if "rating" in data]
        if ratings:
            avg_rating = sum(ratings) / len(ratings)
            rating_counts = {}
            for rating in ratings:
                rating_counts[rating] = rating_counts.get(rating, 0) + 1
                
            rating_text = []
            for i in range(5, 0, -1):
                stars = "⭐" * i
                count = rating_counts.get(i, 0)
                percentage = (count / len(ratings)) * 100
                rating_text.append(f"{stars}: {count} ({percentage:.1f}%)")
                
            embed.add_field(
                name="⭐ Ratings",
                value=(
                    f"Average Rating: {avg_rating:.2f}/5\n"
                    f"Total Ratings: {len(ratings)}\n"
                    f"\n".join(rating_text)
                ),
                inline=False
            )
            
        await ctx.send(embed=embed)

    @mticket.command(name="blacklist")
    @commands.has_permissions(administrator=True)
    async def blacklist_command(self, ctx, action: str = None, user: discord.Member = None):
        """Manage user blacklist for tickets"""
        config = self.ticket_manager.get_config(ctx.guild.id)
        
        if not action:
            embed = discord.Embed(
                title="🎫 Ticket Blacklist",
                description="Users who are not allowed to create tickets",
                color=discord.Color.red()
            )
            
            blacklisted_users = []
            for user_id in config.blacklisted_users:
                user = ctx.guild.get_member(user_id)
                if user:
                    blacklisted_users.append(f"{user.mention} ({user.id})")
                else:
                    blacklisted_users.append(f"Unknown User ({user_id})")
                    
            embed.add_field(
                name="Blacklisted Users",
                value="\n".join(blacklisted_users) if blacklisted_users else "No users blacklisted",
                inline=False
            )
            
            embed.add_field(
                name="Commands",
                value=(
                    "`!mticket blacklist add @user` - Add a user to the blacklist\n"
                    "`!mticket blacklist remove @user` - Remove a user from the blacklist\n"
                    "`!mticket blacklist clear` - Clear the entire blacklist"
                ),
                inline=False
            )
            
            await ctx.send(embed=embed)
            return
            
        if action.lower() == "add" and user:
            if user.id in config.blacklisted_users:
                await ctx.send(f"❌ {user.mention} is already blacklisted")
            else:
                config.blacklisted_users.append(user.id)
                self.ticket_manager.save_config(ctx.guild.id)
                await ctx.send(f"✅ Added {user.mention} to the ticket blacklist")
                
        elif action.lower() == "remove" and user:
            if user.id in config.blacklisted_users:
                config.blacklisted_users.remove(user.id)
                self.ticket_manager.save_config(ctx.guild.id)
                await ctx.send(f"✅ Removed {user.mention} from the ticket blacklist")
            else:
                await ctx.send(f"❌ {user.mention} is not blacklisted")
                
        elif action.lower() == "clear":
            await ctx.send("Are you sure you want to clear the entire blacklist? (yes/no)")
            
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel
                
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=30)
                if msg.content.lower() in ["yes", "y"]:
                    config.blacklisted_users = []
                    self.ticket_manager.save_config(ctx.guild.id)
                    await ctx.send("✅ Ticket blacklist cleared")
                else:
                    await ctx.send("❌ Operation cancelled")
            except asyncio.TimeoutError:
                await ctx.send("Timed out. Operation cancelled.")
                
        else:
            await ctx.send("❌ Invalid command. Use `!mticket blacklist` to see usage.")

    @mticket.command(name="tags")
    @commands.has_permissions(administrator=True)
    async def tags_command(self, ctx, action: str = None, *, tag: str = None):
        """Manage available tags for tickets"""
        config = self.ticket_manager.get_config(ctx.guild.id)
        
        if not action:
            embed = discord.Embed(
                title="🏷️ Ticket Tags",
                description="Tags that can be added to tickets",
                color=discord.Color.blue()
            )
            
            tags = []
            for tag in config.available_tags:
                emoji = config.custom_ticket_emojis.get(tag, "🏷️")
                tags.append(f"{emoji} {tag}")
                
            embed.add_field(
                name="Available Tags",
                value="\n".join(tags) if tags else "No tags configured",
                inline=False
            )
            
            embed.add_field(
                name="Commands",
                value=(
                    "`!mticket tags add <tag>` - Add a new tag\n"
                    "`!mticket tags remove <tag>` - Remove a tag\n"
                    "`!mticket tags emoji <tag> <emoji>` - Set custom emoji for a tag"
                ),
                inline=False
            )
            
            await ctx.send(embed=embed)
            return
            
        if action.lower() == "add" and tag:
            if tag in config.available_tags:
                await ctx.send(f"❌ Tag '{tag}' already exists")
            else:
                config.available_tags.append(tag)
                self.ticket_manager.save_config(ctx.guild.id)
                await ctx.send(f"✅ Added tag: {tag}")
                
        elif action.lower() == "remove" and tag:
            if tag in config.available_tags:
                config.available_tags.remove(tag)
                if tag in config.custom_ticket_emojis:
                    del config.custom_ticket_emojis[tag]
                self.ticket_manager.save_config(ctx.guild.id)
                await ctx.send(f"✅ Removed tag: {tag}")
            else:
                await ctx.send(f"❌ Tag '{tag}' does not exist")
                
        elif action.lower() == "emoji" and tag:
            parts = tag.split(" ", 1)
            if len(parts) != 2:
                await ctx.send("❌ Please provide both a tag name and an emoji")
                return
                
            tag_name, emoji = parts
            
            if tag_name not in config.available_tags:
                await ctx.send(f"❌ Tag '{tag_name}' does not exist")
                return
                
            config.custom_ticket_emojis[tag_name] = emoji
            self.ticket_manager.save_config(ctx.guild.id)
            await ctx.send(f"✅ Set emoji for tag '{tag_name}' to {emoji}")
            
        else:
            await ctx.send("❌ Invalid command. Use `!mticket tags` to see usage.")

    @mticket.command(name="export")
    @commands.has_permissions(administrator=True)
    async def export_command(self, ctx, format_type: str = "csv"):
        """Export ticket data for analysis"""
        config = self.ticket_manager.get_config(ctx.guild.id)
        
        if format_type.lower() not in ["csv", "json"]:
            await ctx.send("❌ Invalid format. Please use 'csv' or 'json'")
            return
            
        await ctx.send("⏳ Generating export... This may take a moment.")
        
        if format_type.lower() == "csv":
            filename = f"ticket_export_{ctx.guild.id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'ticket_id', 'ticket_number', 'category', 'title', 'creator_id', 
                    'created_at', 'closed_at', 'closed_by', 'close_reason',
                    'is_anonymous', 'rating', 'first_response_time', 'resolution_time'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                
                for ticket_id, data in config.closed_tickets.items():
                    row = {
                        'ticket_id': ticket_id,
                        'ticket_number': data.get('ticket_number', 'Unknown'),
                        'category': data.get('category', 'Unknown'),
                        'title': data.get('title', 'Unknown'),
                        'creator_id': data.get('creator_id', 'Unknown'),
                        'created_at': data.get('created_at', 'Unknown'),
                        'closed_at': data.get('closed_at', 'Unknown'),
                        'closed_by': data.get('closed_by', 'Unknown'),
                        'close_reason': data.get('close_reason', 'Unknown'),
                        'is_anonymous': data.get('is_anonymous', False),
                        'rating': data.get('rating', 'None'),
                        'first_response_time': data.get('response_time', 'Unknown'),
                        'resolution_time': data.get('resolution_time', 'Unknown')
                    }
                    writer.writerow(row)
                    
        else:
            filename = f"ticket_export_{ctx.guild.id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.json"
            
            export_data = {
                'closed_tickets': config.closed_tickets,
                'stats': config.ticket_stats
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4)
                
        await ctx.send(file=discord.File(filename))
        os.remove(filename)

    @mticket.command(name="survey")
    @commands.has_permissions(administrator=True)
    async def survey_command(self, ctx):
        """Configure the feedback survey for closed tickets"""
        config = self.ticket_manager.get_config(ctx.guild.id)
        
        embed = discord.Embed(
            title="📝 Ticket Feedback Survey",
            description="Configure the survey sent to users after closing a ticket",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Survey Status",
            value="Enabled" if config.ticket_survey_enabled else "Disabled",
            inline=False
        )
        
        questions = []
        for i, q in enumerate(config.ticket_survey_questions):
            questions.append(f"{i+1}. {q.get('question')} {'(Required)' if q.get('required') else ''}")
            
        embed.add_field(
            name="Current Questions",
            value="\n".join(questions) if questions else "No questions configured",
            inline=False
        )
        
        embed.add_field(
            name="Options",
            value=(
                "1️⃣ Toggle Survey On/Off\n"
                "2️⃣ Add Question\n"
                "3️⃣ Remove Question\n"
                "4️⃣ Clear All Questions"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content in ["1", "2", "3", "4"]
            
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            option = int(msg.content)
            
            if option == 1:
                config.ticket_survey_enabled = not config.ticket_survey_enabled
                await ctx.send(f"✅ Survey {'enabled' if config.ticket_survey_enabled else 'disabled'}")
                
            elif option == 2:
                if len(config.ticket_survey_questions) >= 5:
                    await ctx.send("❌ You can only have up to 5 questions in the survey")
                    return
                    
                await ctx.send("Enter the question text:")
                question_text = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                
                await ctx.send("Enter a placeholder text for the answer:")
                placeholder = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                
                await ctx.send("Is this question required? (yes/no)")
                required_msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                required = required_msg.content.lower() in ["yes", "y"]
                
                await ctx.send("Should this be a long-form answer? (yes/no)")
                long_msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                long = long_msg.content.lower() in ["yes", "y"]
                
                new_question = {
                    "question": question_text.content,
                    "placeholder": placeholder.content,
                    "required": required,
                    "long": long,
                    "max_length": 1000 if long else 100
                }
                
                config.ticket_survey_questions.append(new_question)
                await ctx.send(f"✅ Added question: {question_text.content}")
                
            elif option == 3:
                if not config.ticket_survey_questions:
                    await ctx.send("❌ There are no questions to remove")
                    return
                    
                await ctx.send("Enter the number of the question to remove:")
                num_msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                
                try:
                    num = int(num_msg.content)
                    if 1 <= num <= len(config.ticket_survey_questions):
                        removed = config.ticket_survey_questions.pop(num-1)
                        await ctx.send(f"✅ Removed question: {removed.get('question')}")
                    else:
                        await ctx.send("❌ Invalid question number")
                except ValueError:
                    await ctx.send("❌ Please enter a valid number")
                    
            elif option == 4:
                await ctx.send("Are you sure you want to clear all survey questions? (yes/no)")
                confirm_msg = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=30)
                
                if confirm_msg.content.lower() in ["yes", "y"]:
                    config.ticket_survey_questions = []
                    await ctx.send("✅ All survey questions cleared")
                else:
                    await ctx.send("❌ Operation cancelled")
                    
            self.ticket_manager.save_config(ctx.guild.id)
            
        except asyncio.TimeoutError:
            await ctx.send("Timed out. No changes made.")

    @mticket.command(name="search")
    @commands.has_permissions(administrator=True)
    async def search_tickets_by_tag(self, ctx, tag: str):
        """Search for closed tickets by a specific tag"""
        config = self.ticket_manager.get_config(ctx.guild.id)

        if not config.transcript_channel_id:
            await ctx.send("❌ Transcript channel is not configured. Cannot search transcripts.")
            return

        if not config.available_tags or tag not in config.available_tags:
            available_tags = ", ".join(config.available_tags) if config.available_tags else "None"
            await ctx.send(f"❌ Invalid or non-existent tag. Available tags are: {available_tags}")
            return
            
        matching_tickets = []
        for ticket_id, data in config.closed_tickets.items():
            if tag in data.get("tags", []):
                matching_tickets.append(data)

        if not matching_tickets:
            await ctx.send(f"❌ No closed tickets found with the tag: `{tag}`")
            return

        embed = discord.Embed(
            title=f"Tickets with tag: {tag}",
            description=f"Found {len(matching_tickets)} ticket(s) with the tag `{tag}`.",
            color=config.embed_color_scheme["info"]
        )

        ticket_list_text = []
        for ticket in matching_tickets:
            ticket_number = ticket.get('ticket_number', 'Unknown')
            creator_id = ticket.get('creator_id', 'Unknown')
            creator = ctx.guild.get_member(creator_id)
            creator_name = creator.display_name if creator else f"User ID: {creator_id}"
            
            ticket_list_text.append(f"• **Ticket #{ticket_number}** by {creator_name}")

        embed.add_field(name="Matching Tickets", value="\n".join(ticket_list_text[:25]) or "None", inline=False)
        embed.set_footer(text="Select a ticket from the menu below to view its transcript.")

        view = discord.ui.View()
        view.add_item(TicketSearchSelect(self, config, matching_tickets))

        await ctx.send(embed=embed, view=view)

    async def create_ticket(self, interaction: discord.Interaction, category: TicketCategory, title: str, description: str, is_anonymous: bool = False, custom_fields: dict = None):
        """Create a new ticket"""
        config = self.ticket_manager.get_config(interaction.guild.id)
        
        if interaction.user.id in config.blacklisted_users:
            await interaction.followup.send("You are not allowed to create tickets.", ephemeral=True)
            return
            
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        cooldown_key = f"{guild_id}:{user_id}"
        current_time = datetime.datetime.now().timestamp()
        
        if cooldown_key in self.ticket_manager.cooldowns:
            last_ticket_time = self.ticket_manager.cooldowns[cooldown_key]
            if current_time - last_ticket_time < config.ticket_cooldown:
                remaining = int(config.ticket_cooldown - (current_time - last_ticket_time))
                await interaction.followup.send(
                    f"Please wait {remaining} seconds before creating another ticket.",
                    ephemeral=True
                )
                return
        
        open_tickets = 0
        for ticket_data in config.active_tickets.values():
            if ticket_data.get("creator_id") == user_id:
                open_tickets += 1
                
        if open_tickets >= config.max_open_tickets_per_user:
            await interaction.followup.send(
                f"You already have {open_tickets} open tickets. Please close some before creating new ones.",
                ephemeral=True
            )
            return
            
        ticket_id = str(uuid.uuid4())
        config.ticket_counter += 1
        ticket_number = config.ticket_counter
        
        channel_name = config.ticket_naming_format.format(number=ticket_number)
        
        category_channel = interaction.guild.get_channel(config.ticket_category_id)
        if not category_channel:
            await interaction.followup.send("Ticket category not found. Please contact an administrator.", ephemeral=True)
            return
            
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        if not is_anonymous:
            overwrites[interaction.user] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
        for role_id in config.support_role_ids:
            role = interaction.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                
        for role_id in config.admin_role_ids:
            role = interaction.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
                
        try:
            channel = await category_channel.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                topic=f"Ticket #{ticket_number} | {category.name} | Created by: {'Anonymous' if is_anonymous else interaction.user.name}"
            )
        except Exception as e:
            logger.error(f"Failed to create ticket channel: {e}")
            await interaction.followup.send("Failed to create ticket channel. Please try again later.", ephemeral=True)
            return
            
        ticket_data = {
            "ticket_id": ticket_id,
            "ticket_number": ticket_number,
            "channel_id": channel.id,
            "creator_id": interaction.user.id,
            "category": category.name,
            "title": title,
            "description": description,
            "is_anonymous": is_anonymous,
            "created_at": datetime.datetime.now().isoformat(),
            "last_activity": datetime.datetime.now().isoformat(),
            "custom_fields": custom_fields or {},
            "tags": category.auto_tags.copy() if category.auto_tags else []
        }
        
        config.active_tickets[ticket_id] = ticket_data
        
        if config.ticket_stats_tracking:
            config.ticket_stats["total_created"] += 1
            category_name = category.name
            if category_name not in config.ticket_stats["categories"]:
                config.ticket_stats["categories"][category_name] = {"created": 0, "closed": 0}
            config.ticket_stats["categories"][category_name]["created"] += 1
            
        self.ticket_manager.save_config(interaction.guild.id)
        
        self.ticket_manager.cooldowns[cooldown_key] = current_time
        
        embed = discord.Embed(
            title=f"Ticket #{ticket_number}: {title}",
            description=category.custom_welcome or config.custom_ticket_welcome,
            color=category.color
        )
        
        embed.add_field(name="Category", value=f"{category.emoji} {category.name}", inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(datetime.datetime.now()), inline=True)
        
        if not is_anonymous:
            embed.add_field(name="Created By", value=interaction.user.mention, inline=True)
            
        embed.add_field(name="Description", value=description, inline=False)
        
        if custom_fields:
            custom_fields_text = []
            for name, value in custom_fields.items():
                if value:
                    custom_fields_text.append(f"**{name}**: {value}")
                    
            if custom_fields_text:
                embed.add_field(name="Additional Information", value="\n".join(custom_fields_text), inline=False)
                
        embed.set_footer(text=config.custom_footer)
        
        control_panel = TicketControlPanel(self, ticket_id, config)
        
        welcome_message = await channel.send(
            content=f"{'Support Team' if is_anonymous else interaction.user.mention}, welcome to your ticket!",
            embed=embed,
            view=control_panel
        )
        
        if config.ticket_pin_welcome_message:
            try:
                await welcome_message.pin()
            except:
                pass
                
        await interaction.followup.send(
            f"Your ticket has been created: {channel.mention}",
            ephemeral=True
        )
        
        if config.ticket_creation_notification and config.ticket_creation_notification_channel_id:
            notification_channel = interaction.guild.get_channel(config.ticket_creation_notification_channel_id)
            if notification_channel:
                notification_embed = discord.Embed(
                    title="New Ticket Created",
                    description=f"Ticket #{ticket_number} has been created",
                    color=category.color,
                    timestamp=datetime.datetime.now()
                )
                
                notification_embed.add_field(name="Category", value=category.name, inline=True)
                
                if not is_anonymous:
                    notification_embed.add_field(name="Created By", value=interaction.user.mention, inline=True)
                else:
                    notification_embed.add_field(name="Created By", value="Anonymous User", inline=True)
                    
                notification_embed.add_field(name="Channel", value=channel.mention, inline=True)
                
                await notification_channel.send(embed=notification_embed)

    async def close_ticket(self, interaction: discord.Interaction, ticket_id: str, reason: str = None):
        """Close a ticket"""
        config = self.ticket_manager.get_config(interaction.guild.id)
        
        if ticket_id not in config.active_tickets:
            await interaction.response.send_message("This ticket no longer exists.", ephemeral=True)
            return
            
        ticket_data = config.active_tickets[ticket_id]
        channel_id = ticket_data.get("channel_id")
        channel = interaction.guild.get_channel(channel_id)
        
        if not channel:
            del config.active_tickets[ticket_id]
            self.ticket_manager.save_config(interaction.guild.id)
            await interaction.response.send_message("The ticket channel no longer exists.", ephemeral=True)
            return
            
        has_permission = False
        
        if config.allow_user_close and interaction.user.id == ticket_data.get("creator_id"):
            has_permission = True
            
        if not has_permission:
            for role_id in config.support_role_ids + config.admin_role_ids:
                role = interaction.guild.get_role(role_id)
                if role and role in interaction.user.roles:
                    has_permission = True
                    break
                    
        if not has_permission:
            await interaction.response.send_message("You don't have permission to close this ticket.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=False)
        await interaction.followup.send("Generating transcript and closing ticket...")
        
        transcript_content = None
        try:
            transcript_content = await self.ticket_manager.create_transcript_content(channel, config)
        except Exception as e:
            logger.error(f"Failed to create transcript: {e}")
            await interaction.followup.send("Failed to create transcript, but the ticket will still be closed.")
            
        embed = discord.Embed(
            title=f"Ticket #{ticket_data.get('ticket_number')} Closed",
            description=config.custom_ticket_closed,
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
        
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
            
        embed.set_footer(text=config.custom_footer)
        
        await channel.send(embed=embed)
        
        if transcript_content and config.transcript_channel_id:
            transcript_channel = interaction.guild.get_channel(config.transcript_channel_id)
            if transcript_channel:
                transcript_embed = discord.Embed(
                    title=f"Ticket #{ticket_data.get('ticket_number')} Transcript",
                    description=f"Ticket has been closed by {interaction.user.mention}",
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now()
                )
                
                transcript_embed.add_field(name="Category", value=ticket_data.get("category"), inline=True)
                
                creator_id = ticket_data.get("creator_id")
                creator = interaction.guild.get_member(creator_id)
                
                if creator:
                    if ticket_data.get("is_anonymous", False):
                        transcript_embed.add_field(name="Created By", value="Anonymous User", inline=True)
                    else:
                        transcript_embed.add_field(name="Created By", value=creator.mention, inline=True)
                else:
                    transcript_embed.add_field(name="Created By", value=f"Unknown User ({creator_id})", inline=True)
                    
                transcript_embed.add_field(
                    name="Created At",
                    value=discord.utils.format_dt(datetime.datetime.fromisoformat(ticket_data.get("created_at"))),
                    inline=True
                )
                
                if reason:
                    transcript_embed.add_field(name="Close Reason", value=reason, inline=False)
                    
                if ticket_data.get("tags"):
                    tag_text = []
                    for tag in ticket_data.get("tags"):
                        emoji = config.custom_ticket_emojis.get(tag, "🏷️")
                        tag_text.append(f"{emoji} {tag}")
                        
                    transcript_embed.add_field(name="Tags", value=", ".join(tag_text), inline=False)
                    
                transcript_embed.set_footer(text=config.custom_footer)
                
                try:
                    file_name = f"transcript-{channel.name}.txt"
                    if isinstance(transcript_content, bytes):
                        file = discord.File(io.BytesIO(transcript_content.encode('utf-8')), filename=file_name)
                    else:
                        file = discord.File(io.StringIO(transcript_content), filename=file_name)
                    
                    transcript_message = await transcript_channel.send(embed=transcript_embed, file=file)
                    ticket_data["transcript_message_id"] = transcript_message.id
                except Exception as e:
                    logger.error(f"Failed to send transcript file: {e}")
        
        ticket_data["closed_at"] = datetime.datetime.now().isoformat()
        ticket_data["closed_by"] = interaction.user.id
        ticket_data["close_reason"] = reason
        
        created_at = datetime.datetime.fromisoformat(ticket_data.get("created_at"))
        closed_at = datetime.datetime.now()
        resolution_time = (closed_at - created_at).total_seconds() / 3600
        ticket_data["resolution_time"] = resolution_time
        
        config.closed_tickets[ticket_id] = ticket_data
        del config.active_tickets[ticket_id]
        
        if config.ticket_stats_tracking:
            config.ticket_stats["total_closed"] += 1
            
            category = ticket_data.get("category")
            if category in config.ticket_stats["categories"]:
                config.ticket_stats["categories"][category]["closed"] += 1
                
            total_closed = config.ticket_stats["total_closed"]
            current_avg = config.ticket_stats["avg_resolution_time"]
            
            if total_closed > 1:
                new_avg = ((current_avg * (total_closed - 1)) + resolution_time) / total_closed
            else:
                new_avg = resolution_time
                
            config.ticket_stats["avg_resolution_time"] = new_avg
            
        self.ticket_manager.save_config(interaction.guild.id)
        
        if config.ticket_close_notification and config.ticket_close_notification_channel_id:
            notification_channel = interaction.guild.get_channel(config.ticket_close_notification_channel_id)
            if notification_channel:
                notification_embed = discord.Embed(
                    title="Ticket Closed",
                    description=f"Ticket #{ticket_data.get('ticket_number')} has been closed",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.now()
                )
                
                notification_embed.add_field(name="Category", value=ticket_data.get("category"), inline=True)
                notification_embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
                
                if reason:
                    notification_embed.add_field(name="Reason", value=reason, inline=False)
                    
                await notification_channel.send(embed=notification_embed)
                
        if config.ticket_rating_system and not ticket_data.get("is_anonymous", False):
            creator_id = ticket_data.get("creator_id")
            creator = interaction.guild.get_member(creator_id)
            
            if creator:
                try:
                    rating_embed = discord.Embed(
                        title=f"How was your experience with Ticket #{ticket_data.get('ticket_number')}?",
                        description="Please rate your support experience by clicking one of the buttons below.",
                        color=discord.Color.blue()
                    )
                    
                    rating_view = TicketRatingView(self, ticket_id, config, guild_id=interaction.guild.id)
                        
                    await creator.send(embed=rating_embed, view=rating_view)
                    logger.info(f"Sent rating request to {creator.name}#{creator.discriminator}")
                except Exception as e:
                    logger.error(f"Failed to send rating DM to {creator.name}#{creator.discriminator}: {e}")
                    pass
                    
        if config.dm_user_on_close and not ticket_data.get("is_anonymous", False):
            creator_id = ticket_data.get("creator_id")
            creator = interaction.guild.get_member(creator_id)
            
            if creator:
                try:
                    close_embed = discord.Embed(
                        title=f"Your Ticket #{ticket_data.get('ticket_number')} Has Been Closed",
                        description=f"Your ticket in {interaction.guild.name} has been closed by {interaction.user.display_name}.",
                        color=discord.Color.red(),
                        timestamp=datetime.datetime.now()
                    )
                    
                    if reason:
                        close_embed.add_field(name="Reason", value=reason, inline=False)
                        
                    close_embed.set_footer(text=f"Server: {interaction.guild.name}")
                    
                    await creator.send(embed=close_embed)
                    logger.info(f"Sent closure notification to {creator.name}#{creator.discriminator}")
                except Exception as e:
                    logger.error(f"Failed to send closure DM to {creator.name}#{creator.discriminator}: {e}")
                    pass
                    
        try:
            await channel.delete(reason=f"Ticket #{ticket_data.get('ticket_number')} closed by {interaction.user.name}")
        except Exception as e:
            logger.error(f"Failed to delete ticket channel: {e}")
            await interaction.followup.send("Failed to delete the channel, but the ticket has been closed.")
            
def setup(bot):
    cog = MultiTicketSystem(bot)
    asyncio.create_task(bot.add_cog(cog))
    return cog