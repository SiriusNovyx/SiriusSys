import discord
from discord.ext import commands
import asyncio
import typing
from typing import Optional, List, Literal
import logging
import traceback

logger = logging.getLogger('sync_commands')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

class SyncCommands(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(name="help_sync")
    async def help_sync(self, ctx):
        
        embed = discord.Embed(
            title="🔄 Sync Commands Help",
            description="Commands for managing Discord application commands",
            color=discord.Color.blue()
        )
        
        
        admin_commands = [
            ("!sync_guild", "Sync commands to the current guild only", "Server administrators"),
            ("!sync_status", "Check the status of commands in the current guild and globally", "Server administrators")
        ]
        
        admin_desc = "\n\n".join([f"**{cmd}**\n*{desc}*\nPermission: {perm}" for cmd, desc, perm in admin_commands])
        embed.add_field(name="Administrator Commands", value=admin_desc, inline=False)
        
        
        owner_commands = [
            ("!sync_global", "Sync commands globally to all guilds", "When you want to update commands across all servers"),
            ("!sync_force [guild_id]", "Force sync commands to a specific guild or globally", "When normal sync isn't working"),
            ("!clear_commands [guild_id]", "Remove all commands from a guild or globally", "When you need to start fresh"),
            ("!sync_copy <source_guild_id> [target_guild_id]", "Copy commands from one guild to another or globally", "To replicate command setup"),
            ("!reload_and_sync [guild_id]", "Reload all extensions and sync commands", "After making code changes"),
            ("!sync_debug [guild_id]", "Get detailed debug information about commands", "When troubleshooting sync issues")
        ]
        
        owner_desc = "\n\n".join([f"**{cmd}**\n*{desc}*\nUse case: {use}" for cmd, desc, use in owner_commands])
        embed.add_field(name="Bot Owner Commands", value=owner_desc, inline=False)
        
        embed.set_footer(text="Made By TheZ | Parameters in [brackets] are optional")
        
        await ctx.send(embed=embed)
        
    @commands.command(name="sync_guild")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def sync_guild(self, ctx):
        
        try:
            
            local_commands = self.bot.tree.get_commands(guild=ctx.guild)
            logger.info(f"Guild {ctx.guild.id} has {len(local_commands)} commands before syncing")
            
            
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
            
            
            logger.info(f"Synced commands: {[cmd.name for cmd in synced]}")
            
            embed = discord.Embed(
                title="✅ Guild Sync Complete",
                description=f"Successfully synced {len(synced)} commands to this guild.",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Guild ID: {ctx.guild.id} | Made By TheZ")
            
            await ctx.send(embed=embed)
            logger.info(f"Synced {len(synced)} commands to guild {ctx.guild.id}")
            
        except Exception as e:
            tb = traceback.format_exc()
            error_embed = discord.Embed(
                title="❌ Sync Failed",
                description=f"An error occurred while syncing commands: {str(e)}",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Made By TheZ")
            await ctx.send(embed=error_embed)
            logger.error(f"Error syncing to guild {ctx.guild.id}: {str(e)}\n{tb}")
    
    @commands.command(name="sync_global")
    @commands.is_owner()
    async def sync_global(self, ctx):
        
        try:
            
            local_commands = self.bot.tree.get_commands()
            logger.info(f"Bot has {len(local_commands)} global commands before syncing")
            
            
            synced = await ctx.bot.tree.sync()
            
            
            logger.info(f"Synced global commands: {[cmd.name for cmd in synced]}")
            
            embed = discord.Embed(
                title="✅ Global Sync Complete",
                description=f"Successfully synced {len(synced)} commands globally.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Made By TheZ")
            
            await ctx.send(embed=embed)
            logger.info(f"Synced {len(synced)} commands globally")
            
        except Exception as e:
            tb = traceback.format_exc()
            error_embed = discord.Embed(
                title="❌ Global Sync Failed",
                description=f"An error occurred while syncing commands: {str(e)}",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Made By TheZ")
            await ctx.send(embed=error_embed)
            logger.error(f"Error syncing globally: {str(e)}\n{tb}")
    
    @commands.command(name="sync_force")
    @commands.is_owner()
    async def sync_force(self, ctx, guild_id: Optional[int] = None):
        
        try:
            if guild_id:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    await ctx.send(embed=discord.Embed(
                        title="❌ Guild Not Found",
                        description=f"Could not find guild with ID {guild_id}",
                        color=discord.Color.red()
                    ).set_footer(text="Made By TheZ"))
                    return
                
                
                local_commands = self.bot.tree.get_commands(guild=guild)
                logger.info(f"Guild {guild.id} has {len(local_commands)} commands before force syncing")
                
                
                synced = await ctx.bot.tree.sync(guild=guild)
                
                
                logger.info(f"Force synced commands to guild {guild.id}: {[cmd.name for cmd in synced]}")
                
                embed = discord.Embed(
                    title="✅ Force Guild Sync Complete",
                    description=f"Successfully synced {len(synced)} commands to guild {guild.name}.",
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"Guild ID: {guild.id} | Made By TheZ")
                
                await ctx.send(embed=embed)
                logger.info(f"Force synced {len(synced)} commands to guild {guild.id}")
            else:
                
                local_commands = self.bot.tree.get_commands()
                logger.info(f"Bot has {len(local_commands)} global commands before force syncing")
                
                
                synced = await ctx.bot.tree.sync()
                
                
                logger.info(f"Force synced global commands: {[cmd.name for cmd in synced]}")
                
                embed = discord.Embed(
                    title="✅ Force Global Sync Complete",
                    description=f"Successfully synced {len(synced)} commands globally.",
                    color=discord.Color.green()
                )
                embed.set_footer(text="Made By TheZ")
                
                await ctx.send(embed=embed)
                logger.info(f"Force synced {len(synced)} commands globally")
                
        except Exception as e:
            tb = traceback.format_exc()
            error_embed = discord.Embed(
                title="❌ Force Sync Failed",
                description=f"An error occurred while force syncing commands: {str(e)}",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Made By TheZ")
            await ctx.send(embed=error_embed)
            logger.error(f"Error force syncing: {str(e)}\n{tb}")
    
    @commands.command(name="clear_commands")
    @commands.is_owner()
    async def clear_commands(self, ctx, guild_id: Optional[int] = None):
        
        try:
            if guild_id:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    await ctx.send(embed=discord.Embed(
                        title="❌ Guild Not Found",
                        description=f"Could not find guild with ID {guild_id}",
                        color=discord.Color.red()
                    ).set_footer(text="Made By TheZ"))
                    return
                
                
                confirm_embed = discord.Embed(
                    title="⚠️ Confirm Command Clearing",
                    description=f"Are you sure you want to clear all commands from guild **{guild.name}**?\n\nReply with `yes` to confirm or `no` to cancel.",
                    color=discord.Color.gold()
                )
                confirm_embed.set_footer(text="Made By TheZ")
                await ctx.send(embed=confirm_embed)
                
                try:
                    
                    def check(m):
                        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["yes", "no"]
                    
                    response = await self.bot.wait_for("message", check=check, timeout=30.0)
                    if response.content.lower() != "yes":
                        await ctx.send(embed=discord.Embed(
                            title="🛑 Operation Cancelled",
                            description="Command clearing cancelled.",
                            color=discord.Color.blue()
                        ).set_footer(text="Made By TheZ"))
                        return
                except asyncio.TimeoutError:
                    await ctx.send(embed=discord.Embed(
                        title="⏱️ Timed Out",
                        description="No confirmation received within 30 seconds. Operation cancelled.",
                        color=discord.Color.red()
                    ).set_footer(text="Made By TheZ"))
                    return
                
                
                local_commands = await self.bot.tree.fetch_commands(guild=guild)
                logger.info(f"Guild {guild.id} has {len(local_commands)} commands before clearing")
                
                
                self.bot.tree.clear_commands(guild=guild)
                await self.bot.tree.sync(guild=guild)
                
                embed = discord.Embed(
                    title="✅ Guild Commands Cleared",
                    description=f"Successfully cleared all commands from guild {guild.name}.",
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"Guild ID: {guild.id} | Made By TheZ")
                
                await ctx.send(embed=embed)
                logger.info(f"Cleared commands from guild {guild.id}")
            else:
                
                confirm_embed = discord.Embed(
                    title="⚠️ Confirm Global Command Clearing",
                    description="Are you sure you want to clear all **global commands**?\n\nThis will affect all guilds where the bot is present.\n\nReply with `yes` to confirm or `no` to cancel.",
                    color=discord.Color.gold()
                )
                confirm_embed.set_footer(text="Made By TheZ")
                await ctx.send(embed=confirm_embed)
                
                try:
                    
                    def check(m):
                        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["yes", "no"]
                    
                    response = await self.bot.wait_for("message", check=check, timeout=30.0)
                    if response.content.lower() != "yes":
                        await ctx.send(embed=discord.Embed(
                            title="🛑 Operation Cancelled",
                            description="Global command clearing cancelled.",
                            color=discord.Color.blue()
                        ).set_footer(text="Made By TheZ"))
                        return
                except asyncio.TimeoutError:
                    await ctx.send(embed=discord.Embed(
                        title="⏱️ Timed Out",
                        description="No confirmation received within 30 seconds. Operation cancelled.",
                        color=discord.Color.red()
                    ).set_footer(text="Made By TheZ"))
                    return
                
                
                global_commands = await self.bot.tree.fetch_commands()
                logger.info(f"Bot has {len(global_commands)} global commands before clearing")
                
                
                self.bot.tree.clear_commands()
                await self.bot.tree.sync()
                
                embed = discord.Embed(
                    title="✅ Global Commands Cleared",
                    description="Successfully cleared all global commands.",
                    color=discord.Color.green()
                )
                embed.set_footer(text="Made By TheZ")
                
                await ctx.send(embed=embed)
                logger.info("Cleared global commands")
                
        except Exception as e:
            tb = traceback.format_exc()
            error_embed = discord.Embed(
                title="❌ Command Clearing Failed",
                description=f"An error occurred while clearing commands: {str(e)}",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Made By TheZ")
            await ctx.send(embed=error_embed)
            logger.error(f"Error clearing commands: {str(e)}\n{tb}")
    
    @commands.command(name="sync_status")
    @commands.has_permissions(administrator=True)
    async def sync_status(self, ctx):
        
        try:
            
            local_global_commands = self.bot.tree.get_commands()
            api_global_commands = await self.bot.tree.fetch_commands()
            
            local_guild_commands = []
            api_guild_commands = []
            
            if ctx.guild:
                local_guild_commands = self.bot.tree.get_commands(guild=ctx.guild)
                api_guild_commands = await self.bot.tree.fetch_commands(guild=ctx.guild)
            
            embed = discord.Embed(
                title="🔄 Command Sync Status",
                description="Current status of application commands",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Global Commands",
                value=f"{len(api_global_commands)} commands registered globally (API)\n"
                      f"{len(local_global_commands)} commands registered locally",
                inline=False
            )
            
            if ctx.guild:
                embed.add_field(
                    name=f"Guild Commands ({ctx.guild.name})",
                    value=f"{len(api_guild_commands)} commands registered in this guild (API)\n"
                          f"{len(local_guild_commands)} commands registered locally",
                    inline=False
                )
                if api_guild_commands:
                    cmd_list = "\n".join([f"• /{cmd.name}" for cmd in api_guild_commands])
                    embed.add_field(
                        name="Guild Command List (API)",
                        value=cmd_list if cmd_list else "No commands",
                        inline=False
                    )
                
                if local_guild_commands:
                    cmd_list = "\n".join([f"• /{cmd.name}" for cmd in local_guild_commands])
                    embed.add_field(
                        name="Guild Command List (Local)",
                        value=cmd_list if cmd_list else "No commands",
                        inline=False
                    )
            
            if api_global_commands:
                cmd_list = "\n".join([f"• /{cmd.name}" for cmd in api_global_commands])
                embed.add_field(
                    name="Global Command List (API)",
                    value=cmd_list if cmd_list else "No commands",
                    inline=False
                )
            
            if local_global_commands:
                cmd_list = "\n".join([f"• /{cmd.name}" for cmd in local_global_commands])
                embed.add_field(
                    name="Global Command List (Local)",
                    value=cmd_list if cmd_list else "No commands",
                    inline=False
                )
            
            embed.set_footer(text="Made By TheZ")
            await ctx.send(embed=embed)
            
        except Exception as e:
            tb = traceback.format_exc()
            error_embed = discord.Embed(
                title="❌ Status Check Failed",
                description=f"An error occurred while checking command status: {str(e)}",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Made By TheZ")
            await ctx.send(embed=error_embed)
            logger.error(f"Error checking sync status: {str(e)}\n{tb}")
    
    @commands.command(name="sync_copy")
    @commands.is_owner()
    async def sync_copy(self, ctx, source_guild_id: int, target_guild_id: Optional[int] = None):
        
        try:
            source_guild = self.bot.get_guild(source_guild_id)
            if not source_guild:
                await ctx.send(embed=discord.Embed(
                    title="❌ Source Guild Not Found",
                    description=f"Could not find source guild with ID {source_guild_id}",
                    color=discord.Color.red()
                ).set_footer(text="Made By TheZ"))
                return
            
            
            source_commands = await self.bot.tree.fetch_commands(guild=source_guild)
            logger.info(f"Found {len(source_commands)} commands in source guild {source_guild.name}")
            
            if not source_commands:
                await ctx.send(embed=discord.Embed(
                    title="❌ No Commands Found",
                    description=f"No commands found in source guild {source_guild.name}",
                    color=discord.Color.red()
                ).set_footer(text="Made By TheZ"))
                return
            
            if target_guild_id:
                target_guild = self.bot.get_guild(target_guild_id)
                if not target_guild:
                    await ctx.send(embed=discord.Embed(
                        title="❌ Target Guild Not Found",
                        description=f"Could not find target guild with ID {target_guild_id}",
                        color=discord.Color.red()
                    ).set_footer(text="Made By TheZ"))
                    return
                
                
                confirm_embed = discord.Embed(
                    title="⚠️ Confirm Command Copy",
                    description=f"Are you sure you want to copy {len(source_commands)} commands from **{source_guild.name}** to **{target_guild.name}**?\n\nThis will replace all existing commands in the target guild.\n\nReply with `yes` to confirm or `no` to cancel.",
                    color=discord.Color.gold()
                )
                confirm_embed.set_footer(text="Made By TheZ")
                await ctx.send(embed=confirm_embed)
                
                try:
                    
                    def check(m):
                        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["yes", "no"]
                    
                    response = await self.bot.wait_for("message", check=check, timeout=30.0)
                    if response.content.lower() != "yes":
                        await ctx.send(embed=discord.Embed(
                            title="🛑 Operation Cancelled",
                            description="Command copy cancelled.",
                            color=discord.Color.blue()
                        ).set_footer(text="Made By TheZ"))
                        return
                except asyncio.TimeoutError:
                    await ctx.send(embed=discord.Embed(
                        title="⏱️ Timed Out",
                        description="No confirmation received within 30 seconds. Operation cancelled.",
                        color=discord.Color.red()
                    ).set_footer(text="Made By TheZ"))
                    return
                
                
                self.bot.tree.clear_commands(guild=target_guild)
                await self.bot.tree.sync(guild=target_guild)
                
                
                
                
                synced = await self.bot.tree.sync(guild=target_guild)
                
                embed = discord.Embed(
                    title="✅ Commands Copied",
                    description=f"Successfully copied {len(synced)} commands from {source_guild.name} to {target_guild.name}.",
                    color=discord.Color.green()
                )
                embed.set_footer(text="Made By TheZ")
                
                await ctx.send(embed=embed)
                logger.info(f"Copied commands from guild {source_guild_id} to guild {target_guild_id}")
            else:
                
                confirm_embed = discord.Embed(
                    title="⚠️ Confirm Global Command Copy",
                    description=f"Are you sure you want to copy {len(source_commands)} commands from **{source_guild.name}** to **global commands**?\n\nThis will replace all existing global commands.\n\nReply with `yes` to confirm or `no` to cancel.",
                    color=discord.Color.gold()
                )
                confirm_embed.set_footer(text="Made By TheZ")
                await ctx.send(embed=confirm_embed)
                
                try:
                    
                    def check(m):
                        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["yes", "no"]
                    
                    response = await self.bot.wait_for("message", check=check, timeout=30.0)
                    if response.content.lower() != "yes":
                        await ctx.send(embed=discord.Embed(
                            title="🛑 Operation Cancelled",
                            description="Global command copy cancelled.",
                            color=discord.Color.blue()
                        ).set_footer(text="Made By TheZ"))
                        return
                except asyncio.TimeoutError:
                    await ctx.send(embed=discord.Embed(
                        title="⏱️ Timed Out",
                        description="No confirmation received within 30 seconds. Operation cancelled.",
                        color=discord.Color.red()
                    ).set_footer(text="Made By TheZ"))
                    return
                
                
                self.bot.tree.clear_commands()
                await self.bot.tree.sync()
                
                
                
                synced = await self.bot.tree.sync()
                
                embed = discord.Embed(
                    title="✅ Commands Copied Globally",
                    description=f"Successfully copied {len(synced)} commands from {source_guild.name} to global commands.",
                    color=discord.Color.green()
                )
                embed.set_footer(text="Made By TheZ")
                
                await ctx.send(embed=embed)
                logger.info(f"Copied commands from guild {source_guild_id} to global")
                
        except Exception as e:
            tb = traceback.format_exc()
            error_embed = discord.Embed(
                title="❌ Command Copy Failed",
                description=f"An error occurred while copying commands: {str(e)}",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Made By TheZ")
            await ctx.send(embed=error_embed)
            logger.error(f"Error copying commands: {str(e)}\n{tb}")
    
    @commands.command(name="reload_and_sync")
    @commands.is_owner()
    async def reload_and_sync(self, ctx, guild_id: Optional[int] = None):
        
        try:
            
            reloaded_extensions = []
            failed_extensions = []
            
            for extension in list(self.bot.extensions):
                try:
                    await self.bot.reload_extension(extension)
                    reloaded_extensions.append(extension)
                except Exception as e:
                    failed_extensions.append((extension, str(e)))
                    logger.error(f"Failed to reload extension {extension}: {str(e)}")
            
            logger.info(f"Reloaded {len(reloaded_extensions)} extensions")
            
            
            if guild_id:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    await ctx.send(embed=discord.Embed(
                        title="❌ Guild Not Found",
                        description=f"Could not find guild with ID {guild_id}",
                        color=discord.Color.red()
                    ).set_footer(text="Made By TheZ"))
                    return
                
                
                local_commands = self.bot.tree.get_commands(guild=guild)
                logger.info(f"Guild {guild.id} has {len(local_commands)} local commands before syncing")
                
                
                synced = await ctx.bot.tree.sync(guild=guild)
                
                embed = discord.Embed(
                    title="✅ Reload and Sync Complete",
                    description=f"Successfully reloaded {len(reloaded_extensions)} extensions and synced {len(synced)} commands to guild {guild.name}.",
                    color=discord.Color.green()
                )
                
                if failed_extensions:
                    failed_text = "\n".join([f"• {ext}: {err}" for ext, err in failed_extensions])
                    embed.add_field(
                        name="⚠️ Failed Extensions",
                        value=failed_text,
                        inline=False
                    )
            else:
                
                local_commands = self.bot.tree.get_commands()
                logger.info(f"Bot has {len(local_commands)} local global commands before syncing")
                
                
                synced = await ctx.bot.tree.sync()
                
                embed = discord.Embed(
                    title="✅ Reload and Sync Complete",
                    description=f"Successfully reloaded {len(reloaded_extensions)} extensions and synced {len(synced)} commands globally.",
                    color=discord.Color.green()
                )
                
                if failed_extensions:
                    failed_text = "\n".join([f"• {ext}: {err}" for ext, err in failed_extensions])
                    embed.add_field(
                        name="⚠️ Failed Extensions",
                        value=failed_text,
                        inline=False
                    )
            
            embed.set_footer(text="Made By TheZ")
            await ctx.send(embed=embed)
            
        except Exception as e:
            tb = traceback.format_exc()
            error_embed = discord.Embed(
                title="❌ Reload and Sync Failed",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Made By TheZ")
            await ctx.send(embed=error_embed)
            logger.error(f"Error in reload_and_sync: {str(e)}\n{tb}")
    
    @commands.command(name="sync_debug")
    @commands.is_owner()
    async def sync_debug(self, ctx, guild_id: Optional[int] = None):
        
        try:
            
            guild = None
            if guild_id:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    await ctx.send(embed=discord.Embed(
                        title="❌ Guild Not Found",
                        description=f"Could not find guild with ID {guild_id}",
                        color=discord.Color.red()
                    ).set_footer(text="Made By TheZ"))
                    return
            elif ctx.guild:
                guild = ctx.guild
            
            local_global_commands = self.bot.tree.get_commands()
            local_guild_commands = []
            
            if guild:
                local_guild_commands = self.bot.tree.get_commands(guild=guild)
            
            logger.info(f"Bot ID: {self.bot.user.id}")
            logger.info(f"Bot Application ID: {self.bot.application_id}")
            logger.info(f"Local global commands: {[cmd.name for cmd in local_global_commands]}")
            
            if guild:
                logger.info(f"Guild ID: {guild.id}")
                logger.info(f"Local guild commands: {[cmd.name for cmd in local_guild_commands]}")
            
            embed = discord.Embed(
                title="🔍 Sync Debug Information",
                description="Detailed command sync information",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Bot Information",
                value=f"Bot ID: {self.bot.user.id}\n"
                      f"Application ID: {self.bot.application_id}",
                inline=False
            )
            
            embed.add_field(
                name="Local Global Commands",
                value=f"Count: {len(local_global_commands)}\n"
                      f"Names: {', '.join([cmd.name for cmd in local_global_commands]) if local_global_commands else 'None'}",
                inline=False
            )
            
            if guild:
                embed.add_field(
                    name=f"Local Guild Commands ({guild.name})",
                    value=f"Count: {len(local_guild_commands)}\n"
                          f"Names: {', '.join([cmd.name for cmd in local_guild_commands]) if local_guild_commands else 'None'}",
                    inline=False
                )
            
            try:
                api_global_commands = await self.bot.tree.fetch_commands()
                embed.add_field(
                    name="API Global Commands",
                    value=f"Count: {len(api_global_commands)}\n"
                          f"Names: {', '.join([cmd.name for cmd in api_global_commands]) if api_global_commands else 'None'}",
                    inline=False
                )
                
                if guild:
                    api_guild_commands = await self.bot.tree.fetch_commands(guild=guild)
                    embed.add_field(
                        name=f"API Guild Commands ({guild.name})",
                        value=f"Count: {len(api_guild_commands)}\n"
                              f"Names: {', '.join([cmd.name for cmd in api_guild_commands]) if api_guild_commands else 'None'}",
                        inline=False
                    )
            except Exception as api_error:
                embed.add_field(
                    name="⚠️ API Fetch Error",
                    value=f"Error fetching API commands: {str(api_error)}",
                    inline=False
                )
                logger.error(f"Error fetching API commands: {str(api_error)}")
            
            if guild:
                try:
                    synced = await self.bot.tree.sync(guild=guild)
                    embed.add_field(
                        name="Sync Result (Guild)",
                        value=f"Synced {len(synced)} commands to guild {guild.name}\n"
                              f"Names: {', '.join([cmd.name for cmd in synced]) if synced else 'None'}",
                        inline=False
                    )
                except Exception as sync_error:
                    embed.add_field(
                        name="Sync Error (Guild)",
                        value=f"Error: {str(sync_error)}",
                        inline=False
                    )
            else:
                try:
                    synced = await self.bot.tree.sync()
                    embed.add_field(
                        name="Sync Result (Global)",
                        value=f"Synced {len(synced)} commands globally\n"
                              f"Names: {', '.join([cmd.name for cmd in synced]) if synced else 'None'}",
                        inline=False
                    )
                except Exception as sync_error:
                    embed.add_field(
                        name="Sync Error (Global)",
                        value=f"Error: {str(sync_error)}",
                        inline=False
                    )
            
            embed.set_footer(text="Made By TheZ")
            await ctx.send(embed=embed)
            
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Detailed error in sync_debug: {str(e)}\n{tb}")
            error_embed = discord.Embed(
                title="❌ Debug Failed",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Made By TheZ")
            await ctx.send(embed=error_embed)

def setup(bot):
    cog = SyncCommands(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog


