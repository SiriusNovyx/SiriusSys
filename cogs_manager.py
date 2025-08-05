import asyncio
import os
import discord
from discord.ext import commands
import importlib
import sys
import traceback

class CogManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    def get_cog_names(self):
        
        return sorted(self.bot.cogs.keys())
        
    @commands.command(name="reload")
    @commands.is_owner()
    async def reload_cogs(self, ctx, cog_name=None):

        if cog_name:
            
            await self.reload_specific_cog(ctx, cog_name)
        else:
        
            await self.reload_all_cogs(ctx)
    
    async def reload_specific_cog(self, ctx, cog_name):

        embed = discord.Embed(
            title="🔄 Cog Reload",
            description=f"Attempting to reload cog: `{cog_name}`",
            color=discord.Color.blue()
        )
        
        message = await ctx.send(embed=embed)
        
        try:
            
            actual_cog_name = None
            for loaded_cog in self.bot.cogs:
                if loaded_cog.lower() == cog_name.lower():
                    actual_cog_name = loaded_cog
                    break
            
            if not actual_cog_name:
                embed.description = f"❌ Cog `{cog_name}` is not loaded."
                embed.color = discord.Color.red()
                await message.edit(embed=embed)
                return
            
            cog_instance = self.bot.cogs[actual_cog_name]
            cog_class = cog_instance.__class__
            
            await self.bot.remove_cog(actual_cog_name)
            
            new_cog = cog_class(self.bot)
            
            await self.bot.add_cog(new_cog)
            
            embed.description = f"✅ Successfully reloaded cog: `{actual_cog_name}`"
            embed.color = discord.Color.green()
            
        except Exception as e:
            
            embed.description = f"❌ Failed to reload cog: `{cog_name}`"
            embed.color = discord.Color.red()
            embed.add_field(
                name="Error",
                value=f"```py\n{type(e).__name__}: {str(e)}\n```",
                inline=False
            )
            
            traceback_text = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            if len(traceback_text) > 1024:
                traceback_text = traceback_text[:1021] + "..."
                
            embed.add_field(
                name="Traceback",
                value=f"```py\n{traceback_text}\n```",
                inline=False
            )
        
        await message.edit(embed=embed)
    
    async def reload_all_cogs(self, ctx):
        embed = discord.Embed(
            title="🔄 Cog Reload",
            description="Reloading all cogs...",
            color=discord.Color.blue()
        )
        
        message = await ctx.send(embed=embed)
        
        success_cogs = []
        failed_cogs = {}
        
        cogs_to_reload = list(self.bot.cogs.items())
        
        for cog_name, cog_instance in cogs_to_reload:
            try:
               
                if cog_name == self.__class__.__name__:
                    continue
                    
                cog_class = cog_instance.__class__
                
                await self.bot.remove_cog(cog_name)
                
                new_cog = cog_class(self.bot)
                
                await self.bot.add_cog(new_cog)
                
                success_cogs.append(cog_name)
            except Exception as e:
                failed_cogs[cog_name] = f"{type(e).__name__}: {str(e)}"
        
        if success_cogs:
        
            cogs_per_field = 15
            for i in range(0, len(success_cogs), cogs_per_field):
                field_cogs = success_cogs[i:i+cogs_per_field]
                embed.add_field(
                    name=f"✅ Successfully Reloaded ({i+1}-{i+len(field_cogs)})",
                    value="```\n" + "\n".join(field_cogs) + "```",
                    inline=False
                )
        
        if failed_cogs:
            failed_text = "\n".join([f"{cog}: {error}" for cog, error in failed_cogs.items()])
            if len(failed_text) > 1024:
                failed_text = failed_text[:1021] + "..."
                
            embed.add_field(
                name="❌ Failed to Reload",
                value="```\n" + failed_text + "```",
                inline=False
            )
        
        if not failed_cogs:
            embed.color = discord.Color.green()
            embed.description = f"✅ Successfully reloaded all {len(success_cogs)} cogs!"
        elif not success_cogs:
            embed.color = discord.Color.red()
            embed.description = f"❌ Failed to reload all {len(failed_cogs)} cogs!"
        else:
            embed.color = discord.Color.gold()
            embed.description = f"⚠️ Reloaded {len(success_cogs)} cogs, but {len(failed_cogs)} failed."
        
        await message.edit(embed=embed)
    
    @commands.command(name="load")
    @commands.is_owner()
    async def load_cog(self, ctx, cog_name):
        embed = discord.Embed(
            title="📥 Cog Load",
            description=f"Attempting to load cog: `{cog_name}`",
            color=discord.Color.blue()
        )
        
        message = await ctx.send(embed=embed)
        
        try:
            
            extensions_dir = "Extensions"
            if not os.path.exists(extensions_dir):
                os.makedirs(extensions_dir, exist_ok=True)
                embed.description = f"❌ Extensions directory created. Please add your cog files to the `{extensions_dir}` folder."
                embed.color = discord.Color.red()
                await message.edit(embed=embed)
                return
            
            if not cog_name.endswith('.py'):
                cog_filename = f"{cog_name}.py"
            else:
                cog_filename = cog_name
                cog_name = cog_name[:-3]  
            
            cog_path = os.path.join(extensions_dir, cog_filename)
            if not os.path.exists(cog_path):
                embed.description = f"❌ Could not find file `{cog_filename}` in the Extensions directory."
                embed.add_field(
                    name="Expected Location",
                    value=f"`{cog_path}`",
                    inline=False
                )
                embed.add_field(
                    name="Available Extensions",
                    value=self.list_available_extensions(),
                    inline=False
                )
                embed.color = discord.Color.red()
                await message.edit(embed=embed)
                return
            
            for loaded_cog in self.bot.cogs.values():
                module_name = loaded_cog.__module__
                if module_name.endswith(cog_name):
                    embed.description = f"❌ Cog `{cog_name}` is already loaded."
                    embed.color = discord.Color.red()
                    await message.edit(embed=embed)
                    return
            
            extensions_abs_path = os.path.abspath(extensions_dir)
            if extensions_abs_path not in sys.path:
                sys.path.insert(0, extensions_abs_path)
            
            try:
                
                module = importlib.import_module(cog_name)
                importlib.reload(module)
            except Exception as e:
                embed.description = f"❌ Error importing module `{cog_name}`."
                embed.add_field(
                    name="Error",
                    value=f"```py\n{type(e).__name__}: {str(e)}\n```",
                    inline=False
                )
                embed.color = discord.Color.red()
                await message.edit(embed=embed)
                return
            
            if not hasattr(module, 'setup'):
                embed.description = f"❌ Module `{cog_name}` does not have a setup function."
                embed.add_field(
                    name="Required Format",
                    value=(
                        "Your cog file must include a setup function:\n"
                        "```py\ndef setup(bot):\n    bot.add_cog(YourCog(bot))\n```"
                    ),
                    inline=False
                )
                embed.color = discord.Color.red()
                await message.edit(embed=embed)
                return
            
            try:
              
                if asyncio.iscoroutinefunction(module.setup):
                    await module.setup(self.bot)
                else:
                    module.setup(self.bot)
                
                loaded_cog_name = None
                for name, cog in self.bot.cogs.items():
                    if cog.__module__ == cog_name:
                        loaded_cog_name = name
                        break
                
                extension_loader = self.bot.get_cog('ExtensionLoader')
                if extension_loader and hasattr(extension_loader, 'loaded_extensions'):
                    extension_path = f"Extensions.{cog_name}"
                    if extension_path not in extension_loader.loaded_extensions:
                        extension_loader.loaded_extensions.append(extension_path)
                
                embed.description = f"✅ Successfully loaded cog: `{loaded_cog_name or cog_name}`"
                embed.color = discord.Color.green()
                
                new_commands = []
                if loaded_cog_name:
                    cog = self.bot.get_cog(loaded_cog_name)
                    if cog:
                        for cmd in cog.get_commands():
                            new_commands.append(f"`!{cmd.name}`")
                
                if new_commands:
                    embed.add_field(
                        name="New Commands Available",
                        value=", ".join(new_commands),
                        inline=False
                    )
                
            except Exception as e:
                embed.description = f"❌ Error during setup of `{cog_name}`."
                embed.add_field(
                    name="Error",
                    value=f"```py\n{type(e).__name__}: {str(e)}\n```",
                    inline=False
                )
                
                traceback_text = "".join(traceback.format_exception(type(e), e, e.__traceback__))
                if len(traceback_text) > 1024:
                    traceback_text = traceback_text[:1021] + "..."
                    
                embed.add_field(
                    name="Traceback",
                    value=f"```py\n{traceback_text}\n```",
                    inline=False
                )
                embed.color = discord.Color.red()
        
        except Exception as e:
            
            embed.description = f"❌ Unexpected error loading cog: `{cog_name}`"
            embed.color = discord.Color.red()
            embed.add_field(
                name="Error",
                value=f"```py\n{type(e).__name__}: {str(e)}\n```",
                inline=False
            )
        
        await message.edit(embed=embed)

    def list_available_extensions(self):
       
        extensions_dir = "Extensions"
        if not os.path.exists(extensions_dir):
            return "No Extensions directory found."
        
        py_files = [f for f in os.listdir(extensions_dir) if f.endswith('.py')]
        if not py_files:
            return "No Python files found in the Extensions directory."
        
        return "```\n" + "\n".join(py_files) + "\n```"

    @commands.command(name="unload")
    @commands.is_owner()
    async def unload_cog(self, ctx, cog_name):
        embed = discord.Embed(
            title="📤 Cog Unload",
            description=f"Attempting to unload cog: `{cog_name}`",
            color=discord.Color.blue()
        )
        
        message = await ctx.send(embed=embed)
        
        try:
            
            actual_cog_name = None
            for loaded_cog in self.bot.cogs:
                if loaded_cog.lower() == cog_name.lower():
                    actual_cog_name = loaded_cog
                    break
            
            if not actual_cog_name:
                embed.description = f"❌ Cog `{cog_name}` is not loaded."
                embed.color = discord.Color.red()
                await message.edit(embed=embed)
                return
            
            if actual_cog_name == self.__class__.__name__:
                embed.description = f"❌ Cannot unload the CogManager cog."
                embed.color = discord.Color.red()
                await message.edit(embed=embed)
                return
            
            cog_instance = self.bot.get_cog(actual_cog_name)
            module_name = cog_instance.__module__ if cog_instance else None
            
            await self.bot.remove_cog(actual_cog_name)
            
            if module_name:
                extension_loader = self.bot.get_cog('ExtensionLoader')
                if extension_loader and hasattr(extension_loader, 'loaded_extensions'):
                    extension_path = f"Extensions.{module_name.split('.')[-1]}"
                    if extension_path in extension_loader.loaded_extensions:
                        extension_loader.loaded_extensions.remove(extension_path)
            
            embed.description = f"✅ Successfully unloaded cog: `{actual_cog_name}`"
            embed.color = discord.Color.green()
            
        except Exception as e:
           
            embed.description = f"❌ Failed to unload cog: `{cog_name}`"
            embed.color = discord.Color.red()
            embed.add_field(
                name="Error",
                value=f"```py\n{type(e).__name__}: {str(e)}\n```",
                inline=False
            )
        
        await message.edit(embed=embed)

    @commands.command(name="listcogs")
    @commands.is_owner()
    async def list_cogs(self, ctx):
        embed = discord.Embed(
            title="📋 Cog List",
            description="Here are all the currently loaded cogs:",
            color=discord.Color.blue()
        )
        
        loaded_cogs = self.get_cog_names()
        
        extension_loader = self.bot.get_cog('ExtensionLoader')
        extension_list = []
        if extension_loader and hasattr(extension_loader, 'loaded_extensions'):
            extension_list = [ext.split('.')[-1] for ext in extension_loader.loaded_extensions]
        
        if loaded_cogs:
           
            cogs_per_field = 15
            for i in range(0, len(loaded_cogs), cogs_per_field):
                field_cogs = loaded_cogs[i:i+cogs_per_field]
                embed.add_field(
                    name=f"✅ Loaded Cogs ({i+1}-{i+len(field_cogs)})",
                    value="```\n" + "\n".join(field_cogs) + "```",
                    inline=False
                )
        else:
            embed.add_field(
                name="✅ Loaded Cogs",
                value="```\nNo cogs currently loaded```",
                inline=False
            )
        
        if extension_list:
            embed.add_field(
                name="📦 Loaded Extensions",
                value="```\n" + "\n".join(extension_list) + "```",
                inline=False
            )
        
        embed.set_footer(text="ZygnalBot Made By TheHolyoneZ")
        
        await ctx.send(embed=embed)


    @commands.command(name="coghelp")
    @commands.is_owner()
    async def manager_help(self, ctx):
       
        embed = discord.Embed(
            title="🔧 CogManager Help",
            description="Commands for managing bot cogs without restarting",
            color=discord.Color.blue()
        )
        embed.set_footer(text="ZygnalBot Made By TheHolyoneZ")
        
        embed.add_field(
            name="!reload [cog_name]",
            value=(
                "**Description:** Reload all cogs or a specific cog\n"
                "**Usage:**\n"
                "• `!reload` - Reloads all currently loaded cogs\n"
                "• `!reload ModerationCommands` - Reloads only the ModerationCommands cog\n"
                "**Notes:** Useful for applying changes to cog code without restarting the bot"
            ),
            inline=False
        )
        
        embed.add_field(
            name="!load <module name>",
            value=(
                "**Description:** Load a cog that is not currently loaded\n"
                "**Usage:**\n"
                "• `!load Extension` - Loads the Extension.py from the extension folder\n"
                "**Notes:** Useful for loading new cogs without restarting the bot/Adding ur own cogs\n Check out https://zygnalbot.info/CogHelp.html for Help"
            )
        )

        embed.add_field(
            name="!unload <cog_name>",
            value=(
                "**Description:** Unload a currently loaded cog\n"
                "**Usage:**\n"
                "• `!unload LoveCommands` - Unloads the LoveCommands cog\n"
                "**Notes:** You cannot unload the CogManager itself"
            ),
            inline=False
        )
        
        embed.add_field(
            name="!listcogs",
            value=(
                "**Description:** List all loaded cogs\n"
                "**Usage:**\n"
                "• `!listcogs` - Shows which cogs are currently loaded\n"
                "**Notes:** Helps identify which cogs can be reloaded or unloaded"
            ),
            inline=False
        )
        
        
        embed.add_field(
            name="!coghelp",
            value=(
                "**Description:** Display this help message\n"
                "**Usage:**\n"
                "• `!coghelp` - Shows detailed information about CogManager commands\n"
                "**Notes:** You're looking at it right now!"
            ),
            inline=False
        )

        
        
        embed.add_field(
            name="📝 General Notes",
            value=(
                "• All commands are restricted to the bot owner only\n"
                "• Cog names are case-insensitive for convenience\n"
                "• Error messages include detailed information to help with debugging\n"
                "• For more Infos Check out: https://zygnalbot.info/CogHelp.html"
                
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(CogManager(bot))
