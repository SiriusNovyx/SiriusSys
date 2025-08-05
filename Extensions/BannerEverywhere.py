import discord
from discord.ext import commands
from discord import app_commands, ui, ButtonStyle
import json
import logging
import os
from typing import Dict, List, Optional, Any
import asyncio

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DATA_DIR = os.path.join("data", "banners")

class BannerPanelView(ui.View):
    def __init__(self, bot, cog):
        super().__init__(timeout=None)
        self.bot = bot
        self.cog = cog

    @ui.button(label="Add Channels", style=ButtonStyle.primary, custom_id="add_channels_button")
    async def add_channels_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            "Please send a message in this channel with the channel(s) and banner URL(s) you want to add, separated by commas.\n"
            "**The bot will only add banners to messages that already contain an embed.**\n"
            "Format: `channel_mention:banner_url`\n"
            "Example: `#general:https://example.com/banner1.gif`, `#announcements:https://example.com/banner2.gif`",
            ephemeral=True
        )

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            user_message = await self.bot.wait_for('message', check=check, timeout=60.0)
            await self.cog._add_channels_by_message_logic(interaction, user_message)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ You took too long to respond. Please press the button again to retry.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error handling add channels message: {e}")
            await interaction.followup.send("An unexpected error occurred. Please try again.", ephemeral=True)

    @ui.button(label="Remove Channels", style=ButtonStyle.danger, custom_id="remove_channels_button")
    async def remove_channels_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            "Please send a message in this channel with the channel(s) you want to stop monitoring, separated by commas.\n"
            "Example: `#general, #announcements`",
            ephemeral=True
        )

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            user_message = await self.bot.wait_for('message', check=check, timeout=60.0)
            await self.cog._remove_channels_by_message_logic(interaction, user_message)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ You took too long to respond. Please press the button again to retry.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error handling remove channels message: {e}")
            await interaction.followup.send("An unexpected error occurred. Please try again.", ephemeral=True)

    @ui.button(label="Status", style=ButtonStyle.secondary, custom_id="status_button")
    async def status_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.cog._banner_status_logic(interaction.guild.id, interaction.response.send_message)

class BannerEverywhere(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.guild_configs: Dict[int, Dict[int, str]] = {}
        os.makedirs(BASE_DATA_DIR, exist_ok=True)
        self._load_all_guild_configs()
        self.bot.add_view(BannerPanelView(self.bot, self))

    def _get_guild_config_path(self, guild_id: int) -> str:
        guild_data_dir = os.path.join(BASE_DATA_DIR, str(guild_id))
        os.makedirs(guild_data_dir, exist_ok=True)
        return os.path.join(guild_data_dir, "config.json")

    def _load_guild_config(self, guild_id: int):
        config_path = self._get_guild_config_path(guild_id)
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                try:
                    loaded_data = json.load(f)
                    if isinstance(loaded_data, dict) and 'channel_id' in loaded_data:
                        channel_id = loaded_data.get('channel_id')
                        banner_url = loaded_data.get('banner_url')
                        if channel_id and banner_url:
                            self.guild_configs[guild_id] = {channel_id: banner_url}
                            logger.warning(f"Migrated old banner config format for guild {guild_id}.")
                        else:
                            self.guild_configs[guild_id] = {}
                            logger.warning(f"Old banner config for guild {guild_id} was incomplete.")
                    else:
                        config = {int(k): v for k, v in loaded_data.items() if str(k).isdigit()}
                        self.guild_configs[guild_id] = config
                        logger.info(f"Loaded banner config for guild {guild_id}.")
                except json.JSONDecodeError:
                    self.guild_configs[guild_id] = {}
                    logger.error(f"Failed to decode JSON config for guild {guild_id}. The file might be corrupt.")
        else:
            self.guild_configs[guild_id] = {}

    def _load_all_guild_configs(self):
        for item in os.listdir(BASE_DATA_DIR):
            item_path = os.path.join(BASE_DATA_DIR, item)
            if os.path.isdir(item_path) and item.isdigit():
                self._load_guild_config(int(item))
        logger.info("Loaded all existing guild configurations for BannerEverywhere.")

    def _save_guild_config(self, guild_id: int):
        config_path = self._get_guild_config_path(guild_id)
        try:
            with open(config_path, 'w') as f:
                save_data = {str(k): v for k, v in self.guild_configs.get(guild_id, {}).items()}
                json.dump(save_data, f, indent=2)
            logger.info(f"Saved banner config for guild {guild_id}.")
        except Exception as e:
            logger.error(f"Error saving banner config for guild {guild_id}: {e}")

    async def _add_channels_by_message_logic(self, interaction: discord.Interaction, user_message: discord.Message):
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ You need administrator permissions to configure the banner.", ephemeral=True)
            return

        items = [item.strip() for item in user_message.content.split(',')]
        channels_to_set = {}
        failed_items = []

        for item in items:
            try:
                channel_mention, banner_url = item.split(':', 1)
                channel_id = int(''.join(filter(str.isdigit, channel_mention)))
                channel = interaction.guild.get_channel(channel_id)
                if channel and isinstance(channel, discord.TextChannel):
                    channels_to_set[channel] = banner_url.strip()
                else:
                    failed_items.append(f"Channel not found or is not a text channel: `{channel_mention}`")
            except (ValueError, IndexError):
                failed_items.append(f"Invalid format: `{item}`")

        if not channels_to_set:
            await interaction.followup.send("❌ No valid channels and banners were provided. Please check the format and try again.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        if guild_id not in self.guild_configs:
            self.guild_configs[guild_id] = {}

        updated_channels = []
        for channel, banner_url in channels_to_set.items():
            self.guild_configs[guild_id][channel.id] = banner_url
            updated_channels.append(channel.mention)
        
        self._save_guild_config(guild_id)

        embed = discord.Embed(
            title="✅ Banner Channels Updated",
            description="The following channels are now being monitored for embeds.",
            color=discord.Color.green()
        )
        embed.add_field(name="Channels Added", value="\n".join(updated_channels), inline=False)
        
        if failed_items:
            embed.add_field(name="Failed to Add", value="\n".join(failed_items), inline=False)
        
        embed.set_footer(text=f"Updated by {interaction.user.name}", icon_url=interaction.user.avatar.url)
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _remove_channels_by_message_logic(self, interaction: discord.Interaction, user_message: discord.Message):
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ You need administrator permissions to configure the banner.", ephemeral=True)
            return

        channel_mentions = [c.strip() for c in user_message.content.split(',')]
        channel_ids_to_remove = []
        for mention in channel_mentions:
            try:
                channel_id = int(''.join(filter(str.isdigit, mention)))
                channel_ids_to_remove.append(channel_id)
            except (ValueError, TypeError):
                logger.warning(f"Could not parse channel ID from input: {mention}")

        if not channel_ids_to_remove:
            await interaction.followup.send("❌ No valid channels were provided. Please mention one or more text channels, separated by commas.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        await self._remove_multi_channels_logic(interaction.user, guild_id, channel_ids_to_remove, interaction.followup.send)

    async def _remove_multi_channels_logic(self, user: discord.User, guild_id: int, channel_ids_to_remove: List[int], respond_func):
        if not user.guild_permissions.administrator:
            await respond_func("❌ You need administrator permissions to configure the banner.", ephemeral=True)
            return
        
        if guild_id not in self.guild_configs:
            await respond_func("❌ No banner channels are currently configured for this server.", ephemeral=True)
            return
        
        removed_channels = []
        failed_channels = []
        for channel_id in channel_ids_to_remove:
            if channel_id in self.guild_configs[guild_id]:
                del self.guild_configs[guild_id][channel_id]
                removed_channels.append(f"<#{channel_id}>")
            else:
                failed_channels.append(f"<#{channel_id}>")
        
        if not removed_channels:
            await respond_func("❌ No valid configured channels were provided to remove.", ephemeral=True)
            return
        
        self._save_guild_config(guild_id)

        embed = discord.Embed(
            title="🗑️ Banner Channels Removed",
            description=f"The following channels are no longer being monitored for embeds.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Channels Removed", value="\n".join(removed_channels), inline=False)
        if failed_channels:
            embed.add_field(name="Channels Not Found", value="\n".join(failed_channels), inline=False)
        
        embed.set_footer(text=f"Updated by {user.name}", icon_url=user.avatar.url)
        embed.timestamp = discord.utils.utcnow()

        await respond_func(embed=embed, ephemeral=True)

    async def _banner_status_logic(self, guild_id: int, respond_func):
        config = self.guild_configs.get(guild_id, {})
        
        embed = discord.Embed(
            title="🖼️ BannerEverywhere Status",
            description="Here's the current configuration for banner channels on this server.",
            color=discord.Color.blue()
        )
        
        if config:
            channel_info = []
            for channel_id, banner_url in config.items():
                channel = self.bot.get_channel(channel_id)
                channel_mention = channel.mention if channel else f"<#{channel_id}> (Not found)"
                channel_info.append(f"• **{channel_mention}** - [View Banner]({banner_url})")
            
            embed.add_field(name="Monitored Channels", value="\n".join(channel_info), inline=False)
        else:
            embed.description = "No banner channels are currently configured for this server. Use the `Add Channels` button to get started!"

        await respond_func(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return

        guild_config = self.guild_configs.get(message.guild.id, {})

        if message.channel.id in guild_config and message.embeds:
            if not message.channel.guild.me.guild_permissions.manage_messages:
                logger.warning(f"Bot lacks 'manage_messages' permission in channel {message.channel.id}. Cannot add banner.")
                return

            banner_url = guild_config[message.channel.id]
            try:
                updated_embeds = []
                for embed in message.embeds:
                    updated_embed = discord.Embed.from_dict(embed.to_dict())
                    updated_embed.set_image(url=banner_url)
                    updated_embeds.append(updated_embed)

                await message.edit(embeds=updated_embeds)
                logger.info(f"Edited embed for message {message.id} in channel {message.channel.id}.")

            except discord.Forbidden:
                logger.warning(f"Missing permissions to edit message {message.id}. Bot needs 'manage_messages'.")
            except Exception as e:
                logger.error(f"An unexpected error occurred while editing message {message.id}: {e}")

    @app_commands.command(name="banners", description="Open the banner configuration panel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def banners_panel_slash(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🖼️ BannerEverywhere Control Panel",
            description="Welcome to the BannerEverywhere control panel. Use the buttons below to manage banner settings.",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Admin Only")
        embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar.url)

        await interaction.response.send_message(
            embed=embed,
            view=BannerPanelView(self.bot, self),
            ephemeral=True
        )

    @commands.command(name="banners", help="Open the banner configuration panel. (Admin Only)")
    @commands.has_permissions(administrator=True)
    async def banners_panel_prefix(self, ctx: commands.Context):
        embed = discord.Embed(
            title="🖼️ BannerEverywhere Control Panel",
            description="Welcome to the BannerEverywhere control panel. Use the buttons below to manage banner settings.",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Admin Only")
        embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar.url)

        await ctx.send(
            embed=embed,
            view=BannerPanelView(self.bot, self)
        )

async def setup(bot):
    await bot.add_cog(BannerEverywhere(bot))
    logger.info("BannerEverywhere extension loaded successfully.")

async def teardown(bot):
    cog = bot.get_cog("BannerEverywhere")
    if cog:
        await bot.remove_cog(cog)
        logger.info("BannerEverywhere extension unloaded gracefully.")