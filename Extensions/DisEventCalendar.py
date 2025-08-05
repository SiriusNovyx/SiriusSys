import discord
from discord import app_commands
from discord.ext import commands, tasks
import datetime
import pytz
import json
import os
import asyncio
from typing import Optional, List, Dict, Union, Literal
import uuid
from dateutil.rrule import rrulestr
from dateutil import rrule
import re

class DisEventCalendar(commands.Cog):
    """
    DisEventCalendar - Advanced Event Management System
    Created by TheHolyOneZ
    
    Features:
    - Schedule one-time and recurring events
    - Timezone conversion for international communities
    - Event reminders and notifications
    - User-friendly UI with buttons and select menus
    - Comprehensive permission handling
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.events_file = "data/events.json"
        self.events = {}
        self.reminders = {}
        self.load_events()
        self.check_events.start()
        
    def cog_unload(self):
        self.check_events.cancel()
    
    def load_events(self):
        
        if not os.path.exists("data"):
            os.makedirs("data")
            
        if os.path.exists(self.events_file):
            try:
                with open(self.events_file, 'r') as f:
                    self.events = json.load(f)
                    

                for guild_id, guild_events in self.events.items():
                    for event_id, event in guild_events.items():
                        if event['type'] == 'one-time':
                            event['datetime'] = datetime.datetime.fromisoformat(event['datetime'])
                        elif event['type'] == 'recurring':

                            pass
                        

                        self._schedule_reminders(guild_id, event_id)
            except Exception as e:
                print(f"Error loading events: {e}")
                self.events = {}
    
    def save_events(self):
        
        events_to_save = {}
        

        for guild_id, guild_events in self.events.items():
            events_to_save[guild_id] = {}
            for event_id, event in guild_events.items():
                events_to_save[guild_id][event_id] = event.copy()
                if event['type'] == 'one-time':
                    events_to_save[guild_id][event_id]['datetime'] = event['datetime'].isoformat()
        
        with open(self.events_file, 'w') as f:
            json.dump(events_to_save, f, indent=4)
    
    def _schedule_reminders(self, guild_id, event_id):
        
        if guild_id not in self.events:
            return
            
        if event_id not in self.events[guild_id]:
            return
            
        event = self.events[guild_id][event_id]
        

        if event_id in self.reminders:
            for task in self.reminders[event_id]:
                task.cancel()
            
        self.reminders[event_id] = []
        

        next_time = self._get_next_occurrence(event)
        if not next_time:
            return
            

        for reminder_time in event['reminders']:
            reminder_datetime = next_time - datetime.timedelta(minutes=reminder_time)
            now = datetime.datetime.now(pytz.UTC)
            
            if reminder_datetime > now:
                seconds_until_reminder = (reminder_datetime - now).total_seconds()
                task = asyncio.create_task(self._send_reminder(
                    guild_id, 
                    event_id, 
                    reminder_time, 
                    seconds_until_reminder
                ))
                self.reminders[event_id].append(task)
    
    async def _send_reminder(self, guild_id, event_id, reminder_minutes, delay):
        
        await asyncio.sleep(delay)
        

        if guild_id not in self.events or event_id not in self.events[guild_id]:
            return
            
        event = self.events[guild_id][event_id]
        guild = self.bot.get_guild(int(guild_id))
        
        if not guild:
            return
            
        channel = guild.get_channel(event['channel_id'])
        if not channel:
            return
            

        embed = discord.Embed(
            title=f"Event Reminder: {event['title']}",
            description=f"Event starts in {reminder_minutes} minutes!",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Description", value=event['description'])
        
        if event['type'] == 'one-time':
            event_time = event['datetime']
        else:
            event_time = self._get_next_occurrence(event)
            
        if event_time:
            embed.add_field(
                name="Time", 
                value=f"<t:{int(event_time.timestamp())}:F> (<t:{int(event_time.timestamp())}:R>)"
            )
            

        if 'location' in event and event['location']:
            embed.add_field(name="Location", value=event['location'])
            

        mentions = []
        if 'mention_roles' in event and event['mention_roles']:
            for role_id in event['mention_roles']:
                mentions.append(f"<@&{role_id}>")
                

        if 'mention_users' in event and event['mention_users']:
            for user_id in event['mention_users']:
                mentions.append(f"<@{user_id}>")
                
        mention_text = " ".join(mentions) if mentions else ""
        

        await channel.send(content=mention_text, embed=embed)
    
    def _get_next_occurrence(self, event):
        
        if event['type'] == 'one-time':
            return event['datetime']
        elif event['type'] == 'recurring':
            now = datetime.datetime.now(pytz.UTC)
            

            rule = rrulestr(event['rrule'], dtstart=datetime.datetime.fromisoformat(event['start_date']))
            

            next_occurrences = list(rule.after(now, inc=False))
            
            if next_occurrences:
                return next_occurrences[0]
                
        return None
    
    @tasks.loop(minutes=1)
    async def check_events(self):
        
        now = datetime.datetime.now(pytz.UTC)
        
        for guild_id, guild_events in self.events.items():
            for event_id, event in list(guild_events.items()):

                next_time = self._get_next_occurrence(event)
                
                if not next_time:
                    continue
                    

                time_diff = (next_time - now).total_seconds()
                if 0 <= time_diff <= 60:

                    await self._send_event_notification(guild_id, event_id)
                    

                    if event['type'] == 'one-time':
                        del self.events[guild_id][event_id]
                        self.save_events()
                    else:

                        self._schedule_reminders(guild_id, event_id)
    
    @check_events.before_loop
    async def before_check_events(self):
        await self.bot.wait_until_ready()
    
    async def _send_event_notification(self, guild_id, event_id):
        
        if guild_id not in self.events or event_id not in self.events[guild_id]:
            return
            
        event = self.events[guild_id][event_id]
        guild = self.bot.get_guild(int(guild_id))
        
        if not guild:
            return
            
        channel = guild.get_channel(event['channel_id'])
        if not channel:
            return
            

        embed = discord.Embed(
            title=f"Event Starting: {event['title']}",
            description="This event is starting now!",
            color=discord.Color.green()
        )
        
        embed.add_field(name="Description", value=event['description'])
            

        if 'location' in event and event['location']:
            embed.add_field(name="Location", value=event['location'])
            

        mentions = []
        if 'mention_roles' in event and event['mention_roles']:
            for role_id in event['mention_roles']:
                mentions.append(f"<@&{role_id}>")
                

        if 'mention_users' in event and event['mention_users']:
            for user_id in event['mention_users']:
                mentions.append(f"<@{user_id}>")
                
        mention_text = " ".join(mentions) if mentions else ""
        

        await channel.send(content=mention_text, embed=embed)
    

    def _check_permissions(self, ctx_or_interaction):
        
        if isinstance(ctx_or_interaction, discord.Interaction):
            guild = ctx_or_interaction.guild
            user = ctx_or_interaction.user
        else:  # Context
            guild = ctx_or_interaction.guild
            user = ctx_or_interaction.author
            
        if not guild:
            return False
            
        if user.guild_permissions.administrator:
            return True
            
        if user.guild_permissions.manage_events:
            return True
            

        for role in user.roles:
            if role.name.lower() in ["event manager", "event admin"]:
                return True
                
        return False
    

    class EventCreationView(discord.ui.View):
        def __init__(self, cog, ctx_or_interaction, timeout=300):
            super().__init__(timeout=timeout)
            self.cog = cog
            

            if isinstance(ctx_or_interaction, discord.Interaction):
                self.ctx = None
                self.interaction = ctx_or_interaction
                self.author = ctx_or_interaction.user
                self.channel = ctx_or_interaction.channel
                self.guild = ctx_or_interaction.guild
            else:
                self.ctx = ctx_or_interaction
                self.interaction = None
                self.author = ctx_or_interaction.author
                self.channel = ctx_or_interaction.channel
                self.guild = ctx_or_interaction.guild
                
            self.message = None
            self.event_data = {
                "title": None,
                "description": None,
                "type": "one-time",
                "datetime": None,
                "timezone": "UTC",
                "channel_id": self.channel.id,
                "reminders": [10, 60],  # Default reminders: 10 minutes and 1 hour
                "mention_roles": [],
                "mention_users": [],
                "location": None,
                "created_by": self.author.id
            }
            
        @discord.ui.button(label="Set Title", style=discord.ButtonStyle.primary, custom_id="set_title")
        async def set_title_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.author.id:
                await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
                return
                
            await interaction.response.send_modal(self.TitleModal(self))
        
        @discord.ui.button(label="Set Description", style=discord.ButtonStyle.primary, custom_id="set_description")
        async def set_description_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.author.id:
                await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
                return
                
            await interaction.response.send_modal(self.DescriptionModal(self))
        
        @discord.ui.button(label="Set Date/Time", style=discord.ButtonStyle.primary, custom_id="set_datetime")
        async def set_datetime_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.author.id:
                await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
                return
                
            if self.event_data["type"] == "one-time":
                await interaction.response.send_modal(self.DateTimeModal(self))
            else:
                await interaction.response.send_message(
                    "For recurring events, please use the 'Set Recurrence' button.", 
                    ephemeral=True
                )
        
        @discord.ui.select(
            placeholder="Select Event Type",
            options=[
                discord.SelectOption(label="One-time Event", value="one-time", description="A single event that occurs once"),
                discord.SelectOption(label="Recurring Event", value="recurring", description="An event that repeats on a schedule")
            ],
            custom_id="event_type_select"
        )
        async def event_type_select(self, interaction: discord.Interaction, select: discord.ui.Select):
            if interaction.user.id != self.author.id:
                await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
                return
                
            self.event_data["type"] = select.values[0]
            

            new_view = self.__class__(self.cog, interaction if self.interaction else self.ctx)
            new_view.event_data = self.event_data.copy()
            
            if select.values[0] == "recurring":

                for item in new_view.children[:]:
                    if isinstance(item, discord.ui.Button) and item.custom_id == "set_datetime":
                        new_view.remove_item(item)
                

                recurrence_button = discord.ui.Button(
                    label="Set Recurrence", 
                    style=discord.ButtonStyle.primary,
                    custom_id="set_recurrence"
                )
                recurrence_button.callback = new_view.recurrence_button_callback
                new_view.add_item(recurrence_button)
            


            await interaction.response.edit_message(view=new_view)
            await new_view.update_preview(interaction)
        
        async def recurrence_button_callback(self, interaction: discord.Interaction):
            if interaction.user.id != self.author.id:
                await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
                return
                

            view = self.RecurrenceView(self)
            await interaction.response.send_message("Configure recurrence pattern:", view=view, ephemeral=True)
        
        @discord.ui.button(label="Set Location", style=discord.ButtonStyle.secondary, custom_id="set_location")
        async def set_location_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.author.id:
                await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
                return
                
            await interaction.response.send_modal(self.LocationModal(self))
        
        @discord.ui.button(label="Set Reminders", style=discord.ButtonStyle.secondary, custom_id="set_reminders")
        async def set_reminders_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.author.id:
                await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
                return
                
            await interaction.response.send_modal(self.RemindersModal(self))
        
        @discord.ui.button(label="Set Mentions", style=discord.ButtonStyle.secondary, custom_id="set_mentions")
        async def set_mentions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.author.id:
                await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
                return
                

            view = self.MentionsView(self)
            await interaction.response.send_message("Select roles or users to mention:", view=view, ephemeral=True)
        
        @discord.ui.button(label="Create Event", style=discord.ButtonStyle.success, row=4, custom_id="create_event")
        async def create_event_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.author.id:
                await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
                return
                

            if not self.event_data["title"]:
                await interaction.response.send_message("You must set a title for the event.", ephemeral=True)
                return
                
            if not self.event_data["description"]:
                await interaction.response.send_message("You must set a description for the event.", ephemeral=True)
                return
                
            if self.event_data["type"] == "one-time" and not self.event_data["datetime"]:
                await interaction.response.send_message("You must set a date and time for the event.", ephemeral=True)
                return
                
            if self.event_data["type"] == "recurring" and "rrule" not in self.event_data:
                await interaction.response.send_message("You must set a recurrence pattern for the event.", ephemeral=True)
                return
                

            event_id = str(uuid.uuid4())
            guild_id = str(self.guild.id)
            
            if guild_id not in self.cog.events:
                self.cog.events[guild_id] = {}
                
            self.cog.events[guild_id][event_id] = self.event_data.copy()
            

            self.cog._schedule_reminders(guild_id, event_id)
            

            self.cog.save_events()
            

            embed = discord.Embed(
                title="Event Created",
                description=f"Your event '{self.event_data['title']}' has been created!",
                color=discord.Color.green()
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            


            channel = self.guild.get_channel(self.event_data["channel_id"])
            if channel:
                announcement_embed = self.create_event_embed(is_announcement=True)
                

                mentions = []
                if self.event_data["mention_roles"]:
                    for role_id in self.event_data["mention_roles"]:
                        mentions.append(f"<@&{role_id}>")
                        
                if self.event_data["mention_users"]:
                    for user_id in self.event_data["mention_users"]:
                        mentions.append(f"<@{user_id}>")
                        
                mention_text = " ".join(mentions) if mentions else ""
                
                await channel.send(content=mention_text, embed=announcement_embed)

        
        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=4, custom_id="cancel_event")
        async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.author.id:
                await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
                return
                
            await interaction.response.edit_message(
                content="Event creation cancelled.",
                embed=None,
                view=None
            )
        
        async def update_preview(self, interaction=None):
            
            embed = self.create_event_embed()
            
            try:
                if interaction:
                    await interaction.edit_original_response(embed=embed, view=self)
                elif self.message:
                    if self.ctx:
                        try:
                            message = await self.ctx.fetch_message(self.message.id)
                            await message.edit(embed=embed, view=self)
                        except:
                            pass
                    else:
                        try:
                            await self.message.edit(embed=embed, view=self)
                        except:
                            pass
            except Exception as e:
                print(f"Error updating preview: {e}")
        
        def create_event_embed(self, is_announcement=False):
            
            if is_announcement:
                embed = discord.Embed(
                    title=f"📅 New Event: {self.event_data['title']}",
                    description=self.event_data["description"],
                    color=discord.Color.gold()
                )
            else:
                embed = discord.Embed(
                    title="Event Preview",
                    description="Use the buttons below to configure your event.",
                    color=discord.Color.blue()
                )
                

                if self.event_data["title"]:
                    embed.add_field(name="Title", value=self.event_data["title"], inline=False)
                else:
                    embed.add_field(name="Title", value="Not set", inline=False)
                    
                if self.event_data["description"]:
                    embed.add_field(name="Description", value=self.event_data["description"], inline=False)
                else:
                    embed.add_field(name="Description", value="Not set", inline=False)
            
            embed.add_field(name="Event Type", value=self.event_data["type"].capitalize(), inline=True)
            
            if self.event_data["type"] == "one-time":
                if self.event_data["datetime"]:
                    dt = self.event_data["datetime"]
                    embed.add_field(
                        name="Date & Time", 
                        value=f"<t:{int(dt.timestamp())}:F> (<t:{int(dt.timestamp())}:R>)",
                        inline=True
                    )
                else:
                    embed.add_field(name="Date & Time", value="Not set", inline=True)
            else:
                if "rrule" in self.event_data:

                    rule = rrulestr(self.event_data["rrule"])
                    if hasattr(rule, "_freq"):
                        freq_map = {
                            rrule.DAILY: "Daily",
                            rrule.WEEKLY: "Weekly",
                            rrule.MONTHLY: "Monthly",
                            rrule.YEARLY: "Yearly"
                        }
                        freq = freq_map.get(rule._freq, "Custom")
                        embed.add_field(name="Recurrence", value=freq, inline=True)
                    else:
                        embed.add_field(name="Recurrence", value="Custom", inline=True)
                else:
                    embed.add_field(name="Recurrence", value="Not set", inline=True)
            
            if self.event_data["location"]:
                embed.add_field(name="Location", value=self.event_data["location"], inline=True)
                

            if self.event_data["reminders"]:
                reminder_text = ", ".join([f"{r} minutes" for r in sorted(self.event_data["reminders"])])
                embed.add_field(name="Reminders", value=reminder_text, inline=True)
                

            mentions = []
            if self.event_data["mention_roles"]:
                for role_id in self.event_data["mention_roles"]:
                    role = self.guild.get_role(int(role_id))
                    if role:
                        mentions.append(f"@{role.name}")
                        
            if self.event_data["mention_users"]:
                for user_id in self.event_data["mention_users"]:
                    user = self.guild.get_member(int(user_id))
                    if user:
                        mentions.append(f"@{user.display_name}")
                        
            if mentions:
                embed.add_field(name="Mentions", value=", ".join(mentions), inline=True)
                
            embed.set_footer(text="Created by TheHolyOneZ • DisEventCalendar")
            return embed
        

        class TitleModal(discord.ui.Modal, title="Set Event Title"):
            title_input = discord.ui.TextInput(
                label="Event Title",
                placeholder="Enter a title for your event",
                max_length=100,
                required=True
            )
            
            def __init__(self, parent_view):
                super().__init__()
                self.parent_view = parent_view
                
                if self.parent_view.event_data["title"]:
                    self.title_input.default = self.parent_view.event_data["title"]
            
            async def on_submit(self, interaction: discord.Interaction):
                self.parent_view.event_data["title"] = self.title_input.value
                try:
                    await interaction.response.defer()
                    await self.parent_view.update_preview(interaction)
                except Exception as e:
                    try:
                        await interaction.followup.send("Title updated!", ephemeral=True)
                        await self.parent_view.update_preview()
                    except:
                        pass
        

        class DescriptionModal(discord.ui.Modal, title="Set Event Description"):
            description_input = discord.ui.TextInput(
                label="Event Description",
                placeholder="Enter a description for your event",
                style=discord.TextStyle.paragraph,
                max_length=1000,
                required=True
            )
            
            def __init__(self, parent_view):
                super().__init__()
                self.parent_view = parent_view
                
                if self.parent_view.event_data["description"]:
                    self.description_input.default = self.parent_view.event_data["description"]
            
            async def on_submit(self, interaction: discord.Interaction):
                self.parent_view.event_data["description"] = self.description_input.value
                try:
                    await interaction.response.defer()
                    await self.parent_view.update_preview(interaction)
                except Exception as e:
                    try:
                        await interaction.followup.send("Description updated!", ephemeral=True)
                        await self.parent_view.update_preview()
                    except:
                        pass
        

        class DateTimeModal(discord.ui.Modal, title="Set Event Date & Time"):
            date_input = discord.ui.TextInput(
                label="Date (YYYY-MM-DD)",
                placeholder="e.g., 2023-12-31",
                required=True
            )
            
            time_input = discord.ui.TextInput(
                label="Time (HH:MM)",
                placeholder="e.g., 14:30 (24-hour format)",
                required=True
            )
            
            timezone_input = discord.ui.TextInput(
                label="Timezone",
                placeholder="e.g., UTC, America/New_York, Europe/London",
                default="UTC",
                required=True
            )
            
            def __init__(self, parent_view):
                super().__init__()
                self.parent_view = parent_view
                
                if self.parent_view.event_data["datetime"]:
                    dt = self.parent_view.event_data["datetime"]
                    self.date_input.default = dt.strftime("%Y-%m-%d")
                    self.time_input.default = dt.strftime("%H:%M")
                    self.timezone_input.default = self.parent_view.event_data["timezone"]
            
            async def on_submit(self, interaction: discord.Interaction):
                try:

                    timezone = self.timezone_input.value
                    if timezone not in pytz.all_timezones:
                        raise ValueError(f"Invalid timezone: {timezone}")
                    

                    date_str = self.date_input.value
                    time_str = self.time_input.value
                    dt_str = f"{date_str} {time_str}"
                    

                    local_dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                    local_tz = pytz.timezone(timezone)
                    local_dt = local_tz.localize(local_dt)
                    

                    utc_dt = local_dt.astimezone(pytz.UTC)
                    
                    self.parent_view.event_data["datetime"] = utc_dt
                    self.parent_view.event_data["timezone"] = timezone
                    
                    try:
                        await interaction.response.defer()
                        await self.parent_view.update_preview(interaction)
                    except Exception as e:
                        try:
                            await interaction.followup.send("Date and time updated!", ephemeral=True)
                            await self.parent_view.update_preview()
                        except:
                            pass
                    
                except ValueError as e:
                    await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)
                except Exception as e:
                    await interaction.response.send_message(
                        f"Error: Invalid date or time format. Please use YYYY-MM-DD for date and HH:MM for time.",
                        ephemeral=True
                    )
        

        class LocationModal(discord.ui.Modal, title="Set Event Location"):
            location_input = discord.ui.TextInput(
                label="Event Location",
                placeholder="Enter a location for your event",
                max_length=100,
                required=False
            )
            
            def __init__(self, parent_view):
                super().__init__()
                self.parent_view = parent_view
                
                if self.parent_view.event_data["location"]:
                    self.location_input.default = self.parent_view.event_data["location"]
            
            async def on_submit(self, interaction: discord.Interaction):
                self.parent_view.event_data["location"] = self.location_input.value
                try:
                    await interaction.response.defer()
                    await self.parent_view.update_preview(interaction)
                except Exception as e:
                    try:
                        await interaction.followup.send("Location updated!", ephemeral=True)
                        await self.parent_view.update_preview()
                    except:
                        pass
        

        class RemindersModal(discord.ui.Modal, title="Set Event Reminders"):
            reminders_input = discord.ui.TextInput(
                label="Reminder Times (minutes before event)",
                placeholder="Enter comma-separated values (e.g., 10,30,60)",
                required=True
            )
            
            def __init__(self, parent_view):
                super().__init__()
                self.parent_view = parent_view
                
                if self.parent_view.event_data["reminders"]:
                    self.reminders_input.default = ",".join(map(str, self.parent_view.event_data["reminders"]))
            
            async def on_submit(self, interaction: discord.Interaction):
                try:

                    reminder_values = self.reminders_input.value.split(",")
                    reminders = []
                    
                    for value in reminder_values:
                        minutes = int(value.strip())
                        if minutes <= 0:
                            raise ValueError("Reminder times must be positive numbers")
                        reminders.append(minutes)
                    
                    self.parent_view.event_data["reminders"] = reminders
                    try:
                        await interaction.response.defer()
                        await self.parent_view.update_preview(interaction)
                    except Exception as e:
                        try:
                            await interaction.followup.send("Reminders updated!", ephemeral=True)
                            await self.parent_view.update_preview()
                        except:
                            pass
                    
                except ValueError:
                    await interaction.response.send_message(
                        "Error: Please enter valid numbers separated by commas.",
                        ephemeral=True
                    )
        

        class RecurrenceView(discord.ui.View):
            def __init__(self, parent_view):
                super().__init__(timeout=300)
                self.parent_view = parent_view
                self.frequency = "weekly"
                self.interval = 1
                self.weekdays = []
                self.day_of_month = 1
                self.month = 1
                self.start_date = None
                self.end_date = None
                
            @discord.ui.select(
                placeholder="Select Frequency",
                options=[
                    discord.SelectOption(label="Daily", value="daily", description="Event occurs every day"),
                    discord.SelectOption(label="Weekly", value="weekly", description="Event occurs on specific days of the week"),
                    discord.SelectOption(label="Monthly", value="monthly", description="Event occurs on specific days of the month"),
                    discord.SelectOption(label="Yearly", value="yearly", description="Event occurs on specific days of the year")
                ],
                custom_id="recurrence_frequency"
            )
            async def frequency_select(self, interaction: discord.Interaction, select: discord.ui.Select):
                self.frequency = select.values[0]
                

                new_view = self.__class__(self.parent_view)
                new_view.frequency = self.frequency
                new_view.interval = self.interval
                new_view.weekdays = self.weekdays
                new_view.day_of_month = self.day_of_month
                new_view.month = self.month
                new_view.start_date = self.start_date
                new_view.end_date = self.end_date
                

                if self.frequency == "weekly":
                    weekday_button = discord.ui.Button(
                        label="Set Weekdays",
                        style=discord.ButtonStyle.secondary,
                        custom_id="recurrence_weekday"
                    )
                    weekday_button.callback = new_view.weekday_button_callback
                    new_view.add_item(weekday_button)
                elif self.frequency == "monthly":
                    monthday_button = discord.ui.Button(
                        label="Set Day of Month",
                        style=discord.ButtonStyle.secondary,
                        custom_id="recurrence_monthday"
                    )
                    monthday_button.callback = new_view.monthday_button_callback
                    new_view.add_item(monthday_button)
                elif self.frequency == "yearly":
                    monthday_button = discord.ui.Button(
                        label="Set Day of Month",
                        style=discord.ButtonStyle.secondary,
                        custom_id="recurrence_monthday_yearly"
                    )
                    monthday_button.callback = new_view.monthday_button_callback
                    new_view.add_item(monthday_button)
                    
                    month_button = discord.ui.Button(
                        label="Set Month",
                        style=discord.ButtonStyle.secondary,
                        custom_id="recurrence_month"
                    )
                    month_button.callback = new_view.month_button_callback
                    new_view.add_item(month_button)
                
                await interaction.response.edit_message(view=new_view)
            
            @discord.ui.button(label="Set Start Date", style=discord.ButtonStyle.primary, custom_id="recurrence_start_date")
            async def start_date_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.send_modal(self.StartDateModal(self))
            
            @discord.ui.button(label="Set Interval", style=discord.ButtonStyle.secondary, custom_id="recurrence_interval")
            async def interval_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.send_modal(self.IntervalModal(self))
            
            @discord.ui.button(label="Set End Date (Optional)", style=discord.ButtonStyle.secondary, custom_id="recurrence_end_date")
            async def end_date_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.send_modal(self.EndDateModal(self))
            
            @discord.ui.button(label="Save Recurrence", style=discord.ButtonStyle.success, custom_id="recurrence_save")
            async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if not self.start_date:
                    await interaction.response.send_message("You must set a start date.", ephemeral=True)
                    return
                

                rrule_parts = []
                

                if self.frequency == "daily":
                    rrule_parts.append("FREQ=DAILY")
                elif self.frequency == "weekly":
                    rrule_parts.append("FREQ=WEEKLY")
                    if self.weekdays:
                        weekday_str = ",".join(self.weekdays)
                        rrule_parts.append(f"BYDAY={weekday_str}")
                elif self.frequency == "monthly":
                    rrule_parts.append("FREQ=MONTHLY")
                    rrule_parts.append(f"BYMONTHDAY={self.day_of_month}")
                elif self.frequency == "yearly":
                    rrule_parts.append("FREQ=YEARLY")
                    rrule_parts.append(f"BYMONTHDAY={self.day_of_month}")
                    rrule_parts.append(f"BYMONTH={self.month}")
                

                rrule_parts.append(f"INTERVAL={self.interval}")
                

                if self.end_date:
                    end_date_str = self.end_date.strftime("%Y%m%dT%H%M%SZ")
                    rrule_parts.append(f"UNTIL={end_date_str}")
                

                rrule_str = ";".join(rrule_parts)
                

                self.parent_view.event_data["rrule"] = rrule_str
                self.parent_view.event_data["start_date"] = self.start_date.isoformat()
                if self.end_date:
                    self.parent_view.event_data["end_date"] = self.end_date.isoformat()
                
                await interaction.response.send_message("Recurrence pattern saved!", ephemeral=True)
                await self.parent_view.update_preview()
            
            async def weekday_button_callback(self, interaction: discord.Interaction):
                view = self.WeekdaySelectView(self)
                await interaction.response.send_message("Select weekdays:", view=view, ephemeral=True)
            
            async def monthday_button_callback(self, interaction: discord.Interaction):
                await interaction.response.send_modal(self.MonthdayModal(self))
            
            async def month_button_callback(self, interaction: discord.Interaction):
                view = self.MonthSelectView(self)
                await interaction.response.send_message("Select month:", view=view, ephemeral=True)
            
            class WeekdaySelectView(discord.ui.View):
                def __init__(self, parent_view):
                    super().__init__(timeout=300)
                    self.parent_view = parent_view
                    self.add_item(self.WeekdaySelect(parent_view))
                
                class WeekdaySelect(discord.ui.Select):
                    def __init__(self, parent_view):
                        options = [
                            discord.SelectOption(label="Monday", value="MO"),
                            discord.SelectOption(label="Tuesday", value="TU"),
                            discord.SelectOption(label="Wednesday", value="WE"),
                            discord.SelectOption(label="Thursday", value="TH"),
                            discord.SelectOption(label="Friday", value="FR"),
                            discord.SelectOption(label="Saturday", value="SA"),
                            discord.SelectOption(label="Sunday", value="SU")
                        ]
                        
                        super().__init__(
                            placeholder="Select weekdays",
                            min_values=1,
                            max_values=7,
                            options=options,
                            custom_id="weekday_select"
                        )
                        
                        self.parent_view = parent_view
                    
                    async def callback(self, interaction: discord.Interaction):
                        self.parent_view.weekdays = self.values
                        await interaction.response.send_message(
                            f"Selected weekdays: {', '.join(self.values)}",
                            ephemeral=True
                        )
            
            class MonthdayModal(discord.ui.Modal, title="Set Day of Month"):
                day_input = discord.ui.TextInput(
                    label="Day of Month (1-31)",
                    placeholder="Enter a number between 1 and 31",
                    default="1",
                    required=True
                )
                
                def __init__(self, parent_view):
                    super().__init__()
                    self.parent_view = parent_view
                    self.day_input.default = str(self.parent_view.day_of_month)
                
                async def on_submit(self, interaction: discord.Interaction):
                    try:
                        day = int(self.day_input.value)
                        if day < 1 or day > 31:
                            raise ValueError("Day must be between 1 and 31")
                        
                        self.parent_view.day_of_month = day
                        await interaction.response.send_message(
                            f"Day of month set to: {day}",
                            ephemeral=True
                        )
                    except ValueError as e:
                        await interaction.response.send_message(
                            f"Error: {str(e)}",
                            ephemeral=True
                        )
            
            class MonthSelectView(discord.ui.View):
                def __init__(self, parent_view):
                    super().__init__(timeout=300)
                    self.parent_view = parent_view
                    self.add_item(self.MonthSelect(parent_view))
                
                class MonthSelect(discord.ui.Select):
                    def __init__(self, parent_view):
                        months = [
                            ("January", 1), ("February", 2), ("March", 3),
                            ("April", 4), ("May", 5), ("June", 6),
                            ("July", 7), ("August", 8), ("September", 9),
                            ("October", 10), ("November", 11), ("December", 12)
                        ]
                        
                        options = [
                            discord.SelectOption(label=name, value=str(value))
                            for name, value in months
                        ]
                        
                        super().__init__(
                            placeholder="Select month",
                            options=options,
                            custom_id="month_select"
                        )
                        
                        self.parent_view = parent_view
                    
                    async def callback(self, interaction: discord.Interaction):
                        self.parent_view.month = int(self.values[0])
                        month_name = dict([
                            (1, "January"), (2, "February"), (3, "March"),
                            (4, "April"), (5, "May"), (6, "June"),
                            (7, "July"), (8, "August"), (9, "September"),
                            (10, "October"), (11, "November"), (12, "December")
                        ])[self.parent_view.month]
                        
                        await interaction.response.send_message(
                            f"Month set to: {month_name}",
                            ephemeral=True
                        )
            
            class StartDateModal(discord.ui.Modal, title="Set Start Date"):
                date_input = discord.ui.TextInput(
                    label="Start Date (YYYY-MM-DD)",
                    placeholder="e.g., 2023-12-31",
                    required=True
                )
                
                time_input = discord.ui.TextInput(
                    label="Start Time (HH:MM)",
                    placeholder="e.g., 14:30 (24-hour format)",
                    required=True
                )
                
                timezone_input = discord.ui.TextInput(
                    label="Timezone",
                    placeholder="e.g., UTC, America/New_York, Europe/London",
                    default="UTC",
                    required=True
                )
                
                def __init__(self, parent_view):
                    super().__init__()
                    self.parent_view = parent_view
                
                async def on_submit(self, interaction: discord.Interaction):
                    try:

                        timezone = self.timezone_input.value
                        if timezone not in pytz.all_timezones:
                            raise ValueError(f"Invalid timezone: {timezone}")
                        

                        date_str = self.date_input.value
                        time_str = self.time_input.value
                        dt_str = f"{date_str} {time_str}"
                        

                        local_dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                        local_tz = pytz.timezone(timezone)
                        local_dt = local_tz.localize(local_dt)
                        

                        utc_dt = local_dt.astimezone(pytz.UTC)
                        
                        self.parent_view.start_date = utc_dt
                        self.parent_view.parent_view.event_data["timezone"] = timezone
                        
                        await interaction.response.send_message(
                            f"Start date set to: {local_dt.strftime('%Y-%m-%d %H:%M')} {timezone}",
                            ephemeral=True
                        )
                    except ValueError as e:
                        await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)
                    except Exception as e:
                        await interaction.response.send_message(
                            f"Error: Invalid date or time format. Please use YYYY-MM-DD for date and HH:MM for time.",
                            ephemeral=True
                        )
            
            class EndDateModal(discord.ui.Modal, title="Set End Date"):
                date_input = discord.ui.TextInput(
                    label="End Date (YYYY-MM-DD)",
                    placeholder="e.g., 2023-12-31",
                    required=True
                )
                
                time_input = discord.ui.TextInput(
                    label="End Time (HH:MM)",
                    placeholder="e.g., 14:30 (24-hour format)",
                    required=True
                )
                
                def __init__(self, parent_view):
                    super().__init__()
                    self.parent_view = parent_view
                
                async def on_submit(self, interaction: discord.Interaction):
                    try:

                        date_str = self.date_input.value
                        time_str = self.time_input.value
                        dt_str = f"{date_str} {time_str}"
                        

                        timezone = self.parent_view.parent_view.event_data["timezone"]
                        

                        local_dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                        local_tz = pytz.timezone(timezone)
                        local_dt = local_tz.localize(local_dt)
                        

                        utc_dt = local_dt.astimezone(pytz.UTC)
                        
                        self.parent_view.end_date = utc_dt
                        
                        await interaction.response.send_message(
                            f"End date set to: {local_dt.strftime('%Y-%m-%d %H:%M')} {timezone}",
                            ephemeral=True
                        )
                    except Exception as e:
                        await interaction.response.send_message(
                            f"Error: Invalid date or time format. Please use YYYY-MM-DD for date and HH:MM for time.",
                            ephemeral=True
                        )
            
            class IntervalModal(discord.ui.Modal, title="Set Interval"):
                interval_input = discord.ui.TextInput(
                    label="Interval",
                    placeholder="Enter a number (e.g., 2 for every 2 weeks)",
                    default="1",
                    required=True
                )
                
                def __init__(self, parent_view):
                    super().__init__()
                    self.parent_view = parent_view
                    self.interval_input.default = str(self.parent_view.interval)
                
                async def on_submit(self, interaction: discord.Interaction):
                    try:
                        interval = int(self.interval_input.value)
                        if interval < 1:
                            raise ValueError("Interval must be at least 1")
                        
                        self.parent_view.interval = interval
                        
                        frequency_name = {
                            "daily": "day(s)",
                            "weekly": "week(s)",
                            "monthly": "month(s)",
                            "yearly": "year(s)"
                        }[self.parent_view.frequency]
                        
                        await interaction.response.send_message(
                            f"Interval set to: Every {interval} {frequency_name}",
                            ephemeral=True
                        )
                    except ValueError as e:
                        await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)
        

        class MentionsView(discord.ui.View):
            def __init__(self, parent_view):
                super().__init__(timeout=300)
                self.parent_view = parent_view
                

                self.add_item(self.RoleSelect(parent_view))
                

                add_users_button = discord.ui.Button(
                    label="Add Users",
                    style=discord.ButtonStyle.secondary,
                    custom_id="mentions_add_users"
                )
                add_users_button.callback = self.add_users_callback
                self.add_item(add_users_button)
                

                done_button = discord.ui.Button(
                    label="Done",
                    style=discord.ButtonStyle.success,
                    custom_id="mentions_done"
                )
                done_button.callback = self.done_callback
                self.add_item(done_button)
            
            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                if interaction.user.id != self.parent_view.author.id:
                    await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
                    return False
                return True
            
            async def add_users_callback(self, interaction: discord.Interaction):

                await interaction.response.send_modal(self.UserInputModal(self.parent_view))
            
            async def done_callback(self, interaction: discord.Interaction):
                await interaction.response.edit_message(content="Mentions saved!", view=None)
                await self.parent_view.update_preview()
            
            class RoleSelect(discord.ui.RoleSelect):
                def __init__(self, parent_view):
                    super().__init__(
                        placeholder="Select roles to mention",
                        min_values=0,
                        max_values=25,
                        custom_id="role_select"
                    )
                    self.parent_view = parent_view
                
                async def callback(self, interaction: discord.Interaction):

                    self.parent_view.event_data["mention_roles"] = [role.id for role in self.values]
                    
                    role_names = [role.name for role in self.values]
                    if role_names:
                        await interaction.response.send_message(
                            f"Selected roles: {', '.join(role_names)}",
                            ephemeral=True
                        )
                    else:
                        await interaction.response.send_message("No roles selected.", ephemeral=True)
            
            class UserInputModal(discord.ui.Modal, title="Add Users to Mention"):
                user_input = discord.ui.TextInput(
                    label="User IDs or @mentions",
                    placeholder="Enter user IDs or @mentions, separated by commas",
                    style=discord.TextStyle.paragraph,
                    required=True
                )
                
                def __init__(self, parent_view):
                    super().__init__()
                    self.parent_view = parent_view
                
                async def on_submit(self, interaction: discord.Interaction):

                    input_text = self.user_input.value
                    

                    user_ids = []
                    mention_pattern = r'<@!?(\d+)>'
                    

                    mentions = re.findall(mention_pattern, input_text)
                    if mentions:
                        user_ids.extend(mentions)
                    

                    parts = [p.strip() for p in input_text.split(',')]
                    for part in parts:
                        if part.isdigit():
                            user_ids.append(part)
                    

                    valid_users = []
                    for user_id in user_ids:
                        member = self.parent_view.guild.get_member(int(user_id))
                        if member:
                            valid_users.append(member)
                    

                    self.parent_view.event_data["mention_users"] = [user.id for user in valid_users]
                    
                    if valid_users:
                        user_names = [user.display_name for user in valid_users]
                        await interaction.response.send_message(
                            f"Added users: {', '.join(user_names)}",
                            ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            "No valid users found. Make sure to use valid user IDs or mentions.",
                            ephemeral=True
                        )
    

    event_group = app_commands.Group(name="event", description="Manage events")
    
    @event_group.command(name="create", description="Create a new event")
    async def event_create(self, interaction: discord.Interaction):
        

        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
            
        if not self._check_permissions(interaction):
            await interaction.response.send_message(
                "You don't have permission to create events. You need the 'Manage Events' permission or an appropriate role.",
                ephemeral=True
            )
            return
        

        view = self.EventCreationView(self, interaction)
        

        embed = view.create_event_embed()
        await interaction.response.send_message(embed=embed, view=view)
        

        view.message = await interaction.original_response()
    
    @event_group.command(name="list", description="List all upcoming events")
    async def event_list(self, interaction: discord.Interaction):
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
            
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.events or not self.events[guild_id]:
            await interaction.response.send_message("There are no upcoming events.", ephemeral=True)
            return
        

        embed = discord.Embed(
            title="Upcoming Events",
            description="Here are all upcoming events for this server:",
            color=discord.Color.blue()
        )
        
        now = datetime.datetime.now(pytz.UTC)
        upcoming_events = []
        
        for event_id, event in self.events[guild_id].items():
            next_time = self._get_next_occurrence(event)
            
            if next_time and next_time > now:
                upcoming_events.append((event_id, event, next_time))
        

        upcoming_events.sort(key=lambda x: x[2])
        
        if not upcoming_events:
            await interaction.response.send_message("There are no upcoming events.", ephemeral=True)
            return
        

        for i, (event_id, event, next_time) in enumerate(upcoming_events[:10], 1):
            embed.add_field(
                name=f"{i}. {event['title']}",
                value=f"**When:** <t:{int(next_time.timestamp())}:F> (<t:{int(next_time.timestamp())}:R>)\n"
                      f"**Description:** {event['description'][:100]}{'...' if len(event['description']) > 100 else ''}\n"
                      f"**ID:** `{event_id}`",
                inline=False
            )
        
        if len(upcoming_events) > 10:
            embed.set_footer(text=f"Showing 10 of {len(upcoming_events)} upcoming events.")
        

        view = self.EventListView(self, interaction, upcoming_events)
        await interaction.response.send_message(embed=embed, view=view)
    
    class EventListView(discord.ui.View):
        def __init__(self, cog, interaction, events):
            super().__init__(timeout=300)
            self.cog = cog
            self.interaction = interaction
            self.events = events
        
        @discord.ui.button(label="View Details", style=discord.ButtonStyle.primary, custom_id="view_details")
        async def view_details_button(self, interaction: discord.Interaction, button: discord.ui.Button):

            view = discord.ui.View(timeout=300)
            view.add_item(self.EventSelect(self.cog, self.events))
            await interaction.response.send_message("Select an event to view:", view=view, ephemeral=True)
        
        @discord.ui.button(label="Delete Event", style=discord.ButtonStyle.danger, custom_id="delete_event")
        async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):

            if not self.cog._check_permissions(interaction):
                await interaction.response.send_message(
                    "You don't have permission to delete events.",
                    ephemeral=True
                )
                return
            

            view = discord.ui.View(timeout=300)
            view.add_item(self.EventDeleteSelect(self.cog, self.events))
            await interaction.response.send_message("Select an event to delete:", view=view, ephemeral=True)
        
        class EventSelect(discord.ui.Select):
            def __init__(self, cog, events):
                options = []
                
                for event_id, event, next_time in events[:25]:  # Discord limits to 25 options
                    options.append(
                        discord.SelectOption(
                            label=event['title'][:100],
                            value=event_id,
                            description=f"Occurs at {next_time.strftime('%Y-%m-%d %H:%M')} UTC"
                        )
                    )
                
                super().__init__(
                    placeholder="Select an event",
                    options=options,
                    custom_id="event_select"
                )
                
                self.cog = cog
                self.events = events
            
            async def callback(self, interaction: discord.Interaction):
                event_id = self.values[0]
                guild_id = str(interaction.guild.id)
                
                if guild_id in self.cog.events and event_id in self.cog.events[guild_id]:
                    event = self.cog.events[guild_id][event_id]
                    

                    embed = discord.Embed(
                        title=event['title'],
                        description=event['description'],
                        color=discord.Color.blue()
                    )
                    

                    if event['type'] == 'one-time':
                        dt = event['datetime']
                        embed.add_field(
                            name="Date & Time",
                            value=f"<t:{int(dt.timestamp())}:F> (<t:{int(dt.timestamp())}:R>)",
                            inline=True
                        )
                    else:
                        next_time = self.cog._get_next_occurrence(event)
                        if next_time:
                            embed.add_field(
                                name="Next Occurrence",
                                value=f"<t:{int(next_time.timestamp())}:F> (<t:{int(next_time.timestamp())}:R>)",
                                inline=True
                            )
                            

                            rule = rrulestr(event['rrule'])
                            if hasattr(rule, "_freq"):
                                freq_map = {
                                    rrule.DAILY: "Daily",
                                    rrule.WEEKLY: "Weekly",
                                    rrule.MONTHLY: "Monthly",
                                    rrule.YEARLY: "Yearly"
                                }
                                freq = freq_map.get(rule._freq, "Custom")
                                embed.add_field(name="Recurrence", value=freq, inline=True)
                    
                    if 'location' in event and event['location']:
                        embed.add_field(name="Location", value=event['location'], inline=True)
                    

                    if event['reminders']:
                        reminder_text = ", ".join([f"{r} minutes" for r in sorted(event['reminders'])])
                        embed.add_field(name="Reminders", value=reminder_text, inline=True)
                    

                    mentions = []
                    if 'mention_roles' in event and event['mention_roles']:
                        for role_id in event['mention_roles']:
                            role = interaction.guild.get_role(int(role_id))
                            if role:
                                mentions.append(f"@{role.name}")
                    
                    if 'mention_users' in event and event['mention_users']:
                        for user_id in event['mention_users']:
                            user = interaction.guild.get_member(int(user_id))
                            if user:
                                mentions.append(f"@{user.display_name}")
                    
                    if mentions:
                        embed.add_field(name="Mentions", value=", ".join(mentions), inline=True)
                    

                    if 'created_by' in event:
                        creator = interaction.guild.get_member(event['created_by'])
                        creator_name = creator.display_name if creator else f"User ID: {event['created_by']}"
                        embed.add_field(name="Created By", value=creator_name, inline=True)
                    
                    embed.set_footer(text=f"Event ID: {event_id} • Created by TheHolyOneZ")
                    
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message("Event not found.", ephemeral=True)
        
        class EventDeleteSelect(discord.ui.Select):
            def __init__(self, cog, events):
                options = []
                
                for event_id, event, next_time in events[:25]:  # Discord limits to 25 options
                    options.append(
                        discord.SelectOption(
                            label=event['title'][:100],
                            value=event_id,
                            description=f"Occurs at {next_time.strftime('%Y-%m-%d %H:%M')} UTC"
                        )
                    )
                
                super().__init__(
                    placeholder="Select an event to delete",
                    options=options,
                    custom_id="event_delete_select"
                )
                
                self.cog = cog
                self.events = events
            
            async def callback(self, interaction: discord.Interaction):
                event_id = self.values[0]
                guild_id = str(interaction.guild.id)
                
                if guild_id in self.cog.events and event_id in self.cog.events[guild_id]:

                    view = discord.ui.View(timeout=60)
                    
                    confirm_button = discord.ui.Button(
                        label="Confirm", 
                        style=discord.ButtonStyle.danger,
                        custom_id="confirm_delete"
                    )
                    cancel_button = discord.ui.Button(
                        label="Cancel", 
                        style=discord.ButtonStyle.secondary,
                        custom_id="cancel_delete"
                    )
                    
                    async def confirm_callback(confirm_interaction):
                        if confirm_interaction.user.id != interaction.user.id:
                            await confirm_interaction.response.send_message(
                                "You cannot use this confirmation.", 
                                ephemeral=True
                            )
                            return
                        

                        event_title = self.cog.events[guild_id][event_id]['title']
                        del self.cog.events[guild_id][event_id]
                        

                        if event_id in self.cog.reminders:
                            for task in self.cog.reminders[event_id]:
                                task.cancel()
                            del self.cog.reminders[event_id]
                        

                        self.cog.save_events()
                        
                        await confirm_interaction.response.edit_message(
                            content=f"Event '{event_title}' has been deleted.",
                            view=None
                        )
                    
                    async def cancel_callback(cancel_interaction):
                        if cancel_interaction.user.id != interaction.user.id:
                            await cancel_interaction.response.send_message(
                                "You cannot use this confirmation.", 
                                ephemeral=True
                            )
                            return
                        
                        await cancel_interaction.response.edit_message(
                            content="Event deletion cancelled.",
                            view=None
                        )
                    

                    confirm_button.callback = confirm_callback
                    cancel_button.callback = cancel_callback
                    

                    view.add_item(confirm_button)
                    view.add_item(cancel_button)
                    
                    event_title = self.cog.events[guild_id][event_id]['title']
                    await interaction.response.send_message(
                        f"Are you sure you want to delete the event '{event_title}'?",
                        view=view,
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message("Event not found.", ephemeral=True)
    
    @event_group.command(name="delete", description="Delete an event by ID")
    async def event_delete(self, interaction: discord.Interaction, event_id: str):
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
            
        if not self._check_permissions(interaction):
            await interaction.response.send_message(
                "You don't have permission to delete events.",
                ephemeral=True
            )
            return
            
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.events or event_id not in self.events[guild_id]:
            await interaction.response.send_message(f"Event with ID '{event_id}' not found.", ephemeral=True)
            return
        

        view = discord.ui.View(timeout=60)
        
        confirm_button = discord.ui.Button(
            label="Confirm", 
            style=discord.ButtonStyle.danger,
            custom_id="confirm_delete_cmd"
        )
        cancel_button = discord.ui.Button(
            label="Cancel", 
            style=discord.ButtonStyle.secondary,
            custom_id="cancel_delete_cmd"
        )
        
        async def confirm_callback(confirm_interaction):
            if confirm_interaction.user.id != interaction.user.id:
                await confirm_interaction.response.send_message(
                    "You cannot use this confirmation.", 
                    ephemeral=True
                )
                return
            

            event_title = self.events[guild_id][event_id]['title']
            del self.events[guild_id][event_id]
            

            if event_id in self.reminders:
                for task in self.reminders[event_id]:
                    task.cancel()
                del self.reminders[event_id]
            

            self.save_events()
            
            await confirm_interaction.response.edit_message(
                content=f"Event '{event_title}' has been deleted.",
                view=None
            )
        
        async def cancel_callback(cancel_interaction):
            if cancel_interaction.user.id != interaction.user.id:
                await cancel_interaction.response.send_message(
                    "You cannot use this confirmation.", 
                    ephemeral=True
                )
                return
            
            await cancel_interaction.response.edit_message(
                content="Event deletion cancelled.",
                view=None
            )
        

        confirm_button.callback = confirm_callback
        cancel_button.callback = cancel_callback
        

        view.add_item(confirm_button)
        view.add_item(cancel_button)
        
        event_title = self.events[guild_id][event_id]['title']
        await interaction.response.send_message(
            f"Are you sure you want to delete the event '{event_title}'?",
            view=view,
            ephemeral=True
        )
    
    @event_group.command(name="info", description="Get detailed information about an event")
    async def event_info(self, interaction: discord.Interaction, event_id: str):
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
            
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.events or event_id not in self.events[guild_id]:
            await interaction.response.send_message(f"Event with ID '{event_id}' not found.", ephemeral=True)
            return
        
        event = self.events[guild_id][event_id]
        

        embed = discord.Embed(
            title=event['title'],
            description=event['description'],
            color=discord.Color.blue()
        )
        

        if event['type'] == 'one-time':
            dt = event['datetime']
            embed.add_field(
                name="Date & Time",
                value=f"<t:{int(dt.timestamp())}:F> (<t:{int(dt.timestamp())}:R>)",
                inline=True
            )
        else:
            next_time = self._get_next_occurrence(event)
            if next_time:
                embed.add_field(
                    name="Next Occurrence",
                    value=f"<t:{int(next_time.timestamp())}:F> (<t:{int(next_time.timestamp())}:R>)",
                    inline=True
                )
                

                rule = rrulestr(event['rrule'])
                if hasattr(rule, "_freq"):
                    freq_map = {
                        rrule.DAILY: "Daily",
                        rrule.WEEKLY: "Weekly",
                        rrule.MONTHLY: "Monthly",
                        rrule.YEARLY: "Yearly"
                    }
                    freq = freq_map.get(rule._freq, "Custom")
                    embed.add_field(name="Recurrence", value=freq, inline=True)
        
        if 'location' in event and event['location']:
            embed.add_field(name="Location", value=event['location'], inline=True)
        

        if event['reminders']:
            reminder_text = ", ".join([f"{r} minutes" for r in sorted(event['reminders'])])
            embed.add_field(name="Reminders", value=reminder_text, inline=True)
        

        mentions = []
        if 'mention_roles' in event and event['mention_roles']:
            for role_id in event['mention_roles']:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    mentions.append(f"@{role.name}")
        
        if 'mention_users' in event and event['mention_users']:
            for user_id in event['mention_users']:
                user = interaction.guild.get_member(int(user_id))
                if user:
                    mentions.append(f"@{user.display_name}")
        
        if mentions:
            embed.add_field(name="Mentions", value=", ".join(mentions), inline=True)
        

        if 'created_by' in event:
            creator = interaction.guild.get_member(event['created_by'])
            creator_name = creator.display_name if creator else f"User ID: {event['created_by']}"
            embed.add_field(name="Created By", value=creator_name, inline=True)
        
        embed.set_footer(text=f"Event ID: {event_id} • Created by TheHolyOneZ")
        
        await interaction.response.send_message(embed=embed)
    

    @commands.hybrid_command(name="createevent", description="Create a new event (legacy command)")
    @commands.guild_only()
    async def create_event_legacy(self, ctx):
        

        if not self._check_permissions(ctx):
            await ctx.send(
                "You don't have permission to create events. You need the 'Manage Events' permission or an appropriate role.",
                ephemeral=True
            )
            return
        

        view = self.EventCreationView(self, ctx)
        

        embed = view.create_event_embed()
        message = await ctx.send(embed=embed, view=view)
        

        view.message = message
    
    @commands.hybrid_command(name="listevents", description="List all upcoming events (legacy command)")
    @commands.guild_only()
    async def list_events_legacy(self, ctx):
        
        guild_id = str(ctx.guild.id)
        
        if guild_id not in self.events or not self.events[guild_id]:
            await ctx.send("There are no upcoming events.")
            return
        

        embed = discord.Embed(
            title="Upcoming Events",
            description="Here are all upcoming events for this server:",
            color=discord.Color.blue()
        )
        
        now = datetime.datetime.now(pytz.UTC)
        upcoming_events = []
        
        for event_id, event in self.events[guild_id].items():
            next_time = self._get_next_occurrence(event)
            
            if next_time and next_time > now:
                upcoming_events.append((event_id, event, next_time))
        

        upcoming_events.sort(key=lambda x: x[2])
        
        if not upcoming_events:
            await ctx.send("There are no upcoming events.")
            return
        

        for i, (event_id, event, next_time) in enumerate(upcoming_events[:10], 1):
            embed.add_field(
                name=f"{i}. {event['title']}",
                value=f"**When:** <t:{int(next_time.timestamp())}:F> (<t:{int(next_time.timestamp())}:R>)\n"
                      f"**Description:** {event['description'][:100]}{'...' if len(event['description']) > 100 else ''}\n"
                      f"**ID:** `{event_id}`",
                inline=False
            )
        
        if len(upcoming_events) > 10:
            embed.set_footer(text=f"Showing 10 of {len(upcoming_events)} upcoming events.")
        

        view = self.EventListView(self, ctx, upcoming_events)
        await ctx.send(embed=embed, view=view)
    
    @event_group.command(name="calendar", description="View a calendar of upcoming events")
    async def event_calendar(self, interaction: discord.Interaction):
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
            
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.events or not self.events[guild_id]:
            await interaction.response.send_message("There are no upcoming events.", ephemeral=True)
            return
        

        now = datetime.datetime.now(pytz.UTC)
        current_month = now.month
        current_year = now.year
        

        view = self.CalendarView(self, interaction, current_month, current_year)
        await view.update_calendar()
        
        await interaction.response.send_message(embed=view.embed, view=view)
    
    class CalendarView(discord.ui.View):
        def __init__(self, cog, interaction, month, year):
            super().__init__(timeout=300)
            self.cog = cog
            self.interaction = interaction
            self.month = month
            self.year = year
            self.embed = None
        
        @discord.ui.button(label="Previous Month", style=discord.ButtonStyle.secondary, custom_id="prev_month")
        async def prev_month_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.interaction.user.id:
                await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
                return
                

            self.month -= 1
            if self.month < 1:
                self.month = 12
                self.year -= 1
                
            await self.update_calendar()
            await interaction.response.edit_message(embed=self.embed, view=self)
        
        @discord.ui.button(label="Next Month", style=discord.ButtonStyle.secondary, custom_id="next_month")
        async def next_month_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.interaction.user.id:
                await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
                return
                

            self.month += 1
            if self.month > 12:
                self.month = 1
                self.year += 1
                
            await self.update_calendar()
            await interaction.response.edit_message(embed=self.embed, view=self)
        
        @discord.ui.button(label="Today", style=discord.ButtonStyle.primary, custom_id="today")
        async def today_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.interaction.user.id:
                await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
                return
                

            now = datetime.datetime.now(pytz.UTC)
            self.month = now.month
            self.year = now.year
                
            await self.update_calendar()
            await interaction.response.edit_message(embed=self.embed, view=self)
        
        async def update_calendar(self):
            
            guild_id = str(self.interaction.guild.id)
            

            month_names = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]
            month_name = month_names[self.month - 1]
            

            self.embed = discord.Embed(
                title=f"Event Calendar - {month_name} {self.year}",
                description="Here are the events for this month:",
                color=discord.Color.blue()
            )
            

            month_events = []
            now = datetime.datetime.now(pytz.UTC)
            
            for event_id, event in self.cog.events[guild_id].items():
                if event['type'] == 'one-time':
                    event_time = event['datetime']
                    if event_time.month == self.month and event_time.year == self.year:
                        month_events.append((event_id, event, event_time))
                else:  # Recurring event

                    start_of_month = datetime.datetime(self.year, self.month, 1, tzinfo=pytz.UTC)
                    if self.month == 12:
                        end_of_month = datetime.datetime(self.year + 1, 1, 1, tzinfo=pytz.UTC) - datetime.timedelta(seconds=1)
                    else:
                        end_of_month = datetime.datetime(self.year, self.month + 1, 1, tzinfo=pytz.UTC) - datetime.timedelta(seconds=1)
                    
                    rule = rrulestr(event['rrule'], dtstart=datetime.datetime.fromisoformat(event['start_date']))
                    occurrences = rule.between(start_of_month, end_of_month, inc=True)
                    
                    for occurrence in occurrences:
                        if occurrence > now:  # Only include future occurrences
                            month_events.append((event_id, event, occurrence))
            

            month_events.sort(key=lambda x: x[2])
            

            events_by_day = {}
            for event_id, event, event_time in month_events:
                day = event_time.day
                if day not in events_by_day:
                    events_by_day[day] = []
                events_by_day[day].append((event_id, event, event_time))
            

            for day in sorted(events_by_day.keys()):
                day_events = events_by_day[day]
                day_str = f"**{month_name} {day}, {self.year}**"
                events_str = ""
                
                for event_id, event, event_time in day_events:
                    events_str += f"• {event_time.strftime('%H:%M')} - **{event['title']}**\n"
                
                self.embed.add_field(name=day_str, value=events_str, inline=False)
            
            if not month_events:
                self.embed.add_field(name="No Events", value="There are no events scheduled for this month.", inline=False)
            
            self.embed.set_footer(text="Use the buttons below to navigate between months")
    
    @event_group.command(name="edit", description="Edit an existing event")
    async def event_edit(self, interaction: discord.Interaction, event_id: str):
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
            
        if not self._check_permissions(interaction):
            await interaction.response.send_message(
                "You don't have permission to edit events.",
                ephemeral=True
            )
            return
            
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.events or event_id not in self.events[guild_id]:
            await interaction.response.send_message(f"Event with ID '{event_id}' not found.", ephemeral=True)
            return
        

        view = self.EventEditView(self, interaction, event_id)
        

        embed = view.create_event_embed()
        await interaction.response.send_message(embed=embed, view=view)
        

        view.message = await interaction.original_response()
    
    class EventEditView(EventCreationView):
        def __init__(self, cog, interaction, event_id):
            super().__init__(cog, interaction)
            self.event_id = event_id
            guild_id = str(interaction.guild.id)
            

            self.event_data = cog.events[guild_id][event_id].copy()
        
        @discord.ui.button(label="Save Changes", style=discord.ButtonStyle.success, row=4, custom_id="save_changes")
        async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.author.id:
                await interaction.response.send_message("You cannot use this menu.", ephemeral=True)
                return
                

            if not self.event_data["title"]:
                await interaction.response.send_message("You must set a title for the event.", ephemeral=True)
                return
                
            if not self.event_data["description"]:
                await interaction.response.send_message("You must set a description for the event.", ephemeral=True)
                return
                
            if self.event_data["type"] == "one-time" and not self.event_data["datetime"]:
                await interaction.response.send_message("You must set a date and time for the event.", ephemeral=True)
                return
                
            if self.event_data["type"] == "recurring" and "rrule" not in self.event_data:
                await interaction.response.send_message("You must set a recurrence pattern for the event.", ephemeral=True)
                return
                

            guild_id = str(self.guild.id)
            self.cog.events[guild_id][self.event_id] = self.event_data.copy()
            

            self.cog._schedule_reminders(guild_id, self.event_id)
            

            self.cog.save_events()
            

            embed = discord.Embed(
                title="Event Updated",
                description=f"Your event '{self.event_data['title']}' has been updated!",
                color=discord.Color.green()
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            

            channel = self.guild.get_channel(self.event_data["channel_id"])
            if channel:
                announcement_embed = discord.Embed(
                    title=f"📅 Event Updated: {self.event_data['title']}",
                    description=self.event_data["description"],
                    color=discord.Color.gold()
                )
                
                if self.event_data["type"] == "one-time":
                    dt = self.event_data["datetime"]
                    announcement_embed.add_field(
                        name="Date & Time", 
                        value=f"<t:{int(dt.timestamp())}:F> (<t:{int(dt.timestamp())}:R>)",
                        inline=True
                    )
                else:
                    next_time = self.cog._get_next_occurrence(self.event_data)
                    if next_time:
                        announcement_embed.add_field(
                            name="Next Occurrence",
                            value=f"<t:{int(next_time.timestamp())}:F> (<t:{int(next_time.timestamp())}:R>)",
                            inline=True
                        )
                
                if self.event_data["location"]:
                    announcement_embed.add_field(name="Location", value=self.event_data["location"], inline=True)
                
                announcement_embed.set_footer(text=f"Event ID: {self.event_id} • Updated by {self.author.display_name}")
                
                await channel.send(embed=announcement_embed)

def setup(bot):
    cog = DisEventCalendar(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    return cog





