import discord
from discord.ext import commands
import json
import logging
import asyncio
import os
import datetime
from typing import Dict, List, Any, Optional, Set

logger = logging.getLogger(__name__)

def get_prefix(ctx):
    
    prefix = ctx.prefix if hasattr(ctx, 'prefix') else getattr(ctx.bot, 'command_prefix', '?')
    if callable(prefix):
        try:
            prefix = prefix(ctx.bot, ctx.message)
        except:
            prefix = '?'
    if isinstance(prefix, (list, tuple)):
        prefix = prefix[0] if prefix else '?'
    return str(prefix)

class ZVerifySetup(commands.Cog):
    """
    Automates server setup for verification bots.
    Sets up channel permissions for verification systems where users get a role after verification.
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.setup_data_file = os.path.join("data", "ZVerifySetup", "guild_setups.json")
        self.active_setups: Dict[int, Dict[str, Any]] = {}
        self.user_prompts: Dict[int, Dict[str, Any]] = {}
        

        os.makedirs(os.path.dirname(self.setup_data_file), exist_ok=True)
        

        self.active_setups = self.load_setup_data()
        

        self.migrate_old_data()
        
        logger.info(f"ZVerifySetup loaded with {len(self.active_setups)} saved guild configurations")
    
    def load_setup_data(self) -> Dict[int, Dict[str, Any]]:
        
        try:
            if os.path.exists(self.setup_data_file):
                with open(self.setup_data_file, 'r') as f:
                    data = json.load(f)
                    

                    if "guilds" in data and "metadata" in data:
                        logger.info(f"Loading verification data (version: {data['metadata'].get('version', 'unknown')}, last saved: {data['metadata'].get('last_saved', 'unknown')})")
                        return {int(k): v for k, v in data["guilds"].items()}
                    else:

                        logger.info("Loading verification data from old format")
                        return {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.error(f"Error loading verification setup data: {e}")
        return {}
    
    def save_setup_data(self):
        
        try:

            data = {
                "metadata": {
                    "last_saved": datetime.datetime.now().isoformat(),
                    "version": "1.0"
                },
                "guilds": {str(k): v for k, v in self.active_setups.items()}
            }
            with open(self.setup_data_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved verification setup data for {len(self.active_setups)} guilds")
        except Exception as e:
            logger.error(f"Error saving verification setup data: {e}")
    
    def migrate_old_data(self):
        
        old_file = os.path.join("data", "zverify_setup.json")
        if os.path.exists(old_file) and not os.path.exists(self.setup_data_file):
            try:

                with open(old_file, 'r') as f:
                    old_data = json.load(f)

                    migrated_data = {int(k): v for k, v in old_data.items()}
                    self.active_setups.update(migrated_data)
                

                self.save_setup_data()
                

                backup_file = old_file + ".backup"
                os.rename(old_file, backup_file)
                
                logger.info(f"Successfully migrated {len(migrated_data)} guild configurations from old location")
                logger.info(f"Old data backed up to: {backup_file}")
            except Exception as e:
                logger.error(f"Error migrating old verification setup data: {e}")
    
    @commands.command(name="zverify_setup", aliases=["zvsetup", "zverifysetup"])
    @commands.has_permissions(administrator=True)
    async def zverify_setup_command(self, ctx):
        
        

        guild_id = ctx.guild.id
        if guild_id not in self.active_setups:

            self.active_setups[guild_id] = {
                "verification_channel": None,
                "public_channels": [],
                "admin_channels": [],
                "verified_role": None,
                "autorole": None,
                "uses_autorole": False,
                "write_permissions": {
                    "role": None,
                    "mode": None,
                    "channels": []
                },
                "setup_complete": False
            }
            logger.info(f"Created new setup configuration for guild {guild_id}")
        else:
            logger.info(f"Using existing setup configuration for guild {guild_id}")
        

        setup_data = self.active_setups[guild_id]
        has_existing_setup = setup_data.get("setup_complete", False)
        
        if has_existing_setup:
            embed = discord.Embed(
                title="🔐 ZVerify Server Setup (Existing Configuration Found)",
                description="Found existing verification setup for this server!\n\n"
                           "**What this does:**\n"
                           "• **EXPLICITLY** sets verified role permissions on ALL channels\n"
                           "• **REMOVES** non-admin role permissions for clean setup\n"
                           "• **@everyone ONLY sees public channels** (never verification)\n"
                           "• **PROTECTS** admin channels from public access\n"
                           "• **AUTOMATES** full permission management\n\n"
                           "**⚠️ You can modify or reapply your existing setup**",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="🔐 ZVerify Server Setup",
                description="This tool will automatically configure your server for verification bots.\n\n"
                           "**What this does:**\n"
                           "• **EXPLICITLY** sets verified role permissions on ALL channels\n"
                           "• **REMOVES** non-admin role permissions for clean setup\n"
                           "• **@everyone ONLY sees public channels** (never verification)\n"
                           "• **PROTECTS** admin channels from public access\n"
                           "• **AUTOMATES** full permission management",
                color=discord.Color.blue()
            )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        embed.add_field(
            name="📋 Setup Process",
            value="1️⃣ **Select verification channel** (where users verify)\n"
                  "2️⃣ **Choose verified role** (role given after verification)\n"
                  "3️⃣ **Select public channels** (optional - stay visible to @everyone)\n"
                  "4️⃣ **Select admin channels** (admin-only access)\n"
                  "5️⃣ **Apply permissions** to all channels automatically",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Important Notes",
            value="• This will **CLEAN and SET** permissions on ALL channels\n"
                  "• **REMOVES** existing role permissions (except admin roles)\n"
                  "• **EXPLICITLY SETS** verified role and autorole permissions\n"
                  "• This works with external verification bots\n"
                  "• Only administrators can use this command\n"
                  "• **All other channels** become **verified member only**",
            inline=False
        )
        
        view = ZVerifySetupView(self, guild_id)
        await ctx.send(embed=embed, view=view)
    
    async def apply_verification_permissions(self, guild: discord.Guild, setup_data: Dict[str, Any]) -> Dict[str, Any]:
        
        results = {
            "success": 0,
            "failed": 0,
            "errors": [],
            "channels_modified": []
        }
        
        verification_channel_id = setup_data["verification_channel"]
        public_channel_ids = set(setup_data["public_channels"])
        admin_channel_ids = set(setup_data["admin_channels"])
        verified_role_id = setup_data["verified_role"]
        

        verified_role = guild.get_role(verified_role_id)
        if not verified_role:
            results["errors"].append(f"Verified role not found: {verified_role_id}")
            return results
        

        everyone_role = guild.default_role
        autorole = None
        if setup_data.get("uses_autorole") and setup_data.get("autorole"):
            autorole = guild.get_role(setup_data["autorole"])
        

        write_perms = setup_data.get("write_permissions", {})
        write_role = None
        if write_perms.get("role"):
            write_role = guild.get_role(write_perms["role"])
        write_mode = write_perms.get("mode")
        write_channels = set(write_perms.get("channels", []))
        

        admin_roles = set()
        for role in guild.roles:
            if role.permissions.administrator or role.permissions.manage_channels or role.permissions.manage_guild:
                admin_roles.add(role)
        
        logger.info(f"Starting verification setup for guild {guild.name} ({guild.id})")
        logger.info(f"Admin roles identified: {[r.name for r in admin_roles]}")
        logger.info(f"Verified role: {verified_role.name}, Autorole: {autorole.name if autorole else 'None'}")
        logger.info(f"Verification channel: {verification_channel_id}")
        logger.info(f"Public channels: {list(public_channel_ids)}")
        logger.info(f"Admin channels: {list(admin_channel_ids)}")
        logger.info(f"Write permissions role: {write_role.name if write_role else 'None'}, mode: {write_mode}")
        

        for channel in guild.channels:
            try:
                channel_id = channel.id
                channel_name = getattr(channel, 'name', f'Unknown-{channel_id}')
                

                existing_overwrites = channel.overwrites.copy()
                for target, overwrite in existing_overwrites.items():
                    if isinstance(target, discord.Role):

                        if target not in admin_roles and target != everyone_role and target != verified_role and target != autorole:
                            await channel.set_permissions(target, overwrite=None)
                

                if channel_id == verification_channel_id:

                    logger.info(f"Processing VERIFICATION channel: #{channel_name}")

                    await channel.set_permissions(everyone_role, read_messages=False, send_messages=False)
                    await channel.set_permissions(verified_role, read_messages=False, send_messages=False)
                    
                    if autorole:

                        await channel.set_permissions(autorole, read_messages=True, send_messages=False)
                        results["channels_modified"].append(f"✅ Verification: #{channel_name} (ONLY autorole)")
                    else:

                        results["channels_modified"].append(f"✅ Verification: #{channel_name} (completely hidden)")
                    
                elif channel_id in admin_channel_ids:

                    logger.info(f"Processing ADMIN channel: #{channel_name}")
                    await channel.set_permissions(everyone_role, read_messages=False, send_messages=False)
                    await channel.set_permissions(verified_role, read_messages=False, send_messages=False)
                    if autorole:
                        await channel.set_permissions(autorole, read_messages=False, send_messages=False)
                    results["channels_modified"].append(f"🔒 Admin: #{channel_name}")
                    
                elif channel_id in public_channel_ids:

                    logger.info(f"Processing PUBLIC channel: #{channel_name}")
                    await channel.set_permissions(everyone_role, read_messages=True, send_messages=False)
                    await channel.set_permissions(verified_role, read_messages=True, send_messages=False)
                    if autorole:
                        await channel.set_permissions(autorole, read_messages=True, send_messages=False)
                    results["channels_modified"].append(f"🌐 Public: #{channel_name} (all read-only)")
                    
                else:

                    logger.info(f"Processing MEMBER channel: #{channel_name} (autorole should be DENIED)")
                    await channel.set_permissions(everyone_role, read_messages=False, send_messages=False)
                    await channel.set_permissions(verified_role, read_messages=True, send_messages=True)
                    if autorole:
                        await channel.set_permissions(autorole, read_messages=False, send_messages=False)
                        logger.info(f"DENIED autorole {autorole.name} access to #{channel_name}")
                    results["channels_modified"].append(f"🔐 Members: #{channel_name} (autorole denied)")
                

                if write_role and write_mode and write_channels:
                    logger.info(f"Applying write permissions for {write_role.name} in #{channel_name}, mode: {write_mode}")
                    await self.apply_write_permissions(channel, channel_id, write_role, write_mode, write_channels)
                
                results["success"] += 1
                

                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error setting permissions for channel {channel_name}: {e}")
                results["failed"] += 1
                results["errors"].append(f"Failed to set permissions for #{channel_name}: {str(e)}")
        
        logger.info(f"Verification setup completed for {guild.name}: {results['success']} success, {results['failed']} failed")
        return results
    
    async def apply_write_permissions(self, channel, channel_id: int, write_role: discord.Role, mode: str, write_channels: set):
        
        try:

            current_overwrites = channel.overwrites_for(write_role)
            current_read = current_overwrites.read_messages
            
            logger.info(f"Write permissions for {write_role.name} in #{channel.name}: current_read={current_read}, mode={mode}, channel_in_list={channel_id in write_channels}")
            
            if mode == "exclude":

                if channel_id in write_channels:

                    await channel.set_permissions(write_role, read_messages=current_read, send_messages=False)
                    logger.info(f"EXCLUDE MODE: DENIED writing for {write_role.name} in #{channel.name} (channel is in exclude list)")
                else:

                    await channel.set_permissions(write_role, read_messages=current_read, send_messages=True)
                    logger.info(f"EXCLUDE MODE: ALLOWED writing for {write_role.name} in #{channel.name} (channel NOT in exclude list)")
            
            elif mode == "include":

                if channel_id in write_channels:

                    await channel.set_permissions(write_role, read_messages=current_read, send_messages=True)
                    logger.info(f"INCLUDE MODE: ALLOWED writing for {write_role.name} in #{channel.name} (channel is in include list)")
                else:

                    await channel.set_permissions(write_role, read_messages=current_read, send_messages=False)
                    logger.info(f"INCLUDE MODE: DENIED writing for {write_role.name} in #{channel.name} (channel NOT in include list)")
                    
        except Exception as e:
            logger.error(f"Error applying write permissions to channel {channel.name}: {e}")
    
    def setup_user_prompt(self, user_id: int, guild_id: int, prompt_type: str, channel_id: int):
        
        self.user_prompts[user_id] = {
            "guild_id": guild_id,
            "prompt_type": prompt_type,
            "channel_id": channel_id
        }
        logger.info(f"Set up prompt for user {user_id}: {prompt_type}")
    
    @commands.Cog.listener()
    async def on_message(self, message):
        

        if message.author.bot:
            return
        

        user_id = message.author.id
        if user_id not in self.user_prompts:
            return
        
        prompt_data = self.user_prompts[user_id]
        logger.info(f"Processing prompt response from user {user_id}: {message.content} | Prompt type: {prompt_data['prompt_type']}")
        

        if (message.guild is None or 
            message.guild.id != prompt_data["guild_id"] or
            message.channel.id != prompt_data["channel_id"]):
            logger.info(f"Message not in correct guild/channel. Guild: {message.guild.id if message.guild else None}, Expected: {prompt_data['guild_id']}, Channel: {message.channel.id}, Expected: {prompt_data['channel_id']}")
            return
        

        try:

            original_prompt_type = prompt_data["prompt_type"]
            await self.handle_prompt_response(message, prompt_data)
            


            current_prompt = self.user_prompts.get(user_id)
            if current_prompt and current_prompt["prompt_type"] == original_prompt_type:

                del self.user_prompts[user_id]
                logger.info(f"Removed prompt for user {user_id} after processing {original_prompt_type}")
            else:
                logger.info(f"Keeping new prompt for user {user_id}: {current_prompt['prompt_type'] if current_prompt else 'None'}")
                
        except Exception as e:
            logger.error(f"Error handling prompt response: {e}")
            await message.reply(f"❌ Error processing your response: {str(e)}")

            if user_id in self.user_prompts:
                del self.user_prompts[user_id]
    
    async def handle_prompt_response(self, message: discord.Message, prompt_data: Dict[str, Any]):
        
        guild = message.guild
        user_input = message.content.strip()
        prompt_type = prompt_data["prompt_type"]
        guild_id = prompt_data["guild_id"]
        

        if guild_id not in self.active_setups:
            self.active_setups[guild_id] = {
                "verification_channel": None,
                "public_channels": [],
                "admin_channels": [],
                "verified_role": None,
                "autorole": None,
                "uses_autorole": False,
                "write_permissions": {
                    "role": None,
                    "mode": None,
                    "channels": []
                },
                "setup_complete": False
            }
        
        if prompt_type == "verification_channel":
            await self.handle_verification_channel_response(message, user_input, guild_id)
        elif prompt_type == "autorole_question":
            await self.handle_autorole_question_response(message, user_input, guild_id)
        elif prompt_type == "autorole_selection":
            await self.handle_autorole_selection_response(message, user_input, guild_id)
        elif prompt_type == "verified_role":
            await self.handle_verified_role_response(message, user_input, guild_id)
        elif prompt_type == "public_channels":
            await self.handle_public_channels_response(message, user_input, guild_id)
        elif prompt_type == "admin_channels":
            await self.handle_admin_channels_response(message, user_input, guild_id)
        elif prompt_type == "write_permissions_role":
            await self.handle_write_permissions_role_response(message, user_input, guild_id)
        elif prompt_type == "write_permissions_mode":
            await self.handle_write_permissions_mode_response(message, user_input, guild_id)
        elif prompt_type == "write_permissions_channels":
            await self.handle_write_permissions_channels_response(message, user_input, guild_id)
    
    async def handle_verification_channel_response(self, message: discord.Message, user_input: str, guild_id: int):
        
        guild = message.guild
        channel = None
        

        if user_input.isdigit():
            channel = guild.get_channel(int(user_input))
        

        if not channel:

            channel_name = user_input.lstrip('#')
            channel = discord.utils.get(guild.channels, name=channel_name)
        

        if not channel and user_input.startswith('<#') and user_input.endswith('>'):
            try:
                channel_id = int(user_input[2:-1])
                channel = guild.get_channel(channel_id)
            except:
                pass
        
        if not channel:
            await message.reply(f"❌ Channel not found: `{user_input}`\nTry using the channel name, ID, or mention (e.g., #verification, 123456789, or {message.channel.mention})")
            return
        

        self.active_setups[guild_id]["verification_channel"] = channel.id
        self.save_setup_data()
        
        embed = discord.Embed(
            title="✅ Verification Channel Selected",
            description=f"**Verification Channel:** {channel.mention}",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await message.reply(embed=embed)
    
    async def handle_verified_role_response(self, message: discord.Message, user_input: str, guild_id: int):
        
        guild = message.guild
        role = None
        

        if user_input.isdigit():
            role = guild.get_role(int(user_input))
        

        if not role:

            role_name = user_input.lstrip('@')
            role = discord.utils.get(guild.roles, name=role_name)
        

        if not role and user_input.startswith('<@&') and user_input.endswith('>'):
            try:
                role_id = int(user_input[3:-1])
                role = guild.get_role(role_id)
            except:
                pass
        
        if not role:
            await message.reply(f"❌ Role not found: `{user_input}`\nTry using the role name, ID, or mention (e.g., Member, 123456789, or @Member)")
            return
        

        self.active_setups[guild_id]["verified_role"] = role.id
        self.save_setup_data()
        
        embed = discord.Embed(
            title="✅ Verified Role Selected",
            description=f"**Verified Role:** {role.mention}",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await message.reply(embed=embed)
    
    async def handle_public_channels_response(self, message: discord.Message, user_input: str, guild_id: int):
        
        guild = message.guild
        selected_channels = []
        
        if user_input.lower() in ['none', 'skip', 'cancel', '']:

            self.active_setups[guild_id]["public_channels"] = []
            embed = discord.Embed(
                title="✅ Public Channels Cleared",
                description="**Public Channels:** None selected",
                color=discord.Color.green()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await message.reply(embed=embed)
            return
        

        channel_inputs = [ch.strip() for ch in user_input.split(',')]
        not_found = []
        
        for channel_input in channel_inputs:
            if not channel_input:
                continue
                
            channel = None
            

            if channel_input.isdigit():
                channel = guild.get_channel(int(channel_input))
            

            if not channel:
                channel_name = channel_input.lstrip('#')
                channel = discord.utils.get(guild.channels, name=channel_name)
            

            if not channel and channel_input.startswith('<#') and channel_input.endswith('>'):
                try:
                    channel_id = int(channel_input[2:-1])
                    channel = guild.get_channel(channel_id)
                except:
                    pass
            
            if channel:
                selected_channels.append(channel.id)
            else:
                not_found.append(channel_input)
        

        self.active_setups[guild_id]["public_channels"] = selected_channels
        self.save_setup_data()
        

        embed = discord.Embed(
            title="✅ Public Channels Selected",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        if selected_channels:
            channel_mentions = [guild.get_channel(ch_id).mention for ch_id in selected_channels if guild.get_channel(ch_id)]
            embed.add_field(
                name="Public Channels",
                value=", ".join(channel_mentions[:10]) + (f" (+{len(channel_mentions)-10} more)" if len(channel_mentions) > 10 else ""),
                inline=False
            )
        else:
            embed.add_field(name="Public Channels", value="None selected", inline=False)
        
        if not_found:
            embed.add_field(
                name="⚠️ Not Found",
                value=", ".join(not_found),
                inline=False
            )
        
        await message.reply(embed=embed)
    
    async def handle_admin_channels_response(self, message: discord.Message, user_input: str, guild_id: int):
        
        guild = message.guild
        selected_channels = []
        
        if user_input.lower() in ['none', 'skip', 'cancel', '']:

            self.active_setups[guild_id]["admin_channels"] = []
            embed = discord.Embed(
                title="✅ Admin Channels Cleared",
                description="**Admin Channels:** None selected",
                color=discord.Color.green()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await message.reply(embed=embed)
            return
        

        channel_inputs = [ch.strip() for ch in user_input.split(',')]
        not_found = []
        
        for channel_input in channel_inputs:
            if not channel_input:
                continue
                
            channel = None
            

            if channel_input.isdigit():
                channel = guild.get_channel(int(channel_input))
            

            if not channel:
                channel_name = channel_input.lstrip('#')
                channel = discord.utils.get(guild.channels, name=channel_name)
            

            if not channel and channel_input.startswith('<#') and channel_input.endswith('>'):
                try:
                    channel_id = int(channel_input[2:-1])
                    channel = guild.get_channel(channel_id)
                except:
                    pass
            
            if channel:
                selected_channels.append(channel.id)
            else:
                not_found.append(channel_input)
        

        self.active_setups[guild_id]["admin_channels"] = selected_channels
        self.save_setup_data()
        

        embed = discord.Embed(
            title="✅ Admin Channels Selected",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        if selected_channels:
            channel_mentions = [guild.get_channel(ch_id).mention for ch_id in selected_channels if guild.get_channel(ch_id)]
            embed.add_field(
                name="Admin Channels",
                value=", ".join(channel_mentions[:10]) + (f" (+{len(channel_mentions)-10} more)" if len(channel_mentions) > 10 else ""),
                inline=False
            )
        else:
            embed.add_field(name="Admin Channels", value="None selected", inline=False)
        
        if not_found:
            embed.add_field(
                name="⚠️ Not Found",
                value=", ".join(not_found),
                inline=False
            )
        
        await message.reply(embed=embed)
    
    async def handle_autorole_question_response(self, message: discord.Message, user_input: str, guild_id: int):
        
        user_input_lower = user_input.lower().strip()
        
        if user_input_lower in ['yes', 'y', 'true', '1', 'yeah', 'yep', 'yup']:

            embed = discord.Embed(
                title="🤖 Select Autorole",
                description="Please send the role that users get when they **first join** your server (before verification).",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            
            embed.add_field(
                name="📋 How to specify:",
                value="• **Role name:** `Unverified` or `@Unverified`\n"
                      "• **Role mention:** @Unverified (ping the role)\n"
                      "• **Role ID:** `123456789012345678`",
                inline=False
            )
            
            embed.add_field(
                name="💡 Example:",
                value="Type: `Unverified` or `@New Member`",
                inline=False
            )
            
            embed.add_field(
                name="ℹ️ Why this matters:",
                value="The verification channel will be visible to this role instead of @everyone",
                inline=False
            )
            

            self.setup_user_prompt(
                user_id=message.author.id,
                guild_id=guild_id,
                prompt_type="autorole_selection",
                channel_id=message.channel.id
            )
            logger.info(f"Set up autorole_selection prompt for user {message.author.id} in channel {message.channel.id}")
            
            await message.reply(embed=embed)
            
        elif user_input_lower in ['no', 'n', 'false', '0', 'nope', 'nah']:

            self.active_setups[guild_id]["uses_autorole"] = False
            self.active_setups[guild_id]["autorole"] = None
            
            embed = discord.Embed(
                title="✅ No Autorole",
                description="**Autorole System:** Not used\n\nNow let's select the verified role...",
                color=discord.Color.green()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await message.reply(embed=embed)
            

            await asyncio.sleep(1)
            await self.prompt_verified_role_selection(message, guild_id)
            
        else:
            await message.reply(f"❌ Please answer with **yes** or **no**.\nDo you use an autorole system? (yes/no)")
    
    async def handle_autorole_selection_response(self, message: discord.Message, user_input: str, guild_id: int):
        
        logger.info(f"Handling autorole selection response: {user_input}")
        guild = message.guild
        role = None
        

        if user_input.isdigit():
            role = guild.get_role(int(user_input))
        

        if not role:

            role_name = user_input.lstrip('@')
            role = discord.utils.get(guild.roles, name=role_name)
        

        if not role and user_input.startswith('<@&') and user_input.endswith('>'):
            try:
                role_id = int(user_input[3:-1])
                role = guild.get_role(role_id)
            except:
                pass
        
        if not role:
            await message.reply(f"❌ Role not found: `{user_input}`\nTry using the role name, ID, or mention (e.g., Unverified, 123456789, or @Unverified)")
            return
        

        self.active_setups[guild_id]["uses_autorole"] = True
        self.active_setups[guild_id]["autorole"] = role.id
        
        embed = discord.Embed(
            title="✅ Autorole Selected",
            description=f"**Autorole:** {role.mention}\n\nNow let's select the verified role...",
            color=discord.Color.green()
        )
        await message.reply(embed=embed)
        

        await asyncio.sleep(1)
        await self.prompt_verified_role_selection(message, guild_id)
    
    async def prompt_verified_role_selection(self, message: discord.Message, guild_id: int):
        
        embed = discord.Embed(
            title="👤 Select Verified Member Role",
            description="Please send the role that users receive **after verification**.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        embed.add_field(
            name="📋 How to specify:",
            value="• **Role name:** `Member` or `@Member`\n"
                  "• **Role mention:** @Member (ping the role)\n"
                  "• **Role ID:** `123456789012345678`",
            inline=False
        )
        
        embed.add_field(
            name="💡 Example:",
            value="Type: `Member` or `@Verified`",
            inline=False
        )
        

        self.setup_user_prompt(
            user_id=message.author.id,
            guild_id=guild_id,
            prompt_type="verified_role",
            channel_id=message.channel.id
        )
        
        await message.channel.send(embed=embed)
    
    async def handle_write_permissions_role_response(self, message: discord.Message, user_input: str, guild_id: int):
        
        guild = message.guild
        role = None
        

        if user_input.isdigit():
            role = guild.get_role(int(user_input))
        

        if not role:

            role_name = user_input.lstrip('@')
            role = discord.utils.get(guild.roles, name=role_name)
        

        if not role and user_input.startswith('<@&') and user_input.endswith('>'):
            try:
                role_id = int(user_input[3:-1])
                role = guild.get_role(role_id)
            except:
                pass
        
        if not role:
            await message.reply(f"❌ Role not found: `{user_input}`\nTry using the role name, ID, or mention (e.g., Member, 123456789, or @Member)")
            return
        

        self.active_setups[guild_id]["write_permissions"]["role"] = role.id
        
        embed = discord.Embed(
            title="✅ Write Permissions Role Selected",
            description=f"**Role:** {role.mention}\n\nNow choose the permission mode...",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await message.reply(embed=embed)
        

        await asyncio.sleep(1)
        await self.prompt_write_permissions_mode(message, guild_id)
    
    async def prompt_write_permissions_mode(self, message: discord.Message, guild_id: int):
        
        embed = discord.Embed(
            title="🎯 Choose Write Permission Mode",
            description="How do you want to configure write permissions?",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        embed.add_field(
            name="📌 Option 1: EXCLUDE Mode",
            value="• Role can write in **all channels EXCEPT** the ones you specify\n"
                  "• Good when you want to block specific channels (announcements, rules)\n"
                  "• Example: Write everywhere except #announcements, #rules",
            inline=False
        )
        
        embed.add_field(
            name="📌 Option 2: INCLUDE Mode", 
            value="• Role can write **ONLY in** the channels you specify\n"
                  "• Good for strict control with limited channels\n"
                  "• Example: Write only in #general, #chat, #off-topic",
            inline=False
        )
        
        embed.add_field(
            name="💬 Your choice:",
            value="Type: `exclude` or `include`",
            inline=False
        )
        

        self.setup_user_prompt(
            user_id=message.author.id,
            guild_id=guild_id,
            prompt_type="write_permissions_mode",
            channel_id=message.channel.id
        )
        
        await message.channel.send(embed=embed)
    
    async def handle_write_permissions_mode_response(self, message: discord.Message, user_input: str, guild_id: int):
        
        user_input_lower = user_input.lower().strip()
        
        if user_input_lower in ['exclude', 'ex', 'except', 'block']:
            mode = "exclude"
            mode_text = "EXCLUDE mode (write everywhere except specified channels)"
            prompt_text = "channels to **BLOCK** writing in"
            example_text = "Type: `#announcements, #rules` or channel IDs"
        elif user_input_lower in ['include', 'in', 'only', 'allow']:
            mode = "include" 
            mode_text = "INCLUDE mode (write only in specified channels)"
            prompt_text = "channels to **ALLOW** writing in"
            example_text = "Type: `#general, #chat, #off-topic` or channel IDs"
        else:
            await message.reply(f"❌ Please answer with **exclude** or **include**.\n\n• `exclude` = write everywhere except specified channels\n• `include` = write only in specified channels")
            return
        

        self.active_setups[guild_id]["write_permissions"]["mode"] = mode
        
        embed = discord.Embed(
            title="✅ Write Permission Mode Selected",
            description=f"**Mode:** {mode_text}",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        await message.reply(embed=embed)
        

        await asyncio.sleep(1)
        await self.prompt_write_permissions_channels(message, guild_id, mode, prompt_text, example_text)
    
    async def prompt_write_permissions_channels(self, message: discord.Message, guild_id: int, mode: str, prompt_text: str, example_text: str):
        
        embed = discord.Embed(
            title="📝 Select Channels",
            description=f"Please send the {prompt_text}.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        embed.add_field(
            name="📋 How to specify:",
            value="• **Multiple channels:** `#general, #announcements, #rules`\n"
                  "• **Channel mentions:** " + message.channel.mention + ", #general\n" 
                  "• **Channel IDs:** `123456789, 987654321`\n"
                  "• **Skip this step:** Type `none` or `skip`",
            inline=False
        )
        
        embed.add_field(
            name="💡 Example:",
            value=example_text,
            inline=False
        )
        

        self.setup_user_prompt(
            user_id=message.author.id,
            guild_id=guild_id,
            prompt_type="write_permissions_channels",
            channel_id=message.channel.id
        )
        
        await message.channel.send(embed=embed)
    
    async def handle_write_permissions_channels_response(self, message: discord.Message, user_input: str, guild_id: int):
        
        guild = message.guild
        selected_channels = []
        
        if user_input.lower() in ['none', 'skip', 'cancel', '']:

            self.active_setups[guild_id]["write_permissions"]["channels"] = []
            embed = discord.Embed(
                title="✅ Write Permissions Cleared",
                description="**Write Permissions:** Cleared (default permissions will apply)",
                color=discord.Color.green()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await message.reply(embed=embed)
            return
        

        channel_inputs = [ch.strip() for ch in user_input.split(',')]
        not_found = []
        
        for channel_input in channel_inputs:
            if not channel_input:
                continue
                
            channel = None
            

            if channel_input.isdigit():
                channel = guild.get_channel(int(channel_input))
            

            if not channel:
                channel_name = channel_input.lstrip('#')
                channel = discord.utils.get(guild.channels, name=channel_name)
            

            if not channel and channel_input.startswith('<#') and channel_input.endswith('>'):
                try:
                    channel_id = int(channel_input[2:-1])
                    channel = guild.get_channel(channel_id)
                except:
                    pass
            
            if channel:
                selected_channels.append(channel.id)
            else:
                not_found.append(channel_input)
        

        self.active_setups[guild_id]["write_permissions"]["channels"] = selected_channels
        mode = self.active_setups[guild_id]["write_permissions"]["mode"]
        

        embed = discord.Embed(
            title="✅ Write Permissions Configured",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        if selected_channels:
            channel_mentions = [guild.get_channel(ch_id).mention for ch_id in selected_channels if guild.get_channel(ch_id)]
            mode_desc = "write everywhere EXCEPT" if mode == "exclude" else "write ONLY in"
            embed.add_field(
                name=f"Write Permissions ({mode.upper()} mode)",
                value=f"Role can {mode_desc}:\n" + ", ".join(channel_mentions[:10]) + (f" (+{len(channel_mentions)-10} more)" if len(channel_mentions) > 10 else ""),
                inline=False
            )
        else:
            embed.add_field(name="Write Permissions", value="None configured", inline=False)
        
        if not_found:
            embed.add_field(
                name="⚠️ Not Found",
                value=", ".join(not_found),
                inline=False
            )
        
        await message.reply(embed=embed)

class ZVerifySetupView(discord.ui.View):
    
    
    def __init__(self, cog: ZVerifySetup, guild_id: int):
        super().__init__(timeout=600)
        self.cog = cog
        self.guild_id = guild_id
    
    @discord.ui.button(label="1️⃣ Select Verification Channel", style=discord.ButtonStyle.primary)
    async def select_verification_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        embed = discord.Embed(
            title="🔐 Select Verification Channel",
            description="Please send the verification channel in this chat.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        embed.add_field(
            name="📋 How to specify:",
            value="• **Channel name:** `verification` or `#verification`\n"
                  "• **Channel mention:** " + interaction.channel.mention + "\n"
                  "• **Channel ID:** `123456789012345678`",
            inline=False
        )
        
        embed.add_field(
            name="💡 Example:",
            value="Just type: `#verification` or `verification`",
            inline=False
        )
        

        self.cog.setup_user_prompt(
            user_id=interaction.user.id,
            guild_id=self.guild_id,
            prompt_type="verification_channel",
            channel_id=interaction.channel.id
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="2️⃣ Choose Verified Role", style=discord.ButtonStyle.primary)
    async def select_verified_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        embed = discord.Embed(
            title="🤖 Autorole System Check",
            description="Before setting up the verified role, I need to know about your autorole system.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        embed.add_field(
            name="❓ Do you use an autorole system?",
            value="**Autorole** = A role automatically given to users when they **first join** your server (before verification)\n\n"
                  "Examples: @Unverified, @New Member, @Pending\n\n"
                  "**Please answer:** `yes` or `no`",
            inline=False
        )
        
        embed.add_field(
            name="💡 Why this matters:",
            value="• **If YES:** Verification channel will be visible to autorole only\n"
                  "• **If NO:** Verification channel will be visible to @everyone\n\n"
                  "This makes verification more secure and organized!",
            inline=False
        )
        

        self.cog.setup_user_prompt(
            user_id=interaction.user.id,
            guild_id=self.guild_id,
            prompt_type="autorole_question",
            channel_id=interaction.channel.id
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="3️⃣ Select Public Channels", style=discord.ButtonStyle.secondary)
    async def select_public_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        embed = discord.Embed(
            title="🌐 Select Public Channels (Optional)",
            description="Please send channels that should stay visible to @everyone.\n**This is optional - you can skip this step.**",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        embed.add_field(
            name="📋 How to specify:",
            value="• **Multiple channels:** `#general, #announcements, #rules`\n"
                  "• **Channel mentions:** " + interaction.channel.mention + ", #general\n"
                  "• **Channel IDs:** `123456789, 987654321`\n"
                  "• **Skip this step:** Type `none` or `skip`",
            inline=False
        )
        
        embed.add_field(
            name="💡 Example:",
            value="Type: `#general, #announcements` or just `none`",
            inline=False
        )
        

        self.cog.setup_user_prompt(
            user_id=interaction.user.id,
            guild_id=self.guild_id,
            prompt_type="public_channels",
            channel_id=interaction.channel.id
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="4️⃣ Select Admin Channels", style=discord.ButtonStyle.secondary)
    async def select_admin_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        embed = discord.Embed(
            title="🔒 Select Admin Channels (Optional)",
            description="Please send channels that should be admin-only.\n**This is optional - you can skip this step.**",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        embed.add_field(
            name="📋 How to specify:",
            value="• **Multiple channels:** `#admin, #mod-chat, #logs`\n"
                  "• **Channel mentions:** #admin, " + interaction.channel.mention + "\n"
                  "• **Channel IDs:** `123456789, 987654321`\n"
                  "• **Skip this step:** Type `none` or `skip`",
            inline=False
        )
        
        embed.add_field(
            name="💡 Example:",
            value="Type: `#admin, #mod-chat` or just `none`",
            inline=False
        )
        

        self.cog.setup_user_prompt(
            user_id=interaction.user.id,
            guild_id=self.guild_id,
            prompt_type="admin_channels",
            channel_id=interaction.channel.id
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="✏️ Configure Write Permissions", style=discord.ButtonStyle.secondary)
    async def configure_write_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        embed = discord.Embed(
            title="✏️ Configure Write Permissions (Optional)",
            description="Set up granular write permissions for a specific role.\n**This is optional but recommended for better security.**",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        
        embed.add_field(
            name="❓ What does this do?",
            value="• Controls which channels a role can **write/send messages** in\n"
                  "• You can exclude channels (write everywhere except...) \n"
                  "• Or include channels (write only in specific channels)\n"
                  "• Perfect for blocking announcements/rules or limiting chat access",
            inline=False
        )
        
        embed.add_field(
            name="🤖 Which role to configure?",
            value="Please send the role you want to configure write permissions for.\n"
                  "**Tip:** Usually this is your verified member role.",
            inline=False
        )
        
        embed.add_field(
            name="📋 How to specify:",
            value="• **Role name:** `Member` or `@Member`\n"
                  "• **Role mention:** @Member (ping the role)\n"
                  "• **Role ID:** `123456789012345678`",
            inline=False
        )
        

        self.cog.setup_user_prompt(
            user_id=interaction.user.id,
            guild_id=self.guild_id,
            prompt_type="write_permissions_role",
            channel_id=interaction.channel.id
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="📊 Review Setup", style=discord.ButtonStyle.success)
    async def review_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        setup_data = self.cog.active_setups.get(self.guild_id, {})
        guild = interaction.guild
        
        embed = discord.Embed(
            title="📊 Verification Setup Review",
            description="Review your configuration before applying:",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made By TheHolyOneZ")
        

        if setup_data.get("verification_channel"):
            channel = guild.get_channel(setup_data["verification_channel"])
            embed.add_field(
                name="🔐 Verification Channel",
                value=f"#{channel.name}" if channel else "❌ Channel not found",
                inline=False
            )
        else:
            embed.add_field(name="🔐 Verification Channel", value="❌ Not set", inline=False)
        

        if setup_data.get("uses_autorole"):
            autorole = guild.get_role(setup_data["autorole"]) if setup_data.get("autorole") else None
            embed.add_field(
                name="🤖 Autorole System",
                value=f"**Uses Autorole:** Yes\n**Autorole:** @{autorole.name}" if autorole else "**Uses Autorole:** Yes\n**Autorole:** ❌ Role not found",
                inline=False
            )
        else:
            embed.add_field(
                name="🤖 Autorole System",
                value="**Uses Autorole:** No",
                inline=False
            )
        

        if setup_data.get("verified_role"):
            role = guild.get_role(setup_data["verified_role"])
            embed.add_field(
                name="👤 Verified Role",
                value=f"@{role.name}" if role else "❌ Role not found",
                inline=False
            )
        else:
            embed.add_field(name="👤 Verified Role", value="❌ Not set", inline=False)
        

        public_channels = setup_data.get("public_channels", [])
        if public_channels:
            channel_names = []
            for ch_id in public_channels:
                channel = guild.get_channel(ch_id)
                if channel:
                    channel_names.append(f"#{channel.name}")
            embed.add_field(
                name="🌐 Public Channels",
                value=", ".join(channel_names[:10]) + (f" (+{len(channel_names)-10} more)" if len(channel_names) > 10 else ""),
                inline=False
            )
        else:
            embed.add_field(name="🌐 Public Channels", value="None selected", inline=False)
        

        admin_channels = setup_data.get("admin_channels", [])
        if admin_channels:
            channel_names = []
            for ch_id in admin_channels:
                channel = guild.get_channel(ch_id)
                if channel:
                    channel_names.append(f"#{channel.name}")
            embed.add_field(
                name="🔒 Admin Channels",
                value=", ".join(channel_names[:10]) + (f" (+{len(channel_names)-10} more)" if len(channel_names) > 10 else ""),
                inline=False
            )
        else:
            embed.add_field(name="🔒 Admin Channels", value="None selected", inline=False)
        

        write_perms = setup_data.get("write_permissions", {})
        if write_perms.get("role") and write_perms.get("mode") and write_perms.get("channels"):
            role = guild.get_role(write_perms["role"]) 
            channels = write_perms["channels"]
            mode = write_perms["mode"]
            
            channel_names = []
            for ch_id in channels:
                channel = guild.get_channel(ch_id)
                if channel:
                    channel_names.append(f"#{channel.name}")
            
            mode_desc = "write everywhere EXCEPT" if mode == "exclude" else "write ONLY in"
            embed.add_field(
                name="✏️ Write Permissions",
                value=f"**Role:** @{role.name if role else 'Role not found'}\n"
                      f"**Mode:** {mode.upper()}\n"
                      f"**Rule:** Can {mode_desc}: {', '.join(channel_names[:5])}" +
                      (f" (+{len(channel_names)-5} more)" if len(channel_names) > 5 else ""),
                inline=False
            )
        else:
            embed.add_field(name="✏️ Write Permissions", value="None configured", inline=False)
        

        required_fields = ["verification_channel", "verified_role"]
        missing_fields = [field for field in required_fields if not setup_data.get(field)]
        
        if missing_fields:
            embed.add_field(
                name="⚠️ Missing Required Fields",
                value=f"Please set: {', '.join(missing_fields)}",
                inline=False
            )
        else:
            embed.add_field(
                name="✅ Ready to Apply",
                value="All required fields are set. You can now apply the verification setup.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🚀 Apply Setup", style=discord.ButtonStyle.danger)
    async def apply_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        setup_data = self.cog.active_setups.get(self.guild_id, {})
        

        required_fields = ["verification_channel", "verified_role"]
        missing_fields = [field for field in required_fields if not setup_data.get(field)]
        
        if missing_fields:
            embed = discord.Embed(
                title="❌ Cannot Apply Setup",
                description=f"Missing required fields: {', '.join(missing_fields)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        

        embed = discord.Embed(
            title="⚠️ Confirm Verification Setup",
            description="This will modify permissions on ALL channels in your server.\n\n"
                       "**Are you absolutely sure you want to proceed?**",
            color=discord.Color.orange()
        )
        
        view = ConfirmationView(self.cog, self.guild_id, setup_data)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ConfirmationView(discord.ui.View):
    
    
    def __init__(self, cog: ZVerifySetup, guild_id: int, setup_data: Dict[str, Any]):
        super().__init__(timeout=60)
        self.cog = cog
        self.guild_id = guild_id
        self.setup_data = setup_data
    
    @discord.ui.button(label="✅ Yes, Apply Setup", style=discord.ButtonStyle.danger)
    async def confirm_apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        await interaction.response.send_message("🔄 Applying verification setup... This may take a moment.", ephemeral=True)
        
        try:
            results = await self.cog.apply_verification_permissions(interaction.guild, self.setup_data)
            

            if results["failed"] == 0:
                embed = discord.Embed(
                    title="✅ Verification Setup Complete!",
                    description=f"Successfully configured {results['success']} channels for verification.",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="⚠️ Verification Setup Completed with Errors",
                    description=f"Configured {results['success']} channels, {results['failed']} failed.",
                    color=discord.Color.orange()
                )
            

            if results["channels_modified"]:
                channel_summary = "\n".join(results["channels_modified"][:20])
                if len(results["channels_modified"]) > 20:
                    channel_summary += f"\n... and {len(results['channels_modified']) - 20} more"
                
                embed.add_field(
                    name="📋 Channels Modified",
                    value=channel_summary,
                    inline=False
                )
            

            if results["errors"]:
                error_summary = "\n".join(results["errors"][:5])
                if len(results["errors"]) > 5:
                    error_summary += f"\n... and {len(results['errors']) - 5} more errors"
                
                embed.add_field(
                    name="❌ Errors",
                    value=error_summary,
                    inline=False
                )
            
            embed.add_field(
                name="🎉 Next Steps",
                value="• Your server is now ready for verification bots!\n"
                      "• Users will only see the verification channel until verified\n"
                      "• Verified users will get access to member channels\n"
                      "• Admin channels remain protected",
                inline=False
            )
            

            self.cog.active_setups[self.guild_id]["setup_complete"] = True
            self.cog.active_setups[self.guild_id]["setup_date"] = datetime.datetime.now().isoformat()
            self.cog.save_setup_data()
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error applying verification setup: {e}")
            embed = discord.Embed(
                title="❌ Setup Failed",
                description=f"An error occurred while applying the setup: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        embed = discord.Embed(
            title="❌ Setup Cancelled",
            description="Verification setup was cancelled. No changes were made.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)




class ZVerifySetupCommands(commands.Cog):
    
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="zverify_status", aliases=["zvstatus"])
    @commands.has_permissions(administrator=True)
    async def zverify_status(self, ctx):
        
        cog = self.bot.get_cog("ZVerifySetup")
        if not cog:
            await ctx.send("❌ ZVerifySetup cog not loaded!")
            return
        
        guild_id = ctx.guild.id
        setup_data = cog.active_setups.get(guild_id, {})
        
        if not setup_data:
            prefix = get_prefix(ctx)
            await ctx.send(f"❌ No verification setup found for this server. Use `{prefix}zverify_setup` to start.")
            return
        
        embed = discord.Embed(
            title="📊 Current Verification Setup",
            color=discord.Color.blue()
        )
        

        for key, value in setup_data.items():
            if key == "verification_channel" and value:
                channel = ctx.guild.get_channel(value)
                embed.add_field(name="🔐 Verification Channel", value=f"#{channel.name}" if channel else "❌ Channel not found", inline=False)
            elif key == "verified_role" and value:
                role = ctx.guild.get_role(value)
                embed.add_field(name="👤 Verified Role", value=f"@{role.name}" if role else "❌ Role not found", inline=False)
            elif key in ["public_channels", "admin_channels"] and value:
                channel_names = []
                for ch_id in value:
                    channel = ctx.guild.get_channel(ch_id)
                    if channel:
                        channel_names.append(f"#{channel.name}")
                embed.add_field(
                    name=f"📋 {key.replace('_', ' ').title()}",
                    value=", ".join(channel_names[:5]) + (f" (+{len(channel_names)-5} more)" if len(channel_names) > 5 else "") if channel_names else "None",
                    inline=False
                )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="zverify_reset", aliases=["zvreset"])
    @commands.has_permissions(administrator=True)
    async def reset_zverify_setup(self, ctx):
        
        cog = self.bot.get_cog("ZVerifySetup")
        if not cog:
            await ctx.send("❌ ZVerifySetup cog not loaded!")
            return
        
        guild_id = ctx.guild.id
        if guild_id in cog.active_setups:
            del cog.active_setups[guild_id]
            cog.save_setup_data()
            await ctx.send("✅ Verification setup reset for this server.")
        else:
            await ctx.send("❌ No verification setup found for this server.")

async def setup(bot):
    
    await bot.add_cog(ZVerifySetup(bot))
    await bot.add_cog(ZVerifySetupCommands(bot))
    logger.info("ZVerify Setup extension loaded successfully")

async def teardown(bot):
    
    logger.info("ZVerify Setup extension unloaded")
