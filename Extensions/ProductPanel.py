# Inspired by: Drako Development/ProductPanel Addon
'''
Änderungen / Eigenanteile:
  * Portierung in Python mit lokalem JSON-basiertem Speicher (statt MongoDB).
  * Neue Commands hinzugefügt: `importproductpanel`, `exportproductpanel`.
  * Aktualisiertes Verhalten des `productpanel`-Commands.
  * Cooldowns und Download-Logging wurden anders implementiert.
  * Konfigurationshandling und Embed-Erzeugung idiomatisch für discord.py neu geschrieben.


Hinweis: Die ursprüngliche Lizenzquelle ist unbekannt; diese Implementierung basiert
auf Beobachtung und wurde eigenständig in Python neu umgesetzt und erweitert.
'''

# License for this script: Copyright (c) 2025 TheHolyOneZ
#                               All rights reserved.

import discord
from discord.ext import commands
import yaml
import os
import pathlib
import zipfile
import io
import json
from datetime import datetime, timedelta, timezone
import aiofiles
import shutil
import asyncio
import traceback


DATA_DIR = pathlib.Path("data/productionpanel/")
COOLDOWNS_FILE = DATA_DIR / "cooldowns.json"
DOWNLOAD_LOGS_FILE = DATA_DIR / "download_logs.json"

async def _load_data(file_path):
    if not file_path.exists():
        return {}
    try:
        async with aiofiles.open(file_path, 'r', encoding="utf-8") as f:
            return json.loads(await f.read())
    except json.JSONDecodeError:
        print(f"Fehler beim Laden von {file_path}. Die Datei ist möglicherweise beschädigt.")
        return {}

async def _save_data(file_path, data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(file_path, 'w', encoding="utf-8") as f:
        await f.write(json.dumps(data, indent=4, default=str))


async def get_cooldown(user_id: int, button_id: str):
    cooldowns = await _load_data(COOLDOWNS_FILE)
    key = f"{user_id}_{button_id}"
    entry = cooldowns.get(key)
    if not entry:
        return None
    
    cooldown_time = datetime.fromisoformat(entry["cooldown"])
    return {"cooldown": cooldown_time}

async def set_cooldown(user_id: int, button_id: str, duration: int):
    cooldowns = await _load_data(COOLDOWNS_FILE)
    key = f"{user_id}_{button_id}"
    cooldown_until = datetime.now(timezone.utc) + timedelta(seconds=duration)
    cooldowns[key] = {"cooldown": cooldown_until.isoformat()}
    await _save_data(COOLDOWNS_FILE, cooldowns)

async def log_download(user_id: int, product_name: str):
    logs = await _load_data(DOWNLOAD_LOGS_FILE)
    key = f"{user_id}_{product_name}"
    
    entry = logs.get(key)
    if entry:
        entry["downloadCount"] += 1
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    else:
        entry = {
            "userId": str(user_id),
            "productName": product_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "downloadCount": 1
        }
    
    logs[key] = entry
    await _save_data(DOWNLOAD_LOGS_FILE, logs)
    
    return entry


def create_zip_buffer(path: pathlib.Path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in path.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(path)
                zip_file.write(file_path, arcname)
    buffer.seek(0)
    return buffer

PROJECT_ROOT = pathlib.Path(os.path.dirname(os.path.abspath(__file__))).parent
CONFIG_PATH = PROJECT_ROOT / "config.yml"

RAW_CONFIG_TEMPLATE = '''ProductPanelRole: ["1378773109653508206"]

panels:
  ZygnalBot:
    title: "ZygnalBot - Download Panel"
    description:
      - "**Please choose a product to download:**"
      - ""
      - "📦 **Standard Release** - **$9.99**"
      - "[Purchase here](https://your-purchase-link.com)"
      - ""
      - "🧊 **Full Source** - **$52.99**"
      - "[Purchase here](https://your-purchase-link.com)"
      - ""
      - "Need assistance or more info? Contact our support team."
    Footer: "Powered by Zygnal Development"
    ThumbnailURL: "https://i.imgur.com/placeholder.png"
    AuthorURL: ""
    AuthorName: ""
    FooterURL: "https://i.imgur.com/placeholder.png"
    embedColor: "#315FFF"
    useButtons: true
    products:
      - name: "Standard"
        emoji: "<:Developer:1208223076408361010>"
        description: "Standard Download"
        roleId: "ROLE_ID"
        zipFilePath: "../../products/ZygnalBot/Standard"
        buttonLabel: "Standard Download"
        buttonColor: "SECONDARY"
      - name: "Full Source"
        emoji: "<:Developer:1208223076408361010>"
        description: "Full Source Download"
        roleId: "ROLE_ID"
        zipFilePath: "../../products/ZygnalBot/FullSource"
        buttonLabel: "Full Source Download"
        buttonColor: "SECONDARY"
    cooldownDuration: 60

messages:
  panelNotFound: 'Panel configuration for "%s" not found.'
  panelPosted: "Panel Posted."
  failedToDisplayPanel: "Failed to display panel."
  productNotFound: "Product not found."
  noRequiredRole: "You do not have the required role to download this product."
  cooldownMessage: "You can download the product again %s. (just wait)"
  fileSizeExceeds: "Sorry, the file size exceeds the current limit for this server's boost level. The maximum allowed is %s MB."
  downloadReady: "Here is your download:"
  downloadError: "Error preparing the download, please try again later."
  preparingDownload: "Preparing your download..."

selectMenu:
  placeholder: "Choose a product"

Log:
  ChannelID: "" 
  Embed:
    Title: "📥 New Download Notification"
    Description:
      - "📌 **User:** {user}"
      - "📦 **Product:** {productname}"
      - "⏰ **Downloaded at:** {time}"
      - "🔢 **Total Downloads:** {downloadamount}"
    Footer:
      Text: "Zygnal Development | Product Panel"
      Icon: "https://i.imgur.com/placeholder.png"
    Author:
      Text: "Download Tracker"
      Icon: "https://i.imgur.com/placeholder.png"
    Color: "#315FFF"
    Image: "https://i.imgur.com/placeholder.png"
    Thumbnail: ""
'''

def is_config_missing_or_template():
    if not CONFIG_PATH.exists():
        return True
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

            return (not content.strip()) or (content.strip() == RAW_CONFIG_TEMPLATE.strip())
    except Exception:
        return True

class ProductPanelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if is_config_missing_or_template():
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                f.write(RAW_CONFIG_TEMPLATE)
        self.config_path = str(CONFIG_PATH)
        self.config = self._load_config()

    def _load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _reload_config(self):
        self.config = self._load_config()

    def get_button_style(self, style_name: str):
        styles = {
            "PRIMARY": discord.ButtonStyle.primary,
            "SECONDARY": discord.ButtonStyle.secondary,
            "SUCCESS": discord.ButtonStyle.success,
            "DANGER": discord.ButtonStyle.danger
        }
        return styles.get(style_name.upper(), discord.ButtonStyle.secondary)

    def get_log_embed(self, log_entry, user):
        log_config = self.config["Log"]["Embed"]
        embed = discord.Embed(
            title=log_config.get("Title"),
            color=int(log_config.get("Color")[1:], 16) if log_config.get("Color") else discord.Color.blue()
        )
        if log_config.get("Description"):
            description = "\n".join(log_config["Description"])
            description = description.replace("{user}", f"<@{user.id}>")
            description = description.replace("{productname}", log_entry["productName"])
            
            timestamp_dt = datetime.fromisoformat(log_entry["timestamp"])
            description = description.replace("{time}", f"<t:{int(timestamp_dt.timestamp())}:F>")
            description = description.replace("{downloadamount}", str(log_entry["downloadCount"]))
            embed.description = description
        
        if log_config.get("Footer") and log_config["Footer"].get("Text"):
            embed.set_footer(text=log_config["Footer"]["Text"], icon_url=log_config["Footer"].get("Icon"))
        
        if log_config.get("Author") and log_config["Author"].get("Text"):
            embed.set_author(name=log_config["Author"]["Text"], icon_url=log_config["Author"].get("Icon"))
        
        if log_config.get("Image"):
            embed.set_image(url=log_config["Image"])
        
        if log_config.get("Thumbnail"):
            embed.set_thumbnail(url=log_config["Thumbnail"])
            
        return embed

    async def send_log_message(self, user, product_name):
        log_channel_id = self.config["Log"].get("ChannelID")
        if not log_channel_id:
            return
        
        log_entry = await log_download(user.id, product_name)
        log_channel = self.bot.get_channel(int(log_channel_id))
        if log_channel:
            log_embed = self.get_log_embed(log_entry, user)
            await log_channel.send(embed=log_embed)

    async def _handle_download_request(self, interaction: discord.Interaction, panel_name: str, product_name: str):
        try:
            panel_config = self.config["panels"].get(panel_name)
            if not panel_config:
                await interaction.response.send_message(self.config["messages"]["panelNotFound"].replace("%s", panel_name), ephemeral=True)
                return

            product = next((p for p in panel_config["products"] if p["name"] == product_name), None)
            if not product:
                await interaction.response.send_message(self.config["messages"]["productNotFound"], ephemeral=True)
                return

            required_role_id = int(product["roleId"])
            if required_role_id not in [role.id for role in getattr(interaction.user, 'roles', [])]:
                await interaction.response.send_message(self.config["messages"]["noRequiredRole"], ephemeral=True)
                return

            button_id = f"product_{panel_name}_{product_name}"
            cooldown_duration = panel_config.get("cooldownDuration", 60)
            cooldown_entry = await get_cooldown(interaction.user.id, button_id)

            if cooldown_entry:
                cooldown_time = cooldown_entry["cooldown"]
                if cooldown_time > datetime.now(timezone.utc):
                    cooldown_end_timestamp = int(cooldown_time.timestamp())
                    cooldown_message = self.config["messages"]["cooldownMessage"].replace("%s", f"<t:{cooldown_end_timestamp}:R>")
                    await interaction.response.send_message(cooldown_message, ephemeral=True)
                    return

            await set_cooldown(interaction.user.id, button_id, cooldown_duration)
            await interaction.response.defer(ephemeral=True)

            try:

                zip_path_raw = product["zipFilePath"]
                if not (zip_path_raw.startswith(".") or zip_path_raw.startswith("/")):
                    zip_path_raw = f"../{zip_path_raw}"
                zip_file_path = pathlib.Path(os.path.join(os.path.dirname(os.path.abspath(__file__)), zip_path_raw)).resolve()
                if not zip_file_path.exists() or not zip_file_path.is_dir():
                    raise FileNotFoundError(f"The product directory '{product_name}' does not exist: {zip_file_path}")

                files = [f for f in zip_file_path.iterdir() if f.is_file()]
                if not files:
                    raise FileNotFoundError(f"No files found in the product directory: {zip_file_path}")


                if len(files) == 1 and files[0].suffix in ['.zip', '.rar']:
                    file_to_send = discord.File(str(files[0]))
                else:
                    try:
                        zip_buffer = create_zip_buffer(zip_file_path)
                        file_name = f"{product_name.replace(' ', '_')}.zip"
                        file_to_send = discord.File(zip_buffer, filename=file_name)
                    except Exception as e:
                        print(f"Error zipping product directory: {e}")
                        traceback.print_exc()
                        await interaction.followup.send("Error creating the zip file for download. Please contact an admin.", ephemeral=True)
                        return

                await interaction.followup.send(self.config["messages"]["downloadReady"], file=file_to_send, ephemeral=True)
                await self.send_log_message(interaction.user, product_name)

            except Exception as e:
                print(f"Error preparing download: {e}")
                traceback.print_exc()
                await interaction.followup.send(self.config["messages"]["downloadError"] + f"\nError: {e}", ephemeral=True)

        except Exception as e:
            print(f"Error in _handle_download_request: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        try:
            from discord import InteractionType
            if interaction.type != InteractionType.component:
                return

            custom_id = interaction.data.get("custom_id")
            if not custom_id:
                return


            if custom_id.startswith("product_"):
                try:
                    parts = custom_id.split("_")
                    panel_name = parts[1]
                    product_name = parts[2]
                    await self._handle_download_request(interaction, panel_name, product_name)
                except Exception as e:
                    print(f"Error handling button interaction: {e}")
                    traceback.print_exc()
                    try:
                        await interaction.response.send_message("An error occurred while processing your request (button).", ephemeral=True)
                    except Exception:
                        pass

            elif custom_id.startswith("select_"):
                try:
                    selected_value = interaction.data["values"][0]
                    parts = selected_value.split("_")
                    panel_name = parts[1]
                    product_name = parts[2]
                    await self._handle_download_request(interaction, panel_name, product_name)
                except Exception as e:
                    print(f"Error handling select interaction: {e}")
                    traceback.print_exc()
                    try:
                        await interaction.response.send_message("An error occurred while processing your request (select menu).", ephemeral=True)
                    except Exception:
                        pass
        except Exception as e:
            print(f"Error in on_interaction: {e}")
            traceback.print_exc()
    

    async def _send_panel_message_internal(self, target, panel_name: str):
        user = target.author
        
        role_ids = [int(role_id) for role_id in self.config["ProductPanelRole"]]
        if not any(role.id in role_ids for role in user.roles):
            await target.reply(
                self.config["messages"].get("noPermission", "You do not have permission to use this command."),
                ephemeral=True if isinstance(target, discord.Interaction) else False
            )
            return

        panel_config = self.config["panels"].get(panel_name)
        if not panel_config:
            error_message = self.config["messages"]["panelNotFound"].replace("%s", panel_name)
            await target.reply(error_message, ephemeral=True if isinstance(target, discord.Interaction) else False)
            return

        embed = discord.Embed(
            title=panel_config["title"],
            description="\n".join(panel_config["description"]),
            color=int(panel_config.get("embedColor")[1:], 16) if panel_config.get("embedColor") else discord.Color.blue()
        )
        if panel_config.get("ThumbnailURL"):
            embed.set_thumbnail(url=panel_config["ThumbnailURL"])
        if panel_config.get("Footer"):
            embed.set_footer(text=panel_config["Footer"], icon_url=panel_config.get("FooterURL"))
        if panel_config.get("AuthorName"):
            embed.set_author(name=panel_config["AuthorName"], icon_url=panel_config.get("AuthorURL"))

        view = discord.ui.View()
        if panel_config.get("useButtons"):
            for product in panel_config["products"]:
                button = discord.ui.Button(
                    label=product["buttonLabel"],
                    style=self.get_button_style(product["buttonColor"]),
                    custom_id=f"product_{panel_name}_{product['name']}",
                    emoji=product.get("emoji")
                )
                view.add_item(button)
        else:
            select = discord.ui.Select(
                placeholder=self.config["selectMenu"]["placeholder"],
                options=[
                    discord.SelectOption(
                        label=p["name"],
                        description=p["description"][:100],
                        value=f"product_{panel_name}_{p['name']}",
                        emoji=p.get("emoji")
                    ) for p in panel_config["products"]
                ],
                custom_id=f"select_{panel_name}"
            )
            view.add_item(select)

        await target.channel.send(embed=embed, view=view)
        
        await target.reply(self.config["messages"]["panelPosted"], ephemeral=True if isinstance(target, discord.Interaction) else False)
        
    @discord.app_commands.command(name="productpanel", description="Post your product panels")
    async def productpanel_slash_command(self, interaction: discord.Interaction, panel: str):
        
        await self._send_panel_message_internal(interaction, panel)

    @commands.command(name="importproductpanel")
    @commands.has_permissions(administrator=True)
    async def import_product_panel(self, ctx):
        
        await ctx.send("Please upload the new config.yml as an attachment.")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.attachments

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send("Timeout. No attachment received.")
            return

        attachment = msg.attachments[0]
        if not attachment.filename.endswith((".yml", ".yaml")):
            await ctx.send("Please upload a valid YAML file.")
            return

        try:
            await attachment.save(self.config_path)
            self.config = self._load_config()
            await ctx.send("New config.yml imported and loaded.")
        except Exception as e:
            await ctx.send(f"Failed to save or load the config file: {e}")
            traceback.print_exc()
            return


        panel_names = list(self.config.get("panels", {}).keys())
        if panel_names:
            panels_list = ', '.join(panel_names)
            await ctx.send(f"Available panels: {panels_list}\nUse !productpanel <panelname> to post a panel. Example: !productpanel {panel_names[0]}")
        else:
            await ctx.send("No panels found in the new config.yml.")


        missing_dirs = set()
        for panel in self.config.get("panels", {}).values():
            for product in panel.get("products", []):
                zip_path = product.get("zipFilePath")
                if zip_path:

                    if not (zip_path.startswith(".") or zip_path.startswith("/")):
                        zip_path_check = f"../{zip_path}"
                    else:
                        zip_path_check = zip_path
                    abs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), zip_path_check)
                    if not os.path.exists(abs_path):
                        missing_dirs.add(zip_path)
        if missing_dirs:
            missing_list = '\n'.join(f'- `{d}`' for d in missing_dirs)
            await ctx.send(
                f"**Note:** The following product directories do not exist yet:\n{missing_list}\n"
                f"Please create these folders in your project root directory (where Main_bot_3.py is located).\n"
                f"Each product folder should contain the files for that product."
            )

    @commands.command(name="exportproductpanel")
    @commands.has_permissions(administrator=True)
    async def export_product_panel(self, ctx):
        
        if is_config_missing_or_template():
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                f.write(RAW_CONFIG_TEMPLATE)
        if not os.path.exists(self.config_path):
            await ctx.send("No config.yml found.")
            return
        try:
            await ctx.send("Here is the current config.yml:", file=discord.File(self.config_path))
        except Exception as e:
            await ctx.send(f"Failed to send config.yml: {e}")
            traceback.print_exc()
            return

        panel_names = list(self.config.get("panels", {}).keys())
        if panel_names:
            panels_list = ', '.join(panel_names)
            await ctx.send(f"Available panels: {panels_list}\nUse !productpanel <panelname> to post a panel. Example: !productpanel {panel_names[0]}")
        else:
            await ctx.send("No panels found in the current config.yml.")

    @commands.command(name="productpanel")
    async def productpanel_prefix_command(self, ctx, panel: str = None):
        
        if is_config_missing_or_template():
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                f.write(RAW_CONFIG_TEMPLATE)
            await ctx.send("No config.yml found or it is not configured. A template has been generated. Please download it with !exportproductpanel, configure it, and then upload it with !importproductpanel.")
            return
        if panel is None:
            panel_names = list(self.config.get("panels", {}).keys())
            embed = discord.Embed(
                title="ProductPanel Help",
                description="Use this command to post a product panel.\n\n**Available panels:**\n" + ("\n".join(f"- `{name}`" for name in panel_names) if panel_names else "No panels found."),
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Usage",
                value="`!productpanel <panelname>`\nExample: `!productpanel panel1`",
                inline=False
            )
            embed.add_field(
                name="Import a config",
                value="`!importproductpanel`\nUpload a new config.yml to use a different configuration.",
                inline=False
            )
            embed.add_field(
                name="Export the current config",
                value="`!exportproductpanel`\nDownload the currently used config.yml.",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        await self._send_panel_message_internal(ctx, panel)

    @productpanel_slash_command.autocomplete("panel")
    async def autocomplete_panel(self, interaction: discord.Interaction, current: str):
        choices = []
        for panel_name, panel_data in self.config["panels"].items():
            if current.lower() in panel_data["title"].lower() or current.lower() in panel_name.lower():
                choices.append(discord.app_commands.Choice(name=panel_data["title"], value=panel_name))
        return choices

async def setup(bot):
    await bot.add_cog(ProductPanelCog(bot))


'''
0-1. Bot Generates a new config.yml (auto)
1. Create a new config.yml
2. paste following code into the config.yml





ProductPanelRole: ["1378773109653508206"]

panels:
  ZygnalBot:
    title: "ZygnalBot - Download Panel"
    description:
      - "**Please choose a product to download:**"
      - ""
      - "📦 **Standard Release** - **$9.99**"
      - "[Purchase here](https://your-purchase-link.com)"
      - ""
      - "🧊 **Full Source** - **$52.99**"
      - "[Purchase here](https://your-purchase-link.com)"
      - ""
      - "Need assistance or more info? Contact our support team."
    Footer: "Powered by Zygnal Development"
    ThumbnailURL: "https://i.imgur.com/placeholder.png"
    AuthorURL: ""
    AuthorName: ""
    FooterURL: "https://i.imgur.com/placeholder.png"
    embedColor: "#315FFF"
    useButtons: true
    products:
      - name: "Standard"
        emoji: "<:Developer:1208223076408361010>"
        description: "Standard Download"
        roleId: "ROLE_ID"
        zipFilePath: "../../products/ZygnalBot/Standard"
        buttonLabel: "Standard Download"
        buttonColor: "SECONDARY"
      - name: "Full Source"
        emoji: "<:Developer:1208223076408361010>"
        description: "Full Source Download"
        roleId: "ROLE_ID"
        zipFilePath: "../../products/ZygnalBot/FullSource"
        buttonLabel: "Full Source Download"
        buttonColor: "SECONDARY"
    cooldownDuration: 60

messages:
  panelNotFound: "Panel configuration for \"%s\" not found."
  panelPosted: "Panel Posted."
  failedToDisplayPanel: "Failed to display panel."
  productNotFound: "Product not found."
  noRequiredRole: "You do not have the required role to download this product."
  cooldownMessage: "You can download the product again %s. (just wait)"
  fileSizeExceeds: "Sorry, the file size exceeds the current limit for this server's boost level. The maximum allowed is %s MB."
  downloadReady: "Here is your download:"
  downloadError: "Error preparing the download, please try again later."
  preparingDownload: "Preparing your download..."

selectMenu:
  placeholder: "Choose a product"

Log:
  ChannelID: "" 
  Embed:
    Title: "📥 New Download Notification"
    Description:
      - "📌 **User:** {user}"
      - "📦 **Product:** {productname}"
      - "⏰ **Downloaded at:** {time}"
      - "🔢 **Total Downloads:** {downloadamount}"
    Footer:
      Text: "Zygnal Development | Product Panel"
      Icon: "https://i.imgur.com/placeholder.png"
    Author:
      Text: "Download Tracker"
      Icon: "https://i.imgur.com/placeholder.png"
    Color: "#315FFF"
    Image: "https://i.imgur.com/placeholder.png"
    Thumbnail: ""


Step 3. Configure the config.yml
Step 4. Run the bot
Step 5. Use the !productpanel command






'''