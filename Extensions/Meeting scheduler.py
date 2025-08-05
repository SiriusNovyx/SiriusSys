import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import json
import os
import asyncio
from typing import Optional, List, Dict, Union
import uuid
import pytz
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  


STATUS_EMOJIS = {
    "scheduled": "📅",
    "in_progress": "🔄",
    "completed": "✅",
    "cancelled": "❌"
}

RSVP_EMOJIS = {
    "attending": "✅",
    "maybe": "❓",
    "declined": "❌"
}

class MeetingScheduler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.meetings_file = "data/meetings.json"
        self.config_file = "data/meeting_config.json"
        self.meetings = self.load_meetings()
        self.config = self.load_config()
        self.reminder_loop.start()
        os.makedirs("data", exist_ok=True)
        
    def cog_unload(self):
        self.reminder_loop.cancel()

    async def create_edit_meeting_modal(self, meeting_id, meeting):

        return self.EditMeetingModal(self, meeting_id, meeting) 
    
    def load_config(self) -> Dict:
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {"host_roles": {}}
        return {"host_roles": {}}
        
    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)   

    def load_meetings(self) -> Dict:
        if os.path.exists(self.meetings_file):
            try:
                with open(self.meetings_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {"meetings": {}, "recurring": {}, "completed": {}}
        return {"meetings": {}, "recurring": {}, "completed": {}}
        
    def save_meetings(self):
        with open(self.meetings_file, 'w') as f:
            json.dump(self.meetings, f, indent=4)
            
    @tasks.loop(minutes=5)
    async def reminder_loop(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        

        for meeting_id, meeting in list(self.meetings["meetings"].items()):
            start_time = datetime.datetime.fromisoformat(meeting["start_time"])
            

            time_diff = start_time - now
            if 86340 < time_diff.total_seconds() < 86460:  
                await self.send_reminder(meeting_id, meeting, "24hour")
            

            elif 3540 < time_diff.total_seconds() < 3660:  
                await self.send_reminder(meeting_id, meeting, "1hour")
            

            elif 540 < time_diff.total_seconds() < 660:  
                await self.send_reminder(meeting_id, meeting, "10min")
            

            elif -300 < time_diff.total_seconds() < 300:  
                if meeting["status"] == "scheduled":
                    meeting["status"] = "in_progress"
                    self.save_meetings()
                    await self.send_meeting_starting_notification(meeting_id, meeting)
            

            end_time = datetime.datetime.fromisoformat(meeting["end_time"])
            if now > end_time and meeting["status"] == "in_progress":
                meeting["status"] = "completed"
                

                self.meetings["completed"][meeting_id] = meeting
                del self.meetings["meetings"][meeting_id]
                

                if meeting.get("recurring"):
                    await self.create_next_recurring_instance(meeting)
                
                self.save_meetings()
                await self.send_meeting_summary_request(meeting_id, meeting)
        

        for recurring_id, recurring in self.meetings.get("recurring", {}).items():
            if recurring.get("next_instance_time"):
                next_time = datetime.datetime.fromisoformat(recurring["next_instance_time"])
                if (next_time - now).total_seconds() < 604800:  
                    await self.create_recurring_instance(recurring_id)
    def can_host_meetings(self, guild_id: int, user: discord.Member) -> bool:

        if user.guild_permissions.administrator:
            return True
            

        guild_id_str = str(guild_id)
        if guild_id_str in self.config["host_roles"]:
            host_role_id = int(self.config["host_roles"][guild_id_str])

            return any(role.id == host_role_id for role in user.roles)
            

        return True
    

    def can_manage_meeting(self, meeting: Dict, user: discord.Member) -> bool:

        if user.guild_permissions.administrator:
            return True
            

        if str(user.id) == meeting["host"]:
            return True
            

        return False

    async def create_edit_meeting_modal(self, meeting_id, meeting):
        return self.EditMeetingModal(self, meeting_id, meeting) 
       
    def load_meetings(self) -> Dict:
        if os.path.exists(self.meetings_file):
            try:
                with open(self.meetings_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {"meetings": {}, "recurring": {}, "completed": {}}
        return {"meetings": {}, "recurring": {}, "completed": {}}
        
    def save_meetings(self):
        with open(self.meetings_file, 'w') as f:
            json.dump(self.meetings, f, indent=4)
    

    @app_commands.command(name="set-host-role", description="Set which role can host meetings")
    @app_commands.describe(role="The role that can host meetings")
    @app_commands.default_permissions(administrator=True)
    async def set_host_role(self, interaction: discord.Interaction, role: discord.Role):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only administrators can set host roles.", ephemeral=True)
            return
            

        guild_id = str(interaction.guild.id)
        self.config["host_roles"][guild_id] = str(role.id)
        self.save_config()
        
        await interaction.response.send_message(
            f"✅ The {role.mention} role can now host meetings in this server.", 
            ephemeral=True
        )
    

    @app_commands.command(name="clear-host-role", description="Allow anyone to host meetings")
    @app_commands.default_permissions(administrator=True)
    async def clear_host_role(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only administrators can clear host roles.", ephemeral=True)
            return
            

        guild_id = str(interaction.guild.id)
        if guild_id in self.config["host_roles"]:
            del self.config["host_roles"][guild_id]
            self.save_config()
            
        await interaction.response.send_message(
            "✅ Anyone can now host meetings in this server.", 
            ephemeral=True
        )
    

    @app_commands.command(name="show-host-role", description="Show which role can host meetings")
    async def show_host_role(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        
        if guild_id in self.config["host_roles"]:
            role_id = int(self.config["host_roles"][guild_id])
            role = interaction.guild.get_role(role_id)
            
            if role:
                await interaction.response.send_message(
                    f"The {role.mention} role can host meetings in this server.", 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "The configured host role no longer exists. Administrators can set a new one with `/set-host-role`.", 
                    ephemeral=True
                )
        else:
            await interaction.response.send_message(
                "Anyone can currently host meetings in this server.", 
                ephemeral=True
            )    

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()
    
    async def create_next_recurring_instance(self, completed_meeting):
        
        recurring_type = completed_meeting.get("recurring_type", "weekly")
        start_time = datetime.datetime.fromisoformat(completed_meeting["start_time"])
        end_time = datetime.datetime.fromisoformat(completed_meeting["end_time"])
        

        if recurring_type == "daily":
            next_start = start_time + datetime.timedelta(days=1)
            next_end = end_time + datetime.timedelta(days=1)
        elif recurring_type == "weekly":
            next_start = start_time + datetime.timedelta(days=7)
            next_end = end_time + datetime.timedelta(days=7)
        elif recurring_type == "biweekly":
            next_start = start_time + datetime.timedelta(days=14)
            next_end = end_time + datetime.timedelta(days=14)
        elif recurring_type == "monthly":

            next_start = self.add_month(start_time)
            next_end = self.add_month(end_time)
        else:
            return  
        

        meeting_id = str(uuid.uuid4())
        new_meeting = {
            "title": completed_meeting["title"],
            "description": completed_meeting["description"],
            "start_time": next_start.isoformat(),
            "end_time": next_end.isoformat(),
            "location": completed_meeting.get("location", ""),
            "virtual_link": completed_meeting.get("virtual_link", ""),
            "host": completed_meeting["host"],
            "host_name": completed_meeting["host_name"],
            "guild_id": completed_meeting["guild_id"],
            "channel_id": completed_meeting["channel_id"],
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": "scheduled",
            "recurring": True,
            "recurring_type": recurring_type,
            "recurring_id": completed_meeting.get("recurring_id", ""),
            "attendees": {"attending": [], "maybe": [], "declined": []},
            "agenda_items": completed_meeting.get("agenda_items", []),
            "attachments": [],
            "notes": "",
            "action_items": []
        }
        

        self.meetings["meetings"][meeting_id] = new_meeting
        self.save_meetings()
        

        guild = self.bot.get_guild(int(completed_meeting["guild_id"]))
        if guild:
            channel = guild.get_channel(int(completed_meeting["channel_id"]))
            if channel:
                embed = self.create_meeting_embed(meeting_id, new_meeting)
                view = self.MeetingView(self, meeting_id, new_meeting)
                await channel.send(f"A new recurring meeting has been scheduled:", embed=embed, view=view)
    
    def add_month(self, dt):
        
        month = dt.month + 1
        year = dt.year
        if month > 12:
            month = 1
            year += 1
        

        day = min(dt.day, self.get_days_in_month(year, month))
        
        return dt.replace(year=year, month=month, day=day)
    
    def get_days_in_month(self, year, month):
        
        if month in [4, 6, 9, 11]:
            return 30
        elif month == 2:
            if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                return 29
            else:
                return 28
        else:
            return 31
    
    async def create_recurring_instance(self, recurring_id):
        
        recurring = self.meetings["recurring"].get(recurring_id)
        if not recurring:
            return
        

        meeting_id = str(uuid.uuid4())
        new_meeting = recurring["template"].copy()
        

        next_time = datetime.datetime.fromisoformat(recurring["next_instance_time"])
        duration = datetime.datetime.fromisoformat(recurring["template"]["end_time"]) - \
                  datetime.datetime.fromisoformat(recurring["template"]["start_time"])
        
        new_meeting["start_time"] = next_time.isoformat()
        new_meeting["end_time"] = (next_time + duration).isoformat()
        new_meeting["created_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        new_meeting["status"] = "scheduled"
        new_meeting["recurring_id"] = recurring_id
        new_meeting["attendees"] = {"attending": [], "maybe": [], "declined": []}
        new_meeting["notes"] = ""
        new_meeting["action_items"] = []
        

        self.meetings["meetings"][meeting_id] = new_meeting
        

        recurring_type = recurring.get("type", "weekly")
        if recurring_type == "daily":
            next_instance = next_time + datetime.timedelta(days=1)
        elif recurring_type == "weekly":
            next_instance = next_time + datetime.timedelta(days=7)
        elif recurring_type == "biweekly":
            next_instance = next_time + datetime.timedelta(days=14)
        elif recurring_type == "monthly":
            next_instance = self.add_month(next_time)
        

        recurring["next_instance_time"] = next_instance.isoformat()
        self.save_meetings()
        

        guild = self.bot.get_guild(int(new_meeting["guild_id"]))
        if guild:
            channel = guild.get_channel(int(new_meeting["channel_id"]))
            if channel:
                embed = self.create_meeting_embed(meeting_id, new_meeting)
                view = self.MeetingView(self, meeting_id, new_meeting)
                await channel.send(f"A new recurring meeting has been scheduled:", embed=embed, view=view)
    
    async def send_reminder(self, meeting_id, meeting, reminder_type):
        
        guild = self.bot.get_guild(int(meeting["guild_id"]))
        if not guild:
            return
        
        channel = guild.get_channel(int(meeting["channel_id"]))
        if not channel:
            return
        

        embed = self.create_meeting_embed(meeting_id, meeting)
        
        if reminder_type == "24hour":
            embed.title = f"⏰ 24 Hour Reminder: {meeting['title']}"
            reminder_text = "This meeting will start in 24 hours!"
        elif reminder_type == "1hour":
            embed.title = f"⏰ 1 Hour Reminder: {meeting['title']}"
            reminder_text = "This meeting will start in 1 hour!"
        elif reminder_type == "10min":
            embed.title = f"⏰ 10 Minute Reminder: {meeting['title']}"
            reminder_text = "This meeting will start in 10 minutes!"
        
        embed.description = f"{reminder_text}\n\n{embed.description}"
        

        view = self.MeetingReminderView(self, meeting_id, meeting)
        await channel.send(embed=embed, view=view)
        

        for user_id in meeting["attendees"].get("attending", []):
            try:
                member = guild.get_member(int(user_id))
                if member:
                    await member.send(f"**Reminder for meeting in {guild.name}**", embed=embed)
            except:
                pass  
    
    async def send_meeting_starting_notification(self, meeting_id, meeting):
        
        guild = self.bot.get_guild(int(meeting["guild_id"]))
        if not guild:
            return
        
        channel = guild.get_channel(int(meeting["channel_id"]))
        if not channel:
            return
        

        embed = self.create_meeting_embed(meeting_id, meeting)
        embed.title = f"🚀 Starting Now: {meeting['title']}"
        

        if meeting.get("virtual_link"):
            embed.add_field(name="Join Meeting", value=f"[Click here to join]({meeting['virtual_link']})", inline=False)
        

        attending_mentions = []
        for user_id in meeting["attendees"].get("attending", []):
            attending_mentions.append(f"<@{user_id}>")
        
        if attending_mentions:
            mention_text = " ".join(attending_mentions)
            await channel.send(f"The meeting is starting now! {mention_text}", embed=embed)
        else:
            await channel.send("The meeting is starting now!", embed=embed)
        

        for user_id in meeting["attendees"].get("attending", []):
            try:
                member = guild.get_member(int(user_id))
                if member:
                    dm_embed = embed.copy()
                    if meeting.get("virtual_link"):
                        dm_embed.description += f"\n\n**Join now:** {meeting['virtual_link']}"
                    await member.send("Your meeting is starting now!", embed=dm_embed)
            except:
                pass  
    
    async def send_meeting_summary_request(self, meeting_id, meeting):
        
        guild = self.bot.get_guild(int(meeting["guild_id"]))
        if not guild:
            return
        
        channel = guild.get_channel(int(meeting["channel_id"]))
        if not channel:
            return
        

        embed = discord.Embed(
            title=f"📝 Meeting Completed: {meeting['title']}",
            description="The meeting has ended. The host can now add meeting notes and action items.",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        


        start_time = datetime.datetime.fromisoformat(meeting["start_time"])
        end_time = datetime.datetime.fromisoformat(meeting["end_time"])
        
        embed.add_field(name="Date", value=start_time.strftime("%A, %B %d, %Y"), inline=True)
        embed.add_field(name="Time", value=f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}", inline=True)
        

        attending_count = len(meeting["attendees"].get("attending", []))
        maybe_count = len(meeting["attendees"].get("maybe", []))
        declined_count = len(meeting["attendees"].get("declined", []))
        
        embed.add_field(
            name="Attendance",
            value=f"✅ Attending: {attending_count}\n❓ Maybe: {maybe_count}\n❌ Declined: {declined_count}",
            inline=False
        )
        

        view = self.MeetingSummaryView(self, meeting_id, meeting)
        await channel.send(f"<@{meeting['host']}>", embed=embed, view=view)
    
    def create_meeting_embed(self, meeting_id, meeting):
        
        status_emoji = STATUS_EMOJIS.get(meeting["status"], "📅")
        
        embed = discord.Embed(
            title=f"{status_emoji} {meeting['title']}",
            description=meeting["description"],
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        

        start_time = datetime.datetime.fromisoformat(meeting["start_time"])
        end_time = datetime.datetime.fromisoformat(meeting["end_time"])
        

        duration = end_time - start_time
        hours, remainder = divmod(duration.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        duration_str = ""
        if hours:
            duration_str += f"{hours} hour{'s' if hours > 1 else ''} "
        if minutes:
            duration_str += f"{minutes} minute{'s' if minutes > 1 else ''}"
        

        embed.add_field(name="ID", value=meeting_id[:8], inline=True)
        embed.add_field(name="Status", value=meeting["status"].capitalize(), inline=True)
        embed.add_field(name="Host", value=f"<@{meeting['host']}>", inline=True)
        
        embed.add_field(name="Date", value=start_time.strftime("%A, %B %d, %Y"), inline=True)
        embed.add_field(name="Time", value=f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}", inline=True)
        embed.add_field(name="Duration", value=duration_str, inline=True)
        
        if meeting.get("location"):
            embed.add_field(name="Location", value=meeting["location"], inline=True)
        
        if meeting.get("virtual_link"):
            embed.add_field(name="Virtual Meeting", value="Yes ✓", inline=True)
        
        if meeting.get("recurring"):
            recurring_type = meeting.get("recurring_type", "weekly").capitalize()
            embed.add_field(name="Recurring", value=recurring_type, inline=True)
        

        attending_count = len(meeting["attendees"].get("attending", []))
        maybe_count = len(meeting["attendees"].get("maybe", []))
        declined_count = len(meeting["attendees"].get("declined", []))
        
        if attending_count + maybe_count + declined_count > 0:
            embed.add_field(
                name="RSVP Status",
                value=f"✅ Attending: {attending_count}\n❓ Maybe: {maybe_count}\n❌ Declined: {declined_count}",
                inline=False
            )
        

        if meeting.get("agenda_items"):
            agenda_text = "\n".join([f"• {item}" for item in meeting["agenda_items"]])
            embed.add_field(name="📑 Agenda", value=agenda_text, inline=False)
        

        if meeting["status"] == "completed" and meeting.get("action_items"):
            action_text = "\n".join([f"• {item}" for item in meeting["action_items"]])
            embed.add_field(name="📋 Action Items", value=action_text, inline=False)
        

        if meeting["status"] == "completed" and meeting.get("notes"):
            notes_preview = meeting["notes"][:1000] + "..." if len(meeting["notes"]) > 1000 else meeting["notes"]
            embed.add_field(name="📝 Meeting Notes", value=notes_preview, inline=False)
        

        created_at = datetime.datetime.fromisoformat(meeting["created_at"])
        embed.set_footer(text=f"Created by {meeting['host_name']} • {created_at.strftime('%B %d, %Y')} | Meeting Scheduler by TheZ")
        
        return embed
    
    class MeetingView(discord.ui.View):
        def __init__(self, cog, meeting_id, meeting, timeout=None):
            super().__init__(timeout=timeout)
            self.cog = cog
            self.meeting_id = meeting_id
            self.meeting = meeting
            
        @discord.ui.button(label="RSVP", style=discord.ButtonStyle.primary, emoji="📝")
        async def rsvp_button(self, interaction: discord.Interaction, button: discord.ui.Button):

            view = self.cog.RSVPView(self.cog, self.meeting_id, self.meeting)
            await interaction.response.send_message("Please select your RSVP status:", view=view, ephemeral=True)

        
        @discord.ui.button(label="View Details", style=discord.ButtonStyle.secondary, emoji="🔍")
        async def details_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed = self.cog.create_meeting_embed(self.meeting_id, self.meeting)
            

            attending = self.meeting["attendees"].get("attending", [])
            maybe = self.meeting["attendees"].get("maybe", [])
            declined = self.meeting["attendees"].get("declined", [])
            
            if attending:
                attendee_names = []
                for user_id in attending:
                    member = interaction.guild.get_member(int(user_id))
                    if member:
                        attendee_names.append(member.display_name)
                if attendee_names:
                    embed.add_field(name="✅ Attending", value="\n".join(attendee_names), inline=True)
            
            if maybe:
                maybe_names = []
                for user_id in maybe:
                    member = interaction.guild.get_member(int(user_id))
                    if member:
                        maybe_names.append(member.display_name)
                if maybe_names:
                    embed.add_field(name="❓ Maybe", value="\n".join(maybe_names), inline=True)
            
            if declined:
                declined_names = []
                for user_id in declined:
                    member = interaction.guild.get_member(int(user_id))
                    if member:
                        declined_names.append(member.display_name)
                if declined_names:
                    embed.add_field(name="❌ Declined", value="\n".join(declined_names), inline=True)
            

            if self.meeting.get("virtual_link") and (
                interaction.user.id == int(self.meeting["host"]) or 
                str(interaction.user.id) in attending
            ):
                embed.add_field(
                    name="🔗 Meeting Link", 
                    value=f"[Click here to join]({self.meeting['virtual_link']})",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        @discord.ui.button(label="Edit Meeting", style=discord.ButtonStyle.secondary, emoji="✏️")
        async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):

            if not self.cog.can_manage_meeting(self.meeting, interaction.user):
                await interaction.response.send_message("Only the meeting host or administrators can edit this meeting.", ephemeral=True)
                return
            

            meeting = self.meeting
            meeting_id = self.meeting_id
            cog = self.cog
            

            class EditModal(discord.ui.Modal, title="Edit Meeting"):
                def __init__(self):
                    super().__init__()
                    

                    self.title_input = discord.ui.TextInput(
                        label="Meeting Title",
                        placeholder="Enter meeting title",
                        default=meeting["title"],
                        required=True,
                        max_length=100
                    )
                    
                    self.description_input = discord.ui.TextInput(
                        label="Description",
                        style=discord.TextStyle.paragraph,
                        placeholder="Enter meeting description",
                        default=meeting["description"],
                        required=True,
                        max_length=1000
                    )
                    
                    start_time = datetime.datetime.fromisoformat(meeting["start_time"])
                    formatted_start = start_time.strftime("%Y-%m-%d %H:%M")
                    
                    self.start_time_input = discord.ui.TextInput(
                        label="Start Time (YYYY-MM-DD HH:MM)",
                        placeholder="e.g. 2023-12-31 14:30",
                        default=formatted_start,
                        required=True
                    )
                    
                    end_time = datetime.datetime.fromisoformat(meeting["end_time"])
                    formatted_end = end_time.strftime("%Y-%m-%d %H:%M")
                    
                    self.end_time_input = discord.ui.TextInput(
                        label="End Time (YYYY-MM-DD HH:MM)",
                        placeholder="e.g. 2023-12-31 15:30",
                        default=formatted_end,
                        required=True
                    )
                    
                    location_default = meeting.get("location", "") or meeting.get("virtual_link", "")
                    
                    self.location_input = discord.ui.TextInput(
                        label="Location/Virtual Link (optional)",
                        placeholder="Enter location or meeting link",
                        default=location_default,
                        required=False
                    )
                    

                    self.add_item(self.title_input)
                    self.add_item(self.description_input)
                    self.add_item(self.start_time_input)
                    self.add_item(self.end_time_input)
                    self.add_item(self.location_input)
                
                async def on_submit(self, interaction: discord.Interaction):
                    try:

                        try:
                            start_time = datetime.datetime.strptime(self.start_time_input.value, "%Y-%m-%d %H:%M")
                            start_time = start_time.replace(tzinfo=datetime.timezone.utc)
                        except ValueError:
                            await interaction.response.send_message("Invalid start time format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                            return
                        
                        try:
                            end_time = datetime.datetime.strptime(self.end_time_input.value, "%Y-%m-%d %H:%M")
                            end_time = end_time.replace(tzinfo=datetime.timezone.utc)
                        except ValueError:
                            await interaction.response.send_message("Invalid end time format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                            return
                        
                        if end_time <= start_time:
                            await interaction.response.send_message("End time must be after start time.", ephemeral=True)
                            return
                        

                        meeting["title"] = self.title_input.value
                        meeting["description"] = self.description_input.value
                        meeting["start_time"] = start_time.isoformat()
                        meeting["end_time"] = end_time.isoformat()
                        

                        location_value = self.location_input.value.strip()
                        if location_value.startswith(("http://", "https://")):
                            meeting["virtual_link"] = location_value
                            meeting["location"] = ""
                        else:
                            meeting["location"] = location_value
                            meeting["virtual_link"] = ""
                        
                        meeting["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                        meeting["updated_by"] = str(interaction.user.id)
                        meeting["updated_by_name"] = interaction.user.display_name
                        
                        cog.save_meetings()
                        

                        embed = cog.create_meeting_embed(meeting_id, meeting)
                        await interaction.response.send_message("Meeting details have been updated.", ephemeral=True)
                        
                        try:
                            channel = interaction.guild.get_channel(int(meeting["channel_id"]))
                            if channel:
                                async for message in channel.history(limit=50):
                                    if message.author.id == interaction.client.user.id and message.embeds:
                                        for embed_idx, msg_embed in enumerate(message.embeds):
                                            if msg_embed.title and meeting_id[:8] in str(msg_embed.fields[0].value):
                                                await message.edit(embed=embed, view=cog.MeetingView(cog, meeting_id, meeting))
                                                break
                        except Exception as e:
                            print(f"Error updating message: {e}")
                        
                    except Exception as e:
                        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
            

            try:
                modal = EditModal()
                await interaction.response.send_modal(modal)
            except Exception as e:
                await interaction.response.send_message(f"Error creating modal: {str(e)}", ephemeral=True)


        

        
        @discord.ui.button(label="Manage Agenda", style=discord.ButtonStyle.secondary, emoji="📑", row=1)
        async def agenda_button(self, interaction: discord.Interaction, button: discord.ui.Button):

            if str(interaction.user.id) != self.meeting["host"] and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("Only the meeting host or administrators can manage the agenda.", ephemeral=True)
                return
            

            view = self.cog.AgendaManagementView(self.cog, self.meeting_id, self.meeting)
            await interaction.response.send_message("Manage meeting agenda:", view=view, ephemeral=True)

        
        @discord.ui.button(label="Cancel Meeting", style=discord.ButtonStyle.danger, emoji="❌", row=1)
        async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):

            if str(interaction.user.id) != self.meeting["host"] and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("Only the meeting host or administrators can cancel this meeting.", ephemeral=True)
                return
            

            confirm_view = self.cog.ConfirmView()
            await interaction.response.send_message(f"Are you sure you want to cancel the meeting **{self.meeting['title']}**?", view=confirm_view, ephemeral=True)
            

            await confirm_view.wait()
            if confirm_view.value:
                self.meeting["status"] = "cancelled"
                self.cog.save_meetings()
                

                embed = self.cog.create_meeting_embed(self.meeting_id, self.meeting)
                await interaction.message.edit(embed=embed, view=self.cog.MeetingView(self.cog, self.meeting_id, self.meeting))
                

                cancellation_embed = discord.Embed(
                    title=f"❌ Meeting Cancelled: {self.meeting['title']}",
                    description=f"This meeting has been cancelled by {interaction.user.display_name}.",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.now()
                )
                

                start_time = datetime.datetime.fromisoformat(self.meeting["start_time"])
                cancellation_embed.add_field(name="Was scheduled for", value=start_time.strftime("%A, %B %d, %Y at %I:%M %p"), inline=False)
                
                await interaction.edit_original_response(content="Meeting has been cancelled.", embed=cancellation_embed, view=None)
                

                for user_id in self.meeting["attendees"].get("attending", []):
                    try:
                        member = interaction.guild.get_member(int(user_id))
                        if member:
                            await member.send(f"A meeting you were planning to attend has been cancelled:", embed=cancellation_embed)
                    except:
                        pass  
            else:
                await interaction.edit_original_response(content="Meeting cancellation aborted.", view=None)
    
    class MeetingReminderView(discord.ui.View):
        def __init__(self, cog, meeting_id, meeting):
            super().__init__(timeout=None)
            self.cog = cog
            self.meeting_id = meeting_id
            self.meeting = meeting
            
        @discord.ui.button(label="View Details", style=discord.ButtonStyle.secondary, emoji="🔍")
        async def details_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed = self.cog.create_meeting_embed(self.meeting_id, self.meeting)
            

            attending = self.meeting["attendees"].get("attending", [])
            if attending:
                attendee_names = []
                for user_id in attending:
                    member = interaction.guild.get_member(int(user_id))
                    if member:
                        attendee_names.append(member.display_name)
                if attendee_names:
                    embed.add_field(name="✅ Attending", value="\n".join(attendee_names[:15]) + 
                                   (f"\n...and {len(attendee_names) - 15} more" if len(attendee_names) > 15 else ""), 
                                   inline=True)
            

            if self.meeting.get("virtual_link") and (
                interaction.user.id == int(self.meeting["host"]) or 
                str(interaction.user.id) in attending
            ):
                embed.add_field(
                    name="🔗 Meeting Link", 
                    value=f"[Click here to join]({self.meeting['virtual_link']})",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        @discord.ui.button(label="RSVP", style=discord.ButtonStyle.primary, emoji="📝")
        async def rsvp_button(self, interaction: discord.Interaction, button: discord.ui.Button):

            view = self.cog.RSVPView(self.cog, self.meeting_id, self.meeting)
            await interaction.response.send_message("Please select your RSVP status:", view=view, ephemeral=True)
    
    class MeetingSummaryView(discord.ui.View):
        def __init__(self, cog, meeting_id, meeting):
            super().__init__(timeout=None)
            self.cog = cog
            self.meeting_id = meeting_id
            self.meeting = meeting
            
        @discord.ui.button(label="Add Meeting Notes", style=discord.ButtonStyle.primary, emoji="📝")
        async def notes_button(self, interaction: discord.Interaction, button: discord.ui.Button):

            if str(interaction.user.id) != self.meeting["host"] and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("Only the meeting host or administrators can add meeting notes.", ephemeral=True)
                return
            

            await interaction.response.send_modal(self.cog.MeetingNotesModal(self.cog, self.meeting_id, self.meeting))
        
        @discord.ui.button(label="Add Action Items", style=discord.ButtonStyle.primary, emoji="📋")
        async def action_items_button(self, interaction: discord.Interaction, button: discord.ui.Button):

            if str(interaction.user.id) != self.meeting["host"] and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("Only the meeting host or administrators can add action items.", ephemeral=True)
                return
            

            await interaction.response.send_modal(self.cog.ActionItemsModal(self.cog, self.meeting_id, self.meeting))
        
        @discord.ui.button(label="Generate Summary", style=discord.ButtonStyle.success, emoji="📊")
        async def summary_button(self, interaction: discord.Interaction, button: discord.ui.Button):

            if str(interaction.user.id) != self.meeting["host"] and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("Only the meeting host or administrators can generate the summary.", ephemeral=True)
                return
            

            await self.generate_and_send_summary(interaction)
        
        async def generate_and_send_summary(self, interaction):
            

            embed = discord.Embed(
                title=f"📊 Meeting Summary: {self.meeting['title']}",
                description=self.meeting.get("notes", "No meeting notes were recorded."),
                color=discord.Color.green(),
                timestamp=datetime.datetime.now()
            )
            

            start_time = datetime.datetime.fromisoformat(self.meeting["start_time"])
            end_time = datetime.datetime.fromisoformat(self.meeting["end_time"])
            
            embed.add_field(name="Date", value=start_time.strftime("%A, %B %d, %Y"), inline=True)
            embed.add_field(name="Time", value=f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}", inline=True)
            embed.add_field(name="Host", value=f"<@{self.meeting['host']}>", inline=True)
            

            attending = self.meeting["attendees"].get("attending", [])
            maybe = self.meeting["attendees"].get("maybe", [])
            declined = self.meeting["attendees"].get("declined", [])
            

            attendee_names = []
            for user_id in attending:
                member = interaction.guild.get_member(int(user_id))
                if member:
                    attendee_names.append(member.display_name)
            
            if attendee_names:
                embed.add_field(
                    name=f"✅ Attendees ({len(attendee_names)})",
                    value=", ".join(attendee_names[:10]) + (f" and {len(attendee_names) - 10} more" if len(attendee_names) > 10 else ""),
                    inline=False
                )
            

            if self.meeting.get("agenda_items"):
                agenda_text = "\n".join([f"• {item}" for item in self.meeting["agenda_items"]])
                embed.add_field(name="📑 Agenda", value=agenda_text, inline=False)
            

            if self.meeting.get("action_items"):
                action_text = "\n".join([f"• {item}" for item in self.meeting["action_items"]])
                embed.add_field(name="📋 Action Items", value=action_text, inline=False)
            else:
                embed.add_field(name="📋 Action Items", value="No action items were recorded.", inline=False)
            

            if attending or maybe or declined:

                file = await self.create_attendance_chart(len(attending), len(maybe), len(declined))
                embed.set_image(url="attachment://attendance.png")
                
                await interaction.response.send_message(
                    "Here's the meeting summary:",
                    embed=embed,
                    file=file
                )
            else:
                await interaction.response.send_message(
                    "Here's the meeting summary:",
                    embed=embed
                )
        
        async def create_attendance_chart(self, attending, maybe, declined):
            

            def create_chart():
                labels = ['Attending', 'Maybe', 'Declined']
                sizes = [attending, maybe, declined]
                colors = ['#43B581', '#FAA61A', '#F04747']
                

                filtered_labels = []
                filtered_sizes = []
                filtered_colors = []
                
                for i, size in enumerate(sizes):
                    if size > 0:
                        filtered_labels.append(labels[i])
                        filtered_sizes.append(size)
                        filtered_colors.append(colors[i])
                
                plt.figure(figsize=(8, 6))
                plt.pie(filtered_sizes, labels=filtered_labels, colors=filtered_colors, autopct='%1.1f%%', startangle=90)
                plt.axis('equal')
                plt.title('Meeting Attendance')
                

                buf = BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                plt.close()
                return buf
            

            chart_bytes = await asyncio.to_thread(create_chart)
            return discord.File(chart_bytes, filename="attendance.png")
    
    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.value = None
            
        @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.value = True
            self.stop()
            await interaction.response.defer()
            
        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.value = False
            self.stop()
            await interaction.response.defer()
    
    class RSVPView(discord.ui.View):
        def __init__(self, cog, meeting_id, meeting):
            super().__init__(timeout=60)
            self.cog = cog
            self.meeting_id = meeting_id
            self.meeting = meeting
            
        @discord.ui.button(label="Attending", style=discord.ButtonStyle.success, emoji="✅")
        async def attending_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.update_rsvp(interaction, "attending")
            
        @discord.ui.button(label="Maybe", style=discord.ButtonStyle.secondary, emoji="❓")
        async def maybe_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.update_rsvp(interaction, "maybe")
            
        @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
        async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.update_rsvp(interaction, "declined")
        
        async def update_rsvp(self, interaction, status):
            
            user_id = str(interaction.user.id)
            

            for list_name in ["attending", "maybe", "declined"]:
                if user_id in self.meeting["attendees"].get(list_name, []):
                    self.meeting["attendees"][list_name].remove(user_id)
            

            if status not in self.meeting["attendees"]:
                self.meeting["attendees"][status] = []
            
            self.meeting["attendees"][status].append(user_id)
            

            self.cog.save_meetings()
            

            try:
                channel = interaction.guild.get_channel(int(self.meeting["channel_id"]))
                if channel:
                    async for message in channel.history(limit=50):
                        if message.author.id == interaction.client.user.id and message.embeds:
                            for embed in message.embeds:
                                if embed.title and self.meeting["title"] in embed.title and self.meeting_id[:8] in str(embed.fields[0].value):
                                    new_embed = self.cog.create_meeting_embed(self.meeting_id, self.meeting)
                                    await message.edit(embed=new_embed)
                                    break
            except:
                pass  
            

            status_text = "attending" if status == "attending" else "maybe attending" if status == "maybe" else "declining"
            await interaction.response.send_message(f"You are now {status_text} this meeting.", ephemeral=True)
    
    class AgendaItemRow(discord.ui.Button):
        def __init__(self, index, item):
            super().__init__(
                label=f"{index+1}. {item[:40]}{'...' if len(item) > 40 else ''}",
                style=discord.ButtonStyle.secondary,
                disabled=True
            )
            self.index = index
            self.item = item

        
    class AgendaManagementView(discord.ui.View):
        def __init__(self, cog, meeting_id, meeting):
            super().__init__(timeout=180)
            self.cog = cog
            self.meeting_id = meeting_id
            self.meeting = meeting
            

            if self.meeting.get("agenda_items"):
                for i, item in enumerate(self.meeting["agenda_items"]):

                    self.add_item(self.cog.AgendaItemRow(i, item))
            
        @discord.ui.button(label="Add Agenda Item", style=discord.ButtonStyle.primary, emoji="➕")
        async def add_item_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(self.cog.AddAgendaItemModal(self.cog, self.meeting_id, self.meeting))
        
        @discord.ui.button(label="Clear All Items", style=discord.ButtonStyle.danger, emoji="🗑️")
        async def clear_items_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            confirm_view = self.cog.ConfirmView()
            await interaction.response.send_message("Are you sure you want to clear all agenda items?", view=confirm_view, ephemeral=True)
            
            await confirm_view.wait()
            if confirm_view.value:
                self.meeting["agenda_items"] = []
                self.cog.save_meetings()
                

                embed = self.cog.create_meeting_embed(self.meeting_id, self.meeting)
                try:
                    channel = interaction.guild.get_channel(int(self.meeting["channel_id"]))
                    if channel:
                        async for message in channel.history(limit=50):
                            if message.author.id == interaction.client.user.id and message.embeds:
                                for embed_idx, msg_embed in enumerate(message.embeds):
                                    if msg_embed.title and self.meeting["title"] in msg_embed.title and self.meeting_id[:8] in str(msg_embed.fields[0].value):
                                        await message.edit(embed=embed)
                                        break
                except:
                    pass  
                
                await interaction.edit_original_response(content="All agenda items have been cleared.", view=None)
                

                new_view = self.cog.AgendaManagementView(self.cog, self.meeting_id, self.meeting)
                await interaction.followup.send("Agenda has been updated:", view=new_view, ephemeral=True)
            else:
                await interaction.edit_original_response(content="Operation cancelled.", view=None)
    

    class MeetingNotesModal(discord.ui.Modal, title="Meeting Notes"):
        def __init__(self, cog, meeting_id, meeting):
            super().__init__()
            self.cog = cog
            self.meeting_id = meeting_id
            self.meeting = meeting
            
            self.notes = discord.ui.TextInput(
                label="Meeting Notes",
                style=discord.TextStyle.paragraph,
                placeholder="Enter the meeting notes here...",
                default=meeting.get("notes", ""),
                required=True,
                max_length=4000
            )
            
            self.add_item(self.notes)
        
        async def on_submit(self, interaction: discord.Interaction):
            self.meeting["notes"] = self.notes.value
            self.meeting["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.meeting["updated_by"] = str(interaction.user.id)
            self.meeting["updated_by_name"] = interaction.user.display_name
            
            self.cog.save_meetings()
            
            await interaction.response.send_message("Meeting notes have been saved.", ephemeral=True)
    
    class ActionItemsModal(discord.ui.Modal, title="Action Items"):
        def __init__(self, cog, meeting_id, meeting):
            super().__init__()
            self.cog = cog
            self.meeting_id = meeting_id
            self.meeting = meeting
            
            current_items = "\n".join(meeting.get("action_items", []))
            
            self.action_items = discord.ui.TextInput(
                label="Action Items (one per line)",
                style=discord.TextStyle.paragraph,
                placeholder="Enter action items, one per line...",
                default=current_items,
                required=False,
                max_length=4000
            )
            
            self.add_item(self.action_items)
        
        async def on_submit(self, interaction: discord.Interaction):

            items = [item.strip() for item in self.action_items.value.split("\n") if item.strip()]
            
            self.meeting["action_items"] = items
            self.meeting["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.meeting["updated_by"] = str(interaction.user.id)
            self.meeting["updated_by_name"] = interaction.user.display_name
            
            self.cog.save_meetings()
            
            await interaction.response.send_message(f"{len(items)} action items have been saved.", ephemeral=True)
    
    class AddAgendaItemModal(discord.ui.Modal, title="Add Agenda Item"):
        def __init__(self, cog, meeting_id, meeting):
            super().__init__()
            self.cog = cog
            self.meeting_id = meeting_id
            self.meeting = meeting
            
            self.agenda_item = discord.ui.TextInput(
                label="Agenda Item",
                placeholder="Enter the agenda item...",
                required=True,
                max_length=200
            )
            
            self.add_item(self.agenda_item)
        
        async def on_submit(self, interaction: discord.Interaction):
            if "agenda_items" not in self.meeting:
                self.meeting["agenda_items"] = []
            
            self.meeting["agenda_items"].append(self.agenda_item.value)
            self.meeting["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.meeting["updated_by"] = str(interaction.user.id)
            self.meeting["updated_by_name"] = interaction.user.display_name
            
            self.cog.save_meetings()
            

            embed = self.cog.create_meeting_embed(self.meeting_id, self.meeting)
            try:
                channel = interaction.guild.get_channel(int(self.meeting["channel_id"]))
                if channel:
                    async for message in channel.history(limit=50):
                        if message.author.id == interaction.client.user.id and message.embeds:
                            for embed_idx, msg_embed in enumerate(message.embeds):
                                if msg_embed.title and self.meeting["title"] in msg_embed.title and self.meeting_id[:8] in str(msg_embed.fields[0].value):
                                    await message.edit(embed=embed)
                                    break
            except:
                pass  
            


            new_view = self.cog.AgendaManagementView(self.cog, self.meeting_id, self.meeting)
            await interaction.response.send_message("Agenda item added. Current agenda:", view=new_view, ephemeral=True)

    
    class EditMeetingModal(discord.ui.Modal, title="Edit Meeting"):
        def __init__(self, cog, meeting_id, meeting):
            super().__init__()
            self.cog = cog
            self.meeting_id = meeting_id
            self.meeting = meeting
            
            self.title = discord.ui.TextInput(
                label="Meeting Title",
                placeholder="Enter meeting title",
                default=meeting["title"],
                required=True,
                max_length=100
            )
            
            self.description = discord.ui.TextInput(
                label="Description",
                style=discord.TextStyle.paragraph,
                placeholder="Enter meeting description",
                default=meeting["description"],
                required=True,
                max_length=1000
            )
            
            start_time = datetime.datetime.fromisoformat(meeting["start_time"])
            formatted_start = start_time.strftime("%Y-%m-%d %H:%M")
            
            self.start_time = discord.ui.TextInput(
                label="Start Time (YYYY-MM-DD HH:MM)",
                placeholder="e.g. 2023-12-31 14:30",
                default=formatted_start,
                required=True
            )
            
            end_time = datetime.datetime.fromisoformat(meeting["end_time"])
            formatted_end = end_time.strftime("%Y-%m-%d %H:%M")
            
            self.end_time = discord.ui.TextInput(
                label="End Time (YYYY-MM-DD HH:MM)",
                placeholder="e.g. 2023-12-31 15:30",
                default=formatted_end,
                required=True
            )
            
            self.location = discord.ui.TextInput(
                label="Location/Virtual Link (optional)",
                placeholder="Enter location or meeting link",
                default=meeting.get("location", "") or meeting.get("virtual_link", ""),
                required=False
            )
            
            self.add_item(self.title)
            self.add_item(self.description)
            self.add_item(self.start_time)
            self.add_item(self.end_time)
            self.add_item(self.location)
        
        async def on_submit(self, interaction: discord.Interaction):
            try:

                try:
                    start_time = datetime.datetime.strptime(self.start_time.value, "%Y-%m-%d %H:%M")
                    start_time = start_time.replace(tzinfo=datetime.timezone.utc)
                except ValueError:
                    await interaction.response.send_message("Invalid start time format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                    return
                
                try:
                    end_time = datetime.datetime.strptime(self.end_time.value, "%Y-%m-%d %H:%M")
                    end_time = end_time.replace(tzinfo=datetime.timezone.utc)
                except ValueError:
                    await interaction.response.send_message("Invalid end time format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                    return
                
                if end_time <= start_time:
                    await interaction.response.send_message("End time must be after start time.", ephemeral=True)
                    return
                

                self.meeting["title"] = self.title.value
                self.meeting["description"] = self.description.value
                self.meeting["start_time"] = start_time.isoformat()
                self.meeting["end_time"] = end_time.isoformat()
                

                location_value = self.location.value.strip()
                if location_value.startswith(("http://", "https://")):
                    self.meeting["virtual_link"] = location_value
                    self.meeting["location"] = ""
                else:
                    self.meeting["location"] = location_value
                    self.meeting["virtual_link"] = ""
                
                self.meeting["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self.meeting["updated_by"] = str(interaction.user.id)
                self.meeting["updated_by_name"] = interaction.user.display_name
                
                self.cog.save_meetings()
                

                embed = self.cog.create_meeting_embed(self.meeting_id, self.meeting)
                await interaction.response.send_message("Meeting details have been updated.", ephemeral=True)
                
                try:
                    channel = interaction.guild.get_channel(int(self.meeting["channel_id"]))
                    if channel:
                        async for message in channel.history(limit=50):
                            if message.author.id == interaction.client.user.id and message.embeds:
                                for embed_idx, msg_embed in enumerate(message.embeds):
                                    if msg_embed.title and self.meeting_id[:8] in str(msg_embed.fields[0].value):
                                        await message.edit(embed=embed, view=self.cog.MeetingView(self.cog, self.meeting_id, self.meeting))
                                        break
                except Exception as e:
                    print(f"Error updating message: {e}")
                
            except Exception as e:
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    
    class CreateMeetingModal(discord.ui.Modal, title="Schedule Meeting"):
        def __init__(self, cog, channel_id, guild_id):
            super().__init__()
            self.cog = cog
            self.channel_id = channel_id
            self.guild_id = guild_id
            
            self.title = discord.ui.TextInput(
                label="Meeting Title",
                placeholder="Enter meeting title",
                required=True,
                max_length=100
            )
            
            self.description = discord.ui.TextInput(
                label="Description",
                style=discord.TextStyle.paragraph,
                placeholder="Enter meeting description",
                required=True,
                max_length=1000
            )
            

            now = datetime.datetime.now(datetime.timezone.utc)
            next_hour = now.replace(microsecond=0, second=0, minute=0) + datetime.timedelta(hours=1)
            formatted_start = next_hour.strftime("%Y-%m-%d %H:%M")
            
            self.start_time = discord.ui.TextInput(
                label="Start Time (YYYY-MM-DD HH:MM)",
                placeholder="e.g. 2023-12-31 14:30",
                default=formatted_start,
                required=True
            )
            

            next_hour_plus_one = next_hour + datetime.timedelta(hours=1)
            formatted_end = next_hour_plus_one.strftime("%Y-%m-%d %H:%M")
            
            self.end_time = discord.ui.TextInput(
                label="End Time (YYYY-MM-DD HH:MM)",
                placeholder="e.g. 2023-12-31 15:30",
                default=formatted_end,
                required=True
            )
            
            self.location = discord.ui.TextInput(
                label="Location/Virtual Link (optional)",
                placeholder="Enter location or meeting link",
                required=False
            )
            
            self.add_item(self.title)
            self.add_item(self.description)
            self.add_item(self.start_time)
            self.add_item(self.end_time)
            self.add_item(self.location)
        
        async def on_submit(self, interaction: discord.Interaction):
            try:

                try:
                    start_time = datetime.datetime.strptime(self.start_time.value, "%Y-%m-%d %H:%M")
                    start_time = start_time.replace(tzinfo=datetime.timezone.utc)
                except ValueError:
                    await interaction.response.send_message("Invalid start time format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                    return
                
                try:
                    end_time = datetime.datetime.strptime(self.end_time.value, "%Y-%m-%d %H:%M")
                    end_time = end_time.replace(tzinfo=datetime.timezone.utc)
                except ValueError:
                    await interaction.response.send_message("Invalid end time format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                    return
                
                if end_time <= start_time:
                    await interaction.response.send_message("End time must be after start time.", ephemeral=True)
                    return
                

                meeting_id = str(uuid.uuid4())
                

                location_value = self.location.value.strip()
                virtual_link = ""
                location = ""
                
                if location_value:
                    if location_value.startswith(("http://", "https://")):
                        virtual_link = location_value
                    else:
                        location = location_value
                
                meeting = {
                    "title": self.title.value,
                    "description": self.description.value,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "location": location,
                    "virtual_link": virtual_link,
                    "host": str(interaction.user.id),
                    "host_name": interaction.user.display_name,
                    "guild_id": str(self.guild_id),
                    "channel_id": str(self.channel_id),
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "status": "scheduled",
                    "recurring": False,
                    "attendees": {"attending": [str(interaction.user.id)], "maybe": [], "declined": []},
                    "agenda_items": [],
                    "attachments": [],
                    "notes": "",
                    "action_items": []
                }
                
                self.cog.meetings["meetings"][meeting_id] = meeting
                self.cog.save_meetings()
                

                embed = self.cog.create_meeting_embed(meeting_id, meeting)
                view = self.cog.MeetingView(self.cog, meeting_id, meeting)
                
                await interaction.response.send_message("Meeting scheduled successfully!", ephemeral=True)
                await interaction.channel.send(embed=embed, view=view)
                

                recurring_view = self.cog.RecurringMeetingView(self.cog, meeting_id, meeting)
                await interaction.followup.send("Would you like to make this a recurring meeting?", view=recurring_view, ephemeral=True)
                
            except Exception as e:
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

        
        async def on_submit(self, interaction: discord.Interaction):
            try:

                try:
                    start_time = datetime.datetime.strptime(self.start_time.value, "%Y-%m-%d %H:%M")
                    start_time = start_time.replace(tzinfo=datetime.timezone.utc)
                except ValueError:
                    await interaction.response.send_message("Invalid start time format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                    return
                
                try:
                    end_time = datetime.datetime.strptime(self.end_time.value, "%Y-%m-%d %H:%M")
                    end_time = end_time.replace(tzinfo=datetime.timezone.utc)
                except ValueError:
                    await interaction.response.send_message("Invalid end time format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                    return
                
                if end_time <= start_time:
                    await interaction.response.send_message("End time must be after start time.", ephemeral=True)
                    return
                

                meeting_id = str(uuid.uuid4())
                

                location_value = self.location.value.strip()
                virtual_link = ""
                location = ""
                
                if location_value:
                    if location_value.startswith(("http://", "https://")):
                        virtual_link = location_value
                    else:
                        location = location_value
                
                meeting = {
                    "title": self.title.value,
                    "description": self.description.value,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "location": location,
                    "virtual_link": virtual_link,
                    "host": str(interaction.user.id),
                    "host_name": interaction.user.display_name,
                    "guild_id": str(self.guild_id),
                    "channel_id": str(self.channel_id),
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "status": "scheduled",
                    "recurring": False,
                    "attendees": {"attending": [str(interaction.user.id)], "maybe": [], "declined": []},
                    "agenda_items": [],
                    "attachments": [],
                    "notes": "",
                    "action_items": []
                }
                
                self.cog.meetings["meetings"][meeting_id] = meeting
                self.cog.save_meetings()
                

                embed = self.cog.create_meeting_embed(meeting_id, meeting)
                view = self.cog.MeetingView(self.cog, meeting_id, meeting)
                
                await interaction.response.send_message("Meeting scheduled successfully!", ephemeral=True)
                await interaction.channel.send(embed=embed, view=view)
                
                recurring_view = self.cog.RecurringMeetingView(self.cog, meeting_id, meeting)

                await interaction.followup.send("Would you like to make this a recurring meeting?", view=recurring_view, ephemeral=True)
                
            except Exception as e:
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    
    class RecurringMeetingView(discord.ui.View):
        def __init__(self, cog, meeting_id, meeting):
            super().__init__(timeout=60)
            self.cog = cog
            self.meeting_id = meeting_id
            self.meeting = meeting
            
        @discord.ui.button(label="Daily", style=discord.ButtonStyle.primary)
        async def daily_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.set_recurring(interaction, "daily")
            
        @discord.ui.button(label="Weekly", style=discord.ButtonStyle.primary)
        async def weekly_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.set_recurring(interaction, "weekly")
            
        @discord.ui.button(label="Biweekly", style=discord.ButtonStyle.primary)
        async def biweekly_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.set_recurring(interaction, "biweekly")
            
        @discord.ui.button(label="Monthly", style=discord.ButtonStyle.primary)
        async def monthly_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.set_recurring(interaction, "monthly")
            
        @discord.ui.button(label="No, One-time Only", style=discord.ButtonStyle.secondary)
        async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("Meeting will remain as a one-time event.", ephemeral=True)
            self.stop()
        
        async def set_recurring(self, interaction, recurring_type):
            
            self.meeting["recurring"] = True
            self.meeting["recurring_type"] = recurring_type
            

            recurring_id = str(uuid.uuid4())
            self.meeting["recurring_id"] = recurring_id
            
            self.cog.save_meetings()
            

            embed = self.cog.create_meeting_embed(self.meeting_id, self.meeting)
            try:
                channel = interaction.guild.get_channel(int(self.meeting["channel_id"]))
                if channel:
                    async for message in channel.history(limit=50):
                        if message.author.id == interaction.client.user.id and message.embeds:
                            for embed_idx, msg_embed in enumerate(message.embeds):
                                if msg_embed.title and self.meeting_id[:8] in str(msg_embed.fields[0].value):
                                    await message.edit(embed=embed)
                                    break
            except:
                pass  

            if not self.cog.can_manage_meeting(self.meeting, interaction.user):
                await interaction.response.send_message("Only the meeting host or administrators can set recurring meetings.", ephemeral=True)
                return

            frequency = "daily" if recurring_type == "daily" else "weekly" if recurring_type == "weekly" else "every two weeks" if recurring_type == "biweekly" else "monthly"
            await interaction.response.send_message(f"Meeting has been set to recur {frequency}.", ephemeral=True)
            self.stop()
    
    class MeetingManagerView(discord.ui.View):
        def __init__(self, cog):
            super().__init__(timeout=180)
            self.cog = cog
            
        @discord.ui.button(label="Schedule Meeting", style=discord.ButtonStyle.primary, emoji="📅")
        async def schedule_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not self.cog.can_host_meetings(interaction.guild.id, interaction.user):
                await interaction.response.send_message("You don't have permission to host meetings. Contact an administrator or get the required role.", ephemeral=True)
                return  
            

            class ScheduleMeetingModal(discord.ui.Modal):
                def __init__(self, cog):
                    super().__init__(title="Schedule Meeting")
                    self.cog = cog
                    

                    self.title_input = discord.ui.TextInput(
                        label="Meeting Title",
                        placeholder="Enter meeting title",
                        required=True,
                        max_length=100
                    )
                    
                    self.description_input = discord.ui.TextInput(
                        label="Description",
                        style=discord.TextStyle.paragraph,
                        placeholder="Enter meeting description",
                        required=True,
                        max_length=1000
                    )
                    

                    now = datetime.datetime.now(datetime.timezone.utc)
                    next_hour = now.replace(microsecond=0, second=0, minute=0) + datetime.timedelta(hours=1)
                    formatted_start = next_hour.strftime("%Y-%m-%d %H:%M")
                    
                    self.start_time_input = discord.ui.TextInput(
                        label="Start Time (YYYY-MM-DD HH:MM)",
                        placeholder="e.g. 2023-12-31 14:30",
                        default=formatted_start,
                        required=True
                    )
                    

                    next_hour_plus_one = next_hour + datetime.timedelta(hours=1)
                    formatted_end = next_hour_plus_one.strftime("%Y-%m-%d %H:%M")
                    
                    self.end_time_input = discord.ui.TextInput(
                        label="End Time (YYYY-MM-DD HH:MM)",
                        placeholder="e.g. 2023-12-31 15:30",
                        default=formatted_end,
                        required=True
                    )
                    
                    self.location_input = discord.ui.TextInput(
                        label="Location/Virtual Link (optional)",
                        placeholder="Enter location or meeting link",
                        required=False
                    )
                    

                    self.add_item(self.title_input)
                    self.add_item(self.description_input)
                    self.add_item(self.start_time_input)
                    self.add_item(self.end_time_input)
                    self.add_item(self.location_input)
                
                async def on_submit(self, interaction: discord.Interaction):
                    try:

                        try:
                            start_time = datetime.datetime.strptime(self.start_time_input.value, "%Y-%m-%d %H:%M")
                            start_time = start_time.replace(tzinfo=datetime.timezone.utc)
                        except ValueError:
                            await interaction.response.send_message("Invalid start time format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                            return
                        
                        try:
                            end_time = datetime.datetime.strptime(self.end_time_input.value, "%Y-%m-%d %H:%M")
                            end_time = end_time.replace(tzinfo=datetime.timezone.utc)
                        except ValueError:
                            await interaction.response.send_message("Invalid end time format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                            return
                        
                        if end_time <= start_time:
                            await interaction.response.send_message("End time must be after start time.", ephemeral=True)
                            return
                        

                        meeting_id = str(uuid.uuid4())
                        

                        location_value = self.location_input.value.strip()
                        virtual_link = ""
                        location = ""
                        
                        if location_value:
                            if location_value.startswith(("http://", "https://")):
                                virtual_link = location_value
                            else:
                                location = location_value
                        
                        meeting = {
                            "title": self.title_input.value,
                            "description": self.description_input.value,
                            "start_time": start_time.isoformat(),
                            "end_time": end_time.isoformat(),
                            "location": location,
                            "virtual_link": virtual_link,
                            "host": str(interaction.user.id),
                            "host_name": interaction.user.display_name,
                            "guild_id": str(interaction.guild_id),
                            "channel_id": str(interaction.channel_id),
                            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            "status": "scheduled",
                            "recurring": False,
                            "attendees": {"attending": [str(interaction.user.id)], "maybe": [], "declined": []},
                            "agenda_items": [],
                            "attachments": [],
                            "notes": "",
                            "action_items": []
                        }
                        
                        self.cog.meetings["meetings"][meeting_id] = meeting
                        self.cog.save_meetings()
                        

                        embed = self.cog.create_meeting_embed(meeting_id, meeting)
                        view = self.cog.MeetingView(self.cog, meeting_id, meeting)
                        
                        await interaction.response.send_message("Meeting scheduled successfully!", ephemeral=True)
                        await interaction.channel.send(embed=embed, view=view)
                        

                        recurring_view = self.cog.RecurringMeetingView(self.cog, meeting_id, meeting)
                        await interaction.followup.send("Would you like to make this a recurring meeting?", view=recurring_view, ephemeral=True)
                        
                    except Exception as e:
                        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
            

            try:
                modal = ScheduleMeetingModal(self.cog)
                await interaction.response.send_modal(modal)
            except Exception as e:
                await interaction.response.send_message(f"Error creating modal: {str(e)}", ephemeral=True)




        @discord.ui.button(label="List Meetings", style=discord.ButtonStyle.secondary, emoji="📋")
        async def list_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.list_meetings(interaction)
            
        @discord.ui.button(label="My Meetings", style=discord.ButtonStyle.secondary, emoji="👤")
        async def my_meetings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.list_my_meetings(interaction)
            
        @discord.ui.button(label="Meeting Statistics", style=discord.ButtonStyle.secondary, emoji="📊", row=1)
        async def statistics_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.show_statistics(interaction)
            
        @discord.ui.button(label="Completed Meetings", style=discord.ButtonStyle.secondary, emoji="✅", row=1)
        async def completed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.list_completed_meetings(interaction)
        
        async def list_meetings(self, interaction):
            
            guild_meetings = {}
            now = datetime.datetime.now(datetime.timezone.utc)
            
            for meeting_id, meeting in self.cog.meetings["meetings"].items():
                if meeting.get("guild_id") == str(interaction.guild.id) and meeting["status"] != "cancelled":
                    start_time = datetime.datetime.fromisoformat(meeting["start_time"])
                    if start_time > now:  
                        guild_meetings[meeting_id] = meeting
            
            if not guild_meetings:
                await interaction.response.send_message("No upcoming meetings found.", ephemeral=True)
                return
            

            sorted_meetings = sorted(
                guild_meetings.items(), 
                key=lambda x: datetime.datetime.fromisoformat(x[1]["start_time"])
            )
            
            embed = discord.Embed(
                title="📋 Upcoming Meetings",
                description="Here are the upcoming meetings in this server:",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            
            for meeting_id, meeting in sorted_meetings[:10]:  
                start_time = datetime.datetime.fromisoformat(meeting["start_time"])
                time_until = start_time - now
                days_until = time_until.days
                hours_until = time_until.seconds // 3600
                
                if days_until > 0:
                    time_str = f"in {days_until} day{'s' if days_until > 1 else ''}"
                else:
                    time_str = f"in {hours_until} hour{'s' if hours_until > 1 else ''}"
                

                attendee_count = len(meeting["attendees"].get("attending", []))
                
                embed.add_field(
                    name=f"{meeting['title']} [{meeting_id[:8]}]",
                    value=f"📅 {start_time.strftime('%A, %B %d at %I:%M %p')}\n"
                          f"⏰ {time_str}\n"
                          f"👥 {attendee_count} attending\n"
                          f"🧑‍💼 Host: {meeting['host_name']}",
                    inline=False
                )
            
            if len(sorted_meetings) > 10:
                embed.set_footer(text=f"Showing 10 of {len(sorted_meetings)} upcoming meetings")
            
            view = self.cog.MeetingListView(self.cog, dict(sorted_meetings))
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        async def list_my_meetings(self, interaction):
            
            user_id = str(interaction.user.id)
            my_meetings = {}
            now = datetime.datetime.now(datetime.timezone.utc)
            
            for meeting_id, meeting in self.cog.meetings["meetings"].items():
                if meeting.get("guild_id") == str(interaction.guild.id) and meeting["status"] != "cancelled":

                    if meeting["host"] == user_id or user_id in meeting["attendees"].get("attending", []):
                        start_time = datetime.datetime.fromisoformat(meeting["start_time"])
                        if start_time > now:  
                            my_meetings[meeting_id] = meeting
            
            if not my_meetings:
                await interaction.response.send_message("You don't have any upcoming meetings.", ephemeral=True)
                return
            

            sorted_meetings = sorted(
                my_meetings.items(), 
                key=lambda x: datetime.datetime.fromisoformat(x[1]["start_time"])
            )
            
            embed = discord.Embed(
                title="📋 My Meetings",
                description="Here are your upcoming meetings:",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            
            hosting = []
            attending = []
            
            for meeting_id, meeting in sorted_meetings:
                start_time = datetime.datetime.fromisoformat(meeting["start_time"])
                time_str = start_time.strftime("%A, %B %d at %I:%M %p")
                
                meeting_str = f"**{meeting['title']}** [{meeting_id[:8]}]\n📅 {time_str}"
                
                if meeting["host"] == user_id:
                    hosting.append(meeting_str)
                else:
                    attending.append(meeting_str)
            
            if hosting:
                embed.add_field(
                    name="🧑‍💼 Meetings You're Hosting",
                    value="\n\n".join(hosting[:5]) + (f"\n\n*...and {len(hosting) - 5} more*" if len(hosting) > 5 else ""),
                    inline=False
                )
            
            if attending:
                embed.add_field(
                    name="👤 Meetings You're Attending",
                    value="\n\n".join(attending[:5]) + (f"\n\n*...and {len(attending) - 5} more*" if len(attending) > 5 else ""),
                    inline=False
                )
            
            view = self.cog.MeetingListView(self.cog, dict(sorted_meetings))
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        async def show_statistics(self, interaction):
            
            guild_id = str(interaction.guild.id)
            

            total_meetings = 0
            completed_meetings = 0
            cancelled_meetings = 0
            upcoming_meetings = 0
            total_attendance = 0
            meeting_hours = 0
            

            now = datetime.datetime.now(datetime.timezone.utc)
            for meeting in self.cog.meetings["meetings"].values():
                if meeting.get("guild_id") == guild_id:
                    total_meetings += 1
                    start_time = datetime.datetime.fromisoformat(meeting["start_time"])
                    
                    if meeting["status"] == "cancelled":
                        cancelled_meetings += 1
                    elif start_time > now:
                        upcoming_meetings += 1
                    

                    if meeting["status"] != "cancelled":
                        start = datetime.datetime.fromisoformat(meeting["start_time"])
                        end = datetime.datetime.fromisoformat(meeting["end_time"])
                        duration = (end - start).total_seconds() / 3600  
                        meeting_hours += duration
                    

                    total_attendance += len(meeting["attendees"].get("attending", []))
            

            for meeting in self.cog.meetings["completed"].values():
                if meeting.get("guild_id") == guild_id:
                    total_meetings += 1
                    completed_meetings += 1
                    

                    start = datetime.datetime.fromisoformat(meeting["start_time"])
                    end = datetime.datetime.fromisoformat(meeting["end_time"])
                    duration = (end - start).total_seconds() / 3600  
                    meeting_hours += duration
                    

                    total_attendance += len(meeting["attendees"].get("attending", []))
            

            embed = discord.Embed(
                title="📊 Meeting Statistics",
                description=f"Meeting statistics for {interaction.guild.name}",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(
                name="Meeting Counts",
                value=f"📅 Total Meetings: {total_meetings}\n"
                      f"✅ Completed: {completed_meetings}\n"
                      f"⏳ Upcoming: {upcoming_meetings}\n"
                      f"❌ Cancelled: {cancelled_meetings}",
                inline=True
            )
            
            avg_attendance = total_attendance / total_meetings if total_meetings > 0 else 0
            embed.add_field(
                name="Attendance",
                value=f"👥 Total Attendees: {total_attendance}\n"
                      f"📊 Average Per Meeting: {avg_attendance:.1f}",
                inline=True
            )
            
            embed.add_field(
                name="Time Invested",
                value=f"⏱️ Total Meeting Hours: {meeting_hours:.1f}\n"
                    f"⌛ Average Duration: {meeting_hours / total_meetings:.1f} hours" if total_meetings > 0 else "⏱️ Total Meeting Hours: 0\n⌛ Average Duration: N/A",
                inline=True
            )
            

            host_counts = {}
            for meeting in list(self.cog.meetings["meetings"].values()) + list(self.cog.meetings["completed"].values()):
                if meeting.get("guild_id") == guild_id:
                    host = meeting["host"]
                    host_name = meeting["host_name"]
                    if host not in host_counts:
                        host_counts[host] = {"count": 0, "name": host_name}
                    host_counts[host]["count"] += 1
            

            top_hosts = sorted(host_counts.items(), key=lambda x: x[1]["count"], reverse=True)[:5]
            
            if top_hosts:
                host_text = "\n".join([f"{i+1}. {host_data['name']}: {host_data['count']} meetings" 
                                     for i, (host_id, host_data) in enumerate(top_hosts)])
                embed.add_field(
                    name="🏆 Top Meeting Hosts",
                    value=host_text,
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        async def list_completed_meetings(self, interaction):
            
            guild_completed_meetings = {}
            
            for meeting_id, meeting in self.cog.meetings["completed"].items():
                if meeting.get("guild_id") == str(interaction.guild.id):
                    guild_completed_meetings[meeting_id] = meeting
            
            if not guild_completed_meetings:
                await interaction.response.send_message("No completed meetings found.", ephemeral=True)
                return
            

            sorted_meetings = sorted(
                guild_completed_meetings.items(), 
                key=lambda x: datetime.datetime.fromisoformat(x[1]["end_time"]),
                reverse=True
            )
            
            embed = discord.Embed(
                title="✅ Completed Meetings",
                description="Here are the completed meetings in this server:",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now()
            )
            
            for meeting_id, meeting in sorted_meetings[:10]:  
                start_time = datetime.datetime.fromisoformat(meeting["start_time"])
                

                attendee_count = len(meeting["attendees"].get("attending", []))
                

                has_notes = bool(meeting.get("notes"))
                has_actions = bool(meeting.get("action_items"))
                
                status_icons = ""
                if has_notes:
                    status_icons += "📝 "
                if has_actions:
                    status_icons += "📋 "
                
                embed.add_field(
                    name=f"{meeting['title']} [{meeting_id[:8]}]",
                    value=f"📅 {start_time.strftime('%A, %B %d, %Y')}\n"
                          f"👥 {attendee_count} attended\n"
                          f"🧑‍💼 Host: {meeting['host_name']}\n"
                          f"{status_icons}",
                    inline=False
                )
            
            if len(sorted_meetings) > 10:
                embed.set_footer(text=f"Showing 10 of {len(sorted_meetings)} completed meetings")
            
            view = self.CompletedMeetingListView(self.cog, dict(sorted_meetings))
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    class MeetingListView(discord.ui.View):
        def __init__(self, cog, meetings):
            super().__init__(timeout=180)
            self.cog = cog
            self.meetings = meetings
            

            if meetings:
                options = []
                for meeting_id, meeting in meetings.items():
                    start_time = datetime.datetime.fromisoformat(meeting["start_time"])
                    options.append(
                        discord.SelectOption(
                            label=f"{meeting['title']} [{meeting_id[:8]}]",
                            value=meeting_id,
                            description=f"{start_time.strftime('%b %d, %I:%M %p')}"
                        )
                    )
                
                if options:
                    if len(options) > 25:
                        options = options[:25]  

                    self.add_item(cog.MeetingSelect(options))

        
        @discord.ui.button(label="View Selected Meeting", style=discord.ButtonStyle.primary)
        async def view_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not hasattr(self, 'selected_meeting_id'):
                await interaction.response.send_message("Please select a meeting first.", ephemeral=True)
                return
            
            meeting_id = self.selected_meeting_id
            meeting = self.meetings.get(meeting_id)
            
            if not meeting:
                await interaction.response.send_message("Meeting not found.", ephemeral=True)
                return
            
            embed = self.cog.create_meeting_embed(meeting_id, meeting)
            view = self.cog.MeetingView(self.cog, meeting_id, meeting)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        @discord.ui.button(label="Repost Selected Meeting", style=discord.ButtonStyle.success)
        async def repost_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not hasattr(self, 'selected_meeting_id'):
                await interaction.response.send_message("Please select a meeting first.", ephemeral=True)
                return
            
            meeting_id = self.selected_meeting_id
            meeting = self.meetings.get(meeting_id)
            
            if not meeting:
                await interaction.response.send_message("Meeting not found.", ephemeral=True)
                return
            

            if not self.cog.can_manage_meeting(meeting, interaction.user):
                await interaction.response.send_message("Only the meeting host or administrators can repost this meeting.", ephemeral=True)
                return
            
            embed = self.cog.create_meeting_embed(meeting_id, meeting)
            view = self.cog.MeetingView(self.cog, meeting_id, meeting)
            
            await interaction.response.send_message("Reposting meeting...", ephemeral=True)
            await interaction.channel.send(embed=embed, view=view)
    
    class CompletedMeetingListView(discord.ui.View):
        def __init__(self, cog, meetings):
            super().__init__(timeout=180)
            self.cog = cog
            self.meetings = meetings
            

            if meetings:
                options = []
                for meeting_id, meeting in meetings.items():
                    start_time = datetime.datetime.fromisoformat(meeting["start_time"])
                    options.append(
                        discord.SelectOption(
                            label=f"{meeting['title']} [{meeting_id[:8]}]",
                            value=meeting_id,
                            description=f"{start_time.strftime('%b %d, %I:%M %p')}"
                        )
                    )
                
                if options:
                    if len(options) > 25:
                        options = options[:25]  
                    self.add_item(self.MeetingSelect(options))
        
        @discord.ui.button(label="View Selected Meeting", style=discord.ButtonStyle.primary)
        async def view_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not hasattr(self, 'selected_meeting_id'):
                await interaction.response.send_message("Please select a meeting first.", ephemeral=True)
                return
            
            meeting_id = self.selected_meeting_id
            meeting = self.meetings.get(meeting_id)
            
            if not meeting:
                await interaction.response.send_message("Meeting not found.", ephemeral=True)
                return
            
            embed = self.cog.create_meeting_embed(meeting_id, meeting)
            

            if meeting.get("notes"):
                embed.add_field(
                    name="📝 Full Meeting Notes",
                    value=meeting["notes"][:1024],  
                    inline=False
                )
                

                if len(meeting["notes"]) > 1024:
                    remaining_notes = meeting["notes"][1024:]
                    chunks = [remaining_notes[i:i+1024] for i in range(0, len(remaining_notes), 1024)]
                    for i, chunk in enumerate(chunks):
                        embed.add_field(
                            name=f"📝 Notes (continued {i+1})",
                            value=chunk,
                            inline=False
                        )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        @discord.ui.button(label="Generate Summary", style=discord.ButtonStyle.success, emoji="📊")
        async def summary_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not hasattr(self, 'selected_meeting_id'):
                await interaction.response.send_message("Please select a meeting first.", ephemeral=True)
                return
            
            meeting_id = self.selected_meeting_id
            meeting = self.meetings.get(meeting_id)
            
            if not meeting:
                await interaction.response.send_message("Meeting not found.", ephemeral=True)
                return
            

            if str(interaction.user.id) != meeting["host"] and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("Only the meeting host or administrators can generate the summary.", ephemeral=True)
                return
            

            summary_view = self.cog.MeetingSummaryView(self.cog, meeting_id, meeting)
            await summary_view.generate_and_send_summary(interaction)
    
    class MeetingSelect(discord.ui.Select):
        def __init__(self, options):
            super().__init__(
                placeholder="Select a meeting...",
                min_values=1,
                max_values=1,
                options=options
            )
        
        async def callback(self, interaction: discord.Interaction):
            self.view.selected_meeting_id = self.values[0]
            await interaction.response.send_message(f"Meeting selected. You can now view or repost it using the buttons below.", ephemeral=True)
    
    @app_commands.command(name="meetings", description="Open the meeting scheduler")
    async def meetings_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📅 Meeting Scheduler",
            description="Schedule and manage meetings with the buttons below.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Meeting Scheduler by TheZ")
        view = self.MeetingManagerView(self)
        await interaction.response.send_message(embed=embed, view=view)
    
    @app_commands.command(name="schedule-meeting", description="Schedule a new meeting")
    async def schedule_meeting_command(self, interaction: discord.Interaction):
        if not self.can_host_meetings(interaction.guild.id, interaction.user):
            await interaction.response.send_message("You don't have permission to host meetings. Contact an administrator or get the required role.", ephemeral=True)
            return
        
        await interaction.response.send_modal(
            self.CreateMeetingModal(
                self, 
                interaction.channel.id, 
                interaction.guild.id
            )
        )
    
    @app_commands.command(name="list-meetings", description="List all upcoming meetings")
    async def list_meetings_command(self, interaction: discord.Interaction):
        guild_meetings = {}
        now = datetime.datetime.now(datetime.timezone.utc)
        
        for meeting_id, meeting in self.meetings["meetings"].items():
            if meeting.get("guild_id") == str(interaction.guild.id) and meeting["status"] != "cancelled":
                start_time = datetime.datetime.fromisoformat(meeting["start_time"])
                if start_time > now:  
                    guild_meetings[meeting_id] = meeting
        
        if not guild_meetings:
            await interaction.response.send_message("No upcoming meetings found.", ephemeral=True)
            return
        

        sorted_meetings = sorted(
            guild_meetings.items(), 
            key=lambda x: datetime.datetime.fromisoformat(x[1]["start_time"])
        )
        
        embed = discord.Embed(
            title="📋 Upcoming Meetings",
            description="Here are the upcoming meetings in this server:",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        for meeting_id, meeting in sorted_meetings[:10]:  
            start_time = datetime.datetime.fromisoformat(meeting["start_time"])
            time_until = start_time - now
            days_until = time_until.days
            hours_until = time_until.seconds // 3600
            
            if days_until > 0:
                time_str = f"in {days_until} day{'s' if days_until > 1 else ''}"
            else:
                time_str = f"in {hours_until} hour{'s' if hours_until > 1 else ''}"
            

            attendee_count = len(meeting["attendees"].get("attending", []))
            
            embed.add_field(
                name=f"{meeting['title']} [{meeting_id[:8]}]",
                value=f"📅 {start_time.strftime('%A, %B %d at %I:%M %p')}\n"
                      f"⏰ {time_str}\n"
                      f"👥 {attendee_count} attending\n"
                      f"🧑‍💼 Host: {meeting['host_name']}",
                inline=False
            )
        
        if len(sorted_meetings) > 10:
            embed.set_footer(text=f"Showing 10 of {len(sorted_meetings)} upcoming meetings")
        
        view = self.MeetingListView(self, dict(sorted_meetings))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="my-meetings", description="List meetings you're hosting or attending")
    async def my_meetings_command(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        my_meetings = {}
        now = datetime.datetime.now(datetime.timezone.utc)
        
        for meeting_id, meeting in self.meetings["meetings"].items():
            if meeting.get("guild_id") == str(interaction.guild.id) and meeting["status"] != "cancelled":

                if meeting["host"] == user_id or user_id in meeting["attendees"].get("attending", []):
                    start_time = datetime.datetime.fromisoformat(meeting["start_time"])
                    if start_time > now:  
                        my_meetings[meeting_id] = meeting
        
        if not my_meetings:
            await interaction.response.send_message("You don't have any upcoming meetings.", ephemeral=True)
            return
        

        sorted_meetings = sorted(
            my_meetings.items(), 
            key=lambda x: datetime.datetime.fromisoformat(x[1]["start_time"])
        )
        
        embed = discord.Embed(
            title="📋 My Meetings",
            description="Here are your upcoming meetings:",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        hosting = []
        attending = []
        
        for meeting_id, meeting in sorted_meetings:
            start_time = datetime.datetime.fromisoformat(meeting["start_time"])
            time_str = start_time.strftime("%A, %B %d at %I:%M %p")
            
            meeting_str = f"**{meeting['title']}** [{meeting_id[:8]}]\n📅 {time_str}"
            
            if meeting["host"] == user_id:
                hosting.append(meeting_str)
            else:
                attending.append(meeting_str)
        
        if hosting:
            embed.add_field(
                name="🧑‍💼 Meetings You're Hosting",
                value="\n\n".join(hosting[:5]) + (f"\n\n*...and {len(hosting) - 5} more*" if len(hosting) > 5 else ""),
                inline=False
            )
        
        if attending:
            embed.add_field(
                name="👤 Meetings You're Attending",
                value="\n\n".join(attending[:5]) + (f"\n\n*...and {len(attending) - 5} more*" if len(attending) > 5 else ""),
                inline=False
            )
        
        view = self.MeetingListView(self, dict(sorted_meetings))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="meeting-info", description="Show details about a meeting")
    @app_commands.describe(meeting_id="The ID of the meeting to view")
    async def meeting_info_command(self, interaction: discord.Interaction, meeting_id: str):

        full_meeting_id = None
        meeting = None
        

        if len(meeting_id) < 36:  
            for mid, mtg in self.meetings["meetings"].items():
                if mid.startswith(meeting_id):
                    full_meeting_id = mid
                    meeting = mtg
                    break
            
            if not meeting:
                for mid, mtg in self.meetings["completed"].items():
                    if mid.startswith(meeting_id):
                        full_meeting_id = mid
                        meeting = mtg
                        break
        else:

            meeting = self.meetings["meetings"].get(meeting_id)
            if meeting:
                full_meeting_id = meeting_id
            else:
                meeting = self.meetings["completed"].get(meeting_id)
                if meeting:
                    full_meeting_id = meeting_id
        
        if not meeting:
            await interaction.response.send_message(f"Meeting with ID {meeting_id} not found.", ephemeral=True)
            return
        
        embed = self.create_meeting_embed(full_meeting_id, meeting)
        

        if meeting["status"] not in ["completed", "cancelled"] and full_meeting_id in self.meetings["meetings"]:
            view = self.MeetingView(self, full_meeting_id, meeting)
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="cancel-meeting", description="Cancel a meeting you're hosting")
    @app_commands.describe(meeting_id="The ID of the meeting to cancel")
    async def cancel_meeting_command(self, interaction: discord.Interaction, meeting_id: str):

        full_meeting_id = None
        meeting = None
        

        if len(meeting_id) < 36:  
            for mid, mtg in self.meetings["meetings"].items():
                if mid.startswith(meeting_id):
                    full_meeting_id = mid
                    meeting = mtg
                    break
        else:

            meeting = self.meetings["meetings"].get(meeting_id)
            if meeting:
                full_meeting_id = meeting_id
        
        if not meeting:
            await interaction.response.send_message(f"Meeting with ID {meeting_id} not found.", ephemeral=True)
            return
        

        if not self.can_manage_meeting(meeting, interaction.user):
            await interaction.response.send_message("Only the meeting host or administrators can cancel this meeting.", ephemeral=True)
            return
    
        

        confirm_view = self.ConfirmView()
        await interaction.response.send_message(f"Are you sure you want to cancel the meeting **{meeting['title']}**?", view=confirm_view, ephemeral=True)
        

        await confirm_view.wait()
        if confirm_view.value:
            meeting["status"] = "cancelled"
            self.save_meetings()
            

            try:
                channel = interaction.guild.get_channel(int(meeting["channel_id"]))
                if channel:
                    async for message in channel.history(limit=50):
                        if message.author.id == interaction.client.user.id and message.embeds:
                            for embed in message.embeds:
                                if embed.title and meeting["title"] in embed.title and full_meeting_id[:8] in str(embed.fields[0].value):
                                    new_embed = self.create_meeting_embed(full_meeting_id, meeting)
                                    await message.edit(embed=new_embed, view=self.MeetingView(self, full_meeting_id, meeting))
                                    break
            except:
                pass  
            

            cancellation_embed = discord.Embed(
                title=f"❌ Meeting Cancelled: {meeting['title']}",
                description=f"This meeting has been cancelled by {interaction.user.display_name}.",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now()
            )
            

            start_time = datetime.datetime.fromisoformat(meeting["start_time"])
            cancellation_embed.add_field(name="Was scheduled for", value=start_time.strftime("%A, %B %d, %Y at %I:%M %p"), inline=False)
            
            await interaction.edit_original_response(content="Meeting has been cancelled.", embed=cancellation_embed, view=None)
            

            for user_id in meeting["attendees"].get("attending", []):
                try:
                    member = interaction.guild.get_member(int(user_id))
                    if member and member.id != interaction.user.id:  
                        await member.send(f"A meeting you were planning to attend has been cancelled:", embed=cancellation_embed)
                except:
                    pass  
        else:
            await interaction.edit_original_response(content="Meeting cancellation aborted.", view=None)
    
    @app_commands.command(name="meeting-statistics", description="Show meeting statistics for this server")
    async def meeting_statistics_command(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        

        total_meetings = 0
        completed_meetings = 0
        cancelled_meetings = 0
        upcoming_meetings = 0
        total_attendance = 0
        meeting_hours = 0
        

        now = datetime.datetime.now(datetime.timezone.utc)
        for meeting in self.meetings["meetings"].values():
            if meeting.get("guild_id") == guild_id:
                total_meetings += 1
                start_time = datetime.datetime.fromisoformat(meeting["start_time"])
                
                if meeting["status"] == "cancelled":
                    cancelled_meetings += 1
                elif start_time > now:
                    upcoming_meetings += 1
                

                if meeting["status"] != "cancelled":
                    start = datetime.datetime.fromisoformat(meeting["start_time"])
                    end = datetime.datetime.fromisoformat(meeting["end_time"])
                    duration = (end - start).total_seconds() / 3600  
                    meeting_hours += duration
                

                total_attendance += len(meeting["attendees"].get("attending", []))
        

        for meeting in self.meetings["completed"].values():
            if meeting.get("guild_id") == guild_id:
                total_meetings += 1
                completed_meetings += 1
                

                start = datetime.datetime.fromisoformat(meeting["start_time"])
                end = datetime.datetime.fromisoformat(meeting["end_time"])
                duration = (end - start).total_seconds() / 3600  
                meeting_hours += duration
                

                total_attendance += len(meeting["attendees"].get("attending", []))
        

        embed = discord.Embed(
            title="📊 Meeting Statistics",
            description=f"Meeting statistics for {interaction.guild.name}",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(
            name="Meeting Counts",
            value=f"📅 Total Meetings: {total_meetings}\n"
                  f"✅ Completed: {completed_meetings}\n"
                  f"⏳ Upcoming: {upcoming_meetings}\n"
                  f"❌ Cancelled: {cancelled_meetings}",
            inline=True
        )
        
        avg_attendance = total_attendance / total_meetings if total_meetings > 0 else 0
        embed.add_field(
            name="Attendance",
            value=f"👥 Total Attendees: {total_attendance}\n"
                  f"📊 Average Per Meeting: {avg_attendance:.1f}",
            inline=True
        )
        
        embed.add_field(
            name="Time Invested",
            value=f"⏱️ Total Meeting Hours: {meeting_hours:.1f}\n"
                f"⌛ Average Duration: {meeting_hours / total_meetings:.1f} hours" if total_meetings > 0 else "⏱️ Total Meeting Hours: 0\n⌛ Average Duration: N/A",
            inline=True
        )
        

        host_counts = {}
        for meeting in list(self.meetings["meetings"].values()) + list(self.meetings["completed"].values()):
            if meeting.get("guild_id") == guild_id:
                host = meeting["host"]
                host_name = meeting["host_name"]
                if host not in host_counts:
                    host_counts[host] = {"count": 0, "name": host_name}
                host_counts[host]["count"] += 1
        

        top_hosts = sorted(host_counts.items(), key=lambda x: x[1]["count"], reverse=True)[:5]
        
        if top_hosts:
            host_text = "\n".join([f"{i+1}. {host_data['name']}: {host_data['count']} meetings" 
                                 for i, (host_id, host_data) in enumerate(top_hosts)])
            embed.add_field(
                name="🏆 Top Meeting Hosts",
                value=host_text,
                inline=False
            )
        
        embed.set_footer(text="Meeting Scheduler by TheZ")
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="upcoming-meetings", description="Show meetings scheduled for the next few days")
    @app_commands.describe(days="Number of days to look ahead (default: 7)")
    async def upcoming_meetings_command(self, interaction: discord.Interaction, days: int = 7):
        if days <= 0 or days > 30:
            await interaction.response.send_message("Please specify a number of days between 1 and 30.", ephemeral=True)
            return
        
        guild_id = str(interaction.guild.id)
        now = datetime.datetime.now(datetime.timezone.utc)
        end_date = now + datetime.timedelta(days=days)
        
        upcoming_meetings = {}
        for meeting_id, meeting in self.meetings["meetings"].items():
            if meeting.get("guild_id") == guild_id and meeting["status"] != "cancelled":
                start_time = datetime.datetime.fromisoformat(meeting["start_time"])
                if now <= start_time <= end_date:
                    upcoming_meetings[meeting_id] = meeting
        
        if not upcoming_meetings:
            await interaction.response.send_message(f"No meetings scheduled in the next {days} days.", ephemeral=True)
            return
        

        sorted_meetings = sorted(
            upcoming_meetings.items(), 
            key=lambda x: datetime.datetime.fromisoformat(x[1]["start_time"])
        )
        
        embed = discord.Embed(
            title=f"📅 Upcoming Meetings (Next {days} Days)",
            description=f"Here are the meetings scheduled in the next {days} days:",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        

        meetings_by_day = {}
        for meeting_id, meeting in sorted_meetings:
            start_time = datetime.datetime.fromisoformat(meeting["start_time"])
            day_str = start_time.strftime("%A, %B %d")
            
            if day_str not in meetings_by_day:
                meetings_by_day[day_str] = []
            
            meetings_by_day[day_str].append((meeting_id, meeting))
        

        for day, day_meetings in meetings_by_day.items():
            day_text = []
            for meeting_id, meeting in day_meetings:
                start_time = datetime.datetime.fromisoformat(meeting["start_time"])
                time_str = start_time.strftime("%I:%M %p")
                
                attendee_count = len(meeting["attendees"].get("attending", []))
                
                day_text.append(f"**{meeting['title']}** [{meeting_id[:8]}]\n"
                               f"⏰ {time_str} • 👥 {attendee_count} attending\n"
                               f"🧑‍💼 Host: {meeting['host_name']}")
            
            embed.add_field(
                name=f"📆 {day}",
                value="\n\n".join(day_text),
                inline=False
            )
        
        view = self.MeetingListView(self, dict(sorted_meetings))
        await interaction.response.send_message(embed=embed, view=view)
    
    @app_commands.command(name="rsvp", description="RSVP to a meeting")
    @app_commands.describe(
        meeting_id="The ID of the meeting",
        status="Your RSVP status"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="Attending", value="attending"),
        app_commands.Choice(name="Maybe", value="maybe"),
        app_commands.Choice(name="Declined", value="declined")
    ])
    async def rsvp_command(self, interaction: discord.Interaction, meeting_id: str, status: str):


        full_meeting_id = None
        meeting = None
        

        if len(meeting_id) < 36:  
            for mid, mtg in self.meetings["meetings"].items():
                if mid.startswith(meeting_id):
                    full_meeting_id = mid
                    meeting = mtg
                    break
        else:

            meeting = self.meetings["meetings"].get(meeting_id)
            if meeting:
                full_meeting_id = meeting_id
        
        if not meeting:
            await interaction.response.send_message(f"Meeting with ID {meeting_id} not found.", ephemeral=True)
            return
        

        start_time = datetime.datetime.fromisoformat(meeting["start_time"])
        now = datetime.datetime.now(datetime.timezone.utc)
        
        if start_time < now:
            await interaction.response.send_message("This meeting has already started or ended.", ephemeral=True)
            return
        

        user_id = str(interaction.user.id)
        

        for s in ["attending", "maybe", "declined"]:
            if user_id in meeting["attendees"].get(s, []):
                meeting["attendees"][s].remove(user_id)
        

        if status not in meeting["attendees"]:
            meeting["attendees"][status] = []
        
        meeting["attendees"][status].append(user_id)
        self.save_meetings()
        

        try:
            channel = interaction.guild.get_channel(int(meeting["channel_id"]))
            if channel:
                async for message in channel.history(limit=50):
                    if message.author.id == interaction.client.user.id and message.embeds:
                        for embed in message.embeds:
                            if embed.title and meeting["title"] in embed.title and full_meeting_id[:8] in str(embed.fields[0].value):
                                new_embed = self.create_meeting_embed(full_meeting_id, meeting)
                                await message.edit(embed=new_embed)
                                break
        except:
            pass  
        
        status_text = "attending" if status == "attending" else "maybe attending" if status == "maybe" else "declined"
        await interaction.response.send_message(f"You are now {status_text} the meeting **{meeting['title']}**.", ephemeral=True)
    
    @app_commands.command(name="add-agenda-item", description="Add an agenda item to a meeting")
    @app_commands.describe(
        meeting_id="The ID of the meeting",
        item="The agenda item to add"
    )
    async def add_agenda_item_command(self, interaction: discord.Interaction, meeting_id: str, item: str):

        full_meeting_id = None
        meeting = None
        

        if len(meeting_id) < 36:  
            for mid, mtg in self.meetings["meetings"].items():
                if mid.startswith(meeting_id):
                    full_meeting_id = mid
                    meeting = mtg
                    break
        else:

            meeting = self.meetings["meetings"].get(meeting_id)
            if meeting:
                full_meeting_id = meeting_id
        
        if not meeting:
            await interaction.response.send_message(f"Meeting with ID {meeting_id} not found.", ephemeral=True)
            return
        

        user_id = str(interaction.user.id)
        if not self.can_manage_meeting(meeting, interaction.user) and str(interaction.user.id) not in meeting["attendees"].get("attending", []):
            await interaction.response.send_message("Only the meeting host, administrators, or attendees can add agenda items.", ephemeral=True)
            return
        

        if "agenda_items" not in meeting:
            meeting["agenda_items"] = []
        
        meeting["agenda_items"].append(item)
        meeting["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        meeting["updated_by"] = str(interaction.user.id)
        meeting["updated_by_name"] = interaction.user.display_name
        
        self.save_meetings()
        

        try:
            channel = interaction.guild.get_channel(int(meeting["channel_id"]))
            if channel:
                async for message in channel.history(limit=50):
                    if message.author.id == interaction.client.user.id and message.embeds:
                        for embed in message.embeds:
                            if embed.title and meeting["title"] in embed.title and full_meeting_id[:8] in str(embed.fields[0].value):
                                new_embed = self.create_meeting_embed(full_meeting_id, meeting)
                                await message.edit(embed=new_embed)
                                break
        except:
            pass  
        
        await interaction.response.send_message(f"Agenda item added to meeting **{meeting['title']}**.", ephemeral=True)
    
    @app_commands.command(name="completed-meetings", description="List completed meetings")
    async def completed_meetings_command(self, interaction: discord.Interaction):
        guild_completed_meetings = {}
        
        for meeting_id, meeting in self.meetings["completed"].items():
            if meeting.get("guild_id") == str(interaction.guild.id):
                guild_completed_meetings[meeting_id] = meeting
        
        if not guild_completed_meetings:
            await interaction.response.send_message("No completed meetings found.", ephemeral=True)
            return
        

        sorted_meetings = sorted(
            guild_completed_meetings.items(), 
            key=lambda x: datetime.datetime.fromisoformat(x[1]["end_time"]),
            reverse=True
        )
        
        embed = discord.Embed(
            title="✅ Completed Meetings",
            description="Here are the completed meetings in this server:",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        
        for meeting_id, meeting in sorted_meetings[:10]:  
            start_time = datetime.datetime.fromisoformat(meeting["start_time"])
            

            attendee_count = len(meeting["attendees"].get("attending", []))
            

            has_notes = bool(meeting.get("notes"))
            has_actions = bool(meeting.get("action_items"))
            
            status_icons = ""
            if has_notes:
                status_icons += "📝 "
            if has_actions:
                status_icons += "📋 "
            
            embed.add_field(
                name=f"{meeting['title']} [{meeting_id[:8]}]",
                value=f"📅 {start_time.strftime('%A, %B %d, %Y')}\n"
                      f"👥 {attendee_count} attended\n"
                      f"🧑‍💼 Host: {meeting['host_name']}\n"
                      f"{status_icons}",
                inline=False
            )
        
        if len(sorted_meetings) > 10:
            embed.set_footer(text=f"Showing 10 of {len(sorted_meetings)} completed meetings")
        
        view = self.CompletedMeetingListView(self, dict(sorted_meetings))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    def create_meeting_embed(self, meeting_id, meeting):
        

        if meeting["status"] == "cancelled":
            color = discord.Color.red()
        elif meeting["status"] == "completed":
            color = discord.Color.green()
        else:

            now = datetime.datetime.now(datetime.timezone.utc)
            start_time = datetime.datetime.fromisoformat(meeting["start_time"])
            end_time = datetime.datetime.fromisoformat(meeting["end_time"])
            
            if start_time <= now <= end_time:
                color = discord.Color.gold()  
            else:
                color = discord.Color.blue()  
        

        start_time = datetime.datetime.fromisoformat(meeting["start_time"])
        end_time = datetime.datetime.fromisoformat(meeting["end_time"])
        

        start_str = start_time.strftime("%A, %B %d, %Y at %I:%M %p")
        end_str = end_time.strftime("%I:%M %p")
        

        if hasattr(start_time, 'tzinfo') and start_time.tzinfo:
            tz_name = start_time.tzname() or "UTC"
            start_str += f" {tz_name}"
            end_str += f" {tz_name}"
        

        status_text = meeting["status"].capitalize()
        if meeting["status"] == "scheduled":

            now = datetime.datetime.now(datetime.timezone.utc)
            if start_time <= now <= end_time:
                status_text = "In Progress"
        

        if meeting["status"] == "cancelled":
            title = f"❌ CANCELLED: {meeting['title']}"
        elif meeting["status"] == "completed":
            title = f"✅ {meeting['title']} (Completed)"
        elif start_time <= now <= end_time:
            title = f"🔴 LIVE: {meeting['title']}"
        else:
            title = f"📅 {meeting['title']}"
        
        embed = discord.Embed(
            title=title,
            description=meeting["description"],
            color=color,
            timestamp=datetime.datetime.now()
        )
        

        embed.add_field(name="ID", value=meeting_id[:8], inline=True)
        embed.add_field(name="Status", value=status_text, inline=True)
        embed.add_field(name="Host", value=meeting["host_name"], inline=True)
        

        time_value = f"**Start:** {start_str}\n**End:** {end_str}"
        

        if meeting["status"] == "scheduled" and start_time > now:
            time_until = start_time - now
            days = time_until.days
            hours, remainder = divmod(time_until.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            if days > 0:
                countdown = f"{days} day{'s' if days != 1 else ''}, {hours} hour{'s' if hours != 1 else ''}"
            elif hours > 0:
                countdown = f"{hours} hour{'s' if hours != 1 else ''}, {minutes} minute{'s' if minutes != 1 else ''}"
            else:
                countdown = f"{minutes} minute{'s' if minutes != 1 else ''}"
            
            time_value += f"\n**Starts in:** {countdown}"
        
        embed.add_field(name="Time", value=time_value, inline=False)
        

        if meeting.get("location"):
            embed.add_field(name="Location", value=meeting["location"], inline=False)
        elif meeting.get("virtual_link"):
            embed.add_field(name="Meeting Link", value=meeting["virtual_link"], inline=False)
        

        if meeting.get("recurring"):
            recurring_type = meeting.get("recurring_type", "weekly")
            recurring_text = f"This is a {recurring_type} recurring meeting"
            embed.add_field(name="Recurring", value=recurring_text, inline=False)
        

        attending = meeting["attendees"].get("attending", [])
        maybe = meeting["attendees"].get("maybe", [])
        declined = meeting["attendees"].get("declined", [])
        
        if attending:
            attendee_text = f"**Going ({len(attending)}):** " + ", ".join([f"<@{uid}>" for uid in attending[:5]])
            if len(attending) > 5:
                attendee_text += f" and {len(attending) - 5} more"
            embed.add_field(name="Attendees", value=attendee_text, inline=False)
        
        if maybe:
            maybe_text = f"**Maybe ({len(maybe)}):** " + ", ".join([f"<@{uid}>" for uid in maybe[:5]])
            if len(maybe) > 5:
                maybe_text += f" and {len(maybe) - 5} more"
            embed.add_field(name="Maybe Attending", value=maybe_text, inline=False)
        

        if meeting.get("agenda_items"):
            agenda_items = meeting["agenda_items"]
            agenda_text = "\n".join([f"• {item}" for item in agenda_items[:5]])
            if len(agenda_items) > 5:
                agenda_text += f"\n• ... and {len(agenda_items) - 5} more items"
            embed.add_field(name="📝 Agenda", value=agenda_text, inline=False)
        

        if meeting["status"] == "completed":
            if meeting.get("notes"):
                notes_preview = meeting["notes"][:200] + "..." if len(meeting["notes"]) > 200 else meeting["notes"]
                embed.add_field(name="📝 Meeting Notes", value=notes_preview, inline=False)
            
            if meeting.get("action_items"):
                action_items = meeting["action_items"]
                action_text = "\n".join([f"• {item}" for item in action_items[:3]])
                if len(action_items) > 3:
                    action_text += f"\n• ... and {len(action_items) - 3} more items"
                embed.add_field(name="📋 Action Items", value=action_text, inline=False)
        

        created_at = datetime.datetime.fromisoformat(meeting["created_at"])
        embed.set_footer(text=f"Created by {meeting['host_name']} • {created_at.strftime('%B %d, %Y')} | Meeting Scheduler by TheZ")
        
        return embed

def setup(bot):
    cog = MeetingScheduler(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog







