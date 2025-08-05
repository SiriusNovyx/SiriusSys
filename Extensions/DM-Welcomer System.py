import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
from typing import Optional, Dict, Any
import aiofiles
from datetime import datetime

class DMWelcomerSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/dm_welcomer_config.json"
        self.config = self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading DM Welcomer config: {e}")
        return {}
    
    def save_config(self):
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving DM Welcomer config: {e}")
    
    def get_guild_config(self, guild_id: int) -> Dict[str, Any]:
        
        guild_str = str(guild_id)
        if guild_str not in self.config:
            self.config[guild_str] = {
                "enabled": False,
                "welcome_data": None,
                "stats": {
                    "total_sent": 0,
                    "total_failed": 0,
                    "last_sent": None
                }
            }
            self.save_config()
        return self.config[guild_str]
    
    async def is_admin(self, ctx_or_interaction) -> bool:
        
        if hasattr(ctx_or_interaction, 'user'):
            member = ctx_or_interaction.user
        else:
            member = ctx_or_interaction.author
        return member.guild_permissions.administrator or member.guild_permissions.manage_guild

    @commands.Cog.listener()
    async def on_member_join(self, member):
        
        if member.bot:
            return
            
        guild_config = self.get_guild_config(member.guild.id)
        
        if not guild_config["enabled"] or not guild_config["welcome_data"]:
            return
        
        try:
            welcome_data = guild_config["welcome_data"]
            

            def replace_placeholders(text):
                if not text:
                    return text
                

                replacements = {
                    "{user}": str(member),
                    "{username}": member.name,
                    "{display_name}": member.display_name,
                    "{server}": member.guild.name,
                    "{member_count}": str(member.guild.member_count),
                    "{user.avatar_url}": str(member.display_avatar.url),
                    "{server.icon_url}": str(member.guild.icon.url) if member.guild.icon else ""
                }
                
                result = text
                for placeholder, value in replacements.items():
                    result = result.replace(placeholder, value)
                
                return result
            

            def is_valid_url(url):
                if not url or url == "":
                    return False
                try:

                    return url.startswith(('http://', 'https://')) and '.' in url and len(url) > 10
                except:
                    return False
            

            if "embed" in welcome_data:
                embed_data = welcome_data["embed"]
                embed = discord.Embed()
                

                if "title" in embed_data and embed_data["title"]:
                    embed.title = replace_placeholders(embed_data["title"])
                

                if "description" in embed_data and embed_data["description"]:
                    embed.description = replace_placeholders(embed_data["description"])
                

                if "color" in embed_data:
                    try:
                        color_value = embed_data["color"]
                        if isinstance(color_value, str):
                            if color_value.startswith("0x"):
                                embed.color = discord.Color(int(color_value, 16))
                            elif color_value.startswith("#"):
                                embed.color = discord.Color(int(color_value[1:], 16))
                            else:

                                embed.color = discord.Color(int(color_value, 16))
                        else:
                            embed.color = discord.Color(color_value)
                    except Exception as e:
                        print(f"Color parsing error: {e}")
                        embed.color = discord.Color.blue()
                

                if "thumbnail" in embed_data and embed_data["thumbnail"]:
                    thumbnail_url = replace_placeholders(embed_data["thumbnail"])
                    print(f"Thumbnail URL after replacement: {thumbnail_url}")
                    if is_valid_url(thumbnail_url):
                        try:
                            embed.set_thumbnail(url=thumbnail_url)
                        except Exception as e:
                            print(f"Thumbnail error: {e}")
                    else:
                        print(f"Invalid thumbnail URL: {thumbnail_url}")
                

                if "image" in embed_data and embed_data["image"]:
                    image_url = replace_placeholders(embed_data["image"])
                    print(f"Image URL after replacement: {image_url}")
                    if is_valid_url(image_url):
                        try:
                            embed.set_image(url=image_url)
                        except Exception as e:
                            print(f"Image error: {e}")
                    else:
                        print(f"Invalid image URL: {image_url}")
                

                if "footer" in embed_data:
                    footer_data = embed_data["footer"]
                    footer_text = replace_placeholders(footer_data.get("text", "")) if footer_data.get("text") else ""
                    footer_icon = replace_placeholders(footer_data.get("icon_url", "")) if footer_data.get("icon_url") else ""
                    

                    if footer_icon and not is_valid_url(footer_icon):
                        footer_icon = ""
                    
                    try:
                        if footer_icon:
                            embed.set_footer(text=footer_text, icon_url=footer_icon)
                        else:
                            embed.set_footer(text=footer_text)
                    except Exception as e:
                        print(f"Footer error: {e}")
                        embed.set_footer(text=footer_text)
                

                if "fields" in embed_data and isinstance(embed_data["fields"], list):
                    for field in embed_data["fields"]:
                        try:
                            field_name = replace_placeholders(field.get("name", ""))[:256]
                            field_value = replace_placeholders(field.get("value", ""))[:1024]
                            field_inline = field.get("inline", True)
                            
                            if field_name and field_value:
                                embed.add_field(
                                    name=field_name,
                                    value=field_value,
                                    inline=field_inline
                                )
                        except Exception as e:
                            print(f"Field error: {e}")
                            continue
                

                current_footer_text = embed.footer.text if embed.footer else ""
                if not current_footer_text:
                    embed.set_footer(text="Made By TheHolyOneZ")
                elif "Made By TheHolyOneZ" not in current_footer_text:
                    footer_icon = embed.footer.icon_url if embed.footer else None
                    new_footer_text = f"{current_footer_text} • Made By TheHolyOneZ"
                    try:
                        if footer_icon:
                            embed.set_footer(text=new_footer_text, icon_url=footer_icon)
                        else:
                            embed.set_footer(text=new_footer_text)
                    except:
                        embed.set_footer(text=new_footer_text)
                

                await member.send(embed=embed)
            

            elif "message" in welcome_data:
                message = replace_placeholders(welcome_data["message"])
                await member.send(message)
            

            guild_config["stats"]["total_sent"] += 1
            guild_config["stats"]["last_sent"] = datetime.now().isoformat()
            self.save_config()
            
        except discord.Forbidden:
            print(f"Cannot send DM to {member.name} - DMs disabled")
            guild_config["stats"]["total_failed"] += 1
            self.save_config()
        except discord.HTTPException as e:
            print(f"Discord HTTP Error sending DM welcome to {member.name}: {e}")
            guild_config["stats"]["total_failed"] += 1
            self.save_config()
        except Exception as e:
            print(f"Error sending DM welcome to {member.name}: {e}")
            guild_config["stats"]["total_failed"] += 1
            self.save_config()


    @commands.hybrid_command(name="dm_welcome")
    @app_commands.describe(action="Choose an action to perform")
    async def dm_welcome(self, ctx, action: Optional[str] = None):
        
        if not await self.is_admin(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator or Manage Server permissions to use this command.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        if action and action.lower() == "toggle":
            await self.toggle_dm_welcome(ctx)
        elif action and action.lower() == "status":
            await self.show_status(ctx)
        else:
            await self.show_setup_menu(ctx)

    async def show_setup_menu(self, ctx):
        
        guild_config = self.get_guild_config(ctx.guild.id)
        
        embed = discord.Embed(
            title="🔔 DM Welcome System",
            description="Configure personalized welcome messages sent directly to new members via DM.",
            color=discord.Color.blue()
        )
        
        status_emoji = "🟢" if guild_config["enabled"] else "🔴"
        embed.add_field(
            name="Current Status",
            value=f"{status_emoji} {'Enabled' if guild_config['enabled'] else 'Disabled'}",
            inline=True
        )
        
        embed.add_field(
            name="Messages Sent",
            value=f"✅ {guild_config['stats']['total_sent']}\n❌ {guild_config['stats']['total_failed']} failed",
            inline=True
        )
        
        embed.add_field(
            name="Configuration",
            value="✅ Configured" if guild_config["welcome_data"] else "❌ Not configured",
            inline=True
        )
        
        embed.add_field(
            name="📋 Available Commands",
            value=(
                "`!dm_welcome toggle` - Enable/disable the system\n"
                "`!dm_welcome status` - View current status\n"
                "`!dm_welcome setup` - Configure welcome message"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎯 Features",
            value=(
                "• Customizable embed messages\n"
                "• Placeholder support ({user}, {server}, etc.)\n"
                "• JSON configuration import\n"
                "• Statistics tracking\n"
                "• Easy toggle on/off"
            ),
            inline=False
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        
        view = DMWelcomeSetupView(self, ctx.guild.id)
        await ctx.send(embed=embed, view=view)

    async def toggle_dm_welcome(self, ctx):
        
        guild_config = self.get_guild_config(ctx.guild.id)
        guild_config["enabled"] = not guild_config["enabled"]
        self.save_config()
        
        status = "enabled" if guild_config["enabled"] else "disabled"
        color = discord.Color.green() if guild_config["enabled"] else discord.Color.red()
        emoji = "🟢" if guild_config["enabled"] else "🔴"
        
        embed = discord.Embed(
            title=f"{emoji} DM Welcome System {status.title()}",
            description=f"The DM Welcome system has been **{status}** for this server.",
            color=color
        )
        
        if guild_config["enabled"] and not guild_config["welcome_data"]:
            embed.add_field(
                name="⚠️ Configuration Required",
                value="The system is enabled but no welcome message is configured. Use the setup command to configure it.",
                inline=False
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)

    async def show_status(self, ctx):
        
        guild_config = self.get_guild_config(ctx.guild.id)
        
        embed = discord.Embed(
            title="📊 DM Welcome System Status",
            color=discord.Color.blue()
        )
        

        status_emoji = "🟢" if guild_config["enabled"] else "🔴"
        embed.add_field(
            name="System Status",
            value=f"{status_emoji} {'Enabled' if guild_config['enabled'] else 'Disabled'}",
            inline=True
        )
        

        config_emoji = "✅" if guild_config["welcome_data"] else "❌"
        embed.add_field(
            name="Configuration",
            value=f"{config_emoji} {'Configured' if guild_config['welcome_data'] else 'Not Configured'}",
            inline=True
        )
        

        embed.add_field(
            name="Statistics",
            value=f"📤 Sent: {guild_config['stats']['total_sent']}\n❌ Failed: {guild_config['stats']['total_failed']}",
            inline=True
        )
        

        if guild_config['stats']['last_sent']:
            last_sent = datetime.fromisoformat(guild_config['stats']['last_sent'])
            embed.add_field(
                name="Last Message Sent",
                value=f"<t:{int(last_sent.timestamp())}:R>",
                inline=True
            )
        

        if guild_config["welcome_data"]:
            preview_embed = discord.Embed(
                title="📋 Current Welcome Message Preview",
                description="This is how the welcome message will look:",
                color=discord.Color.green()
            )
            

            welcome_data = guild_config["welcome_data"]
            if "embed" in welcome_data:
                embed_data = welcome_data["embed"]
                preview_text = f"**Title:** {embed_data.get('title', 'None')}\n"
                preview_text += f"**Description:** {embed_data.get('description', 'None')[:100]}{'...' if len(str(embed_data.get('description', ''))) > 100 else ''}\n"
                preview_text += f"**Fields:** {len(embed_data.get('fields', []))}\n"
                preview_text += f"**Color:** {embed_data.get('color', 'Default')}"
                
                preview_embed.add_field(
                    name="Embed Configuration",
                    value=preview_text,
                    inline=False
                )
            elif "message" in welcome_data:
                preview_embed.add_field(
                    name="Text Message",
                    value=welcome_data["message"][:200] + ("..." if len(welcome_data["message"]) > 200 else ""),
                    inline=False
                )
            
            embed.add_field(
                name="Current Configuration",
                value="Use the buttons below to view or modify",
                inline=False
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        
        view = DMWelcomeStatusView(self, ctx.guild.id)
        await ctx.send(embed=embed, view=view)

class DMWelcomeSetupView(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="📁 Upload JSON Config", style=discord.ButtonStyle.primary, emoji="📁")
    async def upload_config(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        embed = discord.Embed(
            title="📁 Upload JSON Configuration",
            description="Upload a JSON file with your welcome message configuration.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📤 How to Upload",
            value=(
                "1. Create your JSON file using one of the examples below\n"
                "2. Click the 'Upload File' button below\n"
                "3. Select your JSON file\n"
                "4. The bot will automatically configure your welcome message"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Supported Placeholders",
            value=(
                "`{user}` - Full user mention\n"
                "`{username}` - Username only\n"
                "`{display_name}` - Display name\n"
                "`{server}` - Server name\n"
                "`{member_count}` - Total member count"
            ),
            inline=False
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        
        view = UploadConfigView(self.cog, self.guild_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="📋 Simple Example", style=discord.ButtonStyle.secondary, emoji="📋")
    async def simple_example(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        example = {
            "embed": {
                "title": "Welcome to {server}!",
                "description": "Hello {user}! Welcome to our amazing server. We're glad to have you here!\n\nYou are our {member_count}th member!",
                "color": "0x00ff00",
                "thumbnail": "{user.avatar_url}",
                "footer": {
                    "text": "Welcome to {server}"
                }
            }
        }
        
        embed = discord.Embed(
            title="📋 Simple Welcome Message Example",
            description="Here's a basic example of a welcome message configuration:",
            color=discord.Color.green()
        )
        
        json_text = json.dumps(example, indent=2)
        embed.add_field(
            name="JSON Configuration",
            value=f"```json\n{json_text}\n```",
            inline=False
        )
        
        embed.add_field(
            name="💡 What this creates:",
            value=(
                "• A green embed with a welcome title\n"
                "• Personal greeting with user mention\n"
                "• User's avatar as thumbnail\n"
                "• Member count in description\n"
                "• Simple footer"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Safe Placeholders:",
            value=(
                "`{user}` - User mention\n"
                "`{username}` - Username only\n"
                "`{display_name}` - Display name\n"
                "`{server}` - Server name\n"
                "`{member_count}` - Member count\n"
                "`{user.avatar_url}` - User's avatar URL"
            ),
            inline=False
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎨 Advanced Example", style=discord.ButtonStyle.secondary, emoji="🎨")
    async def advanced_example(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        example = {
            "embed": {
                "title": "🎉 Welcome to {server}!",
                "description": "Hey there {display_name}! We're excited to have you join our community of {member_count} members!",
                "color": "0x7289da",
                "thumbnail": "{user.avatar_url}",
                "fields": [
                    {
                        "name": "📜 Server Rules",
                        "value": "Please read our rules in the rules channel",
                        "inline": True
                    },
                    {
                        "name": "💬 Get Started",
                        "value": "Introduce yourself and say hello!",
                        "inline": True
                    },
                    {
                        "name": "🎮 Have Fun",
                        "value": "Join our gaming sessions and community events!",
                        "inline": False
                    },
                    {
                        "name": "📊 Server Stats",
                        "value": "You are member #{member_count} in {server}",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "Welcome to {server} • Made By TheHolyOneZ",
                    "icon_url": "{server.icon_url}"
                }
            }
        }
        
        embed = discord.Embed(
            title="🎨 Advanced Welcome Message Example",
            description="Here's a more detailed example with multiple fields and customization:",
            color=discord.Color.purple()
        )
        
        json_text = json.dumps(example, indent=2)

        if len(json_text) > 1000:
            parts = [json_text[i:i+1000] for i in range(0, len(json_text), 1000)]
            for i, part in enumerate(parts):
                embed.add_field(
                    name=f"JSON Configuration (Part {i+1})",
                    value=f"```json\n{part}\n```",
                    inline=False
                )
        else:
            embed.add_field(
                name="JSON Configuration",
                value=f"```json\n{json_text}\n```",
                inline=False
            )
        
        embed.add_field(
            name="🌟 Features in this example:",
            value=(
                "• Custom color and emojis\n"
                "• Multiple information fields\n"
                "• User avatar as thumbnail\n"
                "• Server icon in footer\n"
                "• Dynamic member count\n"
                "• Inline and full-width fields"
            ),
            inline=False
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, ephemeral=True)


    @discord.ui.button(label="💬 Text-Only Example", style=discord.ButtonStyle.secondary, emoji="💬")
    async def text_example(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        example = {
            "message": "Hello {user}! 👋\n\nWelcome to {server}! We're thrilled to have you as our {member_count}th member.\n\nFeel free to introduce yourself and don't hesitate to ask if you have any questions. Enjoy your stay! 🎉"
        }
        
        embed = discord.Embed(
            title="💬 Text-Only Welcome Message Example",
            description="For a simpler approach, you can send plain text messages:",
            color=discord.Color.orange()
        )
        
        json_text = json.dumps(example, indent=2)
        embed.add_field(
            name="JSON Configuration",
            value=f"```json\n{json_text}\n```",
            inline=False
        )
        
        embed.add_field(
            name="📝 Result:",
            value="This will send a friendly text message without embeds, perfect for a more casual approach.",
            inline=False
        )
        
        embed.add_field(
            name="✅ Advantages:",
            value=(
                "• No URL validation issues\n"
                "• Works for all users\n"
                "• Simple and reliable\n"
                "• Easy to customize"
            ),
            inline=False
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class UploadConfigView(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="📤 Upload JSON File", style=discord.ButtonStyle.success, emoji="📤")
    async def upload_file(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        modal = JSONUploadModal(self.cog, self.guild_id)
        await interaction.response.send_modal(modal)

class JSONUploadModal(discord.ui.Modal, title="Upload JSON Configuration"):
    def __init__(self, cog, guild_id):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id

    json_content = discord.ui.TextInput(
        label="Paste your JSON configuration here:",
        placeholder="Paste the entire JSON content here...",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:

            config_data = json.loads(self.json_content.value)
            

            if not isinstance(config_data, dict):
                raise ValueError("JSON must be an object")
            
            if "embed" not in config_data and "message" not in config_data:
                raise ValueError("JSON must contain either 'embed' or 'message' field")
            

            guild_config = self.cog.get_guild_config(self.guild_id)
            guild_config["welcome_data"] = config_data
            self.cog.save_config()
            
            embed = discord.Embed(
                title="✅ Configuration Uploaded Successfully!",
                description="Your welcome message configuration has been saved and is ready to use.",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📋 Next Steps",
                value=(
                    "1. Use `!dm_welcome toggle` to enable the system\n"
                    "2. Test by having someone join the server\n"
                    "3. Check status with `!dm_welcome status`"
                ),
                inline=False
            )
            
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except json.JSONDecodeError as e:
            embed = discord.Embed(
                title="❌ Invalid JSON Format",
                description=f"There was an error parsing your JSON:\n```\n{str(e)}\n```",
                color=discord.Color.red()
            )
            embed.add_field(
                name="💡 Tips",
                value=(
                    "• Check for missing commas or brackets\n"
                    "• Ensure all strings are in quotes\n"
                    "• Use a JSON validator online\n"
                    "• Copy one of the provided examples"
                ),
                inline=False
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError as e:
            embed = discord.Embed(
                title="❌ Invalid Configuration",
                description=f"Configuration error:\n```\n{str(e)}\n```",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Unexpected Error",
                description=f"An unexpected error occurred:\n```\n{str(e)}\n```",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)

class DMWelcomeStatusView(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="🔄 Toggle System", style=discord.ButtonStyle.primary, emoji="🔄")
    async def toggle_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        guild_config = self.cog.get_guild_config(self.guild_id)
        guild_config["enabled"] = not guild_config["enabled"]
        self.cog.save_config()
        
        status = "enabled" if guild_config["enabled"] else "disabled"
        color = discord.Color.green() if guild_config["enabled"] else discord.Color.red()
        emoji = "🟢" if guild_config["enabled"] else "🔴"
        
        embed = discord.Embed(
            title=f"{emoji} System {status.title()}",
            description=f"DM Welcome system has been **{status}**.",
            color=color
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="👁️ Preview Message", style=discord.ButtonStyle.secondary, emoji="👁️")
    async def preview_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        guild_config = self.cog.get_guild_config(self.guild_id)
        
        if not guild_config["welcome_data"]:
            embed = discord.Embed(
                title="❌ No Configuration",
                description="No welcome message is currently configured.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            welcome_data = guild_config["welcome_data"]
            

            preview_embed = discord.Embed(
                title="👁️ Welcome Message Preview",
                description="This is how your welcome message will look:",
                color=discord.Color.blue()
            )
            

            def replace_placeholders(text):
                if not text:
                    return text
                return (text.replace("{user}", f"<@{interaction.user.id}>")
                           .replace("{username}", interaction.user.name)
                           .replace("{display_name}", interaction.user.display_name)
                           .replace("{server}", interaction.guild.name)
                           .replace("{member_count}", str(interaction.guild.member_count)))
            
            if "embed" in welcome_data:
                embed_data = welcome_data["embed"]
                welcome_embed = discord.Embed()
                
                if "title" in embed_data:
                    welcome_embed.title = replace_placeholders(embed_data["title"])
                if "description" in embed_data:
                    welcome_embed.description = replace_placeholders(embed_data["description"])
                if "color" in embed_data:
                    try:
                        color_value = embed_data["color"]
                        if isinstance(color_value, str) and color_value.startswith("0x"):
                            welcome_embed.color = discord.Color(int(color_value, 16))
                        else:
                            welcome_embed.color = discord.Color(color_value)
                    except:
                        welcome_embed.color = discord.Color.blue()
                
                if "thumbnail" in embed_data:
                    thumbnail_url = replace_placeholders(embed_data["thumbnail"])
                    if thumbnail_url == "{user.avatar_url}":
                        thumbnail_url = interaction.user.display_avatar.url
                    welcome_embed.set_thumbnail(url=thumbnail_url)
                
                if "image" in embed_data:
                    welcome_embed.set_image(url=replace_placeholders(embed_data["image"]))
                
                if "fields" in embed_data:
                    for field in embed_data["fields"]:
                        welcome_embed.add_field(
                            name=replace_placeholders(field.get("name", "")),
                            value=replace_placeholders(field.get("value", "")),
                            inline=field.get("inline", True)
                        )
                
                if "footer" in embed_data:
                    footer_text = replace_placeholders(embed_data["footer"].get("text", ""))
                    footer_icon = embed_data["footer"].get("icon_url", "")
                    welcome_embed.set_footer(text=footer_text, icon_url=footer_icon)
                

                if not welcome_embed.footer.text:
                    welcome_embed.set_footer(text="Made By TheHolyOneZ")
                elif "Made By TheHolyOneZ" not in welcome_embed.footer.text:
                    welcome_embed.set_footer(text=f"{welcome_embed.footer.text} • Made By TheHolyOneZ")
                
                await interaction.response.send_message(embed=preview_embed, ephemeral=True)
                await interaction.followup.send(embed=welcome_embed, ephemeral=True)
                
            elif "message" in welcome_data:
                message = replace_placeholders(welcome_data["message"])
                preview_embed.add_field(
                    name="Text Message Preview",
                    value=message,
                    inline=False
                )
                await interaction.response.send_message(embed=preview_embed, ephemeral=True)
                
        except Exception as e:
            embed = discord.Embed(
                title="❌ Preview Error",
                description=f"Error generating preview:\n```\n{str(e)}\n```",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🗑️ Clear Config", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def clear_config(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        embed = discord.Embed(
            title="⚠️ Confirm Configuration Deletion",
            description="Are you sure you want to delete the current welcome message configuration?",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="⚠️ Warning",
            value="This action cannot be undone. You will need to reconfigure the welcome message.",
            inline=False
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        view = ConfirmClearView(self.cog, self.guild_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="📊 View Stats", style=discord.ButtonStyle.secondary, emoji="📊")
    async def view_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        guild_config = self.cog.get_guild_config(self.guild_id)
        stats = guild_config["stats"]
        
        embed = discord.Embed(
            title="📊 DM Welcome Statistics",
            description="Detailed statistics for the DM Welcome system",
            color=discord.Color.blue()
        )
        

        total_attempts = stats["total_sent"] + stats["total_failed"]
        success_rate = (stats["total_sent"] / total_attempts * 100) if total_attempts > 0 else 0
        
        embed.add_field(
            name="📤 Messages Sent",
            value=f"**{stats['total_sent']}** successful",
            inline=True
        )
        
        embed.add_field(
            name="❌ Failed Deliveries",
            value=f"**{stats['total_failed']}** failed",
            inline=True
        )
        
        embed.add_field(
            name="📈 Success Rate",
            value=f"**{success_rate:.1f}%**",
            inline=True
        )
        
        embed.add_field(
            name="📋 Total Attempts",
            value=f"**{total_attempts}** total",
            inline=True
        )
        
        if stats["last_sent"]:
            last_sent = datetime.fromisoformat(stats["last_sent"])
            embed.add_field(
                name="🕒 Last Message",
                value=f"<t:{int(last_sent.timestamp())}:R>",
                inline=True
            )
        else:
            embed.add_field(
                name="🕒 Last Message",
                value="Never",
                inline=True
            )
        

        status_emoji = "🟢" if guild_config["enabled"] else "🔴"
        embed.add_field(
            name="🔄 Current Status",
            value=f"{status_emoji} {'Active' if guild_config['enabled'] else 'Inactive'}",
            inline=True
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ConfirmClearView(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="✅ Yes, Clear Config", style=discord.ButtonStyle.danger)
    async def confirm_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        guild_config = self.cog.get_guild_config(self.guild_id)
        guild_config["welcome_data"] = None
        guild_config["enabled"] = False
        self.cog.save_config()
        
        embed = discord.Embed(
            title="✅ Configuration Cleared",
            description="The welcome message configuration has been deleted and the system has been disabled.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        embed = discord.Embed(
            title="❌ Cancelled",
            description="Configuration deletion has been cancelled.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.edit_message(embed=embed, view=None)


    @app_commands.command(name="dm_welcome_toggle", description="Toggle DM welcome system on/off")
    async def dm_welcome_toggle_slash(self, interaction: discord.Interaction):
        
        if not await self.is_admin_interaction(interaction):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator or Manage Server permissions to use this command.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        guild_config = self.get_guild_config(interaction.guild.id)
        guild_config["enabled"] = not guild_config["enabled"]
        self.save_config()
        
        status = "enabled" if guild_config["enabled"] else "disabled"
        color = discord.Color.green() if guild_config["enabled"] else discord.Color.red()
        emoji = "🟢" if guild_config["enabled"] else "🔴"
        
        embed = discord.Embed(
            title=f"{emoji} DM Welcome System {status.title()}",
            description=f"The DM Welcome system has been **{status}** for this server.",
            color=color
        )
        
        if guild_config["enabled"] and not guild_config["welcome_data"]:
            embed.add_field(
                name="⚠️ Configuration Required",
                value="The system is enabled but no welcome message is configured. Use `/dm_welcome_setup` to configure it.",
                inline=False
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dm_welcome_status", description="View DM welcome system status")
    async def dm_welcome_status_slash(self, interaction: discord.Interaction):
        
        if not await self.is_admin_interaction(interaction):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator or Manage Server permissions to use this command.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        

        class InteractionContext:
            def __init__(self, interaction):
                self.interaction = interaction
                self.guild = interaction.guild
                self.send = self._send
            
            async def _send(self, *args, **kwargs):
                if not self.interaction.response.is_done():
                    await self.interaction.response.send_message(*args, **kwargs)
                else:
                    await self.interaction.followup.send(*args, **kwargs)
        
        ctx = InteractionContext(interaction)
        await self.show_status(ctx)

    @app_commands.command(name="dm_welcome_setup", description="Setup DM welcome system")
    async def dm_welcome_setup_slash(self, interaction: discord.Interaction):
        
        if not await self.is_admin_interaction(interaction):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator or Manage Server permissions to use this command.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        

        class InteractionContext:
            def __init__(self, interaction):
                self.interaction = interaction
                self.guild = interaction.guild
                self.send = self._send
            
            async def _send(self, *args, **kwargs):
                if not self.interaction.response.is_done():
                    await self.interaction.response.send_message(*args, **kwargs)
                else:
                    await self.interaction.followup.send(*args, **kwargs)
        
        ctx = InteractionContext(interaction)
        await self.show_setup_menu(ctx)

    async def is_admin_interaction(self, interaction) -> bool:
        
        member = interaction.user
        return member.guild_permissions.administrator or member.guild_permissions.manage_guild


    @commands.hybrid_command(name="dm_welcome_test")
    @app_commands.describe(user="User to send a test welcome message to")
    async def dm_welcome_test(self, ctx, user: Optional[discord.Member] = None):
        
        if not await self.is_admin(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator or Manage Server permissions to use this command.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        guild_config = self.get_guild_config(ctx.guild.id)
        
        if not guild_config["welcome_data"]:
            embed = discord.Embed(
                title="❌ No Configuration",
                description="No welcome message is configured. Use the setup command first.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        target_user = user or ctx.author
        
        try:
            welcome_data = guild_config["welcome_data"]
            

            def replace_placeholders(text):
                if not text:
                    return text
                return (text.replace("{user}", str(target_user))
                           .replace("{username}", target_user.name)
                           .replace("{display_name}", target_user.display_name)
                           .replace("{server}", ctx.guild.name)
                           .replace("{member_count}", str(ctx.guild.member_count)))
            
            if "embed" in welcome_data:
                embed_data = welcome_data["embed"]
                test_embed = discord.Embed()
                
                if "title" in embed_data:
                    test_embed.title = replace_placeholders(embed_data["title"])
                if "description" in embed_data:
                    test_embed.description = replace_placeholders(embed_data["description"])
                if "color" in embed_data:
                    try:
                        color_value = embed_data["color"]
                        if isinstance(color_value, str) and color_value.startswith("0x"):
                            test_embed.color = discord.Color(int(color_value, 16))
                        else:
                            test_embed.color = discord.Color(color_value)
                    except:
                        test_embed.color = discord.Color.blue()
                
                if "thumbnail" in embed_data:
                    thumbnail_url = replace_placeholders(embed_data["thumbnail"])
                    if thumbnail_url == "{user.avatar_url}":
                        thumbnail_url = target_user.display_avatar.url
                    test_embed.set_thumbnail(url=thumbnail_url)
                
                if "image" in embed_data:
                    test_embed.set_image(url=replace_placeholders(embed_data["image"]))
                
                if "fields" in embed_data:
                    for field in embed_data["fields"]:
                        test_embed.add_field(
                            name=replace_placeholders(field.get("name", "")),
                            value=replace_placeholders(field.get("value", "")),
                            inline=field.get("inline", True)
                        )
                
                if "footer" in embed_data:
                    footer_text = replace_placeholders(embed_data["footer"].get("text", ""))
                    footer_icon = embed_data["footer"].get("icon_url", "")
                    test_embed.set_footer(text=footer_text, icon_url=footer_icon)
                

                if not test_embed.footer.text:
                    test_embed.set_footer(text="Made By TheHolyOneZ")
                elif "Made By TheHolyOneZ" not in test_embed.footer.text:
                    test_embed.set_footer(text=f"{test_embed.footer.text} • Made By TheHolyOneZ")
                
                await target_user.send(embed=test_embed)
                
            elif "message" in welcome_data:
                message = replace_placeholders(welcome_data["message"])
                await target_user.send(message)
            

            embed = discord.Embed(
                title="✅ Test Message Sent",
                description=f"Test welcome message has been sent to {target_user.mention}.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Cannot Send DM",
                description=f"Unable to send DM to {target_user.mention}. They may have DMs disabled.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Test Failed",
                description=f"Error sending test message:\n```\n{str(e)}\n```",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="dm_welcome_export")
    async def dm_welcome_export(self, ctx):
        
        if not await self.is_admin(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator or Manage Server permissions to use this command.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        guild_config = self.get_guild_config(ctx.guild.id)
        
        if not guild_config["welcome_data"]:
            embed = discord.Embed(
                title="❌ No Configuration",
                description="No welcome message is configured to export.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        try:

            export_data = {
                "dm_welcome_config": guild_config["welcome_data"],
                "exported_from": ctx.guild.name,
                "exported_by": str(ctx.author),
                "export_date": datetime.now().isoformat(),
                "version": "1.0"
            }
            

            json_content = json.dumps(export_data, indent=2, ensure_ascii=False)
            filename = f"dm_welcome_config_{ctx.guild.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(json_content)
            

            embed = discord.Embed(
                title="📤 Configuration Exported",
                description="Your DM welcome configuration has been exported successfully.",
                color=discord.Color.green()
            )
            embed.add_field(
                name="📋 Usage",
                value="You can import this configuration on other servers using the upload feature.",
                inline=False
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            
            with open(filename, 'rb') as f:
                file = discord.File(f, filename=filename)
                await ctx.send(embed=embed, file=file)
            

            try:
                os.remove(filename)
            except:
                pass
                
        except Exception as e:
            embed = discord.Embed(
                title="❌ Export Failed",
                description=f"Error exporting configuration:\n```\n{str(e)}\n```",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="dm_welcome_reset_stats")
    async def dm_welcome_reset_stats(self, ctx):
        
        if not await self.is_admin(ctx):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator or Manage Server permissions to use this command.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        guild_config = self.get_guild_config(ctx.guild.id)
        

        guild_config["stats"] = {
            "total_sent": 0,
            "total_failed": 0,
            "last_sent": None
        }
        self.save_config()
        
        embed = discord.Embed(
            title="🔄 Statistics Reset",
            description="All DM welcome statistics have been reset to zero.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)

def setup(bot):
    cog = DMWelcomerSystem(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    return cog
