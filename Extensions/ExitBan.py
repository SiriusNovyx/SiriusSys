import discord
from discord.ext import commands
import asyncio
import json
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ExitBan(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = "data/exitban.json"
        self.user_join_times = {}
        self.settings = {}
        self.ban_lists = {}
        self.load_data()
    
    def load_data(self):
        try:
            os.makedirs("data", exist_ok=True)
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.settings = data.get('settings', {})
                    self.ban_lists = data.get('ban_lists', {})
        except Exception as e:
            logger.error(f"Error loading ExitBan data: {e}")
            self.settings = {}
            self.ban_lists = {}
    
    def save_data(self):
        try:
            data = {
                'settings': self.settings,
                'ban_lists': self.ban_lists
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving ExitBan data: {e}")
    
    def get_guild_settings(self, guild_id):
        guild_id = str(guild_id)
        if guild_id not in self.settings:
            self.settings[guild_id] = {
                'enabled': False,
                'time_limit': 30,
                'auto_ban': False,
                'ban_reason': 'Left server too quickly (ExitBan)'
            }
        return self.settings[guild_id]
    
    def get_guild_ban_list(self, guild_id):
        guild_id = str(guild_id)
        if guild_id not in self.ban_lists:
            self.ban_lists[guild_id] = []
        return self.ban_lists[guild_id]
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        
        guild_id = member.guild.id
        if guild_id not in self.user_join_times:
            self.user_join_times[guild_id] = {}
        
        self.user_join_times[guild_id][member.id] = datetime.now()
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.bot:
            return
        
        guild_id = member.guild.id
        settings = self.get_guild_settings(guild_id)
        
        if not settings['enabled']:
            return
        
        if (guild_id not in self.user_join_times or 
            member.id not in self.user_join_times[guild_id]):
            return
        
        join_time = self.user_join_times[guild_id][member.id]
        leave_time = datetime.now()
        time_in_server = leave_time - join_time
        
        if time_in_server.total_seconds() <= (settings['time_limit'] * 60):
            if settings['auto_ban']:
                try:
                    await member.guild.ban(member, reason=settings['ban_reason'])
                    logger.info(f"Auto-banned {member} from {member.guild} for leaving too quickly")
                except Exception as e:
                    logger.error(f"Failed to auto-ban {member}: {e}")
            else:
                ban_list = self.get_guild_ban_list(guild_id)
                if member.id not in ban_list:
                    ban_list.append(member.id)
                    self.save_data()
                    logger.info(f"Added {member} to ban list for {member.guild}")
        
        del self.user_join_times[guild_id][member.id]
    
    @commands.command(name='exitban')
    @commands.has_permissions(administrator=True)
    async def exitban_panel(self, ctx):
        embed, view = await self.create_main_panel(ctx.guild.id)
        await ctx.send(embed=embed, view=view)
    
    async def create_main_panel(self, guild_id):
        settings = self.get_guild_settings(guild_id)
        ban_list = self.get_guild_ban_list(guild_id)
        
        if settings['enabled']:
            color = 0x00ff00
        else:
            color = 0xff0000
        
        embed = discord.Embed(
            title="🚪 ExitBan Control Panel",
            description="Automatically manage users who leave too quickly after joining",
            color=color
        )
        
        status_emoji = "🟢" if settings['enabled'] else "🔴"
        status_text = "**ENABLED**" if settings['enabled'] else "**DISABLED**"
        
        mode_emoji = "🤖" if settings['auto_ban'] else "📝"
        mode_text = "**Auto Ban**" if settings['auto_ban'] else "**Manual Ban List**"
        
        embed.add_field(
            name="📊 System Status",
            value=f"{status_emoji} {status_text}",
            inline=True
        )
        
        embed.add_field(
            name="⚙️ Ban Mode",
            value=f"{mode_emoji} {mode_text}",
            inline=True
        )
        
        embed.add_field(
            name="⏰ Time Limit",
            value=f"**{settings['time_limit']}** minutes",
            inline=True
        )
        
        if not settings['auto_ban']:
            list_emoji = "📋" if len(ban_list) > 0 else "📄"
            embed.add_field(
                name="📝 Pending Bans",
                value=f"{list_emoji} **{len(ban_list)}** users waiting",
                inline=True
            )
        else:
            embed.add_field(
                name="🤖 Auto Mode",
                value="⚡ Users banned instantly",
                inline=True
            )
        
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        embed.add_field(
            name="📋 Ban Reason",
            value=f"```{settings['ban_reason']}```",
            inline=False
        )
        
        embed.add_field(
            name="📋 Quick Commands",
            value="• `!exitban_banned` - View banned users\n• `!exitban_list` - View ban list",
            inline=False
        )
        
        if settings['enabled']:
            embed.add_field(
                name="ℹ️ How it works",
                value=f"Users who leave within **{settings['time_limit']} minutes** will be {'**banned automatically**' if settings['auto_ban'] else '**added to ban list**'}",
                inline=False
            )
        else:
            embed.add_field(
                name="⚠️ System Disabled",
                value="Click **Toggle Status** to enable ExitBan protection",
                inline=False
            )
        
        embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
        
        view = ExitBanView(self, guild_id)
        return embed, view
    
    async def toggle_status(self, guild_id):
        settings = self.get_guild_settings(guild_id)
        settings['enabled'] = not settings['enabled']
        self.save_data()
    
    async def toggle_mode(self, guild_id):
        settings = self.get_guild_settings(guild_id)
        settings['auto_ban'] = not settings['auto_ban']
        self.save_data()
    
    async def set_time_limit(self, guild_id, minutes):
        settings = self.get_guild_settings(guild_id)
        settings['time_limit'] = minutes
        self.save_data()
    
    async def set_ban_reason(self, guild_id, reason):
        settings = self.get_guild_settings(guild_id)
        settings['ban_reason'] = reason
        self.save_data()
    
    @commands.command(name='exitban_banned')
    @commands.has_permissions(administrator=True)
    async def show_banned_users(self, ctx):
        try:
            banned_users = []
            async for ban_entry in ctx.guild.bans():
                if 'ExitBan' in (ban_entry.reason or ''):
                    banned_users.append(ban_entry)
            
            if not banned_users:
                embed = discord.Embed(
                    title="🚫 ExitBan - Banned Users",
                    description="No users have been banned by ExitBan yet.",
                    color=0x666666
                )
                embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
                await ctx.send(embed=embed)
                return
            
            embed = discord.Embed(
                title="🚫 ExitBan - Banned Users",
                description=f"Found **{len(banned_users)}** users banned by ExitBan",
                color=0xff4444
            )
            
            for i, ban_entry in enumerate(banned_users[:10]):
                user = ban_entry.user
                reason = ban_entry.reason or "No reason provided"
                embed.add_field(
                    name=f"{i+1}. {user.name}#{user.discriminator}",
                    value=f"**ID:** `{user.id}`\n**Reason:** {reason}",
                    inline=False
                )
            
            if len(banned_users) > 10:
                embed.set_footer(text=f"Made by TheHolyOneZ • Showing 10 of {len(banned_users)} banned users")
            else:
                embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Error fetching banned users: {e}",
                color=0xff0000
            )
            error_embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
            await ctx.send(embed=error_embed)
    
    @commands.command(name='exitban_list')
    @commands.has_permissions(administrator=True)
    async def show_ban_list(self, ctx):
        settings = self.get_guild_settings(ctx.guild.id)
        
        if settings['auto_ban']:
            embed = discord.Embed(
                title="📝 ExitBan - Ban List",
                description="🤖 **Auto-ban is enabled**\nUsers are banned automatically when they leave too quickly.",
                color=0x666666
            )
            embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
            await ctx.send(embed=embed)
            return
        
        ban_list = self.get_guild_ban_list(ctx.guild.id)
        
        if not ban_list:
            embed = discord.Embed(
                title="📝 ExitBan - Ban List",
                description="📄 **No users on the ban list**\nUsers who leave too quickly will appear here.",
                color=0x666666
            )
            embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="📝 ExitBan - Ban List",
            description=f"📋 **{len(ban_list)}** users pending manual ban",
            color=0xffaa00
        )
        
        user_list = []
        for i, user_id in enumerate(ban_list[:10], 1):
            try:
                user = await self.bot.fetch_user(user_id)
                user_list.append(f"`{i}.` **{user.name}#{user.discriminator}**\n└ ID: `{user_id}`")
            except:
                user_list.append(f"`{i}.` **Unknown User**\n└ ID: `{user_id}`")
        
        embed.add_field(
            name="👥 Users to Ban",
            value="\n\n".join(user_list) if user_list else "None",
            inline=False
        )
        
        if len(ban_list) > 10:
            embed.set_footer(text=f"Made by TheHolyOneZ • Showing 10 of {len(ban_list)} users")
        else:
            embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
        
        view = BanListView(self, ctx.guild.id)
        await ctx.send(embed=embed, view=view)

class ExitBanView(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
    
    @discord.ui.button(label='Toggle Status', style=discord.ButtonStyle.primary, emoji='🔄')
    async def toggle_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.toggle_status(self.guild_id)
        embed, view = await self.cog.create_main_panel(self.guild_id)
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label='Toggle Mode', style=discord.ButtonStyle.secondary, emoji='⚙️')
    async def toggle_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.toggle_mode(self.guild_id)
        embed, view = await self.cog.create_main_panel(self.guild_id)
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label='Set Time Limit', style=discord.ButtonStyle.secondary, emoji='⏰')
    async def set_time_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TimeModal(self.cog, self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='Set Ban Reason', style=discord.ButtonStyle.secondary, emoji='📝')
    async def set_ban_reason(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(self.cog, self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='Manual Ban All', style=discord.ButtonStyle.danger, emoji='🔨')
    async def manual_ban_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = self.cog.get_guild_settings(self.guild_id)
        if settings['auto_ban']:
            embed = discord.Embed(
                title="❌ Cannot Execute",
                description="**Auto-ban is enabled**\nDisable auto-ban to use manual banning.",
                color=0xff0000
            )
            embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        ban_list = self.cog.get_guild_ban_list(self.guild_id)
        if not ban_list:
            embed = discord.Embed(
                title="❌ No Users to Ban",
                description="**Ban list is empty**\nNo users are currently pending ban.",
                color=0xff0000
            )
            embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        loading_embed = discord.Embed(
            title="🔨 Banning Users...",
            description=f"Processing **{len(ban_list)}** users...",
            color=0xffaa00
        )
        loading_embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
        await interaction.response.send_message(embed=loading_embed, ephemeral=True)
        
        banned_count = 0
        failed_count = 0
        failed_users = []
        
        for user_id in ban_list.copy():
            try:
                user = await self.cog.bot.fetch_user(user_id)
                await interaction.guild.ban(user, reason=settings['ban_reason'])
                ban_list.remove(user_id)
                banned_count += 1
            except Exception as e:
                failed_count += 1
                failed_users.append(f"<@{user_id}> - {str(e)[:50]}")
                logger.error(f"Failed to ban user {user_id}: {e}")
        
        self.cog.save_data()
        
        if failed_count == 0:
            result_embed = discord.Embed(
                title="✅ Ban Complete",
                description=f"**Successfully banned {banned_count} users**\nAll users have been removed from the server.",
                color=0x00ff00
            )
        else:
            result_embed = discord.Embed(
                title="⚠️ Ban Partially Complete",
                description=f"**Banned:** {banned_count} users\n**Failed:** {failed_count} users",
                color=0xffaa00
            )
            if failed_users:
                result_embed.add_field(
                    name="❌ Failed Bans",
                    value="\n".join(failed_users[:5]) + (f"\n... and {len(failed_users)-5} more" if len(failed_users) > 5 else ""),
                    inline=False
                )
        
        result_embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
        await interaction.edit_original_response(embed=result_embed)
        
        embed, view = await self.cog.create_main_panel(self.guild_id)
        await interaction.message.edit(embed=embed, view=view)

class BanListView(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
    
    @discord.ui.button(label='Ban All', style=discord.ButtonStyle.danger, emoji='🔨')
    async def ban_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = self.cog.get_guild_settings(self.guild_id)
        ban_list = self.cog.get_guild_ban_list(self.guild_id)
        
        if not ban_list:
            embed = discord.Embed(
                title="❌ No Users to Ban",
                description="**Ban list is empty**\nNo users are currently pending ban.",
                color=0xff0000
            )
            embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        loading_embed = discord.Embed(
            title="🔨 Banning Users...",
            description=f"Processing **{len(ban_list)}** users...",
            color=0xffaa00
        )
        loading_embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
        await interaction.response.send_message(embed=loading_embed, ephemeral=True)
        
        banned_count = 0
        failed_count = 0
        failed_users = []
        
        for user_id in ban_list.copy():
            try:
                user = await self.cog.bot.fetch_user(user_id)
                await interaction.guild.ban(user, reason=settings['ban_reason'])
                ban_list.remove(user_id)
                banned_count += 1
            except Exception as e:
                failed_count += 1
                failed_users.append(f"<@{user_id}> - {str(e)[:50]}")
                logger.error(f"Failed to ban user {user_id}: {e}")
        
        self.cog.save_data()
        
        if failed_count == 0:
            result_embed = discord.Embed(
                title="✅ Ban Complete",
                description=f"**Successfully banned {banned_count} users**\nAll users have been removed from the server.",
                color=0x00ff00
            )
        else:
            result_embed = discord.Embed(
                title="⚠️ Ban Partially Complete",
                description=f"**Banned:** {banned_count} users\n**Failed:** {failed_count} users",
                color=0xffaa00
            )
            if failed_users:
                result_embed.add_field(
                    name="❌ Failed Bans",
                    value="\n".join(failed_users[:5]) + (f"\n... and {len(failed_users)-5} more" if len(failed_users) > 5 else ""),
                    inline=False
                )
        
        result_embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
        await interaction.edit_original_response(embed=result_embed)
    
    @discord.ui.button(label='Clear List', style=discord.ButtonStyle.secondary, emoji='🗑️')
    async def clear_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        ban_list = self.cog.get_guild_ban_list(self.guild_id)
        cleared_count = len(ban_list)
        ban_list.clear()
        self.cog.save_data()
        
        embed = discord.Embed(
            title="🗑️ Ban List Cleared",
            description=f"**{cleared_count} users** have been removed from the ban list.\nThey will no longer be banned.",
            color=0x00ff00
        )
        embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label='Refresh List', style=discord.ButtonStyle.primary, emoji='🔄')
    async def refresh_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = self.cog.get_guild_settings(self.guild_id)
        
        if settings['auto_ban']:
            embed = discord.Embed(
                title="📝 ExitBan - Ban List",
                description="🤖 **Auto-ban is enabled**\nUsers are banned automatically when they leave too quickly.",
                color=0x666666
            )
            embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
            await interaction.response.edit_message(embed=embed, view=None)
            return
        
        ban_list = self.cog.get_guild_ban_list(self.guild_id)
        
        if not ban_list:
            embed = discord.Embed(
                title="📝 ExitBan - Ban List",
                description="📄 **No users on the ban list**\nUsers who leave too quickly will appear here.",
                color=0x666666
            )
            embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
            await interaction.response.edit_message(embed=embed, view=BanListView(self.cog, self.guild_id))
            return
        
        embed = discord.Embed(
            title="📝 ExitBan - Ban List",
            description=f"📋 **{len(ban_list)}** users pending manual ban",
            color=0xffaa00
        )
        
        user_list = []
        for i, user_id in enumerate(ban_list[:10], 1):
            try:
                user = await self.cog.bot.fetch_user(user_id)
                user_list.append(f"`{i}.` **{user.name}#{user.discriminator}**\n└ ID: `{user_id}`")
            except:
                user_list.append(f"`{i}.` **Unknown User**\n└ ID: `{user_id}`")
        
        embed.add_field(
            name="👥 Users to Ban",
            value="\n\n".join(user_list) if user_list else "None",
            inline=False
        )
        
        if len(ban_list) > 10:
            embed.set_footer(text=f"Made by TheHolyOneZ • Showing 10 of {len(ban_list)} users")
        else:
            embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
        
        view = BanListView(self.cog, self.guild_id)
        await interaction.response.edit_message(embed=embed, view=view)

class TimeModal(discord.ui.Modal, title='⏰ Set Time Limit'):
    def __init__(self, cog, guild_id):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        
        current_limit = self.cog.get_guild_settings(guild_id)['time_limit']
        self.time_input.placeholder = f'Current: {current_limit} minutes'
    
    time_input = discord.ui.TextInput(
        label='Time Limit (in minutes)',
        placeholder='Enter time limit in minutes (e.g., 30)',
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.time_input.value)
            if minutes < 1 or minutes > 10080:
                embed = discord.Embed(
                    title="❌ Invalid Time Limit",
                    description="**Time limit must be between 1 and 10,080 minutes (1 week)**\nPlease enter a valid number.",
                    color=0xff0000
                )
                embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            await self.cog.set_time_limit(self.guild_id, minutes)
            
            if minutes < 60:
                time_display = f"{minutes} minutes"
            elif minutes < 1440:
                hours = minutes // 60
                mins = minutes % 60
                time_display = f"{hours}h {mins}m" if mins > 0 else f"{hours} hours"
            else:
                days = minutes // 1440
                remaining = minutes % 1440
                hours = remaining // 60
                time_display = f"{days}d {hours}h" if hours > 0 else f"{days} days"
            
            embed = discord.Embed(
                title="⏰ Time Limit Updated",
                description=f"**New time limit:** {time_display}\nUsers who leave within this time will be processed by ExitBan.",
                color=0x00ff00
            )
            embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Input",
                description="**Please enter a valid number**\nExample: 30 (for 30 minutes)",
                color=0xff0000
            )
            embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
            await interaction.response.send_message(embed=embed, ephemeral=True)

class ReasonModal(discord.ui.Modal, title='📝 Set Ban Reason'):
    def __init__(self, cog, guild_id):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        
        current_reason = self.cog.get_guild_settings(guild_id)['ban_reason']
        self.reason_input.default = current_reason
    
    reason_input = discord.ui.TextInput(
        label='Ban Reason',
        placeholder='Enter the reason for banning users...',
        required=True,
        max_length=512,
        style=discord.TextStyle.paragraph
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value.strip()
        if not reason:
            embed = discord.Embed(
                title="❌ Invalid Reason",
                description="**Ban reason cannot be empty**\nPlease provide a valid reason for banning users.",
                color=0xff0000
            )
            embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await self.cog.set_ban_reason(self.guild_id, reason)
        
        embed = discord.Embed(
            title="📝 Ban Reason Updated",
            description=f"**New ban reason:**\n```{reason}```\nThis reason will be used when banning users.",
            color=0x00ff00
        )
        embed.set_footer(text="Made by TheHolyOneZ • ExitBan Extension")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

def setup(bot):
    cog = ExitBan(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog


# Extension got speedran by TheHolyOneZ (me) so report bugs to me: https:/zygnalbot.com/support/

