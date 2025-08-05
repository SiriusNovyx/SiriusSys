import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
import datetime
import re
import uuid
from typing import Dict, List, Optional, Union


CONFIG_FILE = "data/disannounce_config.json"
SCHEDULE_FILE = "data/disannounce_schedule.json"


EMBED_COLOR_NEUTRAL = 0x2F3136
EMBED_COLOR_SUCCESS = 0x57F287
EMBED_COLOR_ERROR = 0xED4245
EMBED_COLOR_INFO = 0x3498DB
EMBED_COLOR_WARNING = 0xFEE75C

class AnnouncementManager:
    def __init__(self):
        self.subscriptions = {}  # guild_id -> channel_id
        self.announcement_channels = {}  # source_guild_id -> channel_id (channels that can be subscribed to)
        self.channel_subscribers = {}  # source_channel_id -> [subscriber_guild_ids]
        self.announcement_templates = {}  # guild_id -> template settings
        self.scheduled_announcements = []  # List of scheduled announcements
        self.load_config()
        self.load_schedule()
    
    def load_config(self):

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.subscriptions = data.get('subscriptions', {})
                    self.announcement_channels = data.get('announcement_channels', {})
                    self.channel_subscribers = data.get('channel_subscribers', {})
                    self.announcement_templates = data.get('templates', {})
            except Exception as e:
                print(f"Error loading announcement config: {e}")
                self.subscriptions = {}
                self.announcement_channels = {}
                self.channel_subscribers = {}
                self.announcement_templates = {}
    
    def save_config(self):

        data = {
            'subscriptions': self.subscriptions,
            'announcement_channels': self.announcement_channels,
            'channel_subscribers': self.channel_subscribers,
            'templates': self.announcement_templates
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    
    def load_schedule(self):

        if os.path.exists(SCHEDULE_FILE):
            try:
                with open(SCHEDULE_FILE, 'r') as f:
                    self.scheduled_announcements = json.load(f)
                    

                    for announcement in self.scheduled_announcements:
                        if 'scheduled_time' in announcement:
                            announcement['scheduled_time'] = datetime.datetime.fromisoformat(
                                announcement['scheduled_time']
                            )
            except Exception as e:
                print(f"Error loading announcement schedule: {e}")
                self.scheduled_announcements = []
    
    def save_schedule(self):


        serializable_schedule = []
        for announcement in self.scheduled_announcements:
            serialized = announcement.copy()
            if 'scheduled_time' in serialized and isinstance(serialized['scheduled_time'], datetime.datetime):
                serialized['scheduled_time'] = serialized['scheduled_time'].isoformat()
            serializable_schedule.append(serialized)
            
        with open(SCHEDULE_FILE, 'w') as f:
            json.dump(serializable_schedule, f, indent=4)
    
    def register_announcement_channel(self, guild_id: int, channel_id: int, channel_name: str) -> bool:

        self.announcement_channels[str(guild_id)] = {
            "channel_id": str(channel_id),
            "channel_name": channel_name,
            "guild_id": str(guild_id)
        }
        

        channel_key = f"{guild_id}:{channel_id}"
        if channel_key not in self.channel_subscribers:
            self.channel_subscribers[channel_key] = []
            
        self.save_config()
        return True
    
    def unregister_announcement_channel(self, guild_id: int) -> bool:

        guild_id_str = str(guild_id)
        if guild_id_str not in self.announcement_channels:
            return False
            

        channel_id = self.announcement_channels[guild_id_str]["channel_id"]
        

        del self.announcement_channels[guild_id_str]
        

        channel_key = f"{guild_id}:{channel_id}"
        if channel_key in self.channel_subscribers:
            del self.channel_subscribers[channel_key]
            
        self.save_config()
        return True
    
    def subscribe_to_channel(self, source_guild_id: int, source_channel_id: int, 
                           subscriber_guild_id: int, subscriber_channel_id: int) -> bool:


        self.subscriptions[str(subscriber_guild_id)] = str(subscriber_channel_id)
        

        channel_key = f"{source_guild_id}:{source_channel_id}"
        if channel_key not in self.channel_subscribers:
            self.channel_subscribers[channel_key] = []
            

        if str(subscriber_guild_id) not in self.channel_subscribers[channel_key]:
            self.channel_subscribers[channel_key].append(str(subscriber_guild_id))
            
        self.save_config()
        return True
    
    def unsubscribe_from_channel(self, source_guild_id: int, source_channel_id: int, 
                               subscriber_guild_id: int) -> bool:

        channel_key = f"{source_guild_id}:{source_channel_id}"
        
        if channel_key in self.channel_subscribers:
            if str(subscriber_guild_id) in self.channel_subscribers[channel_key]:
                self.channel_subscribers[channel_key].remove(str(subscriber_guild_id))
                self.save_config()
                return True
                
        return False
    
    def unsubscribe_from_all(self, guild_id: int) -> bool:

        guild_id_str = str(guild_id)
        unsubscribed = False
        

        for channel_key in self.channel_subscribers:
            if guild_id_str in self.channel_subscribers[channel_key]:
                self.channel_subscribers[channel_key].remove(guild_id_str)
                unsubscribed = True
        

        if guild_id_str in self.subscriptions:
            del self.subscriptions[guild_id_str]
            unsubscribed = True
            
        if unsubscribed:
            self.save_config()
            
        return unsubscribed
    
    def get_subscribed_channels(self, guild_id: int) -> List[dict]:

        guild_id_str = str(guild_id)
        subscribed_channels = []
        
        for channel_key, subscribers in self.channel_subscribers.items():
            if guild_id_str in subscribers:
                source_guild_id, source_channel_id = channel_key.split(':')
                

                if source_guild_id in self.announcement_channels:
                    channel_info = self.announcement_channels[source_guild_id].copy()
                    subscribed_channels.append(channel_info)
                    
        return subscribed_channels
    
    def get_channel_subscribers(self, guild_id: int, channel_id: int) -> List[str]:

        channel_key = f"{guild_id}:{channel_id}"
        
        if channel_key in self.channel_subscribers:
            return self.channel_subscribers[channel_key]
            
        return []
    
    def set_template(self, guild_id: int, template_data: dict) -> bool:

        self.announcement_templates[str(guild_id)] = template_data
        self.save_config()
        return True
    
    def get_template(self, guild_id: int) -> Optional[dict]:

        return self.announcement_templates.get(str(guild_id))
    
    def schedule_announcement(self, announcement_data: dict) -> str:


        announcement_id = str(uuid.uuid4())
        announcement_data['id'] = announcement_id
        
        self.scheduled_announcements.append(announcement_data)
        self.scheduled_announcements.sort(
            key=lambda x: x.get('scheduled_time', datetime.datetime.max)
        )
        self.save_schedule()
        return announcement_id
    
    def cancel_scheduled_announcement(self, announcement_id: str) -> bool:

        for i, announcement in enumerate(self.scheduled_announcements):
            if announcement.get('id') == announcement_id:
                del self.scheduled_announcements[i]
                self.save_schedule()
                return True
        return False
    
    def get_scheduled_announcements(self, guild_id: Optional[int] = None) -> List[dict]:

        if guild_id is None:
            return self.scheduled_announcements
        
        guild_id_str = str(guild_id)
        return [a for a in self.scheduled_announcements if a.get('source_guild_id') == guild_id_str]
    
    def get_due_announcements(self) -> List[dict]:

        now = datetime.datetime.now()
        due_announcements = []
        
        for announcement in self.scheduled_announcements:
            scheduled_time = announcement.get('scheduled_time')
            if scheduled_time and scheduled_time <= now:
                due_announcements.append(announcement)
        

        if due_announcements:
            self.scheduled_announcements = [
                a for a in self.scheduled_announcements if a not in due_announcements
            ]
            self.save_schedule()
            
        return due_announcements


class TitleModal(discord.ui.Modal, title="Set Announcement Title"):
    title_input = discord.ui.TextInput(
        label="Title",
        placeholder="Enter the announcement title",
        max_length=256,
        required=True
    )
    
    def __init__(self, view):
        super().__init__()
        self.parent_view = view
        

        if self.parent_view.announcement_data.get('title'):
            self.title_input.default = self.parent_view.announcement_data['title']
    
    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.announcement_data['title'] = self.title_input.value
        

        embed = self.parent_view.create_preview_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class ContentModal(discord.ui.Modal, title="Set Announcement Content"):
    content_input = discord.ui.TextInput(
        label="Content",
        placeholder="Enter the announcement content",
        style=discord.TextStyle.paragraph,
        max_length=4000,
        required=True
    )
    
    def __init__(self, view):
        super().__init__()
        self.parent_view = view
        

        if self.parent_view.announcement_data.get('description'):
            self.content_input.default = self.parent_view.announcement_data['description']
    
    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.announcement_data['description'] = self.content_input.value
        

        embed = self.parent_view.create_preview_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class ColorModal(discord.ui.Modal, title="Set Announcement Color"):
    color_input = discord.ui.TextInput(
        label="Color (Hex Code)",
        placeholder="Enter a hex color code (e.g., #FF5733)",
        min_length=4,
        max_length=7,
        required=True
    )
    
    def __init__(self, view):
        super().__init__()
        self.parent_view = view
        

        if self.parent_view.announcement_data.get('color'):
            color = self.parent_view.announcement_data['color']
            if isinstance(color, int):
                color_hex = f"#{color:06x}"
                self.color_input.default = color_hex
            else:
                self.color_input.default = color
    
    async def on_submit(self, interaction: discord.Interaction):
        color_input = self.color_input.value.strip()
        

        if not color_input.startswith('#'):
            color_input = f"#{color_input}"
        
        try:

            color_int = int(color_input[1:], 16)
            self.parent_view.announcement_data['color'] = color_int
            

            embed = self.parent_view.create_preview_embed()
            await interaction.response.edit_message(embed=embed, view=self.parent_view)
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid color format. Please use a valid hex color code (e.g., #FF5733).",
                ephemeral=True
            )


class ImageModal(discord.ui.Modal, title="Set Announcement Image"):
    image_url = discord.ui.TextInput(
        label="Image URL",
        placeholder="Enter the URL of the image",
        required=True
    )
    
    def __init__(self, view):
        super().__init__()
        self.parent_view = view
        

        if self.parent_view.announcement_data.get('image_url'):
            self.image_url.default = self.parent_view.announcement_data['image_url']
    
    async def on_submit(self, interaction: discord.Interaction):
        url = self.image_url.value.strip()
        

        if not url.startswith(('http://', 'https://')):
            await interaction.response.send_message(
                "❌ Invalid URL. Please enter a valid image URL starting with http:// or https://",
                ephemeral=True
            )
            return
        
        self.parent_view.announcement_data['image_url'] = url
        


        embed = self.parent_view.create_preview_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class ThumbnailModal(discord.ui.Modal, title="Set Announcement Thumbnail"):
    thumbnail_url = discord.ui.TextInput(
        label="Thumbnail URL",
        placeholder="Enter the URL of the thumbnail image",
        required=True
    )
    
    def __init__(self, view):
        super().__init__()
        self.parent_view = view
        

        if self.parent_view.announcement_data.get('thumbnail_url'):
            self.thumbnail_url.default = self.parent_view.announcement_data['thumbnail_url']
    
    async def on_submit(self, interaction: discord.Interaction):
        url = self.thumbnail_url.value.strip()
        

        if not url.startswith(('http://', 'https://')):
            await interaction.response.send_message(
                "❌ Invalid URL. Please enter a valid image URL starting with http:// or https://",
                ephemeral=True
            )
            return
        
        self.parent_view.announcement_data['thumbnail_url'] = url
        

        embed = self.parent_view.create_preview_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class ScheduleModal(discord.ui.Modal, title="Schedule Announcement"):
    date_input = discord.ui.TextInput(
        label="Date (YYYY-MM-DD)",
        placeholder="Enter the date (e.g., 2023-12-31)",
        required=True
    )
    
    time_input = discord.ui.TextInput(
        label="Time (HH:MM) - 24-hour format",
        placeholder="Enter the time (e.g., 14:30)",
        required=True
    )
    
    def __init__(self, view):
        super().__init__()
        self.parent_view = view
        

        now = datetime.datetime.now() + datetime.timedelta(hours=1)
        self.date_input.default = now.strftime("%Y-%m-%d")
        self.time_input.default = now.strftime("%H:%M")
    
    async def on_submit(self, interaction: discord.Interaction):
        try:

            date_str = self.date_input.value.strip()
            time_str = self.time_input.value.strip()
            

            if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                raise ValueError("Invalid date format. Use YYYY-MM-DD.")
            

            if not re.match(r'^\d{2}:\d{2}$', time_str):
                raise ValueError("Invalid time format. Use HH:MM (24-hour format).")
            

            scheduled_time = datetime.datetime.strptime(
                f"{date_str} {time_str}", "%Y-%m-%d %H:%M"
            )
            

            if scheduled_time <= datetime.datetime.now():
                raise ValueError("Cannot schedule announcements in the past.")
            

            self.parent_view.announcement_data['scheduled_time'] = scheduled_time
            

            embed = self.parent_view.create_preview_embed()
            await interaction.response.edit_message(
                content="📢 **Announcement Creator**\n✅ Announcement scheduled for "
                        f"{scheduled_time.strftime('%Y-%m-%d %H:%M')}",
                embed=embed,
                view=self.parent_view
            )
            
        except ValueError as e:
            await interaction.response.send_message(
                f"❌ {str(e)}",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )


class AnnouncementView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=900)  # 15 minute timeout
        self.cog = cog
        self.announcement_data = {
            'title': 'Announcement',
            'description': 'Your announcement content goes here.',
            'color': EMBED_COLOR_NEUTRAL,
            'image_url': None,
            'thumbnail_url': None,
            'footer': 'DisAnnounce | ZygnalBot by TheHolyOneZ'
        }
    
    async def on_timeout(self):

        for item in self.children:
            item.disabled = True
    
    def create_preview_embed(self):

        color = self.announcement_data.get('color', EMBED_COLOR_NEUTRAL)
        
        embed = discord.Embed(
            title=self.announcement_data.get('title', 'Announcement'),
            description=self.announcement_data.get('description', 'Your announcement content goes here.'),
            color=color
        )
        

        if self.announcement_data.get('image_url'):
            embed.set_image(url=self.announcement_data['image_url'])
        

        if self.announcement_data.get('thumbnail_url'):
            embed.set_thumbnail(url=self.announcement_data['thumbnail_url'])
        

        if self.announcement_data.get('scheduled_time'):
            scheduled_time = self.announcement_data['scheduled_time']
            embed.add_field(
                name="Scheduled For",
                value=scheduled_time.strftime("%Y-%m-%d %H:%M"),
                inline=False
            )
        

        embed.set_footer(
            text=self.announcement_data.get('footer', 'DisAnnounce | ZygnalBot by TheHolyOneZ')
        )
        
        return embed
    
    @discord.ui.button(label="Set Title", style=discord.ButtonStyle.primary, row=0)
    async def set_title_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        modal = TitleModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Set Content", style=discord.ButtonStyle.primary, row=0)
    async def set_content_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        modal = ContentModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Set Color", style=discord.ButtonStyle.primary, row=0)
    async def set_color_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        modal = ColorModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Set Image", style=discord.ButtonStyle.secondary, row=1)
    async def set_image_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        modal = ImageModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Set Thumbnail", style=discord.ButtonStyle.secondary, row=1)
    async def set_thumbnail_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        modal = ThumbnailModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Schedule", style=discord.ButtonStyle.success, row=2)
    async def schedule_button(self, interaction: discord.Interaction, button: discord.ui.Button):


        if not self.announcement_data.get('title') or not self.announcement_data.get('description'):
            await interaction.response.send_message(
                "❌ Please set both a title and content before scheduling.",
                ephemeral=True
            )
            return
        
        modal = ScheduleModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Send Now", style=discord.ButtonStyle.danger, row=2)
    async def send_now_button(self, interaction: discord.Interaction, button: discord.ui.Button):


        if not self.announcement_data.get('title') or not self.announcement_data.get('description'):
            await interaction.response.send_message(
                "❌ Please set both a title and content before sending.",
                ephemeral=True
            )
            return
        

        success, result = await self.cog.send_announcement(self.announcement_data)
        
        if success:
            await interaction.response.edit_message(
                content=f"✅ Announcement sent successfully to {result} servers!",
                embed=self.create_preview_embed(),
                view=None  # Remove buttons
            )
        else:
            await interaction.response.send_message(
                f"❌ Failed to send announcement: {result}",
                ephemeral=True
            )
    
    @discord.ui.button(label="Save Template", style=discord.ButtonStyle.secondary, row=3)
    async def save_template_button(self, interaction: discord.Interaction, button: discord.ui.Button):


        if not self.announcement_data.get('title') or not self.announcement_data.get('description'):
            await interaction.response.send_message(
                "❌ Please set both a title and content before saving as a template.",
                ephemeral=True
            )
            return
        

        template_data = self.announcement_data.copy()
        if 'scheduled_time' in template_data:
            del template_data['scheduled_time']
        

        guild_id = interaction.guild.id
        self.cog.announcement_manager.set_template(guild_id, template_data)
        
        await interaction.response.send_message(
            "✅ Template saved successfully! You can use it for future announcements.",
            ephemeral=True
        )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=3)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.edit_message(
            content="❌ Announcement creation cancelled.",
            embed=None,
            view=None  # Remove buttons
        )


class ScheduledAnnouncementsView(discord.ui.View):
    def __init__(self, cog, guild_id, announcements):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.guild_id = guild_id
        self.announcements = announcements
        self.current_page = 0
        self.announcements_per_page = 4
    
    async def on_timeout(self):

        for item in self.children:
            item.disabled = True
    
    def create_embed(self):

        embed = discord.Embed(
            title="DisAnnounce - Scheduled Announcements",
            description="Here are your scheduled announcements:",
            color=EMBED_COLOR_INFO
        )
        
        if not self.announcements:
            embed.description = "You don't have any scheduled announcements."
            return embed
        

        start_idx = self.current_page * self.announcements_per_page
        end_idx = min(start_idx + self.announcements_per_page, len(self.announcements))
        

        for i in range(start_idx, end_idx):
            announcement = self.announcements[i]
            

            scheduled_time = announcement.get('scheduled_time')
            time_str = scheduled_time.strftime("%Y-%m-%d %H:%M") if scheduled_time else "Unknown"
            

            embed.add_field(
                name=f"{i+1}. {announcement.get('title', 'Untitled')}",
                value=(
                    f"**Scheduled for:** {time_str}\n"
                    f"**ID:** {announcement.get('id', 'Unknown')}\n"
                    f"Use the buttons below to manage this announcement."
                ),
                inline=False
            )
        

        total_pages = (len(self.announcements) + self.announcements_per_page - 1) // self.announcements_per_page
        embed.set_footer(text=f"Page {self.current_page + 1}/{total_pages} | ZygnalBot by TheHolyOneZ")
        
        return embed
    
    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        if self.current_page > 0:
            self.current_page -= 1
            

            self.previous_button.disabled = (self.current_page == 0)
            self.next_button.disabled = False
            
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        total_pages = (len(self.announcements) + self.announcements_per_page - 1) // self.announcements_per_page
        
        if self.current_page < total_pages - 1:
            self.current_page += 1
            

            self.previous_button.disabled = False
            self.next_button.disabled = (self.current_page == total_pages - 1)
            
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="View Details", style=discord.ButtonStyle.primary)
    async def view_button(self, interaction: discord.Interaction, button: discord.ui.Button):


        select_options = []
        
        start_idx = self.current_page * self.announcements_per_page
        end_idx = min(start_idx + self.announcements_per_page, len(self.announcements))
        
        for i in range(start_idx, end_idx):
            announcement = self.announcements[i]
            select_options.append(
                discord.SelectOption(
                    label=f"{i+1}. {announcement.get('title', 'Untitled')}",
                    value=str(i),
                    description=f"Scheduled for: {announcement.get('scheduled_time').strftime('%Y-%m-%d %H:%M')}"
                )
            )
        
        if not select_options:
            await interaction.response.send_message(
                "❌ No announcements to view on this page.",
                ephemeral=True
            )
            return
        

        select = discord.ui.Select(
            placeholder="Select an announcement to view",
            options=select_options
        )
        
        async def select_callback(select_interaction):
            idx = int(select.values[0])
            announcement = self.announcements[idx]
            

            color = announcement.get('color', EMBED_COLOR_INFO)
            if isinstance(color, str):
                color = int(color, 16)
            
            embed = discord.Embed(
                title=announcement.get('title', 'Untitled'),
                description=announcement.get('description', 'No content'),
                color=color
            )
            

            scheduled_time = announcement.get('scheduled_time')
            if scheduled_time:
                embed.add_field(
                    name="Scheduled For",
                    value=scheduled_time.strftime("%Y-%m-%d %H:%M"),
                    inline=False
                )
            

            if announcement.get('image_url'):
                embed.set_image(url=announcement['image_url'])
            
            if announcement.get('thumbnail_url'):
                embed.set_thumbnail(url=announcement['thumbnail_url'])
            

            embed.set_footer(
                text=announcement.get('footer', 'DisAnnounce | ZygnalBot by TheHolyOneZ')
            )
            
            await select_interaction.response.send_message(
                "📢 **Announcement Preview:**",
                embed=embed,
                ephemeral=True
            )
        
        select.callback = select_callback
        

        view = discord.ui.View(timeout=60)
        view.add_item(select)
        
        await interaction.response.send_message(
            "Select an announcement to view:",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):


        select_options = []
        
        start_idx = self.current_page * self.announcements_per_page
        end_idx = min(start_idx + self.announcements_per_page, len(self.announcements))
        
        for i in range(start_idx, end_idx):
            announcement = self.announcements[i]
            select_options.append(
                discord.SelectOption(
                    label=f"{i+1}. {announcement.get('title', 'Untitled')}",
                    value=str(i),
                    description=f"Scheduled for: {announcement.get('scheduled_time').strftime('%Y-%m-%d %H:%M')}"
                )
            )
        
        if not select_options:
            await interaction.response.send_message(
                "❌ No announcements to cancel on this page.",
                ephemeral=True
            )
            return
        

        select = discord.ui.Select(
            placeholder="Select an announcement to cancel",
            options=select_options
        )
        
        async def select_callback(select_interaction):
            idx = int(select.values[0])
            announcement = self.announcements[idx]
            announcement_id = announcement.get('id')
            

            success = self.cog.announcement_manager.cancel_scheduled_announcement(announcement_id)
            
            if success:

                self.announcements.pop(idx)
                

                embed = self.create_embed()
                

                await interaction.message.edit(embed=embed, view=self)
                
                await select_interaction.response.send_message(
                    "✅ Announcement cancelled successfully!",
                    ephemeral=True
                )
            else:
                await select_interaction.response.send_message(
                    "❌ Failed to cancel the announcement.",
                    ephemeral=True
                )
        
        select.callback = select_callback
        

        view = discord.ui.View(timeout=60)
        view.add_item(select)
        
        await interaction.response.send_message(
            "⚠️ Select an announcement to cancel:",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):


        self.announcements = self.cog.announcement_manager.get_scheduled_announcements(self.guild_id)
        self.current_page = 0
        

        self.previous_button.disabled = True
        total_pages = (len(self.announcements) + self.announcements_per_page - 1) // self.announcements_per_page
        self.next_button.disabled = (total_pages <= 1)
        

        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)


class DisAnnounce(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.announcement_manager = AnnouncementManager()
        self.check_scheduled_announcements.start()
    
    def cog_unload(self):
        self.check_scheduled_announcements.cancel()
    
    @tasks.loop(minutes=1)
    async def check_scheduled_announcements(self):

        try:
            due_announcements = self.announcement_manager.get_due_announcements()
            
            for announcement in due_announcements:
                await self.send_announcement(announcement)
        except Exception as e:
            print(f"Error checking scheduled announcements: {e}")
    
    @check_scheduled_announcements.before_loop
    async def before_check_scheduled_announcements(self):

        await self.bot.wait_until_ready()
    
    async def send_announcement(self, announcement_data):

        try:
            source_guild_id = announcement_data.get('source_guild_id')
            source_channel_id = announcement_data.get('source_channel_id')
            
            if not source_guild_id or not source_channel_id:
                return False, "Missing source guild or channel information"
                

            channel_key = f"{source_guild_id}:{source_channel_id}"
            subscribers = self.announcement_manager.channel_subscribers.get(channel_key, [])
            
            if not subscribers:
                return False, "No servers are subscribed to this announcement channel"
            

            color = announcement_data.get('color', EMBED_COLOR_NEUTRAL)
            if isinstance(color, str):
                color = int(color, 16)
            
            embed = discord.Embed(
                title=announcement_data.get('title', 'Announcement'),
                description=announcement_data.get('description', 'Your announcement content goes here.'),
                color=color,
                timestamp=datetime.datetime.now()
            )
            

            source_guild_name = announcement_data.get('source_guild_name', 'Unknown Server')
            author_name = announcement_data.get('author_name', 'Unknown')
            
            embed.set_author(
                name=f"Announcement from {source_guild_name}",
                icon_url=self.bot.user.display_avatar.url
            )
            

            if announcement_data.get('image_url'):
                embed.set_image(url=announcement_data['image_url'])
            
            if announcement_data.get('thumbnail_url'):
                embed.set_thumbnail(url=announcement_data['thumbnail_url'])
            

            embed.set_footer(
                text=announcement_data.get('footer', f"DisAnnounce | ZygnalBot by TheHolyOneZ")
            )
            

            sent_count = 0
            for subscriber_guild_id in subscribers:
                try:

                    if subscriber_guild_id not in self.announcement_manager.subscriptions:
                        continue
                        
                    subscriber_channel_id = self.announcement_manager.subscriptions[subscriber_guild_id]
                    
                    guild = self.bot.get_guild(int(subscriber_guild_id))
                    if not guild:
                        continue
                    
                    channel = guild.get_channel(int(subscriber_channel_id))
                    if not channel:
                        continue
                    
                    await channel.send(embed=embed)
                    sent_count += 1
                except Exception as e:
                    print(f"Error sending announcement to guild {subscriber_guild_id}: {e}")
            
            return True, sent_count
        except Exception as e:
            return False, str(e)
    
    @commands.group(name="disannounce", invoke_without_command=True)
    @commands.has_permissions(manage_channels=True)
    async def disannounce(self, ctx):

        embed = discord.Embed(
            title="DisAnnounce - Multi-Server Announcements",
            description="Send and manage announcements across multiple Discord servers.",
            color=EMBED_COLOR_NEUTRAL
        )
        
        embed.add_field(
            name="Basic Commands",
            value=(
                "• `!disannounce create` - Create a new announcement\n"
                "• `!disannounce register` - Register a channel for announcements\n"
                "• `!disannounce subscribe <guild_id> <channel_id>` - Subscribe to announcements\n"
                "• `!disannounce unsubscribe <guild_id> <channel_id>` - Unsubscribe from announcements\n"
                "• `!disannounce scheduled` - View scheduled announcements"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Advanced Commands",
            value=(
                "• `!disannounce template` - Manage announcement templates\n"
                "• `!disannounce status` - Check subscription status\n"
                "• `!disannounce list` - List available announcement channels"
            ),
            inline=False
        )
        
        embed.set_footer(text="ZygnalBot by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @disannounce.command(name="create")
    @commands.has_permissions(administrator=True)
    async def create_announcement(self, ctx):


        if str(ctx.guild.id) not in self.announcement_manager.announcement_channels:
            embed = discord.Embed(
                title="Error",
                description="❌ You need to register an announcement channel first using `!disannounce register`.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
            

        channel_info = self.announcement_manager.announcement_channels[str(ctx.guild.id)]
        channel_id = int(channel_info["channel_id"])
        

        if ctx.channel.id != channel_id:
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="Error",
                    description=f"❌ Announcements can only be created in the registered channel: {channel.mention}",
                    color=EMBED_COLOR_ERROR
                )
                embed.set_footer(text="ZygnalBot by TheHolyOneZ")
                await ctx.send(embed=embed)
                return
        

        view = AnnouncementView(self)
        

        view.announcement_data['source_guild_id'] = str(ctx.guild.id)
        view.announcement_data['source_guild_name'] = ctx.guild.name
        view.announcement_data['source_channel_id'] = str(ctx.channel.id)
        view.announcement_data['author_id'] = str(ctx.author.id)
        view.announcement_data['author_name'] = ctx.author.display_name
        

        template = self.announcement_manager.get_template(ctx.guild.id)
        if template:
            view.announcement_data.update(template)
        

        embed = view.create_preview_embed()
        

        await ctx.send(
            "📢 **Announcement Creator**\nUse the buttons below to customize your announcement:",
            embed=embed,
            view=view
        )
    
    @disannounce.command(name="register")
    @commands.has_permissions(administrator=True)
    async def register(self, ctx, channel: discord.TextChannel = None):

        if not channel:
            channel = ctx.channel
        

        if not channel.permissions_for(ctx.guild.me).send_messages or not channel.permissions_for(ctx.guild.me).embed_links:
            embed = discord.Embed(
                title="Error",
                description="❌ I don't have permission to send messages or embed links in that channel.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        

        success = self.announcement_manager.register_announcement_channel(
            ctx.guild.id, channel.id, channel.name
        )
        
        if success:
            embed = discord.Embed(
                title="DisAnnounce - Channel Registered",
                description=f"✅ Successfully registered {channel.mention} as an announcement channel!",
                color=EMBED_COLOR_SUCCESS
            )
            embed.add_field(
                name="What's Next?",
                value=(
                    "• Other servers can now subscribe to your announcements\n"
                    "• Use `!disannounce create` in this channel to create announcements\n"
                    "• Share your server ID and channel ID with other servers so they can subscribe"
                ),
                inline=False
            )
            embed.add_field(
                name="Your Channel Information",
                value=f"Server ID: `{ctx.guild.id}`\nChannel ID: `{channel.id}`",
                inline=False
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Error",
                description="❌ Failed to register announcement channel.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
    
    @disannounce.command(name="unregister")
    @commands.has_permissions(administrator=True)
    async def unregister(self, ctx):


        success = self.announcement_manager.unregister_announcement_channel(ctx.guild.id)
        
        if success:
            embed = discord.Embed(
                title="DisAnnounce - Channel Unregistered",
                description="✅ Successfully unregistered your announcement channel.",
                color=EMBED_COLOR_SUCCESS
            )
            embed.add_field(
                name="Note",
                value="Other servers will no longer receive announcements from this server.",
                inline=False
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Error",
                description="❌ This server doesn't have a registered announcement channel.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
    
    @disannounce.command(name="subscribe")
    @commands.has_permissions(administrator=True)
    async def subscribe(self, ctx, source_guild_id: int, source_channel_id: int, channel: discord.TextChannel = None):

        if not channel:
            channel = ctx.channel
        

        if not channel.permissions_for(ctx.guild.me).send_messages or not channel.permissions_for(ctx.guild.me).embed_links:
            embed = discord.Embed(
                title="Error",
                description="❌ I don't have permission to send messages or embed links in that channel.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        

        channel_key = f"{source_guild_id}:{source_channel_id}"
        source_guild_id_str = str(source_guild_id)
        
        if source_guild_id_str not in self.announcement_manager.announcement_channels:
            embed = discord.Embed(
                title="Error",
                description="❌ The specified server doesn't have a registered announcement channel.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        

        success = self.announcement_manager.subscribe_to_channel(
            source_guild_id, source_channel_id,
            ctx.guild.id, channel.id
        )
        
        if success:
            source_guild_name = "Unknown Server"
            source_guild = self.bot.get_guild(source_guild_id)
            if source_guild:
                source_guild_name = source_guild.name
            
            embed = discord.Embed(
                title="DisAnnounce - Subscription",
                description=f"✅ Successfully subscribed to announcements from {source_guild_name}!",
                color=EMBED_COLOR_SUCCESS
            )
            embed.add_field(
                name="Subscription Details",
                value=f"You will receive announcements in {channel.mention}",
                inline=False
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Error",
                description="❌ Failed to subscribe to announcements.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
    
    @disannounce.command(name="unsubscribe")
    @commands.has_permissions(administrator=True)
    async def unsubscribe(self, ctx, source_guild_id: int = None, source_channel_id: int = None):

        if source_guild_id is None or source_channel_id is None:

            success = self.announcement_manager.unsubscribe_from_all(ctx.guild.id)
            
            if success:
                embed = discord.Embed(
                    title="DisAnnounce - Unsubscribed",
                    description="✅ Successfully unsubscribed from all announcement channels.",
                    color=EMBED_COLOR_SUCCESS
                )
                embed.set_footer(text="ZygnalBot by TheHolyOneZ")
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="Error",
                    description="❌ This server is not subscribed to any announcement channels.",
                    color=EMBED_COLOR_ERROR
                )
                embed.set_footer(text="ZygnalBot by TheHolyOneZ")
                await ctx.send(embed=embed)
        else:

            success = self.announcement_manager.unsubscribe_from_channel(
                source_guild_id, source_channel_id, ctx.guild.id
            )
            
            if success:
                source_guild_name = "Unknown Server"
                source_guild = self.bot.get_guild(source_guild_id)
                if source_guild:
                    source_guild_name = source_guild.name
                
                embed = discord.Embed(
                    title="DisAnnounce - Unsubscribed",
                    description=f"✅ Successfully unsubscribed from announcements from {source_guild_name}.",
                    color=EMBED_COLOR_SUCCESS
                )
                embed.set_footer(text="ZygnalBot by TheHolyOneZ")
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="Error",
                    description="❌ This server is not subscribed to the specified announcement channel.",
                    color=EMBED_COLOR_ERROR
                )
                embed.set_footer(text="ZygnalBot by TheHolyOneZ")
                await ctx.send(embed=embed)
    
    @disannounce.command(name="list")
    @commands.has_permissions(manage_channels=True)
    async def list_channels(self, ctx):


        channels = self.announcement_manager.announcement_channels
        
        if not channels:
            embed = discord.Embed(
                title="DisAnnounce - Available Channels",
                description="No announcement channels are currently registered.",
                color=EMBED_COLOR_NEUTRAL
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="DisAnnounce - Available Channels",
            description="Here are the announcement channels you can subscribe to:",
            color=EMBED_COLOR_INFO
        )
        
        for guild_id, channel_info in channels.items():
            guild_name = "Unknown Server"
            guild = self.bot.get_guild(int(guild_id))
            if guild:
                guild_name = guild.name
            

            channel_key = f"{guild_id}:{channel_info['channel_id']}"
            is_subscribed = str(ctx.guild.id) in self.announcement_manager.channel_subscribers.get(channel_key, [])
            
            embed.add_field(
                name=f"{guild_name} {' ✅' if is_subscribed else ''}",
                value=(
                    f"Channel: #{channel_info['channel_name']}\n"
                    f"Server ID: `{guild_id}`\n"
                    f"Channel ID: `{channel_info['channel_id']}`\n"
                    f"Status: {'Subscribed' if is_subscribed else 'Not Subscribed'}"
                ),
                inline=False
            )
        
        embed.add_field(
            name="How to Subscribe",
            value="Use `!disannounce subscribe <server_id> <channel_id>` to subscribe to a channel.",
            inline=False
        )
        
        embed.set_footer(text="ZygnalBot by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @disannounce.command(name="status")
    @commands.has_permissions(manage_channels=True)
    async def status(self, ctx):

        embed = discord.Embed(
            title="DisAnnounce - Status",
            description="Your current DisAnnounce configuration:",
            color=EMBED_COLOR_INFO
        )
        

        if str(ctx.guild.id) in self.announcement_manager.announcement_channels:
            channel_info = self.announcement_manager.announcement_channels[str(ctx.guild.id)]
            channel_id = int(channel_info["channel_id"])
            channel = ctx.guild.get_channel(channel_id)
            
            if channel:
                embed.add_field(
                    name="Registered Announcement Channel",
                    value=f"{channel.mention} (ID: {channel.id})",
                    inline=False
                )
                

                channel_key = f"{ctx.guild.id}:{channel.id}"
                subscribers = self.announcement_manager.channel_subscribers.get(channel_key, [])
                
                embed.add_field(
                    name="Subscribers",
                    value=f"{len(subscribers)} servers are subscribed to your announcements",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Registered Announcement Channel",
                    value=f"Channel ID: {channel_id} (not found)",
                    inline=False
                )
        else:
            embed.add_field(
                name="Registered Announcement Channel",
                value="None - Use `!disannounce register` to register a channel",
                inline=False
            )
        

        subscribed_channels = self.announcement_manager.get_subscribed_channels(ctx.guild.id)
        
        if subscribed_channels:
            channels_text = ""
            for channel_info in subscribed_channels:
                guild_id = channel_info["guild_id"]
                guild_name = "Unknown Server"
                
                guild = self.bot.get_guild(int(guild_id))
                if guild:
                    guild_name = guild.name
                
                channels_text += f"• {guild_name} (Server ID: {guild_id}, Channel: #{channel_info['channel_name']})\n"
            
            embed.add_field(
                name=f"Subscribed To ({len(subscribed_channels)})",
                value=channels_text or "None",
                inline=False
            )
        else:
            embed.add_field(
                name="Subscribed To",
                value="None - Use `!disannounce subscribe <server_id> <channel_id>` to subscribe",
                inline=False
            )
        

        template = self.announcement_manager.get_template(ctx.guild.id)
        if template:
            embed.add_field(
                name="Announcement Template",
                value="✅ This server has a custom announcement template",
                inline=False
            )
        else:
            embed.add_field(
                name="Announcement Template",
                value="❌ No custom template set - Use `!disannounce template create` to create one",
                inline=False
            )
        

        if str(ctx.guild.id) in self.announcement_manager.subscriptions:
            channel_id = int(self.announcement_manager.subscriptions[str(ctx.guild.id)])
            channel = ctx.guild.get_channel(channel_id)
            
            if channel:
                embed.add_field(
                    name="Subscription Channel",
                    value=f"You will receive announcements in {channel.mention}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Subscription Channel",
                    value=f"Channel ID: {channel_id} (not found)",
                    inline=False
                )
        
        embed.set_footer(text="ZygnalBot by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @disannounce.command(name="scheduled")
    @commands.has_permissions(manage_channels=True)
    async def scheduled(self, ctx):


        announcements = self.announcement_manager.get_scheduled_announcements(ctx.guild.id)
        

        view = ScheduledAnnouncementsView(self, ctx.guild.id, announcements)
        

        embed = view.create_embed()
        

        view.previous_button.disabled = True  # Start at page 0
        view.next_button.disabled = (len(announcements) <= 4)  # Disable if all fit on one page
        
        await ctx.send(embed=embed, view=view)
    
    @disannounce.group(name="template", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def template(self, ctx):

        embed = discord.Embed(
            title="DisAnnounce - Template Management",
            description="Manage your server's announcement templates.",
            color=EMBED_COLOR_NEUTRAL
        )
        
        embed.add_field(
            name="Commands",
            value=(
                "• `!disannounce template create` - Create a new template\n"
                "• `!disannounce template view` - View your current template\n"
                "• `!disannounce template delete` - Delete your template"
            ),
            inline=False
        )
        
        embed.set_footer(text="ZygnalBot by TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @template.command(name="create")
    async def template_create(self, ctx):


        view = AnnouncementView(self)
        

        template = self.announcement_manager.get_template(ctx.guild.id)
        if template:
            view.announcement_data.update(template)
        

        embed = view.create_preview_embed()
        

        await ctx.send(
            "📝 **Template Creator**\nUse the buttons below to customize your announcement template:",
            embed=embed,
            view=view
        )
    
    @template.command(name="view")
    async def template_view(self, ctx):


        template = self.announcement_manager.get_template(ctx.guild.id)
        
        if not template:
            embed = discord.Embed(
                title="DisAnnounce - Template",
                description="❌ This server doesn't have a template.",
                color=EMBED_COLOR_ERROR
            )
            embed.add_field(
                name="Create a Template",
                value="Use `!disannounce template create` to create a template.",
                inline=False
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        

        color = int(template['color'], 16) if isinstance(template['color'], str) else template['color']
        
        embed = discord.Embed(
            title=template['title'],
            description=template['description'],
            color=color
        )
        
        if template.get('image_url'):
            embed.set_image(url=template['image_url'])
        
        if template.get('thumbnail_url'):
            embed.set_thumbnail(url=template['thumbnail_url'])
        
        embed.set_footer(text=template.get('footer', 'DisAnnounce | ZygnalBot by TheHolyOneZ'))
        
        await ctx.send("📝 **Your Announcement Template:**", embed=embed)
    
    @template.command(name="delete")
    async def template_delete(self, ctx):


        template = self.announcement_manager.get_template(ctx.guild.id)
        
        if not template:
            embed = discord.Embed(
                title="DisAnnounce - Template",
                description="❌ This server doesn't have a template to delete.",
                color=EMBED_COLOR_ERROR
            )
            embed.set_footer(text="ZygnalBot by TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        

        self.announcement_manager.announcement_templates.pop(str(ctx.guild.id), None)
        self.announcement_manager.save_config()
        
        embed = discord.Embed(
            title="DisAnnounce - Template Deleted",
            description="✅ Your announcement template has been deleted.",
            color=EMBED_COLOR_SUCCESS
        )
        embed.set_footer(text="ZygnalBot by TheHolyOneZ")
        await ctx.send(embed=embed)


def setup(bot):

    cog = DisAnnounce(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog



