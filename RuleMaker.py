import discord
from discord.ext import commands
import json
import os
from datetime import datetime
import uuid

class RuleView(discord.ui.View):
    def __init__(self, rules_cog, timeout=None):
        super().__init__(timeout=timeout)
        self.rules_cog = rules_cog
        
    @discord.ui.button(label="Next Page", style=discord.ButtonStyle.primary, emoji="➡️", custom_id="rules:next_page")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rules_cog.change_page(interaction, 1)
        
    @discord.ui.button(label="Previous Page", style=discord.ButtonStyle.primary, emoji="⬅️", custom_id="rules:prev_page")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rules_cog.change_page(interaction, -1)
        
    @discord.ui.button(label="Jump to Section", style=discord.ButtonStyle.secondary, emoji="🔍", custom_id="rules:jump")
    async def jump_section(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rules_cog.show_section_selector(interaction)

class RuleCreationModal(discord.ui.Modal):
    def __init__(self, rules_cog, section_id=None, rule_id=None):
        super().__init__(title="Create/Edit Rule")
        self.rules_cog = rules_cog
        self.section_id = section_id
        self.rule_id = rule_id
        
        title_value = ""
        description_value = ""
        
        if section_id and rule_id:
            rule_data = self.rules_cog.get_rule(section_id, rule_id)
            if rule_data:
                title_value = rule_data.get("title", "")
                description_value = rule_data.get("description", "")
        
        self.title_input = discord.ui.TextInput(
            label="Rule Title",
            placeholder="Enter a title for this rule",
            required=True,
            max_length=100,
            default=title_value
        )
        self.add_item(self.title_input)
        
        self.description_input = discord.ui.TextInput(
            label="Rule Description",
            placeholder="Enter the rule description and details",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=1000,
            default=description_value
        )
        self.add_item(self.description_input)
        
    async def on_submit(self, interaction: discord.Interaction):
        title = self.title_input.value
        description = self.description_input.value
        
        if self.section_id and self.rule_id:
 
            success = await self.rules_cog.edit_rule(interaction, self.section_id, self.rule_id, title, description)
        else:

            success = await self.rules_cog.add_rule(interaction, self.section_id, title, description)
            
        if success:
            await interaction.response.send_message("Rule has been saved successfully!", ephemeral=True)
        else:
            await interaction.response.send_message("Failed to save the rule. Please try again.", ephemeral=True)

class SectionCreationModal(discord.ui.Modal):
    def __init__(self, rules_cog, section_id=None):
        super().__init__(title="Create/Edit Section")
        self.rules_cog = rules_cog
        self.section_id = section_id
        title_value = ""
        description_value = ""
        
        if section_id:
            section_data = self.rules_cog.get_section(section_id)
            if section_data:
                title_value = section_data.get("title", "")
                description_value = section_data.get("description", "")
        
        self.title_input = discord.ui.TextInput(
            label="Section Title",
            placeholder="Enter a title for this section",
            required=True,
            max_length=100,
            default=title_value
        )
        self.add_item(self.title_input)
        
        self.description_input = discord.ui.TextInput(
            label="Section Description",
            placeholder="Enter a brief description for this section",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=500,
            default=description_value
        )
        self.add_item(self.description_input)
        
    async def on_submit(self, interaction: discord.Interaction):
        title = self.title_input.value
        description = self.description_input.value
        
        if self.section_id:
            success = await self.rules_cog.edit_section(interaction, self.section_id, title, description)
        else:
            success = await self.rules_cog.add_section(interaction, title, description)
            
        if success:
            await interaction.response.send_message("Section has been saved successfully!", ephemeral=True)
        else:
            await interaction.response.send_message("Failed to save the section. Please try again.", ephemeral=True)

class RuleConfigView(discord.ui.View):
    def __init__(self, rules_cog, timeout=None):
        super().__init__(timeout=timeout)
        self.rules_cog = rules_cog
        
    @discord.ui.button(label="Add Section", style=discord.ButtonStyle.success, emoji="📑", custom_id="rules:add_section")
    async def add_section(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SectionCreationModal(self.rules_cog)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Edit Section", style=discord.ButtonStyle.primary, emoji="✏️", custom_id="rules:edit_section")
    async def edit_section(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rules_cog.show_section_selector(interaction, for_edit=True)
        
    @discord.ui.button(label="Delete Section", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="rules:delete_section")
    async def delete_section(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rules_cog.show_section_selector(interaction, for_delete=True)
        
    @discord.ui.button(label="Add Rule", style=discord.ButtonStyle.success, emoji="📝", custom_id="rules:add_rule")
    async def add_rule(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rules_cog.show_section_selector(interaction, for_add_rule=True)
        
    @discord.ui.button(label="Edit Rule", style=discord.ButtonStyle.primary, emoji="📋", custom_id="rules:edit_rule")
    async def edit_rule(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rules_cog.show_section_selector(interaction, for_edit_rule=True)
        
    @discord.ui.button(label="Delete Rule", style=discord.ButtonStyle.danger, emoji="❌", custom_id="rules:delete_rule")
    async def delete_rule(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rules_cog.show_section_selector(interaction, for_delete_rule=True)
        
    @discord.ui.button(label="Publish Rules", style=discord.ButtonStyle.success, emoji="📢", custom_id="rules:publish")
    async def publish_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rules_cog.show_publish_options(interaction)
        
    @discord.ui.button(label="Theme Settings", style=discord.ButtonStyle.secondary, emoji="🎨", custom_id="rules:theme")
    async def theme_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rules_cog.show_theme_settings(interaction)

class RuleMaker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_folder = "data/rules"
        self.user_sessions = {}  
        self.create_data_folder()
        
    def create_data_folder(self):
        
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
            
    def get_guild_file_path(self, guild_id):
        
        return f"{self.data_folder}/{guild_id}_rules.json"
    
    def load_guild_rules(self, guild_id):
        
        file_path = self.get_guild_file_path(guild_id)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return self.create_default_rules_structure()
        return self.create_default_rules_structure()
    
    def save_guild_rules(self, guild_id, data):
        
        file_path = self.get_guild_file_path(guild_id)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    
    def create_default_rules_structure(self):
        
        return {
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "version": 1,
                "theme": {
                    "color": 0x3498db,  # Discord blue
                    "title_format": "📜 {guild_name} Rules",
                    "footer_text": "Last updated: {date}",
                    "show_rule_numbers": True,
                    "section_emoji": "📌",
                    "rule_emoji": "⚖️"
                }
            },
            "sections": []
        }
    
    def get_section(self, section_id):
        
        for guild_id, session in self.user_sessions.items():
            rules_data = self.load_guild_rules(guild_id)
            for section in rules_data.get("sections", []):
                if section.get("id") == section_id:
                    return section
        return None
    
    def get_rule(self, section_id, rule_id):
        
        section = self.get_section(section_id)
        if section:
            for rule in section.get("rules", []):
                if rule.get("id") == rule_id:
                    return rule
        return None
    
    async def add_section(self, interaction, title, description=""):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        
        new_section = {
            "id": str(uuid.uuid4()),
            "title": title,
            "description": description,
            "rules": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        rules_data["sections"].append(new_section)
        rules_data["metadata"]["last_updated"] = datetime.now().isoformat()
        
        self.save_guild_rules(guild_id, rules_data)
        return True
    
    async def edit_section(self, interaction, section_id, title, description=""):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        
        for section in rules_data.get("sections", []):
            if section.get("id") == section_id:
                section["title"] = title
                section["description"] = description
                section["updated_at"] = datetime.now().isoformat()
                rules_data["metadata"]["last_updated"] = datetime.now().isoformat()
                
                self.save_guild_rules(guild_id, rules_data)
                return True
                
        return False
    
    async def delete_section(self, interaction, section_id):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        
        for i, section in enumerate(rules_data.get("sections", [])):
            if section.get("id") == section_id:
                rules_data["sections"].pop(i)
                rules_data["metadata"]["last_updated"] = datetime.now().isoformat()
                
                self.save_guild_rules(guild_id, rules_data)
                return True
                
        return False
    
    async def add_rule(self, interaction, section_id, title, description):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        
        for section in rules_data.get("sections", []):
            if section.get("id") == section_id:
                new_rule = {
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "description": description,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                
                section["rules"].append(new_rule)
                section["updated_at"] = datetime.now().isoformat()
                rules_data["metadata"]["last_updated"] = datetime.now().isoformat()
                
                self.save_guild_rules(guild_id, rules_data)
                return True
                
        return False
    
    async def edit_rule(self, interaction, section_id, rule_id, title, description):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        
        for section in rules_data.get("sections", []):
            if section.get("id") == section_id:
                for rule in section.get("rules", []):
                    if rule.get("id") == rule_id:
                        rule["title"] = title
                        rule["description"] = description
                        rule["updated_at"] = datetime.now().isoformat()
                        
                        section["updated_at"] = datetime.now().isoformat()
                        rules_data["metadata"]["last_updated"] = datetime.now().isoformat()
                        
                        self.save_guild_rules(guild_id, rules_data)
                        return True
                        
        return False
    
    async def delete_rule(self, interaction, section_id, rule_id):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        
        for section in rules_data.get("sections", []):
            if section.get("id") == section_id:
                for i, rule in enumerate(section.get("rules", [])):
                    if rule.get("id") == rule_id:
                        section["rules"].pop(i)
                        section["updated_at"] = datetime.now().isoformat()
                        rules_data["metadata"]["last_updated"] = datetime.now().isoformat()
                        
                        self.save_guild_rules(guild_id, rules_data)
                        return True
                        
        return False
    
    async def change_page(self, interaction, direction):
        
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        
        if guild_id not in self.user_sessions:
            self.user_sessions[guild_id] = {}
            
        if user_id not in self.user_sessions[guild_id]:
            self.user_sessions[guild_id][user_id] = {"current_page": 0, "current_section": None}
            
        rules_data = self.load_guild_rules(guild_id)
        sections = rules_data.get("sections", [])
        
        if not sections:
            await interaction.response.send_message("No rules have been created yet.", ephemeral=True)
            return
            
        current_page = self.user_sessions[guild_id][user_id]["current_page"]
        new_page = current_page + direction
        if new_page < 0:
            new_page = len(sections) - 1
        elif new_page >= len(sections):
            new_page = 0
            
        self.user_sessions[guild_id][user_id]["current_page"] = new_page
        self.user_sessions[guild_id][user_id]["current_section"] = sections[new_page]["id"]
        
        await self.display_rules_page(interaction, guild_id, new_page)
    
    async def show_section_selector(self, interaction, for_edit=False, for_delete=False, 
                                   for_add_rule=False, for_edit_rule=False, for_delete_rule=False):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        sections = rules_data.get("sections", [])
        
        if not sections:
            await interaction.response.send_message("No sections have been created yet.", ephemeral=True)
            return
        options = [discord.SelectOption(label=section["title"], value=section["id"]) for section in sections]
        
        class SectionSelector(discord.ui.Select):
            def __init__(self, rules_cog, options, for_edit, for_delete, for_add_rule, for_edit_rule, for_delete_rule):
                super().__init__(placeholder="Select a section", options=options)
                self.rules_cog = rules_cog
                self.for_edit = for_edit
                self.for_delete = for_delete
                self.for_add_rule = for_add_rule
                self.for_edit_rule = for_edit_rule
                self.for_delete_rule = for_delete_rule
                
            async def callback(self, interaction: discord.Interaction):
                section_id = self.values[0]
                
                if self.for_edit:
                    modal = SectionCreationModal(self.rules_cog, section_id)
                    await interaction.response.send_modal(modal)
                    
                elif self.for_delete:
                    view = ConfirmView(self.rules_cog, section_id=section_id)
                    await interaction.response.send_message("Are you sure you want to delete this section? This will delete all rules in this section.", 
                                                           view=view, ephemeral=True)
                    
                elif self.for_add_rule:
                    modal = RuleCreationModal(self.rules_cog, section_id)
                    await interaction.response.send_modal(modal)
                    
                elif self.for_edit_rule or self.for_delete_rule:
                    await self.rules_cog.show_rule_selector(interaction, section_id, for_edit=self.for_edit_rule, for_delete=self.for_delete_rule)
                    
                else:
                    for i, section in enumerate(rules_data.get("sections", [])):
                        if section.get("id") == section_id:
                            await self.rules_cog.display_rules_page(interaction, guild_id, i)
                            break
        
        class SectionSelectorView(discord.ui.View):
            def __init__(self, rules_cog, timeout=180):
                super().__init__(timeout=timeout)
                self.add_item(SectionSelector(rules_cog, options, for_edit, for_delete, for_add_rule, for_edit_rule, for_delete_rule))
                
        await interaction.response.send_message("Select a section:", view=SectionSelectorView(self), ephemeral=True)
    
    async def show_rule_selector(self, interaction, section_id, for_edit=False, for_delete=False):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        
        for section in rules_data.get("sections", []):
            if section.get("id") == section_id:
                rules = section.get("rules", [])
                
                if not rules:
                    await interaction.response.send_message("No rules have been created in this section yet.", ephemeral=True)
                    return
                options = [discord.SelectOption(label=rule["title"], value=rule["id"]) for rule in rules]
                
                class RuleSelector(discord.ui.Select):
                    def __init__(self, rules_cog, section_id, options, for_edit, for_delete):
                        super().__init__(placeholder="Select a rule", options=options)
                        self.rules_cog = rules_cog
                        self.section_id = section_id
                        self.for_edit = for_edit
                        self.for_delete = for_delete
                        
                    async def callback(self, interaction: discord.Interaction):
                        rule_id = self.values[0]
                        
                        if self.for_edit:
                            modal = RuleCreationModal(self.rules_cog, self.section_id, rule_id)
                            await interaction.response.send_modal(modal)
                            
                        elif self.for_delete:
                            view = ConfirmView(self.rules_cog, section_id=self.section_id, rule_id=rule_id)
                            await interaction.response.send_message("Are you sure you want to delete this rule?", 
                                                                  view=view, ephemeral=True)
                
                class RuleSelectorView(discord.ui.View):
                    def __init__(self, rules_cog, timeout=180):
                        super().__init__(timeout=timeout)
                        self.add_item(RuleSelector(rules_cog, section_id, options, for_edit, for_delete))
                        
                await interaction.response.send_message("Select a rule:", view=RuleSelectorView(self), ephemeral=True)
                return
                
        await interaction.response.send_message("Section not found.", ephemeral=True)
    
    async def display_rules_page(self, interaction, guild_id, page_index):
        
        rules_data = self.load_guild_rules(guild_id)
        sections = rules_data.get("sections", [])
        theme = rules_data.get("metadata", {}).get("theme", {})
        
        if not sections:
            await interaction.response.send_message("No rules have been created yet.", ephemeral=True)
            return
            
        if page_index < 0 or page_index >= len(sections):
            page_index = 0
            
        section = sections[page_index]
        rules = section.get("rules", [])
        embed = discord.Embed(
            title=f"{theme.get('section_emoji', '📌')} {section['title']}",
            description=section.get("description", ""),
            color=theme.get("color", 0x3498db)
        )
        if rules:
            for i, rule in enumerate(rules):
                rule_num = f"{i+1}. " if theme.get("show_rule_numbers", True) else ""
                rule_title = f"{theme.get('rule_emoji', '⚖️')} {rule_num}{rule['title']}"
                embed.add_field(name=rule_title, value=rule['description'], inline=False)
        else:
            embed.add_field(name="No Rules", value="No rules have been created in this section yet.", inline=False)
        footer_text = theme.get("footer_text", "Last updated: {date}")
        footer_text = footer_text.replace("{date}", datetime.now().strftime("%Y-%m-%d"))
        footer_text = footer_text.replace("{guild_name}", interaction.guild.name)
        footer_text += f" | Page {page_index + 1}/{len(sections)}"
        embed.set_footer(text=footer_text)
        view = RuleView(self)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view)
    
    async def show_publish_options(self, interaction):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        
        if not rules_data.get("sections", []):
            await interaction.response.send_message("No rules have been created yet.", ephemeral=True)
            return
        channels = [channel for channel in interaction.guild.text_channels 
                   if channel.permissions_for(interaction.guild.me).send_messages]
        
        options = [discord.SelectOption(label=channel.name, value=str(channel.id)) for channel in channels]
        
        class ChannelSelector(discord.ui.Select):
            def __init__(self, rules_cog, options):
                super().__init__(placeholder="Select a channel to publish rules", options=options)
                self.rules_cog = rules_cog
                
            async def callback(self, interaction: discord.Interaction):
                channel_id = int(self.values[0])
                channel = interaction.guild.get_channel(channel_id)
                
                if not channel:
                    await interaction.response.send_message("Channel not found.", ephemeral=True)
                    return
                await self.rules_cog.publish_rules_to_channel(interaction, channel)
                
        class PublishOptionsView(discord.ui.View):
            def __init__(self, rules_cog, timeout=180):
                super().__init__(timeout=timeout)
                self.rules_cog = rules_cog
                self.add_item(ChannelSelector(rules_cog, options))
                
            @discord.ui.button(label="Publish as Single Message", style=discord.ButtonStyle.primary, custom_id="rules:publish_single")
            async def publish_single(self, interaction: discord.Interaction, button: discord.ui.Button):
                
                view = discord.ui.View(timeout=180)
                view.add_item(ChannelSelector(self.rules_cog, options))
                await interaction.response.send_message("Select a channel to publish all rules as a single message:", 
                                                    view=view, ephemeral=True)
                
            @discord.ui.button(label="Publish as Multiple Messages", style=discord.ButtonStyle.primary, custom_id="rules:publish_multiple")
            async def publish_multiple(self, interaction: discord.Interaction, button: discord.ui.Button):
                
                view = discord.ui.View(timeout=180)
                view.add_item(ChannelSelector(self.rules_cog, options))
                await interaction.response.send_message("Select a channel to publish each section as a separate message:", 
                                                    view=view, ephemeral=True)


                
        await interaction.response.send_message("How would you like to publish your rules?", view=PublishOptionsView(self), ephemeral=True)
    
    async def publish_rules_to_channel(self, interaction, channel, as_single_message=True):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        sections = rules_data.get("sections", [])
        theme = rules_data.get("metadata", {}).get("theme", {})
        
        if not sections:
            await interaction.response.send_message("No rules have been created yet.", ephemeral=True)
            return
            
        if as_single_message:
            title_format = theme.get("title_format", "📜 {guild_name} Rules")
            title = title_format.replace("{guild_name}", interaction.guild.name)
            
            embed = discord.Embed(
                title=title,
                description="Please read and follow all server rules.",
                color=theme.get("color", 0x3498db)
            )
            
            for section in sections:
                section_text = f"**{theme.get('section_emoji', '📌')} {section['title']}**\n"
                if section.get("description"):
                    section_text += f"{section['description']}\n\n"
                    
                rules_text = ""
                for i, rule in enumerate(section.get("rules", [])):
                    rule_num = f"{i+1}. " if theme.get("show_rule_numbers", True) else ""
                    rules_text += f"**{theme.get('rule_emoji', '⚖️')} {rule_num}{rule['title']}**\n{rule['description']}\n\n"
                
                if rules_text:
                    embed.add_field(name=section_text, value=rules_text, inline=False)
            footer_text = theme.get("footer_text", "Last updated: {date}")
            footer_text = footer_text.replace("{date}", datetime.now().strftime("%Y-%m-%d"))
            footer_text = footer_text.replace("{guild_name}", interaction.guild.name)
            embed.set_footer(text=footer_text)
            
            await channel.send(embed=embed)
            await interaction.response.send_message(f"Rules published to {channel.mention}!", ephemeral=True)
            
        else:
            for section in sections:
                embed = discord.Embed(
                    title=f"{theme.get('section_emoji', '📌')} {section['title']}",
                    description=section.get("description", ""),
                    color=theme.get("color", 0x3498db)
                )
                for i, rule in enumerate(section.get("rules", [])):
                    rule_num = f"{i+1}. " if theme.get("show_rule_numbers", True) else ""
                    rule_title = f"{theme.get('rule_emoji', '⚖️')} {rule_num}{rule['title']}"
                    embed.add_field(name=rule_title, value=rule['description'], inline=False)
                footer_text = theme.get("footer_text", "Last updated: {date}")
                footer_text = footer_text.replace("{date}", datetime.now().strftime("%Y-%m-%d"))
                footer_text = footer_text.replace("{guild_name}", interaction.guild.name)
                embed.set_footer(text=footer_text)
                
                await channel.send(embed=embed)
            
            await interaction.response.send_message(f"Rules published to {channel.mention} as separate messages!", ephemeral=True)
    
    async def show_theme_settings(self, interaction):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        theme = rules_data.get("metadata", {}).get("theme", {})
        
        embed = discord.Embed(
            title="Rule Theme Settings",
            description="Customize how your rules look and feel",
            color=theme.get("color", 0x3498db)
        )
        
        embed.add_field(name="Current Theme", value=f"""
        **Color**: {hex(theme.get('color', 0x3498db))}
        **Title Format**: {theme.get('title_format', '📜 {guild_name} Rules')}
        **Footer Text**: {theme.get('footer_text', 'Last updated: {date}')}
        **Show Rule Numbers**: {theme.get('show_rule_numbers', True)}
        **Section Emoji**: {theme.get('section_emoji', '📌')}
        **Rule Emoji**: {theme.get('rule_emoji', '⚖️')}
        """, inline=False)
        
        class ThemeSettingsView(discord.ui.View):
            def __init__(self, rules_cog, timeout=180):
                super().__init__(timeout=timeout)
                self.rules_cog = rules_cog
                
            @discord.ui.button(label="Change Color", style=discord.ButtonStyle.primary, custom_id="rules:change_color")
            async def change_color(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.rules_cog.show_color_picker(interaction)
                
            @discord.ui.button(label="Change Title Format", style=discord.ButtonStyle.primary, custom_id="rules:change_title")
            async def change_title(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.rules_cog.show_title_editor(interaction)
                
            @discord.ui.button(label="Change Footer Text", style=discord.ButtonStyle.primary, custom_id="rules:change_footer")
            async def change_footer(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.rules_cog.show_footer_editor(interaction)
                
            @discord.ui.button(label="Toggle Rule Numbers", style=discord.ButtonStyle.secondary, custom_id="rules:toggle_numbers")
            async def toggle_numbers(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.rules_cog.toggle_rule_numbers(interaction)
                
            @discord.ui.button(label="Change Emojis", style=discord.ButtonStyle.secondary, custom_id="rules:change_emojis")
            async def change_emojis(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.rules_cog.show_emoji_editor(interaction)
                
            @discord.ui.button(label="Reset to Default", style=discord.ButtonStyle.danger, custom_id="rules:reset_theme")
            async def reset_theme(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.rules_cog.reset_theme(interaction)
                
        await interaction.response.send_message(embed=embed, view=ThemeSettingsView(self), ephemeral=True)
    
    async def show_color_picker(self, interaction):
        
        colors = {
            "Discord Blue": 0x3498db,
            "Discord Green": 0x2ecc71,
            "Discord Red": 0xe74c3c,
            "Discord Yellow": 0xf1c40f,
            "Discord Purple": 0x9b59b6,
            "Discord Orange": 0xe67e22,
            "Discord Teal": 0x1abc9c,
            "Discord Pink": 0xe91e63,
            "Discord Gray": 0x95a5a6
        }
        
        options = [discord.SelectOption(label=name, value=str(color)) for name, color in colors.items()]
        
        class ColorSelector(discord.ui.Select):
            def __init__(self, rules_cog, options):
                super().__init__(placeholder="Select a color", options=options)
                self.rules_cog = rules_cog
                
            async def callback(self, interaction: discord.Interaction):
                color = int(self.values[0])
                guild_id = interaction.guild.id
                rules_data = self.rules_cog.load_guild_rules(guild_id)
                
                rules_data["metadata"]["theme"]["color"] = color
                self.rules_cog.save_guild_rules(guild_id, rules_data)
                
                await interaction.response.send_message(f"Theme color updated to {hex(color)}!", ephemeral=True)
                
        class ColorPickerView(discord.ui.View):
            def __init__(self, rules_cog, timeout=180):
                super().__init__(timeout=timeout)
                self.add_item(ColorSelector(rules_cog, options))
                
            @discord.ui.button(label="Custom Color (Hex)", style=discord.ButtonStyle.secondary, custom_id="rules:custom_color")
            async def custom_color(self, interaction: discord.Interaction, button: discord.ui.Button):
                modal = discord.ui.Modal(title="Custom Color")
                
                hex_input = discord.ui.TextInput(
                    label="Hex Color Code",
                    placeholder="Enter a hex color code (e.g., #3498db)",
                    required=True,
                    min_length=7,
                    max_length=7
                )
                modal.add_item(hex_input)
                
                async def on_submit(interaction: discord.Interaction):
                    try:
                        hex_color = hex_input.value.strip()
                        if not hex_color.startswith('#'):
                            hex_color = f"#{hex_color}"
                            
                        color = int(hex_color[1:], 16)
                        
                        guild_id = interaction.guild.id
                        rules_data = self.children[0].rules_cog.load_guild_rules(guild_id)
                        
                        rules_data["metadata"]["theme"]["color"] = color
                        self.children[0].rules_cog.save_guild_rules(guild_id, rules_data)
                        
                        await interaction.response.send_message(f"Theme color updated to {hex_color}!", ephemeral=True)
                    except ValueError:
                        await interaction.response.send_message("Invalid hex color code. Please use format #RRGGBB.", ephemeral=True)
                
                modal.on_submit = on_submit
                await interaction.response.send_modal(modal)
                
        await interaction.response.send_message("Select a theme color:", view=ColorPickerView(self), ephemeral=True)
    
    async def show_title_editor(self, interaction):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        current_format = rules_data.get("metadata", {}).get("theme", {}).get("title_format", "📜 {guild_name} Rules")
        
        modal = discord.ui.Modal(title="Edit Title Format")
        
        title_input = discord.ui.TextInput(
            label="Title Format",
            placeholder="Use {guild_name} as a placeholder for the server name",
            required=True,
            default=current_format,
            max_length=100
        )
        modal.add_item(title_input)
        
        async def on_submit(interaction: discord.Interaction):
            new_format = title_input.value
            
            rules_data["metadata"]["theme"]["title_format"] = new_format
            self.save_guild_rules(guild_id, rules_data)
            
            await interaction.response.send_message(f"Title format updated to: {new_format}", ephemeral=True)
            
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
    
    async def show_footer_editor(self, interaction):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        current_footer = rules_data.get("metadata", {}).get("theme", {}).get("footer_text", "Last updated: {date}")
        
        modal = discord.ui.Modal(title="Edit Footer Text")
        
        footer_input = discord.ui.TextInput(
            label="Footer Text",
            placeholder="Use {date} and {guild_name} as placeholders",
            required=True,
            default=current_footer,
            max_length=100
        )
        modal.add_item(footer_input)
        
        async def on_submit(interaction: discord.Interaction):
            new_footer = footer_input.value
            
            rules_data["metadata"]["theme"]["footer_text"] = new_footer
            self.save_guild_rules(guild_id, rules_data)
            
            await interaction.response.send_message(f"Footer text updated to: {new_footer}", ephemeral=True)
            
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
    
    async def toggle_rule_numbers(self, interaction):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        current_setting = rules_data.get("metadata", {}).get("theme", {}).get("show_rule_numbers", True)
        
        rules_data["metadata"]["theme"]["show_rule_numbers"] = not current_setting
        self.save_guild_rules(guild_id, rules_data)
        
        status = "enabled" if not current_setting else "disabled"
        await interaction.response.send_message(f"Rule numbers are now {status}!", ephemeral=True)
    
    async def show_emoji_editor(self, interaction):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        theme = rules_data.get("metadata", {}).get("theme", {})
        
        current_section_emoji = theme.get("section_emoji", "📌")
        current_rule_emoji = theme.get("rule_emoji", "⚖️")
        
        modal = discord.ui.Modal(title="Edit Emojis")
        
        section_emoji_input = discord.ui.TextInput(
            label="Section Emoji",
            placeholder="Enter an emoji for sections",
            required=True,
            default=current_section_emoji,
            max_length=5
        )
        modal.add_item(section_emoji_input)
        
        rule_emoji_input = discord.ui.TextInput(
            label="Rule Emoji",
            placeholder="Enter an emoji for rules",
            required=True,
            default=current_rule_emoji,
            max_length=5
        )
        modal.add_item(rule_emoji_input)
        
        async def on_submit(interaction: discord.Interaction):
            section_emoji = section_emoji_input.value
            rule_emoji = rule_emoji_input.value
            
            rules_data["metadata"]["theme"]["section_emoji"] = section_emoji
            rules_data["metadata"]["theme"]["rule_emoji"] = rule_emoji
            self.save_guild_rules(guild_id, rules_data)
            
            await interaction.response.send_message(f"Emojis updated! Section: {section_emoji}, Rule: {rule_emoji}", ephemeral=True)
            
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
    
    async def reset_theme(self, interaction):
        
        guild_id = interaction.guild.id
        rules_data = self.load_guild_rules(guild_id)
        
        default_theme = {
            "color": 0x3498db,
            "title_format": "📜 {guild_name} Rules",
            "footer_text": "Last updated: {date}",
            "show_rule_numbers": True,
            "section_emoji": "📌",
            "rule_emoji": "⚖️"
        }
        
        rules_data["metadata"]["theme"] = default_theme
        self.save_guild_rules(guild_id, rules_data)
        
        await interaction.response.send_message("Theme has been reset to default!", ephemeral=True)
    @commands.group(name="rule_help", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def rules(self, ctx):
        
        embed = discord.Embed(
            title="📜 Rules Management System",
            description="Create and manage beautiful rule displays for your server",
            color=0x3498db
        )
        
        embed.add_field(name="Available Commands", value="""
        `rule_help setup` - Start the rule setup wizard
        `rule_help view` - View the current rules
        `rule_help manage` - Manage existing rules
        `rule_help publish` - Publish rules to a channel
        `rule_help theme` - Customize rule appearance
        `rule_help import` - Import rules from another channel
        `rule_help export` - Export rules to a file
        """, inline=False)

        embed.set_footer(text="© ZygnalBot 2025 TheholyOneZ")

        await ctx.send(embed=embed)
    
    @rules.command(name="setup")
    @commands.has_permissions(manage_guild=True)
    async def rules_setup(self, ctx):
        
        view = RuleConfigView(self)
        
        embed = discord.Embed(
            title="📜 Rule Setup Wizard",
            description="Let's set up rules for your server! Use the buttons below to create sections and rules.",
            color=0x3498db
        )
        
        embed.add_field(name="Getting Started", value="""
        1. First, create a section using the 'Add Section' button
        2. Then add rules to that section with 'Add Rule'
        3. Organize your rules into logical sections
        4. Use 'Publish Rules' when you're ready to share with your server
        """, inline=False)

        embed.set_footer(text="© ZygnalBot 2025 TheholyOneZ")
        await ctx.send(embed=embed, view=view)
    
    @rules.command(name="view")
    async def rules_view(self, ctx):
        
        guild_id = ctx.guild.id
        rules_data = self.load_guild_rules(guild_id)
        sections = rules_data.get("sections", [])
        
        if not sections:
            await ctx.send("No rules have been created yet.")
            return
        if guild_id not in self.user_sessions:
            self.user_sessions[guild_id] = {}
            
        if ctx.author.id not in self.user_sessions[guild_id]:
            self.user_sessions[guild_id][ctx.author.id] = {"current_page": 0, "current_section": sections[0]["id"]}
        class FakeInteraction:
            def __init__(self, ctx):
                self.response = self
                self.guild = ctx.guild
                self.user = ctx.author
                self.is_done_called = False
                self.ctx = ctx
                
            def is_done(self):
                return self.is_done_called
                
            async def send_message(self, **kwargs):
                self.is_done_called = True
                return await self.ctx.send(**kwargs)
                
            async def edit_original_response(self, **kwargs):
                return await self.ctx.send(**kwargs)
        
        fake_interaction = FakeInteraction(ctx)
        await self.display_rules_page(fake_interaction, guild_id, 0)
    
    @rules.command(name="manage")
    @commands.has_permissions(manage_guild=True)
    async def rules_manage(self, ctx):
      
        view = RuleConfigView(self)
        
        embed = discord.Embed(
            title="📜 Rule Management",
            description="Use the buttons below to manage your server rules.",
            color=0x3498db
        )

        embed.set_footer(text="© ZygnalBot 2025 TheholyOneZ")
        await ctx.send(embed=embed, view=view)
    
    @rules.command(name="publish")
    @commands.has_permissions(manage_guild=True)
    async def rules_publish(self, ctx):

        class FakeInteraction:
            def __init__(self, ctx):
                self.response = self
                self.guild = ctx.guild
                self.user = ctx.author
                self.is_done_called = False
                self.ctx = ctx
                
            def is_done(self):
                return self.is_done_called
                
            async def send_message(self, **kwargs):
                self.is_done_called = True
                return await self.ctx.send(**kwargs)
        
        fake_interaction = FakeInteraction(ctx)
        await self.show_publish_options(fake_interaction)
    
    @rules.command(name="theme")
    @commands.has_permissions(manage_guild=True)
    async def rules_theme(self, ctx):

        class FakeInteraction:
            def __init__(self, ctx):
                self.response = self
                self.guild = ctx.guild
                self.user = ctx.author
                self.is_done_called = False
                self.ctx = ctx
                
            def is_done(self):
                return self.is_done_called
                
            async def send_message(self, **kwargs):
                self.is_done_called = True
                return await self.ctx.send(**kwargs)
        
        fake_interaction = FakeInteraction(ctx)
        await self.show_theme_settings(fake_interaction)
    
    @rules.command(name="import")
    @commands.has_permissions(manage_guild=True)
    async def rules_import(self, ctx, channel: discord.TextChannel = None):
       
        if not channel:
            await ctx.send("Please specify a channel to import rules from.")
            return
            
        await ctx.send(f"Looking for rules in {channel.mention}...")
        
        messages = []
        async for message in channel.history(limit=100):
            if message.author.bot and message.embeds:
                messages.append(message)
                
        if not messages:
            await ctx.send("No rule messages found in that channel.")
            return
            
        guild_id = ctx.guild.id
        rules_data = self.load_guild_rules(guild_id)
        imported_count = 0
        
        for message in messages:
            for embed in message.embeds:
             
                if embed.title and embed.fields:
                   
                    section_id = str(uuid.uuid4())
                    section_title = embed.title
                    section_description = embed.description or ""
                    
                    import re
                    section_title = re.sub(r'^\s*[^\w\s]+\s*', '', section_title)
                    
                    new_section = {
                        "id": section_id,
                        "title": section_title,
                        "description": section_description,
                        "rules": [],
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }
                    
                    for field in embed.fields:
                        if field.name and field.value:
                           
                            rule_title = re.sub(r'^\s*[^\w\s]+\s*', '', field.name)
                            rule_title = re.sub(r'^\s*\d+\.\s*', '', rule_title)
                            
                            new_rule = {
                                "id": str(uuid.uuid4()),
                                "title": rule_title,
                                "description": field.value,
                                "created_at": datetime.now().isoformat(),
                                "updated_at": datetime.now().isoformat()
                            }
                            
                            new_section["rules"].append(new_rule)
                            
                    rules_data["sections"].append(new_section)
                    imported_count += 1
                    
        if imported_count > 0:
            rules_data["metadata"]["last_updated"] = datetime.now().isoformat()
            self.save_guild_rules(guild_id, rules_data)
            await ctx.send(f"Successfully imported {imported_count} rule sections!")
        else:
            await ctx.send("Could not identify any rule embeds to import.")
    
    @rules.command(name="export")
    @commands.has_permissions(manage_guild=True)
    async def rules_export(self, ctx):
      
        guild_id = ctx.guild.id
        rules_data = self.load_guild_rules(guild_id)
        
        if not rules_data.get("sections", []):
            await ctx.send("No rules have been created yet.")
            return
            
        import json
        rules_json = json.dumps(rules_data, indent=4)
        
        import io
        file = io.BytesIO(rules_json.encode())
        
        await ctx.send("Here are your exported rules:", file=discord.File(file, filename=f"{ctx.guild.name}_rules.json"))
    

class ConfirmView(discord.ui.View):
    def __init__(self, rules_cog, section_id=None, rule_id=None, timeout=180):
        super().__init__(timeout=timeout)
        self.rules_cog = rules_cog
        self.section_id = section_id
        self.rule_id = rule_id
        
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, custom_id="rules:confirm_delete")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.section_id and self.rule_id:

            success = await self.rules_cog.delete_rule(interaction, self.section_id, self.rule_id)
            if success:
                await interaction.response.send_message("Rule has been deleted.", ephemeral=True)
            else:
                await interaction.response.send_message("Failed to delete the rule.", ephemeral=True)
        elif self.section_id:

            success = await self.rules_cog.delete_section(interaction, self.section_id)
            if success:
                await interaction.response.send_message("Section and all its rules have been deleted.", ephemeral=True)
            else:
                await interaction.response.send_message("Failed to delete the section.", ephemeral=True)
                
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="rules:cancel_delete")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Operation cancelled.", ephemeral=True)

class PersistentRuleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Next Page", style=discord.ButtonStyle.primary, emoji="➡️", custom_id="persistent_rules:next_page")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
       
        pass
        
    @discord.ui.button(label="Previous Page", style=discord.ButtonStyle.primary, emoji="⬅️", custom_id="persistent_rules:prev_page")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        pass

def setup(bot):
    bot.add_cog(RuleMaker(bot))




