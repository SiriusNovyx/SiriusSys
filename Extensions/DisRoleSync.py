import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
import datetime
import uuid
from typing import Dict, List, Optional, Union, Set


CONFIG_FILE = "data/disrolesync_config.json"


EMBED_COLOR_NEUTRAL = 0x2F3136
EMBED_COLOR_SUCCESS = 0x57F287
EMBED_COLOR_ERROR = 0xED4245
EMBED_COLOR_INFO = 0x3498DB
EMBED_COLOR_WARNING = 0xFEE75C

class RoleSyncManager:
    def __init__(self):
        self.server_links = {}  # source_guild_id -> [target_guild_ids]
        self.role_mappings = {}  # f"{source_guild_id}:{source_role_id}" -> {target_guild_id: target_role_id}
        self.pending_approvals = {}  # approval_id -> approval_data
        self.sync_settings = {}  # guild_id -> settings
        self.pending_server_links = {}  # request_id -> {source_guild_id, target_guild_id, timestamp}
        self.load_config()
    
    def load_config(self):
        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.server_links = data.get('server_links', {})
                    self.role_mappings = data.get('role_mappings', {})
                    self.pending_approvals = data.get('pending_approvals', {})
                    self.sync_settings = data.get('sync_settings', {})
                    self.pending_server_links = data.get('pending_server_links', {})
            except Exception as e:
                print(f"Error loading role sync config: {e}")
                self.server_links = {}
                self.role_mappings = {}
                self.pending_approvals = {}
                self.sync_settings = {}
                self.pending_server_links = {}
    
    def save_config(self):
        
        data = {
            'server_links': self.server_links,
            'role_mappings': self.role_mappings,
            'pending_approvals': self.pending_approvals,
            'sync_settings': self.sync_settings,
            'pending_server_links': self.pending_server_links
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    
    def link_servers(self, source_guild_id: int, target_guild_id: int) -> bool:
        
        source_guild_id_str = str(source_guild_id)
        target_guild_id_str = str(target_guild_id)
        

        if source_guild_id_str not in self.server_links:
            self.server_links[source_guild_id_str] = []
        

        if target_guild_id_str not in self.server_links[source_guild_id_str]:
            self.server_links[source_guild_id_str].append(target_guild_id_str)
            self.save_config()
            return True
        
        return False
    
    def unlink_servers(self, source_guild_id: int, target_guild_id: int) -> bool:
        
        source_guild_id_str = str(source_guild_id)
        target_guild_id_str = str(target_guild_id)
        
        if source_guild_id_str in self.server_links and target_guild_id_str in self.server_links[source_guild_id_str]:
            self.server_links[source_guild_id_str].remove(target_guild_id_str)
            

            if not self.server_links[source_guild_id_str]:
                del self.server_links[source_guild_id_str]
            

            keys_to_remove = []
            for key in self.role_mappings:
                src_guild, _ = key.split(':')
                if src_guild == source_guild_id_str and target_guild_id_str in self.role_mappings[key]:
                    del self.role_mappings[key][target_guild_id_str]
                    if not self.role_mappings[key]:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.role_mappings[key]
            
            self.save_config()
            return True
        
        return False
    
    def get_linked_servers(self, guild_id: int) -> List[str]:
        
        guild_id_str = str(guild_id)
        return self.server_links.get(guild_id_str, [])
    
    def map_roles(self, source_guild_id: int, source_role_id: int, target_guild_id: int, target_role_id: int) -> bool:
        
        key = f"{source_guild_id}:{source_role_id}"
        
        if key not in self.role_mappings:
            self.role_mappings[key] = {}
        
        self.role_mappings[key][str(target_guild_id)] = str(target_role_id)
        self.save_config()
        return True
    
    def unmap_role(self, source_guild_id: int, source_role_id: int, target_guild_id: int) -> bool:
        
        key = f"{source_guild_id}:{source_role_id}"
        target_guild_id_str = str(target_guild_id)
        
        if key in self.role_mappings and target_guild_id_str in self.role_mappings[key]:
            del self.role_mappings[key][target_guild_id_str]
            

            if not self.role_mappings[key]:
                del self.role_mappings[key]
            
            self.save_config()
            return True
        
        return False
    
    def get_role_mappings(self, source_guild_id: int) -> Dict[str, Dict[str, str]]:
        
        result = {}
        prefix = f"{source_guild_id}:"
        
        for key, mappings in self.role_mappings.items():
            if key.startswith(prefix):
                result[key] = mappings
        
        return result
    
    def get_mapped_role(self, source_guild_id: int, source_role_id: int, target_guild_id: int) -> Optional[str]:
        
        key = f"{source_guild_id}:{source_role_id}"
        target_guild_id_str = str(target_guild_id)
        
        if key in self.role_mappings and target_guild_id_str in self.role_mappings[key]:
            return self.role_mappings[key][target_guild_id_str]
        
        return None
    
    def create_approval(self, source_guild_id: int, target_guild_id: int, user_id: int, roles: List[Dict]) -> str:
        
        approval_id = str(uuid.uuid4())
        
        self.pending_approvals[approval_id] = {
            'source_guild_id': str(source_guild_id),
            'target_guild_id': str(target_guild_id),
            'user_id': str(user_id),
            'roles': roles,
            'created_at': datetime.datetime.now().isoformat(),
            'status': 'pending'
        }
        
        self.save_config()
        return approval_id
    
    def approve_sync(self, approval_id: str) -> bool:
        
        if approval_id in self.pending_approvals:
            self.pending_approvals[approval_id]['status'] = 'approved'
            self.save_config()
            return True
        return False
    
    def deny_sync(self, approval_id: str) -> bool:
        
        if approval_id in self.pending_approvals:
            self.pending_approvals[approval_id]['status'] = 'denied'
            self.save_config()
            return True
        return False
    
    def get_pending_approvals(self, guild_id: int) -> List[Dict]:
        
        guild_id_str = str(guild_id)
        result = []
        
        for approval_id, data in self.pending_approvals.items():
            if data['target_guild_id'] == guild_id_str and data['status'] == 'pending':
                approval_data = data.copy()
                approval_data['id'] = approval_id
                result.append(approval_data)
        
        return result
    
    def create_server_link_request(self, source_guild_id: int, target_guild_id: int) -> str:
        
        request_id = str(uuid.uuid4())
        
        self.pending_server_links[request_id] = {
            'source_guild_id': str(source_guild_id),
            'target_guild_id': str(target_guild_id),
            'created_at': datetime.datetime.now().isoformat(),
            'status': 'pending'
        }
        
        self.save_config()
        return request_id
    
    def approve_server_link(self, request_id: str) -> bool:
        
        if request_id in self.pending_server_links and self.pending_server_links[request_id]['status'] == 'pending':
            source_guild_id = int(self.pending_server_links[request_id]['source_guild_id'])
            target_guild_id = int(self.pending_server_links[request_id]['target_guild_id'])
            

            success = self.link_servers(source_guild_id, target_guild_id)
            
            if success:
                self.pending_server_links[request_id]['status'] = 'approved'
                self.save_config()
                return True
        
        return False
    
    def deny_server_link(self, request_id: str) -> bool:
        
        if request_id in self.pending_server_links and self.pending_server_links[request_id]['status'] == 'pending':
            self.pending_server_links[request_id]['status'] = 'denied'
            self.save_config()
            return True
        
        return False
    
    def get_pending_server_link_requests(self, guild_id: int) -> List[Dict]:
        
        guild_id_str = str(guild_id)
        result = []
        
        for request_id, data in self.pending_server_links.items():
            if data['target_guild_id'] == guild_id_str and data['status'] == 'pending':
                request_data = data.copy()
                request_data['id'] = request_id
                result.append(request_data)
        
        return result
    
    def set_sync_settings(self, guild_id: int, settings: Dict) -> bool:
        
        self.sync_settings[str(guild_id)] = settings
        self.save_config()
        return True
    
    def get_sync_settings(self, guild_id: int) -> Dict:
        
        default_settings = {
            'require_approval': True,
            'auto_sync_on_join': True,
            'sync_removals': True,
            'notification_channel': None
        }
        
        user_settings = self.sync_settings.get(str(guild_id), {})

        for key, value in default_settings.items():
            if key not in user_settings:
                user_settings[key] = value
        
        return user_settings


class ServerLinkView(discord.ui.View):
    def __init__(self, cog, guild):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.guild = guild
    
    async def on_timeout(self):

        for item in self.children:
            item.disabled = True
    
    @discord.ui.button(label="Link Server", style=discord.ButtonStyle.primary)
    async def link_server_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        modal = LinkServerModal(self.cog, self.guild)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Unlink Server", style=discord.ButtonStyle.danger)
    async def unlink_server_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        

        linked_servers = self.cog.role_sync_manager.get_linked_servers(self.guild.id)
        
        if not linked_servers:
            await interaction.response.send_message(
                "❌ This server is not linked to any other servers.",
                ephemeral=True
            )
            return
        

        options = []
        for server_id in linked_servers:
            server = self.cog.bot.get_guild(int(server_id))
            server_name = server.name if server else f"Unknown Server ({server_id})"
            
            options.append(
                discord.SelectOption(
                    label=server_name,
                    value=server_id,
                    description=f"Server ID: {server_id}"
                )
            )
        

        select = discord.ui.Select(
            placeholder="Select a server to unlink",
            options=options
        )
        
        async def select_callback(select_interaction):
            target_guild_id = int(select.values[0])
            

            success = self.cog.role_sync_manager.unlink_servers(self.guild.id, target_guild_id)
            
            if success:
                target_guild = self.cog.bot.get_guild(target_guild_id)
                target_name = target_guild.name if target_guild else f"Unknown Server ({target_guild_id})"
                
                await select_interaction.response.send_message(
                    f"✅ Successfully unlinked from {target_name}!",
                    ephemeral=True
                )
                

                embed = await self.cog.create_server_links_embed(self.guild)
                try:
                    await interaction.message.edit(embed=embed)
                except discord.errors.NotFound:


                    await select_interaction.channel.send(embed=embed, view=self.parent_view)
            else:
                await select_interaction.response.send_message(
                    "❌ Failed to unlink server.",
                    ephemeral=True
                )
        
        select.callback = select_callback
        

        view = discord.ui.View(timeout=60)
        view.add_item(select)
        
        await interaction.response.send_message(
            "Select a server to unlink:",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="View Settings", style=discord.ButtonStyle.secondary)
    async def settings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        

        settings = self.cog.role_sync_manager.get_sync_settings(self.guild.id)
        

        view = SyncSettingsView(self.cog, self.guild, settings)
        embed = view.create_settings_embed()
        
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        embed = await self.cog.create_server_links_embed(self.guild)
        await interaction.response.edit_message(embed=embed, view=self)


class LinkServerModal(discord.ui.Modal, title="Link Server"):
    server_id = discord.ui.TextInput(
        label="Server ID",
        placeholder="Enter the ID of the server to link",
        required=True
    )
    
    def __init__(self, cog, guild):
        super().__init__()
        self.cog = cog
        self.guild = guild
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            target_guild_id = int(self.server_id.value.strip())
            

            target_guild = self.cog.bot.get_guild(target_guild_id)
            if not target_guild:
                await interaction.response.send_message(
                    "❌ I'm not in that server. Make sure the bot is added to both servers you want to link.",
                    ephemeral=True
                )
                return
            

            if target_guild_id == self.guild.id:
                await interaction.response.send_message(
                    "❌ You cannot link a server to itself.",
                    ephemeral=True
                )
                return
            

            linked_servers = self.cog.role_sync_manager.get_linked_servers(self.guild.id)
            if str(target_guild_id) in linked_servers:
                await interaction.response.send_message(
                    f"⚠️ This server is already linked with {target_guild.name}.",
                    ephemeral=True
                )
                return
            

            request_id = self.cog.role_sync_manager.create_server_link_request(self.guild.id, target_guild_id)
            

            target_settings = self.cog.role_sync_manager.get_sync_settings(target_guild_id)
            notification_channel_id = target_settings.get('notification_channel')
            
            notification_sent = False
            

            if notification_channel_id:
                channel = target_guild.get_channel(int(notification_channel_id))
                if channel and channel.permissions_for(target_guild.me).send_messages:
                    embed = discord.Embed(
                        title="DisRoleSync - New Server Link Request",
                        description=f"A server has requested to link with your server for role synchronization.",
                        color=EMBED_COLOR_WARNING
                    )
                    
                    embed.add_field(
                        name="Requesting Server",
                        value=f"{self.guild.name} (ID: {self.guild.id})",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="Server Owner",
                        value=f"{self.guild.owner.mention if self.guild.owner else 'Unknown'}",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="Request ID",
                        value=request_id,
                        inline=False
                    )
                    
                    embed.set_footer(text="Use !disrolesync serverrequests to manage server link requests")
                    
                    await channel.send(embed=embed)
                    notification_sent = True
            

            if not notification_sent:

                for channel in target_guild.text_channels:

                    everyone_role = target_guild.default_role
                    if (channel.overwrites_for(everyone_role).read_messages is False and 
                            channel.permissions_for(target_guild.me).send_messages):
                        embed = discord.Embed(
                            title="DisRoleSync - New Server Link Request",
                            description=f"A server has requested to link with your server for role synchronization.",
                            color=EMBED_COLOR_WARNING
                        )
                        
                        embed.add_field(
                            name="Requesting Server",
                            value=f"{self.guild.name} (ID: {self.guild.id})",
                            inline=True
                        )
                        
                        embed.add_field(
                            name="Server Owner",
                            value=f"{self.guild.owner.mention if self.guild.owner else 'Unknown'}",
                            inline=True
                        )
                        
                        embed.add_field(
                            name="Request ID",
                            value=request_id,
                            inline=False
                        )
                        
                        embed.add_field(
                            name="Note",
                            value="This message was sent to this channel because no notification channel is configured. "
                                  "Use `!disrolesync settings` to set a notification channel.",
                            inline=False
                        )
                        
                        embed.set_footer(text="Use !disrolesync serverrequests to manage server link requests")
                        
                        await channel.send(embed=embed)
                        notification_sent = True
                        break
            

            if not notification_sent and target_guild.owner:
                try:
                    embed = discord.Embed(
                        title="DisRoleSync - New Server Link Request",
                        description=f"A server has requested to link with your server ({target_guild.name}) for role synchronization.",
                        color=EMBED_COLOR_WARNING
                    )
                    
                    embed.add_field(
                        name="Requesting Server",
                        value=f"{self.guild.name} (ID: {self.guild.id})",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="Server Owner",
                        value=f"{self.guild.owner.name if self.guild.owner else 'Unknown'}",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="Request ID",
                        value=request_id,
                        inline=False
                    )
                    
                    embed.add_field(
                        name="Note",
                        value="This DM was sent because no notification channel is configured in your server. "
                              "Use `!disrolesync settings` to set a notification channel.",
                        inline=False
                    )
                    
                    embed.set_footer(text="Use !disrolesync serverrequests to manage server link requests")
                    
                    await target_guild.owner.send(embed=embed)
                    notification_sent = True
                except:
                    pass  # DM failed, continue
            
            await interaction.response.send_message(
                f"✅ Link request sent to {target_guild.name}!\n\n"
                f"An administrator in that server must approve the link request before you can set up role mappings.\n"
                f"They can approve it using `!disrolesync serverrequests`.",
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid server ID. Please enter a valid server ID.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )


class SyncSettingsView(discord.ui.View):
    def __init__(self, cog, guild, settings):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.guild = guild
        self.settings = settings
    
    def create_settings_embed(self):
        
        embed = discord.Embed(
            title="DisRoleSync - Settings",
            description="Configure how role synchronization works for your server.",
            color=EMBED_COLOR_INFO
        )
        

        embed.add_field(
            name="Require Approval",
            value="✅ Enabled" if self.settings.get('require_approval', True) else "❌ Disabled",
            inline=True
        )
        
        embed.add_field(
            name="Auto-Sync on Join",
            value="✅ Enabled" if self.settings.get('auto_sync_on_join', True) else "❌ Disabled",
            inline=True
        )
        
        embed.add_field(
            name="Sync Role Removals",
            value="✅ Enabled" if self.settings.get('sync_removals', True) else "❌ Disabled",
            inline=True
        )
        

        notification_channel_id = self.settings.get('notification_channel')
        if notification_channel_id:
            channel = self.guild.get_channel(int(notification_channel_id))
            channel_mention = channel.mention if channel else f"Unknown Channel ({notification_channel_id})"
            embed.add_field(
                name="Notification Channel",
                value=channel_mention,
                inline=False
            )
        else:
            embed.add_field(
                name="Notification Channel",
                value="None set (notifications will be sent to a private channel or server owner)",
                inline=False
            )
        
        embed.set_footer(text="Use the buttons below to change settings")
        return embed
    
    @discord.ui.button(label="Toggle Approval", style=discord.ButtonStyle.primary)
    async def toggle_approval_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        self.settings['require_approval'] = not self.settings.get('require_approval', True)
        

        self.cog.role_sync_manager.set_sync_settings(self.guild.id, self.settings)
        

        embed = self.create_settings_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Toggle Auto-Sync", style=discord.ButtonStyle.primary)
    async def toggle_autosync_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        self.settings['auto_sync_on_join'] = not self.settings.get('auto_sync_on_join', True)
        

        self.cog.role_sync_manager.set_sync_settings(self.guild.id, self.settings)
        

        embed = self.create_settings_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Toggle Sync Removals", style=discord.ButtonStyle.primary)
    async def toggle_removals_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        self.settings['sync_removals'] = not self.settings.get('sync_removals', True)
        

        self.cog.role_sync_manager.set_sync_settings(self.guild.id, self.settings)
        

        embed = self.create_settings_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Set Notification Channel", style=discord.ButtonStyle.secondary)
    async def set_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        

        options = []
        

        for channel in self.guild.text_channels:
            if len(options) < 25:  # Discord has a limit of 25 options
                options.append(
                    discord.SelectOption(
                        label=channel.name,
                        value=str(channel.id),
                        description=f"Channel ID: {channel.id}"
                    )
                )
        

        options.append(
            discord.SelectOption(
                label="None (Clear setting)",
                value="none",
                description="Remove notification channel"
            )
        )
        

        select = discord.ui.Select(
            placeholder="Select a notification channel",
            options=options
        )
        
        async def select_callback(select_interaction):
            if select.values[0] == "none":
                self.settings['notification_channel'] = None
            else:
                self.settings['notification_channel'] = select.values[0]
            

            self.cog.role_sync_manager.set_sync_settings(self.guild.id, self.settings)
            

            embed = self.create_settings_embed()
            try:
                await interaction.message.edit(embed=embed, view=self)
            except discord.errors.NotFound:

                await select_interaction.channel.send(embed=embed, view=self)
            
            await select_interaction.response.send_message(
                "✅ Notification channel updated!",
                ephemeral=True
            )
        
        select.callback = select_callback
        

        view = discord.ui.View(timeout=60)
        view.add_item(select)
        
        await interaction.response.send_message(
            "Select a notification channel:",
            view=view,
            ephemeral=True
        )


class RoleMappingView(discord.ui.View):
    def __init__(self, cog, source_guild, target_guild):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.source_guild = source_guild
        self.target_guild = target_guild
        self.current_page = 0
        self.roles_per_page = 10
    
    async def on_timeout(self):

        for item in self.children:
            item.disabled = True
    
    async def create_mapping_embed(self):
        
        embed = discord.Embed(
            title=f"DisRoleSync - Role Mappings",
            description=f"Role mappings between **{self.source_guild.name}** and **{self.target_guild.name}**",
            color=EMBED_COLOR_INFO
        )
        

        source_to_target_mappings = self.cog.role_sync_manager.get_role_mappings(self.source_guild.id)
        target_to_source_mappings = self.cog.role_sync_manager.get_role_mappings(self.target_guild.id)
        
        if not source_to_target_mappings and not target_to_source_mappings:
            embed.add_field(
                name="No Mappings",
                value="No roles have been mapped between these servers yet. Use the buttons below to create mappings.",
                inline=False
            )
            return embed
        

        target_guild_id_str = str(self.target_guild.id)
        source_guild_id_str = str(self.source_guild.id)
        relevant_mappings = []
        

        for key, targets in source_to_target_mappings.items():
            if target_guild_id_str in targets:
                source_guild_id, source_role_id = key.split(':')
                target_role_id = targets[target_guild_id_str]
                
                source_role = discord.utils.get(self.source_guild.roles, id=int(source_role_id))
                target_role = discord.utils.get(self.target_guild.roles, id=int(target_role_id))
                
                if source_role and target_role:

                    reverse_key = f"{self.target_guild.id}:{target_role_id}"
                    has_reverse = False
                    
                    if reverse_key in target_to_source_mappings and source_guild_id_str in target_to_source_mappings[reverse_key]:
                        if target_to_source_mappings[reverse_key][source_guild_id_str] == str(source_role_id):
                            has_reverse = True
                    
                    relevant_mappings.append({
                        'source_role': source_role,
                        'target_role': target_role,
                        'two_way': has_reverse,
                        'key': key
                    })
        
        if not relevant_mappings:
            embed.add_field(
                name="No Mappings",
                value="No roles have been mapped between these servers yet. Use the buttons below to create mappings.",
                inline=False
            )
            return embed
        

        relevant_mappings.sort(key=lambda m: m['source_role'].position, reverse=True)
        

        start_idx = self.current_page * self.roles_per_page
        end_idx = min(start_idx + self.roles_per_page, len(relevant_mappings))
        

        for i in range(start_idx, end_idx):
            mapping = relevant_mappings[i]
            source_role = mapping['source_role']
            target_role = mapping['target_role']
            mapping_type = "↔️ Two-way" if mapping['two_way'] else "→ One-way"
            
            embed.add_field(
                name=f"{source_role.name} {mapping_type} {target_role.name}",
                value=f"Source Role ID: {source_role.id}\nTarget Role ID: {target_role.id}",
                inline=False
            )
        

        total_pages = (len(relevant_mappings) + self.roles_per_page - 1) // self.roles_per_page
        embed.set_footer(text=f"Page {self.current_page + 1}/{max(1, total_pages)} | ZygnalBot by TheHolyOneZ")
        
        return embed
    
    @discord.ui.button(label="Add Mapping", style=discord.ButtonStyle.primary)
    async def add_mapping_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        

        source_options = []
        target_options = []
        

        for role in sorted(self.source_guild.roles, key=lambda r: r.position, reverse=True):
            if not role.is_default() and len(source_options) < 25:
                source_options.append(
                    discord.SelectOption(
                        label=role.name[:100],  # Limit label length to prevent errors
                        value=str(role.id),
                        description=f"Role ID: {role.id}"[:100]  # Limit description length
                    )
                )
        
        for role in sorted(self.target_guild.roles, key=lambda r: r.position, reverse=True):
            if not role.is_default() and len(target_options) < 25:
                target_options.append(
                    discord.SelectOption(
                        label=role.name[:100],  # Limit label length to prevent errors
                        value=str(role.id),
                        description=f"Role ID: {role.id}"[:100]  # Limit description length
                    )
                )
        
        if not source_options or not target_options:
            await interaction.response.send_message(
                "❌ One or both servers don't have any roles that can be mapped.",
                ephemeral=True
            )
            return
        

        class MappingSelectionView(discord.ui.View):
            def __init__(self, parent_view, timeout=60):
                super().__init__(timeout=timeout)
                self.parent_view = parent_view
                self.source_role_id = None
                self.target_role_id = None
                self.two_way = True  # Default to two-way mapping
                

                self.source_select = discord.ui.Select(
                    placeholder=f"Select a role from {parent_view.source_guild.name}",
                    options=source_options
                )
                self.source_select.callback = self.source_select_callback
                
                self.target_select = discord.ui.Select(
                    placeholder=f"Select a role from {parent_view.target_guild.name}",
                    options=target_options
                )
                self.target_select.callback = self.target_select_callback
                
                self.add_item(self.source_select)
                self.add_item(self.target_select)
            
            async def source_select_callback(self, select_interaction):
                self.source_role_id = int(self.source_select.values[0])
                await select_interaction.response.defer()
            
            async def target_select_callback(self, select_interaction):
                self.target_role_id = int(self.target_select.values[0])
                await select_interaction.response.defer()
            
            @discord.ui.button(label="Two-Way Mapping: ON", style=discord.ButtonStyle.success, row=1)
            async def toggle_two_way_button(self, toggle_interaction, button):
                self.two_way = not self.two_way
                button.label = f"Two-Way Mapping: {'ON' if self.two_way else 'OFF'}"
                button.style = discord.ButtonStyle.success if self.two_way else discord.ButtonStyle.secondary
                await toggle_interaction.response.edit_message(view=self)
            
            @discord.ui.button(label="Confirm Mapping", style=discord.ButtonStyle.primary, row=1)
            async def confirm_button(self, confirm_interaction, button):
                if not self.source_role_id or not self.target_role_id:
                    await confirm_interaction.response.send_message(
                        "❌ Please select both source and target roles.",
                        ephemeral=True
                    )
                    return
                

                success1 = self.parent_view.cog.role_sync_manager.map_roles(
                    self.parent_view.source_guild.id, self.source_role_id,
                    self.parent_view.target_guild.id, self.target_role_id
                )
                

                success2 = True
                if self.two_way:
                    success2 = self.parent_view.cog.role_sync_manager.map_roles(
                        self.parent_view.target_guild.id, self.target_role_id,
                        self.parent_view.source_guild.id, self.source_role_id
                    )
                
                if success1 and success2:
                    source_role = discord.utils.get(self.parent_view.source_guild.roles, id=self.source_role_id)
                    target_role = discord.utils.get(self.parent_view.target_guild.roles, id=self.target_role_id)
                    
                    mapping_type = "two-way" if self.two_way else "one-way"
                    await confirm_interaction.response.send_message(
                        f"✅ Successfully created {mapping_type} mapping between:\n"
                        f"• **{source_role.name}** in {self.parent_view.source_guild.name}\n"
                        f"• **{target_role.name}** in {self.parent_view.target_guild.name}",
                        ephemeral=True
                    )
                    

                    embed = await self.parent_view.create_mapping_embed()
                    try:
                        await interaction.message.edit(embed=embed, view=self.parent_view)
                    except discord.errors.NotFound:

                        await confirm_interaction.channel.send(embed=embed, view=self.parent_view)
                else:
                    await confirm_interaction.response.send_message(
                        "❌ Failed to create role mapping.",
                        ephemeral=True
                    )
        

        mapping_view = MappingSelectionView(self)
        await interaction.response.send_message(
            "Select roles to map:\n"
            "**Note:** Two-way mapping is enabled by default. Toggle it off if you only want one-way synchronization.",
            view=mapping_view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Remove Mapping", style=discord.ButtonStyle.danger)
    async def remove_mapping_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        

        source_to_target_mappings = self.cog.role_sync_manager.get_role_mappings(self.source_guild.id)
        target_to_source_mappings = self.cog.role_sync_manager.get_role_mappings(self.target_guild.id)
        
        if not source_to_target_mappings and not target_to_source_mappings:
            await interaction.response.send_message(
                "❌ No role mappings exist for this server.",
                ephemeral=True
            )
            return
        

        target_guild_id_str = str(self.target_guild.id)
        source_guild_id_str = str(self.source_guild.id)
        relevant_mappings = []
        

        for key, targets in source_to_target_mappings.items():
            if target_guild_id_str in targets:
                source_guild_id, source_role_id = key.split(':')
                target_role_id = targets[target_guild_id_str]
                
                source_role = discord.utils.get(self.source_guild.roles, id=int(source_role_id))
                target_role = discord.utils.get(self.target_guild.roles, id=int(target_role_id))
                
                if source_role and target_role:

                    reverse_key = f"{self.target_guild.id}:{target_role_id}"
                    has_reverse = False
                    
                    if reverse_key in target_to_source_mappings and source_guild_id_str in target_to_source_mappings[reverse_key]:
                        if target_to_source_mappings[reverse_key][source_guild_id_str] == str(source_role_id):
                            has_reverse = True
                    
                    relevant_mappings.append({
                        'source_role': source_role,
                        'target_role': target_role,
                        'two_way': has_reverse,
                        'key': key,
                        'reverse_key': reverse_key if has_reverse else None,
                        'source_role_id': source_role_id,
                        'target_role_id': target_role_id
                    })
        
        if not relevant_mappings:
            await interaction.response.send_message(
                "❌ No role mappings exist between these servers.",
                ephemeral=True
            )
            return
        

        options = []
        for idx, mapping in enumerate(relevant_mappings):
            source_role = mapping['source_role']
            target_role = mapping['target_role']
            mapping_type = "↔️ Two-way" if mapping['two_way'] else "→ One-way"
            

            label = f"{source_role.name[:40]} {mapping_type} {target_role.name[:40]}"
            if len(label) > 100:
                label = label[:97] + "..."
                
            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(idx),  # Use index to reference the mapping
                    description="Remove this mapping"[:100]
                )
            )
        

        select = discord.ui.Select(
            placeholder="Select a mapping to remove",
            options=options[:25]  # Discord has a limit of 25 options
        )
        
        class RemoveMappingView(discord.ui.View):
            def __init__(self, parent_view, mappings, timeout=60):
                super().__init__(timeout=timeout)
                self.parent_view = parent_view
                self.mappings = mappings
                self.selected_mapping = None
                self.remove_both_directions = True
                
                self.add_item(select)
            
            @discord.ui.button(label="Remove Both Directions: ON", style=discord.ButtonStyle.success, row=1)
            async def toggle_both_directions(self, toggle_interaction, button):

                if self.selected_mapping and self.selected_mapping['two_way']:
                    self.remove_both_directions = not self.remove_both_directions
                    button.label = f"Remove Both Directions: {'ON' if self.remove_both_directions else 'OFF'}"
                    button.style = discord.ButtonStyle.success if self.remove_both_directions else discord.ButtonStyle.secondary
                    await toggle_interaction.response.edit_message(view=self)
                else:
                    await toggle_interaction.response.send_message(
                        "This option is only available for two-way mappings.",
                        ephemeral=True
                    )
            
            @discord.ui.button(label="Confirm Removal", style=discord.ButtonStyle.danger, row=1)
            async def confirm_removal(self, confirm_interaction, button):
                if not self.selected_mapping:
                    await confirm_interaction.response.send_message(
                        "❌ Please select a mapping to remove.",
                        ephemeral=True
                    )
                    return
                
                source_guild_id = self.parent_view.source_guild.id
                target_guild_id = self.parent_view.target_guild.id
                source_role_id = int(self.selected_mapping['source_role_id'])
                target_role_id = int(self.selected_mapping['target_role_id'])
                

                success1 = self.parent_view.cog.role_sync_manager.unmap_role(
                    source_guild_id, source_role_id, target_guild_id
                )
                
                success2 = True

                if self.selected_mapping['two_way'] and self.remove_both_directions:

                    success2 = self.parent_view.cog.role_sync_manager.unmap_role(
                        target_guild_id, target_role_id, source_guild_id
                    )
                
                if success1 and success2:
                    source_role = self.selected_mapping['source_role']
                    target_role = self.selected_mapping['target_role']
                    
                    message = f"✅ Successfully removed mapping between **{source_role.name}** and **{target_role.name}**!"
                    if self.selected_mapping['two_way'] and self.remove_both_directions:
                        message += "\nBoth directions of the mapping have been removed."
                    
                    await confirm_interaction.response.send_message(
                        message,
                        ephemeral=True
                    )
                    

                    embed = await self.parent_view.create_mapping_embed()
                    try:
                        await interaction.message.edit(embed=embed, view=self.parent_view)
                    except discord.errors.NotFound:

                        await confirm_interaction.channel.send(embed=embed, view=self.parent_view)
                else:
                    await confirm_interaction.response.send_message(
                        "❌ Failed to remove role mapping.",
                        ephemeral=True
                    )
        

        remove_view = RemoveMappingView(self, relevant_mappings)
        

        async def select_callback(select_interaction):
            idx = int(select.values[0])
            remove_view.selected_mapping = relevant_mappings[idx]
            

            for child in remove_view.children:
                if isinstance(child, discord.ui.Button) and "Remove Both Directions" in child.label:
                    child.disabled = not remove_view.selected_mapping['two_way']
                    if not remove_view.selected_mapping['two_way']:
                        child.label = "Remove Both Directions: N/A"
                        child.style = discord.ButtonStyle.secondary
                    else:
                        child.label = "Remove Both Directions: ON"
                        child.style = discord.ButtonStyle.success
                        remove_view.remove_both_directions = True
            
            await select_interaction.response.edit_message(view=remove_view)
        
        select.callback = select_callback
        
        await interaction.response.send_message(
            "Select a role mapping to remove:",
            view=remove_view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        if self.current_page > 0:
            self.current_page -= 1
            embed = await self.create_mapping_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        

        mappings = self.cog.role_sync_manager.get_role_mappings(self.source_guild.id)
        

        target_guild_id_str = str(self.target_guild.id)
        relevant_mappings = []
        
        for key, targets in mappings.items():
            if target_guild_id_str in targets:
                source_guild_id, source_role_id = key.split(':')
                target_role_id = targets[target_guild_id_str]
                
                source_role = discord.utils.get(self.source_guild.roles, id=int(source_role_id))
                target_role = discord.utils.get(self.target_guild.roles, id=int(target_role_id))
                
                if source_role and target_role:
                    relevant_mappings.append({
                        'source_role': source_role,
                        'target_role': target_role
                    })
        
        total_pages = (len(relevant_mappings) + self.roles_per_page - 1) // self.roles_per_page
        
        if self.current_page < total_pages - 1:
            self.current_page += 1
            embed = await self.create_mapping_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        embed = await self.create_mapping_embed()
        await interaction.response.edit_message(embed=embed, view=self)


class ApprovalView(discord.ui.View):
    def __init__(self, cog, guild):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.guild = guild
        self.current_page = 0
        self.approvals_per_page = 5
    
    async def on_timeout(self):

        for item in self.children:
            item.disabled = True
    
    async def create_approvals_embed(self):
        
        embed = discord.Embed(
            title="DisRoleSync - Pending Approvals",
            description="Role sync requests awaiting approval",
            color=EMBED_COLOR_WARNING
        )
        

        approvals = self.cog.role_sync_manager.get_pending_approvals(self.guild.id)
        
        if not approvals:
            embed.description = "No pending role sync approvals."
            return embed
        

        approvals.sort(key=lambda a: a.get('created_at', ''), reverse=True)
        

        start_idx = self.current_page * self.approvals_per_page
        end_idx = min(start_idx + self.approvals_per_page, len(approvals))
        

        for i in range(start_idx, end_idx):
            approval = approvals[i]
            

            user_id = int(approval['user_id'])
            source_guild_id = int(approval['source_guild_id'])
            
            user = self.cog.bot.get_user(user_id)
            user_name = user.name if user else f"Unknown User ({user_id})"
            
            source_guild = self.cog.bot.get_guild(source_guild_id)
            source_guild_name = source_guild.name if source_guild else f"Unknown Server ({source_guild_id})"
            

            roles_text = ""
            for role_data in approval.get('roles', []):
                roles_text += f"• {role_data.get('name', 'Unknown Role')}\n"
            
            if not roles_text:
                roles_text = "No roles to sync"
            

            embed.add_field(
                name=f"Request from {user_name}",
                value=(
                    f"**Source Server:** {source_guild_name}\n"
                    f"**Requested Roles:**\n{roles_text}\n"
                    f"**ID:** {approval['id']}"
                ),
                inline=False
            )
        

        total_pages = (len(approvals) + self.approvals_per_page - 1) // self.approvals_per_page
        embed.set_footer(text=f"Page {self.current_page + 1}/{max(1, total_pages)} | ZygnalBot by TheHolyOneZ")
        
        return embed
    
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        

        approvals = self.cog.role_sync_manager.get_pending_approvals(self.guild.id)
        
        if not approvals:
            await interaction.response.send_message(
                "❌ No pending approvals to process.",
                ephemeral=True
            )
            return
        

        approvals.sort(key=lambda a: a.get('created_at', ''), reverse=True)
        

        options = []
        for approval in approvals[:25]:  # Discord has a limit of 25 options
            user_id = int(approval['user_id'])
            user = self.cog.bot.get_user(user_id)
            user_name = user.name if user else f"Unknown User ({user_id})"
            
            options.append(
                discord.SelectOption(
                    label=f"Request from {user_name}",
                    value=approval['id'],
                    description=f"Approve this request"
                )
            )
        

        select = discord.ui.Select(
            placeholder="Select a request to approve",
            options=options
        )
        
        async def select_callback(select_interaction):
            approval_id = select.values[0]
            

            success = self.cog.role_sync_manager.approve_sync(approval_id)
            
            if success:

                approval_data = None
                for approval in approvals:
                    if approval['id'] == approval_id:
                        approval_data = approval
                        break
                
                if approval_data:

                    await self.cog.sync_user_roles(
                        int(approval_data['user_id']),
                        int(approval_data['source_guild_id']),
                        int(approval_data['target_guild_id']),
                        approval_data.get('roles', [])
                    )
                
                await select_interaction.response.send_message(
                    "✅ Role sync request approved and processed!",
                    ephemeral=True
                )
                

                embed = await self.create_approvals_embed()
                await interaction.message.edit(embed=embed, view=self)
            else:
                await select_interaction.response.send_message(
                    "❌ Failed to approve role sync request.",
                    ephemeral=True
                )
        
        select.callback = select_callback
        

        view = discord.ui.View(timeout=60)
        view.add_item(select)
        
        await interaction.response.send_message(
            "Select a role sync request to approve:",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        

        approvals = self.cog.role_sync_manager.get_pending_approvals(self.guild.id)
        
        if not approvals:
            await interaction.response.send_message(
                "❌ No pending approvals to process.",
                ephemeral=True
            )
            return
        

        approvals.sort(key=lambda a: a.get('created_at', ''), reverse=True)
        

        options = []
        for approval in approvals[:25]:  # Discord has a limit of 25 options
            user_id = int(approval['user_id'])
            user = self.cog.bot.get_user(user_id)
            user_name = user.name if user else f"Unknown User ({user_id})"
            
            options.append(
                discord.SelectOption(
                    label=f"Request from {user_name}",
                    value=approval['id'],
                    description=f"Deny this request"
                )
            )
        

        select = discord.ui.Select(
            placeholder="Select a request to deny",
            options=options
        )
        
        async def select_callback(select_interaction):
            approval_id = select.values[0]
            

            success = self.cog.role_sync_manager.deny_sync(approval_id)
            
            if success:
                await select_interaction.response.send_message(
                    "✅ Role sync request denied!",
                    ephemeral=True
                )
                

                embed = await self.create_approvals_embed()
                await interaction.message.edit(embed=embed, view=self)
            else:
                await select_interaction.response.send_message(
                    "❌ Failed to deny role sync request.",
                    ephemeral=True
                )
        
        select.callback = select_callback
        

        view = discord.ui.View(timeout=60)
        view.add_item(select)
        
        await interaction.response.send_message(
            "Select a role sync request to deny:",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        if self.current_page > 0:
            self.current_page -= 1
            embed = await self.create_approvals_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        

        approvals = self.cog.role_sync_manager.get_pending_approvals(self.guild.id)
        total_pages = (len(approvals) + self.approvals_per_page - 1) // self.approvals_per_page
        
        if self.current_page < total_pages - 1:
            self.current_page += 1
            embed = await self.create_approvals_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        self.current_page = 0
        embed = await self.create_approvals_embed()
        await interaction.response.edit_message(embed=embed, view=self)


class ServerRequestView(discord.ui.View):
    def __init__(self, cog, guild):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.guild = guild
        self.current_page = 0
        self.requests_per_page = 5
    
    async def on_timeout(self):

        for item in self.children:
            item.disabled = True
    
    async def create_requests_embed(self):
        
        embed = discord.Embed(
            title="DisRoleSync - Pending Server Link Requests",
            description="Servers requesting to link with your server",
            color=EMBED_COLOR_WARNING
        )
        

        requests = self.cog.role_sync_manager.get_pending_server_link_requests(self.guild.id)
        
        if not requests:
            embed.description = "No pending server link requests."
            return embed
        

        requests.sort(key=lambda r: r.get('created_at', ''), reverse=True)
        

        start_idx = self.current_page * self.requests_per_page
        end_idx = min(start_idx + self.requests_per_page, len(requests))
        

        for i in range(start_idx, end_idx):
            request = requests[i]
            

            source_guild_id = int(request['source_guild_id'])
            source_guild = self.cog.bot.get_guild(source_guild_id)
            source_guild_name = source_guild.name if source_guild else f"Unknown Server ({source_guild_id})"
            

            embed.add_field(
                name=f"Request from {source_guild_name}",
                value=(
                    f"**Server ID:** {source_guild_id}\n"
                    f"**Requested On:** {datetime.datetime.fromisoformat(request['created_at']).strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"**Request ID:** {request['id']}"
                ),
                inline=False
            )
        

        total_pages = (len(requests) + self.requests_per_page - 1) // self.requests_per_page
        embed.set_footer(text=f"Page {self.current_page + 1}/{max(1, total_pages)} | ZygnalBot by TheHolyOneZ")
        
        return embed
    
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        

        requests = self.cog.role_sync_manager.get_pending_server_link_requests(self.guild.id)
        
        if not requests:
            await interaction.response.send_message(
                "❌ No pending requests to process.",
                ephemeral=True
            )
            return
        

        requests.sort(key=lambda r: r.get('created_at', ''), reverse=True)
        

        options = []
        for request in requests[:25]:  # Discord has a limit of 25 options
            source_guild_id = int(request['source_guild_id'])
            source_guild = self.cog.bot.get_guild(source_guild_id)
            source_guild_name = source_guild.name if source_guild else f"Unknown Server ({source_guild_id})"
            
            options.append(
                discord.SelectOption(
                    label=f"Request from {source_guild_name}",
                    value=request['id'],
                    description=f"Approve this request"
                )
            )
        

        select = discord.ui.Select(
            placeholder="Select a request to approve",
            options=options
        )
        
        async def select_callback(select_interaction):
            request_id = select.values[0]
            

            success = self.cog.role_sync_manager.approve_server_link(request_id)
            
            if success:

                request_data = None
                for request in requests:
                    if request['id'] == request_id:
                        request_data = request
                        break
                
                if request_data:
                    source_guild_id = int(request_data['source_guild_id'])
                    source_guild = self.cog.bot.get_guild(source_guild_id)
                    source_guild_name = source_guild.name if source_guild else f"Unknown Server ({source_guild_id})"
                    
                    await select_interaction.response.send_message(
                        f"✅ Server link request from {source_guild_name} approved!\n\n"
                        f"The servers are now linked and role mappings can be set up.",
                        ephemeral=True
                    )
                    

                    if source_guild:
                        source_settings = self.cog.role_sync_manager.get_sync_settings(source_guild_id)
                        notification_channel_id = source_settings.get('notification_channel')
                        
                        notification_sent = False
                        

                        if notification_channel_id:
                            channel = source_guild.get_channel(int(notification_channel_id))
                            if channel and channel.permissions_for(source_guild.me).send_messages:
                                embed = discord.Embed(
                                    title="DisRoleSync - Server Link Approved",
                                    description=f"Your server link request has been approved!",
                                    color=EMBED_COLOR_SUCCESS
                                )
                                
                                embed.add_field(
                                    name="Linked Server",
                                    value=f"{self.guild.name} (ID: {self.guild.id})",
                                    inline=False
                                )
                                
                                embed.add_field(
                                    name="Next Steps",
                                    value="You can now set up role mappings using `!disrolesync roles`",
                                    inline=False
                                )
                                
                                await channel.send(embed=embed)
                                notification_sent = True
                        

                        if not notification_sent:

                            for channel in source_guild.text_channels:

                                everyone_role = source_guild.default_role
                                if (channel.overwrites_for(everyone_role).read_messages is False and 
                                        channel.permissions_for(source_guild.me).send_messages):
                                    embed = discord.Embed(
                                        title="DisRoleSync - Server Link Approved",
                                        description=f"Your server link request has been approved!",
                                        color=EMBED_COLOR_SUCCESS
                                    )
                                    
                                    embed.add_field(
                                        name="Linked Server",
                                        value=f"{self.guild.name} (ID: {self.guild.id})",
                                        inline=False
                                    )
                                    
                                    embed.add_field(
                                        name="Next Steps",
                                        value="You can now set up role mappings using `!disrolesync roles`",
                                        inline=False
                                    )
                                    
                                    embed.add_field(
                                        name="Note",
                                        value="This message was sent to this channel because no notification channel is configured. "
                                              "Use `!disrolesync settings` to set a notification channel.",
                                        inline=False
                                    )
                                    
                                    await channel.send(embed=embed)
                                    notification_sent = True
                                    break
                

                embed = await self.create_requests_embed()
                await interaction.message.edit(embed=embed, view=self)
            else:
                await select_interaction.response.send_message(
                    "❌ Failed to approve server link request.",
                    ephemeral=True
                )
        
        select.callback = select_callback
        

        view = discord.ui.View(timeout=60)
        view.add_item(select)
        
        await interaction.response.send_message(
            "Select a server link request to approve:",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        

        requests = self.cog.role_sync_manager.get_pending_server_link_requests(self.guild.id)
        
        if not requests:
            await interaction.response.send_message(
                "❌ No pending requests to process.",
                ephemeral=True
            )
            return
        

        requests.sort(key=lambda r: r.get('created_at', ''), reverse=True)
        

        options = []
        for request in requests[:25]:  # Discord has a limit of 25 options
            source_guild_id = int(request['source_guild_id'])
            source_guild = self.cog.bot.get_guild(source_guild_id)
            source_guild_name = source_guild.name if source_guild else f"Unknown Server ({source_guild_id})"
            
            options.append(
                discord.SelectOption(
                    label=f"Request from {source_guild_name}",
                    value=request['id'],
                    description=f"Deny this request"
                )
            )
        

        select = discord.ui.Select(
            placeholder="Select a request to deny",
            options=options
        )
        
        async def select_callback(select_interaction):
            request_id = select.values[0]
            

            success = self.cog.role_sync_manager.deny_server_link(request_id)
            
            if success:

                request_data = None
                for request in requests:
                    if request['id'] == request_id:
                        request_data = request
                        break
                
                if request_data:
                    source_guild_id = int(request_data['source_guild_id'])
                    source_guild = self.cog.bot.get_guild(source_guild_id)
                    source_guild_name = source_guild.name if source_guild else f"Unknown Server ({source_guild_id})"
                    
                    await select_interaction.response.send_message(
                        f"✅ Server link request from {source_guild_name} denied!",
                        ephemeral=True
                    )
                

                embed = await self.create_requests_embed()
                await interaction.message.edit(embed=embed, view=self)
            else:
                await select_interaction.response.send_message(
                    "❌ Failed to deny server link request.",
                    ephemeral=True
                )
        
        select.callback = select_callback
        

        view = discord.ui.View(timeout=60)
        view.add_item(select)
        
        await interaction.response.send_message(
            "Select a server link request to deny:",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        if self.current_page > 0:
            self.current_page -= 1
            embed = await self.create_requests_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        

        requests = self.cog.role_sync_manager.get_pending_server_link_requests(self.guild.id)
        total_pages = (len(requests) + self.requests_per_page - 1) // self.requests_per_page
        
        if self.current_page < total_pages - 1:
            self.current_page += 1
            embed = await self.create_requests_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        self.current_page = 0
        embed = await self.create_requests_embed()
        await interaction.response.edit_message(embed=embed, view=self)


class DisRoleSync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_sync_manager = RoleSyncManager()
        self.check_role_changes.start()
        
    def cog_unload(self):
        self.check_role_changes.cancel()
    
    @tasks.loop(minutes=5)
    async def check_role_changes(self):
        


        pass
    
    @check_role_changes.before_loop
    async def before_check_role_changes(self):
        
        await self.bot.wait_until_ready()
    
    async def create_server_links_embed(self, guild):
        
        embed = discord.Embed(
            title="DisRoleSync - Server Links",
            description=f"Server links for **{guild.name}**",
            color=EMBED_COLOR_INFO
        )
        

        linked_servers = self.role_sync_manager.get_linked_servers(guild.id)
        
        if not linked_servers:
            embed.add_field(
                name="No Linked Servers",
                value="This server is not linked to any other servers. Use the buttons below to create links.",
                inline=False
            )
        else:

            for server_id in linked_servers:
                server = self.bot.get_guild(int(server_id))
                if server:

                    mappings = self.role_sync_manager.get_role_mappings(guild.id)
                    mapping_count = 0
                    
                    for key, targets in mappings.items():
                        if server_id in targets:
                            mapping_count += 1
                    
                    embed.add_field(
                        name=server.name,
                        value=(
                            f"Server ID: {server.id}\n"
                            f"Role Mappings: {mapping_count}\n"
                            f"Use `!disrolesync roles {server.id}` to manage role mappings"
                        ),
                        inline=False
                    )
                else:
                    embed.add_field(
                        name=f"Unknown Server ({server_id})",
                        value="The bot is no longer in this server or the server no longer exists.",
                        inline=False
                    )
        

        pending_requests = self.role_sync_manager.get_pending_server_link_requests(guild.id)
        if pending_requests:
            embed.add_field(
                name="⚠️ Pending Server Link Requests",
                value=f"There are {len(pending_requests)} servers requesting to link with this server.\n"
                      f"Use `!disrolesync serverrequests` to manage these requests.",
                inline=False
            )
        
        embed.set_footer(text="Use the buttons below to manage server links | ZygnalBot by TheHolyOneZ")
        return embed
    
    async def find_notification_channel(self, guild):
        

        everyone_role = guild.default_role
        for channel in guild.text_channels:
            if (channel.overwrites_for(everyone_role).read_messages is False and 
                    channel.permissions_for(guild.me).send_messages):
                return channel
        

        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                return channel
        
        return None
    
    async def sync_user_roles(self, user_id, source_guild_id, target_guild_id, roles_data=None):
        

        source_guild = self.bot.get_guild(source_guild_id)
        target_guild = self.bot.get_guild(target_guild_id)
        
        if not source_guild or not target_guild:
            return False, "One or both servers not found"
        

        source_member = source_guild.get_member(user_id)
        target_member = target_guild.get_member(user_id)
        
        if not source_member or not target_member:
            return False, "User not found in one or both servers"
        

        if roles_data:
            roles_to_sync = []
            for role_data in roles_data:
                role_id = int(role_data.get('id'))
                role = discord.utils.get(source_guild.roles, id=role_id)
                if role:
                    roles_to_sync.append(role)
        else:

            roles_to_sync = source_member.roles
        

        roles_to_add = []
        

        for role in roles_to_sync:
            if role.is_default():
                continue  # Skip @everyone role
            
            mapped_role_id = self.role_sync_manager.get_mapped_role(
                source_guild.id, role.id, target_guild.id
            )
            
            if mapped_role_id:
                target_role = discord.utils.get(target_guild.roles, id=int(mapped_role_id))
                if target_role and target_role not in target_member.roles:
                    roles_to_add.append(target_role)
        

        if roles_to_add:
            try:
                await target_member.add_roles(*roles_to_add, reason="DisRoleSync - Role synchronization")
                return True, f"Added {len(roles_to_add)} roles"
            except discord.Forbidden:
                return False, "Bot doesn't have permission to add roles"
            except Exception as e:
                return False, f"Error adding roles: {str(e)}"
        
        return True, "No new roles to add"
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        
        guild = member.guild
        settings = self.role_sync_manager.get_sync_settings(guild.id)
        

        if not settings.get('auto_sync_on_join', True):
            return
        

        linked_servers = []
        

        for server_id_str in self.role_sync_manager.server_links:
            if str(guild.id) in self.role_sync_manager.server_links[server_id_str]:
                linked_servers.append(int(server_id_str))
        

        linked_servers.extend([int(s) for s in self.role_sync_manager.get_linked_servers(guild.id)])
        

        linked_servers = list(set(linked_servers))
        
        for source_guild_id in linked_servers:
            source_guild = self.bot.get_guild(source_guild_id)
            if not source_guild:
                continue
            

            source_member = source_guild.get_member(member.id)
            if not source_member:
                continue
            

            roles_to_sync = []
            for role in source_member.roles:
                if not role.is_default():  # Skip @everyone
                    mapped_role_id = self.role_sync_manager.get_mapped_role(
                        source_guild.id, role.id, guild.id
                    )
                    if mapped_role_id:
                        roles_to_sync.append({
                            'id': str(role.id),
                            'name': role.name
                        })
            
            if not roles_to_sync:
                continue
            

            if settings.get('require_approval', True):

                approval_id = self.role_sync_manager.create_approval(
                    source_guild.id, guild.id, member.id, roles_to_sync
                )
                

                notification_channel_id = settings.get('notification_channel')
                notification_channel = None
                
                if notification_channel_id:
                    notification_channel = guild.get_channel(int(notification_channel_id))
                

                if not notification_channel:
                    notification_channel = await self.find_notification_channel(guild)
                
                if notification_channel:
                    embed = discord.Embed(
                        title="DisRoleSync - New Approval Request",
                        description=f"A new role sync request needs approval",
                        color=EMBED_COLOR_WARNING
                    )
                    
                    embed.add_field(
                        name="User",
                        value=f"{member.mention} ({member.name})",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="Source Server",
                        value=source_guild.name,
                        inline=True
                    )
                    
                    roles_text = "\n".join([f"• {role['name']}" for role in roles_to_sync])
                    embed.add_field(
                        name="Roles to Sync",
                        value=roles_text or "None",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="Approval ID",
                        value=approval_id,
                        inline=False
                    )
                    
                    if not settings.get('notification_channel'):
                        embed.add_field(
                            name="Note",
                            value="This message was sent to this channel because no notification channel is configured. "
                                  "Use `!disrolesync settings` to set a notification channel.",
                            inline=False
                        )
                    
                    embed.set_footer(text="Use !disrolesync approvals to manage requests")
                    
                    await notification_channel.send(embed=embed)
            else:

                await self.sync_user_roles(member.id, source_guild.id, guild.id, roles_to_sync)
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        

        if before.roles == after.roles:
            return
        
        guild = after.guild
        settings = self.role_sync_manager.get_sync_settings(guild.id)
        

        linked_servers = self.role_sync_manager.get_linked_servers(guild.id)
        if not linked_servers:
            return
        

        added_roles = [role for role in after.roles if role not in before.roles]
        removed_roles = [role for role in before.roles if role not in after.roles]
        
        for target_guild_id_str in linked_servers:
            target_guild = self.bot.get_guild(int(target_guild_id_str))
            if not target_guild:
                continue
            
            target_member = target_guild.get_member(after.id)
            if not target_member:
                continue
            

            for role in added_roles:
                if role.is_default():
                    continue  # Skip @everyone
                
                mapped_role_id = self.role_sync_manager.get_mapped_role(
                    guild.id, role.id, int(target_guild_id_str)
                )
                
                if mapped_role_id:
                    target_role = discord.utils.get(target_guild.roles, id=int(mapped_role_id))
                    if target_role and target_role not in target_member.roles:
                        try:
                            await target_member.add_roles(target_role, reason="DisRoleSync - Role synchronization")
                        except:
                            pass  # Silently fail if we can't add the role
            

            if settings.get('sync_removals', True):
                for role in removed_roles:
                    if role.is_default():
                        continue  # Skip @everyone
                    
                    mapped_role_id = self.role_sync_manager.get_mapped_role(
                        guild.id, role.id, int(target_guild_id_str)
                    )
                    
                    if mapped_role_id:
                        target_role = discord.utils.get(target_guild.roles, id=int(mapped_role_id))
                        if target_role and target_role in target_member.roles:
                            try:
                                await target_member.remove_roles(target_role, reason="DisRoleSync - Role synchronization")
                            except:
                                pass  # Silently fail if we can't remove the role
    
    @commands.group(name="disrolesync", invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    async def disrolesync(self, ctx):
        
        embed = discord.Embed(
            title="DisRoleSync - Cross-Server Role Synchronization",
            description="Automatically sync roles between linked Discord servers.",
            color=EMBED_COLOR_NEUTRAL
        )
        
        embed.add_field(
            name="Commands",
            value=(
                "• `!disrolesync servers` - Manage server links\n"
                "• `!disrolesync roles <server_id>` - Manage role mappings\n"
                "• `!disrolesync approvals` - Manage pending role sync approvals\n"
                "• `!disrolesync serverrequests` - Manage pending server link requests\n"
                "• `!disrolesync settings` - Configure sync settings\n"
                "• `!disrolesync sync <user>` - Manually sync roles for a user"
            ),
            inline=False
        )
        
        embed.add_field(
            name="How It Works",
            value=(
                "1. Link two or more servers together\n"
                "2. Create role mappings between servers\n"
                "3. When users get roles in one server, they automatically get the mapped roles in linked servers"
            ),
            inline=False
        )
        
        embed.set_footer(text="ZygnalBot by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @disrolesync.command(name="servers")
    @commands.has_permissions(administrator=True)
    async def manage_servers(self, ctx):
        
        embed = await self.create_server_links_embed(ctx.guild)
        view = ServerLinkView(self, ctx.guild)
        await ctx.send(embed=embed, view=view)
    
    @disrolesync.command(name="roles")
    @commands.has_permissions(administrator=True)
    async def manage_roles(self, ctx, target_guild_id: int = None):
        
        if not target_guild_id:

            linked_servers = self.role_sync_manager.get_linked_servers(ctx.guild.id)
            
            if not linked_servers:
                embed = discord.Embed(
                    title="DisRoleSync - No Linked Servers",
                    description="This server is not linked to any other servers. Use `!disrolesync servers` to create links first.",
                    color=EMBED_COLOR_ERROR
                )
                embed.set_footer(text="ZygnalBot by TheHolyOneZ")
                await ctx.send(embed=embed)
                return
            

            options = []
            for server_id in linked_servers:
                server = self.bot.get_guild(int(server_id))
                server_name = server.name if server else f"Unknown Server ({server_id})"
                
                options.append(
                    discord.SelectOption(
                        label=server_name,
                        value=server_id,
                        description=f"Manage role mappings with this server"
                    )
                )
            

            select = discord.ui.Select(
                placeholder="Select a server to manage role mappings",
                options=options
            )
            
            async def select_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("This menu is not for you.", ephemeral=True)
                    return
                
                target_guild_id = int(select.values[0])
                target_guild = self.bot.get_guild(target_guild_id)
                
                if not target_guild:
                    await interaction.response.send_message(
                        "❌ I can no longer access that server. The bot may have been removed.",
                        ephemeral=True
                    )
                    return
                

                view = RoleMappingView(self, ctx.guild, target_guild)
                embed = await view.create_mapping_embed()
                
                await interaction.response.send_message(embed=embed, view=view)
            
            select.callback = select_callback
            

            view = discord.ui.View(timeout=60)
            view.add_item(select)
            
            await ctx.send(
                "Select a server to manage role mappings:",
                view=view
            )
            return
        

        target_guild = self.bot.get_guild(target_guild_id)
        if not target_guild:
            await ctx.send(f"❌ I can't find a server with ID {target_guild_id}. Make sure the bot is in that server.")
            return
        

        linked_servers = self.role_sync_manager.get_linked_servers(ctx.guild.id)
        if str(target_guild_id) not in linked_servers:
            await ctx.send(f"❌ This server is not linked with {target_guild.name}. Use `!disrolesync servers` to create a link first.")
            return
        

        view = RoleMappingView(self, ctx.guild, target_guild)
        embed = await view.create_mapping_embed()
        
        await ctx.send(embed=embed, view=view)
    
    @disrolesync.command(name="approvals")
    @commands.has_permissions(administrator=True)
    async def manage_approvals(self, ctx):
        
        view = ApprovalView(self, ctx.guild)
        embed = await view.create_approvals_embed()
        
        await ctx.send(embed=embed, view=view)
    
    @disrolesync.command(name="serverrequests")
    @commands.has_permissions(administrator=True)
    async def manage_server_requests(self, ctx):
        
        view = ServerRequestView(self, ctx.guild)
        embed = await view.create_requests_embed()
        
        await ctx.send(embed=embed, view=view)
    
    @disrolesync.command(name="settings")
    @commands.has_permissions(administrator=True)
    async def manage_settings(self, ctx):
        
        settings = self.role_sync_manager.get_sync_settings(ctx.guild.id)
        view = SyncSettingsView(self, ctx.guild, settings)
        embed = view.create_settings_embed()
        
        await ctx.send(embed=embed, view=view)
    
    @disrolesync.command(name="sync")
    @commands.has_permissions(manage_roles=True)
    async def manual_sync(self, ctx, member: discord.Member = None, target_guild_id: int = None):
        
        if not member:
            member = ctx.author
        
        if not target_guild_id:

            linked_servers = self.role_sync_manager.get_linked_servers(ctx.guild.id)
            
            if not linked_servers:
                await ctx.send("❌ This server is not linked to any other servers. Use `!disrolesync servers` to create links first.")
                return
            

            options = []
            for server_id in linked_servers:
                server = self.bot.get_guild(int(server_id))
                if not server:
                    continue
                

                if not server.get_member(member.id):
                    continue
                
                options.append(
                    discord.SelectOption(
                        label=server.name,
                        value=server_id,
                        description=f"Sync roles with this server"
                    )
                )
            
            if not options:
                await ctx.send(f"❌ {member.mention} is not in any linked servers or there are no valid linked servers.")
                return
            

            select = discord.ui.Select(
                placeholder="Select a server to sync roles with",
                options=options
            )
            
            async def select_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("This menu is not for you.", ephemeral=True)
                    return
                
                target_guild_id = int(select.values[0])
                target_guild = self.bot.get_guild(target_guild_id)
                
                if not target_guild:
                    await interaction.response.send_message(
                        "❌ I can no longer access that server.",
                        ephemeral=True
                    )
                    return
                

                direction_view = discord.ui.View(timeout=60)
                
                async def to_target_callback(direction_interaction):

                    success, message = await self.sync_user_roles(
                        member.id, ctx.guild.id, target_guild_id
                    )
                    
                    if success:
                        await direction_interaction.response.send_message(
                            f"✅ Successfully synced roles for {member.mention} from {ctx.guild.name} to {target_guild.name}!",
                            ephemeral=True
                        )
                    else:
                        await direction_interaction.response.send_message(
                            f"❌ Failed to sync roles: {message}",
                            ephemeral=True
                        )
                
                async def from_target_callback(direction_interaction):

                    success, message = await self.sync_user_roles(
                        member.id, target_guild_id, ctx.guild.id
                    )
                    
                    if success:
                        await direction_interaction.response.send_message(
                            f"✅ Successfully synced roles for {member.mention} from {target_guild.name} to {ctx.guild.name}!",
                            ephemeral=True
                        )
                    else:
                        await direction_interaction.response.send_message(
                            f"❌ Failed to sync roles: {message}",
                            ephemeral=True
                        )
                
                to_target_button = discord.ui.Button(
                    label=f"From {ctx.guild.name} to {target_guild.name}",
                    style=discord.ButtonStyle.primary
                )
                to_target_button.callback = to_target_callback
                
                from_target_button = discord.ui.Button(
                    label=f"From {target_guild.name} to {ctx.guild.name}",
                    style=discord.ButtonStyle.secondary
                )
                from_target_button.callback = from_target_callback
                
                direction_view.add_item(to_target_button)
                direction_view.add_item(from_target_button)
                
                await interaction.response.send_message(
                    f"Select sync direction for {member.mention}:",
                    view=direction_view,
                    ephemeral=True
                )
            
            select.callback = select_callback
            

            view = discord.ui.View(timeout=60)
            view.add_item(select)
            
            await ctx.send(
                f"Select a server to sync roles with for {member.mention}:",
                view=view
            )
            return
        

        target_guild = self.bot.get_guild(target_guild_id)
        if not target_guild:
            await ctx.send(f"❌ I can't find a server with ID {target_guild_id}. Make sure the bot is in that server.")
            return
        

        linked_servers = self.role_sync_manager.get_linked_servers(ctx.guild.id)
        if str(target_guild_id) not in linked_servers:
            await ctx.send(f"❌ This server is not linked with {target_guild.name}. Use `!disrolesync servers` to create a link first.")
            return
        

        target_member = target_guild.get_member(member.id)
        if not target_member:
            await ctx.send(f"❌ {member.mention} is not in {target_guild.name}.")
            return
        

        success, message = await self.sync_user_roles(
            member.id, ctx.guild.id, target_guild_id
        )
        
        if success:
            await ctx.send(f"✅ Successfully synced roles for {member.mention} to {target_guild.name}!")
        else:
            await ctx.send(f"❌ Failed to sync roles: {message}")


def setup(bot):
    
    cog = DisRoleSync(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog





