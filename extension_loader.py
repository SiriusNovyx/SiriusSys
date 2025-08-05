import os
import sys
import asyncio
import importlib
import traceback
from pathlib import Path
import shutil

import discord
from discord.ext import commands
from dotenv import load_dotenv

import logging
import colorama
from colorama import Fore, Style, Back

colorama.init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    FORMATS = {
        logging.DEBUG: Fore.CYAN + "%(asctime)s - %(levelname)s - %(message)s" + Style.RESET_ALL,
        logging.INFO: Fore.GREEN + "%(asctime)s - %(levelname)s - %(message)s" + Style.RESET_ALL,
        logging.WARNING: Fore.YELLOW + "%(asctime)s - %(levelname)s - %(message)s" + Style.RESET_ALL,
        logging.ERROR: Fore.RED + "%(asctime)s - %(levelname)s - %(message)s" + Style.RESET_ALL,
        logging.CRITICAL: Back.RED + Fore.WHITE + "%(asctime)s - %(levelname)s - %(message)s" + Style.RESET_ALL
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


root_logger = logging.getLogger()
root_logger.handlers = []
root_handler = logging.StreamHandler()
root_handler.setFormatter(ColoredFormatter())
root_logger.addHandler(root_handler)
root_logger.setLevel(logging.WARNING)

logger = logging.getLogger('extension_loader')
logger.setLevel(logging.INFO)
logger.propagate = False
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter())
logger.addHandler(handler)


class ExtensionLoader(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.extensions_dir = "Extensions"
        self.loaded_extensions: set[str] = set()

        load_dotenv()
        self.auto_load = os.getenv("AutoExtension", "Off").lower() == "on"

    @commands.Cog.listener()
    async def on_ready(self):
        if self.auto_load:
            await self.load_all_extensions()

    def _normalize_basename_candidates(self, raw: str) -> set[str]:
        base = raw.strip()
        return {
            base,
            base.replace(" ", "_"),
            base.replace("_", " "),
        }

    def _derive_file_and_module(self, raw_name: str) -> tuple[str, str, Path]:

        ext_dir = Path(self.extensions_dir)
        if not ext_dir.exists():
            raise FileNotFoundError(f"Extensions-Ordner '{self.extensions_dir}' existiert nicht.")

        base_input = raw_name
        if base_input.lower().endswith(".py"):
            base_input = base_input[:-3]

        candidates = self._normalize_basename_candidates(base_input)
        found_file: Path | None = None
        module_base = None

        for base in candidates:
            candidate = ext_dir / f"{base}.py"
            if candidate.exists():
                found_file = candidate
                module_base = base.replace(" ", "_")
                break

        if not found_file or module_base is None:
            raise FileNotFoundError(f"Keine Extension-Datei gefunden für '{raw_name}' (z.B. erwartet 'server stats.py').")

        if not module_base.isidentifier():
            safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in module_base)
            module_base = safe

        module_path = f"{self.extensions_dir}.{module_base}"
        filename = found_file.name  
        return filename, module_path, found_file

    async def load_all_extensions(self):
        logger.info(f"{Fore.CYAN}╔══════════════════════════════════════╗")
        logger.info(f"{Fore.CYAN}║      Auto-loading Extensions...      ║")
        logger.info(f"{Fore.CYAN}╚══════════════════════════════════════╝")

        ext_dir = Path(self.extensions_dir)
        if not ext_dir.exists():
            logger.warning(f"Extensions directory '{self.extensions_dir}' not found.")
            return

        extension_files = [f for f in os.listdir(self.extensions_dir)
                           if f.endswith('.py') and not f.startswith('_')]

        success_count = 0
        fail_count = 0

        for extension_file in extension_files:
            try:
                success = await self.load_extension(extension_file)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception:
                fail_count += 1
                logger.error(f"{Fore.RED}✗ Failed to load: {extension_file}")
                logger.error(traceback.format_exc())

        total = success_count + fail_count
        logger.info(f"{Fore.CYAN}╔══════════════════════════════════════╗")
        logger.info(f"{Fore.CYAN}║      Extension Loading Summary       ║")
        logger.info(f"{Fore.CYAN}╠══════════════════════════════════════╣")
        logger.info(f"{Fore.CYAN}║ {Fore.GREEN}Loaded: {success_count}{Fore.CYAN} | {Fore.RED}Failed: {fail_count}{Fore.CYAN} | Total: {total} ║")
        logger.info(f"{Fore.CYAN}╚══════════════════════════════════════╝")

    async def load_extension(self, extension_name: str):
        try:
            filename, module_path, file_path = self._derive_file_and_module(extension_name)
            spec = importlib.util.spec_from_file_location(module_path, file_path)
            if not spec or not spec.loader:
                raise FileNotFoundError(f"Spec konnte nicht erstellt werden für {filename}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_path] = module
            spec.loader.exec_module(module)

            if hasattr(module, 'setup'):
                if asyncio.iscoroutinefunction(module.setup):
                    await module.setup(self.bot)
                else:
                    module.setup(self.bot)
                    logger.warning(f"Extension {filename} uses a synchronous setup function. Consider updating to 'async def setup'.")
                self.loaded_extensions.add(filename)
                logger.info(f"{Fore.GREEN}✓ Successfully loaded: {filename}")
                return True
            else:
                raise ValueError(f"Extension {filename} has no setup function")
        except Exception as e:
            logger.error(f"{Fore.RED}Error loading {extension_name}: {e}")
            return False

    async def unload_extension(self, extension_name: str):
        try:
            filename, module_path, file_path = self._derive_file_and_module(extension_name)

            for name, cog in list(self.bot.cogs.items()):
                if hasattr(cog, '__module__') and cog.__module__ == module_path:
                    await self.bot.remove_cog(name)

            if module_path in sys.modules:
                del sys.modules[module_path]

            self.loaded_extensions.discard(filename)
            logger.info(f"{Fore.GREEN}✓ Unloaded: {filename}")
            return True
        except Exception as e:
            logger.error(f"{Fore.RED}Error unloading {extension_name}: {e}")
            return False

    async def reload_extension(self, extension_name: str):
        try:
            filename, module_path, file_path = self._derive_file_and_module(extension_name)

            if filename in self.loaded_extensions:
                unload_success = await self.unload_extension(extension_name)
                if not unload_success:
                    logger.error(f"{Fore.RED}Failed to unload {filename} during reload.")
                    return False

            return await self.load_extension(extension_name)
        except Exception as e:
            logger.error(f"{Fore.RED}Error reloading {extension_name}: {e}")
            return False

    async def remove_extension(self, extension_name: str, backup: bool = True) -> bool:
        try:
            filename, module_path, file_path = self._derive_file_and_module(extension_name)

            if filename in self.loaded_extensions:
                unload_success = await self.unload_extension(extension_name)
                if not unload_success:
                    logger.error(f"{Fore.RED}Konnte {filename} nicht unloaden, Abbruch des Löschens.")
                    return False
            else:
                if module_path in sys.modules:
                    del sys.modules[module_path]

            if not file_path.exists():
                logger.warning(f"{Fore.YELLOW}Extension-Datei {file_path} existiert nicht mehr.")
                self.loaded_extensions.discard(filename)
                return True

            if backup:
                target = file_path.with_suffix(".py.bak")
                shutil.move(str(file_path), str(target))
                logger.info(f"{Fore.GREEN}Extension-Datei gesichert: {target.name}")
            else:
                file_path.unlink()
                logger.info(f"{Fore.GREEN}Extension-Datei gelöscht: {filename}")

            self.loaded_extensions.discard(filename)
            return True
        except Exception as e:
            logger.error(f"{Fore.RED}Fehler beim Entfernen der Extension {extension_name}: {e}")
            return False

    @commands.group(name="extension", aliases=["ext"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def extension_group(self, ctx):
        embed = discord.Embed(
            title="🧩 Extension Management",
            description="Use these commands to manage bot extensions",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Commands",
            value="`!extension list` - List all extensions\n"
                  "`!extension load <name>` - Load an extension\n"
                  "`!extension unload <name>` - Unload an extension\n"
                  "`!extension reload <name>` - Reload an extension\n"
                  "`!extension remove <name>` - Remove (unload + delete with backup)\n"
                  "`!extension reloadall` - Reload all extensions",
            inline=False
        )
        await ctx.send(embed=embed)

    @extension_group.command(name="list")
    @commands.has_permissions(administrator=True)
    async def list_extensions(self, ctx):
        if not os.path.exists(self.extensions_dir):
            await ctx.send("❌ Extensions directory not found.")
            return

        available_extensions = [f for f in os.listdir(self.extensions_dir)
                                if f.endswith('.py') and not f.startswith('_')]

        embed = discord.Embed(
            title="🧩 Extensions Status",
            description="List of available and loaded extensions",
            color=discord.Color.blue()
        )

        loaded_list = ""
        for ext in sorted(self.loaded_extensions):
            ext_name = ext[:-3]
            loaded_list += f"✅ {ext_name}\n"
        if loaded_list:
            embed.add_field(name="Loaded Extensions", value=loaded_list, inline=False)
        else:
            embed.add_field(name="Loaded Extensions", value="No extensions loaded", inline=False)

        not_loaded = [ext for ext in available_extensions if ext not in self.loaded_extensions]
        not_loaded_list = ""
        for ext in sorted(not_loaded):
            not_loaded_list += f"❌ {ext[:-3]}\n"
        if not_loaded_list:
            embed.add_field(name="Available Extensions", value=not_loaded_list, inline=False)

        embed.set_footer(text=f"Auto-loading is {'enabled' if self.auto_load else 'disabled'}")
        await ctx.send(embed=embed)

    @extension_group.command(name="load")
    @commands.has_permissions(administrator=True)
    async def load_extension_cmd(self, ctx, *, extension_name: str):
        if extension_name.lower().endswith(".py"):
            extension_name = extension_name[:-3]
       
        if any(extension_name == (e[:-3]).replace("_", " ") or extension_name == (e[:-3]) for e in self.loaded_extensions):
            await ctx.send(f"❌ Extension `{extension_name}` is already loaded.")
            return

        success = await self.load_extension(extension_name)
        if success:
            await ctx.send(f"✅ Successfully loaded extension `{extension_name}`.")
        else:
            await ctx.send(f"❌ Failed to load extension `{extension_name}`. Check logs for details.")

    @extension_group.command(name="unload")
    @commands.has_permissions(administrator=True)
    async def unload_extension_cmd(self, ctx, *, extension_name: str):
        if extension_name.lower().endswith(".py"):
            extension_name = extension_name[:-3]
        if not any(extension_name == (e[:-3]).replace("_", " ") or extension_name == (e[:-3]) for e in self.loaded_extensions):
            await ctx.send(f"❌ Extension `{extension_name}` is not loaded.")
            return

        success = await self.unload_extension(extension_name)
        if success:
            await ctx.send(f"✅ Successfully unloaded extension `{extension_name}`.")
        else:
            await ctx.send(f"❌ Failed to unload extension `{extension_name}`. Check logs for details.")

    @extension_group.command(name="reload")
    @commands.has_permissions(administrator=True)
    async def reload_extension_cmd(self, ctx, *, extension_name: str):
        if extension_name.lower().endswith(".py"):
            extension_name = extension_name[:-3]
        if not any(extension_name == (e[:-3]).replace("_", " ") or extension_name == (e[:-3]) for e in self.loaded_extensions):
            await ctx.send(f"❌ Extension `{extension_name}` is not loaded. Use `!extension load {extension_name}` first.")
            return

        success = await self.reload_extension(extension_name)
        if success:
            await ctx.send(f"✅ Successfully reloaded extension `{extension_name}`.")
        else:
            await ctx.send(f"❌ Failed to reload extension `{extension_name}`. Check logs for details.")

    @extension_group.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def remove_extension_cmd(self, ctx, *, extension_name: str):
        if extension_name.lower().endswith(".py"):
            extension_name = extension_name[:-3]

        if not any(extension_name == (e[:-3]).replace("_", " ") or extension_name == (e[:-3]) for e in self.loaded_extensions):
            await ctx.send(f"⚠️ Extension `{extension_name}` war nicht geladen. Versuche trotzdem zu entfernen.")
        success = await self.remove_extension(extension_name, backup=True)
        if success:
            await ctx.send(f"🗑️ Extension `{extension_name}` wurde entfernt (Backup erstellt).")
        else:
            await ctx.send(f"❌ Konnte Extension `{extension_name}` nicht entfernen. Schau in die Logs.")

    @extension_group.command(name="reloadall")
    @commands.has_permissions(administrator=True)
    async def reload_all_extensions(self, ctx):
        if not self.loaded_extensions:
            await ctx.send("❌ No extensions are currently loaded.")
            return

        extensions_to_reload = list(self.loaded_extensions)
        success_count = 0
        fail_count = 0

        for extension in extensions_to_reload:
          
            name_no_ext = extension[:-3]
            success = await self.reload_extension(name_no_ext)
            if success:
                success_count += 1
            else:
                fail_count += 1

        await ctx.send(f"✅ Reloaded {success_count} extensions. Failed: {fail_count}")


def configure_all_loggers():
    for name, logger_instance in logging.Logger.manager.loggerDict.items():
        if isinstance(logger_instance, logging.Logger):
            logger_instance.handlers = []
            logger_instance.propagate = False
            custom_handler = logging.StreamHandler()
            custom_handler.setFormatter(ColoredFormatter())
            logger_instance.addHandler(custom_handler)


configure_all_loggers()


async def setup(bot):
    await bot.add_cog(ExtensionLoader(bot))
