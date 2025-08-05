import discord
from discord.ext import commands
import json
import aiohttp
import asyncio
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class RegistrationModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="📋 Registration Form")
        self.cog = cog
        
        self.name_input = discord.ui.TextInput(
            label="Full Name",
            placeholder="Enter your full name...",
            max_length=100,
            style=discord.TextStyle.short,
            required=True
        )
        
        self.project_input = discord.ui.TextInput(
            label="Project Name",
            placeholder="Enter your project name...",
            max_length=150,
            style=discord.TextStyle.short,
            required=True
        )
        
        self.description_input = discord.ui.TextInput(
            label="Project Description (Optional)",
            placeholder="Briefly describe your project...",
            max_length=1000,
            style=discord.TextStyle.paragraph,
            required=False
        )
        
        self.add_item(self.name_input)
        self.add_item(self.project_input)
        self.add_item(self.description_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        registration_data = {
            "user": interaction.user,
            "name": self.name_input.value.strip(),
            "project_name": self.project_input.value.strip(),
            "description": self.description_input.value.strip() if self.description_input.value else "No description provided",
            "timestamp": datetime.utcnow(),
            "guild": interaction.guild
        }
        
        try:
            private_channel = await self.cog.create_private_channel(interaction.guild, interaction.user, registration_data["project_name"])
            registration_data["channel"] = private_channel
            
            success = await self.cog.send_registration_webhook(registration_data)
            
            if success and private_channel:
                embed = discord.Embed(
                    title="✅ Registration Successful",
                    description="Your registration has been submitted successfully!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Name", value=registration_data["name"], inline=True)
                embed.add_field(name="Project", value=registration_data["project_name"], inline=True)
                embed.add_field(name="Private Channel", value=private_channel.mention, inline=True)
                embed.add_field(
                    name="Next Steps",
                    value=f"Your private channel {private_channel.mention} has been created! You can now upload your project files, documentation, and communicate with administrators.",
                    inline=False
                )
                embed.set_footer(text="Made by TheHolyOneZ")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                welcome_embed = discord.Embed(
                    title=f"🎉 Welcome {interaction.user.display_name}!",
                    description=f"This is your private project channel for **{registration_data['project_name']}**",
                    color=discord.Color.blue()
                )
                welcome_embed.add_field(
                    name="📁 What you can upload here:",
                    value="• Project documentation\n• Source code files\n• README files\n• Design assets\n• Screenshots\n• Any project-related files",
                    inline=False
                )
                welcome_embed.add_field(
                    name="💬 Communication:",
                    value="• Ask questions about your project\n• Get feedback from administrators\n• Request assistance or guidance\n• Share updates and progress",
                    inline=False
                )
                welcome_embed.add_field(
                    name="📋 Project Details:",
                    value=f"**Name:** {registration_data['name']}\n**Project:** {registration_data['project_name']}\n**Description:** {registration_data['description']}",
                    inline=False
                )
                welcome_embed.set_footer(text="Made by TheHolyOneZ • Upload your files and start collaborating!")
                
                await private_channel.send(f"{interaction.user.mention}", embed=welcome_embed)
                
            else:
                embed = discord.Embed(
                    title="❌ Registration Failed",
                    description="There was an error processing your registration. Please try again or contact an administrator.",
                    color=discord.Color.red()
                )
                embed.set_footer(text="Made by TheHolyOneZ")
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Registration error: {e}")
            embed = discord.Embed(
                title="❌ Registration Error",
                description="An unexpected error occurred during registration. Please contact an administrator.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await interaction.followup.send(embed=embed, ephemeral=True)

class RegistrationView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    
    @discord.ui.button(
        label="📝 Register Now",
        style=discord.ButtonStyle.primary,
        custom_id="registration_button",
        emoji="📝"
    )
    async def register_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        config = self.cog.config.get(guild_id, {})
        cooldown_hours = config.get("cooldown_hours", 0)
        
        if cooldown_hours > 0:
            last_registration = self.cog.get_last_registration(guild_id, user_id)
            if last_registration:
                time_diff = datetime.utcnow() - datetime.fromisoformat(last_registration)
                if time_diff.total_seconds() < (cooldown_hours * 3600):
                    remaining_hours = cooldown_hours - (time_diff.total_seconds() / 3600)
                    embed = discord.Embed(
                        title="⏰ Registration Cooldown",
                        description=f"You can register again in {remaining_hours:.1f} hours.",
                        color=discord.Color.orange()
                    )
                    embed.set_footer(text="Made by TheHolyOneZ")
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
        
        modal = RegistrationModal(self.cog)
        await interaction.response.send_modal(modal)
        
        self.cog.update_last_registration(guild_id, user_id)

class RegistrationSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/registration_config.json"
        self.config = self.load_config()
        
        self.bot.add_view(RegistrationView(self))
    
    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def save_config(self):
        import os
        os.makedirs("data", exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4, default=str)
    
    def get_prefix(self, ctx):
        if hasattr(self.bot, 'command_prefix'):
            if callable(self.bot.command_prefix):
                return self.bot.command_prefix(self.bot, ctx.message)
            return self.bot.command_prefix
        return "!"
    
    def get_last_registration(self, guild_id: str, user_id: str) -> Optional[str]:
        return self.config.get(guild_id, {}).get("last_registrations", {}).get(user_id)
    
    def update_last_registration(self, guild_id: str, user_id: str):
        if guild_id not in self.config:
            self.config[guild_id] = {}
        if "last_registrations" not in self.config[guild_id]:
            self.config[guild_id]["last_registrations"] = {}
        
        self.config[guild_id]["last_registrations"][user_id] = datetime.utcnow().isoformat()
        self.save_config()
    
    async def create_private_channel(self, guild, user, project_name):
        try:
            category_name = "📁 Project Channels"
            category = discord.utils.get(guild.categories, name=category_name)
            
            if not category:
                category = await guild.create_category(category_name)
            
            channel_name = f"📋-{user.name}-{project_name}".lower().replace(" ", "-")[:50]
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                )
            }
            
            for member in guild.members:
                if member.guild_permissions.administrator:
                    overwrites[member] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        attach_files=True,
                        embed_links=True,
                        read_message_history=True,
                        manage_messages=True
                    )
            
            channel = await guild.create_text_channel(
                channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Private project channel for {user.display_name} - Project: {project_name}"
            )
            
            return channel
            
        except Exception as e:
            logger.error(f"Failed to create private channel: {e}")
            return None
    
    async def send_registration_webhook(self, data) -> bool:
        guild_id = str(data["guild"].id)
        webhook_url = self.config.get(guild_id, {}).get("webhook_url")
        
        if not webhook_url:
            logger.warning(f"No webhook configured for guild {guild_id}")
            return False
        
        embed = discord.Embed(
            title="📋 New Registration Submitted",
            description="A new user has registered and received their private project channel!",
            color=discord.Color.blue(),
            timestamp=data["timestamp"]
        )
        
        embed.add_field(name="👤 Discord User", value=f"{data['user'].mention} ({data['user'].name})", inline=True)
        embed.add_field(name="📝 Full Name", value=data["name"], inline=True)
        embed.add_field(name="🏷️ User ID", value=str(data["user"].id), inline=True)
        
        embed.add_field(name="📁 Project Name", value=data["project_name"], inline=False)
        
        if data["description"] != "No description provided":
            embed.add_field(name="📄 Project Description", value=data["description"], inline=False)
        
        if data.get("channel"):
            embed.add_field(name="🔗 Private Channel", value=f"{data['channel'].mention}\n[Click to view channel](https://discord.com/channels/{data['guild'].id}/{data['channel'].id})", inline=False)
        
        embed.add_field(name="🏠 Server", value=data["guild"].name, inline=True)
        embed.add_field(name="📊 Member Count", value=len(data["guild"].members), inline=True)
        embed.add_field(name="📅 Account Created", value=data["user"].created_at.strftime('%Y-%m-%d'), inline=True)
        
        if data["user"].avatar:
            embed.set_thumbnail(url=data["user"].avatar.url)
        
        embed.set_footer(text="Made by TheHolyOneZ • Registration System")
        
        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(webhook_url, session=session)
                await webhook.send(embed=embed)
            return True
        except Exception as e:
            logger.error(f"Failed to send registration webhook: {e}")
            return False
    
    @commands.group(name="register", aliases=["reg"], invoke_without_command=True)
    async def register_group(self, ctx):
        prefix = self.get_prefix(ctx)
        
        embed = discord.Embed(
            title="📋 Registration System",
            description="Professional user registration and project management system with automatic private channel creation",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📋 Setup Commands",
            value=(
                f"`{prefix}register setup` - Interactive setup wizard\n"
                f"`{prefix}register panel` - Create registration panel\n"
                f"`{prefix}register webhook <url>` - Set webhook URL\n"
                f"`{prefix}register settings` - View current settings"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Configuration Commands",
            value=(
                f"`{prefix}register cooldown <hours>` - Set registration cooldown\n"
                f"`{prefix}register customize` - Customize registration embed\n"
                f"`{prefix}register test` - Test webhook connection\n"
                f"`{prefix}register stats` - View registration statistics"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎯 Features",
            value="• Automatic private channel creation\n• Admin-only channel access\n• Webhook notifications with channel links\n• Professional registration forms\n• Customizable embeds",
            inline=False
        )
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @register_group.command(name="setup")
    async def setup_wizard(self, ctx):
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator permissions to set up the registration system.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🛠️ Registration System Setup",
            description="Let's set up your registration system with automatic private channel creation!",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        
        await ctx.send("**Step 1:** Please provide the webhook URL where registrations should be sent:")
        
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            webhook_url = msg.content.strip()
            
            try:
                async with aiohttp.ClientSession() as session:
                    webhook = discord.Webhook.from_url(webhook_url, session=session)
                    test_embed = discord.Embed(
                        title="🧪 Webhook Test",
                        description="Registration system webhook configured successfully!",
                        color=discord.Color.green()
                    )
                    test_embed.set_footer(text="Made by TheHolyOneZ")
                    await webhook.send(embed=test_embed)
                
                guild_id = str(ctx.guild.id)
                if guild_id not in self.config:
                    self.config[guild_id] = {}
                self.config[guild_id]["webhook_url"] = webhook_url
                
                await ctx.send("✅ Webhook configured and tested successfully!")
                
            except Exception as e:
                await ctx.send(f"❌ Webhook test failed: {str(e)}")
                return
                
        except asyncio.TimeoutError:
            await ctx.send("Setup timed out. Please try again.")
            return
        
        await ctx.send("**Step 2:** Set registration cooldown in hours (0 for no cooldown):")
        
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            try:
                cooldown_hours = int(msg.content.strip())
                if cooldown_hours < 0:
                    cooldown_hours = 0
                
                self.config[guild_id]["cooldown_hours"] = cooldown_hours
                await ctx.send(f"✅ Cooldown set to {cooldown_hours} hours!")
                
            except ValueError:
                await ctx.send("❌ Invalid number. Setting cooldown to 0 hours.")
                self.config[guild_id]["cooldown_hours"] = 0
                
        except asyncio.TimeoutError:
            self.config[guild_id]["cooldown_hours"] = 0
            await ctx.send("⏰ Timeout. Setting cooldown to 0 hours.")
        
        self.config[guild_id]["embed_settings"] = {
            "title": "📋 Project Registration",
            "description": "For organizational purposes, please use the button below to register and get a private channel to upload files, docs, and readmes.\n\n**What you'll get:**\n• Private project channel\n• File upload access\n• Direct communication with administrators\n• Project tracking and updates",
            "color": 0x3498DB,
            "footer": "Click the button below to get started!"
        }
        
        self.save_config()
        
        prefix = self.get_prefix(ctx)
        embed = discord.Embed(
            title="✅ Setup Complete!",
            description="Registration system has been configured successfully!",
            color=discord.Color.green()
        )
        embed.add_field(name="Webhook", value="✅ Configured and tested", inline=True)
        embed.add_field(name="Cooldown", value=f"{cooldown_hours} hours", inline=True)
        embed.add_field(name="Channel Creation", value="✅ Automatic private channels", inline=True)
        embed.add_field(name="Next Step", value=f"Use `{prefix}register panel` to create the registration panel", inline=False)
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @register_group.command(name="panel")
    async def create_panel(self, ctx):
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator permissions to create registration panels.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        guild_id = str(ctx.guild.id)
        config = self.config.get(guild_id, {})
        prefix = self.get_prefix(ctx)
        
        if not config.get("webhook_url"):
            embed = discord.Embed(
                title="❌ Setup Required",
                description=f"Please run `{prefix}register setup` first to configure the webhook.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        embed_settings = config.get("embed_settings", {
            "title": "📋 Project Registration",
            "description": "For organizational purposes, please use the button below to register and get a private channel to upload files, docs, and readmes.\n\n**What you'll get:**\n• Private project channel\n• File upload access\n• Direct communication with administrators\n• Project tracking and updates",
            "color": 0x3498DB,
            "footer": "Click the button below to get started!"
        })
        
        formatted_description = embed_settings["description"].format(
            server=ctx.guild.name,
            user="{user}",
            member_count=len(ctx.guild.members),
            bot_name=self.bot.user.name
        )
        
        embed = discord.Embed(
            title=embed_settings["title"],
            description=formatted_description,
            color=embed_settings["color"]
        )
        
        embed.add_field(
            name="📋 Registration Process",
            value="1️⃣ Click the register button\n2️⃣ Fill out the form\n3️⃣ Get your private channel instantly\n4️⃣ Start uploading your project files",
            inline=True
        )
        
        embed.add_field(
            name="📁 What to Upload",
            value="• Project documentation\n• Source code files\n• README files\n• Design assets\n• Screenshots\n• Any project files",
            inline=True
        )
        
        embed.add_field(
            name="🔒 Privacy & Security",
            value="• Only you and admins can see your channel\n• Direct admin communication\n• Professional project management",
            inline=True
        )
        
        embed.set_footer(text=embed_settings["footer"])
        
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        
        view = RegistrationView(self)
        
        await ctx.send(embed=embed, view=view)
        
        confirm_embed = discord.Embed(
            title="✅ Registration Panel Created",
            description="The registration panel has been posted successfully! Users will now get private channels automatically upon registration.",
            color=discord.Color.green()
        )
        confirm_embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.author.send(embed=confirm_embed)
    
    @register_group.command(name="webhook")
    async def set_webhook(self, ctx, webhook_url: str = None):
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator permissions to configure webhooks.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        prefix = self.get_prefix(ctx)
        
        if not webhook_url:
            embed = discord.Embed(
                title="📝 Set Webhook URL",
                description="Please provide a webhook URL:",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Usage",
                value=f"`{prefix}register webhook <webhook_url>`",
                inline=False
            )
            embed.add_field(
                name="How to get a webhook URL",
                value="1. Go to your channel settings\n2. Click 'Integrations'\n3. Click 'Webhooks'\n4. Create a new webhook\n5. Copy the webhook URL",
                inline=False
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(webhook_url, session=session)
                test_embed = discord.Embed(
                    title="🧪 Webhook Test",
                    description=f"Registration webhook configured by {ctx.author.mention}",
                    color=discord.Color.green()
                )
                test_embed.add_field(name="Server", value=ctx.guild.name, inline=True)
                test_embed.add_field(name="Configured By", value=ctx.author.mention, inline=True)
                test_embed.add_field(name="Features", value="✅ Private channel creation\n✅ Admin notifications\n✅ Direct channel links", inline=False)
                test_embed.set_footer(text="Made by TheHolyOneZ")
                await webhook.send(embed=test_embed)
            
            guild_id = str(ctx.guild.id)
            if guild_id not in self.config:
                self.config[guild_id] = {}
            self.config[guild_id]["webhook_url"] = webhook_url
            self.save_config()
            
            embed = discord.Embed(
                title="✅ Webhook Configured",
                description="Webhook has been set and tested successfully!",
                color=discord.Color.green()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Webhook Error",
                description=f"Failed to configure webhook: {str(e)}",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
    
    @register_group.command(name="settings")
    async def view_settings(self, ctx):
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator permissions to view settings.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        guild_id = str(ctx.guild.id)
        config = self.config.get(guild_id, {})
        
        embed = discord.Embed(
            title="⚙️ Registration Settings",
            description=f"Current configuration for {ctx.guild.name}",
            color=discord.Color.blue()
        )
        
        webhook_status = "✅ Configured" if config.get("webhook_url") else "❌ Not configured"
        embed.add_field(name="Webhook", value=webhook_status, inline=True)
        
        cooldown = config.get("cooldown_hours", 0)
        embed.add_field(name="Cooldown", value=f"{cooldown} hours", inline=True)
        
        reg_count = len(config.get("last_registrations", {}))
        embed.add_field(name="Total Registrations", value=reg_count, inline=True)
        
        embed.add_field(name="Private Channels", value="✅ Auto-creation enabled", inline=True)
        embed.add_field(name="Admin Access", value="✅ Automatic permissions", inline=True)
        embed.add_field(name="Channel Links", value="✅ Webhook integration", inline=True)
        
        embed_settings = config.get("embed_settings", {})
        if embed_settings:
            embed.add_field(
                name="Panel Title",
                value=embed_settings.get("title", "Not set"),
                inline=False
            )
            embed.add_field(
                name="Panel Color",
                value=f"#{embed_settings.get('color', 0x3498DB):06x}",
                inline=True
            )
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @register_group.command(name="cooldown")
    async def set_cooldown(self, ctx, hours: int):
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator permissions to set cooldown.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        if hours < 0:
            hours = 0
        
        guild_id = str(ctx.guild.id)
        if guild_id not in self.config:
            self.config[guild_id] = {}
        
        self.config[guild_id]["cooldown_hours"] = hours
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Cooldown Updated",
            description=f"Registration cooldown set to {hours} hours.",
            color=discord.Color.green()
        )
        
        if hours == 0:
            embed.add_field(name="Note", value="Users can register multiple times without restriction.", inline=False)
        else:
            embed.add_field(name="Note", value=f"Users must wait {hours} hours between registrations.", inline=False)
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @register_group.command(name="customize")
    async def customize_embed(self, ctx):
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator permissions to customize the embed.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        prefix = self.get_prefix(ctx)
        
        embed = discord.Embed(
            title="🎨 Embed Customization",
            description="Customize your registration panel embed",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="Available Variables",
            value="`{server}` - Server name\n`{user}` - User mention\n`{member_count}` - Member count\n`{bot_name}` - Bot name",
            inline=False
        )
        
        embed.add_field(
            name="Commands",
            value=(
                f"`{prefix}register title <title>` - Set embed title\n"
                f"`{prefix}register description <text>` - Set embed description\n"
                f"`{prefix}register color <hex>` - Set embed color\n"
                f"`{prefix}register footer <text>` - Set embed footer"
            ),
            inline=False
        )
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @register_group.command(name="title")
    async def set_title(self, ctx, *, title: str):
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator permissions to customize the embed.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        guild_id = str(ctx.guild.id)
        if guild_id not in self.config:
            self.config[guild_id] = {}
        if "embed_settings" not in self.config[guild_id]:
            self.config[guild_id]["embed_settings"] = {}
        
        self.config[guild_id]["embed_settings"]["title"] = title
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Title Updated",
            description=f"Registration embed title set to: **{title}**",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @register_group.command(name="description")
    async def set_description(self, ctx, *, description: str):
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator permissions to customize the embed.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        guild_id = str(ctx.guild.id)
        if guild_id not in self.config:
            self.config[guild_id] = {}
        if "embed_settings" not in self.config[guild_id]:
            self.config[guild_id]["embed_settings"] = {}
        
        self.config[guild_id]["embed_settings"]["description"] = description
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Description Updated",
            description="Registration embed description has been updated.",
            color=discord.Color.green()
        )
        embed.add_field(name="New Description", value=description[:1000] + ("..." if len(description) > 1000 else ""), inline=False)
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @register_group.command(name="color")
    async def set_color(self, ctx, color: str):
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator permissions to customize the embed.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        try:
            if color.startswith('#'):
                color_int = int(color[1:], 16)
            elif color.startswith('0x'):
                color_int = int(color, 16)
            else:
                color_int = int(color, 16)
            
            if color_int > 0xFFFFFF:
                raise ValueError("Color value too large")
            
            guild_id = str(ctx.guild.id)
            if guild_id not in self.config:
                self.config[guild_id] = {}
            if "embed_settings" not in self.config[guild_id]:
                self.config[guild_id]["embed_settings"] = {}
            
            self.config[guild_id]["embed_settings"]["color"] = color_int
            self.save_config()
            
            embed = discord.Embed(
                title="✅ Color Updated",
                description=f"Registration embed color set to: #{color_int:06x}",
                color=color_int
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Color",
                description="Please provide a valid hex color (e.g., #FF0000, 0xFF0000, or FF0000)",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
    
    @register_group.command(name="footer")
    async def set_footer(self, ctx, *, footer: str):
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator permissions to customize the embed.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        guild_id = str(ctx.guild.id)
        if guild_id not in self.config:
            self.config[guild_id] = {}
        if "embed_settings" not in self.config[guild_id]:
            self.config[guild_id]["embed_settings"] = {}
        
        self.config[guild_id]["embed_settings"]["footer"] = footer
        self.save_config()
        
        embed = discord.Embed(
            title="✅ Footer Updated",
            description=f"Registration embed footer set to: **{footer}**",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @register_group.command(name="test")
    async def test_webhook(self, ctx):
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator permissions to test the webhook.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        guild_id = str(ctx.guild.id)
        webhook_url = self.config.get(guild_id, {}).get("webhook_url")
        prefix = self.get_prefix(ctx)
        
        if not webhook_url:
            embed = discord.Embed(
                title="❌ No Webhook",
                description=f"No webhook URL configured. Use `{prefix}register webhook <url>` to set one.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        try:
            test_channel = await self.create_private_channel(ctx.guild, ctx.author, "Test Project")
            
            test_data = {
                "user": ctx.author,
                "name": "Test User",
                "project_name": "Test Project",
                "description": "This is a test registration to verify webhook functionality and private channel creation.",
                "timestamp": datetime.utcnow(),
                "guild": ctx.guild,
                "channel": test_channel
            }
            
            success = await self.send_registration_webhook(test_data)
            
            if success and test_channel:
                embed = discord.Embed(
                    title="✅ Webhook Test Successful",
                    description="Test registration sent successfully to the webhook with private channel creation!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Test Channel Created", value=test_channel.mention, inline=True)
                embed.add_field(name="Channel Link", value=f"[Click to view](https://discord.com/channels/{ctx.guild.id}/{test_channel.id})", inline=True)
                embed.add_field(name="Note", value="You can delete the test channel if needed.", inline=False)
            else:
                embed = discord.Embed(
                    title="❌ Webhook Test Failed",
                    description="Failed to send test registration. Check the webhook URL and permissions.",
                    color=discord.Color.red()
                )
            
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Test Error",
                description=f"An error occurred during testing: {str(e)}",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
    
    @register_group.command(name="stats")
    async def view_stats(self, ctx):
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator permissions to view statistics.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        guild_id = str(ctx.guild.id)
        config = self.config.get(guild_id, {})
        registrations = config.get("last_registrations", {})
        
        embed = discord.Embed(
            title="📊 Registration Statistics",
            description=f"Statistics for {ctx.guild.name}",
            color=discord.Color.gold()
        )
        
        total_registrations = len(registrations)
        embed.add_field(name="Total Registrations", value=total_registrations, inline=True)
        
        recent_count = 0
        current_time = datetime.utcnow()
        for timestamp_str in registrations.values():
            try:
                reg_time = datetime.fromisoformat(timestamp_str)
                if (current_time - reg_time).total_seconds() < 86400:
                    recent_count += 1
            except:
                continue
        
        embed.add_field(name="Last 24 Hours", value=recent_count, inline=True)
        
        webhook_status = "✅ Active" if config.get("webhook_url") else "❌ Not configured"
        embed.add_field(name="Webhook Status", value=webhook_status, inline=True)
        
        cooldown = config.get("cooldown_hours", 0)
        embed.add_field(name="Cooldown Setting", value=f"{cooldown} hours", inline=True)
        
        embed.add_field(name="System Status", value="🟢 Online", inline=True)
        
        project_channels = len([c for c in ctx.guild.channels if c.name.startswith("📋-")])
        embed.add_field(name="Project Channels", value=project_channels, inline=True)
        
        setup_complete = bool(config.get("webhook_url") and config.get("embed_settings"))
        setup_status = "✅ Complete" if setup_complete else "⚠️ Incomplete"
        embed.add_field(name="Setup Status", value=setup_status, inline=True)
        
        embed.add_field(name="Features Active", value="✅ Private channel creation\n✅ Admin notifications\n✅ Direct channel links", inline=True)
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @register_group.command(name="clear")
    async def clear_registrations(self, ctx):
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator permissions to clear registration data.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="⚠️ Clear Registration Data",
            description="This will clear all registration timestamps and cooldown data. This action cannot be undone!",
            color=discord.Color.orange()
        )
        embed.add_field(name="What will be cleared:", value="• User registration timestamps\n• Cooldown data\n• Registration statistics", inline=False)
        embed.add_field(name="What will NOT be cleared:", value="• Webhook configuration\n• Embed customization\n• System settings\n• Created private channels", inline=False)
        embed.set_footer(text="React with ✅ to confirm or ❌ to cancel")
        
        message = await ctx.send(embed=embed)
        await message.add_reaction("✅")
        await message.add_reaction("❌")
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == message.id
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "✅":
                guild_id = str(ctx.guild.id)
                if guild_id in self.config:
                    self.config[guild_id]["last_registrations"] = {}
                    self.save_config()
                
                embed = discord.Embed(
                    title="✅ Data Cleared",
                    description="All registration data has been cleared successfully.",
                    color=discord.Color.green()
                )
                embed.set_footer(text="Made by TheHolyOneZ")
                await message.edit(embed=embed)
                await message.clear_reactions()
                
            else:
                embed = discord.Embed(
                    title="❌ Cancelled",
                    description="Registration data clearing has been cancelled.",
                    color=discord.Color.blue()
                )
                embed.set_footer(text="Made by TheHolyOneZ")
                await message.edit(embed=embed)
                await message.clear_reactions()
                
        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="⏰ Timeout",
                description="Confirmation timed out. No data was cleared.",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await message.edit(embed=embed)
            await message.clear_reactions()
    
    @register_group.command(name="cleanup")
    async def cleanup_channels(self, ctx):
        if not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need Administrator permissions to cleanup channels.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        project_channels = [c for c in ctx.guild.channels if c.name.startswith("📋-")]
        
        if not project_channels:
            embed = discord.Embed(
                title="ℹ️ No Project Channels",
                description="No project channels found to cleanup.",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="⚠️ Cleanup Project Channels",
            description=f"This will delete all {len(project_channels)} project channels. This action cannot be undone!",
            color=discord.Color.orange()
        )
        embed.add_field(name="Channels to be deleted:", value=f"{len(project_channels)} project channels", inline=False)
        embed.add_field(name="⚠️ Warning:", value="All messages and files in these channels will be permanently lost!", inline=False)
        embed.set_footer(text="React with ✅ to confirm or ❌ to cancel")
        
        message = await ctx.send(embed=embed)
        await message.add_reaction("✅")
        await message.add_reaction("❌")
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == message.id
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "✅":
                deleted_count = 0
                for channel in project_channels:
                    try:
                        await channel.delete(reason="Project channel cleanup by administrator")
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Failed to delete channel {channel.name}: {e}")
                
                embed = discord.Embed(
                    title="✅ Cleanup Complete",
                    description=f"Successfully deleted {deleted_count} project channels.",
                    color=discord.Color.green()
                )
                embed.set_footer(text="Made by TheHolyOneZ")
                await message.edit(embed=embed)
                await message.clear_reactions()
                
            else:
                embed = discord.Embed(
                    title="❌ Cancelled",
                    description="Channel cleanup has been cancelled.",
                    color=discord.Color.blue()
                )
                embed.set_footer(text="Made by TheHolyOneZ")
                await message.edit(embed=embed)
                await message.clear_reactions()
                
        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="⏰ Timeout",
                description="Confirmation timed out. No channels were deleted.",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Made by TheHolyOneZ")
            await message.edit(embed=embed)
            await message.clear_reactions()
    
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Registration System initialized")
        logger.info(f"Configured for {len(self.config)} servers")
    
    def cog_unload(self):
        logger.info("Registration System unloaded")

async def setup(bot):
    await bot.add_cog(RegistrationSystem(bot))

def setup(bot):
    cog = RegistrationSystem(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    return cog

__version__ = "2.0.0"
__author__ = "TheHolyOneZ"
__description__ = "Professional registration system with automatic private channel creation and webhook integration"

def get_cog_info():
    return {
        "name": "Registration System",
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "commands": [
            "register", "reg"
        ],
        "features": [
            "Professional registration forms",
            "Automatic private channel creation",
            "Admin-only channel access",
            "Customizable embeds with variables",
            "Webhook integration with channel links",
            "Registration cooldown system",
            "Comprehensive statistics",
            "Easy setup wizard",
            "Persistent button views",
            "Channel cleanup tools"
        ]
    }

if __name__ == "__main__":
    print(f"Registration System v{__version__} by {__author__}")
    print("This is a Discord bot extension and should be loaded by a bot framework.")
    print("")
    print("ZygnalBot Is a good One! zygnalbot.com")
    print(f"Bye - {__author__}")
