import os
import asyncio
import json
import discord
from discord.ext import commands
from colorama import Fore, Style, init
from datetime import datetime

init()

class AutoConfigLoader(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_folder = "Normal_Config"
        self.ensure_config_folder_exists()
        
    def ensure_config_folder_exists(self):
       
        if not os.path.exists(self.config_folder):
            os.makedirs(self.config_folder)
            print(f"{Fore.YELLOW}[CONFIG] {Fore.WHITE}Created config folder: {self.config_folder}{Style.RESET_ALL}")
    
    def get_latest_config(self):
       
        if not os.path.exists(self.config_folder):
            return None
            
        config_files = [f for f in os.listdir(self.config_folder) 
                       if f.endswith('.json') 
                       and os.path.isfile(os.path.join(self.config_folder, f))]
        
        if not config_files:
            return None
            
        latest_file = max(config_files, 
                          key=lambda f: os.path.getmtime(os.path.join(self.config_folder, f)))
        
        return os.path.join(self.config_folder, latest_file)
    
    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(5)
        
        print(f"\n{Fore.CYAN}╔{'═' * 50}╗")
        print(f"║{' ' * 50}║")
        print(f"║{Fore.WHITE}  🔄 Auto Config Loader is active!{' ' * 19}{Fore.CYAN}║")
        print(f"║{Fore.WHITE}  📁 Looking for config files in: {Fore.YELLOW}{self.config_folder}{' ' * (19 - len(self.config_folder))}{Fore.CYAN}║")
        print(f"║{' ' * 50}║")
        print(f"╚{'═' * 50}╝{Style.RESET_ALL}")
        
        latest_config = self.get_latest_config()
        if latest_config:
            print(f"{Fore.CYAN}[CONFIG] Found config file: {latest_config}{Style.RESET_ALL}")
            
            target_channel = None
            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        target_channel = channel
                        break
                if target_channel:
                    break
            
            try:
               
                class CustomContext:
                    def __init__(self, bot, channel, guild):
                        self.bot = bot
                        self.channel = channel
                        self.guild = guild
                        self.message = type('obj', (object,), {
                            'attachments': [],
                            'author': guild.me
                        })
                        
                    async def send(self, content=None, embed=None):
                        return await self.channel.send(content=content, embed=embed)
                
                ctx = CustomContext(self.bot, target_channel, target_channel.guild)
                
                class CustomAttachment:
                    def __init__(self, filename, content):
                        self.filename = filename
                        self._content = content
                        
                    async def read(self):
                        return self._content
                
                with open(latest_config, 'rb') as f:
                    config_content = f.read()
                
                attachment = CustomAttachment(os.path.basename(latest_config), config_content)
                
                ctx.message.attachments = [attachment]
                
                import_cmd = self.bot.get_command('importconfig')
                
                if import_cmd:
                    
                    await import_cmd(ctx)
                    print(f"{Fore.GREEN}[CONFIG] Successfully executed importconfig with {os.path.basename(latest_config)}{Style.RESET_ALL}")
                else:
                
                    print(f"{Fore.RED}[CONFIG] Command 'importconfig' not found{Style.RESET_ALL}")
                    
                    if target_channel:
                        await target_channel.send(
                            f"❌ **Auto Config Loader**: Could not find the 'importconfig' command. "
                            f"Please manually import the configuration file."
                        )
                        await target_channel.send(file=discord.File(latest_config))
                
            except Exception as e:
                print(f"{Fore.RED}[CONFIG ERROR] Failed to auto-load config: {e}{Style.RESET_ALL}")
                
                if target_channel:
                    await target_channel.send(f"❌ **Error loading configuration**: {str(e)}")
                    
                    await target_channel.send(
                        "Here's the configuration file for manual import:",
                        file=discord.File(latest_config)
                    )
        else:
            print(f"{Fore.YELLOW}[CONFIG] No configuration files found in {self.config_folder}{Style.RESET_ALL}")

async def setup(bot):
    await bot.add_cog(AutoConfigLoader(bot))
