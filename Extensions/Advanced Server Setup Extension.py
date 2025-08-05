import discord
from discord.ext import commands
import asyncio
import json
import typing
from discord.ui import View, Select, Button, Modal, TextInput

class ServerSetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.setup_sessions = {}
        self.templates = {
            "gaming": {
                "categories": [
                    {"name": "🎮 GENERAL", "channels": [
                        {"name": "📢-announcements", "type": "text", "permissions": "announcement"},
                        {"name": "🤝-welcome", "type": "text"},
                        {"name": "📜-rules", "type": "text"},
                        {"name": "🎮-game-chat", "type": "text"},
                        {"name": "🔎-looking-for-game", "type": "text"},
                        {"name": "General Gaming", "type": "voice", "user_limit": 0},
                        {"name": "Casual Gaming", "type": "voice", "user_limit": 5},
                        {"name": "Competitive", "type": "voice", "user_limit": 5}
                    ]},
                    {"name": "🔫 FPS GAMES", "channels": [
                        {"name": "fps-chat", "type": "text"},
                        {"name": "Valorant", "type": "voice", "user_limit": 5},
                        {"name": "CS:GO", "type": "voice", "user_limit": 5},
                        {"name": "Apex Legends", "type": "voice", "user_limit": 3},
                        {"name": "Call of Duty", "type": "voice", "user_limit": 4},
                        {"name": "Overwatch", "type": "voice", "user_limit": 6}
                    ]},
                    {"name": "🎲 BATTLE ROYALE", "channels": [
                        {"name": "br-chat", "type": "text"},
                        {"name": "Fortnite", "type": "voice", "user_limit": 4},
                        {"name": "PUBG", "type": "voice", "user_limit": 4},
                        {"name": "Warzone", "type": "voice", "user_limit": 4}
                    ]},
                    {"name": "🏆 MOBA & MMO", "channels": [
                        {"name": "moba-chat", "type": "text"},
                        {"name": "League of Legends", "type": "voice", "user_limit": 5},
                        {"name": "Dota 2", "type": "voice", "user_limit": 5},
                        {"name": "World of Warcraft", "type": "voice", "user_limit": 10},
                        {"name": "Final Fantasy XIV", "type": "voice", "user_limit": 8}
                    ]},
                    {"name": "🎵 COMMUNITY", "channels": [
                        {"name": "general-chat", "type": "text"},
                        {"name": "memes", "type": "text"},
                        {"name": "music-requests", "type": "text"},
                        {"name": "Chill Lounge", "type": "voice", "user_limit": 0},
                        {"name": "Music Room", "type": "voice", "user_limit": 0},
                        {"name": "AFK", "type": "voice", "user_limit": 0}
                    ]},
                    {"name": "🔒 ADMIN", "channels": [
                        {"name": "admin-chat", "type": "text"},
                        {"name": "mod-commands", "type": "text"},
                        {"name": "bot-logs", "type": "text"},
                        {"name": "Staff Meeting", "type": "voice", "user_limit": 0}
                    ]}
                ]
            },
            "community": {
                "categories": [
                    {"name": "📢 INFORMATION", "channels": [
                        {"name": "📢-announcements", "type": "text", "permissions": "announcement"},
                        {"name": "🤝-welcome", "type": "text"},
                        {"name": "📜-rules", "type": "text"},
                        {"name": "📌-important-info", "type": "text"},
                        {"name": "🎭-roles", "type": "text"},
                        {"name": "🎁-giveaways", "type": "text"}
                    ]},
                    {"name": "💬 GENERAL", "channels": [
                        {"name": "general-chat", "type": "text"},
                        {"name": "off-topic", "type": "text"},
                        {"name": "memes", "type": "text"},
                        {"name": "selfies", "type": "text"},
                        {"name": "pets", "type": "text"},
                        {"name": "General Lounge", "type": "voice", "user_limit": 0},
                        {"name": "Chill Zone", "type": "voice", "user_limit": 0}
                    ]},
                    {"name": "🎵 MEDIA", "channels": [
                        {"name": "music-chat", "type": "text"},
                        {"name": "art-showcase", "type": "text"},
                        {"name": "video-share", "type": "text"},
                        {"name": "Music Room", "type": "voice", "user_limit": 0},
                        {"name": "Karaoke", "type": "voice", "user_limit": 0},
                        {"name": "Movie Night", "type": "voice", "user_limit": 0}
                    ]},
                    {"name": "🎮 GAMING", "channels": [
                        {"name": "gaming-chat", "type": "text"},
                        {"name": "looking-for-game", "type": "text"},
                        {"name": "Gaming 1", "type": "voice", "user_limit": 5},
                        {"name": "Gaming 2", "type": "voice", "user_limit": 5},
                        {"name": "Gaming 3", "type": "voice", "user_limit": 5}
                    ]},
                    {"name": "🔒 ADMIN", "channels": [
                        {"name": "admin-chat", "type": "text"},
                        {"name": "mod-commands", "type": "text"},
                        {"name": "bot-logs", "type": "text"},
                        {"name": "Staff Meeting", "type": "voice", "user_limit": 0}
                    ]}
                ]
            },
            "education": {
                "categories": [
                    {"name": "📢 INFORMATION", "channels": [
                        {"name": "📢-announcements", "type": "text", "permissions": "announcement"},
                        {"name": "🤝-welcome", "type": "text"},
                        {"name": "📜-rules", "type": "text"},
                        {"name": "📚-resources", "type": "text"}
                    ]},
                    {"name": "💬 GENERAL", "channels": [
                        {"name": "general-chat", "type": "text"},
                        {"name": "introductions", "type": "text"},
                        {"name": "off-topic", "type": "text"},
                        {"name": "Lounge", "type": "voice", "user_limit": 0}
                    ]},
                    {"name": "📚 STUDY ROOMS", "channels": [
                        {"name": "study-chat", "type": "text"},
                        {"name": "homework-help", "type": "text"},
                        {"name": "Study Room 1", "type": "voice", "user_limit": 5},
                        {"name": "Study Room 2", "type": "voice", "user_limit": 5},
                        {"name": "Study Room 3", "type": "voice", "user_limit": 5},
                        {"name": "Study Room 4", "type": "voice", "user_limit": 5},
                        {"name": "Study Room 5", "type": "voice", "user_limit": 5}
                    ]},
                    {"name": "🧪 SUBJECTS", "channels": [
                        {"name": "mathematics", "type": "text"},
                        {"name": "sciences", "type": "text"},
                        {"name": "languages", "type": "text"},
                        {"name": "computer-science", "type": "text"},
                        {"name": "humanities", "type": "text"},
                        {"name": "arts", "type": "text"},
                        {"name": "Math Help", "type": "voice", "user_limit": 0},
                        {"name": "Science Lab", "type": "voice", "user_limit": 0},
                        {"name": "Language Exchange", "type": "voice", "user_limit": 0},
                        {"name": "Coding Session", "type": "voice", "user_limit": 0}
                    ]},
                    {"name": "🔒 ADMIN", "channels": [
                        {"name": "admin-chat", "type": "text"},
                        {"name": "mod-commands", "type": "text"},
                        {"name": "Staff Meeting", "type": "voice", "user_limit": 0}
                    ]}
                ]
            },
            "business": {
                "categories": [
                    {"name": "📢 INFORMATION", "channels": [
                        {"name": "📢-announcements", "type": "text", "permissions": "announcement"},
                        {"name": "🤝-welcome", "type": "text"},
                        {"name": "📜-rules", "type": "text"},
                        {"name": "📊-company-info", "type": "text"}
                    ]},
                    {"name": "💼 GENERAL", "channels": [
                        {"name": "general-chat", "type": "text"},
                        {"name": "introductions", "type": "text"},
                        {"name": "water-cooler", "type": "text"},
                        {"name": "Lounge", "type": "voice", "user_limit": 0}
                    ]},
                    {"name": "🏢 DEPARTMENTS", "channels": [
                        {"name": "marketing", "type": "text"},
                        {"name": "sales", "type": "text"},
                        {"name": "development", "type": "text"},
                        {"name": "hr", "type": "text"},
                        {"name": "finance", "type": "text"},
                        {"name": "Marketing Team", "type": "voice", "user_limit": 0},
                        {"name": "Sales Team", "type": "voice", "user_limit": 0},
                        {"name": "Dev Team", "type": "voice", "user_limit": 0},
                        {"name": "HR Team", "type": "voice", "user_limit": 0},
                        {"name": "Finance Team", "type": "voice", "user_limit": 0}
                    ]},
                    {"name": "🤝 MEETINGS", "channels": [
                        {"name": "meeting-schedule", "type": "text"},
                        {"name": "meeting-notes", "type": "text"},
                        {"name": "Conference Room 1", "type": "voice", "user_limit": 0},
                        {"name": "Conference Room 2", "type": "voice", "user_limit": 0},
                        {"name": "Conference Room 3", "type": "voice", "user_limit": 0},
                        {"name": "Breakout Room 1", "type": "voice", "user_limit": 5},
                        {"name": "Breakout Room 2", "type": "voice", "user_limit": 5}
                    ]},
                    {"name": "🔒 MANAGEMENT", "channels": [
                        {"name": "management-chat", "type": "text"},
                        {"name": "admin-commands", "type": "text"},
                        {"name": "Executive Meeting", "type": "voice", "user_limit": 0}
                    ]}
                ]
            },
            "custom": {
                "categories": [
                    {"name": "📢 INFORMATION", "channels": [
                        {"name": "📢-announcements", "type": "text", "permissions": "announcement"},
                        {"name": "🤝-welcome", "type": "text"},
                        {"name": "📜-rules", "type": "text"}
                    ]},
                    {"name": "💬 GENERAL", "channels": [
                        {"name": "general-chat", "type": "text"},
                        {"name": "off-topic", "type": "text"},
                        {"name": "General Voice", "type": "voice", "user_limit": 0}
                    ]},
                    {"name": "🔒 ADMIN", "channels": [
                        {"name": "admin-chat", "type": "text"},
                        {"name": "mod-commands", "type": "text"},
                        {"name": "Staff Meeting", "type": "voice", "user_limit": 0}
                    ]}
                ]
            }
        }
        
    @commands.command(name="advancedsetup")
    @commands.is_owner()
    async def advanced_setup(self, ctx):
        self.setup_sessions[ctx.author.id] = {
            "step": "template_selection",
            "server_name": "New Server",
            "template": None,
            "categories": [],
            "custom_categories": []
        }
        
        await self.send_template_selection(ctx)
    
    async def send_template_selection(self, ctx):
        view = View(timeout=300)
        template_select = Select(
            placeholder="Select a server template",
            options=[
                discord.SelectOption(label="Gaming Server", value="gaming", description="Perfect for gaming communities", emoji="🎮"),
                discord.SelectOption(label="Community Server", value="community", description="General community server", emoji="💬"),
                discord.SelectOption(label="Educational Server", value="education", description="For study groups and classes", emoji="📚"),
                discord.SelectOption(label="Business Server", value="business", description="For companies and organizations", emoji="💼"),
                discord.SelectOption(label="Custom Server", value="custom", description="Start with minimal channels", emoji="🔧")
            ]
        )
        
        async def template_callback(interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message("This setup is not for you.", ephemeral=True)
            
            template = interaction.data["values"][0]
            self.setup_sessions[ctx.author.id]["template"] = template
            self.setup_sessions[ctx.author.id]["categories"] = self.templates[template]["categories"].copy()
            
            await interaction.response.edit_message(content=f"Selected template: **{template.title()}**", view=None)
            await self.send_server_name_prompt(ctx)
        
        template_select.callback = template_callback
        view.add_item(template_select)
        
        await ctx.send("🚀 **Advanced Server Setup**\nLet's create your perfect server! First, choose a template:", view=view)
    
    async def send_server_name_prompt(self, ctx):
        class ServerNameModal(Modal, title="Server Name"):
            server_name = TextInput(
                label="What should your server be called?",
                placeholder="Enter server name...",
                default="New Server",
                required=True,
                max_length=100
            )
            
            async def on_submit(self, interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("This setup is not for you.", ephemeral=True)
                
                self.cog.setup_sessions[ctx.author.id]["server_name"] = self.server_name.value
                await interaction.response.send_message(f"Server name set to: **{self.server_name.value}**")
                await self.cog.send_category_customization(ctx)
        
        modal = ServerNameModal()
        modal.cog = self
        
        view = View()
        button = Button(label="Set Server Name", style=discord.ButtonStyle.primary)
        
        async def button_callback(interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message("This setup is not for you.", ephemeral=True)
            
            await interaction.response.send_modal(modal)
        
        button.callback = button_callback
        view.add_item(button)
        
        await ctx.send("📝 **Name Your Server**\nWhat would you like to call your new server?", view=view)
    
    async def send_category_customization(self, ctx):
        session = self.setup_sessions[ctx.author.id]
        
        embed = discord.Embed(
            title="🔧 Category Customization",
            description="Your server will include these categories. You can add, remove, or customize them.",
            color=discord.Color.blue()
        )
        
        for i, category in enumerate(session["categories"]):
            channel_count = len(category["channels"])
            text_count = sum(1 for ch in category["channels"] if ch["type"] == "text")
            voice_count = sum(1 for ch in category["channels"] if ch["type"] == "voice")
            
            embed.add_field(
                name=f"{i+1}. {category['name']}",
                value=f"Contains {channel_count} channels ({text_count} text, {voice_count} voice)",
                inline=False
            )
        
        view = View(timeout=300)
        add_category = Button(label="Add Category", style=discord.ButtonStyle.green, emoji="➕")
        
        async def add_category_callback(interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message("This setup is not for you.", ephemeral=True)
            
            await interaction.response.send_modal(self.CategoryModal(self, ctx))
        
        add_category.callback = add_category_callback
        view.add_item(add_category)
        if session["categories"]:
            edit_options = [
                discord.SelectOption(label=f"{i+1}. {cat['name']}", value=str(i))
                for i, cat in enumerate(session["categories"])
            ]
            
            edit_select = Select(
                placeholder="Edit a category",
                options=edit_options
            )
            
            async def edit_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("This setup is not for you.", ephemeral=True)
                
                category_index = int(interaction.data["values"][0])
                session["editing_category"] = category_index
                await interaction.response.send_message(f"Editing category: **{session['categories'][category_index]['name']}**")
                await self.send_category_editor(ctx, category_index)
            
            edit_select.callback = edit_callback
            view.add_item(edit_select)
        continue_button = Button(label="Continue to Server Creation", style=discord.ButtonStyle.primary)
        
        async def continue_callback(interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message("This setup is not for you.", ephemeral=True)
            
            await interaction.response.edit_message(content="Preparing to create your server...", embed=None, view=None)
            await self.send_confirmation(ctx)
        
        continue_button.callback = continue_callback
        view.add_item(continue_button)
        
        await ctx.send(embed=embed, view=view)
    
    class CategoryModal(Modal):
        def __init__(self, cog, ctx):
            super().__init__(title="Add New Category")
            self.cog = cog
            self.ctx = ctx
            
            self.category_name = TextInput(
                label="Category Name",
                placeholder="e.g. GENERAL CHAT",
                required=True,
                max_length=100
            )
            
            self.text_channels = TextInput(
                label="Text Channels (comma separated)",
                placeholder="general, memes, announcements",
                required=False,
                style=discord.TextStyle.paragraph
            )
            
            self.voice_channels = TextInput(
                label="Voice Channels (comma separated)",
                placeholder="General Voice, Gaming, Music",
                required=False,
                style=discord.TextStyle.paragraph
            )
            
            self.add_item(self.category_name)
            self.add_item(self.text_channels)
            self.add_item(self.voice_channels)
        
        async def on_submit(self, interaction):
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message("This setup is not for you.", ephemeral=True)
            
            category = {
                "name": self.category_name.value,
                "channels": []
            }
            if self.text_channels.value:
                text_channel_names = [name.strip() for name in self.text_channels.value.split(",")]
                for name in text_channel_names:
                    if name:
                        category["channels"].append({
                            "name": name,
                            "type": "text"
                        })
            if self.voice_channels.value:
                voice_channel_names = [name.strip() for name in self.voice_channels.value.split(",")]
                for name in voice_channel_names:
                    if name:
                        category["channels"].append({
                            "name": name,
                            "type": "voice",
                            "user_limit": 0
                        })
            
            self.cog.setup_sessions[self.ctx.author.id]["categories"].append(category)
            
            await interaction.response.send_message(f"Added category: **{self.category_name.value}** with {len(category['channels'])} channels")
            await self.cog.send_category_customization(self.ctx)
    
    async def send_category_editor(self, ctx, category_index):
        
        session = self.setup_sessions[ctx.author.id]
        category = session["categories"][category_index]
        
        embed = discord.Embed(
            title=f"Editing Category: {category['name']}",
            description="Here are the channels in this category:",
            color=discord.Color.gold()
        )
        
        for i, channel in enumerate(category["channels"]):
            channel_type = "Text Channel" if channel["type"] == "text" else "Voice Channel"
            user_limit = f" (Limit: {channel['user_limit']})" if channel["type"] == "voice" and "user_limit" in channel else ""
            embed.add_field(
                name=f"{i+1}. {channel['name']}",
                value=f"{channel_type}{user_limit}",
                inline=True
            )
        
        view = View(timeout=300)
        
        rename_button = Button(label="Rename Category", style=discord.ButtonStyle.primary)
        
        async def rename_callback(interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message("This setup is not for you.", ephemeral=True)
            
            modal = Modal(title="Rename Category")
            name_input = TextInput(
                label="New Category Name",
                placeholder="Enter new name...",
                default=category["name"],
                required=True
            )
            modal.add_item(name_input)
            
            async def modal_callback(interaction):
                category["name"] = name_input.value
                await interaction.response.send_message(f"Category renamed to: **{name_input.value}**")
                await self.send_category_editor(ctx, category_index)
            
            modal.on_submit = modal_callback
            await interaction.response.send_modal(modal)
        
        rename_button.callback = rename_callback
        view.add_item(rename_button)
        
        add_channel = Button(label="Add Channel", style=discord.ButtonStyle.green)
        
        async def add_channel_callback(interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message("This setup is not for you.", ephemeral=True)
            
            modal = Modal(title="Add Channel")
            name_input = TextInput(
                label="Channel Name",
                placeholder="Enter channel name...",
                required=True
            )
            
            type_select = Select(
                placeholder="Channel Type",
                options=[
                    discord.SelectOption(label="Text Channel", value="text"),
                    discord.SelectOption(label="Voice Channel", value="voice")
                ]
            )
            
            limit_input = TextInput(
                label="User Limit (Voice only, 0 for unlimited)",
                placeholder="Enter a number...",
                default="0",
                required=False
            )
            
            modal.add_item(name_input)
            
            
            async def modal_callback(interaction):
                new_channel = {
                    "name": name_input.value,
                    "type": "text"  
                }
                
                await interaction.response.send_message(
                    content=f"Added {new_channel['type']} channel: **{new_channel['name']}**",
                    view=channel_type_view
                )
            
            modal.on_submit = modal_callback
            
            channel_type_view = View()
            
            text_button = Button(label="Text Channel", style=discord.ButtonStyle.primary)
            voice_button = Button(label="Voice Channel", style=discord.ButtonStyle.secondary)
            
            async def text_callback(interaction):
                new_channel = {
                    "name": name_input.value,
                    "type": "text"
                }
                category["channels"].append(new_channel)
                await interaction.response.edit_message(content=f"Added text channel: **{new_channel['name']}**", view=None)
                await self.send_category_editor(ctx, category_index)
            
            async def voice_callback(interaction):
                limit_modal = Modal(title="Voice Channel User Limit")
                limit_input = TextInput(
                    label="User Limit (0 for unlimited)",
                    placeholder="Enter a number...",
                    default="0",
                    required=True
                )
                limit_modal.add_item(limit_input)
                
                async def limit_callback(interaction):
                    try:
                        user_limit = int(limit_input.value)
                        if user_limit < 0:
                            user_limit = 0
                    except ValueError:
                        user_limit = 0
                    
                    new_channel = {
                        "name": name_input.value,
                        "type": "voice",
                        "user_limit": user_limit
                    }
                    category["channels"].append(new_channel)
                    await interaction.response.send_message(f"Added voice channel: **{new_channel['name']}** (Limit: {user_limit})")
                    await self.send_category_editor(ctx, category_index)
                
                limit_modal.on_submit = limit_callback
                await interaction.response.send_modal(limit_modal)
            
            text_button.callback = text_callback
            voice_button.callback = voice_callback
            
            channel_type_view.add_item(text_button)
            channel_type_view.add_item(voice_button)
            
            await interaction.response.send_modal(modal)
        
        add_channel.callback = add_channel_callback
        view.add_item(add_channel)
        if category["channels"]:
            remove_options = [
                discord.SelectOption(label=f"{i+1}. {ch['name']}", value=str(i))
                for i, ch in enumerate(category["channels"])
            ]
            
            remove_select = Select(
                placeholder="Remove a channel",
                options=remove_options
            )
            
            async def remove_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("This setup is not for you.", ephemeral=True)
                
                channel_index = int(interaction.data["values"][0])
                removed_channel = category["channels"].pop(channel_index)
                await interaction.response.send_message(f"Removed channel: **{removed_channel['name']}**")
                await self.send_category_editor(ctx, category_index)
            
            remove_select.callback = remove_callback
            view.add_item(remove_select)
        delete_button = Button(label="Delete Category", style=discord.ButtonStyle.danger)
        
        async def delete_callback(interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message("This setup is not for you.", ephemeral=True)
            
            confirm_view = View()
            yes_button = Button(label="Yes, Delete", style=discord.ButtonStyle.danger)
            no_button = Button(label="No, Keep It", style=discord.ButtonStyle.secondary)
            
            async def yes_callback(interaction):
                session["categories"].pop(category_index)
                await interaction.response.edit_message(content=f"Category **{category['name']}** has been deleted.", view=None)
                await self.send_category_customization(ctx)
            
            async def no_callback(interaction):
                await interaction.response.edit_message(content="Category deletion cancelled.", view=None)
                await self.send_category_editor(ctx, category_index)
            
            yes_button.callback = yes_callback
            no_button.callback = no_callback
            
            confirm_view.add_item(yes_button)
            confirm_view.add_item(no_button)
            
            await interaction.response.send_message(f"Are you sure you want to delete the category **{category['name']}**?", view=confirm_view)
        
        delete_button.callback = delete_callback
        view.add_item(delete_button)
        back_button = Button(label="Back to Categories", style=discord.ButtonStyle.secondary)
        
        async def back_callback(interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message("This setup is not for you.", ephemeral=True)
            
            await interaction.response.edit_message(content="Returning to category overview...", embed=None, view=None)
            await self.send_category_customization(ctx)
        
        back_button.callback = back_callback
        view.add_item(back_button)
        
        await ctx.send(embed=embed, view=view)
    
    async def send_confirmation(self, ctx):
        session = self.setup_sessions[ctx.author.id]
        
        embed = discord.Embed(
            title="🚀 Server Creation Summary",
            description=f"You're about to create a new server with the following setup:",
            color=discord.Color.green()
        )
        
        embed.add_field(name="Server Name", value=session["server_name"], inline=False)
        embed.add_field(name="Template", value=session["template"].title(), inline=False)
        
        category_count = len(session["categories"])
        total_channels = sum(len(category["channels"]) for category in session["categories"])
        text_channels = sum(
            sum(1 for channel in category["channels"] if channel["type"] == "text")
            for category in session["categories"]
        )
        voice_channels = sum(
            sum(1 for channel in category["channels"] if channel["type"] == "voice")
            for category in session["categories"]
        )
        
        embed.add_field(name="Categories", value=str(category_count), inline=True)
        embed.add_field(name="Total Channels", value=str(total_channels), inline=True)
        embed.add_field(name="Channel Types", value=f"{text_channels} text, {voice_channels} voice", inline=True)
        
        view = View(timeout=300)
        create_button = Button(label="Create Server", style=discord.ButtonStyle.success, emoji="✅")
        
        async def create_callback(interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message("This setup is not for you.", ephemeral=True)
            
            await interaction.response.edit_message(content="🔨 Creating your server... This may take a while depending on the number of channels.", embed=None, view=None)
            await self.setup_current_server(ctx)
        
        create_button.callback = create_callback
        view.add_item(create_button)
        
        edit_button = Button(label="Edit Setup", style=discord.ButtonStyle.primary)
        
        async def edit_callback(interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message("This setup is not for you.", ephemeral=True)
            
            await interaction.response.edit_message(content="Returning to category customization...", embed=None, view=None)
            await self.send_category_customization(ctx)
        
        edit_button.callback = edit_callback
        view.add_item(edit_button)
        cancel_button = Button(label="Cancel", style=discord.ButtonStyle.danger)
        
        async def cancel_callback(interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message("This setup is not for you.", ephemeral=True)
            
            del self.setup_sessions[ctx.author.id]
            await interaction.response.edit_message(content="Server creation cancelled.", embed=None, view=None)
        
        cancel_button.callback = cancel_callback
        view.add_item(cancel_button)
        
        await ctx.send(embed=embed, view=view)
    
    async def setup_current_server(self, ctx):
        session = self.setup_sessions[ctx.author.id]
        guild = ctx.guild
        
        if not guild:
            return await ctx.send("This command must be used in a server.")
        
        if not ctx.author.guild_permissions.administrator:
            return await ctx.send("You need administrator permissions to set up this server.")
        
        try:
            confirm_msg = await ctx.send(f"⚠️ This will modify your current server '{guild.name}'. Are you sure you want to continue?")
            await confirm_msg.add_reaction("✅")
            await confirm_msg.add_reaction("❌")
            
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_msg.id
            
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
                if str(reaction.emoji) == "❌":
                    return await ctx.send("Server setup cancelled.")
            except asyncio.TimeoutError:
                return await ctx.send("Server setup timed out.")
            progress_message = await ctx.send(f"Setting up server structure... (0/{len(session['categories'])} categories)")
            
            for i, category_data in enumerate(session["categories"]):
                category = await guild.create_category(category_data["name"])
                for channel_data in category_data["channels"]:
                    try:
                        if channel_data["type"] == "text":
                            channel = await guild.create_text_channel(
                                name=channel_data["name"],
                                category=category
                            )
                            if "permissions" in channel_data and channel_data["permissions"] == "announcement":
                                await channel.set_permissions(guild.default_role, send_messages=False)
                                
                        elif channel_data["type"] == "voice":
                            user_limit = channel_data.get("user_limit", 0)
                            await guild.create_voice_channel(
                                name=channel_data["name"],
                                category=category,
                                user_limit=user_limit
                            )
                    except discord.HTTPException as e:
                        await ctx.send(f"Error creating channel {channel_data['name']}: {e}")
                await progress_message.edit(content=f"Setting up server structure... ({i+1}/{len(session['categories'])} categories)")
                await asyncio.sleep(1)
            
            await ctx.send(f"✅ Server **{guild.name}** has been successfully set up with {len(session['categories'])} categories and {sum(len(category['channels']) for category in session['categories'])} channels!")
            del self.setup_sessions[ctx.author.id]
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to manage channels in this server.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ An error occurred while setting up the server: {e}")

    
    @commands.command(name="savetemplate")
    @commands.is_owner()
    async def save_template(self, ctx, template_name: str):
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        
        template = {
            "categories": []
        }
        
        for category in ctx.guild.categories:
            category_data = {
                "name": category.name,
                "channels": []
            }
            
            for channel in category.text_channels:
                channel_data = {
                    "name": channel.name,
                    "type": "text"
                }
                
                if isinstance(channel, discord.TextChannel) and channel.is_news():
                    channel_data["permissions"] = "announcement"
                
                category_data["channels"].append(channel_data)
            
            for channel in category.voice_channels:
                channel_data = {
                    "name": channel.name,
                    "type": "voice",
                    "user_limit": channel.user_limit
                }
                category_data["channels"].append(channel_data)
            
            template["categories"].append(category_data)
        
        self.templates[template_name] = template
        
        await ctx.send(f"✅ Template **{template_name}** has been saved with {len(template['categories'])} categories and {sum(len(category['channels']) for category in template['categories'])} channels!")

def setup(bot):
    
    cog = ServerSetupCog(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog


