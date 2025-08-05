import discord
from discord.ext import commands
from discord.ext.commands import has_permissions, MissingPermissions, MissingRequiredArgument, BadArgument
import random
import asyncio
from typing import Optional

class ExtraUtilsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, MissingPermissions):
            embed = discord.Embed(
                title="Permission Denied",
                description="You do not have the necessary permissions to use this command.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
        elif isinstance(error, MissingRequiredArgument):
            embed = discord.Embed(
                title="Missing Argument",
                description=f"You are missing a required argument: `{error.param.name}`. Please check the command help for usage.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
        elif isinstance(error, BadArgument):
            embed = discord.Embed(
                title="Invalid Argument",
                description="A provided argument was invalid. Please check the command help for the correct format.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Made By TheHolyOneZ")
            await ctx.send(embed=embed)
        else:
            raise error

    @commands.command(name="extrautils", aliases=["eut"])
    async def extra_utils_help(self, ctx):
        prefix = ctx.prefix
        embed = discord.Embed(
            title="🛠️ Extra Utils Commands",
            description="A collection of useful utility commands for server management and information.",
            color=discord.Color.gold()
        )
        
        message_commands = [
            f"`{prefix}firstmsg` - Jumps to the first message in the channel. (Requires `Manage Messages`)",
            f"`{prefix}lastmsg` - Jumps to the most recent message in the channel.",
            f"`{prefix}jumpto <messageID>` - Goes to a specific message by ID.",
            f"`{prefix}searchmsg <text>` - Finds and links to the first message containing the specified text.",
            f"`{prefix}randommsg` - Picks a random message from the channel.",
            f"`{prefix}clearpins` - Unpins all messages in the current channel. (Requires `Manage Messages`)"
        ]
        embed.add_field(name="✉️ Message & Channel Utilities", value="\n".join(message_commands), inline=False)
        
        role_commands = [
            f"`{prefix}nickall <name>` - Changes all members' nicknames at once. (Requires `Manage Nicknames`)",
            f"`{prefix}resetnicks` - Resets all members' nicknames to default. (Requires `Manage Nicknames`)",
            f"`{prefix}roleremoveall <role>` - Removes a role from all members. (Requires `Manage Roles`)",
            f"`{prefix}rolebots <role>` - Gives or removes a role to/from all bots. (Requires `Manage Roles`)",
            f"`{prefix}rolehumans <role>` - Gives or removes a role to/from all human members. (Requires `Manage Roles`)"
        ]
        embed.add_field(name="👥 Member & Role Management", value="\n".join(role_commands), inline=False)
        
        info_commands = [
            f"`{prefix}serverage` - Shows how old the server is.",
            f"`{prefix}membercount` - Shows the total member count.",
            f"`{prefix}onlinecount` - Shows how many members are online.",
            f"`{prefix}rolecount <role>` - Shows how many members have a certain role.",
            f"`{prefix}joined @user` - Shows when a user joined the server.",
            f"`{prefix}created @user` - Shows when a user's Discord account was created.",
            f"`{prefix}randomuser` - Picks a random online human member.",
            f"`{prefix}ubanner @user` - Shows a user's profile banner."
        ]
        embed.add_field(name="ℹ️ Info & Stats", value="\n".join(info_commands), inline=False)
        
        embed.set_footer(text="Made By TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.command(name="firstmsg")
    @has_permissions(manage_messages=True)
    async def jump_to_first_message(self, ctx):
        await ctx.typing()
        try:
            first_msg = [msg async for msg in ctx.channel.history(limit=1, oldest_first=True)][0]
            embed = discord.Embed(
                title="First Message",
                description=f"Jumping to the first message in this channel.",
                color=discord.Color.blue()
            )
            embed.add_field(name="Author", value=first_msg.author.mention, inline=True)
            embed.add_field(name="Sent At", value=discord.utils.format_dt(first_msg.created_at, style='F'), inline=True)
            embed.set_footer(text=f"Made By TheHolyOneZ")
            await ctx.send(embed=embed, reference=first_msg, view=discord.ui.View().add_item(discord.ui.Button(label="Go to Message", url=first_msg.jump_url)))
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @commands.command(name="lastmsg")
    async def jump_to_last_message(self, ctx):
        await ctx.typing()
        try:
            last_msg = [msg async for msg in ctx.channel.history(limit=1)][0]
            embed = discord.Embed(
                title="Most Recent Message",
                description=f"Jumping to the most recent message in this channel.",
                color=discord.Color.blue()
            )
            embed.add_field(name="Author", value=last_msg.author.mention, inline=True)
            embed.add_field(name="Sent At", value=discord.utils.format_dt(last_msg.created_at, style='F'), inline=True)
            embed.set_footer(text=f"Made By TheHolyOneZ")
            await ctx.send(embed=embed, reference=last_msg, view=discord.ui.View().add_item(discord.ui.Button(label="Go to Message", url=last_msg.jump_url)))
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @commands.command(name="jumpto")
    async def jump_to_specific_message(self, ctx, message_id: int):
        await ctx.typing()
        try:
            message = await ctx.channel.fetch_message(message_id)
            embed = discord.Embed(
                title="Jump to Message",
                description=f"Jumping to the requested message.",
                color=discord.Color.blue()
            )
            embed.add_field(name="Author", value=message.author.mention, inline=True)
            embed.add_field(name="Sent At", value=discord.utils.format_dt(message.created_at, style='F'), inline=True)
            embed.set_footer(text=f"Made By TheHolyOneZ")
            await ctx.send(embed=embed, reference=message, view=discord.ui.View().add_item(discord.ui.Button(label="Go to Message", url=message.jump_url)))
        except discord.NotFound:
            await ctx.send("Message not found. Please ensure the ID is correct and the message is in this channel.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @commands.command(name="searchmsg")
    async def search_message(self, ctx, *, text: str):
        await ctx.typing()
        try:
            async for message in ctx.channel.history(limit=500, before=ctx.message):
                if text.lower() in message.content.lower():
                    embed = discord.Embed(
                        title="Message Found",
                        description=f"Found a message containing `{text}`.",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Author", value=message.author.mention, inline=True)
                    embed.add_field(name="Sent At", value=discord.utils.format_dt(message.created_at, style='F'), inline=True)
                    embed.set_footer(text=f"Made By TheHolyOneZ")
                    await ctx.send(embed=embed, reference=message, view=discord.ui.View().add_item(discord.ui.Button(label="Go to Message", url=message.jump_url)))
                    return
            await ctx.send(f"No message containing `{text}` found in the last 500 messages.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @commands.command(name="randommsg")
    async def random_message(self, ctx):
        await ctx.typing()
        try:
            messages = [msg async for msg in ctx.channel.history(limit=500)]
            if not messages:
                return await ctx.send("No messages to select from in this channel.")
            random_message = random.choice(messages)
            embed = discord.Embed(
                title="Random Message",
                description="Here is a random message from this channel.",
                color=discord.Color.green()
            )
            embed.add_field(name="Author", value=random_message.author.mention, inline=True)
            embed.add_field(name="Sent At", value=discord.utils.format_dt(random_message.created_at, style='F'), inline=True)
            embed.set_footer(text=f"Made By TheHolyOneZ")
            await ctx.send(embed=embed, reference=random_message, view=discord.ui.View().add_item(discord.ui.Button(label="Go to Message", url=random_message.jump_url)))
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @commands.command(name="clearpins")
    @has_permissions(manage_messages=True)
    async def clear_pins(self, ctx):
        await ctx.typing()
        try:
            pinned_messages = await ctx.channel.pins()
            if not pinned_messages:
                return await ctx.send("There are no pinned messages in this channel.")
            
            for message in pinned_messages:
                await message.unpin()
            
            embed = discord.Embed(
                title="Pins Cleared",
                description=f"Successfully unpinned all {len(pinned_messages)} messages in this channel.",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Made By TheHolyOneZ")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @commands.command(name="nickall")
    @has_permissions(manage_nicknames=True)
    async def nick_all(self, ctx, *, new_name: str):
        await ctx.typing()
        success_count = 0
        failed_members = []
        for member in ctx.guild.members:
            if ctx.author.top_role > member.top_role or ctx.author.id == ctx.guild.owner_id:
                try:
                    await member.edit(nick=new_name)
                    success_count += 1
                except discord.Forbidden:
                    failed_members.append(member.mention)
        
        embed = discord.Embed(
            title="Nicknames Updated",
            description=f"Successfully changed the nicknames of {success_count} members to `{new_name}`.",
            color=discord.Color.green()
        )
        if failed_members:
            embed.add_field(name="Failed to change", value="\n".join(failed_members), inline=False)
        embed.set_footer(text=f"Made By TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.command(name="resetnicks")
    @has_permissions(manage_nicknames=True)
    async def reset_nicks(self, ctx):
        await ctx.typing()
        success_count = 0
        failed_members = []
        for member in ctx.guild.members:
            if ctx.author.top_role > member.top_role or ctx.author.id == ctx.guild.owner_id:
                try:
                    await member.edit(nick=None)
                    success_count += 1
                except discord.Forbidden:
                    failed_members.append(member.mention)
        
        embed = discord.Embed(
            title="Nicknames Reset",
            description=f"Successfully reset the nicknames of {success_count} members.",
            color=discord.Color.green()
        )
        if failed_members:
            embed.add_field(name="Failed to reset", value="\n".join(failed_members), inline=False)
        embed.set_footer(text=f"Made By TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.command(name="roleremoveall")
    @has_permissions(manage_roles=True)
    async def role_remove_all(self, ctx, role: discord.Role):
        await ctx.typing()
        success_count = 0
        failed_members = []
        for member in role.members:
            if ctx.author.top_role > member.top_role or ctx.author.id == ctx.guild.owner_id:
                try:
                    await member.remove_roles(role)
                    success_count += 1
                except discord.Forbidden:
                    failed_members.append(member.mention)
        
        embed = discord.Embed(
            title=f"Role Removed",
            description=f"Successfully removed the role `{role.name}` from {success_count} members.",
            color=discord.Color.green()
        )
        if failed_members:
            embed.add_field(name="Failed to remove from", value="\n".join(failed_members), inline=False)
        embed.set_footer(text=f"Made By TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.command(name="rolebots")
    @has_permissions(manage_roles=True)
    async def role_bots(self, ctx, role: discord.Role):
        await ctx.typing()
        added_count = 0
        removed_count = 0
        failed_bots = []

        for member in ctx.guild.members:
            if member.bot:
                if role in member.roles:
                    try:
                        await member.remove_roles(role)
                        removed_count += 1
                    except discord.Forbidden:
                        failed_bots.append(member.mention)
                else:
                    try:
                        await member.add_roles(role)
                        added_count += 1
                    except discord.Forbidden:
                        failed_bots.append(member.mention)

        embed = discord.Embed(
            title=f"Role `{role.name}` Status for Bots",
            description=f"Added to {added_count} bots and removed from {removed_count} bots.",
            color=discord.Color.blue()
        )
        if failed_bots:
            embed.add_field(name="Failed to process", value="\n".join(failed_bots), inline=False)
        embed.set_footer(text=f"Made By TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.command(name="rolehumans")
    @has_permissions(manage_roles=True)
    async def role_humans(self, ctx, role: discord.Role):
        await ctx.typing()
        added_count = 0
        removed_count = 0
        failed_humans = []

        for member in ctx.guild.members:
            if not member.bot:
                if role in member.roles:
                    try:
                        await member.remove_roles(role)
                        removed_count += 1
                    except discord.Forbidden:
                        failed_humans.append(member.mention)
                else:
                    try:
                        await member.add_roles(role)
                        added_count += 1
                    except discord.Forbidden:
                        failed_humans.append(member.mention)

        embed = discord.Embed(
            title=f"Role `{role.name}` Status for Humans",
            description=f"Added to {added_count} humans and removed from {removed_count} humans.",
            color=discord.Color.blue()
        )
        if failed_humans:
            embed.add_field(name="Failed to process", value="\n".join(failed_humans), inline=False)
        embed.set_footer(text=f"Made By TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.command(name="serverage")
    async def server_age(self, ctx):
        created_at = ctx.guild.created_at
        age = discord.utils.utcnow() - created_at
        days = age.days
        years = days // 365
        months = (days % 365) // 30
        
        embed = discord.Embed(
            title=f"Server Age of {ctx.guild.name}",
            description=f"This server was created on **{discord.utils.format_dt(created_at, style='F')}**.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Total Age", value=f"{years} years, {months} months, and {days % 30} days old.", inline=False)
        embed.set_footer(text=f"Made By TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.command(name="membercount")
    async def member_count(self, ctx):
        member_count = ctx.guild.member_count
        embed = discord.Embed(
            title=f"Member Count for {ctx.guild.name}",
            description=f"There are currently **{member_count}** members in this server.",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Made By TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.command(name="onlinecount")
    async def online_count(self, ctx):
        online_members = [member for member in ctx.guild.members if member.status != discord.Status.offline]
        online_count = len(online_members)
        embed = discord.Embed(
            title=f"Online Members in {ctx.guild.name}",
            description=f"There are currently **{online_count}** members online.",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Made By TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.command(name="rolecount")
    async def role_count(self, ctx, role: discord.Role):
        member_count = len(role.members)
        embed = discord.Embed(
            title=f"Role Count for {role.name}",
            description=f"There are **{member_count}** members with the role `{role.name}`.",
            color=role.color
        )
        embed.set_footer(text=f"Made By TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.command(name="joined")
    async def joined_date(self, ctx, member: discord.Member):
        joined_at = member.joined_at
        embed = discord.Embed(
            title=f"{member.display_name}'s Joined Date",
            description=f"{member.mention} joined this server on **{discord.utils.format_dt(joined_at, style='F')}**.",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Made By TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.command(name="created")
    async def account_created_date(self, ctx, member: discord.Member):
        created_at = member.created_at
        embed = discord.Embed(
            title=f"{member.display_name}'s Account Creation Date",
            description=f"{member.mention}'s account was created on **{discord.utils.format_dt(created_at, style='F')}**.",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Made By TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.command(name="randomuser")
    async def random_user(self, ctx):
        online_members = [member for member in ctx.guild.members if member.status != discord.Status.offline and not member.bot]
        if not online_members:
            return await ctx.send("There are no online human members to pick from.")
        
        random_member = random.choice(online_members)
        embed = discord.Embed(
            title="Random User Selected",
            description=f"The chosen user is: {random_member.mention}",
            color=discord.Color.purple()
        )
        embed.set_thumbnail(url=random_member.display_avatar.url)
        embed.set_footer(text=f"Made By TheHolyOneZ")
        await ctx.send(embed=embed)

    @commands.command(name="ubanner")
    async def user_banner(self, ctx, member: discord.User):
        await ctx.typing()
        
        user = await self.bot.fetch_user(member.id)
        if user.banner:
            embed = discord.Embed(
                title=f"{user.display_name}'s Profile Banner",
                color=discord.Color.purple()
            )
            embed.set_image(url=user.banner.url)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"{user.display_name} does not have a profile banner.")

async def setup(bot):
    await bot.add_cog(ExtraUtilsCog(bot))
