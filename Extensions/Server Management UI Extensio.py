import discord
from discord.ext import commands
import asyncio
from discord import ui, ButtonStyle, SelectOption
from datetime import datetime, timedelta
import json
import os
import logging


logger = logging.getLogger('server_management')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

class ChannelCreationView(ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
        
    @ui.select(
        placeholder="Select channel type",
        options=[
            SelectOption(label="Text Channel", value="text", description="Create a text channel"),
            SelectOption(label="Voice Channel", value="voice", description="Create a voice channel"),
            SelectOption(label="Category", value="category", description="Create a category")
        ]
    )
    async def channel_type_select(self, interaction: discord.Interaction, select: ui.Select):
        self.channel_type = select.values[0]
        await interaction.response.send_modal(ChannelNameModal(self.cog, self.channel_type))

class ChannelNameModal(ui.Modal, title="Create Channel"):
    def __init__(self, cog, channel_type):
        super().__init__()
        self.cog = cog
        self.channel_type = channel_type
        
    name = ui.TextInput(label="Channel Name", placeholder="Enter channel name", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        channel_name = self.name.value
        
        try:
            if self.channel_type == "text":
                await guild.create_text_channel(channel_name)
            elif self.channel_type == "voice":
                await guild.create_voice_channel(channel_name)
            elif self.channel_type == "category":
                await guild.create_category(channel_name)
                
            await interaction.response.send_message(f"✅ {self.channel_type.capitalize()} channel '{channel_name}' created successfully!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to create channels.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error creating channel: {str(e)}", ephemeral=True)

class PermissionManagementView(ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
        self.selected_channel = None
        self.selected_role = None
        
    async def update_channel_select(self, interaction):

        for item in self.children[:]:
            if isinstance(item, ui.Select) and item.custom_id == "channel_select":
                self.remove_item(item)
        

        channel_options = []
        for channel in interaction.guild.channels:
            if len(channel_options) < 25:
                channel_options.append(SelectOption(
                    label=channel.name[:25],
                    value=str(channel.id),
                    description=f"{str(channel.type).replace('_', ' ').title()} channel"[:50]
                ))
        
        channel_select = ui.Select(
            placeholder="Select a channel",
            custom_id="channel_select",
            options=channel_options
        )
        
        async def channel_select_callback(interaction: discord.Interaction):
            self.selected_channel = interaction.guild.get_channel(int(channel_select.values[0]))
            await self.update_role_select(interaction)
            
        channel_select.callback = channel_select_callback
        self.add_item(channel_select)
        
        if isinstance(interaction, discord.Interaction):
            await interaction.response.edit_message(view=self)
        else:

            await interaction.message.edit(view=self)
        
    async def update_role_select(self, interaction):

        for item in self.children[:]:
            if isinstance(item, ui.Select) and item.custom_id == "role_select":
                self.remove_item(item)
        

        role_options = []
        for role in interaction.guild.roles:
            if not role.is_default() and len(role_options) < 24:
                role_options.append(SelectOption(
                    label=role.name[:25],
                    value=str(role.id),
                    description=f"Role with {len([p for p in role.permissions if p[1]])} permissions"[:50]
                ))
        

        role_options.append(SelectOption(
            label="@everyone",
            value=str(interaction.guild.default_role.id),
            description="Default role for all members"
        ))
        
        role_select = ui.Select(
            placeholder="Select a role",
            custom_id="role_select",
            options=role_options
        )
        
        async def role_select_callback(interaction: discord.Interaction):
            self.selected_role = interaction.guild.get_role(int(role_select.values[0]))
            await self.show_permission_editor(interaction)
            
        role_select.callback = role_select_callback
        self.add_item(role_select)
        await interaction.response.edit_message(view=self)
    
    async def show_permission_editor(self, interaction):

        perm_view = PermissionEditorView(self.cog, self.selected_channel, self.selected_role)
        await interaction.response.edit_message(
            content=f"Editing permissions for role **{self.selected_role.name}** in channel **{self.selected_channel.name}**",
            view=perm_view
        )

class PermissionEditorView(ui.View):
    def __init__(self, cog, channel, role):
        super().__init__(timeout=300)
        self.cog = cog
        self.channel = channel
        self.role = role
        self.add_permission_buttons()
        
    def add_permission_buttons(self):

        permissions = [
            ("Read Messages", "view_channel"),
            ("Send Messages", "send_messages"),
            ("Manage Messages", "manage_messages"),
            ("Embed Links", "embed_links"),
            ("Attach Files", "attach_files"),
            ("Read History", "read_message_history"),
            ("Add Reactions", "add_reactions"),
            ("Use External Emojis", "use_external_emojis"),
            ("Mention Everyone", "mention_everyone"),
            ("Connect", "connect"),
            ("Speak", "speak"),
            ("Manage Channel", "manage_channels")
        ]
        
        for i, (label, perm_name) in enumerate(permissions):

            current_value = self.get_permission_value(perm_name, self.channel.overwrites_for(self.role))
            
            if current_value is True:
                style = ButtonStyle.success
            elif current_value is False:
                style = ButtonStyle.danger
            else:
                style = ButtonStyle.secondary
                
            button = ui.Button(
                label=label,
                custom_id=f"perm_{perm_name}",
                style=style,
                row=i // 3
            )
            

            def make_callback(button, perm):
                async def button_callback(interaction):
                    try:

                        await interaction.response.defer(ephemeral=False)
                        

                        overwrite = self.channel.overwrites_for(self.role)
                        current_value = self.get_permission_value(perm, overwrite)
                        

                        if current_value is True:
                            setattr(overwrite, perm, False)
                            button.style = ButtonStyle.danger
                        elif current_value is False:
                            setattr(overwrite, perm, None)
                            button.style = ButtonStyle.secondary
                        else:
                            setattr(overwrite, perm, True)
                            button.style = ButtonStyle.success
                        

                        await self.channel.set_permissions(self.role, overwrite=overwrite)
                        

                        await interaction.edit_original_response(view=self)
                    except Exception as e:

                        print(f"Error in permission button callback: {e}")
                
                return button_callback

            

            button.callback = make_callback(button, perm_name)
            self.add_item(button)    
    def has_permission(self, perm_name):
        overwrite = self.channel.overwrites_for(self.role)
        return self.get_permission_value(perm_name, overwrite) is True
    
    def get_permission_value(self, perm_name, overwrite):
        if hasattr(overwrite, perm_name):
            return getattr(overwrite, perm_name)
        return None

class ScheduleChannelView(ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
        self.selected_channel = None
        self.action = "open"
        
    @ui.select(
        placeholder="Select action",
        options=[
            SelectOption(label="Open Channel", value="open", description="Schedule when to open a channel"),
            SelectOption(label="Close Channel", value="close", description="Schedule when to close a channel")
        ]
    )
    async def action_select(self, interaction: discord.Interaction, select: ui.Select):
        self.action = select.values[0]
        await self.update_channel_select(interaction)
    
    async def update_channel_select(self, interaction):

        for item in self.children[:]:
            if isinstance(item, ui.Select) and item.custom_id == "channel_select":
                self.remove_item(item)
        

        channel_options = []
        for channel in interaction.guild.channels:
            if not isinstance(channel, discord.CategoryChannel) and len(channel_options) < 25:
                channel_options.append(SelectOption(
                    label=channel.name[:25],
                    value=str(channel.id),
                    description=f"{str(channel.type).replace('_', ' ').title()} channel"[:50]
                ))
        
        channel_select = ui.Select(
            placeholder="Select a channel",
            custom_id="channel_select",
            options=channel_options
        )
        
        async def channel_select_callback(interaction: discord.Interaction):
            self.selected_channel = interaction.guild.get_channel(int(channel_select.values[0]))
            await interaction.response.send_modal(ScheduleTimeModal(self.cog, self.selected_channel, self.action))
            
        channel_select.callback = channel_select_callback
        self.add_item(channel_select)
        await interaction.response.edit_message(view=self)

class ScheduleTimeModal(ui.Modal, title="Schedule Channel Action"):
    def __init__(self, cog, channel, action):
        super().__init__()
        self.cog = cog
        self.channel = channel
        self.action = action
        
    date = ui.TextInput(
        label="Date (YYYY-MM-DD)",
        placeholder="e.g., 2023-12-31",
        required=True
    )
    
    time = ui.TextInput(
        label="Time (HH:MM)",
        placeholder="e.g., 14:30 (24-hour format)",
        required=True
    )
    
    reason = ui.TextInput(
        label="Reason (Optional)",
        placeholder="Why is this channel being opened/closed?",
        required=False,
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:

            date_str = self.date.value
            time_str = self.time.value
            scheduled_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            

            schedule_data = {
                "channel_id": self.channel.id,
                "action": self.action,
                "scheduled_time": scheduled_time.isoformat(),
                "guild_id": interaction.guild.id,
                "created_by": interaction.user.id,
                "reason": self.reason.value if self.reason.value else None
            }
            

            self.cog.schedules.append(schedule_data)
            self.cog.save_schedules()
            

            self.cog.start_schedule_task(schedule_data)
            
            action_text = "opened" if self.action == "open" else "closed"
            embed = discord.Embed(
                title="Channel Schedule Created",
                description=f"Channel **{self.channel.name}** will be **{action_text}** on **{date_str}** at **{time_str}**",
                color=discord.Color.green()
            )
            
            if self.reason.value:
                embed.add_field(name="Reason", value=self.reason.value)
                
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid date or time format. Please use YYYY-MM-DD for date and HH:MM for time.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error scheduling channel action: {str(e)}",
                ephemeral=True
            )

class CancelScheduleView(ui.View):
    def __init__(self, cog, schedules):
        super().__init__(timeout=300)
        self.cog = cog
        self.schedules = schedules
        self.add_schedule_select()
        
    def add_schedule_select(self):
        options = []
        for i, schedule in enumerate(self.schedules):
            channel_id = schedule['channel_id']
            channel = self.cog.bot.get_channel(channel_id)
            channel_name = channel.name if channel else f"Unknown ({channel_id})"
            
            scheduled_time = datetime.fromisoformat(schedule['scheduled_time']).strftime("%Y-%m-%d %H:%M")
            action = "Open" if schedule['action'] == 'open' else "Close"
            
            options.append(SelectOption(
                label=f"{action} {channel_name}",
                value=str(i),
                description=f"Scheduled for {scheduled_time}"[:50]
            ))
        
        select = ui.Select(
            placeholder="Select a schedule to cancel",
            options=options
        )
        
        async def select_callback(interaction: discord.Interaction):
            index = int(select.values[0])
            schedule = self.schedules[index]
            

            self.cog.schedules.remove(schedule)
            self.cog.save_schedules()
            

            task_id = f"{schedule['guild_id']}_{schedule['channel_id']}_{schedule['action']}"
            if task_id in self.cog.schedule_tasks:
                self.cog.schedule_tasks[task_id].cancel()
                del self.cog.schedule_tasks[task_id]
            

            channel = interaction.guild.get_channel(schedule['channel_id'])
            channel_name = channel.name if channel else f"Unknown Channel ({schedule['channel_id']})"
            scheduled_time = datetime.fromisoformat(schedule['scheduled_time']).strftime("%Y-%m-%d %H:%M")
            action = "open" if schedule['action'] == 'open' else "close"
            
            embed = discord.Embed(
                title="Schedule Cancelled",
                description=f"The scheduled action to **{action}** channel **{channel_name}** at **{scheduled_time}** has been cancelled.",
                color=discord.Color.red()
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        select.callback = select_callback
        self.add_item(select)

class AutomatedChannelView(ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
        self.selected_role = None
        self.channel_type = "text"
        self.selected_category = None
        
    @ui.select(
        placeholder="Select channel type",
        options=[
            SelectOption(label="Text Channel", value="text", description="Create a text channel"),
            SelectOption(label="Voice Channel", value="voice", description="Create a voice channel")
        ]
    )
    async def channel_type_select(self, interaction: discord.Interaction, select: ui.Select):
        self.channel_type = select.values[0]
        await self.update_category_select(interaction)
    
    async def update_category_select(self, interaction):

        for item in self.children[:]:
            if isinstance(item, ui.Select) and item.custom_id == "category_select":
                self.remove_item(item)
        

        category_options = [
            SelectOption(label="No Category", value="0", description="Don't place in any category")
        ]
        
        for category in interaction.guild.categories:
            if len(category_options) < 25:
                category_options.append(SelectOption(
                    label=category.name[:25],
                    value=str(category.id)
                ))
        
        category_select = ui.Select(
            placeholder="Select a category (optional)",
            custom_id="category_select",
            options=category_options
        )
        
        async def category_select_callback(interaction: discord.Interaction):
            category_id = int(category_select.values[0])
            self.selected_category = interaction.guild.get_channel(category_id) if category_id != 0 else None
            await self.update_role_select(interaction)
            
        category_select.callback = category_select_callback
        self.add_item(category_select)
        await interaction.response.edit_message(view=self)
    
    async def update_role_select(self, interaction):

        for item in self.children[:]:
            if isinstance(item, ui.Select) and item.custom_id == "role_select":
                self.remove_item(item)
        

        role_options = []
        for role in interaction.guild.roles:
            if not role.is_default() and len(role_options) < 25:
                role_options.append(SelectOption(
                    label=role.name[:25],
                    value=str(role.id)
                ))
        
        role_select = ui.Select(
            placeholder="Select a role",
            custom_id="role_select",
            options=role_options
        )
        
        async def role_select_callback(interaction: discord.Interaction):
            self.selected_role = interaction.guild.get_role(int(role_select.values[0]))
            await interaction.response.send_modal(AutomatedChannelModal(
                self.cog, 
                self.channel_type, 
                self.selected_role,
                self.selected_category
            ))
            
        role_select.callback = role_select_callback
        self.add_item(role_select)
        await interaction.response.edit_message(view=self)

class AutomatedChannelModal(ui.Modal, title="Create Role Channel"):
    def __init__(self, cog, channel_type, role, category=None):
        super().__init__()
        self.cog = cog
        self.channel_type = channel_type
        self.role = role
        self.category = category
        
    name = ui.TextInput(
        label="Channel Name",
        placeholder="Enter channel name (use {role} to include role name)",
        required=True
    )
    
    topic = ui.TextInput(
        label="Channel Topic (Text channels only)",
        placeholder="Enter channel topic or description",
        required=False,
        max_length=1024
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        channel_name = self.name.value.replace("{role}", self.role.name)
        
        try:

            if self.channel_type == "text":
                channel = await guild.create_text_channel(
                    name=channel_name,
                    category=self.category,
                    topic=self.topic.value if self.topic.value else None
                )
            else:
                channel = await guild.create_voice_channel(
                    name=channel_name,
                    category=self.category
                )
            


            await channel.set_permissions(self.role, view_channel=True, send_messages=True)
            

            await channel.set_permissions(guild.default_role, view_channel=False)
            

            guild_id = str(guild.id)
            if guild_id not in self.cog.automated_channels:
                self.cog.automated_channels[guild_id] = []
                
            self.cog.automated_channels[guild_id].append({
                "channel_id": channel.id,
                "role_id": self.role.id,
                "channel_type": self.channel_type,
                "created_at": datetime.now().isoformat()
            })
            
            self.cog.save_automated_channels()
            
            embed = discord.Embed(
                title="Role Channel Created",
                description=f"Created {self.channel_type} channel **{channel_name}** for role **{self.role.name}**",
                color=discord.Color.green()
            )
            
            if self.category:
                embed.add_field(name="Category", value=self.category.name)
                
            if self.channel_type == "text" and self.topic.value:
                embed.add_field(name="Topic", value=self.topic.value)
                
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to create channels.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error creating channel: {str(e)}", ephemeral=True)

class MaintenanceModeView(ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
        
    @ui.button(label="Activate Maintenance Mode", style=ButtonStyle.danger, custom_id="activate_maintenance")
    async def activate_maintenance(self, interaction: discord.Interaction, button: ui.Button):

        await interaction.response.defer(ephemeral=True)
        

        if not hasattr(self.cog, 'maintenance_backup'):
            self.cog.maintenance_backup = {}
        
        guild = interaction.guild
        

        await interaction.followup.send(
            "Please select which channels should remain accessible during maintenance:",
            view=EssentialChannelsView(self.cog, guild),
            ephemeral=True
        )
    
    @ui.button(label="Deactivate Maintenance Mode", style=ButtonStyle.success, custom_id="deactivate_maintenance")
    async def deactivate_maintenance(self, interaction: discord.Interaction, button: ui.Button):

        await interaction.response.defer(ephemeral=True)
        
        if not hasattr(self.cog, 'maintenance_backup') or not self.cog.maintenance_backup:
            await interaction.followup.send("❌ Maintenance mode is not active.", ephemeral=True)
            return
        

        try:
            guild_id = str(interaction.guild.id)
            if guild_id not in self.cog.maintenance_backup:
                await interaction.followup.send("❌ No maintenance backup found for this server.", ephemeral=True)
                return
                

            class ConfirmView(ui.View):
                def __init__(self, cog):
                    super().__init__(timeout=60)
                    self.cog = cog
                
                @ui.button(label="Confirm", style=ButtonStyle.success)
                async def confirm(self, i: discord.Interaction, b: ui.Button):
                    await i.response.defer(ephemeral=True)
                    
                    try:
                        guild = i.guild
                        guild_id = str(guild.id)
                        backup = self.cog.maintenance_backup[guild_id]
                        

                        for channel_id, role_permissions in backup.items():
                            channel = guild.get_channel(int(channel_id))
                            if not channel:
                                continue
                                
                            for role_id, permissions in role_permissions.items():
                                role = guild.get_role(int(role_id))
                                if not role:
                                    continue
                                    

                                overwrite = discord.PermissionOverwrite(**permissions)
                                await channel.set_permissions(role, overwrite=overwrite)
                        

                        del self.cog.maintenance_backup[guild_id]
                        self.cog.save_maintenance_backup()
                        
                        embed = discord.Embed(
                            title="Maintenance Mode Deactivated",
                            description="All channel permissions have been restored to their original state.",
                            color=discord.Color.green()
                        )
                        
                        await i.followup.send(embed=embed, ephemeral=True)
                        

                        log_channels = [c for c in guild.text_channels if 'log' in c.name.lower()]
                        if log_channels:
                            announce_embed = discord.Embed(
                                title="Server Maintenance Ended",
                                description="The server is now back to normal operation. All channels have been restored.",
                                color=discord.Color.green(),
                                timestamp=datetime.now()
                            )
                            await log_channels[0].send(embed=announce_embed)
                            
                    except Exception as e:

                        print(f"Error deactivating maintenance mode: {e}")
                        await i.followup.send(f"❌ Error deactivating maintenance mode: {str(e)}", ephemeral=True)
                
                @ui.button(label="Cancel", style=ButtonStyle.secondary)
                async def cancel(self, i: discord.Interaction, b: ui.Button):
                    await i.response.send_message("Maintenance mode deactivation cancelled.", ephemeral=True)
            

            embed = discord.Embed(
                title="Confirm Deactivation",
                description="Are you sure you want to deactivate maintenance mode and restore all channel permissions?",
                color=discord.Color.orange()
            )
            
            await interaction.followup.send(embed=embed, view=ConfirmView(self.cog), ephemeral=True)
            
        except Exception as e:

            print(f"Error in deactivate maintenance: {e}")
            await interaction.followup.send(f"❌ Error preparing to deactivate maintenance mode: {str(e)}", ephemeral=True)


class EssentialChannelsView(ui.View):
    def __init__(self, cog, guild):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.essential_channels = []
        self.add_channel_selects()
        
    def add_channel_selects(self):

        channels = [c for c in self.guild.channels if isinstance(c, (discord.TextChannel, discord.VoiceChannel))]
        

        for i in range(0, len(channels), 25):
            chunk = channels[i:i+25]
            options = [
                SelectOption(label=c.name[:25], value=str(c.id), description=f"{str(c.type).replace('_', ' ').title()} channel"[:50])
                for c in chunk
            ]
            
            select = ui.Select(
                placeholder=f"Select essential channels (group {i//25 + 1})",
                options=options,
                max_values=len(options),
                custom_id=f"essential_channels_{i//25}"
            )
            

            def make_callback(select_index):
                async def select_callback(interaction):
                    selected_values = interaction.data.get('values', [])
                    if selected_values:
                        self.essential_channels.extend([int(v) for v in selected_values])
                    

                    if interaction.data['custom_id'] == f"essential_channels_{(len(channels)-1)//25}":
                        await self.prepare_maintenance(interaction)
                    else:
                        await interaction.response.defer()
                
                return select_callback
            
            select.callback = make_callback(i//25)
            self.add_item(select)    
    async def prepare_maintenance(self, interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:

            class ConfirmView(ui.View):
                def __init__(self, parent_view):
                    super().__init__(timeout=60)
                    self.parent_view = parent_view
                
                @ui.button(label="Confirm", style=ButtonStyle.danger)
                async def confirm_button(self, i: discord.Interaction, b: ui.Button):
                    await i.response.defer(ephemeral=True)
                    await self.parent_view.activate_maintenance(i)
                
                @ui.button(label="Cancel", style=ButtonStyle.secondary)
                async def cancel_button(self, i: discord.Interaction, b: ui.Button):
                    await i.response.send_message("Maintenance mode activation cancelled.", ephemeral=True)
            

            essential_channels_text = ""
            for channel_id in self.essential_channels:
                channel = self.guild.get_channel(channel_id)
                if channel:
                    essential_channels_text += f"• {channel.name}\n"
            
            if not essential_channels_text:
                essential_channels_text = "None selected"
            
            embed = discord.Embed(
                title="Confirm Maintenance Mode",
                description="Are you sure you want to activate maintenance mode? This will hide all channels except the essential ones.",
                color=discord.Color.orange()
            )
            
            embed.add_field(name="Essential Channels", value=essential_channels_text[:1024])
            
            await interaction.followup.send(embed=embed, view=ConfirmView(self), ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error preparing maintenance mode: {e}")
            await interaction.followup.send(f"❌ Error preparing maintenance mode: {str(e)}", ephemeral=True)
    
    async def activate_maintenance(self, interaction):
        try:

            guild_id = str(self.guild.id)
            if guild_id not in self.cog.maintenance_backup:
                self.cog.maintenance_backup[guild_id] = {}
            

            embed = discord.Embed(
                title="Activating Maintenance Mode",
                description="Please wait while I configure channel permissions...",
                color=discord.Color.orange()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            

            channels_to_process = [c for c in self.guild.channels if 
                                  isinstance(c, (discord.TextChannel, discord.VoiceChannel)) and
                                  c.id not in self.essential_channels]
            
            for channel in channels_to_process:

                channel_backup = {}
                for target, overwrite in channel.overwrites.items():
                    if isinstance(target, discord.Role):
                        channel_backup[str(target.id)] = {k: v for k, v in overwrite._values.items() if v is not None}
                
                self.cog.maintenance_backup[guild_id][str(channel.id)] = channel_backup
                

                for role in self.guild.roles:
                    if role.permissions.administrator:
                        continue
                    await channel.set_permissions(role, view_channel=False)
            

            self.cog.save_maintenance_backup()
            

            success_embed = discord.Embed(
                title="Maintenance Mode Activated",
                description="Maintenance mode has been activated. Only essential channels are accessible.",
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            

            log_channels = [c for c in self.guild.text_channels if 'log' in c.name.lower()]
            if log_channels and log_channels[0].id in self.essential_channels:
                announce_embed = discord.Embed(
                    title="Server Maintenance Mode",
                    description="The server is now in maintenance mode. Only essential channels are accessible.",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                await log_channels[0].send(embed=announce_embed)
                
        except Exception as e:
            logger.error(f"Error activating maintenance mode: {e}")
            await interaction.followup.send(f"❌ Error activating maintenance mode: {str(e)}", ephemeral=True)

class ServerManagementUI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.schedules = []
        self.schedule_tasks = {}
        self.maintenance_backup = {}
        self.automated_channels = {}
        self.data_dir = "data/server_management"
        

        os.makedirs(self.data_dir, exist_ok=True)
        

        self.load_schedules()
        self.load_automated_channels()
        self.load_maintenance_backup()
        
    def load_schedules(self):
        try:
            path = f"{self.data_dir}/schedules.json"
            if os.path.exists(path):
                with open(path, 'r') as f:
                    self.schedules = json.load(f)
                    

                for schedule in self.schedules:
                    self.start_schedule_task(schedule)
                    
                logger.info(f"Loaded {len(self.schedules)} channel schedules")
        except Exception as e:
            logger.error(f"Error loading schedules: {e}")
    
    def save_schedules(self):
        try:
            path = f"{self.data_dir}/schedules.json"
            with open(path, 'w') as f:
                json.dump(self.schedules, f)
        except Exception as e:
            logger.error(f"Error saving schedules: {e}")
    
    def load_automated_channels(self):
        try:
            path = f"{self.data_dir}/automated_channels.json"
            if os.path.exists(path):
                with open(path, 'r') as f:
                    self.automated_channels = json.load(f)
                logger.info(f"Loaded automated channels for {len(self.automated_channels)} guilds")
        except Exception as e:
            logger.error(f"Error loading automated channels: {e}")
    
    def save_automated_channels(self):
        try:
            path = f"{self.data_dir}/automated_channels.json"
            with open(path, 'w') as f:
                json.dump(self.automated_channels, f)
        except Exception as e:
            logger.error(f"Error saving automated channels: {e}")
    
    def load_maintenance_backup(self):
        try:
            path = f"{self.data_dir}/maintenance_backup.json"
            if os.path.exists(path):
                with open(path, 'r') as f:
                    self.maintenance_backup = json.load(f)
                logger.info(f"Loaded maintenance backup for {len(self.maintenance_backup)} guilds")
        except Exception as e:
            logger.error(f"Error loading maintenance backup: {e}")
    
    def save_maintenance_backup(self):
        try:
            path = f"{self.data_dir}/maintenance_backup.json"
            with open(path, 'w') as f:
                json.dump(self.maintenance_backup, f)
        except Exception as e:
            logger.error(f"Error saving maintenance backup: {e}")
    
    def start_schedule_task(self, schedule):
        scheduled_time = datetime.fromisoformat(schedule['scheduled_time'])
        now = datetime.now()
        
        if scheduled_time > now:

            delta = (scheduled_time - now).total_seconds()
            

            task_id = f"{schedule['guild_id']}_{schedule['channel_id']}_{schedule['action']}"
            

            if task_id in self.schedule_tasks:
                self.schedule_tasks[task_id].cancel()
            

            self.schedule_tasks[task_id] = asyncio.create_task(self.execute_scheduled_action(schedule, delta))
    
    async def execute_scheduled_action(self, schedule, delay):
        await asyncio.sleep(delay)
        
        try:
            guild = self.bot.get_guild(schedule['guild_id'])
            if not guild:
                return
                
            channel = guild.get_channel(schedule['channel_id'])
            if not channel:
                return
                
            if schedule['action'] == 'open':

                await channel.set_permissions(guild.default_role, view_channel=True)
                

                if isinstance(channel, discord.TextChannel):
                    embed = discord.Embed(
                        title="Channel Opened",
                        description="This channel is now open to everyone.",
                        color=discord.Color.green(),
                        timestamp=datetime.now()
                    )
                    
                    if 'reason' in schedule and schedule['reason']:
                        embed.add_field(name="Reason", value=schedule['reason'])
                        
                    await channel.send(embed=embed)
            else:

                await channel.set_permissions(guild.default_role, view_channel=False)
                

                log_channels = [c for c in guild.text_channels if 'log' in c.name.lower()]
                if log_channels:
                    embed = discord.Embed(
                        title="Channel Closed",
                        description=f"Channel {channel.mention} has been closed as scheduled.",
                        color=discord.Color.red(),
                        timestamp=datetime.now()
                    )
                    
                    if 'reason' in schedule and schedule['reason']:
                        embed.add_field(name="Reason", value=schedule['reason'])
                        
                    await log_channels[0].send(embed=embed)
            

            self.schedules = [s for s in self.schedules if not (
                s['guild_id'] == schedule['guild_id'] and 
                s['channel_id'] == schedule['channel_id'] and 
                s['action'] == schedule['action'] and
                s['scheduled_time'] == schedule['scheduled_time']
            )]
            self.save_schedules()
            
        except Exception as e:
            logger.error(f"Error executing scheduled action: {e}")
        

        task_id = f"{schedule['guild_id']}_{schedule['channel_id']}_{schedule['action']}"
        if task_id in self.schedule_tasks:
            del self.schedule_tasks[task_id]
    
    @commands.group(name="server", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def server_management(self, ctx):

        embed = discord.Embed(
            title="Server Management Dashboard",
            description="Use the following commands to manage your server:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Channel Management",
            value="`!server create` - Create new channels\n"
                  "`!server permissions` - Manage channel permissions\n"
                  "`!server automated` - Create role-specific channels",
            inline=False
        )
        
        embed.add_field(
            name="Scheduling",
            value="`!server schedule` - Schedule channel opening/closing\n"
                  "`!server schedules` - View all scheduled actions\n"
                  "`!server cancel` - Cancel a scheduled action",
            inline=False
        )
        
        embed.add_field(
            name="Maintenance",
            value="`!server maintenance` - Toggle maintenance mode",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @server_management.command(name="create")
    @commands.has_permissions(manage_channels=True)
    async def create_channel(self, ctx):

        view = ChannelCreationView(self)
        await ctx.send("Select the type of channel you want to create:", view=view)
    
    @server_management.command(name="permissions")
    @commands.has_permissions(manage_permissions=True)
    async def manage_permissions(self, ctx):

        view = PermissionManagementView(self)
        message = await ctx.send("Loading permission management...", view=view)
        

        class CustomInteraction:
            def __init__(self, message, guild):
                self.message = message
                self.guild = guild
                
        await view.update_channel_select(CustomInteraction(message, ctx.guild))
    
    @server_management.command(name="schedule")
    @commands.has_permissions(manage_channels=True)
    async def schedule_channel(self, ctx):

        view = ScheduleChannelView(self)
        await ctx.send("Schedule channel actions:", view=view)
    
    @server_management.command(name="schedules")
    @commands.has_permissions(manage_channels=True)
    async def list_schedules(self, ctx):

        guild_schedules = [s for s in self.schedules if s['guild_id'] == ctx.guild.id]
        
        if not guild_schedules:
            await ctx.send("No scheduled actions for this server.")
            return
        
        embed = discord.Embed(
            title="Scheduled Channel Actions",
            description="Here are all the scheduled channel actions for this server:",
            color=discord.Color.blue()
        )
        
        for i, schedule in enumerate(guild_schedules, 1):
            channel = ctx.guild.get_channel(schedule['channel_id'])
            channel_name = channel.name if channel else "Unknown Channel"
            scheduled_time = datetime.fromisoformat(schedule['scheduled_time']).strftime("%Y-%m-%d %H:%M")
            action = "Open" if schedule['action'] == 'open' else "Close"
            
            value = f"Scheduled for: {scheduled_time}"
            if 'reason' in schedule and schedule['reason']:
                value += f"\nReason: {schedule['reason']}"
                
            embed.add_field(
                name=f"{i}. {action} {channel_name}",
                value=value,
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @server_management.command(name="cancel")
    @commands.has_permissions(manage_channels=True)
    async def cancel_schedule(self, ctx):

        guild_schedules = [s for s in self.schedules if s['guild_id'] == ctx.guild.id]
        
        if not guild_schedules:
            await ctx.send("No scheduled actions to cancel.")
            return
        
        view = CancelScheduleView(self, guild_schedules)
        embed = discord.Embed(
            title="Cancel Scheduled Action",
            description="Select a scheduled action to cancel:",
            color=discord.Color.blue()
        )
        
        await ctx.send(embed=embed, view=view)
    
    @server_management.command(name="automated")
    @commands.has_permissions(manage_channels=True)
    async def automated_channel(self, ctx):

        view = AutomatedChannelView(self)
        await ctx.send("Create a channel for a specific role:", view=view)
    
    @server_management.command(name="maintenance")
    @commands.has_permissions(administrator=True)
    async def maintenance_mode(self, ctx):

        view = MaintenanceModeView(self)
        embed = discord.Embed(
            title="Maintenance Mode Controls",
            description="Maintenance mode restricts access to non-essential channels, allowing you to perform server updates without disruption.",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="Activate Maintenance Mode",
            value="This will hide all channels except those you select as essential.",
            inline=False
        )
        
        embed.add_field(
            name="Deactivate Maintenance Mode",
            value="This will restore all channel permissions to their original state.",
            inline=False
        )
        
        await ctx.send(embed=embed, view=view)
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):

        channel_id = channel.id
        guild_id = channel.guild.id
        

        self.schedules = [s for s in self.schedules if not (
            s['guild_id'] == guild_id and s['channel_id'] == channel_id
        )]
        

        for task_id in list(self.schedule_tasks.keys()):
            if f"_{channel_id}_" in task_id:
                self.schedule_tasks[task_id].cancel()
                del self.schedule_tasks[task_id]
        

        guild_id_str = str(guild_id)
        if guild_id_str in self.automated_channels:
            self.automated_channels[guild_id_str] = [
                c for c in self.automated_channels[guild_id_str] 
                if c['channel_id'] != channel_id
            ]
        

        self.save_schedules()
        self.save_automated_channels()
    
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):

        guild_id_str = str(role.guild.id)
        role_id = role.id
        

        if guild_id_str in self.automated_channels:

            channels_to_update = [
                c for c in self.automated_channels[guild_id_str]
                if c['role_id'] == role_id
            ]
            

            self.automated_channels[guild_id_str] = [
                c for c in self.automated_channels[guild_id_str]
                if c['role_id'] != role_id
            ]
            

            self.save_automated_channels()
            

            if channels_to_update:
                log_channels = [c for c in role.guild.text_channels if 'log' in c.name.lower()]
                if log_channels:
                    channel_mentions = []
                    for channel_data in channels_to_update:
                        channel = role.guild.get_channel(channel_data['channel_id'])
                        if channel:
                            channel_mentions.append(channel.mention)
                    
                    if channel_mentions:
                        embed = discord.Embed(
                            title="Role-Specific Channels Updated",
                            description=f"The role **{role.name}** was deleted. The following channels were affected:\n" +
                                       "\n".join(channel_mentions),
                            color=discord.Color.orange(),
                            timestamp=datetime.now()
                        )
                        await log_channels[0].send(embed=embed)

def setup(bot):

    cog = ServerManagementUI(bot)
    

    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    

    return cog




