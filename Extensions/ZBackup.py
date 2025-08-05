import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import json
import datetime
import asyncio
import aiohttp
import io
import traceback
from typing import Optional, Union, List, Dict, Any
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ZBackup")
handler = logging.FileHandler(filename="zbackup.log", encoding="utf-8", mode="a")
handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
logger.addHandler(handler)

class ZBackup(commands.Cog):

    
    def __init__(self, bot):
        self.bot = bot
        self.backup_path = "backups"
        
        if not os.path.exists(self.backup_path):
            os.makedirs(self.backup_path)
            
    async def cog_load(self):
        logger.info("ZBackup cog loaded successfully")
    
    async def cog_unload(self):
        logger.info("ZBackup cog unloaded")
    
    def cog_check(self, ctx):
        
        if ctx.guild is None:
            return False
        return ctx.author.guild_permissions.administrator
    
    async def backup_server_settings(self, guild: discord.Guild) -> Dict[str, Any]:

        settings = {
            "name": guild.name,
            "description": guild.description,
            "icon_url": str(guild.icon.url) if guild.icon else None,
            "banner_url": str(guild.banner.url) if guild.banner else None,
            "splash_url": str(guild.splash.url) if guild.splash else None,
            "discovery_splash_url": str(guild.discovery_splash.url) if guild.discovery_splash else None,
            "features": guild.features,
            "preferred_locale": guild.preferred_locale,
            "verification_level": guild.verification_level.value,
            "default_notifications": guild.default_notifications.value,
            "explicit_content_filter": guild.explicit_content_filter.value,
            "afk_timeout": guild.afk_timeout,
            "afk_channel_id": guild.afk_channel.id if guild.afk_channel else None,
            "afk_channel_name": guild.afk_channel.name if guild.afk_channel else None,
            "system_channel_id": guild.system_channel.id if guild.system_channel else None,
            "system_channel_name": guild.system_channel.name if guild.system_channel else None,
            "system_channel_flags": {
                "join_notifications": guild.system_channel_flags.join_notifications,
                "premium_subscriptions": guild.system_channel_flags.premium_subscriptions,
                "guild_reminder_notifications": guild.system_channel_flags.guild_reminder_notifications,
                "join_notification_replies": guild.system_channel_flags.join_notification_replies
            } if guild.system_channel_flags else None,
            "rules_channel_id": guild.rules_channel.id if guild.rules_channel else None,
            "rules_channel_name": guild.rules_channel.name if guild.rules_channel else None,
            "public_updates_channel_id": guild.public_updates_channel.id if guild.public_updates_channel else None,
            "public_updates_channel_name": guild.public_updates_channel.name if guild.public_updates_channel else None,
            "premium_tier": guild.premium_tier,
            "premium_subscription_count": guild.premium_subscription_count,
            "mfa_level": guild.mfa_level.value,
            "nsfw_level": guild.nsfw_level.value,
            "max_presences": guild.max_presences,
            "max_members": guild.max_members,
            "max_video_channel_users": guild.max_video_channel_users,
            "vanity_url_code": guild.vanity_url_code
        }
        
        return settings

    

    async def clear_channels(self, guild: discord.Guild):

        try:
            
            for channel in guild.channels:
                try:
                    await channel.delete(reason="Clearing channels for backup restoration")
                    
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error deleting channel {channel.name}: {e}")
            
            logger.info(f"Cleared all channels in {guild.name}")
        except Exception as e:
            logger.error(f"Error clearing channels: {traceback.format_exc()}")
            raise Exception(f"Failed to clear channels: {str(e)}")

    async def clear_roles(self, guild: discord.Guild):

        try:
            
            for role in reversed(guild.roles):  
                if role.name != "@everyone" and role.position < guild.me.top_role.position:
                    try:
                        await role.delete(reason="Clearing roles for backup restoration")
                        
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.error(f"Error deleting role {role.name}: {e}")
            
            logger.info(f"Cleared all roles in {guild.name}")
        except Exception as e:
            logger.error(f"Error clearing roles: {traceback.format_exc()}")
            raise Exception(f"Failed to clear roles: {str(e)}")

    async def clear_emojis(self, guild: discord.Guild):

        try:
            
            for emoji in guild.emojis:
                try:
                    await emoji.delete(reason="Clearing emojis for backup restoration")
                    
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error deleting emoji {emoji.name}: {e}")
            
            logger.info(f"Cleared all emojis in {guild.name}")
        except Exception as e:
            logger.error(f"Error clearing emojis: {traceback.format_exc()}")
            raise Exception(f"Failed to clear emojis: {str(e)}")

    async def clear_stickers(self, guild: discord.Guild):

        try:
            
            for sticker in guild.stickers:
                try:
                    await sticker.delete(reason="Clearing stickers for backup restoration")
                    
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error deleting sticker {sticker.name}: {e}")
            
            logger.info(f"Cleared all stickers in {guild.name}")
        except Exception as e:
            logger.error(f"Error clearing stickers: {traceback.format_exc()}")
            raise Exception(f"Failed to clear stickers: {str(e)}")

    async def clear_bans(self, guild: discord.Guild):

        try:
            
            bans = [ban_entry async for ban_entry in guild.bans()]
            for ban_entry in bans:
                try:
                    await guild.unban(ban_entry.user, reason="Clearing bans for backup restoration")
                    
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error unbanning user {ban_entry.user}: {e}")
            
            logger.info(f"Cleared all bans in {guild.name}")
        except Exception as e:
            logger.error(f"Error clearing bans: {traceback.format_exc()}")
            raise Exception(f"Failed to clear bans: {str(e)}")

    async def backup_roles(self, guild: discord.Guild) -> List[Dict[str, Any]]:

        roles = []
        for role in sorted(guild.roles, key=lambda r: r.position, reverse=True):
            
            if role.is_default():
                continue
                
            role_data = {
                "id": role.id,
                "name": role.name,
                "permissions": role.permissions.value,
                "color": role.color.value,
                "hoist": role.hoist,
                "mentionable": role.mentionable,
                "position": role.position,
                "managed": role.managed,
                "icon": str(role.icon.url) if role.icon else None,
                "unicode_emoji": role.unicode_emoji
            }
            roles.append(role_data)
        return roles
    
    async def backup_channels(self, guild: discord.Guild) -> List[Dict[str, Any]]:

        result = []
        
        
        for category in guild.categories:
            category_data = {
                "id": category.id,
                "name": category.name,
                "position": category.position,
                "type": "category",
                "overwrites": await self.backup_permission_overwrites(category.overwrites),
                "nsfw": category.is_nsfw(),
                "original_id": category.id  
            }
            result.append(category_data)
        
        
        for channel in guild.text_channels:
            channel_data = {
                "id": channel.id,
                "name": channel.name,
                "position": channel.position,
                "type": "text",
                "topic": channel.topic,
                "nsfw": channel.is_nsfw(),
                "rate_limit_per_user": channel.slowmode_delay,
                "category_id": channel.category_id,
                "category_name": channel.category.name if channel.category else None,
                "overwrites": await self.backup_permission_overwrites(channel.overwrites),
                "default_auto_archive_duration": channel.default_auto_archive_duration,
                "original_id": channel.id  
            }
            result.append(channel_data)
        
        
        for channel in guild.voice_channels:
            channel_data = {
                "id": channel.id,
                "name": channel.name,
                "position": channel.position,
                "type": "voice",
                "bitrate": channel.bitrate,
                "user_limit": channel.user_limit,
                "category_id": channel.category_id,
                "category_name": channel.category.name if channel.category else None,
                "overwrites": await self.backup_permission_overwrites(channel.overwrites),
                "original_id": channel.id  
            }
            result.append(channel_data)
        
        
        for channel in guild.forums:
            channel_data = {
                "id": channel.id,
                "name": channel.name,
                "position": channel.position,
                "type": "forum",
                "topic": channel.topic,
                "nsfw": channel.is_nsfw(),
                "rate_limit_per_user": channel.slowmode_delay,
                "category_id": channel.category_id,
                "category_name": channel.category.name if channel.category else None,
                "overwrites": await self.backup_permission_overwrites(channel.overwrites),
                "available_tags": [{"name": tag.name, "emoji": str(tag.emoji) if tag.emoji else None, "moderated": tag.moderated} for tag in channel.available_tags],
                "default_reaction_emoji": str(channel.default_reaction_emoji) if channel.default_reaction_emoji else None,
                "default_thread_slowmode_delay": channel.default_thread_slowmode_delay,
                "original_id": channel.id  
            }
            result.append(channel_data)
        
        
        for channel in guild.stage_channels:
            channel_data = {
                "id": channel.id,
                "name": channel.name,
                "position": channel.position,
                "type": "stage",
                "topic": channel.topic,
                "bitrate": channel.bitrate,
                "user_limit": channel.user_limit,
                "category_id": channel.category_id,
                "category_name": channel.category.name if channel.category else None,
                "overwrites": await self.backup_permission_overwrites(channel.overwrites),
                "original_id": channel.id  
            }
            result.append(channel_data)
        
        
        for channel in guild.text_channels + list(guild.forums):
            for thread in channel.threads:
                thread_data = {
                    "id": thread.id,
                    "name": thread.name,
                    "type": "thread",
                    "parent_id": thread.parent_id,
                    "parent_name": thread.parent.name if thread.parent else None,
                    "archived": thread.archived,
                    "locked": thread.locked,
                    "slowmode_delay": thread.slowmode_delay,
                    "auto_archive_duration": thread.auto_archive_duration,
                    "original_id": thread.id  
                }
                result.append(thread_data)
        
        return result

    
    async def backup_permission_overwrites(self, overwrites: Dict[Union[discord.Role, discord.Member], discord.PermissionOverwrite]) -> List[Dict[str, Any]]:

        result = []
        
        for target, overwrite in overwrites.items():
            
            allow, deny = overwrite.pair()
            
            
            target_type = "role" if isinstance(target, discord.Role) else "member"
            
            
            name = target.name if target_type == "role" else None
            
            result.append({
                "id": target.id,
                "type": target_type,
                "name": name,  
                "allow": allow.value,
                "deny": deny.value
            })
        
        return result

    
    async def backup_emojis(self, guild: discord.Guild) -> List[Dict[str, Any]]:

        emojis = []
        for emoji in guild.emojis:
            
            emoji_image = None
            async with aiohttp.ClientSession() as session:
                async with session.get(str(emoji.url)) as resp:
                    if resp.status == 200:
                        emoji_image = await resp.read()
            
            emoji_data = {
                "id": emoji.id,
                "name": emoji.name,
                "animated": emoji.animated,
                "available": emoji.available,
                "managed": emoji.managed,
                "require_colons": emoji.require_colons,
                "roles": [role.id for role in emoji.roles] if emoji.roles else [],
                "image": emoji_image.hex() if emoji_image else None
            }
            emojis.append(emoji_data)
        return emojis
    
    async def backup_stickers(self, guild: discord.Guild) -> List[Dict[str, Any]]:

        stickers = []
        for sticker in guild.stickers:
            
            sticker_image = None
            async with aiohttp.ClientSession() as session:
                async with session.get(str(sticker.url)) as resp:
                    if resp.status == 200:
                        sticker_image = await resp.read()
            
            sticker_data = {
                "id": sticker.id,
                "name": sticker.name,
                "description": sticker.description,
                "emoji": sticker.emoji,
                "format_type": sticker.format.value,
                "available": sticker.available,
                "image": sticker_image.hex() if sticker_image else None
            }
            stickers.append(sticker_data)
        return stickers
    
    async def backup_messages(self, guild: discord.Guild, limit: int = 100) -> Dict[int, List[Dict[str, Any]]]:

        messages_by_channel = {}
        
        for channel in guild.text_channels:
            try:
                channel_messages = []
                async for message in channel.history(limit=limit):
                    
                    if message.author.bot:
                        continue
                        
                    
                    attachments = []
                    for attachment in message.attachments:
                        try:
                            file_data = None
                            async with aiohttp.ClientSession() as session:
                                async with session.get(attachment.url) as resp:
                                    if resp.status == 200:
                                        file_data = await resp.read()
                            
                            if file_data:
                                attachments.append({
                                    "filename": attachment.filename,
                                    "content_type": attachment.content_type,
                                    "size": attachment.size,
                                    "data": file_data.hex()
                                })
                        except Exception as e:
                            logger.error(f"Error backing up attachment {attachment.filename}: {e}")
                    
                    
                    embeds = []
                    for embed in message.embeds:
                        embeds.append(embed.to_dict())
                    
                    message_data = {
                        "id": message.id,
                        "content": message.content,
                        "author_id": message.author.id,
                        "author_name": message.author.name,
                        "created_at": message.created_at.isoformat(),
                        "edited_at": message.edited_at.isoformat() if message.edited_at else None,
                        "pinned": message.pinned,
                        "attachments": attachments,
                        "embeds": embeds,
                        "reactions": [{"emoji": str(reaction.emoji), "count": reaction.count} for reaction in message.reactions]
                    }
                    channel_messages.append(message_data)
                
                if channel_messages:
                    messages_by_channel[channel.id] = channel_messages
                    
            except discord.Forbidden:
                logger.warning(f"No permission to read message history in #{channel.name}")
            except Exception as e:
                logger.error(f"Error backing up messages in #{channel.name}: {e}")
        
        return messages_by_channel
    
    async def backup_bans(self, guild: discord.Guild) -> List[Dict[str, Any]]:

        bans = []
        try:
            async for ban_entry in guild.bans():
                ban_data = {
                    "user_id": ban_entry.user.id,
                    "user_name": ban_entry.user.name,
                    "reason": ban_entry.reason
                }
                bans.append(ban_data)
        except discord.Forbidden:
            logger.warning(f"No permission to view bans in {guild.name}")
        except Exception as e:
            logger.error(f"Error backing up bans in {guild.name}: {e}")
        
        return bans
    
    async def create_full_backup(self, guild: discord.Guild, include_messages: bool = True, message_limit: int = 100) -> Dict[str, Any]:

        backup_data = {
            "backup_version": "1.0",
            "backup_date": datetime.datetime.now().isoformat(),
            "guild_id": guild.id,
            "server_settings": await self.backup_server_settings(guild),
            "roles": await self.backup_roles(guild),
            "channels": await self.backup_channels(guild),
            "emojis": await self.backup_emojis(guild),
            "stickers": await self.backup_stickers(guild),
            "bans": await self.backup_bans(guild)
        }
        
        if include_messages:
            backup_data["messages"] = await self.backup_messages(guild, limit=message_limit)
        
        return backup_data
    
    async def save_backup_to_file(self, backup_data: Dict[str, Any], guild_id: int) -> str:

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(self.backup_path, str(guild_id))
        
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        backup_file = os.path.join(backup_dir, f"backup_{timestamp}.json")
        
        
        
        attachments_dir = os.path.join(backup_dir, f"attachments_{timestamp}")
        if not os.path.exists(attachments_dir):
            os.makedirs(attachments_dir)
        
        
        if "messages" in backup_data:
            for channel_id, messages in backup_data["messages"].items():
                channel_dir = os.path.join(attachments_dir, str(channel_id))
                
                for i, message in enumerate(messages):
                    if message["attachments"]:
                        if not os.path.exists(channel_dir):
                            os.makedirs(channel_dir)
                        
                        for j, attachment in enumerate(message["attachments"]):
                            file_data = bytes.fromhex(attachment["data"])
                            file_path = os.path.join(channel_dir, f"{message['id']}_{j}_{attachment['filename']}")
                            
                            with open(file_path, "wb") as f:
                                f.write(file_data)
                            
                            
                            attachment["data"] = file_path
        
        
        emoji_dir = os.path.join(backup_dir, f"emojis_{timestamp}")
        if not os.path.exists(emoji_dir):
            os.makedirs(emoji_dir)
            
        for emoji in backup_data["emojis"]:
            if emoji["image"]:
                emoji_data = bytes.fromhex(emoji["image"])
                file_path = os.path.join(emoji_dir, f"{emoji['id']}.png")
                
                with open(file_path, "wb") as f:
                    f.write(emoji_data)
                
                
                emoji["image"] = file_path
        
        
        sticker_dir = os.path.join(backup_dir, f"stickers_{timestamp}")
        if not os.path.exists(sticker_dir):
            os.makedirs(sticker_dir)
            
        for sticker in backup_data["stickers"]:
            if sticker["image"]:
                sticker_data = bytes.fromhex(sticker["image"])
                file_path = os.path.join(sticker_dir, f"{sticker['id']}.png")
                
                with open(file_path, "wb") as f:
                    f.write(sticker_data)
                
                
                sticker["image"] = file_path
        
        
        server_assets_dir = os.path.join(backup_dir, f"server_assets_{timestamp}")
        if not os.path.exists(server_assets_dir):
            os.makedirs(server_assets_dir)
        
        server_settings = backup_data["server_settings"]
        for asset_type in ["icon_url", "banner_url", "splash_url", "discovery_splash_url"]:
            if server_settings.get(asset_type):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(server_settings[asset_type]) as resp:
                            if resp.status == 200:
                                asset_data = await resp.read()
                                file_path = os.path.join(server_assets_dir, f"{asset_type}.png")
                                
                                with open(file_path, "wb") as f:
                                    f.write(asset_data)
                                
                                
                                server_settings[asset_type] = file_path
                except Exception as e:
                    logger.error(f"Error saving server asset {asset_type}: {e}")
        
        
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=4)
        
        
        metadata = {
            "backup_date": backup_data["backup_date"],
            "guild_id": backup_data["guild_id"],
            "guild_name": backup_data["server_settings"]["name"],
            "roles_count": len(backup_data["roles"]),
            "channels_count": len(backup_data["channels"]),
            "emojis_count": len(backup_data["emojis"]),
            "stickers_count": len(backup_data["stickers"]),
            "bans_count": len(backup_data["bans"]),
            "messages_count": sum(len(messages) for messages in backup_data.get("messages", {}).values()),
            "backup_file": backup_file,
            "attachments_dir": attachments_dir if "messages" in backup_data else None,
            "emoji_dir": emoji_dir,
            "sticker_dir": sticker_dir,
            "server_assets_dir": server_assets_dir
        }
        
        metadata_file = os.path.join(backup_dir, f"metadata_{timestamp}.json")
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
        
        return metadata_file
    
    async def load_backup_from_file(self, backup_file: str) -> Dict[str, Any]:

        try:
            with open(backup_file, "r", encoding="utf-8") as f:
                backup_data = json.load(f)
            
            
            if "messages" in backup_data:
                for channel_id, messages in backup_data["messages"].items():
                    for message in messages:
                        if "attachments" in message and message["attachments"]:
                            for attachment in message["attachments"]:
                                if "data" in attachment and attachment["data"] and os.path.isfile(attachment["data"]):
                                    try:
                                        with open(attachment["data"], "rb") as f:
                                            attachment["data"] = f.read().hex()
                                    except Exception as e:
                                        logger.error(f"Error loading attachment: {e}")
                                        attachment["data"] = None
            
            
            if "emojis" in backup_data:
                for emoji in backup_data["emojis"]:
                    if "image" in emoji and emoji["image"] and os.path.isfile(emoji["image"]):
                        try:
                            with open(emoji["image"], "rb") as f:
                                emoji["image"] = f.read().hex()
                        except Exception as e:
                            logger.error(f"Error loading emoji image: {e}")
                            emoji["image"] = None
            
            
            if "stickers" in backup_data:
                for sticker in backup_data["stickers"]:
                    if "image" in sticker and sticker["image"] and os.path.isfile(sticker["image"]):
                        try:
                            with open(sticker["image"], "rb") as f:
                                sticker["image"] = f.read().hex()
                        except Exception as e:
                            logger.error(f"Error loading sticker image: {e}")
                            sticker["image"] = None
            
            
            if "server_settings" in backup_data:
                server_settings = backup_data["server_settings"]
                for asset_type in ["icon_url", "banner_url", "splash_url", "discovery_splash_url"]:
                    if asset_type in server_settings and server_settings[asset_type] and os.path.isfile(server_settings[asset_type]):
                        try:
                            with open(server_settings[asset_type], "rb") as f:
                                server_settings[asset_type + "_data"] = f.read().hex()
                        except Exception as e:
                            logger.error(f"Error loading server asset {asset_type}: {e}")
                            server_settings[asset_type + "_data"] = None
            
            return backup_data
        
        except Exception as e:
            logger.error(f"Error loading backup file: {traceback.format_exc()}")
            raise Exception(f"Failed to load backup file: {str(e)}")

    
    async def restore_roles(self, guild: discord.Guild, roles_data: List[Dict[str, Any]]) -> Dict[int, discord.Role]:

        role_id_map = {}  
        
        
        for role in guild.roles:
            if not role.is_default() and not role.managed:
                try:
                    await role.delete(reason="Restoring from backup")
                    await asyncio.sleep(1)  
                except discord.HTTPException as e:
                    logger.error(f"Error deleting role {role.name}: {e}")
        
        
        for role_data in roles_data:
            try:
                
                if role_data["managed"]:
                    continue
                
                
                role_icon = None
                if role_data["icon"]:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(role_data["icon"]) as resp:
                            if resp.status == 200:
                                role_icon = await resp.read()
                
                new_role = await guild.create_role(
                    name=role_data["name"],
                    permissions=discord.Permissions(role_data["permissions"]),
                    color=discord.Color(role_data["color"]),
                    hoist=role_data["hoist"],
                    mentionable=role_data["mentionable"],
                    display_icon=role_icon,
                    reason="Restoring from backup"
                )
                
                
                role_id_map[role_data["id"]] = new_role
                await asyncio.sleep(1)  
                
            except discord.HTTPException as e:
                logger.error(f"Error creating role {role_data['name']}: {e}")
        
        
        positions = {role_id_map[role_data["id"]]: role_data["position"] 
                    for role_data in roles_data if role_data["id"] in role_id_map}
        
        if positions:
            try:
                await guild.edit_role_positions(positions=positions)
            except discord.HTTPException as e:
                logger.error(f"Error updating role positions: {e}")
        
        return role_id_map
    
    async def restore_channels(self, guild: discord.Guild, channels_data: List[Dict[str, Any]]) -> Dict[int, discord.abc.GuildChannel]:

        
        channel_map = {}
        
        
        categories = sorted([c for c in channels_data if c["type"] == "category"], key=lambda c: c["position"])
        text_channels = sorted([c for c in channels_data if c["type"] == "text"], key=lambda c: c["position"])
        voice_channels = sorted([c for c in channels_data if c["type"] == "voice"], key=lambda c: c["position"])
        forum_channels = sorted([c for c in channels_data if c["type"] == "forum"], key=lambda c: c["position"])
        stage_channels = sorted([c for c in channels_data if c["type"] == "stage"], key=lambda c: c["position"])
        threads = [c for c in channels_data if c["type"] == "thread"]
        
        
        for category_data in categories:
            try:
                
                overwrites = await self.create_permission_overwrites(guild, category_data["overwrites"])
                
                
                category = await guild.create_category(
                    name=category_data["name"],
                    overwrites=overwrites,
                    position=category_data["position"],
                    reason="Restoring from backup"
                )
                
                
                channel_map[category_data["original_id"]] = category
                
                logger.info(f"Restored category {category.name}")
                
            except Exception as e:
                logger.error(f"Error restoring category {category_data['name']}: {e}")
        
        
        for channel_data in text_channels:
            try:
                
                category = None
                if channel_data.get("category_id") and channel_data["category_id"] in channel_map:
                    category = channel_map[channel_data["category_id"]]
                
                
                overwrites = await self.create_permission_overwrites(guild, channel_data["overwrites"])
                
                
                channel = await guild.create_text_channel(
                    name=channel_data["name"],
                    topic=channel_data.get("topic"),
                    position=channel_data["position"],
                    nsfw=channel_data.get("nsfw", False),
                    slowmode_delay=channel_data.get("rate_limit_per_user", 0),
                    category=category,
                    overwrites=overwrites,
                    default_auto_archive_duration=channel_data.get("default_auto_archive_duration", 1440),
                    reason="Restoring from backup"
                )
                
                
                channel_map[channel_data["original_id"]] = channel
                
                logger.info(f"Restored text channel {channel.name}")
                
            except Exception as e:
                logger.error(f"Error restoring text channel {channel_data['name']}: {e}")
        
        
        for channel_data in voice_channels:
            try:
                
                category = None
                if channel_data.get("category_id") and channel_data["category_id"] in channel_map:
                    category = channel_map[channel_data["category_id"]]
                
                
                overwrites = await self.create_permission_overwrites(guild, channel_data["overwrites"])
                
                
                channel = await guild.create_voice_channel(
                    name=channel_data["name"],
                    bitrate=min(channel_data.get("bitrate", 64000), guild.bitrate_limit),
                    user_limit=channel_data.get("user_limit", 0),
                    position=channel_data["position"],
                    category=category,
                    overwrites=overwrites,
                    reason="Restoring from backup"
                )
                
                
                channel_map[channel_data["original_id"]] = channel
                
                logger.info(f"Restored voice channel {channel.name}")
                
            except Exception as e:
                logger.error(f"Error restoring voice channel {channel_data['name']}: {e}")
        
        
        for channel_data in forum_channels:
            try:
                
                category = None
                if channel_data.get("category_id") and channel_data["category_id"] in channel_map:
                    category = channel_map[channel_data["category_id"]]
                
                
                overwrites = await self.create_permission_overwrites(guild, channel_data["overwrites"])
                
                
                channel = await guild.create_forum(
                    name=channel_data["name"],
                    topic=channel_data.get("topic"),
                    position=channel_data["position"],
                    nsfw=channel_data.get("nsfw", False),
                    slowmode_delay=channel_data.get("rate_limit_per_user", 0),
                    category=category,
                    overwrites=overwrites,
                    reason="Restoring from backup"
                )
                
                
                channel_map[channel_data["original_id"]] = channel
                
                logger.info(f"Restored forum channel {channel.name}")
                
            except Exception as e:
                logger.error(f"Error restoring forum channel {channel_data['name']}: {e}")
        
        
        for channel_data in stage_channels:
            try:
                
                category = None
                if channel_data.get("category_id") and channel_data["category_id"] in channel_map:
                    category = channel_map[channel_data["category_id"]]
                
                
                overwrites = await self.create_permission_overwrites(guild, channel_data["overwrites"])
                
                
                channel = await guild.create_stage_channel(
                    name=channel_data["name"],
                    topic=channel_data.get("topic"),
                    position=channel_data["position"],
                    category=category,
                    overwrites=overwrites,
                    reason="Restoring from backup"
                )
                
                
                channel_map[channel_data["original_id"]] = channel
                
                logger.info(f"Restored stage channel {channel.name}")
                
            except Exception as e:
                logger.error(f"Error restoring stage channel {channel_data['name']}: {e}")
        
        
        for thread_data in threads:
            try:
                
                if thread_data.get("parent_id") and thread_data["parent_id"] in channel_map:
                    parent = channel_map[thread_data["parent_id"]]
                    
                    
                    thread = await parent.create_thread(
                        name=thread_data["name"],
                        auto_archive_duration=thread_data.get("auto_archive_duration", 1440),
                        slowmode_delay=thread_data.get("slowmode_delay", 0),
                        reason="Restoring from backup"
                    )
                    
                    
                    channel_map[thread_data["original_id"]] = thread
                    
                    logger.info(f"Restored thread {thread.name}")
            except Exception as e:
                logger.error(f"Error restoring thread {thread_data['name']}: {e}")
        
        return channel_map
    
    async def create_permission_overwrites(self, guild: discord.Guild, overwrites_data: List[Dict[str, Any]]) -> Dict[Union[discord.Role, discord.Member], discord.PermissionOverwrite]:

        result = {}
        
        for overwrite_data in overwrites_data:
            
            target = None
            
            if overwrite_data["type"] == "role":
                
                target = discord.utils.get(guild.roles, name=overwrite_data["name"])
                
                
                if not target and overwrite_data["name"] == "@everyone":
                    target = guild.default_role
            
            elif overwrite_data["type"] == "member":
                
                try:
                    target = await guild.fetch_member(int(overwrite_data["id"]))
                except:
                    
                    continue
            
            
            if not target:
                continue
            
            
            permissions = discord.PermissionOverwrite()
            
            
            for perm_name, perm_value in overwrite_data["permissions"].items():
                if perm_value is not None:  
                    setattr(permissions, perm_name, perm_value)
            
            result[target] = permissions
        
        return result

    async def restore_server_settings(self, guild: discord.Guild, settings_data: Dict[str, Any]):

        try:
            
            settings = {}
            
            
            if "name" in settings_data:
                settings["name"] = settings_data["name"]
            
            if "description" in settings_data:
                settings["description"] = settings_data["description"]
            
            if "region" in settings_data:
                settings["region"] = settings_data["region"]
            
            if "afk_timeout" in settings_data:
                settings["afk_timeout"] = settings_data["afk_timeout"]
            
            if "verification_level" in settings_data:
                settings["verification_level"] = discord.VerificationLevel(settings_data["verification_level"])
            
            if "default_notifications" in settings_data:
                settings["default_notifications"] = discord.NotificationLevel(settings_data["default_notifications"])
            
            if "explicit_content_filter" in settings_data:
                settings["explicit_content_filter"] = discord.ContentFilter(settings_data["explicit_content_filter"])
            
            
            if "preferred_locale" in settings_data:
                
                locale = settings_data["preferred_locale"]
                if isinstance(locale, list):
                    
                    if len(locale) > 1:
                        locale = locale[1]
                    else:
                        locale = locale[0]
                
                
                try:
                    
                    settings["preferred_locale"] = locale
                except:
                    
                    settings["preferred_locale"] = "en-US"
            
            
            if "system_channel_id" in settings_data and settings_data["system_channel_id"]:
                
                system_channel_name = settings_data.get("system_channel_name")
                if system_channel_name:
                    system_channel = discord.utils.get(guild.text_channels, name=system_channel_name)
                    if system_channel:
                        settings["system_channel"] = system_channel
            
            if "system_channel_flags" in settings_data:
                flags = discord.SystemChannelFlags()
                flag_data = settings_data["system_channel_flags"]
                
                
                if isinstance(flag_data, dict):
                    for flag_name, flag_value in flag_data.items():
                        if hasattr(flags, flag_name):
                            setattr(flags, flag_name, flag_value)
                    
                    settings["system_channel_flags"] = flags
            
            
            if "rules_channel_id" in settings_data and settings_data["rules_channel_id"]:
                
                rules_channel_name = settings_data.get("rules_channel_name")
                if rules_channel_name:
                    rules_channel = discord.utils.get(guild.text_channels, name=rules_channel_name)
                    if rules_channel:
                        settings["rules_channel"] = rules_channel
            
            
            if "public_updates_channel_id" in settings_data and settings_data["public_updates_channel_id"]:
                
                public_updates_channel_name = settings_data.get("public_updates_channel_name")
                if public_updates_channel_name:
                    public_updates_channel = discord.utils.get(guild.text_channels, name=public_updates_channel_name)
                    if public_updates_channel:
                        settings["public_updates_channel"] = public_updates_channel
            
            
            if "afk_channel_id" in settings_data and settings_data["afk_channel_id"]:
                
                afk_channel_name = settings_data.get("afk_channel_name")
                if afk_channel_name:
                    afk_channel = discord.utils.get(guild.voice_channels, name=afk_channel_name)
                    if afk_channel:
                        settings["afk_channel"] = afk_channel
            
            
            await guild.edit(
                reason="Restoring server settings from backup",
                **settings
            )
            
            logger.info(f"Restored server settings for {guild.name}")
            
        except Exception as e:
            logger.error(f"Error restoring server settings: {traceback.format_exc()}")
            raise Exception(f"Failed to restore server settings: {str(e)}")

    
    async def restore_emojis(self, guild: discord.Guild, emojis_data: List[Dict[str, Any]]) -> None:

        
        for emoji in guild.emojis:
            try:
                await emoji.delete(reason="Restoring from backup")
                await asyncio.sleep(1)  
            except discord.HTTPException as e:
                logger.error(f"Error deleting emoji {emoji.name}: {e}")
        
        
        for emoji_data in emojis_data:
            try:
                
                if not emoji_data.get("image"):
                    continue
                
                
                roles = []
                for role_id in emoji_data["roles"]:
                    role = guild.get_role(role_id)
                    if role:
                        roles.append(role)
                
                
                image_data = bytes.fromhex(emoji_data["image"])
                await guild.create_custom_emoji(
                    name=emoji_data["name"],
                    image=image_data,
                    roles=roles,
                    reason="Restoring from backup"
                )
                
                await asyncio.sleep(1)  
                
            except discord.HTTPException as e:
                logger.error(f"Error creating emoji {emoji_data['name']}: {e}")
    
    async def restore_stickers(self, guild: discord.Guild, stickers_data: List[Dict[str, Any]]) -> None:

        
        for sticker in guild.stickers:
            try:
                await sticker.delete(reason="Restoring from backup")
                await asyncio.sleep(1)  
            except discord.HTTPException as e:
                logger.error(f"Error deleting sticker {sticker.name}: {e}")
        
        
        for sticker_data in stickers_data:
            try:
                
                if not sticker_data.get("image"):
                    continue
                
                
                image_data = bytes.fromhex(sticker_data["image"])
                await guild.create_sticker(
                    name=sticker_data["name"],
                    description=sticker_data["description"],
                    emoji=sticker_data["emoji"],
                    file=discord.File(io.BytesIO(image_data), filename="sticker.png"),
                    reason="Restoring from backup"
                )
                
                await asyncio.sleep(1)  
                
            except discord.HTTPException as e:
                logger.error(f"Error creating sticker {sticker_data['name']}: {e}")
    
    async def restore_bans(self, guild: discord.Guild, bans_data: List[Dict[str, Any]]) -> None:

        
        current_bans = {}
        try:
            async for ban_entry in guild.bans():
                current_bans[ban_entry.user.id] = ban_entry
        except discord.Forbidden:
            logger.warning(f"No permission to view bans in {guild.name}")
            return
        
        
        for ban_data in bans_data:
            try:
                
                if ban_data["user_id"] in current_bans:
                    continue
                
                
                await guild.ban(
                    discord.Object(id=ban_data["user_id"]),
                    reason=ban_data["reason"] or "Restoring from backup",
                    delete_message_days=0
                )
                
                await asyncio.sleep(1)  
                
            except discord.HTTPException as e:
                logger.error(f"Error banning user {ban_data['user_name']} ({ban_data['user_id']}): {e}")
    
    async def restore_messages(self, guild: discord.Guild, messages_data: Dict[str, List[Dict[str, Any]]], channel_map: Dict[int, discord.abc.GuildChannel]):

        webhook_cache = {}
        
        
        for original_channel_id, messages in messages_data.items():
            
            if int(original_channel_id) in channel_map:
                channel = channel_map[int(original_channel_id)]
                
                
                if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel, discord.ForumChannel)):
                    continue
                    
                try:
                    
                    if channel.id not in webhook_cache:
                        try:
                            
                            webhooks = await channel.webhooks()
                            webhook = next((w for w in webhooks if w.user.id == self.bot.user.id), None)
                            
                            if not webhook:
                                webhook = await channel.create_webhook(name="ZBackup Message Restoration")
                            
                            webhook_cache[channel.id] = webhook
                        except Exception as e:
                            logger.error(f"Error creating webhook for channel {channel.name}: {e}")
                            continue
                    
                    webhook = webhook_cache[channel.id]
                    
                    
                    sorted_messages = []
                    for message_data in messages:
                        
                        if "timestamp" in message_data:
                            timestamp_key = "timestamp"
                        elif "created_at" in message_data:
                            timestamp_key = "created_at"
                        else:
                            
                            sorted_messages = messages
                            break
                    
                    if not sorted_messages:  
                        sorted_messages = sorted(messages, key=lambda m: datetime.datetime.fromisoformat(m[timestamp_key]))
                    
                    
                    messages_by_author = {}
                    for message_data in sorted_messages:
                        
                        if isinstance(message_data.get("author"), dict):
                            author_id = message_data["author"]["id"]
                        else:
                            author_id = message_data.get("author_id", "unknown")
                        
                        if author_id not in messages_by_author:
                            messages_by_author[author_id] = []
                        messages_by_author[author_id].append(message_data)
                    
                    
                    for author_id, author_messages in messages_by_author.items():
                        
                        first_message = author_messages[0]
                        
                        
                        if isinstance(first_message.get("author"), dict):
                            author_data = first_message["author"]
                            author_name = author_data.get("name", "Unknown User")
                            avatar_url = author_data.get("avatar_url")
                        else:
                            author_name = first_message.get("author_name", "Unknown User")
                            avatar_url = None
                        
                        
                        batch_size = 5
                        for i in range(0, len(author_messages), batch_size):
                            batch = author_messages[i:i+batch_size]
                            
                            for message_data in batch:
                                try:
                                    
                                    content = message_data.get("content", "")
                                    if not content and not message_data.get("embeds") and not message_data.get("attachments"):
                                        content = "*Empty message*"
                                    
                                    
                                    embeds = []
                                    for embed_data in message_data.get("embeds", []):
                                        try:
                                            embed = discord.Embed.from_dict(embed_data)
                                            embeds.append(embed)
                                        except Exception as e:
                                            logger.error(f"Error creating embed: {e}")
                                    
                                    
                                    files = []
                                    for attachment in message_data.get("attachments", []):
                                        if "data" in attachment and attachment["data"]:
                                            try:
                                                file_data = bytes.fromhex(attachment["data"])
                                                file = discord.File(io.BytesIO(file_data), filename=attachment["filename"])
                                                files.append(file)
                                            except Exception as e:
                                                logger.error(f"Error creating file from attachment: {e}")
                                    
                                    
                                    await webhook.send(
                                        content=content,
                                        username=author_name,
                                        avatar_url=avatar_url,
                                        embeds=embeds,
                                        files=files,
                                        wait=True
                                    )
                                    
                                    
                                    await asyncio.sleep(0.5)
                                    
                                except Exception as e:
                                    logger.error(f"Error restoring message: {e}")
                                
                            
                            await asyncio.sleep(2)
                        
                    logger.info(f"Restored {len(messages)} messages in channel {channel.name}")
                        
                except Exception as e:
                    logger.error(f"Error restoring messages for channel {channel.name}: {traceback.format_exc()}")
            else:
                logger.warning(f"Could not find matching channel for original ID {original_channel_id}")
            
        
        for webhook in webhook_cache.values():
            try:
                await webhook.delete()
            except:
                pass
    
    async def restore_backup(self, guild: discord.Guild, backup_data: Dict[str, Any], options: Dict[str, bool]):

        
        channel_map = {}
        
        
        if options["channels"]:
            await self.clear_channels(guild)
        
        if options["roles"]:
            await self.clear_roles(guild)
        
        if options["emojis"]:
            await self.clear_emojis(guild)
        
        if options["stickers"]:
            await self.clear_stickers(guild)
        
        if options["bans"]:
            await self.clear_bans(guild)
        
        
        if options["roles"]:
            await self.restore_roles(guild, backup_data["roles"])
        
        if options["channels"]:
            
            channel_map = await self.restore_channels(guild, backup_data["channels"])
        
        if options["emojis"]:
            await self.restore_emojis(guild, backup_data["emojis"])
        
        if options["stickers"]:
            await self.restore_stickers(guild, backup_data["stickers"])
        
        if options["bans"]:
            await self.restore_bans(guild, backup_data["bans"])
        
        if options["server_settings"]:
            await self.restore_server_settings(guild, backup_data["server_settings"])
        
        if options["messages"] and "messages" in backup_data:
            await self.restore_messages(guild, backup_data["messages"], channel_map)
        
        logger.info(f"Backup restoration completed for {guild.name}")

    
    @commands.hybrid_group(name="zbackup", description="Advanced server backup and restoration system")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def zbackup(self, ctx: commands.Context):

        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="ZBackup Help",
                description="Advanced server backup and restoration system",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            
            
            embed.add_field(
                name="📥 Backup Commands",
                value=(
                    f"[] Means Optional\n"
                    f"`{ctx.prefix}zbackup create [include_messages] [message_limit]` - Create a new backup\n"
                    f"`{ctx.prefix}zbackup list` - List all available backups\n"
                    f"`{ctx.prefix}zbackup info <backup_id>` - Show detailed information about a backup\n"
                    f"`{ctx.prefix}zbackup schedule [interval] [include_messages] [message_limit] [keep_count]` - Schedule automatic backups"
                ),
                inline=False
            )
            
            embed.add_field(
                name="📤 Restoration Commands",
                value=(
                    f"`{ctx.prefix}zbackup restore <backup_id> [options]` - Restore a backup\n"
                    f"Options: roles, channels, emojis, stickers, bans, messages, server_settings"
                ),
                inline=False
            )
            
            embed.add_field(
                name="💾 Management Commands",
                value=(
                    f"`{ctx.prefix}zbackup delete <backup_id>` - Delete a backup\n"
                    f"`{ctx.prefix}zbackup export <backup_id>` - Export a backup to a file\n"
                    f"`{ctx.prefix}zbackup import` - Import a backup from a file"
                ),
                inline=False
            )
            
            embed.add_field(
                name="📋 Examples",
                value=(
                    f"`{ctx.prefix}zbackup create` - Create a full backup including messages\n"
                    f"`{ctx.prefix}zbackup create False` - Create a backup without messages\n"
                    f"`{ctx.prefix}zbackup restore abc123 channels=True roles=True messages=False` - Restore only channels and roles"
                ),
                inline=False
            )
            
            embed.set_footer(text=f"ZygnalBot On Top")
            
            await ctx.send(embed=embed)

    
    @zbackup.command(name="create", description="Create a new backup of the server")
    @app_commands.describe(
        include_messages="Whether to include messages in the backup",
        message_limit="Maximum number of messages to backup per channel"
    )
    async def create_backup(self, ctx: commands.Context, include_messages: bool = True, message_limit: int = 100):

        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        
        
        if not ctx.guild.me.guild_permissions.administrator:
            return await ctx.send("I need Administrator permission to create a complete backup.")
        
        
        if message_limit > 1000:
            message_limit = 1000
            await ctx.send("Message limit capped at 1000 messages per channel for performance reasons.")
        
        
        progress_message = await ctx.send("Creating backup... This may take a while.")
        
        try:
            
            async def update_progress(status):
                await progress_message.edit(content=f"Creating backup... {status}")
            
            
            await update_progress("Backing up server settings")
            backup_data = await self.create_full_backup(ctx.guild, include_messages, message_limit)
            
            await update_progress("Saving backup to disk")
            metadata_file = await self.save_backup_to_file(backup_data, ctx.guild.id)
            
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            
            
            embed = discord.Embed(
                title="Server Backup Created",
                description=f"Backup of **{ctx.guild.name}** has been created successfully.",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="Backup ID", value=os.path.basename(metadata_file).replace("metadata_", "").replace(".json", ""), inline=False)
            embed.add_field(name="Roles", value=str(metadata["roles_count"]), inline=True)
            embed.add_field(name="Channels", value=str(metadata["channels_count"]), inline=True)
            embed.add_field(name="Emojis", value=str(metadata["emojis_count"]), inline=True)
            embed.add_field(name="Stickers", value=str(metadata["stickers_count"]), inline=True)
            embed.add_field(name="Bans", value=str(metadata["bans_count"]), inline=True)
            
            if include_messages:
                embed.add_field(name="Messages", value=str(metadata["messages_count"]), inline=True)
            
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
            
            await progress_message.edit(content=None, embed=embed)
            
        except Exception as e:
            logger.error(f"Error creating backup: {traceback.format_exc()}")
            await progress_message.edit(content=f"Error creating backup: {str(e)}")
    
    @zbackup.command(name="list", description="List all available backups for this server")
    async def list_backups(self, ctx: commands.Context):

        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        
        backup_dir = os.path.join(self.backup_path, str(ctx.guild.id))
        
        if not os.path.exists(backup_dir):
            return await ctx.send("No backups found for this server.")
        
        
        metadata_files = [f for f in os.listdir(backup_dir) if f.startswith("metadata_") and f.endswith(".json")]
        
        if not metadata_files:
            return await ctx.send("No backups found for this server.")
        
        
        backups = []
        for metadata_file in metadata_files:
            try:
                with open(os.path.join(backup_dir, metadata_file), "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                
                backup_id = metadata_file.replace("metadata_", "").replace(".json", "")
                backup_date = datetime.datetime.fromisoformat(metadata["backup_date"])
                
                backups.append({
                    "id": backup_id,
                    "date": backup_date,
                    "metadata": metadata
                })
            except Exception as e:
                logger.error(f"Error loading metadata file {metadata_file}: {e}")
        
        
        backups.sort(key=lambda b: b["date"], reverse=True)
        
        
        embeds = []
        for i in range(0, len(backups), 5):
            embed = discord.Embed(
                title="Server Backups",
                description=f"Available backups for **{ctx.guild.name}**",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            
            for backup in backups[i:i+5]:
                metadata = backup["metadata"]
                channels_count = metadata.get("channels_count", "N/A")
                roles_count = metadata.get("roles_count", "N/A")
                messages_count = metadata.get("messages_count", "N/A")
                
                embed.add_field(
                    name=f"Backup {backup['id']}",
                    value=f"**Date:** {backup['date'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                          f"**Channels:** {channels_count}\n"
                          f"**Roles:** {roles_count}\n"
                          f"**Messages:** {messages_count}",
                    inline=False
                )
            
            embed.set_footer(text=f"Page {i//5 + 1}/{(len(backups)+4)//5} • Use 'zbackup info <id>' for details")
            embeds.append(embed)
        
        if not embeds:
            return await ctx.send("No valid backups found for this server.")
        
        
        current_page = 0
        message = await ctx.send(embed=embeds[current_page])
        
        
        if len(embeds) > 1:
            await message.add_reaction("⬅️")
            await message.add_reaction("➡️")
            
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["⬅️", "➡️"] and reaction.message.id == message.id
            
            while True:
                try:
                    reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
                    
                    if str(reaction.emoji) == "➡️" and current_page < len(embeds) - 1:
                        current_page += 1
                        await message.edit(embed=embeds[current_page])
                        await message.remove_reaction(reaction, user)
                    
                    elif str(reaction.emoji) == "⬅️" and current_page > 0:
                        current_page -= 1
                        await message.edit(embed=embeds[current_page])
                        await message.remove_reaction(reaction, user)
                    
                    else:
                        await message.remove_reaction(reaction, user)
                
                except asyncio.TimeoutError:
                    await message.clear_reactions()
                    break
    
    @zbackup.command(name="info", description="Show detailed information about a specific backup")
    @app_commands.describe(backup_id="The ID of the backup to show information for")
    async def backup_info(self, ctx: commands.Context, backup_id: str):

        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        
        backup_dir = os.path.join(self.backup_path, str(ctx.guild.id))
        metadata_file = os.path.join(backup_dir, f"metadata_{backup_id}.json")
        
        if not os.path.exists(metadata_file):
            return await ctx.send(f"Backup with ID `{backup_id}` not found.")
        
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            backup_date = datetime.datetime.fromisoformat(metadata["backup_date"])
            
            embed = discord.Embed(
                title=f"Backup Information: {backup_id}",
                description=f"Detailed information about backup `{backup_id}`",
                color=discord.Color.blue(),
                timestamp=backup_date
            )
            
            embed.add_field(name="Server Name", value=metadata["guild_name"], inline=False)
            embed.add_field(name="Backup Date", value=backup_date.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
            
            embed.add_field(name="Roles", value=str(metadata["roles_count"]), inline=True)
            embed.add_field(name="Channels", value=str(metadata["channels_count"]), inline=True)
            embed.add_field(name="Emojis", value=str(metadata["emojis_count"]), inline=True)
            embed.add_field(name="Stickers", value=str(metadata["stickers_count"]), inline=True)
            embed.add_field(name="Bans", value=str(metadata["bans_count"]), inline=True)
            
            if "messages_count" in metadata:
                embed.add_field(name="Messages", value=str(metadata["messages_count"]), inline=True)
            
            
            backup_size = 0
            backup_file = metadata.get("backup_file")
            if backup_file and os.path.exists(backup_file):
                backup_size += os.path.getsize(backup_file)
            
            
            for dir_key in ["attachments_dir", "emoji_dir", "sticker_dir", "server_assets_dir"]:
                if dir_key in metadata and metadata[dir_key] and os.path.exists(metadata[dir_key]):
                    for root, dirs, files in os.walk(metadata[dir_key]):
                        for file in files:
                            backup_size += os.path.getsize(os.path.join(root, file))
            
            
            if backup_size < 1024:
                size_str = f"{backup_size} B"
            elif backup_size < 1024 * 1024:
                size_str = f"{backup_size / 1024:.2f} KB"
            elif backup_size < 1024 * 1024 * 1024:
                size_str = f"{backup_size / (1024 * 1024):.2f} MB"
            else:
                size_str = f"{backup_size / (1024 * 1024 * 1024):.2f} GB"
            
            embed.add_field(name="Backup Size", value=size_str, inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing backup info: {traceback.format_exc()}")
            await ctx.send(f"Error showing backup info: {str(e)}")
    
    @zbackup.command(name="delete", description="Delete a backup")
    @app_commands.describe(backup_id="The ID of the backup to delete")
    async def delete_backup(self, ctx: commands.Context, backup_id: str):

        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        
        backup_dir = os.path.join(self.backup_path, str(ctx.guild.id))
        metadata_file = os.path.join(backup_dir, f"metadata_{backup_id}.json")
        
        if not os.path.exists(metadata_file):
            return await ctx.send(f"Backup with ID `{backup_id}` not found.")
        
        
        confirm_message = await ctx.send(f"Are you sure you want to delete backup `{backup_id}`? This action cannot be undone. React with ✅ to confirm or ❌ to cancel.")
        await confirm_message.add_reaction("✅")
        await confirm_message.add_reaction("❌")
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_message.id
        
        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
            
            if str(reaction.emoji) == "✅":
                try:
                    
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                    
                    
                    backup_file = metadata.get("backup_file")
                    if backup_file and os.path.exists(backup_file):
                        os.remove(backup_file)
                    
                    
                    for dir_key in ["attachments_dir", "emoji_dir", "sticker_dir", "server_assets_dir"]:
                        if dir_key in metadata and metadata[dir_key] and os.path.exists(metadata[dir_key]):
                            for root, dirs, files in os.walk(metadata[dir_key], topdown=False):
                                for file in files:
                                    os.remove(os.path.join(root, file))
                                for dir in dirs:
                                    os.rmdir(os.path.join(root, dir))
                            os.rmdir(metadata[dir_key])
                    
                    
                    os.remove(metadata_file)
                    
                    await confirm_message.edit(content=f"Backup `{backup_id}` has been deleted successfully.")
                    
                except Exception as e:
                    logger.error(f"Error deleting backup: {traceback.format_exc()}")
                    await confirm_message.edit(content=f"Error deleting backup: {str(e)}")
            
            else:
                await confirm_message.edit(content="Backup deletion cancelled.")
            
            await confirm_message.clear_reactions()
            
        except asyncio.TimeoutError:
            await confirm_message.edit(content="Backup deletion cancelled due to timeout.")
            await confirm_message.clear_reactions()
    
    @zbackup.command(name="restore", description="Restore a backup to the server")
    @app_commands.describe(
        backup_id="The ID of the backup to restore",
        roles="Whether to restore roles",
        channels="Whether to restore channels",
        emojis="Whether to restore emojis",
        stickers="Whether to restore stickers",
        bans="Whether to restore bans",
        messages="Whether to restore messages",
        server_settings="Whether to restore server settings"
    )
    async def restore_backup_cmd(
        self, ctx: commands.Context, 
        backup_id: str,
        roles: bool = True,
        channels: bool = True,
        emojis: bool = True,
        stickers: bool = True,
        bans: bool = True,
        messages: bool = True,
        server_settings: bool = True
    ):

        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        
        
        if not ctx.author.guild_permissions.administrator:
            return await ctx.send("You need Administrator permission to restore a backup.")
        
        
        if not ctx.guild.me.guild_permissions.administrator:
            return await ctx.send("I need Administrator permission to restore a backup.")
        
        backup_dir = os.path.join(self.backup_path, str(ctx.guild.id))
        backup_file = os.path.join(backup_dir, f"backup_{backup_id}.json")
        
        if not os.path.exists(backup_file):
            return await ctx.send(f"Backup with ID `{backup_id}` not found.")
        
        
        warning_embed = discord.Embed(
            title="⚠️ Backup Restoration Warning",
            description="Restoring a backup will overwrite data on this server. This action cannot be undone.",
            color=discord.Color.yellow(),
            timestamp=datetime.datetime.now()
        )
        
        warning_embed.add_field(
            name="The following will be affected:",
            value="\n".join([
                f"✅ Roles: {roles}",
                f"✅ Channels: {channels}",
                f"✅ Emojis: {emojis}",
                f"✅ Stickers: {stickers}",
                f"✅ Bans: {bans}",
                f"✅ Messages: {messages}",
                f"✅ Server Settings: {server_settings}"
            ]),
            inline=False
        )
        
        warning_embed.add_field(
            name="Confirmation Required",
            value="Please type `confirm` to proceed with the restoration or `cancel` to abort.",
            inline=False
        )
        
        warning_embed.set_footer(text="This operation will timeout in 60 seconds.")
        
        confirmation_message = await ctx.send(embed=warning_embed)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["confirm", "cancel"]
        
        try:
            response = await self.bot.wait_for("message", timeout=60.0, check=check)
            
            if response.content.lower() == "cancel":
                return await ctx.send("Backup restoration cancelled.")
            
            
            progress_message = await ctx.send("Restoring backup... This may take a while.")
            
            try:
                
                channel_id = ctx.channel.id
                guild_id = ctx.guild.id
                
                
                async def update_progress(status):
                    nonlocal progress_message, channel_id  
                    try:
                        
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            
                            try:
                                await progress_message.edit(content=f"Restoring backup... {status}")
                            except discord.NotFound:
                                
                                progress_message = await channel.send(f"Restoring backup... {status}")
                        else:
                            
                            guild = self.bot.get_guild(guild_id)
                            if guild and guild.system_channel:
                                try:
                                    progress_message = await guild.system_channel.send(f"Restoring backup... {status}")
                                    channel_id = guild.system_channel.id  
                                except Exception:
                                    pass
                    except Exception as e:
                        logger.error(f"Error updating progress: {e}")
                
                
                await update_progress("Loading backup data")
                backup_data = await self.load_backup_from_file(backup_file)
                
                
                options = {
                    "roles": roles,
                    "channels": channels,
                    "emojis": emojis,
                    "stickers": stickers,
                    "bans": bans,
                    "messages": messages,
                    "server_settings": server_settings
                }
                
                
                await update_progress("Starting restoration process")
                await self.restore_backup(ctx.guild, backup_data, options)
                
                
                success_embed = discord.Embed(
                    title="Backup Restoration Complete",
                    description=f"Backup `{backup_id}` has been successfully restored to this server.",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.now()
                )
                
                success_embed.add_field(
                    name="Restored Components",
                    value="\n".join([
                        f"✅ Roles: {roles}",
                        f"✅ Channels: {channels}",
                        f"✅ Emojis: {emojis}",
                        f"✅ Stickers: {stickers}",
                        f"✅ Bans: {bans}",
                        f"✅ Messages: {messages}",
                        f"✅ Server Settings: {server_settings}"
                    ]),
                    inline=False
                )
                
                success_embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
                
                
                try:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        await channel.send(embed=success_embed)
                    else:
                        
                        guild = self.bot.get_guild(guild_id)
                        if guild and guild.system_channel:
                            await guild.system_channel.send(embed=success_embed)
                except Exception as e:
                    logger.error(f"Error sending success message: {e}")
                
            except Exception as e:
                logger.error(f"Error restoring backup: {traceback.format_exc()}")
                error_message = f"Error restoring backup: {str(e)}"
                
                
                try:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        await channel.send(error_message)
                    else:
                        
                        guild = self.bot.get_guild(guild_id)
                        if guild and guild.system_channel:
                            await guild.system_channel.send(error_message)
                except Exception as e:
                    logger.error(f"Error sending error message: {e}")
                
        except asyncio.TimeoutError:
            await ctx.send("Backup restoration cancelled due to timeout.")





    
    @zbackup.command(name="export", description="Export a backup to a file that can be downloaded")
    @app_commands.describe(backup_id="The ID of the backup to export")
    async def export_backup(self, ctx: commands.Context, backup_id: str):

        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        
        backup_dir = os.path.join(self.backup_path, str(ctx.guild.id))
        backup_file = os.path.join(backup_dir, f"backup_{backup_id}.json")
        metadata_file = os.path.join(backup_dir, f"metadata_{backup_id}.json")
        
        if not os.path.exists(backup_file) or not os.path.exists(metadata_file):
            return await ctx.send(f"Backup with ID `{backup_id}` not found.")
        
        
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        
        export_filename = f"zbackup_{ctx.guild.name.replace(' ', '_')}_{backup_id}.zip"
        export_path = os.path.join(backup_dir, export_filename)
        
        progress_message = await ctx.send("Preparing backup for export... This may take a while.")
        
        try:
            import zipfile
            
            with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                
                zipf.write(backup_file, os.path.basename(backup_file))
                
                
                zipf.write(metadata_file, os.path.basename(metadata_file))
                
                
                for dir_key in ["attachments_dir", "emoji_dir", "sticker_dir", "server_assets_dir"]:
                    if dir_key in metadata and metadata[dir_key] and os.path.exists(metadata[dir_key]):
                        dir_path = metadata[dir_key]
                        for root, dirs, files in os.walk(dir_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                zipf.write(file_path, os.path.relpath(file_path, backup_dir))
            
            
            file_size = os.path.getsize(export_path)
            
            if file_size > 8 * 1024 * 1024:  
                await progress_message.edit(content=f"The backup export is too large to send via Discord ({file_size / (1024 * 1024):.2f} MB). Please access it directly on the server at `{export_path}`.")
            else:
                await progress_message.edit(content="Backup exported successfully. Uploading file...")
                await ctx.send(file=discord.File(export_path, filename=export_filename))
                await progress_message.edit(content="Backup exported and uploaded successfully.")
        
        except Exception as e:
            logger.error(f"Error exporting backup: {traceback.format_exc()}")
            await progress_message.edit(content=f"Error exporting backup: {str(e)}")
        
        
        try:
            os.remove(export_path)
        except:
            pass
    
    @zbackup.command(name="import", description="Import a backup from a file")
    async def import_backup(self, ctx: commands.Context):

        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        
        await ctx.send("Please upload the backup zip file. You have 60 seconds to upload the file.")
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and len(m.attachments) > 0
        
        try:
            response = await self.bot.wait_for("message", timeout=60.0, check=check)
            
            if not response.attachments:
                return await ctx.send("No file uploaded. Import cancelled.")
            
            attachment = response.attachments[0]
            
            if not attachment.filename.endswith(".zip"):
                return await ctx.send("The uploaded file must be a zip file. Import cancelled.")
            
            progress_message = await ctx.send("Downloading and processing backup file... This may take a while.")
            
            try:
                import zipfile
                import tempfile
                
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    
                    zip_path = os.path.join(temp_dir, attachment.filename)
                    await attachment.save(zip_path)
                    
                    
                    with zipfile.ZipFile(zip_path, 'r') as zipf:
                        zipf.extractall(temp_dir)
                    
                    
                    backup_file = None
                    metadata_file = None
                    
                    for file in os.listdir(temp_dir):
                        if file.startswith("backup_") and file.endswith(".json"):
                            backup_file = os.path.join(temp_dir, file)
                        elif file.startswith("metadata_") and file.endswith(".json"):
                            metadata_file = os.path.join(temp_dir, file)
                    
                    if not backup_file or not metadata_file:
                        return await progress_message.edit(content="Invalid backup file. Could not find backup or metadata files.")
                    
                    
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                    
                    
                    backup_dir = os.path.join(self.backup_path, str(ctx.guild.id))
                    if not os.path.exists(backup_dir):
                        os.makedirs(backup_dir)
                    
                    
                    backup_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    
                    new_backup_file = os.path.join(backup_dir, f"backup_{backup_id}.json")
                    new_metadata_file = os.path.join(backup_dir, f"metadata_{backup_id}.json")
                    
                    import shutil
                    shutil.copy2(backup_file, new_backup_file)
                    
                    
                    metadata["backup_file"] = new_backup_file
                    
                    
                    for dir_key in ["attachments_dir", "emoji_dir", "sticker_dir", "server_assets_dir"]:
                        if dir_key in metadata and metadata[dir_key]:
                            new_dir = os.path.join(backup_dir, f"{dir_key.split('_')[0]}_{backup_id}")
                            os.makedirs(new_dir, exist_ok=True)
                            
                            
                            old_dir = os.path.basename(metadata[dir_key])
                            old_dir_path = os.path.join(temp_dir, old_dir)
                            
                            if os.path.exists(old_dir_path):
                                for root, dirs, files in os.walk(old_dir_path):
                                    for dir_name in dirs:
                                        os.makedirs(os.path.join(new_dir, dir_name), exist_ok=True)
                                    
                                    for file in files:
                                        src_file = os.path.join(root, file)
                                        rel_path = os.path.relpath(src_file, old_dir_path)
                                        dst_file = os.path.join(new_dir, rel_path)
                                        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                                        shutil.copy2(src_file, dst_file)
                            
                            metadata[dir_key] = new_dir
                    
                    
                    with open(new_metadata_file, "w", encoding="utf-8") as f:
                        json.dump(metadata, f, ensure_ascii=False, indent=4)
                    
                    
                    embed = discord.Embed(
                        title="Backup Imported Successfully",
                        description=f"Backup has been imported with ID: `{backup_id}`",
                        color=discord.Color.green(),
                        timestamp=datetime.datetime.now()
                    )
                    
                    embed.add_field(name="Server Name", value=metadata["guild_name"], inline=False)
                    embed.add_field(name="Roles", value=str(metadata["roles_count"]), inline=True)
                    embed.add_field(name="Channels", value=str(metadata["channels_count"]), inline=True)
                    embed.add_field(name="Emojis", value=str(metadata["emojis_count"]), inline=True)
                    embed.add_field(name="Stickers", value=str(metadata["stickers_count"]), inline=True)
                    
                    if "messages_count" in metadata:
                        embed.add_field(name="Messages", value=str(metadata["messages_count"]), inline=True)
                    
                    embed.add_field(
                        name="Restore Command",
                        value=f"`{ctx.prefix}zbackup restore {backup_id}`",
                        inline=False
                    )
                    
                    await progress_message.edit(content=None, embed=embed)
            
            except Exception as e:
                logger.error(f"Error importing backup: {traceback.format_exc()}")
                await progress_message.edit(content=f"Error importing backup: {str(e)}")
        
        except asyncio.TimeoutError:
            await ctx.send("No file uploaded within the time limit. Import cancelled.")
    
    @zbackup.command(name="schedule", description="Schedule automatic backups")
    @app_commands.describe(
        interval="Backup interval in hours (0 to disable)",
        include_messages="Whether to include messages in the backup",
        message_limit="Maximum number of messages to backup per channel",
        keep_count="Number of backups to keep (0 for unlimited)"
    )
    async def schedule_backup(self, ctx: commands.Context, interval: int = 24, include_messages: bool = True, message_limit: int = 100, keep_count: int = 5):

        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        
        
        if not ctx.guild.me.guild_permissions.administrator:
            return await ctx.send("I need Administrator permission to create automatic backups.")
        
        
        if interval < 0:
            return await ctx.send("Interval must be a positive number or 0 to disable.")
        
        
        if message_limit < 0 or message_limit > 1000:
            return await ctx.send("Message limit must be between 0 and 1000.")
        
        
        if keep_count < 0:
            return await ctx.send("Keep count must be a positive number or 0 for unlimited.")
        
        
        
        config_dir = os.path.join(self.backup_path, "schedules")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        
        config_file = os.path.join(config_dir, f"{ctx.guild.id}.json")
        
        config = {
            "guild_id": ctx.guild.id,
            "interval": interval,
            "include_messages": include_messages,
            "message_limit": message_limit,
            "keep_count": keep_count,
            "last_backup": None,
            "next_backup": datetime.datetime.now().isoformat() if interval > 0 else None
        }
        
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        
        if interval > 0:
            embed = discord.Embed(
                title="Automatic Backups Scheduled",
                description=f"Automatic backups have been scheduled for this server.",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="Interval", value=f"{interval} hours", inline=True)
            embed.add_field(name="Include Messages", value=str(include_messages), inline=True)
            embed.add_field(name="Message Limit", value=str(message_limit), inline=True)
            embed.add_field(name="Keep Count", value=f"{keep_count if keep_count > 0 else 'Unlimited'}", inline=True)
            embed.add_field(name="Next Backup", value="In a few moments", inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("Automatic backups have been disabled for this server.")
    
    @tasks.loop(minutes=5.0)
    async def check_scheduled_backups(self):

        config_dir = os.path.join(self.backup_path, "schedules")
        if not os.path.exists(config_dir):
            return
        
        now = datetime.datetime.now()
        
        for config_file in os.listdir(config_dir):
            if not config_file.endswith(".json"):
                continue
            
            try:
                with open(os.path.join(config_dir, config_file), "r", encoding="utf-8") as f:
                    config = json.load(f)
                
                
                if config["interval"] <= 0 or not config["next_backup"]:
                    continue
                
                next_backup = datetime.datetime.fromisoformat(config["next_backup"])
                
                
                if now >= next_backup:
                    guild_id = int(config["guild_id"])
                    guild = self.bot.get_guild(guild_id)
                    
                    if not guild:
                        logger.warning(f"Could not find guild {guild_id} for scheduled backup")
                        continue
                    
                    
                    try:
                        logger.info(f"Creating scheduled backup for guild {guild.name} ({guild.id})")
                        
                        backup_data = await self.create_full_backup(
                            guild,
                            config["include_messages"],
                            config["message_limit"]
                        )
                        
                        metadata_file = await self.save_backup_to_file(backup_data, guild.id)
                        
                        
                        config["last_backup"] = now.isoformat()
                        
                        
                        next_backup = now + datetime.timedelta(hours=config["interval"])
                        config["next_backup"] = next_backup.isoformat()
                        
                        
                        with open(os.path.join(config_dir, config_file), "w", encoding="utf-8") as f:
                            json.dump(config, f, ensure_ascii=False, indent=4)
                        
                        
                        if config["keep_count"] > 0:
                            await self.cleanup_old_backups(guild.id, config["keep_count"])
                        
                        logger.info(f"Scheduled backup completed for guild {guild.name} ({guild.id})")
                        
                        
                        try:
                            system_channel = guild.system_channel
                            if system_channel and system_channel.permissions_for(guild.me).send_messages:
                                with open(metadata_file, "r", encoding="utf-8") as f:
                                    metadata = json.load(f)
                                
                                backup_id = os.path.basename(metadata_file).replace("metadata_", "").replace(".json", "")
                                
                                embed = discord.Embed(
                                    title="Automatic Backup Created",
                                    description=f"A scheduled backup of this server has been created.",
                                    color=discord.Color.green(),
                                    timestamp=now
                                )
                                
                                embed.add_field(name="Backup ID", value=backup_id, inline=False)
                                embed.add_field(name="Roles", value=str(metadata["roles_count"]), inline=True)
                                embed.add_field(name="Channels", value=str(metadata["channels_count"]), inline=True)
                                embed.add_field(name="Emojis", value=str(metadata["emojis_count"]), inline=True)
                                
                                if "messages_count" in metadata:
                                    embed.add_field(name="Messages", value=str(metadata["messages_count"]), inline=True)
                                
                                embed.add_field(name="Next Backup", value=next_backup.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
                                
                                await system_channel.send(embed=embed)
                        except Exception as e:
                            logger.error(f"Error notifying server about scheduled backup: {e}")
                    
                    except Exception as e:
                        logger.error(f"Error creating scheduled backup for guild {guild_id}: {traceback.format_exc()}")
            
            except Exception as e:
                logger.error(f"Error processing scheduled backup config {config_file}: {e}")
    
    @check_scheduled_backups.before_loop
    async def before_check_scheduled_backups(self):

        await self.bot.wait_until_ready()
    
    async def cleanup_old_backups(self, guild_id: int, keep_count: int):

        backup_dir = os.path.join(self.backup_path, str(guild_id))
        if not os.path.exists(backup_dir):
            return
        
        
        metadata_files = [f for f in os.listdir(backup_dir) if f.startswith("metadata_") and f.endswith(".json")]
        
        if len(metadata_files) <= keep_count:
            return
        
        
        backups = []
        for metadata_file in metadata_files:
            try:
                with open(os.path.join(backup_dir, metadata_file), "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                
                backup_id = metadata_file.replace("metadata_", "").replace(".json", "")
                backup_date = datetime.datetime.fromisoformat(metadata["backup_date"])
                
                backups.append({
                    "id": backup_id,
                    "date": backup_date,
                    "metadata": metadata,
                    "metadata_file": os.path.join(backup_dir, metadata_file)
                })
            except Exception as e:
                logger.error(f"Error loading metadata file {metadata_file}: {e}")
        
        
        backups.sort(key=lambda b: b["date"], reverse=True)
        
        
        for backup in backups[keep_count:]:
            try:
                
                backup_file = backup["metadata"].get("backup_file")
                if backup_file and os.path.exists(backup_file):
                    os.remove(backup_file)
                
                
                for dir_key in ["attachments_dir", "emoji_dir", "sticker_dir", "server_assets_dir"]:
                    if dir_key in backup["metadata"] and backup["metadata"][dir_key] and os.path.exists(backup["metadata"][dir_key]):
                        for root, dirs, files in os.walk(backup["metadata"][dir_key], topdown=False):
                            for file in files:
                                os.remove(os.path.join(root, file))
                            for dir in dirs:
                                os.rmdir(os.path.join(root, dir))
                        os.rmdir(backup["metadata"][dir_key])
                
                
                os.remove(backup["metadata_file"])
                
                logger.info(f"Deleted old backup {backup['id']} for guild {guild_id}")
                
            except Exception as e:
                logger.error(f"Error deleting old backup {backup['id']}: {e}")
    
    @zbackup.error
    @create_backup.error
    @list_backups.error
    @backup_info.error
    @delete_backup.error
    @restore_backup_cmd.error
    @export_backup.error
    @import_backup.error
    @schedule_backup.error
    async def zbackup_error(self, ctx: commands.Context, error):

        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need Administrator permission to use this command.")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("I need Administrator permission to perform backup operations.")
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send("This command can only be used in a server.")
        elif isinstance(error, commands.CommandInvokeError):
            logger.error(f"Error in {ctx.command.name}: {traceback.format_exc()}")
            await ctx.send(f"An error occurred while executing the command: {str(error.original)}")
        else:
            logger.error(f"Unexpected error in {ctx.command.name}: {traceback.format_exc()}")
            await ctx.send(f"An unexpected error occurred: {str(error)}")

async def setup(bot):

    backup_cog = ZBackup(bot)
    await bot.add_cog(backup_cog)
    backup_cog.check_scheduled_backups.start()




