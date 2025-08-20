"""
CUSTOM LICENSE AGREEMENT FOR ZYGNALBOT EXTENSION
Copyright © 2025 TheHolyOneZ (TheZ)
All Rights Reserved

1. DEFINITIONS
1.1. "Extension" refers to the software files, code, assets, and all associated materials released under this license.
1.2. "Emoji" refers only to image files in formats such as PNG, JPG, GIF, or WebP located in the designated emoji asset folders within the Extension.
1.3. "Authorized User" refers solely to individuals who are actively using the Discord bot known as "ZygnalBot" (case-insensitive) in accordance with its official terms of service.
1.4. "ZygnalID" refers to the unique user identifier assigned by ZygnalBot to its authorized users.

2. GRANT OF LIMITED PERMISSION
2.1. Authorized Users are granted a non-exclusive, non-transferable, and revocable permission to:
    - Edit, replace, or add to the emoji files within the Extension.
2.2. No other rights are granted. All rights not expressly granted are reserved by TheHolyOneZ (TheZ).

3. PROHIBITED ACTIONS
The following actions are strictly forbidden without prior written consent from TheHolyOneZ (TheZ):
3.1. Editing, altering, deleting, renaming, moving, or otherwise modifying any files within the Extension that are not emoji files.
3.2. Altering, obscuring, or removing:
    - The copyright notice contained within this file.
    - Any mention of the names "ZygnalBot", "zygnalbot", "TheHolyOneZ", or "TheZ".
3.3. Distributing, sublicensing, selling, leasing, renting, or otherwise transferring the Extension, in whole or in part, outside of ZygnalBot.
3.4. Using the Extension in any other software or platform without explicit authorization.

4. ENFORCEMENT & CONSEQUENCES
4.1. If any of the names "ZygnalBot", "zygnalbot", "TheHolyOneZ", or "TheZ" are removed, altered, obscured, or tampered with in any way:
    - The violator's ZygnalID will be immediately deactivated and permanently flagged to prevent reactivation.
    - The violator will be banned from any future participation in ZygnalBot services.
    - The violation will be logged and may be shared with other ZygnalBot administrators and services to prevent further abuse.
4.2. No exceptions will be made for accidental or unintentional changes.

5. ACKNOWLEDGMENT
By using, downloading, installing, or modifying this Extension, you acknowledge that you have read, understood, and agree to be bound by the terms of this license.

END OF LICENSE
"""


import discord
from discord.ext import commands
import aiohttp
import json
import os
import asyncio
import logging
from datetime import datetime
import re
import io

logger = logging.getLogger(__name__)

class ExtensionMarketplace(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = "https://zygnalbot.com/extension/api/extensions.php?action=list"
        self.extensions_folder = "Extensions"
        self.zygnal_id_file = "ZygnalID.txt"
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
                    elif response.status == 429:
                        return {"error": "Rate limit exceeded. Please try again in a moment."}
                    else:
                        logger.error(f"API request failed with status {response.status}")
                        return {"error": f"API request failed with status {response.status}"}
        except Exception as e:
            logger.error(f"Error fetching extensions: {e}")
            return {"error": f"Error fetching extensions: {e}"}
    
    async def download_extension(self, extension_data):
        if not self.extensions_folder or not isinstance(self.extensions_folder, str):
            error_msg = "The download file path (Extensions folder) is not configured correctly."
            logger.error(error_msg)
            return None, error_msg
        try:
            zygnal_id = await self.ensure_zygnal_id()
            if not zygnal_id:
                error_msg = "Could not read or generate a ZygnalID. Please check file permissions for ZygnalID.txt."
                logger.error(error_msg)
                return None, error_msg
            query_suffix = f"&zygnalid={zygnal_id}"
            if extension_data.get('customUrl'):
                base_url = extension_data['customUrl']
                if base_url.startswith('http') and zygnal_id:
                    sep = '&' if ('?' in base_url) else '?'
                    download_url = f"{base_url}{sep}zygnalid={zygnal_id}"
                else:
                    download_url = base_url
            else:
                extension_id = extension_data['id']
                download_url = f"https://zygnalbot.com/extension/download.php?id={extension_id}{query_suffix}"
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url, timeout=60) as response:
                    response_text = await response.text()
                    if response.status == 200:
                        if "invalid" in response_text.lower() and "zygnalid" in response_text.lower() or "not activated" in response_text.lower():
                            error_message = (
                                "Your ZygnalID is invalid or not activated. "
                                "Please use the `marketplace myid` command to view your ZygnalID. "
                                "Then, open a ticket in the ZygnalBot support server and provide the ID to have it enabled."
                            )
                            logger.error(f"Download failed: {error_message}")
                            return None, error_message
                        filename = f"{extension_data['title'].replace(' ', '_').lower()}.{extension_data['fileType']}"
                        filename = re.sub(r'[^\w\-_\.]', '', filename)
                        filepath = os.path.join(self.extensions_folder, filename)
                        if not os.path.exists(self.extensions_folder):
                            os.makedirs(self.extensions_folder)
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(response_text)
                        return filepath, "Success"
                    elif response.status == 429:
                        error_message = f"Download failed due to rate limiting. You can download a maximum of 5 files every 2 minutes."
                        logger.error(error_message)
                        return None, error_message
                    else:
                        error_message = f"Download failed with status code: {response.status}."
                        if response_text and not response_text.strip().startswith("<!DOCTYPE html>"):
                            error_message = f"The server returned an error: {response_text}"
                        logger.error(f"Download failed: {error_message}")
                        return None, error_message
        except aiohttp.ClientConnectorError as e:
            error_msg = f"Network connection error: Could not connect to the download server. Details: {e}"
            logger.error(error_msg)
            return None, error_msg
        except asyncio.TimeoutError:
            error_msg = "The download request timed out. The server might be busy or down."
            logger.error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"An unexpected error occurred during download: {e}"
            logger.error(error_msg)
            return None, error_msg

    async def ensure_zygnal_id(self) -> str:
        try:
            if os.path.exists(self.zygnal_id_file):
                with open(self.zygnal_id_file, 'r', encoding='utf-8') as f:
                    val = f.read().strip()
                return val
            import secrets
            alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
            new_id = ''.join(secrets.choice(alphabet) for _ in range(16))
            with open(self.zygnal_id_file, 'w', encoding='utf-8') as f:
                f.write(new_id)
            return new_id
        except Exception as gen_err:
            logger.error(f"Failed to generate/read ZygnalID: {gen_err}")
            return ""

    def _is_valid_zygnal_id(self, value: str) -> bool:
        return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9]{16}", value))
    
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
        await self.ensure_zygnal_id()
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
                  f"`{ctx.prefix}marketplace refresh` - Refresh extension list\n"
                  f"`{ctx.prefix}mp myid` - permission required: be bot owner",
            inline=False
        )
        embed.add_field(
            name="⚡ Quick Actions",
            value="Use the buttons below for quick access to marketplace features!",
            inline=False
        )
        embed.set_footer(text="ZygnalBot • Extension Marketplace v2.0")
        view = MarketplaceMenuView(self)
        await ctx.send(embed=embed, view=view)
    
    async def show_marketplace_menu_slash(self, interaction: discord.Interaction):
        await self.ensure_zygnal_id()
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
        if not data or data.get('error'):
            error_message = data.get('error', "Failed to fetch extensions from marketplace!")
            embed = discord.Embed(
                title="❌ Error",
                description=error_message,
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
        if not data or data.get('error'):
            error_message = data.get('error', "Failed to fetch extensions from marketplace!")
            embed = discord.Embed(
                title="❌ Error",
                description=error_message,
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
        if not data or data.get('error'):
            error_message = data.get('error', "Failed to fetch extensions from marketplace!")
            embed = discord.Embed(
                title="❌ Error",
                description=error_message,
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
        if not data or data.get('error'):
            error_message = data.get('error', "Failed to fetch extensions from marketplace!")
            embed = discord.Embed(
                title="❌ Error",
                description=error_message,
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
            error_message = data.get('error', "Failed to fetch extensions from marketplace!")
            embed = discord.Embed(
                title="❌ Refresh Failed",
                description=error_message,
                color=discord.Color.red()
            )
        embed.set_footer(text="Made By TheHolyOneZ")
        await message.edit(embed=embed)

    @marketplace_group.command(name='myid')
    async def myid(self, ctx):
        bot_owner_id = os.environ.get('BOT_OWNER_ID')
        if not bot_owner_id or str(ctx.author.id) != bot_owner_id:
            await ctx.send("This command can only be used by the bot owner.", delete_after=10)
            return

        zygnal_id = await self.ensure_zygnal_id()
        if zygnal_id:
            embed = discord.Embed(
                title="🔑 Your ZygnalID",
                description=f"This is your unique ZygnalID for the extension marketplace. If an extension fails to download due to an invalid ID, open a support ticket and provide this ID.",
                color=discord.Color.blue()
            )
            embed.add_field(name="ID", value=f"```{zygnal_id}```")
            try:
                await ctx.author.send(embed=embed)
                await ctx.message.add_reaction('✅')
            except discord.Forbidden:
                await ctx.send("I couldn't send you a DM. Please check your privacy settings.", delete_after=10)
        else:
            await ctx.send("❌ Could not read or generate a ZygnalID. Check file permissions for `ZygnalID.txt`.", delete_after=10)

class MarketplaceMenuView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
    
    @discord.ui.button(label='Browse All', style=discord.ButtonStyle.primary, emoji='🔍')
    async def browse_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        data = await self.cog.fetch_extensions()
        if not data or data.get('error'):
            error_message = data.get('error', "Failed to fetch extensions from marketplace!")
            embed = discord.Embed(
                title="❌ Error",
                description=error_message,
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
        if not data or data.get('error'):
            error_message = data.get('error', "Failed to fetch extensions from marketplace!")
            embed = discord.Embed(
                title="❌ Error",
                description=error_message,
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
            error_message = data.get('error', "Failed to fetch extensions from marketplace!")
            embed = discord.Embed(
                title="❌ Refresh Failed",
                description=error_message,
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
        if not data or data.get('error'):
            error_message = data.get('error', "Failed to fetch extensions from marketplace!")
            embed = discord.Embed(
                title="❌ Error",
                description=error_message,
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
            prev_button = discord.ui.Button(label='< Previous', style=discord.ButtonStyle.secondary)
            prev_button.callback = self.previous_page
            self.add_item(prev_button)
        
        if self.page < self.max_pages:
            next_button = discord.ui.Button(label='Next >', style=discord.ButtonStyle.secondary)
            next_button.callback = self.next_page
            self.add_item(next_button)
        
        page_extensions = self.get_page_extensions()
        for ext in page_extensions:
            install_button = discord.ui.Button(
                label=f"Install {ext['title'][:20]}",
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
        
        install_button = discord.ui.Button(label='📦 Install Extension', style=discord.ButtonStyle.success)
        install_button.callback = self.install_extension
        self.add_item(install_button)
        
        if extension.get('customUrl'):
            view_source_button = discord.ui.Button(label='🔗 View Source', style=discord.ButtonStyle.link, url=extension['customUrl'])
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
            details = ext['details']
            if len(details) > 1024:
                embed.add_field(name="📋 Details", value="Details are too long to display and are attached in the file below.", inline=False)
            else:
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
        embed.add_field(name="Description", value=self.extension['description'][:500] + "..." if len(self.extension['description']) > 500 else self.extension['description'], inline=False)
        embed.set_footer(text="Made By TheHolyOneZ • This will download and save the extension to your Extensions folder")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def show_details(self, ctx):
        embed = self.create_detail_embed()
        details_file = None
        details = self.extension.get('details')
        if details and len(details) > 1024:
            details_file = discord.File(
                io.StringIO(details),
                filename=f"{self.extension['title'].replace(' ', '_')}_details.txt"
            )
        await ctx.send(embed=embed, view=self, file=details_file)
    
    async def show_details_interaction(self, interaction: discord.Interaction):
        embed = self.create_detail_embed()
        details_file = None
        details = self.extension.get('details')
        if details and len(details) > 1024:
            details_file = discord.File(
                io.StringIO(details),
                filename=f"{self.extension['title'].replace(' ', '_')}_details.txt"
            )
        await interaction.response.send_message(embed=embed, view=self, file=details_file, ephemeral=True)

class InstallConfirmView(discord.ui.View):
    def __init__(self, cog, extension):
        super().__init__(timeout=60)
        self.cog = cog
        self.extension = extension
    
    @discord.ui.button(label='✅ Confirm Install', style=discord.ButtonStyle.success)
    async def confirm_install(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="📥 Installing Extension...",
            description=f"Downloading **{self.extension['title']}**...",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.edit_original_response(embed=embed, view=None)
        
        filepath, message = await self.cog.download_extension(self.extension)
        
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
                description=f"Failed to download **{self.extension['title']}**.",
                color=discord.Color.red()
            )
            embed.add_field(name="Error Details", value=message, inline=False)
            embed.add_field(name="🔍 Troubleshooting", value="• Check the error details above.\n• Ensure the bot has permissions to write files in its directory.\n• Verify your internet connection.", inline=False)
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.edit_original_response(embed=embed, view=None)
    
    @discord.ui.button(label='❌ Cancel', style=discord.ButtonStyle.danger)
    async def cancel_install(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❌ Installation Cancelled",
            description="Extension installation was cancelled.",
            color=discord.Color.red()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.edit_message(embed=embed, view=None)


@discord.app_commands.command(name='marketplace-browse', description='Browse all available extensions')
@discord.app_commands.default_permissions(administrator=True)
async def marketplace_browse_slash(interaction: discord.Interaction, page: int = 1):
    cog = interaction.client.get_cog('ExtensionMarketplace')
    if cog:
        await interaction.response.defer()
        data = await cog.fetch_extensions()
        if not data or data.get('error'):
            error_message = data.get('error', "Failed to fetch extensions from marketplace!")
            embed = discord.Embed(
                title="❌ Error",
                description=error_message,
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
        if not data or data.get('error'):
            error_message = data.get('error', "Failed to fetch extensions from marketplace!")
            embed = discord.Embed(
                title="❌ Error",
                description=error_message,
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
        if not data or data.get('error'):
            error_message = data.get('error', "Failed to fetch extensions from marketplace!")
            embed = discord.Embed(
                title="❌ Error",
                description=error_message,
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
        if not data or data.get('error'):
            error_message = data.get('error', "Failed to fetch extensions from marketplace!")
            embed = discord.Embed(
                title="❌ Error",
                description=error_message,
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
            error_message = data.get('error', "Failed to fetch extensions from marketplace!")
            embed = discord.Embed(
                title="❌ Refresh Failed",
                description=error_message,
                color=discord.Color.red()
            )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ExtensionMarketplace(bot))
