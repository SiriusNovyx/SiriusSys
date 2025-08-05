import discord
from discord.ext import commands, tasks
from discord import app_commands, ui, ButtonStyle
import json
import logging
import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
import threading


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


BASE_DATA_DIR = os.path.join("data", "zauction")


class AuctionPanelView(ui.View):
    def __init__(self, bot, cog):
        super().__init__(timeout=None)
        self.bot = bot
        self.cog = cog

        self.add_item(self.AddChannelButton())
        self.add_item(self.RemoveChannelButton())
        self.add_item(self.StatusButton())
        self.add_item(self.ToggleThreadDeletionButton())
        self.add_item(self.ToggleConfirmationMessageButton()) 
        self.add_item(self.ManualCleanupButton())

    class AddChannelButton(ui.Button):
        def __init__(self):
            super().__init__(label="Add Channel", style=ButtonStyle.primary, custom_id="add_channel_button")
        
        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_modal(AddChannelModal(self.view.cog))

    class RemoveChannelButton(ui.Button):
        def __init__(self):
            super().__init__(label="Remove Channel", style=ButtonStyle.danger, custom_id="remove_channel_button")
        
        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_modal(RemoveChannelModal(self.view.cog))

    class StatusButton(ui.Button):
        def __init__(self):
            super().__init__(label="Status", style=ButtonStyle.secondary, custom_id="status_button")
        
        async def callback(self, interaction: discord.Interaction):
            await self.view.cog._auction_status_logic(interaction.guild.id, interaction.response.send_message, ephemeral=True)

    class ToggleThreadDeletionButton(ui.Button):
        def __init__(self):
            super().__init__(label="Toggle Thread Deletion", style=ButtonStyle.secondary, custom_id="toggle_deletion_button")
        
        async def callback(self, interaction: discord.Interaction):
            await self.view.cog._toggle_thread_deletion_logic(interaction.user, interaction.guild.id, interaction.response.send_message)

    class ToggleConfirmationMessageButton(ui.Button):
        def __init__(self):
            super().__init__(label="Toggle Confirmation Msg", style=ButtonStyle.secondary, custom_id="toggle_confirmation_button")
        
        async def callback(self, interaction: discord.Interaction):
            await self.view.cog._toggle_confirmation_message_logic(interaction.user, interaction.guild.id, interaction.response.send_message)

    class ManualCleanupButton(ui.Button):
        def __init__(self):
            super().__init__(label="Cleanup Now", style=ButtonStyle.secondary, custom_id="cleanup_now_button")
        
        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            await self.view.cog._manual_cleanup_logic(interaction.user, interaction.guild.id, interaction.followup.send, is_interaction=True)

class AddChannelModal(ui.Modal, title="Add Auction Channel"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.channel_input = ui.TextInput(
            label="Channel ID or Mention",
            placeholder="e.g. #auctions or 123456789012345678",
            min_length=1,
            max_length=200,
        )
        self.add_item(self.channel_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel_id_or_mention = self.channel_input.value
        try:
            channel_id = int(''.join(filter(str.isdigit, channel_id_or_mention)))
            channel = interaction.guild.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                await interaction.followup.send("❌ Invalid channel provided. Please provide a valid text channel ID or mention.", ephemeral=True)
                return
            await self.cog._add_auction_channel_logic(interaction.user, channel, interaction.followup.send)
        except (ValueError, TypeError):
            await interaction.followup.send("❌ Invalid channel ID format. Please provide a valid text channel ID or mention.", ephemeral=True)

class RemoveChannelModal(ui.Modal, title="Remove Auction Channel"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.channel_input = ui.TextInput(
            label="Channel ID or Mention",
            placeholder="e.g. #auctions or 123456789012345678",
            min_length=1,
            max_length=200,
        )
        self.add_item(self.channel_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel_id_or_mention = self.channel_input.value
        try:
            channel_id = int(''.join(filter(str.isdigit, channel_id_or_mention)))
            channel = interaction.guild.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                await interaction.followup.send("❌ Invalid channel provided. Please provide a valid text channel ID or mention.", ephemeral=True)
                return
            await self.cog._remove_auction_channel_logic(interaction.user, channel, interaction.followup.send)
        except (ValueError, TypeError):
            await interaction.followup.send("❌ Invalid channel ID format. Please provide a valid text channel ID or mention.", ephemeral=True)

class AuctionSystem(commands.Cog):
    """
    Discord Auction System for Sorare trading cards.

    Features:
    - Monitors designated auction channels for new posts
    - Creates a public thread for each new auction
    - Sets 10-day auto-deletion timers for the auction post and each reply
    - Automatically cleans up old auction listings, replies, and optionally their threads
    - Stores all data (configs, timestamps, auction info) per guild in /data/zauction/{guild_id}/
    - Continues checking for expired auctions even after bot restarts.
    """

    def __init__(self, bot):
        self.bot = bot

        self.guild_configs: Dict[int, Dict] = {}

        self.db_lock = threading.Lock()
        self.bot.add_view(AuctionPanelView(self.bot, self))


        os.makedirs(BASE_DATA_DIR, exist_ok=True)


        self.cleanup_task.start()

    def get_guild_data_dir(self, guild_id: int) -> str:
        
        path = os.path.join(BASE_DATA_DIR, str(guild_id))
        os.makedirs(path, exist_ok=True)
        return path

    def get_guild_config_path(self, guild_id: int) -> str:
        
        return os.path.join(self.get_guild_data_dir(guild_id), "config.json")

    def get_guild_db_path(self, guild_id: int) -> str:
        
        return os.path.join(self.get_guild_data_dir(guild_id), "auction_system.db")

    def _ensure_guild_data(self, guild_id: int):
        """
        Ensures the guild's data directory, config, and database are initialized.
        This method is called before any operation requiring guild-specific data.
        """
        if guild_id not in self.guild_configs:

            self.guild_configs[guild_id] = {'auction_channels': set(), 'send_confirmation': True}

            self._load_guild_config(guild_id)

            self._init_guild_database(guild_id)
            logger.info(f"Initialized data structures for guild {guild_id}")

    def _load_guild_config(self, guild_id: int):
        
        config_path = self.get_guild_config_path(guild_id)
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)

                    self.guild_configs[guild_id]['auction_channels'] = set(config.get('auction_channels', []))
                    self.guild_configs[guild_id]['send_confirmation'] = config.get('send_confirmation', True)
                    logger.info(f"Loaded config for guild {guild_id}: {len(self.guild_configs[guild_id]['auction_channels'])} channels, send_confirmation={self.guild_configs[guild_id]['send_confirmation']}")
        except Exception as e:
            logger.error(f"Error loading auction config for guild {guild_id}: {e}")

            self.guild_configs[guild_id]['auction_channels'] = set()
            self.guild_configs[guild_id]['send_confirmation'] = True

    def _save_guild_config(self, guild_id: int):
        
        config_path = self.get_guild_config_path(guild_id)
        try:
            config = {
                'auction_channels': list(self.guild_configs[guild_id]['auction_channels']),
                'send_confirmation': self.guild_configs[guild_id]['send_confirmation']
            }
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Saved auction config for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error saving auction config for guild {guild_id}: {e}")

    def _init_guild_database(self, guild_id: int):
        
        db_path = self.get_guild_db_path(guild_id)
        try:
            with self.db_lock: 
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()

                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS auction_messages (
                            message_id INTEGER PRIMARY KEY,
                            channel_id INTEGER NOT NULL,
                            guild_id INTEGER NOT NULL,
                            author_id INTEGER NOT NULL,
                            thread_id INTEGER NOT NULL,
                            anchor_message_id INTEGER NOT NULL,
                            created_at TIMESTAMP NOT NULL,
                            deletion_time TIMESTAMP NOT NULL,
                            is_deleted INTEGER DEFAULT 0,
                            delete_thread_on_expire INTEGER DEFAULT 1
                        )
                    ''')



                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS auction_replies (
                            reply_id INTEGER PRIMARY KEY,
                            auction_message_id INTEGER NOT NULL,
                            thread_id INTEGER NOT NULL,
                            author_id INTEGER NOT NULL,
                            deletion_time TIMESTAMP NOT NULL,
                            is_deleted INTEGER DEFAULT 0,
                            reaction_added INTEGER DEFAULT 0,
                            FOREIGN KEY (auction_message_id) REFERENCES auction_messages (message_id)
                        )
                    ''')

                    conn.commit()
                    logger.info(f"Auction database initialized successfully for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error initializing auction database for guild {guild_id}: {e}")



    def _add_auction_message_sync(self, message: discord.Message, thread_id: int, anchor_message_id: int):
        
        guild_id = message.guild.id
        self._ensure_guild_data(guild_id)
        db_path = self.get_guild_db_path(guild_id)
        try:
            deletion_time = datetime.now() + timedelta(days=10)
            with self.db_lock:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT OR REPLACE INTO auction_messages
                        (message_id, channel_id, guild_id, author_id, thread_id, anchor_message_id, created_at, deletion_time, delete_thread_on_expire)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        message.id,
                        message.channel.id,
                        guild_id,
                        message.author.id,
                        thread_id,
                        anchor_message_id,
                        datetime.now().isoformat(),
                        deletion_time.isoformat(),
                        1 
                    ))
                    conn.commit()
            logger.info(f"Added auction message {message.id} with thread {thread_id} and anchor {anchor_message_id} for guild {guild_id}. Deletion on {deletion_time}")
            return True
        except Exception as e:
            logger.error(f"Error adding auction message to database for guild {guild_id}: {e}")
            return False

    def _add_auction_reply_sync(self, reply: discord.Message, auction_message_id: int, thread_id: int):
        
        guild_id = reply.guild.id
        self._ensure_guild_data(guild_id)
        db_path = self.get_guild_db_path(guild_id)
        try:
            deletion_time = datetime.now() + timedelta(days=10)
            with self.db_lock:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT OR REPLACE INTO auction_replies
                        (reply_id, auction_message_id, thread_id, author_id, deletion_time, reaction_added)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        reply.id,
                        auction_message_id,
                        thread_id,
                        reply.author.id,
                        deletion_time.isoformat(),
                        0 
                    ))
                    conn.commit()
            logger.debug(f"Added reply {reply.id} to auction {auction_message_id} for guild {guild_id}. Deletion on {deletion_time}")
            return True
        except Exception as e:
            logger.error(f"Error adding auction reply to database for guild {guild_id}: {e}")
            return False

    def _mark_reply_reaction_added_sync(self, reply_id: int):
        

        guild_id = self._get_guild_id_from_reply_sync(reply_id)
        if not guild_id:
            logger.warning(f"Could not find guild for reply {reply_id} to mark reaction.")
            return False

        self._ensure_guild_data(guild_id)
        db_path = self.get_guild_db_path(guild_id)
        try:
            with self.db_lock:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE auction_replies
                        SET reaction_added = 1
                        WHERE reply_id = ?
                    ''', (reply_id,))
                    conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error marking reply {reply_id} as reacted: {e}")
            return False
            
    def _is_reply_reaction_added_sync(self, reply_id: int) -> bool:
        

        guild_id = self._get_guild_id_from_reply_sync(reply_id)
        if not guild_id:
            return False

        self._ensure_guild_data(guild_id)
        db_path = self.get_guild_db_path(guild_id)
        try:
            with self.db_lock:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT reaction_added FROM auction_replies
                        WHERE reply_id = ?
                    ''', (reply_id,))
                    result = cursor.fetchone()
                    if result:
                        return bool(result[0])
            return False
        except Exception as e:
            logger.error(f"Error checking reaction status for reply {reply_id}: {e}")
            return False

    def _get_pending_deletions_sync(self, guild_id: int) -> List[Dict]:
        
        self._ensure_guild_data(guild_id)
        db_path = self.get_guild_db_path(guild_id)
        try:
            with self.db_lock:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT message_id, channel_id, guild_id, thread_id, anchor_message_id, delete_thread_on_expire, deletion_time
                        FROM auction_messages
                        WHERE deletion_time <= ? AND is_deleted = 0 AND guild_id = ?
                    ''', (datetime.now().isoformat(), guild_id))
                    results = cursor.fetchall()
                    return [
                        {
                            'message_id': row[0],
                            'channel_id': row[1],
                            'guild_id': row[2],
                            'thread_id': row[3],
                            'anchor_message_id': row[4],
                            'delete_thread': row[5],
                            'deletion_time': datetime.fromisoformat(row[6])
                        }
                        for row in results
                    ]
        except Exception as e:
            logger.error(f"Error getting pending auction message deletions for guild {guild_id}: {e}")
            return []

    def _get_pending_reply_deletions_sync(self, guild_id: int) -> List[Dict]:
        
        self._ensure_guild_data(guild_id)
        db_path = self.get_guild_db_path(guild_id)
        try:
            with self.db_lock:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT ar.reply_id, ar.thread_id, am.guild_id
                        FROM auction_replies ar
                        JOIN auction_messages am ON ar.auction_message_id = am.message_id
                        WHERE ar.deletion_time <= ? AND ar.is_deleted = 0
                    ''', (datetime.now().isoformat(),))
                    results = cursor.fetchall()
                    return [
                        {
                            'reply_id': row[0],
                            'thread_id': row[1],
                            'guild_id': row[2]
                        }
                        for row in results
                    ]
        except Exception as e:
            logger.error(f"Error getting pending reply deletions for guild {guild_id}: {e}")
            return []


    def _mark_as_deleted_sync(self, guild_id: int, message_id: int):
        
        self._ensure_guild_data(guild_id)
        db_path = self.get_guild_db_path(guild_id)
        try:
            with self.db_lock:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE auction_messages
                        SET is_deleted = 1
                        WHERE message_id = ? AND guild_id = ?
                    ''', (message_id, guild_id))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error marking message {message_id} as deleted for guild {guild_id}: {e}")

    def _mark_reply_as_deleted_sync(self, reply_id: int):
        
        guild_id = self._get_guild_id_from_reply_sync(reply_id)
        if not guild_id:
            logger.warning(f"Could not find guild for reply {reply_id} to mark as deleted.")
            return

        db_path = self.get_guild_db_path(guild_id)
        try:
            with self.db_lock:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE auction_replies
                        SET is_deleted = 1
                        WHERE reply_id = ?
                    ''', (reply_id,))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error marking reply {reply_id} as deleted: {e}")

    def _get_guild_id_from_reply_sync(self, reply_id: int) -> Optional[int]:
        
        for item in os.listdir(BASE_DATA_DIR):
            item_path = os.path.join(BASE_DATA_DIR, item)
            if os.path.isdir(item_path) and item.isdigit():
                guild_id = int(item)
                db_path = os.path.join(item_path, "auction_system.db")
                try:
                    with self.db_lock:
                        with sqlite3.connect(db_path) as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                SELECT am.guild_id FROM auction_replies ar
                                JOIN auction_messages am ON ar.auction_message_id = am.message_id
                                WHERE ar.reply_id = ?
                            ''', (reply_id,))
                            result = cursor.fetchone()
                            if result:
                                return result[0]
                except Exception as e:
                    logger.error(f"Error finding guild for reply {reply_id} in db {db_path}: {e}")
        return None

    def _get_auction_message_from_thread_sync(self, thread_id: int) -> Optional[int]:
        
        for item in os.listdir(BASE_DATA_DIR):
            item_path = os.path.join(BASE_DATA_DIR, item)
            if os.path.isdir(item_path) and item.isdigit():
                db_path = os.path.join(item_path, "auction_system.db")
                try:
                    with self.db_lock:
                        with sqlite3.connect(db_path) as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                SELECT message_id FROM auction_messages
                                WHERE thread_id = ? AND is_deleted = 0
                            ''', (thread_id,))
                            result = cursor.fetchone()
                            if result:
                                return result[0]
                except Exception as e:
                    logger.error(f"Error finding auction message for thread {thread_id} in db {db_path}: {e}")
        return None

    def _get_auction_message_from_anchor_sync(self, anchor_id: int) -> Optional[int]:
        
        for item in os.listdir(BASE_DATA_DIR):
            item_path = os.path.join(BASE_DATA_DIR, item)
            if os.path.isdir(item_path) and item.isdigit():
                db_path = os.path.join(item_path, "auction_system.db")
                try:
                    with self.db_lock:
                        with sqlite3.connect(db_path) as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                SELECT message_id FROM auction_messages
                                WHERE anchor_message_id = ? AND is_deleted = 0
                            ''', (anchor_id,))
                            result = cursor.fetchone()
                            if result:
                                return result[0]
                except Exception as e:
                    logger.error(f"Error finding auction message for anchor {anchor_id} in db {db_path}: {e}")
        return None
        
    def _is_auction_thread_sync(self, thread_id: int) -> bool:
        
        return self._get_auction_message_from_thread_sync(thread_id) is not None

    def _get_time_remaining_sync(self, guild_id: int, message_id: int) -> str:
        
        self._ensure_guild_data(guild_id)
        db_path = self.get_guild_db_path(guild_id)
        try:
            with self.db_lock:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT deletion_time FROM auction_messages
                        WHERE message_id = ? AND guild_id = ?
                    ''', (message_id, guild_id))
                    result = cursor.fetchone()
                    if result:
                        deletion_time = datetime.fromisoformat(result[0])
                        remaining = deletion_time - datetime.now()
                        if remaining.total_seconds() <= 0:
                            return "Expired"
                        days = remaining.days
                        hours = remaining.seconds // 3600
                        minutes = (remaining.seconds % 3600) // 60
                        if days > 0:
                            return f"{days}d {hours}h"
                        elif hours > 0:
                            return f"{hours}h {minutes}m"
                        else:
                            return f"{minutes}m"
                    return "Unknown"
        except Exception as e:
            logger.error(f"Error getting time remaining for guild {guild_id}: {e}")
            return "Unknown"

    def _get_toggle_state_sync(self, guild_id: int) -> bool:
        
        self._ensure_guild_data(guild_id)
        db_path = self.get_guild_db_path(guild_id)
        try:
            with self.db_lock:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT delete_thread_on_expire FROM auction_messages
                        WHERE guild_id = ? AND is_deleted = 0
                        LIMIT 1
                    ''', (guild_id,))
                    result = cursor.fetchone()
                    if result:
                        return bool(result[0])

                    return True
        except Exception as e:
            logger.error(f"Error getting toggle state for guild {guild_id}: {e}")
            return True

    def _set_toggle_state_sync(self, guild_id: int, state: bool) -> bool:
        
        self._ensure_guild_data(guild_id)
        db_path = self.get_guild_db_path(guild_id)
        try:
            with self.db_lock:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE auction_messages
                        SET delete_thread_on_expire = ?
                        WHERE guild_id = ?
                    ''', (int(state), guild_id))
                    conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error setting toggle state for guild {guild_id}: {e}")
            return False



    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        
        logger.info(f"Joined new guild: {guild.name} ({guild.id}). Initializing data.")
        self._ensure_guild_data(guild.id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        

        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        self._ensure_guild_data(guild_id)


        if message.channel.id in self.guild_configs[guild_id]['auction_channels']:

            if not message.is_system(): 
                try:
                    logger.info(f"Received a new auction message from {message.author.name}. Creating a new thread.")
                    thread_name = f"ClICK HERE TO OPEN AUCTION | {message.author.display_name}'s Auction"
                    thread = await message.create_thread(name=thread_name)
                    

                    if self.guild_configs[guild_id]['send_confirmation']:
                        info_embed = self.get_auction_confirmation_embed(message)
                        await thread.send(embed=info_embed)


                    anchor_embed = discord.Embed(
                        title="💬 Place Your Bids Here!",
                        description=f"Reply to this message with your offers and comments. The auction post and this thread will be automatically cleaned up after 10 days.",
                        color=discord.Color.blue()
                    )
                    anchor_message = await thread.send(embed=anchor_embed)
                    

                    if await asyncio.to_thread(self._add_auction_message_sync, message, thread.id, anchor_message.id):
                        logger.info(f"Successfully added auction message {message.id} to DB with anchor {anchor_message.id}.")
                    else:
                        logger.error(f"Failed to add new auction message {message.id} to the database. Deleting the created thread.")
                        await thread.delete()

                except Exception as e:
                    logger.error(f"Error creating thread for message {message.id} in guild {guild_id}: {e}")

        elif isinstance(message.channel, discord.Thread):

            if message.reference and message.reference.message_id:
                auction_message_id = await asyncio.to_thread(self._get_auction_message_from_anchor_sync, message.reference.message_id)
                if auction_message_id:

                    success = await asyncio.to_thread(self._add_auction_reply_sync, message, auction_message_id, message.channel.id)
                    if success:
                        logger.debug(f"Added reply {message.id} to auction {auction_message_id} in thread {message.channel.id}.")

                        try:
                            await message.add_reaction("⏰")
                            await asyncio.to_thread(self._mark_reply_reaction_added_sync, message.id)
                        except Exception as e:
                            logger.error(f"Failed to add reaction to message {message.id}: {e}")
        

        if message.embeds:
            try:

                await message.edit(suppress=True)
                logger.info(f"Suppressed embeds for message {message.id} in channel {message.channel.id}.")
            except discord.Forbidden:
                logger.warning(f"Missing permissions to suppress embeds for message {message.id}. Bot needs 'manage_messages'.")
            except Exception as e:
                logger.error(f"Error suppressing embeds for message {message.id}: {e}")



    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):

        message_id = payload.message_id
        guild_id = payload.guild_id

        if not guild_id:
            return

        self._ensure_guild_data(guild_id)
        db_path = self.get_guild_db_path(guild_id)
        
        try:
            with self.db_lock:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT thread_id FROM auction_messages
                        WHERE message_id = ? AND guild_id = ? AND is_deleted = 0
                    ''', (message_id, guild_id))
                    result = cursor.fetchone()

            if result:
                thread_id = result[0]
                thread = self.bot.get_channel(thread_id)
                if thread and isinstance(thread, discord.Thread):
                    await thread.delete()
                    logger.info(f"Main auction message {message_id} was deleted, so its thread {thread_id} was also deleted.")
                

                await asyncio.to_thread(self._mark_as_deleted_sync, guild_id, message_id)

        except Exception as e:
            logger.error(f"Error handling on_raw_message_delete for message {message_id} in guild {guild_id}: {e}")
    
    def get_auction_confirmation_embed(self, original_message: discord.Message) -> discord.Embed:
        
        embed = discord.Embed(
            title="🏛️ Auction Tracking Started",
            description=f"This thread is for comments and bids on [this auction post]({original_message.jump_url}).",
            color=discord.Color.green(),
            timestamp=original_message.created_at
        )
        embed.add_field(
            name="⏰ Deletion Info",
            value="• The auction post and all replies in this thread will be automatically deleted in **10 days**.\n"
                    "• Each message has its own 10-day countdown from when it was sent.",
            inline=False
        )
        embed.set_footer(text="ZygnalBot Auction System")
        return embed

    @tasks.loop(minutes=30)
    async def cleanup_task(self):
        """
        Periodic task to clean up expired auctions and individual replies across all guilds.
        """
        logger.info("Starting cleanup task...")
        guild_ids_to_check = []
        for item in os.listdir(BASE_DATA_DIR):
            item_path = os.path.join(BASE_DATA_DIR, item)
            if os.path.isdir(item_path) and item.isdigit():
                guild_ids_to_check.append(int(item))

        if not guild_ids_to_check:
            logger.debug("No guild data directories found to clean up.")
            return

        for guild_id in guild_ids_to_check:
            self._ensure_guild_data(guild_id)


            pending_reply_deletions = await asyncio.to_thread(self._get_pending_reply_deletions_sync, guild_id)
            if pending_reply_deletions:
                logger.info(f"Processing {len(pending_reply_deletions)} pending reply deletions for guild {guild_id}")
                for reply in pending_reply_deletions:
                    try:
                        thread = self.bot.get_channel(reply['thread_id'])
                        if thread:
                            reply_message = await thread.fetch_message(reply['reply_id'])
                            await reply_message.delete()
                            await asyncio.to_thread(self._mark_reply_as_deleted_sync, reply['reply_id'])
                        else:
                            await asyncio.to_thread(self._mark_reply_as_deleted_sync, reply['reply_id'])
                    except discord.NotFound:
                        await asyncio.to_thread(self._mark_reply_as_deleted_sync, reply['reply_id'])
                    except Exception as e:
                        logger.error(f"Error deleting reply {reply['reply_id']} in thread {reply['thread_id']}: {e}")
                    await asyncio.sleep(0.5)


            pending_auction_deletions = await asyncio.to_thread(self._get_pending_deletions_sync, guild_id)
            if pending_auction_deletions:
                logger.info(f"Processing {len(pending_auction_deletions)} pending auction post deletions for guild {guild_id}")
                for auction in pending_auction_deletions:
                    try:
                        guild = self.bot.get_guild(auction['guild_id'])
                        if not guild:
                            await asyncio.to_thread(self._mark_as_deleted_sync, auction['guild_id'], auction['message_id'])
                            continue


                        if auction['delete_thread']:
                            try:
                                thread = guild.get_channel(auction['thread_id'])
                                if thread:
                                    await thread.delete()
                                    logger.info(f"Successfully deleted expired auction thread {auction['thread_id']} in guild {guild_id}")
                                else:
                                    logger.warning(f"Thread {auction['thread_id']} not found for auction {auction['message_id']} during cleanup.")
                            except Exception as e:
                                logger.error(f"Error deleting thread {auction['thread_id']} for auction {auction['message_id']} in guild {guild_id}: {e}")
                        

                        try:
                            main_channel = guild.get_channel(auction['channel_id'])
                            if main_channel:
                                auction_message = await main_channel.fetch_message(auction['message_id'])
                                await auction_message.delete()
                                await asyncio.to_thread(self._mark_as_deleted_sync, guild_id, auction['message_id'])
                                logger.info(f"Successfully deleted expired auction message {auction['message_id']} in guild {guild_id}")
                            else:
                                await asyncio.to_thread(self._mark_as_deleted_sync, guild_id, auction['message_id'])

                        except discord.NotFound:
                            await asyncio.to_thread(self._mark_as_deleted_sync, guild_id, auction['message_id'])
                            logger.info(f"Auction message {auction['message_id']} was already deleted in guild {guild_id}")

                        except Exception as e:
                            logger.error(f"Error deleting auction message {auction['message_id']} in guild {guild_id}: {e}")

                    except Exception as e:
                        logger.error(f"Error processing auction deletion {auction['message_id']} for guild {guild_id}: {e}")

                    await asyncio.sleep(1)
        logger.info("Cleanup task completed.")

    @cleanup_task.before_loop
    async def before_cleanup_task(self):
        """
        Waits for the bot to be ready.
        """
        await self.bot.wait_until_ready()
        logger.info("Bot ready, cleanup task is now active.")

    async def _add_auction_channel_logic(self, user: discord.User, channel: discord.TextChannel, respond_func):
        
        if not channel.guild:
            await respond_func("❌ This command can only be used in a server channel.")
            return

        guild_id = channel.guild.id
        self._ensure_guild_data(guild_id)

        if not user.guild_permissions.administrator:
            await respond_func("❌ You need administrator permissions to configure auction channels.")
            return

        if channel.id in self.guild_configs[guild_id]['auction_channels']:
            await respond_func(f"✅ {channel.mention} is already being monitored for auctions.", ephemeral=True)
            return

        self.guild_configs[guild_id]['auction_channels'].add(channel.id)
        self._save_guild_config(guild_id)

        embed = discord.Embed(
            title="✅ Auction Channel Added",
            description=f"Now monitoring {channel.mention} for auction posts",
            color=discord.Color.green()
        )

        embed.add_field(
            name="📋 What happens now?",
            value="• New messages will create an auction post with a dedicated thread for replies\n"
                  "• Each message (post and replies) gets a 10-day auto-deletion timer",
            inline=False
        )

        await respond_func(embed=embed, ephemeral=True)

    async def _remove_auction_channel_logic(self, user: discord.User, channel: discord.TextChannel, respond_func):
        
        if not channel.guild:
            await respond_func("❌ This command can only be used in a server channel.")
            return

        guild_id = channel.guild.id
        self._ensure_guild_data(guild_id)

        if not user.guild_permissions.administrator:
            await respond_func("❌ You need administrator permissions to configure auction channels.")
            return

        if channel.id not in self.guild_configs[guild_id]['auction_channels']:
            await respond_func(f"❌ {channel.mention} is not currently being monitored.", ephemeral=True)
            return

        self.guild_configs[guild_id]['auction_channels'].remove(channel.id)
        self._save_guild_config(guild_id)

        embed = discord.Embed(
            title="✅ Auction Channel Removed",
            description=f"No longer monitoring {channel.mention} for auction posts",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="📋 Note",
            value="Existing auctions and their threads in this channel will still be deleted when their timers expire.",
            inline=False
        )

        await respond_func(embed=embed, ephemeral=True)

    async def _toggle_thread_deletion_logic(self, user: discord.User, guild_id: int, respond_func):
        
        self._ensure_guild_data(guild_id)

        if not user.guild_permissions.administrator:
            await respond_func("❌ You need administrator permissions to toggle this setting.", ephemeral=True)
            return

        current_state = await asyncio.to_thread(self._get_toggle_state_sync, guild_id)
        new_state = not current_state
        success = await asyncio.to_thread(self._set_toggle_state_sync, guild_id, new_state)

        if success:
            state_text = "enabled" if new_state else "disabled"
            embed = discord.Embed(
                title="✅ Thread Deletion Toggle Updated",
                description=f"Automatic deletion of entire threads when an auction expires is now **{state_text}**.",
                color=discord.Color.green() if new_state else discord.Color.red()
            )
            if not new_state:
                embed.add_field(
                    name="⚠️ Important",
                    value="When an auction post expires, only the post will be deleted. The thread will remain.",
                    inline=False
                )
            await respond_func(embed=embed, ephemeral=True)
        else:
            await respond_func("❌ An error occurred while updating the toggle state.", ephemeral=True)

    async def _toggle_confirmation_message_logic(self, user: discord.User, guild_id: int, respond_func):
        
        self._ensure_guild_data(guild_id)

        if not user.guild_permissions.administrator:
            await respond_func("❌ You need administrator permissions to toggle this setting.", ephemeral=True)
            return

        current_state = self.guild_configs[guild_id]['send_confirmation']
        new_state = not current_state
        self.guild_configs[guild_id]['send_confirmation'] = new_state
        self._save_guild_config(guild_id)

        state_text = "enabled" if new_state else "disabled"
        color = discord.Color.green() if new_state else discord.Color.red()

        embed = discord.Embed(
            title="✅ Confirmation Message Toggle Updated",
            description=f"The 'Auction Tracking Started' confirmation message is now **{state_text}**.",
            color=color
        )
        if not new_state:
            embed.add_field(
                name="⚠️ Note",
                value="New auction threads will no longer have the initial confirmation embed sent. The 'Place Your Bids Here' anchor message will still be sent.",
                inline=False
            )
        await respond_func(embed=embed, ephemeral=True)


    async def _auction_status_logic(self, guild_id: int, respond_func, ephemeral: bool = False):
        
        self._ensure_guild_data(guild_id)
        db_path = self.get_guild_db_path(guild_id)
        try:
            with self.db_lock:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT COUNT(*) FROM auction_messages
                        WHERE is_deleted = 0 AND guild_id = ?
                    ''', (guild_id,))
                    active_auctions = cursor.fetchone()[0]
                    
                    cursor.execute('''
                        SELECT COUNT(*) FROM auction_replies
                        WHERE is_deleted = 0 AND thread_id IN (SELECT thread_id FROM auction_messages WHERE guild_id = ?)
                    ''', (guild_id,))
                    active_replies = cursor.fetchone()[0]

            thread_deletion_state = await asyncio.to_thread(self._get_toggle_state_sync, guild_id)
            thread_deletion_status = "Enabled (threads will be deleted)" if thread_deletion_state else "Disabled (threads will remain)"

            confirmation_state = self.guild_configs[guild_id]['send_confirmation']
            confirmation_status = "Enabled" if confirmation_state else "Disabled"


            embed = discord.Embed(
                title="🏛️ Auction System Status",
                color=discord.Color.blue()
            )

            channel_mentions = []
            for channel_id in self.guild_configs[guild_id]['auction_channels']:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    channel_mentions.append(channel.mention)
                else:
                    channel_mentions.append(f"<#{channel_id}> (Not found)")

            embed.add_field(
                name="📍 Monitored Channels",
                value="\n".join(channel_mentions) if channel_mentions else "None configured",
                inline=False
            )

            embed.add_field(
                name="📊 Statistics",
                value=f"**Active Auctions:** {active_auctions}\n"
                      f"**Active Replies:** {active_replies}",
                inline=False
            )

            embed.add_field(
                name="⚙️ System Info",
                value=f"**Cleanup Task:** {'Running' if not self.cleanup_task.is_being_cancelled() else 'Stopped'}\n"
                      f"**Thread Deletion:** {thread_deletion_status}\n"
                      f"**Confirmation Message:** {confirmation_status}",
                inline=False
            )

            if ephemeral:
                await respond_func(embed=embed, ephemeral=True)
            else:
                await respond_func(embed=embed)

        except Exception as e:
            logger.error(f"Error retrieving auction status for guild {guild_id}: {e}")
            if ephemeral:
                await respond_func("❌ Error retrieving auction status.", ephemeral=True)
            else:
                await respond_func("❌ Error retrieving auction status.")

    async def _manual_cleanup_logic(self, user: discord.User, guild_id: int, respond_func, is_interaction: bool = False):
        
        self._ensure_guild_data(guild_id)

        if not user.guild_permissions.administrator:
            await respond_func("❌ You need administrator permissions to trigger manual cleanup.")
            return

        if is_interaction:
            pass

        try:

            pending_reply_deletions = await asyncio.to_thread(self._get_pending_reply_deletions_sync, guild_id)
            deleted_replies_count = 0
            for reply in pending_reply_deletions:
                try:
                    thread = self.bot.get_channel(reply['thread_id'])
                    if thread:
                        reply_message = await thread.fetch_message(reply['reply_id'])
                        await reply_message.delete()
                        await asyncio.to_thread(self._mark_reply_as_deleted_sync, reply['reply_id'])
                        deleted_replies_count += 1
                except discord.NotFound:
                    await asyncio.to_thread(self._mark_reply_as_deleted_sync, reply['reply_id'])
                except Exception as e:
                    logger.error(f"Error deleting reply {reply['reply_id']} during manual cleanup: {e}")
                await asyncio.sleep(0.5)


            pending_auction_deletions = await asyncio.to_thread(self._get_pending_deletions_sync, guild_id)
            deleted_auctions_count = 0
            for auction in pending_auction_deletions:
                try:
                    guild = self.bot.get_guild(auction['guild_id'])
                    if not guild:
                        await asyncio.to_thread(self._mark_as_deleted_sync, auction['guild_id'], auction['message_id'])
                        continue

                    if auction['delete_thread']:
                        try:
                            thread = guild.get_channel(auction['thread_id'])
                            if thread:
                                await thread.delete()
                        except discord.NotFound:
                            pass
                        except Exception as e:
                            logger.error(f"Error deleting thread {auction['thread_id']} during manual cleanup: {e}")

                    try:
                        main_channel = guild.get_channel(auction['channel_id'])
                        if main_channel:
                            auction_message = await main_channel.fetch_message(auction['message_id'])
                            await auction_message.delete()
                            await asyncio.to_thread(self._mark_as_deleted_sync, guild_id, auction['message_id'])
                            deleted_auctions_count += 1
                    except discord.NotFound:
                        await asyncio.to_thread(self._mark_as_deleted_sync, guild_id, auction['message_id'])
                    except Exception as e:
                        logger.error(f"Error deleting auction message {auction['message_id']} in guild {guild_id} during manual cleanup: {e}")

                except Exception as e:
                    logger.error(f"Error processing single auction deletion {auction['message_id']} during manual cleanup: {e}")
                await asyncio.sleep(1)

            embed = discord.Embed(
                title="✅ Manual Cleanup Completed",
                description=f"Processed {deleted_auctions_count} expired auctions and {deleted_replies_count} expired replies for this guild.",
                color=discord.Color.green()
            )

            await respond_func(embed=embed)

        except Exception as e:
            logger.error(f"Error in manual cleanup for guild {guild_id}: {e}")
            await respond_func("❌ Error during manual cleanup.")

    @app_commands.command(name="zauction", description="Open the ZygnalBot Auction System control panel.")
    async def zauction_panel_slash(self, interaction: discord.Interaction):
        
        await interaction.response.send_message(
            "Welcome to the ZygnalBot Auction System control panel. Use the buttons below to manage auction settings.",
            view=AuctionPanelView(self.bot, self),
            ephemeral=True
        )

    @commands.command(name="zauction", help="Open the ZygnalBot Auction System control panel.")
    async def zauction_panel_prefix(self, ctx: commands.Context):
        
        await ctx.send(
            "Welcome to the ZygnalBot Auction System control panel. Use the buttons below to manage auction settings.",
            view=AuctionPanelView(self.bot, self)
        )

async def setup(bot):
    
    await bot.add_cog(AuctionSystem(bot))
    logger.info("Auction System extension loaded successfully")

async def teardown(bot):
    """
    Cleanup function to handle a graceful shutdown.
    It cancels the cleanup task and waits for it to complete.
    """
    cog = bot.get_cog("AuctionSystem")
    if cog and hasattr(cog, 'cleanup_task') and cog.cleanup_task.is_running():
        cog.cleanup_task.cancel()
        try:

            await asyncio.wait_for(cog.cleanup_task, timeout=5.0)
        except asyncio.CancelledError:

            pass
        except asyncio.TimeoutError:
            logger.warning("Timed out while waiting for cleanup task to cancel.")
        except Exception as e:
            logger.error(f"Error during teardown cleanup: {e}")

    logger.info("Auction System extension unloaded gracefully.")