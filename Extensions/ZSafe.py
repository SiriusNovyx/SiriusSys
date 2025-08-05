
import discord
from discord.ext import commands
import json
import os
import asyncio
from typing import Optional, Dict, List
import random
import time
import re

class ZSafeConfig:
    def __init__(self):
        self.config_dir = "data/zsafe"
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.pending_file = os.path.join(self.config_dir, "pending.json")
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
            
    def load_pending(self) -> Dict:
        if not os.path.exists(self.pending_file):
            return {}
        try:
            with open(self.pending_file, 'r') as f:
                return json.load(f)
        except:
            return {}
            
    def save_pending(self, pending: Dict):
        with open(self.pending_file, 'w') as f:
            json.dump(pending, f, indent=4)

class NumberPadView(discord.ui.View):
    def __init__(self, cog, user_id: int, correct_code: str, guild_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.correct_code = correct_code
        self.guild_id = guild_id
        self.entered_code = ""
        self.add_number_buttons()
        
    def add_number_buttons(self):
        numbers = [
            [1, 2, 3],
            [4, 5, 6], 
            [7, 8, 9]
        ]
        
        for row_idx, row in enumerate(numbers):
            for num in row:
                button = discord.ui.Button(
                    label=str(num),
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"num_{num}",
                    row=row_idx
                )
                button.callback = self.create_number_callback(str(num))
                self.add_item(button)
        
        cancel_button = discord.ui.Button(
            label="❌",
            style=discord.ButtonStyle.danger,
            custom_id="cancel",
            row=3
        )
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)
        
        zero_button = discord.ui.Button(
            label="0",
            style=discord.ButtonStyle.secondary,
            custom_id="num_0",
            row=3
        )
        zero_button.callback = self.create_number_callback("0")
        self.add_item(zero_button)
        
        clear_button = discord.ui.Button(
            label="🔄",
            style=discord.ButtonStyle.secondary,
            custom_id="clear",
            row=3
        )
        clear_button.callback = self.clear_callback
        self.add_item(clear_button)
        
        submit_button = discord.ui.Button(
            label="✅ Submit",
            style=discord.ButtonStyle.success,
            custom_id="submit",
            row=4
        )
        submit_button.callback = self.submit_callback
        self.add_item(submit_button)
        
    def create_number_callback(self, number: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ This verification is not for you!", ephemeral=True)
                return
                
            if len(self.entered_code) < len(self.correct_code):
                self.entered_code += number
                
            embed = self.create_keypad_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        return callback
        
    async def cancel_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This verification is not for you!", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="❌ Verification Cancelled",
            description="You have cancelled the verification process.",
            color=discord.Color.red()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        pending = self.cog.config.load_pending()
        user_key = f"{self.guild_id}_{self.user_id}"
        if user_key in pending:
            del pending[user_key]
            self.cog.config.save_pending(pending)
            
        await interaction.response.edit_message(embed=embed, view=None)
        
    async def clear_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This verification is not for you!", ephemeral=True)
            return
            
        self.entered_code = ""
        embed = self.create_keypad_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        
    async def submit_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This verification is not for you!", ephemeral=True)
            return
            
        if len(self.entered_code) != len(self.correct_code):
            embed = discord.Embed(
                title="❌ Incomplete Code",
                description=f"Please enter all {len(self.correct_code)} digits before submitting.",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        if self.entered_code == self.correct_code:
            await self.process_successful_verification(interaction)
        else:
            await self.process_failed_verification(interaction)
            
    async def process_successful_verification(self, interaction: discord.Interaction):
        try:
            config = self.cog.config.load_config()
            guild_config = config["guilds"].get(str(self.guild_id), {})
            
            member = interaction.guild.get_member(self.user_id)
            if not member:
                await interaction.response.send_message("❌ Member not found!", ephemeral=True)
                return
            
            role_changes = {"added": [], "removed": [], "failed": []}
                
            roles_to_add = guild_config.get("add_roles", [])
            for role_id in roles_to_add:
                role = interaction.guild.get_role(role_id)
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role, reason="ZSafe verification completed")
                        role_changes["added"].append(role.name)
                    except Exception as e:
                        role_changes["failed"].append(f"Add {role.name}: {str(e)}")
                        
            roles_to_remove = guild_config.get("remove_roles", [])
            for role_id in roles_to_remove:
                role = interaction.guild.get_role(role_id)
                if role and role in member.roles:
                    try:
                        await member.remove_roles(role, reason="ZSafe verification completed")
                        role_changes["removed"].append(role.name)
                    except Exception as e:
                        role_changes["failed"].append(f"Remove {role.name}: {str(e)}")
                        
            pending = self.cog.config.load_pending()
            user_key = f"{self.guild_id}_{self.user_id}"
            if user_key in pending:
                del pending[user_key]
                self.cog.config.save_pending(pending)
                
            embed = discord.Embed(
                title="✅ Verification Successful!",
                description="🎉 You have been successfully verified!",
                color=discord.Color.green()
            )
            
            if role_changes["added"]:
                embed.add_field(
                    name="➕ Roles Added",
                    value="\n".join([f"• {role}" for role in role_changes["added"]]),
                    inline=True
                )
            
            if role_changes["removed"]:
                embed.add_field(
                    name="➖ Roles Removed", 
                    value="\n".join([f"• {role}" for role in role_changes["removed"]]),
                    inline=True
                )
                
            if role_changes["failed"]:
                embed.add_field(
                    name="⚠️ Role Errors",
                    value="\n".join([f"• {error}" for error in role_changes["failed"]]),
                    inline=False
                )
            
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Verification Error",
                description=f"An error occurred during verification: {str(e)}\nPlease contact an administrator.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.edit_message(embed=embed, view=None)
            
    async def process_failed_verification(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="❌ Verification Failed",
            description="The code you entered is incorrect. Please try again.",
            color=discord.Color.red()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        self.entered_code = ""
        keypad_embed = self.create_keypad_embed()
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await interaction.edit_original_response(embed=keypad_embed, view=self)
        
    def create_keypad_embed(self) -> discord.Embed:
        code_display = ""
        for i in range(len(self.correct_code)):
            if i < len(self.entered_code):
                code_display += f"`{self.entered_code[i]}` "
            else:
                code_display += "`_` "
        
        embed = discord.Embed(
            title="🔢 Enter Verification Code",
            description=f"Enter the {len(self.correct_code)}-digit code shown above.\n\n"
                       f"**Current Input:** {code_display}\n"
                       f"**Progress:** {len(self.entered_code)}/{len(self.correct_code)} digits entered\n\n"
                       f"Use the number buttons below to enter your code.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🎯 Instructions",
            value="• Click number buttons to enter code\n"
                  "• ❌ Cancel verification\n"
                  "• 🔄 Clear current input\n"
                  "• ✅ Submit when complete",
            inline=False
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed
        
    async def on_timeout(self):
        pending = self.cog.config.load_pending()
        user_key = f"{self.guild_id}_{self.user_id}"
        if user_key in pending:
            del pending[user_key]
            self.cog.config.save_pending(pending)

class VerificationView(discord.ui.View):
    def __init__(self, cog, button_label: str = "🔐 Verify"):
        super().__init__(timeout=None)
        self.cog = cog
        for item in self.children:
            if hasattr(item, 'custom_id') and item.custom_id == "zsafe_verify_button":
                item.label = button_label
                break
        
    @discord.ui.button(label="🔐 Verify", style=discord.ButtonStyle.primary, custom_id="zsafe_verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = self.cog.config.load_config()
        guild_config = config["guilds"].get(str(interaction.guild.id), {})
        
        if not guild_config:
            await interaction.response.send_message("❌ ZSafe verification is not set up for this server!", ephemeral=True)
            return
            
        pending = self.cog.config.load_pending()
        user_key = f"{interaction.guild.id}_{interaction.user.id}"
        
        if user_key in pending:
            if time.time() - pending[user_key]["timestamp"] < 300:
                await interaction.response.send_message("❌ You already have a pending verification! Please complete it first.", ephemeral=True)
                return
            else:
                del pending[user_key]
                self.cog.config.save_pending(pending)
                
        code_length = guild_config.get("code_length", 4)
        verification_code = ''.join([str(random.randint(0, 9)) for _ in range(code_length)])
        
        pending[user_key] = {
            "code": verification_code,
            "timestamp": time.time()
        }
        self.cog.config.save_pending(pending)
        
        embed = discord.Embed(
            title="🔐 Your Verification Code",
            description=f"**Your verification code is:** `{verification_code}`\n\n"
                       f"📱 Use the number pad below to enter this code.\n"
                       f"⏰ This code expires in 5 minutes.",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="🎯 How to verify:",
            value="1. Memorize the code above\n"
                  "2. Use the number pad below\n"
                  "3. Click ✅ Submit when done",
            inline=False
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        view = NumberPadView(self.cog, interaction.user.id, verification_code, interaction.guild.id)
        keypad_embed = view.create_keypad_embed()
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await interaction.followup.send(embed=keypad_embed, view=view, ephemeral=True)

class ChannelSelectView(discord.ui.View):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        
        self.channel_select = discord.ui.ChannelSelect(
            placeholder="Select channel to post verification embed...",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
        self.channel_select.callback = self.channel_select_callback
        self.add_item(self.channel_select)
        
    async def channel_select_callback(self, interaction: discord.Interaction):
        channel = self.channel_select.values[0]
        
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("❌ Please select a text channel!", ephemeral=True)
            return
        
        bot_perms = channel.permissions_for(interaction.guild.me)
        if not bot_perms.send_messages:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages in {channel.mention}!\n"
                f"Please give me **Send Messages** permission in that channel.",
                ephemeral=True
            )
            return
        
        if not bot_perms.embed_links:
            await interaction.response.send_message(
                f"⚠️ I don't have **Embed Links** permission in {channel.mention}!\n"
                f"The verification embed may not display properly.",
                ephemeral=True
            )
            return
        
        config = self.cog.config.load_config()
        guild_config = config["guilds"].get(str(self.guild_id), {})
        
        if not guild_config:
            await interaction.response.send_message("❌ ZSafe is not configured! Please set up basic settings first.", ephemeral=True)
            return
            
        embed = self.cog.create_verification_embed(guild_config)
        view = VerificationView(self.cog, guild_config.get("button_label", "🔐 Verify"))
        
        try:
            await channel.send(embed=embed, view=view)
            
            success_embed = discord.Embed(
                title="✅ Verification Posted Successfully",
                description=f"Verification embed has been posted in {channel.mention}!",
                color=discord.Color.green()
            )
            success_embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.edit_message(embed=success_embed, view=None)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Failed to Post Verification",
                description=f"Error: {str(e)}\n\nMake sure I have permission to send messages in that channel.",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.edit_message(embed=error_embed, view=None)

class ZSafeSetupView(discord.ui.View):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        
    @discord.ui.button(label="📝 Basic Settings", emoji="⚙️", style=discord.ButtonStyle.primary, row=0)
    async def basic_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BasicSettingsModal(self.cog, self.guild_id)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="🎨 Embed Design", emoji="🖌️", style=discord.ButtonStyle.secondary, row=0)
    async def embed_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EmbedDesignModal(self.cog, self.guild_id)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="➕ Add Roles", emoji="🎭", style=discord.ButtonStyle.success, row=1)
    async def add_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RoleSelectView(self.cog, interaction.guild, "add")
        embed = discord.Embed(
            title="➕ Select Roles to Add After Verification",
            description="Choose which roles members should **receive** after successful verification.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    @discord.ui.button(label="➖ Remove Roles", emoji="🗑️", style=discord.ButtonStyle.danger, row=1)
    async def remove_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RoleSelectView(self.cog, interaction.guild, "remove")
        embed = discord.Embed(
            title="➖ Select Roles to Remove After Verification",
            description="Choose which roles should be **removed** from members after successful verification.",
            color=discord.Color.red()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    @discord.ui.button(label="📊 View Status", emoji="📈", style=discord.ButtonStyle.secondary, row=2)
    async def view_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.cog.create_status_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @discord.ui.button(label="🔄 Reset All", emoji="⚠️", style=discord.ButtonStyle.danger, row=2)
    async def reset_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ConfirmResetView(self.cog, self.guild_id)
        embed = discord.Embed(
            title="⚠️ Confirm Reset",
            description="Are you sure you want to reset ALL ZSafe settings?\n\n"
                       "**This will delete:**\n"
                       "• All configuration settings\n"
                       "• Role assignments\n"
                       "• Embed customization\n"
                       "• Pending verifications\n\n"
                       "**This action cannot be undone!**",
            color=discord.Color.red()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    @discord.ui.button(label="❌ Close Menu", emoji="🚪", style=discord.ButtonStyle.secondary, row=3)
    async def close_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="✅ ZSafe Setup Closed",
            description="Setup menu has been closed. Use `!zsafe` to reopen.",
            color=discord.Color.from_rgb(128, 128, 128)
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.edit_message(embed=embed, view=None)

class BasicSettingsModal(discord.ui.Modal):
    def __init__(self, cog, guild_id: int):
        super().__init__(title="⚙️ Basic ZSafe Settings")
        self.cog = cog
        self.guild_id = guild_id
        
        config = cog.config.load_config()
        guild_config = config["guilds"].get(str(guild_id), {})
        
        if guild_config.get("code_length"):
            self.code_length.default = str(guild_config["code_length"])
        if guild_config.get("button_label"):
            self.button_label.default = guild_config["button_label"]
        
    code_length = discord.ui.TextInput(
        label="Code Length (1-8 digits)",
        placeholder="4",
        required=True,
        max_length=1
    )
    
    button_label = discord.ui.TextInput(
        label="Verification Button Label",
        placeholder="🔐 Verify",
        required=True,
        max_length=80
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            try:
                length = int(self.code_length.value)
                if length < 1 or length > 8:
                    await interaction.response.send_message("❌ Code length must be between 1 and 8 digits!", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("❌ Code length must be a number!", ephemeral=True)
                return
                
            config = self.cog.config.load_config()
            guild_id_str = str(self.guild_id)
            
            if guild_id_str not in config["guilds"]:
                config["guilds"][guild_id_str] = {}
                
            config["guilds"][guild_id_str].update({
                "code_length": length,
                "button_label": self.button_label.value
            })
            
            self.cog.config.save_config(config)
            
            embed = discord.Embed(
                title="✅ Basic Settings Updated",
                description=f"**Code Length:** {length} digits\n"
                           f"**Button Label:** {self.button_label.value}",
                color=discord.Color.green()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error updating settings: {str(e)}", ephemeral=True)

class EmbedDesignModal(discord.ui.Modal):
    def __init__(self, cog, guild_id: int):
        super().__init__(title="🎨 Embed Design Settings")
        self.cog = cog
        self.guild_id = guild_id
        
        config = cog.config.load_config()
        guild_config = config["guilds"].get(str(guild_id), {})
        
        if guild_config.get("embed_title"):
            self.embed_title.default = guild_config["embed_title"]
        if guild_config.get("embed_description"):
            self.embed_description.default = guild_config["embed_description"]
        if guild_config.get("embed_color"):
            self.embed_color.default = guild_config["embed_color"]
        
    embed_title = discord.ui.TextInput(
        label="Verification Embed Title",
        placeholder="🔐 Server Verification",
        required=True,
        max_length=256
    )
    
    embed_description = discord.ui.TextInput(
        label="Verification Embed Description",
        placeholder="Click the button below to verify yourself...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )
    
    embed_color = discord.ui.TextInput(
        label="Embed Color (Hex)",
        placeholder="#0099ff",
        required=False,
        max_length=7
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            color_hex = "#0099ff"
            if self.embed_color.value:
                hex_color = self.embed_color.value.strip()
                if not hex_color.startswith('#'):
                    hex_color = '#' + hex_color
                if re.match(r'^#[0-9A-Fa-f]{6}$', hex_color):
                    color_hex = hex_color
                else:
                    await interaction.response.send_message("❌ Invalid hex color format! Use format: #0099ff", ephemeral=True)
                    return
                    
            config = self.cog.config.load_config()
            guild_id_str = str(self.guild_id)
            
            if guild_id_str not in config["guilds"]:
                config["guilds"][guild_id_str] = {}
                
            config["guilds"][guild_id_str].update({
                "embed_title": self.embed_title.value,
                "embed_description": self.embed_description.value,
                "embed_color": color_hex
            })
            
            self.cog.config.save_config(config)
            
            preview_color = discord.Color(int(color_hex[1:], 16))
            preview_embed = discord.Embed(
                title=self.embed_title.value,
                description=self.embed_description.value,
                color=preview_color
            )
            preview_embed.set_footer(text="Made By TheHolyOneZ")
            
            embed = discord.Embed(
                title="✅ Embed Design Updated",
                description="Your verification embed design has been saved!",
                color=discord.Color.green()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await interaction.followup.send(content="**Preview:**", embed=preview_embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error updating embed design: {str(e)}", ephemeral=True)

class RoleSelectView(discord.ui.View):
    def __init__(self, cog, guild: discord.Guild, action_type: str):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.action_type = action_type
        self.add_role_select()
        
    def add_role_select(self):
        roles = [role for role in self.guild.roles if role != self.guild.default_role and not role.is_bot_managed()]
        
        if not roles:
            return
            
        options = []
        for role in roles[:25]:
            options.append(discord.SelectOption(
                label=role.name,
                value=str(role.id),
                description=f"Position: {role.position} | Members: {len(role.members)}"
            ))
            
        select = discord.ui.Select(
            placeholder=f"Select roles to {self.action_type} after verification...",
            options=options,
            max_values=min(len(options), 25)
        )
        select.callback = self.role_select_callback
        self.add_item(select)
        
    async def role_select_callback(self, interaction: discord.Interaction):
        selected_role_ids = [int(role_id) for role_id in interaction.data['values']]
        
        config = self.cog.config.load_config()
        guild_id = str(interaction.guild.id)
        
        if guild_id not in config["guilds"]:
            config["guilds"][guild_id] = {}
            
        config["guilds"][guild_id][f"{self.action_type}_roles"] = selected_role_ids
        self.cog.config.save_config(config)
        
        role_names = []
        for role_id in selected_role_ids:
            role = interaction.guild.get_role(role_id)
            if role:
                role_names.append(role.name)
                
        embed = discord.Embed(
            title=f"✅ Roles to {self.action_type.title()} Updated",
            description=f"Selected roles will be **{self.action_type}ed** after successful verification:\n\n" +
                       "\n".join([f"• {name}" for name in role_names]),
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.edit_message(embed=embed, view=None)

class ConfirmResetView(discord.ui.View):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild_id = guild_id
        
    @discord.ui.button(label="✅ Confirm Reset", style=discord.ButtonStyle.danger)
    async def confirm_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            config = self.cog.config.load_config()
            guild_id_str = str(self.guild_id)
            
            if guild_id_str in config["guilds"]:
                del config["guilds"][guild_id_str]
                self.cog.config.save_config(config)
                
            pending = self.cog.config.load_pending()
            guild_keys = [k for k in pending.keys() if k.startswith(f"{self.guild_id}_")]
            for key in guild_keys:
                del pending[key]
            self.cog.config.save_pending(pending)
            
            embed = discord.Embed(
                title="✅ ZSafe Reset Complete",
                description="All ZSafe settings have been reset for this server.\n"
                           "Use `!zsafe` to set up verification again.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error resetting ZSafe: {str(e)}", ephemeral=True)
            
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❌ Reset Cancelled",
            description="ZSafe settings have not been changed.",
            color=discord.Color.from_rgb(128, 128, 128)
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await interaction.response.edit_message(embed=embed, view=None)

class ZSafe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = ZSafeConfig()
        
    async def cog_load(self):
        print("🔐 ZSafe Verification System loaded!")
        self.bot.add_view(VerificationView(self))
        
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
        
    def create_verification_embed(self, guild_config: Dict) -> discord.Embed:
        color = discord.Color.blue()
        try:
            if guild_config.get("embed_color"):
                color = discord.Color(int(guild_config["embed_color"][1:], 16))
        except:
            pass
            
        embed = discord.Embed(
            title=guild_config.get("embed_title", "🔐 Server Verification"),
            description=guild_config.get("embed_description", "Click the button below to verify yourself and gain access to the server."),
            color=color
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed
        
    async def create_status_embed(self, guild: discord.Guild) -> discord.Embed:
        config = self.config.load_config()
        guild_config = config["guilds"].get(str(guild.id), {})
        
        if not guild_config:
            embed = discord.Embed(
                title="📊 ZSafe Status",
                description="❌ ZSafe is not configured for this server.\n\n"
                           "Use the setup buttons to configure verification.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            return embed
            
        embed = discord.Embed(
            title="📊 ZSafe Status",
            description="Current ZSafe configuration for this server:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="⚙️ Basic Settings",
            value=f"**Code Length:** {guild_config.get('code_length', 4)} digits\n"
                  f"**Button Label:** {guild_config.get('button_label', '🔐 Verify')}",
            inline=True
        )
        
        embed.add_field(
            name="🎨 Embed Design",
            value=f"**Title:** {guild_config.get('embed_title', 'Not set')}\n"
                  f"**Color:** {guild_config.get('embed_color', '#0099ff')}",
            inline=True
        )
        
        add_roles = guild_config.get("add_roles", [])
        add_role_names = []
        for role_id in add_roles:
            role = guild.get_role(role_id)
            if role:
                add_role_names.append(role.name)
                
        embed.add_field(
            name="➕ Roles to Add",
            value="\n".join([f"• {name}" for name in add_role_names]) if add_role_names else "None configured",
            inline=True
        )
        
        remove_roles = guild_config.get("remove_roles", [])
        remove_role_names = []
        for role_id in remove_roles:
            role = guild.get_role(role_id)
            if role:
                remove_role_names.append(role.name)
                
        embed.add_field(
            name="➖ Roles to Remove",
            value="\n".join([f"• {role}" for role in remove_role_names]) if remove_role_names else "None configured",
            inline=True
        )
        
        pending = self.config.load_pending()
        guild_pending = [k for k in pending.keys() if k.startswith(f"{guild.id}_")]
        
        embed.add_field(
            name="⏳ Active Verifications",
            value=f"{len(guild_pending)} users currently verifying",
            inline=True
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed

    @commands.command(name="zsafe", aliases=["zs", "verification"])
    @commands.has_permissions(manage_guild=True)
    async def zsafe_setup(self, ctx):
        prefix = self.get_prefix(ctx)
        
        embed = discord.Embed(
            title="🔐 ZSafe Verification System",
            description="**Complete verification system setup and management**\n\n"
                       "🎯 **What is ZSafe?**\n"
                       "ZSafe is a secure verification system that uses random number codes "
                       "to verify users, similar to a digital safe combination.\n\n"
                       "📋 **Setup Steps:**\n"
                       "1. Configure basic settings (code length, button label)\n"
                       "2. Design your verification embed\n"
                       "3. Set roles to add/remove after verification\n"
                       "4. Use the post command to deploy verification\n\n"
                       "**Use the buttons below to configure everything:**",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🛠️ Available Options",
            value="• **📝 Basic Settings** - Code length, button label\n"
                  "• **🎨 Embed Design** - Title, description, color\n"
                  "• **➕ Add Roles** - Roles given after verification\n"
                  "• **➖ Remove Roles** - Roles removed after verification\n"
                  "• **📊 View Status** - Check current configuration",
            inline=False
        )
        
        embed.add_field(
            name="⚡ Quick Commands",
            value=f"`{prefix}zsafe-post [channel]` - Post verification embed\n"
                  f"`{prefix}zsafe-status` - View current settings\n"
                  f"`{prefix}zsafe-help` - Show detailed help",
            inline=False
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        
        view = ZSafeSetupView(self, ctx.guild.id)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="zsafe-post")
    @commands.has_permissions(manage_guild=True)
    async def zsafe_post(self, ctx, channel: discord.TextChannel = None):
        config = self.config.load_config()
        guild_config = config["guilds"].get(str(ctx.guild.id), {})
        prefix = self.get_prefix(ctx)
        
        if not guild_config:
            embed = discord.Embed(
                title="❌ ZSafe Not Configured",
                description="ZSafe is not set up for this server!\n\n"
                           f"Use `{prefix}zsafe` to configure it first.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
            
        target_channel = channel or ctx.channel
        
        bot_perms = target_channel.permissions_for(ctx.guild.me)
        if not bot_perms.send_messages:
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description=f"I don't have permission to send messages in {target_channel.mention}!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
            return
        
        embed = self.create_verification_embed(guild_config)
        view = VerificationView(self, guild_config.get("button_label", "🔐 Verify"))
        
        try:
            await target_channel.send(embed=embed, view=view)
            
            success_embed = discord.Embed(
                title="✅ Verification Posted",
                description=f"ZSafe verification embed has been posted in {target_channel.mention}!",
                color=discord.Color.green()
            )
            success_embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=success_embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Failed to Post",
                description=f"Error: {str(e)}\n\nMake sure I have permission to send messages in that channel.",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=error_embed)

    @commands.command(name="zsafe-status")
    @commands.has_permissions(manage_guild=True)
    async def zsafe_status(self, ctx):
        embed = await self.create_status_embed(ctx.guild)
        await ctx.send(embed=embed)

    @commands.command(name="zsafe-reset")
    @commands.has_permissions(manage_guild=True)
    async def zsafe_reset(self, ctx):
        view = ConfirmResetView(self, ctx.guild.id)
        embed = discord.Embed(
            title="⚠️ Confirm ZSafe Reset",
            description="Are you sure you want to reset ALL ZSafe settings?\n\n"
                       "**This will delete:**\n"
                       "• All configuration settings\n"
                       "• Role assignments\n"
                       "• Embed customization\n"
                       "• Pending verifications\n\n"
                       "**This action cannot be undone!**",
            color=discord.Color.red()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed, view=view)

    @commands.command(name="zsafe-help")
    async def zsafe_help(self, ctx):
        prefix = self.get_prefix(ctx)
        
        embed = discord.Embed(
            title="🔐 ZSafe Verification System Help",
            description="**Complete verification system with number pad interface**",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🎯 What is ZSafe?",
            value="ZSafe is a secure verification system that generates random number codes "
                  "for users to enter using an interactive number pad, similar to a digital safe.",
            inline=False
        )
        
        embed.add_field(
            name="👑 Admin Commands",
            value=f"`{prefix}zsafe` - Main setup menu (all-in-one)\n"
                  f"`{prefix}zsafe-post [channel]` - Post verification embed\n"
                  f"`{prefix}zsafe-status` - View current configuration\n"
                  f"`{prefix}zsafe-reset` - Reset all settings\n"
                  f"`{prefix}zsafe-help` - Show this help",
            inline=False
        )
        
        embed.add_field(
            name="🛠️ Setup Features",
            value="• **Code Length** - 1-8 digit verification codes\n"
                  "• **Custom Button** - Personalized verification button\n"
                  "• **Embed Design** - Custom title, description, colors\n"
                  "• **Role Management** - Add/remove roles after verification\n"
                  "• **Quick Deployment** - Post verification with single command",
            inline=False
        )
        
        embed.add_field(
            name="👤 User Experience",
            value="1. Click verification button\n"
                  "2. Receive random code (ephemeral message)\n"
                  "3. Use interactive number pad to enter code\n"
                  "4. Get verified and receive configured roles\n"
                  "5. Codes expire after 5 minutes for security",
            inline=False
        )
        
        embed.add_field(
            name="🔒 Security Features",
            value="• **Ephemeral Messages** - Only user can see verification\n"
                  "• **User-Specific** - Can't use someone else's keypad\n"
                  "• **Time Limits** - Codes expire automatically\n"
                  "• **One at a Time** - Prevents multiple pending verifications\n"
                  "• **Auto Cleanup** - Expired codes removed automatically",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Requirements",
            value="• **Manage Server** permission for setup commands\n"
                  "• **Manage Roles** permission for role assignment\n"
                  "• Bot needs **Send Messages** permission in target channels",
            inline=False
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            pending = self.config.load_pending()
            current_time = time.time()
            expired_keys = []
            
            for key, data in pending.items():
                if current_time - data["timestamp"] > 300:
                    expired_keys.append(key)
                    
            for key in expired_keys:
                del pending[key]
                
            if expired_keys:
                self.config.save_pending(pending)
                print(f"🧹 ZSafe: Cleaned up {len(expired_keys)} expired verification codes")
                
        except Exception as e:
            print(f"ZSafe: Error cleaning up verification codes: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = self.config.load_config()
        guild_config = config["guilds"].get(str(member.guild.id), {})
        
        if guild_config:
            print(f"🔐 ZSafe: New member {member} joined {member.guild.name} - verification available")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        try:
            config = self.config.load_config()
            guild_id_str = str(guild.id)
            
            if guild_id_str in config["guilds"]:
                del config["guilds"][guild_id_str]
                self.config.save_config(config)
                print(f"🧹 ZSafe: Cleaned up config for {guild.name}")
                
            pending = self.config.load_pending()
            guild_keys = [k for k in pending.keys() if k.startswith(f"{guild.id}_")]
            for key in guild_keys:
                del pending[key]
                
            if guild_keys:
                self.config.save_pending(pending)
                print(f"🧹 ZSafe: Cleaned up {len(guild_keys)} pending verifications for {guild.name}")
                
        except Exception as e:
            print(f"ZSafe: Error cleaning up guild data: {e}")

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type == discord.InteractionType.component:
            if hasattr(interaction, 'custom_id') and 'zsafe' in str(interaction.custom_id):
                try:
                    pending = self.config.load_pending()
                    current_time = time.time()
                    expired_keys = []
                    
                    for key, data in pending.items():
                        if current_time - data["timestamp"] > 300:
                            expired_keys.append(key)
                            
                    for key in expired_keys:
                        del pending[key]
                        
                    if expired_keys:
                        self.config.save_pending(pending)
                        
                except Exception:
                    pass


async def setup(bot):
    await bot.add_cog(ZSafe(bot))