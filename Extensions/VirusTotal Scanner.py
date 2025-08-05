import discord
from discord.ext import commands
import aiohttp
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import hashlib
import base64
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

class VirusTotalConfig:
    
    def __init__(self, config_path: str = "VirusTotal/config.json"):
        self.config_path = config_path
        self.base_dir = os.path.dirname(config_path)
        self.scan_history_path = os.path.join(self.base_dir, "scan_history.json")
        self._ensure_directories()
        self.config = self._load_config()
        self.scan_history = self._load_scan_history()
    
    def _ensure_directories(self):
        os.makedirs(self.base_dir, exist_ok=True)
    
    def _load_config(self) -> Dict:
        default_config = {
            "api_key": "",
            "guilds": {},
            "global_settings": {
                "max_file_size_mb": 32,
                "rate_limit_per_user": 5,
                "rate_limit_window_minutes": 60,
                "enabled": True
            }
        }
        
        if not os.path.exists(self.config_path):
            with open(self.config_path, 'w') as f:
                json.dump(default_config, f, indent=4)
            return default_config
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return default_config
    
    def _load_scan_history(self) -> Dict:
        if not os.path.exists(self.scan_history_path):
            return {"scans": []}
        
        try:
            with open(self.scan_history_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading scan history: {e}")
            return {"scans": []}
    
    def save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def save_scan_history(self):
        try:
            with open(self.scan_history_path, 'w') as f:
                json.dump(self.scan_history, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving scan history: {e}")
    
    def get_guild_config(self, guild_id: int) -> Dict:
        guild_str = str(guild_id)
        if guild_str not in self.config["guilds"]:
            self.config["guilds"][guild_str] = {
                "allowed_channels": [],
                "allowed_roles": [],
                "admin_roles": [],
                "auto_scan_channels": [],
                "rate_limits": {
                    "per_user": 5,
                    "window_minutes": 60
                },
                "enabled": True,
                "require_role": False,
                "alert_channel": None,
                "alerts_enabled": False
            }
            self.save_config()
        return self.config["guilds"][guild_str]
    
    def add_scan_record(self, guild_id: int, user_id: int, filename: str, 
                       file_hash: str, results: Dict):
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "guild_id": guild_id,
            "user_id": user_id,
            "filename": filename,
            "file_hash": file_hash,
            "results": results
        }
        
        self.scan_history["scans"].append(record)
        
        if len(self.scan_history["scans"]) > 1000:
            self.scan_history["scans"] = self.scan_history["scans"][-1000:]
        
        self.save_scan_history()

class RateLimiter:
    
    def __init__(self):
        self.user_requests: Dict[int, List[datetime]] = {}
    
    def can_make_request(self, user_id: int, limit: int, window_minutes: int) -> bool:
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=window_minutes)
        
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []
        
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id] 
            if req_time > cutoff
        ]
        
        return len(self.user_requests[user_id]) < limit
    
    def add_request(self, user_id: int):
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []
        self.user_requests[user_id].append(datetime.utcnow())

class VirusTotalAPI:
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.virustotal.com/api/v3"
    
    async def scan_file(self, file_data: bytes, filename: str) -> Dict:
        if not self.api_key:
            raise Exception("VirusTotal API key not configured")
        
        headers = {"X-Apikey": self.api_key}
        
        data = aiohttp.FormData()
        data.add_field('file', file_data, filename=filename)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/files",
                headers=headers,
                data=data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Upload failed: {error_text}")
                
                upload_result = await response.json()
                analysis_id = upload_result["data"]["id"]
        

        return await self.wait_for_analysis(analysis_id)
    
    async def wait_for_analysis(self, analysis_id: str, max_retries: int = 30) -> Dict:
        
        headers = {"X-Apikey": self.api_key}
        
        for attempt in range(max_retries):
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/analyses/{analysis_id}",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Analysis retrieval failed: {error_text}")
                    
                    result = await response.json()
                    

                    attributes = result.get("data", {}).get("attributes", {})
                    status = attributes.get("status", "")
                    
                    if status == "completed":

                        stats = attributes.get("stats", {})
                        total_engines = sum(stats.values()) if stats else 0
                        
                        if total_engines > 0:
                            logger.info(f"Analysis complete: {stats}")
                            return result
                        else:
                            logger.warning(f"Analysis complete but no stats available, retrying...")
                    

                    wait_time = min(5 + (attempt * 2), 30)
                    logger.info(f"Analysis status: {status}, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
        
        raise Exception("Analysis timed out - please try again later")
    
    async def get_analysis(self, analysis_id: str) -> Dict:
        
        headers = {"X-Apikey": self.api_key}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/analyses/{analysis_id}",
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Analysis retrieval failed: {error_text}")
                
                return await response.json()

class ScanResultView(discord.ui.View):
    
    def __init__(self, scanner_cog, scan_data: Dict, user_id: int):
        super().__init__(timeout=300)
        self.scanner_cog = scanner_cog
        self.scan_data = scan_data
        self.user_id = user_id
    
    @discord.ui.button(label="📊 Detailed Results", style=discord.ButtonStyle.primary, custom_id="detailed_results")
    async def detailed_results(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the user who initiated the scan can view detailed results.", ephemeral=True)
            return
        
        embed = self._create_detailed_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🔍 View All Scans", style=discord.ButtonStyle.secondary, custom_id="view_all_scans")
    async def view_all_scans(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ScanHistoryView(self.scanner_cog, interaction.guild.id, interaction.user.id)
        embed = view.create_history_embed(page=0)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="🗑️ Delete Results", style=discord.ButtonStyle.danger, custom_id="delete_results")
    async def delete_results(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the user who initiated the scan can delete results.", ephemeral=True)
            return
        
        await interaction.response.edit_message(content="🗑️ Scan results deleted.", embed=None, view=None)
    
    def _create_detailed_embed(self) -> discord.Embed:
        attributes = self.scan_data.get("data", {}).get("attributes", {})
        stats = attributes.get("stats", {})
        
        embed = discord.Embed(
            title="🔍 Detailed Scan Results",
            color=discord.Color.red() if stats.get("malicious", 0) > 0 else discord.Color.green()
        )
        
        engines = attributes.get("results", {})
        malicious_engines = []
        suspicious_engines = []
        clean_engines = []
        
        for engine, result in engines.items():
            category = result.get("category", "undetected")
            if category == "malicious":
                malicious_engines.append(f"🔴 {engine}: {result.get('result', 'Malicious')}")
            elif category == "suspicious":
                suspicious_engines.append(f"🟡 {engine}: {result.get('result', 'Suspicious')}")
            else:
                clean_engines.append(f"🟢 {engine}")
        
        if malicious_engines:
            embed.add_field(
                name="🚨 Malicious Detections",
                value="\n".join(malicious_engines[:10]) + ("\n..." if len(malicious_engines) > 10 else ""),
                inline=False
            )
        
        if suspicious_engines:
            embed.add_field(
                name="⚠️ Suspicious Detections",
                value="\n".join(suspicious_engines[:5]) + ("\n..." if len(suspicious_engines) > 5 else ""),
                inline=False
            )
        
        embed.add_field(
            name="📈 Summary",
            value=f"Clean: {len(clean_engines)}\nSuspicious: {len(suspicious_engines)}\nMalicious: {len(malicious_engines)}",
            inline=True
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed

class ScanHistoryView(discord.ui.View):
    
    def __init__(self, scanner_cog, guild_id: int, user_id: int):
        super().__init__(timeout=300)
        self.scanner_cog = scanner_cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.current_page = 0
        self.items_per_page = 5
    
    def get_user_scans(self) -> List[Dict]:
        all_scans = self.scanner_cog.config.scan_history.get("scans", [])
        return [
            scan for scan in all_scans 
            if scan.get("guild_id") == self.guild_id and scan.get("user_id") == self.user_id
        ]
    
    def create_history_embed(self, page: int = 0) -> discord.Embed:
        user_scans = self.get_user_scans()
        total_pages = max(1, (len(user_scans) + self.items_per_page - 1) // self.items_per_page)
        
        embed = discord.Embed(
            title="📋 Your Scan History",
            description=f"Page {page + 1} of {total_pages} • Total scans: {len(user_scans)}",
            color=discord.Color.blue()
        )
        
        start_idx = page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_scans = user_scans[start_idx:end_idx]
        
        for scan in page_scans:
            timestamp = datetime.fromisoformat(scan["timestamp"])
            results = scan.get("results", {}).get("data", {}).get("attributes", {})
            stats = results.get("stats", {})
            
            status = "🔴 Malicious" if stats.get("malicious", 0) > 0 else (
                "🟡 Suspicious" if stats.get("suspicious", 0) > 0 else "🟢 Clean"
            )
            
            embed.add_field(
                name=f"📄 {scan['filename']}",
                value=f"**Status:** {status}\n"
                      f"**Date:** {timestamp.strftime('%Y-%m-%d %H:%M')}\n"
                      f"**Detections:** {stats.get('malicious', 0)}/{stats.get('malicious', 0) + stats.get('suspicious', 0) + stats.get('harmless', 0) + stats.get('undetected', 0)}",
                inline=False
            )
        
        if not page_scans:
            embed.add_field(
                name="No scans found",
                value="You haven't scanned any files yet.",
                inline=False
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed
    
    @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, custom_id="previous_page")
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            embed = self.create_history_embed(self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ Already on the first page.", ephemeral=True)
    
    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary, custom_id="next_page")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_scans = self.get_user_scans()
        total_pages = max(1, (len(user_scans) + self.items_per_page - 1) // self.items_per_page)
        
        if self.current_page < total_pages - 1:
            self.current_page += 1
            embed = self.create_history_embed(self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ Already on the last page.", ephemeral=True)
    
    @discord.ui.button(label="🔍 Filter", style=discord.ButtonStyle.primary, custom_id="filter_results")
    async def filter_results(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = FilterModal(self)
        await interaction.response.send_modal(modal)

class FilterModal(discord.ui.Modal):
    
    def __init__(self, history_view):
        super().__init__(title="Filter Scan Results")
        self.history_view = history_view
        
        self.filename_filter = discord.ui.TextInput(
            label="Filename (partial match)",
            placeholder="Enter filename to search for...",
            required=False,
            max_length=100
        )
        
        self.status_filter = discord.ui.TextInput(
            label="Status (clean/suspicious/malicious)",
            placeholder="Enter status to filter by...",
            required=False,
            max_length=20
        )
        
        self.add_item(self.filename_filter)
        self.add_item(self.status_filter)
    
    async def on_submit(self, interaction: discord.Interaction):
        filtered_embed = self.create_filtered_embed()
        await interaction.response.edit_message(embed=filtered_embed, view=self.history_view)
    
    def create_filtered_embed(self) -> discord.Embed:
        all_scans = self.history_view.get_user_scans()
        filtered_scans = []
        
        filename_query = self.filename_filter.value.lower() if self.filename_filter.value else ""
        status_query = self.status_filter.value.lower() if self.status_filter.value else ""
        
        for scan in all_scans:
            if filename_query and filename_query not in scan['filename'].lower():
                continue
            
            if status_query:
                results = scan.get("results", {}).get("data", {}).get("attributes", {})
                stats = results.get("stats", {})
                
                if status_query == "malicious" and stats.get("malicious", 0) == 0:
                    continue
                elif status_query == "suspicious" and stats.get("suspicious", 0) == 0:
                    continue
                elif status_query == "clean" and (stats.get("malicious", 0) > 0 or stats.get("suspicious", 0) > 0):
                    continue
            
            filtered_scans.append(scan)
        
        embed = discord.Embed(
            title="🔍 Filtered Scan Results",
            description=f"Found {len(filtered_scans)} matching scans",
            color=discord.Color.blue()
        )
        
        for scan in filtered_scans[:10]:
            timestamp = datetime.fromisoformat(scan["timestamp"])
            results = scan.get("results", {}).get("data", {}).get("attributes", {})
            stats = results.get("stats", {})
            
            status = "🔴 Malicious" if stats.get("malicious", 0) > 0 else (
                "🟡 Suspicious" if stats.get("suspicious", 0) > 0 else "🟢 Clean"
            )
            
            embed.add_field(
                name=f"📄 {scan['filename']}",
                value=f"**Status:** {status}\n"
                      f"**Date:** {timestamp.strftime('%Y-%m-%d %H:%M')}\n"
                      f"**Detections:** {stats.get('malicious', 0)}/{stats.get('malicious', 0) + stats.get('suspicious', 0) + stats.get('harmless', 0) + stats.get('undetected', 0)}",
                inline=False
            )
        
        if len(filtered_scans) > 10:
            embed.set_footer(text=f"Showing first 10 of {len(filtered_scans)} results • Made By TheHolyOneZ")
        else:
            embed.set_footer(text="Made By TheHolyOneZ")
        
        return embed

class ScannerMainView(discord.ui.View):
    
    def __init__(self, scanner_cog):
        super().__init__(timeout=None)
        self.scanner_cog = scanner_cog
    
    @discord.ui.button(label="📤 Upload & Scan File", style=discord.ButtonStyle.primary, emoji="🔍", custom_id="upload_scan_file")
    async def upload_file(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.scanner_cog.can_user_scan(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "❌ You don't have permission to use the scanner in this server.",
                ephemeral=True
            )
            return
        
        guild_config = self.scanner_cog.config.get_guild_config(interaction.guild.id)
        if not guild_config["enabled"] or not self.scanner_cog.config.config["global_settings"]["enabled"]:
            await interaction.response.send_message(
                "❌ File scanning is currently disabled.",
                ephemeral=True
            )
            return
        
        rate_limit = guild_config["rate_limits"]
        if not self.scanner_cog.rate_limiter.can_make_request(
            interaction.user.id, 
            rate_limit["per_user"], 
            rate_limit["window_minutes"]
        ):
            await interaction.response.send_message(
                f"❌ Rate limit exceeded. You can scan {rate_limit['per_user']} files per {rate_limit['window_minutes']} minutes.",
                ephemeral=True
            )
            return
        
        modal = FileUploadModal(self.scanner_cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📋 View Scan History", style=discord.ButtonStyle.secondary, emoji="📊", custom_id="view_scan_history")
    async def view_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ScanHistoryView(self.scanner_cog, interaction.guild.id, interaction.user.id)
        embed = view.create_history_embed(page=0)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="ℹ️ Scanner Info", style=discord.ButtonStyle.secondary, emoji="❓", custom_id="scanner_info")
    async def scanner_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.create_info_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def create_info_embed(self, guild: discord.Guild) -> discord.Embed:
        guild_config = self.scanner_cog.config.get_guild_config(guild.id)
        global_config = self.scanner_cog.config.config["global_settings"]
        
        embed = discord.Embed(
            title="🔍 VirusTotal Scanner Information",
            description="Advanced file scanning using VirusTotal API",
            color=discord.Color.blue()
        )
        
        status = "🟢 Online" if guild_config["enabled"] and global_config["enabled"] else "🔴 Offline"
        embed.add_field(name="Status", value=status, inline=True)
        
        embed.add_field(
            name="Rate Limits",
            value=f"{guild_config['rate_limits']['per_user']} scans per {guild_config['rate_limits']['window_minutes']} minutes",
            inline=True
        )
        
        embed.add_field(
            name="Max File Size",
            value=f"{global_config['max_file_size_mb']} MB",
            inline=True
        )
        
        if guild_config["allowed_channels"]:
            channels = [f"<#{ch_id}>" for ch_id in guild_config["allowed_channels"]]
            embed.add_field(
                name="Allowed Channels",
                value="\n".join(channels[:5]) + ("\n..." if len(channels) > 5 else ""),
                inline=False
            )
        
        if guild_config["require_role"] and guild_config["allowed_roles"]:
            roles = [f"<@&{role_id}>" for role_id in guild_config["allowed_roles"]]
            embed.add_field(
                name="Required Roles",
                value="\n".join(roles[:5]) + ("\n..." if len(roles) > 5 else ""),
                inline=False
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed

class FileUploadModal(discord.ui.Modal):
    
    def __init__(self, scanner_cog):
        super().__init__(title="File Upload Instructions")
        self.scanner_cog = scanner_cog
        
        self.instructions = discord.ui.TextInput(
            label="Please attach your file in the next message",
            placeholder="After clicking Submit, send a message with your file attached...",
            style=discord.TextStyle.paragraph,
            required=False,
            default="Click Submit, then send a message with your file attached in this channel."
        )
        self.add_item(self.instructions)
    
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📤 Ready for File Upload",
            description="Please send a message with your file attached in this channel.\n\n"
                       "**Supported formats:** Any file type\n"
                       f"**Max size:** {self.scanner_cog.config.config['global_settings']['max_file_size_mb']} MB\n"
                       "**Timeout:** 60 seconds",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        def check(message):
            return (message.author.id == interaction.user.id and 
                   message.channel.id == interaction.channel.id and 
                   message.attachments)
        
        try:
            message = await self.scanner_cog.bot.wait_for('message', check=check, timeout=60.0)
            await self.scanner_cog.process_file_upload(message, interaction.user)
        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                title="⏰ Upload Timeout",
                description="File upload timed out. Please try again.",
                color=discord.Color.red()
            )
            timeout_embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.followup.send(embed=timeout_embed, ephemeral=True)

class AdminPanelView(discord.ui.View):
    
    def __init__(self, scanner_cog, guild_id: int):
        super().__init__(timeout=300)
        self.scanner_cog = scanner_cog
        self.guild_id = guild_id
    
    @discord.ui.button(label="🛑 Toggle Scanner", style=discord.ButtonStyle.danger, custom_id="toggle_scanner_admin")
    async def toggle_scanner(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return
        
        guild_config = self.scanner_cog.config.get_guild_config(self.guild_id)
        guild_config["enabled"] = not guild_config["enabled"]
        self.scanner_cog.config.save_config()
        
        status = "enabled" if guild_config["enabled"] else "disabled"
        embed = discord.Embed(
            title="🛑 Scanner Status Changed",
            description=f"Scanner has been **{status}** for this server",
            color=discord.Color.green() if status == "enabled" else discord.Color.red()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="👥 Manage Roles", style=discord.ButtonStyle.primary, custom_id="manage_roles_admin")
    async def manage_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return
        
        view = RoleManagementView(self.scanner_cog, self.guild_id)
        embed = view.create_role_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="🔑 Set API Key", style=discord.ButtonStyle.secondary, custom_id="set_api_key_admin")
    async def set_api_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return
        
        modal = APIKeyModal(self.scanner_cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📊 View All Scans", style=discord.ButtonStyle.secondary, custom_id="view_all_scans_admin")
    async def view_all_scans(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.scanner_cog.is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ Admin permission required.", ephemeral=True)
            return
        
        view = AdminScanHistoryView(self.scanner_cog, self.guild_id)
        embed = view.create_admin_history_embed(page=0)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="⚙️ Advanced Settings", style=discord.ButtonStyle.primary, custom_id="advanced_settings_admin")
    async def advanced_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return
        
        view = AdvancedSettingsView(self.scanner_cog, self.guild_id)
        embed = view.create_settings_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class RoleManagementView(discord.ui.View):
    
    def __init__(self, scanner_cog, guild_id: int):
        super().__init__(timeout=300)
        self.scanner_cog = scanner_cog
        self.guild_id = guild_id
    
    def create_role_embed(self) -> discord.Embed:
        guild_config = self.scanner_cog.config.get_guild_config(self.guild_id)
        
        embed = discord.Embed(
            title="👥 Role Management",
            description="Configure which roles can use the scanner",
            color=discord.Color.blue()
        )
        
        require_role = "✅ Enabled" if guild_config["require_role"] else "❌ Disabled"
        embed.add_field(name="Require Role", value=require_role, inline=True)
        
        if guild_config["allowed_roles"]:
            roles = [f"<@&{role_id}>" for role_id in guild_config["allowed_roles"]]
            embed.add_field(
                name="Allowed Roles",
                value="\n".join(roles[:10]) + ("\n..." if len(roles) > 10 else ""),
                inline=False
            )
        else:
            embed.add_field(name="Allowed Roles", value="None configured", inline=False)
        
        if guild_config["admin_roles"]:
            admin_roles = [f"<@&{role_id}>" for role_id in guild_config["admin_roles"]]
            embed.add_field(
                name="Admin Roles",
                value="\n".join(admin_roles[:10]) + ("\n..." if len(admin_roles) > 10 else ""),
                inline=False
            )
        else:
            embed.add_field(name="Admin Roles", value="None configured", inline=False)
        
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed
    
    @discord.ui.button(label="🔄 Toggle Role Requirement", style=discord.ButtonStyle.primary, custom_id="toggle_role_req")
    async def toggle_role_requirement(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_config = self.scanner_cog.config.get_guild_config(self.guild_id)
        guild_config["require_role"] = not guild_config["require_role"]
        self.scanner_cog.config.save_config()
        
        status = "enabled" if guild_config["require_role"] else "disabled"
        embed = discord.Embed(
            title="✅ Role Requirement Updated",
            description=f"Role requirement has been **{status}**",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        updated_embed = self.create_role_embed()
        await interaction.response.edit_message(embed=updated_embed, view=self)
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="➕ Add Allowed Role", style=discord.ButtonStyle.success, custom_id="add_allowed_role")
    async def add_allowed_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RoleSelectionModal(self.scanner_cog, self.guild_id, "allowed", "add")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ Remove Allowed Role", style=discord.ButtonStyle.danger, custom_id="remove_allowed_role")
    async def remove_allowed_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RoleSelectionModal(self.scanner_cog, self.guild_id, "allowed", "remove")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="👑 Add Admin Role", style=discord.ButtonStyle.success, custom_id="add_admin_role")
    async def add_admin_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RoleSelectionModal(self.scanner_cog, self.guild_id, "admin", "add")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="👑 Remove Admin Role", style=discord.ButtonStyle.danger, custom_id="remove_admin_role")
    async def remove_admin_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RoleSelectionModal(self.scanner_cog, self.guild_id, "admin", "remove")
        await interaction.response.send_modal(modal)

class RoleSelectionModal(discord.ui.Modal):
    
    def __init__(self, scanner_cog, guild_id: int, role_type: str, action: str):
        super().__init__(title=f"{action.title()} {role_type.title()} Role")
        self.scanner_cog = scanner_cog
        self.guild_id = guild_id
        self.role_type = role_type
        self.action = action
        
        self.role_input = discord.ui.TextInput(
            label="Role Name or ID",
            placeholder="Enter role name or ID...",
            required=True,
            max_length=100
        )
        self.add_item(self.role_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        role_input = self.role_input.value.strip()
        
        role = None
        if role_input.isdigit():
            role = guild.get_role(int(role_input))
        else:
            role = discord.utils.get(guild.roles, name=role_input)
        
        if not role:
            await interaction.response.send_message(f"❌ Role '{role_input}' not found.", ephemeral=True)
            return
        
        guild_config = self.scanner_cog.config.get_guild_config(self.guild_id)
        role_key = f"{self.role_type}_roles"
        
        if self.action == "add":
            if role.id not in guild_config[role_key]:
                guild_config[role_key].append(role.id)
                self.scanner_cog.config.save_config()
                embed = discord.Embed(
                    title="✅ Role Added",
                    description=f"Added {role.mention} to {self.role_type} roles",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ Role Already Added",
                    description=f"{role.mention} is already in {self.role_type} roles",
                    color=discord.Color.red()
                )
        else:
            if role.id in guild_config[role_key]:
                guild_config[role_key].remove(role.id)
                self.scanner_cog.config.save_config()
                embed = discord.Embed(
                    title="✅ Role Removed",
                    description=f"Removed {role.mention} from {self.role_type} roles",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ Role Not Found",
                    description=f"{role.mention} is not in {self.role_type} roles",
                    color=discord.Color.red()
                )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class APIKeyModal(discord.ui.Modal):
    
    def __init__(self, scanner_cog):
        super().__init__(title="Set VirusTotal API Key")
        self.scanner_cog = scanner_cog
        
        self.api_key_input = discord.ui.TextInput(
            label="VirusTotal API Key",
            placeholder="Enter your VirusTotal API key...",
            required=True,
            max_length=64,
            style=discord.TextStyle.short
        )
        self.add_item(self.api_key_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        api_key = self.api_key_input.value.strip()
        
        if len(api_key) != 64 or not all(c in '0123456789abcdef' for c in api_key.lower()):
            embed = discord.Embed(
                title="❌ Invalid API Key",
                description="Please provide a valid 64-character VirusTotal API key.\n\nGet one from: https://www.virustotal.com/gui/join-us",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        self.scanner_cog.config.config["api_key"] = api_key
        self.scanner_cog.config.save_config()
        self.scanner_cog._initialize_api()
        
        embed = discord.Embed(
            title="✅ API Key Set Successfully",
            description="VirusTotal API key has been configured and the scanner is now ready to use!",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AdvancedSettingsView(discord.ui.View):
    
    def __init__(self, scanner_cog, guild_id: int):
        super().__init__(timeout=300)
        self.scanner_cog = scanner_cog
        self.guild_id = guild_id
    
    def create_settings_embed(self) -> discord.Embed:
        guild_config = self.scanner_cog.config.get_guild_config(self.guild_id)
        
        embed = discord.Embed(
            title="⚙️ Advanced Settings",
            description="Configure advanced scanner options",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Rate Limits",
            value=f"{guild_config['rate_limits']['per_user']} scans per {guild_config['rate_limits']['window_minutes']} minutes",
            inline=True
        )
        
        auto_scan_count = len(guild_config.get("auto_scan_channels", []))
        embed.add_field(
            name="Auto-Scan Channels",
            value=f"{auto_scan_count} configured",
            inline=True
        )
        
        alert_status = "✅ Enabled" if guild_config.get("alerts_enabled", False) else "❌ Disabled"
        embed.add_field(
            name="Threat Alerts",
            value=alert_status,
            inline=True
        )
        
        if guild_config.get("alert_channel"):
            embed.add_field(
                name="Alert Channel",
                value=f"<#{guild_config['alert_channel']}>",
                inline=True
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed
    
    @discord.ui.button(label="⏱️ Set Rate Limits", style=discord.ButtonStyle.primary, custom_id="set_rate_limits")
    async def set_rate_limits(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RateLimitModal(self.scanner_cog, self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔄 Auto-Scan Channels", style=discord.ButtonStyle.secondary, custom_id="manage_autoscan")
    async def manage_autoscan(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = AutoScanView(self.scanner_cog, self.guild_id)
        embed = view.create_autoscan_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="🚨 Threat Alerts", style=discord.ButtonStyle.secondary, custom_id="manage_alerts")
    async def manage_alerts(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AlertChannelModal(self.scanner_cog, self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📤 Export Data", style=discord.ButtonStyle.success, custom_id="export_data")
    async def export_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ExportView(self.scanner_cog, self.guild_id)
        embed = discord.Embed(
            title="📤 Export Scan Data",
            description="Choose export format:",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class RateLimitModal(discord.ui.Modal):
    
    def __init__(self, scanner_cog, guild_id: int):
        super().__init__(title="Set Rate Limits")
        self.scanner_cog = scanner_cog
        self.guild_id = guild_id
        
        guild_config = scanner_cog.config.get_guild_config(guild_id)
        
        self.per_user = discord.ui.TextInput(
            label="Scans per user",
            placeholder="Enter number (1-100)",
            default=str(guild_config["rate_limits"]["per_user"]),
            max_length=3
        )
        
        self.window_minutes = discord.ui.TextInput(
            label="Time window (minutes)",
            placeholder="Enter minutes (1-1440)",
            default=str(guild_config["rate_limits"]["window_minutes"]),
            max_length=4
        )
        
        self.add_item(self.per_user)
        self.add_item(self.window_minutes)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            per_user = int(self.per_user.value)
            window_minutes = int(self.window_minutes.value)
            
            if per_user < 1 or per_user > 100:
                await interaction.response.send_message("❌ Per user limit must be between 1 and 100", ephemeral=True)
                return
            
            if window_minutes < 1 or window_minutes > 1440:
                await interaction.response.send_message("❌ Window must be between 1 and 1440 minutes", ephemeral=True)
                return
            
            guild_config = self.scanner_cog.config.get_guild_config(self.guild_id)
            guild_config["rate_limits"]["per_user"] = per_user
            guild_config["rate_limits"]["window_minutes"] = window_minutes
            self.scanner_cog.config.save_config()
            
            embed = discord.Embed(
                title="✅ Rate Limits Updated",
                description=f"Set to {per_user} scans per {window_minutes} minutes",
                color=discord.Color.green()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers", ephemeral=True)

class AutoScanView(discord.ui.View):
    
    def __init__(self, scanner_cog, guild_id: int):
        super().__init__(timeout=300)
        self.scanner_cog = scanner_cog
        self.guild_id = guild_id
    
    def create_autoscan_embed(self) -> discord.Embed:
        guild_config = self.scanner_cog.config.get_guild_config(self.guild_id)
        auto_scan_channels = guild_config.get("auto_scan_channels", [])
        
        embed = discord.Embed(
            title="🔄 Auto-Scan Channels",
            description="Channels where files are automatically scanned when uploaded",
            color=discord.Color.blue()
        )
        
        if auto_scan_channels:
            channels = [f"<#{ch_id}>" for ch_id in auto_scan_channels]
            embed.add_field(
                name="Configured Channels",
                value="\n".join(channels[:15]) + ("\n..." if len(channels) > 15 else ""),
                inline=False
            )
        else:
            embed.add_field(
                name="Configured Channels",
                value="None configured",
                inline=False
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed
    
    @discord.ui.button(label="➕ Add Channel", style=discord.ButtonStyle.success, custom_id="add_autoscan_channel")
    async def add_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelSelectionModal(self.scanner_cog, self.guild_id, "add")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ Remove Channel", style=discord.ButtonStyle.danger, custom_id="remove_autoscan_channel")
    async def remove_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelSelectionModal(self.scanner_cog, self.guild_id, "remove")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🗑️ Clear All", style=discord.ButtonStyle.danger, custom_id="clear_autoscan_channels")
    async def clear_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_config = self.scanner_cog.config.get_guild_config(self.guild_id)
        guild_config["auto_scan_channels"] = []
        self.scanner_cog.config.save_config()
        
        embed = discord.Embed(
            title="✅ Channels Cleared",
            description="All auto-scan channels have been removed",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        updated_embed = self.create_autoscan_embed()
        await interaction.response.edit_message(embed=updated_embed, view=self)
        await interaction.followup.send(embed=embed, ephemeral=True)

class ChannelSelectionModal(discord.ui.Modal):
    
    def __init__(self, scanner_cog, guild_id: int, action: str):
        super().__init__(title=f"{action.title()} Auto-Scan Channel")
        self.scanner_cog = scanner_cog
        self.guild_id = guild_id
        self.action = action
        
        self.channel_input = discord.ui.TextInput(
            label="Channel Name or ID",
            placeholder="Enter channel name or ID...",
            required=True,
            max_length=100
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        channel_input = self.channel_input.value.strip()
        
        channel = None
        if channel_input.isdigit():
            channel = guild.get_channel(int(channel_input))
        else:
            channel = discord.utils.get(guild.text_channels, name=channel_input)
        
        if not channel:
            await interaction.response.send_message(f"❌ Channel '{channel_input}' not found.", ephemeral=True)
            return
        
        guild_config = self.scanner_cog.config.get_guild_config(self.guild_id)
        if "auto_scan_channels" not in guild_config:
            guild_config["auto_scan_channels"] = []
        
        if self.action == "add":
            if channel.id not in guild_config["auto_scan_channels"]:
                guild_config["auto_scan_channels"].append(channel.id)
                self.scanner_cog.config.save_config()
                embed = discord.Embed(
                    title="✅ Channel Added",
                    description=f"Added {channel.mention} to auto-scan channels",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ Channel Already Added",
                    description=f"{channel.mention} is already in auto-scan channels",
                    color=discord.Color.red()
                )
        else:
            if channel.id in guild_config["auto_scan_channels"]:
                guild_config["auto_scan_channels"].remove(channel.id)
                self.scanner_cog.config.save_config()
                embed = discord.Embed(
                    title="✅ Channel Removed",
                    description=f"Removed {channel.mention} from auto-scan channels",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ Channel Not Found",
                    description=f"{channel.mention} is not in auto-scan channels",
                    color=discord.Color.red()
                )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AlertChannelModal(discord.ui.Modal):
    
    def __init__(self, scanner_cog, guild_id: int):
        super().__init__(title="Configure Threat Alerts")
        self.scanner_cog = scanner_cog
        self.guild_id = guild_id
        
        self.channel_input = discord.ui.TextInput(
            label="Alert Channel (Name or ID)",
            placeholder="Enter channel name or ID for threat alerts...",
            required=True,
            max_length=100
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        channel_input = self.channel_input.value.strip()
        
        channel = None
        if channel_input.isdigit():
            channel = guild.get_channel(int(channel_input))
        else:
            channel = discord.utils.get(guild.text_channels, name=channel_input)
        
        if not channel:
            await interaction.response.send_message(f"❌ Channel '{channel_input}' not found.", ephemeral=True)
            return
        
        guild_config = self.scanner_cog.config.get_guild_config(self.guild_id)
        guild_config["alert_channel"] = channel.id
        guild_config["alerts_enabled"] = True
        self.scanner_cog.config.save_config()
        
        embed = discord.Embed(
            title="✅ Threat Alerts Configured",
            description=f"Threat alerts will be sent to {channel.mention}",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ExportView(discord.ui.View):
    
    def __init__(self, scanner_cog, guild_id: int):
        super().__init__(timeout=300)
        self.scanner_cog = scanner_cog
        self.guild_id = guild_id
    
    @discord.ui.button(label="📄 JSON Format", style=discord.ButtonStyle.primary, custom_id="export_json")
    async def export_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._export_data(interaction, "json")
    
    @discord.ui.button(label="📊 CSV Format", style=discord.ButtonStyle.secondary, custom_id="export_csv")
    async def export_csv(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._export_data(interaction, "csv")
    
    async def _export_data(self, interaction: discord.Interaction, format_type: str):
        all_scans = self.scanner_cog.config.scan_history.get("scans", [])
        guild_scans = [scan for scan in all_scans if scan.get("guild_id") == self.guild_id]
        
        if not guild_scans:
            await interaction.response.send_message("❌ No scan data to export", ephemeral=True)
            return
        
        if format_type == "json":
            data = json.dumps(guild_scans, indent=2)
            filename = f"virustotal_scans_{self.guild_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            import csv
            from io import StringIO
            
            output = StringIO()
            writer = csv.writer(output)
            
            writer.writerow(["Timestamp", "User ID", "Filename", "File Hash", "Status", "Malicious", "Suspicious", "Clean"])
            
            for scan in guild_scans:
                results = scan.get("results", {}).get("data", {}).get("attributes", {})
                stats = results.get("stats", {})
                
                status = "Malicious" if stats.get("malicious", 0) > 0 else (
                    "Suspicious" if stats.get("suspicious", 0) > 0 else "Clean"
                )
                
                writer.writerow([
                    scan.get("timestamp", ""),
                    scan.get("user_id", ""),
                    scan.get("filename", ""),
                    scan.get("file_hash", ""),
                    status,
                    stats.get("malicious", 0),
                    stats.get("suspicious", 0),
                    stats.get("harmless", 0) + stats.get("undetected", 0)
                ])
            
            data = output.getvalue()
            filename = f"virustotal_scans_{self.guild_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        file_data = BytesIO(data.encode('utf-8'))
        discord_file = discord.File(file_data, filename=filename)
        
        embed = discord.Embed(
            title="📊 Scan Data Export",
            description=f"Exported {len(guild_scans)} scan records in {format_type.upper()} format",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, file=discord_file, ephemeral=True)

class AdminScanHistoryView(discord.ui.View):
    
    def __init__(self, scanner_cog, guild_id: int):
        super().__init__(timeout=300)
        self.scanner_cog = scanner_cog
        self.guild_id = guild_id
        self.current_page = 0
        self.items_per_page = 10
    
    def get_guild_scans(self) -> List[Dict]:
        all_scans = self.scanner_cog.config.scan_history.get("scans", [])
        return [scan for scan in all_scans if scan.get("guild_id") == self.guild_id]
    
    def create_admin_history_embed(self, page: int = 0) -> discord.Embed:
        guild_scans = self.get_guild_scans()
        total_pages = max(1, (len(guild_scans) + self.items_per_page - 1) // self.items_per_page)
        
        embed = discord.Embed(
            title="🛡️ Server Scan History (Admin View)",
            description=f"Page {page + 1} of {total_pages} • Total scans: {len(guild_scans)}",
            color=discord.Color.gold()
        )
        
        start_idx = page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_scans = sorted(guild_scans, key=lambda x: x.get("timestamp", ""), reverse=True)[start_idx:end_idx]
        
        for scan in page_scans:
            timestamp = datetime.fromisoformat(scan["timestamp"])
            results = scan.get("results", {}).get("data", {}).get("attributes", {})
            stats = results.get("stats", {})
            
            status = "🔴 Malicious" if stats.get("malicious", 0) > 0 else (
                "🟡 Suspicious" if stats.get("suspicious", 0) > 0 else "🟢 Clean"
            )
            
            user_id = scan.get("user_id", 0)
            embed.add_field(
                name=f"📄 {scan['filename']}",
                value=f"**User:** <@{user_id}>\n"
                      f"**Status:** {status}\n"
                      f"**Date:** {timestamp.strftime('%Y-%m-%d %H:%M')}\n"
                      f"**Detections:** {stats.get('malicious', 0)}/{stats.get('malicious', 0) + stats.get('suspicious', 0) + stats.get('harmless', 0) + stats.get('undetected', 0)}",
                inline=False
            )
        
        if not page_scans:
            embed.add_field(
                name="No scans found",
                value="No scan history available for this server.",
                inline=False
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed
    
    @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, custom_id="admin_previous_page")
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            embed = self.create_admin_history_embed(self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ Already on the first page.", ephemeral=True)
    
    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary, custom_id="admin_next_page")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_scans = self.get_guild_scans()
        total_pages = max(1, (len(guild_scans) + self.items_per_page - 1) // self.items_per_page)
        
        if self.current_page < total_pages - 1:
            self.current_page += 1
            embed = self.create_admin_history_embed(self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ Already on the last page.", ephemeral=True)

class VirusTotalScanner(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.config = VirusTotalConfig()
        self.rate_limiter = RateLimiter()
        self.api = None
        self._initialize_api()
        

        self.bot.add_view(ScannerMainView(self))
    
    def _initialize_api(self):
        api_key = self.config.config.get("api_key", "")
        if api_key:
            self.api = VirusTotalAPI(api_key)
    
    def can_user_scan(self, user: discord.Member, guild: discord.Guild) -> bool:
        guild_config = self.config.get_guild_config(guild.id)
        
        if guild_config["require_role"]:
            user_role_ids = [role.id for role in user.roles]
            allowed_roles = guild_config["allowed_roles"]
            if not any(role_id in allowed_roles for role_id in user_role_ids):
                return False
        
        return True
    
    def is_admin(self, user: discord.Member, guild: discord.Guild) -> bool:
        if user.guild_permissions.administrator:
            return True
        
        guild_config = self.config.get_guild_config(guild.id)
        user_role_ids = [role.id for role in user.roles]
        admin_roles = guild_config["admin_roles"]
        
        return any(role_id in admin_roles for role_id in user_role_ids)
    
    async def process_file_upload(self, message: discord.Message, user: discord.Member):
        attachment = message.attachments[0]
        
        max_size_mb = self.config.config["global_settings"]["max_file_size_mb"]
        if attachment.size > max_size_mb * 1024 * 1024:
            embed = discord.Embed(
                title="❌ File Too Large",
                description=f"File size ({attachment.size / 1024 / 1024:.1f} MB) exceeds the limit of {max_size_mb} MB.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await message.reply(embed=embed)
            return
        
        if not self.api:
            embed = discord.Embed(
                title="❌ Scanner Not Configured",
                description="VirusTotal API key is not configured. Please contact an administrator.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await message.reply(embed=embed)
            return
        
        guild_config = self.config.get_guild_config(message.guild.id)
        self.rate_limiter.add_request(user.id)
        
        try:
            file_data = await attachment.read()
            file_hash = hashlib.sha256(file_data).hexdigest()
            
            scanning_embed = discord.Embed(
                title="🔄 Scanning File...",
                description=f"**File:** {attachment.filename}\n"
                           f"**Size:** {attachment.size / 1024:.1f} KB\n"
                           f"**Hash:** `{file_hash[:16]}...`\n\n"
                           "⏳ Please wait while we scan your file with 70+ antivirus engines...\n"
                           "This may take 30-60 seconds.",
                color=discord.Color.orange()
            )
            scanning_embed.set_footer(text="Made By TheHolyOneZ")
            scanning_message = await message.reply(embed=scanning_embed)
            
            results = await self.api.scan_file(file_data, attachment.filename)
            
            self.config.add_scan_record(
                message.guild.id, user.id, attachment.filename, file_hash, results
            )
            
            results_embed = self.create_results_embed(results, attachment.filename, file_hash)
            view = ScanResultView(self, results, user.id)
            
            await scanning_message.edit(embed=results_embed, view=view)
            
            await self._send_threat_alert(message.guild, results, attachment.filename, user)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Scan Failed",
                description=f"An error occurred while scanning the file:\n```{str(e)}```\n\n"
                           "This could be due to:\n"
                           "• API rate limits\n"
                           "• Network connectivity issues\n"
                           "• Invalid API key\n"
                           "• File too large for VirusTotal",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Made By TheHolyOneZ")
            
            try:
                await scanning_message.edit(embed=error_embed, view=None)
            except:
                await message.reply(embed=error_embed)
            
            logger.error(f"Scan failed for {attachment.filename}: {e}")
    
    async def _send_threat_alert(self, guild: discord.Guild, results: Dict, filename: str, user: discord.Member):
        guild_config = self.config.get_guild_config(guild.id)
        
        if not guild_config.get("alerts_enabled", False) or not guild_config.get("alert_channel"):
            return
        
        attributes = results.get("data", {}).get("attributes", {})
        stats = attributes.get("stats", {})
        
        if stats.get("malicious", 0) > 0 or stats.get("suspicious", 0) > 0:
            alert_channel = guild.get_channel(guild_config["alert_channel"])
            if alert_channel:
                threat_type = "🔴 MALICIOUS" if stats.get("malicious", 0) > 0 else "🟡 SUSPICIOUS"
                
                embed = discord.Embed(
                    title="🚨 Threat Detection Alert",
                    description=f"A {threat_type.lower()} file has been detected!",
                    color=discord.Color.red() if stats.get("malicious", 0) > 0 else discord.Color.orange()
                )
                
                embed.add_field(
                    name="📄 File Details",
                    value=f"**Name:** {filename}\n"
                          f"**User:** {user.mention}\n"
                          f"**Status:** {threat_type}",
                    inline=False
                )
                
                embed.add_field(
                    name="🔍 Detection Summary",
                    value=f"**Malicious:** {stats.get('malicious', 0)}\n"
                          f"**Suspicious:** {stats.get('suspicious', 0)}\n"
                          f"**Total Engines:** {sum(stats.values())}",
                    inline=True
                )
                
                embed.set_footer(text="Made By TheHolyOneZ")
                
                try:
                    await alert_channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Failed to send threat alert: {e}")
    
    def create_results_embed(self, results: Dict, filename: str, file_hash: str) -> discord.Embed:
        attributes = results.get("data", {}).get("attributes", {})
        stats = attributes.get("stats", {})
        
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        harmless = stats.get("harmless", 0)
        undetected = stats.get("undetected", 0)
        total = malicious + suspicious + harmless + undetected
        
        if malicious > 0:
            color = discord.Color.red()
            status = "🔴 MALICIOUS DETECTED"
            description = "⚠️ **WARNING: This file has been flagged as malicious by one or more antivirus engines.**"
        elif suspicious > 0:
            color = discord.Color.orange()
            status = "🟡 SUSPICIOUS"
            description = "⚠️ This file has been flagged as suspicious. Exercise caution."
        else:
            color = discord.Color.green()
            status = "🟢 CLEAN"
            description = "✅ No threats detected in this file."
        
        embed = discord.Embed(
            title="🔍 VirusTotal Scan Results",
            description=description,
            color=color
        )
        
        embed.add_field(
            name="📄 File Information",
            value=f"**Name:** {filename}\n"
                  f"**Hash:** `{file_hash[:32]}...`\n"
                  f"**Status:** {status}",
            inline=False
        )
        
        embed.add_field(
            name="📊 Detection Summary",
            value=f"🔴 Malicious: **{malicious}**\n"
                  f"🟡 Suspicious: **{suspicious}**\n"
                  f"🟢 Clean: **{harmless + undetected}**\n"
                  f"📈 Total Engines: **{total}**",
            inline=True
        )
        
        scan_date = attributes.get("date", 0)
        if scan_date:
            scan_time = datetime.fromtimestamp(scan_date)
            embed.add_field(
                name="🕒 Scan Date",
                value=scan_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
                inline=True
            )
        
        if malicious > 0 or suspicious > 0:
            engines = attributes.get("results", {})
            threat_engines = []
            
            for engine, result in engines.items():
                category = result.get("category", "")
                if category in ["malicious", "suspicious"]:
                    threat_name = result.get("result", "Unknown")
                    threat_engines.append(f"• **{engine}**: {threat_name}")
                
                if len(threat_engines) >= 5:
                    break
            
            if threat_engines:
                embed.add_field(
                    name="🚨 Top Threat Detections",
                    value="\n".join(threat_engines),
                    inline=False
                )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed
    
    @commands.group(name="vtscan", aliases=["virustotal"], invoke_without_command=True)
    async def vtscan(self, ctx):
        
        embed = discord.Embed(
            title="🔍 VirusTotal File Scanner",
            description="Advanced malware detection using VirusTotal's comprehensive database",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🚀 Quick Start",
            value="Click the **Upload & Scan File** button below to get started!",
            inline=False
        )
        
        embed.add_field(
            name="📋 Features",
            value="• Real-time malware detection\n"
                  "• Detailed scan reports\n"
                  "• Scan history tracking\n"
                  "• Advanced filtering options\n"
                  "• Rate limiting protection",
            inline=True
        )
        
        embed.add_field(
            name="🛡️ Security",
            value="• Files are scanned securely\n"
                  "• No files stored locally\n"
                  "• Powered by VirusTotal\n"
                  "• 70+ antivirus engines",
            inline=True
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        view = ScannerMainView(self)
        await ctx.send(embed=embed, view=view)
    
    @vtscan.command(name="status")
    async def status(self, ctx):
        
        guild_config = self.config.get_guild_config(ctx.guild.id)
        global_config = self.config.config["global_settings"]
        
        embed = discord.Embed(
            title="📊 VirusTotal Scanner Status",
            description="Current configuration and status information",
            color=discord.Color.blue()
        )
        

        api_status = "✅ Configured" if self.config.config.get("api_key") else "❌ Not Set"
        global_status = "✅ Enabled" if global_config["enabled"] else "❌ Disabled"
        guild_status = "✅ Enabled" if guild_config["enabled"] else "❌ Disabled"
        
        embed.add_field(
            name="🔧 Configuration Status",
            value=f"**API Key:** {api_status}\n"
                  f"**Global Status:** {global_status}\n"
                  f"**Server Status:** {guild_status}",
            inline=True
        )
        
        embed.add_field(
            name="⚙️ Settings",
            value=f"**Max File Size:** {global_config['max_file_size_mb']} MB\n"
                  f"**Rate Limit:** {guild_config['rate_limits']['per_user']}/{guild_config['rate_limits']['window_minutes']}min\n"
                  f"**Require Role:** {'Yes' if guild_config['require_role'] else 'No'}",
            inline=True
        )
        

        all_scans = self.config.scan_history.get("scans", [])
        guild_scans = [scan for scan in all_scans if scan.get("guild_id") == ctx.guild.id]
        user_scans = [scan for scan in guild_scans if scan.get("user_id") == ctx.author.id]
        
        embed.add_field(
            name="📈 Statistics",
            value=f"**Your Scans:** {len(user_scans)}\n"
                  f"**Server Scans:** {len(guild_scans)}\n"
                  f"**Total Scans:** {len(all_scans)}",
            inline=True
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @commands.group(name="vtadmin", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def vtadmin(self, ctx):
        
        prefix = ctx.prefix
        embed = discord.Embed(
            title="🛡️ VirusTotal Admin Panel",
            description="Advanced administration tools for the VirusTotal scanner",
            color=discord.Color.gold()
        )
        
        guild_config = self.config.get_guild_config(ctx.guild.id)
        
        embed.add_field(
            name="📊 Current Status",
            value=f"**Enabled:** {'✅' if guild_config['enabled'] else '❌'}\n"
                  f"**API Key:** {'✅ Set' if self.config.config.get('api_key') else '❌ Not Set'}\n"
                  f"**Rate Limit:** {guild_config['rate_limits']['per_user']}/{guild_config['rate_limits']['window_minutes']}min\n"
                  f"**Require Role:** {'✅' if guild_config['require_role'] else '❌'}",
            inline=False
        )
        
        embed.add_field(
            name="🔧 Available Commands",
            value=f"`{prefix}vtadmin panel` - Interactive admin panel\n"
                  f"`{prefix}vtadmin autoscan <add/remove/list/clear> [channel]` - Configure auto-scanning\n"
                  f"`{prefix}vtadmin alerts [channel]` - Configure threat alerts\n"
                  f"`{prefix}vtadmin export [json/csv]` - Export scan data\n"
                  f"`{prefix}vtadmin config` - View detailed configuration",
            inline=False
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        view = AdminPanelView(self, ctx.guild.id)
        await ctx.send(embed=embed, view=view)
    
    @vtadmin.command(name="panel")
    @commands.has_permissions(administrator=True)
    async def admin_panel(self, ctx):
        
        view = AdminPanelView(self, ctx.guild.id)
        embed = discord.Embed(
            title="🛡️ Interactive Admin Panel",
            description="Use the buttons below to manage scanner settings",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed, view=view)
    
    @vtadmin.command(name="autoscan")
    @commands.has_permissions(administrator=True)
    async def configure_autoscan(self, ctx, action: str = None, channel: discord.TextChannel = None):
        
        if not action:
            embed = discord.Embed(
                title="❌ Missing Arguments",
                description=f"**Usage:** `{ctx.prefix}vtadmin autoscan <action> [channel]`\n\n"
                           "**Actions:**\n"
                           "• `add <channel>` - Add channel to auto-scan\n"
                           "• `remove <channel>` - Remove channel from auto-scan\n"
                           "• `list` - Show configured channels\n"
                           "• `clear` - Remove all channels",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if action.lower() not in ["add", "remove", "list", "clear"]:
            await ctx.send("❌ Action must be `add`, `remove`, `list`, or `clear`")
            return
        
        guild_config = self.config.get_guild_config(ctx.guild.id)
        
        if "auto_scan_channels" not in guild_config:
            guild_config["auto_scan_channels"] = []
        
        if action.lower() == "list":
            channels = guild_config["auto_scan_channels"]
            if channels:
                channel_mentions = [f"<#{ch_id}>" for ch_id in channels]
                embed = discord.Embed(
                    title="📋 Auto-Scan Channels",
                    description="\n".join(channel_mentions),
                    color=discord.Color.blue()
                )
            else:
                embed = discord.Embed(
                    title="📋 Auto-Scan Channels",
                    description="No channels configured for auto-scanning",
                    color=discord.Color.blue()
                )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if action.lower() == "clear":
            guild_config["auto_scan_channels"] = []
            self.config.save_config()
            embed = discord.Embed(
                title="✅ Channels Cleared",
                description="All auto-scan channels have been removed",
                color=discord.Color.green()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if not channel:
            await ctx.send("❌ Please specify a channel")
            return
        
        if action.lower() == "add":
            if channel.id not in guild_config["auto_scan_channels"]:
                guild_config["auto_scan_channels"].append(channel.id)
                self.config.save_config()
                embed = discord.Embed(
                    title="✅ Channel Added",
                    description=f"Added {channel.mention} to auto-scan channels",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ Channel Already Added",
                    description=f"{channel.mention} is already in auto-scan channels",
                    color=discord.Color.red()
                )
        
        elif action.lower() == "remove":
            if channel.id in guild_config["auto_scan_channels"]:
                guild_config["auto_scan_channels"].remove(channel.id)
                self.config.save_config()
                embed = discord.Embed(
                    title="✅ Channel Removed",
                    description=f"Removed {channel.mention} from auto-scan channels",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ Channel Not Found",
                    description=f"{channel.mention} is not in auto-scan channels",
                    color=discord.Color.red()
                )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @vtadmin.command(name="alerts")
    @commands.has_permissions(administrator=True)
    async def configure_alerts(self, ctx, channel: discord.TextChannel = None):
        
        guild_config = self.config.get_guild_config(ctx.guild.id)
        
        if not channel:
            alert_channel = guild_config.get("alert_channel")
            if alert_channel:
                embed = discord.Embed(
                    title="🚨 Threat Alerts Configuration",
                    description=f"**Alert Channel:** <#{alert_channel}>\n"
                               f"**Enabled:** {'✅' if guild_config.get('alerts_enabled', False) else '❌'}",
                    color=discord.Color.orange()
                )
            else:
                embed = discord.Embed(
                    title="🚨 Threat Alerts Configuration",
                    description="No alert channel configured",
                    color=discord.Color.orange()
                )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        guild_config["alert_channel"] = channel.id
        guild_config["alerts_enabled"] = True
        self.config.save_config()
        
        embed = discord.Embed(
            title="✅ Alerts Configured",
            description=f"Threat alerts will be sent to {channel.mention}",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @vtadmin.command(name="export")
    @commands.has_permissions(administrator=True)
    async def export_data(self, ctx, format_type: str = "json"):
        
        if format_type.lower() not in ["json", "csv"]:
            await ctx.send("❌ Format must be `json` or `csv`")
            return
        
        all_scans = self.config.scan_history.get("scans", [])
        guild_scans = [scan for scan in all_scans if scan.get("guild_id") == ctx.guild.id]
        
        if not guild_scans:
            await ctx.send("❌ No scan data to export")
            return
        
        if format_type.lower() == "json":
            data = json.dumps(guild_scans, indent=2)
            filename = f"virustotal_scans_{ctx.guild.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            import csv
            from io import StringIO
            
            output = StringIO()
            writer = csv.writer(output)
            
            writer.writerow(["Timestamp", "User ID", "Filename", "File Hash", "Status", "Malicious", "Suspicious", "Clean"])
            
            for scan in guild_scans:
                results = scan.get("results", {}).get("data", {}).get("attributes", {})
                stats = results.get("stats", {})
                
                status = "Malicious" if stats.get("malicious", 0) > 0 else (
                    "Suspicious" if stats.get("suspicious", 0) > 0 else "Clean"
                )
                
                writer.writerow([
                    scan.get("timestamp", ""),
                    scan.get("user_id", ""),
                    scan.get("filename", ""),
                    scan.get("file_hash", ""),
                    status,
                    stats.get("malicious", 0),
                    stats.get("suspicious", 0),
                    stats.get("harmless", 0) + stats.get("undetected", 0)
                ])
            
            data = output.getvalue()
            filename = f"virustotal_scans_{ctx.guild.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        file_data = BytesIO(data.encode('utf-8'))
        discord_file = discord.File(file_data, filename=filename)
        
        embed = discord.Embed(
            title="📊 Scan Data Export",
            description=f"Exported {len(guild_scans)} scan records in {format_type.upper()} format",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed, file=discord_file)
    
    @vtadmin.command(name="config")
    @commands.has_permissions(administrator=True)
    async def view_config(self, ctx):
        
        guild_config = self.config.get_guild_config(ctx.guild.id)
        
        embed = discord.Embed(
            title="⚙️ VirusTotal Scanner Configuration",
            description="Current server settings for the VirusTotal scanner",
            color=discord.Color.blue()
        )
        
        status = "🟢 Enabled" if guild_config["enabled"] else "🔴 Disabled"
        embed.add_field(name="Status", value=status, inline=True)
        
        api_status = "✅ Set" if self.config.config.get("api_key") else "❌ Not Set"
        embed.add_field(name="API Key", value=api_status, inline=True)
        
        embed.add_field(
            name="Rate Limits",
            value=f"{guild_config['rate_limits']['per_user']} per {guild_config['rate_limits']['window_minutes']} min",
            inline=True
        )
        
        role_req = "✅ Yes" if guild_config["require_role"] else "❌ No"
        embed.add_field(name="Require Role", value=role_req, inline=True)
        
        auto_scan_count = len(guild_config.get("auto_scan_channels", []))
        embed.add_field(name="Auto-Scan Channels", value=str(auto_scan_count), inline=True)
        
        alert_status = "✅ Enabled" if guild_config.get("alerts_enabled", False) else "❌ Disabled"
        embed.add_field(name="Threat Alerts", value=alert_status, inline=True)
        
        if guild_config["allowed_channels"]:
            channels = [f"<#{ch_id}>" for ch_id in guild_config["allowed_channels"]]
            embed.add_field(
                name="Allowed Channels",
                value="\n".join(channels[:10]) + ("\n..." if len(channels) > 10 else ""),
                inline=False
            )
        else:
            embed.add_field(name="Allowed Channels", value="All channels", inline=False)
        
        if guild_config["allowed_roles"]:
            roles = [f"<@&{role_id}>" for role_id in guild_config["allowed_roles"]]
            embed.add_field(
                name="Allowed Roles",
                value="\n".join(roles[:10]) + ("\n..." if len(roles) > 10 else ""),
                inline=False
            )
        
        if guild_config["admin_roles"]:
            admin_roles = [f"<@&{role_id}>" for role_id in guild_config["admin_roles"]]
            embed.add_field(
                name="Admin Roles",
                value="\n".join(admin_roles[:10]) + ("\n..." if len(admin_roles) > 10 else ""),
                inline=False
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @vtadmin.command(name="setapi")
    @commands.has_permissions(administrator=True)
    async def set_api_key(self, ctx, api_key: str = None):
        
        if not api_key:
            embed = discord.Embed(
                title="🔑 Set VirusTotal API Key",
                description="**Usage:** `!vtadmin setapi <your_api_key>`\n\n"
                           "**Get your API key from:**\n"
                           "https://www.virustotal.com/gui/join-us\n\n"
                           "⚠️ **Security Note:** The message containing your API key will be automatically deleted.",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if len(api_key) != 64 or not all(c in '0123456789abcdef' for c in api_key.lower()):
            embed = discord.Embed(
                title="❌ Invalid API Key",
                description="Please provide a valid 64-character VirusTotal API key.\n\nGet one from: https://www.virustotal.com/gui/join-us",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        self.config.config["api_key"] = api_key
        self.config.save_config()
        self._initialize_api()
        
        try:
            await ctx.message.delete()
        except:
            pass
        
        embed = discord.Embed(
            title="✅ API Key Set Successfully",
            description="VirusTotal API key has been configured and the scanner is now ready to use!\n\n"
                       "🔒 Your message containing the API key has been deleted for security.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @vtadmin.command(name="toggle")
    @commands.has_permissions(administrator=True)
    async def toggle_scanner(self, ctx, setting: str = None):
        
        if not setting:
            embed = discord.Embed(
                title="❌ Missing Setting",
                description="**Usage:** `!vtadmin toggle <setting>`\n\n"
                           "**Available Settings:**\n"
                           "• `enabled` - Enable/disable scanner\n"
                           "• `require_role` - Toggle role requirement\n"
                           "• `alerts` - Toggle threat alerts",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        guild_config = self.config.get_guild_config(ctx.guild.id)
        
        if setting.lower() == "enabled":
            guild_config["enabled"] = not guild_config["enabled"]
            status = "enabled" if guild_config["enabled"] else "disabled"
            self.config.save_config()
            embed = discord.Embed(
                title="✅ Scanner Status Changed",
                description=f"Scanner has been **{status}** for this server",
                color=discord.Color.green() if status == "enabled" else discord.Color.red()
            )
        
        elif setting.lower() == "require_role":
            guild_config["require_role"] = not guild_config["require_role"]
            status = "enabled" if guild_config["require_role"] else "disabled"
            self.config.save_config()
            embed = discord.Embed(
                title="✅ Role Requirement Changed",
                description=f"Role requirement has been **{status}**",
                color=discord.Color.green()
            )
        
        elif setting.lower() == "alerts":
            guild_config["alerts_enabled"] = not guild_config.get("alerts_enabled", False)
            status = "enabled" if guild_config["alerts_enabled"] else "disabled"
            self.config.save_config()
            embed = discord.Embed(
                title="✅ Threat Alerts Changed",
                description=f"Threat alerts have been **{status}**",
                color=discord.Color.green()
            )
        
        else:
            embed = discord.Embed(
                title="❌ Invalid Setting",
                description="Valid settings: `enabled`, `require_role`, `alerts`",
                color=discord.Color.red()
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @vtadmin.command(name="ratelimit")
    @commands.has_permissions(administrator=True)
    async def set_rate_limit(self, ctx, per_user: int = None, window_minutes: int = None):
        
        if per_user is None or window_minutes is None:
            guild_config = self.config.get_guild_config(ctx.guild.id)
            current_limit = guild_config["rate_limits"]
            
            embed = discord.Embed(
                title="⏱️ Rate Limit Configuration",
                description=f"**Current Setting:** {current_limit['per_user']} scans per {current_limit['window_minutes']} minutes\n\n"
                           f"**Usage:** `{ctx.prefix}vtadmin ratelimit <per_user> <window_minutes>`\n\n"
                           "**Example:** `!vtadmin ratelimit 5 60` (5 scans per hour)",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if per_user < 1 or per_user > 100:
            await ctx.send("❌ Per user limit must be between 1 and 100")
            return
        
        if window_minutes < 1 or window_minutes > 1440:
            await ctx.send("❌ Window must be between 1 and 1440 minutes")
            return
        
        guild_config = self.config.get_guild_config(ctx.guild.id)
        guild_config["rate_limits"]["per_user"] = per_user
        guild_config["rate_limits"]["window_minutes"] = window_minutes
        self.config.save_config()
        
        embed = discord.Embed(
            title="✅ Rate Limit Updated",
            description=f"Rate limit set to **{per_user}** scans per **{window_minutes}** minutes",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @vtadmin.command(name="stats")
    @commands.has_permissions(administrator=True)
    async def admin_stats(self, ctx):
        
        all_scans = self.config.scan_history.get("scans", [])
        guild_scans = [scan for scan in all_scans if scan.get("guild_id") == ctx.guild.id]
        
        malicious_count = 0
        suspicious_count = 0
        clean_count = 0
        user_stats = {}
        
        for scan in guild_scans:
            results = scan.get("results", {}).get("data", {}).get("attributes", {})
            stats = results.get("stats", {})
            user_id = scan.get("user_id", 0)
            
            if user_id not in user_stats:
                user_stats[user_id] = {"total": 0, "malicious": 0, "suspicious": 0, "clean": 0}
            
            user_stats[user_id]["total"] += 1
            
            if stats.get("malicious", 0) > 0:
                malicious_count += 1
                user_stats[user_id]["malicious"] += 1
            elif stats.get("suspicious", 0) > 0:
                suspicious_count += 1
                user_stats[user_id]["suspicious"] += 1
            else:
                clean_count += 1
                user_stats[user_id]["clean"] += 1
        
        embed = discord.Embed(
            title="📊 Advanced Scanner Statistics",
            description="Detailed statistics for this server",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="🏢 Server Overview",
            value=f"**Total Scans:** {len(guild_scans)}\n"
                  f"🔴 Malicious: {malicious_count}\n"
                  f"🟡 Suspicious: {suspicious_count}\n"
                  f"🟢 Clean: {clean_count}\n"
                  f"👥 Active Users: {len(user_stats)}",
            inline=True
        )
        
        if guild_scans:
            threat_rate = ((malicious_count + suspicious_count) / len(guild_scans)) * 100
            embed.add_field(
                name="📈 Threat Analysis",
                value=f"**Threat Rate:** {threat_rate:.1f}%\n"
                      f"**Safety Score:** {100 - threat_rate:.1f}%\n"
                      f"**Risk Level:** {'🔴 High' if threat_rate > 10 else '🟡 Medium' if threat_rate > 5 else '🟢 Low'}",
                inline=True
            )
        
        top_users = sorted(user_stats.items(), key=lambda x: x[1]["total"], reverse=True)[:5]
        if top_users:
            top_users_text = []
            for user_id, stats in top_users:
                total = stats["total"]
                threats = stats["malicious"] + stats["suspicious"]
                top_users_text.append(f"<@{user_id}>: {total} scans ({threats} threats)")
            
            embed.add_field(
                name="👑 Top Users",
                value="\n".join(top_users_text),
                inline=False
            )
        
        recent_scans = sorted(guild_scans, key=lambda x: x.get("timestamp", ""), reverse=True)[:5]
        if recent_scans:
            recent_text = []
            for scan in recent_scans:
                timestamp = datetime.fromisoformat(scan["timestamp"])
                results = scan.get("results", {}).get("data", {}).get("attributes", {})
                stats = results.get("stats", {})
                
                status = "🔴" if stats.get("malicious", 0) > 0 else (
                    "🟡" if stats.get("suspicious", 0) > 0 else "🟢"
                )
                
                recent_text.append(f"{status} {scan['filename'][:25]}... - {timestamp.strftime('%m/%d %H:%M')}")
            
            embed.add_field(
                name="🕒 Recent Activity",
                value="\n".join(recent_text),
                inline=False
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @vtadmin.command(name="cleanup")
    @commands.has_permissions(administrator=True)
    async def cleanup_history(self, ctx, days: int = None):
        
        if days is None:
            embed = discord.Embed(
                title="🧹 Cleanup Scan History",
                description="**Usage:** `!vtadmin cleanup <days>`\n\n"
                           "This will remove scan records older than the specified number of days.\n\n"
                           "**Example:** `!vtadmin cleanup 30` (removes records older than 30 days)\n"
                           "**Range:** 1-365 days",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if days < 1 or days > 365:
            await ctx.send("❌ Days must be between 1 and 365")
            return
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        all_scans = self.config.scan_history.get("scans", [])
        
        filtered_scans = []
        removed_count = 0
        
        for scan in all_scans:
            scan_date = datetime.fromisoformat(scan["timestamp"])
            if scan_date > cutoff_date or scan.get("guild_id") != ctx.guild.id:
                filtered_scans.append(scan)
            else:
                removed_count += 1
        
        self.config.scan_history["scans"] = filtered_scans
        self.config.save_scan_history()
        
        embed = discord.Embed(
            title="🧹 History Cleanup Complete",
            description=f"Successfully removed **{removed_count}** scan records older than **{days}** days",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @commands.command(name="vtstats")
    async def user_stats(self, ctx):
        
        all_scans = self.config.scan_history.get("scans", [])
        guild_scans = [scan for scan in all_scans if scan.get("guild_id") == ctx.guild.id]
        user_scans = [scan for scan in guild_scans if scan.get("user_id") == ctx.author.id]
        
        total_guild_scans = len(guild_scans)
        total_user_scans = len(user_scans)
        
        user_malicious = 0
        user_suspicious = 0
        user_clean = 0
        
        for scan in user_scans:
            results = scan.get("results", {}).get("data", {}).get("attributes", {})
            stats = results.get("stats", {})
            
            if stats.get("malicious", 0) > 0:
                user_malicious += 1
            elif stats.get("suspicious", 0) > 0:
                user_suspicious += 1
            else:
                user_clean += 1
        
        embed = discord.Embed(
            title="📊 Your Scanner Statistics",
            description="Your file scanning statistics for this server",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="👤 Your Stats",
            value=f"**Total Scans:** {total_user_scans}\n"
                  f"🔴 Malicious: {user_malicious}\n"
                  f"🟡 Suspicious: {user_suspicious}\n"
                  f"🟢 Clean: {user_clean}",
            inline=True
        )
        
        if total_guild_scans > 0:
            percentage = (total_user_scans / total_guild_scans) * 100
            user_counts = {}
            for scan in guild_scans:
                user_id = scan.get("user_id", 0)
            user_counts[user_id] = user_counts.get(user_id, 0) + 1
            
            sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
            user_rank = next((i + 1 for i, (uid, _) in enumerate(sorted_users) if uid == ctx.author.id), len(sorted_users))
            
            embed.add_field(
                name="📈 Server Comparison",
                value=f"**Server Total:** {total_guild_scans}\n"
                      f"**Your Share:** {percentage:.1f}%\n"
                      f"**Rank:** #{user_rank}",
                inline=True
            )
        
        if total_user_scans > 0:
            user_threat_rate = ((user_malicious + user_suspicious) / total_user_scans) * 100
            embed.add_field(
                name="🛡️ Safety Analysis",
                value=f"**Threat Rate:** {user_threat_rate:.1f}%\n"
                      f"**Safety Score:** {100 - user_threat_rate:.1f}%\n"
                      f"**Status:** {'🔴 High Risk' if user_threat_rate > 20 else '🟡 Medium Risk' if user_threat_rate > 10 else '🟢 Low Risk'}",
                inline=True
            )
        
        recent_user_scans = sorted(user_scans, key=lambda x: x.get("timestamp", ""), reverse=True)[:5]
        if recent_user_scans:
            recent_text = []
            for scan in recent_user_scans:
                timestamp = datetime.fromisoformat(scan["timestamp"])
                results = scan.get("results", {}).get("data", {}).get("attributes", {})
                stats = results.get("stats", {})
                
                status = "🔴" if stats.get("malicious", 0) > 0 else (
                    "🟡" if stats.get("suspicious", 0) > 0 else "🟢"
                )
                
                recent_text.append(f"{status} {scan['filename'][:30]}... - {timestamp.strftime('%m/%d %H:%M')}")
            
            embed.add_field(
                name="🕒 Your Recent Scans",
                value="\n".join(recent_text),
                inline=False
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        
        if message.author.bot or not message.guild or not message.attachments:
            return
        
        guild_config = self.config.get_guild_config(message.guild.id)
        auto_scan_channels = guild_config.get("auto_scan_channels", [])
        
        if message.channel.id not in auto_scan_channels:
            return
        
        if not self.can_user_scan(message.author, message.guild):
            return
        
        if not guild_config["enabled"] or not self.config.config["global_settings"]["enabled"]:
            return
        
        rate_limit = guild_config["rate_limits"]
        if not self.rate_limiter.can_make_request(
            message.author.id, 
            rate_limit["per_user"], 
            rate_limit["window_minutes"]
        ):
            return
        
        await self.process_file_upload(message, message.author)
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        
        self.config.get_guild_config(guild.id)
    
    @vtscan.error
    async def vtscan_error(self, ctx, error):
        
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You don't have permission to use this command.",
                color=discord.Color.red()
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❌ Missing Argument",
                description=f"Missing required argument: `{error.param.name}`",
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="❌ Command Error",
                description="An unexpected error occurred. Please try again.",
                color=discord.Color.red()
            )
            logger.error(f"Command error in vtscan: {error}")
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @vtadmin.error
    async def vtadmin_error(self, ctx, error):
        
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You need Administrator permissions to use this command.",
                color=discord.Color.red()
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❌ Missing Argument",
                description=f"Missing required argument: `{error.param.name}`\n\nUse `{ctx.prefix}vtadmin` for help.",
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="❌ Command Error",
                description="An unexpected error occurred. Please try again.",
                color=discord.Color.red()
            )
            logger.error(f"Command error in vtadmin: {error}")
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)


class VirusTotalGlobalCommands(commands.Cog):
    
    
    def __init__(self, bot, scanner_cog):
        self.bot = bot
        self.scanner = scanner_cog
    
    @commands.group(name="vtglobal", invoke_without_command=True)
    @commands.is_owner()
    async def vtglobal(self, ctx):
        
        embed = discord.Embed(
            title="🌐 Global VirusTotal Management",
            description="Bot owner commands for global scanner management",
            color=discord.Color.gold()
        )
        
        global_config = self.scanner.config.config["global_settings"]
        total_scans = len(self.scanner.config.scan_history.get("scans", []))
        
        embed.add_field(
            name="📊 Global Status",
            value=f"**Enabled:** {'✅' if global_config['enabled'] else '❌'}\n"
                  f"**API Key:** {'✅ Set' if self.scanner.config.config.get('api_key') else '❌ Not Set'}\n"
                  f"**Total Scans:** {total_scans}\n"
                  f"**Max File Size:** {global_config['max_file_size_mb']} MB",
            inline=False
        )
        
        embed.add_field(
            name="🔧 Available Commands",
            value=f"`{ctx.prefix}vtglobal toggle` - Enable/disable globally\n"
                  f"`{ctx.prefix}vtglobal stats` - Global statistics\n"
                  f"`{ctx.prefix}vtglobal cleanup <days>` - Global cleanup\n"
                  f"`{ctx.prefix}vtglobal export` - Export all data\n"
                  f"`{ctx.prefix}vtglobal setsize <mb>` - Set max file size",
            inline=False
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @vtglobal.command(name="toggle")
    @commands.is_owner()
    async def global_toggle(self, ctx):
        
        current_status = self.scanner.config.config["global_settings"]["enabled"]
        self.scanner.config.config["global_settings"]["enabled"] = not current_status
        self.scanner.config.save_config()
        
        status = "enabled" if self.scanner.config.config["global_settings"]["enabled"] else "disabled"
        embed = discord.Embed(
            title="🛑 Global Scanner Control",
            description=f"Scanner has been globally **{status}**",
            color=discord.Color.green() if status == "enabled" else discord.Color.red()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @vtglobal.command(name="stats")
    @commands.is_owner()
    async def global_stats(self, ctx):
        
        all_scans = self.scanner.config.scan_history.get("scans", [])
        
        guild_stats = {}
        user_stats = {}
        malicious_total = 0
        suspicious_total = 0
        clean_total = 0
        
        for scan in all_scans:
            guild_id = scan.get("guild_id", 0)
            user_id = scan.get("user_id", 0)
            
            if guild_id not in guild_stats:
                guild_stats[guild_id] = {"total": 0, "malicious": 0, "suspicious": 0, "clean": 0}
            
            if user_id not in user_stats:
                user_stats[user_id] = {"total": 0, "malicious": 0, "suspicious": 0, "clean": 0}
            
            results = scan.get("results", {}).get("data", {}).get("attributes", {})
            stats = results.get("stats", {})
            
            guild_stats[guild_id]["total"] += 1
            user_stats[user_id]["total"] += 1
            
            if stats.get("malicious", 0) > 0:
                malicious_total += 1
                guild_stats[guild_id]["malicious"] += 1
                user_stats[user_id]["malicious"] += 1
            elif stats.get("suspicious", 0) > 0:
                suspicious_total += 1
                guild_stats[guild_id]["suspicious"] += 1
                user_stats[user_id]["suspicious"] += 1
            else:
                clean_total += 1
                guild_stats[guild_id]["clean"] += 1
                user_stats[user_id]["clean"] += 1
        
        embed = discord.Embed(
            title="🌐 Global Scanner Statistics",
            description="Comprehensive statistics across all servers",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="📊 Overall Stats",
            value=f"**Total Scans:** {len(all_scans)}\n"
                  f"🔴 Malicious: {malicious_total}\n"
                  f"🟡 Suspicious: {suspicious_total}\n"
                  f"🟢 Clean: {clean_total}\n"
                  f"🏢 Active Servers: {len(guild_stats)}\n"
                  f"👥 Active Users: {len(user_stats)}",
            inline=True
        )
        
        if len(all_scans) > 0:
            threat_rate = ((malicious_total + suspicious_total) / len(all_scans)) * 100
            embed.add_field(
                name="📈 Threat Analysis",
                value=f"**Global Threat Rate:** {threat_rate:.1f}%\n"
                      f"**Safety Score:** {100 - threat_rate:.1f}%\n"
                      f"**Risk Assessment:** {'🔴 High' if threat_rate > 15 else '🟡 Medium' if threat_rate > 8 else '🟢 Low'}",
                inline=True
            )
        
        top_guilds = sorted(guild_stats.items(), key=lambda x: x[1]["total"], reverse=True)[:5]
        if top_guilds:
            top_guilds_text = []
            for guild_id, stats in top_guilds:
                guild = self.bot.get_guild(guild_id)
                guild_name = guild.name if guild else f"Unknown ({guild_id})"
                threats = stats["malicious"] + stats["suspicious"]
                top_guilds_text.append(f"**{guild_name}**: {stats['total']} scans ({threats} threats)")
            
            embed.add_field(
                name="🏆 Top Servers",
                value="\n".join(top_guilds_text),
                inline=False
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @vtglobal.command(name="cleanup")
    @commands.is_owner()
    async def global_cleanup(self, ctx, days: int):
        
        if days < 1 or days > 365:
            await ctx.send("❌ Days must be between 1 and 365")
            return
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        all_scans = self.scanner.config.scan_history.get("scans", [])
        
        filtered_scans = []
        removed_count = 0
        
        for scan in all_scans:
            scan_date = datetime.fromisoformat(scan["timestamp"])
            if scan_date > cutoff_date:
                filtered_scans.append(scan)
            else:
                removed_count += 1
        
        self.scanner.config.scan_history["scans"] = filtered_scans
        self.scanner.config.save_scan_history()
        
        embed = discord.Embed(
            title="🧹 Global Cleanup Complete",
            description=f"Successfully removed **{removed_count}** scan records older than **{days}** days across all servers",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @vtglobal.command(name="export")
    @commands.is_owner()
    async def global_export(self, ctx, format_type: str = "json"):
        
        if format_type.lower() not in ["json", "csv"]:
            await ctx.send("❌ Format must be `json` or `csv`")
            return
        
        all_scans = self.scanner.config.scan_history.get("scans", [])
        
        if not all_scans:
            await ctx.send("❌ No scan data to export")
            return
        
        if format_type.lower() == "json":
            data = json.dumps(all_scans, indent=2)
            filename = f"virustotal_global_scans_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            import csv
            from io import StringIO
            
            output = StringIO()
            writer = csv.writer(output)
            
            writer.writerow(["Timestamp", "Guild ID", "User ID", "Filename", "File Hash", "Status", "Malicious", "Suspicious", "Clean"])
            
            for scan in all_scans:
                results = scan.get("results", {}).get("data", {}).get("attributes", {})
                stats = results.get("stats", {})
                
                status = "Malicious" if stats.get("malicious", 0) > 0 else (
                    "Suspicious" if stats.get("suspicious", 0) > 0 else "Clean"
                )
                
                writer.writerow([
                    scan.get("timestamp", ""),
                    scan.get("guild_id", ""),
                    scan.get("user_id", ""),
                    scan.get("filename", ""),
                    scan.get("file_hash", ""),
                    status,
                    stats.get("malicious", 0),
                    stats.get("suspicious", 0),
                    stats.get("harmless", 0) + stats.get("undetected", 0)
                ])
            
            data = output.getvalue()
            filename = f"virustotal_global_scans_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        file_data = BytesIO(data.encode('utf-8'))
        discord_file = discord.File(file_data, filename=filename)
        
        embed = discord.Embed(
            title="📊 Global Scan Data Export",
            description=f"Exported **{len(all_scans)}** scan records from all servers in {format_type.upper()} format",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed, file=discord_file)
    
    @vtglobal.command(name="setsize")
    @commands.is_owner()
    async def set_max_file_size(self, ctx, size_mb: int):
        
        if size_mb < 1 or size_mb > 256:
            await ctx.send("❌ File size must be between 1 and 256 MB")
            return
        
        self.scanner.config.config["global_settings"]["max_file_size_mb"] = size_mb
        self.scanner.config.save_config()
        
        embed = discord.Embed(
            title="✅ Max File Size Updated",
            description=f"Global maximum file size set to **{size_mb} MB**",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)


async def setup(bot):
    
    scanner_cog = VirusTotalScanner(bot)
    global_cog = VirusTotalGlobalCommands(bot, scanner_cog)
    
    await bot.add_cog(scanner_cog)
    await bot.add_cog(global_cog)
    
    logger.info("VirusTotal Scanner extension loaded successfully")
    return scanner_cog

def setup(bot):
    
    scanner_cog = VirusTotalScanner(bot)
    global_cog = VirusTotalGlobalCommands(bot, scanner_cog)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(scanner_cog))
    loop.create_task(bot.add_cog(global_cog))
    
    logger.info("VirusTotal Scanner extension loaded successfully")
    return scanner_cog

if __name__ == "__main__":
    print("VirusTotal Scanner Extension")
    print("This extension provides comprehensive file scanning using VirusTotal API")
    print("Features:")
    print("- Interactive UI with buttons and modals")
    print("- Rate limiting and permission management")
    print("- Scan history tracking and filtering")
    print("- Auto-scanning in configured channels")
    print("- Threat alerts for malicious files")
    print("- Admin panel for configuration")
    print("- Data export capabilities")
    print("- Global management commands for bot owners")
