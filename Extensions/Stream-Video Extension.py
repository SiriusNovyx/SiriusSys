import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import datetime
import asyncio
from typing import Dict, List, Optional, Union

class StreamVideo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.stream_data_path = "data/stream_data.json"
        self.config_path = "data/stream_config.json"
        self.stream_data = {}  
        self.config = {} 
        self.active_streamers = {}  
        
        os.makedirs("data", exist_ok=True)
        
        self.load_data()
        self.verify_active_streamers.start()
        self.update_stream_time.start()
        self.check_rewards.start()

    def load_data(self):
        try:
            if os.path.exists(self.stream_data_path):
                with open(self.stream_data_path, 'r') as f:
                    self.stream_data = json.load(f)
        except Exception as e:
            print(f"Error loading stream data: {e}")
            self.stream_data = {}
            
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
        except Exception as e:
            print(f"Error loading stream config: {e}")
            self.config = {}

    def save_data(self):
        try:
            with open(self.stream_data_path, 'w') as f:
                json.dump(self.stream_data, f, indent=4)
        except Exception as e:
            print(f"Error saving stream data: {e}")
            
        try:
            if not os.path.exists("data"):
                os.makedirs("data", exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving stream config: {e}")

    def cog_unload(self):
        self.update_stream_time.cancel()
        self.check_rewards.cancel()
        self.verify_active_streamers.cancel()
        self.save_data()

    @tasks.loop(minutes=1)
    async def update_stream_time(self):
        if not self.active_streamers:
            return
            
        current_time = datetime.datetime.now().timestamp()
        
        for guild_id, guild_streamers in list(self.active_streamers.items()):
            if str(guild_id) not in self.stream_data:
                self.stream_data[str(guild_id)] = {}
                
            for user_id, stream_info in list(guild_streamers.items()):
                if not stream_info.get('active', True):
                    continue
                    
                elapsed_time = (current_time - stream_info['start_time']) / 3600
                
                if str(user_id) not in self.stream_data[str(guild_id)]:
                    self.stream_data[str(guild_id)][str(user_id)] = {
                        "stream_time": 0,
                        "camera_time": 0,
                        "last_stream": current_time
                    }
                
                if stream_info['using_camera']:
                    self.stream_data[str(guild_id)][str(user_id)]["camera_time"] += elapsed_time
                    print(f"Update: Added {elapsed_time:.4f} hours to camera time")
                elif stream_info.get('streaming', False):
                    self.stream_data[str(guild_id)][str(user_id)]["stream_time"] += elapsed_time
                    print(f"Update: Added {elapsed_time:.4f} hours to stream time")
                
                self.active_streamers[guild_id][user_id]['start_time'] = current_time
        
        self.save_data()

    @tasks.loop(seconds=30)
    async def verify_active_streamers(self):
        current_time = datetime.datetime.now().timestamp()
        
        for guild_id in list(self.active_streamers.keys()):
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
                
            for user_id in list(self.active_streamers[guild_id].keys()):
                member = guild.get_member(user_id)
                if not member or not member.voice:
                    if user_id in self.active_streamers[guild_id]:
                        elapsed_time = (current_time - self.active_streamers[guild_id][user_id]['start_time']) / 3600
                        
                        if str(guild_id) not in self.stream_data:
                            self.stream_data[str(guild_id)] = {}
                        if str(user_id) not in self.stream_data[str(guild_id)]:
                            self.stream_data[str(guild_id)][str(user_id)] = {"stream_time": 0, "camera_time": 0, "last_stream": current_time}
                        
                        if self.active_streamers[guild_id][user_id]['using_camera']:
                            self.stream_data[str(guild_id)][str(user_id)]["camera_time"] += elapsed_time
                        elif self.active_streamers[guild_id][user_id].get('streaming', False):
                            self.stream_data[str(guild_id)][str(user_id)]["stream_time"] += elapsed_time
                            
                        self.stream_data[str(guild_id)][str(user_id)]["last_stream"] = current_time
                        
                        del self.active_streamers[guild_id][user_id]
                    continue
                
                voice_state = member.voice
                
                is_streaming = voice_state.self_stream
                is_using_camera = voice_state.self_video
                
                if not is_streaming and not is_using_camera and user_id in self.active_streamers[guild_id]:
                    elapsed_time = (current_time - self.active_streamers[guild_id][user_id]['start_time']) / 3600
                    
                    if str(guild_id) not in self.stream_data:
                        self.stream_data[str(guild_id)] = {}
                    if str(user_id) not in self.stream_data[str(guild_id)]:
                        self.stream_data[str(guild_id)][str(user_id)] = {"stream_time": 0, "camera_time": 0, "last_stream": current_time}
                    
                    if self.active_streamers[guild_id][user_id]['using_camera']:
                        self.stream_data[str(guild_id)][str(user_id)]["camera_time"] += elapsed_time
                    elif self.active_streamers[guild_id][user_id].get('streaming', False):
                        self.stream_data[str(guild_id)][str(user_id)]["stream_time"] += elapsed_time
                        
                    self.stream_data[str(guild_id)][str(user_id)]["last_stream"] = current_time
                    
                    self.active_streamers[guild_id][user_id]['active'] = False
                    
                elif (is_streaming != self.active_streamers[guild_id][user_id].get('streaming', False) or 
                      is_using_camera != self.active_streamers[guild_id][user_id]['using_camera']):
                    
                    elapsed_time = (current_time - self.active_streamers[guild_id][user_id]['start_time']) / 3600
                    
                    if str(guild_id) not in self.stream_data:
                        self.stream_data[str(guild_id)] = {}
                    if str(user_id) not in self.stream_data[str(guild_id)]:
                        self.stream_data[str(guild_id)][str(user_id)] = {"stream_time": 0, "camera_time": 0, "last_stream": current_time}
                    
                    if self.active_streamers[guild_id][user_id]['using_camera']:
                        self.stream_data[str(guild_id)][str(user_id)]["camera_time"] += elapsed_time
                    elif self.active_streamers[guild_id][user_id].get('streaming', False):
                        self.stream_data[str(guild_id)][str(user_id)]["stream_time"] += elapsed_time
                    
                    if not is_streaming and not is_using_camera:
                        self.stream_data[str(guild_id)][str(user_id)]["last_stream"] = current_time
                        self.active_streamers[guild_id][user_id]['active'] = False
                    else:
                        self.active_streamers[guild_id][user_id] = {
                            'start_time': current_time,
                            'using_camera': is_using_camera,
                            'streaming': is_streaming,
                            'active': True
                        }
        
        self.save_data()

    async def scan_for_streamers(self):
        for guild in self.bot.guilds:
            for voice_channel in guild.voice_channels:
                for member in voice_channel.members:
                    if member.voice and (member.voice.self_stream or member.voice.self_video):
                        if guild.id not in self.active_streamers:
                            self.active_streamers[guild.id] = {}
                        
                        self.active_streamers[guild.id][member.id] = {
                            'start_time': datetime.datetime.now().timestamp(),
                            'using_camera': member.voice.self_video,
                            'streaming': member.voice.self_stream,
                            'active': True
                        }

    @verify_active_streamers.before_loop
    async def before_verify_active_streamers(self):
        await self.bot.wait_until_ready()
        await self.scan_for_streamers()

    @update_stream_time.before_loop
    async def before_update_stream_time(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=1)
    async def check_rewards(self):
        has_rewards = False
        for guild_id in self.config:
            if "rewards" in self.config[guild_id] and self.config[guild_id]["rewards"]:
                has_rewards = True
                break
        
        if not has_rewards:
            return
        
        for guild in self.bot.guilds:
            guild_id = str(guild.id)
            
            if guild_id not in self.config or "rewards" not in self.config[guild_id]:
                continue
            
            if guild_id not in self.stream_data:
                continue
            
            announcement_channel_id = self.config[guild_id].get("announcement_channel")
            announcement_channel = guild.get_channel(int(announcement_channel_id)) if announcement_channel_id else None
            
            voice_members = []
            for voice_channel in guild.voice_channels:
                voice_members.extend(voice_channel.members)
            
            for member in voice_members:
                user_id = str(member.id)
                
                if user_id not in self.stream_data[guild_id]:
                    continue
                
                user_data = self.stream_data[guild_id][user_id]
                
                for reward in self.config[guild_id]["rewards"]:
                    try:
                        role = guild.get_role(int(reward["role_id"]))
                        if not role or role in member.roles:
                            continue
                        
                        if reward["type"] == "stream" and user_data["stream_time"] >= float(reward["hours"]):
                            await member.add_roles(role, reason=f"Streamed for {reward['hours']} hours")
                            
                            if announcement_channel:
                                embed = discord.Embed(
                                    title="🏆 Streaming Achievement Unlocked!",
                                    description=f"Congratulations {member.mention}! You've streamed for {reward['hours']} hours and earned the {role.name} role!",
                                    color=discord.Color.purple()
                                )
                                await announcement_channel.send(embed=embed)
                                
                        elif reward["type"] == "camera" and user_data["camera_time"] >= float(reward["hours"]):
                            await member.add_roles(role, reason=f"Streamed with camera for {reward['hours']} hours")
                            
                            if announcement_channel:
                                embed = discord.Embed(
                                    title="📹 Camera Achievement Unlocked!",
                                    description=f"Congratulations {member.mention}! You've streamed with camera for {reward['hours']} hours and earned the {role.name} role!",
                                    color=discord.Color.purple()
                                )
                                await announcement_channel.send(embed=embed)
                    except Exception as e:
                        print(f"Error processing reward: {e}")

    @check_rewards.before_loop
    async def before_check_rewards(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild_id = member.guild.id
        user_id = member.id
        current_time = datetime.datetime.now().timestamp()
        
        if before.self_stream != after.self_stream or before.self_video != after.self_video:
            print(f"Voice state update for {member.name}: stream {before.self_stream}->{after.self_stream}, camera {before.self_video}->{after.self_video}")
        
        if guild_id not in self.active_streamers:
            self.active_streamers[guild_id] = {}
            
        if (not before.self_stream and after.self_stream) or (not before.self_video and after.self_video):
            if after.self_video:
                print(f"Camera state changed for {member.name}: {before.self_video} -> {after.self_video}")
                if not after.self_stream:
                    print(f"User {member.name} turned on camera without streaming")
            
            self.active_streamers[guild_id][user_id] = {
                'start_time': current_time,
                'using_camera': after.self_video,
                'streaming': after.self_stream,
                'active': True
            }
            
        elif (before.self_stream and not after.self_stream) or (before.self_video and not after.self_video):
            if user_id in self.active_streamers[guild_id]:
                elapsed_time = (current_time - self.active_streamers[guild_id][user_id]['start_time']) / 3600
                
                if str(guild_id) not in self.stream_data:
                    self.stream_data[str(guild_id)] = {}
                if str(user_id) not in self.stream_data[str(guild_id)]:
                    self.stream_data[str(guild_id)][str(user_id)] = {"stream_time": 0, "camera_time": 0, "last_stream": current_time}
                
                if before.self_video:
                    print(f"Camera state changed for {member.name}: {before.self_video} -> {after.self_video}")
                    self.stream_data[str(guild_id)][str(user_id)]["camera_time"] += elapsed_time
                    print(f"Added {elapsed_time:.4f} hours to camera time for {member.name} (camera state change)")
                elif before.self_stream:
                    self.stream_data[str(guild_id)][str(user_id)]["stream_time"] += elapsed_time
                    print(f"Added {elapsed_time:.4f} hours to stream time for {member.name} (stream state change)")
                
                if not after.self_stream and not after.self_video:
                    self.stream_data[str(guild_id)][str(user_id)]["last_stream"] = current_time
                    self.active_streamers[guild_id][user_id]['active'] = False
                else:
                    self.active_streamers[guild_id][user_id] = {
                        'start_time': current_time,
                        'using_camera': after.self_video,
                        'streaming': after.self_stream,
                        'active': True
                    }
                
                self.save_data()
        
        elif before.self_video != after.self_video or before.self_stream != after.self_stream:
            if user_id in self.active_streamers[guild_id]:
                elapsed_time = (current_time - self.active_streamers[guild_id][user_id]['start_time']) / 3600
                
                if str(guild_id) not in self.stream_data:
                    self.stream_data[str(guild_id)] = {}
                if str(user_id) not in self.stream_data[str(guild_id)]:
                    self.stream_data[str(guild_id)][str(user_id)] = {"stream_time": 0, "camera_time": 0, "last_stream": current_time}
                
                if self.active_streamers[guild_id][user_id]['using_camera']:
                    self.stream_data[str(guild_id)][str(user_id)]["camera_time"] += elapsed_time
                    print(f"Added {elapsed_time:.4f} hours to camera time for {member.name} (state change)")
                elif self.active_streamers[guild_id][user_id].get('streaming', False):
                    self.stream_data[str(guild_id)][str(user_id)]["stream_time"] += elapsed_time
                    print(f"Added {elapsed_time:.4f} hours to stream time for {member.name} (state change)")
                
                self.active_streamers[guild_id][user_id] = {
                    'start_time': current_time,
                    'using_camera': after.self_video,
                    'streaming': after.self_stream,
                    'active': True if (after.self_video or after.self_stream) else False
                }
                
                self.save_data()

    @commands.hybrid_command(name="stream-config", description="Configure stream tracking settings")
    @commands.has_permissions(administrator=True)
    async def stream_config(self, ctx):
        embed = discord.Embed(
            title="Stream Tracking Configuration",
            description="Configure how stream tracking works in your server",
            color=discord.Color.blue()
        )
        
        guild_id = str(ctx.guild.id)
        if guild_id not in self.config:
            self.config[guild_id] = {"rewards": []}
            
        announcement_channel_id = self.config[guild_id].get("announcement_channel")
        announcement_channel = ctx.guild.get_channel(int(announcement_channel_id)) if announcement_channel_id else None
        
        embed.add_field(
            name="Announcement Channel",
            value=f"{announcement_channel.mention if announcement_channel else 'Not set'}",
            inline=False
        )
        
        embed.add_field(
            name="Rewards",
            value=self._format_rewards(ctx.guild) or "No rewards configured",
            inline=False
        )
        
        view = StreamConfigView(self, ctx)
        
        await ctx.send(embed=embed, view=view)

    def _format_rewards(self, guild):
        guild_id = str(guild.id)
        if guild_id not in self.config or "rewards" not in self.config[guild_id]:
            return ""
            
        rewards_text = []
        for reward in self.config[guild_id]["rewards"]:
            role = guild.get_role(int(reward["role_id"]))
            role_name = role.name if role else f"Unknown Role ({reward['role_id']})"
            rewards_text.append(f"• {reward['type'].capitalize()}: {reward['hours']} hours → {role_name}")
            
        return "\n".join(rewards_text)

    @commands.hybrid_command(name="stream-leaderboard", description="View streaming leaderboard")
    async def stream_leaderboard(self, ctx, type: str = "stream"):
        if type.lower() not in ["stream", "camera"]:
            await ctx.send("Invalid type. Please use 'stream' or 'camera'.")
            return
            
        guild_id = str(ctx.guild.id)
        if guild_id not in self.stream_data:
            await ctx.send("No streaming data available for this server.")
            return
            
        time_key = "camera_time" if type.lower() == "camera" else "stream_time"
        sorted_users = sorted(
            self.stream_data[guild_id].items(),
            key=lambda x: x[1][time_key],
            reverse=True
        )[:10]
        
        if not sorted_users:
            await ctx.send(f"No {type} data available for this server.")
            return
            
        embed = discord.Embed(
            title=f"🏆 {type.capitalize()} Leaderboard",
            description=f"Top streamers in {ctx.guild.name}",
            color=discord.Color.gold()
        )
        
        for i, (user_id, data) in enumerate(sorted_users, 1):
            member = ctx.guild.get_member(int(user_id))
            name = member.display_name if member else f"User {user_id}"
            hours = round(data[time_key], 2)
            embed.add_field(
                name=f"{i}. {name}",
                value=f"{hours} hours",
                inline=False
            )
            
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="stream-profile", description="View your or another user's streaming profile")
    async def stream_profile(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)
        
        if guild_id not in self.stream_data or user_id not in self.stream_data[guild_id]:
            await ctx.send(f"No streaming data available for {member.display_name}.")
            return
            
        user_data = self.stream_data[guild_id][user_id]
        
        embed = discord.Embed(
            title=f"Streaming Profile: {member.display_name}",
            color=member.color
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(
            name="🎮 Stream Time",
            value=f"{round(user_data['stream_time'], 2)} hours",
            inline=True
        )
        
        embed.add_field(
            name="📹 Camera Time",
            value=f"{round(user_data['camera_time'], 2)} hours",
            inline=True
        )
        
        total_time = user_data['stream_time'] + user_data['camera_time']
        embed.add_field(
            name="⏱️ Total Time",
            value=f"{round(total_time, 2)} hours",
            inline=True
        )
        
        if user_data.get('last_stream', 0) > 0:
            embed.add_field(
                name="🕒 Last Stream",
                value=f"<t:{int(user_data['last_stream'])}:R>",
                inline=False
            )
        else:
            embed.add_field(
                name="🕒 Last Stream",
                value="Currently streaming or no record",
                inline=False
            )
        
        if guild_id in self.config and "rewards" in self.config[guild_id]:
            earned_rewards = []
            for reward in self.config[guild_id]["rewards"]:
                role = ctx.guild.get_role(int(reward["role_id"]))
                if not role:
                    continue
                    
                if reward["type"] == "stream" and user_data["stream_time"] >= float(reward["hours"]):
                    earned_rewards.append(f"🎮 {role.name}")
                elif reward["type"] == "camera" and user_data["camera_time"] >= float(reward["hours"]):
                    earned_rewards.append(f"📹 {role.name}")
            
            if earned_rewards:
                embed.add_field(
                    name="🏆 Earned Rewards",
                    value="\n".join(earned_rewards),
                    inline=False
                )
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="stream-reset", description="Reset streaming data for a user or the entire server")
    @commands.has_permissions(administrator=True)
    async def stream_reset(self, ctx, target = None):
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.stream_data:
            await ctx.send("No streaming data exists for this server.")
            return
            
        if target is None or (isinstance(target, str) and target.lower() == "server"):
            embed = discord.Embed(
                title="⚠️ Reset Server Streaming Data",
                description="Are you sure you want to reset ALL streaming data for this server? This cannot be undone.",
                color=discord.Color.red()
            )
            
            view = ConfirmView(ctx.author)
            message = await ctx.send(embed=embed, view=view)
            
            await view.wait()
            if view.value:
                self.stream_data[guild_id] = {}
                self.save_data()
                await message.edit(content="All streaming data for this server has been reset.", embed=None, view=None)
            else:
                await message.edit(content="Operation cancelled.", embed=None, view=None)
                
        elif isinstance(target, discord.Member):
            user_id = str(target.id)
            if user_id not in self.stream_data[guild_id]:
                await ctx.send(f"No streaming data exists for {target.display_name}.")
                return
                
            embed = discord.Embed(
                title=f"⚠️ Reset User Streaming Data",
                description=f"Are you sure you want to reset streaming data for {target.mention}? This cannot be undone.",
                color=discord.Color.red()
            )
            
            view = ConfirmView(ctx.author)
            message = await ctx.send(embed=embed, view=view)
            
            await view.wait()
            if view.value:
                del self.stream_data[guild_id][user_id]
                self.save_data()
                await message.edit(content=f"Streaming data for {target.display_name} has been reset.", embed=None, view=None)
            else:
                await message.edit(content="Operation cancelled.", embed=None, view=None)
        else:
            await ctx.send("Invalid target. Please specify a user or 'server'.")

    @commands.hybrid_command(name="stream-ui", description="Open the streaming dashboard")
    async def stream_ui(self, ctx):
        embed = discord.Embed(
            title="🎮 Streaming Dashboard",
            description="Select an option below to view streaming information",
            color=discord.Color.blurple()
        )
        
        view = StreamDashboardView(self, ctx)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="stream-help", description="View all streaming commands")
    async def stream_help(self, ctx):
        try:
            prefix = ctx.prefix or "/"
        except:
            prefix = "/"
            
        embed = discord.Embed(
            title="🎮 Streaming Commands",
            description=f"Here are all the commands available in the Stream-Video extension",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="User Commands",
            value=(
                f"`{prefix}stream-profile [user]` - View your or another user's streaming profile\n"
                f"`{prefix}stream-leaderboard [stream/camera]` - View the streaming leaderboard\n"
                f"`{prefix}stream-ui` - Open the streaming dashboard UI\n"
                f"`{prefix}stream-help` - Show this help message"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Admin Commands",
            value=(
                f"`{prefix}stream-config` - Configure stream tracking settings\n"
                f"`{prefix}stream-reset [user/server]` - Reset streaming data"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="stream-debug", description="Debug streaming data")
    @commands.has_permissions(administrator=True)
    async def stream_debug(self, ctx):
        embed = discord.Embed(
            title="Stream Debug Information",
            description="Current streaming data and active streamers",
            color=discord.Color.blue()
        )
        
        active_streamers_text = ""
        for guild_id, guild_streamers in self.active_streamers.items():
            guild = self.bot.get_guild(guild_id)
            guild_name = guild.name if guild else f"Unknown Guild ({guild_id})"
            active_streamers_text += f"**{guild_name}**:\n"
            
            for user_id, stream_info in guild_streamers.items():
                member = guild.get_member(user_id) if guild else None
                name = member.display_name if member else f"User {user_id}"
                start_time = datetime.datetime.fromtimestamp(stream_info['start_time'])
                using_camera = "Yes" if stream_info['using_camera'] else "No"
                streaming = "Yes" if stream_info.get('streaming', False) else "No"
                active = "Yes" if stream_info.get('active', True) else "No"
                
                active_streamers_text += f"- {name}: Started <t:{int(stream_info['start_time'])}:R>, Camera: {using_camera}, Streaming: {streaming}, Active: {active}\n"
        
        embed.add_field(
            name="Active Streamers",
            value=active_streamers_text or "No active streamers",
            inline=False
        )
        
        data_summary = ""
        for guild_id, guild_data in self.stream_data.items():
            guild = self.bot.get_guild(int(guild_id))
            guild_name = guild.name if guild else f"Unknown Guild ({guild_id})"
            data_summary += f"**{guild_name}**:\n"
            
            for user_id, user_data in list(guild_data.items())[:5]:
                member = guild.get_member(int(user_id)) if guild else None
                name = member.display_name if member else f"User {user_id}"
                stream_time = round(user_data.get("stream_time", 0), 2)
                camera_time = round(user_data.get("camera_time", 0), 2)
                last_stream = f"<t:{int(user_data.get('last_stream', 0))}:R>" if user_data.get('last_stream', 0) > 0 else "Never"
                
                data_summary += f"- {name}: Stream: {stream_time}h, Camera: {camera_time}h, Last: {last_stream}\n"
            
            if len(guild_data) > 5:
                data_summary += f"- And {len(guild_data) - 5} more users...\n"
        
        embed.add_field(
            name="Stream Data Summary",
            value=data_summary or "No stream data",
            inline=False
        )
        
        embed.add_field(
            name="File Paths",
            value=f"Stream Data: `{self.stream_data_path}`\nConfig: `{self.config_path}`",
            inline=False
        )
        
        await ctx.send(embed=embed)

class ConfirmView(discord.ui.View):
    def __init__(self, author, timeout=60):
        super().__init__(timeout=timeout)
        self.author = author
        self.value = None
        
    async def interaction_check(self, interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("This confirmation is not for you.", ephemeral=True)
            return False
        return True
        
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.defer()
        self.stop()
        
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.defer()
        self.stop()

class StreamConfigView(discord.ui.View):
    def __init__(self, cog, ctx, timeout=300):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.author = ctx.author
        
    async def interaction_check(self, interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
            return False
        return True
        
    @discord.ui.button(label="Set Announcement Channel", style=discord.ButtonStyle.primary)
    async def set_announcement_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelSelectModal(self.cog, self.ctx)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Add Reward", style=discord.ButtonStyle.green)
    async def add_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RewardModal(self.cog, self.ctx)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Remove Reward", style=discord.ButtonStyle.red)
    async def remove_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(self.ctx.guild.id)
        if guild_id not in self.cog.config or not self.cog.config[guild_id].get("rewards"):
            await interaction.response.send_message("No rewards configured for this server.", ephemeral=True)
            return
            
        options = []
        for i, reward in enumerate(self.cog.config[guild_id]["rewards"]):
            role = self.ctx.guild.get_role(int(reward["role_id"]))
            role_name = role.name if role else f"Unknown Role ({reward['role_id']})"
            options.append(
                discord.SelectOption(
                    label=f"{reward['type'].capitalize()}: {reward['hours']} hours → {role_name}",
                    value=str(i)
                )
            )
            
        select = RewardSelect(self.cog, options)
        view = discord.ui.View()
        view.add_item(select)
        
        await interaction.response.send_message("Select a reward to remove:", view=view, ephemeral=True)
        
    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        await interaction.response.defer()

class ChannelSelectModal(discord.ui.Modal, title="Set Announcement Channel"):
    channel_id = discord.ui.TextInput(
        label="Channel ID",
        placeholder="Enter the channel ID for announcements",
        required=True
    )
    
    def __init__(self, cog, ctx):
        super().__init__()
        self.cog = cog
        self.ctx = ctx
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_id.value)
            channel = self.ctx.guild.get_channel(channel_id)
            
            if not channel:
                await interaction.response.send_message("Invalid channel ID. Please try again.", ephemeral=True)
                return
                
            guild_id = str(self.ctx.guild.id)
            if guild_id not in self.cog.config:
                self.cog.config[guild_id] = {"rewards": []}
                
            self.cog.config[guild_id]["announcement_channel"] = channel_id
            self.cog.save_data()
            
            await interaction.response.send_message(f"Announcement channel set to {channel.mention}", ephemeral=True)
            
            embed = discord.Embed(
                title="Stream Tracking Configuration",
                description="Configure how stream tracking works in your server",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Announcement Channel",
                value=channel.mention,
                inline=False
            )
            
            embed.add_field(
                name="Rewards",
                value=self.cog._format_rewards(self.ctx.guild) or "No rewards configured",
                inline=False
            )
            
            await interaction.message.edit(embed=embed)
            
        except ValueError:
            await interaction.response.send_message("Invalid channel ID. Please enter a valid number.", ephemeral=True)

class RewardModal(discord.ui.Modal, title="Add Streaming Reward"):
    reward_type = discord.ui.TextInput(
        label="Reward Type",
        placeholder="Enter 'stream' or 'camera'",
        required=True
    )
    
    hours = discord.ui.TextInput(
        label="Required Hours",
        placeholder="Enter the number of hours required",
        required=True
    )
    
    role_id = discord.ui.TextInput(
        label="Role ID",
        placeholder="Enter the role ID to award",
        required=True
    )
    
    def __init__(self, cog, ctx):
        super().__init__()
        self.cog = cog
        self.ctx = ctx
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            reward_type = self.reward_type.value.lower()
            if reward_type not in ["stream", "camera"]:
                await interaction.response.send_message("Invalid reward type. Please use 'stream' or 'camera'.", ephemeral=True)
                return
                
            hours = float(self.hours.value)
            role_id = int(self.role_id.value)
            
            role = self.ctx.guild.get_role(role_id)
            if not role:
                await interaction.response.send_message("Invalid role ID. Please try again.", ephemeral=True)
                return
                
            guild_id = str(self.ctx.guild.id)
            if guild_id not in self.cog.config:
                self.cog.config[guild_id] = {"rewards": []}
                
            if "rewards" not in self.cog.config[guild_id]:
                self.cog.config[guild_id]["rewards"] = []
                
            self.cog.config[guild_id]["rewards"].append({
                "type": reward_type,
                "hours": hours,
                "role_id": role_id
            })
            
            self.cog.save_data()
            
            await interaction.response.send_message(f"Added reward: {reward_type.capitalize()} for {hours} hours → {role.name}", ephemeral=True)
            
            embed = discord.Embed(
                title="Stream Tracking Configuration",
                description="Configure how stream tracking works in your server",
                color=discord.Color.blue()
            )
            
            announcement_channel_id = self.cog.config[guild_id].get("announcement_channel")
            announcement_channel = self.ctx.guild.get_channel(int(announcement_channel_id)) if announcement_channel_id else None
            
            embed.add_field(
                name="Announcement Channel",
                value=f"{announcement_channel.mention if announcement_channel else 'Not set'}",
                inline=False
            )
            
            embed.add_field(
                name="Rewards",
                value=self.cog._format_rewards(self.ctx.guild),
                inline=False
            )
            
            await interaction.message.edit(embed=embed)
            
        except ValueError:
            await interaction.response.send_message("Invalid input. Please check your values and try again.", ephemeral=True)

class RewardSelect(discord.ui.Select):
    def __init__(self, cog, options):
        super().__init__(placeholder="Select a reward to remove", options=options)
        self.cog = cog
        
    async def callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        try:
            index = int(self.values[0])
            removed_reward = self.cog.config[guild_id]["rewards"].pop(index)
            self.cog.save_data()
            
            role = interaction.guild.get_role(int(removed_reward["role_id"]))
            role_name = role.name if role else f"Unknown Role ({removed_reward['role_id']})"
            
            await interaction.response.send_message(
                f"Removed reward: {removed_reward['type'].capitalize()} for {removed_reward['hours']} hours → {role_name}",
                ephemeral=True
            )
            
            embed = discord.Embed(
                title="Stream Tracking Configuration",
                description="Configure how stream tracking works in your server",
                color=discord.Color.blue()
            )
            
            announcement_channel_id = self.cog.config[guild_id].get("announcement_channel")
            announcement_channel = interaction.guild.get_channel(int(announcement_channel_id)) if announcement_channel_id else None
            
            embed.add_field(
                name="Announcement Channel",
                value=f"{announcement_channel.mention if announcement_channel else 'Not set'}",
                inline=False
            )
            
            embed.add_field(
                name="Rewards",
                value=self.cog._format_rewards(interaction.guild) or "No rewards configured",
                inline=False
            )
            
            await interaction.message.edit(embed=embed, view=None)
            
        except (ValueError, IndexError):
            await interaction.response.send_message("An error occurred while removing the reward.", ephemeral=True)

class StreamDashboardView(discord.ui.View):
    def __init__(self, cog, ctx, timeout=180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        
    @discord.ui.button(label="My Profile", style=discord.ButtonStyle.primary)
    async def my_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.stream_profile(self.ctx, interaction.user)
        
    @discord.ui.button(label="Stream Leaderboard", style=discord.ButtonStyle.secondary)
    async def stream_leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.stream_leaderboard(self.ctx, "stream")
        
    @discord.ui.button(label="Camera Leaderboard", style=discord.ButtonStyle.secondary)
    async def camera_leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.stream_leaderboard(self.ctx, "camera")
        
    @discord.ui.button(label="Configuration", style=discord.ButtonStyle.green)
    async def configuration(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to access configuration.", ephemeral=True)
            return
            
        await interaction.response.defer()
        await self.cog.stream_config(self.ctx)
        
    @discord.ui.button(label="Close", style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        await interaction.response.defer()

def setup(bot):
    cog = StreamVideo(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    return cog
