import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import json
import os
import asyncio
from typing import Optional, List, Dict, Union
import uuid
PRIORITY_COLORS = {
    "low": discord.Color.green(),
    "medium": discord.Color.gold(),
    "high": discord.Color.red()
}
STATUS_EMOJIS = {
    "open": "📝",
    "in_progress": "⏳",
    "completed": "✅",
    "archived": "📁"
}

class TaskManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tasks_file = "data/tasks.json"
        self.tasks = self.load_tasks()
        self.reminder_loop.start()
        os.makedirs("data", exist_ok=True)
        
    def cog_unload(self):
        self.reminder_loop.cancel()
        
    def load_tasks(self) -> Dict:
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {"tasks": {}, "projects": {}, "archived": {}}
        return {"tasks": {}, "projects": {}, "archived": {}}
        
    def save_tasks(self):
        with open(self.tasks_file, 'w') as f:
            json.dump(self.tasks, f, indent=4)
            
    @tasks.loop(minutes=30)
    async def reminder_loop(self):
        now = datetime.datetime.now()
        
        for task_id, task in self.tasks["tasks"].items():
            if task["status"] in ["open", "in_progress"]:
                due_date = datetime.datetime.fromisoformat(task["due_date"])
                time_diff = due_date - now
                if 0 < time_diff.total_seconds() < 86400:  # 24 hours in seconds
                    await self.send_reminder(task_id, task, "upcoming")
                elif time_diff.total_seconds() < 0:
                    await self.send_reminder(task_id, task, "overdue")
    
    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()
        
    async def send_reminder(self, task_id, task, reminder_type):
        guild = self.bot.get_guild(task["guild_id"])
        if not guild:
            return
        if task.get("assigned_to"):
            for user_id in task["assigned_to"]:
                user = guild.get_member(int(user_id))
                if user:
                    try:
                        embed = self.create_task_embed(task_id, task)
                        
                        if reminder_type == "upcoming":
                            embed.title = f"⏰ Upcoming Task Reminder"
                            embed.description = f"You have a task due soon!\n\n{embed.description}"
                        else:
                            embed.title = f"⚠️ Overdue Task Alert"
                            embed.description = f"This task is now overdue!\n\n{embed.description}"
                            embed.color = discord.Color.dark_red()
                            
                        await user.send(embed=embed)
                    except discord.Forbidden:
                        pass  # User has DMs closed
        if task.get("channel_id"):
            channel = guild.get_channel(int(task["channel_id"]))
            if channel:
                embed = self.create_task_embed(task_id, task)
                
                if reminder_type == "upcoming":
                    embed.title = f"⏰ Upcoming Task Reminder"
                    embed.description = f"Task due soon!\n\n{embed.description}"
                else:
                    embed.title = f"⚠️ Overdue Task Alert"
                    embed.description = f"This task is now overdue!\n\n{embed.description}"
                    embed.color = discord.Color.dark_red()
                    
                await channel.send(embed=embed)
    
    def create_task_embed(self, task_id, task):
        priority_color = PRIORITY_COLORS.get(task.get("priority", "medium"), discord.Color.blue())
        
        embed = discord.Embed(
            title=f"{STATUS_EMOJIS.get(task['status'], '📝')} Task: {task['name']}",
            description=task["description"],
            color=priority_color,
            timestamp=datetime.datetime.now()
        )
        due_date = datetime.datetime.fromisoformat(task["due_date"])
        formatted_date = due_date.strftime("%B %d, %Y at %I:%M %p")
        embed.add_field(name="ID", value=task_id, inline=True)
        embed.add_field(name="Status", value=task["status"].replace("_", " ").title(), inline=True)
        embed.add_field(name="Priority", value=task.get("priority", "medium").title(), inline=True)
        embed.add_field(name="Due Date", value=formatted_date, inline=True)
        if task.get("assigned_to"):
            assigned_users = []
            for user_id in task["assigned_to"]:
                assigned_users.append(f"<@{user_id}>")
            embed.add_field(name="Assigned To", value=", ".join(assigned_users), inline=True)
        if task.get("project_id"):
            project = self.tasks["projects"].get(task["project_id"])
            if project:
                embed.add_field(name="Project", value=project["name"], inline=True)
        created_at = datetime.datetime.fromisoformat(task["created_at"])
        embed.set_footer(text=f"Created by {task['created_by_name']} • {created_at.strftime('%B %d, %Y')} | Task Manager by TheZ")
        
        return embed
    class TaskView(discord.ui.View):
        def __init__(self, cog, task_id, task, timeout=180):
            super().__init__(timeout=timeout)
            self.cog = cog
            self.task_id = task_id
            self.task = task
            
        @discord.ui.button(label="Complete", style=discord.ButtonStyle.success, emoji="✅")
        async def complete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not await self.check_permission(interaction):
                return
                
            self.task["status"] = "completed"
            self.task["completed_at"] = datetime.datetime.now().isoformat()
            self.task["completed_by"] = str(interaction.user.id)
            self.task["completed_by_name"] = interaction.user.display_name
            
            self.cog.tasks["tasks"][self.task_id] = self.task
            self.cog.save_tasks()
            
            embed = self.cog.create_task_embed(self.task_id, self.task)
            await interaction.response.edit_message(embed=embed, view=self.cog.TaskView(self.cog, self.task_id, self.task))
            
        @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, emoji="📝")
        async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not await self.check_permission(interaction):
                return
                
            await interaction.response.send_modal(self.cog.EditTaskModal(self.cog, self.task_id, self.task))
            
        @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
        async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not await self.check_permission(interaction):
                return
            view = self.cog.ConfirmView()
            await interaction.response.send_message(f"Are you sure you want to delete task **{self.task['name']}**?", view=view, ephemeral=True)
            await view.wait()
            if view.value:
                del self.cog.tasks["tasks"][self.task_id]
                self.cog.save_tasks()
                await interaction.edit_original_response(content=f"Task **{self.task['name']}** has been deleted.", view=None)
                try:
                    await interaction.message.edit(content="This task has been deleted.", embed=None, view=None)
                except:
                    pass
            else:
                await interaction.edit_original_response(content="Task deletion cancelled.", view=None)
                
        @discord.ui.button(label="Assign", style=discord.ButtonStyle.secondary, emoji="👤", row=1)
        async def assign_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not await self.check_permission(interaction):
                return
                
            await interaction.response.send_modal(self.cog.AssignTaskModal(self.cog, self.task_id, self.task))
            
        @discord.ui.button(label="Change Status", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
        async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not await self.check_permission(interaction):
                return
            view = self.cog.StatusSelectView(self.cog, self.task_id, self.task)
            await interaction.response.send_message("Select a new status:", view=view, ephemeral=True)
            
        @discord.ui.button(label="Archive", style=discord.ButtonStyle.secondary, emoji="📁", row=1)
        async def archive_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not await self.check_permission(interaction):
                return
            if self.task["status"] != "completed":
                await interaction.response.send_message("Only completed tasks can be archived.", ephemeral=True)
                return
            self.cog.tasks["archived"][self.task_id] = self.task
            del self.cog.tasks["tasks"][self.task_id]
            self.cog.save_tasks()
            
            await interaction.response.edit_message(content="This task has been archived.", embed=None, view=None)
            
        async def check_permission(self, interaction):
            if str(interaction.user.id) == self.task.get("created_by"):
                return True
            if str(interaction.user.id) in self.task.get("assigned_to", []):
                return True
            if interaction.user.guild_permissions.administrator:
                return True
                
            await interaction.response.send_message("You don't have permission to modify this task.", ephemeral=True)
            return False
            
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
            
    class StatusSelectView(discord.ui.View):
        def __init__(self, cog, task_id, task):
            super().__init__(timeout=60)
            self.cog = cog
            self.task_id = task_id
            self.task = task
            self.add_item(discord.ui.Select(
                placeholder="Select a status",
                options=[
                    discord.SelectOption(label="Open", value="open", emoji="📝", default=task["status"] == "open"),
                    discord.SelectOption(label="In Progress", value="in_progress", emoji="⏳", default=task["status"] == "in_progress"),
                    discord.SelectOption(label="Completed", value="completed", emoji="✅", default=task["status"] == "completed")
                ],
                custom_id="status_select"
            ))
            
        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if interaction.data["component_type"] == 3:  # Select menu
                selected_status = interaction.data["values"][0]
                self.task["status"] = selected_status
                if selected_status == "completed":
                    self.task["completed_at"] = datetime.datetime.now().isoformat()
                    self.task["completed_by"] = str(interaction.user.id)
                    self.task["completed_by_name"] = interaction.user.display_name
                
                self.cog.tasks["tasks"][self.task_id] = self.task
                self.cog.save_tasks()
                try:
                    original_message = await interaction.channel.fetch_message(interaction.message.reference.message_id)
                    embed = self.cog.create_task_embed(self.task_id, self.task)
                    await original_message.edit(embed=embed, view=self.cog.TaskView(self.cog, self.task_id, self.task))
                except:
                    pass
                
                await interaction.response.edit_message(content=f"Task status updated to: {selected_status.replace('_', ' ').title()}", view=None)
                return False
            return True
            
    class EditTaskModal(discord.ui.Modal, title="Edit Task"):
        def __init__(self, cog, task_id, task):
            super().__init__()
            self.cog = cog
            self.task_id = task_id
            self.task = task
            
            self.name = discord.ui.TextInput(
                label="Task Name",
                placeholder="Enter task name",
                default=task["name"],
                required=True
            )
            
            self.description = discord.ui.TextInput(
                label="Description",
                placeholder="Enter task description",
                default=task["description"],
                style=discord.TextStyle.paragraph,
                required=True
            )
            due_date = datetime.datetime.fromisoformat(task["due_date"])
            formatted_due_date = due_date.strftime("%Y-%m-%d %H:%M")
            
            self.due_date = discord.ui.TextInput(
                label="Due Date (YYYY-MM-DD HH:MM)",
                placeholder="e.g. 2023-12-31 14:30",
                default=formatted_due_date,
                required=True
            )
            
            self.priority = discord.ui.TextInput(
                label="Priority (low, medium, high)",
                placeholder="Enter priority level",
                default=task.get("priority", "medium"),
                required=True
            )
            
            self.add_item(self.name)
            self.add_item(self.description)
            self.add_item(self.due_date)
            self.add_item(self.priority)
            
        async def on_submit(self, interaction: discord.Interaction):
            try:
                priority = self.priority.value.lower()
                if priority not in ["low", "medium", "high"]:
                    await interaction.response.send_message("Invalid priority. Please use low, medium, or high.", ephemeral=True)
                    return
                try:
                    due_date = datetime.datetime.strptime(self.due_date.value, "%Y-%m-%d %H:%M")
                except ValueError:
                    await interaction.response.send_message("Invalid date format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                    return
                self.task["name"] = self.name.value
                self.task["description"] = self.description.value
                self.task["due_date"] = due_date.isoformat()
                self.task["priority"] = priority
                self.task["updated_at"] = datetime.datetime.now().isoformat()
                self.task["updated_by"] = str(interaction.user.id)
                self.task["updated_by_name"] = interaction.user.display_name
                
                self.cog.tasks["tasks"][self.task_id] = self.task
                self.cog.save_tasks()
                embed = self.cog.create_task_embed(self.task_id, self.task)
                await interaction.response.edit_message(embed=embed, view=self.cog.TaskView(self.cog, self.task_id, self.task))
                
            except Exception as e:
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    
    class AssignTaskModal(discord.ui.Modal, title="Assign Task"):
        def __init__(self, cog, task_id, task):
            super().__init__()
            self.cog = cog
            self.task_id = task_id
            self.task = task
            current_assigned = ""
            if task.get("assigned_to"):
                current_assigned = ", ".join(task["assigned_to"])
            
            self.assigned_to = discord.ui.TextInput(
                label="User IDs (comma separated)",
                placeholder="e.g. 123456789, 987654321",
                default=current_assigned,
                required=False
            )
            
            self.add_item(self.assigned_to)
            
        async def on_submit(self, interaction: discord.Interaction):
            try:
                user_ids = []
                if self.assigned_to.value:
                    for user_id in self.assigned_to.value.split(","):
                        user_id = user_id.strip()
                        if user_id:
                            user_ids.append(user_id)
                self.task["assigned_to"] = user_ids
                self.task["updated_at"] = datetime.datetime.now().isoformat()
                self.task["updated_by"] = str(interaction.user.id)
                self.task["updated_by_name"] = interaction.user.display_name
                
                self.cog.tasks["tasks"][self.task_id] = self.task
                self.cog.save_tasks()
                embed = self.cog.create_task_embed(self.task_id, self.task)
                await interaction.response.edit_message(embed=embed, view=self.cog.TaskView(self.cog, self.task_id, self.task))
                
            except Exception as e:
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    
    class AddTaskModal(discord.ui.Modal, title="Add New Task"):
        def __init__(self, cog, channel_id, guild_id, project_id=None):
            super().__init__()
            self.cog = cog
            self.channel_id = channel_id
            self.guild_id = guild_id
            self.project_id = project_id
            
            self.name = discord.ui.TextInput(
                label="Task Name",
                placeholder="Enter task name",
                required=True
            )
            
            self.description = discord.ui.TextInput(
                label="Description",
                placeholder="Enter task description",
                style=discord.TextStyle.paragraph,
                required=True
            )
            tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
            
            self.due_date = discord.ui.TextInput(
                label="Due Date (YYYY-MM-DD HH:MM)",
                placeholder="e.g. 2023-12-31 14:30",
                default=tomorrow,
                required=True
            )
            
            self.priority = discord.ui.TextInput(
                label="Priority (low, medium, high)",
                placeholder="Enter priority level",
                default="medium",
                required=True
            )
            
            self.assigned_to = discord.ui.TextInput(
                label="Assign To (User IDs, comma separated)",
                placeholder="e.g. 123456789, 987654321",
                required=False
            )
            
            self.add_item(self.name)
            self.add_item(self.description)
            self.add_item(self.due_date)
            self.add_item(self.priority)
            self.add_item(self.assigned_to)
            
        async def on_submit(self, interaction: discord.Interaction):
            try:
                priority = self.priority.value.lower()
                if priority not in ["low", "medium", "high"]:
                    await interaction.response.send_message("Invalid priority. Please use low, medium, or high.", ephemeral=True)
                    return
                try:
                    due_date = datetime.datetime.strptime(self.due_date.value, "%Y-%m-%d %H:%M")
                except ValueError:
                    await interaction.response.send_message("Invalid date format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                    return
                assigned_users = []
                if self.assigned_to.value:
                    for user_id in self.assigned_to.value.split(","):
                        user_id = user_id.strip()
                        if user_id:
                            assigned_users.append(user_id)
                task_id = str(uuid.uuid4())
                task = {
                    "name": self.name.value,
                    "description": self.description.value,
                    "due_date": due_date.isoformat(),
                    "priority": priority,
                    "status": "open",
                    "created_at": datetime.datetime.now().isoformat(),
                    "created_by": str(interaction.user.id),
                    "created_by_name": interaction.user.display_name,
                    "guild_id": self.guild_id,
                    "channel_id": self.channel_id,
                    "assigned_to": assigned_users
                }
                if self.project_id:
                    task["project_id"] = self.project_id
                self.cog.tasks["tasks"][task_id] = task
                self.cog.save_tasks()
                embed = self.cog.create_task_embed(task_id, task)
                view = self.cog.TaskView(self.cog, task_id, task)
                
                await interaction.response.send_message(embed=embed, view=view)
                
            except Exception as e:
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    
    class ProjectView(discord.ui.View):
        def __init__(self, cog, project_id, project, timeout=180):
            super().__init__(timeout=timeout)
            self.cog = cog
            self.project_id = project_id
            self.project = project
            self.project_tasks = {}
            for task_id, task in self.cog.tasks["tasks"].items():
                if task.get("project_id") == project_id:
                    self.project_tasks[task_id] = task
            if self.project_tasks:
                options = []
                for task_id, task in self.project_tasks.items():
                    priority_emoji = "🟢" if task.get("priority") == "low" else "🟡" if task.get("priority") == "medium" else "🔴"
                    status_emoji = STATUS_EMOJIS.get(task["status"], "📝")
                    due_date = datetime.datetime.fromisoformat(task["due_date"])
                    due_str = due_date.strftime("%b %d")
                    option = discord.SelectOption(
                        label=f"{task['name']} [{task_id[:8]}]",
                        description=f"Due: {due_str} | {task['status'].replace('_', ' ').title()}",
                        value=task_id,
                        emoji=priority_emoji
                    )
                    options.append(option)
                if len(options) > 25:
                    options = options[:25]
                    
                if options:
                    self.add_item(ProjectTaskSelect(options))
            
        @discord.ui.button(label="Add Task", style=discord.ButtonStyle.primary, emoji="➕")
        async def add_task_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(
                self.cog.AddTaskModal(
                    self.cog,
                    interaction.channel.id,
                    interaction.guild.id,
                    self.project_id
                )
            )
            
        @discord.ui.button(label="View Tasks", style=discord.ButtonStyle.secondary, emoji="📋")
        async def view_tasks_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            project_tasks = {}
            for task_id, task in self.cog.tasks["tasks"].items():
                if task.get("project_id") == self.project_id:
                    project_tasks[task_id] = task
            
            if not project_tasks:
                await interaction.response.send_message("No tasks found for this project.", ephemeral=True)
                return
            embed = discord.Embed(
                title=f"📋 Tasks for Project: {self.project['name']}",
                description=self.project["description"],
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            open_tasks = []
            in_progress_tasks = []
            completed_tasks = []
            
            for task_id, task in project_tasks.items():
                task_line = f"• [{task_id[:8]}] **{task['name']}** ({task['priority']})"
                
                if task["status"] == "open":
                    open_tasks.append(task_line)
                elif task["status"] == "in_progress":
                    in_progress_tasks.append(task_line)
                elif task["status"] == "completed":
                    completed_tasks.append(task_line)
            if open_tasks:
                embed.add_field(name="📝 Open", value="\n".join(open_tasks), inline=False)
            if in_progress_tasks:
                embed.add_field(name="⏳ In Progress", value="\n".join(in_progress_tasks), inline=False)
            if completed_tasks:
                embed.add_field(name="✅ Completed", value="\n".join(completed_tasks), inline=False)
            total_tasks = len(project_tasks)
            completed_count = len(completed_tasks)
            progress_percent = (completed_count / total_tasks) * 100 if total_tasks > 0 else 0
            progress_bar = self.create_progress_bar(progress_percent)
            embed.add_field(name="📊 Progress", value=f"{progress_bar} {progress_percent:.1f}% ({completed_count}/{total_tasks})", inline=False)

            embed.set_footer(text="Task Manager by TheZ")
            view = ProjectTaskListView(self.cog, project_tasks)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        @discord.ui.button(label="Edit Project", style=discord.ButtonStyle.primary, emoji="📝")
        async def edit_project_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not await self.check_permission(interaction):
                return
                
            await interaction.response.send_modal(self.cog.EditProjectModal(self.cog, self.project_id, self.project))
            
        @discord.ui.button(label="Delete Project", style=discord.ButtonStyle.danger, emoji="🗑️")
        async def delete_project_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not await self.check_permission(interaction):
                return
            view = self.cog.ConfirmView()
            await interaction.response.send_message(f"Are you sure you want to delete project **{self.project['name']}**? All associated tasks will be deleted as well.", view=view, ephemeral=True)
            await view.wait()
            if view.value:
                tasks_to_delete = []
                for task_id, task in self.cog.tasks["tasks"].items():
                    if task.get("project_id") == self.project_id:
                        tasks_to_delete.append(task_id)
                
                for task_id in tasks_to_delete:
                    del self.cog.tasks["tasks"][task_id]
                del self.cog.tasks["projects"][self.project_id]
                self.cog.save_tasks()
                
                await interaction.edit_original_response(content=f"Project **{self.project['name']}** and {len(tasks_to_delete)} associated tasks have been deleted.", view=None)
                try:
                    await interaction.message.edit(content="This project has been deleted.", embed=None, view=None)
                except:
                    pass
            else:
                await interaction.edit_original_response(content="Project deletion cancelled.", view=None)
        
        @discord.ui.button(label="View Selected Task", style=discord.ButtonStyle.secondary, emoji="👁️", row=1)
        async def view_task_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not hasattr(self, 'selected_task_id'):
                await interaction.response.send_message("Please select a task first using the dropdown menu.", ephemeral=True)
                return
            
            task_id = self.selected_task_id
            task = self.project_tasks.get(task_id)
            
            if not task:
                await interaction.response.send_message("Task not found. It may have been deleted.", ephemeral=True)
                return
            embed = self.cog.create_task_embed(task_id, task)
            view = self.cog.TaskView(self.cog, task_id, task)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        @discord.ui.button(label="Repost Selected Task", style=discord.ButtonStyle.success, emoji="📤", row=1)
        async def repost_task_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not hasattr(self, 'selected_task_id'):
                await interaction.response.send_message("Please select a task first using the dropdown menu.", ephemeral=True)
                return
            
            task_id = self.selected_task_id
            task = self.project_tasks.get(task_id)
            
            if not task:
                await interaction.response.send_message("Task not found. It may have been deleted.", ephemeral=True)
                return
            embed = self.cog.create_task_embed(task_id, task)
            view = self.cog.TaskView(self.cog, task_id, task)
            await interaction.response.send_message("Reposting task...", ephemeral=True)
            await interaction.channel.send(embed=embed, view=view)
                
        def create_progress_bar(self, percent, length=10):
            filled = int(percent / 100 * length)
            empty = length - filled
            return "█" * filled + "░" * empty
            
        async def check_permission(self, interaction):
            if str(interaction.user.id) == self.project.get("created_by"):
                return True
            if interaction.user.guild_permissions.administrator:
                return True
                
            await interaction.response.send_message("You don't have permission to modify this project.", ephemeral=True)
            return False

        
    class EditProjectModal(discord.ui.Modal, title="Edit Project"):
        def __init__(self, cog, project_id, project):
            super().__init__()
            self.cog = cog
            self.project_id = project_id
            self.project = project
            
            self.name = discord.ui.TextInput(
                label="Project Name",
                placeholder="Enter project name",
                default=project["name"],
                required=True
            )
            
            self.description = discord.ui.TextInput(
                label="Description",
                placeholder="Enter project description",
                default=project["description"],
                style=discord.TextStyle.paragraph,
                required=True
            )
            due_date = datetime.datetime.fromisoformat(project["due_date"])
            formatted_due_date = due_date.strftime("%Y-%m-%d %H:%M")
            
            self.due_date = discord.ui.TextInput(
                label="Due Date (YYYY-MM-DD HH:MM)",
                placeholder="e.g. 2023-12-31 14:30",
                default=formatted_due_date,
                required=True
            )
            
            self.add_item(self.name)
            self.add_item(self.description)
            self.add_item(self.due_date)
            
        async def on_submit(self, interaction: discord.Interaction):
            try:
                try:
                    due_date = datetime.datetime.strptime(self.due_date.value, "%Y-%m-%d %H:%M")
                except ValueError:
                    await interaction.response.send_message("Invalid date format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                    return
                self.project["name"] = self.name.value
                self.project["description"] = self.description.value
                self.project["due_date"] = due_date.isoformat()
                self.project["updated_at"] = datetime.datetime.now().isoformat()
                self.project["updated_by"] = str(interaction.user.id)
                self.project["updated_by_name"] = interaction.user.display_name
                
                self.cog.tasks["projects"][self.project_id] = self.project
                self.cog.save_tasks()
                embed = self.create_project_embed(self.project_id, self.project)
                await interaction.response.edit_message(embed=embed, view=self.cog.ProjectView(self.cog, self.project_id, self.project))
                
            except Exception as e:
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
                
        def create_project_embed(self, project_id, project):
            embed = discord.Embed(
                title=f"📂 Project: {project['name']}",
                description=project["description"],
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            due_date = datetime.datetime.fromisoformat(project["due_date"])
            formatted_date = due_date.strftime("%B %d, %Y at %I:%M %p")
            embed.add_field(name="ID", value=project_id, inline=True)
            embed.add_field(name="Due Date", value=formatted_date, inline=True)
            created_at = datetime.datetime.fromisoformat(project["created_at"])
            embed.set_footer(text=f"Created by {project['created_by_name']} • {created_at.strftime('%B %d, %Y')}")
            
            return embed
    
    class AddProjectModal(discord.ui.Modal, title="Create New Project"):
        def __init__(self, cog, channel_id, guild_id):
            super().__init__()
            self.cog = cog
            self.channel_id = channel_id
            self.guild_id = guild_id
            
            self.name = discord.ui.TextInput(
                label="Project Name",
                placeholder="Enter project name",
                required=True
            )
            
            self.description = discord.ui.TextInput(
                label="Description",
                placeholder="Enter project description",
                style=discord.TextStyle.paragraph,
                required=True
            )
            two_weeks_later = (datetime.datetime.now() + datetime.timedelta(days=14)).strftime("%Y-%m-%d %H:%M")
            
            self.due_date = discord.ui.TextInput(
                label="Due Date (YYYY-MM-DD HH:MM)",
                placeholder="e.g. 2023-12-31 14:30",
                default=two_weeks_later,
                required=True
            )
            
            self.add_item(self.name)
            self.add_item(self.description)
            self.add_item(self.due_date)
            
        async def on_submit(self, interaction: discord.Interaction):
            try:
                try:
                    due_date = datetime.datetime.strptime(self.due_date.value, "%Y-%m-%d %H:%M")
                except ValueError:
                    await interaction.response.send_message("Invalid date format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                    return
                project_id = str(uuid.uuid4())
                project = {
                    "name": self.name.value,
                    "description": self.description.value,
                    "due_date": due_date.isoformat(),
                    "created_at": datetime.datetime.now().isoformat(),
                    "created_by": str(interaction.user.id),
                    "created_by_name": interaction.user.display_name,
                    "guild_id": self.guild_id,
                    "channel_id": self.channel_id
                }
                self.cog.tasks["projects"][project_id] = project
                self.cog.save_tasks()
                embed = self.create_project_embed(project_id, project)
                view = self.cog.ProjectView(self.cog, project_id, project)
                
                await interaction.response.send_message(embed=embed, view=view)
                
            except Exception as e:
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
                
        def create_project_embed(self, project_id, project):
            embed = discord.Embed(
                title=f"📂 Project: {project['name']}",
                description=project["description"],
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            due_date = datetime.datetime.fromisoformat(project["due_date"])
            formatted_date = due_date.strftime("%B %d, %Y at %I:%M %p")
            embed.add_field(name="ID", value=project_id, inline=True)
            embed.add_field(name="Due Date", value=formatted_date, inline=True)
            created_at = datetime.datetime.fromisoformat(project["created_at"])
            embed.set_footer(text=f"Created by {project['created_by_name']} • {created_at.strftime('%B %d, %Y')}")
            
            return embed
    
    class TaskManagerView(discord.ui.View):
        def __init__(self, cog):
            super().__init__(timeout=180)
            self.cog = cog
            
        @discord.ui.button(label="Add Task", style=discord.ButtonStyle.primary, emoji="➕")
        async def add_task_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(
                self.cog.AddTaskModal(
                    self.cog, 
                    interaction.channel.id, 
                    interaction.guild.id
                )
            )
            
        @discord.ui.button(label="List Tasks", style=discord.ButtonStyle.secondary, emoji="📋")
        async def list_tasks_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.list_tasks_manually(interaction)
            
        @discord.ui.button(label="Create Project", style=discord.ButtonStyle.success, emoji="📂")
        async def create_project_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(
                self.cog.AddProjectModal(
                    self.cog, 
                    interaction.channel.id, 
                    interaction.guild.id
                )
            )
            
        @discord.ui.button(label="List Projects", style=discord.ButtonStyle.secondary, emoji="📚")
        async def list_projects_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.list_projects_manually(interaction)
            
        @discord.ui.button(label="Task Statistics", style=discord.ButtonStyle.secondary, emoji="📊", row=1)
        async def statistics_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.show_statistics_manually(interaction)
            
        @discord.ui.button(label="Archived Tasks", style=discord.ButtonStyle.secondary, emoji="📁", row=1)
        async def archived_tasks_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.list_archived_tasks(interaction)
        async def list_tasks_manually(self, interaction: discord.Interaction):
            guild_tasks = {}
            for task_id, task in self.cog.tasks["tasks"].items():
                if task.get("guild_id") == interaction.guild_id:
                    guild_tasks[task_id] = task
            
            if not guild_tasks:
                await interaction.response.send_message("No tasks found matching your criteria.", ephemeral=True)
                return
            embed = discord.Embed(
                title="📋 Task List",
                description="Here are your tasks. Select a task from the dropdown to view or edit it.",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            open_tasks = []
            in_progress_tasks = []
            completed_tasks = []
            
            for task_id, task in guild_tasks.items():
                due_date = datetime.datetime.fromisoformat(task["due_date"])
                due_str = due_date.strftime("%b %d")
                
                priority_emoji = "🟢" if task.get("priority") == "low" else "🟡" if task.get("priority") == "medium" else "🔴"
                
                task_line = f"{priority_emoji} [{task_id[:8]}] **{task['name']}** (Due: {due_str})"
                
                if task["status"] == "open":
                    open_tasks.append(task_line)
                elif task["status"] == "in_progress":
                    in_progress_tasks.append(task_line)
                elif task["status"] == "completed":
                    completed_tasks.append(task_line)
            if open_tasks:
                embed.add_field(name="📝 Open", value="\n".join(open_tasks[:10]) + (f"\n*...and {len(open_tasks) - 10} more*" if len(open_tasks) > 10 else ""), inline=False)
            if in_progress_tasks:
                embed.add_field(name="⏳ In Progress", value="\n".join(in_progress_tasks[:10]) + (f"\n*...and {len(in_progress_tasks) - 10} more*" if len(in_progress_tasks) > 10 else ""), inline=False)
            if completed_tasks:
                embed.add_field(name="✅ Completed", value="\n".join(completed_tasks[:10]) + (f"\n*...and {len(completed_tasks) - 10} more*" if len(completed_tasks) > 10 else ""), inline=False)
            total_tasks = len(guild_tasks)
            completed_count = len(completed_tasks)
            progress_percent = (completed_count / total_tasks) * 100 if total_tasks > 0 else 0
            progress_bar = self.cog.create_progress_bar(progress_percent)
            
            embed.add_field(name="📊 Progress", value=f"{progress_bar} {progress_percent:.1f}% ({completed_count}/{total_tasks})", inline=False)
            view = TaskListView(self.cog, guild_tasks)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        async def list_projects_manually(self, interaction: discord.Interaction):
            guild_projects = {}
            for project_id, project in self.cog.tasks["projects"].items():
                if project.get("guild_id") == interaction.guild_id:
                    guild_projects[project_id] = project
            
            if not guild_projects:
                await interaction.response.send_message("No projects found.", ephemeral=True)
                return
            embed = discord.Embed(
                title="📚 Project List",
                description="Here are your projects. Select a project from the dropdown to view or edit it.",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            
            for project_id, project in guild_projects.items():
                due_date = datetime.datetime.fromisoformat(project["due_date"])
                due_str = due_date.strftime("%b %d, %Y")
                task_count = 0
                completed_count = 0
                for task in self.cog.tasks["tasks"].values():
                    if task.get("project_id") == project_id:
                        task_count += 1
                        if task["status"] == "completed":
                            completed_count += 1
                
                progress = f"{completed_count}/{task_count} tasks completed"
                
                embed.add_field(
                    name=f"📂 {project['name']} [{project_id[:8]}]",
                    value=f"Due: {due_str}\n{progress}",
                    inline=True
                )
            view = ProjectListView(self.cog, guild_projects)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        async def show_statistics_manually(self, interaction: discord.Interaction):
            guild_tasks = {}
            for task_id, task in self.cog.tasks["tasks"].items():
                if task.get("guild_id") == interaction.guild_id:
                    guild_tasks[task_id] = task
            
            if not guild_tasks:
                await interaction.response.send_message("No tasks found.", ephemeral=True)
                return
            total_tasks = len(guild_tasks)
            open_tasks = sum(1 for task in guild_tasks.values() if task["status"] == "open")
            in_progress_tasks = sum(1 for task in guild_tasks.values() if task["status"] == "in_progress")
            completed_tasks = sum(1 for task in guild_tasks.values() if task["status"] == "completed")
            low_priority = sum(1 for task in guild_tasks.values() if task.get("priority") == "low")
            medium_priority = sum(1 for task in guild_tasks.values() if task.get("priority") == "medium")
            high_priority = sum(1 for task in guild_tasks.values() if task.get("priority") == "high")
            now = datetime.datetime.now()
            overdue_tasks = 0
            due_today = 0
            due_this_week = 0
            
            for task in guild_tasks.values():
                if task["status"] in ["open", "in_progress"]:
                    due_date = datetime.datetime.fromisoformat(task["due_date"])
                    if due_date < now:
                        overdue_tasks += 1
                    elif due_date.date() == now.date():
                        due_today += 1
                    elif (due_date - now).days <= 7:
                        due_this_week += 1
            user_tasks = {}
            user_completed = {}
            
            for task in guild_tasks.values():
                if "assigned_to" in task:
                    for user_id in task["assigned_to"]:
                        if user_id not in user_tasks:
                            user_tasks[user_id] = 0
                            user_completed[user_id] = 0
                        
                        user_tasks[user_id] += 1
                        if task["status"] == "completed":
                            user_completed[user_id] += 1
            embed = discord.Embed(
                title="📊 Task Statistics",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            progress_percent = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
            progress_bar = self.cog.create_progress_bar(progress_percent)
            
            embed.add_field(
                name="Overall Progress",
                value=f"{progress_bar} {progress_percent:.1f}%\n{completed_tasks}/{total_tasks} tasks completed",
                inline=False
            )
            embed.add_field(
                name="Status Breakdown",
                value=f"📝 Open: {open_tasks}\n⏳ In Progress: {in_progress_tasks}\n✅ Completed: {completed_tasks}",
                inline=True
            )
            embed.add_field(
                name="Priority Breakdown",
                value=f"🟢 Low: {low_priority}\n🟡 Medium: {medium_priority}\n🔴 High: {high_priority}",
                inline=True
            )
            embed.add_field(
                name="Due Date Statistics",
                value=f"⚠️ Overdue: {overdue_tasks}\n📅 Due Today: {due_today}\n📆 Due This Week: {due_this_week}",
                inline=True
            )
            if user_tasks:
                sorted_users = sorted(user_tasks.keys(), key=lambda u: user_completed.get(u, 0), reverse=True)
                
                top_users = []
                for i, user_id in enumerate(sorted_users[:5]):
                    member = interaction.guild.get_member(int(user_id))
                    name = member.display_name if member else f"User {user_id}"
                    completion_rate = (user_completed[user_id] / user_tasks[user_id]) * 100 if user_tasks[user_id] > 0 else 0
                    
                    top_users.append(f"{i+1}. {name}: {user_completed[user_id]}/{user_tasks[user_id]} ({completion_rate:.1f}%)")
                
                embed.add_field(
                    name="🏆 Top Task Completers",
                    value="\n".join(top_users) if top_users else "No data available",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
        async def list_archived_tasks(self, interaction: discord.Interaction):
            guild_archived_tasks = {}
            for task_id, task in self.cog.tasks["archived"].items():
                if task.get("guild_id") == interaction.guild_id:
                    guild_archived_tasks[task_id] = task
            
            if not guild_archived_tasks:
                await interaction.response.send_message("No archived tasks found.", ephemeral=True)
                return
            embed = discord.Embed(
                title="📁 Archived Tasks",
                description="Here are your archived tasks. Select a task from the dropdown to view or restore it.",
                color=discord.Color.dark_gray(),
                timestamp=datetime.datetime.now()
            )
            sorted_tasks = sorted(
                guild_archived_tasks.items(), 
                key=lambda x: datetime.datetime.fromisoformat(x[1].get("completed_at", x[1]["created_at"])),
                reverse=True
            )
            
            for task_id, task in sorted_tasks[:15]:  # Limit to 15 tasks to avoid embed limits
                completed_at = datetime.datetime.fromisoformat(task.get("completed_at", task["created_at"]))
                completed_str = completed_at.strftime("%b %d, %Y")
                
                priority_emoji = "🟢" if task.get("priority") == "low" else "🟡" if task.get("priority") == "medium" else "🔴"
                
                embed.add_field(
                    name=f"{priority_emoji} {task['name']} [{task_id[:8]}]",
                    value=f"{task['description'][:100]}{'...' if len(task['description']) > 100 else ''}\nCompleted: {completed_str}",
                    inline=False
                )
            
            if len(sorted_tasks) > 15:
                embed.set_footer(text=f"Showing 15 of {len(sorted_tasks)} archived tasks")
            view = ArchivedTasksView(self.cog, guild_archived_tasks)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    @app_commands.command(name="tasks", description="Open the task manager")
    async def tasks_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📋 Task Manager",
            description="Manage your tasks and projects with the buttons below.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Task Manager by TheZ")
        view = self.TaskManagerView(self)
        await interaction.response.send_message(embed=embed, view=view)
    
    @app_commands.command(name="add-task", description="Add a new task")
    @app_commands.describe(
        name="The name of the task",
        description="A description of the task",
        due_date="Due date in YYYY-MM-DD HH:MM format",
        priority="Priority level (low, medium, high)"
    )
    async def add_task_command(self, interaction: discord.Interaction, 
                              name: str, 
                              description: str, 
                              due_date: str, 
                              priority: str = "medium"):
        try:
            priority = priority.lower()
            if priority not in ["low", "medium", "high"]:
                await interaction.response.send_message("Invalid priority. Please use low, medium, or high.", ephemeral=True)
                return
            try:
                due_date_obj = datetime.datetime.strptime(due_date, "%Y-%m-%d %H:%M")
            except ValueError:
                await interaction.response.send_message("Invalid date format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                return
            task_id = str(uuid.uuid4())
            task = {
                "name": name,
                "description": description,
                "due_date": due_date_obj.isoformat(),
                "priority": priority,
                "status": "open",
                "created_at": datetime.datetime.now().isoformat(),
                "created_by": str(interaction.user.id),
                "created_by_name": interaction.user.display_name,
                "guild_id": interaction.guild_id,
                "channel_id": interaction.channel_id,
                "assigned_to": []
            }
            self.tasks["tasks"][task_id] = task
            self.save_tasks()
            embed = self.create_task_embed(task_id, task)
            view = self.TaskView(self, task_id, task)
            
            await interaction.response.send_message(embed=embed, view=view)
            
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="list-tasks", description="List all tasks")
    @app_commands.describe(
        status="Filter tasks by status",
        priority="Filter tasks by priority",
        assigned_to="Filter tasks assigned to a specific user (ID)"
    )
    async def list_tasks_command(self, interaction: discord.Interaction, 
                                status: Optional[str] = None, 
                                priority: Optional[str] = None,
                                assigned_to: Optional[str] = None):
        guild_tasks = {}
        for task_id, task in self.tasks["tasks"].items():
            if task.get("guild_id") == interaction.guild_id:
                if status and task["status"] != status:
                    continue
                if priority and task.get("priority") != priority:
                    continue
                if assigned_to and assigned_to not in task.get("assigned_to", []):
                    continue
                    
                guild_tasks[task_id] = task
        
        if not guild_tasks:
            await interaction.response.send_message("No tasks found matching your criteria.", ephemeral=True)
            return
        embed = discord.Embed(
            title="📋 Task List",
            description="Here are your tasks:",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        open_tasks = []
        in_progress_tasks = []
        completed_tasks = []
        
        for task_id, task in guild_tasks.items():
            due_date = datetime.datetime.fromisoformat(task["due_date"])
            due_str = due_date.strftime("%b %d")
            
            priority_emoji = "🟢" if task.get("priority") == "low" else "🟡" if task.get("priority") == "medium" else "🔴"
            
            task_line = f"{priority_emoji} [{task_id[:8]}] **{task['name']}** (Due: {due_str})"
            
            if task["status"] == "open":
                open_tasks.append(task_line)
            elif task["status"] == "in_progress":
                in_progress_tasks.append(task_line)
            elif task["status"] == "completed":
                completed_tasks.append(task_line)
        if open_tasks:
            embed.add_field(name="📝 Open", value="\n".join(open_tasks[:10]) + (f"\n*...and {len(open_tasks) - 10} more*" if len(open_tasks) > 10 else ""), inline=False)
        if in_progress_tasks:
            embed.add_field(name="⏳ In Progress", value="\n".join(in_progress_tasks[:10]) + (f"\n*...and {len(in_progress_tasks) - 10} more*" if len(in_progress_tasks) > 10 else ""), inline=False)
        if completed_tasks:
            embed.add_field(name="✅ Completed", value="\n".join(completed_tasks[:10]) + (f"\n*...and {len(completed_tasks) - 10} more*" if len(completed_tasks) > 10 else ""), inline=False)
        total_tasks = len(guild_tasks)
        completed_count = len(completed_tasks)
        progress_percent = (completed_count / total_tasks) * 100 if total_tasks > 0 else 0
        progress_bar = self.create_progress_bar(progress_percent)
        
        embed.add_field(name="📊 Progress", value=f"{progress_bar} {progress_percent:.1f}% ({completed_count}/{total_tasks})", inline=False)
        embed.set_footer(text="Task Manager by TheZ")


        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def create_progress_bar(self, percent, length=10):
        filled = int(percent / 100 * length)
        empty = length - filled
        return "█" * filled + "░" * empty
    
    @app_commands.command(name="delete-task", description="Delete a task by ID")
    @app_commands.describe(task_id="The ID of the task to delete")
    async def delete_task_command(self, interaction: discord.Interaction, task_id: str):
        if task_id not in self.tasks["tasks"]:
            await interaction.response.send_message(f"Task with ID {task_id} not found.", ephemeral=True)
            return
        
        task = self.tasks["tasks"][task_id]
        if str(interaction.user.id) != task["created_by"] and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You don't have permission to delete this task.", ephemeral=True)
            return
        view = self.ConfirmView()
        await interaction.response.send_message(f"Are you sure you want to delete task **{task['name']}**?", view=view, ephemeral=True)
        await view.wait()
        if view.value:
            del self.tasks["tasks"][task_id]
            self.save_tasks()
            await interaction.edit_original_response(content=f"Task **{task['name']}** has been deleted.", view=None)
        else:
            await interaction.edit_original_response(content="Task deletion cancelled.", view=None)
    
    @app_commands.command(name="clear-tasks", description="Delete all completed tasks")
    async def clear_tasks_command(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
            return
        completed_tasks = []
        for task_id, task in list(self.tasks["tasks"].items()):
            if task["status"] == "completed" and task.get("guild_id") == interaction.guild_id:
                completed_tasks.append(task_id)
        
        if not completed_tasks:
            await interaction.response.send_message("No completed tasks to clear.", ephemeral=True)
            return
        view = self.ConfirmView()
        await interaction.response.send_message(f"Are you sure you want to delete {len(completed_tasks)} completed tasks?", view=view, ephemeral=True)
        await view.wait()
        if view.value:
            for task_id in completed_tasks:
                del self.tasks["tasks"][task_id]
            self.save_tasks()
            await interaction.edit_original_response(content=f"{len(completed_tasks)} completed tasks have been deleted.", view=None)
        else:
            await interaction.edit_original_response(content="Task deletion cancelled.", view=None)
    
    @app_commands.command(name="edit-task", description="Edit a task by ID")
    @app_commands.describe(
        task_id="The ID of the task to edit",
        field="The field to edit (name, description, due_date, priority, status)",
        value="The new value for the field"
    )
    async def edit_task_command(self, interaction: discord.Interaction, task_id: str, field: str, value: str):
        if task_id not in self.tasks["tasks"]:
            await interaction.response.send_message(f"Task with ID {task_id} not found.", ephemeral=True)
            return
        
        task = self.tasks["tasks"][task_id]
        if str(interaction.user.id) != task["created_by"] and str(interaction.user.id) not in task.get("assigned_to", []) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You don't have permission to edit this task.", ephemeral=True)
            return
        valid_fields = ["name", "description", "due_date", "priority", "status"]
        if field not in valid_fields:
            await interaction.response.send_message(f"Invalid field. Valid fields are: {', '.join(valid_fields)}", ephemeral=True)
            return
        try:
            if field == "due_date":
                try:
                    due_date = datetime.datetime.strptime(value, "%Y-%m-%d %H:%M")
                    task["due_date"] = due_date.isoformat()
                except ValueError:
                    await interaction.response.send_message("Invalid date format. Please use YYYY-MM-DD HH:MM", ephemeral=True)
                    return
            elif field == "priority":
                value = value.lower()
                if value not in ["low", "medium", "high"]:
                    await interaction.response.send_message("Invalid priority. Please use low, medium, or high.", ephemeral=True)
                    return
                task["priority"] = value
            elif field == "status":
                value = value.lower()
                if value not in ["open", "in_progress", "completed"]:
                    await interaction.response.send_message("Invalid status. Please use open, in_progress, or completed.", ephemeral=True)
                    return
                task["status"] = value
                if value == "completed":
                    task["completed_at"] = datetime.datetime.now().isoformat()
                    task["completed_by"] = str(interaction.user.id)
                    task["completed_by_name"] = interaction.user.display_name
            else:
                task[field] = value
            task["updated_at"] = datetime.datetime.now().isoformat()
            task["updated_by"] = str(interaction.user.id)
            task["updated_by_name"] = interaction.user.display_name
            
            self.tasks["tasks"][task_id] = task
            self.save_tasks()
            embed = self.create_task_embed(task_id, task)
            view = self.TaskView(self, task_id, task)
            
            await interaction.response.send_message(f"Task updated successfully!", embed=embed, view=view)
            
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="task-info", description="Show details about a task")
    @app_commands.describe(task_id="The ID of the task to view")
    async def task_info_command(self, interaction: discord.Interaction, task_id: str):
        if task_id not in self.tasks["tasks"]:
            await interaction.response.send_message(f"Task with ID {task_id} not found.", ephemeral=True)
            return
        
        task = self.tasks["tasks"][task_id]
        embed = self.create_task_embed(task_id, task)
        view = self.TaskView(self, task_id, task)
        
        await interaction.response.send_message(embed=embed, view=view)
    
    @app_commands.command(name="assign-task", description="Assign a task to a user")
    @app_commands.describe(
        task_id="The ID of the task to assign",
        user="The user to assign the task to"
    )
    async def assign_task_command(self, interaction: discord.Interaction, task_id: str, user: discord.Member):
        if task_id not in self.tasks["tasks"]:
            await interaction.response.send_message(f"Task with ID {task_id} not found.", ephemeral=True)
            return
        
        task = self.tasks["tasks"][task_id]
        if str(interaction.user.id) != task["created_by"] and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You don't have permission to assign this task.", ephemeral=True)
            return
        if "assigned_to" not in task:
            task["assigned_to"] = []
        
        user_id = str(user.id)
        if user_id not in task["assigned_to"]:
            task["assigned_to"].append(user_id)
        task["updated_at"] = datetime.datetime.now().isoformat()
        task["updated_by"] = str(interaction.user.id)
        task["updated_by_name"] = interaction.user.display_name
        
        self.tasks["tasks"][task_id] = task
        self.save_tasks()
        embed = self.create_task_embed(task_id, task)
        view = self.TaskView(self, task_id, task)
        
        await interaction.response.send_message(f"Task assigned to {user.display_name}!", embed=embed, view=view)
        try:
            user_embed = discord.Embed(
                title="📋 Task Assigned to You",
                description=f"You have been assigned a new task in {interaction.guild.name}",
                color=discord.Color.blue()
            )
            user_embed.add_field(name="Task", value=task["name"], inline=False)
            user_embed.add_field(name="Description", value=task["description"], inline=False)
            user_embed.add_field(name="Due Date", value=datetime.datetime.fromisoformat(task["due_date"]).strftime("%B %d, %Y at %I:%M %p"), inline=False)
            
            await user.send(embed=user_embed)
        except:
            pass  # User has DMs closed
    
    @app_commands.command(name="unassign-task", description="Remove a user from a task")
    @app_commands.describe(
        task_id="The ID of the task",
        user="The user to remove from the task"
    )
    async def unassign_task_command(self, interaction: discord.Interaction, task_id: str, user: discord.Member):
        if task_id not in self.tasks["tasks"]:
            await interaction.response.send_message(f"Task with ID {task_id} not found.", ephemeral=True)
            return
        
        task = self.tasks["tasks"][task_id]
        if str(interaction.user.id) != task["created_by"] and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You don't have permission to unassign this task.", ephemeral=True)
            return
        if "assigned_to" not in task:
            task["assigned_to"] = []
        
        user_id = str(user.id)
        if user_id in task["assigned_to"]:
            task["assigned_to"].remove(user_id)
        else:
            await interaction.response.send_message(f"{user.display_name} is not assigned to this task.", ephemeral=True)
            return
        task["updated_at"] = datetime.datetime.now().isoformat()
        task["updated_by"] = str(interaction.user.id)
        task["updated_by_name"] = interaction.user.display_name
        
        self.tasks["tasks"][task_id] = task
        self.save_tasks()
        embed = self.create_task_embed(task_id, task)
        view = self.TaskView(self, task_id, task)
        
        await interaction.response.send_message(f"{user.display_name} has been unassigned from the task!", embed=embed, view=view)
    
    @app_commands.command(name="set-priority", description="Set the priority of a task")
    @app_commands.describe(
        task_id="The ID of the task",
        priority="The priority level (low, medium, high)"
    )
    @app_commands.choices(priority=[
        app_commands.Choice(name="Low", value="low"),
        app_commands.Choice(name="Medium", value="medium"),
        app_commands.Choice(name="High", value="high")
    ])
    async def set_priority_command(self, interaction: discord.Interaction, task_id: str, priority: str):
        if task_id not in self.tasks["tasks"]:
            await interaction.response.send_message(f"Task with ID {task_id} not found.", ephemeral=True)
            return
        
        task = self.tasks["tasks"][task_id]
        if str(interaction.user.id) != task["created_by"] and str(interaction.user.id) not in task.get("assigned_to", []) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You don't have permission to change this task's priority.", ephemeral=True)
            return
        task["priority"] = priority
        task["updated_at"] = datetime.datetime.now().isoformat()
        task["updated_by"] = str(interaction.user.id)
        task["updated_by_name"] = interaction.user.display_name
        
        self.tasks["tasks"][task_id] = task
        self.save_tasks()
        embed = self.create_task_embed(task_id, task)
        view = self.TaskView(self, task_id, task)
        
        await interaction.response.send_message(f"Task priority set to {priority}!", embed=embed, view=view)
    
    @app_commands.command(name="change-status", description="Change the status of a task")
    @app_commands.describe(
        task_id="The ID of the task",
        status="The new status (open, in_progress, completed)"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="Open", value="open"),
        app_commands.Choice(name="In Progress", value="in_progress"),
        app_commands.Choice(name="Completed", value="completed")
    ])
    async def change_status_command(self, interaction: discord.Interaction, task_id: str, status: str):
        if task_id not in self.tasks["tasks"]:
            await interaction.response.send_message(f"Task with ID {task_id} not found.", ephemeral=True)
            return
        
        task = self.tasks["tasks"][task_id]
        if str(interaction.user.id) != task["created_by"] and str(interaction.user.id) not in task.get("assigned_to", []) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You don't have permission to change this task's status.", ephemeral=True)
            return
        task["status"] = status
        if status == "completed":
            task["completed_at"] = datetime.datetime.now().isoformat()
            task["completed_by"] = str(interaction.user.id)
            task["completed_by_name"] = interaction.user.display_name
        task["updated_at"] = datetime.datetime.now().isoformat()
        task["updated_by"] = str(interaction.user.id)
        task["updated_by_name"] = interaction.user.display_name
        
        self.tasks["tasks"][task_id] = task
        self.save_tasks()
        embed = self.create_task_embed(task_id, task)
        view = self.TaskView(self, task_id, task)
        
        await interaction.response.send_message(f"Task status changed to {status.replace('_', ' ')}!", embed=embed, view=view)
    
    @app_commands.command(name="duplicate-task", description="Create a copy of an existing task")
    @app_commands.describe(task_id="The ID of the task to duplicate")
    async def duplicate_task_command(self, interaction: discord.Interaction, task_id: str):
        if task_id not in self.tasks["tasks"]:
            await interaction.response.send_message(f"Task with ID {task_id} not found.", ephemeral=True)
            return
        
        original_task = self.tasks["tasks"][task_id]
        new_task_id = str(uuid.uuid4())
        new_task = original_task.copy()
        new_task["name"] = f"Copy of {original_task['name']}"
        new_task["status"] = "open"
        new_task["created_at"] = datetime.datetime.now().isoformat()
        new_task["created_by"] = str(interaction.user.id)
        new_task["created_by_name"] = interaction.user.display_name
        if "completed_at" in new_task:
            del new_task["completed_at"]
        if "completed_by" in new_task:
            del new_task["completed_by"]
        if "completed_by_name" in new_task:
            del new_task["completed_by_name"]
        self.tasks["tasks"][new_task_id] = new_task
        self.save_tasks()
        embed = self.create_task_embed(new_task_id, new_task)
        view = self.TaskView(self, new_task_id, new_task)
        
        await interaction.response.send_message(f"Task duplicated successfully!", embed=embed, view=view)
    
    @app_commands.command(name="archive-task", description="Archive a completed task")
    @app_commands.describe(task_id="The ID of the task to archive")
    async def archive_task_command(self, interaction: discord.Interaction, task_id: str):
        if task_id not in self.tasks["tasks"]:
            await interaction.response.send_message(f"Task with ID {task_id} not found.", ephemeral=True)
            return
        
        task = self.tasks["tasks"][task_id]
        if str(interaction.user.id) != task["created_by"] and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You don't have permission to archive this task.", ephemeral=True)
            return
        if task["status"] != "completed":
            await interaction.response.send_message("Only completed tasks can be archived.", ephemeral=True)
            return
        self.tasks["archived"][task_id] = task
        del self.tasks["tasks"][task_id]
        self.save_tasks()
        
        await interaction.response.send_message(f"Task **{task['name']}** has been archived.", ephemeral=True)
    
    @app_commands.command(name="list-projects", description="List all projects")
    async def list_projects_command(self, interaction: discord.Interaction):
        guild_projects = {}
        for project_id, project in self.tasks["projects"].items():
            if project.get("guild_id") == interaction.guild_id:
                guild_projects[project_id] = project
        
        if not guild_projects:
            await interaction.response.send_message("No projects found.", ephemeral=True)
            return
        embed = discord.Embed(
            title="📚 Project List",
            description="Here are your projects:",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        for project_id, project in guild_projects.items():
            due_date = datetime.datetime.fromisoformat(project["due_date"])
            due_str = due_date.strftime("%b %d, %Y")
            task_count = 0
            completed_count = 0
            for task in self.tasks["tasks"].values():
                if task.get("project_id") == project_id:
                    task_count += 1
                    if task["status"] == "completed":
                        completed_count += 1
            
            progress = f"{completed_count}/{task_count} tasks completed"
            
            embed.add_field(
                name=f"📂 {project['name']} [{project_id[:8]}]",
                value=f"Due: {due_str}\n{progress}",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="task-statistics", description="Show task statistics")
    async def task_statistics_command(self, interaction: discord.Interaction):
        guild_tasks = {}
        for task_id, task in self.tasks["tasks"].items():
            if task.get("guild_id") == interaction.guild_id:
                guild_tasks[task_id] = task
        
        if not guild_tasks:
            await interaction.response.send_message("No tasks found.", ephemeral=True)
            return
        total_tasks = len(guild_tasks)
        open_tasks = sum(1 for task in guild_tasks.values() if task["status"] == "open")
        in_progress_tasks = sum(1 for task in guild_tasks.values() if task["status"] == "in_progress")
        completed_tasks = sum(1 for task in guild_tasks.values() if task["status"] == "completed")
        low_priority = sum(1 for task in guild_tasks.values() if task.get("priority") == "low")
        medium_priority = sum(1 for task in guild_tasks.values() if task.get("priority") == "medium")
        high_priority = sum(1 for task in guild_tasks.values() if task.get("priority") == "high")
        now = datetime.datetime.now()
        overdue_tasks = 0
        due_today = 0
        due_this_week = 0
        
        for task in guild_tasks.values():
            if task["status"] in ["open", "in_progress"]:
                due_date = datetime.datetime.fromisoformat(task["due_date"])
                if due_date < now:
                    overdue_tasks += 1
                elif due_date.date() == now.date():
                    due_today += 1
                elif (due_date - now).days <= 7:
                    due_this_week += 1
        user_tasks = {}
        user_completed = {}
        
        for task in guild_tasks.values():
            if "assigned_to" in task:
                for user_id in task["assigned_to"]:
                    if user_id not in user_tasks:
                        user_tasks[user_id] = 0
                        user_completed[user_id] = 0
                    
                    user_tasks[user_id] += 1
                    if task["status"] == "completed":
                        user_completed[user_id] += 1
        embed = discord.Embed(
            title="📊 Task Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        progress_percent = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
        progress_bar = self.create_progress_bar(progress_percent)
        
        embed.add_field(
            name="Overall Progress",
            value=f"{progress_bar} {progress_percent:.1f}%\n{completed_tasks}/{total_tasks} tasks completed",
            inline=False
        )
        embed.add_field(
            name="Status Breakdown",
            value=f"📝 Open: {open_tasks}\n⏳ In Progress: {in_progress_tasks}\n✅ Completed: {completed_tasks}",
            inline=True
        )
        embed.add_field(
            name="Priority Breakdown",
            value=f"🟢 Low: {low_priority}\n🟡 Medium: {medium_priority}\n🔴 High: {high_priority}",
            inline=True
        )
        embed.add_field(
            name="Due Date Statistics",
            value=f"⚠️ Overdue: {overdue_tasks}\n📅 Due Today: {due_today}\n📆 Due This Week: {due_this_week}",
            inline=True
        )
        if user_tasks:
            sorted_users = sorted(user_tasks.keys(), key=lambda u: user_completed.get(u, 0), reverse=True)
            
            top_users = []
            for i, user_id in enumerate(sorted_users[:5]):
                member = interaction.guild.get_member(int(user_id))
                name = member.display_name if member else f"User {user_id}"
                completion_rate = (user_completed[user_id] / user_tasks[user_id]) * 100 if user_tasks[user_id] > 0 else 0
                
                top_users.append(f"{i+1}. {name}: {user_completed[user_id]}/{user_tasks[user_id]} ({completion_rate:.1f}%)")
            
            embed.add_field(
                name="🏆 Top Task Completers",
                value="\n".join(top_users) if top_users else "No data available",
                inline=False
            )
            
        embed.set_footer(text="Task Manager by TheZ")
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="pin-tasks", description="Pin the task list to the channel")
    async def pin_tasks_command(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You need 'Manage Messages' permission to pin tasks.", ephemeral=True)
            return
        guild_tasks = {}
        for task_id, task in self.tasks["tasks"].items():
            if task.get("guild_id") == interaction.guild_id and task["status"] != "completed":
                guild_tasks[task_id] = task
        
        if not guild_tasks:
            await interaction.response.send_message("No active tasks to pin.", ephemeral=True)
            return
        embed = discord.Embed(
            title="📌 Pinned Task List",
            description="Here are the current active tasks:",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        sorted_tasks = sorted(guild_tasks.items(), key=lambda x: datetime.datetime.fromisoformat(x[1]["due_date"]))
        
        for task_id, task in sorted_tasks:
            due_date = datetime.datetime.fromisoformat(task["due_date"])
            due_str = due_date.strftime("%b %d, %Y")
            
            priority_emoji = "🟢" if task.get("priority") == "low" else "🟡" if task.get("priority") == "medium" else "🔴"
            status_emoji = STATUS_EMOJIS.get(task["status"], "📝")
            assigned_text = ""
            if task.get("assigned_to"):
                assigned_users = []
                for user_id in task["assigned_to"]:
                    assigned_users.append(f"<@{user_id}>")
                assigned_text = f"\nAssigned to: {', '.join(assigned_users)}"
            
            embed.add_field(
                name=f"{priority_emoji} {status_emoji} {task['name']} [{task_id[:8]}]",
                value=f"{task['description'][:100]}{'...' if len(task['description']) > 100 else ''}\nDue: {due_str}{assigned_text}",
                inline=False
            )
        await interaction.response.send_message("Pinning task list...", ephemeral=True)
        message = await interaction.channel.send(embed=embed)
        await message.pin()
        try:
            async for msg in interaction.channel.history(limit=10):
                if msg.type == discord.MessageType.pins_add and msg.author.id == interaction.client.user.id:
                    await msg.delete()
                    break
        except:
            pass
        
        await interaction.edit_original_response(content="Task list has been pinned to the channel!")

    @app_commands.command(name="archived-tasks", description="View archived tasks")
    async def archived_tasks_command(self, interaction: discord.Interaction):
        guild_archived_tasks = {}
        for task_id, task in self.tasks["archived"].items():
            if task.get("guild_id") == interaction.guild_id:
                guild_archived_tasks[task_id] = task
        
        if not guild_archived_tasks:
            await interaction.response.send_message("No archived tasks found.", ephemeral=True)
            return
        embed = discord.Embed(
            title="📁 Archived Tasks",
            description="Here are your archived tasks:",
            color=discord.Color.dark_gray(),
            timestamp=datetime.datetime.now()
        )
        sorted_tasks = sorted(
            guild_archived_tasks.items(), 
            key=lambda x: datetime.datetime.fromisoformat(x[1].get("completed_at", x[1]["created_at"])),
            reverse=True
        )
        
        for task_id, task in sorted_tasks[:15]:  # Limit to 15 tasks to avoid embed limits
            completed_at = datetime.datetime.fromisoformat(task.get("completed_at", task["created_at"]))
            completed_str = completed_at.strftime("%b %d, %Y")
            
            priority_emoji = "🟢" if task.get("priority") == "low" else "🟡" if task.get("priority") == "medium" else "🔴"
            
            embed.add_field(
                name=f"{priority_emoji} {task['name']} [{task_id[:8]}]",
                value=f"{task['description'][:100]}{'...' if len(task['description']) > 100 else ''}\nCompleted: {completed_str}",
                inline=False
            )
        
        if len(sorted_tasks) > 15:
            embed.set_footer(text=f"Showing 15 of {len(sorted_tasks)} archived tasks")
        view = ArchivedTasksView(self, guild_archived_tasks)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="my-tasks", description="Show tasks assigned to you")
    async def my_tasks_command(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        assigned_tasks = {}
        for task_id, task in self.tasks["tasks"].items():
            if task.get("guild_id") == interaction.guild_id and user_id in task.get("assigned_to", []):
                assigned_tasks[task_id] = task
        
        if not assigned_tasks:
            await interaction.response.send_message("You don't have any tasks assigned to you.", ephemeral=True)
            return
        embed = discord.Embed(
            title="📋 My Tasks",
            description=f"Tasks assigned to {interaction.user.display_name}:",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        open_tasks = []
        in_progress_tasks = []
        completed_tasks = []
        
        for task_id, task in assigned_tasks.items():
            due_date = datetime.datetime.fromisoformat(task["due_date"])
            due_str = due_date.strftime("%b %d")
            
            priority_emoji = "🟢" if task.get("priority") == "low" else "🟡" if task.get("priority") == "medium" else "🔴"
            
            task_line = f"{priority_emoji} [{task_id[:8]}] **{task['name']}** (Due: {due_str})"
            
            if task["status"] == "open":
                open_tasks.append(task_line)
            elif task["status"] == "in_progress":
                in_progress_tasks.append(task_line)
            elif task["status"] == "completed":
                completed_tasks.append(task_line)
        if open_tasks:
            embed.add_field(name="📝 Open", value="\n".join(open_tasks), inline=False)
        if in_progress_tasks:
            embed.add_field(name="⏳ In Progress", value="\n".join(in_progress_tasks), inline=False)
        if completed_tasks:
            embed.add_field(name="✅ Completed", value="\n".join(completed_tasks), inline=False)
        total_tasks = len(assigned_tasks)
        completed_count = len(completed_tasks)
        progress_percent = (completed_count / total_tasks) * 100 if total_tasks > 0 else 0
        progress_bar = self.create_progress_bar(progress_percent)
        
        embed.add_field(name="📊 Progress", value=f"{progress_bar} {progress_percent:.1f}% ({completed_count}/{total_tasks})", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="overdue-tasks", description="Show overdue tasks")
    async def overdue_tasks_command(self, interaction: discord.Interaction):
        now = datetime.datetime.now()
        overdue_tasks = {}
        
        for task_id, task in self.tasks["tasks"].items():
            if task.get("guild_id") == interaction.guild_id and task["status"] != "completed":
                due_date = datetime.datetime.fromisoformat(task["due_date"])
                if due_date < now:
                    overdue_tasks[task_id] = task
        
        if not overdue_tasks:
            await interaction.response.send_message("No overdue tasks found.", ephemeral=True)
            return
        embed = discord.Embed(
            title="⚠️ Overdue Tasks",
            description="These tasks are past their due date:",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        sorted_tasks = sorted(overdue_tasks.items(), key=lambda x: datetime.datetime.fromisoformat(x[1]["due_date"]))
        
        for task_id, task in sorted_tasks:
            due_date = datetime.datetime.fromisoformat(task["due_date"])
            days_overdue = (now - due_date).days
            
            priority_emoji = "🟢" if task.get("priority") == "low" else "🟡" if task.get("priority") == "medium" else "🔴"
            assigned_text = ""
            if task.get("assigned_to"):
                assigned_users = []
                for user_id in task["assigned_to"]:
                    assigned_users.append(f"<@{user_id}>")
                assigned_text = f"\nAssigned to: {', '.join(assigned_users)}"
            
            embed.add_field(
                name=f"{priority_emoji} {task['name']} [{task_id[:8]}]",
                value=f"{task['description'][:100]}{'...' if len(task['description']) > 100 else ''}\n⏰ **{days_overdue} days overdue**{assigned_text}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="upcoming-tasks", description="Show upcoming tasks")
    @app_commands.describe(days="Number of days to look ahead (default: 7)")
    async def upcoming_tasks_command(self, interaction: discord.Interaction, days: int = 7):
        if days <= 0 or days > 30:
            await interaction.response.send_message("Please specify a number of days between 1 and 30.", ephemeral=True)
            return
        now = datetime.datetime.now()
        end_date = now + datetime.timedelta(days=days)
        upcoming_tasks = {}
        
        for task_id, task in self.tasks["tasks"].items():
            if task.get("guild_id") == interaction.guild_id and task["status"] != "completed":
                due_date = datetime.datetime.fromisoformat(task["due_date"])
                if now <= due_date <= end_date:
                    upcoming_tasks[task_id] = task
        
        if not upcoming_tasks:
            await interaction.response.send_message(f"No tasks due in the next {days} days.", ephemeral=True)
            return
        embed = discord.Embed(
            title=f"📅 Upcoming Tasks (Next {days} Days)",
            description="These tasks are due soon:",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now()
        )
        sorted_tasks = sorted(upcoming_tasks.items(), key=lambda x: datetime.datetime.fromisoformat(x[1]["due_date"]))
        
        for task_id, task in sorted_tasks:
            due_date = datetime.datetime.fromisoformat(task["due_date"])
            days_until = (due_date - now).days
            
            if days_until == 0:
                due_text = "**Due today!**"
            elif days_until == 1:
                due_text = "**Due tomorrow!**"
            else:
                due_text = f"**Due in {days_until} days**"
            
            priority_emoji = "🟢" if task.get("priority") == "low" else "🟡" if task.get("priority") == "medium" else "🔴"
            assigned_text = ""
            if task.get("assigned_to"):
                assigned_users = []
                for user_id in task["assigned_to"]:
                    assigned_users.append(f"<@{user_id}>")
                assigned_text = f"\nAssigned to: {', '.join(assigned_users)}"
            
            embed.add_field(
                name=f"{priority_emoji} {task['name']} [{task_id[:8]}]",
                value=f"{task['description'][:100]}{'...' if len(task['description']) > 100 else ''}\n⏰ {due_text} ({due_date.strftime('%b %d')}){assigned_text}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    def create_task_embed(self, task_id, task):
        if task.get("priority") == "high":
            color = discord.Color.red()
        elif task.get("priority") == "medium":
            color = discord.Color.gold()
        else:
            color = discord.Color.green()
        status_emoji = STATUS_EMOJIS.get(task["status"], "📝")
        
        embed = discord.Embed(
            title=f"{status_emoji} Task: {task['name']}",
            description=task["description"],
            color=color,
            timestamp=datetime.datetime.now()
        )
        due_date = datetime.datetime.fromisoformat(task["due_date"])
        formatted_date = due_date.strftime("%B %d, %Y at %I:%M %p")
        now = datetime.datetime.now()
        if due_date < now and task["status"] != "completed":
            days_overdue = (now - due_date).days
            overdue_text = f"⚠️ **OVERDUE by {days_overdue} days**"
            embed.add_field(name="Due Date", value=f"{formatted_date}\n{overdue_text}", inline=True)
        else:
            embed.add_field(name="Due Date", value=formatted_date, inline=True)
        embed.add_field(name="ID", value=task_id, inline=True)
        embed.add_field(name="Priority", value=task.get("priority", "medium").capitalize(), inline=True)
        embed.add_field(name="Status", value=task["status"].replace("_", " ").capitalize(), inline=True)
        if task.get("assigned_to"):
            assigned_users = []
            for user_id in task["assigned_to"]:
                assigned_users.append(f"<@{user_id}>")
            embed.add_field(name="Assigned To", value=", ".join(assigned_users), inline=False)
        if task.get("project_id") and task["project_id"] in self.tasks["projects"]:
            project = self.tasks["projects"][task["project_id"]]
            embed.add_field(name="Project", value=f"📂 {project['name']}", inline=True)
        if task["status"] == "completed" and task.get("completed_at"):
            completed_at = datetime.datetime.fromisoformat(task["completed_at"])
            completed_by = task.get("completed_by_name", "Unknown")
            embed.add_field(name="Completed", value=f"By {completed_by} on {completed_at.strftime('%B %d, %Y')}", inline=False)
        created_at = datetime.datetime.fromisoformat(task["created_at"])
        embed.set_footer(text=f"Created by {task['created_by_name']} • {created_at.strftime('%B %d, %Y')}")
        
        return embed

class ProjectListView(discord.ui.View):
    def __init__(self, cog, projects):
        super().__init__(timeout=180)
        self.cog = cog
        self.projects = projects
        options = []
        for project_id, project in projects.items():
            options.append(
                discord.SelectOption(
                    label=f"{project['name']} [{project_id[:8]}]",
                    value=project_id,
                    description=f"Due: {datetime.datetime.fromisoformat(project['due_date']).strftime('%b %d, %Y')}"
                )
            )
        if options:
            self.add_item(ProjectSelect(options))
    
    @discord.ui.button(label="Repost Selected Project", style=discord.ButtonStyle.primary)
    async def repost_project_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not hasattr(self, 'selected_project_id'):
            await interaction.response.send_message("Please select a project first.", ephemeral=True)
            return
        
        project_id = self.selected_project_id
        project = self.projects.get(project_id)
        
        if not project:
            await interaction.response.send_message("Project not found.", ephemeral=True)
            return
        embed = self.create_project_embed(project_id, project)
        view = self.cog.ProjectView(self.cog, project_id, project)
        await interaction.response.send_message("Reposting project...", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)
    
    @discord.ui.button(label="Repost in Different Channel", style=discord.ButtonStyle.secondary)
    async def repost_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not hasattr(self, 'selected_project_id'):
            await interaction.response.send_message("Please select a project first.", ephemeral=True)
            return
        await interaction.response.send_modal(ChannelSelectModal(self))
    
    def create_project_embed(self, project_id, project):
        embed = discord.Embed(
            title=f"📂 Project: {project['name']}",
            description=project["description"],
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        due_date = datetime.datetime.fromisoformat(project["due_date"])
        formatted_date = due_date.strftime("%B %d, %Y at %I:%M %p")
        embed.add_field(name="ID", value=project_id, inline=True)
        embed.add_field(name="Due Date", value=formatted_date, inline=True)
        task_count = 0
        completed_count = 0
        for task in self.cog.tasks["tasks"].values():
            if task.get("project_id") == project_id:
                task_count += 1
                if task["status"] == "completed":
                    completed_count += 1
        
        if task_count > 0:
            progress_percent = (completed_count / task_count) * 100
            progress_bar = self.cog.create_progress_bar(progress_percent)
            embed.add_field(
                name="Progress",
                value=f"{progress_bar} {progress_percent:.1f}% ({completed_count}/{task_count})",
                inline=False
            )
        created_at = datetime.datetime.fromisoformat(project["created_at"])
        embed.set_footer(text=f"Created by {project['created_by_name']} • {created_at.strftime('%B %d, %Y')}")
        
        return embed


class ProjectSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Select a project...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        self.view.selected_project_id = self.values[0]
        await interaction.response.send_message(f"Project selected. You can now repost it using the buttons below.", ephemeral=True)

class ChannelSelectModal(discord.ui.Modal, title="Select Channel"):
    def __init__(self, project_view):
        super().__init__()
        self.project_view = project_view
        
        self.channel_id = discord.ui.TextInput(
            label="Channel ID",
            placeholder="Enter the channel ID where you want to post this project",
            required=True
        )
        
        self.add_item(self.channel_id)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_id.value.strip())
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                await interaction.response.send_message("Channel not found. Please check the ID and try again.", ephemeral=True)
                return
            if not channel.permissions_for(interaction.guild.me).send_messages:
                await interaction.response.send_message("I don't have permission to send messages in that channel.", ephemeral=True)
                return
            project_id = self.project_view.selected_project_id
            project = self.project_view.projects.get(project_id)
            
            if not project:
                await interaction.response.send_message("Project not found. It may have been deleted.", ephemeral=True)
                return
            embed = self.project_view.create_project_embed(project_id, project)
            view = self.project_view.cog.ProjectView(self.project_view.cog, project_id, project)
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"Project posted to <#{channel_id}>!", ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("Invalid channel ID. Please enter a valid number.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

    
    async def callback(self, interaction: discord.Interaction):
        self.view.selected_project_id = self.values[0]
        await interaction.response.send_message(f"Project selected. You can now repost it.", ephemeral=True)

class ChannelSelectModal(discord.ui.Modal, title="Select Channel"):
    def __init__(self, project_view):
        super().__init__()
        self.project_view = project_view
        
        self.channel_id = discord.ui.TextInput(
            label="Channel ID",
            placeholder="Enter the channel ID where you want to post the project",
            required=True
        )
        
        self.add_item(self.channel_id)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_id.value.strip())
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                await interaction.response.send_message("Channel not found. Please check the ID.", ephemeral=True)
                return
            permissions = channel.permissions_for(interaction.guild.me)
            if not (permissions.send_messages and permissions.embed_links):
                await interaction.response.send_message("I don't have permission to send messages or embeds in that channel.", ephemeral=True)
                return
            project_id = self.project_view.selected_project_id
            project = self.project_view.projects.get(project_id)
            
            if not project:
                await interaction.response.send_message("Project not found.", ephemeral=True)
                return
            embed = self.project_view.create_project_embed(project_id, project)
            view = self.project_view.cog.ProjectView(self.project_view.cog, project_id, project)
            await interaction.response.send_message(f"Reposting project to <#{channel_id}>...", ephemeral=True)
            await channel.send(embed=embed, view=view)
            
        except ValueError:
            await interaction.response.send_message("Invalid channel ID. Please enter a valid number.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

class ArchivedTasksView(discord.ui.View):
    def __init__(self, cog, archived_tasks):
        super().__init__(timeout=180)
        self.cog = cog
        self.archived_tasks = archived_tasks
        options = []
        for task_id, task in archived_tasks.items():
            completed_at = datetime.datetime.fromisoformat(task.get("completed_at", task["created_at"]))
            options.append(
                discord.SelectOption(
                    label=f"{task['name']} [{task_id[:8]}]",
                    value=task_id,
                    description=f"Completed: {completed_at.strftime('%b %d, %Y')}"
                )
            )
        if options:
            if len(options) > 25:
                options = options[:25]
            self.add_item(ArchivedTaskSelect(options))
    
    @discord.ui.button(label="View Selected Task", style=discord.ButtonStyle.primary)
    async def view_task_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not hasattr(self, 'selected_task_id'):
            await interaction.response.send_message("Please select a task first.", ephemeral=True)
            return
        
        task_id = self.selected_task_id
        task = self.archived_tasks.get(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found.", ephemeral=True)
            return
        embed = self.cog.create_task_embed(task_id, task)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Restore Task", style=discord.ButtonStyle.success)
    async def restore_task_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not hasattr(self, 'selected_task_id'):
            await interaction.response.send_message("Please select a task first.", ephemeral=True)
            return
        
        task_id = self.selected_task_id
        task = self.archived_tasks.get(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found.", ephemeral=True)
            return
        self.cog.tasks["tasks"][task_id] = task
        del self.cog.tasks["archived"][task_id]
        task["status"] = "completed"
        task["updated_at"] = datetime.datetime.now().isoformat()
        task["updated_by"] = str(interaction.user.id)
        task["updated_by_name"] = interaction.user.display_name
        
        self.cog.save_tasks()
        embed = self.cog.create_task_embed(task_id, task)
        view = self.cog.TaskView(self.cog, task_id, task)
        await interaction.response.send_message("Task restored successfully!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)
    
    @discord.ui.button(label="Delete Permanently", style=discord.ButtonStyle.danger)
    async def delete_task_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not hasattr(self, 'selected_task_id'):
            await interaction.response.send_message("Please select a task first.", ephemeral=True)
            return
        
        task_id = self.selected_task_id
        task = self.archived_tasks.get(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found.", ephemeral=True)
            return
        view = self.cog.ConfirmView()
        await interaction.response.send_message(f"Are you sure you want to permanently delete task **{task['name']}**? This cannot be undone.", view=view, ephemeral=True)
        await view.wait()
        if view.value:
            del self.cog.tasks["archived"][task_id]
            self.cog.save_tasks()
            await interaction.edit_original_response(content=f"Task **{task['name']}** has been permanently deleted.", view=None)
        else:
            await interaction.edit_original_response(content="Task deletion cancelled.", view=None)

class ArchivedTaskSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Select an archived task...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        self.view.selected_task_id = self.values[0]
        await interaction.response.send_message(f"Task selected. You can now view or restore it.", ephemeral=True)
class TaskListView(discord.ui.View):
    def __init__(self, cog, tasks):
        super().__init__(timeout=180)
        self.cog = cog
        self.tasks = tasks
        options = []
        for task_id, task in tasks.items():
            priority_emoji = "🟢" if task.get("priority") == "low" else "🟡" if task.get("priority") == "medium" else "🔴"
            status_emoji = STATUS_EMOJIS.get(task["status"], "📝")
            due_date = datetime.datetime.fromisoformat(task["due_date"])
            due_str = due_date.strftime("%b %d")
            option = discord.SelectOption(
                label=f"{task['name']} [{task_id[:8]}]",
                description=f"Due: {due_str} | {task['status'].replace('_', ' ').title()}",
                value=task_id,
                emoji=priority_emoji
            )
            options.append(option)
        if len(options) > 25:
            options = options[:25]
            
        if options:
            self.add_item(TaskSelect(options))
            
    @discord.ui.button(label="View Selected Task", style=discord.ButtonStyle.primary)
    async def view_task_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not hasattr(self, 'selected_task_id'):
            await interaction.response.send_message("Please select a task first using the dropdown menu.", ephemeral=True)
            return
        
        task_id = self.selected_task_id
        task = self.tasks.get(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found. It may have been deleted.", ephemeral=True)
            return
        embed = self.cog.create_task_embed(task_id, task)
        view = self.cog.TaskView(self.cog, task_id, task)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Edit Selected Task", style=discord.ButtonStyle.secondary)
    async def edit_task_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not hasattr(self, 'selected_task_id'):
            await interaction.response.send_message("Please select a task first using the dropdown menu.", ephemeral=True)
            return
        
        task_id = self.selected_task_id
        task = self.tasks.get(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found. It may have been deleted.", ephemeral=True)
            return
        if not await self.check_permission(interaction, task):
            return
        await interaction.response.send_modal(self.cog.EditTaskModal(self.cog, task_id, task))
    
    @discord.ui.button(label="Change Status", style=discord.ButtonStyle.secondary)
    async def change_status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not hasattr(self, 'selected_task_id'):
            await interaction.response.send_message("Please select a task first using the dropdown menu.", ephemeral=True)
            return
        
        task_id = self.selected_task_id
        task = self.tasks.get(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found. It may have been deleted.", ephemeral=True)
            return
        if not await self.check_permission(interaction, task):
            return
        view = self.cog.StatusSelectView(self.cog, task_id, task)
        await interaction.response.send_message("Select a new status:", view=view, ephemeral=True)
    
    @discord.ui.button(label="Repost Task", style=discord.ButtonStyle.success)
    async def repost_task_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not hasattr(self, 'selected_task_id'):
            await interaction.response.send_message("Please select a task first using the dropdown menu.", ephemeral=True)
            return
        
        task_id = self.selected_task_id
        task = self.tasks.get(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found. It may have been deleted.", ephemeral=True)
            return
        embed = self.cog.create_task_embed(task_id, task)
        view = self.cog.TaskView(self.cog, task_id, task)
        await interaction.response.send_message("Reposting task...", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)
    
    async def check_permission(self, interaction, task):
        if str(interaction.user.id) == task.get("created_by"):
            return True
        if str(interaction.user.id) in task.get("assigned_to", []):
            return True
        if interaction.user.guild_permissions.administrator:
            return True
            
        await interaction.response.send_message("You don't have permission to modify this task.", ephemeral=True)
        return False

class TaskSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Select a task...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        self.view.selected_task_id = self.values[0]
        await interaction.response.send_message(f"Task selected. You can now view, edit, or repost it using the buttons below.", ephemeral=True)

class ProjectTaskListView(discord.ui.View):
    def __init__(self, cog, tasks):
        super().__init__(timeout=180)
        self.cog = cog
        self.tasks = tasks
        options = []
        for task_id, task in tasks.items():
            priority_emoji = "🟢" if task.get("priority") == "low" else "🟡" if task.get("priority") == "medium" else "🔴"
            status_emoji = STATUS_EMOJIS.get(task["status"], "📝")
            due_date = datetime.datetime.fromisoformat(task["due_date"])
            due_str = due_date.strftime("%b %d")
            option = discord.SelectOption(
                label=f"{task['name']} [{task_id[:8]}]",
                description=f"Due: {due_str} | {task['status'].replace('_', ' ').title()}",
                value=task_id,
                emoji=priority_emoji
            )
            options.append(option)
        if len(options) > 25:
            options = options[:25]
            
        if options:
            self.add_item(TaskSelect(options))
    
    @discord.ui.button(label="View Selected Task", style=discord.ButtonStyle.primary)
    async def view_task_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not hasattr(self, 'selected_task_id'):
            await interaction.response.send_message("Please select a task first using the dropdown menu.", ephemeral=True)
            return
        
        task_id = self.selected_task_id
        task = self.tasks.get(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found. It may have been deleted.", ephemeral=True)
            return
        embed = self.cog.create_task_embed(task_id, task)
        view = self.cog.TaskView(self.cog, task_id, task)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Repost Selected Task", style=discord.ButtonStyle.success)
    async def repost_task_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not hasattr(self, 'selected_task_id'):
            await interaction.response.send_message("Please select a task first using the dropdown menu.", ephemeral=True)
            return
        
        task_id = self.selected_task_id
        task = self.tasks.get(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found. It may have been deleted.", ephemeral=True)
            return
        embed = self.cog.create_task_embed(task_id, task)
        view = self.cog.TaskView(self.cog, task_id, task)
        await interaction.response.send_message("Reposting task...", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)

class ProjectTaskSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Select a task from this project...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        self.view.selected_task_id = self.values[0]
        await interaction.response.send_message(f"Task selected. You can now view or repost it using the buttons below.", ephemeral=True)

def setup(bot):
    cog = TaskManager(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog

