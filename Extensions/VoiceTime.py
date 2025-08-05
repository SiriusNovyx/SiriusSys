import discord
from discord.ext import commands
import datetime
import json
import os
from typing import Optional, Union, Dict, List
import asyncio
import re

class VoiceTime(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_data_file = "data/voice_time_data.json"
        self.voice_roles_file = "data/voice_roles.json"
        self.voice_data = self.load_voice_data()
        self.voice_roles = self.load_voice_roles()
        self.currently_in_voice = {}
        self.last_checked = {}
        self.check_rewards_task = self.bot.loop.create_task(self.check_role_rewards())
        
    def load_voice_data(self):
        if os.path.exists(self.voice_data_file):
            try:
                with open(self.voice_data_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading voice data: {e}")
                return {}
        return {}
    
    def save_voice_data(self):
        try:
            with open(self.voice_data_file, 'w') as f:
                json.dump(self.voice_data, f, indent=4)
        except Exception as e:
            print(f"Error saving voice data: {e}")
    
    def load_voice_roles(self):
        if os.path.exists(self.voice_roles_file):
            try:
                with open(self.voice_roles_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading voice roles data: {e}")
                return {}
        return {}
    
    def save_voice_roles(self):
        try:
            with open(self.voice_roles_file, 'w') as f:
                json.dump(self.voice_roles, f, indent=4)
        except Exception as e:
            print(f"Error saving voice roles data: {e}")
    
    def cog_unload(self):
        if self.check_rewards_task:
            self.check_rewards_task.cancel()
    
    async def check_role_rewards(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                current_time = datetime.datetime.now().timestamp()
                
                for guild_id, guild_data in self.voice_roles.items():
                    guild = self.bot.get_guild(int(guild_id))
                    if not guild:
                        continue
                        
                    announcement_channel_id = guild_data.get("announcement_channel")
                    announcement_channel = None
                    if announcement_channel_id:
                        announcement_channel = guild.get_channel(int(announcement_channel_id))
                    
                    role_rewards = guild_data.get("role_rewards", {})
                    
                    if not role_rewards:
                        continue
                    
                    for member in guild.members:
                        user_id = str(member.id)
                        
                        if user_id not in self.voice_data:
                            continue
                        
                        is_in_voice = user_id in self.currently_in_voice
                        was_checked_recently = (user_id in self.last_checked and 
                                            (current_time - self.last_checked[user_id]) < 60)
                        
                        if was_checked_recently and not is_in_voice:
                            continue
                        
                        self.last_checked[user_id] = current_time
                        
                        voice_time = await self.get_user_voice_time(user_id)
                        
                        for role_id, time_required in role_rewards.items():
                            role = guild.get_role(int(role_id))
                            if not role:
                                continue
                                
                            if role in member.roles:
                                continue
                            
                            if voice_time >= time_required:
                                try:
                                    await member.add_roles(role, reason="Voice time reward")
                                    print(f"Gave role {role.name} to {member.display_name} for reaching {self.format_time(time_required)} voice time threshold")
                                    
                                    if announcement_channel:
                                        embed = discord.Embed(
                                            title="🎉 Voice Time Reward Achieved!",
                                            description=f"**{member.display_name}** has reached **{self.format_time(time_required)}** in voice channels and earned the **{role.name}** role!",
                                            color=discord.Color.gold()
                                        )
                                        embed.set_thumbnail(url=member.display_avatar.url)
                                        embed.set_footer(text="Made by TheHolyOneZ")
                                        await announcement_channel.send(embed=embed)
                                except Exception as e:
                                    print(f"Error giving role reward: {e}")
            except Exception as e:
                print(f"Error in check_role_rewards task: {e}")
                
            await asyncio.sleep(10)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        user_id = str(member.id)
        
        if before.channel is None and after.channel is not None:
            self.currently_in_voice[user_id] = datetime.datetime.now().timestamp()
            
        elif before.channel is not None and after.channel is None:
            if user_id in self.currently_in_voice:
                join_time = self.currently_in_voice.pop(user_id)
                time_spent = datetime.datetime.now().timestamp() - join_time
                
                if user_id not in self.voice_data:
                    self.voice_data[user_id] = {
                        "total_time": 0,
                        "sessions": 0,
                        "channels": {},
                        "last_session": time_spent
                    }
                
                self.voice_data[user_id]["total_time"] += time_spent
                self.voice_data[user_id]["sessions"] += 1
                self.voice_data[user_id]["last_session"] = time_spent
                
                channel_id = str(before.channel.id)
                if "channels" not in self.voice_data[user_id]:
                    self.voice_data[user_id]["channels"] = {}
                if channel_id not in self.voice_data[user_id]["channels"]:
                    self.voice_data[user_id]["channels"][channel_id] = 0
                self.voice_data[user_id]["channels"][channel_id] += time_spent
                
                self.save_voice_data()
                
                await self.check_user_role_rewards(member)

    async def check_user_role_rewards(self, member):
        user_id = str(member.id)
        guild_id = str(member.guild.id)
        
        if guild_id not in self.voice_roles:
            return
            
        guild_data = self.voice_roles[guild_id]
        role_rewards = guild_data.get("role_rewards", {})
        if not role_rewards:
            return
            
        voice_time = await self.get_user_voice_time(user_id)
        
        announcement_channel_id = guild_data.get("announcement_channel")
        announcement_channel = None
        if announcement_channel_id:
            announcement_channel = member.guild.get_channel(int(announcement_channel_id))
        
        for role_id, time_required in role_rewards.items():
            role = member.guild.get_role(int(role_id))
            if not role or role in member.roles:
                continue
                
            if voice_time >= time_required:
                try:
                    await member.add_roles(role, reason="Voice time reward")
                    print(f"Gave role {role.name} to {member.display_name} for reaching {self.format_time(time_required)} voice time threshold")
                    
                    if announcement_channel:
                        embed = discord.Embed(
                            title="🎉 Voice Time Reward Achieved!",
                            description=f"**{member.display_name}** has reached **{self.format_time(time_required)}** in voice channels and earned the **{role.name}** role!",
                            color=discord.Color.gold()
                        )
                        embed.set_thumbnail(url=member.display_avatar.url)
                        embed.set_footer(text="Made by TheHolyOneZ")
                        await announcement_channel.send(embed=embed)
                except Exception as e:
                    print(f"Error giving role reward: {e}")
    
    def parse_time(self, time_str):
        if not time_str:
            return 0
            
        time_regex = re.compile(r'(\d+)([dhms])')
        matches = time_regex.findall(time_str.lower())
        
        total_seconds = 0
        for value, unit in matches:
            value = int(value)
            if unit == 'd':
                total_seconds += value * 86400
            elif unit == 'h':
                total_seconds += value * 3600
            elif unit == 'm':
                total_seconds += value * 60
            elif unit == 's':
                total_seconds += value
                
        return total_seconds
    
    def format_time(self, seconds):
        days, remainder = divmod(int(seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, remainder = divmod(remainder, 60)
        seconds = remainder
        
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds > 0 or not parts:
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
            
        return ", ".join(parts)
    
    async def get_user_voice_time(self, user_id):
        user_id = str(user_id)
        
        current_session = 0
        if user_id in self.currently_in_voice:
            current_session = datetime.datetime.now().timestamp() - self.currently_in_voice[user_id]
        
        stored_time = 0
        if user_id in self.voice_data:
            stored_time = self.voice_data[user_id]["total_time"]
            
        return stored_time + current_session
    
    @commands.hybrid_command(name="voice", description="Check how long a user has been in voice channels")
    async def voice_time(self, ctx, user: Optional[discord.Member] = None):
        user = user or ctx.author
        user_id = str(user.id)
        
        voice_time = await self.get_user_voice_time(user_id)
        formatted_time = self.format_time(voice_time)
        
        sessions = 0
        last_session = 0
        if user_id in self.voice_data:
            sessions = self.voice_data[user_id]["sessions"]
            last_session = self.voice_data[user_id].get("last_session", 0)
        
        embed = discord.Embed(
            title=f"🎙️ Voice Time for {user.display_name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Total Time", value=f"⏱️ {formatted_time}", inline=False)
        embed.add_field(name="Voice Sessions", value=f"🔄 {sessions}", inline=True)
        
        if last_session > 0:
            embed.add_field(
                name="Last Session", 
                value=f"⏲️ {self.format_time(last_session)}",
                inline=True
            )
        
        if user_id in self.currently_in_voice:
            current_session = datetime.datetime.now().timestamp() - self.currently_in_voice[user_id]
            embed.add_field(
                name="Current Session", 
                value=f"🔴 LIVE: {self.format_time(current_session)}",
                inline=False
            )
        
        guild_id = str(ctx.guild.id)
        if guild_id in self.voice_roles:
            role_rewards = self.voice_roles[guild_id].get("role_rewards", {})
            if role_rewards:
                progress_text = ""
                for role_id, time_required in sorted(role_rewards.items(), key=lambda x: int(x[1])):
                    role = ctx.guild.get_role(int(role_id))
                    if not role:
                        continue
                        
                    has_role = role in user.roles
                    progress = min(100, int((voice_time / time_required) * 100)) if time_required > 0 else 100
                    
                    status = "✅" if has_role else f"{progress}%"
                    progress_text += f"**{role.name}**: {status} ({self.format_time(time_required)})\n"
                
                if progress_text:
                    embed.add_field(name="Role Rewards Progress", value=progress_text, inline=False)
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="voiceleaderboard", aliases=["vlb"], description="Show voice time leaderboard")
    async def voice_leaderboard(self, ctx, limit: int = 10):
        if limit > 25:
            limit = 25
            
        sorted_users = sorted(
            self.voice_data.items(),
            key=lambda x: x[1]["total_time"],
            reverse=True
        )[:limit]
        
        if not sorted_users:
            await ctx.send("No voice data recorded yet!")
            return
        
        embed = discord.Embed(
            title="🏆 Voice Time Leaderboard",
            description="Users with the most time spent in voice channels",
            color=discord.Color.gold()
        )
        
        for i, (user_id, data) in enumerate(sorted_users, 1):
            try:
                user = await self.bot.fetch_user(int(user_id))
                username = user.display_name
            except:
                username = f"Unknown User ({user_id})"
                
            formatted_time = self.format_time(data["total_time"])
            
            prefix = ""
            if i == 1:
                prefix = "🥇 "
            elif i == 2:
                prefix = "🥈 "
            elif i == 3:
                prefix = "🥉 "
            else:
                prefix = f"#{i} "
                
            embed.add_field(
                name=f"{prefix}{username}",
                value=f"⏱️ {formatted_time}\n🔄 {data['sessions']} sessions",
                inline=False
            )
            
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="channelstats", description="Show voice stats for a specific channel")
    async def channel_stats(self, ctx, channel: Optional[discord.VoiceChannel] = None):
        channel = channel or (ctx.author.voice.channel if ctx.author.voice else None)
        
        if not channel:
            await ctx.send("Please specify a voice channel or join one!")
            return
            
        channel_id = str(channel.id)
        
        channel_data = []
        for user_id, data in self.voice_data.items():
            if "channels" in data and channel_id in data["channels"]:
                channel_data.append((user_id, data["channels"][channel_id]))
        
        if not channel_data:
            await ctx.send(f"No recorded voice activity in {channel.name}!")
            return
            
        channel_data.sort(key=lambda x: x[1], reverse=True)
        
        embed = discord.Embed(
            title=f"📊 Voice Stats for #{channel.name}",
            color=discord.Color.green()
        )
        
        total_channel_time = sum(time for _, time in channel_data)
        embed.add_field(
            name="Total Channel Activity",
            value=f"⏱️ {self.format_time(total_channel_time)}",
            inline=False
        )
        
        for i, (user_id, time) in enumerate(channel_data[:5], 1):
            try:
                user = await self.bot.fetch_user(int(user_id))
                username = user.display_name
            except:
                username = f"Unknown User ({user_id})"
                
            prefix = ""
            if i == 1:
                prefix = "🥇 "
            elif i == 2:
                prefix = "🥈 "
            elif i == 3:
                prefix = "🥉 "
            else:
                prefix = f"#{i} "
                
            embed.add_field(
                name=f"{prefix}{username}",
                value=f"⏱️ {self.format_time(time)}",
                inline=True
            )
        
        embed.add_field(
            name="Channel Info",
            value=f"🔊 Bitrate: {channel.bitrate//1000}kbps\n👥 User Limit: {channel.user_limit or 'Unlimited'}\n👤 Current Users: {len(channel.members)}",
            inline=False
        )
            
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="voicestats", description="Show detailed voice statistics for a user")
    async def voice_stats(self, ctx, user: Optional[discord.Member] = None):
        user = user or ctx.author
        user_id = str(user.id)
        
        if user_id not in self.voice_data:
            await ctx.send(f"{user.display_name} has no recorded voice activity!")
            return
            
        data = self.voice_data[user_id]
        total_time = await self.get_user_voice_time(user_id)
        
        embed = discord.Embed(
            title=f"📈 Voice Statistics for {user.display_name}",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="Total Time",
            value=f"⏱️ {self.format_time(total_time)}",
            inline=False
        )
        
        embed.add_field(
            name="Voice Sessions",
            value=f"🔄 {data['sessions']}",
            inline=True
        )
        
        if data["sessions"] > 0:
            avg_session = data["total_time"] / data["sessions"]
            embed.add_field(
                name="Average Session",
                value=f"⌛ {self.format_time(avg_session)}",
                inline=True
            )
        
        if "last_session" in data and data["last_session"] > 0:
            embed.add_field(
                name="Last Session",
                value=f"⏲️ {self.format_time(data['last_session'])}",
                inline=True
            )
        
        if user_id in self.currently_in_voice:
            current_session = datetime.datetime.now().timestamp() - self.currently_in_voice[user_id]
            embed.add_field(
                name="Current Session",
                value=f"🔴 LIVE: {self.format_time(current_session)}",
                inline=True
            )
        
        if "channels" in data and data["channels"]:
            sorted_channels = sorted(
                data["channels"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            
            channel_text = ""
            for i, (channel_id, time) in enumerate(sorted_channels, 1):
                try:
                    channel = self.bot.get_channel(int(channel_id))
                    channel_name = channel.name if channel else f"Unknown Channel ({channel_id})"
                except:
                    channel_name = f"Unknown Channel ({channel_id})"
                    
                channel_text += f"**{i}. {channel_name}**: {self.format_time(time)}\n"
                
            embed.add_field(
                name="Top Channels",
                value=channel_text or "No channel data",
                inline=False
            )
        
        guild_id = str(ctx.guild.id)
        if guild_id in self.voice_roles:
            role_rewards = self.voice_roles[guild_id].get("role_rewards", {})
            if role_rewards:
                progress_text = ""
                for role_id, time_required in sorted(role_rewards.items(), key=lambda x: int(x[1])):
                    role = ctx.guild.get_role(int(role_id))
                    if not role:
                        continue
                        
                    has_role = role in user.roles
                    progress = min(100, int((total_time / time_required) * 100)) if time_required > 0 else 100
                    
                    status = "✅" if has_role else f"{progress}%"
                    progress_text += f"**{role.name}**: {status} ({self.format_time(time_required)})\n"
                
                if progress_text:
                    embed.add_field(name="Role Rewards Progress", value=progress_text, inline=False)
            
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="voicerole", description="Set up a role reward for voice time (Admin only)")
    @commands.has_permissions(administrator=True)
    async def voice_role(self, ctx, role: discord.Role, time_requirement: str, announcement_channel: Optional[discord.TextChannel] = None):
        seconds_required = self.parse_time(time_requirement)
        if seconds_required <= 0:
            await ctx.send("Invalid time format. Use format like: 10h, 30m, 1d, etc.")
            return
            
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.voice_roles:
            self.voice_roles[guild_id] = {
                "role_rewards": {},
                "announcement_channel": None
            }
            
        self.voice_roles[guild_id]["role_rewards"][str(role.id)] = seconds_required
        
        if announcement_channel:
            self.voice_roles[guild_id]["announcement_channel"] = str(announcement_channel.id)
            
        self.save_voice_roles()
        
        embed = discord.Embed(
            title="✅ Voice Role Reward Set",
            description=f"Users will receive the **{role.name}** role after spending **{self.format_time(seconds_required)}** in voice channels.",
            color=discord.Color.green()
        )
        
        if announcement_channel:
            embed.add_field(
                name="Announcements",
                value=f"Role rewards will be announced in {announcement_channel.mention}",
                inline=False
            )
            
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="removevoicerole", description="Remove a voice time role reward (Admin only)")
    @commands.has_permissions(administrator=True)
    async def remove_voice_role(self, ctx, role: discord.Role):
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.voice_roles or str(role.id) not in self.voice_roles[guild_id]["role_rewards"]:
            await ctx.send(f"No voice time reward is set for the {role.name} role.")
            return
            
        del self.voice_roles[guild_id]["role_rewards"][str(role.id)]
        self.save_voice_roles()
        
        embed = discord.Embed(
            title="🗑️ Voice Role Reward Removed",
            description=f"The voice time reward for the **{role.name}** role has been removed.",
            color=discord.Color.red()
        )
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="voiceroles", description="List all voice time role rewards")
    async def voice_roles_list(self, ctx):
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.voice_roles or not self.voice_roles[guild_id]["role_rewards"]:
            await ctx.send("No voice time role rewards are set up for this server.")
            return
            
        role_rewards = self.voice_roles[guild_id]["role_rewards"]
        
        embed = discord.Embed(
            title="🏆 Voice Time Role Rewards",
            description="The following roles are awarded based on voice time:",
            color=discord.Color.blue()
        )
        
        for role_id, time_required in sorted(role_rewards.items(), key=lambda x: int(x[1])):
            role = ctx.guild.get_role(int(role_id))
            if not role:
                continue
                
            embed.add_field(
                name=role.name,
                value=f"Required Time: {self.format_time(time_required)}",
                inline=False
            )
            
        announcement_channel_id = self.voice_roles[guild_id].get("announcement_channel")
        if announcement_channel_id:
            channel = ctx.guild.get_channel(int(announcement_channel_id))
            if channel:
                embed.add_field(
                    name="Announcement Channel",
                    value=channel.mention,
                    inline=False
                )
                
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="setannouncechannel", description="Set the channel for voice role announcements (Admin only)")
    @commands.has_permissions(administrator=True)
    async def set_announce_channel(self, ctx, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.voice_roles:
            self.voice_roles[guild_id] = {
                "role_rewards": {},
                "announcement_channel": None
            }
            
        self.voice_roles[guild_id]["announcement_channel"] = str(channel.id)
        self.save_voice_roles()
        
        embed = discord.Embed(
            title="📢 Announcement Channel Set",
            description=f"Voice role reward announcements will be sent to {channel.mention}",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="resetvoice", description="Reset voice time data (Admin only)")
    @commands.has_permissions(administrator=True)
    async def reset_voice(self, ctx, user: Optional[discord.Member] = None):
        if user:
            user_id = str(user.id)
            if user_id in self.voice_data:
                del self.voice_data[user_id]
                self.save_voice_data()
                
                embed = discord.Embed(
                    title="🗑️ Voice Data Reset",
                    description=f"Voice data for **{user.display_name}** has been reset.",
                    color=discord.Color.red()
                )
                embed.set_footer(text="Made by TheHolyOneZ")
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"{user.display_name} has no voice data to reset.")
        else:
            embed = discord.Embed(
                title="⚠️ Full Reset Confirmation",
                description="Are you sure you want to reset ALL voice data? This cannot be undone.",
                color=discord.Color.orange()
            )
            embed.set_footer(text="React with ✅ to confirm or ❌ to cancel")
            confirm_msg = await ctx.send(embed=embed)
            await confirm_msg.add_reaction("✅")
            await confirm_msg.add_reaction("❌")
            
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_msg.id
            
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
                
                if str(reaction.emoji) == "✅":
                    self.voice_data = {}
                    self.save_voice_data()
                    
                    embed = discord.Embed(
                        title="🗑️ All Voice Data Reset",
                        description="All voice time data has been reset.",
                        color=discord.Color.red()
                    )
                    embed.set_footer(text="Made by TheHolyOneZ")
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("Reset cancelled.")
            except asyncio.TimeoutError:
                await ctx.send("Reset cancelled due to timeout.")

    @commands.hybrid_command(name="voicecheck", description="Check if a user qualifies for voice time roles")
    @commands.has_permissions(administrator=True)
    async def voice_check(self, ctx, user: discord.Member):
        user_id = str(user.id)
        guild_id = str(ctx.guild.id)
        
        if user_id not in self.voice_data:
            await ctx.send(f"{user.display_name} has no recorded voice activity!")
            return
            
        if guild_id not in self.voice_roles or not self.voice_roles[guild_id]["role_rewards"]:
            await ctx.send("No voice time role rewards are set up for this server.")
            return
            
        voice_time = await self.get_user_voice_time(user_id)
        role_rewards = self.voice_roles[guild_id]["role_rewards"]
        
        embed = discord.Embed(
            title=f"🔍 Voice Role Check for {user.display_name}",
            description=f"Total Voice Time: {self.format_time(voice_time)}",
            color=discord.Color.blue()
        )
        
        roles_added = []
        roles_already = []
        roles_not_qualified = []
        
        for role_id, time_required in role_rewards.items():
            role = ctx.guild.get_role(int(role_id))
            if not role:
                continue
                
            if role in user.roles:
                roles_already.append(f"✅ **{role.name}** - Already has role ({self.format_time(time_required)})")
            elif voice_time >= time_required:
                try:
                    await user.add_roles(role, reason="Voice time reward manual check")
                    roles_added.append(f"🎉 **{role.name}** - Role added! ({self.format_time(time_required)})")
                except Exception as e:
                    roles_added.append(f"❌ **{role.name}** - Error adding role: {str(e)}")
            else:
                progress = int((voice_time / time_required) * 100)
                roles_not_qualified.append(f"⏳ **{role.name}** - {progress}% progress ({self.format_time(time_required)})")
        
        if roles_added:
            embed.add_field(name="Roles Added", value="\n".join(roles_added), inline=False)
        if roles_already:
            embed.add_field(name="Roles Already Assigned", value="\n".join(roles_already), inline=False)
        if roles_not_qualified:
            embed.add_field(name="Not Qualified Yet", value="\n".join(roles_not_qualified), inline=False)
            
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="voicetop", description="Show top users for a specific voice statistic")
    async def voice_top(self, ctx, category: str = "total", limit: int = 5):
        if limit > 25:
            limit = 25
            
        if category.lower() not in ["total", "sessions", "average"]:
            await ctx.send("Invalid category. Choose from: total, sessions, average")
            return
            
        if category.lower() == "total":
            sorted_users = sorted(
                self.voice_data.items(),
                key=lambda x: x[1]["total_time"],
                reverse=True
            )[:limit]
            title = "🏆 Top Users by Total Voice Time"
            description = "Users who have spent the most time in voice channels"
            
        elif category.lower() == "sessions":
            sorted_users = sorted(
                self.voice_data.items(),
                key=lambda x: x[1]["sessions"],
                reverse=True
            )[:limit]
            title = "🔄 Top Users by Voice Sessions"
            description = "Users with the most voice channel sessions"
            
        else:
            users_with_avg = []
            for user_id, data in self.voice_data.items():
                if data["sessions"] > 0:
                    avg_time = data["total_time"] / data["sessions"]
                    users_with_avg.append((user_id, avg_time))
                    
            sorted_users = sorted(
                users_with_avg,
                key=lambda x: x[1],
                reverse=True
            )[:limit]
            title = "⌛ Top Users by Average Session Length"
            description = "Users with the longest average voice sessions"
        
        if not sorted_users:
            await ctx.send("No voice data recorded yet!")
            return
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.gold()
        )
        
        for i, item in enumerate(sorted_users, 1):
            user_id = item[0]
            
            try:
                user = await self.bot.fetch_user(int(user_id))
                username = user.display_name
            except:
                username = f"Unknown User ({user_id})"
                
            prefix = ""
            if i == 1:
                prefix = "🥇 "
            elif i == 2:
                prefix = "🥈 "
            elif i == 3:
                prefix = "🥉 "
            else:
                prefix = f"#{i} "
                
            if category.lower() == "total":
                value = f"⏱️ {self.format_time(item[1]['total_time'])}"
            elif category.lower() == "sessions":
                value = f"🔄 {item[1]['sessions']} sessions"
            else:
                value = f"⌛ {self.format_time(item[1])} per session"
                
            embed.add_field(
                name=f"{prefix}{username}",
                value=value,
                inline=False
            )
            
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="voiceactivity", description="Show voice activity over time")
    async def voice_activity(self, ctx, user: Optional[discord.Member] = None):
        user = user or ctx.author
        user_id = str(user.id)
        
        if user_id not in self.voice_data:
            await ctx.send(f"{user.display_name} has no recorded voice activity!")
            return
            
        data = self.voice_data[user_id]
        total_time = await self.get_user_voice_time(user_id)
        
        avg_session = data["total_time"] / data["sessions"] if data["sessions"] > 0 else 0
        
        top_channel_id = None
        top_channel_time = 0
        if "channels" in data and data["channels"]:
            top_channel_id, top_channel_time = max(data["channels"].items(), key=lambda x: x[1])
        
        embed = discord.Embed(
            title=f"📊 Voice Activity for {user.display_name}",
            color=discord.Color.teal()
        )
        
        embed.add_field(
            name="Total Voice Time",
            value=f"⏱️ {self.format_time(total_time)}",
            inline=False
        )
        
        stats_text = f"🔄 **Sessions**: {data['sessions']}\n"
        stats_text += f"⌛ **Average Session**: {self.format_time(avg_session)}\n"
        
        if top_channel_id:
            try:
                channel = self.bot.get_channel(int(top_channel_id))
                channel_name = channel.name if channel else "Unknown Channel"
            except:
                channel_name = "Unknown Channel"
                
            stats_text += f"🔊 **Favorite Channel**: {channel_name} ({self.format_time(top_channel_time)})\n"
            
            percentage = (top_channel_time / data["total_time"]) * 100
            stats_text += f"📈 **Channel Preference**: {percentage:.1f}% of time in favorite channel"
            
        embed.add_field(
            name="Activity Stats",
            value=stats_text,
            inline=False
        )
        
        guild_id = str(ctx.guild.id)
        if guild_id in self.voice_roles:
            role_rewards = self.voice_roles[guild_id].get("role_rewards", {})
            if role_rewards:
                next_role = None
                next_role_time = float('inf')
                
                for role_id, time_required in role_rewards.items():
                    role = ctx.guild.get_role(int(role_id))
                    if not role or role in user.roles:
                        continue
                        
                    if time_required > total_time and time_required < next_role_time:
                        next_role = role
                        next_role_time = time_required
                
                if next_role:
                    time_left = next_role_time - total_time
                    progress = (total_time / next_role_time) * 100
                    
                    embed.add_field(
                        name="Next Role Reward",
                        value=f"🎯 **{next_role.name}**\n⏳ {self.format_time(time_left)} remaining\n📊 {progress:.1f}% progress",
                        inline=False
                    )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="voicehelp", description="Show help for voice time commands")
    async def voice_help(self, ctx):
        prefix = ctx.prefix
        
        embed = discord.Embed(
            title="🎙️ Voice Time Commands",
            description=f"Here are all the available voice time commands:",
            color=discord.Color.blue()
        )
        
        user_commands = [
            f"`{prefix}voice [@user]` - Shows voice time with role progress",
            f"`{prefix}voiceleaderboard` - Shows top users by voice time",
            f"`{prefix}channelstats [channel]` - Shows statistics for a voice channel",
            f"`{prefix}voicestats [@user]` - Shows detailed voice statistics",
            f"`{prefix}voiceroles` - Lists all voice time role rewards",
            f"`{prefix}voicetop [category] [limit]` - Shows top users by different metrics",
            f"`{prefix}voiceactivity [@user]` - Shows voice activity trends"
        ]
        
        admin_commands = [
            f"`{prefix}voicerole @role 10h [#channel]` - Set up role rewards",
            f"`{prefix}removevoicerole @role` - Remove a role reward",
            f"`{prefix}setannouncechannel #channel` - Set announcement channel",
            f"`{prefix}resetvoice [@user]` - Reset voice data",
            f"`{prefix}voicecheck @user` - Manually checks and grants roles"
        ]
        
        embed.add_field(
            name="User Commands",
            value="\n".join(user_commands),
            inline=False
        )
        
        embed.add_field(
            name="Admin Commands",
            value="\n".join(admin_commands),
            inline=False
        )
        
        embed.add_field(
            name="Time Format Examples",
            value="`10s` - 10 seconds\n`5m` - 5 minutes\n`2h` - 2 hours\n`1d` - 1 day\n`1d12h30m` - 1 day, 12 hours, 30 minutes",
            inline=False
        )
        
        view = discord.ui.View()
        
        stats_button = discord.ui.Button(label="Statistics Commands", style=discord.ButtonStyle.primary)
        async def stats_callback(interaction):
            if interaction.user != ctx.author:
                return
                
            stats_embed = discord.Embed(
                title="📊 Voice Statistics Commands",
                description="Detailed information about statistics commands:",
                color=discord.Color.green()
            )
            
            stats_embed.add_field(
                name=f"{prefix}voicestats [@user]",
                value="Shows detailed voice statistics including total time, sessions, average session length, top channels, and role progress.",
                inline=False
            )
            
            stats_embed.add_field(
                name=f"{prefix}voicetop [category] [limit]",
                value="Shows top users by different metrics.\nCategories: `total` (default), `sessions`, `average`\nLimit: Number of users to show (default: 5, max: 25)",
                inline=False
            )
            
            stats_embed.add_field(
                name=f"{prefix}channelstats [channel]",
                value="Shows statistics for a specific voice channel including total activity time, top users, and channel info.",
                inline=False
            )
            
            stats_embed.add_field(
                name=f"{prefix}voiceactivity [@user]",
                value="Shows voice activity trends including favorite channels, channel preferences, and next role progress.",
                inline=False
            )
            
            stats_embed.set_footer(text="Made by TheHolyOneZ")
            await interaction.response.send_message(embed=stats_embed, ephemeral=True)
            
        stats_button.callback = stats_callback
        view.add_item(stats_button)
        
        roles_button = discord.ui.Button(label="Role Reward Commands", style=discord.ButtonStyle.success)
        async def roles_callback(interaction):
            if interaction.user != ctx.author:
                return
                
            roles_embed = discord.Embed(
                title="🏆 Voice Role Rewards Commands",
                description="Detailed information about role reward commands:",
                color=discord.Color.gold()
            )
            
            roles_embed.add_field(
                name=f"{prefix}voicerole @role 10h [#channel]",
                value="Sets up a role reward for users who reach a certain voice time. Optionally specify an announcement channel.",
                inline=False
            )
            
            roles_embed.add_field(
                name=f"{prefix}removevoicerole @role",
                value="Removes a voice time role reward.",
                inline=False
            )
            
            roles_embed.add_field(
                name=f"{prefix}voiceroles",
                value="Lists all voice time role rewards set up for the server.",
                inline=False
            )
            
            roles_embed.add_field(
                name=f"{prefix}setannouncechannel #channel",
                value="Sets the channel for voice role reward announcements.",
                inline=False
            )
            
            roles_embed.add_field(
                name=f"{prefix}voicecheck @user",
                value="Manually checks if a user qualifies for voice time roles and grants them if needed.",
                inline=False
            )
            
            roles_embed.set_footer(text="Made by TheHolyOneZ")
            await interaction.response.send_message(embed=roles_embed, ephemeral=True)
            
        roles_button.callback = roles_callback
        view.add_item(roles_button)
        
        admin_button = discord.ui.Button(label="Admin Commands", style=discord.ButtonStyle.danger)
        async def admin_callback(interaction):
            if interaction.user != ctx.author:
                return
                
            admin_embed = discord.Embed(
                title="⚙️ Voice Admin Commands",
                description="Detailed information about admin commands:",
                color=discord.Color.red()
            )
            
            admin_embed.add_field(
                name=f"{prefix}resetvoice [@user]",
                value="Resets voice time data. If a user is specified, only their data is reset. Otherwise, all data is reset (with confirmation).",
                inline=False
            )
            
            admin_embed.add_field(
                name=f"{prefix}voicecheck @user",
                value="Manually checks if a user qualifies for voice time roles and grants them if needed.",
                inline=False
            )
            
            admin_embed.add_field(
                name=f"{prefix}voicerole @role 10h [#channel]",
                value="Sets up a role reward for users who reach a certain voice time.",
                inline=False
            )
            
            admin_embed.add_field(
                name=f"{prefix}removevoicerole @role",
                value="Removes a voice time role reward.",
                inline=False
            )
            
            admin_embed.add_field(
                name=f"{prefix}setannouncechannel #channel",
                value="Sets the channel for voice role reward announcements.",
                inline=False
            )
            
            admin_embed.set_footer(text="Made by TheHolyOneZ")
            await interaction.response.send_message(embed=admin_embed, ephemeral=True)
            
        admin_button.callback = admin_callback
        view.add_item(admin_button)
        
        embed.set_footer(text="Made by TheHolyOneZ")
        await ctx.send(embed=embed, view=view)

def setup(bot):
    cog = VoiceTime(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    return cog
