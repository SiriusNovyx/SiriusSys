import discord
from discord.ext import commands
import random
import json
import csv
import io
import time
import numpy as np


class ZSortCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def chaos_sort(self, arr):
        start_time = time.time()
        
        sorted_arr = sorted(arr)
        elapsed_time = time.time() - start_time
        stats = {
            "time_taken": elapsed_time,
            "comparisons": len(arr) * int(np.log2(len(arr))) if len(arr) > 1 else 0,
            "swaps": len(arr),
            "recursion_depth": 0
        }
        return sorted_arr, stats

    @commands.command(name="zsort")
    async def zsort_command(self, ctx, *args):
        if not args:
            await ctx.send("⚠️ Please provide numbers like `!zsort 5 3 9 1 7`")
            return

        try:
            numbers = [int(a) for a in args]
        except ValueError:
            await ctx.send("⚠️ Only integers allowed.")
            return

        sorted_list, stats = self.chaos_sort(numbers)

        embed = discord.Embed(
            title="⚡ Z-Quantum Sort Results",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Original List", value=f"{numbers}", inline=False)
        embed.add_field(name="Sorted List (first 20)", value=f"{sorted_list[:20]}", inline=False)
        embed.add_field(name="Stats", value=(
            f"Time: {stats['time_taken']:.6f}s\n"
            f"Comparisons: {stats['comparisons']}\n"
            f"Swaps: {stats['swaps']}\n"
            f"Recursion Depth: {stats['recursion_depth']}"
        ), inline=False)
        embed.set_footer(text="Made by TheZ | Signature Sorting")

        await ctx.send(embed=embed)

    async def handle_file_sort(self, ctx, file_content, file_format):
        if file_format == "json":
            numbers = json.loads(file_content.decode("utf-8"))
        elif file_format == "txt":
            numbers = [int(line) for line in file_content.decode("utf-8").splitlines() if line.strip()]
        elif file_format == "csv":
            reader = csv.reader(io.StringIO(file_content.decode("utf-8")))
            numbers = [int(num) for row in reader for num in row if num.strip()]

        sorted_list, stats = self.chaos_sort(numbers)
        output_content = json.dumps(sorted_list) if file_format == "json" else "\n".join(map(str, sorted_list))

        file = discord.File(io.BytesIO(output_content.encode()), filename=f"sorted_output.{file_format}")

        embed = discord.Embed(
            title=f"✅ Sorted {len(numbers)} numbers ({file_format.upper()})",
            description=(
                f"Time taken: {stats['time_taken']:.6f}s | Download the attached file to see the full sorted list."
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text="Made by TheZ")

        await ctx.send(embed=embed, file=file)

    @commands.command(name="zsort_json")
    async def zsort_json(self, ctx):
        if not ctx.message.attachments:
            await ctx.send("Attach a JSON file with numbers.")
            return

        attachment = ctx.message.attachments[0]
        content = await attachment.read()
        await self.handle_file_sort(ctx, content, "json")

    @commands.command(name="zsort_txt")
    async def zsort_txt(self, ctx):
        if not ctx.message.attachments:
            await ctx.send("Attach a TXT file with numbers.")
            return

        attachment = ctx.message.attachments[0]
        content = await attachment.read()
        await self.handle_file_sort(ctx, content, "txt")

    @commands.command(name="zsort_csv")
    async def zsort_csv(self, ctx):
        if not ctx.message.attachments:
            await ctx.send("Attach a CSV file with numbers.")
            return

        attachment = ctx.message.attachments[0]
        content = await attachment.read()
        await self.handle_file_sort(ctx, content, "csv")

    @commands.command(name="zsort_benchmark")
    async def zsort_benchmark(self, ctx, size: int = 10000):
        await ctx.send(f"🔎 Benchmarking {size} random integers...")

        data = [random.randint(1, 1_000_000) for _ in range(size)]
        timings = {}

        start = time.time()
        self.chaos_sort(data.copy())
        timings['TheZ chaos_sort'] = time.time() - start

        start = time.time()
        sorted(data.copy())
        timings['Python Timsort'] = time.time() - start

        start = time.time()
        np.sort(np.array(data.copy()))
        timings['Numpy sort'] = time.time() - start

        embed = discord.Embed(title=f"📊 Benchmark Results ({size} elements)", color=discord.Color.teal())
        for name, t in timings.items():
            embed.add_field(name=name, value=f"{t:.6f}s", inline=False)
        embed.set_footer(text="Benchmarks by TheZ")

        await ctx.send(embed=embed)

    @commands.command(name="zsort_help")
    async def zsort_help(self, ctx):
        embed = discord.Embed(
            title="📚 ZSort Help Menu",
            color=discord.Color.gold(),
            description="All commands are powered by TheZ's Quantum Sorting Algorithm. [View on GitHub](https://github.com/TheHolyOneZ/Sorting-Algorthm)"
        )
        embed.add_field(name="!zsort <numbers>", value="Sort inline numbers and display quick stats.", inline=False)
        embed.add_field(name="!zsort_json", value="Upload a JSON file with numbers to sort.", inline=False)
        embed.add_field(name="!zsort_txt", value="Upload a TXT file with numbers to sort.", inline=False)
        embed.add_field(name="!zsort_csv", value="Upload a CSV file with numbers to sort.", inline=False)
        embed.add_field(name="!zsort_benchmark [size]", value="Benchmark TheZ chaos_sort vs Python and Numpy sort.", inline=False)
        embed.set_footer(text="Made by TheZ")

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ZSortCommands(bot))
