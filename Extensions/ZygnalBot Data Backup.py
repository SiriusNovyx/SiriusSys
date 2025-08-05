import discord
from discord.ext import commands
import zipfile
import os
import tempfile
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DataBackupExtension(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_folder = "data"
        
    @commands.command(name="backup_data", aliases=["download_data", "export_data"])
    @commands.has_permissions(administrator=True)
    async def backup_data(self, ctx):
        try:
            if not os.path.exists(self.data_folder):
                await ctx.send("❌ Data folder not found!")
                return
            
            loading_msg = await ctx.send("📦 Creating backup of data folder...")
            
            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
                temp_zip_path = temp_file.name
            
            try:
                with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(self.data_folder):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, start=os.path.dirname(self.data_folder))
                            zipf.write(file_path, arcname)
                
                file_size = os.path.getsize(temp_zip_path)
                if file_size > 25 * 1024 * 1024:
                    await loading_msg.edit(content="❌ Backup file is too large to send via Discord (>25MB)")
                    return
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"data_backup_{timestamp}.zip"
                
                with open(temp_zip_path, 'rb') as f:
                    discord_file = discord.File(f, filename=filename)
                    
                    embed = discord.Embed(
                        title="📦 Data Backup Complete",
                        description=f"Successfully created backup of data folder",
                        color=discord.Color.green(),
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="File Size", value=f"{file_size / 1024 / 1024:.2f} MB", inline=True)
                    embed.add_field(name="Requested by", value=ctx.author.mention, inline=True)
                    embed.set_footer(text="ZygnalBot Data Backup")
                    
                    await loading_msg.delete()
                    await ctx.send(embed=embed, file=discord_file)
                    
            finally:
                if os.path.exists(temp_zip_path):
                    os.unlink(temp_zip_path)
                    
        except Exception as e:
            logger.error(f"Error creating data backup: {e}")
            await ctx.send(f"❌ Error creating backup: {str(e)}")
    
    @commands.command(name="backup_info")
    async def backup_info(self, ctx):
        try:
            if not os.path.exists(self.data_folder):
                await ctx.send("❌ Data folder not found!")
                return
            
            total_size = 0
            file_count = 0
            folder_count = 0
            
            for root, dirs, files in os.walk(self.data_folder):
                folder_count += len(dirs)
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):
                        total_size += os.path.getsize(file_path)
                        file_count += 1
            
            embed = discord.Embed(
                title="📊 Data Folder Information",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Total Size", value=f"{total_size / 1024 / 1024:.2f} MB", inline=True)
            embed.add_field(name="Files", value=str(file_count), inline=True)
            embed.add_field(name="Folders", value=str(folder_count), inline=True)
            embed.add_field(name="Backup Command", value="`!backup_data`", inline=False)
            embed.add_field(name="Requirements", value="Administrator permissions", inline=True)
            embed.add_field(name="File Limit", value="25MB (Discord limit)", inline=True)
            embed.set_footer(text="ZygnalBot Data Backup Extension")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting data folder info: {e}")
            await ctx.send(f"❌ Error getting folder information: {str(e)}")
    
    @backup_data.error
    async def backup_data_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need administrator permissions to use this command!")
        else:
            logger.error(f"Backup command error: {error}")
            await ctx.send(f"❌ An error occurred: {str(error)}")

def setup(bot):
    cog = DataBackupExtension(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog
