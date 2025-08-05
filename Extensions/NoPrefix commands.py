import discord
from discord.ext import commands
import json
import os
import asyncio
from typing import Optional, Dict, Any

__version__ = "1.0.0"
__author__ = "TheHolyOneZ"

class NoPrefixCommands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/no_prefix_config.json"
        self.config = self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        if not os.path.exists("data"):
            os.makedirs("data")
            
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading no prefix config: {e}")
                
        return {
            "guilds": {},
            "global_settings": {
                "enabled": True,
                "allow_everyone_when_no_roles": False
            }
        }
    
    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving no prefix config: {e}")
    
    def get_guild_config(self, guild_id: int) -> Dict[str, Any]:
        guild_id_str = str(guild_id)
        if guild_id_str not in self.config["guilds"]:
            self.config["guilds"][guild_id_str] = {
                "enabled": True,
                "authorized_roles": [],
                "global_toggle": False,
                "blacklisted_commands": ["eval", "exec", "sudo"],
                "allowed_commands": []
            }
            self.save_config()
        return self.config["guilds"][guild_id_str]
    
    def can_use_no_prefix(self, member: discord.Member) -> bool:
        guild_config = self.get_guild_config(member.guild.id)
        
        if not guild_config["enabled"]:
            return False
            
        if guild_config["global_toggle"]:
            return True
            
        authorized_roles = guild_config["authorized_roles"]
        if not authorized_roles:
            return guild_config.get("allow_everyone_when_no_roles", False)
            
        user_role_ids = [role.id for role in member.roles]
        return any(role_id in user_role_ids for role_id in authorized_roles)
    
    def is_command_allowed(self, command_name: str, guild_id: int) -> bool:
        guild_config = self.get_guild_config(guild_id)
        
        if command_name in guild_config["blacklisted_commands"]:
            return False
            
        allowed_commands = guild_config["allowed_commands"]
        if allowed_commands:
            return command_name in allowed_commands
            
        return True
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
            
        if not message.guild:
            return
            
        guild_config = self.get_guild_config(message.guild.id)
        if not guild_config["enabled"]:
            return
            
        can_use = self.can_use_no_prefix(message.author)
        if not can_use:
            return
            
        try:
            prefixes = await self.bot.get_prefix(message)
            if isinstance(prefixes, str):
                prefixes = [prefixes]
        except:
            prefixes = ['!', '?', '.', '>', '<', '-', '+', '=', '/', '\\']
            
        for prefix in prefixes:
            if message.content.startswith(str(prefix)):
                return
                
        content_parts = message.content.strip().split()
        if not content_parts:
            return
            
        potential_command = content_parts[0].lower()
        
        command = self.bot.get_command(potential_command)
        if not command:
            return
            
        if not self.is_command_allowed(potential_command, message.guild.id):
            return
            
        try:
            bot_prefixes = await self.bot.get_prefix(message)
            if isinstance(bot_prefixes, list):
                primary_prefix = bot_prefixes[0]
            else:
                primary_prefix = bot_prefixes
                
            prefixed_content = f"{primary_prefix}{message.content}"
            
            original_content = message.content
            message.content = prefixed_content
            
            ctx = await self.bot.get_context(message)
            
            message.content = original_content
            
            if ctx.valid and ctx.command:
                ctx.message.content = prefixed_content
                await self.bot.invoke(ctx)
                
        except Exception as e:
            print(f"No-prefix command error for '{potential_command}': {e}")
    
    @commands.group(name="noprefix", aliases=["np"])
    @commands.has_permissions(administrator=True)
    async def noprefix(self, ctx):
        if ctx.invoked_subcommand is None:
            await self.show_status(ctx)
    
    async def show_status(self, ctx):
        guild_config = self.get_guild_config(ctx.guild.id)
        
        status = "🟢 ENABLED" if guild_config["enabled"] else "🔴 DISABLED"
        global_toggle = "🟢 ON" if guild_config["global_toggle"] else "🔴 OFF"
        
        role_names = []
        for role_id in guild_config["authorized_roles"]:
            role = ctx.guild.get_role(role_id)
            if role:
                role_names.append(role.name)
        
        try:
            prefixes = await self.bot.get_prefix(ctx)
            if isinstance(prefixes, list):
                prefix = prefixes[0]
            else:
                prefix = prefixes
        except:
            prefix = "!"
        
        embed = discord.Embed(
            title="🚀 No Prefix Commands System",
            description=f"**Status:** {status}\n**Global Toggle:** {global_toggle}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📋 Authorized Roles",
            value="\n".join(role_names) if role_names else "None configured",
            inline=False
        )
        
        embed.add_field(
            name="🚫 Blacklisted Commands",
            value=", ".join(guild_config["blacklisted_commands"]) if guild_config["blacklisted_commands"] else "None",
            inline=False
        )
        
        if guild_config["allowed_commands"]:
            embed.add_field(
                name="✅ Allowed Commands Only",
                value=", ".join(guild_config["allowed_commands"]),
                inline=False
            )
        
        available_commands = []
        for command in self.bot.commands:
            if not command.hidden and self.is_command_allowed(command.name, ctx.guild.id):
                available_commands.append(command.name)
        
        if available_commands:
            commands_display = ", ".join(available_commands[:20])
            if len(available_commands) > 20:
                commands_display += f" ... and {len(available_commands) - 20} more"
            
            embed.add_field(
                name="📝 Available Commands",
                value=commands_display,
                inline=False
            )
        
        embed.add_field(
            name="🔒 SECURITY NOTE",
            value="**All original permission checks remain active!** This system only removes the need to type prefixes - it does NOT bypass any command restrictions, role requirements, or permission checks.",
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ How it works",
            value=f"Users with authorized roles can use bot commands without prefixes!\nExample: `panel` instead of `{prefix}panel`",
            inline=False
        )
        
        embed.add_field(
            name="📋 Command List",
            value=f"`{prefix}noprefix` - Show this panel\n`{prefix}noprefix toggle` - Enable/disable system\n`{prefix}noprefix global` - Toggle global access\n`{prefix}noprefix addrole <role>` - Add authorized role\n`{prefix}noprefix removerole <role>` - Remove authorized role\n`{prefix}noprefix blacklist <command>` - Blacklist command\n`{prefix}noprefix whitelist <command>` - Remove from blacklist\n`{prefix}noprefix test` - Test functionality",
            inline=False
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        
        view = NoPrefixControlView(self, ctx.guild.id)
        await ctx.send(embed=embed, view=view)
    
    @noprefix.command(name="toggle")
    @commands.has_permissions(administrator=True)
    async def toggle_system(self, ctx):
        guild_config = self.get_guild_config(ctx.guild.id)
        guild_config["enabled"] = not guild_config["enabled"]
        self.save_config()
        
        status = "enabled" if guild_config["enabled"] else "disabled"
        embed = discord.Embed(
            title="✅ System Updated",
            description=f"No Prefix Commands system has been **{status}**",
            color=discord.Color.green() if guild_config["enabled"] else discord.Color.red()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @noprefix.command(name="global")
    @commands.has_permissions(administrator=True)
    async def toggle_global(self, ctx):
        guild_config = self.get_guild_config(ctx.guild.id)
        guild_config["global_toggle"] = not guild_config["global_toggle"]
        self.save_config()
        
        status = "enabled" if guild_config["global_toggle"] else "disabled"
        embed = discord.Embed(
            title="🌐 Global Toggle Updated",
            description=f"Global no-prefix access has been **{status}**\n{'Everyone can now use commands without prefix!' if guild_config['global_toggle'] else 'Only authorized roles can use no-prefix commands.'}",
            color=discord.Color.green() if guild_config["global_toggle"] else discord.Color.orange()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @noprefix.command(name="addrole")
    @commands.has_permissions(administrator=True)
    async def add_role(self, ctx, role: discord.Role):
        guild_config = self.get_guild_config(ctx.guild.id)
        
        if role.id in guild_config["authorized_roles"]:
            embed = discord.Embed(
                title="❌ Role Already Added",
                description=f"{role.mention} is already authorized for no-prefix commands",
                color=discord.Color.red()
            )
        else:
            guild_config["authorized_roles"].append(role.id)
            self.save_config()
            
            embed = discord.Embed(
                title="✅ Role Added",
                description=f"{role.mention} can now use commands without prefix",
                color=discord.Color.green()
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @noprefix.command(name="removerole")
    @commands.has_permissions(administrator=True)
    async def remove_role(self, ctx, role: discord.Role):
        guild_config = self.get_guild_config(ctx.guild.id)
        
        if role.id not in guild_config["authorized_roles"]:
            embed = discord.Embed(
                title="❌ Role Not Found",
                description=f"{role.mention} is not in the authorized roles list",
                color=discord.Color.red()
            )
        else:
            guild_config["authorized_roles"].remove(role.id)
            self.save_config()
            
            embed = discord.Embed(
                title="✅ Role Removed",
                description=f"{role.mention} can no longer use commands without prefix",
                color=discord.Color.green()
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @noprefix.command(name="blacklist")
    @commands.has_permissions(administrator=True)
    async def blacklist_command(self, ctx, command_name: str):
        guild_config = self.get_guild_config(ctx.guild.id)
        
        if command_name in guild_config["blacklisted_commands"]:
            embed = discord.Embed(
                title="❌ Already Blacklisted",
                description=f"Command `{command_name}` is already blacklisted",
                color=discord.Color.red()
            )
        else:
            guild_config["blacklisted_commands"].append(command_name)
            self.save_config()
            
            embed = discord.Embed(
                title="🚫 Command Blacklisted",
                description=f"Command `{command_name}` cannot be used without prefix",
                color=discord.Color.orange()
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @noprefix.command(name="whitelist")
    @commands.has_permissions(administrator=True)
    async def whitelist_command(self, ctx, command_name: str):
        guild_config = self.get_guild_config(ctx.guild.id)
        
        if command_name not in guild_config["blacklisted_commands"]:
            embed = discord.Embed(
                title="❌ Not Blacklisted",
                description=f"Command `{command_name}` is not blacklisted",
                color=discord.Color.red()
            )
        else:
            guild_config["blacklisted_commands"].remove(command_name)
            self.save_config()
            
            embed = discord.Embed(
                title="✅ Command Whitelisted",
                description=f"Command `{command_name}` can now be used without prefix",
                color=discord.Color.green()
            )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)
    
    @noprefix.command(name="test")
    @commands.has_permissions(administrator=True)
    async def test_noprefix(self, ctx, *, test_message: str = "panel"):
        guild_config = self.get_guild_config(ctx.guild.id)
        can_use = self.can_use_no_prefix(ctx.author)
        
        embed = discord.Embed(title="🧪 No-Prefix Test Results", color=discord.Color.blue())
        embed.add_field(name="System Enabled", value=guild_config["enabled"], inline=True)
        embed.add_field(name="Global Toggle", value=guild_config["global_toggle"], inline=True)
        embed.add_field(name="Can Use No-Prefix", value=can_use, inline=True)
        embed.add_field(name="Test Command", value=test_message, inline=False)
        
        command = self.bot.get_command(test_message.split()[0])
        embed.add_field(name="Command Found", value=command is not None, inline=True)
        
        if command:
            embed.add_field(name="Command Name", value=command.name, inline=True)
            is_allowed = self.is_command_allowed(command.name, ctx.guild.id)
            embed.add_field(name="Command Allowed", value=is_allowed, inline=True)
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)


class NoPrefixControlView(discord.ui.View):
    
    def __init__(self, cog: NoPrefixCommands, guild_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
    
    @discord.ui.button(label="Toggle System", style=discord.ButtonStyle.primary, emoji="🔄")
    async def toggle_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
            
        guild_config = self.cog.get_guild_config(self.guild_id)
        guild_config["enabled"] = not guild_config["enabled"]
        self.cog.save_config()
        
        status = "enabled" if guild_config["enabled"] else "disabled"
        embed = discord.Embed(
            title="✅ System Updated",
            description=f"No Prefix Commands system has been **{status}**",
            color=discord.Color.green() if guild_config["enabled"] else discord.Color.red()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Global Toggle", style=discord.ButtonStyle.secondary, emoji="🌐")
    async def toggle_global(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
            
        guild_config = self.cog.get_guild_config(self.guild_id)
        guild_config["global_toggle"] = not guild_config["global_toggle"]
        self.cog.save_config()
        
        status = "enabled" if guild_config["global_toggle"] else "disabled"
        embed = discord.Embed(
            title="🌐 Global Toggle Updated",
            description=f"Global no-prefix access has been **{status}**\n{'Everyone can now use commands without prefix!' if guild_config['global_toggle'] else 'Only authorized roles can use no-prefix commands.'}",
            color=discord.Color.green() if guild_config["global_toggle"] else discord.Color.orange()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Manage Roles", style=discord.ButtonStyle.success, emoji="👥")
    async def manage_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
            
        modal = RoleManagementModal(self.cog, self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Command Settings", style=discord.ButtonStyle.danger, emoji="⚙️")
    async def command_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions!", ephemeral=True)
            return
            
        modal = CommandSettingsModal(self.cog, self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="System Info", style=discord.ButtonStyle.gray, emoji="ℹ️")
    async def system_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="ℹ️ No Prefix Commands - How It Works",
            description="**This system is a convenience feature that does NOT bypass security!**",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🔄 Process Flow",
            value="1. User types: `panel`\n2. System converts to: `!panel`\n3. Bot processes normally with ALL checks\n4. Original user's permissions are verified\n5. Command succeeds or fails based on user's actual permissions",
            inline=False
        )
        
        embed.add_field(
            name="🔒 Security Guarantees",
            value="• **All permission decorators still apply**\n• **Admin commands still require admin permissions**\n• **Bot owner commands still require bot ownership**\n• **Role restrictions are fully preserved**\n• **Cooldowns and limits remain active**",
            inline=False
        )
        
        embed.add_field(
            name="❌ What This System CANNOT Do",
            value="• Grant extra permissions to users\n• Bypass `@commands.has_permissions()` checks\n• Override role-based restrictions\n• Skip authorization functions like `is_authorized()`\n• Give access to owner-only commands",
            inline=False
        )
        
        embed.add_field(
            name="✅ What This System DOES",
            value="• Removes the need to type prefixes\n• Maintains all original security checks\n• Uses the original user's identity for all checks\n• Provides convenient command access for authorized users",
            inline=False
        )
        
        embed.add_field(
            name="🛡️ Example Security Test",
            value="**Non-admin user tries:** `globalban webhook`\n**System converts to:** `!globalban webhook`\n**Result:** ❌ Access Denied (same as typing `!globalban webhook`)\n\n**Admin user tries:** `globalban webhook`\n**System converts to:** `!globalban webhook`\n**Result:** ✅ Command works (same as typing `!globalban webhook`)",
            inline=False
        )
        
        embed.set_footer(text="Made By TheHolyOneZ • No security compromises, just convenience!")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Refresh Status", style=discord.ButtonStyle.gray, emoji="🔄")
    async def refresh_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_config = self.cog.get_guild_config(self.guild_id)
        
        status = "🟢 ENABLED" if guild_config["enabled"] else "🔴 DISABLED"
        global_toggle = "🟢 ON" if guild_config["global_toggle"] else "🔴 OFF"
        
        role_names = []
        for role_id in guild_config["authorized_roles"]:
            role = interaction.guild.get_role(role_id)
            if role:
                role_names.append(role.name)
        
        try:
            prefixes = await self.cog.bot.get_prefix(interaction.message)
            if isinstance(prefixes, list):
                prefix = prefixes[0]
            else:
                prefix = prefixes
        except:
            prefix = "!"
        
        embed = discord.Embed(
            title="🚀 No Prefix Commands System",
            description=f"**Status:** {status}\n**Global Toggle:** {global_toggle}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📋 Authorized Roles",
            value="\n".join(role_names) if role_names else "None configured",
            inline=False
        )
        
        embed.add_field(
            name="🚫 Blacklisted Commands",
            value=", ".join(guild_config["blacklisted_commands"]) if guild_config["blacklisted_commands"] else "None",
            inline=False
        )
        
        if guild_config["allowed_commands"]:
            embed.add_field(
                name="✅ Allowed Commands Only",
                value=", ".join(guild_config["allowed_commands"]),
                inline=False
            )
        
        available_commands = []
        for command in self.cog.bot.commands:
            if not command.hidden and self.cog.is_command_allowed(command.name, self.guild_id):
                available_commands.append(command.name)
        
        if available_commands:
            commands_display = ", ".join(available_commands[:20])
            if len(available_commands) > 20:
                commands_display += f" ... and {len(available_commands) - 20} more"
            
            embed.add_field(
                name="📝 Available Commands",
                value=commands_display,
                inline=False
            )
        
        embed.add_field(
            name="🔒 SECURITY NOTE",
            value="**All original permission checks remain active!** This system only removes the need to type prefixes - it does NOT bypass any command restrictions, role requirements, or permission checks.",
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ How it works",
            value=f"Users with authorized roles can use bot commands without prefixes!\nExample: `panel` instead of `{prefix}panel`",
            inline=False
        )
        
        embed.add_field(
            name="📋 Command List",
            value=f"`{prefix}noprefix` - Show this panel\n`{prefix}noprefix toggle` - Enable/disable system\n`{prefix}noprefix global` - Toggle global access\n`{prefix}noprefix addrole <role>` - Add authorized role\n`{prefix}noprefix removerole <role>` - Remove authorized role\n`{prefix}noprefix blacklist <command>` - Blacklist command\n`{prefix}noprefix whitelist <command>` - Remove from blacklist\n`{prefix}noprefix test` - Test functionality",
            inline=False
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=self)


class RoleManagementModal(discord.ui.Modal, title="Manage Authorized Roles"):
    
    def __init__(self, cog: NoPrefixCommands, guild_id: int):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        
        guild_config = cog.get_guild_config(guild_id)
        current_roles = ", ".join([str(role_id) for role_id in guild_config["authorized_roles"]])
        
        self.role_input = discord.ui.TextInput(
            label="Role IDs (comma separated)",
            placeholder="123456789, 987654321, ...",
            default=current_roles,
            max_length=1000,
            required=False
        )
        self.add_item(self.role_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            guild_config = self.cog.get_guild_config(self.guild_id)
            
            role_ids = []
            if self.role_input.value.strip():
                for role_id_str in self.role_input.value.split(","):
                    try:
                        role_id = int(role_id_str.strip())
                        role = interaction.guild.get_role(role_id)
                        if role:
                            role_ids.append(role_id)
                    except ValueError:
                        continue
            
            guild_config["authorized_roles"] = role_ids
            self.cog.save_config()
            
            role_names = []
            for role_id in role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    role_names.append(role.name)
            
            embed = discord.Embed(
                title="✅ Roles Updated",
                description=f"Authorized roles updated!\n\n**Current roles:**\n{chr(10).join(role_names) if role_names else 'None'}",
                color=discord.Color.green()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to update roles: {str(e)}",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)


class CommandSettingsModal(discord.ui.Modal, title="Command Settings"):
    
    def __init__(self, cog: NoPrefixCommands, guild_id: int):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        
        guild_config = cog.get_guild_config(guild_id)
        
        self.blacklist_input = discord.ui.TextInput(
            label="Blacklisted Commands (comma separated)",
            placeholder="eval, exec, sudo, ...",
            default=", ".join(guild_config["blacklisted_commands"]),
            max_length=1000,
            required=False
        )
        self.add_item(self.blacklist_input)
        
        self.whitelist_input = discord.ui.TextInput(
            label="Allowed Commands Only (leave empty for all)",
            placeholder="panel, help, info, ...",
            default=", ".join(guild_config["allowed_commands"]),
            max_length=1000,
            required=False
        )
        self.add_item(self.whitelist_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            guild_config = self.cog.get_guild_config(self.guild_id)
            
            blacklisted = []
            if self.blacklist_input.value.strip():
                blacklisted = [cmd.strip().lower() for cmd in self.blacklist_input.value.split(",") if cmd.strip()]
            
            allowed = []
            if self.whitelist_input.value.strip():
                allowed = [cmd.strip().lower() for cmd in self.whitelist_input.value.split(",") if cmd.strip()]
            
            guild_config["blacklisted_commands"] = blacklisted
            guild_config["allowed_commands"] = allowed
            self.cog.save_config()
            
            embed = discord.Embed(
                title="✅ Command Settings Updated",
                color=discord.Color.green()
            )
            
            if blacklisted:
                embed.add_field(
                    name="🚫 Blacklisted Commands",
                    value=", ".join(blacklisted),
                    inline=False
                )
            
            if allowed:
                embed.add_field(
                    name="✅ Allowed Commands Only",
                    value=", ".join(allowed),
                    inline=False
                )
            
            if not blacklisted and not allowed:
                embed.description = "All commands are now allowed (no restrictions)"
            
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to update command settings: {str(e)}",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)


def setup(bot):
    cog = NoPrefixCommands(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    return cog


if __name__ == "__main__":
    print(f"No Prefix Commands System v{__version__} by {__author__}")
    print("This is a Discord bot extension and should be loaded by a bot framework.")
    print("Recommended for ZygnalBot")
