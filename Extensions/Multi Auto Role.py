import discord
from discord.ext import commands
import json
import os
import asyncio
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class MultiRoleView(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        
        config = self.cog.load_config(self.ctx.guild.id)
        is_enabled = config.get("enabled", False) if config else False
        

        enable_button = discord.ui.Button(
            label="✅ Disable" if is_enabled else "🔴 Enable",
            style=discord.ButtonStyle.danger if is_enabled else discord.ButtonStyle.success,
            custom_id="toggle_enable"
        )
        enable_button.callback = self.toggle_enable
        self.add_item(enable_button)
        

        set_roles_button = discord.ui.Button(
            label="🎭 Set Roles",
            style=discord.ButtonStyle.primary,
            custom_id="set_roles"
        )
        set_roles_button.callback = self.set_roles
        self.add_item(set_roles_button)
        

        refresh_button = discord.ui.Button(
            label="🔄 Refresh",
            style=discord.ButtonStyle.secondary,
            custom_id="refresh"
        )
        refresh_button.callback = self.refresh_status
        self.add_item(refresh_button)
    
    async def toggle_enable(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command author can toggle this!", ephemeral=True)
            return
        
        config = self.cog.load_config(self.ctx.guild.id)
        if not config:
            config = {"enabled": False, "roles": []}
        
        config["enabled"] = not config.get("enabled", False)
        self.cog.save_config(self.ctx.guild.id, config)
        
        status = "enabled" if config["enabled"] else "disabled"
        embed = self.create_status_embed()
        self.update_buttons()
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def set_roles(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command author can set roles!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎭 Set Auto Roles",
            description="**Please mention all the roles you want to assign to new members!**\n\n"
                       "Example: `@Member @Newcomer @Verified`\n\n"
                       "You have 60 seconds to send your message with the role mentions.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        def check(message):
            return (message.author == self.ctx.author and 
                   message.channel == self.ctx.channel)
        
        try:
            message = await self.cog.bot.wait_for('message', timeout=60.0, check=check)
            
            if not message.role_mentions:
                embed = discord.Embed(
                    title="❌ No Roles Found",
                    description="Please mention at least one role! Try again.",
                    color=discord.Color.red()
                )
                embed.set_footer(text="Made By TheHolyOneZ")
                await message.reply(embed=embed)
                

                embed = self.create_status_embed()
                self.update_buttons()
                await interaction.edit_original_response(embed=embed, view=self)
                return
            

            config = self.cog.load_config(self.ctx.guild.id)
            if not config:
                config = {"enabled": False, "roles": []}
            
            config["roles"] = [role.id for role in message.role_mentions]
            self.cog.save_config(self.ctx.guild.id, config)
            

            role_list = [f"• {role.name}" for role in message.role_mentions]
            embed = discord.Embed(
                title="✅ Roles Set Successfully!",
                description=f"**{len(message.role_mentions)} roles** will now be assigned to new members:\n\n" + 
                           "\n".join(role_list),
                color=discord.Color.green()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await message.reply(embed=embed)
            

            embed = self.create_status_embed()
            self.update_buttons()
            await interaction.edit_original_response(embed=embed, view=self)
            
        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="⏰ Timeout",
                description="Role setup cancelled due to timeout.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await interaction.edit_original_response(embed=embed, view=None)
    
    async def refresh_status(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command author can refresh!", ephemeral=True)
            return
        
        embed = self.create_status_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    def create_status_embed(self):
        config = self.cog.load_config(self.ctx.guild.id)
        
        embed = discord.Embed(
            title="🎭 Multi Auto Role System",
            description="**Automatically assign multiple roles to new members when they join!**",
            color=discord.Color.green() if config and config.get("enabled", False) else discord.Color.red()
        )
        
        if config:
            status = "🟢 **ENABLED**" if config.get("enabled", False) else "🔴 **DISABLED**"
            embed.add_field(
                name="📊 Status",
                value=status,
                inline=True
            )
            
            role_count = len(config.get("roles", []))
            embed.add_field(
                name="🎭 Configured Roles",
                value=f"**{role_count}** roles",
                inline=True
            )
            
            embed.add_field(
                name="⚡ Quick Info",
                value="Click buttons below to manage",
                inline=True
            )
            

            if config.get("roles"):
                role_list = []
                for role_id in config["roles"][:10]:
                    role = self.ctx.guild.get_role(role_id)
                    if role:
                        role_list.append(f"• {role.name}")
                    else:
                        role_list.append(f"• Role ID: {role_id} (Deleted)")
                
                if len(config["roles"]) > 10:
                    role_list.append(f"... and {len(config['roles']) - 10} more")
                
                embed.add_field(
                    name="📋 Roles List",
                    value="\n".join(role_list) if role_list else "No valid roles found",
                    inline=False
                )
        else:
            embed.add_field(
                name="📊 Status",
                value="🔴 **NOT CONFIGURED**",
                inline=True
            )
            
            embed.add_field(
                name="🎭 Configured Roles",
                value="**0** roles",
                inline=True
            )
            
            embed.add_field(
                name="⚡ Get Started",
                value="Click 'Set Roles' to begin",
                inline=True
            )
        
        embed.add_field(
            name="✨ Key Features",
            value="• **Multiple roles** assigned instantly on join\n"
                  "• **Simple setup** with role mentions\n"
                  "• **Easy toggle** enable/disable\n"
                  "• **Real-time status** updates",
            inline=False
        )
        
        embed.set_footer(text="Made By TheHolyOneZ")
        return embed

class MultiAutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_dir = "Data/multi_auto_role"
        self.ensure_directories()
    
    def ensure_directories(self):
        os.makedirs(self.config_dir, exist_ok=True)
    
    def load_config(self, guild_id: int) -> Optional[dict]:
        config_path = os.path.join(self.config_dir, f"{guild_id}.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config for guild {guild_id}: {e}")
        return None
    
    def save_config(self, guild_id: int, config: dict):
        config_path = os.path.join(self.config_dir, f"{guild_id}.json")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save config for guild {guild_id}: {e}")
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        
        config = self.load_config(member.guild.id)
        if not config or not config.get("enabled", False):
            return
        
        roles_to_assign = []
        for role_id in config.get("roles", []):
            role = member.guild.get_role(role_id)
            if role:
                roles_to_assign.append(role)
        
        if not roles_to_assign:
            return
        
        try:
            await member.add_roles(*roles_to_assign, reason="Multi Auto Role - Automatic assignment on join")
            logger.info(f"Assigned {len(roles_to_assign)} roles to {member} in {member.guild}")
        except discord.Forbidden:
            logger.error(f"No permission to assign roles to {member} in {member.guild}")
        except Exception as e:
            logger.error(f"Error assigning roles to {member}: {e}")
    
    @commands.command(name="multirole")
    @commands.has_permissions(administrator=True)
    async def multirole(self, ctx):
        view = MultiRoleView(self, ctx)
        embed = view.create_status_embed()
        await ctx.send(embed=embed, view=view)

def setup(bot):
    cog = MultiAutoRole(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog
