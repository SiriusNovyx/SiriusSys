import discord
from discord.ext import commands
from discord import app_commands
import json
import inspect
import logging
import asyncio
import os
import traceback
from typing import Dict, List, Any, Optional, Union

logger = logging.getLogger(__name__)

class CommandConverter(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.conversion_data_file = os.path.join("data", "command_converter.json")
        self.converted_commands: Dict[str, bool] = self.load_conversion_data()
        self.pending_conversions: List[Dict[str, Any]] = []
        self.file_upload_listeners: Dict[int, bool] = {}
        self.custom_selection_active: Dict[int, bool] = {}


        os.makedirs(os.path.dirname(self.conversion_data_file), exist_ok=True)

    def load_conversion_data(self) -> Dict[str, bool]:
        
        try:
            if os.path.exists(self.conversion_data_file):
                with open(self.conversion_data_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading conversion data: {e}")
        return {}

    def save_conversion_data(self):
        
        try:
            with open(self.conversion_data_file, 'w') as f:
                json.dump(self.converted_commands, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving conversion data: {e}")

    def get_param_type_name(self, annotation) -> Optional[str]:

        if annotation == inspect.Parameter.empty:
            return None
        

        if getattr(annotation, '__origin__', None) is Union:

            for arg in annotation.__args__:
                if arg is not type(None):
                    return self.get_param_type_name(arg)
        

        if getattr(annotation, '__origin__', None) is Optional:
            return self.get_param_type_name(annotation.__args__[0])
        

        if hasattr(annotation, '__module__') and annotation.__module__.startswith('discord'):
            return f"discord.{annotation.__name__}"
            

        if annotation in [str, int, float, bool]:
            return annotation.__name__
        

        if hasattr(annotation, '__name__'):
            return annotation.__name__
            
        return str(annotation)

    def get_command_signature(self, command: commands.Command) -> Dict[str, Any]:
        
        try:
            sig = inspect.signature(command.callback)
            params = []
            warnings = []


            for param_name, param in sig.parameters.items():
                if param_name in ['self', 'ctx']:
                    continue

                param_type_name = self.get_param_type_name(param.annotation)
                
                param_info = {
                    'name': param_name,
                    'required': param.default == inspect.Parameter.empty,
                    'type': param_type_name,
                    'description': f"Parameter for {command.name}"
                }


                if not param_info['type']:
                    warnings.append(f"Missing type annotation for parameter: {param_name}")
                    param_info['type'] = 'str'
                elif param_info['type'] not in ['str', 'int', 'float', 'bool', 'discord.Member', 'discord.TextChannel', 'discord.Role']:
                    warnings.append(f"Complex or unsupported type annotation for {param_name}: {param.annotation}")
                    param_info['type'] = 'str'
                
                params.append(param_info)

            return {
                'name': command.name,
                'description': command.help or f"Converted from prefix command: {command.name}",
                'parameters': params,
                'warnings': warnings,
                'qualified_name': command.qualified_name,
                'cog_name': command.cog.qualified_name if command.cog else None
            }
        except Exception as e:
            logger.error(f"Error getting signature for command {command.name}: {e}")
            return {
                'name': command.name,
                'description': command.help or f"Converted from prefix command: {command.name}",
                'parameters': [],
                'warnings': [f"Error analyzing command: {str(e)}"],
                'qualified_name': command.qualified_name,
                'cog_name': command.cog.qualified_name if command.cog else None
            }

    def scan_prefix_commands(self) -> List[Dict[str, Any]]:
        
        commands_data = []

        logger.info(f"Command Converter: Scanning {len(self.bot.commands)} total bot commands")

        for command in self.bot.commands:
            logger.debug(f"Command Converter: Checking command '{command.qualified_name}'")


            if command.qualified_name in self.converted_commands:
                logger.debug(f"Command Converter: Skipping '{command.qualified_name}' - already converted")
                continue


            if command.hidden or not hasattr(command, 'callback'):
                logger.debug(f"Command Converter: Skipping '{command.qualified_name}' - hidden or no callback")
                continue

            logger.debug(f"Command Converter: Analyzing command '{command.qualified_name}'")
            command_data = self.get_command_signature(command)
            

            if any("Complex or unsupported type" in w for w in command_data.get('warnings', [])):
                logger.debug(f"Command Converter: Skipping '{command.qualified_name}' - unsupported parameter type")
                continue

            commands_data.append(command_data)

        logger.info(f"Command Converter: Finished scanning, found {len(commands_data)} convertible commands")
        return commands_data

    async def create_slash_command(self, command_data: Dict[str, Any]) -> bool:
        
        try:

            original_command = self.bot.get_command(command_data['qualified_name'])
            if not original_command:
                logger.error(f"Original command {command_data['qualified_name']} not found")
                return False
            

            for cmd in self.bot.tree.walk_commands():
                if cmd.name == command_data['name']:
                    logger.error(f"Slash command with name '{command_data['name']}' already registered.")
                    return False
            

            param_names = [param['name'] for param in command_data['parameters']]


            if not param_names:

                async def slash_callback(interaction: discord.Interaction):
                    await self.execute_original_command(interaction, original_command, {})
            else:

                param_strs = []
                for param in command_data['parameters']:
                    if param['required']:
                        param_strs.append(f"{param['name']}: {param['type']}")
                    else:
                        param_strs.append(f"{param['name']}: Optional[{param['type']}] = None")

                params_str = ", ".join(param_strs)


                kwargs_lines = '\n    '.join([f'kwargs["{param}"] = {param}' for param in param_names])
                exec_code = f"""async def slash_callback(interaction: discord.Interaction, {params_str}):
    kwargs = {{}}
    {kwargs_lines}
    await converter.execute_original_command(interaction, original_command, kwargs)
"""

                namespace = {
                    'discord': discord,
                    'Optional': Optional,
                    'Union': Union,
                    'str': str,
                    'int': int,
                    'float': float,
                    'bool': bool,
                    'Member': discord.Member,
                    'TextChannel': discord.TextChannel,
                    'Role': discord.Role,
                    'converter': self,
                    'original_command': original_command
                }

                exec(exec_code, namespace)
                slash_callback = namespace['slash_callback']


            slash_command = app_commands.Command(
                name=command_data['name'],
                description=command_data['description'][:100],
                callback=slash_callback
            )


            self.bot.tree.add_command(slash_command)

            return True

        except Exception as e:
            logger.error(f"Error creating slash command for {command_data['name']}: {e}")
            return False

    async def execute_original_command(self, interaction: discord.Interaction, original_command: commands.Command, kwargs: Dict[str, Any]):
        
        try:

            ctx = await self.bot.get_context(interaction)
            ctx.interaction = interaction


            await interaction.response.defer()


            if original_command.cog:
                await original_command.callback(original_command.cog, ctx, **kwargs)
            else:
                await original_command.callback(ctx, **kwargs)

        except Exception as e:
            logger.error(f"Error executing original command {original_command.name}: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"❌ Error executing command: {str(e)}",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ Error executing command: {str(e)}",
                        ephemeral=True
                    )
            except:
                pass

    async def initiate_conversion_process(self, user: discord.User):
        
        try:
            logger.info("Command Converter: Scanning prefix commands...")

            commands_data = self.scan_prefix_commands()

            logger.info(f"Command Converter: Found {len(commands_data)} total commands to analyze")

            if not commands_data:
                logger.info("Command Converter: No prefix commands found that need conversion")
                return "No prefix commands found that need conversion."


            convertible_commands = []
            skipped_commands = []

            for cmd_data in commands_data:
                critical_warnings = [w for w in cmd_data['warnings']
                                   if 'Missing type annotation' in w or 'Error analyzing' in w]
                if critical_warnings:
                    skipped_commands.append(cmd_data)
                else:
                    convertible_commands.append(cmd_data)

            if not convertible_commands:
                logger.info("No commands with proper type annotations found for conversion")
                return f"No commands with proper type annotations found for conversion. {len(skipped_commands)} commands were skipped."

            self.pending_conversions = convertible_commands

            logger.info(f"Sending conversion DM to user: {user} (ID: {user.id})")


            embed = discord.Embed(
                title="🔄 Command Conversion Available",
                description=f"Found **{len(convertible_commands)}** prefix commands that can be converted to slash commands.",
                color=discord.Color.blue()
            )

            if skipped_commands:
                embed.add_field(
                    name="⚠️ Skipped Commands",
                    value=f"{len(skipped_commands)} commands were skipped due to missing type annotations or errors.",
                    inline=False
                )

            embed.add_field(
                name="❓ What's Next?",
                value="Do you want to convert all prefix commands into slash + prefix hybrid commands?",
                inline=False
            )

            view = ConversionConfirmView(self)

            try:
                await user.send(embed=embed, view=view)
                logger.info(f"Sent conversion confirmation DM to {user}")
                return f"✅ Conversion options sent to your DMs! Found {len(convertible_commands)} convertible commands."
            except discord.Forbidden:
                logger.error("Cannot send DM to user - DMs are disabled")
                return "❌ Cannot send DM - please enable DMs from server members."
            except Exception as e:
                logger.error(f"Error sending DM to user: {e}")
                return f"❌ Error sending DM: {str(e)}"

        except Exception as e:
            logger.error(f"Error in conversion process: {e}")
            return f"❌ Error in conversion process: {str(e)}"

    def setup_file_listener(self, user: discord.User):
        
        self.file_upload_listeners[user.id] = True
        logger.info(f"File upload listener set up for {user} (ID: {user.id})")

    @commands.Cog.listener()
    async def on_message(self, message):
        

        if (not isinstance(message.channel, discord.DMChannel) or
            message.author.bot or
            message.author.id not in self.file_upload_listeners or
            not message.attachments):
            return


        try:
            attachment = message.attachments[0]


            if not attachment.filename.lower().endswith('.json'):
                await message.reply("❌ Please upload a JSON file (.json extension).")
                return


            file_content = await attachment.read()
            custom_data = json.loads(file_content.decode('utf-8'))


            result = await self.process_custom_conversion_data(message.author, custom_data)
            await message.reply(result)


            if message.author.id in self.file_upload_listeners:
                del self.file_upload_listeners[message.author.id]

        except json.JSONDecodeError as e:
            await message.reply(f"❌ Invalid JSON format: {str(e)}")
        except Exception as e:
            await message.reply(f"❌ Error processing file: {str(e)}")
            logger.error(f"Error processing uploaded file from {message.author}: {e}")

    async def process_custom_conversion_data(self, user: discord.User, custom_data: dict) -> str:
        
        try:

            if "commands" not in custom_data or not isinstance(custom_data["commands"], list):
                return "❌ Invalid JSON structure. Must have a 'commands' array."


            activated_commands = []
            skipped_commands = []

            for cmd in custom_data["commands"]:
                if not isinstance(cmd, dict) or "name" not in cmd or "activate" not in cmd:
                    continue

                if cmd["activate"] == 1:
                    activated_commands.append(cmd["name"])
                else:
                    skipped_commands.append(cmd["name"])


            try:
                current_commands = await self.bot.tree.fetch_commands()
                available_slots = 100 - len(current_commands)

                if len(activated_commands) > available_slots:
                    return (f"❌ Too many commands activated!\n"
                           f"**Activated:** {len(activated_commands)}\n"
                           f"**Available slots:** {available_slots}\n"
                           f"**Current usage:** {len(current_commands)}/100\n\n"
                           f"Please reduce the number of activated commands.")
            except Exception as e:
                logger.warning(f"Could not fetch current commands for validation: {e}")


            filtered_conversions = []
            for cmd_data in self.pending_conversions:
                for custom_cmd in custom_data["commands"]:
                    if (custom_cmd.get("name") == cmd_data["name"] and
                        custom_cmd.get("activate") == 1):
                        filtered_conversions.append(cmd_data)
                        break


            self.pending_conversions = filtered_conversions


            self.custom_selection_active[user.id] = True


            result = (f"✅ **Custom list processed successfully!**\n\n"
                     f"📊 **Selection Summary:**\n"
                     f"• Commands to convert: **{len(activated_commands)}**\n"
                     f"• Commands to skip: **{len(skipped_commands)}**\n"
                     f"• Matched commands: **{len(filtered_conversions)}**\n\n")

            if len(filtered_conversions) < len(activated_commands):
                result += f"⚠️ **Note:** {len(activated_commands) - len(filtered_conversions)} activated commands were not found in the original scan.\n\n"

            result += "🚀 **Ready to convert your custom selection!** Use the 'Confirm conversion' button from the previous message to proceed.\n\n"
            result += "✅ **Your custom JSON has been loaded and will be used for conversion.**"

            return result

        except Exception as e:
            logger.error(f"Error processing custom conversion data: {e}")
            return f"❌ Error processing custom list: {str(e)}"

    async def perform_conversion_with_interaction(self, interaction: discord.Interaction):
        
        try:

            await self.perform_conversion_internal(interaction, use_followup=True)
        except Exception as e:
            logger.error(f"Error performing conversion: {e}")
            await interaction.followup.send(f"❌ Error during conversion: {str(e)}", ephemeral=True)

    async def perform_conversion(self, interaction: discord.Interaction):
        
        try:
            await interaction.response.send_message("🔄 Converting commands...", ephemeral=True)
            await self.perform_conversion_internal(interaction, use_followup=False)
        except Exception as e:
            logger.error(f"Error performing conversion: {e}")
            await interaction.followup.send(f"❌ Error during conversion: {str(e)}", ephemeral=True)

    async def perform_conversion_internal(self, interaction: discord.Interaction, use_followup: bool = False):
        
        try:
            successful_conversions = 0
            failed_conversions = []
            limit_exceeded = False


            sorted_commands = sorted(self.pending_conversions, key=lambda x: len(x['name']))

            for command_data in sorted_commands:
                success = await self.create_slash_command(command_data)
                if success:
                    successful_conversions += 1
                    self.converted_commands[command_data['qualified_name']] = True
                else:
                    failed_conversions.append(command_data['name'])

                    if "maximum number of slash commands exceeded" in str(failed_conversions):
                        limit_exceeded = True


            try:
                await self.bot.tree.sync()
                sync_success = True
            except Exception as e:
                logger.error(f"Error syncing command tree: {e}")
                sync_success = False


            self.save_conversion_data()


            title = "✅ Conversion Complete"
            color = discord.Color.green()

            if not sync_success:
                title = "⚠️ Conversion Complete (Sync Failed)"
                color = discord.Color.orange()
            elif limit_exceeded:
                title = "⚠️ Conversion Complete (Limit Reached)"
                color = discord.Color.yellow()

            embed = discord.Embed(title=title, color=color)


            selection_type = "Custom Selection" if interaction.user.id in self.custom_selection_active else "Default Selection"

            embed.add_field(
                name="📊 Results",
                value=f"**Selection Type:** {selection_type}\n"
                      f"**Successful:** {successful_conversions}\n"
                      f"**Failed:** {len(failed_conversions)}",
                inline=False
            )

            if limit_exceeded:
                embed.add_field(
                    name="⚠️ Discord Limit Reached",
                    value="Hit the 100 global slash command limit. Consider using guild commands or removing unused slash commands.",
                    inline=False
                )

            if failed_conversions:
                embed.add_field(
                    name="❌ Failed Commands",
                    value=", ".join(failed_conversions[:10]),
                    inline=False
                )

            if sync_success:
                embed.add_field(
                    name="🌐 Sync Status",
                    value="✅ Slash commands synced globally",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🌐 Sync Status",
                    value="❌ Failed to sync - commands created but not active",
                    inline=False
                )


            if use_followup:
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)


            self.pending_conversions = []
            if interaction.user.id in self.custom_selection_active:
                del self.custom_selection_active[interaction.user.id]

        except Exception as e:
            logger.error(f"Error performing internal conversion: {e}")
            embed = discord.Embed(
                title="❌ Conversion Failed",
                description=f"An error occurred during conversion: {str(e)}",
                color=discord.Color.red()
            )
            if use_followup:
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)

class ConversionConfirmView(discord.ui.View):
    

    def __init__(self, converter: CommandConverter):
        super().__init__(timeout=300)
        self.converter = converter

    @discord.ui.button(label="Yes, show commands", style=discord.ButtonStyle.primary, emoji="👁️")
    async def show_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        try:


            preview_data = {
                "commands_to_convert": len(self.converter.pending_conversions),
                "note": "First 100 commands are set to activate: 1 (will convert), rest are 0 (will skip). Edit as needed.",
                "instructions": {
                    "how_to_use": [
                        "1. Download this JSON file",
                        "2. Edit the 'activate' values: 1 = convert, 0 = skip",
                        "3. Make sure only 100 or fewer commands have 'activate': 1",
                        "4. Upload the edited file back to this chat",
                        "5. The bot will automatically process your custom selection"
                    ]
                },
                "commands": []
            }

            for i, cmd_data in enumerate(self.converter.pending_conversions):
                cmd_preview = {
                    "name": cmd_data['name'],
                    "description": cmd_data['description'],
                    "activate": 1 if i < 100 else 0,
                    "parameters": [
                        {
                            "name": param['name'],
                            "type": param['type'],
                            "required": param['required']
                        }
                        for param in cmd_data['parameters']
                    ]
                }
                preview_data["commands"].append(cmd_preview)


            json_preview = json.dumps(preview_data, indent=2)


            embed = discord.Embed(
                title="📋 Command Conversion Preview",
                description="Here are the commands available for conversion:",
                color=discord.Color.blue()
            )


            activated_count = sum(1 for i in range(min(100, len(self.converter.pending_conversions))))
            deactivated_count = max(0, len(self.converter.pending_conversions) - 100)

            embed.add_field(
                name="📊 Auto-Selection Applied",
                value=f"**First {activated_count} commands:** `activate: 1` (will convert)\n"
                      f"**Remaining {deactivated_count} commands:** `activate: 0` (will skip)\n"
                      f"**Total commands found:** {len(self.converter.pending_conversions)}",
                inline=False
            )


            with open("command_preview.json", "w") as f:
                json.dump(preview_data, f, indent=2)

            embed.add_field(
                name="📄 How to Use Custom Selection",
                value="📎 **Download** the attached JSON file\n"
                      "✏️ **Edit** the `activate` values: `1` = convert, `0` = skip\n"
                      "📤 **Upload** the edited file back to this DM chat\n"
                      "🤖 **Wait** for the bot to automatically process it",
                inline=False
            )

            embed.add_field(
                name="⚠️ Important Notes",
                value="• Maximum 100 commands can have `activate: 1`\n"
                      "• First 100 commands are pre-selected for you\n"
                      "• Upload your file directly to this DM (no buttons needed)",
                inline=False
            )

            file = discord.File("command_preview.json")
            view = ConversionExecuteView(self.converter)


            self.converter.setup_file_listener(interaction.user)

            await interaction.response.send_message(
                embed=embed,
                file=file,
                view=view,
                ephemeral=True
            )


            try:
                os.remove("command_preview.json")
            except:
                pass

        except Exception as e:
            logger.error(f"Error showing command preview: {e}")
            embed = discord.Embed(
                title="❌ Preview Error",
                description=f"Error generating preview: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class ConversionExecuteView(discord.ui.View):
    

    def __init__(self, converter: CommandConverter):
        super().__init__(timeout=300)
        self.converter = converter
    
    @discord.ui.button(label="Confirm conversion", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_conversion(self, interaction: discord.Interaction, button: discord.ui.Button):
        

        if self.converter.custom_selection_active.get(interaction.user.id, False):
            await interaction.response.send_message("🔄 Converting your CUSTOM selection...", ephemeral=True)
        else:
            await interaction.response.send_message("🔄 Converting all commands...", ephemeral=True)


        await self.converter.perform_conversion_with_interaction(interaction)


        button.disabled = True
        await interaction.edit_original_response(view=self)

    @discord.ui.button(label="Upload custom list", style=discord.ButtonStyle.secondary, emoji="📤")
    async def show_upload_instructions(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        embed = discord.Embed(
            title="📤 How to Upload Custom List",
            description="Follow these steps to upload your custom conversion selection:",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="📋 Step-by-Step Instructions",
            value="1️⃣ **Download** the JSON file from the 'Yes, show commands' option\n"
                  "2️⃣ **Edit** the file - change `activate` values:\n"
                  "     • `1` = Convert this command\n"
                  "     • `0` = Skip this command\n"
                  "3️⃣ **Save** your changes to the JSON file\n"
                  "4️⃣ **Drag & drop** the file directly into this DM chat\n"
                  "5️⃣ **Wait** for automatic processing confirmation\n"
                  "6️⃣ **Click** 'Confirm conversion' to proceed",
            inline=False
        )

        embed.add_field(
            name="⚠️ Important Notes",
            value="• Maximum **100 commands** can have `activate: 1`\n"
                  "• First **100 commands** are pre-selected for you\n"
                  "• **No buttons needed** - just upload the file!\n"
                  "• Bot will **auto-detect** and process your file",
            inline=False
        )

        embed.add_field(
            name="🎯 Pro Tip",
            value="The JSON file includes instructions at the top. Look for the `instructions` section for guidance!",
            inline=False
        )


        self.converter.setup_file_listener(interaction.user)

        embed.set_footer(text="✅ File upload listener activated! You can now upload your edited JSON file.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_conversion(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        embed = discord.Embed(
            title="❌ Conversion Cancelled",
            description="Command conversion has been cancelled.",
            color=discord.Color.red()
        )


        self.converter.pending_conversions = []

        await interaction.response.send_message(embed=embed, ephemeral=True)


class CommandConverterCommands(commands.Cog):
    

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="convert_cmd")
    @commands.is_owner()
    async def convert_commands(self, ctx):
        
        converter = self.bot.get_cog("CommandConverter")
        if not converter:
            await ctx.send("❌ CommandConverter cog not loaded!")
            return

        await ctx.send("🔍 Scanning commands and preparing conversion options...")
        try:
            result = await converter.initiate_conversion_process(ctx.author)
            await ctx.send(result)
        except Exception as e:
            await ctx.send(f"❌ Error during conversion: {str(e)}")
            logger.error(f"Manual scan error: {e}")
            logger.error(traceback.format_exc())

    @commands.command(name="scan_commands")
    @commands.is_owner()
    async def manual_scan(self, ctx):
        
        await ctx.send("⚠️ This command is deprecated. Use `?convert_cmd` instead.")
        await self.convert_commands(ctx)

    @commands.command(name="reset_conversions")
    @commands.is_owner()
    async def reset_conversions(self, ctx):
        
        converter = self.bot.get_cog("CommandConverter")
        if not converter:
            await ctx.send("❌ CommandConverter cog not loaded!")
            return

        converter.converted_commands = {}
        converter.save_conversion_data()
        await ctx.send("✅ Conversion data reset!")

    @commands.command(name="debug_converter")
    @commands.is_owner()
    async def debug_converter(self, ctx):
        
        converter = self.bot.get_cog("CommandConverter")
        if not converter:
            await ctx.send("❌ CommandConverter cog not loaded!")
            return

        embed = discord.Embed(
            title="🔍 Command Converter Debug Info",
            color=discord.Color.blue()
        )


        owner_id_env = os.getenv('BOT_OWNER_ID', 'Not set')
        embed.add_field(
            name="🔑 BOT_OWNER_ID Environment Variable",
            value=f"`{owner_id_env}`",
            inline=False
        )


        embed.add_field(
            name="👤 Command User",
            value=f"{ctx.author} (ID: {ctx.author.id})",
            inline=False
        )


        commands_data = converter.scan_prefix_commands()
        convertible = []
        skipped = []

        for cmd_data in commands_data:
            critical_warnings = [w for w in cmd_data['warnings']
                               if 'Missing type annotation' in w or 'Error analyzing' in w]
            if critical_warnings:
                skipped.append(cmd_data)
            else:
                convertible.append(cmd_data)

        embed.add_field(
            name="📊 Command Scan Results",
            value=f"**Total Found:** {len(commands_data)}\n"
                  f"**Convertible:** {len(convertible)}\n"
                  f"**Skipped:** {len(skipped)}",
            inline=False
        )

        if convertible:
            cmd_list = [f"• `{cmd['name']}`" for cmd in convertible[:10]]
            embed.add_field(
                name="✅ Convertible Commands",
                value="\n".join(cmd_list) + (f"\n... and {len(convertible)-10} more" if len(convertible) > 10 else ""),
                inline=False
            )

        if skipped:
            skip_list = [f"• `{cmd['name']}` - {cmd['warnings'][0][:50]}..." if cmd['warnings'] else f"• `{cmd['name']}` - Unknown issue" for cmd in skipped[:5]]
            embed.add_field(
                name="⚠️ Skipped Commands",
                value="\n".join(skip_list) + (f"\n... and {len(skipped)-5} more" if len(skipped) > 5 else ""),
                inline=False
            )


        embed.add_field(
            name="💾 Previously Converted",
            value=f"{len(converter.converted_commands)} commands" if converter.converted_commands else "None",
            inline=False
        )

        await ctx.send(embed=embed)

    @commands.command(name="slash_count")
    @commands.is_owner()
    async def count_slash_commands(self, ctx):
        
        try:
            app_commands = await self.bot.tree.fetch_commands()

            embed = discord.Embed(
                title="📊 Slash Command Usage",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="Current Usage",
                value=f"**{len(app_commands)}/100** global slash commands",
                inline=False
            )

            if len(app_commands) >= 90:
                embed.add_field(
                    name="⚠️ Warning",
                    value="Very close to the 100 command limit!",
                    inline=False
                )
            elif len(app_commands) >= 75:
                embed.add_field(
                    name="🟡 Caution",
                    value="Getting close to the limit. Consider cleaning up unused commands.",
                    inline=False
                )

            embed.add_field(
                name="Available Slots",
                value=f"{100 - len(app_commands)} commands can still be added",
                inline=False
            )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error fetching slash commands: {str(e)}")

async def setup(bot):
    
    await bot.add_cog(CommandConverter(bot))
    await bot.add_cog(CommandConverterCommands(bot))
    logger.info("Command Converter extension loaded successfully")

async def teardown(bot):
    
    logger.info("Command Converter extension unloaded")