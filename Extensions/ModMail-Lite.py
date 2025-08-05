import discord
from discord.ext import commands
import asyncio
import datetime
import json
import os
import traceback


__author__ = "TheHolyOneZ"
__version__ = "1.2.0"
__copyright__ = "Copyright (c) TheHolyOneZ 2025"


DEBUG = {
    "ENABLED": False,
    "LOG_THREAD_LOOKUP": False,
    "LOG_THREAD_MESSAGES": False,
    "PRINT_THREAD_IDS": False,
    "VERBOSE_ERRORS": False
}

class ModMailLite(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/TheZModMail/modmail_config.json"
        self.threads_file = "data/TheZModMail/modmail_threads.json"
        self.active_threads = {}
        self.pending_reports = {}
        self.load_config()
        self.load_user_threads()
    
    def debug_log(self, message, level="INFO"):
        
        if DEBUG["ENABLED"]:
            print(f"[ModMail {level}] {message}")
    
    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {}
            self.save_config()
    
    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)
    
    def load_user_threads(self):
        if os.path.exists(self.threads_file):
            with open(self.threads_file, 'r') as f:
                self.active_threads = json.load(f)
        else:
            self.active_threads = {}
            self.save_user_threads()
    
    def save_user_threads(self):
        with open(self.threads_file, 'w') as f:
            json.dump(self.active_threads, f, indent=4)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        if isinstance(message.channel, discord.DMChannel):
            await self.handle_dm_message(message)
        elif isinstance(message.channel, discord.Thread):
            await self.handle_thread_message(message)
    
    async def handle_dm_message(self, message):
        user_id = str(message.author.id)
        content = message.content.strip()
        

        for guild_id, settings in self.config.items():
            if "blocked_users" in settings and user_id in settings.get("blocked_users", {}):
                guild = self.bot.get_guild(int(guild_id))
                if guild and message.author in guild.members:
                    block_info = settings['blocked_users'][user_id]
                    block_embed = discord.Embed(
                        title="Access Denied",
                        description=f"You are blocked from using ModMail in **{guild.name}**.",
                        color=discord.Color.red()
                    )
                    block_embed.add_field(name="Reason", value=block_info['reason'], inline=False)
                    block_embed.add_field(name="Blocked On", value=datetime.datetime.fromisoformat(block_info['blocked_at']).strftime("%Y-%m-%d"), inline=False)
                    block_embed.set_footer(text=f"If you believe this is an error, please contact a server administrator. | Made by {__author__}")
                    await message.author.send(embed=block_embed)
                    return
        

        if content.lower() == "!report" and user_id not in self.pending_reports and user_id not in self.active_threads:

            mutual_guilds = []
            for guild_id, settings in self.config.items():
                guild = self.bot.get_guild(int(guild_id))
                if guild and message.author in guild.members:
                    mutual_guilds.append((guild_id, guild, settings))
            
            if not mutual_guilds:
                no_guild_embed = discord.Embed(
                    title="No Available Servers",
                    description="I couldn't find any mutual servers with ModMail enabled.",
                    color=discord.Color.red()
                )
                no_guild_embed.set_footer(text=f"Made by {__author__}")
                await message.author.send(embed=no_guild_embed)
                return
            

            if len(mutual_guilds) > 1:
                guild_list = "\n".join([f"{idx+1}. {guild.name}" for idx, (_, guild, _) in enumerate(mutual_guilds)])
                selection_embed = discord.Embed(
                    title="Select a Server",
                    description="Please select which server you want to contact by replying with the number:",
                    color=discord.Color.blue()
                )
                selection_embed.add_field(name="Available Servers", value=guild_list, inline=False)
                selection_embed.set_footer(text=f"Reply with a number (e.g., 1) | Made by {__author__}")
                
                await message.author.send(embed=selection_embed)
                
                def check(m):
                    return m.author.id == message.author.id and isinstance(m.channel, discord.DMChannel)
                
                try:
                    reply = await self.bot.wait_for('message', check=check, timeout=60.0)
                    try:
                        selection = int(reply.content.strip()) - 1
                        if 0 <= selection < len(mutual_guilds):
                            guild_id, guild, settings = mutual_guilds[selection]
                        else:
                            error_embed = discord.Embed(
                                title="Invalid Selection",
                                description=f"Please try again with `!report` and select a number between 1 and {len(mutual_guilds)}.",
                                color=discord.Color.red()
                            )
                            error_embed.set_footer(text=f"Made by {__author__}")
                            await message.author.send(embed=error_embed)
                            return
                    except ValueError:
                        error_embed = discord.Embed(
                            title="Invalid Selection",
                            description="Please try again with `!report` and enter a valid number.",
                            color=discord.Color.red()
                        )
                        error_embed.set_footer(text=f"Made by {__author__}")
                        await message.author.send(embed=error_embed)
                        return
                except asyncio.TimeoutError:
                    timeout_embed = discord.Embed(
                        title="Selection Timed Out",
                        description="Please try again with `!report`.",
                        color=discord.Color.red()
                    )
                    timeout_embed.set_footer(text=f"Made by {__author__}")
                    await message.author.send(embed=timeout_embed)
                    return
            else:
                guild_id, guild, settings = mutual_guilds[0]
            

            self.pending_reports[user_id] = {
                "guild_id": str(guild_id),  
                "timestamp": datetime.datetime.now().isoformat(),
                "server_name": guild.name
            }
            

            report_embed = discord.Embed(
                title="ModMail Report Started",
                description="Everything you send now will be forwarded to the staff team. Please describe your issue or concern in detail.",
                color=discord.Color.blue()
            )
            report_embed.add_field(name="Server", value=guild.name, inline=False)
            report_embed.add_field(name="To Cancel", value="Type `!cancel` to cancel this report", inline=False)
            report_embed.add_field(name="Attachments", value="You can include images or files with your message", inline=False)
            report_embed.set_footer(text=f"Your messages will be sent to staff until the conversation is closed | Made by {__author__}")
            
            await message.author.send(embed=report_embed)
            return
        

        elif content.lower() == "!cancel" and user_id in self.pending_reports:
            server_name = self.pending_reports[user_id].get("server_name", "the server")
            del self.pending_reports[user_id]
            
            cancel_embed = discord.Embed(
                title="Report Canceled",
                description=f"Your report to **{server_name}** has been canceled.",
                color=discord.Color.orange()
            )
            cancel_embed.add_field(name="Start Again", value="Type `!report` to start a new report", inline=False)
            cancel_embed.set_footer(text=f"Made by {__author__}")
            
            await message.author.send(embed=cancel_embed)
            return
        

        elif content.lower() == "!help":
            help_embed = discord.Embed(
                title="ModMail Help",
                description="Here are the commands you can use in direct messages:",
                color=discord.Color.blue()
            )
            help_embed.add_field(name="!report", value="Start a new ModMail conversation", inline=False)
            help_embed.add_field(name="!cancel", value="Cancel a pending report", inline=False)
            help_embed.add_field(name="!close", value="Request to close your active conversation", inline=False)
            help_embed.add_field(name="!status", value="Check if you have any active conversations", inline=False)
            help_embed.set_footer(text=f"Made by {__author__}")
            
            await message.author.send(embed=help_embed)
            return
        

        elif content.lower() == "!status":
            if user_id in self.active_threads:
                thread_info = self.active_threads[user_id]
                guild_id = thread_info["guild_id"]
                guild = self.bot.get_guild(int(guild_id))
                
                if guild:
                    status_embed = discord.Embed(
                        title="Active Conversation",
                        description=f"You have an active ModMail conversation with **{guild.name}**.",
                        color=discord.Color.green()
                    )
                    
                    if thread_info["claimed_by"]:
                        staff = guild.get_member(thread_info["claimed_by"])
                        if staff:
                            status_embed.add_field(name="Assigned Staff", value=staff.display_name, inline=False)
                    
                    started_time = datetime.datetime.fromisoformat(thread_info["started_at"])
                    time_elapsed = datetime.datetime.now() - started_time
                    hours, remainder = divmod(int(time_elapsed.total_seconds()), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m {seconds}s"
                    status_embed.add_field(name="Conversation Age", value=time_str, inline=False)
                    status_embed.set_footer(text=f"Made by {__author__}")
                    
                    await message.author.send(embed=status_embed)
                else:
                    await message.author.send(f"You have an active conversation, but I can no longer access the server. | Made by {__author__}")
            elif user_id in self.pending_reports:
                server_name = self.pending_reports[user_id].get("server_name", "a server")
                await message.author.send(f"You're currently starting a report to **{server_name}**. Please describe your issue or type `!cancel` to cancel. | Made by {__author__}")
            else:
                await message.author.send(f"You don't have any active ModMail conversations. Type `!report` to start one. | Made by {__author__}")
            return
        

        elif content.lower() == "!close" and user_id in self.active_threads:
            thread_info = self.active_threads[user_id]
            guild_id = thread_info["guild_id"]
            thread_id = thread_info["thread_id"]
            
            guild = self.bot.get_guild(int(guild_id))
            
            if not guild:
                await message.author.send(f"I can no longer access the server for this conversation. The conversation has been closed. | Made by {__author__}")
                del self.active_threads[user_id]
                self.save_user_threads()
                return
            

            thread = None
            

            thread = guild.get_channel(int(thread_id))
            

            if not thread and guild_id in self.config:
                modmail_channel_id = self.config[guild_id].get("channel_id")
                if modmail_channel_id:
                    modmail_channel = guild.get_channel(int(modmail_channel_id))
                    if modmail_channel:

                        for t in modmail_channel.threads:
                            if str(t.id) == str(thread_id):
                                thread = t
                                self.debug_log(f"Found thread {thread_id} in active threads of ModMail channel")
                                break
                        

                        if not thread:
                            try:
                                thread = await modmail_channel.fetch_thread(int(thread_id))
                                self.debug_log(f"Found thread {thread_id} via direct fetch")
                            except Exception as e:
                                self.debug_log(f"Error fetching thread: {str(e)}")
            
            if not thread:
                self.debug_log(f"Thread {thread_id} not found, closing conversation")
                await message.author.send(f"The conversation thread was not found. The conversation has been closed. | Made by {__author__}")
                del self.active_threads[user_id]
                self.save_user_threads()
                return
            
            close_request_embed = discord.Embed(
                title="Close Request",
                description=f"**{message.author.name}** has requested to close this conversation.",
                color=discord.Color.gold(),
                timestamp=datetime.datetime.now()
            )
            close_request_embed.set_footer(text=f"Made by {__author__}")
            await thread.send(embed=close_request_embed)
            
            await message.author.send(f"I've notified the staff that you'd like to close this conversation. They'll close it soon. | Made by {__author__}")
            return
        

        elif user_id in self.pending_reports:
            try:
                guild_id = self.pending_reports[user_id]["guild_id"]
                guild = self.bot.get_guild(int(guild_id))
                
                if not guild:
                    await message.author.send(f"I can no longer access the server. Report canceled. | Made by {__author__}")
                    del self.pending_reports[user_id]
                    return
                
                settings = self.config[guild_id]
                

                modmail_channel = guild.get_channel(int(settings["channel_id"]))
                if not modmail_channel:
                    await message.author.send(f"ModMail channel not found. Please contact server administrators directly. | Made by {__author__}")
                    del self.pending_reports[user_id]
                    return
                

                thread_name = f"ModMail: {message.author.name}"
                self.debug_log(f"Creating thread '{thread_name}' in channel {modmail_channel.id}")
                
                thread = await modmail_channel.create_thread(
                    name=thread_name,
                    auto_archive_duration=1440
                )
                

                self.active_threads[user_id] = {
                    "thread_id": str(thread.id),  
                    "guild_id": str(guild_id),   
                    "parent_channel_id": str(modmail_channel.id),  
                    "claimed_by": None,
                    "anonymous_mode": False,    
                    "exclusive_mode": True,      
                    "started_at": datetime.datetime.now().isoformat()
                }
                

                self.save_user_threads()
                

                del self.pending_reports[user_id]
                

                user_info_embed = discord.Embed(
                    title="New ModMail Conversation",
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now()
                )
                user_info_embed.set_footer(text=f"Made by {__author__}")
                
                member = guild.get_member(message.author.id)
                roles_str = ", ".join([role.mention for role in member.roles if role.name != "@everyone"]) if member else "No roles"
                
                user_info_embed.add_field(name="User", value=f"{message.author.mention} ({message.author.id})", inline=False)
                user_info_embed.add_field(name="Account Created", value=f"<t:{int(message.author.created_at.timestamp())}:F>", inline=True)
                
                if member and member.joined_at:
                    user_info_embed.add_field(name="Joined Server", value=f"<t:{int(member.joined_at.timestamp())}:F>", inline=True)
                    user_info_embed.add_field(name="Roles", value=roles_str if roles_str else "No roles", inline=False)
                
                user_info_embed.set_thumbnail(url=message.author.display_avatar.url)
                
                await thread.send(embed=user_info_embed)
                

                commands_embed = discord.Embed(
                    title="Staff Commands",
                    color=discord.Color.gold(),
                    description="Available commands in this thread:"
                )
                commands_embed.add_field(name="!modmail claim", value="Claim this conversation", inline=True)
                commands_embed.add_field(name="!modmail close [reason]", value="Close this conversation", inline=True)
                commands_embed.add_field(name="!modmail anonymous <message>", value="Send anonymous message", inline=True)
                commands_embed.add_field(name="!modmail anonymous_mode", value="Toggle anonymous mode", inline=True)
                commands_embed.add_field(name="!modmail exclusive_mode", value="Toggle exclusive mode", inline=True)
                commands_embed.add_field(name="!modmail transfer @member", value="Transfer to another staff", inline=True)
                commands_embed.add_field(name="!modmail export", value="Export conversation", inline=True)
                commands_embed.set_footer(text=f"Made by {__author__}")
                
                await thread.send(embed=commands_embed)
                

                user_message_embed = discord.Embed(
                    description=message.content,
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.now()
                )
                user_message_embed.set_author(name=f"{message.author.name}", icon_url=message.author.display_avatar.url)
                user_message_embed.set_footer(text=f"Made by {__author__}")
                
                if message.attachments:
                    attachment_links = []
                    for attachment in message.attachments:
                        attachment_links.append(f"[{attachment.filename}]({attachment.url})")
                    user_message_embed.add_field(name="Attachments", value="\n".join(attachment_links), inline=False)
                
                await thread.send(embed=user_message_embed)
                

                if "staff_role_id" in settings and settings["staff_role_id"]:
                    staff_role = guild.get_role(int(settings["staff_role_id"]))
                    if staff_role:
                        await thread.send(f"{staff_role.mention} A new ModMail conversation has been started.")
                

                confirm_embed = discord.Embed(
                    title="Report Sent",
                    description="Your message has been sent to the staff team. We'll respond as soon as possible.",
                    color=discord.Color.green()
                )
                confirm_embed.add_field(name="Server", value=guild.name, inline=False)
                confirm_embed.add_field(name="Close Request", value="Type `!close` if you want to close this conversation", inline=False)
                confirm_embed.set_footer(text=f"Made by {__author__}")
                
                await message.author.send(embed=confirm_embed)
                
            except Exception as e:
                error_embed = discord.Embed(
                    title="Error Creating Thread",
                    description=f"There was an error creating your ModMail thread: {str(e)}",
                    color=discord.Color.red()
                )
                error_embed.add_field(name="Try Again", value="Please try again later or contact a server administrator directly.", inline=False)
                error_embed.set_footer(text=f"Made by {__author__}")
                await message.author.send(embed=error_embed)
                

                self.debug_log(f"ModMail error for user {message.author.id}: {str(e)}", level="ERROR")
                if DEBUG["VERBOSE_ERRORS"]:
                    self.debug_log(traceback.format_exc(), level="ERROR")
                
                if user_id in self.pending_reports:
                    del self.pending_reports[user_id]
                return
        

        elif user_id in self.active_threads:
            try:
                thread_info = self.active_threads[user_id]
                guild_id = thread_info["guild_id"]
                thread_id = thread_info["thread_id"]
                
                self.debug_log(f"Processing message from user {user_id} for thread {thread_id}")
                
                guild = self.bot.get_guild(int(guild_id))
                
                if not guild:
                    self.debug_log(f"Guild {guild_id} not found, closing conversation")
                    error_embed = discord.Embed(
                        title="Server Unavailable",
                        description="I can no longer access the server for this conversation. The conversation has been closed.",
                        color=discord.Color.red()
                    )
                    error_embed.set_footer(text=f"Made by {__author__}")
                    await message.author.send(embed=error_embed)
                    del self.active_threads[user_id]
                    self.save_user_threads()
                    return
                

                thread = None
                

                thread = guild.get_channel(int(thread_id))
                

                if not thread and "parent_channel_id" in thread_info:
                    parent_channel = guild.get_channel(int(thread_info["parent_channel_id"]))
                    if parent_channel:

                        for t in parent_channel.threads:
                            if str(t.id) == str(thread_id):
                                thread = t
                                self.debug_log(f"Found thread {thread_id} in active threads of parent channel")
                                break
                        

                        if not thread:
                            try:
                                thread = await parent_channel.fetch_thread(int(thread_id))
                                self.debug_log(f"Found thread {thread_id} via direct fetch")
                            except Exception as e:
                                self.debug_log(f"Error fetching thread: {str(e)}")
                
                if not thread:
                    self.debug_log(f"Thread {thread_id} not found, closing conversation")
                    error_embed = discord.Embed(
                        title="Thread Not Found",
                        description="The conversation thread was not found. Please start a new conversation.",
                        color=discord.Color.orange()
                    )
                    error_embed.add_field(name="Start New", value="Type `!report` to start a new conversation", inline=False)
                    error_embed.set_footer(text=f"Made by {__author__}")
                    
                    await message.author.send(embed=error_embed)
                    del self.active_threads[user_id]
                    self.save_user_threads()
                    return
                

                user_message_embed = discord.Embed(
                    description=message.content,
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.now()
                )
                user_message_embed.set_author(name=f"{message.author.name}", icon_url=message.author.display_avatar.url)
                user_message_embed.set_footer(text=f"Made by {__author__}")
                
                if message.attachments:
                    attachment_links = []
                    for attachment in message.attachments:
                        attachment_links.append(f"[{attachment.filename}]({attachment.url})")
                    user_message_embed.add_field(name="Attachments", value="\n".join(attachment_links), inline=False)
                
                await thread.send(embed=user_message_embed)
                

                if thread.archived:
                    await thread.edit(archived=False)
                    await thread.send("⚠️ **This thread was archived but has been reopened due to a new message from the user.**")
                

                try:
                    await message.add_reaction("✅")
                except:

                    await message.author.send(f"✅ Message sent to staff. | Made by {__author__}")
            
            except Exception as e:
                self.debug_log(f"Error sending message to thread: {str(e)}", level="ERROR")
                if DEBUG["VERBOSE_ERRORS"]:
                    self.debug_log(traceback.format_exc(), level="ERROR")
                await message.author.send(f"Error sending your message: {str(e)} | Made by {__author__}")
        

        else:
            help_embed = discord.Embed(
                title="ModMail Help",
                description="To start a conversation with server staff, type `!report`",
                color=discord.Color.blue()
            )
            help_embed.add_field(name="Available Commands", value="`!help` - Show this help message\n`!report` - Start a new report\n`!status` - Check active conversations", inline=False)
            help_embed.set_footer(text=f"Made by {__author__}")
            await message.author.send(embed=help_embed)

    async def handle_thread_message(self, message):
        
        if message.author.bot:
            return
        

        if message.content.startswith("!modmail") or message.content.startswith("/modmail"):
            return
        
        if DEBUG["LOG_THREAD_MESSAGES"]:
            self.debug_log(f"Processing message in thread {message.channel.id} from {message.author.name}")
        

        user_id = None
        thread_info = None
        for uid, t_info in self.active_threads.items():
            if DEBUG["LOG_THREAD_LOOKUP"]:
                self.debug_log(f"Comparing with: user={uid}, thread={t_info['thread_id']}, type={type(t_info['thread_id']).__name__}")
                if DEBUG["PRINT_THREAD_IDS"]:
                    self.debug_log(f"Thread IDs: {message.channel.id} == {t_info['thread_id']} ? {str(message.channel.id) == str(t_info['thread_id'])}")
            
            if str(message.channel.id) == str(t_info["thread_id"]):
                user_id = uid
                thread_info = t_info
                self.debug_log(f"Found matching thread for user {uid}")
                break
        
        if not user_id:

            return
        

        exclusive_mode = thread_info.get("exclusive_mode", True)  # Default to True if not set
        if exclusive_mode and thread_info["claimed_by"] and thread_info["claimed_by"] != message.author.id:

            claimer = message.guild.get_member(thread_info["claimed_by"])
            if claimer:
                exclusive_embed = discord.Embed(
                    title="Exclusive Mode Active",
                    description=f"This thread is in exclusive mode and claimed by {claimer.mention}. Only they can respond.",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.now()
                )
                exclusive_embed.add_field(
                    name="Options", 
                    value="• Ask them to disable exclusive mode with `!modmail exclusive_mode`\n• Ask them to transfer the thread to you with `!modmail transfer @you`\n• Administrators can override this restriction",
                    inline=False
                )
                exclusive_embed.set_footer(text=f"Made by {__author__}")
                


                if not message.author.guild_permissions.administrator:
                    await message.channel.send(embed=exclusive_embed)
                    return
                else:

                    await message.channel.send(f"⚠️ **Admin Override**: {message.author.mention} is bypassing exclusive mode as an administrator.")
        

        anonymous_mode = thread_info.get("anonymous_mode", False)  # Default to False if not set
        

        if not thread_info["claimed_by"] and not message.content.startswith("!anonymous"):
            thread_info["claimed_by"] = message.author.id
            self.save_user_threads()
            claim_embed = discord.Embed(
                title="Thread Claimed",
                description=f"This conversation has been automatically claimed by {message.author.mention}",
                color=discord.Color.gold(),
                timestamp=datetime.datetime.now()
            )
            claim_embed.set_footer(text=f"Made by {__author__}")
            await message.channel.send(embed=claim_embed)
        
        try:

            user = await self.bot.fetch_user(int(user_id))
            

            staff_embed = discord.Embed(
                description=message.content,
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            

            if anonymous_mode:
                staff_embed.set_author(name="Staff Team", icon_url=message.guild.icon.url if message.guild.icon else None)
            elif thread_info["claimed_by"] == message.author.id:
                staff_embed.set_author(name=f"{message.author.name} (Staff)", icon_url=message.author.display_avatar.url)
            else:
                staff_embed.set_author(name=f"{message.author.name} (Staff, Not Assigned)", icon_url=message.author.display_avatar.url)
            
            staff_embed.set_footer(text=f"Made by {__author__}")
            

            if message.attachments:
                attachment_links = []
                for attachment in message.attachments:
                    attachment_links.append(f"[{attachment.filename}]({attachment.url})")
                staff_embed.add_field(name="Attachments", value="\n".join(attachment_links), inline=False)
            

            await user.send(embed=staff_embed)
            self.debug_log(f"Sent {'anonymous ' if anonymous_mode else ''}staff message to user {user_id}")
            

            await message.add_reaction("✅")
            
        except discord.Forbidden:
            error_embed = discord.Embed(
                title="Message Not Delivered",
                description="Failed to send message to user. They may have blocked the bot or closed their DMs.",
                color=discord.Color.red()
            )
            error_embed.add_field(name="Suggestion", value="You may want to close this thread as the user cannot receive messages.", inline=False)
            error_embed.set_footer(text=f"Made by {__author__}")
            await message.channel.send(embed=error_embed)
            self.debug_log(f"Failed to send message to user {user_id}: Forbidden", level="WARNING")
            
        except discord.NotFound:
            error_embed = discord.Embed(
                title="User Not Found",
                description="The user associated with this thread could not be found. They may have deleted their account.",
                color=discord.Color.red()
            )
            error_embed.add_field(name="Suggestion", value="You should close this thread as the user no longer exists.", inline=False)
            error_embed.set_footer(text=f"Made by {__author__}")
            await message.channel.send(embed=error_embed)
            self.debug_log(f"Failed to send message to user {user_id}: Not Found", level="WARNING")
            
        except Exception as e:
            error_embed = discord.Embed(
                title="Error Sending Message",
                description=f"An error occurred while sending your message: {str(e)}",
                color=discord.Color.red()
            )
            error_embed.set_footer(text=f"Made by {__author__}")
            await message.channel.send(embed=error_embed)
            self.debug_log(f"Error sending message to user {user_id}: {str(e)}", level="ERROR")
            if DEBUG["VERBOSE_ERRORS"]:
                self.debug_log(traceback.format_exc(), level="ERROR")
    
    @commands.hybrid_group(name="modmail", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def modmail(self, ctx):
        
        embed = discord.Embed(
            title="ModMail Commands",
            color=discord.Color.blue(),
            description="Available ModMail commands:"
        )
        embed.add_field(name="!modmail setup [#channel]", value="Set up ModMail in a channel", inline=False)
        embed.add_field(name="!modmail claim", value="Claim a ModMail thread", inline=False)
        embed.add_field(name="!modmail close [reason]", value="Close a ModMail thread", inline=False)
        embed.add_field(name="!modmail anonymous <message>", value="Send a one-time anonymous message", inline=False)
        embed.add_field(name="!modmail anonymous_mode", value="Toggle anonymous mode for all messages", inline=False)
        embed.add_field(name="!modmail exclusive_mode", value="Toggle exclusive mode (only assigned staff can reply)", inline=False)
        embed.add_field(name="!modmail transfer @member", value="Transfer thread to another staff member", inline=False)
        embed.add_field(name="!modmail export", value="Export the current thread", inline=False)
        embed.add_field(name="!modmail status", value="Show ModMail status", inline=False)
        embed.add_field(name="!modmail debug", value="Debug active threads (admin only)", inline=False)
        embed.set_footer(text=f"Made by {__author__}")
        
        await ctx.send(embed=embed)
    
    @modmail.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_modmail(self, ctx, channel: discord.TextChannel = None):
        
        if not channel:
            channel = ctx.channel
        
        guild_id = str(ctx.guild.id)
        
        self.config[guild_id] = {
            "channel_id": channel.id,
            "use_threads": True,
            "log_channel_id": None,
            "staff_role_id": None,
            "setup_by": ctx.author.id,
            "setup_time": datetime.datetime.now().isoformat()
        }
        
        self.save_config()
        self.debug_log(f"ModMail set up in guild {guild_id}, channel {channel.id}")
        
        embed = discord.Embed(
            title="ModMail Setup Complete",
            description=f"ModMail has been set up in {channel.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="How it works", value="Users can DM the bot with `!report` to create a new ModMail thread", inline=False)
        embed.add_field(name="Commands", value="`!modmail claim` - Claim a thread\n`!modmail close` - Close a thread\n`!modmail anonymous` - Send anonymous message\n`!modmail export` - Export conversation", inline=False)
        embed.add_field(name="Next Steps", value="Use `!modmail staffrole @role` to set a staff role to be pinged for new threads", inline=False)
        embed.set_footer(text=f"Made by {__author__}")
        
        await ctx.send(embed=embed)
    
    @modmail.command(name="claim")
    @commands.has_permissions(manage_messages=True)
    async def claim_thread(self, ctx):
        
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("This command can only be used in a ModMail thread.")
            return
        
        self.debug_log(f"Claim request for thread {ctx.channel.id} by {ctx.author.name}")
        
        user_id = None
        for uid, thread_info in self.active_threads.items():
            if str(ctx.channel.id) == str(thread_info["thread_id"]):
                user_id = uid
                if thread_info["claimed_by"]:
                    claimer = ctx.guild.get_member(thread_info["claimed_by"])
                    if claimer:
                        await ctx.send(f"This thread is already claimed by {claimer.mention}")
                        return
                thread_info["claimed_by"] = ctx.author.id
                self.save_user_threads()
                break
        
        if not user_id:
            await ctx.send("This doesn't appear to be an active ModMail thread.")
            return
        
        embed = discord.Embed(
            title="Thread Claimed",
            description=f"This conversation has been claimed by {ctx.author.mention}",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now()
        )
        embed.set_footer(text=f"Made by {__author__}")
        await ctx.send(embed=embed)
        
        try:
            user = await self.bot.fetch_user(int(user_id))
            user_embed = discord.Embed(
                title="Staff Assigned",
                description=f"A staff member has been assigned to your conversation.",
                color=discord.Color.gold(),
                timestamp=datetime.datetime.now()
            )
            user_embed.set_footer(text=f"Made by {__author__}")
            await user.send(embed=user_embed)
        except Exception as e:
            self.debug_log(f"Failed to notify user {user_id} about thread claim: {str(e)}", level="WARNING")
    
    @modmail.command(name="close")
    @commands.has_permissions(manage_messages=True)
    async def close_thread(self, ctx, *, reason=None):
        
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("This command can only be used in a ModMail thread.")
            return
        
        self.debug_log(f"Close request for thread {ctx.channel.id} by {ctx.author.name}")
        
        user_id = None
        for uid, thread_info in self.active_threads.items():
            if str(ctx.channel.id) == str(thread_info["thread_id"]):
                user_id = uid
                break
        
        if not user_id:
            await ctx.send("This doesn't appear to be an active ModMail thread.")
            return
        

        await self.export_conversation(ctx.channel, auto=True)
        
        try:
            user = await self.bot.fetch_user(int(user_id))
            close_embed = discord.Embed(
                title="ModMail Conversation Closed",
                description=f"This ModMail conversation has been closed by a staff member.",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now()
            )
            if reason:
                close_embed.add_field(name="Reason", value=reason, inline=False)
            close_embed.set_footer(text=f"You can start a new conversation by sending !report | Made by {__author__}")
            
            await user.send(embed=close_embed)
        except discord.HTTPException:
            await ctx.send("Failed to notify user that the thread was closed.")
        
        del self.active_threads[user_id]
        self.save_user_threads()
        
        close_confirm_embed = discord.Embed(
            title="Thread Closed",
            description="This ModMail thread has been closed.",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        if reason:
            close_confirm_embed.add_field(name="Reason", value=reason, inline=False)
        close_confirm_embed.add_field(name="Closed by", value=ctx.author.mention, inline=False)
        close_confirm_embed.set_footer(text=f"Made by {__author__}")
        
        await ctx.send(embed=close_confirm_embed)
        await ctx.channel.edit(archived=True, locked=True)
    
    @modmail.command(name="anonymous")
    @commands.has_permissions(manage_messages=True)
    async def send_anonymous(self, ctx, *, message):
        
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("This command can only be used in a ModMail thread.")
            return
        
        self.debug_log(f"Anonymous message request in thread {ctx.channel.id} by {ctx.author.name}")
        
        user_id = None
        for uid, thread_info in self.active_threads.items():
            if str(ctx.channel.id) == str(thread_info["thread_id"]):
                user_id = uid
                break
        
        if not user_id:
            await ctx.send("This doesn't appear to be an active ModMail thread.")
            return
        
        try:
            user = await self.bot.fetch_user(int(user_id))
            anon_embed = discord.Embed(
                description=message,
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            anon_embed.set_author(name="Staff Team", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
            anon_embed.set_footer(text=f"Made by {__author__}")
            
            await user.send(embed=anon_embed)
            self.debug_log(f"Sent anonymous message to user {user_id}")
            
            await ctx.message.delete()
            
            confirm_embed = discord.Embed(
                description=message,
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            confirm_embed.set_author(name=f"Anonymous message sent by {ctx.author.name}")
            confirm_embed.set_footer(text=f"Made by {__author__}")
            await ctx.send(embed=confirm_embed)
            
        except Exception as e:
            await ctx.send(f"Failed to send anonymous message to user: {str(e)}")
            self.debug_log(f"Failed to send anonymous message to user {user_id}: {str(e)}", level="ERROR")
    
    @modmail.command(name="anonymous_mode")
    @commands.has_permissions(manage_messages=True)
    async def toggle_anonymous_mode(self, ctx):
        
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("This command can only be used in a ModMail thread.")
            return
        
        self.debug_log(f"Anonymous mode toggle request in thread {ctx.channel.id} by {ctx.author.name}")
        
        user_id = None
        for uid, thread_info in self.active_threads.items():
            if str(ctx.channel.id) == str(thread_info["thread_id"]):
                user_id = uid
                

                if thread_info["claimed_by"] and thread_info["claimed_by"] != ctx.author.id and not ctx.author.guild_permissions.administrator:
                    claimer = ctx.guild.get_member(thread_info["claimed_by"])
                    if claimer:
                        await ctx.send(f"Only the thread owner ({claimer.mention}) or administrators can toggle anonymous mode.")
                        return
                

                thread_info["anonymous_mode"] = not thread_info.get("anonymous_mode", False)
                anonymous_status = "enabled" if thread_info["anonymous_mode"] else "disabled"
                

                if not thread_info["claimed_by"]:
                    thread_info["claimed_by"] = ctx.author.id
                    await ctx.send(f"Thread automatically claimed by {ctx.author.mention}")
                
                self.save_user_threads()
                break
        
        if not user_id:
            await ctx.send("This doesn't appear to be an active ModMail thread.")
            return
        
        embed = discord.Embed(
            title="Anonymous Mode",
            description=f"Anonymous mode has been **{anonymous_status}** for this thread.",
            color=discord.Color.gold() if thread_info["anonymous_mode"] else discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        if thread_info["anonymous_mode"]:
            embed.add_field(name="Info", value="All your messages will now appear as from 'Staff Team'", inline=False)
        else:
            embed.add_field(name="Info", value="Your messages will now show your name", inline=False)
        
        embed.set_footer(text=f"Made by {__author__}")
        await ctx.send(embed=embed)
    
    @modmail.command(name="exclusive_mode")
    @commands.has_permissions(manage_messages=True)
    async def toggle_exclusive_mode(self, ctx):
        
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("This command can only be used in a ModMail thread.")
            return
        
        self.debug_log(f"Exclusive mode toggle request in thread {ctx.channel.id} by {ctx.author.name}")
        
        user_id = None
        for uid, thread_info in self.active_threads.items():
            if str(ctx.channel.id) == str(thread_info["thread_id"]):
                user_id = uid
                

                if thread_info["claimed_by"] and thread_info["claimed_by"] != ctx.author.id and not ctx.author.guild_permissions.administrator:
                    claimer = ctx.guild.get_member(thread_info["claimed_by"])
                    if claimer:
                        await ctx.send(f"Only the thread owner ({claimer.mention}) or administrators can toggle exclusive mode.")
                        return
                

                thread_info["exclusive_mode"] = not thread_info.get("exclusive_mode", True)
                exclusive_status = "enabled" if thread_info["exclusive_mode"] else "disabled"
                

                if not thread_info["claimed_by"]:
                    thread_info["claimed_by"] = ctx.author.id
                    await ctx.send(f"Thread automatically claimed by {ctx.author.mention}")
                
                self.save_user_threads()
                break
        
        if not user_id:
            await ctx.send("This doesn't appear to be an active ModMail thread.")
            return
        
        embed = discord.Embed(
            title="Exclusive Mode",
            description=f"Exclusive mode has been **{exclusive_status}** for this thread.",
            color=discord.Color.gold() if thread_info["exclusive_mode"] else discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        if thread_info["exclusive_mode"]:
            embed.add_field(name="Info", value="Only the assigned staff member can reply to this thread.", inline=False)
        else:
            embed.add_field(name="Info", value="Any staff member can now reply to this thread.", inline=False)
        
        embed.set_footer(text=f"Made by {__author__}")
        await ctx.send(embed=embed)
    
    @modmail.command(name="transfer")
    @commands.has_permissions(manage_messages=True)
    async def transfer_thread(self, ctx, member: discord.Member):
        
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("This command can only be used in a ModMail thread.")
            return
        
        self.debug_log(f"Transfer request in thread {ctx.channel.id} from {ctx.author.name} to {member.name}")
        

        if not member.guild_permissions.manage_messages:
            await ctx.send(f"{member.mention} doesn't have the required permissions to handle ModMail threads.")
            return
        
        user_id = None
        for uid, thread_info in self.active_threads.items():
            if str(ctx.channel.id) == str(thread_info["thread_id"]):
                user_id = uid
                

                if (thread_info["claimed_by"] and 
                    thread_info["claimed_by"] != ctx.author.id and 
                    not ctx.author.guild_permissions.administrator):
                    
                    claimer = ctx.guild.get_member(thread_info["claimed_by"])
                    if claimer:
                        await ctx.send(f"Only the thread owner ({claimer.mention}) or administrators can transfer this thread.")
                        return
                

                if member.id == ctx.author.id:
                    await ctx.send("You already own this thread.")
                    return
                    

                if thread_info["claimed_by"] == member.id:
                    await ctx.send(f"This thread is already assigned to {member.mention}.")
                    return
                

                previous_owner_id = thread_info["claimed_by"]
                

                thread_info["claimed_by"] = member.id
                self.save_user_threads()
                break
        
        if not user_id:
            await ctx.send("This doesn't appear to be an active ModMail thread.")
            return
        
        embed = discord.Embed(
            title="Thread Transferred",
            description=f"This thread has been transferred to {member.mention}.",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now()
        )
        
        if previous_owner_id:
            previous_owner = ctx.guild.get_member(previous_owner_id)
            if previous_owner:
                embed.add_field(name="Previous Owner", value=previous_owner.mention, inline=False)
        
        embed.set_footer(text=f"Made by {__author__}")
        await ctx.send(embed=embed)
        
        try:
            user = await self.bot.fetch_user(int(user_id))
            user_embed = discord.Embed(
                title="Staff Assignment Changed",
                description="Your conversation has been assigned to a different staff member.",
                color=discord.Color.gold(),
                timestamp=datetime.datetime.now()
            )
            user_embed.set_footer(text=f"Made by {__author__}")
            await user.send(embed=user_embed)
        except Exception as e:
            self.debug_log(f"Failed to notify user {user_id} about thread transfer: {str(e)}", level="WARNING")
    
    @modmail.command(name="export")
    @commands.has_permissions(manage_messages=True)
    async def export_thread(self, ctx):
        
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("This command can only be used in a ModMail thread.")
            return
        
        await self.export_conversation(ctx.channel)
    
    async def export_conversation(self, thread, auto=False):
        
        if auto:
            await thread.send("Auto-exporting conversation before closing...")
        else:
            await thread.send("Exporting conversation transcript...")
        
        messages = []
        async for message in thread.history(limit=None, oldest_first=True):
            if message.author.bot and message.embeds:
                for embed in message.embeds:
                    if embed.author and embed.description:
                        messages.append(f"[{message.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {embed.author.name}: {embed.description}")
            elif not message.author.bot:
                messages.append(f"[{message.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {message.author.name}: {message.content}")
        
        if not messages:
            await thread.send("No messages found to export.")
            return
        
        transcript = "\n".join(messages)
        
        file_name = f"transcript-{thread.id}.txt"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(transcript)
        
        await thread.send(file=discord.File(file_name))
        

        for guild_id, settings in self.config.items():
            guild = self.bot.get_guild(int(guild_id))
            if guild and thread in guild.threads:
                if settings.get("log_channel_id"):
                    log_channel = guild.get_channel(int(settings["log_channel_id"]))
                    if log_channel:
                        log_embed = discord.Embed(
                            title="ModMail Transcript",
                            description=f"Transcript from thread {thread.name}",
                            color=discord.Color.blue(),
                            timestamp=datetime.datetime.now()
                        )
                        log_embed.set_footer(text=f"Made by {__author__}")
                        await log_channel.send(embed=log_embed, file=discord.File(file_name))
                break
        
        import os
        os.remove(file_name)
    
    @modmail.command(name="status")
    @commands.has_permissions(administrator=True)
    async def modmail_status(self, ctx):
        
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            await ctx.send("ModMail is not set up for this server. Use `!modmail setup` first.")
            return
        
        active_count = 0
        for user_id, thread_info in self.active_threads.items():
            if thread_info["guild_id"] == guild_id:
                active_count += 1
        
        settings = self.config[guild_id]
        channel = ctx.guild.get_channel(int(settings["channel_id"]))
        log_channel = None
        if settings.get("log_channel_id"):
            log_channel = ctx.guild.get_channel(int(settings["log_channel_id"]))
        
        staff_role = None
        if settings.get("staff_role_id"):
            staff_role = ctx.guild.get_role(int(settings["staff_role_id"]))
        
        embed = discord.Embed(
            title="ModMail Status",
            color=discord.Color.blue()
        )
        embed.add_field(name="Active Threads", value=str(active_count), inline=True)
        embed.add_field(name="ModMail Channel", value=channel.mention if channel else "Not found", inline=True)
        embed.add_field(name="Log Channel", value=log_channel.mention if log_channel else "Not set", inline=True)
        embed.add_field(name="Staff Role", value=staff_role.mention if staff_role else "Not set", inline=True)
        embed.add_field(name="Setup Date", value=datetime.datetime.fromisoformat(settings["setup_time"]).strftime("%Y-%m-%d"), inline=True)
        embed.set_footer(text=f"Made by {__author__}")
        
        await ctx.send(embed=embed)
    
    @modmail.command(name="logs")
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, ctx, channel: discord.TextChannel = None):
        
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            await ctx.send("ModMail is not set up for this server. Use `!modmail setup` first.")
            return
        
        if channel:
            self.config[guild_id]["log_channel_id"] = channel.id
            self.save_config()
            await ctx.send(f"ModMail logs will now be sent to {channel.mention}")
        else:
            self.config[guild_id]["log_channel_id"] = None
            self.save_config()
            await ctx.send("ModMail logging has been disabled.")
    
    @modmail.command(name="staffrole")
    @commands.has_permissions(administrator=True)
    async def set_staff_role(self, ctx, role: discord.Role = None):
        
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            await ctx.send("ModMail is not set up for this server. Use `!modmail setup` first.")
            return
        
        if role:
            self.config[guild_id]["staff_role_id"] = role.id
            self.save_config()
            await ctx.send(f"Staff role set to {role.mention}. This role will be pinged for new ModMail threads.")
        else:
            self.config[guild_id]["staff_role_id"] = None
            self.save_config()
            await ctx.send("Staff role has been unset. No role will be pinged for new threads.")
    
    @modmail.command(name="block")
    @commands.has_permissions(administrator=True)
    async def block_user(self, ctx, user_id: str, *, reason=None):
        
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            await ctx.send("ModMail is not set up for this server.")
            return
        
        if "blocked_users" not in self.config[guild_id]:
            self.config[guild_id]["blocked_users"] = {}
        
        self.config[guild_id]["blocked_users"][user_id] = {
            "reason": reason or "No reason provided",
            "blocked_by": ctx.author.id,
            "blocked_at": datetime.datetime.now().isoformat()
        }
        
        self.save_config()
        
        await ctx.send(f"User ID `{user_id}` has been blocked from using ModMail.")
        
        if user_id in self.active_threads:
            thread_info = self.active_threads[user_id]
            if thread_info["guild_id"] == guild_id:
                thread = ctx.guild.get_channel(int(thread_info["thread_id"]))
                if thread:
                    await thread.send(f"This user has been blocked from using ModMail by {ctx.author.mention}.\nReason: {reason or 'No reason provided'}")
                    await self.close_thread(ctx, reason="User blocked")
    
    @modmail.command(name="unblock")
    @commands.has_permissions(administrator=True)
    async def unblock_user(self, ctx, user_id: str):
        
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            await ctx.send("ModMail is not set up for this server.")
            return
        
        if "blocked_users" not in self.config[guild_id] or user_id not in self.config[guild_id]["blocked_users"]:
            await ctx.send(f"User ID `{user_id}` is not blocked.")
            return
        
        del self.config[guild_id]["blocked_users"][user_id]
        self.save_config()
        
        await ctx.send(f"User ID `{user_id}` has been unblocked and can use ModMail again.")
    
    @modmail.command(name="blocklist")
    @commands.has_permissions(administrator=True)
    async def blocklist(self, ctx):
        
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.config:
            await ctx.send("ModMail is not set up for this server.")
            return
        
        if "blocked_users" not in self.config[guild_id] or not self.config[guild_id]["blocked_users"]:
            await ctx.send("No users are currently blocked.")
            return
        
        embed = discord.Embed(
            title="ModMail Blocked Users",
            color=discord.Color.red(),
            description=f"Total blocked users: {len(self.config[guild_id]['blocked_users'])}"
        )
        
        for user_id, block_info in self.config[guild_id]["blocked_users"].items():
            blocker = ctx.guild.get_member(block_info["blocked_by"])
            blocker_name = blocker.name if blocker else "Unknown"
            
            embed.add_field(
                name=f"User ID: {user_id}",
                value=f"Reason: {block_info['reason']}\nBlocked by: {blocker_name}\nDate: {block_info['blocked_at'].split('T')[0]}",
                inline=False
            )
        
        embed.set_footer(text=f"Made by {__author__}")
        await ctx.send(embed=embed)
    
    @modmail.command(name="debug")
    @commands.has_permissions(administrator=True)
    async def debug_threads(self, ctx):
        
        await self.debug_active_threads(ctx)
    
    async def debug_active_threads(self, ctx):
        
        if not ctx.author.guild_permissions.administrator:
            return
            
        debug_info = "Active Threads Debug Info:\n"
        for user_id, thread_info in self.active_threads.items():
            debug_info += f"User: {user_id}\n"
            debug_info += f"Thread ID: {thread_info['thread_id']} (type: {type(thread_info['thread_id']).__name__})\n"
            debug_info += f"Guild ID: {thread_info['guild_id']} (type: {type(thread_info['guild_id']).__name__})\n"
            debug_info += f"Claimed: {thread_info['claimed_by']}\n"
            debug_info += f"Anonymous Mode: {thread_info.get('anonymous_mode', False)}\n"
            debug_info += f"Exclusive Mode: {thread_info.get('exclusive_mode', True)}\n"
            debug_info += "---\n"
        
        if not self.active_threads:
            debug_info += "No active threads found.\n"
        

        if len(debug_info) > 1900:
            chunks = [debug_info[i:i+1900] for i in range(0, len(debug_info), 1900)]
            for chunk in chunks:
                await ctx.send(f"```{chunk}```")
        else:
            await ctx.send(f"```{debug_info}```")
    
    @modmail.command(name="cleanup")
    @commands.has_permissions(administrator=True)
    async def cleanup_threads(self, ctx):
        
        count = 0
        invalid_threads = []
        
        for user_id, thread_info in list(self.active_threads.items()):
            guild_id = thread_info["guild_id"]
            thread_id = thread_info["thread_id"]
            
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                invalid_threads.append((user_id, f"Guild {guild_id} not found"))
                continue
                
            thread = guild.get_channel(int(thread_id))
            if not thread:
                invalid_threads.append((user_id, f"Thread {thread_id} not found in guild {guild.name}"))
                continue
        

        for user_id, reason in invalid_threads:
            del self.active_threads[user_id]
            count += 1
            self.debug_log(f"Cleaned up thread for user {user_id}: {reason}")
        
        self.save_user_threads()
        
        await ctx.send(f"Cleaned up {count} invalid threads.")
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if isinstance(channel, discord.Thread):
            for user_id, thread_info in list(self.active_threads.items()):
                if str(channel.id) == str(thread_info["thread_id"]):
                    del self.active_threads[user_id]
                    self.save_user_threads()
                    try:
                        user = await self.bot.fetch_user(int(user_id))
                        await user.send(f"The ModMail thread has been closed by a staff member. | Made by {__author__}")
                    except:
                        pass
                    break

def setup(bot):
    cog = ModMailLite(bot)
    asyncio.create_task(bot.add_cog(cog))
    return cog




