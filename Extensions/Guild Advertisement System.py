import discord
from discord.ext import commands, tasks
import json
import asyncio
import os
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional, Any
import logging
import random

logger = logging.getLogger(__name__)

class GuildAdvertisementSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_path = "data/Z_Ads/guild_ads_config.json"
        self.pending_requests_path = "data/Z_Ads/pending_ad_requests.json"
        self.approved_connections_path = "data/Z_Ads/approved_ad_connections.json"
        self.advertisements_path = "data/Z_Ads/guild_advertisements.json"
        self.guild_cache_path = "data/Z_Ads/guild_cache.json"
        self.audit_log_path = "data/Z_Ads/guild_ads_audit.json"
        self.blacklist_path = "data/Z_Ads/guild_ads_blacklist.json"
        self.whitelist_path = "data/Z_Ads/guild_ads_whitelist.json"
        self.rate_limits_path = "data/Z_Ads/guild_ads_rate_limits.json"
        
        self.config = self._load_json(self.config_path, {})
        self.pending_requests = self._load_json(self.pending_requests_path, {})
        self.approved_connections = self._load_json(self.approved_connections_path, {})
        self.advertisements = self._load_json(self.advertisements_path, {})
        self.guild_cache = self._load_json(self.guild_cache_path, {})
        self.audit_log = self._load_json(self.audit_log_path, {})
        self.blacklist = self._load_json(self.blacklist_path, {})
        self.whitelist = self._load_json(self.whitelist_path, {})
        self.rate_limits = self._load_json(self.rate_limits_path, {})
        
        self.ad_scheduler.start()
        
    def _load_json(self, path: str, default: dict) -> dict:
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump(default, f, indent=4)
            return default
        
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {path}: {e}")
            return default
    
    def _save_json(self, path: str, data: dict):
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving {path}: {e}")
    
    def _log_audit_event(self, guild_id: int, event_type: str, details: dict):
        if str(guild_id) not in self.audit_log:
            self.audit_log[str(guild_id)] = []
        
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "details": details
        }
        
        self.audit_log[str(guild_id)].append(event)
        
        if len(self.audit_log[str(guild_id)]) > 100:
            self.audit_log[str(guild_id)] = self.audit_log[str(guild_id)][-100:]
        
        self._save_json(self.audit_log_path, self.audit_log)
    
    def _is_blacklisted(self, requester_guild_id: int, target_guild_id: int) -> bool:
        target_blacklist = self.blacklist.get(str(target_guild_id), [])
        return requester_guild_id in target_blacklist
    
    def _is_whitelisted(self, requester_guild_id: int, target_guild_id: int) -> bool:
        target_whitelist = self.whitelist.get(str(target_guild_id), {})
        
        if not target_whitelist.get("enabled", False):
            return True
        
        requester_guild = self.bot.get_guild(requester_guild_id)
        if not requester_guild:
            return False
        
        if "guild_ids" in target_whitelist:
            if requester_guild_id in target_whitelist["guild_ids"]:
                return True
        
        if "min_members" in target_whitelist:
            if len(requester_guild.members) < target_whitelist["min_members"]:
                return False
        
        if "max_members" in target_whitelist:
            if len(requester_guild.members) > target_whitelist["max_members"]:
                return False
        
        if "min_age_days" in target_whitelist:
            guild_age = (datetime.now() - requester_guild.created_at.replace(tzinfo=None)).days
            if guild_age < target_whitelist["min_age_days"]:
                return False
        
        return True
    
    def _check_rate_limit(self, requester_guild_id: int, target_guild_id: int) -> tuple[bool, int]:
        rate_key = f"{requester_guild_id}_{target_guild_id}"
        current_time = datetime.now()
        
        if rate_key in self.rate_limits:
            last_request = datetime.fromisoformat(self.rate_limits[rate_key]["last_request"])
            cooldown_hours = self.rate_limits[rate_key].get("cooldown_hours", 24)
            
            time_diff = current_time - last_request
            if time_diff.total_seconds() < (cooldown_hours * 3600):
                remaining_seconds = (cooldown_hours * 3600) - time_diff.total_seconds()
                return False, int(remaining_seconds)
        
        self.rate_limits[rate_key] = {
            "last_request": current_time.isoformat(),
            "cooldown_hours": 24,
            "request_count": self.rate_limits.get(rate_key, {}).get("request_count", 0) + 1
        }
        self._save_json(self.rate_limits_path, self.rate_limits)
        
        return True, 0
    
    def _cache_guild_info(self, guild: discord.Guild):
        self.guild_cache[str(guild.id)] = {
            "name": guild.name,
            "member_count": len(guild.members),
            "owner_id": guild.owner_id,
            "icon_url": guild.icon.url if guild.icon else None,
            "created_at": guild.created_at.isoformat(),
            "cached_at": datetime.now().isoformat()
        }
        self._save_json(self.guild_cache_path, self.guild_cache)
    
    def _get_cached_guild_info(self, guild_id: int) -> dict:
        return self.guild_cache.get(str(guild_id), {})
    
    def _is_admin_or_owner(self, member: discord.Member) -> bool:
        return (member.guild_permissions.administrator or 
                member.id == member.guild.owner_id)
    
    def _replace_variables(self, text: str, origin_guild_info: dict, 
                          target_guild_info: dict, role: discord.Role = None) -> str:
        replacements = {
            "{server}": target_guild_info.get("name", "Unknown Server"),
            "{origin_server}": origin_guild_info.get("name", "Unknown Server"),
            "{role}": role.mention if role else "",
            "{member_count}": str(target_guild_info.get("member_count", 0)),
            "{origin_member_count}": str(origin_guild_info.get("member_count", 0))
        }
        
        for var, replacement in replacements.items():
            text = text.replace(var, replacement)
        
        return text

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            self._cache_guild_info(guild)
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        self._cache_guild_info(guild)
    
    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        self._cache_guild_info(after)
    
    @tasks.loop(minutes=1)
    async def ad_scheduler(self):
        current_time = datetime.now()
        current_hour = current_time.hour
        current_minute = current_time.minute
        current_date = current_time.date().isoformat()
        
        for connection_key, connection_data in self.approved_connections.items():
            try:
                if connection_data.get("last_ad_date") != current_date:
                    connection_data["ads_sent_today"] = 0
                    connection_data["last_ad_date"] = current_date
                
                if connection_data["ads_sent_today"] >= connection_data["max_ads_per_day"]:
                    continue
                
                if not self._is_time_allowed(current_hour, current_minute, connection_data):
                    continue
                
                requester_guild_id = connection_data["requester_guild_id"]
                target_guild_id = connection_data["target_guild_id"]
                
                requester_guild = self.bot.get_guild(requester_guild_id)
                target_guild = self.bot.get_guild(target_guild_id)
                
                if not requester_guild or not target_guild:
                    continue
                
                target_channel = target_guild.get_channel(connection_data["channel_id"])
                if not target_channel:
                    continue
                
                guild_ads = self.advertisements.get(str(requester_guild_id), {})
                active_ads = [ad_data for ad_data in guild_ads.values() if ad_data.get("active", True)]
                
                if not active_ads:
                    continue
                
                selected_ad = random.choice(active_ads)
                
                role = None
                if connection_data.get("role_id"):
                    role = target_guild.get_role(connection_data["role_id"])
                
                requester_guild_info = self._get_cached_guild_info(requester_guild_id)
                target_guild_info = self._get_cached_guild_info(target_guild_id)
                
                embed = discord.Embed(
                    title=self._replace_variables(selected_ad["title"], requester_guild_info, target_guild_info, role),
                    description=self._replace_variables(selected_ad["description"], requester_guild_info, target_guild_info, role),
                    color=discord.Color(selected_ad["color"]),
                    timestamp=datetime.now()
                )
                
                if selected_ad.get("image"):
                    embed.set_image(url=selected_ad["image"])
                
                embed.set_footer(
                    text=f"Advertisement from {requester_guild_info.get('name', 'Unknown Server')}",
                    icon_url=requester_guild_info.get('icon_url')
                )
                
                content = role.mention if role else None
                await target_channel.send(content=content, embed=embed)
                
                connection_data["ads_sent_today"] += 1
                
                self._log_audit_event(target_guild_id, "ad_sent", {
                    "from_guild": requester_guild_info.get("name", "Unknown"),
                    "from_guild_id": requester_guild_id,
                    "ad_title": selected_ad["title"],
                    "channel_id": target_channel.id,
                    "channel_name": target_channel.name
                })
                
                self._log_audit_event(requester_guild_id, "ad_delivered", {
                    "to_guild": target_guild_info.get("name", "Unknown"),
                    "to_guild_id": target_guild_id,
                    "ad_title": selected_ad["title"],
                    "channel_id": target_channel.id
                })
                
            except Exception as e:
                logger.error(f"Error sending scheduled ad: {e}")
        
        self._save_json(self.approved_connections_path, self.approved_connections)
    
    def _is_time_allowed(self, hour: int, minute: int, connection_data: dict) -> bool:
        allowed_hours = connection_data["allowed_hours"]
        allowed_minutes = connection_data["allowed_minutes"]
        
        if allowed_hours != "*":
            if "-" in allowed_hours:
                try:
                    start_hour, end_hour = map(int, allowed_hours.split("-"))
                    if not (start_hour <= hour <= end_hour):
                        return False
                except:
                    return False
            else:
                try:
                    allowed_hour_list = [int(h.strip()) for h in allowed_hours.split(",")]
                    if hour not in allowed_hour_list:
                        return False
                except:
                    return False
        
        if allowed_minutes != "*":
            try:
                allowed_minute_list = [int(m.strip()) for m in allowed_minutes.split(",")]
                if minute not in allowed_minute_list:
                    return False
            except:
                return False
        
        return True
    
    @commands.group(name="guildads", aliases=["gads", "ads"], invoke_without_command=True)
    async def guildads(self, ctx):
        
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🎯 Guild Advertisement System",
                description="**Professional cross-guild advertising with approval system**\n\n*Reach new audiences while respecting server boundaries*",
                color=discord.Color.from_rgb(88, 101, 242),
                timestamp=datetime.now()
            )
            
            embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            

            embed.add_field(
                name="📝 **For Advertisers**",
                value=(
                    f"`{ctx.prefix}guildads request <guild_id>` • Request advertising permission\n"
                    f"`{ctx.prefix}guildads create` • Create new advertisement\n"
                    f"`{ctx.prefix}guildads list` • View your advertisements\n"
                    f"`{ctx.prefix}guildads edit <ad_id>` • Edit existing advertisement\n"
                    f"`{ctx.prefix}guildads toggle <ad_id>` • Enable/disable advertisement\n"
                    f"`{ctx.prefix}guildads test <ad_id>` • Preview advertisement"
                ),
                inline=False
            )
            

            embed.add_field(
                name="⚙️ **For Guild Owners**",
                value=(
                    f"`{ctx.prefix}guildads pending` • View pending requests\n"
                    f"`{ctx.prefix}guildads connections` • View approved connections\n"
                    f"`{ctx.prefix}guildads revoke <guild_id>` • Revoke advertising permission\n"
                    f"`{ctx.prefix}guildads stats` • View detailed statistics\n"
                    f"`{ctx.prefix}guildads audit` • View audit log\n"
                    f"`{ctx.prefix}guildads whitelist` • Manage whitelist settings\n"
                    f"`{ctx.prefix}guildads blacklist` • Manage blacklist settings"
                ),
                inline=False
            )
            

            embed.add_field(
                name="✨ **Key Features**",
                value=(
                    "🔹 **Smart Variables:** `{server}`, `{origin_server}`, `{role}`, `{member_count}`\n"
                    "🔹 **Time Scheduling:** Flexible hour/minute restrictions\n"
                    "🔹 **Daily Limits:** Configurable maximum ads per day\n"
                    "🔹 **Role Mentions:** Optional role pinging with approval\n"
                    "🔹 **Interactive Setup:** Beautiful embeds with buttons\n"
                    "🔹 **Security Controls:** Whitelist/blacklist system\n"
                    "🔹 **Audit Logging:** Complete activity tracking\n"
                    "🔹 **Auto-cleanup:** Smart data management"
                ),
                inline=False
            )
            

            embed.add_field(
                name="📚 **Quick Start**",
                value=(
                    f"`{ctx.prefix}guildads request 123456789` • Request to advertise\n"
                    f"`{ctx.prefix}guildads create` • Create new advertisement\n"
                    f"`{ctx.prefix}guildads stats` • View statistics"
                ),
                inline=False
            )
            

            embed.add_field(
                name="🔒 **Security & Control**",
                value="Only guild owners can approve requests • Only admins can manage ads • Complete audit trail • Advanced filtering options",
                inline=False
            )
            
            embed.set_footer(
                text=f"Guild Advertisement System • Powered by {self.bot.user.name}",
                icon_url=ctx.guild.icon.url if ctx.guild and ctx.guild.icon else None
            )
            
            await ctx.send(embed=embed)
    
    @guildads.command(name="request", aliases=["req"])
    async def request_advertising(self, ctx, guild_id: str):
        if not self._is_admin_or_owner(ctx.author):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only administrators and guild owners can request advertising permissions.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        try:
            target_guild_id = int(guild_id)
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Guild ID",
                description="Please provide a valid guild ID (numbers only).",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        if target_guild_id == ctx.guild.id:
            embed = discord.Embed(
                title="❌ Self-Advertising Not Allowed",
                description="You cannot request to advertise in your own guild!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        target_guild = self.bot.get_guild(target_guild_id)
        if not target_guild:
            embed = discord.Embed(
                title="❌ Guild Not Found",
                description="Target guild not found or bot is not in that guild!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        if self._is_blacklisted(ctx.guild.id, target_guild_id):
            embed = discord.Embed(
                title="❌ Blacklisted",
                description="Your guild has been blacklisted by the target guild.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        if not self._is_whitelisted(ctx.guild.id, target_guild_id):
            embed = discord.Embed(
                title="❌ Not Whitelisted",
                description="Your guild does not meet the whitelist requirements for the target guild.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        is_allowed, cooldown_remaining = self._check_rate_limit(ctx.guild.id, target_guild_id)
        if not is_allowed:
            hours = cooldown_remaining // 3600
            minutes = (cooldown_remaining % 3600) // 60
            embed = discord.Embed(
                title="⏰ Rate Limited",
                description=f"You must wait {hours}h {minutes}m before making another request to this guild.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        
        self._cache_guild_info(ctx.guild)
        self._cache_guild_info(target_guild)
        
        connection_key = f"{ctx.guild.id}_{target_guild_id}"
        if connection_key in self.pending_requests:
            embed = discord.Embed(
                title="⏳ Request Already Pending",
                description=f"You already have a pending request for **{target_guild.name}**!",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        
        if connection_key in self.approved_connections:
            embed = discord.Embed(
                title="✅ Already Approved",
                description=f"You already have advertising permission for **{target_guild.name}**!",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            return
        
        self.pending_requests[connection_key] = {
            "requester_guild_id": ctx.guild.id,
            "requester_guild_name": ctx.guild.name,
            "target_guild_id": target_guild_id,
            "requested_at": datetime.now().isoformat(),
            "requester_user_id": ctx.author.id
        }
        
        self._save_json(self.pending_requests_path, self.pending_requests)
        
        if target_guild.owner:
            embed = discord.Embed(
                title="📢 New Advertisement Request",
                description=f"**{ctx.guild.name}** wants to send advertisements to your server.",
                color=discord.Color.from_rgb(255, 165, 0),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📊 Guild Information",
                value=(
                    f"**🏢 Name:** {ctx.guild.name}\n"
                    f"**👥 Members:** {len(ctx.guild.members):,}\n"
                    f"**📅 Created:** {ctx.guild.created_at.strftime('%B %d, %Y')}\n"
                    f"**👤 Requested by:** {ctx.author.mention} (`{ctx.author}`)\n"
                    f"**🆔 Guild ID:** `{ctx.guild.id}`"
                ),
                inline=False
            )
            
            embed.add_field(
                name="⚠️ Important Information",
                value=(
                    "• You have full control over approval settings\n"
                    "• You can set specific channels, times, and limits\n"
                    "• You can revoke permission at any time\n"
                    "• Only you (guild owner) can approve this request"
                ),
                inline=False
            )
            
            embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
            embed.set_footer(
                text=f"From: {ctx.guild.name} • Guild Advertisement System",
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
            )
            
            view = AdRequestView(self, ctx.guild.id, target_guild_id, ctx.author.id)
            
            try:
                await target_guild.owner.send(embed=embed, view=view)
                
                success_embed = discord.Embed(
                    title="✅ Request Sent Successfully!",
                    description=f"Advertisement request sent to **{target_guild.name}** owner!",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                success_embed.add_field(
                    name="📋 What happens next?",
                    value=(
                        f"• The owner of **{target_guild.name}** will receive a DM\n"
                        f"• They can approve or deny your request\n"
                        f"• You'll be notified of their decision\n"
                        f"• If approved, you can create advertisements!"
                    ),
                    inline=False
                )
                success_embed.set_footer(text="Guild Advertisement System")
                
                await ctx.send(embed=success_embed)
                
            except discord.Forbidden:
                del self.pending_requests[connection_key]
                self._save_json(self.pending_requests_path, self.pending_requests)
                
                embed = discord.Embed(
                    title="❌ Could Not Send Request",
                    description="Could not send request to the target guild owner (DMs disabled).",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Guild Owner Not Found",
                description="Could not find the target guild owner!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
    
    @guildads.command(name="create", aliases=["new", "add"])
    async def create_advertisement(self, ctx):
        if not self._is_admin_or_owner(ctx.author):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only administrators and guild owners can create advertisements.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        has_connections = any(
            conn["requester_guild_id"] == ctx.guild.id 
            for conn in self.approved_connections.values()
        )
        
        if not has_connections:
            embed = discord.Embed(
                title="⚠️ No Approved Connections",
                description="You need approved advertising connections before creating advertisements.",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="🚀 Get Started",
                value=f"Use `{ctx.prefix}guildads request <guild_id>` to request advertising permission from other guilds.",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        modal = AdCreationModal(self, ctx.guild.id)
        
        embed = discord.Embed(
            title="📝 Create Advertisement",
            description="Click the button below to open the advertisement creation form.",
            color=discord.Color.blue()
        )
        
        class CreateAdView(discord.ui.View):
            def __init__(self, modal):
                super().__init__(timeout=300)
                self.modal = modal
            
            @discord.ui.button(label="📝 Create Advertisement", style=discord.ButtonStyle.primary, emoji="📝")
            async def create_ad(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Only the command user can use this button.", ephemeral=True)
                    return
                await interaction.response.send_modal(self.modal)
        
        view = CreateAdView(modal)
        await ctx.send(embed=embed, view=view)
    
    @guildads.command(name="list", aliases=["ls", "show"])
    async def list_advertisements(self, ctx):
        if not self._is_admin_or_owner(ctx.author):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only administrators and guild owners can view advertisements.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        guild_ads = self.advertisements.get(str(ctx.guild.id), {})
        
        if not guild_ads:
            embed = discord.Embed(
                title="📭 No Advertisements Found",
                description="No advertisements found for this guild.",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="🚀 Get Started",
                value=f"Use `{ctx.prefix}guildads create` to create your first advertisement!",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"📢 Advertisements for {ctx.guild.name}",
            description=f"Total advertisements: **{len(guild_ads)}**",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        for ad_id, ad_data in guild_ads.items():
            status_emoji = "🟢" if ad_data.get("active", True) else "🔴"
            status_text = "Active" if ad_data.get("active", True) else "Inactive"
            
            created_date = "Unknown"
            if "created_at" in ad_data:
                try:
                    created_date = datetime.fromisoformat(ad_data["created_at"]).strftime("%b %d, %Y")
                except:
                    pass
            
            embed.add_field(
                name=f"{status_emoji} {ad_id}: {ad_data['title'][:30]}{'...' if len(ad_data['title']) > 30 else ''}",
                value=f"**Status:** {status_text}\n**Created:** {created_date}",
                inline=True
            )
        
        embed.set_footer(
            text=f"Use {ctx.prefix}guildads edit <ad_id> to modify • {ctx.prefix}guildads toggle <ad_id> to enable/disable",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None
        )
        
        await ctx.send(embed=embed)
    
    @guildads.command(name="edit", aliases=["modify", "update"])
    async def edit_advertisement(self, ctx, ad_id: str):
        if not self._is_admin_or_owner(ctx.author):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only administrators and guild owners can edit advertisements.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        guild_ads = self.advertisements.get(str(ctx.guild.id), {})
        
        if ad_id not in guild_ads:
            embed = discord.Embed(
                title="❌ Advertisement Not Found",
                description=f"Advertisement `{ad_id}` not found!",
                color=discord.Color.red()
            )
            embed.add_field(
                name="💡 Available Advertisements",
                value=f"Use `{ctx.prefix}guildads list` to see all your advertisements.",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        modal = AdCreationModal(self, ctx.guild.id, edit_mode=True, ad_id=ad_id)
        
        current_ad = guild_ads[ad_id]
        embed = discord.Embed(
            title=f"✏️ Edit Advertisement: {ad_id}",
            description="Click the button below to edit this advertisement.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📋 Current Advertisement",
            value=f"**Title:** {current_ad['title']}\n**Status:** {'🟢 Active' if current_ad.get('active', True) else '🔴 Inactive'}",
            inline=False
        )
        
        class EditAdView(discord.ui.View):
            def __init__(self, modal):
                super().__init__(timeout=300)
                self.modal = modal
            
            @discord.ui.button(label="✏️ Edit Advertisement", style=discord.ButtonStyle.secondary, emoji="✏️")
            async def edit_ad(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Only the command user can use this button.", ephemeral=True)
                    return
                await interaction.response.send_modal(self.modal)
        
        view = EditAdView(modal)
        await ctx.send(embed=embed, view=view)
    
    @guildads.command(name="toggle", aliases=["enable", "disable"])
    async def toggle_advertisement(self, ctx, ad_id: str):
        if not self._is_admin_or_owner(ctx.author):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only administrators and guild owners can toggle advertisements.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        guild_ads = self.advertisements.get(str(ctx.guild.id), {})
        
        if ad_id not in guild_ads:
            embed = discord.Embed(
                title="❌ Advertisement Not Found",
                description=f"Advertisement `{ad_id}` not found!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        current_status = guild_ads[ad_id].get("active", True)
        guild_ads[ad_id]["active"] = not current_status
        guild_ads[ad_id]["last_modified"] = datetime.now().isoformat()
        
        self._save_json(self.advertisements_path, self.advertisements)
        
        new_status = guild_ads[ad_id]["active"]
        status_text = "enabled" if new_status else "disabled"
        status_emoji = "🟢" if new_status else "🔴"
        
        embed = discord.Embed(
            title=f"{status_emoji} Advertisement {status_text.title()}",
            description=f"Advertisement **{ad_id}** has been {status_text}.",
            color=discord.Color.green() if new_status else discord.Color.red(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📋 Advertisement Details",
            value=f"**Title:** {guild_ads[ad_id]['title']}\n**Status:** {status_emoji} {status_text.title()}",
            inline=False
        )
        
        embed.set_footer(text=f"Advertisement ID: {ad_id}")
        
        await ctx.send(embed=embed)
    
    @guildads.command(name="test", aliases=["preview"])
    async def test_advertisement(self, ctx, ad_id: str):
        if not self._is_admin_or_owner(ctx.author):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only administrators and guild owners can test advertisements.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        guild_ads = self.advertisements.get(str(ctx.guild.id), {})
        
        if ad_id not in guild_ads:
            embed = discord.Embed(
                title="❌ Advertisement Not Found",
                description=f"Advertisement `{ad_id}` not found!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        selected_ad = guild_ads[ad_id]
        
        self._cache_guild_info(ctx.guild)
        guild_info = self._get_cached_guild_info(ctx.guild.id)
        
        embed = discord.Embed(
            title=self._replace_variables(selected_ad["title"], guild_info, guild_info),
            description=self._replace_variables(selected_ad["description"], guild_info, guild_info),
            color=discord.Color(selected_ad["color"]),
            timestamp=datetime.now()
        )
        
        if selected_ad.get("image"):
            embed.set_image(url=selected_ad["image"])
        
        embed.set_footer(text=f"🧪 TEST PREVIEW • Advertisement ID: {ad_id}")
        
        preview_embed = discord.Embed(
            title="🧪 Advertisement Preview",
            description=f"Here's how your advertisement `{ad_id}` will look:",
            color=discord.Color.blue()
        )
        
        await ctx.send(embed=preview_embed)
        await ctx.send(embed=embed)
    
    @guildads.command(name="connections", aliases=["conn", "links"])
    async def view_connections(self, ctx):
        if not self._is_admin_or_owner(ctx.author):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only administrators and guild owners can view connections.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        incoming_connections = []
        outgoing_connections = []
        
        for connection_key, connection_data in self.approved_connections.items():
            if connection_data["target_guild_id"] == ctx.guild.id:
                requester_guild_info = self._get_cached_guild_info(connection_data["requester_guild_id"])
                if requester_guild_info:
                    incoming_connections.append({
                        "guild_info": requester_guild_info,
                        "data": connection_data,
                        "key": connection_key
                    })
            elif connection_data["requester_guild_id"] == ctx.guild.id:
                target_guild_info = self._get_cached_guild_info(connection_data["target_guild_id"])
                if target_guild_info:
                    outgoing_connections.append({
                        "guild_info": target_guild_info,
                        "data": connection_data,
                        "key": connection_key
                    })
        
        embed = discord.Embed(
            title="🔗 Advertising Connections",
            description=f"Connection overview for **{ctx.guild.name}**",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if incoming_connections:
            incoming_text = ""
            for conn in incoming_connections:
                channel = ctx.guild.get_channel(conn["data"]["channel_id"])
                channel_name = channel.name if channel else "Unknown Channel"
                guild_name = conn["guild_info"].get("name", "Unknown Guild")
                
                incoming_text += f"**🏢 {guild_name}**\n"
                incoming_text += f"└ 📢 Channel: #{channel_name}\n"
                incoming_text += f"└ 📊 Today: {conn['data']['ads_sent_today']}/{conn['data']['max_ads_per_day']} ads\n"
                incoming_text += f"└ 🕐 Schedule: {conn['data']['allowed_hours']} hrs, {conn['data']['allowed_minutes']} mins\n\n"
            
            embed.add_field(
                name="📥 Incoming Advertisements",
                value=incoming_text[:1024] if incoming_text else "None",
                inline=False
            )
        
        if outgoing_connections:
            outgoing_text = ""
            for conn in outgoing_connections:
                target_guild = self.bot.get_guild(conn["data"]["target_guild_id"])
                target_channel = target_guild.get_channel(conn["data"]["channel_id"]) if target_guild else None
                channel_name = target_channel.name if target_channel else "Unknown Channel"
                guild_name = conn["guild_info"].get("name", "Unknown Guild")
                
                outgoing_text += f"**🏢 {guild_name}**\n"
                outgoing_text += f"└ 📢 Channel: #{channel_name}\n"
                outgoing_text += f"└ 📊 Today: {conn['data']['ads_sent_today']}/{conn['data']['max_ads_per_day']} ads\n"
                outgoing_text += f"└ 🕐 Schedule: {conn['data']['allowed_hours']} hrs, {conn['data']['allowed_minutes']} mins\n\n"
            
            embed.add_field(
                name="📤 Outgoing Advertisements",
                value=outgoing_text[:1024] if outgoing_text else "None",
                inline=False
            )
        
        if not incoming_connections and not outgoing_connections:
            embed.add_field(
                name="📭 No Connections",
                value=f"No advertising connections found.\nUse `{ctx.prefix}guildads request <guild_id>` to get started!",
                inline=False
            )
        
        embed.set_footer(
            text=f"Use {ctx.prefix}guildads revoke <guild_id> to remove connections",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None
        )
        
        await ctx.send(embed=embed)
    
    @guildads.command(name="pending", aliases=["requests"])
    async def view_pending(self, ctx):
        if ctx.author.id != ctx.guild.owner_id:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the guild owner can view pending requests.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        pending_for_guild = []
        for request_key, request_data in self.pending_requests.items():
            if request_data["target_guild_id"] == ctx.guild.id:
                requester_guild_info = self._get_cached_guild_info(request_data["requester_guild_id"])
                if requester_guild_info:
                    pending_for_guild.append({
                        "guild_info": requester_guild_info,
                        "data": request_data,
                        "key": request_key
                    })
        
        if not pending_for_guild:
            embed = discord.Embed(
                title="📭 No Pending Requests",
                description="No pending advertisement requests for your guild.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Requests will appear here when other guilds want to advertise in your server.")
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="📋 Pending Advertisement Requests",
            description=f"**{len(pending_for_guild)}** pending request(s) for **{ctx.guild.name}**",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        
        for i, request in enumerate(pending_for_guild, 1):
            guild_info = request["guild_info"]
            data = request["data"]
            
            requested_date = "Unknown"
            if "requested_at" in data:
                try:
                    requested_date = datetime.fromisoformat(data["requested_at"]).strftime("%B %d, %Y")
                except:
                    pass
            
            embed.add_field(
                name=f"#{i} 🏢 {guild_info.get('name', 'Unknown Guild')}",
                value=(
                    f"**👥 Members:** {guild_info.get('member_count', 0):,}\n"
                    f"**📅 Requested:** {requested_date}\n"
                    f"**🆔 Guild ID:** `{data['requester_guild_id']}`"
                ),
                inline=True
            )
        
        embed.add_field(
            name="📬 Check Your DMs",
            value="Detailed request information and approval options are sent to your DMs.",
            inline=False
        )
        
        embed.set_footer(
            text="Only you (guild owner) can approve or deny these requests",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None
        )
        
        await ctx.send(embed=embed)
    
    @guildads.command(name="revoke", aliases=["remove", "delete"])
    async def revoke_permission(self, ctx, guild_id: str):
        if ctx.author.id != ctx.guild.owner_id:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the guild owner can revoke advertising permissions.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        try:
            target_guild_id = int(guild_id)
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Guild ID",
                description="Please provide a valid guild ID (numbers only).",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        connection_key = f"{target_guild_id}_{ctx.guild.id}"
        
        if connection_key not in self.approved_connections:
            embed = discord.Embed(
                title="❌ No Permission Found",
                description="No advertising permission found for this guild!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        target_guild_info = self._get_cached_guild_info(target_guild_id)
        guild_name = target_guild_info.get("name", f"Guild {target_guild_id}")
        
        connection_data = self.approved_connections[connection_key]
        del self.approved_connections[connection_key]
        self._save_json(self.approved_connections_path, self.approved_connections)
        
        target_guild = self.bot.get_guild(target_guild_id)
        if target_guild and target_guild.owner:
            embed_notify = discord.Embed(
                title="❌ Advertising Permission Revoked",
                description=f"Your advertising permission for **{ctx.guild.name}** has been revoked.",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            
            embed_notify.add_field(
                name="📋 Connection Details",
                value=(
                    f"**Guild:** {ctx.guild.name}\n"
                    f"**Ads Sent Today:** {connection_data.get('ads_sent_today', 0)}\n"
                    f"**Total Days Active:** {(datetime.now() - datetime.fromisoformat(connection_data['approved_at'])).days}"
                ),
                inline=False
            )
            
            embed_notify.set_footer(text="Guild Advertisement System")
            
            try:
                await target_guild.owner.send(embed=embed_notify)
            except:
                pass
        
        embed = discord.Embed(
            title="✅ Permission Revoked",
            description=f"Advertising permission revoked for **{guild_name}**.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📊 Connection Statistics",
            value=(
                f"**Ads Sent Today:** {connection_data.get('ads_sent_today', 0)}\n"
                f"**Max Ads/Day:** {connection_data.get('max_ads_per_day', 0)}\n"
                f"**Days Active:** {(datetime.now() - datetime.fromisoformat(connection_data['approved_at'])).days}"
            ),
            inline=False
        )
        
        embed.set_footer(text="The affected guild owner has been notified.")
        
        await ctx.send(embed=embed)
    
    @guildads.command(name="stats", aliases=["statistics", "info"])
    async def view_stats(self, ctx):
        if not self._is_admin_or_owner(ctx.author):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only administrators and guild owners can view statistics.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        guild_ads = self.advertisements.get(str(ctx.guild.id), {})
        total_ads = len(guild_ads)
        active_ads = len([ad for ad in guild_ads.values() if ad.get("active", True)])
        
        incoming_count = len([conn for conn in self.approved_connections.values() 
                             if conn["target_guild_id"] == ctx.guild.id])
        outgoing_count = len([conn for conn in self.approved_connections.values() 
                             if conn["requester_guild_id"] == ctx.guild.id])
        
        pending_incoming = len([req for req in self.pending_requests.values() 
                               if req["target_guild_id"] == ctx.guild.id])
        pending_outgoing = len([req for req in self.pending_requests.values() 
                               if req["requester_guild_id"] == ctx.guild.id])
        
        ads_sent_today = 0
        ads_received_today = 0
        max_daily_outgoing = 0
        max_daily_incoming = 0
        
        for conn in self.approved_connections.values():
            if conn["requester_guild_id"] == ctx.guild.id:
                ads_sent_today += conn.get("ads_sent_today", 0)
                max_daily_outgoing += conn.get("max_ads_per_day", 0)
            elif conn["target_guild_id"] == ctx.guild.id:
                ads_received_today += conn.get("ads_sent_today", 0)
                max_daily_incoming += conn.get("max_ads_per_day", 0)
        
        embed = discord.Embed(
            title=f"📊 Advertising Statistics",
            description=f"Comprehensive stats for **{ctx.guild.name}**",
            color=discord.Color.from_rgb(88, 101, 242),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📢 Advertisements",
            value=(
                f"**📝 Total:** {total_ads}\n"
                f"**🟢 Active:** {active_ads}\n"
                f"**🔴 Inactive:** {total_ads - active_ads}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🔗 Connections",
            value=(
                f"**📤 Outgoing:** {outgoing_count}\n"
                f"**📥 Incoming:** {incoming_count}\n"
                f"**⏳ Pending:** {pending_incoming + pending_outgoing}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="📈 Today's Activity",
            value=(
                f"**📤 Sent:** {ads_sent_today}/{max_daily_outgoing}\n"
                f"**📥 Received:** {ads_received_today}/{max_daily_incoming}\n"
                f"**📊 Efficiency:** {round((ads_sent_today/max_daily_outgoing*100) if max_daily_outgoing > 0 else 0, 1)}%"
            ),
            inline=True
        )
        
        blacklisted_count = len(self.blacklist.get(str(ctx.guild.id), []))
        whitelist_enabled = self.whitelist.get(str(ctx.guild.id), {}).get("enabled", False)
        
        embed.add_field(
            name="🔒 Security Settings",
            value=(
                f"**🚫 Blacklisted:** {blacklisted_count} guilds\n"
                f"**📝 Whitelist:** {'🟢 Enabled' if whitelist_enabled else '🔴 Disabled'}\n"
                f"**📋 Audit Events:** {len(self.audit_log.get(str(ctx.guild.id), []))}"
            ),
            inline=True
        )
        
        embed.set_footer(
            text=f"Use {ctx.prefix}guildads connections for detailed view",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None
        )
        
        await ctx.send(embed=embed)
    
    @guildads.command(name="cleanup", aliases=["clean"])
    async def cleanup_data(self, ctx):
        if ctx.author.id != ctx.guild.owner_id:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the guild owner can perform cleanup operations.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        cleaned_items = []
        
        connections_to_remove = []
        for key, conn in self.approved_connections.items():
            requester_guild = self.bot.get_guild(conn["requester_guild_id"])
            target_guild = self.bot.get_guild(conn["target_guild_id"])
            
            if not requester_guild or not target_guild:
                connections_to_remove.append(key)
        
        for key in connections_to_remove:
            del self.approved_connections[key]
            cleaned_items.append(f"Removed invalid connection: {key}")
        
        requests_to_remove = []
        for key, req in self.pending_requests.items():
            requester_guild = self.bot.get_guild(req["requester_guild_id"])
            target_guild = self.bot.get_guild(req["target_guild_id"])
            
            if not requester_guild or not target_guild:
                requests_to_remove.append(key)
        
        for key in requests_to_remove:
            del self.pending_requests[key]
            cleaned_items.append(f"Removed invalid request: {key}")
        
        old_rate_limits = []
        cutoff_date = datetime.now() - timedelta(days=30)
        for key, data in self.rate_limits.items():
            try:
                timestamp = datetime.fromisoformat(data["last_request"])
                if timestamp < cutoff_date:
                    old_rate_limits.append(key)
            except:
                old_rate_limits.append(key)
        
        for key in old_rate_limits:
            del self.rate_limits[key]
            cleaned_items.append(f"Removed old rate limit: {key}")
        
        cutoff_date = datetime.now() - timedelta(days=180)
        for guild_id, events in self.audit_log.items():
            original_count = len(events)
            self.audit_log[guild_id] = [
                event for event in events
                if datetime.fromisoformat(event["timestamp"]) > cutoff_date
            ]
            removed_count = original_count - len(self.audit_log[guild_id])
            if removed_count > 0:
                cleaned_items.append(f"Removed {removed_count} old audit events for guild {guild_id}")
        
        if connections_to_remove:
            self._save_json(self.approved_connections_path, self.approved_connections)
        if requests_to_remove:
            self._save_json(self.pending_requests_path, self.pending_requests)
        if old_rate_limits:
            self._save_json(self.rate_limits_path, self.rate_limits)
        if any("audit events" in item for item in cleaned_items):
            self._save_json(self.audit_log_path, self.audit_log)
        
        self._log_audit_event(ctx.guild.id, "cleanup_performed", {
            "items_cleaned": len(cleaned_items),
            "performed_by": str(ctx.author)
        })
        
        embed = discord.Embed(
            title="🧹 Cleanup Complete",
            description=f"Cleaned up {len(cleaned_items)} invalid/old items.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        if cleaned_items:
            embed.add_field(
                name="🗑️ Items Cleaned",
                value="\n".join(cleaned_items[:10]) + 
                      (f"\n... and {len(cleaned_items)-10} more" if len(cleaned_items) > 10 else ""),
                inline=False
            )
        else:
            embed.add_field(
                name="✨ All Clean",
                value="No invalid items found. Your data is already clean!",
                inline=False
            )
        
        await ctx.send(embed=embed)
    

    @guildads.command(name="audit", aliases=["log", "history"])
    async def view_audit_log(self, ctx):
        
        if not self._is_admin_or_owner(ctx.author):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only administrators and guild owners can view audit logs.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        guild_events = self.audit_log.get(str(ctx.guild.id), [])
        
        if not guild_events:
            embed = discord.Embed(
                title="📭 No Audit Events",
                description="No audit events found for this guild.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        

        guild_events.sort(key=lambda x: x["timestamp"], reverse=True)
        
        embed = discord.Embed(
            title="📋 Guild Advertisement Audit Log",
            description=f"Recent activity for **{ctx.guild.name}**",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        

        for i, event in enumerate(guild_events[:10], 1):
            try:
                event_time = datetime.fromisoformat(event["timestamp"]).strftime("%b %d, %Y %H:%M")
            except:
                event_time = "Unknown"
            
            event_type = event["type"].replace("_", " ").title() 
            details = event.get("details", {})
            
            value = f"**Time:** {event_time}\n"
            if details:
                for key, val in details.items():
                    if key != "timestamp":
                        value += f"**{key.replace('_', ' ').title()}:** {val}\n"
            
            embed.add_field(
                name=f"#{i} {event_type}",
                value=value[:1024],
                inline=False
            )
        
        if len(guild_events) > 10:
            embed.set_footer(text=f"Showing 10 of {len(guild_events)} events")
        
        await ctx.send(embed=embed)
    
    @guildads.command(name="whitelist", aliases=["wl"])
    async def manage_whitelist(self, ctx, action: str = None, *, criteria: str = None):
        
        if ctx.author.id != ctx.guild.owner_id:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the guild owner can manage the whitelist.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        guild_id = str(ctx.guild.id)
        
        if not action:

            whitelist_data = self.whitelist.get(guild_id, {"enabled": False, "criteria": {}})
            
            embed = discord.Embed(
                title="🤍 Whitelist Configuration",
                description=f"Whitelist settings for **{ctx.guild.name}**",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            status = "🟢 Enabled" if whitelist_data["enabled"] else "🔴 Disabled"
            embed.add_field(name="Status", value=status, inline=True)
            
            criteria = whitelist_data.get("criteria", {})
            if criteria:
                criteria_text = ""
                for key, value in criteria.items():
                    criteria_text += f"**{key.replace('_', ' ').title()}:** {value}\n"
                embed.add_field(name="Criteria", value=criteria_text or "None", inline=False)
            
            embed.add_field(
                name="Available Actions",
                value=(
                    f"`{ctx.prefix}guildads whitelist enable` - Enable whitelist\n"
                    f"`{ctx.prefix}guildads whitelist disable` - Disable whitelist\n"
                    f"`{ctx.prefix}guildads whitelist min_members 100` - Set minimum members\n"
                    f"`{ctx.prefix}guildads whitelist min_age 30` - Set minimum guild age (days)\n"
                    f"`{ctx.prefix}guildads whitelist clear` - Clear all criteria"
                ),
                inline=False
            )
            
            await ctx.send(embed=embed)
            return
        
        action = action.lower()
        
        if action == "enable":
            if guild_id not in self.whitelist:
                self.whitelist[guild_id] = {"enabled": True, "criteria": {}}
            else:
                self.whitelist[guild_id]["enabled"] = True
            
            self._save_json(self.whitelist_path, self.whitelist)
            self._log_audit_event(ctx.guild.id, "whitelist_enabled", {"enabled_by": str(ctx.author)})
            
            embed = discord.Embed(
                title="✅ Whitelist Enabled",
                description="Whitelist has been enabled. Only guilds meeting your criteria can send ad requests.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            
        elif action == "disable":
            if guild_id in self.whitelist:
                self.whitelist[guild_id]["enabled"] = False
                self._save_json(self.whitelist_path, self.whitelist)
                self._log_audit_event(ctx.guild.id, "whitelist_disabled", {"disabled_by": str(ctx.author)})
            
            embed = discord.Embed(
                title="✅ Whitelist Disabled",
                description="Whitelist has been disabled. All guilds can now send ad requests.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            
        elif action == "min_members":
            if not criteria or not criteria.isdigit():
                embed = discord.Embed(
                    title="❌ Invalid Input",
                    description="Please provide a valid number for minimum members.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            min_members = int(criteria)
            if guild_id not in self.whitelist:
                self.whitelist[guild_id] = {"enabled": False, "criteria": {}}
            
            self.whitelist[guild_id]["criteria"]["min_members"] = min_members
            self._save_json(self.whitelist_path, self.whitelist)
            self._log_audit_event(ctx.guild.id, "whitelist_criteria_updated", {
                "criteria": "min_members",
                "value": min_members,
                "updated_by": str(ctx.author)
            })
            
            embed = discord.Embed(
                title="✅ Minimum Members Set",
                description=f"Minimum member count set to **{min_members:,}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            
        elif action == "min_age":
            if not criteria or not criteria.isdigit():
                embed = discord.Embed(
                    title="❌ Invalid Input",
                    description="Please provide a valid number of days for minimum guild age.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            min_age = int(criteria)
            if guild_id not in self.whitelist:
                self.whitelist[guild_id] = {"enabled": False, "criteria": {}}
            
            self.whitelist[guild_id]["criteria"]["min_age_days"] = min_age
            self._save_json(self.whitelist_path, self.whitelist)
            self._log_audit_event(ctx.guild.id, "whitelist_criteria_updated", {
                "criteria": "min_age_days",
                "value": min_age,
                "updated_by": str(ctx.author)
            })
            
            embed = discord.Embed(
                title="✅ Minimum Age Set",
                description=f"Minimum guild age set to **{min_age}** days",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            
        elif action == "clear":
            if guild_id in self.whitelist:
                self.whitelist[guild_id]["criteria"] = {}
                self._save_json(self.whitelist_path, self.whitelist)
                self._log_audit_event(ctx.guild.id, "whitelist_criteria_cleared", {"cleared_by": str(ctx.author)})
            
            embed = discord.Embed(
                title="✅ Criteria Cleared",
                description="All whitelist criteria have been cleared.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            
        else:
            embed = discord.Embed(
                title="❌ Invalid Action",
                description=f"Unknown action: `{action}`",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Available Actions",
                value="enable, disable, min_members, min_age, clear",
                inline=False
            )
            await ctx.send(embed=embed)
    
    @guildads.command(name="blacklist", aliases=["bl"])
    async def manage_blacklist(self, ctx, action: str = None, guild_id: str = None):
        
        if ctx.author.id != ctx.guild.owner_id:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the guild owner can manage the blacklist.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        guild_id_str = str(ctx.guild.id)
        
        if not action:

            blacklisted_guilds = self.blacklist.get(guild_id_str, [])
            
            embed = discord.Embed(
                title="🖤 Blacklist Configuration",
                description=f"Blacklisted guilds for **{ctx.guild.name}**",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            
            if blacklisted_guilds:
                blacklist_text = ""
                for i, bl_guild_id in enumerate(blacklisted_guilds, 1):
                    guild_info = self._get_cached_guild_info(int(bl_guild_id))
                    guild_name = guild_info.get("name", f"Guild {bl_guild_id}")
                    blacklist_text += f"**{i}.** {guild_name} (`{bl_guild_id}`)\n"
                
                embed.add_field(
                    name=f"Blacklisted Guilds ({len(blacklisted_guilds)})",
                    value=blacklist_text[:1024],
                    inline=False
                )
            else:
                embed.add_field(
                    name="Blacklisted Guilds",
                    value="No guilds are currently blacklisted.",
                    inline=False
                )
            
            embed.add_field(
                name="Available Actions",
                value=(
                    f"`{ctx.prefix}guildads blacklist add <guild_id>` - Add guild to blacklist\n"
                    f"`{ctx.prefix}guildads blacklist remove <guild_id>` - Remove guild from blacklist\n"
                    f"`{ctx.prefix}guildads blacklist clear` - Clear entire blacklist"
                ),
                inline=False
            )
            
            await ctx.send(embed=embed)
            return
        
        action = action.lower()
        
        if action == "add":
            if not guild_id:
                embed = discord.Embed(
                    title="❌ Missing Guild ID",
                    description="Please provide a guild ID to blacklist.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            try:
                target_guild_id = int(guild_id)
            except ValueError:
                embed = discord.Embed(
                    title="❌ Invalid Guild ID",
                    description="Please provide a valid guild ID (numbers only).",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            if target_guild_id == ctx.guild.id:
                embed = discord.Embed(
                    title="❌ Cannot Blacklist Self",
                    description="You cannot blacklist your own guild!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            if guild_id_str not in self.blacklist:
                self.blacklist[guild_id_str] = []
            
            if str(target_guild_id) not in self.blacklist[guild_id_str]:
                self.blacklist[guild_id_str].append(str(target_guild_id))
                self._save_json(self.blacklist_path, self.blacklist)
                self._log_audit_event(ctx.guild.id, "guild_blacklisted", {
                    "blacklisted_guild_id": target_guild_id,
                    "blacklisted_by": str(ctx.author)
                })
                

                target_guild = self.bot.get_guild(target_guild_id)
                guild_name = target_guild.name if target_guild else f"Guild {target_guild_id}"
                
                embed = discord.Embed(
                    title="✅ Guild Blacklisted",
                    description=f"**{guild_name}** has been added to the blacklist.",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="⚠️ Already Blacklisted",
                    description="This guild is already blacklisted.",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
                
        elif action == "remove":
            if not guild_id:
                embed = discord.Embed(
                    title="❌ Missing Guild ID",
                    description="Please provide a guild ID to remove from blacklist.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            try:
                target_guild_id = int(guild_id)
            except ValueError:
                embed = discord.Embed(
                    title="❌ Invalid Guild ID",
                    description="Please provide a valid guild ID (numbers only).",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            if guild_id_str in self.blacklist and str(target_guild_id) in self.blacklist[guild_id_str]:
                self.blacklist[guild_id_str].remove(str(target_guild_id))
                self._save_json(self.blacklist_path, self.blacklist)
                self._log_audit_event(ctx.guild.id, "guild_unblacklisted", {
                    "unblacklisted_guild_id": target_guild_id,
                    "unblacklisted_by": str(ctx.author)
                })
                
                target_guild = self.bot.get_guild(target_guild_id)
                guild_name = target_guild.name if target_guild else f"Guild {target_guild_id}"
                
                embed = discord.Embed(
                    title="✅ Guild Removed from Blacklist",
                    description=f"**{guild_name}** has been removed from the blacklist.",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="⚠️ Not Blacklisted",
                    description="This guild is not in the blacklist.",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
                
        elif action == "clear":
            if guild_id_str in self.blacklist:
                cleared_count = len(self.blacklist[guild_id_str])
                self.blacklist[guild_id_str] = []
                self._save_json(self.blacklist_path, self.blacklist)
                self._log_audit_event(ctx.guild.id, "blacklist_cleared", {
                    "cleared_count": cleared_count,
                    "cleared_by": str(ctx.author)
                })
                
                embed = discord.Embed(
                    title="✅ Blacklist Cleared",
                    description=f"Removed **{cleared_count}** guilds from the blacklist.",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="⚠️ Blacklist Empty",
                    description="The blacklist is already empty.",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
                
        else:
            embed = discord.Embed(
                title="❌ Invalid Action",
                description=f"Unknown action: `{action}`",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Available Actions",
                value="add, remove, clear",
                inline=False
            )
            await ctx.send(embed=embed)


    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        guild_id_str = str(guild.id)
        
        self._log_audit_event(guild.id, "bot_left", {
            "guild_name": guild.name,
            "cleanup_performed": True
        })
        
        if guild_id_str in self.advertisements:
            del self.advertisements[guild_id_str]
            self._save_json(self.advertisements_path, self.advertisements)
        
        to_remove = []
        for key, conn in self.approved_connections.items():
            if conn["requester_guild_id"] == guild.id or conn["target_guild_id"] == guild.id:
                to_remove.append(key)
        
        for key in to_remove:
            del self.approved_connections[key]
        
        if to_remove:
            self._save_json(self.approved_connections_path, self.approved_connections)
        
        to_remove = []
        for key, req in self.pending_requests.items():
            if req["requester_guild_id"] == guild.id or req["target_guild_id"] == guild.id:
                to_remove.append(key)
        
        for key in to_remove:
            del self.pending_requests[key]
        
        if to_remove:
            self._save_json(self.pending_requests_path, self.pending_requests)
        
        if guild_id_str in self.guild_cache:
            del self.guild_cache[guild_id_str]
            self._save_json(self.guild_cache_path, self.guild_cache)
        
        if guild_id_str in self.blacklist:
            del self.blacklist[guild_id_str]
            self._save_json(self.blacklist_path, self.blacklist)
        
        if guild_id_str in self.whitelist:
            del self.whitelist[guild_id_str]
            self._save_json(self.whitelist_path, self.whitelist)
        
        rate_limits_to_remove = []
        for key in self.rate_limits.keys():
            if str(guild.id) in key:
                rate_limits_to_remove.append(key)
        
        for key in rate_limits_to_remove:
            del self.rate_limits[key]
        
        if rate_limits_to_remove:
            self._save_json(self.rate_limits_path, self.rate_limits)
    
    @ad_scheduler.before_loop
    async def before_ad_scheduler(self):
        await self.bot.wait_until_ready()
    
    def cog_unload(self):
        self.ad_scheduler.cancel()
    
    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description="You don't have permission to use this command.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="❌ Invalid Argument",
                description="Invalid argument provided. Please check your input.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏰ Command Cooldown",
                description=f"Command is on cooldown. Try again in {error.retry_after:.1f} seconds.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❌ Missing Argument",
                description=f"Missing required argument: `{error.param.name}`",
                color=discord.Color.red()
            )

            await ctx.send(embed=embed)
        else:
            logger.error(f"Unhandled error in guild ads command: {error}")
            embed = discord.Embed(
                title="❌ Unexpected Error",
                description="An unexpected error occurred. Please try again later.",
                color=discord.Color.red()
            )
            embed.set_footer(text="If this persists, please contact the bot administrator.")
            await ctx.send(embed=embed)

class AdRequestView(discord.ui.View):
    def __init__(self, cog, requester_guild_id: int, target_guild_id: int, requester_user_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.requester_guild_id = requester_guild_id
        self.target_guild_id = target_guild_id
        self.requester_user_id = requester_user_id
    
    @discord.ui.button(label="✅ Approve Request", style=discord.ButtonStyle.green, emoji="✅")
    async def approve_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_guild_info = self.cog._get_cached_guild_info(self.target_guild_id)
        
        if interaction.user.id != target_guild_info.get("owner_id"):
            await interaction.response.send_message("❌ Only the guild owner can approve ad requests.", ephemeral=True)
            return
        
        await interaction.response.send_modal(AdApprovalModal(self.cog, self.requester_guild_id, self.target_guild_id, self.requester_user_id))
    
    @discord.ui.button(label="❌ Deny Request", style=discord.ButtonStyle.red, emoji="❌")
    async def deny_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_guild_info = self.cog._get_cached_guild_info(self.target_guild_id)
        
        if interaction.user.id != target_guild_info.get("owner_id"):
            await interaction.response.send_message("❌ Only the guild owner can deny ad requests.", ephemeral=True)
            return
        
        request_key = f"{self.requester_guild_id}_{self.target_guild_id}"
        if request_key in self.cog.pending_requests:
            del self.cog.pending_requests[request_key]
            self.cog._save_json(self.cog.pending_requests_path, self.cog.pending_requests)
        
        requester_guild_info = self.cog._get_cached_guild_info(self.requester_guild_id)
        target_guild_info = self.cog._get_cached_guild_info(self.target_guild_id)
        
        requester = self.cog.bot.get_user(self.requester_user_id)
        if requester:
            embed = discord.Embed(
                title="❌ Advertisement Request Denied",
                description=f"Your request to send ads to **{target_guild_info.get('name', 'Unknown Server')}** has been denied.",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="📋 Request Details",
                value=f"**From Guild:** {requester_guild_info.get('name', 'Unknown')}\n**To Guild:** {target_guild_info.get('name', 'Unknown')}",
                inline=False
            )
            embed.set_footer(text="Guild Advertisement System", icon_url=self.cog.bot.user.avatar.url if self.cog.bot.user.avatar else None)
            
            try:
                await requester.send(embed=embed)
            except:
                pass
        
        embed = discord.Embed(
            title="❌ Request Denied",
            description="The advertisement request has been denied and the requester has been notified.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class AdApprovalModal(discord.ui.Modal):
    def __init__(self, cog, requester_guild_id: int, target_guild_id: int, requester_user_id: int):
        super().__init__(title="📋 Advertisement Approval Settings")
        self.cog = cog
        self.requester_guild_id = requester_guild_id
        self.target_guild_id = target_guild_id
        self.requester_user_id = requester_user_id
        
        self.channel_id = discord.ui.TextInput(
            label="📢 Channel ID for Advertisements",
            placeholder="Enter the channel ID where ads will be posted",
            required=True,
            max_length=20
        )
        
        self.allowed_hours = discord.ui.TextInput(
            label="🕐 Allowed Hours (24h format)",
            placeholder="e.g., 9-17 or 9,12,15 or * for all hours",
            required=True,
            max_length=50,
            default="9-21"
        )
        
        self.allowed_minutes = discord.ui.TextInput(
            label="⏰ Allowed Minutes",
            placeholder="e.g., 0,30 or * for all minutes",
            required=True,
            max_length=50,
            default="0,30"
        )
        
        self.role_mentions = discord.ui.TextInput(
            label="👥 Role ID for Mentions (Optional)",
            placeholder="Enter role ID if role mentions are allowed, leave empty if not",
            required=False,
            max_length=20
        )
        
        self.max_ads_per_day = discord.ui.TextInput(
            label="📊 Max Ads Per Day",
            placeholder="Maximum number of ads per day (default: 3)",
            required=False,
            max_length=2,
            default="3"
        )
        
        self.add_item(self.channel_id)
        self.add_item(self.allowed_hours)
        self.add_item(self.allowed_minutes)
        self.add_item(self.role_mentions)
        self.add_item(self.max_ads_per_day)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            target_guild = self.cog.bot.get_guild(self.target_guild_id)
            if not target_guild:
                await interaction.response.send_message("❌ Target guild not found!", ephemeral=True)
                return
            
            channel = target_guild.get_channel(int(self.channel_id.value))
            if not channel:
                await interaction.response.send_message("❌ Invalid channel ID! Channel not found in your guild.", ephemeral=True)
                return
            
            role = None
            if self.role_mentions.value.strip():
                role = target_guild.get_role(int(self.role_mentions.value))
                if not role:
                    await interaction.response.send_message("❌ Invalid role ID! Role not found in your guild.", ephemeral=True)
                    return
            
            max_ads = 3
            if self.max_ads_per_day.value.strip():
                max_ads = int(self.max_ads_per_day.value)
                if max_ads < 1 or max_ads > 20:
                    await interaction.response.send_message("❌ Max ads per day must be between 1 and 20!", ephemeral=True)
                    return
            
            connection_key = f"{self.requester_guild_id}_{self.target_guild_id}"
            self.cog.approved_connections[connection_key] = {
                "requester_guild_id": self.requester_guild_id,
                "target_guild_id": self.target_guild_id,
                "channel_id": int(self.channel_id.value),
                "allowed_hours": self.allowed_hours.value,
                "allowed_minutes": self.allowed_minutes.value,
                "role_id": role.id if role else None,
                "max_ads_per_day": max_ads,
                "approved_at": datetime.now().isoformat(),
                "ads_sent_today": 0,
                "last_ad_date": None,
                "approved_by": interaction.user.id
            }
            
            if connection_key in self.cog.pending_requests:
                del self.cog.pending_requests[connection_key]
            
            self.cog._save_json(self.cog.approved_connections_path, self.cog.approved_connections)
            self.cog._save_json(self.cog.pending_requests_path, self.cog.pending_requests)
            
            requester_guild_info = self.cog._get_cached_guild_info(self.requester_guild_id)
            target_guild_info = self.cog._get_cached_guild_info(self.target_guild_id)
            
            requester = self.cog.bot.get_user(self.requester_user_id)
            if requester:
                embed = discord.Embed(
                    title="✅ Advertisement Request Approved!",
                    description=f"🎉 Your request to send ads to **{target_guild_info.get('name', 'Unknown Server')}** has been approved!",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="📋 Approved Settings",
                    value=(
                        f"**📢 Channel:** <#{channel.id}> (`{channel.name}`)\n"
                        f"**🕐 Allowed Hours:** `{self.allowed_hours.value}`\n"
                        f"**⏰ Allowed Minutes:** `{self.allowed_minutes.value}`\n"
                        f"**👥 Role Mentions:** {'✅ Yes' if role else '❌ No'}\n"
                        f"**📊 Max Ads/Day:** `{max_ads}`"
                    ),
                    inline=False
                )
                
                if role:
                    embed.add_field(
                        name="👥 Mention Role",
                        value=f"{role.mention} (`{role.name}`)",
                        inline=False
                    )
                
                embed.add_field(
                    name="🚀 Next Steps",
                    value="Use `!guildads create` to create your first advertisement!\nUse `!guildads list` to manage your ads.",
                    inline=False
                )
                
                embed.set_footer(text="Guild Advertisement System", icon_url=self.cog.bot.user.avatar.url if self.cog.bot.user.avatar else None)
                
                try:
                    await requester.send(embed=embed)
                except:
                    pass
            
            success_embed = discord.Embed(
                title="✅ Request Approved Successfully!",
                description=f"Advertisement request from **{requester_guild_info.get('name', 'Unknown')}** has been approved.",
                color=discord.Color.green()
            )
            success_embed.add_field(
                name="📋 Settings Applied",
                value=(
                    f"**Channel:** #{channel.name}\n"
                    f"**Hours:** {self.allowed_hours.value}\n"
                    f"**Minutes:** {self.allowed_minutes.value}\n"
                    f"**Max Ads/Day:** {max_ads}"
                ),
                inline=False
            )
            
            await interaction.response.edit_message(embed=success_embed, view=None)
            
        except ValueError as e:
            await interaction.response.send_message(f"❌ Invalid input! Please check your values. Error: {str(e)}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in approval modal: {e}")
            await interaction.response.send_message("❌ An error occurred while processing the approval.", ephemeral=True)

class AdCreationModal(discord.ui.Modal):
    def __init__(self, cog, guild_id: int, edit_mode: bool = False, ad_id: str = None):
        super().__init__(title="📝 Create Advertisement" if not edit_mode else f"✏️ Edit Advertisement ({ad_id})")
        self.cog = cog
        self.guild_id = guild_id
        self.edit_mode = edit_mode
        self.ad_id = ad_id
        
        self.ad_title = discord.ui.TextInput(
            label="📢 Advertisement Title",
            placeholder="Enter the title for your advertisement",
            required=True,
            max_length=100
        )
        
        self.ad_description = discord.ui.TextInput(
            label="📝 Advertisement Description",
            placeholder="Supports: {server}, {origin_server}, {role}, {member_count}",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000
        )
        
        self.ad_color = discord.ui.TextInput(
            label="🎨 Embed Color (Hex)",
            placeholder="e.g., #FF5733 or leave empty for default blue",
            required=False,
            max_length=7
        )
        
        self.ad_image = discord.ui.TextInput(
            label="🖼️ Image URL (Optional)",
            placeholder="Enter image URL or leave empty",
            required=False,
            max_length=500
        )
        
        if edit_mode and ad_id:
            guild_ads = self.cog.advertisements.get(str(guild_id), {})
            if ad_id in guild_ads:
                existing_ad = guild_ads[ad_id]
                self.ad_title.default = existing_ad["title"]
                self.ad_description.default = existing_ad["description"]
                self.ad_color.default = f"#{existing_ad['color']:06x}"
                self.ad_image.default = existing_ad.get("image", "")
        
        self.add_item(self.ad_title)
        self.add_item(self.ad_description)
        self.add_item(self.ad_color)
        self.add_item(self.ad_image)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            color = discord.Color.blue()
            if self.ad_color.value.strip():
                color_hex = self.ad_color.value.strip().replace('#', '')
                if len(color_hex) == 6 and all(c in '0123456789ABCDEFabcdef' for c in color_hex):
                    color = discord.Color(int(color_hex, 16))
                else:
                    await interaction.response.send_message("❌ Invalid color format! Use hex format like #FF5733", ephemeral=True)
                    return
            
            ad_data = {
                "title": self.ad_title.value,
                "description": self.ad_description.value,
                "color": color.value,
                "image": self.ad_image.value.strip() if self.ad_image.value.strip() else None,
                "active": True
            }
            
            if self.edit_mode:
                ad_data["updated_at"] = datetime.now().isoformat()
            else:
                ad_data["created_at"] = datetime.now().isoformat()
            
            if str(self.guild_id) not in self.cog.advertisements:
                self.cog.advertisements[str(self.guild_id)] = {}
            
            if self.edit_mode and self.ad_id:
                self.cog.advertisements[str(self.guild_id)][self.ad_id].update(ad_data)
                ad_id = self.ad_id
                action_text = "updated"
            else:
                ad_id = f"ad_{len(self.cog.advertisements[str(self.guild_id)]) + 1}"
                self.cog.advertisements[str(self.guild_id)][ad_id] = ad_data
                action_text = "created"
            
            self.cog._save_json(self.cog.advertisements_path, self.cog.advertisements)
            
            embed = discord.Embed(
                title=ad_data["title"],
                description=ad_data["description"],
                color=discord.Color(ad_data["color"]),
                timestamp=datetime.now()
            )
            
            if ad_data["image"]:
                embed.set_image(url=ad_data["image"])
            
            embed.set_footer(text=f"Advertisement ID: {ad_id} • {action_text.title()}")
            
            await interaction.response.send_message(f"✅ Advertisement {action_text} successfully!", embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error creating/editing advertisement: {e}")
            await interaction.response.send_message("❌ An error occurred while processing the advertisement.", ephemeral=True)

def setup(bot):
    cog = GuildAdvertisementSystem(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog
