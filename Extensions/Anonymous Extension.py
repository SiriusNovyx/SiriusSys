import discord
from discord.ext import commands
import json
import os
import random
import asyncio
from datetime import datetime
import uuid

class AnonymousExtension(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.confession_channels = {}
        self.anon_chat_pairs = {}
        self.waiting_for_chat = {}
        self.config_path = "Extensions/config/anonymous_config.json"
        self.embed_config_path = "Extensions/config/custom_embed_anon.json"
        self.load_config()
        self.load_embed_config()

    def load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    
                    confession_channels = config.get("confession_channels", {})
                    for guild_id, value in list(confession_channels.items()):
                        if isinstance(value, int):
                            confession_channels[guild_id] = {
                                "channel_id": value,
                                "footer": "Anonymous Confession",
                                "include_timestamp": True
                            }
                    
                    self.confession_channels = confession_channels
                    self.anon_chat_pairs = config.get("anon_chat_pairs", {})
            else:
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                self.save_config()
        except Exception as e:
            print(f"Error loading anonymous config: {e}")

    def save_config(self):
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump({
                    "confession_channels": self.confession_channels,
                    "anon_chat_pairs": self.anon_chat_pairs
                }, f, indent=4)
        except Exception as e:
            print(f"Error saving anonymous config: {e}")

    def load_embed_config(self):
        try:
            if os.path.exists(self.embed_config_path):
                with open(self.embed_config_path, 'r') as f:
                    self.embed_config = json.load(f)
            else:
                self.embed_config = {
                    "confession": {
                        "title": "Anonymous Confession",
                        "description": "Someone has shared a confession!",
                        "color": "0x7289DA",
                        "button_label": "Confess",
                        "button_emoji": "🔒",
                        "button_color": "blurple",
                        "footer": "Anonymous Confession",
                        "include_timestamp": True
                    },
                    "anon_chat": {
                        "title": "Anonymous Chat",
                        "description": "You are now chatting anonymously with someone!",
                        "color": "0x2ECC71",
                        "button_label": "Find Chat Partner",
                        "button_emoji": "👥",
                        "button_color": "green",
                        "auto_delete_channels": True,
                        "chat_timeout_hours": 24
                    }
                }
                os.makedirs(os.path.dirname(self.embed_config_path), exist_ok=True)
                with open(self.embed_config_path, 'w') as f:
                    json.dump(self.embed_config, f, indent=4)
        except Exception as e:
            print(f"Error with embed config: {e}")

    def get_button_color(self, color_name):
        colors = {
            "blurple": discord.ButtonStyle.primary,
            "green": discord.ButtonStyle.success,
            "red": discord.ButtonStyle.danger,
            "grey": discord.ButtonStyle.secondary
        }
        return colors.get(color_name.lower(), discord.ButtonStyle.primary)

    @commands.group(name="confession", aliases=["confess", "anon"], invoke_without_command=True)
    async def confession(self, ctx):
        embed = discord.Embed(
            title="Anonymous Confession System",
            description="Manage anonymous confessions in your server",
            color=int(self.embed_config["confession"]["color"], 16)
        )
        embed.add_field(name="Admin Commands", value="`!confession setup` - Set up confession channel\n`!confession config` - Configure confession settings", inline=False)
        embed.add_field(name="User Commands", value="`!confession send <message>` - Send an anonymous confession", inline=False)
        
        await ctx.send(embed=embed)

    @confession.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_confession(self, ctx):
        view = ConfessionSetupView(self, ctx)
        
        embed = discord.Embed(
            title="Confession System Setup",
            description="Please select a channel for anonymous confessions and configure settings.",
            color=int(self.embed_config["confession"]["color"], 16)
        )
        
        await ctx.send(embed=embed, view=view)

    @confession.command(name="config")
    @commands.has_permissions(administrator=True)
    async def config_confession(self, ctx):
        view = ConfessionConfigView(self, ctx)
        
        embed = discord.Embed(
            title="Confession System Configuration",
            description="Customize how confessions appear in your server.",
            color=int(self.embed_config["confession"]["color"], 16)
        )
        
        await ctx.send(embed=embed, view=view)

    @commands.group(name="anonchat", aliases=["ac"], invoke_without_command=True)
    async def anonchat(self, ctx):
        embed = discord.Embed(
            title="Anonymous Chat System",
            description="Manage anonymous chats in your server",
            color=int(self.embed_config["anon_chat"]["color"], 16)
        )
        embed.add_field(name="Admin Commands", value="`!anonchat setup` - Set up anonymous chat system\n`!anonchat config` - Configure anonymous chat settings", inline=False)
        embed.add_field(name="User Commands", value="`!anonchat end` - End your current anonymous chat", inline=False)
        
        await ctx.send(embed=embed)

    @anonchat.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_anonchat(self, ctx):
        view = AnonChatSetupView(self, ctx)
        
        embed = discord.Embed(
            title="Anonymous Chat System Setup",
            description="Please select a channel for anonymous chat requests and configure settings.",
            color=int(self.embed_config["anon_chat"]["color"], 16)
        )
        
        await ctx.send(embed=embed, view=view)

    @anonchat.command(name="config")
    @commands.has_permissions(administrator=True)
    async def config_anonchat(self, ctx):
        view = AnonChatConfigView(self, ctx)
        
        embed = discord.Embed(
            title="Anonymous Chat System Configuration",
            description="Customize how anonymous chats work in your server.",
            color=int(self.embed_config["anon_chat"]["color"], 16)
        )
        
        await ctx.send(embed=embed, view=view)

    @anonchat.command(name="end")
    async def end_anonchat(self, ctx):
        user_id = str(ctx.author.id)
        
        pair_id = None
        for pid, pair in self.anon_chat_pairs.items():
            if pair.get("user1") == user_id or pair.get("user2") == user_id:
                pair_id = pid
                break
                
        if not pair_id:
            await ctx.reply("You are not in an anonymous chat.")
            return
            
        pair = self.anon_chat_pairs[pair_id]
        other_user_id = pair["user1"] if pair["user2"] == user_id else pair["user2"]
        
        try:
            channel1 = self.bot.get_channel(int(pair["channel1"]))
            channel2 = self.bot.get_channel(int(pair["channel2"]))
            
            if channel1:
                try:
                    await channel1.send("The anonymous chat has ended.")
                except:
                    pass
                    
            if channel2:
                try:
                    await channel2.send("The anonymous chat has ended.")
                except:
                    pass
                
            if self.embed_config["anon_chat"].get("auto_delete_channels", True):
                try:
                    if channel1:
                        await channel1.delete()
                except Exception as e:
                    print(f"Error deleting channel1: {e}")
                    
                try:
                    if channel2:
                        await channel2.delete()
                except Exception as e:
                    print(f"Error deleting channel2: {e}")
                
        except Exception as e:
            print(f"Error ending chat: {e}")
            
        del self.anon_chat_pairs[pair_id]
        self.save_config()
        
        await ctx.reply("Your anonymous chat has been ended.")

    @commands.command(name="anonhelp")
    async def anon_help(self, ctx):
        embed = discord.Embed(
            title="Anonymous Extension Help",
            description="This extension provides anonymous confessions and anonymous chat features.",
            color=0x7289DA
        )
        
        admin_commands = (
            "**Admin Commands:**\n"
            "`!confession setup` - Set up the confession channel with an interactive UI\n"
            "`!confession config` - Configure confession settings (title, color, etc.)\n"
            "`!anonchat setup` - Set up the anonymous chat request channel\n"
            "`!anonchat config` - Configure anonymous chat settings\n"
        )
        embed.add_field(name="Setup & Configuration", value=admin_commands, inline=False)
        
        user_commands = (
            "**User Commands:**\n"
            "`!confession send <message>` - Send an anonymous confession\n"
            "`!anonchat end` - End your current anonymous chat\n"
            "`!anonhelp` - Display this help message\n"
        )
        embed.add_field(name="User Commands", value=user_commands, inline=False)
        
        interactive = (
            "**Interactive Features:**\n"
            "• Click the confession button to submit a confession\n"
            "• Click the chat button to find an anonymous chat partner\n"
            "• Use the End Chat button in your chat channel to end a conversation\n"
        )
        embed.add_field(name="Interactive Features", value=interactive, inline=False)
        
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component:
            return
            
        if interaction.data["custom_id"] == "confession_button":
            await interaction.response.send_modal(
                ConfessionModal(self)
            )
        elif interaction.data["custom_id"] == "anon_chat_button":
            await self.handle_anon_chat_request(interaction)
        elif interaction.data["custom_id"] == "end_anon_chat":
            user_id = str(interaction.user.id)
            
            pair_id = None
            for pid, pair in self.anon_chat_pairs.items():
                if pair.get("user1") == user_id or pair.get("user2") == user_id:
                    pair_id = pid
                    break
                    
            if not pair_id:
                try:
                    await interaction.response.send_message("You are not in an anonymous chat.", ephemeral=True)
                except discord.errors.NotFound:
                    pass
                return
                
            pair = self.anon_chat_pairs[pair_id]
            other_user_id = pair["user1"] if pair["user2"] == user_id else pair["user2"]
            
            try:
                channel1 = self.bot.get_channel(int(pair["channel1"]))
                channel2 = self.bot.get_channel(int(pair["channel2"]))
                
                if channel1:
                    try:
                        await channel1.send("The anonymous chat has ended.")
                    except:
                        pass
                        
                if channel2:
                    try:
                        await channel2.send("The anonymous chat has ended.")
                    except:
                        pass
                    
                if self.embed_config["anon_chat"].get("auto_delete_channels", True):
                    try:
                        if channel1:
                            await channel1.delete()
                    except Exception as e:
                        print(f"Error deleting channel1: {e}")
                        
                    try:
                        if channel2:
                            await channel2.delete()
                    except Exception as e:
                        print(f"Error deleting channel2: {e}")
                    
            except Exception as e:
                print(f"Error ending chat: {e}")
                
            del self.anon_chat_pairs[pair_id]
            self.save_config()
            
            try:
                await interaction.response.send_message("Your anonymous chat has been ended.", ephemeral=True)
            except discord.errors.NotFound:
                pass

    async def handle_anon_chat_request(self, interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)
        
        for pair in self.anon_chat_pairs.values():
            if pair.get("user1") == user_id or pair.get("user2") == user_id:
                await interaction.response.send_message("You are already in an anonymous chat. End it first with `!anonchat end`", ephemeral=True)
                return
        
        current_time = datetime.now().timestamp()
        
        self.waiting_for_chat = {uid: data for uid, data in self.waiting_for_chat.items() 
                                if current_time - data["timestamp"] < 1800}
        
        match_found = False
        match_user_id = None
        
        for waiting_user_id, data in list(self.waiting_for_chat.items()):
            if waiting_user_id != user_id and data["guild_id"] == guild_id:
                match_user_id = waiting_user_id
                del self.waiting_for_chat[waiting_user_id]
                match_found = True
                break
                
        if match_found:
            await interaction.response.send_message("Match found! Creating anonymous chat channels...", ephemeral=True)
            await self.create_anon_chat(interaction.user, self.bot.get_user(int(match_user_id)), interaction.guild)
        else:
            self.waiting_for_chat[user_id] = {"timestamp": current_time, "guild_id": guild_id}
            await interaction.response.send_message("You've been added to the waiting list for an anonymous chat. You'll be notified when a match is found.", ephemeral=True)

    async def create_anon_chat(self, user1, user2, guild):
        try:
            overwrites1 = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user1: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            overwrites2 = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user2: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            channel1 = await guild.create_text_channel(
                f"anonymous-chat-{random.randint(1000, 9999)}",
                overwrites=overwrites1,
                topic="Anonymous Chat - Your messages are being sent to another user anonymously"
            )
            
            channel2 = await guild.create_text_channel(
                f"anonymous-chat-{random.randint(1000, 9999)}",
                overwrites=overwrites2,
                topic="Anonymous Chat - Your messages are being sent to another user anonymously"
            )
            
            pair_id = f"{user1.id}-{user2.id}-{random.randint(1000, 9999)}"
            
            self.anon_chat_pairs[pair_id] = {
                "user1": str(user1.id),
                "user2": str(user2.id),
                "channel1": channel1.id,
                "channel2": channel2.id,
                "guild_id": str(guild.id),
                "created_at": datetime.now().timestamp()
            }
            self.save_config()
            
            config = self.embed_config["anon_chat"]
            embed = discord.Embed(
                title=config["title"],
                description=config["description"],
                color=int(config["color"], 16)
            )
            embed.add_field(name="Instructions", value="Type messages in this channel to chat anonymously. Use `!anonchat end` to end the chat.")
            
            view = discord.ui.View()
            button = discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="End Chat",
                emoji="🚫",
                custom_id="end_anon_chat"
            )
            view.add_item(button)
            
            await channel1.send(embed=embed, view=view)
            await channel2.send(embed=embed, view=view)
            
            try:
                await user1.send(f"Your anonymous chat is ready! Go to {channel1.mention}")
                await user2.send(f"Your anonymous chat is ready! Go to {channel2.mention}")
            except:
                await channel1.send(f"{user1.mention} Your anonymous chat is ready!")
                await channel2.send(f"{user2.mention} Your anonymous chat is ready!")
                
        except Exception as e:
            print(f"Error creating anonymous chat: {e}")
            try:
                await user1.send("There was an error creating your anonymous chat.")
                await user2.send("There was an error creating your anonymous chat.")
            except:
                pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
            
        for pair_id, pair in self.anon_chat_pairs.items():
            if message.channel.id == int(pair["channel1"]):
                target_channel = self.bot.get_channel(int(pair["channel2"]))
                if target_channel:
                    files = [await attachment.to_file() for attachment in message.attachments]
                    
                    embed = discord.Embed(
                        description=message.content if message.content else "",
                        color=int(self.embed_config["anon_chat"]["color"], 16),
                        timestamp=datetime.now()
                    )
                    
                    if files:
                        await target_channel.send(embed=embed, files=files)
                    else:
                        if message.content:
                            await target_channel.send(embed=embed)
                return
                
            elif message.channel.id == int(pair["channel2"]):
                target_channel = self.bot.get_channel(int(pair["channel1"]))
                if target_channel:
                    files = [await attachment.to_file() for attachment in message.attachments]
                    
                    embed = discord.Embed(
                        description=message.content if message.content else "",
                        color=int(self.embed_config["anon_chat"]["color"], 16),
                        timestamp=datetime.now()
                    )
                    
                    if files:
                        await target_channel.send(embed=embed, files=files)
                    else:
                        if message.content:
                            await target_channel.send(embed=embed)
                return

    @confession.command(name="send")
    async def send_confession(self, ctx, *, message: str = None):
        try:
            await ctx.message.delete()
        except:
            pass
            
        if not message:
            await ctx.author.send("Please provide a message to confess.")
            return
            
        guild_id = str(ctx.guild.id)
        if guild_id not in self.confession_channels:
            await ctx.author.send("Confession channel not set up in this server.")
            return
            
        channel_id = self.confession_channels[guild_id]["channel_id"]
        channel = self.bot.get_channel(int(channel_id))
        
        if not channel:
            await ctx.author.send("Confession channel not found. Please contact an admin.")
            return
            
        config = self.embed_config["confession"]
        embed = discord.Embed(
            title=config["title"],
            description=message,
            color=int(config["color"], 16)
        )
        
        if self.confession_channels[guild_id].get("include_timestamp", True):
            embed.timestamp = datetime.now()
            
        footer_text = self.confession_channels[guild_id].get("footer", config.get("footer", "Anonymous Confession"))
        if footer_text:
            embed.set_footer(text=footer_text)
        
        await channel.send(embed=embed)
        await ctx.author.send("Your confession has been sent anonymously!")


class ConfessionSetupView(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.button_channel = None
        self.confession_channel = None
        
        self.add_item(ButtonChannelSelect(cog, self))
        self.add_item(ConfessionChannelSelect(cog, self))
        
    @discord.ui.button(label="Confirm Setup", style=discord.ButtonStyle.success, row=2)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.button_channel or not self.confession_channel:
            await interaction.response.send_message("Please select both channels first!", ephemeral=True)
            return
            
        guild_id = str(interaction.guild_id)
        
        if guild_id not in self.cog.confession_channels:
            self.cog.confession_channels[guild_id] = {}
            
        self.cog.confession_channels[guild_id]["channel_id"] = self.confession_channel.id
        self.cog.confession_channels[guild_id]["button_channel_id"] = self.button_channel.id
        self.cog.confession_channels[guild_id]["footer"] = self.cog.embed_config["confession"].get("footer", "Anonymous Confession")
        self.cog.confession_channels[guild_id]["include_timestamp"] = self.cog.embed_config["confession"].get("include_timestamp", True)
        
        self.cog.save_config()
        
        view = discord.ui.View(timeout=None)
        config = self.cog.embed_config["confession"]
        button = discord.ui.Button(
            style=self.cog.get_button_color(config["button_color"]),
            label=config["button_label"],
            emoji=config["button_emoji"],
            custom_id="confession_button"
        )
        view.add_item(button)
        
        embed = discord.Embed(
            title=config["title"],
            description=f"Click the button below to submit an anonymous confession to {self.confession_channel.mention}.",
            color=int(config["color"], 16)
        )
        
        await self.button_channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"Confession system set up successfully!\n"
            f"• Confession button placed in: {self.button_channel.mention}\n"
            f"• Confessions will be posted in: {self.confession_channel.mention}", 
            ephemeral=True
        )
        
        for item in self.children:
            item.disabled = True
            
        await interaction.message.edit(view=self)


class ButtonChannelSelect(discord.ui.Select):
    def __init__(self, cog, parent_view):
        self.cog = cog
        self.parent_view = parent_view
        
        options = []
        for channel in self.cog.bot.get_guild(parent_view.ctx.guild.id).text_channels:
            if len(options) < 25:
                options.append(discord.SelectOption(
                    label=channel.name,
                    value=str(channel.id),
                    description=f"#{channel.name}"
                ))
        
        super().__init__(
            placeholder="Select channel for confession button...",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )
        
    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        self.parent_view.button_channel = interaction.guild.get_channel(channel_id)
        await interaction.response.send_message(f"Button will be placed in: {self.parent_view.button_channel.mention}", ephemeral=True)


class ConfessionChannelSelect(discord.ui.Select):
    def __init__(self, cog, parent_view):
        self.cog = cog
        self.parent_view = parent_view
        
        options = []
        for channel in self.cog.bot.get_guild(parent_view.ctx.guild.id).text_channels:
            if len(options) < 25:
                options.append(discord.SelectOption(
                    label=channel.name,
                    value=str(channel.id),
                    description=f"#{channel.name}"
                ))
        
        super().__init__(
            placeholder="Select channel for confessions to appear...",
            min_values=1,
            max_values=1,
            options=options,
            row=1
        )
        
    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        self.parent_view.confession_channel = interaction.guild.get_channel(channel_id)
        await interaction.response.send_message(f"Confessions will be posted in: {self.parent_view.confession_channel.mention}", ephemeral=True)


class ConfessionConfigView(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.config = self.cog.embed_config["confession"]
        
    @discord.ui.button(label="Edit Title", style=discord.ButtonStyle.primary, row=0)
    async def edit_title_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ConfigModal(self.cog, "confession", "title", self.config["title"])
        )
        
    @discord.ui.button(label="Edit Description", style=discord.ButtonStyle.primary, row=0)
    async def edit_description_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ConfigModal(self.cog, "confession", "description", self.config["description"])
        )
        
    @discord.ui.button(label="Edit Color", style=discord.ButtonStyle.primary, row=1)
    async def edit_color_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ConfigModal(self.cog, "confession", "color", self.config["color"])
        )
        
    @discord.ui.button(label="Edit Button Label", style=discord.ButtonStyle.primary, row=1)
    async def edit_button_label_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ConfigModal(self.cog, "confession", "button_label", self.config["button_label"])
        )
        
    @discord.ui.button(label="Edit Footer", style=discord.ButtonStyle.primary, row=2)
    async def edit_footer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ConfigModal(self.cog, "confession", "footer", self.config.get("footer", "Anonymous Confession"))
        )
        
    @discord.ui.button(label="Toggle Timestamp", style=discord.ButtonStyle.secondary, row=2)
    async def toggle_timestamp_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.config["include_timestamp"] = not self.config.get("include_timestamp", True)
        
        with open(self.cog.embed_config_path, 'w') as f:
            json.dump(self.cog.embed_config, f, indent=4)
            
        await interaction.response.send_message(f"Timestamp display is now {'enabled' if self.config['include_timestamp'] else 'disabled'}", ephemeral=True)
        
    @discord.ui.button(label="Preview", style=discord.ButtonStyle.success, row=3)
    async def preview_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=self.config["title"],
            description="This is a preview of how confessions will look.",
            color=int(self.config["color"], 16)
        )
        
        if self.config.get("include_timestamp", True):
            embed.timestamp = datetime.now()
            
        if self.config.get("footer"):
            embed.set_footer(text=self.config["footer"])
            
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ChannelSelect(discord.ui.Select):
    def __init__(self, cog, parent_view):
        self.cog = cog
        self.parent_view = parent_view
        
        options = []
        for channel in self.cog.bot.get_guild(parent_view.ctx.guild.id).text_channels:
            if len(options) < 25:  
                options.append(discord.SelectOption(
                    label=channel.name,
                    value=str(channel.id),
                    description=f"#{channel.name}"
                ))
        
        super().__init__(
            placeholder="Select a channel...",
            min_values=1,
            max_values=1,
            options=options
        )
        
    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        self.parent_view.selected_channel = interaction.guild.get_channel(channel_id)
        await interaction.response.send_message(f"Selected channel: {self.parent_view.selected_channel.mention}", ephemeral=True)

class AnonChatSetupView(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.selected_channel = None
        
        self.add_item(ChannelSelect(cog, self))
        
    @discord.ui.button(label="Confirm Setup", style=discord.ButtonStyle.success, row=1)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_channel:
            await interaction.response.send_message("Please select a channel first!", ephemeral=True)
            return
            
        view = discord.ui.View(timeout=None)
        config = self.cog.embed_config["anon_chat"]
        button = discord.ui.Button(
            style=self.cog.get_button_color(config["button_color"]),
            label=config["button_label"],
            emoji=config["button_emoji"],
            custom_id="anon_chat_button"
        )
        view.add_item(button)
        
        embed = discord.Embed(
            title=config["title"],
            description=f"Click the button below to find an anonymous chat partner.",
            color=int(config["color"], 16)
        )
        
        await self.selected_channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"Anonymous chat request button has been added to {self.selected_channel.mention}.", ephemeral=True)
        
        for item in self.children:
            item.disabled = True
            
        await interaction.message.edit(view=self)


class AnonChatConfigView(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.config = self.cog.embed_config["anon_chat"]
        
    @discord.ui.button(label="Edit Title", style=discord.ButtonStyle.primary, row=0)
    async def edit_title_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ConfigModal(self.cog, "anon_chat", "title", self.config["title"])
        )
        
    @discord.ui.button(label="Edit Description", style=discord.ButtonStyle.primary, row=0)
    async def edit_description_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ConfigModal(self.cog, "anon_chat", "description", self.config["description"])
        )
        
    @discord.ui.button(label="Edit Color", style=discord.ButtonStyle.primary, row=1)
    async def edit_color_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ConfigModal(self.cog, "anon_chat", "color", self.config["color"])
        )
        
    @discord.ui.button(label="Edit Button Label", style=discord.ButtonStyle.primary, row=1)
    async def edit_button_label_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ConfigModal(self.cog, "anon_chat", "button_label", self.config["button_label"])
        )
        
    @discord.ui.button(label="Toggle Auto-Delete", style=discord.ButtonStyle.secondary, row=2)
    async def toggle_auto_delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.config["auto_delete_channels"] = not self.config.get("auto_delete_channels", True)
        
        with open(self.cog.embed_config_path, 'w') as f:
            json.dump(self.cog.embed_config, f, indent=4)
            
        await interaction.response.send_message(f"Auto-delete channels is now {'enabled' if self.config['auto_delete_channels'] else 'disabled'}", ephemeral=True)
        
    @discord.ui.button(label="Set Chat Timeout", style=discord.ButtonStyle.secondary, row=2)
    async def set_timeout_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ConfigModal(self.cog, "anon_chat", "chat_timeout_hours", str(self.config.get("chat_timeout_hours", 24)))
        )
        
    @discord.ui.button(label="Preview", style=discord.ButtonStyle.success, row=3)
    async def preview_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=self.config["title"],
            description=self.config["description"],
            color=int(self.config["color"], 16)
        )
        
        embed.add_field(name="Settings", value=
            f"Auto-delete channels: {'✅' if self.config.get('auto_delete_channels', True) else '❌'}\n"
            f"Chat timeout: {self.config.get('chat_timeout_hours', 24)} hours"
        )
            
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ConfigModal(discord.ui.Modal):
    def __init__(self, cog, config_type, field_name, current_value):
        super().__init__(title=f"Edit {field_name.replace('_', ' ').title()}")
        self.cog = cog
        self.config_type = config_type
        self.field_name = field_name
        
        self.value_input = discord.ui.TextInput(
            label=f"New {field_name.replace('_', ' ').title()}",
            style=discord.TextStyle.short if field_name != "description" else discord.TextStyle.paragraph,
            placeholder=f"Enter new {field_name.replace('_', ' ')}...",
            default=current_value,
            required=True,
            max_length=1000 if field_name == "description" else 100
        )
        self.add_item(self.value_input)
        
    async def on_submit(self, interaction: discord.Interaction):
        self.cog.embed_config[self.config_type][self.field_name] = self.value_input.value
        
        with open(self.cog.embed_config_path, 'w') as f:
            json.dump(self.cog.embed_config, f, indent=4)
            
        await interaction.response.send_message(f"{self.field_name.replace('_', ' ').title()} updated successfully!", ephemeral=True)


class ConfessionModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Submit Anonymous Confession")
        self.cog = cog
        
        self.confession = discord.ui.TextInput(
            label="Your Confession",
            style=discord.TextStyle.paragraph,
            placeholder="Type your anonymous confession here...",
            required=True,
            max_length=2000
        )
        self.add_item(self.confession)
        
    async def on_submit(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        if guild_id not in self.cog.confession_channels:
            await interaction.response.send_message("Confession channel not set up in this server.", ephemeral=True)
            return
            
        channel_id = self.cog.confession_channels[guild_id]["channel_id"]
        channel = interaction.client.get_channel(int(channel_id))
        
        if not channel:
            await interaction.response.send_message("Confession channel not found. Please contact an admin.", ephemeral=True)
            return
            
        config = self.cog.embed_config["confession"]
        embed = discord.Embed(
            title=config["title"],
            description=self.confession.value,
            color=int(config["color"], 16)
        )
        
        if self.cog.confession_channels[guild_id].get("include_timestamp", True):
            embed.timestamp = datetime.now()
            
        footer_text = self.cog.confession_channels[guild_id].get("footer", config.get("footer", "Anonymous Confession"))
        if footer_text:
            embed.set_footer(text=footer_text)
        
        await channel.send(embed=embed)
        await interaction.response.send_message("Your confession has been sent anonymously!", ephemeral=True)


async def cleanup_expired_chats(cog):
    while True:
        try:
            current_time = datetime.now().timestamp()
            timeout_seconds = cog.embed_config["anon_chat"].get("chat_timeout_hours", 24) * 3600
            
            expired_pairs = []
            for pair_id, pair in cog.anon_chat_pairs.items():
                if current_time - pair["created_at"] > timeout_seconds:
                    expired_pairs.append(pair_id)
                    
            for pair_id in expired_pairs:
                pair = cog.anon_chat_pairs[pair_id]
                
                try:
                    channel1 = cog.bot.get_channel(int(pair["channel1"]))
                    channel2 = cog.bot.get_channel(int(pair["channel2"]))
                    
                    if channel1:
                        await channel1.send("This anonymous chat has expired and will be closed.")
                    if channel2:
                        await channel2.send("This anonymous chat has expired and will be closed.")
                        
                    if cog.embed_config["anon_chat"].get("auto_delete_channels", True):
                        try:
                            if channel1:
                                await channel1.delete()
                            if channel2:
                                await channel2.delete()
                        except Exception as e:
                            print(f"Error deleting expired channels: {e}")
                            
                except Exception as e:
                    print(f"Error ending expired chat: {e}")
                    
                del cog.anon_chat_pairs[pair_id]
                
            if expired_pairs:
                cog.save_config()
                
        except Exception as e:
            print(f"Error in cleanup task: {e}")
            
        await asyncio.sleep(3600)


def setup(bot):
    cog = AnonymousExtension(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    loop.create_task(cleanup_expired_chats(cog))
    
    return cog


