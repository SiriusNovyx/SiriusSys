
import discord
from discord.ext import commands
import aiohttp
import json
import os
import asyncio
import logging
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class ExtensionMarketplace(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = "https://zygnalbot.de/get_extensions.php"
        self.extensions_folder = "Extensions"
        self.cache = {}
        self.cache_time = None
        self.cache_duration = 300
    
    async def fetch_extensions(self, force_refresh=False):
        if not force_refresh and self.cache_time and (datetime.now() - self.cache_time).seconds < self.cache_duration:
            return self.cache
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success'):
                            self.cache = data
                            self.cache_time = datetime.now()
                            return data
                        else:
                            logger.error("API returned success: false")
                            return None
                    else:
                        logger.error(f"API request failed with status {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error fetching extensions: {e}")
            return None
    
    async def download_extension(self, extension_data):
        try:
            if extension_data.get('customUrl'):
                download_url = extension_data['customUrl']
            else:
                extension_id = extension_data['id']
                download_url = f"https://zygnalbot.de/download_extension.php?id={extension_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url, timeout=60) as response:
                    if response.status == 200:
                        content = await response.text()
                        filename = f"{extension_data['title'].replace(' ', '_').lower()}.{extension_data['fileType']}"
                        filename = re.sub(r'[^\w\-_\.]', '', filename)
                        filepath = os.path.join(self.extensions_folder, filename)
                        
                        if not os.path.exists(self.extensions_folder):
                            os.makedirs(self.extensions_folder)
                        
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(content)
                        
                        return filepath
                    else:
                        logger.error(f"Download failed with status {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error downloading extension: {e}")
            return None
    
    @commands.group(name='marketplace', aliases=['mp', 'extensions'], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def marketplace_group(self, ctx):
        if ctx.invoked_subcommand is None:
            await self.show_marketplace_menu(ctx)
    
    @discord.app_commands.command(name='marketplace', description='Browse and manage extensions from the marketplace')
    @discord.app_commands.default_permissions(administrator=True)
    async def marketplace_slash(self, interaction: discord.Interaction):
        await self.show_marketplace_menu_slash(interaction)
    
    async def show_marketplace_menu(self, ctx):
        embed = discord.Embed(
            title="🛒 Extension Marketplace",
            description="Browse, preview, and install extensions directly to your bot!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🔍 Available Commands",
            value=f"`{ctx.prefix}marketplace browse` - Browse all extensions\n"
                  f"`{ctx.prefix}marketplace search <query>` - Search extensions\n"
                  f"`{ctx.prefix}marketplace categories` - Browse by category\n"
                  f"`{ctx.prefix}marketplace install <id>` - Install extension\n"
                  f"`{ctx.prefix}marketplace info <id>` - View extension details\n"
                  f"`{ctx.prefix}marketplace refresh` - Refresh extension list",
            inline=False
        )
        embed.add_field(
            name="⚡ Quick Actions",
            value="Use the buttons below for quick access to marketplace features!",
            inline=False
        )
        embed.set_footer(text="Made By TheHolyOneZ • Extension Marketplace v1.0")
        view = MarketplaceMenuView(self)
        await ctx.send(embed=embed, view=view)
    
    async def show_marketplace_menu_slash(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛒 Extension Marketplace",
            description="Browse, preview, and install extensions directly to your bot!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🔍 Available Slash Commands",
            value="`/marketplace` - Main marketplace menu\n"
                  "`/marketplace-browse` - Browse all extensions\n"
                  "`/marketplace-search` - Search extensions\n"
                  "`/marketplace-install` - Install extension by ID",
            inline=False
        )
        embed.add_field(
            name="⚡ Quick Actions",
            value="Use the buttons below for quick access to marketplace features!",
            inline=False
        )
        embed.set_footer(text="Made By TheHolyOneZ • Extension Marketplace v1.0")
        view = MarketplaceMenuView(self)
        await interaction.response.send_message(embed=embed, view=view)
    
    @marketplace_group.command(name='browse')
    @commands.has_permissions(administrator=True)
    async def browse_extensions(self, ctx, page: int = 1):
        await ctx.send("🔄 Loading extensions from marketplace...")
        data = await self.fetch_extensions()
        if not data or not data.get('extensions'):
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to fetch extensions from marketplace!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        extensions = data['extensions']
        view = ExtensionBrowserView(self, extensions, page)
        await view.send_page(ctx)
    
    @marketplace_group.command(name='search')
    @commands.has_permissions(administrator=True)
    async def search_extensions(self, ctx, *, query: str):
        await ctx.send(f"🔍 Searching for '{query}'...")
        data = await self.fetch_extensions()
        if not data or not data.get('extensions'):
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to fetch extensions from marketplace!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        extensions = data['extensions']
        query_lower = query.lower()
        filtered_extensions = [
            ext for ext in extensions
            if query_lower in ext.get('title', '').lower() or 
               query_lower in ext.get('description', '').lower() or
               query_lower in ext.get('details', '').lower()
        ]
        
        if not filtered_extensions:
            embed = discord.Embed(
                title="🔍 Search Results",
                description=f"No extensions found matching '{query}'",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        view = ExtensionBrowserView(self, filtered_extensions, 1, f"Search: {query}")
        await view.send_page(ctx)
    
    @marketplace_group.command(name='info')
    @commands.has_permissions(administrator=True)
    async def extension_info(self, ctx, extension_id: int):
        data = await self.fetch_extensions()
        if not data or not data.get('extensions'):
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to fetch extensions from marketplace!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        extension = next((ext for ext in data['extensions'] if ext['id'] == extension_id), None)
        if not extension:
            embed = discord.Embed(
                title="❌ Extension Not Found",
                description=f"No extension found with ID {extension_id}",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        view = ExtensionDetailView(self, extension)
        await view.show_details(ctx)
    
    @marketplace_group.command(name='install')
    @commands.has_permissions(administrator=True)
    async def install_extension(self, ctx, extension_id: int):
        data = await self.fetch_extensions()
        if not data or not data.get('extensions'):
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to fetch extensions from marketplace!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        extension = next((ext for ext in data['extensions'] if ext['id'] == extension_id), None)
        if not extension:
            embed = discord.Embed(
                title="❌ Extension Not Found",
                description=f"No extension found with ID {extension_id}",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        view = InstallConfirmView(self, extension)
        embed = discord.Embed(
            title="📦 Install Extension",
            description=f"Are you sure you want to install **{extension['title']}**?",
            color=discord.Color.blue()
        )
        embed.add_field(name="Version", value=extension['version'], inline=True)
        embed.add_field(name="Status", value=extension['status'].title(), inline=True)
        embed.add_field(name="File Type", value=extension['fileType'].upper(), inline=True)
        embed.add_field(name="Description", value=extension['description'][:500] + "..." if len(extension['description']) > 500 else extension['description'], inline=False)
        embed.set_footer(text="Made By TheHolyOneZ • This will download and save the extension to your Extensions folder")
        await ctx.send(embed=embed, view=view)
    
    @marketplace_group.command(name='refresh')
    @commands.has_permissions(administrator=True)
    async def refresh_cache(self, ctx):
        embed = discord.Embed(
            title="🔄 Refreshing...",
            description="Fetching latest extensions from marketplace...",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        message = await ctx.send(embed=embed)
        
        data = await self.fetch_extensions(force_refresh=True)
        if data and data.get('extensions'):
            embed = discord.Embed(
                title="✅ Cache Refreshed",
                description=f"Successfully loaded {len(data['extensions'])} extensions from marketplace!",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Refresh Failed",
                description="Failed to fetch extensions from marketplace!",
                color=discord.Color.red()
            )
        embed.set_footer(text="Made By TheHolyOneZ")
        await message.edit(embed=embed)

class MarketplaceMenuView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
    
    @discord.ui.button(label='Browse All', style=discord.ButtonStyle.primary, emoji='🔍')
    async def browse_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        data = await self.cog.fetch_extensions()
        if not data or not data.get('extensions'):
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to fetch extensions from marketplace!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        extensions = data['extensions']
        view = ExtensionBrowserView(self.cog, extensions, 1)
        await view.send_page_interaction(interaction)
    
    @discord.ui.button(label='Search', style=discord.ButtonStyle.secondary, emoji='🔎')
    async def search_extensions(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SearchModal(self.cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='Categories', style=discord.ButtonStyle.secondary, emoji='📂')
    async def browse_categories(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        data = await self.cog.fetch_extensions()
        if not data or not data.get('extensions'):
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to fetch extensions from marketplace!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        extensions = data['extensions']
        categories = {}
        for ext in extensions:
            status = ext.get('status', 'unknown').title()
            if status not in categories:
                categories[status] = []
            categories[status].append(ext)
        
        embed = discord.Embed(
            title="📂 Extension Categories",
            description="Browse extensions by status/category:",
            color=discord.Color.blue()
        )
        
        for category, exts in categories.items():
            embed.add_field(
                name=f"{category} ({len(exts)})",
                value=f"Extensions with {category.lower()} status",
                inline=True
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        view = CategorySelectView(self.cog, categories)
        await interaction.followup.send(embed=embed, view=view)
    
    @discord.ui.button(label='Refresh', style=discord.ButtonStyle.success, emoji='🔄')
    async def refresh_cache(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        data = await self.cog.fetch_extensions(force_refresh=True)
        if data and data.get('extensions'):
            embed = discord.Embed(
                title="✅ Cache Refreshed",
                description=f"Successfully loaded {len(data['extensions'])} extensions from marketplace!",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Refresh Failed",
                description="Failed to fetch extensions from marketplace!",
                color=discord.Color.red()
            )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.followup.send(embed=embed, ephemeral=True)

class SearchModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="🔍 Search Extensions")
        self.cog = cog
        
        self.search_query = discord.ui.TextInput(
            label="Search Query",
            placeholder="Enter keywords to search for...",
            required=True,
            max_length=100
        )
        self.add_item(self.search_query)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        query = self.search_query.value
        
        data = await self.cog.fetch_extensions()
        if not data or not data.get('extensions'):
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to fetch extensions from marketplace!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        extensions = data['extensions']
        query_lower = query.lower()
        filtered_extensions = [
            ext for ext in extensions
            if query_lower in ext.get('title', '').lower() or 
               query_lower in ext.get('description', '').lower() or
               query_lower in ext.get('details', '').lower()
        ]
        
        if not filtered_extensions:
            embed = discord.Embed(
                title="🔍 Search Results",
                description=f"No extensions found matching '{query}'",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        view = ExtensionBrowserView(self.cog, filtered_extensions, 1, f"Search: {query}")
        await view.send_page_interaction(interaction)

class CategorySelectView(discord.ui.View):
    def __init__(self, cog, categories):
        super().__init__(timeout=300)
        self.cog = cog
        self.categories = categories
        
        options = []
        for category, exts in categories.items():
            emoji = "✅" if category == "Working" else "⚠️" if category == "Beta" else "❌" if category == "Broken" else "❓"
            options.append(discord.SelectOption(
                label=f"{category} ({len(exts)})",
                description=f"Browse {len(exts)} extensions with {category.lower()} status",
                emoji=emoji,
                value=category
            ))
        
        if options:
            select = discord.ui.Select(placeholder="Choose a category to browse...", options=options[:25])
            select.callback = self.category_selected
            self.add_item(select)
    
    async def category_selected(self, interaction: discord.Interaction):
        category = interaction.data['values'][0]
        extensions = self.categories[category]
        
        view = ExtensionBrowserView(self.cog, extensions, 1, f"Category: {category}")
        await view.send_page_interaction(interaction)

class ExtensionBrowserView(discord.ui.View):
    def __init__(self, cog, extensions, page=1, title_suffix=""):
        super().__init__(timeout=300)
        self.cog = cog
        self.extensions = extensions
        self.page = page
        self.title_suffix = title_suffix
        self.per_page = 5
        self.max_pages = (len(extensions) + self.per_page - 1) // self.per_page
    
    def get_page_extensions(self):
        start = (self.page - 1) * self.per_page
        end = start + self.per_page
        return self.extensions[start:end]
    
    def create_embed(self):
        page_extensions = self.get_page_extensions()
        
        title = f"🛒 Extension Marketplace"
        if self.title_suffix:
            title += f" - {self.title_suffix}"
        
        embed = discord.Embed(
            title=title,
            description=f"Showing {len(page_extensions)} of {len(self.extensions)} extensions (Page {self.page}/{self.max_pages})",
            color=discord.Color.blue()
        )
        
        for ext in page_extensions:
            status_emoji = "✅" if ext['status'] == "working" else "⚠️" if ext['status'] == "beta" else "❌"
            
            value = f"**Description:** {ext['description'][:100]}{'...' if len(ext['description']) > 100 else ''}\n"
            value += f"**Version:** {ext['version']} | **Status:** {status_emoji} {ext['status'].title()}\n"
            value += f"**Type:** {ext['fileType'].upper()} | **Date:** {ext['date']}\n"
            value += f"**ID:** `{ext['id']}`"
            
            embed.add_field(
                name=f"📦 {ext['title']}",
                value=value,
                inline=False
            )
        
        embed.set_footer(text="Made By TheHolyOneZ • Use buttons to navigate or install extensions")
        return embed
    
    def update_buttons(self):
        self.clear_items()
        
        if self.page > 1:
            prev_button = discord.ui.Button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
            prev_button.callback = self.previous_page
            self.add_item(prev_button)
        
        if self.page < self.max_pages:
            next_button = discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.secondary)
            next_button.callback = self.next_page
            self.add_item(next_button)
        
        page_extensions = self.get_page_extensions()
        for ext in page_extensions:
            install_button = discord.ui.Button(
                label=f"📦 Install {ext['title'][:20]}",
                style=discord.ButtonStyle.success,
                custom_id=f"install_{ext['id']}"
            )
            install_button.callback = lambda i, ext_id=ext['id']: self.install_extension(i, ext_id)
            self.add_item(install_button)
        
        info_select_options = []
        for ext in page_extensions:
            info_select_options.append(discord.SelectOption(
                label=f"ℹ️ {ext['title'][:50]}",
                description=f"View details for {ext['title']}",
                value=str(ext['id'])
            ))
        
        if info_select_options:
            info_select = discord.ui.Select(placeholder="📋 View Extension Details...", options=info_select_options)
            info_select.callback = self.view_details
            self.add_item(info_select)
    
    async def previous_page(self, interaction: discord.Interaction):
        self.page -= 1
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def install_extension(self, interaction: discord.Interaction, ext_id: int):
        extension = next((ext for ext in self.extensions if ext['id'] == ext_id), None)
        if not extension:
            await interaction.response.send_message("❌ Extension not found!", ephemeral=True)
            return
        
        view = InstallConfirmView(self.cog, extension)
        embed = discord.Embed(
            title="📦 Install Extension",
            description=f"Are you sure you want to install **{extension['title']}**?",
            color=discord.Color.blue()
        )
        embed.add_field(name="Version", value=extension['version'], inline=True)
        embed.add_field(name="Status", value=extension['status'].title(), inline=True)
        embed.add_field(name="File Type", value=extension['fileType'].upper(), inline=True)
        embed.add_field(name="Description", value=extension['description'][:500] + "..." if len(extension['description']) > 500 else extension['description'], inline=False)
        embed.set_footer(text="Made By TheHolyOneZ • This will download and save the extension to your Extensions folder")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def view_details(self, interaction: discord.Interaction):
        ext_id = int(interaction.data['values'][0])
        extension = next((ext for ext in self.extensions if ext['id'] == ext_id), None)
        if not extension:
            await interaction.response.send_message("❌ Extension not found!", ephemeral=True)
            return
        
        view = ExtensionDetailView(self.cog, extension)
        await view.show_details_interaction(interaction)
    
    async def send_page(self, ctx):
        self.update_buttons()
        embed = self.create_embed()
        await ctx.send(embed=embed, view=self)
    
    async def send_page_interaction(self, interaction: discord.Interaction):
        self.update_buttons()
        embed = self.create_embed()
        await interaction.followup.send(embed=embed, view=self)

class ExtensionDetailView(discord.ui.View):
    def __init__(self, cog, extension):
        super().__init__(timeout=300)
        self.cog = cog
        self.extension = extension
        
        install_button = discord.ui.Button(label="📦 Install Extension", style=discord.ButtonStyle.success)
        install_button.callback = self.install_extension
        self.add_item(install_button)
        
        if extension.get('customUrl'):
            view_source_button = discord.ui.Button(label="🔗 View Source", style=discord.ButtonStyle.link, url=extension['customUrl'])
            self.add_item(view_source_button)
    
    def create_detail_embed(self):
        ext = self.extension
        status_emoji = "✅" if ext['status'] == "working" else "⚠️" if ext['status'] == "beta" else "❌"
        
        embed = discord.Embed(
            title=f"📦 {ext['title']}",
            description=ext['description'],
            color=discord.Color.green() if ext['status'] == "working" else discord.Color.orange() if ext['status'] == "beta" else discord.Color.red()
        )
        
        embed.add_field(name="🆔 ID", value=ext['id'], inline=True)
        embed.add_field(name="📊 Version", value=ext['version'], inline=True)
        embed.add_field(name="📁 File Type", value=ext['fileType'].upper(), inline=True)
        embed.add_field(name="📅 Date", value=ext['date'], inline=True)
        embed.add_field(name="🔧 Status", value=f"{status_emoji} {ext['status'].title()}", inline=True)
        embed.add_field(name="🔗 Custom URL", value="Yes" if ext.get('customUrl') else "No", inline=True)
        
        if ext.get('details'):
            details = ext['details'][:1000] + "..." if len(ext['details']) > 1000 else ext['details']
            embed.add_field(name="📋 Details", value=details, inline=False)
        
        embed.set_footer(text="Made By TheHolyOneZ • Extension Marketplace")
        return embed
    
    async def install_extension(self, interaction: discord.Interaction):
        view = InstallConfirmView(self.cog, self.extension)
        embed = discord.Embed(
            title="📦 Install Extension",
            description=f"Are you sure you want to install **{self.extension['title']}**?",
            color=discord.Color.blue()
        )
        embed.add_field(name="Version", value=self.extension['version'], inline=True)
        embed.add_field(name="Status", value=self.extension['status'].title(), inline=True)
        embed.add_field(name="File Type", value=self.extension['fileType'].upper(), inline=True)
        embed.set_footer(text="Made By TheHolyOneZ • This will download and save the extension to your Extensions folder")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def show_details(self, ctx):
        embed = self.create_detail_embed()
        await ctx.send(embed=embed, view=self)
    
    async def show_details_interaction(self, interaction: discord.Interaction):
        embed = self.create_detail_embed()
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

class InstallConfirmView(discord.ui.View):
    def __init__(self, cog, extension):
        super().__init__(timeout=60)
        self.cog = cog
        self.extension = extension
    
    @discord.ui.button(label="✅ Confirm Install", style=discord.ButtonStyle.success)
    async def confirm_install(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="📥 Installing Extension...",
            description=f"Downloading **{self.extension['title']}**...",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.followup.edit_message(interaction.message.id, embed=embed, view=None)
        
        filepath = await self.cog.download_extension(self.extension)
        
        if filepath:
            try:
                if callable(self.cog.bot.command_prefix):
                    class MockMessage:
                        def __init__(self, guild):
                            self.guild = guild
                    
                    mock_msg = MockMessage(interaction.guild)
                    prefix = await self.cog.bot.command_prefix(self.cog.bot, mock_msg)
                    if isinstance(prefix, list):
                        prefix = prefix[0]  
                else:
                    prefix = self.cog.bot.command_prefix
            except:
                prefix = "!"
            
            embed = discord.Embed(
                title="✅ Extension Installed Successfully!",
                description=f"**{self.extension['title']}** has been installed to `{filepath}`",
                color=discord.Color.green()
            )
            embed.add_field(name="📁 File Location", value=filepath, inline=False)
            embed.add_field(name="⚠️ Important", value="You may need to restart the bot or reload extensions for changes to take effect.", inline=False)
            embed.add_field(name="🔄 Next Steps", value=f"1. Use `{prefix}ext load <extension_name>` if available\n2. Check logs for any errors\n3. Restart the bot if needed", inline=False)
        else:
            embed = discord.Embed(
                title="❌ Installation Failed",
                description=f"Failed to download **{self.extension['title']}**",
                color=discord.Color.red()
            )
            embed.add_field(name="🔍 Troubleshooting", value="• Check your internet connection\n• Verify the extension URL is accessible\n• Check bot permissions for file writing", inline=False)
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.edit_original_response(embed=embed, view=None)
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel_install(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❌ Installation Cancelled",
            description="Extension installation was cancelled.",
            color=discord.Color.red()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.edit_message(embed=embed, view=None)


# Slash Commands
@discord.app_commands.command(name='marketplace-browse', description='Browse all available extensions')
@discord.app_commands.default_permissions(administrator=True)
async def marketplace_browse_slash(interaction: discord.Interaction, page: int = 1):
    cog = interaction.client.get_cog('ExtensionMarketplace')
    if cog:
        await interaction.response.defer()
        data = await cog.fetch_extensions()
        if not data or not data.get('extensions'):
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to fetch extensions from marketplace!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.followup.send(embed=embed)
            return
        
        extensions = data['extensions']
        view = ExtensionBrowserView(cog, extensions, page)
        await view.send_page_interaction(interaction)

@discord.app_commands.command(name='marketplace-search', description='Search for extensions')
@discord.app_commands.default_permissions(administrator=True)
async def marketplace_search_slash(interaction: discord.Interaction, query: str):
    cog = interaction.client.get_cog('ExtensionMarketplace')
    if cog:
        await interaction.response.defer()
        data = await cog.fetch_extensions()
        if not data or not data.get('extensions'):
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to fetch extensions from marketplace!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.followup.send(embed=embed)
            return
        
        extensions = data['extensions']
        query_lower = query.lower()
        filtered_extensions = [
            ext for ext in extensions
            if query_lower in ext.get('title', '').lower() or 
               query_lower in ext.get('description', '').lower() or
               query_lower in ext.get('details', '').lower()
        ]
        
        if not filtered_extensions:
            embed = discord.Embed(
                title="🔍 Search Results",
                description=f"No extensions found matching '{query}'",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.followup.send(embed=embed)
            return
        
        view = ExtensionBrowserView(cog, filtered_extensions, 1, f"Search: {query}")
        await view.send_page_interaction(interaction)

@discord.app_commands.command(name='marketplace-install', description='Install an extension by ID')
@discord.app_commands.default_permissions(administrator=True)
async def marketplace_install_slash(interaction: discord.Interaction, extension_id: int):
    cog = interaction.client.get_cog('ExtensionMarketplace')
    if cog:
        await interaction.response.defer()
        data = await cog.fetch_extensions()
        if not data or not data.get('extensions'):
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to fetch extensions from marketplace!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.followup.send(embed=embed)
            return
        
        extension = next((ext for ext in data['extensions'] if ext['id'] == extension_id), None)
        if not extension:
            embed = discord.Embed(
                title="❌ Extension Not Found",
                description=f"No extension found with ID {extension_id}",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.followup.send(embed=embed)
            return
        
        view = InstallConfirmView(cog, extension)
        embed = discord.Embed(
            title="📦 Install Extension",
            description=f"Are you sure you want to install **{extension['title']}**?",
            color=discord.Color.blue()
        )
        embed.add_field(name="Version", value=extension['version'], inline=True)
        embed.add_field(name="Status", value=extension['status'].title(), inline=True)
        embed.add_field(name="File Type", value=extension['fileType'].upper(), inline=True)
        embed.add_field(name="Description", value=extension['description'][:500] + "..." if len(extension['description']) > 500 else extension['description'], inline=False)
        embed.set_footer(text="Made By TheHolyOneZ • This will download and save the extension to your Extensions folder")
        await interaction.followup.send(embed=embed, view=view)

@discord.app_commands.command(name='marketplace-info', description='Get detailed information about an extension')
@discord.app_commands.default_permissions(administrator=True)
async def marketplace_info_slash(interaction: discord.Interaction, extension_id: int):
    cog = interaction.client.get_cog('ExtensionMarketplace')
    if cog:
        await interaction.response.defer()
        data = await cog.fetch_extensions()
        if not data or not data.get('extensions'):
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to fetch extensions from marketplace!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.followup.send(embed=embed)
            return
        
        extension = next((ext for ext in data['extensions'] if ext['id'] == extension_id), None)
        if not extension:
            embed = discord.Embed(
                title="❌ Extension Not Found",
                description=f"No extension found with ID {extension_id}",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.followup.send(embed=embed)
            return
        
        view = ExtensionDetailView(cog, extension)
        await view.show_details_interaction(interaction)

@discord.app_commands.command(name='marketplace-refresh', description='Refresh the extension marketplace cache')
@discord.app_commands.default_permissions(administrator=True)
async def marketplace_refresh_slash(interaction: discord.Interaction):
    cog = interaction.client.get_cog('ExtensionMarketplace')
    if cog:
        await interaction.response.defer()
        data = await cog.fetch_extensions(force_refresh=True)
        if data and data.get('extensions'):
            embed = discord.Embed(
                title="✅ Cache Refreshed",
                description=f"Successfully loaded {len(data['extensions'])} extensions from marketplace!",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Refresh Failed",
                description="Failed to fetch extensions from marketplace!",
                color=discord.Color.red()
            )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ExtensionMarketplace(bot))

"""
you can change the "async def setup"
to a "def setup(bot) to adjust it (make it to a normal extension)

Extra info: async def setup is just the modern/current standard its still a extension
but zygnalbot ext. loader mainly uses older setups like: def setup(bot)
"""