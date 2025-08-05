import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Union
import re
import uuid

class DeletePeriodConfig:
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.enabled = False
        self.log_channel_id = None
        self.access_levels = {
            "messages": {"type": "permissions", "values": ["manage_messages"]},
            "channels": {"type": "permissions", "values": ["manage_channels"]},
            "categories": {"type": "permissions", "values": ["manage_channels"]},
            "roles": {"type": "permissions", "values": ["manage_roles"]},
            "webhooks": {"type": "permissions", "values": ["manage_webhooks"]},
            "voice_channels": {"type": "permissions", "values": ["manage_channels"]}
        }
        self.scheduled_deletions = []
        self.next_deletion_id = 1
        
    def to_dict(self):
        return {
            "guild_id": self.guild_id,
            "enabled": self.enabled,
            "log_channel_id": self.log_channel_id,
            "access_levels": self.access_levels,
            "scheduled_deletions": self.scheduled_deletions,
            "next_deletion_id": self.next_deletion_id
        }
    
    @classmethod
    def from_dict(cls, data):
        config = cls(data["guild_id"])
        config.enabled = data.get("enabled", False)
        config.log_channel_id = data.get("log_channel_id")
        config.access_levels = data.get("access_levels", config.access_levels)
        config.scheduled_deletions = data.get("scheduled_deletions", [])
        config.next_deletion_id = data.get("next_deletion_id", 1)
        
        for action_type in config.access_levels:
            if isinstance(config.access_levels[action_type], list):
                config.access_levels[action_type] = {
                    "type": "permissions",
                    "values": config.access_levels[action_type]
                }
        
        return config

class DeletePeriod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_dir = "data/deleteperiod"
        self.configs = {}
        self.ensure_data_dir()
        self.load_configs()
        self.deletion_checker.start()
    
    def cog_unload(self):
        self.deletion_checker.cancel()
    
    def ensure_data_dir(self):
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
    
    def get_config_path(self, guild_id: int) -> str:
        return os.path.join(self.config_dir, f"{guild_id}.json")
    
    def load_configs(self):
        for filename in os.listdir(self.config_dir):
            if filename.endswith('.json'):
                guild_id = int(filename[:-5])
                try:
                    with open(os.path.join(self.config_dir, filename), 'r') as f:
                        data = json.load(f)
                        self.configs[guild_id] = DeletePeriodConfig.from_dict(data)
                except Exception as e:
                    print(f"Error loading config for guild {guild_id}: {e}")
    
    def save_config(self, guild_id: int):
        config = self.get_config(guild_id)
        try:
            with open(self.get_config_path(guild_id), 'w') as f:
                json.dump(config.to_dict(), f, indent=4)
        except Exception as e:
            print(f"Error saving config for guild {guild_id}: {e}")
    
    def get_config(self, guild_id: int) -> DeletePeriodConfig:
        if guild_id not in self.configs:
            self.configs[guild_id] = DeletePeriodConfig(guild_id)
            self.save_config(guild_id)
        return self.configs[guild_id]
    
    def has_permission(self, member: discord.Member, action_type: str, config: DeletePeriodConfig) -> bool:
        if member.guild_permissions.administrator:
            return True
        
        access_config = config.access_levels.get(action_type, {"type": "permissions", "values": []})
        
        if access_config["type"] == "permissions":
            member_perms = member.guild_permissions
            for perm in access_config["values"]:
                if hasattr(member_perms, perm) and getattr(member_perms, perm):
                    return True
        elif access_config["type"] == "roles":
            member_role_ids = [role.id for role in member.roles]
            for role_id in access_config["values"]:
                if role_id in member_role_ids:
                    return True
        
        return False
    
    async def log_action(self, guild: discord.Guild, action: str, details: str, user: discord.Member, status: str = "success"):
        config = self.get_config(guild.id)
        if not config.log_channel_id:
            return
        
        log_channel = guild.get_channel(config.log_channel_id)
        if not log_channel:
            return
        
        color = discord.Color.green() if status == "success" else discord.Color.red()
        embed = discord.Embed(
            title="🗑️ Delete Period Action",
            color=color,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="Action", value=action, inline=True)
        embed.add_field(name="Status", value=status.title(), inline=True)
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Details", value=details, inline=False)
        embed.set_footer(text="Made By TheHolyOneZ")
        
        try:
            await log_channel.send(embed=embed)
        except:
            pass
    
    def schedule_deletion(self, guild_id: int, deletion_type: str, target_data: dict, minutes: int, user_id: int):
        config = self.get_config(guild_id)
        
        deletion_time = datetime.utcnow() + timedelta(minutes=minutes)
        deletion_id = str(uuid.uuid4())[:8]
        
        deletion_entry = {
            "id": deletion_id,
            "guild_id": guild_id,
            "type": deletion_type,
            "target_data": target_data,
            "scheduled_time": deletion_time.isoformat(),
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat()
        }
        
        config.scheduled_deletions.append(deletion_entry)
        self.save_config(guild_id)
        
        return deletion_id
    
    @tasks.loop(minutes=1)
    async def deletion_checker(self):
        current_time = datetime.utcnow()
        
        for guild_id, config in self.configs.items():
            deletions_to_remove = []
            
            for deletion in config.scheduled_deletions:
                scheduled_time = datetime.fromisoformat(deletion["scheduled_time"])
                
                if current_time >= scheduled_time:
                    await self.execute_scheduled_deletion(deletion)
                    deletions_to_remove.append(deletion)
            
            for deletion in deletions_to_remove:
                config.scheduled_deletions.remove(deletion)
            
            if deletions_to_remove:
                self.save_config(guild_id)
    
    @deletion_checker.before_loop
    async def before_deletion_checker(self):
        await self.bot.wait_until_ready()
    
    async def execute_scheduled_deletion(self, deletion):
        guild = self.bot.get_guild(deletion["guild_id"])
        if not guild:
            return
        
        user = guild.get_member(deletion["user_id"])
        if not user:
            return
        
        deletion_type = deletion["type"]
        target_data = deletion["target_data"]
        
        try:
            if deletion_type == "messages":
                await self.execute_message_deletion(guild, target_data, user)
            elif deletion_type == "channels":
                await self.execute_channel_deletion(guild, target_data, user)
            elif deletion_type == "voice_channels":
                await self.execute_voice_deletion(guild, target_data, user)
            elif deletion_type == "categories":
                await self.execute_category_deletion(guild, target_data, user)
            elif deletion_type == "roles":
                await self.execute_role_deletion(guild, target_data, user)
            elif deletion_type == "webhooks":
                await self.execute_webhook_deletion(guild, target_data, user)
        except Exception as e:
            await self.log_action(guild, f"Scheduled {deletion_type} deletion", f"Error: {str(e)}", user, "error")
            print(f"Error executing scheduled deletion: {e}")
    
    async def execute_message_deletion(self, guild, target_data, user):
        method = target_data["method"]
        
        if method == "url":
            deleted_count = 0
            for url in target_data["urls"]:
                try:
                    url_pattern = r'https://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/(\d+)/(\d+)/(\d+)'
                    match = re.search(url_pattern, url)
                    
                    if match:
                        guild_id, channel_id, message_id = match.groups()
                        
                        if int(guild_id) == guild.id:
                            channel = self.bot.get_channel(int(channel_id))
                            if channel:
                                try:
                                    message = await channel.fetch_message(int(message_id))
                                    await message.delete()
                                    deleted_count += 1
                                except discord.NotFound:
                                    pass
                                except discord.Forbidden:
                                    pass
                except:
                    continue
            
            await self.log_action(guild, "Scheduled Message Deletion (URL)", f"Deleted {deleted_count} messages", user)
        
        elif method == "channel":
            total_deleted = 0
            for channel_id in target_data["channel_ids"]:
                channel = guild.get_channel(channel_id)
                if channel:
                    try:
                        deleted = await channel.purge(limit=None)
                        total_deleted += len(deleted)
                    except:
                        continue
            
            await self.log_action(guild, "Scheduled Channel Purge", f"Deleted {total_deleted} messages", user)
        
        elif method == "user":
            total_deleted = 0
            user_ids = target_data["user_ids"]
            scope = target_data["scope"]
            
            if scope == "current":
                channel = guild.get_channel(target_data["channel_id"])
                if channel:
                    for user_id in user_ids:
                        target_user = guild.get_member(user_id)
                        if target_user:
                            def user_check(m):
                                return m.author == target_user
                            try:
                                deleted = await channel.purge(limit=None, check=user_check)
                                total_deleted += len(deleted)
                            except:
                                continue
            else:
                for channel in guild.text_channels:
                    try:
                        for user_id in user_ids:
                            target_user = guild.get_member(user_id)
                            if target_user:
                                def user_check(m):
                                    return m.author == target_user
                                deleted = await channel.purge(limit=None, check=user_check)
                                total_deleted += len(deleted)
                    except:
                        continue
            
            await self.log_action(guild, "Scheduled User Message Deletion", f"Deleted {total_deleted} messages", user)
        
        elif method == "time":
            after_time = datetime.fromisoformat(target_data["after_time"])
            total_deleted = 0
            
            for channel in guild.text_channels:
                try:
                    deleted = await channel.purge(after=after_time)
                    total_deleted += len(deleted)
                except:
                    continue
            
            await self.log_action(guild, "Scheduled Time-based Deletion", f"Deleted {total_deleted} messages", user)
        
        elif method == "pattern":
            pattern = target_data["pattern"].lower()
            total_deleted = 0
            
            for channel in guild.text_channels:
                try:
                    def pattern_check(m):
                        return pattern in m.content.lower()
                    
                    deleted = await channel.purge(limit=None, check=pattern_check)
                    total_deleted += len(deleted)
                except:
                    continue
            
            await self.log_action(guild, "Scheduled Pattern Deletion", f"Deleted {total_deleted} messages", user)
    
    async def execute_channel_deletion(self, guild, target_data, user):
        deleted_count = 0
        already_deleted = 0
        
        for channel_id in target_data["channel_ids"]:
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    await channel.delete()
                    deleted_count += 1
                except:
                    continue
            else:
                already_deleted += 1
        
        details = f"Deleted {deleted_count} channels"
        if already_deleted > 0:
            details += f" ({already_deleted} already deleted)"
        
        await self.log_action(guild, "Scheduled Channel Deletion", details, user)
    
    async def execute_voice_deletion(self, guild, target_data, user):
        deleted_count = 0
        already_deleted = 0
        
        for channel_id in target_data["channel_ids"]:
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    await channel.delete()
                    deleted_count += 1
                except:
                    continue
            else:
                already_deleted += 1
        
        details = f"Deleted {deleted_count} voice channels"
        if already_deleted > 0:
            details += f" ({already_deleted} already deleted)"
        
        await self.log_action(guild, "Scheduled Voice Channel Deletion", details, user)
    
    async def execute_category_deletion(self, guild, target_data, user):
        deleted_categories = 0
        deleted_channels = 0
        already_deleted_categories = 0
        delete_channels = target_data["delete_channels"]
        
        for category_id in target_data["category_ids"]:
            category = guild.get_channel(category_id)
            if category:
                try:
                    if delete_channels:
                        channels_in_cat = category.channels.copy()
                        for channel in channels_in_cat:
                            try:
                                await channel.delete()
                                deleted_channels += 1
                            except:
                                continue
                    else:
                        for channel in category.channels:
                            try:
                                await channel.edit(category=None)
                            except:
                                pass
                    
                    await category.delete()
                    deleted_categories += 1
                except:
                    continue
            else:
                already_deleted_categories += 1
        
        action_desc = f"Deleted {deleted_categories} categories"
        if delete_channels:
            action_desc += f" and {deleted_channels} channels"
        if already_deleted_categories > 0:
            action_desc += f" ({already_deleted_categories} categories already deleted)"
        
        await self.log_action(guild, "Scheduled Category Deletion", action_desc, user)
    
    async def execute_role_deletion(self, guild, target_data, user):
        deleted_count = 0
        already_deleted = 0
        
        for role_id in target_data["role_ids"]:
            role = guild.get_role(role_id)
            if role:
                try:
                    await role.delete()
                    deleted_count += 1
                except:
                    continue
            else:
                already_deleted += 1
        
        details = f"Deleted {deleted_count} roles"
        if already_deleted > 0:
            details += f" ({already_deleted} already deleted)"
        
        await self.log_action(guild, "Scheduled Role Deletion", details, user)
    
    async def execute_webhook_deletion(self, guild, target_data, user):
        deleted_count = 0
        already_deleted = 0
        
        for webhook_data in target_data["webhooks"]:
            try:
                webhook = await self.bot.fetch_webhook(webhook_data["id"])
                if webhook.guild and webhook.guild.id == guild.id:
                    await webhook.delete()
                    deleted_count += 1
            except discord.NotFound:
                already_deleted += 1
            except:
                continue
        
        details = f"Deleted {deleted_count} webhooks"
        if already_deleted > 0:
            details += f" ({already_deleted} already deleted)"
        
        await self.log_action(guild, "Scheduled Webhook Deletion", details, user)
    
    @commands.group(name="deleteperiod", aliases=["dp"])
    async def deleteperiod(self, ctx):
        if ctx.invoked_subcommand is None:
            await self.show_main_menu(ctx)
    
    @deleteperiod.command(name="view")
    async def view_deletion(self, ctx, deletion_id: str = None):
        config = self.get_config(ctx.guild.id)
        
        if not deletion_id:
            await ctx.send("❌ Please provide a deletion ID. Usage: `!dp view <deletion_id>`")
            return
        
        deletion = None
        for d in config.scheduled_deletions:
            if d["id"] == deletion_id:
                deletion = d
                break
        
        if not deletion:
            await ctx.send(f"❌ No scheduled deletion found with ID: `{deletion_id}`")
            return
        
        scheduled_time = datetime.fromisoformat(deletion["scheduled_time"])
        created_time = datetime.fromisoformat(deletion.get("created_at", deletion["scheduled_time"]))
        user = ctx.guild.get_member(deletion["user_id"])
        user_name = user.display_name if user else "Unknown User"
        
        embed = discord.Embed(
            title=f"🗑️ Deletion Details - {deletion['id']}",
            color=discord.Color.red()
        )
        
        embed.add_field(name="Type", value=deletion['type'].title(), inline=True)
        embed.add_field(name="Scheduled By", value=user_name, inline=True)
        embed.add_field(name="Status", value="⏳ Pending", inline=True)
        
        embed.add_field(name="Created", value=f"<t:{int(created_time.timestamp())}:F>", inline=True)
        embed.add_field(name="Scheduled Time", value=f"<t:{int(scheduled_time.timestamp())}:F>", inline=True)
        embed.add_field(name="Time Remaining", value=f"<t:{int(scheduled_time.timestamp())}:R>", inline=True)
        
        target_info = []
        target_data = deletion["target_data"]
        
        if deletion['type'] == "messages":
            method = target_data.get("method", "unknown")
            if method == "url":
                target_info.append(f"Method: URL ({len(target_data.get('urls', []))} messages)")
            elif method == "channel":
                target_info.append(f"Method: Channel Purge ({len(target_data.get('channel_ids', []))} channels)")
            elif method == "user":
                scope = target_data.get("scope", "unknown")
                target_info.append(f"Method: User Messages ({len(target_data.get('user_ids', []))} users, {scope})")
            elif method == "time":
                target_info.append(f"Method: Time Range")
            elif method == "pattern":
                target_info.append(f"Method: Pattern Match")
        
        elif deletion['type'] in ["channels", "voice_channels"]:
            target_info.append(f"Targets: {len(target_data.get('channel_ids', []))} channels")
        
        elif deletion['type'] == "categories":
            include_channels = target_data.get("delete_channels", False)
            target_info.append(f"Targets: {len(target_data.get('category_ids', []))} categories")
            target_info.append(f"Include Channels: {'Yes' if include_channels else 'No'}")
        
        elif deletion['type'] == "roles":
            target_info.append(f"Targets: {len(target_data.get('role_ids', []))} roles")
        
        elif deletion['type'] == "webhooks":
            target_info.append(f"Targets: {len(target_data.get('webhooks', []))} webhooks")
        
        embed.add_field(name="Target Details", value="\n".join(target_info) if target_info else "No details available", inline=False)
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await ctx.send(embed=embed)
    
    @deleteperiod.command(name="permissions")
    async def manage_permissions(self, ctx, action: str = None, deletion_type: str = None, *, value: str = None):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions to manage access levels.")
            return
        
        config = self.get_config(ctx.guild.id)
        valid_types = ["messages", "channels", "categories", "roles", "webhooks", "voice_channels"]
        
        if not action:
            embed = discord.Embed(
                title="🔐 Permission Management",
                description="Configure who can use different deletion types",
                color=discord.Color.blue()
            )
            
            for del_type in valid_types:
                access_config = config.access_levels.get(del_type, {"type": "permissions", "values": []})
                if access_config["type"] == "permissions":
                    value_str = ", ".join(access_config["values"])
                else:
                    role_names = []
                    for role_id in access_config["values"]:
                        role = ctx.guild.get_role(role_id)
                        role_names.append(role.name if role else f"Unknown Role ({role_id})")
                    value_str = ", ".join(role_names)
                
                embed.add_field(
                    name=f"{del_type.title()}",
                    value=f"Type: {access_config['type'].title()}\nValues: {value_str or 'None'}",
                    inline=True
                )
            
            embed.add_field(
                name="Commands",
                value=(
                    "`!dp permissions setroles <type> @role1 @role2` - Set role-based access\n"
                    "`!dp permissions setperms <type> perm1 perm2` - Set permission-based access\n"
                    "`!dp permissions reset <type>` - Reset to default permissions"
                ),
                inline=False
            )
            
            await ctx.send(embed=embed)
            return
        
        if deletion_type not in valid_types:
            await ctx.send(f"❌ Invalid deletion type. Valid types: {', '.join(valid_types)}")
            return
        
        if action.lower() == "setroles":
            if not ctx.message.role_mentions:
                await ctx.send("❌ Please mention at least one role.")
                return
            
            role_ids = [role.id for role in ctx.message.role_mentions]
            config.access_levels[deletion_type] = {
                "type": "roles",
                "values": role_ids
            }
            self.save_config(ctx.guild.id)
            
            role_names = [role.name for role in ctx.message.role_mentions]
            await ctx.send(f"✅ Set role-based access for {deletion_type}: {', '.join(role_names)}")
        
        elif action.lower() == "setperms":
            if not value:
                await ctx.send("❌ Please provide permission names (e.g., manage_messages manage_channels)")
                return
            
            perms = value.split()
            config.access_levels[deletion_type] = {
                "type": "permissions",
                "values": perms
            }
            self.save_config(ctx.guild.id)
            
            await ctx.send(f"✅ Set permission-based access for {deletion_type}: {', '.join(perms)}")
        
        elif action.lower() == "reset":
            default_perms = {
                "messages": ["manage_messages"],
                "channels": ["manage_channels"],
                "categories": ["manage_channels"],
                "roles": ["manage_roles"],
                "webhooks": ["manage_webhooks"],
                "voice_channels": ["manage_channels"]
            }
            
            config.access_levels[deletion_type] = {
                "type": "permissions",
                "values": default_perms.get(deletion_type, [])
            }
            self.save_config(ctx.guild.id)
            
            await ctx.send(f"✅ Reset access level for {deletion_type} to default permissions")
        
        else:
            await ctx.send("❌ Invalid action. Use: setroles, setperms, or reset")
    
    async def show_main_menu(self, ctx):
        config = self.get_config(ctx.guild.id)
        
        embed = discord.Embed(
            title="🗑️ Delete Period System",
            description="Advanced scheduled deletion management system",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="⚙️ System Status",
            value=f"Status: {'🟢 Enabled' if config.enabled else '🔴 Disabled'}\nLog Channel: {'✅ Set' if config.log_channel_id else '❌ Not Set'}",
            inline=True
        )
        
        embed.add_field(
            name="📊 Scheduled Deletions",
            value=f"Active: {len(config.scheduled_deletions)}",
            inline=True
        )
        
        embed.add_field(name="⠀", value="⠀", inline=True)
        
        embed.add_field(
            name="🎛️ Available Actions",
            value="Use the buttons below to schedule deletions:",
            inline=False
        )
        
        embed.add_field(
            name="📋 Commands",
            value=(
                "`!dp view <id>` - View deletion details\n"
                "`!dp permissions` - Manage access levels"
            ),
            inline=False
        )
        
        embed.set_footer(text="Made By TheHolyOneZ • Times shown in your local timezone")
        
        view = MainMenuView(self, ctx.author, config)
        await ctx.send(embed=embed, view=view)

class MainMenuView(discord.ui.View):
    def __init__(self, cog, user, config):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.config = config
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user
    
    @discord.ui.button(label="Delete Messages", emoji="💬", style=discord.ButtonStyle.danger, row=0)
    async def delete_messages(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.has_permission(interaction.user, "messages", self.config):
            await interaction.response.send_message("❌ You don't have permission to delete messages.", ephemeral=True)
            return
        
        view = MessageDeletionView(self.cog, interaction.user, self.config)
        embed = discord.Embed(
            title="💬 Schedule Message Deletion",
            description="Choose how you want to delete messages:",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Delete Channels", emoji="📁", style=discord.ButtonStyle.danger, row=0)
    async def delete_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.has_permission(interaction.user, "channels", self.config):
            await interaction.response.send_message("❌ You don't have permission to delete channels.", ephemeral=True)
            return
        
        view = ChannelDeletionView(self.cog, interaction.user, self.config)
        embed = discord.Embed(
            title="📁 Schedule Channel Deletion",
            description="Select channels to schedule for deletion:",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Delete Voice Channels", emoji="🎵", style=discord.ButtonStyle.danger, row=0)
    async def delete_voice_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.has_permission(interaction.user, "voice_channels", self.config):
            await interaction.response.send_message("❌ You don't have permission to delete voice channels.", ephemeral=True)
            return
        
        view = VoiceChannelDeletionView(self.cog, interaction.user, self.config)
        embed = discord.Embed(
            title="🎵 Schedule Voice Channel Deletion",
            description="Select voice channels to schedule for deletion:",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Delete Categories", emoji="📂", style=discord.ButtonStyle.danger, row=1)
    async def delete_categories(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.has_permission(interaction.user, "categories", self.config):
            await interaction.response.send_message("❌ You don't have permission to delete categories.", ephemeral=True)
            return
        
        view = CategoryDeletionView(self.cog, interaction.user, self.config)
        embed = discord.Embed(
            title="📂 Schedule Category Deletion",
            description="Select categories to schedule for deletion:",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Delete Roles", emoji="👥", style=discord.ButtonStyle.danger, row=1)
    async def delete_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.has_permission(interaction.user, "roles", self.config):
            await interaction.response.send_message("❌ You don't have permission to delete roles.", ephemeral=True)
            return
        
        view = RoleDeletionView(self.cog, interaction.user, self.config)
        embed = discord.Embed(
            title="👥 Schedule Role Deletion",
            description="Select roles to schedule for deletion:",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Delete Webhooks", emoji="🔗", style=discord.ButtonStyle.danger, row=1)
    async def delete_webhooks(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.has_permission(interaction.user, "webhooks", self.config):
            await interaction.response.send_message("❌ You don't have permission to delete webhooks.", ephemeral=True)
            return
        
        view = WebhookDeletionView(self.cog, interaction.user, self.config)
        embed = discord.Embed(
            title="🔗 Schedule Webhook Deletion",
            description="Select webhooks to schedule for deletion:",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Settings", emoji="⚙️", style=discord.ButtonStyle.secondary, row=2)
    async def settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions to access settings.", ephemeral=True)
            return
        
        view = SettingsView(self.cog, interaction.user, self.config)
        embed = discord.Embed(
            title="⚙️ Delete Period Settings",
            description="Configure the Delete Period system:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📊 Current Status",
            value=f"System: {'🟢 Enabled' if self.config.enabled else '🔴 Disabled'}\nLog Channel: {'✅ Set' if self.config.log_channel_id else '❌ Not Set'}",
            inline=False
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)

class MessageDeletionView(discord.ui.View):
    def __init__(self, cog, user, config):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.config = config
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user
    
    @discord.ui.button(label="Delete by Message URL", style=discord.ButtonStyle.primary, row=0)
    async def delete_by_url(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MessageURLModal(self.cog, self.user, self.config)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Delete by Channel", style=discord.ButtonStyle.primary, row=0)
    async def delete_by_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ChannelSelectView(self.cog, self.user, self.config, "message_purge")
        embed = discord.Embed(
            title="📁 Select Channels to Purge",
            description="Select channels to purge all messages from:",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Delete by User", style=discord.ButtonStyle.primary, row=1)
    async def delete_by_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = UserMessageModal(self.cog, self.user, self.config)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Delete by Time Range", style=discord.ButtonStyle.primary, row=1)
    async def delete_by_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = TimeRangeView(self.cog, self.user, self.config)
        embed = discord.Embed(
            title="⏰ Select Time Range",
            description="Choose the time range for message deletion:",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Delete by Pattern", style=discord.ButtonStyle.primary, row=2)
    async def delete_by_pattern(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PatternModal(self.cog, self.user, self.config)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Back", emoji="⬅️", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MainMenuView(self.cog, self.user, self.config)
        embed = discord.Embed(
            title="🗑️ Delete Period System",
            description="Advanced scheduled deletion management system",
            color=discord.Color.red()
        )
        embed.add_field(
            name="⚙️ System Status",
            value=f"Status: {'🟢 Enabled' if self.config.enabled else '🔴 Disabled'}\nLog Channel: {'✅ Set' if self.config.log_channel_id else '❌ Not Set'}",
            inline=True
        )
        embed.add_field(
            name="📊 Scheduled Deletions",
            value=f"Active: {len(self.config.scheduled_deletions)}",
            inline=True
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)

class MessageURLModal(discord.ui.Modal):
    def __init__(self, cog, user, config):
        super().__init__(title="Delete Messages by URL")
        self.cog = cog
        self.user = user
        self.config = config
    
    urls = discord.ui.TextInput(
        label="Message URLs",
        placeholder="Enter message URLs (one per line)...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000
    )
    
    minutes = discord.ui.TextInput(
        label="Delete in how many minutes?",
        placeholder="Enter number of minutes (e.g., 5, 30, 60)...",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            minutes_int = int(self.minutes.value)
            if minutes_int < 1:
                await interaction.followup.send("❌ Minutes must be at least 1.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Please enter a valid number for minutes.", ephemeral=True)
            return
        
        urls = [url.strip() for url in self.urls.value.split('\n') if url.strip()]
        
        if not urls:
            await interaction.followup.send("❌ No valid URLs provided.", ephemeral=True)
            return
        
        target_data = {
            "method": "url",
            "urls": urls
        }
        
        deletion_id = self.cog.schedule_deletion(
            interaction.guild.id,
            "messages",
            target_data,
            minutes_int,
            interaction.user.id
        )
        
        embed = discord.Embed(
            title="✅ Message Deletion Scheduled",
            description=f"Scheduled deletion of {len(urls)} message(s) in {minutes_int} minute(s)",
            color=discord.Color.green()
        )
        embed.add_field(name="Deletion ID", value=str(deletion_id), inline=True)
        embed.add_field(name="Scheduled Time", value=f"<t:{int((datetime.utcnow() + timedelta(minutes=minutes_int)).timestamp())}:R>", inline=True)
        embed.set_footer(text="Made By TheHolyOneZ • Starting deletion process...")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class UserMessageModal(discord.ui.Modal):
    def __init__(self, cog, user, config):
        super().__init__(title="Delete Messages by User")
        self.cog = cog
        self.user = user
        self.config = config
    
    users = discord.ui.TextInput(
        label="User IDs or Mentions",
        placeholder="Enter user IDs or mentions (one per line)...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )
    
    scope = discord.ui.TextInput(
        label="Scope (current/server)",
        placeholder="Enter 'current' for current channel or 'server' for entire server",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    minutes = discord.ui.TextInput(
        label="Delete in how many minutes?",
        placeholder="Enter number of minutes (e.g., 5, 30, 60)...",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            minutes_int = int(self.minutes.value)
            if minutes_int < 1:
                await interaction.followup.send("❌ Minutes must be at least 1.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Please enter a valid number for minutes.", ephemeral=True)
            return
        
        scope_value = self.scope.value.lower()
        if scope_value not in ["current", "server"]:
            await interaction.followup.send("❌ Scope must be either 'current' or 'server'.", ephemeral=True)
            return
        
        user_inputs = [u.strip() for u in self.users.value.split('\n') if u.strip()]
        user_ids = []
        
        for user_input in user_inputs:
            try:
                if user_input.startswith('<@') and user_input.endswith('>'):
                    user_id = int(user_input[2:-1].replace('!', ''))
                else:
                    user_id = int(user_input)
                
                if interaction.guild.get_member(user_id):
                    user_ids.append(user_id)
            except ValueError:
                continue
        
        if not user_ids:
            await interaction.followup.send("❌ No valid users found.", ephemeral=True)
            return
        
        target_data = {
            "method": "user",
            "user_ids": user_ids,
            "scope": scope_value,
            "channel_id": interaction.channel.id if scope_value == "current" else None
        }
        
        deletion_id = self.cog.schedule_deletion(
            interaction.guild.id,
            "messages",
            target_data,
            minutes_int,
            interaction.user.id
        )
        
        embed = discord.Embed(
            title="✅ User Message Deletion Scheduled",
            description=f"Scheduled deletion of messages from {len(user_ids)} user(s) in {minutes_int} minute(s)",
            color=discord.Color.green()
        )
        embed.add_field(name="Deletion ID", value=str(deletion_id), inline=True)
        embed.add_field(name="Scope", value=scope_value.title(), inline=True)
        embed.add_field(name="Scheduled Time", value=f"<t:{int((datetime.utcnow() + timedelta(minutes=minutes_int)).timestamp())}:R>", inline=True)
        embed.set_footer(text="Made By TheHolyOneZ • This may take several minutes to complete")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class PatternModal(discord.ui.Modal):
    def __init__(self, cog, user, config):
        super().__init__(title="Delete Messages by Pattern")
        self.cog = cog
        self.user = user
        self.config = config
    
    pattern = discord.ui.TextInput(
        label="Text Pattern",
        placeholder="Enter the text pattern to search for and delete...",
        style=discord.TextStyle.short,
        required=True,
        max_length=500
    )
    
    minutes = discord.ui.TextInput(
        label="Delete in how many minutes?",
        placeholder="Enter number of minutes (e.g., 5, 30, 60)...",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            minutes_int = int(self.minutes.value)
            if minutes_int < 1:
                await interaction.followup.send("❌ Minutes must be at least 1.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Please enter a valid number for minutes.", ephemeral=True)
            return
        
        target_data = {
            "method": "pattern",
            "pattern": self.pattern.value
        }
        
        deletion_id = self.cog.schedule_deletion(
            interaction.guild.id,
            "messages",
            target_data,
            minutes_int,
            interaction.user.id
        )
        
        embed = discord.Embed(
            title="✅ Pattern Message Deletion Scheduled",
            description=f"Scheduled deletion of messages containing '{self.pattern.value}' in {minutes_int} minute(s)",
            color=discord.Color.green()
        )
        embed.add_field(name="Deletion ID", value=str(deletion_id), inline=True)
        embed.add_field(name="Pattern", value=self.pattern.value, inline=True)
        embed.add_field(name="Scheduled Time", value=f"<t:{int((datetime.utcnow() + timedelta(minutes=minutes_int)).timestamp())}:R>", inline=True)
        embed.set_footer(text="Made By TheHolyOneZ • This may take several minutes to complete")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class TimeRangeView(discord.ui.View):
    def __init__(self, cog, user, config):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.config = config
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user
    
    @discord.ui.button(label="Last Hour", style=discord.ButtonStyle.primary, row=0)
    async def last_hour(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.schedule_time_deletion(interaction, 1, "hour")
    
    @discord.ui.button(label="Last 24 Hours", style=discord.ButtonStyle.primary, row=0)
    async def last_day(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.schedule_time_deletion(interaction, 24, "hours")
    
    @discord.ui.button(label="Last 7 Days", style=discord.ButtonStyle.primary, row=1)
    async def last_week(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.schedule_time_deletion(interaction, 7 * 24, "hours")
    
    @discord.ui.button(label="Last 30 Days", style=discord.ButtonStyle.primary, row=1)
    async def last_month(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.schedule_time_deletion(interaction, 30 * 24, "hours")
    
    @discord.ui.button(label="Custom Range", style=discord.ButtonStyle.secondary, row=2)
    async def custom_range(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomTimeModal(self.cog, self.user, self.config)
        await interaction.response.send_modal(modal)
    
    async def schedule_time_deletion(self, interaction, hours_back, unit):
        modal = ScheduleTimeModal(self.cog, self.user, self.config, hours_back, unit)
        await interaction.response.send_modal(modal)

class ScheduleTimeModal(discord.ui.Modal):
    def __init__(self, cog, user, config, hours_back, unit):
        super().__init__(title=f"Schedule Deletion - Last {hours_back} {unit}")
        self.cog = cog
        self.user = user
        self.config = config
        self.hours_back = hours_back
        self.unit = unit
    
    minutes = discord.ui.TextInput(
        label="Delete in how many minutes?",
        placeholder="Enter number of minutes (e.g., 5, 30, 60)...",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            minutes_int = int(self.minutes.value)
            if minutes_int < 1:
                await interaction.followup.send("❌ Minutes must be at least 1.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Please enter a valid number for minutes.", ephemeral=True)
            return
        
        after_time = datetime.utcnow() - timedelta(hours=self.hours_back)
        
        target_data = {
            "method": "time",
            "after_time": after_time.isoformat()
        }
        
        deletion_id = self.cog.schedule_deletion(
            interaction.guild.id,
            "messages",
            target_data,
            minutes_int,
            interaction.user.id
        )
        
        embed = discord.Embed(
            title="✅ Time-based Message Deletion Scheduled",
            description=f"Scheduled deletion of messages from the last {self.hours_back} {self.unit} in {minutes_int} minute(s)",
            color=discord.Color.green()
        )
        embed.add_field(name="Deletion ID", value=str(deletion_id), inline=True)
        embed.add_field(name="Time Range", value=f"Last {self.hours_back} {self.unit}", inline=True)
        embed.add_field(name="Scheduled Time", value=f"<t:{int((datetime.utcnow() + timedelta(minutes=minutes_int)).timestamp())}:R>", inline=True)
        embed.set_footer(text="Made By TheHolyOneZ • This may take several minutes to complete")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class CustomTimeModal(discord.ui.Modal):
    def __init__(self, cog, user, config):
        super().__init__(title="Custom Time Range Deletion")
        self.cog = cog
        self.user = user
        self.config = config
    
    days_back = discord.ui.TextInput(
        label="Days to go back",
        placeholder="Enter number of days (e.g., 1, 7, 30)...",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    minutes = discord.ui.TextInput(
        label="Delete in how many minutes?",
        placeholder="Enter number of minutes (e.g., 5, 30, 60)...",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            days_int = int(self.days_back.value)
            minutes_int = int(self.minutes.value)
            if days_int < 1 or minutes_int < 1:
                await interaction.followup.send("❌ Days and minutes must be at least 1.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Please enter valid numbers.", ephemeral=True)
            return
        
        after_time = datetime.utcnow() - timedelta(days=days_int)
        
        target_data = {
            "method": "time",
            "after_time": after_time.isoformat()
        }
        
        deletion_id = self.cog.schedule_deletion(
            interaction.guild.id,
            "messages",
            target_data,
            minutes_int,
            interaction.user.id
        )
        
        embed = discord.Embed(
            title="✅ Custom Time-based Message Deletion Scheduled",
            description=f"Scheduled deletion of messages from the last {days_int} day(s) in {minutes_int} minute(s)",
            color=discord.Color.green()
        )
        embed.add_field(name="Deletion ID", value=str(deletion_id), inline=True)
        embed.add_field(name="Time Range", value=f"Last {days_int} day(s)", inline=True)
        embed.add_field(name="Scheduled Time", value=f"<t:{int((datetime.utcnow() + timedelta(minutes=minutes_int)).timestamp())}:R>", inline=True)
        embed.set_footer(text="Made By TheHolyOneZ • This may take several minutes to complete")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class ChannelSelectView(discord.ui.View):
    def __init__(self, cog, user, config, action_type):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.config = config
        self.action_type = action_type
        self.selected_channels = []
        
        self.add_item(ChannelSelectDropdown(self))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user
    
    @discord.ui.button(label="Schedule Deletion", style=discord.ButtonStyle.danger, row=1)
    async def schedule_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_channels:
            await interaction.response.send_message("❌ No channels selected.", ephemeral=True)
            return
        
        if self.action_type == "message_purge":
            modal = ChannelPurgeModal(self.cog, self.user, self.config, self.selected_channels)
        else:
            modal = ChannelDeletionModal(self.cog, self.user, self.config, self.selected_channels)
        
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Back", emoji="⬅️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.action_type == "message_purge":
            view = MessageDeletionView(self.cog, self.user, self.config)
            embed = discord.Embed(
                title="💬 Schedule Message Deletion",
                description="Choose how you want to delete messages:",
                color=discord.Color.orange()
            )
        else:
            view = MainMenuView(self.cog, self.user, self.config)
            embed = discord.Embed(
                title="🗑️ Delete Period System",
                description="Advanced scheduled deletion management system",
                color=discord.Color.red()
            )
            embed.add_field(
                name="⚙️ System Status",
                value=f"Status: {'🟢 Enabled' if self.config.enabled else '🔴 Disabled'}\nLog Channel: {'✅ Set' if self.config.log_channel_id else '❌ Not Set'}",
                inline=True
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.edit_message(embed=embed, view=view)

class ChannelSelectDropdown(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        
        options = []
        for channel in parent_view.user.guild.text_channels[:25]:
            options.append(discord.SelectOption(
                label=f"#{channel.name}",
                value=str(channel.id),
                description=f"Category: {channel.category.name if channel.category else 'No Category'}"
            ))
        
        super().__init__(
            placeholder="Select channels...",
            min_values=1,
            max_values=len(options),
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_channels = [int(channel_id) for channel_id in self.values]
        
        selected_names = []
        for channel_id in self.parent_view.selected_channels:
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                selected_names.append(f"#{channel.name}")
        
        embed = discord.Embed(
            title="📁 Channels Selected",
            description=f"Selected {len(self.parent_view.selected_channels)} channel(s):",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="Selected Channels",
            value="\n".join(selected_names[:10]) + (f"\n... and {len(selected_names) - 10} more" if len(selected_names) > 10 else ""),
            inline=False
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class ChannelPurgeModal(discord.ui.Modal):
    def __init__(self, cog, user, config, selected_channels):
        super().__init__(title="Schedule Channel Purge")
        self.cog = cog
        self.user = user
        self.config = config
        self.selected_channels = selected_channels
    
    minutes = discord.ui.TextInput(
        label="Delete in how many minutes?",
        placeholder="Enter number of minutes (e.g., 5, 30, 60)...",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            minutes_int = int(self.minutes.value)
            if minutes_int < 1:
                await interaction.followup.send("❌ Minutes must be at least 1.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Please enter a valid number for minutes.", ephemeral=True)
            return
        
        target_data = {
            "method": "channel",
            "channel_ids": self.selected_channels
        }
        
        deletion_id = self.cog.schedule_deletion(
            interaction.guild.id,
            "messages",
            target_data,
            minutes_int,
            interaction.user.id
        )
        
        embed = discord.Embed(
            title="✅ Channel Purge Scheduled",
            description=f"Scheduled purge of {len(self.selected_channels)} channel(s) in {minutes_int} minute(s)",
            color=discord.Color.green()
        )
        embed.add_field(name="Deletion ID", value=str(deletion_id), inline=True)
        embed.add_field(name="Channels", value=str(len(self.selected_channels)), inline=True)
        embed.add_field(name="Scheduled Time", value=f"<t:{int((datetime.utcnow() + timedelta(minutes=minutes_int)).timestamp())}:R>", inline=True)
        embed.set_footer(text="Made By TheHolyOneZ • This may take several minutes to complete")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class ChannelDeletionModal(discord.ui.Modal):
    def __init__(self, cog, user, config, selected_channels):
        super().__init__(title="Schedule Channel Deletion")
        self.cog = cog
        self.user = user
        self.config = config
        self.selected_channels = selected_channels
    
    minutes = discord.ui.TextInput(
        label="Delete in how many minutes?",
        placeholder="Enter number of minutes (e.g., 5, 30, 60)...",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            minutes_int = int(self.minutes.value)
            if minutes_int < 1:
                await interaction.followup.send("❌ Minutes must be at least 1.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Please enter a valid number for minutes.", ephemeral=True)
            return
        
        target_data = {
            "channel_ids": self.selected_channels
        }
        
        deletion_id = self.cog.schedule_deletion(
            interaction.guild.id,
            "channels",
            target_data,
            minutes_int,
            interaction.user.id
        )
        
        embed = discord.Embed(
            title="✅ Channel Deletion Scheduled",
            description=f"Scheduled deletion of {len(self.selected_channels)} channel(s) in {minutes_int} minute(s)",
            color=discord.Color.green()
        )
        embed.add_field(name="Deletion ID", value=str(deletion_id), inline=True)
        embed.add_field(name="Channels", value=str(len(self.selected_channels)), inline=True)
        embed.add_field(name="Scheduled Time", value=f"<t:{int((datetime.utcnow() + timedelta(minutes=minutes_int)).timestamp())}:R>", inline=True)
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class ChannelDeletionView(discord.ui.View):
    def __init__(self, cog, user, config):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.config = config
        self.selected_channels = []
        
        self.add_item(ChannelSelectDropdown(self))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user
    
    @discord.ui.button(label="Schedule Deletion", style=discord.ButtonStyle.danger, row=1)
    async def schedule_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_channels:
            await interaction.response.send_message("❌ No channels selected.", ephemeral=True)
            return
        
        modal = ChannelDeletionModal(self.cog, self.user, self.config, self.selected_channels)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Back", emoji="⬅️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MainMenuView(self.cog, self.user, self.config)
        embed = discord.Embed(
            title="🗑️ Delete Period System",
            description="Advanced scheduled deletion management system",
            color=discord.Color.red()
        )
        embed.add_field(
            name="⚙️ System Status",
            value=f"Status: {'🟢 Enabled' if self.config.enabled else '🔴 Disabled'}\nLog Channel: {'✅ Set' if self.config.log_channel_id else '❌ Not Set'}",
            inline=True
        )
        embed.add_field(
            name="📊 Scheduled Deletions",
            value=f"Active: {len(self.config.scheduled_deletions)}",
            inline=True
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)

class VoiceChannelDeletionView(discord.ui.View):
    def __init__(self, cog, user, config):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.config = config
        self.selected_channels = []
        
        self.add_item(VoiceChannelSelectDropdown(self))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user
    
    @discord.ui.button(label="Schedule Deletion", style=discord.ButtonStyle.danger, row=1)
    async def schedule_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_channels:
            await interaction.response.send_message("❌ No voice channels selected.", ephemeral=True)
            return
        
        modal = VoiceChannelDeletionModal(self.cog, self.user, self.config, self.selected_channels)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Back", emoji="⬅️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MainMenuView(self.cog, self.user, self.config)
        embed = discord.Embed(
            title="🗑️ Delete Period System",
            description="Advanced scheduled deletion management system",
            color=discord.Color.red()
        )
        embed.add_field(
            name="⚙️ System Status",
            value=f"Status: {'🟢 Enabled' if self.config.enabled else '🔴 Disabled'}\nLog Channel: {'✅ Set' if self.config.log_channel_id else '❌ Not Set'}",
            inline=True
        )
        embed.add_field(
            name="📊 Scheduled Deletions",
            value=f"Active: {len(self.config.scheduled_deletions)}",
            inline=True
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)

class VoiceChannelSelectDropdown(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        
        options = []
        for channel in parent_view.user.guild.voice_channels[:25]:
            options.append(discord.SelectOption(
                label=channel.name,
                value=str(channel.id),
                description=f"Category: {channel.category.name if channel.category else 'No Category'}"
            ))
        
        if not options:
            options.append(discord.SelectOption(
                label="No voice channels found",
                value="none",
                description="This server has no voice channels"
            ))
        
        super().__init__(
            placeholder="Select voice channels...",
            min_values=1,
            max_values=len(options) if options[0].value != "none" else 1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("❌ No voice channels available.", ephemeral=True)
            return
        
        self.parent_view.selected_channels = [int(channel_id) for channel_id in self.values]
        
        selected_names = []
        for channel_id in self.parent_view.selected_channels:
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                selected_names.append(channel.name)
        
        embed = discord.Embed(
            title="🎵 Voice Channels Selected",
            description=f"Selected {len(self.parent_view.selected_channels)} voice channel(s):",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="Selected Channels",
            value="\n".join(selected_names[:10]) + (f"\n... and {len(selected_names) - 10} more" if len(selected_names) > 10 else ""),
            inline=False
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class VoiceChannelDeletionModal(discord.ui.Modal):
    def __init__(self, cog, user, config, selected_channels):
        super().__init__(title="Schedule Voice Channel Deletion")
        self.cog = cog
        self.user = user
        self.config = config
        self.selected_channels = selected_channels
    
    minutes = discord.ui.TextInput(
        label="Delete in how many minutes?",
        placeholder="Enter number of minutes (e.g., 5, 30, 60)...",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            minutes_int = int(self.minutes.value)
            if minutes_int < 1:
                await interaction.followup.send("❌ Minutes must be at least 1.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Please enter a valid number for minutes.", ephemeral=True)
            return
        
        target_data = {
            "channel_ids": self.selected_channels
        }
        
        deletion_id = self.cog.schedule_deletion(
            interaction.guild.id,
            "voice_channels",
            target_data,
            minutes_int,
            interaction.user.id
        )
        
        embed = discord.Embed(
            title="✅ Voice Channel Deletion Scheduled",
            description=f"Scheduled deletion of {len(self.selected_channels)} voice channel(s) in {minutes_int} minute(s)",
            color=discord.Color.green()
        )
        embed.add_field(name="Deletion ID", value=str(deletion_id), inline=True)
        embed.add_field(name="Voice Channels", value=str(len(self.selected_channels)), inline=True)
        embed.add_field(name="Scheduled Time", value=f"<t:{int((datetime.utcnow() + timedelta(minutes=minutes_int)).timestamp())}:R>", inline=True)
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class CategoryDeletionView(discord.ui.View):
    def __init__(self, cog, user, config):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.config = config
        self.selected_categories = []
        self.delete_channels = False
        
        self.add_item(CategorySelectDropdown(self))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user
    
    @discord.ui.button(label="Delete Category Only", style=discord.ButtonStyle.primary, row=1)
    async def delete_category_only(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_categories:
            await interaction.response.send_message("❌ No categories selected.", ephemeral=True)
            return
        
        self.delete_channels = False
        modal = CategoryDeletionModal(self.cog, self.user, self.config, self.selected_categories, self.delete_channels)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Delete Category + Channels", style=discord.ButtonStyle.danger, row=1)
    async def delete_category_and_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_categories:
            await interaction.response.send_message("❌ No categories selected.", ephemeral=True)
            return
        
        self.delete_channels = True
        modal = CategoryDeletionModal(self.cog, self.user, self.config, self.selected_categories, self.delete_channels)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Back", emoji="⬅️", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MainMenuView(self.cog, self.user, self.config)
        embed = discord.Embed(
            title="🗑️ Delete Period System",
            description="Advanced scheduled deletion management system",
            color=discord.Color.red()
        )
        embed.add_field(
            name="⚙️ System Status",
            value=f"Status: {'🟢 Enabled' if self.config.enabled else '🔴 Disabled'}\nLog Channel: {'✅ Set' if self.config.log_channel_id else '❌ Not Set'}",
            inline=True
        )
        embed.add_field(
            name="📊 Scheduled Deletions",
            value=f"Active: {len(self.config.scheduled_deletions)}",
            inline=True
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)

class CategorySelectDropdown(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        
        options = []
        for category in parent_view.user.guild.categories[:25]:
            channel_count = len(category.channels)
            options.append(discord.SelectOption(
                label=category.name,
                value=str(category.id),
                description=f"{channel_count} channel(s) in this category"
            ))
        
        if not options:
            options.append(discord.SelectOption(
                label="No categories found",
                value="none",
                description="This server has no categories"
            ))
        
        super().__init__(
            placeholder="Select categories...",
            min_values=1,
            max_values=len(options) if options[0].value != "none" else 1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("❌ No categories available.", ephemeral=True)
            return
        self.parent_view.selected_categories = [int(category_id) for category_id in self.values]
        
        selected_names = []
        total_channels = 0
        for category_id in self.parent_view.selected_categories:
            category = interaction.guild.get_channel(category_id)
            if category:
                selected_names.append(f"{category.name} ({len(category.channels)} channels)")
                total_channels += len(category.channels)
        
        embed = discord.Embed(
            title="📂 Categories Selected",
            description=f"Selected {len(self.parent_view.selected_categories)} categor{'y' if len(self.parent_view.selected_categories) == 1 else 'ies'} with {total_channels} total channels:",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="Selected Categories",
            value="\n".join(selected_names[:10]) + (f"\n... and {len(selected_names) - 10} more" if len(selected_names) > 10 else ""),
            inline=False
        )
        embed.add_field(
            name="⚠️ Deletion Options",
            value="• **Category Only**: Moves channels out of category, then deletes category\n• **Category + Channels**: Deletes all channels in category, then deletes category",
            inline=False
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class CategoryDeletionModal(discord.ui.Modal):
    def __init__(self, cog, user, config, selected_categories, delete_channels):
        super().__init__(title="Schedule Category Deletion")
        self.cog = cog
        self.user = user
        self.config = config
        self.selected_categories = selected_categories
        self.delete_channels = delete_channels
    
    minutes = discord.ui.TextInput(
        label="Delete in how many minutes?",
        placeholder="Enter number of minutes (e.g., 5, 30, 60)...",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            minutes_int = int(self.minutes.value)
            if minutes_int < 1:
                await interaction.followup.send("❌ Minutes must be at least 1.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Please enter a valid number for minutes.", ephemeral=True)
            return
        
        target_data = {
            "category_ids": self.selected_categories,
            "delete_channels": self.delete_channels
        }
        
        deletion_id = self.cog.schedule_deletion(
            interaction.guild.id,
            "categories",
            target_data,
            minutes_int,
            interaction.user.id
        )
        
        action_type = "Category + Channel Deletion" if self.delete_channels else "Category Deletion"
        
        embed = discord.Embed(
            title=f"✅ {action_type} Scheduled",
            description=f"Scheduled {action_type.lower()} of {len(self.selected_categories)} categor{'y' if len(self.selected_categories) == 1 else 'ies'} in {minutes_int} minute(s)",
            color=discord.Color.green()
        )
        embed.add_field(name="Deletion ID", value=str(deletion_id), inline=True)
        embed.add_field(name="Categories", value=str(len(self.selected_categories)), inline=True)
        embed.add_field(name="Include Channels", value="✅ Yes" if self.delete_channels else "❌ No", inline=True)
        embed.add_field(name="Scheduled Time", value=f"<t:{int((datetime.utcnow() + timedelta(minutes=minutes_int)).timestamp())}:R>", inline=True)
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class RoleDeletionView(discord.ui.View):
    def __init__(self, cog, user, config):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.config = config
        self.selected_roles = []
        
        self.add_item(RoleSelectDropdown(self))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user
    
    @discord.ui.button(label="Schedule Deletion", style=discord.ButtonStyle.danger, row=1)
    async def schedule_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_roles:
            await interaction.response.send_message("❌ No roles selected.", ephemeral=True)
            return
        
        modal = RoleDeletionModal(self.cog, self.user, self.config, self.selected_roles)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Back", emoji="⬅️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MainMenuView(self.cog, self.user, self.config)
        embed = discord.Embed(
            title="🗑️ Delete Period System",
            description="Advanced scheduled deletion management system",
            color=discord.Color.red()
        )
        embed.add_field(
            name="⚙️ System Status",
            value=f"Status: {'🟢 Enabled' if self.config.enabled else '🔴 Disabled'}\nLog Channel: {'✅ Set' if self.config.log_channel_id else '❌ Not Set'}",
            inline=True
        )
        embed.add_field(
            name="📊 Scheduled Deletions",
            value=f"Active: {len(self.config.scheduled_deletions)}",
            inline=True
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)

class RoleSelectDropdown(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        
        options = []
        user_top_role = parent_view.user.top_role
        bot_member = parent_view.user.guild.get_member(parent_view.user.guild.me.id)
        bot_top_role = bot_member.top_role if bot_member else None
        
        for role in parent_view.user.guild.roles:
            if (role.name != "@everyone" and 
                role < user_top_role and 
                (bot_top_role is None or role < bot_top_role) and
                not role.managed):
                
                member_count = len(role.members)
                options.append(discord.SelectOption(
                    label=role.name,
                    value=str(role.id),
                    description=f"{member_count} member(s) have this role"
                ))
        
        options = options[:25]
        
        if not options:
            options.append(discord.SelectOption(
                label="No deletable roles found",
                value="none",
                description="No roles available for deletion"
            ))
        
        super().__init__(
            placeholder="Select roles...",
            min_values=1,
            max_values=len(options) if options[0].value != "none" else 1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("❌ No deletable roles available.", ephemeral=True)
            return
        
        self.parent_view.selected_roles = [int(role_id) for role_id in self.values]
        
        selected_names = []
        total_members = 0
        for role_id in self.parent_view.selected_roles:
            role = interaction.guild.get_role(role_id)
            if role:
                member_count = len(role.members)
                selected_names.append(f"{role.name} ({member_count} members)")
                total_members += member_count
        
        embed = discord.Embed(
            title="👥 Roles Selected",
            description=f"Selected {len(self.parent_view.selected_roles)} role(s) affecting {total_members} total member assignments:",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="Selected Roles",
            value="\n".join(selected_names[:10]) + (f"\n... and {len(selected_names) - 10} more" if len(selected_names) > 10 else ""),
            inline=False
        )
        embed.add_field(
            name="⚠️ Warning",
            value="Deleting roles will remove them from all members who have them!",
            inline=False
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class RoleDeletionModal(discord.ui.Modal):
    def __init__(self, cog, user, config, selected_roles):
        super().__init__(title="Schedule Role Deletion")
        self.cog = cog
        self.user = user
        self.config = config
        self.selected_roles = selected_roles
    
    minutes = discord.ui.TextInput(
        label="Delete in how many minutes?",
        placeholder="Enter number of minutes (e.g., 5, 30, 60)...",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            minutes_int = int(self.minutes.value)
            if minutes_int < 1:
                await interaction.followup.send("❌ Minutes must be at least 1.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Please enter a valid number for minutes.", ephemeral=True)
            return
        
        target_data = {
            "role_ids": self.selected_roles
        }
        
        deletion_id = self.cog.schedule_deletion(
            interaction.guild.id,
            "roles",
            target_data,
            minutes_int,
            interaction.user.id
        )
        
        embed = discord.Embed(
            title="✅ Role Deletion Scheduled",
            description=f"Scheduled deletion of {len(self.selected_roles)} role(s) in {minutes_int} minute(s)",
            color=discord.Color.green()
        )
        embed.add_field(name="Deletion ID", value=str(deletion_id), inline=True)
        embed.add_field(name="Roles", value=str(len(self.selected_roles)), inline=True)
        embed.add_field(name="Scheduled Time", value=f"<t:{int((datetime.utcnow() + timedelta(minutes=minutes_int)).timestamp())}:R>", inline=True)
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class WebhookDeletionView(discord.ui.View):
    def __init__(self, cog, user, config):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.config = config
        self.selected_webhooks = []
        self.webhooks_data = []
        
        asyncio.create_task(self.load_webhooks())
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user
    
    async def load_webhooks(self):
        try:
            self.webhooks_data = []
            for channel in self.user.guild.text_channels:
                try:
                    webhooks = await channel.webhooks()
                    for webhook in webhooks:
                        self.webhooks_data.append({
                            "id": webhook.id,
                            "name": webhook.name,
                            "channel": channel.name,
                            "channel_id": channel.id
                        })
                except:
                    continue
        except Exception as e:
            print(f"Error loading webhooks: {e}")
    
    @discord.ui.button(label="Refresh Webhooks", style=discord.ButtonStyle.secondary, row=0)
    async def refresh_webhooks(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.load_webhooks()
        
        if not self.webhooks_data:
            embed = discord.Embed(
                title="🔗 No Webhooks Found",
                description="This server has no webhooks to delete.",
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="🔗 Schedule Webhook Deletion",
                description=f"Found {len(self.webhooks_data)} webhook(s). Select webhooks to schedule for deletion:",
                color=discord.Color.orange()
            )
            
            webhook_list = []
            for i, webhook in enumerate(self.webhooks_data[:10]):
                webhook_list.append(f"{i+1}. **{webhook['name']}** in #{webhook['channel']}")
            
            if webhook_list:
                embed.add_field(
                    name="Available Webhooks",
                    value="\n".join(webhook_list) + (f"\n... and {len(self.webhooks_data) - 10} more" if len(self.webhooks_data) > 10 else ""),
                    inline=False
                )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        
        self.clear_items()
        self.add_item(WebhookSelectDropdown(self))
        self.add_item(self.refresh_webhooks)
        self.add_item(self.schedule_deletion)
        self.add_item(self.back)
        
        await interaction.followup.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Schedule Deletion", style=discord.ButtonStyle.danger, row=1)
    async def schedule_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_webhooks:
            await interaction.response.send_message("❌ No webhooks selected.", ephemeral=True)
            return
        
        modal = WebhookDeletionModal(self.cog, self.user, self.config, self.selected_webhooks)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Back", emoji="⬅️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MainMenuView(self.cog, self.user, self.config)
        embed = discord.Embed(
            title="🗑️ Delete Period System",
            description="Advanced scheduled deletion management system",
            color=discord.Color.red()
        )
        embed.add_field(
            name="⚙️ System Status",
            value=f"Status: {'🟢 Enabled' if self.config.enabled else '🔴 Disabled'}\nLog Channel: {'✅ Set' if self.config.log_channel_id else '❌ Not Set'}",
            inline=True
        )
        embed.add_field(
            name="📊 Scheduled Deletions",
            value=f"Active: {len(self.config.scheduled_deletions)}",
            inline=True
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)

class WebhookSelectDropdown(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        
        options = []
        for webhook in parent_view.webhooks_data[:25]:
            options.append(discord.SelectOption(
                label=webhook['name'],
                value=str(webhook['id']),
                description=f"Channel: #{webhook['channel']}"
            ))
        
        if not options:
            options.append(discord.SelectOption(
                label="No webhooks found",
                value="none",
                description="This server has no webhooks"
            ))
        
        super().__init__(
            placeholder="Select webhooks...",
            min_values=1,
            max_values=len(options) if options[0].value != "none" else 1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("❌ No webhooks available.", ephemeral=True)
            return
        
        selected_webhook_ids = [int(webhook_id) for webhook_id in self.values]
        self.parent_view.selected_webhooks = []
        
        selected_names = []
        for webhook_data in self.parent_view.webhooks_data:
            if webhook_data['id'] in selected_webhook_ids:
                self.parent_view.selected_webhooks.append(webhook_data)
                selected_names.append(f"**{webhook_data['name']}** in #{webhook_data['channel']}")
        
        embed = discord.Embed(
            title="🔗 Webhooks Selected",
            description=f"Selected {len(self.parent_view.selected_webhooks)} webhook(s):",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="Selected Webhooks",
            value="\n".join(selected_names[:10]) + (f"\n... and {len(selected_names) - 10} more" if len(selected_names) > 10 else ""),
            inline=False
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class WebhookDeletionModal(discord.ui.Modal):
    def __init__(self, cog, user, config, selected_webhooks):
        super().__init__(title="Schedule Webhook Deletion")
        self.cog = cog
        self.user = user
        self.config = config
        self.selected_webhooks = selected_webhooks
    
    minutes = discord.ui.TextInput(
        label="Delete in how many minutes?",
        placeholder="Enter number of minutes (e.g., 5, 30, 60)...",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            minutes_int = int(self.minutes.value)
            if minutes_int < 1:
                await interaction.followup.send("❌ Minutes must be at least 1.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Please enter a valid number for minutes.", ephemeral=True)
            return
        
        target_data = {
            "webhooks": self.selected_webhooks
        }
        
        deletion_id = self.cog.schedule_deletion(
            interaction.guild.id,
            "webhooks",
            target_data,
            minutes_int,
            interaction.user.id
        )
        
        embed = discord.Embed(
            title="✅ Webhook Deletion Scheduled",
            description=f"Scheduled deletion of {len(self.selected_webhooks)} webhook(s) in {minutes_int} minute(s)",
            color=discord.Color.green()
        )
        embed.add_field(name="Deletion ID", value=str(deletion_id), inline=True)
        embed.add_field(name="Webhooks", value=str(len(self.selected_webhooks)), inline=True)
        embed.add_field(name="Scheduled Time", value=f"<t:{int((datetime.utcnow() + timedelta(minutes=minutes_int)).timestamp())}:R>", inline=True)
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class SettingsView(discord.ui.View):
    def __init__(self, cog, user, config):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.config = config
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user
    
    @discord.ui.button(label="Toggle System", style=discord.ButtonStyle.primary, row=0)
    async def toggle_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.config.enabled = not self.config.enabled
        self.cog.save_config(interaction.guild.id)
        
        status = "🟢 Enabled" if self.config.enabled else "🔴 Disabled"
        
        embed = discord.Embed(
            title="⚙️ System Status Updated",
            description=f"Delete Period system is now {status}",
            color=discord.Color.green() if self.config.enabled else discord.Color.red()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Set Log Channel", style=discord.ButtonStyle.secondary, row=0)
    async def set_log_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LogChannelView(self.cog, self.user, self.config)
        embed = discord.Embed(
            title="📝 Set Log Channel",
            description="Select a channel for deletion logs:",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="View Scheduled Deletions", style=discord.ButtonStyle.secondary, row=1)
    async def view_scheduled(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.config.scheduled_deletions:
            embed = discord.Embed(
                title="📊 No Scheduled Deletions",
                description="There are currently no scheduled deletions.",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📊 Scheduled Deletions",
            description=f"Currently {len(self.config.scheduled_deletions)} scheduled deletion(s):",
            color=discord.Color.blue()
        )
        
        for i, deletion in enumerate(self.config.scheduled_deletions[:10]):
            scheduled_time = datetime.fromisoformat(deletion["scheduled_time"])
            user = interaction.guild.get_member(deletion["user_id"])
            user_name = user.display_name if user else "Unknown User"
            
            embed.add_field(
                name=f"ID: {deletion['id']} - {deletion['type'].title()}",
                value=f"Scheduled by: {user_name}\nTime: <t:{int(scheduled_time.timestamp())}:R>",
                inline=True
            )
        
        if len(self.config.scheduled_deletions) > 10:
            embed.add_field(
                name="...",
                value=f"And {len(self.config.scheduled_deletions) - 10} more",
                inline=True
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Cancel Scheduled Deletion", style=discord.ButtonStyle.danger, row=1)
    async def cancel_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.config.scheduled_deletions:
            await interaction.response.send_message("❌ No scheduled deletions to cancel.", ephemeral=True)
            return
        
        modal = CancelDeletionModal(self.cog, self.user, self.config)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Back", emoji="⬅️", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MainMenuView(self.cog, self.user, self.config)
        embed = discord.Embed(
            title="🗑️ Delete Period System",
            description="Advanced scheduled deletion management system",
            color=discord.Color.red()
        )
        embed.add_field(
            name="⚙️ System Status",
            value=f"Status: {'🟢 Enabled' if self.config.enabled else '🔴 Disabled'}\nLog Channel: {'✅ Set' if self.config.log_channel_id else '❌ Not Set'}",
            inline=True
        )
        embed.add_field(
            name="📊 Scheduled Deletions",
            value=f"Active: {len(self.config.scheduled_deletions)}",
            inline=True
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)

class LogChannelView(discord.ui.View):
    def __init__(self, cog, user, config):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.config = config
        
        self.add_item(LogChannelSelectDropdown(self))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user
    
    @discord.ui.button(label="Remove Log Channel", style=discord.ButtonStyle.danger, row=1)
    async def remove_log_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.config.log_channel_id = None
        self.cog.save_config(interaction.guild.id)
        
        embed = discord.Embed(
            title="✅ Log Channel Removed",
            description="Log channel has been removed. Deletion logs will no longer be sent.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Back", emoji="⬅️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = SettingsView(self.cog, self.user, self.config)
        embed = discord.Embed(
            title="⚙️ Delete Period Settings",
            description="Configure the Delete Period system:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📊 Current Status",
            value=f"System: {'🟢 Enabled' if self.config.enabled else '🔴 Disabled'}\nLog Channel: {'✅ Set' if self.config.log_channel_id else '❌ Not Set'}",
            inline=False
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=view)

class LogChannelSelectDropdown(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        
        options = []
        for channel in parent_view.user.guild.text_channels[:25]:
            options.append(discord.SelectOption(
                label=f"#{channel.name}",
                value=str(channel.id),
                description=f"Category: {channel.category.name if channel.category else 'No Category'}"
            ))
        
        super().__init__(
            placeholder="Select a log channel...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        channel = interaction.guild.get_channel(channel_id)
        
        if not channel:
            await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
            return
        
        self.parent_view.config.log_channel_id = channel_id
        self.parent_view.cog.save_config(interaction.guild.id)
        
        embed = discord.Embed(
            title="✅ Log Channel Set",
            description=f"Log channel has been set to {channel.mention}",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class CancelDeletionModal(discord.ui.Modal):
    def __init__(self, cog, user, config):
        super().__init__(title="Cancel Scheduled Deletion")
        self.cog = cog
        self.user = user
        self.config = config
    
    deletion_id = discord.ui.TextInput(
        label="Deletion ID",
        placeholder="Enter the deletion ID to cancel...",
        style=discord.TextStyle.short,
        required=True,
        max_length=50
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        deletion_id = self.deletion_id.value.strip()
        
        for i, deletion in enumerate(self.config.scheduled_deletions):
            if str(deletion["id"]) == deletion_id:
                if (deletion["user_id"] != interaction.user.id and 
                    not interaction.user.guild_permissions.administrator):
                    await interaction.followup.send("❌ You can only cancel your own scheduled deletions unless you're an administrator.", ephemeral=True)
                    return
                
                removed_deletion = self.config.scheduled_deletions.pop(i)
                self.cog.save_config(interaction.guild.id)
                
                embed = discord.Embed(
                    title="✅ Deletion Cancelled",
                    description=f"Successfully cancelled scheduled {removed_deletion['type']} deletion",
                    color=discord.Color.green()
                )
                embed.add_field(name="Deletion ID", value=deletion_id, inline=True)
                embed.add_field(name="Type", value=removed_deletion['type'].title(), inline=True)
                embed.set_footer(text="Made By TheHolyOneZ")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
        
        await interaction.followup.send("❌ Deletion ID not found.", ephemeral=True)


def setup(bot):
    cog = DeletePeriod(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog