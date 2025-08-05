import discord
from discord.ext import commands
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Optional, Union

class BanAppealSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_path = "data/ban_appeal_config.json"
        self.appeals_path = "data/ban_appeals.json"
        self.config = self.load_config()
        self.appeals = self.load_appeals()

    @commands.Cog.listener() 
    async def on_message(self, message):
           
        if message.author.bot:
            return
                
        if message.guild is None:
              
            return  
            
        guild_id = message.guild.id

    def load_config(self) -> Dict:
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {}
        
    def save_config(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)
            
    def load_appeals(self) -> Dict:
        if os.path.exists(self.appeals_path):
            with open(self.appeals_path, 'r') as f:
                return json.load(f)
        return {}
        
    def save_appeals(self):
        os.makedirs(os.path.dirname(self.appeals_path), exist_ok=True)
        with open(self.appeals_path, 'w') as f:
            json.dump(self.appeals, f, indent=4)
    
    @commands.group(name="banappeal", aliases=["ba"])
    @commands.has_permissions(administrator=True)
    async def ban_appeal(self, ctx):
        if ctx.invoked_subcommand is None:
            await self.show_ban_management_panel(ctx)
    
    @ban_appeal.command(name="setup")
    async def setup_ban_appeal(self, ctx):
        embed = discord.Embed(
            title="🛡️ Ban Appeal System Setup",
            description=(
                "The ban appeal system lets you manage bans across two servers:\n\n"
                "**Community Server**: Your main server where users are banned from\n"
                "**Appeal Server**: A separate server where banned users can submit appeals\n\n"
                "Use the buttons below to configure the system:"
            ),
            color=discord.Color.from_rgb(64, 64, 64)
        )
        await ctx.send(embed=embed, view=SetupView(self))
    
    async def show_ban_management_panel(self, ctx):
        embed = discord.Embed(
            title="🛡️ Ban Management System",
            description="Manage bans and appeals across your servers",
            color=discord.Color.from_rgb(64, 64, 64)  # Dark gray
        )
        
        main_server = self.get_main_server_name(ctx.guild.id)
        appeal_server = self.get_appeal_server_name(ctx.guild.id)
        
        embed.add_field(
            name="Current Configuration",
            value=f"**Community Server**: {main_server or 'Not set'}\n"
                  f"**Appeal Server**: {appeal_server or 'Not set'}",
            inline=False
        )
        
        embed.add_field(
            name="Pending Appeals",
            value=f"{self.get_pending_appeals_count(ctx.guild.id)} appeals waiting for review",
            inline=False
        )
        
        embed.set_footer(text="Use the buttons below to manage the ban appeal system")
        
        await ctx.send(embed=embed, view=BanManagementView(self, ctx))
    
    def get_main_server_name(self, guild_id: int) -> Optional[str]:
        str_guild_id = str(guild_id)
        if str_guild_id in self.config:
            main_id = self.config[str_guild_id].get("main_server")
            if main_id:
                guild = self.bot.get_guild(int(main_id))
                return guild.name if guild else "Unknown Server"
        return None
    
    def get_appeal_server_name(self, guild_id: int) -> Optional[str]:
        str_guild_id = str(guild_id)
        

        if str_guild_id in self.config and self.config[str_guild_id].get("appeal_server"):
            appeal_id = self.config[str_guild_id].get("appeal_server")
            guild = self.bot.get_guild(int(appeal_id))
            return guild.name if guild else "Unknown Server"
        

        if str_guild_id in self.config and self.config[str_guild_id].get("main_server"):
            main_id = self.config[str_guild_id].get("main_server")

            for server_id, config in self.config.items():
                if config.get("main_server") == main_id and config.get("appeal_server"):
                    appeal_id = config.get("appeal_server")
                    guild = self.bot.get_guild(int(appeal_id))
                    return guild.name if guild else "Unknown Server"
        
        return None
    
    def get_pending_appeals_count(self, guild_id: int) -> int:
        str_guild_id = str(guild_id)
        if str_guild_id in self.appeals:
            return sum(1 for appeal in self.appeals[str_guild_id].values() if appeal["status"] == "pending")
        return 0
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild_id = str(member.guild.id)
        

        if guild_id in self.config:
            main_server_id = self.config[guild_id].get("main_server")
            if not main_server_id:
                return
                
            main_guild = self.bot.get_guild(int(main_server_id))
            if not main_guild:
                return
                
            try:
                ban_entry = await main_guild.fetch_ban(member)

                embed = discord.Embed(
                    title="🔒 You are banned from our community server",
                    description=(
                        f"You are currently banned from **{main_guild.name}**.\n\n"
                        f"If you believe this was a mistake or want to appeal your ban, "
                        f"you can submit an appeal using the button below."
                    ),
                    color=discord.Color.dark_red()
                )
                
                try:
                    await member.send(embed=embed, view=AppealView(self, member, main_guild))
                except discord.Forbidden:

                    welcome_channel = discord.utils.get(member.guild.text_channels, name="welcome")
                    if welcome_channel:
                        await welcome_channel.send(
                            f"{member.mention} You appear to be banned from our community server. "
                            f"You can submit an appeal using the button below.",
                            embed=embed,
                            view=AppealView(self, member, main_guild)
                        )
            except discord.NotFound:

                pass
    
    async def create_appeal(self, user_id: int, guild_id: int, reason: str, files=None) -> bool:
        str_guild_id = str(guild_id)
        str_user_id = str(user_id)
        
        if str_guild_id not in self.appeals:
            self.appeals[str_guild_id] = {}
            
        self.appeals[str_guild_id][str_user_id] = {
            "reason": reason,
            "status": "pending",
            "timestamp": datetime.now().isoformat(),
            "reviewed_by": None,
            "review_notes": None,
            "files": files or []
        }
        
        self.save_appeals()
        

        if str_guild_id in self.config:
            appeal_channel_id = self.config[str_guild_id].get("appeal_channel")
            if appeal_channel_id:
                channel = self.bot.get_channel(int(appeal_channel_id))
                if channel:
                    user = await self.bot.fetch_user(user_id)
                    embed = discord.Embed(
                        title="🔔 New Ban Appeal",
                        description=f"**User**: {user.name} ({user.id})\n\n**Reason**:\n{reason}",
                        color=discord.Color.dark_gray()
                    )
                    
                    if files and len(files) > 0:
                        file_list = "\n".join([f"• [{file['filename']}]({file['url']})" for file in files])
                        embed.add_field(
                            name=f"📎 Attachments ({len(files)})",
                            value=file_list,
                            inline=False
                        )
                    
                    embed.set_thumbnail(url=user.display_avatar.url)
                    embed.timestamp = datetime.now()
                    
                    await channel.send(embed=embed, view=AppealReviewView(self, user_id, guild_id))
        
        return True




class SetupView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
    
    
    @discord.ui.button(label="Set Appeal/main Server", style=discord.ButtonStyle.secondary, emoji="🔄", row=0)
    async def set_appeal_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AppealServerModal(self.cog))
    
    @discord.ui.button(label="Set Appeal Notification Channel", style=discord.ButtonStyle.secondary, emoji="📢", row=1)
    async def set_appeal_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        
        if guild_id not in self.cog.config:
            self.cog.config[guild_id] = {}
            
        self.cog.config[guild_id]["appeal_channel"] = channel_id
        self.cog.save_config()
        

        if self.cog.config.get(guild_id, {}).get("appeal_channel") == channel_id:
            embed = discord.Embed(
                title="📢 Appeal Notification Channel Set",
                description=(
                    f"This channel (#{interaction.channel.name}) has been set as the **appeal notification channel**.\n\n"
                    f"**What this means:**\n"
                    f"• New ban appeals will be posted in this channel\n"
                    f"• File attachments from appeals will be shown here\n"
                    f"• Staff can review, approve, or deny appeals from here\n"
                    f"• Make sure appropriate staff have access to this channel"
                ),
                color=discord.Color.dark_blue()
            )
            

            sample_embed = discord.Embed(
                title="🔔 Sample Appeal Notification",
                description="This is how appeal notifications will appear in this channel:",
                color=discord.Color.dark_gray()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            

            sample_appeal_embed = discord.Embed(
                title="🔔 Sample Ban Appeal",
                description=f"**User**: Example User (123456789)\n\n**Reason**:\nThis is a sample appeal reason.",
                color=discord.Color.dark_gray()
            )
            
            sample_appeal_embed.add_field(
                name="📎 Attachments (2)",
                value="• [evidence1.png](https://example.com/evidence1.png)\n• [screenshot.jpg](https://example.com/screenshot.jpg)",
                inline=False
            )
            
            sample_appeal_embed.set_footer(text="This is just a sample to show how appeals will appear")
            

            await interaction.followup.send(embed=sample_appeal_embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ There was an error setting the appeal notification channel. Please try again.", ephemeral=True)



class CommunityServerModal(discord.ui.Modal, title="Set Community Server"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        
        self.server_id = discord.ui.TextInput(
            label="Community Server ID",
            placeholder="Enter the ID of the server where users are banned from",
            required=True
        )
        
        self.add_item(self.server_id)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            server_id = int(self.server_id.value)
            server = interaction.client.get_guild(server_id)
            
            if not server:
                return await interaction.response.send_message(
                    "❌ I couldn't find that server. Make sure:\n"
                    "• I'm a member of the server\n"
                    "• The ID is correct\n"
                    "• I have ban permissions there", 
                    ephemeral=True
                )
            

            str_server_id = str(server_id)
            if str_server_id not in self.cog.config:
                self.cog.config[str_server_id] = {}
                
            self.cog.config[str_server_id]["main_server"] = str_server_id
            self.cog.save_config()
            
            embed = discord.Embed(
                title="✅ Community Server Set",
                description=(
                    f"**{server.name}** has been set as your **Community Server**.\n\n"
                    f"**What this means:**\n"
                    f"• This is the server where users are banned from\n"
                    f"• Approved appeals will unban users from this server\n"
                    f"• You'll need to set up an Appeal Server where banned users can go"
                ),
                color=discord.Color.dark_green()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Please enter a valid server ID.", ephemeral=True)


class AppealServerModal(discord.ui.Modal, title="Set Appeal Server"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        
        self.community_id = discord.ui.TextInput(
            label="Community Server ID",
            placeholder="ID of the server where users are banned from",
            required=True
        )
        
        self.appeal_id = discord.ui.TextInput(
            label="Appeal Server ID",
            placeholder="ID of the server where users submit appeals",
            required=True
        )
        
        self.add_item(self.community_id)
        self.add_item(self.appeal_id)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            community_id = int(self.community_id.value)
            appeal_id = int(self.appeal_id.value)
            
            community_guild = interaction.client.get_guild(community_id)
            appeal_guild = interaction.client.get_guild(appeal_id)
            
            if not community_guild:
                return await interaction.response.send_message(
                    "❌ I couldn't find the community server. Make sure:\n"
                    "• I'm a member of the server\n"
                    "• The ID is correct\n"
                    "• I have ban permissions there", 
                    ephemeral=True
                )
                
            if not appeal_guild:
                return await interaction.response.send_message(
                    "❌ I couldn't find the appeal server. Make sure:\n"
                    "• I'm a member of the server\n"
                    "• The ID is correct", 
                    ephemeral=True
                )
            

            str_community_id = str(community_id)
            if str_community_id not in self.cog.config:
                self.cog.config[str_community_id] = {}
            

            str_appeal_id = str(appeal_id)
            if str_appeal_id not in self.cog.config:
                self.cog.config[str_appeal_id] = {}
            


            self.cog.config[str_community_id]["main_server"] = str_community_id
            self.cog.config[str_appeal_id]["main_server"] = str_community_id
            self.cog.config[str_appeal_id]["appeal_server"] = str_appeal_id
            
            self.cog.save_config()
            
            embed = discord.Embed(
                title="✅ Servers Linked",
                description=(
                    f"**Community Server**: {community_guild.name}\n"
                    f"**Appeal Server**: {appeal_guild.name}\n\n"
                    f"The servers have been successfully linked. Banned users from {community_guild.name} "
                    f"will be able to submit appeals when they join {appeal_guild.name}.\n\n"
                    f"Don't forget to set an appeal notification channel!"
                ),
                color=discord.Color.dark_green()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Please enter valid server IDs.", ephemeral=True)


class BanManagementView(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
    
    @discord.ui.button(label="View Appeals", style=discord.ButtonStyle.secondary, emoji="📋")
    async def view_appeals(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.cog.appeals or not self.cog.appeals[guild_id]:
            return await interaction.response.send_message("There are no appeals for this server.", ephemeral=True)
        
        appeals = self.cog.appeals[guild_id]
        
        embed = discord.Embed(
            title="📋 Ban Appeals",
            description="List of all ban appeals for this server",
            color=discord.Color.dark_gray()
        )
        
        for user_id, appeal in appeals.items():
            user = await self.cog.bot.fetch_user(int(user_id))
            status_emoji = "🟡" if appeal["status"] == "pending" else "🟢" if appeal["status"] == "approved" else "🔴"
            
            embed.add_field(
                name=f"{status_emoji} {user.name} ({user.id})",
                value=f"**Status**: {appeal['status'].capitalize()}\n"
                      f"**Submitted**: <t:{int(datetime.fromisoformat(appeal['timestamp']).timestamp())}:R>",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Setup", style=discord.ButtonStyle.primary, emoji="⚙️")
    async def setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🛡️ Ban Appeal System Setup",
            description=(
                "The ban appeal system lets you manage bans across two servers:\n\n"
                "**Community Server**: Your main server where users are banned from\n"
                "**Appeal Server**: A separate server where banned users can submit appeals\n\n"
                "Use the buttons below to configure the system:"
            ),
            color=discord.Color.from_rgb(64, 64, 64)
        )
        await interaction.response.send_message(embed=embed, view=SetupView(self.cog), ephemeral=True)
    
    @discord.ui.button(label="Ban User", style=discord.ButtonStyle.danger, emoji="🔨")
    async def ban_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BanUserModal(self.cog))


class BanUserModal(discord.ui.Modal, title="Ban User"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        
        self.user_id = discord.ui.TextInput(
            label="User ID",
            placeholder="Enter the user ID to ban",
            required=True
        )
        
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Enter the reason for the ban",
            style=discord.TextStyle.paragraph,
            required=True
        )
        
        self.add_item(self.user_id)
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_id.value)
            reason = self.reason.value
            
            try:
                user = await self.cog.bot.fetch_user(user_id)
                await interaction.guild.ban(user, reason=reason)
                
                embed = discord.Embed(
                    title="🔨 User Banned",
                    description=f"**User**: {user.name} ({user.id})\n**Reason**: {reason}",
                    color=discord.Color.dark_red()
                )
                embed.set_thumbnail(url=user.display_avatar.url)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except discord.NotFound:
                await interaction.response.send_message("User not found.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("I don't have permission to ban that user.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Please enter a valid user ID.", ephemeral=True)


class AppealView(discord.ui.View):
    def __init__(self, cog, member, main_guild):
        super().__init__(timeout=None)
        self.cog = cog
        self.member = member
        self.main_guild = main_guild
    
    @discord.ui.button(label="Submit Ban Appeal", style=discord.ButtonStyle.danger, emoji="🔓", custom_id="submit_appeal")
    async def submit_appeal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.member.id:
            return await interaction.response.send_message("This appeal form is not for you.", ephemeral=True)
        
        await interaction.response.send_modal(AppealFormModal(self.cog, self.main_guild.id))


class AppealFormModal(discord.ui.Modal, title="Ban Appeal Form"):
    def __init__(self, cog, guild_id):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        
        self.appeal_reason = discord.ui.TextInput(
            label="Why should we unban you?",
            style=discord.TextStyle.paragraph,
            placeholder="Explain why you should be unbanned...",
            required=True,
            max_length=1000
        )
        
        self.add_item(self.appeal_reason)
    
    async def on_submit(self, interaction: discord.Interaction):

        await interaction.response.send_message(
            "Your appeal reason has been recorded. Would you like to attach evidence or screenshots to support your appeal?",
            view=AppealFileUploadView(self.cog, interaction.user.id, self.guild_id, self.appeal_reason.value),
            ephemeral=True
        )











class AppealFileUploadView(discord.ui.View):
    def __init__(self, cog, user_id, guild_id, reason):
        super().__init__(timeout=600)  # 10 minute timeout for file upload
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.reason = reason
        self.files = []
        self.waiting_for_files = False
    
    @discord.ui.button(label="Upload Evidence", style=discord.ButtonStyle.primary, emoji="📎")
    async def upload_file(self, interaction: discord.Interaction, button: discord.ui.Button):

        if self.waiting_for_files:
            return await interaction.response.send_message(
                "Already waiting for file upload. Please upload your files or wait for the timeout.",
                ephemeral=True
            )
        
        self.waiting_for_files = True
        
        await interaction.response.send_message(
            "Please upload your evidence or screenshots in your next message (up to 25MB). "
            "You can attach multiple files to a single message. "
            "You have 2 minutes to upload.",
            ephemeral=True
        )
        

        try:
            def check(m):
                return m.author.id == interaction.user.id and len(m.attachments) > 0
            
            message = await self.cog.bot.wait_for('message', check=check, timeout=120)
            

            for attachment in message.attachments:
                if attachment.size <= 25 * 1024 * 1024:  # 25MB limit
                    self.files.append({
                        "filename": attachment.filename,
                        "url": attachment.url,
                        "size": attachment.size
                    })
            

            try:
                await message.delete()
            except:
                pass
            
            file_names = ", ".join([file["filename"] for file in self.files[-len(message.attachments):]])
            
            try:
                await interaction.followup.send(
                    f"✅ Files uploaded: {file_names}\n"
                    f"Total files: {len(self.files)}\n"
                    f"You can upload more files or submit your appeal when ready.",
                    ephemeral=True
                )
            except discord.NotFound:

                if isinstance(message.channel, discord.DMChannel):
                    await message.channel.send(
                        f"✅ Files uploaded: {file_names}\n"
                        f"Total files: {len(self.files)}\n"
                        f"You can upload more files or submit your appeal when ready."
                    )
            
        except asyncio.TimeoutError:
            try:
                await interaction.followup.send(
                    "File upload timed out. You can try again or submit without files.", 
                    ephemeral=True
                )
            except discord.NotFound:
                pass
        
        self.waiting_for_files = False
    
    @discord.ui.button(label="Submit Appeal", style=discord.ButtonStyle.success, emoji="✅")
    async def submit_appeal(self, interaction: discord.Interaction, button: discord.ui.Button):

        for child in self.children:
            child.disabled = True
            
        try:
            await interaction.response.edit_message(view=self)
        except:

            pass
            

        success = await self.cog.create_appeal(
            self.user_id,
            self.guild_id,
            self.reason,
            self.files
        )
        
        if success:
            embed = discord.Embed(
                title="✅ Appeal Submitted",
                description=(
                    "Your ban appeal has been submitted and will be reviewed by our staff team.\n\n"
                    f"**Files Attached**: {len(self.files)}\n\n"
                    "You will be notified via DM when a decision has been made on your appeal.\n"
                    "Please make sure your DMs are open to receive the notification."
                ),
                color=discord.Color.dark_green()
            )
            
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except discord.NotFound:

                user = await self.cog.bot.fetch_user(self.user_id)
                try:
                    await user.send(embed=embed)
                except:
                    pass
        else:
            try:
                await interaction.followup.send(
                    "There was an error submitting your appeal. Please try again later.", 
                    ephemeral=True
                )
            except:
                pass
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):

        for child in self.children:
            child.disabled = True
            
        try:
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("Appeal submission cancelled.", ephemeral=True)
        except:

            try:
                await interaction.response.send_message("Appeal submission cancelled.", ephemeral=True)
            except:
                pass












class AppealReviewView(discord.ui.View):
    def __init__(self, cog, user_id, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.custom_id_prefix = f"appeal_{user_id}_{guild_id}"
    
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✅", custom_id="approve_appeal")
    async def approve_appeal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReviewModal(self.cog, self.user_id, self.guild_id, "approved"))
    
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="❌", custom_id="deny_appeal")
    async def deny_appeal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReviewModal(self.cog, self.user_id, self.guild_id, "denied"))
    
    @discord.ui.button(label="View Details", style=discord.ButtonStyle.secondary, emoji="🔍", custom_id="view_details")
    async def view_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        str_guild_id = str(self.guild_id)
        str_user_id = str(self.user_id)
        
        if str_guild_id not in self.cog.appeals or str_user_id not in self.cog.appeals[str_guild_id]:
            return await interaction.response.send_message("Appeal not found.", ephemeral=True)
        
        appeal = self.cog.appeals[str_guild_id][str_user_id]
        user = await self.cog.bot.fetch_user(self.user_id)
        
        embed = discord.Embed(
            title=f"Appeal from {user.name}",
            description=f"**User ID**: {self.user_id}\n**Status**: {appeal['status'].capitalize()}",
            color=discord.Color.dark_gray()
        )
        
        embed.add_field(
            name="Appeal Reason",
            value=appeal["reason"] or "No reason provided",
            inline=False
        )
        

        if appeal.get("files"):
            file_list = "\n".join([f"• [{file['filename']}]({file['url']})" for file in appeal["files"]])
            embed.add_field(
                name=f"📎 Attachments ({len(appeal['files'])})",
                value=file_list,
                inline=False
            )
        
        if appeal["review_notes"]:
            embed.add_field(
                name="Review Notes",
                value=appeal["review_notes"],
                inline=False
            )
        
        if appeal["reviewed_by"]:
            reviewer = await self.cog.bot.fetch_user(int(appeal["reviewed_by"]))
            embed.add_field(
                name="Reviewed By",
                value=f"{reviewer.name} ({reviewer.id})",
                inline=False
            )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.timestamp = datetime.fromisoformat(appeal["timestamp"])
        
        await interaction.response.send_message(embed=embed, ephemeral=True)



class ReviewModal(discord.ui.Modal, title="Review Ban Appeal"):
    def __init__(self, cog, user_id, guild_id, decision):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.decision = decision
        
        self.notes = discord.ui.TextInput(
            label="Review Notes",
            style=discord.TextStyle.paragraph,
            placeholder="Enter your notes for this decision...",
            required=True
        )
        
        self.add_item(self.notes)
    
    async def on_submit(self, interaction: discord.Interaction):
        str_guild_id = str(self.guild_id)
        str_user_id = str(self.user_id)
        
        if str_guild_id not in self.cog.appeals or str_user_id not in self.cog.appeals[str_guild_id]:
            return await interaction.response.send_message("Appeal not found.", ephemeral=True)
        

        self.cog.appeals[str_guild_id][str_user_id]["status"] = self.decision
        self.cog.appeals[str_guild_id][str_user_id]["review_notes"] = self.notes.value
        self.cog.appeals[str_guild_id][str_user_id]["reviewed_by"] = str(interaction.user.id)
        self.cog.save_appeals()
        

        if self.decision == "approved":
            main_guild = self.cog.bot.get_guild(self.guild_id)
            if main_guild:
                try:
                    user = await self.cog.bot.fetch_user(self.user_id)
                    await main_guild.unban(user, reason=f"Ban appeal approved by {interaction.user.name}")
                except (discord.NotFound, discord.Forbidden):
                    pass
        

        user = await self.cog.bot.fetch_user(self.user_id)
        
        decision_color = discord.Color.dark_green() if self.decision == "approved" else discord.Color.dark_red()
        decision_title = "Appeal Approved" if self.decision == "approved" else "Appeal Denied"
        decision_emoji = "✅" if self.decision == "approved" else "❌"
        
        embed = discord.Embed(
            title=f"{decision_emoji} {decision_title}",
            description=f"Your ban appeal for **{self.cog.bot.get_guild(self.guild_id).name}** has been reviewed.",
            color=decision_color
        )
        
        embed.add_field(
            name="Decision",
            value=f"Your appeal has been **{self.decision}**.",
            inline=False
        )
        
        if self.notes.value:
            embed.add_field(
                name="Staff Notes",
                value=self.notes.value,
                inline=False
            )
        
        if self.decision == "approved":
            embed.add_field(
                name="Next Steps",
                value="You can now rejoin the server using a new invite link.",
                inline=False
            )
        
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            pass
        

        staff_embed = discord.Embed(
            title=f"{decision_emoji} Appeal {self.decision.capitalize()}",
            description=f"You have {self.decision} the ban appeal for {user.name} ({user.id}).",
            color=decision_color
        )
        
        await interaction.response.send_message(embed=staff_embed, ephemeral=True)
        

        if interaction.message:
            original_embed = interaction.message.embeds[0]
            original_embed.color = decision_color
            original_embed.title = f"{decision_emoji} {original_embed.title} - {self.decision.capitalize()}"
            
            await interaction.message.edit(embed=original_embed, view=None)


def setup(bot):

    cog = BanAppealSystem(bot)
    

    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    

    return cog


