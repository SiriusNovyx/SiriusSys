import discord
from discord.ext import commands
import json
import os
import asyncio
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class TourUploadView(discord.ui.View):
    
    def __init__(self, cog, ctx):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.waiting_for_upload = False
    
    @discord.ui.button(label="📤 Upload Tour JSON", style=discord.ButtonStyle.primary, emoji="📤")
    async def upload_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the command author can upload configurations!", ephemeral=True)
            return
        
        self.waiting_for_upload = True
        
        embed = discord.Embed(
            title="📤 Upload Your Tour Configuration",
            description="**Please upload your JSON file in this channel now!**\n\n"
                       "I'm waiting for you to attach a `.json` file to your next message.\n"
                       "You have 5 minutes to upload it.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📋 What to do:",
            value="1. Click the **+** button next to the message box\n"
                  "2. Select **Upload a File**\n"
                  "3. Choose your `.json` configuration file\n"
                  "4. Send the message with the file attached",
            inline=False
        )
        
        embed.add_field(
            name="💡 Need an example?",
            value="Use the **Download Example** button below to get a template!",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        def check(message):
            return (message.author == self.ctx.author and 
                   message.channel == self.ctx.channel and 
                   message.attachments)
        
        try:
            message = await self.cog.bot.wait_for('message', timeout=300.0, check=check)
            await self.process_upload(message, interaction)
        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="⏰ Upload Timeout",
                description="Upload cancelled due to timeout. Please try again!",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed, view=None)
    
    async def process_upload(self, message: discord.Message, interaction: discord.Interaction):
        attachment = message.attachments[0]
        
        if not attachment.filename.endswith('.json'):
            await message.reply("❌ Please upload a valid JSON file!")
            return
        
        try:
            content = await attachment.read()
            config = json.loads(content.decode('utf-8'))
            
            validation_result = self.cog.validate_tour_config(config)
            if not validation_result["valid"]:
                error_embed = discord.Embed(
                    title="❌ Invalid Configuration",
                    description="Your JSON file has some issues:",
                    color=discord.Color.red()
                )
                
                for error in validation_result["errors"]:
                    error_embed.add_field(name="Error", value=error, inline=False)
                
                await message.reply(embed=error_embed)
                return
            
            self.cog.save_tour_config(self.ctx.guild.id, config)
            
            success_embed = discord.Embed(
                title="✅ Tour Configuration Uploaded Successfully!",
                description=f"**Tour Name:** {config.get('name', 'Unnamed Tour')}\n"
                           f"**Total Steps:** {len(config.get('steps', []))}\n"
                           f"**Auto-send on join:** {'✅' if config.get('send_on_join', False) else '❌'}",
                color=discord.Color.green()
            )
            
            steps_preview = []
            for i, step in enumerate(config.get('steps', [])[:5]):
                steps_preview.append(f"**{i+1}.** {step.get('title', f'Step {i+1}')}")
            
            if len(config.get('steps', [])) > 5:
                steps_preview.append(f"... and {len(config.get('steps', [])) - 5} more steps")
            
            success_embed.add_field(
                name="📋 Tour Steps Preview",
                value="\n".join(steps_preview) if steps_preview else "No steps found",
                inline=False
            )
            
            success_embed.add_field(
                name="🎯 Next Steps",
                value=f"• Use `{await self.cog.get_prefix(self.ctx)}tour enable` to activate the tour\n"
                      f"• Use `{await self.cog.get_prefix(self.ctx)}tour preview` to test it yourself\n"
                      f"• Use `{await self.cog.get_prefix(self.ctx)}tour test @user` to send it to someone",
                inline=False
            )
            
            await message.reply(embed=success_embed)
            
            final_embed = discord.Embed(
                title="🎉 Upload Complete!",
                description="Your tour configuration has been successfully uploaded and saved!",
                color=discord.Color.green()
            )
            await interaction.edit_original_response(embed=final_embed, view=None)
            
        except json.JSONDecodeError as e:
            error_embed = discord.Embed(
                title="❌ JSON Parse Error",
                description=f"Your JSON file has syntax errors:\n```\n{str(e)}\n```",
                color=discord.Color.red()
            )
            error_embed.add_field(
                name="💡 Tip",
                value="Use a JSON validator like [jsonlint.com](https://jsonlint.com) to check your syntax!",
                inline=False
            )
            await message.reply(embed=error_embed)
        
        except Exception as e:
            await message.reply(f"❌ Error processing file: {str(e)}")
    
    @discord.ui.button(label="📋 Download Example", style=discord.ButtonStyle.secondary, emoji="📋")
    async def download_example(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the command author can download the example!", ephemeral=True)
            return
        
        example_config = self.cog.create_comprehensive_example()
        
        temp_path = f"temp_example_{interaction.guild.id}.json"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(example_config, f, indent=4)
        
        try:
            embed = discord.Embed(
                title="📋 Example Tour Configuration",
                description="Here's a comprehensive example showing all available features!\n\n"
                           "**This example includes:**\n"
                           "• Multiple interactive steps with different layouts\n"
                           "• Custom buttons with various actions\n"
                           "• Role assignments and link buttons\n"
                           "• Images, thumbnails, and rich embeds\n"
                           "• Completion rewards",
                color=discord.Color.blue()
            )
            
            await interaction.response.send_message(
                embed=embed,
                file=discord.File(temp_path, filename="example_tour_configuration.json"),
                ephemeral=True
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_upload(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the command author can cancel!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="❌ Upload Cancelled",
            description="Tour configuration upload has been cancelled.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

class WelcomeTourView(discord.ui.View):
    
    def __init__(self, tour_data: Dict, user: discord.Member, bot, guild: discord.Guild):
        super().__init__(timeout=600)
        self.tour_data = tour_data
        self.user = user
        self.bot = bot
        self.guild = guild
        self.current_step = 0
        self.total_steps = len(tour_data.get("steps", []))
        self.cached_roles = {}
        
        self.cache_roles()
        self.update_buttons()
    
    def cache_roles(self):
        for step in self.tour_data.get("steps", []):
            for button in step.get("buttons", []):
                role_id = button.get("role_id")
                if role_id and role_id not in self.cached_roles:
                    role = self.guild.get_role(role_id)
                    self.cached_roles[role_id] = role
        
        completion = self.tour_data.get("completion", {})
        completion_role_id = completion.get("role_id")
        if completion_role_id and completion_role_id not in self.cached_roles:
            role = self.guild.get_role(completion_role_id)
            self.cached_roles[completion_role_id] = role
    
    def update_buttons(self):
        self.clear_items()
        
        nav_row = []
        
        if self.current_step > 0:
            prev_btn = discord.ui.Button(
                label="◀️ Previous",
                style=discord.ButtonStyle.secondary,
                custom_id="prev",
                row=0
            )
            prev_btn.callback = self.previous_step
            nav_row.append(prev_btn)
        
        step_btn = discord.ui.Button(
            label=f"Step {self.current_step + 1} of {self.total_steps}",
            style=discord.ButtonStyle.primary,
            disabled=True,
            row=0
        )
        nav_row.append(step_btn)
        
        if self.current_step < self.total_steps - 1:
            next_btn = discord.ui.Button(
                label="Next ▶️",
                style=discord.ButtonStyle.primary,
                custom_id="next",
                row=0
            )
            next_btn.callback = self.next_step
            nav_row.append(next_btn)
        else:
            finish_btn = discord.ui.Button(
                label="🎉 Complete Tour",
                style=discord.ButtonStyle.success,
                custom_id="finish",
                row=0
            )
            finish_btn.callback = self.finish_tour
            nav_row.append(finish_btn)
        
        for btn in nav_row:
            self.add_item(btn)
        
        skip_btn = discord.ui.Button(
            label="⏭️ Skip Tour",
            style=discord.ButtonStyle.danger,
            custom_id="skip",
            row=1
        )
        skip_btn.callback = self.skip_tour
        self.add_item(skip_btn)
        
        restart_btn = discord.ui.Button(
            label="🔄 Restart",
            style=discord.ButtonStyle.secondary,
            custom_id="restart",
            row=1
        )
        restart_btn.callback = self.restart_tour
        self.add_item(restart_btn)
        
        current_step_data = self.tour_data["steps"][self.current_step]
        if "buttons" in current_step_data:
            for i, btn_data in enumerate(current_step_data["buttons"][:15]):
                row = 2 + (i // 5)
                
                custom_btn = discord.ui.Button(
                    label=btn_data.get("label", "Button"),
                    style=getattr(discord.ButtonStyle, btn_data.get("style", "secondary")),
                    emoji=btn_data.get("emoji"),
                    url=btn_data.get("url") if btn_data.get("type") == "link" else None,
                    disabled=btn_data.get("disabled", False),
                    row=row
                )
                
                if btn_data.get("type") != "link":
                    custom_btn.callback = lambda i, data=btn_data: self.custom_button_callback(i, data)
                
                self.add_item(custom_btn)
    
    async def custom_button_callback(self, interaction: discord.Interaction, button_data: Dict):
        if interaction.user != self.user:
            await interaction.response.send_message("🚫 This tour is not for you!", ephemeral=True)
            return
        
        action = button_data.get("action")
        
        if action == "send_message":
            await interaction.response.send_message(
                button_data.get("message", "Button clicked!"),
                ephemeral=button_data.get("ephemeral", True)
            )
        
        elif action == "add_role":
            role_id = button_data.get("role_id")
            if role_id and role_id in self.cached_roles:
                role = self.cached_roles[role_id]
                if role:
                    try:
                        await self.user.add_roles(role, reason="Welcome tour role assignment")
                        await interaction.response.send_message(
                            f"✅ **Role Added!**\nYou now have the **{role.name}** role!",
                            ephemeral=True
                        )
                    except Exception as e:
                        await interaction.response.send_message(
                            f"❌ **Failed to add role:** {str(e)}",
                            ephemeral=True
                        )
                else:
                    await interaction.response.send_message(
                        "❌ **Role not found!** Please contact an administrator.",
                        ephemeral=True
                    )
        
        elif action == "remove_role":
            role_id = button_data.get("role_id")
            if role_id and role_id in self.cached_roles:
                role = self.cached_roles[role_id]
                if role and role in self.user.roles:
                    try:
                        await self.user.remove_roles(role, reason="Welcome tour role removal")
                        await interaction.response.send_message(
                            f"✅ **Role Removed!**\nThe **{role.name}** role has been removed.",
                            ephemeral=True
                        )
                    except Exception as e:
                        await interaction.response.send_message(
                            f"❌ **Failed to remove role:** {str(e)}",
                            ephemeral=True
                        )
        
        elif action == "next_step":
            await self.next_step(interaction)
        
        elif action == "previous_step":
            await self.previous_step(interaction)
        
        else:
            await interaction.response.send_message(
                f"🔘 Button clicked: {button_data.get('label', 'Unknown')}",
                ephemeral=True
            )
    
    async def restart_tour(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("🚫 This tour is not for you!", ephemeral=True)
            return
        
        self.current_step = 0
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def previous_step(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("🚫 This tour is not for you!", ephemeral=True)
            return
        
        if self.current_step > 0:
            self.current_step -= 1
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("📍 You're already at the first step!", ephemeral=True)
    
    async def next_step(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("🚫 This tour is not for you!", ephemeral=True)
            return
        
        if self.current_step < self.total_steps - 1:
            self.current_step += 1
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("📍 You're already at the last step! Click 'Complete Tour' to finish.", ephemeral=True)
    
    async def finish_tour(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("🚫 This tour is not for you!", ephemeral=True)
            return
        
        completion_data = self.tour_data.get("completion", {})
        embed = discord.Embed(
            title=completion_data.get("title", "🎉 Congratulations!"),
            description=completion_data.get("description", "You've successfully completed the welcome tour!"),
            color=discord.Color.green()
        )
        
        if completion_data.get("image"):
            embed.set_image(url=completion_data["image"])
        if completion_data.get("thumbnail"):
            embed.set_thumbnail(url=completion_data["thumbnail"])
        
        for field in completion_data.get("fields", []):
            embed.add_field(
                name=field.get("name", "Field"),
                value=field.get("value", "Value"),
                inline=field.get("inline", False)
            )
        
        completion_role_id = completion_data.get("role_id")
        if completion_role_id and completion_role_id in self.cached_roles:
            role = self.cached_roles[completion_role_id]
            if role:
                try:
                    await self.user.add_roles(role, reason="Welcome tour completion reward")
                    embed.add_field(
                        name="🏷️ Reward Unlocked!",
                        value=f"You've been awarded the **{role.name}** role!",
                        inline=False
                    )
                except Exception as e:
                    logger.error(f"Failed to add completion role: {e}")
        
        embed.set_footer(text=f"Welcome to {self.guild.name}! • Tour completed")
        
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()
    
    async def skip_tour(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("🚫 This tour is not for you!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⏭️ Tour Skipped",
            description="No worries! You can always ask an administrator to restart your tour if you change your mind.\n\n"
                       "Feel free to explore the server and don't hesitate to ask questions!",
            color=discord.Color.orange()
        )
        
        embed.set_footer(text=f"Welcome to {self.guild.name}!")
        
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()
    
    def create_embed(self) -> discord.Embed:
        step_data = self.tour_data["steps"][self.current_step]
        
        color_value = step_data.get("color", "0x3498db")
        if isinstance(color_value, str):
            if color_value.startswith("0x"):
                color = discord.Color(int(color_value, 16))
            else:
                color = discord.Color(int(color_value.replace("#", ""), 16))
        else:
            color = discord.Color(color_value)
        
        embed = discord.Embed(
            title=step_data.get("title", f"Step {self.current_step + 1}"),
            description=step_data.get("description", ""),
            color=color
        )
        
        for field in step_data.get("fields", []):
            embed.add_field(
                name=field.get("name", "Field"),
                value=field.get("value", "Value"),
                inline=field.get("inline", False)
            )
        
        if step_data.get("image"):
            embed.set_image(url=step_data["image"])
        if step_data.get("thumbnail"):
            embed.set_thumbnail(url=step_data["thumbnail"])
        if step_data.get("author"):
            author_data = step_data["author"]
            embed.set_author(
                name=author_data.get("name", ""),
                url=author_data.get("url"),
                icon_url=author_data.get("icon_url")
            )
        
        footer_text = step_data.get("footer", "")
        progress_bar = "▓" * (self.current_step + 1) + "░" * (self.total_steps - self.current_step - 1)
        progress_text = f"Progress: {progress_bar} ({self.current_step + 1}/{self.total_steps})"
        
        if footer_text:
            footer_text += f" • {progress_text}"
        else:
            footer_text = progress_text
        
        embed.set_footer(text=footer_text)
        
        return embed

class WelcomeTourCarousel(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.config_dir = "Data/welcome_tours"
        self.ensure_directories()
        self.active_tours = {}
    
    async def get_prefix(self, ctx):
        try:
            prefixes = await self.bot.get_prefix(ctx.message)
            if isinstance(prefixes, list):
                return prefixes[0]
            return prefixes
        except:
            return "!"
    
    def ensure_directories(self):
        os.makedirs(self.config_dir, exist_ok=True)
        
        example_path = os.path.join(self.config_dir, "comprehensive_example.json")
        if not os.path.exists(example_path):
            example_config = self.create_comprehensive_example()
            with open(example_path, 'w', encoding='utf-8') as f:
                json.dump(example_config, f, indent=4)
    
    def create_comprehensive_example(self) -> Dict:
        return {
            "name": "🎠 Ultimate Server Tour",
            "description": "A comprehensive interactive tour showcasing all available features!",
            "enabled": True,
            "send_on_join": True,
            "steps": [
                {
                    "title": "🎉 Welcome to Our Amazing Server!",
                    "description": "**Hey there, welcome!** 👋\n\nWe're absolutely thrilled to have you join our community! This interactive tour will guide you through everything you need to know to get started.\n\n*Click the buttons below to interact with this step, then use **Next** to continue!*",
                    "color": "0x3498db",
                    "image": "https://via.placeholder.com/600x300/3498db/ffffff?text=🎉+WELCOME+TO+OUR+SERVER!",
                    "thumbnail": "https://via.placeholder.com/150x150/3498db/ffffff?text=👋",
                    "author": {
                        "name": "Server Welcome Bot",
                        "icon_url": "https://via.placeholder.com/64x64/3498db/ffffff?text=🤖"
                    },
                    "fields": [
                        {
                            "name": "🌟 What makes us special?",
                            "value": "• **Active community** with 24/7 support\n• **Regular events** and giveaways\n• **Helpful members** always ready to assist\n• **Custom bots** with unique features",
                            "inline": True
                        },
                        {
                            "name": "🎯 What's in this tour?",
                            "value": "• Server rules and guidelines\n• Important channels overview\n• Role system explanation\n• Bot commands and features\n• Community events info",
                            "inline": True
                        }
                    ],
                    "buttons": [
                        {
                            "label": "🌟 Get Newcomer Role",
                            "style": "success",
                            "type": "action",
                            "action": "add_role",
                            "role_id": 123456789012345678,
                            "emoji": "🌟"
                        },
                        {
                            "label": "👋 Say Hello!",
                            "style": "primary",
                            "type": "action",
                            "action": "send_message",
                            "message": "🎉 **Welcome message sent!**\nThanks for saying hello! The community is excited to meet you!",
                            "ephemeral": True
                        }
                    ],
                    "footer": "Step 1: Getting Started"
                },
                {
                    "title": "📜 Server Rules & Community Guidelines",
                    "description": "**Before we dive in, let's cover the important stuff!** 📋\n\nOur community thrives because everyone follows these simple guidelines. Don't worry - they're pretty straightforward!\n\n*Understanding and following these rules helps keep our server awesome for everyone.*",
                    "color": "0xe74c3c",
                    "thumbnail": "https://via.placeholder.com/150x150/e74c3c/ffffff?text=📜",
                    "fields": [
                        {
                            "name": "🚫 What's NOT allowed:",
                            "value": "• **Spam** or excessive self-promotion\n• **Harassment** or bullying of any kind\n• **NSFW content** outside designated channels\n• **Hate speech** or discriminatory language\n• **Sharing personal information** of others",
                            "inline": True
                        },
                        {
                            "name": "✅ What we LOVE to see:",
                            "value": "• **Respectful discussions** and debates\n• **Helping other members** with questions\n• **Sharing cool projects** and achievements\n• **Participating in events** and activities\n• **Being welcoming** to new members",
                            "inline": True
                        },
                        {
                            "name": "⚖️ Consequences",
                            "value": "We use a **3-strike system**:\n• 1st: Warning\n• 2nd: Temporary mute\n• 3rd: Permanent ban\n\n*Serious violations may result in immediate action.*",
                            "inline": False
                        }
                    ],
                    "buttons": [
                        {
                            "label": "📖 Read Full Rules",
                            "style": "primary",
                            "type": "link",
                            "url": "https://discord.com/channels/YOUR_SERVER_ID/YOUR_RULES_CHANNEL_ID"
                        },
                        {
                            "label": "✅ I Understand",
                            "style": "success",
                            "type": "action",
                            "action": "send_message",
                            "message": "✅ **Great!** Thanks for taking the time to understand our community guidelines. You're all set to participate respectfully!",
                            "ephemeral": True
                        }
                    ],
                    "footer": "Step 2: Community Guidelines"
                }
            ],
            "completion": {
                "title": "🎉 Congratulations! Tour Complete!",
                "description": "**You've successfully completed the server tour!** 🎊\n\nYou're now fully equipped to dive into our amazing community. We're excited to see you participate and make new friends!\n\n**Welcome to the family!** 👨‍👩‍👧‍👦",
                "image": "https://via.placeholder.com/600x300/2ecc71/ffffff?text=🎉+TOUR+COMPLETE!",
                "thumbnail": "https://via.placeholder.com/150x150/2ecc71/ffffff?text=✅",
                "fields": [
                    {
                        "name": "🎯 What's Next?",
                        "value": "• Head to **#introductions** and tell us about yourself\n• Join a voice channel and meet other members\n• Check out **#events** for upcoming activities\n• Start chatting in **#general** - don't be shy!",
                        "inline": False
                    }
                ],
                "role_id": 123456789012345683
            }
        }
    
    def validate_tour_config(self, config: Dict) -> Dict[str, Any]:
        errors = []
        
        if "name" not in config:
            errors.append("Missing required field: 'name'")
        
        if "steps" not in config or not isinstance(config["steps"], list):
            errors.append("Missing or invalid 'steps' array")
        elif len(config["steps"]) == 0:
            errors.append("Tour must have at least one step")
        
        for i, step in enumerate(config.get("steps", [])):
            if not isinstance(step, dict):
                errors.append(f"Step {i+1}: Must be an object")
                continue
            
            if "title" not in step:
                errors.append(f"Step {i+1}: Missing required field 'title'")
            
            if "buttons" in step:
                if not isinstance(step["buttons"], list):
                    errors.append(f"Step {i+1}: 'buttons' must be an array")
                else:
                    for j, button in enumerate(step["buttons"]):
                        if not isinstance(button, dict):
                            errors.append(f"Step {i+1}, Button {j+1}: Must be an object")
                        elif "label" not in button:
                            errors.append(f"Step {i+1}, Button {j+1}: Missing required field 'label'")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def load_tour_config(self, guild_id: int) -> Optional[Dict]:
        config_path = os.path.join(self.config_dir, f"{guild_id}.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load tour config for guild {guild_id}: {e}")
        return None
    
    def save_tour_config(self, guild_id: int, config: Dict):
        config_path = os.path.join(self.config_dir, f"{guild_id}.json")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save tour config for guild {guild_id}: {e}")
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        
        tour_config = self.load_tour_config(member.guild.id)
        if not tour_config or not tour_config.get("enabled", False) or not tour_config.get("send_on_join", False):
            return
        
        if member.id in self.active_tours:
            return
        
        try:
            await self.send_tour(member, tour_config)
        except Exception as e:
            logger.error(f"Failed to send welcome tour to {member}: {e}")
    
    async def send_tour(self, member: discord.Member, tour_config: Dict):
        if not tour_config.get("steps"):
            return
        
        self.active_tours[member.id] = True
        
        try:
            view = WelcomeTourView(tour_config, member, self.bot, member.guild)
            embed = view.create_embed()
            
            welcome_message = (
                f"🎉 **Welcome to {member.guild.name}!**\n\n"
                f"{tour_config.get('description', 'Take this interactive tour to get started!')}\n\n"
                f"**🎠 Interactive Tour Features:**\n"
                f"• Navigate with **Previous/Next** buttons\n"
                f"• Click **custom buttons** to interact with each step\n"
                f"• Use **Restart** to go back to the beginning\n"
                f"• **Skip** if you want to explore on your own\n\n"
                f"*Let's get started!* 🚀"
            )
            
            await member.send(content=welcome_message, embed=embed, view=view)
            await view.wait()
            
        except discord.Forbidden:
            welcome_channel = discord.utils.get(member.guild.text_channels, name="welcome")
            if not welcome_channel:
                welcome_channel = member.guild.system_channel
            
            if welcome_channel:
                try:
                    view = WelcomeTourView(tour_config, member, self.bot, member.guild)
                    embed = view.create_embed()
                    
                    welcome_message = (
                        f"🎉 **Welcome {member.mention}!**\n\n"
                        f"{tour_config.get('description', 'Take this interactive tour to get started!')}\n\n"
                        f"*I tried to send this tour to your DMs, but they seem to be closed. "
                        f"No worries - you can take the tour right here!*"
                    )
                    
                    await welcome_channel.send(content=welcome_message, embed=embed, view=view)
                    await view.wait()
                except Exception as e:
                    logger.error(f"Failed to send tour in channel: {e}")
        
        except Exception as e:
            logger.error(f"Error sending tour: {e}")
        
        finally:
            self.active_tours.pop(member.id, None)
    
    @commands.group(name="tour", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def tour(self, ctx):
        prefix = await self.get_prefix(ctx)
        
        embed = discord.Embed(
            title="🎠 Welcome Tour Carousel",
            description="**Advanced Interactive Welcome Tour System**\n\n"
                       "Create engaging, multi-step welcome experiences for new members with custom buttons, role assignments, and rich embeds!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📤 Quick Setup",
            value=f"`{prefix}tour upload` - **Upload your tour JSON via Discord**\n"
                  f"`{prefix}tour enable` - Enable the tour system\n"
                  f"`{prefix}tour disable` - Disable the tour system",
            inline=False
        )
        
        embed.add_field(
            name="🔧 Management Commands",
            value=f"`{prefix}tour preview` - Preview your current tour\n"
                  f"`{prefix}tour test @user` - Send tour to specific user\n"
                  f"`{prefix}tour status` - View current configuration status\n"
                  f"`{prefix}tour export` - Download your current configuration",
            inline=False
        )
        
        embed.add_field(
            name="🎯 Advanced Features",
            value="• **Multi-step carousel** with navigation buttons\n"
                  "• **Custom interactive buttons** with role assignments\n"
                  "• **Rich embeds** with images, thumbnails, and fields\n"
                  "• **Progress tracking** with visual progress bars\n"
                  "• **Completion rewards** and role assignments\n"
                  "• **Automatic DM delivery** with channel fallback",
            inline=False
        )
        
        embed.set_footer(text=f"Use {prefix}tour upload to get started with the interactive setup!")
        
        await ctx.send(embed=embed)
    
    @tour.command(name="upload")
    @commands.has_permissions(administrator=True)
    async def upload_tour(self, ctx):
        prefix = await self.get_prefix(ctx)
        
        embed = discord.Embed(
            title="📤 Upload Tour Configuration",
            description="**Ready to create your interactive welcome tour?** 🎠\n\n"
                       "You can either upload your own JSON configuration or download our comprehensive example to get started!\n\n"
                       "**What you can create:**\n"
                       "• Multi-step interactive tours with custom navigation\n"
                       "• Rich embeds with images, colors, and custom fields\n"
                       "• Interactive buttons for role assignments and actions\n"
                       "• Completion rewards and progress tracking\n"
                       "• Automatic delivery to new members",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🎯 How it works:",
            value="1. **Click 'Upload Tour JSON'** below\n"
                  "2. **Upload your .json file** when prompted\n"
                  "3. **Bot validates** your configuration\n"
                  "4. **Tour is ready** to use immediately!",
            inline=True
        )
        
        embed.add_field(
            name="📋 Need an example?",
            value="Click **'Download Example'** to get a comprehensive template showing all available features!\n\n"
                  "*The example includes 6 detailed steps with interactive buttons, role assignments, and rich formatting.*",
            inline=True
        )
        
        embed.add_field(
            name="🔧 After uploading:",
            value=f"• Use `{prefix}tour enable` to activate\n"
                  f"• Use `{prefix}tour preview` to test it\n"
                  f"• Use `{prefix}tour status` to check settings",
            inline=False
        )
        
        embed.set_footer(text="Click the buttons below to get started!")
        
        view = TourUploadView(self, ctx)
        await ctx.send(embed=embed, view=view)
    
    @tour.command(name="enable")
    @commands.has_permissions(administrator=True)
    async def enable_tour(self, ctx):
        config = self.load_tour_config(ctx.guild.id)
        if not config:
            prefix = await self.get_prefix(ctx)
            embed = discord.Embed(
                title="❌ No Tour Configuration Found",
                description=f"You need to create a tour configuration first!\n\n"
                           f"Use `{prefix}tour upload` to create your interactive tour.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        config["enabled"] = True
        config["send_on_join"] = True
        self.save_tour_config(ctx.guild.id, config)
        
        embed = discord.Embed(
            title="✅ Welcome Tour Enabled!",
            description=f"**Tour Name:** {config.get('name', 'Unnamed Tour')}\n"
                       f"**Total Steps:** {len(config.get('steps', []))}\n\n"
                       f"The welcome tour will now be automatically sent to all new members who join the server!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="📬 Delivery Method",
            value="• **Primary:** Direct message to new members\n"
                  "• **Fallback:** Welcome channel if DMs are disabled",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @tour.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def disable_tour(self, ctx):
        config = self.load_tour_config(ctx.guild.id)
        if not config:
            await ctx.send("❌ No tour configuration found.")
            return
        
        config["enabled"] = False
        config["send_on_join"] = False
        self.save_tour_config(ctx.guild.id, config)
        
        embed = discord.Embed(
            title="❌ Welcome Tour Disabled",
            description="The welcome tour has been disabled and will no longer be sent to new members.\n\n"
                       "*Your tour configuration has been saved and can be re-enabled at any time.*",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    
    @tour.command(name="preview")
    @commands.has_permissions(administrator=True)
    async def preview_tour(self, ctx):
        config = self.load_tour_config(ctx.guild.id)
        if not config:
            prefix = await self.get_prefix(ctx)
            embed = discord.Embed(
                title="❌ No Tour Configuration Found",
                description=f"You need to create a tour configuration first!\n\n"
                           f"Use `{prefix}tour upload` to create your interactive tour.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        try:
            await self.send_tour(ctx.author, config)
            
            embed = discord.Embed(
                title="✅ Tour Preview Sent!",
                description=f"**{config.get('name', 'Your Tour')}** has been sent to your DMs for preview!\n\n"
                           f"*If you don't see it, check that your DMs are open and try again.*",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📊 Tour Details",
                value=f"**Steps:** {len(config.get('steps', []))}\n"
                      f"**Enabled:** {'✅' if config.get('enabled', False) else '❌'}\n"
                      f"**Auto-send:** {'✅' if config.get('send_on_join', False) else '❌'}",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Cannot Send Preview",
                description="I couldn't send the tour preview to your DMs. Please make sure your DMs are open and try again.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
    
    @tour.command(name="test")
    @commands.has_permissions(administrator=True)
    async def test_tour(self, ctx, member: discord.Member):
        config = self.load_tour_config(ctx.guild.id)
        if not config:
            prefix = await self.get_prefix(ctx)
            embed = discord.Embed(
                title="❌ No Tour Configuration Found",
                description=f"You need to create a tour configuration first!\n\n"
                           f"Use `{prefix}tour upload` to create your interactive tour.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        if member.bot:
            await ctx.send("❌ Cannot send tours to bots!")
            return
        
        try:
            await self.send_tour(member, config)
            
            embed = discord.Embed(
                title="✅ Tour Sent Successfully!",
                description=f"**{config.get('name', 'Tour')}** has been sent to {member.mention}!\n\n"
                           f"*The tour was delivered via DM, or in the welcome channel if DMs are disabled.*",
                color=discord.Color.green()
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Failed to Send Tour",
                description=f"There was an error sending the tour to {member.mention}:\n```{str(e)}```",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
    
    @tour.command(name="export")
    @commands.has_permissions(administrator=True)
    async def export_config(self, ctx):
        config = self.load_tour_config(ctx.guild.id)
        if not config:
            prefix = await self.get_prefix(ctx)
            embed = discord.Embed(
                title="❌ No Tour Configuration Found",
                description=f"You need to create a tour configuration first!\n\n"
                           f"Use `{prefix}tour upload` to create your interactive tour.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        config_json = json.dumps(config, indent=4)
        
        temp_path = f"temp_tour_export_{ctx.guild.id}.json"
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(config_json)
        
        try:
            embed = discord.Embed(
                title="📤 Tour Configuration Export",
                description=f"**Tour Name:** {config.get('name', 'Unnamed Tour')}\n"
                           f"**Total Steps:** {len(config.get('steps', []))}\n"
                           f"**File Size:** {len(config_json)} characters\n\n"
                           f"*Your complete tour configuration is attached below!*",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="💡 Usage Tips",
                value="• **Backup:** Save this file as a backup of your tour\n"
                      "• **Share:** Send to other server admins\n"
                      "• **Modify:** Edit and re-upload with changes\n"
                      "• **Template:** Use as a base for other servers",
                inline=False
            )
            
            await ctx.send(
                embed=embed,
                file=discord.File(temp_path, filename=f"tour_config_{ctx.guild.name.replace(' ', '_')}.json")
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    @tour.command(name="status")
    @commands.has_permissions(administrator=True)
    async def tour_status(self, ctx):
        config = self.load_tour_config(ctx.guild.id)
        prefix = await self.get_prefix(ctx)
        
        embed = discord.Embed(
            title="🎠 Welcome Tour Status",
            color=discord.Color.blue()
        )
        
        if config:
            embed.add_field(
                name="📊 Configuration Status",
                value=f"**Name:** {config.get('name', 'Unnamed Tour')}\n"
                      f"**Enabled:** {'✅ Active' if config.get('enabled', False) else '❌ Disabled'}\n"
                      f"**Auto-send:** {'✅ On' if config.get('send_on_join', False) else '❌ Off'}\n"
                      f"**Total Steps:** {len(config.get('steps', []))}",
                inline=False
            )
            
            if config.get('steps'):
                step_info = []
                for i, step in enumerate(config['steps'][:5]):
                    buttons_count = len(step.get('buttons', []))
                    fields_count = len(step.get('fields', []))
                    step_info.append(f"**{i+1}.** {step.get('title', f'Step {i+1}')} "
                                   f"({buttons_count} buttons, {fields_count} fields)")
                
                if len(config['steps']) > 5:
                    step_info.append(f"... and {len(config['steps']) - 5} more steps")
                
                embed.add_field(
                    name="📋 Tour Steps Preview",
                    value="\n".join(step_info),
                    inline=False
                )
            
            completion = config.get('completion', {})
            if completion.get('role_id'):
                embed.add_field(
                    name="🎁 Completion Reward",
                    value=f"Role ID: `{completion['role_id']}`\n"
                          f"*Members get this role when they complete the tour*",
                    inline=False
                )
        else:
            embed.add_field(
                name="❌ No Configuration Found",
                value=f"You haven't created a tour configuration yet.\n\n"
                      f"Use `{prefix}tour upload` to create your first interactive welcome tour!",
                inline=False
            )
        
        embed.add_field(
            name="🔄 Current Activity",
            value=f"**Active Tours:** {len(self.active_tours)} members currently taking tours\n"
                  f"**Server Members:** {ctx.guild.member_count} total members",
            inline=False
        )
        
        if config:
            embed.add_field(
                name="🔧 Quick Actions",
                value=f"`{prefix}tour preview` - Test your tour\n"
                      f"`{prefix}tour {'disable' if config.get('enabled') else 'enable'}` - Toggle tour\n"
                      f"`{prefix}tour export` - Download configuration\n"
                      f"`{prefix}tour upload` - Update configuration",
                inline=False
            )
        else:
            embed.add_field(
                name="🚀 Get Started",
                value=f"`{prefix}tour upload` - Create your first tour\n"
                      f"`{prefix}tour help` - View all commands",
                inline=False
            )
        
        embed.set_footer(text=f"Welcome Tour Carousel • Server: {ctx.guild.name}")
        await ctx.send(embed=embed)
    
    @tour.command(name="help")
    async def tour_help(self, ctx):
        prefix = await self.get_prefix(ctx)
        
        embed = discord.Embed(
            title="🎠 Welcome Tour Carousel - Help",
            description="**Complete guide to creating interactive welcome tours**\n\n"
                       "The Welcome Tour Carousel creates engaging, multi-step welcome experiences with custom buttons, role assignments, and rich embeds!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📤 Setup Commands",
            value=f"`{prefix}tour upload` - **Interactive JSON upload via Discord**\n"
                  f"└ Upload your tour configuration file through Discord\n"
                  f"`{prefix}tour enable` - **Activate the tour system**\n"
                  f"└ New members will automatically receive the tour\n"
                  f"`{prefix}tour disable` - **Deactivate the tour system**\n"
                  f"└ Stops sending tours to new members",
            inline=False
        )
        
        embed.add_field(
            name="🔧 Management Commands",
            value=f"`{prefix}tour status` - **View current configuration and stats**\n"
                  f"`{prefix}tour preview` - **Test your tour (sent to your DMs)**\n"
                  f"`{prefix}tour test @user` - **Send tour to specific member**\n"
                  f"`{prefix}tour export` - **Download your current configuration**",
            inline=False
        )
        
        embed.add_field(
            name="🎯 Key Features",
            value="• **Multi-step carousel** with Previous/Next navigation\n"
                  "• **Custom interactive buttons** with role assignments\n"
                  "• **Rich embeds** with images, thumbnails, colors, and fields\n"
                  "• **Progress tracking** with visual progress bars\n"
                  "• **Completion rewards** and automatic role assignments\n"
                  "• **Smart delivery** via DM with channel fallback\n"
                  "• **JSON configuration** for easy sharing and backups",
            inline=False
        )
        
        embed.add_field(
            name="📋 JSON Configuration Structure",
            value="```json\n"
                  "{\n"
                  '  "name": "Your Tour Name",\n'
                  '  "description": "Tour description",\n'
                  '  "enabled": true,\n'
                  '  "send_on_join": true,\n'
                  '  "steps": [\n'
                  "    {\n"
                  '      "title": "Step Title",\n'
                  '      "description": "Step content",\n'
                  '      "color": "0x3498db",\n'
                  '      "buttons": [...],\n'
                  '      "fields": [...]\n'
                  "    }\n"
                  "  ],\n"
                  '  "completion": {...}\n'
                  "}\n"
                  "```",
            inline=False
        )
        
        embed.add_field(
            name="🎨 Button Types & Actions",
            value="**Button Actions:**\n"
                  "• `add_role` - Assign role to user\n"
                  "• `remove_role` - Remove role from user\n"
                  "• `send_message` - Send custom message\n"
                  "• `next_step` - Go to next step\n"
                  "• `previous_step` - Go to previous step\n\n"
                  "**Button Types:**\n"
                  "• `action` - Interactive button with callback\n"
                  "• `link` - URL button (external links)",
            inline=False
        )
        
        embed.add_field(
            name="💡 Pro Tips",
            value="• Use the **Upload** command's example download for a complete template\n"
                  "• Test your tour with `preview` before enabling\n"
                  "• Use role IDs (not names) for button role assignments\n"
                  "• Images should be direct URLs (Discord CDN recommended)\n"
                  "• Keep step descriptions concise but informative\n"
                  "• Use emojis to make your tour more engaging!",
            inline=False
        )
        
        embed.set_footer(text=f"Use {prefix}tour upload to get started with the interactive setup!")
        await ctx.send(embed=embed)
    
    @commands.command(name="welcome-tour")
    @commands.has_permissions(administrator=True)
    async def welcome_tour_alias(self, ctx):
        await self.tour(ctx)

def setup(bot):
    cog = WelcomeTourCarousel(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog
