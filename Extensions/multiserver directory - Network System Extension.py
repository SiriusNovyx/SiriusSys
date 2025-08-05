import discord
from discord.ext import commands
import asyncio
from typing import Dict, List, Optional, Union, Set
import json
import os
import datetime
from discord import app_commands

class ServerNode:
    def __init__(self, server_id: int, name: str, description: str = "", tags: List[str] = None, 
                 member_count: int = 0, invite_link: str = "", category: str = "General"):
        self.server_id = server_id
        self.name = name
        self.description = description
        self.tags = tags or []
        self.member_count = member_count
        self.invite_link = invite_link
        self.category = category
        self.connections = []
        self.visible_channels = []
        self.network_purpose = ""
        self.icon_url = ""
        self.banner_url = ""
        self.features = []
        self.owner_name = ""
        self.created_at = datetime.datetime.now()

class ServerNetwork:
    def __init__(self, name: str, owner_id: int, public: bool = True, description: str = "", purpose: str = "", 
                 category: str = "General", tags: List[str] = None):
        self.name = name
        self.owner_id = owner_id
        self.public = public
        self.servers = {}
        self.created_at = datetime.datetime.now()
        self.description = description
        self.purpose = purpose
        self.category = category
        self.tags = tags or []
        self.icon_url = ""
        self.banner_url = ""
        self.default_role_id = None
        self.featured_servers = []
    
    def add_server(self, server: ServerNode):
        self.servers[server.server_id] = server
    
    def remove_server(self, server_id: int):
        if server_id in self.servers:
            for node in self.servers.values():
                if server_id in node.connections:
                    node.connections.remove(server_id)
            del self.servers[server_id]
    
    def add_connection(self, server_id1: int, server_id2: int):
        if server_id1 in self.servers and server_id2 in self.servers:
            if server_id2 not in self.servers[server_id1].connections:
                self.servers[server_id1].connections.append(server_id2)
            if server_id1 not in self.servers[server_id2].connections:
                self.servers[server_id2].connections.append(server_id1)
    
    def remove_connection(self, server_id1: int, server_id2: int):
        if server_id1 in self.servers and server_id2 in self.servers:
            if server_id2 in self.servers[server_id1].connections:
                self.servers[server_id1].connections.remove(server_id2)
            if server_id1 in self.servers[server_id2].connections:
                self.servers[server_id2].connections.remove(server_id1)
    
    def set_featured_servers(self, server_ids: List[int]):
        self.featured_servers = [sid for sid in server_ids if sid in self.servers]

class ServerDirectoryView(discord.ui.View):
    def __init__(self, cog, network: ServerNetwork, user: discord.Member, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.network = network
        self.user = user
        self.current_server_id = None
        self.page = 0
        self.servers_per_page = 5
        self.filter_category = None
        self.filter_tag = None
        
    @discord.ui.button(label="Browse Servers", style=discord.ButtonStyle.primary, emoji="🔍")
    async def browse_servers(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        await self.show_server_list(interaction)
    
    @discord.ui.button(label="View Map", style=discord.ButtonStyle.secondary, emoji="🗺️")
    async def view_map(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_network_map(interaction)
    
    @discord.ui.button(label="Filter", style=discord.ButtonStyle.secondary, emoji="🏷️")
    async def filter_servers(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_filter_options(interaction)
    
    @discord.ui.button(label="Featured", style=discord.ButtonStyle.success, emoji="⭐")
    async def featured_servers(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_featured_servers(interaction)
    
    @discord.ui.button(label="Info", style=discord.ButtonStyle.secondary, emoji="ℹ️")
    async def network_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_network_info(interaction)
    
    async def show_server_list(self, interaction: discord.Interaction):
        servers = list(self.network.servers.values())
        
        if self.filter_category:
            servers = [s for s in servers if s.category == self.filter_category]
        if self.filter_tag:
            servers = [s for s in servers if self.filter_tag in s.tags]
        
        total_pages = max(1, (len(servers) + self.servers_per_page - 1) // self.servers_per_page)
        if self.page >= total_pages:
            self.page = 0
        
        start_idx = self.page * self.servers_per_page
        end_idx = min(start_idx + self.servers_per_page, len(servers))
        current_servers = servers[start_idx:end_idx]
        
        embed = discord.Embed(
            title=f"Server Directory - {self.network.name}",
            description=f"{self.network.description}\n\n**Purpose:** {self.network.purpose}\n\nBrowse through connected servers in this network.\n\nPage {self.page + 1}/{total_pages}",
            color=discord.Color.blue()
        )
        
        if self.network.icon_url:
            embed.set_thumbnail(url=self.network.icon_url)
        
        if not current_servers:
            embed.add_field(name="No Servers Found", value="No servers match your current filters.")
        
        for server in current_servers:
            value = f"{server.description[:100]}...\n" if len(server.description) > 100 else f"{server.description}\n"
            value += f"**Members:** {server.member_count} | **Category:** {server.category}\n"
            value += f"**Tags:** {', '.join(server.tags)}\n"
            if server.owner_name:
                value += f"**Owner:** {server.owner_name}\n"
            
            embed.add_field(
                name=f"{server.name}",
                value=value,
                inline=False
            )
        
        view = ServerListView(self, servers, total_pages)
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def show_network_map(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"Network Map - {self.network.name}",
            description=f"{self.network.description}\n\n**Purpose:** {self.network.purpose}\n\nVisual representation of connected servers",
            color=discord.Color.green()
        )
        
        if self.network.icon_url:
            embed.set_thumbnail(url=self.network.icon_url)
        
        map_text = ""
        for server_id, server in self.network.servers.items():
            map_text += f"**{server.name}** connects to:\n"
            for connection_id in server.connections:
                if connection_id in self.network.servers:
                    map_text += f"└─ {self.network.servers[connection_id].name}\n"
            map_text += "\n"
        
        if not map_text:
            map_text = "No connections found in this network."
        
        embed.description += f"\n\n{map_text}"
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def show_filter_options(self, interaction: discord.Interaction):
        categories = set()
        tags = set()
        
        for server in self.network.servers.values():
            categories.add(server.category)
            for tag in server.tags:
                tags.add(tag)
        
        embed = discord.Embed(
            title="Filter Servers",
            description="Select a category or tag to filter the server list",
            color=discord.Color.gold()
        )
        
        view = FilterView(self, list(categories), list(tags))
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def show_featured_servers(self, interaction: discord.Interaction):
        featured_servers = []
        for server_id in self.network.featured_servers:
            if server_id in self.network.servers:
                featured_servers.append(self.network.servers[server_id])
        
        if not featured_servers:
            featured_servers = list(self.network.servers.values())[:5]
        
        embed = discord.Embed(
            title=f"⭐ Featured Servers - {self.network.name}",
            description=f"{self.network.description}\n\nHighlighted servers in this network:",
            color=discord.Color.gold()
        )
        
        if self.network.icon_url:
            embed.set_thumbnail(url=self.network.icon_url)
        
        if not featured_servers:
            embed.add_field(name="No Servers Found", value="No featured servers in this network.")
        
        for server in featured_servers:
            value = f"{server.description[:100]}...\n" if len(server.description) > 100 else f"{server.description}\n"
            value += f"**Members:** {server.member_count} | **Category:** {server.category}\n"
            value += f"**Tags:** {', '.join(server.tags)}\n"
            
            embed.add_field(
                name=f"{server.name}",
                value=value,
                inline=False
            )
        
        view = FeaturedServersView(self, featured_servers)
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def show_network_info(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"Network Information - {self.network.name}",
            description=f"{self.network.description}",
            color=discord.Color.purple()
        )
        
        if self.network.icon_url:
            embed.set_thumbnail(url=self.network.icon_url)
        
        if self.network.banner_url:
            embed.set_image(url=self.network.banner_url)
        
        owner_name = "Unknown"
        try:
            owner = await self.cog.bot.fetch_user(self.network.owner_id)
            owner_name = str(owner)
        except:
            pass
        
        embed.add_field(name="Owner", value=owner_name, inline=True)
        embed.add_field(name="Visibility", value="Public" if self.network.public else "Private", inline=True)
        embed.add_field(name="Created", value=self.network.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="Servers", value=str(len(self.network.servers)), inline=True)
        
        total_connections = sum(len(server.connections) for server in self.network.servers.values()) // 2
        embed.add_field(name="Connections", value=str(total_connections), inline=True)
        
        embed.add_field(name="Category", value=self.network.category, inline=True)
        
        if self.network.tags:
            embed.add_field(name="Tags", value=", ".join(self.network.tags), inline=False)
        
        if self.network.purpose:
            embed.add_field(name="Purpose", value=self.network.purpose, inline=False)
        
        await interaction.response.edit_message(embed=embed, view=self)

class ServerListView(discord.ui.View):
    def __init__(self, parent_view, servers, total_pages):
        super().__init__(timeout=180)
        self.parent_view = parent_view
        self.servers = servers
        self.total_pages = total_pages
        
        self.add_item(discord.ui.Button(label="◀️ Previous", style=discord.ButtonStyle.secondary, 
                                        custom_id="prev_page", disabled=parent_view.page == 0))
        self.add_item(discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.secondary, 
                                        custom_id="next_page", disabled=parent_view.page >= total_pages - 1))
        
        start_idx = parent_view.page * parent_view.servers_per_page
        end_idx = min(start_idx + parent_view.servers_per_page, len(servers))
        
        for i in range(start_idx, end_idx):
            self.add_item(discord.ui.Button(label=f"View {servers[i].name}", 
                                           style=discord.ButtonStyle.primary,
                                           custom_id=f"server_{servers[i].server_id}"))
        
        self.add_item(discord.ui.Button(label="Back", style=discord.ButtonStyle.danger, custom_id="back"))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data["custom_id"] == "prev_page":
            self.parent_view.page -= 1
            await self.parent_view.show_server_list(interaction)
        elif interaction.data["custom_id"] == "next_page":
            self.parent_view.page += 1
            await self.parent_view.show_server_list(interaction)
        elif interaction.data["custom_id"] == "back":
            await interaction.response.edit_message(view=self.parent_view)
        elif interaction.data["custom_id"].startswith("server_"):
            server_id = int(interaction.data["custom_id"].split("_")[1])
            await self.show_server_details(interaction, server_id)
        
        return True
    
    async def show_server_details(self, interaction: discord.Interaction, server_id: int):
        server = None
        for s in self.servers:
            if s.server_id == server_id:
                server = s
                break
        
        if not server:
            await interaction.response.send_message("Server not found", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"Server Details - {server.name}",
            description=server.description,
            color=discord.Color.blue()
        )
        
        if server.icon_url:
            embed.set_thumbnail(url=server.icon_url)
        
        if server.banner_url:
            embed.set_image(url=server.banner_url)
        
        embed.add_field(name="Members", value=str(server.member_count), inline=True)
        embed.add_field(name="Category", value=server.category, inline=True)
        embed.add_field(name="Tags", value=", ".join(server.tags) or "None", inline=False)
        
        if server.owner_name:
            embed.add_field(name="Owner", value=server.owner_name, inline=True)
        
        if server.created_at:
            embed.add_field(name="Created", value=server.created_at.strftime("%Y-%m-%d"), inline=True)
        
        if server.features:
            embed.add_field(name="Features", value=", ".join(server.features), inline=False)
        
        connected_servers = []
        for conn_id in server.connections:
            for s in self.servers:
                if s.server_id == conn_id:
                    connected_servers.append(s.name)
        
        if connected_servers:
            embed.add_field(name="Connected To", value="\n".join(connected_servers), inline=False)
        else:
            embed.add_field(name="Connected To", value="No connections", inline=False)
        
        if server.network_purpose:
            embed.add_field(name="Purpose in Network", value=server.network_purpose, inline=False)
        
        view = ServerDetailView(self.parent_view, server)
        await interaction.response.edit_message(embed=embed, view=view)

class ServerDetailView(discord.ui.View):
    def __init__(self, parent_view, server):
        super().__init__(timeout=180)
        self.parent_view = parent_view
        self.server = server
        
        if server.invite_link:
            self.add_item(discord.ui.Button(label="Join Server", style=discord.ButtonStyle.success, 
                                           url=server.invite_link))
        
        self.add_item(discord.ui.Button(label="View Channels", style=discord.ButtonStyle.primary,
                                       custom_id="view_channels"))
        
        self.add_item(discord.ui.Button(label="Back to List", style=discord.ButtonStyle.secondary, 
                                       custom_id="back_to_list"))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data["custom_id"] == "back_to_list":
            await self.parent_view.show_server_list(interaction)
        elif interaction.data["custom_id"] == "view_channels":
            await self.show_server_channels(interaction)
        return True
    
    async def show_server_channels(self, interaction: discord.Interaction):
        if not self.server.visible_channels:
            await interaction.response.send_message("No channel information available for this server.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"Channel Map - {self.server.name}",
            description="Channels accessible in this server:",
            color=discord.Color.green()
        )
        
        if self.server.icon_url:
            embed.set_thumbnail(url=self.server.icon_url)
        
        channel_map = ""
        for channel_type, channel_name in self.server.visible_channels:
            if channel_type == "category":
                channel_map += f"**{channel_name}**\n"
            elif channel_type == "text":
                channel_map += f"├─ 📝 {channel_name}\n"
            elif channel_type == "voice":
                channel_map += f"├─ 🔊 {channel_name}\n"
            elif channel_type == "forum":
                channel_map += f"├─ 📋 {channel_name}\n"
            elif channel_type == "announcement":
                channel_map += f"├─ 📢 {channel_name}\n"
            else:
                channel_map += f"├─ {channel_name}\n"
        
        embed.description += f"\n```\n{channel_map}\n```"
        
        back_button = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary, custom_id="back")
        
        view = discord.ui.View()
        view.add_item(back_button)
        
        async def back_callback(interaction):
            embed = discord.Embed(
                title=f"Server Details - {self.server.name}",
                description=self.server.description,
                color=discord.Color.blue()
            )
            
            if self.server.icon_url:
                embed.set_thumbnail(url=self.server.icon_url)
            
            await interaction.response.edit_message(embed=embed, view=self)
        
        back_button.callback = back_callback
        
        await interaction.response.edit_message(embed=embed, view=view)

class FeaturedServersView(discord.ui.View):
    def __init__(self, parent_view, servers):
        super().__init__(timeout=180)
        self.parent_view = parent_view
        self.servers = servers
        
        for i, server in enumerate(servers[:5]):
            self.add_item(discord.ui.Button(label=f"View {server.name}", 
                                           style=discord.ButtonStyle.primary,
                                           custom_id=f"server_{server.server_id}"))
        
        self.add_item(discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary, custom_id="back"))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data["custom_id"] == "back":
            await interaction.response.edit_message(view=self.parent_view)
        elif interaction.data["custom_id"].startswith("server_"):
            server_id = int(interaction.data["custom_id"].split("_")[1])
            
            server = None
            for s in self.servers:
                if s.server_id == server_id:
                    server = s
                    break
            
            if not server:
                await interaction.response.send_message("Server not found", ephemeral=True)
                return True
            
            embed = discord.Embed(
                title=f"Server Details - {server.name}",
                description=server.description,
                color=discord.Color.blue()
            )
            
            if server.icon_url:
                embed.set_thumbnail(url=server.icon_url)
            
            embed.add_field(name="Members", value=str(server.member_count), inline=True)
            embed.add_field(name="Category", value=server.category, inline=True)
            embed.add_field(name="Tags", value=", ".join(server.tags) or "None", inline=False)
            
            view = ServerDetailView(self.parent_view, server)
            await interaction.response.edit_message(embed=embed, view=view)
        
        return True

class FilterView(discord.ui.View):
    def __init__(self, parent_view, categories, tags):
        super().__init__(timeout=180)
        self.parent_view = parent_view
        
        self.add_item(CategorySelect(parent_view, categories))
        self.add_item(TagSelect(parent_view, tags))
        self.add_item(discord.ui.Button(label="Clear Filters", style=discord.ButtonStyle.danger, 
                                       custom_id="clear_filters"))
        self.add_item(discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary, 
                                       custom_id="back"))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data["custom_id"] == "clear_filters":
            self.parent_view.filter_category = None
            self.parent_view.filter_tag = None
            await self.parent_view.show_server_list(interaction)
        elif interaction.data["custom_id"] == "back":
            await interaction.response.edit_message(view=self.parent_view)
        return True

class CategorySelect(discord.ui.Select):
    def __init__(self, parent_view, categories):
        options = [discord.SelectOption(label="All Categories", value="all")]
        options.extend([discord.SelectOption(label=category) for category in categories])
        
        super().__init__(
            placeholder="Filter by category...",
            min_values=1,
            max_values=1,
            options=options
        )
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "all":
            self.parent_view.filter_category = None
        else:
            self.parent_view.filter_category = self.values[0]
        
        await self.parent_view.show_server_list(interaction)

class TagSelect(discord.ui.Select):
    def __init__(self, parent_view, tags):
        options = [discord.SelectOption(label="All Tags", value="all")]
        options.extend([discord.SelectOption(label=tag) for tag in tags])
        
        super().__init__(
            placeholder="Filter by tag...",
            min_values=1,
            max_values=1,
            options=options
        )
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "all":
            self.parent_view.filter_tag = None
        else:
            self.parent_view.filter_tag = self.values[0]
        
        await self.parent_view.show_server_list(interaction)

class CreateNetworkModal(discord.ui.Modal, title="Create Server Network"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        
        self.network_name = discord.ui.TextInput(
            label="Network Name",
            placeholder="Enter a name for your server network",
            required=True,
            max_length=100
        )
        
        self.network_description = discord.ui.TextInput(
            label="Description",
            placeholder="Describe what this network is about",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        
        self.network_purpose = discord.ui.TextInput(
            label="Purpose",
            placeholder="What is the purpose of this network?",
            required=True,
            max_length=200
        )
        
        self.network_category = discord.ui.TextInput(
            label="Category",
            placeholder="e.g. Gaming, Education, Community",
            required=True,
            max_length=50
        )
        
        self.network_public = discord.ui.TextInput(
            label="Public Network? (yes/no)",
            placeholder="Type 'yes' for public, 'no' for private",
            required=True,
            max_length=3
        )
        
        self.add_item(self.network_name)
        self.add_item(self.network_description)
        self.add_item(self.network_purpose)
        self.add_item(self.network_category)
        self.add_item(self.network_public)
    
    async def on_submit(self, interaction: discord.Interaction):
        is_public = self.network_public.value.lower() in ["yes", "y", "true"]
        
        network = ServerNetwork(
            name=self.network_name.value,
            owner_id=interaction.user.id,
            public=is_public,
            description=self.network_description.value,
            purpose=self.network_purpose.value,
            category=self.network_category.value
        )
        
        server = interaction.guild
        
        try:
            invite = await self.get_or_create_invite(server)
            invite_link = invite.url if invite else ""
        except:
            invite_link = ""
        
        server_node = ServerNode(
            server_id=server.id,
            name=server.name,
            description="This server",
            member_count=server.member_count,
            invite_link=invite_link,
            category=self.network_category.value
        )
        
        server_node.icon_url = str(server.icon.url) if server.icon else ""
        server_node.banner_url = str(server.banner.url) if hasattr(server, 'banner') and server.banner else ""
        server_node.owner_name = str(server.owner) if server.owner else "Unknown"
        server_node.created_at = server.created_at
        
        network.add_server(server_node)
        network.icon_url = server_node.icon_url
        
        await self.cog.save_network(network)
        
        embed = discord.Embed(
            title="Server Network Created",
            description=f"Your network '{network.name}' has been created successfully!",
            color=discord.Color.green()
        )
        
        if network.icon_url:
            embed.set_thumbnail(url=network.icon_url)
        
        embed.add_field(name="Description", value=network.description, inline=False)
        embed.add_field(name="Purpose", value=network.purpose, inline=False)
        embed.add_field(name="Category", value=network.category, inline=True)
        embed.add_field(name="Visibility", value="Public" if network.public else "Private", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def get_or_create_invite(self, guild):
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).create_instant_invite:
                try:
                    invites = await channel.invites()
                    if invites:
                        return invites[0]
                    else:
                        return await channel.create_invite(max_age=0, max_uses=0, unique=False)
                except:
                    continue
        return None

class AddServerModal(discord.ui.Modal, title="Add Server to Network"):
    def __init__(self, cog, network):
        super().__init__()
        self.cog = cog
        self.network = network
        
        self.server_name = discord.ui.TextInput(
            label="Server Name",
            placeholder="Enter the server name",
            required=True,
            max_length=100
        )
        
        self.server_description = discord.ui.TextInput(
            label="Description",
            placeholder="Brief description of the server",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        
        self.server_category = discord.ui.TextInput(
            label="Category",
            placeholder="e.g. Gaming, Education, Community",
            required=True,
            max_length=50
        )
        
        self.server_tags = discord.ui.TextInput(
            label="Tags (comma separated)",
            placeholder="e.g. gaming, minecraft, roleplay",
            required=False,
            max_length=100
        )
        
        self.server_purpose = discord.ui.TextInput(
            label="Purpose in Network",
            placeholder="What role does this server play in the network?",
            required=False,
            max_length=200
        )
        
        self.add_item(self.server_name)
        self.add_item(self.server_description)
        self.add_item(self.server_category)
        self.add_item(self.server_tags)
        self.add_item(self.server_purpose)

    async def on_submit(self, interaction: discord.Interaction):
        tags = [tag.strip() for tag in self.server_tags.value.split(",") if tag.strip()]
        
        try:
            invite = await self.get_or_create_invite(interaction.guild)
            invite_link = invite.url if invite else ""
        except:
            invite_link = ""
        
        server_node = ServerNode(
            server_id=interaction.guild.id,
            name=self.server_name.value,
            description=self.server_description.value,
            tags=tags,
            member_count=interaction.guild.member_count,
            invite_link=invite_link,
            category=self.server_category.value
        )
        
        server_node.network_purpose = self.server_purpose.value
        server_node.icon_url = str(interaction.guild.icon.url) if interaction.guild.icon else ""
        server_node.banner_url = str(interaction.guild.banner.url) if hasattr(interaction.guild, 'banner') and interaction.guild.banner else ""
        server_node.owner_name = str(interaction.guild.owner) if interaction.guild.owner else "Unknown"
        server_node.created_at = interaction.guild.created_at
        
        for guild in self.cog.bot.guilds:
            if guild.name.lower() == self.server_name.value.lower():
                server_node.server_id = guild.id
                server_node.member_count = guild.member_count
                server_node.icon_url = str(guild.icon.url) if guild.icon else ""
                server_node.banner_url = str(guild.banner.url) if hasattr(guild, 'banner') and guild.banner else ""
                server_node.owner_name = str(guild.owner) if guild.owner else "Unknown"
                server_node.created_at = guild.created_at
                
                try:
                    invite = await self.get_or_create_invite(guild)
                    server_node.invite_link = invite.url if invite else ""
                except:
                    pass
                
                break
        
        self.network.add_server(server_node)
        await self.cog.save_network(self.network)
        
        embed = discord.Embed(
            title="Server Added",
            description=f"'{server_node.name}' has been added to the network '{self.network.name}'!",
            color=discord.Color.green()
        )
        
        if server_node.icon_url:
            embed.set_thumbnail(url=server_node.icon_url)
        
        embed.add_field(name="Description", value=server_node.description, inline=False)
        embed.add_field(name="Category", value=server_node.category, inline=True)
        embed.add_field(name="Tags", value=", ".join(server_node.tags) or "None", inline=True)
        
        if server_node.network_purpose:
            embed.add_field(name="Purpose in Network", value=server_node.network_purpose, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def get_or_create_invite(self, guild):
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).create_instant_invite:
                try:
                    invites = await channel.invites()
                    if invites:
                        return invites[0]
                    else:
                        return await channel.create_invite(max_age=0, max_uses=0, unique=False)
                except:
                    continue
        return None

class ServerMapModal(discord.ui.Modal, title="Generate Server Map"):
    def __init__(self, cog, guild):
        super().__init__()
        self.cog = cog
        self.guild = guild
        
        self.role_name = discord.ui.TextInput(
            label="Role Name",
            placeholder="Enter a role name to view channels accessible to it",
            required=False,
            max_length=100
        )
        
        self.add_item(self.role_name)
    
    async def on_submit(self, interaction: discord.Interaction):
        role = None
        if self.role_name.value:
            for r in self.guild.roles:
                if r.name.lower() == self.role_name.value.lower():
                    role = r
                    break
        
        if not role and self.role_name.value:
            await interaction.response.send_message(f"Role '{self.role_name.value}' not found. Showing default view.", ephemeral=True)
            return
        
        embed, view = await self.cog.generate_server_map(self.guild, role)
        
        try:
            await interaction.response.send_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view)

class MultiServerDirectory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.networks = {}
        self.data_folder = "data/server_networks"
        self.ensure_data_folder()
        self.bot.loop.create_task(self.load_networks())
    
    def ensure_data_folder(self):
        os.makedirs(self.data_folder, exist_ok=True)
    
    async def load_networks(self):
        for filename in os.listdir(self.data_folder):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(self.data_folder, filename), 'r') as f:
                        data = json.load(f)
                    
                    network = ServerNetwork(
                        name=data["name"],
                        owner_id=data["owner_id"],
                        public=data["public"]
                    )
                    
                    if "description" in data:
                        network.description = data["description"]
                    if "purpose" in data:
                        network.purpose = data["purpose"]
                    if "category" in data:
                        network.category = data["category"]
                    if "tags" in data:
                        network.tags = data["tags"]
                    if "icon_url" in data:
                        network.icon_url = data["icon_url"]
                    if "banner_url" in data:
                        network.banner_url = data["banner_url"]
                    if "default_role_id" in data:
                        network.default_role_id = data["default_role_id"]
                    if "featured_servers" in data:
                        network.featured_servers = data["featured_servers"]
                    
                    network.created_at = datetime.datetime.fromisoformat(data["created_at"])
                    
                    for server_data in data["servers"]:
                        server = ServerNode(
                            server_id=server_data["id"],
                            name=server_data["name"],
                            description=server_data["description"],
                            tags=server_data.get("tags", []),
                            member_count=server_data["member_count"],
                            invite_link=server_data.get("invite_link", ""),
                            category=server_data.get("category", "General")
                        )
                        
                        server.connections = server_data.get("connections", [])
                        server.visible_channels = server_data.get("visible_channels", [])
                        server.network_purpose = server_data.get("network_purpose", "")
                        server.icon_url = server_data.get("icon_url", "")
                        server.banner_url = server_data.get("banner_url", "")
                        server.features = server_data.get("features", [])
                        server.owner_name = server_data.get("owner_name", "")
                        
                        if "created_at" in server_data:
                            server.created_at = datetime.datetime.fromisoformat(server_data["created_at"])
                        
                        network.add_server(server)
                    
                    network_id = int(filename.split(".")[0])
                    self.networks[network_id] = network
                except Exception as e:
                    print(f"Error loading network from {filename}: {e}")
    
    async def save_network(self, network: ServerNetwork):
        network_id = None
        for nid, net in self.networks.items():
            if net.name == network.name and net.owner_id == network.owner_id:
                network_id = nid
                break
        
        if network_id is None:
            network_id = int(datetime.datetime.now().timestamp())
            self.networks[network_id] = network
        
        data = {
            "name": network.name,
            "owner_id": network.owner_id,
            "public": network.public,
            "created_at": network.created_at.isoformat(),
            "description": network.description,
            "purpose": network.purpose,
            "category": network.category,
            "tags": network.tags,
            "icon_url": network.icon_url,
            "banner_url": network.banner_url,
            "default_role_id": network.default_role_id,
            "featured_servers": network.featured_servers,
            "servers": []
        }
        
        for server in network.servers.values():
            server_data = {
                "id": server.server_id,
                "name": server.name,
                "description": server.description,
                "tags": server.tags,
                "member_count": server.member_count,
                "invite_link": server.invite_link,
                "category": server.category,
                "connections": server.connections,
                "visible_channels": server.visible_channels,
                "network_purpose": server.network_purpose,
                "icon_url": server.icon_url,
                "banner_url": server.banner_url,
                "features": server.features,
                "owner_name": server.owner_name
            }
            
            if server.created_at:
                server_data["created_at"] = server.created_at.isoformat()
            
            data["servers"].append(server_data)
        
        with open(os.path.join(self.data_folder, f"{network_id}.json"), 'w') as f:
            json.dump(data, f, indent=4)


    
    @commands.hybrid_group(name="network", description="Server network commands")
    async def network(self, ctx):
        if ctx.invoked_subcommand is None:
            prefix = ctx.prefix
            embed = discord.Embed(
                title="Server Network Commands",
                description=f"Use `{prefix}network help` for more information",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
    @network.command(name="postmap", description="Post a server map to a specific channel")
    @commands.has_permissions(administrator=True)
    async def post_server_map(self, ctx, channel: discord.TextChannel, role: discord.Role = None):

        if not channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.send(f"I don't have permission to send messages in {channel.mention}", ephemeral=True)
            return
        
        embed, view = await self.generate_server_map(ctx.guild, role)
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        await channel.send(embed=embed, view=view)
        
        role_text = f" with {role.name} permissions" if role else ""
        await ctx.send(f"Server map{role_text} has been posted to {channel.mention}", ephemeral=True)


    @network.command(name="postnetworkmap", description="Post a network map to a specific channel")
    @commands.has_permissions(administrator=True)
    async def post_network_map(self, ctx, network_id: int, channel: discord.TextChannel):
        
        if network_id not in self.networks:
            await ctx.send("Network not found.", ephemeral=True)
            return
        
        network = self.networks[network_id]
        
        if not network.public and network.owner_id != ctx.author.id:
            await ctx.send("You don't have permission to view this private network.", ephemeral=True)
            return
        
        if not channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.send(f"I don't have permission to send messages in {channel.mention}", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"Network Map - {network.name}",
            description=f"{network.description}\n\n**Purpose:** {network.purpose}\n\nVisual representation of connected servers",
            color=discord.Color.green()
        )
        
        if network.icon_url:
            embed.set_thumbnail(url=network.icon_url)
        
        map_text = ""
        for server_id, server in network.servers.items():
            map_text += f"**{server.name}** connects to:\n"
            for connection_id in server.connections:
                if connection_id in network.servers:
                    map_text += f"└─ {network.servers[connection_id].name}\n"
            map_text += "\n"
        
        if not map_text:
            map_text = "No connections found in this network."
        
        embed.description += f"\n\n{map_text}"
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        await channel.send(embed=embed)
        
        await ctx.send(f"Network map for '{network.name}' has been posted to {channel.mention}", ephemeral=True)

    @network.command(name="create", description="Create a new server network")
    @commands.has_permissions(administrator=True)
    async def network_create(self, ctx):
        if ctx.interaction:
            modal = CreateNetworkModal(self)
            await ctx.interaction.response.send_modal(modal)
        else:
            await ctx.send("Please answer the following questions to create a network:")
            
            await ctx.send("What would you like to name your network?")
            try:
                name_msg = await self.bot.wait_for(
                    'message',
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=60.0
                )
                network_name = name_msg.content
                
                await ctx.send("Enter a description for your network:")
                desc_msg = await self.bot.wait_for(
                    'message',
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=60.0
                )
                network_description = desc_msg.content
                
                await ctx.send("What is the purpose of this network?")
                purpose_msg = await self.bot.wait_for(
                    'message',
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=60.0
                )
                network_purpose = purpose_msg.content
                
                await ctx.send("What category does this network belong to? (e.g. Gaming, Education)")
                cat_msg = await self.bot.wait_for(
                    'message',
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=60.0
                )
                network_category = cat_msg.content
                
                await ctx.send("Should this network be public? (yes/no)")
                public_msg = await self.bot.wait_for(
                    'message',
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=60.0
                )
                is_public = public_msg.content.lower() in ["yes", "y", "true"]
                
                network = ServerNetwork(
                    name=network_name,
                    owner_id=ctx.author.id,
                    public=is_public,
                    description=network_description,
                    purpose=network_purpose,
                    category=network_category
                )
                
                server = ctx.guild
                
                try:
                    invite = await self.get_or_create_invite(server)
                    invite_link = invite.url if invite else ""
                except:
                    invite_link = ""
                
                server_node = ServerNode(
                    server_id=server.id,
                    name=server.name,
                    description="This server",
                    member_count=server.member_count,
                    invite_link=invite_link,
                    category=network_category
                )
                
                server_node.icon_url = str(server.icon.url) if server.icon else ""
                server_node.banner_url = str(server.banner.url) if hasattr(server, 'banner') and server.banner else ""
                server_node.owner_name = str(server.owner) if server.owner else "Unknown"
                server_node.created_at = server.created_at
                
                network.add_server(server_node)
                network.icon_url = server_node.icon_url
                
                await self.save_network(network)
                
                embed = discord.Embed(
                    title="Server Network Created",
                    description=f"Your network '{network.name}' has been created successfully!",
                    color=discord.Color.green()
                )
                
                if network.icon_url:
                    embed.set_thumbnail(url=network.icon_url)
                
                embed.add_field(name="Description", value=network.description, inline=False)
                embed.add_field(name="Purpose", value=network.purpose, inline=False)
                embed.add_field(name="Category", value=network.category, inline=True)
                embed.add_field(name="Visibility", value="Public" if network.public else "Private", inline=True)
                
                await ctx.send(embed=embed)
                
            except asyncio.TimeoutError:
                await ctx.send("Network creation timed out. Please try again.")
    
    async def get_or_create_invite(self, guild):
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).create_instant_invite:
                try:
                    invites = await channel.invites()
                    if invites:
                        return invites[0]
                    else:
                        return await channel.create_invite(max_age=0, max_uses=0, unique=False)
                except:
                    continue
        return None
    
    @network.command(name="list", description="List available server networks")
    async def network_list(self, ctx):
        user_networks = []
        public_networks = []
        
        for network_id, network in self.networks.items():
            if network.owner_id == ctx.author.id:
                user_networks.append((network_id, network))
            elif network.public:
                public_networks.append((network_id, network))
        
        embed = discord.Embed(
            title="Server Networks",
            description="Browse available server networks",
            color=discord.Color.blue()
        )
        
        if user_networks:
            networks_text = "\n".join([f"• **{network.name}** (ID: {network_id})\n  {network.description[:50]}..." for network_id, network in user_networks])
            embed.add_field(name="Your Networks", value=networks_text, inline=False)
        
        if public_networks:
            networks_text = "\n".join([f"• **{network.name}** (ID: {network_id})\n  {network.description[:50]}..." for network_id, network in public_networks])
            embed.add_field(name="Public Networks", value=networks_text, inline=False)
        
        if not user_networks and not public_networks:
            embed.description = "No networks found. Create one with the network create command!"
        
        prefix = ctx.prefix
        embed.set_footer(text=f"Use '{prefix}network view <id>' to browse a network")
        
        await ctx.send(embed=embed)
    
    @network.command(name="view", description="View a server network")
    async def network_view(self, ctx, network_id: int):
        if network_id not in self.networks:
            await ctx.send("Network not found. Use the network list command to see available networks.", ephemeral=True)
            return
        
        network = self.networks[network_id]
        
        if not network.public and network.owner_id != ctx.author.id:
            await ctx.send("You don't have permission to view this private network.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"Server Network - {network.name}",
            description=f"{network.description}\n\n**Purpose:** {network.purpose}\n\nUse the buttons below to browse this server network",
            color=discord.Color.blue()
        )
        
        if network.icon_url:
            embed.set_thumbnail(url=network.icon_url)
        
        embed.add_field(name="Servers", value=str(len(network.servers)), inline=True)
        
        total_connections = sum(len(server.connections) for server in network.servers.values()) // 2
        embed.add_field(name="Connections", value=str(total_connections), inline=True)
        
        embed.add_field(name="Category", value=network.category, inline=True)
        
        if network.tags:
            embed.add_field(name="Tags", value=", ".join(network.tags), inline=False)
        
        view = ServerDirectoryView(self, network, ctx.author)
        await ctx.send(embed=embed, view=view)
    
    @network.command(name="add", description="Add a server to a network")
    @commands.has_permissions(administrator=True)
    async def network_add(self, ctx, network_id: int):
        if network_id not in self.networks:
            await ctx.send("Network not found. Use the network list command to see available networks.", ephemeral=True)
            return
        
        network = self.networks[network_id]
        
        if network.owner_id != ctx.author.id:
            await ctx.send("You don't have permission to add servers to this network.", ephemeral=True)
            return
        
        if ctx.interaction:
            modal = AddServerModal(self, network)
            await ctx.interaction.response.send_modal(modal)
        else:
            await ctx.send("Please answer the following questions to add a server:")
            
            try:
                await ctx.send("What is the name of the server?")
                name_msg = await self.bot.wait_for(
                    'message',
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=60.0
                )
                server_name = name_msg.content
                
                await ctx.send("Enter a brief description of the server:")
                desc_msg = await self.bot.wait_for(
                    'message',
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=60.0
                )
                server_description = desc_msg.content
                
                await ctx.send("What category does this server belong to? (e.g. Gaming, Education)")
                cat_msg = await self.bot.wait_for(
                    'message',
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=60.0
                )
                server_category = cat_msg.content
                
                await ctx.send("Enter tags for this server (comma separated):")
                tags_msg = await self.bot.wait_for(
                    'message',
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=60.0
                )
                tags = [tag.strip() for tag in tags_msg.content.split(",") if tag.strip()]
                
                await ctx.send("What is this server's purpose in the network?")
                purpose_msg = await self.bot.wait_for(
                    'message',
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=60.0
                )
                server_purpose = purpose_msg.content
                
                try:
                    invite = await self.get_or_create_invite(ctx.guild)
                    invite_link = invite.url if invite else ""
                except:
                    invite_link = ""
                
                server_node = ServerNode(
                    server_id=ctx.guild.id,
                    name=server_name,
                    description=server_description,
                    tags=tags,
                    member_count=ctx.guild.member_count,
                    invite_link=invite_link,
                    category=server_category
                )
                
                server_node.network_purpose = server_purpose
                server_node.icon_url = str(ctx.guild.icon.url) if ctx.guild.icon else ""
                server_node.banner_url = str(ctx.guild.banner.url) if hasattr(ctx.guild, 'banner') and ctx.guild.banner else ""
                server_node.owner_name = str(ctx.guild.owner) if ctx.guild.owner else "Unknown"
                server_node.created_at = ctx.guild.created_at
                
                for guild in self.bot.guilds:
                    if guild.name.lower() == server_name.lower():
                        server_node.server_id = guild.id
                        server_node.member_count = guild.member_count
                        server_node.icon_url = str(guild.icon.url) if guild.icon else ""
                        server_node.banner_url = str(guild.banner.url) if hasattr(guild, 'banner') and guild.banner else ""
                        server_node.owner_name = str(guild.owner) if guild.owner else "Unknown"
                        server_node.created_at = guild.created_at
                        
                        try:
                            invite = await self.get_or_create_invite(guild)
                            server_node.invite_link = invite.url if invite else ""
                        except:
                            pass
                        
                        break
                
                network.add_server(server_node)
                await self.save_network(network)
                
                embed = discord.Embed(
                    title="Server Added",
                    description=f"'{server_node.name}' has been added to the network '{network.name}'!",
                    color=discord.Color.green()
                )
                
                if server_node.icon_url:
                    embed.set_thumbnail(url=server_node.icon_url)
                
                embed.add_field(name="Description", value=server_node.description, inline=False)
                embed.add_field(name="Category", value=server_node.category, inline=True)
                embed.add_field(name="Tags", value=", ".join(server_node.tags) or "None", inline=True)
                
                if server_node.network_purpose:
                    embed.add_field(name="Purpose in Network", value=server_node.network_purpose, inline=False)
                
                await ctx.send(embed=embed)
                
            except asyncio.TimeoutError:
                await ctx.send("Server addition timed out. Please try again.")
    
    @network.command(name="connect", description="Connect two servers in a network")
    @commands.has_permissions(administrator=True)
    async def network_connect(self, ctx, network_id: int, server1_name: str, server2_name: str):
        if network_id not in self.networks:
            await ctx.send("Network not found.", ephemeral=True)
            return
        
        network = self.networks[network_id]
        
        if network.owner_id != ctx.author.id:
            await ctx.send("You don't have permission to modify this network.", ephemeral=True)
            return
        
        server1_id = None
        server2_id = None
        
        for server_id, server in network.servers.items():
            if server.name.lower() == server1_name.lower():
                server1_id = server_id
            elif server.name.lower() == server2_name.lower():
                server2_id = server_id
        
        if not server1_id:
            await ctx.send(f"Server '{server1_name}' not found in this network.", ephemeral=True)
            return
        
        if not server2_id:
            await ctx.send(f"Server '{server2_name}' not found in this network.", ephemeral=True)
            return
        
        network.add_connection(server1_id, server2_id)
        await self.save_network(network)
        
        embed = discord.Embed(
            title="Servers Connected",
            description=f"Connected '{server1_name}' and '{server2_name}' in the network!",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)
    
    @network.command(name="remove", description="Remove a server from a network")
    @commands.has_permissions(administrator=True)
    async def network_remove(self, ctx, network_id: int, server_name: str):
        if network_id not in self.networks:
            await ctx.send("Network not found.", ephemeral=True)
            return
        
        network = self.networks[network_id]
        
        if network.owner_id != ctx.author.id:
            await ctx.send("You don't have permission to modify this network.", ephemeral=True)
            return
        
        server_id = None
        for sid, server in network.servers.items():
            if server.name.lower() == server_name.lower():
                server_id = sid
                break
        
        if not server_id:
            await ctx.send(f"Server '{server_name}' not found in this network.", ephemeral=True)
            return
        
        network.remove_server(server_id)
        await self.save_network(network)
        
        embed = discord.Embed(
            title="Server Removed",
            description=f"Removed '{server_name}' from the network!",
            color=discord.Color.red()
        )
        
        await ctx.send(embed=embed)
    
    @network.command(name="delete", description="Delete a server network")
    @commands.has_permissions(administrator=True)
    async def network_delete(self, ctx, network_id: int):
        if network_id not in self.networks:
            await ctx.send("Network not found.", ephemeral=True)
            return
        
        network = self.networks[network_id]
        
        if network.owner_id != ctx.author.id:
            await ctx.send("You don't have permission to delete this network.", ephemeral=True)
            return
        
        try:
            os.remove(os.path.join(self.data_folder, f"{network_id}.json"))
        except:
            pass
        
        self.networks.pop(network_id, None)
        
        embed = discord.Embed(
            title="Network Deleted",
            description=f"Network '{network.name}' has been deleted!",
            color=discord.Color.red()
        )
        
        await ctx.send(embed=embed)
    
    @network.command(name="update", description="Update server information in a network")
    @commands.has_permissions(administrator=True)
    async def network_update(self, ctx, network_id: int):
        if network_id not in self.networks:
            await ctx.send("Network not found.", ephemeral=True)
            return
        
        network = self.networks[network_id]
        
        if network.owner_id != ctx.author.id:
            await ctx.send("You don't have permission to modify this network.", ephemeral=True)
            return
        
        updated_count = 0
        for server_id, server in network.servers.items():
            guild = self.bot.get_guild(server_id)
            if guild:
                server.name = guild.name
                server.member_count = guild.member_count
                server.icon_url = str(guild.icon.url) if guild.icon else ""
                server.banner_url = str(guild.banner.url) if hasattr(guild, 'banner') and guild.banner else ""
                server.owner_name = str(guild.owner) if guild.owner else "Unknown"
                
                try:
                    invite = await self.get_or_create_invite(guild)
                    server.invite_link = invite.url if invite else server.invite_link
                except:
                    pass
                
                updated_count += 1
        
        await self.save_network(network)
        
        embed = discord.Embed(
            title="Network Updated",
            description=f"Updated information for {updated_count} servers in the network!",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)
    
    @network.command(name="map", description="View a server network map")
    async def network_map(self, ctx, network_id: int):
        if network_id not in self.networks:
            await ctx.send("Network not found.", ephemeral=True)
            return
        
        network = self.networks[network_id]
        
        if not network.public and network.owner_id != ctx.author.id:
            await ctx.send("You don't have permission to view this private network.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"Network Map - {network.name}",
            description=f"{network.description}\n\n**Purpose:** {network.purpose}\n\nVisual representation of connected servers",
            color=discord.Color.green()
        )
        
        if network.icon_url:
            embed.set_thumbnail(url=network.icon_url)
        
        map_text = ""
        for server_id, server in network.servers.items():
            map_text += f"**{server.name}** connects to:\n"
            for connection_id in server.connections:
                if connection_id in network.servers:
                    map_text += f"└─ {network.networks[connection_id].name}\n"
            map_text += "\n"
        
        if not map_text:
            map_text = "No connections found in this network."
        
        embed.description += f"\n\n{map_text}"
        
        await ctx.send(embed=embed)
    
    @network.command(name="servermap", description="Generate a map of your server's channels")
    @commands.has_permissions(administrator=True)
    async def server_map(self, ctx, role: discord.Role = None):
        embed, view = await self.generate_server_map(ctx.guild, role)
        await ctx.send(embed=embed, view=view)
    
    async def generate_server_map(self, guild, role=None):
        embed = discord.Embed(
            title=f"Server Channel Map - {guild.name}",
            description="Visual map of channels in this server",
            color=discord.Color.green()
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        if role:
            embed.description += f"\nShowing channels accessible to role: **{role.name}**"
        
        categories = {}
        standalone_channels = []
        
        for channel in guild.channels:
            if isinstance(channel, discord.CategoryChannel):
                if role and not channel.permissions_for(role).view_channel:
                    continue
                categories[channel.id] = {"name": channel.name, "channels": []}
            elif channel.category_id is None:
                if role and not channel.permissions_for(role).view_channel:
                    continue
                standalone_channels.append(channel)
        
        for channel in guild.channels:
            if not isinstance(channel, discord.CategoryChannel) and channel.category_id is not None:
                if channel.category_id in categories:
                    if role and not channel.permissions_for(role).view_channel:
                        continue
                    channel_type = "text"
                    if isinstance(channel, discord.VoiceChannel):
                        channel_type = "voice"
                    elif isinstance(channel, discord.ForumChannel):
                        channel_type = "forum"
                    elif isinstance(channel, discord.StageChannel):
                        channel_type = "stage"
                    elif hasattr(channel, 'news') and channel.news:
                        channel_type = "announcement"
                    
                    categories[channel.category_id]["channels"].append({
                        "name": channel.name,
                        "type": channel_type,
                        "id": channel.id
                    })
        
        map_text = ""
        
        for category_id, category in categories.items():
            map_text += f"**{category['name']}**\n"
            for channel in category["channels"]:
                if channel["type"] == "text":
                    map_text += f"├─ 📝 {channel['name']}\n"
                elif channel["type"] == "voice":
                    map_text += f"├─ 🔊 {channel['name']}\n"
                elif channel["type"] == "forum":
                    map_text += f"├─ 📋 {channel['name']}\n"
                elif channel["type"] == "stage":
                    map_text += f"├─ 🎭 {channel['name']}\n"
                elif channel["type"] == "announcement":
                    map_text += f"├─ 📢 {channel['name']}\n"
                else:
                    map_text += f"├─ {channel['name']}\n"
            map_text += "\n"
        
        if standalone_channels:
            map_text += "**Standalone Channels**\n"
            for channel in standalone_channels:
                if isinstance(channel, discord.TextChannel):
                    map_text += f"├─ 📝 {channel.name}\n"
                elif isinstance(channel, discord.VoiceChannel):
                    map_text += f"├─ 🔊 {channel.name}\n"
                elif isinstance(channel, discord.ForumChannel):
                    map_text += f"├─ 📋 {channel.name}\n"
                elif isinstance(channel, discord.StageChannel):
                    map_text += f"├─ 🎭 {channel.name}\n"
                else:
                    map_text += f"├─ {channel.name}\n"
        
        embed.description += f"\n\n{map_text}"
        
        # Create a view with role selection
        view = discord.ui.View()
        
        select_role_button = discord.ui.Button(
            label="Select Different Role", 
            style=discord.ButtonStyle.primary,
            custom_id="select_role"
        )
        
        async def select_role_callback(interaction):
            if interaction.user.guild_permissions.administrator:
                modal = ServerMapModal(self, guild)
                await interaction.response.send_modal(modal)
            else:
                await interaction.response.send_message("You need administrator permissions to do this.", ephemeral=True)
        
        select_role_button.callback = select_role_callback
        view.add_item(select_role_button)
        
        return embed, view
    
    @network.command(name="featured", description="Set featured servers in a network (comma-separated)")
    @commands.has_permissions(administrator=True)
    async def set_featured(self, ctx, network_id: int, server_names: str = ""):
        if network_id not in self.networks:
            await ctx.send("Network not found.", ephemeral=True)
            return
            
        network = self.networks[network_id]
            
        if network.owner_id != ctx.author.id:
            await ctx.send("You don't have permission to modify this network.", ephemeral=True)
            return
            
        # Split by commas and strip whitespace
        names = [name.strip() for name in server_names.split(',') if name.strip()]
        
        if not names:
            await ctx.send("Please provide at least one server name to feature (comma-separated).", ephemeral=True)
            return
            
        server_ids = []
        not_found = []
            
        for name in names:
            found = False
            for server_id, server in network.servers.items():
                if server.name.lower() == name.lower():
                    server_ids.append(server_id)
                    found = True
                    break
                    
            if not found:
                not_found.append(name)
            
        if not_found:
            await ctx.send(f"The following servers were not found: {', '.join(not_found)}", ephemeral=True)
        
        if server_ids:
            network.featured_servers = server_ids  # Assuming this is how you set featured servers
            await self.save_network(network)
            
            embed = discord.Embed(
                title="Featured Servers Updated",
                description=f"Updated featured servers in network '{network.name}'!",
                color=discord.Color.green()
            )
            
            featured_servers = []
            for server_id in network.featured_servers:
                if server_id in network.servers:
                    featured_servers.append(network.servers[server_id].name)
            
            if featured_servers:
                embed.add_field(name="Featured Servers", value="\n".join(featured_servers), inline=False)
            
            await ctx.send(embed=embed)

    
    @network.command(name="invite", description="Generate or update invite links for servers")
    @commands.has_permissions(administrator=True)
    async def update_invites(self, ctx, network_id: int):
        if network_id not in self.networks:
            await ctx.send("Network not found.", ephemeral=True)
            return
        
        network = self.networks[network_id]
        
        if network.owner_id != ctx.author.id:
            await ctx.send("You don't have permission to modify this network.", ephemeral=True)
            return
        
        updated_count = 0
        for server_id, server in network.servers.items():
            guild = self.bot.get_guild(server_id)
            if guild:
                try:
                    invite = await self.get_or_create_invite(guild)
                    if invite:
                        server.invite_link = invite.url
                        updated_count += 1
                except:
                    continue
        
        await self.save_network(network)
        
        embed = discord.Embed(
            title="Invite Links Updated",
            description=f"Updated invite links for {updated_count} servers in the network!",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)
    
    @network.command(name="edit", description="Edit network information")
    @commands.has_permissions(administrator=True)
    async def edit_network(self, ctx, network_id: int, field: str, *, value: str):
        if network_id not in self.networks:
            await ctx.send("Network not found.", ephemeral=True)
            return
        
        network = self.networks[network_id]
        
        if network.owner_id != ctx.author.id:
            await ctx.send("You don't have permission to modify this network.", ephemeral=True)
            return
        
        field = field.lower()
        
        if field == "name":
            network.name = value
        elif field == "description":
            network.description = value
        elif field == "purpose":
            network.purpose = value
        elif field == "category":
            network.category = value
        elif field == "tags":
            network.tags = [tag.strip() for tag in value.split(",") if tag.strip()]
        elif field == "public":
            network.public = value.lower() in ["yes", "y", "true", "1"]
        elif field == "icon":
            network.icon_url = value
        elif field == "banner":
            network.banner_url = value
        else:
            await ctx.send(f"Unknown field: {field}. Valid fields are: name, description, purpose, category, tags, public, icon, banner", ephemeral=True)
            return
        
        await self.save_network(network)
        
        embed = discord.Embed(
            title="Network Updated",
            description=f"Updated {field} for network '{network.name}'!",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)
    
    @network.command(name="editserver", description="Edit server information in a network")
    @commands.has_permissions(administrator=True)
    async def edit_server(self, ctx, network_id: int, server_name: str, field: str, *, value: str):
        if network_id not in self.networks:
            await ctx.send("Network not found.", ephemeral=True)
            return
        
        network = self.networks[network_id]
        
        if network.owner_id != ctx.author.id:
            await ctx.send("You don't have permission to modify this network.", ephemeral=True)
            return
        
        server_id = None
        for sid, server in network.servers.items():
            if server.name.lower() == server_name.lower():
                server_id = sid
                break
        
        if not server_id:
            await ctx.send(f"Server '{server_name}' not found in this network.", ephemeral=True)
            return
        
        server = network.servers[server_id]
        field = field.lower()
        
        if field == "name":
            server.name = value
        elif field == "description":
            server.description = value
        elif field == "category":
            server.category = value
        elif field == "tags":
            server.tags = [tag.strip() for tag in value.split(",") if tag.strip()]
        elif field == "invite":
            server.invite_link = value
        elif field == "purpose":
            server.network_purpose = value
        elif field == "icon":
            server.icon_url = value
        elif field == "banner":
            server.banner_url = value
        elif field == "owner":
            server.owner_name = value
        else:
            await ctx.send(f"Unknown field: {field}. Valid fields are: name, description, category, tags, invite, purpose, icon, banner, owner", ephemeral=True)
            return
        
        await self.save_network(network)
        
        embed = discord.Embed(
            title="Server Updated",
            description=f"Updated {field} for server '{server.name}' in network '{network.name}'!",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        for network in self.networks.values():
            for server_id, server in network.servers.items():
                if server_id == guild.id:
                    server.name = guild.name
                    server.member_count = guild.member_count
                    server.icon_url = str(guild.icon.url) if guild.icon else ""
                    server.banner_url = str(guild.banner.url) if hasattr(guild, 'banner') and guild.banner else ""
                    server.owner_name = str(guild.owner) if guild.owner else "Unknown"
                    
                    try:
                        invite = await self.get_or_create_invite(guild)
                        server.invite_link = invite.url if invite else server.invite_link
                    except:
                        pass
                    
                    await self.save_network(network)
    
    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        if before.name != after.name or before.member_count != after.member_count:
            for network in self.networks.values():
                for server_id, server in network.servers.items():
                    if server_id == after.id:
                        server.name = after.name
                        server.member_count = after.member_count
                        server.icon_url = str(after.icon.url) if after.icon else ""
                        server.banner_url = str(after.banner.url) if hasattr(after, 'banner') and after.banner else ""
                        server.owner_name = str(after.owner) if after.owner else "Unknown"
                        await self.save_network(network)
    
    @network.command(name="help", description="Show help for server network commands")
    async def network_help(self, ctx):
        prefix = ctx.prefix
        
        embed = discord.Embed(
            title="Server Network Directory Help",
            description="Commands for managing and browsing server networks",
            color=discord.Color.blue()
        )
        
        commands = [
            (f"{prefix}network create", "Create a new server network"),
            (f"{prefix}network list", "List available networks"),
            (f"{prefix}network view <id>", "Browse a server network"),
            (f"{prefix}network add <id>", "Add a server to a network"),
            (f"{prefix}network connect <id> <server1> <server2>", "Connect two servers"),
            (f"{prefix}network remove <id> <server>", "Remove a server from a network"),
            (f"{prefix}network delete <id>", "Delete a network"),
            (f"{prefix}network update <id>", "Update server information"),
            (f"{prefix}network map <id>", "View a network map"),
            (f"{prefix}network servermap [role]", "Generate a map of your server's channels"),
            (f"{prefix}network featured <id> <server_names>", "Set featured servers (comma-separated)"),
            (f"{prefix}network invite <id>", "Update invite links"),
            (f"{prefix}network edit <id> <field> <value>", "Edit network information"),
            (f"{prefix}network editserver <id> <server> <field> <value>", "Edit server information"),
            (f"{prefix}network postmap <channel> [role]", "Post a server map to a specific channel"),
            (f"{prefix}network postnetworkmap <id> <channel>", "Post a network map to a specific channel")
        ]
        
        for command, description in commands:
            embed.add_field(name=command, value=description, inline=False)
        
        embed.add_field(
            name="Network Fields",
            value="name, description, purpose, category, tags, public, icon, banner",
            inline=False
        )
        
        embed.add_field(
            name="Server Fields",
            value="name, description, category, tags, invite, purpose, icon, banner, owner",
            inline=False
        )
        
        embed.set_footer(text="Server networks allow you to create a directory of connected servers")
        
        await ctx.send(embed=embed)
        
def setup(bot):
    cog = MultiServerDirectory(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    return cog

