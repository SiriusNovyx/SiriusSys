import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
from typing import Optional, Dict, List
import re

class RoleControlConfig:
    def __init__(self):
        self.config_dir = "RoleControl"
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.templates_file = os.path.join(self.config_dir, "templates.json")
        self.ensure_directories()
        
    def ensure_directories(self):
        os.makedirs(self.config_dir, exist_ok=True)
        
    def load_config(self) -> Dict:
        if not os.path.exists(self.config_file):
            default_config = {"guilds": {}}
            self.save_config(default_config)
            return default_config
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except:
            return {"guilds": {}}
            
    def save_config(self, config: Dict):
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=4)
            
    def load_templates(self) -> Dict:
        if not os.path.exists(self.templates_file):
            default_templates = {
                "Moderator": {
                    "permissions": {
                        "kick_members": True,
                        "ban_members": True,
                        "manage_messages": True,
                        "mute_members": True,
                        "deafen_members": True,
                        "move_members": True
                    },
                    "color": "#ff6b6b",
                    "hoist": True,
                    "mentionable": True
                },
                "Helper": {
                    "permissions": {
                        "manage_messages": True,
                        "mute_members": True,
                        "deafen_members": True
                    },
                    "color": "#4ecdc4",
                    "hoist": True,
                    "mentionable": True
                },
                "Member": {
                    "permissions": {
                        "send_messages": True,
                        "read_messages": True,
                        "connect": True,
                        "speak": True
                    },
                    "color": "#45b7d1",
                    "hoist": False,
                    "mentionable": False
                }
            }
            self.save_templates(default_templates)
            return default_templates
        try:
            with open(self.templates_file, 'r') as f:
                return json.load(f)
        except:
            return {}
            
    def save_templates(self, templates: Dict):
        with open(self.templates_file, 'w') as f:
            json.dump(templates, f, indent=4)

class RoleSelectView(discord.ui.View):
    def __init__(self, cog, guild: discord.Guild):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        
    @discord.ui.select(
        placeholder="🎭 Select a role to manage or create new...",
        options=[
            discord.SelectOption(
                label="Create New Role",
                value="create_new",
                emoji="➕",
                description="Create a brand new role"
            )
        ]
    )
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if select.values[0] == "create_new":
            await interaction.response.send_modal(CreateRoleModal(self.cog, self.guild))
        else:
            role_id = int(select.values[0])
            role = self.guild.get_role(role_id)
            if role:
                view = RoleManagementView(self.cog, role)
                embed = self.cog.create_role_management_embed(role)
                await interaction.response.edit_message(embed=embed, view=view)
                
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

class CreateRoleModal(discord.ui.Modal):
    def __init__(self, cog, guild: discord.Guild):
        super().__init__(title="Create New Role")
        self.cog = cog
        self.guild = guild
        
    role_name = discord.ui.TextInput(
        label="Role Name",
        placeholder="Enter the role name...",
        required=True,
        max_length=100
    )
    
    role_color = discord.ui.TextInput(
        label="Role Color (Hex)",
        placeholder="#ff6b6b or ff6b6b",
        required=False,
        max_length=7
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:

            color = discord.Color.default()
            if self.role_color.value:
                hex_color = self.role_color.value.strip()
                if not hex_color.startswith('#'):
                    hex_color = '#' + hex_color
                if re.match(r'^#[0-9A-Fa-f]{6}$', hex_color):
                    color = discord.Color(int(hex_color[1:], 16))
                    

            role = await self.guild.create_role(
                name=self.role_name.value,
                color=color,
                reason=f"Role created by {interaction.user}"
            )
            

            view = RoleManagementView(self.cog, role)
            embed = self.cog.create_role_management_embed(role)
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error creating role: {str(e)}", ephemeral=True)

class RoleManagementView(discord.ui.View):
    def __init__(self, cog, role: discord.Role):
        super().__init__(timeout=300)
        self.cog = cog
        self.role = role
        
    @discord.ui.button(label="Edit Permissions", emoji="🔐", style=discord.ButtonStyle.primary)
    async def edit_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PermissionManagementView(self.cog, self.role)
        embed = self.cog.create_permission_embed(self.role)
        await interaction.response.edit_message(embed=embed, view=view)
        
    @discord.ui.button(label="Edit Appearance", emoji="🎨", style=discord.ButtonStyle.secondary)
    async def edit_appearance(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditAppearanceModal(self.cog, self.role))
        
    @discord.ui.button(label="Role Position", emoji="📊", style=discord.ButtonStyle.secondary)
    async def edit_position(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditPositionModal(self.cog, self.role))
        
    @discord.ui.button(label="Apply Template", emoji="📋", style=discord.ButtonStyle.success)
    async def apply_template(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = TemplateSelectView(self.cog, self.role)
        embed = self.cog.create_template_embed()
        await interaction.response.edit_message(embed=embed, view=view)
        
    @discord.ui.button(label="Delete Role", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def delete_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ConfirmDeleteView(self.cog, self.role)
        embed = discord.Embed(
            title="⚠️ Confirm Role Deletion",
            description=f"Are you sure you want to delete the role **{self.role.name}**?\n\n"
                       f"👥 **Members with this role:** {len(self.role.members)}\n"
                       f"🔢 **Role position:** {self.role.position}\n\n"
                       f"**This action cannot be undone!**",
            color=discord.Color.red()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.edit_message(embed=embed, view=view)
        
    @discord.ui.button(label="Back to Main", emoji="🏠", style=discord.ButtonStyle.gray, row=1)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = await self.cog.create_main_view(interaction.guild)
        embed = self.cog.create_main_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=view)

class PermissionManagementView(discord.ui.View):
    def __init__(self, cog, role: discord.Role):
        super().__init__(timeout=300)
        self.cog = cog
        self.role = role
        
    @discord.ui.select(
        placeholder="🔐 Select permission category...",
        options=[
            discord.SelectOption(label="General Permissions", value="general", emoji="⚙️"),
            discord.SelectOption(label="Membership Permissions", value="membership", emoji="👥"),
            discord.SelectOption(label="Text Permissions", value="text", emoji="💬"),
            discord.SelectOption(label="Voice Permissions", value="voice", emoji="🔊"),
            discord.SelectOption(label="Advanced Permissions", value="advanced", emoji="🔧")
        ]
    )
    async def permission_category_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        category = select.values[0]
        view = SpecificPermissionView(self.cog, self.role, category)
        embed = self.cog.create_specific_permission_embed(self.role, category)
        await interaction.response.edit_message(embed=embed, view=view)
        
    @discord.ui.button(label="Back to Role", emoji="🔙", style=discord.ButtonStyle.gray)
    async def back_to_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RoleManagementView(self.cog, self.role)
        embed = self.cog.create_role_management_embed(self.role)
        await interaction.response.edit_message(embed=embed, view=view)

class SpecificPermissionView(discord.ui.View):
    def __init__(self, cog, role: discord.Role, category: str):
        super().__init__(timeout=300)
        self.cog = cog
        self.role = role
        self.category = category
        self.add_permission_toggles()
        
    def add_permission_toggles(self):
        permissions_map = {
            "general": [
                ("administrator", "Administrator", "👑"),
                ("manage_guild", "Manage Server", "🏰"),
                ("manage_roles", "Manage Roles", "🎭"),
                ("manage_channels", "Manage Channels", "📝"),
                ("view_audit_log", "View Audit Log", "📋")
            ],
            "membership": [
                ("kick_members", "Kick Members", "👢"),
                ("ban_members", "Ban Members", "🔨"),
                ("create_instant_invite", "Create Invite", "📨"),
                ("change_nickname", "Change Nickname", "✏️"),
                ("manage_nicknames", "Manage Nicknames", "📝")
            ],
            "text": [
                ("send_messages", "Send Messages", "💬"),
                ("manage_messages", "Manage Messages", "🗑️"),
                ("embed_links", "Embed Links", "🔗"),
                ("attach_files", "Attach Files", "📎"),
                ("mention_everyone", "Mention Everyone", "📢")
            ],
            "voice": [
                ("connect", "Connect", "🔊"),
                ("speak", "Speak", "🎤"),
                ("mute_members", "Mute Members", "🔇"),
                ("deafen_members", "Deafen Members", "🔈"),
                ("move_members", "Move Members", "↔️")
            ],
            "advanced": [
                ("manage_webhooks", "Manage Webhooks", "🪝"),
                ("manage_emojis_and_stickers", "Manage Emojis", "😀"),
                ("use_application_commands", "Use App Commands", "⚡"),
                ("priority_speaker", "Priority Speaker", "📻"),
                ("stream", "Video/Stream", "📹")
            ]
        }
        
        perms = permissions_map.get(self.category, [])
        current_perms = self.role.permissions
        
        for i, (perm_name, display_name, emoji) in enumerate(perms[:25]):  
            has_perm = getattr(current_perms, perm_name, False)
            style = discord.ButtonStyle.success if has_perm else discord.ButtonStyle.secondary
            button = discord.ui.Button(
                label=display_name,
                emoji=emoji,
                style=style,
                custom_id=f"perm_{perm_name}",
                row=i // 5
            )
            button.callback = self.create_permission_callback(perm_name)
            self.add_item(button)
            
        back_button = discord.ui.Button(label="Back", emoji="🔙", style=discord.ButtonStyle.gray, row=4)
        back_button.callback = self.back_callback
        self.add_item(back_button)
        
    def create_permission_callback(self, perm_name: str):
        async def callback(interaction: discord.Interaction):
            try:
                current_perms = self.role.permissions
                new_value = not getattr(current_perms, perm_name, False)
                
                new_perms = discord.Permissions(permissions=current_perms.value)
                
                setattr(new_perms, perm_name, new_value)
                
                await self.role.edit(
                    permissions=new_perms,
                    reason=f"Permission '{perm_name}' {'enabled' if new_value else 'disabled'} by {interaction.user}"
                )
                
                view = SpecificPermissionView(self.cog, self.role, self.category)
                embed = self.cog.create_specific_permission_embed(self.role, self.category)
                await interaction.response.edit_message(embed=embed, view=view)
                
            except Exception as e:
                await interaction.response.send_message(f"❌ Error updating permission: {str(e)}", ephemeral=True)
        return callback
        
    async def back_callback(self, interaction: discord.Interaction):
        view = PermissionManagementView(self.cog, self.role)
        embed = self.cog.create_permission_embed(self.role)
        await interaction.response.edit_message(embed=embed, view=view)


class EditAppearanceModal(discord.ui.Modal):
    def __init__(self, cog, role: discord.Role):
        super().__init__(title=f"Edit {role.name} Appearance")
        self.cog = cog
        self.role = role
        

        self.role_name.default = role.name
        self.role_color.default = f"#{role.color.value:06x}" if role.color.value != 0 else ""
        
    role_name = discord.ui.TextInput(
        label="Role Name",
        placeholder="Enter the role name...",
        required=True,
        max_length=100
    )
    
    role_color = discord.ui.TextInput(
        label="Role Color (Hex)",
        placeholder="#ff6b6b or ff6b6b",
        required=False,
        max_length=7
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:

            color = self.role.color
            if self.role_color.value:
                hex_color = self.role_color.value.strip()
                if not hex_color.startswith('#'):
                    hex_color = '#' + hex_color
                if re.match(r'^#[0-9A-Fa-f]{6}$', hex_color):
                    color = discord.Color(int(hex_color[1:], 16))
                    

            await self.role.edit(
                name=self.role_name.value,
                color=color,
                reason=f"Role appearance updated by {interaction.user}"
            )
            

            updated_role = interaction.guild.get_role(self.role.id)
            view = RoleManagementView(self.cog, updated_role)
            embed = self.cog.create_role_management_embed(updated_role)
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error updating role appearance: {str(e)}", ephemeral=True)

class EditPositionModal(discord.ui.Modal):
    def __init__(self, cog, role: discord.Role):
        super().__init__(title=f"Edit {role.name} Position")
        self.cog = cog
        self.role = role
        
        self.position_input.default = str(role.position)
        
    position_input = discord.ui.TextInput(
        label="Role Position",
        placeholder="Enter position number (1 = bottom, higher = top)",
        required=True,
        max_length=3
    )
    
    hoist_toggle = discord.ui.TextInput(
        label="Display Separately (yes/no)",
        placeholder="yes or no",
        required=False,
        max_length=3
    )
    
    mentionable_toggle = discord.ui.TextInput(
        label="Allow Mentions (yes/no)",
        placeholder="yes or no",
        required=False,
        max_length=3
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:

            try:
                position = int(self.position_input.value)
                position = max(1, min(position, len(interaction.guild.roles) - 1))
            except ValueError:
                position = self.role.position
                

            hoist = self.role.hoist
            if self.hoist_toggle.value.lower() in ['yes', 'y', 'true', '1']:
                hoist = True
            elif self.hoist_toggle.value.lower() in ['no', 'n', 'false', '0']:
                hoist = False
                
            mentionable = self.role.mentionable
            if self.mentionable_toggle.value.lower() in ['yes', 'y', 'true', '1']:
                mentionable = True
            elif self.mentionable_toggle.value.lower() in ['no', 'n', 'false', '0']:
                mentionable = False
                

            await self.role.edit(
                position=position,
                hoist=hoist,
                mentionable=mentionable,
                reason=f"Role settings updated by {interaction.user}"
            )
            

            updated_role = interaction.guild.get_role(self.role.id)
            view = RoleManagementView(self.cog, updated_role)
            embed = self.cog.create_role_management_embed(updated_role)
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error updating role settings: {str(e)}", ephemeral=True)

class TemplateSelectView(discord.ui.View):
    def __init__(self, cog, role: discord.Role):
        super().__init__(timeout=300)
        self.cog = cog
        self.role = role
        self.add_template_options()
        
    def add_template_options(self):
        templates = self.cog.config.load_templates()
        
        options = []
        for name, template in templates.items():
            options.append(discord.SelectOption(
                label=name,
                value=name,
                description=f"Color: {template.get('color', '#000000')} | Perms: {len(template.get('permissions', {}))}"
            ))
            
        if options:
            select = discord.ui.Select(
                placeholder="📋 Select a template to apply...",
                options=options[:25]
            )
            select.callback = self.template_select_callback
            self.add_item(select)
            

        back_button = discord.ui.Button(label="Back to Role", emoji="🔙", style=discord.ButtonStyle.gray)
        back_button.callback = self.back_callback
        self.add_item(back_button)
        
    async def template_select_callback(self, interaction: discord.Interaction):
        template_name = interaction.data['values'][0]
        templates = self.cog.config.load_templates()
        template = templates.get(template_name)
        
        if not template:
            await interaction.response.send_message("❌ Template not found!", ephemeral=True)
            return
            
        try:

            permissions = discord.Permissions(**template.get('permissions', {}))
            color = discord.Color.default()
            
            if 'color' in template:
                hex_color = template['color']
                if not hex_color.startswith('#'):
                    hex_color = '#' + hex_color
                if re.match(r'^#[0-9A-Fa-f]{6}$', hex_color):
                    color = discord.Color(int(hex_color[1:], 16))
                    
            await self.role.edit(
                permissions=permissions,
                color=color,
                hoist=template.get('hoist', False),
                mentionable=template.get('mentionable', False),
                reason=f"Template '{template_name}' applied by {interaction.user}"
            )
            

            updated_role = interaction.guild.get_role(self.role.id)
            view = RoleManagementView(self.cog, updated_role)
            embed = self.cog.create_role_management_embed(updated_role)
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error applying template: {str(e)}", ephemeral=True)
            
    async def back_callback(self, interaction: discord.Interaction):
        view = RoleManagementView(self.cog, self.role)
        embed = self.cog.create_role_management_embed(self.role)
        await interaction.response.edit_message(embed=embed, view=view)

class ConfirmDeleteView(discord.ui.View):
    def __init__(self, cog, role: discord.Role):
        super().__init__(timeout=60)
        self.cog = cog
        self.role = role
        
    @discord.ui.button(label="Confirm Delete", emoji="✅", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            role_name = self.role.name
            await self.role.delete(reason=f"Role deleted by {interaction.user}")
            
            embed = discord.Embed(
                title="✅ Role Deleted Successfully",
                description=f"The role **{role_name}** has been permanently deleted.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            

            view = await self.cog.create_main_view(interaction.guild)
            main_embed = self.cog.create_main_embed(interaction.guild)
            await interaction.response.edit_message(embed=main_embed, view=view)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error deleting role: {str(e)}", ephemeral=True)
            
    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RoleManagementView(self.cog, self.role)
        embed = self.cog.create_role_management_embed(self.role)
        await interaction.response.edit_message(embed=embed, view=view)

class RoleControl(commands.Cog):
    
    
    def __init__(self, bot):
        self.bot = bot
        self.config = RoleControlConfig()
        
    async def cog_load(self):
        print("🎛️ Role Control System loaded!")
        
    def get_prefix(self, ctx):
        
        if hasattr(self.bot, 'command_prefix'):
            prefix = self.bot.command_prefix
            if callable(prefix):
                try:
                    prefix = prefix(self.bot, ctx.message)
                    if isinstance(prefix, list):
                        prefix = prefix[0]
                except:
                    prefix = '!'
            return prefix
        return '!'
        
    def create_main_embed(self, guild: discord.Guild) -> discord.Embed:
        
        embed = discord.Embed(
            title="🎛️ Role Control Panel",
            description=f"**Advanced Role & Permission Control for {guild.name}**\n\n"
                       f"🎯 **Total Roles:** {len(guild.roles) - 1}\n"
                       f"👥 **Total Members:** {guild.member_count}\n"
                       f"🔐 **Bot Permissions:** {'✅ Manage Roles' if guild.me.guild_permissions.manage_roles else '❌ Missing Manage Roles'}\n\n"
                       f"**Select a role below to manage or create a new one!**",
            color=discord.Color.blurple()
        )
        

        role_stats = {}
        for role in guild.roles[1:]:
            if role.members:
                role_stats[role.name] = len(role.members)
                
        if role_stats:
            top_roles = sorted(role_stats.items(), key=lambda x: x[1], reverse=True)[:5]
            stats_text = "\n".join([f"**{name}:** {count} members" for name, count in top_roles])
            embed.add_field(
                name="📊 Most Popular Roles",
                value=stats_text,
                inline=True
            )
            
        embed.add_field(
            name="🛠️ Available Actions",
            value="• **Create New Role** - Build from scratch\n"
                  "• **Edit Existing Role** - Modify permissions & appearance\n"
                  "• **Apply Templates** - Use pre-made configurations\n"
                  "• **Manage Positions** - Reorder role hierarchy\n"
                  "• **Bulk Operations** - Mass role management",
            inline=False
        )
        
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed
        
    async def create_main_view(self, guild: discord.Guild) -> RoleSelectView:
        
        view = RoleSelectView(self, guild)
        

        options = [
            discord.SelectOption(
                label="Create New Role",
                value="create_new",
                emoji="➕",
                description="Create a brand new role"
            )
        ]
        

        roles = sorted([r for r in guild.roles if r != guild.default_role], 
                      key=lambda r: r.position, reverse=True)[:24]
        
        for role in roles:
            member_count = len(role.members)
            options.append(discord.SelectOption(
                label=role.name,
                value=str(role.id),
                description=f"Position: {role.position} | Members: {member_count}",
                emoji="🎭"
            ))
            
        view.role_select.options = options
        return view
        
    def create_role_management_embed(self, role: discord.Role) -> discord.Embed:
        
        embed = discord.Embed(
            title=f"🎛️ Managing Role: {role.name}",
            description=f"**Complete role control for {role.mention}**",
            color=role.color if role.color.value != 0 else discord.Color.blurple()
        )
        

        embed.add_field(
            name="📊 Role Information",
            value=f"**Position:** {role.position}\n"
                  f"**Members:** {len(role.members)}\n"
                  f"**Color:** #{role.color.value:06x}\n"
                  f"**Hoisted:** {'Yes' if role.hoist else 'No'}\n"
                  f"**Mentionable:** {'Yes' if role.mentionable else 'No'}",
            inline=True
        )
        

        perms = role.permissions
        key_perms = []
        if perms.administrator:
            key_perms.append("👑 Administrator")
        if perms.manage_guild:
            key_perms.append("🏰 Manage Server")
        if perms.manage_roles:
            key_perms.append("🎭 Manage Roles")
        if perms.kick_members:
            key_perms.append("👢 Kick Members")
        if perms.ban_members:
            key_perms.append("🔨 Ban Members")
            
        embed.add_field(
            name="🔐 Key Permissions",
            value="\n".join(key_perms) if key_perms else "No special permissions",
            inline=True
        )
        

        if len(role.members) <= 10:
            members_text = "\n".join([f"• {member.display_name}" for member in role.members[:10]])
            embed.add_field(
                name=f"👥 Members ({len(role.members)})",
                value=members_text or "No members",
                inline=False
            )
        elif len(role.members) > 10:
            embed.add_field(
                name=f"👥 Members ({len(role.members)})",
                value=f"Too many members to display. Use Discord's member list to view all members with this role.",
                inline=False
            )
            
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed
        
    def create_permission_embed(self, role: discord.Role) -> discord.Embed:
        
        embed = discord.Embed(
            title=f"🔐 Permission Control: {role.name}",
            description=f"**Configure permissions for {role.mention}**\n\n"
                       f"Select a permission category below to manage specific permissions.",
            color=role.color if role.color.value != 0 else discord.Color.gold()
        )
        
        perms = role.permissions
        

        categories = {
            "General": ["administrator", "manage_guild", "manage_roles", "manage_channels", "view_audit_log"],
            "Membership": ["kick_members", "ban_members", "create_instant_invite", "change_nickname", "manage_nicknames"],
            "Text": ["send_messages", "manage_messages", "embed_links", "attach_files", "mention_everyone"],
            "Voice": ["connect", "speak", "mute_members", "deafen_members", "move_members"],
            "Advanced": ["manage_webhooks", "manage_emojis", "use_application_commands", "priority_speaker", "stream"]
        }
        
        for category, perm_list in categories.items():
            enabled = sum(1 for perm in perm_list if getattr(perms, perm, False))
            total = len(perm_list)
            
            embed.add_field(
                name=f"📋 {category} Permissions",
                value=f"**{enabled}/{total}** enabled\n"
                      f"{'🟢' if enabled > 0 else '🔴'} {'High' if enabled > total//2 else 'Low'} access level",
                inline=True
            )
            
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed
        
    def create_specific_permission_embed(self, role: discord.Role, category: str) -> discord.Embed:
        
        category_names = {
            "general": "⚙️ General Permissions",
            "membership": "👥 Membership Permissions", 
            "text": "💬 Text Permissions",
            "voice": "🔊 Voice Permissions",
            "advanced": "🔧 Advanced Permissions"
        }
        
        embed = discord.Embed(
            title=f"{category_names.get(category, category.title())} - {role.name}",
            description=f"**Configure {category} permissions for {role.mention}**\n\n"
                       f"🟢 **Green buttons** = Permission enabled\n"
                       f"⚫ **Gray buttons** = Permission disabled\n\n"
                       f"Click any button to toggle that permission on/off.",
            color=role.color if role.color.value != 0 else discord.Color.green()
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed
        
    def create_template_embed(self) -> discord.Embed:
        
        embed = discord.Embed(
            title="📋 Role Templates",
            description="**Apply pre-configured role templates**\n\n"
                       "Templates include permissions, colors, and display settings.\n"
                       "Select a template below to apply it to your role.",
            color=discord.Color.purple()
        )
        
        templates = self.config.load_templates()
        
        for name, template in templates.items():
            perm_count = len(template.get('permissions', {}))
            color = template.get('color', '#000000')
            
            embed.add_field(
                name=f"🎯 {name}",
                value=f"**Color:** {color}\n"
                      f"**Permissions:** {perm_count} configured\n"
                      f"**Hoisted:** {'Yes' if template.get('hoist') else 'No'}\n"
                      f"**Mentionable:** {'Yes' if template.get('mentionable') else 'No'}",
                inline=True
            )
            
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed

    @commands.group(name="rolecontrol", aliases=["rc", "rcontrol"], invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    async def rolecontrol(self, ctx):
        
        if ctx.invoked_subcommand is None:
            view = await self.create_main_view(ctx.guild)
            embed = self.create_main_embed(ctx.guild)
            await ctx.send(embed=embed, view=view)
            
    @rolecontrol.command(name="panel", aliases=["main", "menu"])
    @commands.has_permissions(manage_roles=True)
    async def panel(self, ctx):
        
        view = await self.create_main_view(ctx.guild)
        embed = self.create_main_embed(ctx.guild)
        await ctx.send(embed=embed, view=view)
        
    @rolecontrol.command(name="create")
    @commands.has_permissions(manage_roles=True)
    async def create_role_command(self, ctx, *, name: str):
        
        try:
            role = await ctx.guild.create_role(
                name=name,
                reason=f"Role created by {ctx.author}"
            )
            
            embed = discord.Embed(
                title="✅ Role Created Successfully",
                description=f"Created role {role.mention} with default settings.\n\n"
                           f"Use the control panel to configure permissions and appearance.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            
            view = RoleManagementView(self, role)
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Creating Role",
                description=f"Failed to create role: {str(e)}",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            
    @rolecontrol.command(name="edit")
    @commands.has_permissions(manage_roles=True)
    async def edit_role_command(self, ctx, *, role: discord.Role):
        
        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You cannot edit roles higher than or equal to your highest role.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
            
        view = RoleManagementView(self, role)
        embed = self.create_role_management_embed(role)
        await ctx.send(embed=embed, view=view)
        
    @rolecontrol.command(name="list")
    @commands.has_permissions(manage_roles=True)
    async def list_roles(self, ctx):
        
        prefix = self.get_prefix(ctx)
        roles = sorted([r for r in ctx.guild.roles if r != ctx.guild.default_role], 
                      key=lambda r: r.position, reverse=True)
        
        embed = discord.Embed(
            title="📋 Server Roles",
            description=f"**All roles in {ctx.guild.name}**\n\n"
                       f"Use `{prefix}rolecontrol edit <role>` to manage a specific role.",
            color=discord.Color.blue()
        )
        

        chunk_size = 10
        for i in range(0, len(roles), chunk_size):
            chunk = roles[i:i+chunk_size]
            role_list = []
            
            for role in chunk:
                member_count = len(role.members)
                color_hex = f"#{role.color.value:06x}" if role.color.value != 0 else "#000000"
                role_list.append(f"**{role.name}** - {member_count} members ({color_hex})")
                
            embed.add_field(
                name=f"Roles {i+1}-{min(i+chunk_size, len(roles))}",
                value="\n".join(role_list) if role_list else "No roles",
                inline=False
            )
            
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
        
    @rolecontrol.command(name="info")
    @commands.has_permissions(manage_roles=True)
    async def role_info(self, ctx, *, role: discord.Role):
        
        prefix = self.get_prefix(ctx)
        embed = discord.Embed(
            title=f"ℹ️ Role Information: {role.name}",
            description=f"**Detailed information for {role.mention}**\n\n"
                       f"Use `{prefix}rolecontrol edit {role.name}` to manage this role.",
            color=role.color if role.color.value != 0 else discord.Color.blue()
        )
        

        embed.add_field(
            name="📊 Basic Information",
            value=f"**ID:** {role.id}\n"
                  f"**Position:** {role.position}\n"
                  f"**Created:** <t:{int(role.created_at.timestamp())}:R>\n"
                  f"**Color:** #{role.color.value:06x}\n"
                  f"**Hoisted:** {'Yes' if role.hoist else 'No'}\n"
                  f"**Mentionable:** {'Yes' if role.mentionable else 'No'}",
            inline=True
        )
        

        embed.add_field(
            name="👥 Member Information",
            value=f"**Total Members:** {len(role.members)}\n"
                  f"**Percentage:** {(len(role.members) / ctx.guild.member_count * 100):.1f}%\n"
                  f"**Bots with Role:** {sum(1 for m in role.members if m.bot)}\n"
                  f"**Humans with Role:** {sum(1 for m in role.members if not m.bot)}",
            inline=True
        )
        

        perms = role.permissions
        dangerous_perms = []
        if perms.administrator:
            dangerous_perms.append("👑 Administrator")
        if perms.manage_guild:
            dangerous_perms.append("🏰 Manage Server")
        if perms.manage_roles:
            dangerous_perms.append("🎭 Manage Roles")
        if perms.ban_members:
            dangerous_perms.append("🔨 Ban Members")
        if perms.kick_members:
            dangerous_perms.append("👢 Kick Members")
            
        embed.add_field(
            name="⚠️ Dangerous Permissions",
            value="\n".join(dangerous_perms) if dangerous_perms else "None",
            inline=False
        )
        

        if 1 <= len(role.members) <= 20:
            recent_members = sorted(role.members, key=lambda m: m.joined_at or ctx.guild.created_at, reverse=True)[:10]
            member_list = [f"• {member.display_name}" for member in recent_members]
            embed.add_field(
                name="👥 Recent Members",
                value="\n".join(member_list),
                inline=False
            )
            
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
        
    @rolecontrol.command(name="cleanup")
    @commands.has_permissions(manage_roles=True)
    async def cleanup_roles(self, ctx):
        
        prefix = self.get_prefix(ctx)
        unused_roles = [role for role in ctx.guild.roles 
                       if len(role.members) == 0 and role != ctx.guild.default_role]
        
        embed = discord.Embed(
            title="🧹 Role Cleanup",
            description=f"**Found {len(unused_roles)} unused roles**\n\n"
                       f"Use `{prefix}rolecontrol edit <role>` to manage or delete specific roles.",
            color=discord.Color.orange()
        )
        
        if unused_roles:
            role_list = []
            for role in unused_roles[:20]:
                created_days = (discord.utils.utcnow() - role.created_at).days
                role_list.append(f"• **{role.name}** (Created {created_days} days ago)")
                
            embed.add_field(
                name="🗑️ Unused Roles",
                value="\n".join(role_list),
                inline=False
            )
            
            embed.add_field(
                name="⚠️ Warning",
                value="Review these roles carefully before deletion.\n"
                      "Some roles might be used for automation or special purposes.",
                inline=False
            )
        else:
            embed.add_field(
                name="✅ All Clean",
                value="No unused roles found in this server!",
                inline=False
            )
            
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
        
    @rolecontrol.command(name="templates")
    @commands.has_permissions(manage_roles=True)
    async def list_templates(self, ctx):
        
        prefix = self.get_prefix(ctx)
        embed = self.create_template_embed()
        embed.description += f"\n\nUse `{prefix}rolecontrol panel` to apply templates to roles."
        await ctx.send(embed=embed)
        
    @rolecontrol.command(name="help")
    async def help_command(self, ctx):
        
        prefix = self.get_prefix(ctx)
        
        embed = discord.Embed(
            title="🎛️ Role Control Help",
            description=f"**Complete role and permission management system**\n\n"
                       f"Use `{prefix}rolecontrol` or `{prefix}rc` to access commands.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🎯 Main Commands",
            value=f"`{prefix}rolecontrol` - Open main control panel\n"
                  f"`{prefix}rc panel` - Alternative panel access\n"
                  f"`{prefix}rc create <name>` - Quick role creation\n"
                  f"`{prefix}rc edit <role>` - Edit existing role\n"
                  f"`{prefix}rc list` - List all server roles\n"
                  f"`{prefix}rc info <role>` - Detailed role info",
            inline=False
        )
        
        embed.add_field(
            name="🛠️ Management Features",
            value="• **Interactive Control Panel** - Visual role management\n"
                  "• **Permission Categories** - Organized permission control\n"
                  "• **Role Templates** - Pre-configured role setups\n"
                  "• **Appearance Editor** - Colors, names, positions\n"
                  "• **Bulk Operations** - Mass role management\n"
                  "• **Safety Checks** - Prevents accidental changes",
            inline=False
        )
        
        embed.add_field(
            name="🔐 Permission Categories",
            value="• **General** - Administrator, server management\n"
                  "• **Membership** - Kick, ban, invite permissions\n"
                  "• **Text** - Message, embed, file permissions\n"
                  "• **Voice** - Connect, speak, mute permissions\n"
                  "• **Advanced** - Webhooks, emojis, slash commands",
            inline=False
        )
        
        embed.add_field(
            name="📋 Available Templates",
            value="• **Moderator** - Full moderation permissions\n"
                  "• **Helper** - Basic moderation tools\n"
                  "• **Member** - Standard user permissions\n"
                  "• *More templates can be added via JSON*",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Requirements",
            value="• **Manage Roles** permission required\n"
                  "• Cannot edit roles higher than your highest role\n"
                  "• Bot needs **Manage Roles** permission\n"
                  "• Some features require additional permissions",
            inline=False
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
        
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        
        print(f"🎭 Role created: {role.name} in {role.guild.name}")
        
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        
        print(f"🗑️ Role deleted: {role.name} in {role.guild.name}")
        
    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        
        if before.name != after.name:
            print(f"✏️ Role renamed: {before.name} -> {after.name} in {after.guild.name}")
        if before.permissions != after.permissions:
            print(f"🔐 Role permissions updated: {after.name} in {after.guild.name}")
        if before.color != after.color:
            print(f"🎨 Role color changed: {after.name} in {after.guild.name}")

def setup(bot):
    cog = RoleControl(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog
