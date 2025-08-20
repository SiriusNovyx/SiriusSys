import discord
from discord.ext import commands
import aiohttp
import json
import os
from datetime import datetime, timedelta

class UpdateChecker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.version = "V7.9.7"  
        self.config_path = "data/update_config.json"
        self.update_url = "https://zygnalbot.de/versions/api/update.php"
        self.check_cooldown = timedelta(hours=4)  
        self.load_config()
        
    def load_config(self):
       
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.last_check = datetime.fromisoformat(config.get('last_check')) if config.get('last_check') else None
                    self.latest_version = config.get('latest_version')
                    self.download_url = config.get('download_url')
            except Exception as e:
                print(f"Error loading update config: {e}")
                self.last_check = None
                self.latest_version = None
                self.download_url = "https://zygnalbot.de"
        else:
            self.last_check = None
            self.latest_version = None
            self.download_url = "https://zygnalbot.de"
                
    def save_config(self):
        
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        config = {
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'latest_version': self.latest_version,
            'download_url': self.download_url
        }
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving update config: {e}")
    
    async def check_for_updates(self, force=False):
        if not force and self.last_check and (datetime.now() - self.last_check) < self.check_cooldown:
            return False
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.update_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.latest_version = data.get('version')
                        self.download_url = data.get('download_url', self.download_url)
                        self.last_check = datetime.now()
                        self.save_config()
                        return True
                    else:
                        print(f"Update check failed with status {response.status}")
                        return False
        except Exception as e:
            print(f"Error checking for updates: {e}")
            return False
    
    def parse_version(self, version_str):
        if version_str.lower().startswith('v'):
            version_str = version_str[1:]
            
        parts = version_str.split('.')
        
        result = []
        for part in parts:
            try:
                result.append(int(part))
            except ValueError:
                
                result.append(part)
                
        return result
    
    def version_is_newer(self, version1, version2):
        
        v1_parts = self.parse_version(version1)
        v2_parts = self.parse_version(version2)
        
        for i in range(max(len(v1_parts), len(v2_parts))):
            
            if i >= len(v1_parts):
                return False
            if i >= len(v2_parts):
                return True
                
            v1 = v1_parts[i]
            v2 = v2_parts[i]
            
            if type(v1) != type(v2):
                v1 = str(v1)
                v2 = str(v2)
                
            if v1 > v2:
                return True
            elif v1 < v2:
                return False
                
        return False
    
    @commands.command(name="checkupdate", aliases=["update", "version"])
    async def check_update_cmd(self, ctx, force_param: str = None):
        force = False
        if force_param and force_param.lower() == 'force':
            force = True
        
        embed = discord.Embed(
            title="🔄 ZygnalBot Update Checker",
            color=discord.Color.blue()
        )
        embed.set_footer(text="ZygnalBot Made By TheHolyoneZ")
        
        embed.add_field(
            name="Current Version",
            value=f"v{self.version}",
            inline=False
        )
        
        checking_message = await ctx.send("Checking for updates...")
        update_checked = await self.check_for_updates(force=force)
        
        if self.latest_version:
            if self.version_is_newer(self.latest_version, self.version):
                
                embed.color = discord.Color.green()
                embed.description = "✅ A new version is available!"
                embed.add_field(
                    name="Latest Version",
                    value=f"v{self.latest_version}",
                    inline=True
                )
                
                if self.last_check:
                    embed.add_field(
                        name="Last Checked",
                        value=self.last_check.strftime("%Y-%m-%d %H:%M:%S"),
                        inline=True
                    )
            
                
                view = discord.ui.View(timeout=300)
                
                if self.download_url:
                    view.add_item(discord.ui.Button(
                        label="Download Update",
                        style=discord.ButtonStyle.link,
                        url=self.download_url
                    ))
                    
                
                await checking_message.edit(content=None, embed=embed, view=view)
            else:
              
                embed.description = "✅ You're running the latest version!"
                
                if self.last_check:
                    embed.add_field(
                        name="Last Checked",
                        value=self.last_check.strftime("%Y-%m-%d %H:%M:%S"),
                        inline=True
                    )
                
                await checking_message.edit(content=None, embed=embed)
        else:
            
            embed.color = discord.Color.orange()
            
            if update_checked:
                embed.description = "⚠️ Connected to update server but received invalid data."
            else:
                embed.description = "⚠️ Couldn't connect to update server."
                
                if self.last_check:
                    embed.add_field(
                        name="Last Successful Check",
                        value=self.last_check.strftime("%Y-%m-%d %H:%M:%S"),
                        inline=True
                    )
            
            await checking_message.edit(content=None, embed=embed)

    @commands.command(name="updatehelp", aliases=["updateinfo", "versionhelp"])
    async def update_help(self, ctx):
      
        embed = discord.Embed(
            title="🔄 ZygnalBot Update System Help",
            description="Commands and information about the bot's update checking system",
            color=discord.Color.blue()
        )
        embed.set_footer(text="ZygnalBot Made By TheHolyoneZ")
        
        embed.add_field(
            name="!checkupdate [force]",
            value=(
                "**Description:** Check if a new version of ZygnalBot is available\n"
                "**Aliases:** `!update`, `!version`\n"
                "**Usage:**\n"
                "• `!checkupdate` - Checks for updates (respects cooldown period)\n"
                "• `!checkupdate force` - Forces an update check, ignoring cooldown\n"
                "**Notes:** The bot automatically checks for updates every 4 hours"
            ),
            inline=False
        )
        
        embed.add_field(
            name="!updatehelp",
            value=(
                "**Description:** Display this help message\n"
                "**Aliases:** `!updateinfo`, `!versionhelp`\n"
                "**Usage:**\n"
                "• `!updatehelp` - Shows detailed information about update commands\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Current Version",
            value=f"v{self.version}",
            inline=True
        )
        
        if self.last_check:
            time_since = datetime.now() - self.last_check
            hours = int(time_since.total_seconds() // 3600)
            minutes = int((time_since.total_seconds() % 3600) // 60)
            
            embed.add_field(
                name="Last Update Check",
                value=f"{self.last_check.strftime('%Y-%m-%d %H:%M:%S')}\n({hours}h {minutes}m ago)",
                inline=True
            )
        else:
            embed.add_field(
                name="Last Update Check",
                value="Never checked",
                inline=True
            )
        
        embed.add_field(
            name="📝 Update System Information",
            value=(
                "• The bot checks for updates every 4 hours\n"
                "• Update checks connect to the official ZygnalBot server\n"
                "• When a new version is available, a download link will be provided\n"
                "• Version numbers follow the format: `MAJOR.MINOR.PATCH`\n"
                "• The update system helps ensure you have the latest features and security fixes"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔄 Update Process",
            value=(
                "1. Use `!checkupdate` to see if a new version is available\n"
                "2. If available, click the 'Download Update' button\n"
                "3. Follow the instructions on the download page\n"
                "4. Restart your bot after updating\n"
                "5. Verify the new version with `!version`"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(UpdateChecker(bot))