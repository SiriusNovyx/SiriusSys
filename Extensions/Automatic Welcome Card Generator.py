import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import aiohttp
import io
from typing import Optional, Dict, Any
import colorsys
from datetime import datetime
import math
import random

class WelcomeCardGenerator(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.base_dir = "WelcomeCards"
        self.config_path = os.path.join(self.base_dir, "config.json")
        self.templates_dir = os.path.join(self.base_dir, "templates")
        self.fonts_dir = os.path.join(self.base_dir, "fonts")
        self.backgrounds_dir = os.path.join(self.base_dir, "backgrounds")
        self.setup_directories()
        self.config = self._load_config()
        self.default_fonts = self._setup_fonts()
        
    def setup_directories(self):
        for directory in [self.base_dir, self.templates_dir, self.fonts_dir, self.backgrounds_dir]:
            os.makedirs(directory, exist_ok=True)
            
    def _load_config(self) -> Dict:
        if not os.path.exists(self.config_path):
            default_config = {
                "guilds": {},
                "global_settings": {
                    "default_template": "modern",
                    "max_custom_templates": 10
                }
            }
            with open(self.config_path, 'w') as f:
                json.dump(default_config, f, indent=4)
            return default_config
            
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading welcome card config: {e}")
            return {"guilds": {}, "global_settings": {"default_template": "modern", "max_custom_templates": 10}}
            
    def _save_config(self) -> None:
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving welcome card config: {e}")
            
    def _get_guild_config(self, guild_id: int) -> Dict:
        guild_id_str = str(guild_id)
        if guild_id_str not in self.config["guilds"]:
            self.config["guilds"][guild_id_str] = {
                "enabled": False,
                "channel_id": None,
                "template": "modern",
                "background_color": "#2F3136",
                "text_color": "#FFFFFF",
                "accent_color": "#5865F2",
                "welcome_message": "Welcome to {server}!",
                "subtitle": "We're glad to have you here, {user}!",
                "show_member_count": True,
                "show_join_date": True,
                "custom_background": None,
                "font_family": "default",
                "border_enabled": True,
                "border_color": "#5865F2",
                "shadow_enabled": True,
                "blur_background": False
            }
        return self.config["guilds"][guild_id_str]
        
    def _setup_fonts(self) -> Dict:
        fonts = {}
        try:
            fonts['title'] = ImageFont.truetype("arial.ttf", 54)
            fonts['subtitle'] = ImageFont.truetype("arial.ttf", 30)
            fonts['info'] = ImageFont.truetype("arial.ttf", 28)
        except:
            try:
                fonts['title'] = ImageFont.load_default()
                fonts['subtitle'] = ImageFont.load_default()
                fonts['info'] = ImageFont.load_default()
            except:
                fonts['title'] = None
                fonts['subtitle'] = None
                fonts['info'] = None
        return fonts
        
    async def download_avatar(self, user: discord.Member) -> Image.Image:
        try:
            avatar_url = user.display_avatar.url
            async with aiohttp.ClientSession() as session:
                async with session.get(str(avatar_url)) as resp:
                    if resp.status == 200:
                        avatar_bytes = await resp.read()
                        avatar = Image.open(io.BytesIO(avatar_bytes))
                        avatar = avatar.convert("RGBA")
                        avatar = avatar.resize((200, 200), Image.Resampling.LANCZOS)
                        return avatar
        except Exception as e:
            print(f"Error downloading avatar: {e}")
            
        avatar = Image.new("RGBA", (200, 200), (114, 137, 218, 255))
        draw = ImageDraw.Draw(avatar)
        draw.text((100, 100), user.name[0].upper(), fill="white", anchor="mm", font=self.default_fonts['title'])
        return avatar
        
    def create_circular_avatar(self, avatar: Image.Image, template: str = "modern") -> Image.Image:
        mask = Image.new("L", (200, 200), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, 200, 200), fill=255)
        
        circular_avatar = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        circular_avatar.paste(avatar, (0, 0))
        circular_avatar.putalpha(mask)
        
        if template in ["neon", "cyberpunk"]:
            glow = Image.new("RGBA", (220, 220), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow)
            for i in range(10):
                alpha = 30 - i * 3
                glow_draw.ellipse([(10-i, 10-i), (210+i, 210+i)], outline=(0, 255, 255, alpha), width=2)
            
            final_avatar = Image.new("RGBA", (220, 220), (0, 0, 0, 0))
            final_avatar.paste(glow, (0, 0), glow)
            final_avatar.paste(circular_avatar, (10, 10), circular_avatar)
            return final_avatar
        
        return circular_avatar
        
    def hex_to_rgb(self, hex_color: str) -> tuple:
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
    def create_gradient(self, width: int, height: int, color1: tuple, color2: tuple, direction: str = "horizontal") -> Image.Image:
        gradient = Image.new("RGBA", (width, height))
        draw = ImageDraw.Draw(gradient)
        
        if direction == "horizontal":
            for x in range(width):
                ratio = x / width
                r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
                g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
                b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
                draw.line([(x, 0), (x, height)], fill=(r, g, b))
        elif direction == "vertical":
            for y in range(height):
                ratio = y / height
                r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
                g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
                b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
                draw.line([(0, y), (width, y)], fill=(r, g, b))
        elif direction == "diagonal":
            for x in range(width):
                for y in range(height):
                    ratio = (x + y) / (width + height)
                    r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
                    g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
                    b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
                    draw.point((x, y), fill=(r, g, b))
        
        return gradient
        
    def create_geometric_pattern(self, width: int, height: int, color: tuple) -> Image.Image:
        pattern = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(pattern)
        
        for i in range(0, width, 60):
            for j in range(0, height, 60):
                alpha = random.randint(10, 30)
                draw.polygon([(i, j+30), (i+30, j), (i+60, j+30), (i+30, j+60)], 
                           fill=(*color, alpha))
        
        return pattern
        
    def add_glass_effect(self, img: Image.Image, x: int, y: int, w: int, h: int) -> Image.Image:
        glass_overlay = Image.new("RGBA", (w, h), (255, 255, 255, 30))
        
        highlight = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        highlight_draw = ImageDraw.Draw(highlight)
        highlight_draw.rectangle([(0, 0), (w, h//3)], fill=(255, 255, 255, 40))
        
        glass_overlay = Image.alpha_composite(glass_overlay, highlight)
        img.paste(glass_overlay, (x, y), glass_overlay)
        
        return img

    async def generate_welcome_card(self, user: discord.Member, guild_config: Dict) -> io.BytesIO:
        
        width, height = 1000, 500
        template = guild_config.get("template", "modern")
        

        if template == "neon":
            return await self._generate_neon_card(user, guild_config, width, height)
        elif template == "glass":
            return await self._generate_glass_card(user, guild_config, width, height)
        elif template == "cyberpunk":
            return await self._generate_cyberpunk_card(user, guild_config, width, height)
        elif template == "elegant":
            return await self._generate_elegant_card(user, guild_config, width, height)
        elif template == "cosmic":
            return await self._generate_cosmic_card(user, guild_config, width, height)
        elif template == "aurora":
            return await self._generate_aurora_card(user, guild_config, width, height)
        elif template == "thez":
            return await self._generate_thez_card(user, guild_config, width, height)
        else:
            return await self._generate_modern_card(user, guild_config, width, height)

    async def _generate_modern_card(self, user: discord.Member, guild_config: Dict, width: int, height: int) -> io.BytesIO:
        

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        

        bg_color = self.hex_to_rgb(guild_config["background_color"])
        accent_color = self.hex_to_rgb(guild_config["accent_color"])
        

        for y in range(height):
            ratio = y / height
            r = int(bg_color[0] * (1 - ratio) + accent_color[0] * ratio * 0.3)
            g = int(bg_color[1] * (1 - ratio) + accent_color[1] * ratio * 0.3)
            b = int(bg_color[2] * (1 - ratio) + accent_color[2] * ratio * 0.3)
            
            gradient_line = Image.new("RGBA", (width, 1), (r, g, b, 255))
            img.paste(gradient_line, (0, y))
        
        draw = ImageDraw.Draw(img)
        

        self._add_geometric_patterns(draw, width, height, accent_color)
        

        panel = Image.new("RGBA", (width - 100, height - 100), (255, 255, 255, 20))
        panel_blur = panel.filter(ImageFilter.GaussianBlur(radius=10))
        img.paste(panel_blur, (50, 50), panel_blur)
        

        self._add_premium_border(draw, width, height, accent_color)
        

        avatar = await self.download_avatar(user)
        avatar = avatar.resize((140, 140), Image.Resampling.LANCZOS)
        

        circular_avatar = self._create_premium_avatar(avatar, accent_color)
        

        avatar_x, avatar_y = 80, 80
        img.paste(circular_avatar, (avatar_x, avatar_y), circular_avatar)
        

        self._add_modern_premium_text(draw, user, guild_config, width, height, avatar_x + 160)
        

        self._add_modern_decorations(draw, width, height, accent_color)
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', quality=95)
        img_bytes.seek(0)
        return img_bytes

    async def _generate_neon_card(self, user: discord.Member, guild_config: Dict, width: int, height: int) -> io.BytesIO:
        

        img = Image.new("RGBA", (width, height), (5, 5, 20, 255))
        draw = ImageDraw.Draw(img)
        

        self._add_neon_grid(draw, width, height)
        

        neon_colors = [(0, 255, 255), (255, 0, 255), (255, 255, 0)]
        

        for i in range(8):
            alpha = 150 - i * 15
            color = (*neon_colors[0], alpha)
            draw.rectangle([(60 + i, 60 + i), (width - 60 - i, height - 60 - i)], 
                         outline=color, width=2)
        

        avatar = await self.download_avatar(user)
        avatar = avatar.resize((120, 120), Image.Resampling.LANCZOS)
        

        neon_avatar = self._create_neon_avatar(avatar, neon_colors)
        
        avatar_x, avatar_y = 100, 120
        img.paste(neon_avatar, (avatar_x, avatar_y), neon_avatar)
        

        self._add_neon_premium_text(draw, user, guild_config, width, height, avatar_x + 140)
        

        self._add_neon_effects(draw, width, height, neon_colors)
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', quality=95)
        img_bytes.seek(0)
        return img_bytes

    async def _generate_glass_card(self, user: discord.Member, guild_config: Dict, width: int, height: int) -> io.BytesIO:
        

        img = Image.new("RGBA", (width, height), (30, 30, 46, 255))
        

        for i in range(height):
            ratio = i / height
            r = int(30 + (100 * ratio))
            g = int(30 + (150 * ratio))
            b = int(46 + (200 * ratio))
            
            line = Image.new("RGBA", (width, 1), (r, g, b, 255))
            img.paste(line, (0, i))
        

        self._add_glass_orbs(img, width, height)
        
        draw = ImageDraw.Draw(img)
        

        glass_panel = Image.new("RGBA", (width - 80, height - 80), (255, 255, 255, 40))
        glass_blur = glass_panel.filter(ImageFilter.GaussianBlur(radius=15))
        img.paste(glass_blur, (40, 40), glass_blur)
        

        for i in range(3):
            alpha = 100 - i * 20
            draw.rectangle([(40 + i, 40 + i), (width - 40 - i, height - 40 - i)], 
                         outline=(255, 255, 255, alpha), width=1)
        

        avatar = await self.download_avatar(user)
        avatar = avatar.resize((130, 130), Image.Resampling.LANCZOS)
        
        glass_avatar = self._create_glass_avatar(avatar)
        
        avatar_x, avatar_y = 90, 100
        img.paste(glass_avatar, (avatar_x, avatar_y), glass_avatar)
        

        self._add_glass_premium_text(draw, user, guild_config, width, height, avatar_x + 150)
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', quality=95)
        img_bytes.seek(0)
        return img_bytes

    async def _generate_cyberpunk_card(self, user: discord.Member, guild_config: Dict, width: int, height: int) -> io.BytesIO:
        

        img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
        

        self._add_matrix_rain(img, width, height)
        
        draw = ImageDraw.Draw(img)
        

        cyber_colors = [(255, 0, 128), (0, 255, 255), (255, 255, 0)]
        

        self._add_cyberpunk_hud(draw, width, height, cyber_colors)
        

        avatar = await self.download_avatar(user)
        avatar = avatar.resize((125, 125), Image.Resampling.LANCZOS)
        
        cyber_avatar = self._create_cyberpunk_avatar(avatar, cyber_colors)
        
        avatar_x, avatar_y = 100, 110
        img.paste(cyber_avatar, (avatar_x, avatar_y), cyber_avatar)
        

        self._add_cyberpunk_premium_text(draw, user, guild_config, width, height, avatar_x + 145)
        

        self._add_cyberpunk_effects(draw, width, height, cyber_colors)
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', quality=95)
        img_bytes.seek(0)
        return img_bytes

    async def _generate_elegant_card(self, user: discord.Member, guild_config: Dict, width: int, height: int) -> io.BytesIO:
        

        img = Image.new("RGBA", (width, height), (248, 248, 245, 255))
        

        for i in range(height):
            ratio = i / height
            r = int(248 - (20 * ratio))
            g = int(248 - (30 * ratio))
            b = int(245 - (40 * ratio))
            
            line = Image.new("RGBA", (width, 1), (r, g, b, 255))
            img.paste(line, (0, i))
        
        draw = ImageDraw.Draw(img)
        

        self._add_elegant_patterns(draw, width, height)
        

        gold_color = (184, 150, 107)
        self._add_luxury_frame(draw, width, height, gold_color)
        

        avatar = await self.download_avatar(user)
        avatar = avatar.resize((135, 135), Image.Resampling.LANCZOS)
        
        elegant_avatar = self._create_elegant_avatar(avatar, gold_color)
        
        avatar_x, avatar_y = 95, 105
        img.paste(elegant_avatar, (avatar_x, avatar_y), elegant_avatar)
        

        self._add_elegant_premium_text(draw, user, guild_config, width, height, avatar_x + 155)
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', quality=95)
        img_bytes.seek(0)
        return img_bytes

    async def _generate_cosmic_card(self, user: discord.Member, guild_config: Dict, width: int, height: int) -> io.BytesIO:
        

        img = Image.new("RGBA", (width, height), (5, 5, 20, 255))
        

        self._add_nebula_background(img, width, height)
        

        self._add_starfield(img, width, height)
        
        draw = ImageDraw.Draw(img)
        

        cosmic_colors = [(100, 200, 255), (255, 100, 200), (200, 255, 100)]
        self._add_cosmic_rings(draw, width, height, cosmic_colors)
        

        avatar = await self.download_avatar(user)
        avatar = avatar.resize((128, 128), Image.Resampling.LANCZOS)
        
        cosmic_avatar = self._create_cosmic_avatar(avatar, cosmic_colors)
        
        avatar_x, avatar_y = 105, 115
        img.paste(cosmic_avatar, (avatar_x, avatar_y), cosmic_avatar)
        

        self._add_cosmic_premium_text(draw, user, guild_config, width, height, avatar_x + 148)
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', quality=95)
        img_bytes.seek(0)
        return img_bytes

    async def _generate_aurora_card(self, user: discord.Member, guild_config: Dict, width: int, height: int) -> io.BytesIO:
        

        img = Image.new("RGBA", (width, height), (15, 20, 25, 255))
        

        self._add_aurora_waves(img, width, height)
        
        draw = ImageDraw.Draw(img)
        

        aurora_colors = [(0, 255, 150), (100, 255, 200), (200, 100, 255)]
        

        self._add_aurora_panels(draw, width, height, aurora_colors)
        

        avatar = await self.download_avatar(user)
        avatar = avatar.resize((132, 132), Image.Resampling.LANCZOS)
        
        aurora_avatar = self._create_aurora_avatar(avatar, aurora_colors)
        
        avatar_x, avatar_y = 98, 108
        img.paste(aurora_avatar, (avatar_x, avatar_y), aurora_avatar)
        

        self._add_aurora_premium_text(draw, user, guild_config, width, height, avatar_x + 152)
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', quality=95)
        img_bytes.seek(0)
        return img_bytes

    def _create_premium_avatar(self, avatar: Image.Image, accent_color: tuple) -> Image.Image:
        
        size = avatar.size[0]
        

        glow_size = size + 40
        glow_img = Image.new("RGBA", (glow_size, glow_size), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_img)
        

        for i in range(20):
            alpha = 100 - i * 4
            if alpha > 0:
                glow_draw.ellipse([(i, i), (glow_size - i, glow_size - i)], 
                                outline=(*accent_color, alpha), width=2)
        

        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size, size), fill=255)
        

        circular_avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        circular_avatar.paste(avatar, (0, 0))
        circular_avatar.putalpha(mask)
        

        final_avatar = Image.new("RGBA", (glow_size, glow_size), (0, 0, 0, 0))
        final_avatar.paste(glow_img, (0, 0), glow_img)
        final_avatar.paste(circular_avatar, (20, 20), circular_avatar)
        

        border_draw = ImageDraw.Draw(final_avatar)
        for i in range(3):
            border_draw.ellipse([(18 + i, 18 + i), (glow_size - 18 - i, glow_size - 18 - i)], 
                              outline=(*accent_color, 200 - i * 50), width=2)
        
        return final_avatar

    def _create_neon_avatar(self, avatar: Image.Image, neon_colors: list) -> Image.Image:
        
        size = avatar.size[0]
        glow_size = size + 50
        

        neon_img = Image.new("RGBA", (glow_size, glow_size), (0, 0, 0, 0))
        neon_draw = ImageDraw.Draw(neon_img)
        

        for color_idx, color in enumerate(neon_colors):
            for i in range(15):
                alpha = 120 - i * 6
                if alpha > 0:
                    offset = color_idx * 5 + i
                    neon_draw.ellipse([(offset, offset), (glow_size - offset, glow_size - offset)], 
                                    outline=(*color, alpha), width=3)
        

        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size, size), fill=255)
        
        circular_avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        circular_avatar.paste(avatar, (0, 0))
        circular_avatar.putalpha(mask)
        

        final_avatar = Image.new("RGBA", (glow_size, glow_size), (0, 0, 0, 0))
        final_avatar.paste(neon_img, (0, 0), neon_img)
        final_avatar.paste(circular_avatar, (25, 25), circular_avatar)
        
        return final_avatar

    def _create_glass_avatar(self, avatar: Image.Image) -> Image.Image:
        
        size = avatar.size[0]
        glass_size = size + 30
        

        glass_bg = Image.new("RGBA", (glass_size, glass_size), (255, 255, 255, 60))
        glass_blur = glass_bg.filter(ImageFilter.GaussianBlur(radius=8))
        

        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size, size), fill=255)
        
        circular_avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        circular_avatar.paste(avatar, (0, 0))
        circular_avatar.putalpha(mask)
        

        final_avatar = Image.new("RGBA", (glass_size, glass_size), (0, 0, 0, 0))
        final_avatar.paste(glass_blur, (0, 0), glass_blur)
        final_avatar.paste(circular_avatar, (15, 15), circular_avatar)
        

        glass_draw = ImageDraw.Draw(final_avatar)
        glass_draw.ellipse([(12, 12), (glass_size - 12, glass_size - 12)], 
                         outline=(255, 255, 255, 150), width=2)
        
        return final_avatar

    def _create_cyberpunk_avatar(self, avatar: Image.Image, cyber_colors: list) -> Image.Image:
        
        size = avatar.size[0]
        cyber_size = size + 45
        

        cyber_img = Image.new("RGBA", (cyber_size, cyber_size), (0, 0, 0, 0))
        cyber_draw = ImageDraw.Draw(cyber_img)
        

        for i in range(0, cyber_size, 4):
            cyber_draw.line([(0, i), (cyber_size, i)], fill=(0, 255, 255, 30), width=1)
        

        for i, color in enumerate(cyber_colors):
            for j in range(8):
                alpha = 150 - j * 15
                offset = i * 3 + j
                cyber_draw.ellipse([(offset, offset), (cyber_size - offset, cyber_size - offset)], 
                                 outline=(*color, alpha), width=2)
        

        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size, size), fill=255)
        
        circular_avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        circular_avatar.paste(avatar, (0, 0))
        circular_avatar.putalpha(mask)
        

        final_avatar = Image.new("RGBA", (cyber_size, cyber_size), (0, 0, 0, 0))
        final_avatar.paste(cyber_img, (0, 0), cyber_img)
        final_avatar.paste(circular_avatar, (22, 22), circular_avatar)
        
        return final_avatar

    def _create_elegant_avatar(self, avatar: Image.Image, gold_color: tuple) -> Image.Image:
        
        size = avatar.size[0]
        elegant_size = size + 35
        

        frame_img = Image.new("RGBA", (elegant_size, elegant_size), (0, 0, 0, 0))
        frame_draw = ImageDraw.Draw(frame_img)
        

        for i in range(6):
            alpha = 200 - i * 25
            frame_draw.ellipse([(i * 2, i * 2), (elegant_size - i * 2, elegant_size - i * 2)], 
                             outline=(*gold_color, alpha), width=3)
        

        corner_size = 15
        for angle in [0, 90, 180, 270]:

            pass
        

        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size, size), fill=255)
        
        circular_avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        circular_avatar.paste(avatar, (0, 0))
        circular_avatar.putalpha(mask)
        

        final_avatar = Image.new("RGBA", (elegant_size, elegant_size), (0, 0, 0, 0))
        final_avatar.paste(frame_img, (0, 0), frame_img)
        final_avatar.paste(circular_avatar, (17, 17), circular_avatar)
        
        return final_avatar

    def _create_cosmic_avatar(self, avatar: Image.Image, cosmic_colors: list) -> Image.Image:
        
        size = avatar.size[0]
        cosmic_size = size + 48
        

        cosmic_img = Image.new("RGBA", (cosmic_size, cosmic_size), (0, 0, 0, 0))
        cosmic_draw = ImageDraw.Draw(cosmic_img)
        

        for i, color in enumerate(cosmic_colors):
            for j in range(12):
                alpha = 140 - j * 10
                if alpha > 0:
                    radius = i * 8 + j * 2
                    cosmic_draw.ellipse([(24 - radius, 24 - radius), 
                                       (cosmic_size - 24 + radius, cosmic_size - 24 + radius)], 
                                      outline=(*color, alpha), width=2)
        

        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size, size), fill=255)
        
        circular_avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        circular_avatar.paste(avatar, (0, 0))
        circular_avatar.putalpha(mask)
        

        final_avatar = Image.new("RGBA", (cosmic_size, cosmic_size), (0, 0, 0, 0))
        final_avatar.paste(cosmic_img, (0, 0), cosmic_img)
        final_avatar.paste(circular_avatar, (24, 24), circular_avatar)
        
        return final_avatar

    def _create_aurora_avatar(self, avatar: Image.Image, aurora_colors: list) -> Image.Image:
        
        size = avatar.size[0]
        aurora_size = size + 42
        

        aurora_img = Image.new("RGBA", (aurora_size, aurora_size), (0, 0, 0, 0))
        aurora_draw = ImageDraw.Draw(aurora_img)
        

        import math
        for i in range(20):
            for color_idx, color in enumerate(aurora_colors):
                alpha = 120 - i * 4
                if alpha > 0:

                    offset = i + math.sin(color_idx) * 5
                    aurora_draw.ellipse([(offset, offset), (aurora_size - offset, aurora_size - offset)], 
                                      outline=(*color, alpha), width=2)
        

        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size, size), fill=255)
        
        circular_avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        circular_avatar.paste(avatar, (0, 0))
        circular_avatar.putalpha(mask)
        

        final_avatar = Image.new("RGBA", (aurora_size, aurora_size), (0, 0, 0, 0))
        final_avatar.paste(aurora_img, (0, 0), aurora_img)
        final_avatar.paste(circular_avatar, (21, 21), circular_avatar)
        
        return final_avatar


    def _add_modern_premium_text(self, draw: ImageDraw.Draw, user: discord.Member, guild_config: Dict, width: int, height: int, text_x: int):
        
        welcome_text = guild_config["welcome_message"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        subtitle_text = guild_config["subtitle"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        

        max_width = width - text_x - 50
        

        welcome_y = 120
        line_height = 60
        

        welcome_lines = self._wrap_text(welcome_text, self.default_fonts['title'], max_width)
        
        for line_idx, line in enumerate(welcome_lines):
            current_y = welcome_y + (line_idx * line_height)
            
            if self.default_fonts['title']:

                draw.text((text_x + 3, current_y + 3), line, 
                         fill=(0, 0, 0, 120), font=self.default_fonts['title'], anchor="lm")

                draw.text((text_x, current_y), line, 
                         fill=self.hex_to_rgb(guild_config["text_color"]), font=self.default_fonts['title'], anchor="lm")
            else:
                draw.text((text_x + 3, current_y + 3), line, 
                         fill=(0, 0, 0, 120), anchor="lm")
                draw.text((text_x, current_y), line, 
                         fill=self.hex_to_rgb(guild_config["text_color"]), anchor="lm")
        

        subtitle_y = welcome_y + (len(welcome_lines) * line_height) + 20
        

        subtitle_lines = self._wrap_text(subtitle_text, self.default_fonts['subtitle'], max_width)
        subtitle_line_height = 40
        
        for line_idx, line in enumerate(subtitle_lines):
            current_y = subtitle_y + (line_idx * subtitle_line_height)
            
            if self.default_fonts['subtitle']:
                draw.text((text_x, current_y), line, 
                         fill=self.hex_to_rgb(guild_config["accent_color"]), font=self.default_fonts['subtitle'], anchor="lm")
            else:
                draw.text((text_x, current_y), line, 
                         fill=self.hex_to_rgb(guild_config["accent_color"]), anchor="lm")
        

        member_y = subtitle_y + (len(subtitle_lines) * subtitle_line_height) + 20
        

        if guild_config.get("show_member_count", True):
            member_text = f"Member #{user.guild.member_count}"
            
            if self.default_fonts['info']:
                draw.text((text_x, member_y), member_text, 
                         fill=self.hex_to_rgb(guild_config["text_color"]), font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x, member_y), member_text, 
                         fill=self.hex_to_rgb(guild_config["text_color"]), anchor="lm")
        

        if guild_config.get("show_join_date", True):
            join_text = f"Joined: {user.joined_at.strftime('%B %d, %Y')}"
            join_y = member_y + 30
            
            if self.default_fonts['info']:
                draw.text((text_x, join_y), join_text, 
                         fill=self.hex_to_rgb(guild_config["accent_color"]), font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x, join_y), join_text, 
                         fill=self.hex_to_rgb(guild_config["accent_color"]), anchor="lm")

    def _add_neon_premium_text(self, draw: ImageDraw.Draw, user: discord.Member, guild_config: Dict, width: int, height: int, text_x: int):
        
        welcome_text = guild_config["welcome_message"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        subtitle_text = guild_config["subtitle"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        

        max_width = width - text_x - 50
        

        neon_colors = [
            (255, 0, 255),
            (0, 255, 255),
            (255, 255, 0)
        ]
        

        welcome_y = 120
        line_height = 60
        

        welcome_lines = self._wrap_text(welcome_text, self.default_fonts['title'], max_width)
        
        for line_idx, line in enumerate(welcome_lines):
            current_y = welcome_y + (line_idx * line_height)
            

            for i in range(8):
                alpha = 100 - i * 10
                if alpha > 0:
                    for color in neon_colors:
                        if self.default_fonts['title']:
                            draw.text((text_x + i, current_y + i), line, 
                                     fill=(*color, alpha), font=self.default_fonts['title'], anchor="lm")
                        else:
                            draw.text((text_x + i, current_y + i), line, 
                                     fill=(*color, alpha), anchor="lm")
            

            if self.default_fonts['title']:
                draw.text((text_x, current_y), line, 
                         fill=(255, 255, 255), font=self.default_fonts['title'], anchor="lm")
            else:
                draw.text((text_x, current_y), line, fill=(255, 255, 255), anchor="lm")
        

        subtitle_y = welcome_y + (len(welcome_lines) * line_height) + 20
        

        subtitle_lines = self._wrap_text(subtitle_text, self.default_fonts['subtitle'], max_width)
        subtitle_line_height = 40
        
        for line_idx, line in enumerate(subtitle_lines):
            current_y = subtitle_y + (line_idx * subtitle_line_height)
            

            for i in range(6):
                alpha = 80 - i * 10
                if alpha > 0:
                    if self.default_fonts['subtitle']:
                        draw.text((text_x + i, current_y + i), line, 
                                 fill=(*neon_colors[0], alpha), font=self.default_fonts['subtitle'], anchor="lm")
                    else:
                        draw.text((text_x + i, current_y + i), line, 
                                 fill=(*neon_colors[0], alpha), anchor="lm")
            
            if self.default_fonts['subtitle']:
                draw.text((text_x, current_y), line, 
                         fill=neon_colors[0], font=self.default_fonts['subtitle'], anchor="lm")
            else:
                draw.text((text_x, current_y), line, fill=neon_colors[0], anchor="lm")
        

        member_y = subtitle_y + (len(subtitle_lines) * subtitle_line_height) + 20
        

        if guild_config.get("show_member_count", True):
            member_text = f"Member #{user.guild.member_count}"
            
            for i in range(4):
                alpha = 60 - i * 10
                if alpha > 0:
                    if self.default_fonts['info']:
                        draw.text((text_x + i, member_y + i), member_text, 
                                 fill=(*neon_colors[1], alpha), font=self.default_fonts['info'], anchor="lm")
                    else:
                        draw.text((text_x + i, member_y + i), member_text, 
                                 fill=(*neon_colors[1], alpha), anchor="lm")
            
            if self.default_fonts['info']:
                draw.text((text_x, member_y), member_text, 
                         fill=neon_colors[1], font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x, member_y), member_text, fill=neon_colors[1], anchor="lm")
        

        if guild_config.get("show_join_date", True):
            join_text = f"Joined: {user.joined_at.strftime('%B %d, %Y')}"
            join_y = member_y + 30
            
            for i in range(4):
                alpha = 60 - i * 10
                if alpha > 0:
                    if self.default_fonts['info']:
                        draw.text((text_x + i, join_y + i), join_text, 
                                 fill=(*neon_colors[2], alpha), font=self.default_fonts['info'], anchor="lm")
                    else:
                        draw.text((text_x + i, join_y + i), join_text, 
                                 fill=(*neon_colors[2], alpha), anchor="lm")
            
            if self.default_fonts['info']:
                draw.text((text_x, join_y), join_text, 
                         fill=neon_colors[2], font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x, join_y), join_text, fill=neon_colors[2], anchor="lm")

    def _add_glass_premium_text(self, draw: ImageDraw.Draw, user: discord.Member, guild_config: Dict, width: int, height: int, text_x: int):
        
        welcome_text = guild_config["welcome_message"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        subtitle_text = guild_config["subtitle"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        

        max_width = width - text_x - 50
        

        welcome_y = 120
        line_height = 60
        

        welcome_lines = self._wrap_text(welcome_text, self.default_fonts['title'], max_width)
        
        for line_idx, line in enumerate(welcome_lines):
            current_y = welcome_y + (line_idx * line_height)
            
            if self.default_fonts['title']:

                draw.text((text_x + 2, current_y + 2), line, 
                         fill=(255, 255, 255, 40), font=self.default_fonts['title'], anchor="lm")

                draw.text((text_x, current_y), line, 
                         fill=(255, 255, 255, 200), font=self.default_fonts['title'], anchor="lm")
            else:
                draw.text((text_x + 2, current_y + 2), line, 
                         fill=(255, 255, 255, 40), anchor="lm")
                draw.text((text_x, current_y), line, 
                         fill=(255, 255, 255, 200), anchor="lm")
        

        subtitle_y = welcome_y + (len(welcome_lines) * line_height) + 20
        

        subtitle_lines = self._wrap_text(subtitle_text, self.default_fonts['subtitle'], max_width)
        subtitle_line_height = 40
        
        for line_idx, line in enumerate(subtitle_lines):
            current_y = subtitle_y + (line_idx * subtitle_line_height)
            
            if self.default_fonts['subtitle']:

                draw.text((text_x + 1, current_y + 1), line, 
                         fill=(255, 255, 255, 30), font=self.default_fonts['subtitle'], anchor="lm")
                draw.text((text_x, current_y), line, 
                         fill=(255, 255, 255, 180), font=self.default_fonts['subtitle'], anchor="lm")
            else:
                draw.text((text_x + 1, current_y + 1), line, 
                         fill=(255, 255, 255, 30), anchor="lm")
                draw.text((text_x, current_y), line, 
                         fill=(255, 255, 255, 180), anchor="lm")
        

        member_y = subtitle_y + (len(subtitle_lines) * subtitle_line_height) + 20
        

        if guild_config.get("show_member_count", True):
            member_text = f"Member #{user.guild.member_count}"
            
            if self.default_fonts['info']:
                draw.text((text_x + 1, member_y + 1), member_text, 
                         fill=(255, 255, 255, 20), font=self.default_fonts['info'], anchor="lm")
                draw.text((text_x, member_y), member_text, 
                         fill=(255, 255, 255, 160), font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x + 1, member_y + 1), member_text, 
                         fill=(255, 255, 255, 20), anchor="lm")
                draw.text((text_x, member_y), member_text, 
                         fill=(255, 255, 255, 160), anchor="lm")
        

        if guild_config.get("show_join_date", True):
            join_text = f"Joined: {user.joined_at.strftime('%B %d, %Y')}"
            join_y = member_y + 30
            
            if self.default_fonts['info']:
                draw.text((text_x + 1, join_y + 1), join_text, 
                         fill=(255, 255, 255, 20), font=self.default_fonts['info'], anchor="lm")
                draw.text((text_x, join_y), join_text, 
                         fill=(255, 255, 255, 160), font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x + 1, join_y + 1), join_text, 
                         fill=(255, 255, 255, 20), anchor="lm")
                draw.text((text_x, join_y), join_text, 
                         fill=(255, 255, 255, 160), anchor="lm")

    def _add_cyberpunk_premium_text(self, draw: ImageDraw.Draw, user: discord.Member, guild_config: Dict, width: int, height: int, text_x: int):
        
        welcome_text = guild_config["welcome_message"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        subtitle_text = guild_config["subtitle"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        

        max_width = width - text_x - 50
        

        cyber_colors = [
            (255, 0, 128),
            (0, 255, 255),
            (255, 255, 0)
        ]
        

        welcome_y = 120
        line_height = 60
        

        welcome_lines = self._wrap_text(welcome_text, self.default_fonts['title'], max_width)
        
        for line_idx, line in enumerate(welcome_lines):
            current_y = welcome_y + (line_idx * line_height)
            

            for i in range(6):
                alpha = 120 - i * 15
                if alpha > 0:
                    for color in cyber_colors:
                        if self.default_fonts['title']:
                            draw.text((text_x + i, current_y + i), line, 
                                     fill=(*color, alpha), font=self.default_fonts['title'], anchor="lm")
                        else:
                            draw.text((text_x + i, current_y + i), line, 
                                     fill=(*color, alpha), anchor="lm")
            

            if self.default_fonts['title']:
                draw.text((text_x, current_y), line, 
                         fill=(255, 255, 255), font=self.default_fonts['title'], anchor="lm")
            else:
                draw.text((text_x, current_y), line, fill=(255, 255, 255), anchor="lm")
        

        subtitle_y = welcome_y + (len(welcome_lines) * line_height) + 20
        

        subtitle_lines = self._wrap_text(subtitle_text, self.default_fonts['subtitle'], max_width)
        subtitle_line_height = 40
        
        for line_idx, line in enumerate(subtitle_lines):
            current_y = subtitle_y + (line_idx * subtitle_line_height)
            

            for i in range(4):
                alpha = 100 - i * 20
                if alpha > 0:
                    if self.default_fonts['subtitle']:
                        draw.text((text_x + i, current_y + i), line, 
                                 fill=(*cyber_colors[0], alpha), font=self.default_fonts['subtitle'], anchor="lm")
                    else:
                        draw.text((text_x + i, current_y + i), line, 
                                 fill=(*cyber_colors[0], alpha), anchor="lm")
            
            if self.default_fonts['subtitle']:
                draw.text((text_x, current_y), line, 
                         fill=cyber_colors[0], font=self.default_fonts['subtitle'], anchor="lm")
            else:
                draw.text((text_x, current_y), line, fill=cyber_colors[0], anchor="lm")
        

        member_y = subtitle_y + (len(subtitle_lines) * subtitle_line_height) + 20
        

        if guild_config.get("show_member_count", True):
            member_text = f"Member #{user.guild.member_count}"
            
            for i in range(3):
                alpha = 80 - i * 20
                if alpha > 0:
                    if self.default_fonts['info']:
                        draw.text((text_x + i, member_y + i), member_text, 
                                 fill=(*cyber_colors[1], alpha), font=self.default_fonts['info'], anchor="lm")
                    else:
                        draw.text((text_x + i, member_y + i), member_text, 
                                 fill=(*cyber_colors[1], alpha), anchor="lm")
            
            if self.default_fonts['info']:
                draw.text((text_x, member_y), member_text, 
                         fill=cyber_colors[1], font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x, member_y), member_text, fill=cyber_colors[1], anchor="lm")
        

        if guild_config.get("show_join_date", True):
            join_text = f"Joined: {user.joined_at.strftime('%B %d, %Y')}"
            join_y = member_y + 30
            
            for i in range(3):
                alpha = 80 - i * 20
                if alpha > 0:
                    if self.default_fonts['info']:
                        draw.text((text_x + i, join_y + i), join_text, 
                                 fill=(*cyber_colors[2], alpha), font=self.default_fonts['info'], anchor="lm")
                    else:
                        draw.text((text_x + i, join_y + i), join_text, 
                                 fill=(*cyber_colors[2], alpha), anchor="lm")
            
            if self.default_fonts['info']:
                draw.text((text_x, join_y), join_text, 
                         fill=cyber_colors[2], font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x, join_y), join_text, fill=cyber_colors[2], anchor="lm")

    def _add_elegant_premium_text(self, draw: ImageDraw.Draw, user: discord.Member, guild_config: Dict, width: int, height: int, text_x: int):
        
        welcome_text = guild_config["welcome_message"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        subtitle_text = guild_config["subtitle"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        

        max_width = width - text_x - 50
        

        gold = (212, 175, 55)
        

        welcome_y = 120
        line_height = 60
        

        welcome_lines = self._wrap_text(welcome_text, self.default_fonts['title'], max_width)
        
        for line_idx, line in enumerate(welcome_lines):
            current_y = welcome_y + (line_idx * line_height)
            
            if self.default_fonts['title']:

                draw.text((text_x + 2, current_y + 2), line, 
                         fill=(0, 0, 0, 100), font=self.default_fonts['title'], anchor="lm")

                draw.text((text_x, current_y), line, 
                         fill=gold, font=self.default_fonts['title'], anchor="lm")
            else:
                draw.text((text_x + 2, current_y + 2), line, 
                         fill=(0, 0, 0, 100), anchor="lm")
                draw.text((text_x, current_y), line, fill=gold, anchor="lm")
        

        subtitle_y = welcome_y + (len(welcome_lines) * line_height) + 20
        

        subtitle_lines = self._wrap_text(subtitle_text, self.default_fonts['subtitle'], max_width)
        subtitle_line_height = 40
        
        for line_idx, line in enumerate(subtitle_lines):
            current_y = subtitle_y + (line_idx * subtitle_line_height)
            
            if self.default_fonts['subtitle']:

                draw.text((text_x + 1, current_y + 1), line, 
                         fill=(0, 0, 0, 80), font=self.default_fonts['subtitle'], anchor="lm")
                draw.text((text_x, current_y), line, 
                         fill=(255, 255, 255), font=self.default_fonts['subtitle'], anchor="lm")
            else:
                draw.text((text_x + 1, current_y + 1), line, 
                         fill=(0, 0, 0, 80), anchor="lm")
                draw.text((text_x, current_y), line, 
                         fill=(255, 255, 255), anchor="lm")
        

        member_y = subtitle_y + (len(subtitle_lines) * subtitle_line_height) + 20
        

        if guild_config.get("show_member_count", True):
            member_text = f"Member #{user.guild.member_count}"
            
            if self.default_fonts['info']:
                draw.text((text_x + 1, member_y + 1), member_text, 
                         fill=(0, 0, 0, 60), font=self.default_fonts['info'], anchor="lm")
                draw.text((text_x, member_y), member_text, 
                         fill=gold, font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x + 1, member_y + 1), member_text, 
                         fill=(0, 0, 0, 60), anchor="lm")
                draw.text((text_x, member_y), member_text, fill=gold, anchor="lm")
        

        if guild_config.get("show_join_date", True):
            join_text = f"Joined: {user.joined_at.strftime('%B %d, %Y')}"
            join_y = member_y + 30
            
            if self.default_fonts['info']:
                draw.text((text_x + 1, join_y + 1), join_text, 
                         fill=(0, 0, 0, 60), font=self.default_fonts['info'], anchor="lm")
                draw.text((text_x, join_y), join_text, 
                         fill=gold, font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x + 1, join_y + 1), join_text, 
                         fill=(0, 0, 0, 60), anchor="lm")
                draw.text((text_x, join_y), join_text, fill=gold, anchor="lm")

    def _add_cosmic_premium_text(self, draw: ImageDraw.Draw, user: discord.Member, guild_config: Dict, width: int, height: int, text_x: int):
        
        welcome_text = guild_config["welcome_message"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        subtitle_text = guild_config["subtitle"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        

        max_width = width - text_x - 50
        

        cosmic_colors = [
            (138, 43, 226),
            (0, 191, 255),
            (255, 105, 180)
        ]
        

        welcome_y = 120
        line_height = 60
        

        welcome_lines = self._wrap_text(welcome_text, self.default_fonts['title'], max_width)
        
        for line_idx, line in enumerate(welcome_lines):
            current_y = welcome_y + (line_idx * line_height)
            

            for i in range(8):
                alpha = 100 - i * 10
                if alpha > 0:
                    for color in cosmic_colors:
                        if self.default_fonts['title']:
                            draw.text((text_x + i, current_y + i), line, 
                                     fill=(*color, alpha), font=self.default_fonts['title'], anchor="lm")
                        else:
                            draw.text((text_x + i, current_y + i), line, 
                                     fill=(*color, alpha), anchor="lm")
            

            if self.default_fonts['title']:
                draw.text((text_x, current_y), line, 
                         fill=(255, 255, 255), font=self.default_fonts['title'], anchor="lm")
            else:
                draw.text((text_x, current_y), line, fill=(255, 255, 255), anchor="lm")
        

        subtitle_y = welcome_y + (len(welcome_lines) * line_height) + 20
        

        subtitle_lines = self._wrap_text(subtitle_text, self.default_fonts['subtitle'], max_width)
        subtitle_line_height = 40
        
        for line_idx, line in enumerate(subtitle_lines):
            current_y = subtitle_y + (line_idx * subtitle_line_height)
            

            for i in range(6):
                alpha = 80 - i * 10
                if alpha > 0:
                    if self.default_fonts['subtitle']:
                        draw.text((text_x + i, current_y + i), line, 
                                 fill=(*cosmic_colors[0], alpha), font=self.default_fonts['subtitle'], anchor="lm")
                    else:
                        draw.text((text_x + i, current_y + i), line, 
                                 fill=(*cosmic_colors[0], alpha), anchor="lm")
            
            if self.default_fonts['subtitle']:
                draw.text((text_x, current_y), line, 
                         fill=cosmic_colors[0], font=self.default_fonts['subtitle'], anchor="lm")
            else:
                draw.text((text_x, current_y), line, fill=cosmic_colors[0], anchor="lm")
        

        member_y = subtitle_y + (len(subtitle_lines) * subtitle_line_height) + 20
        

        if guild_config.get("show_member_count", True):
            member_text = f"Member #{user.guild.member_count}"
            
            for i in range(4):
                alpha = 60 - i * 10
                if alpha > 0:
                    if self.default_fonts['info']:
                        draw.text((text_x + i, member_y + i), member_text, 
                                 fill=(*cosmic_colors[1], alpha), font=self.default_fonts['info'], anchor="lm")
                    else:
                        draw.text((text_x + i, member_y + i), member_text, 
                                 fill=(*cosmic_colors[1], alpha), anchor="lm")
            
            if self.default_fonts['info']:
                draw.text((text_x, member_y), member_text, 
                         fill=cosmic_colors[1], font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x, member_y), member_text, fill=cosmic_colors[1], anchor="lm")
        

        if guild_config.get("show_join_date", True):
            join_text = f"Joined: {user.joined_at.strftime('%B %d, %Y')}"
            join_y = member_y + 30
            
            for i in range(4):
                alpha = 60 - i * 10
                if alpha > 0:
                    if self.default_fonts['info']:
                        draw.text((text_x + i, join_y + i), join_text, 
                                 fill=(*cosmic_colors[2], alpha), font=self.default_fonts['info'], anchor="lm")
                    else:
                        draw.text((text_x + i, join_y + i), join_text, 
                                 fill=(*cosmic_colors[2], alpha), anchor="lm")
            
            if self.default_fonts['info']:
                draw.text((text_x, join_y), join_text, 
                         fill=cosmic_colors[2], font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x, join_y), join_text, fill=cosmic_colors[2], anchor="lm")

    def _add_aurora_premium_text(self, draw: ImageDraw.Draw, user: discord.Member, guild_config: Dict, width: int, height: int, text_x: int):
        
        welcome_text = guild_config["welcome_message"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        subtitle_text = guild_config["subtitle"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        

        max_width = width - text_x - 50
        

        aurora_colors = [
            (0, 255, 255),
            (255, 0, 255),
            (0, 255, 128)
        ]
        

        welcome_y = 120
        line_height = 60
        

        welcome_lines = self._wrap_text(welcome_text, self.default_fonts['title'], max_width)
        
        for line_idx, line in enumerate(welcome_lines):
            current_y = welcome_y + (line_idx * line_height)
            

            for i in range(10):
                alpha = 120 - i * 10
                if alpha > 0:
                    for color in aurora_colors:
                        if self.default_fonts['title']:
                            draw.text((text_x + i, current_y + i), line, 
                                     fill=(*color, alpha), font=self.default_fonts['title'], anchor="lm")
                        else:
                            draw.text((text_x + i, current_y + i), line, 
                                     fill=(*color, alpha), anchor="lm")
            

            if self.default_fonts['title']:
                draw.text((text_x, current_y), line, 
                         fill=(255, 255, 255), font=self.default_fonts['title'], anchor="lm")
            else:
                draw.text((text_x, current_y), line, fill=(255, 255, 255), anchor="lm")
        

        subtitle_y = welcome_y + (len(welcome_lines) * line_height) + 20
        

        subtitle_lines = self._wrap_text(subtitle_text, self.default_fonts['subtitle'], max_width)
        subtitle_line_height = 40
        
        for line_idx, line in enumerate(subtitle_lines):
            current_y = subtitle_y + (line_idx * subtitle_line_height)
            

            for i in range(8):
                alpha = 100 - i * 10
                if alpha > 0:
                    if self.default_fonts['subtitle']:
                        draw.text((text_x + i, current_y + i), line, 
                                 fill=(*aurora_colors[0], alpha), font=self.default_fonts['subtitle'], anchor="lm")
                    else:
                        draw.text((text_x + i, current_y + i), line, 
                                 fill=(*aurora_colors[0], alpha), anchor="lm")
            
            if self.default_fonts['subtitle']:
                draw.text((text_x, current_y), line, 
                         fill=aurora_colors[0], font=self.default_fonts['subtitle'], anchor="lm")
            else:
                draw.text((text_x, current_y), line, fill=aurora_colors[0], anchor="lm")
        

        member_y = subtitle_y + (len(subtitle_lines) * subtitle_line_height) + 20
        

        if guild_config.get("show_member_count", True):
            member_text = f"Member #{user.guild.member_count}"
            
            for i in range(6):
                alpha = 80 - i * 10
                if alpha > 0:
                    if self.default_fonts['info']:
                        draw.text((text_x + i, member_y + i), member_text, 
                                 fill=(*aurora_colors[1], alpha), font=self.default_fonts['info'], anchor="lm")
                    else:
                        draw.text((text_x + i, member_y + i), member_text, 
                                 fill=(*aurora_colors[1], alpha), anchor="lm")
            
            if self.default_fonts['info']:
                draw.text((text_x, member_y), member_text, 
                         fill=aurora_colors[1], font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x, member_y), member_text, fill=aurora_colors[1], anchor="lm")
        

        if guild_config.get("show_join_date", True):
            join_text = f"Joined: {user.joined_at.strftime('%B %d, %Y')}"
            join_y = member_y + 30
            
            for i in range(6):
                alpha = 80 - i * 10
                if alpha > 0:
                    if self.default_fonts['info']:
                        draw.text((text_x + i, join_y + i), join_text, 
                                 fill=(*aurora_colors[2], alpha), font=self.default_fonts['info'], anchor="lm")
                    else:
                        draw.text((text_x + i, join_y + i), join_text, 
                                 fill=(*aurora_colors[2], alpha), anchor="lm")
            
            if self.default_fonts['info']:
                draw.text((text_x, join_y), join_text, 
                         fill=aurora_colors[2], font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x, join_y), join_text, fill=aurora_colors[2], anchor="lm")


    def _add_geometric_patterns(self, draw: ImageDraw.Draw, width: int, height: int, accent_color: tuple):
        

        for i in range(0, width + height, 50):
            draw.line([(i, 0), (i - height, height)], fill=(*accent_color, 30), width=2)
        

        hex_size = 20
        for x in range(0, width, hex_size * 2):
            for y in range(0, height, hex_size * 2):
                if x < 100 or x > width - 100 or y < 100 or y > height - 100:
                    self._draw_hexagon(draw, x, y, hex_size, (*accent_color, 40))

    def _draw_hexagon(self, draw: ImageDraw.Draw, x: int, y: int, size: int, color: tuple):
        
        import math
        points = []
        for i in range(6):
            angle = math.pi * i / 3
            px = x + size * math.cos(angle)
            py = y + size * math.sin(angle)
            points.append((px, py))
        draw.polygon(points, outline=color, width=1)

    def _add_premium_border(self, draw: ImageDraw.Draw, width: int, height: int, accent_color: tuple):
        
        border_width = 5
        for i in range(border_width):
            alpha = 200 - i * 30
            draw.rectangle([(i, i), (width - i - 1, height - i - 1)], 
                         outline=(*accent_color, alpha), width=2)

    def _add_modern_decorations(self, draw: ImageDraw.Draw, width: int, height: int, accent_color: tuple):
        

        corner_size = 30

        draw.arc([(20, 20), (20 + corner_size, 20 + corner_size)], 180, 270, 
                fill=accent_color, width=3)

        draw.arc([(width - 20 - corner_size, 20), (width - 20, 20 + corner_size)], 
                270, 360, fill=accent_color, width=3)

        draw.arc([(20, height - 20 - corner_size), (20 + corner_size, height - 20)], 
                90, 180, fill=accent_color, width=3)

        draw.arc([(width - 20 - corner_size, height - 20 - corner_size), 
                 (width - 20, height - 20)], 0, 90, fill=accent_color, width=3)

    def _add_neon_grid(self, draw: ImageDraw.Draw, width: int, height: int):
        
        grid_size = 40
        neon_color = (0, 255, 255, 80)
        

        for x in range(0, width, grid_size):
            draw.line([(x, 0), (x, height)], fill=neon_color, width=1)
        

        for y in range(0, height, grid_size):
            draw.line([(0, y), (width, y)], fill=neon_color, width=1)

    def _add_neon_effects(self, draw: ImageDraw.Draw, width: int, height: int, neon_colors: list):
        

        for i, color in enumerate(neon_colors):
            y_pos = 100 + i * 150
            for j in range(5):
                alpha = 150 - j * 25
                draw.line([(50 + j, y_pos + j), (width - 50 - j, y_pos + j)], 
                         fill=(*color, alpha), width=3)

    def _add_glass_orbs(self, img: Image.Image, width: int, height: int):
        
        orb_positions = [(150, 100), (width - 200, 150), (200, height - 150), (width - 150, height - 100)]
        
        for x, y in orb_positions:
            orb_size = 60
            orb = Image.new("RGBA", (orb_size, orb_size), (255, 255, 255, 30))
            orb_blur = orb.filter(ImageFilter.GaussianBlur(radius=15))
            

            mask = Image.new("L", (orb_size, orb_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, orb_size, orb_size), fill=255)
            orb_blur.putalpha(mask)
            
            img.paste(orb_blur, (x - orb_size // 2, y - orb_size // 2), orb_blur)

    def _add_matrix_rain(self, img: Image.Image, width: int, height: int):
        
        import random
        matrix_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        matrix_draw = ImageDraw.Draw(matrix_overlay)
        

        for x in range(0, width, 20):
            column_height = random.randint(50, 200)
            for y in range(0, column_height, 15):
                alpha = max(0, 150 - y)
                char = random.choice("01")
                matrix_draw.text((x, y), char, fill=(0, 255, 0, alpha))
        
        img.paste(matrix_overlay, (0, 0), matrix_overlay)

    def _add_cyberpunk_hud(self, draw: ImageDraw.Draw, width: int, height: int, cyber_colors: list):
        

        hud_size = 50
        for color in cyber_colors:

            draw.line([(30, 30), (30 + hud_size, 30)], fill=color, width=3)
            draw.line([(30, 30), (30, 30 + hud_size)], fill=color, width=3)
            

            draw.line([(width - 30 - hud_size, 30), (width - 30, 30)], fill=color, width=3)
            draw.line([(width - 30, 30), (width - 30, 30 + hud_size)], fill=color, width=3)
            

            draw.line([(30, height - 30), (30 + hud_size, height - 30)], fill=color, width=3)
            draw.line([(30, height - 30 - hud_size), (30, height - 30)], fill=color, width=3)
            

            draw.line([(width - 30 - hud_size, height - 30), (width - 30, height - 30)], fill=color, width=3)
            draw.line([(width - 30, height - 30 - hud_size), (width - 30, height - 30)], fill=color, width=3)

    def _add_cyberpunk_effects(self, draw: ImageDraw.Draw, width: int, height: int, cyber_colors: list):
        

        for i in range(0, height, 8):
            alpha = 50 if i % 16 == 0 else 20
            draw.line([(0, i), (width, i)], fill=(0, 255, 255, alpha), width=1)
        

        import random
        for _ in range(5):
            y = random.randint(0, height - 20)
            w = random.randint(100, 300)
            x = random.randint(0, width - w)
            draw.rectangle([(x, y), (x + w, y + 3)], fill=cyber_colors[0])

    def _add_elegant_patterns(self, draw: ImageDraw.Draw, width: int, height: int):
        
        gold_color = (184, 150, 107, 100)
        

        flourish_size = 80

        self._draw_flourish(draw, 40, 40, flourish_size, gold_color, 0)
        self._draw_flourish(draw, width - 40, 40, flourish_size, gold_color, 90)

        self._draw_flourish(draw, 40, height - 40, flourish_size, gold_color, 270)
        self._draw_flourish(draw, width - 40, height - 40, flourish_size, gold_color, 180)

    def _draw_flourish(self, draw: ImageDraw.Draw, x: int, y: int, size: int, color: tuple, rotation: int):
        
        import math

        for i in range(3):
            curve_points = []
            for t in range(0, 90, 5):
                angle = math.radians(t + rotation)
                px = x + (size - i * 10) * math.cos(angle) * 0.5
                py = y + (size - i * 10) * math.sin(angle) * 0.3
                curve_points.append((px, py))
            
            if len(curve_points) > 1:
                for j in range(len(curve_points) - 1):
                    draw.line([curve_points[j], curve_points[j + 1]], fill=color, width=2)

    def _add_luxury_frame(self, draw: ImageDraw.Draw, width: int, height: int, gold_color: tuple):
        
        frame_width = 15
        

        for i in range(frame_width):
            alpha = 200 - i * 10
            frame_color = (*gold_color, alpha)
            draw.rectangle([(i, i), (width - i - 1, height - i - 1)], 
                         outline=frame_color, width=2)
        

        corner_size = 25
        for corner in [(corner_size, corner_size), (width - corner_size, corner_size), 
                      (corner_size, height - corner_size), (width - corner_size, height - corner_size)]:
            draw.ellipse([(corner[0] - 10, corner[1] - 10), 
                         (corner[0] + 10, corner[1] + 10)], 
                        outline=gold_color, width=3)

    def _add_nebula_background(self, img: Image.Image, width: int, height: int):
        
        import random
        nebula_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        

        for _ in range(20):
            x = random.randint(0, width)
            y = random.randint(0, height)
            size = random.randint(50, 150)
            

            colors = [(100, 50, 200, 60), (200, 50, 100, 60), (50, 100, 200, 60)]
            color = random.choice(colors)
            
            cloud = Image.new("RGBA", (size, size), color)
            cloud_blur = cloud.filter(ImageFilter.GaussianBlur(radius=25))
            

            mask = Image.new("L", (size, size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, size, size), fill=255)
            cloud_blur.putalpha(mask)
            
            nebula_overlay.paste(cloud_blur, (x - size // 2, y - size // 2), cloud_blur)
        
        img.paste(nebula_overlay, (0, 0), nebula_overlay)

    def _add_starfield(self, img: Image.Image, width: int, height: int):
        
        import random
        star_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        star_draw = ImageDraw.Draw(star_overlay)
        

        for _ in range(100):
            x = random.randint(0, width)
            y = random.randint(0, height)
            brightness = random.randint(100, 255)
            size = random.randint(1, 3)
            
            star_draw.ellipse([(x, y), (x + size, y + size)], 
                            fill=(brightness, brightness, brightness, 200))
        
        img.paste(star_overlay, (0, 0), star_overlay)

    def _add_cosmic_rings(self, draw: ImageDraw.Draw, width: int, height: int, cosmic_colors: list):
        
        center_x, center_y = width // 2, height // 2
        
        for i, color in enumerate(cosmic_colors):
            for j in range(5):
                radius = 100 + i * 50 + j * 20
                alpha = 120 - j * 20
                if alpha > 0:

                    draw.ellipse([(center_x - radius, center_y - radius), 
                                (center_x + radius, center_y + radius)], 
                               outline=(*color, alpha), width=2)

    def _add_aurora_waves(self, img: Image.Image, width: int, height: int):
        
        import math
        aurora_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        aurora_draw = ImageDraw.Draw(aurora_overlay)
        

        wave_colors = [(0, 255, 150, 80), (100, 255, 200, 60), (200, 100, 255, 70)]
        

        for color_idx, color in enumerate(wave_colors):
            wave_points = []
            for x in range(0, width, 10):

                wave_height = 50 + 30 * math.sin((x + color_idx * 50) * 0.02)
                y = height // 2 + wave_height + color_idx * 40
                wave_points.append((x, y))
            

            if len(wave_points) > 2:

                wave_points.append((width, height))
                wave_points.append((0, height))
                aurora_draw.polygon(wave_points, fill=color)
        

        aurora_blur = aurora_overlay.filter(ImageFilter.GaussianBlur(radius=15))
        img.paste(aurora_blur, (0, 0), aurora_blur)

    def _add_aurora_panels(self, draw: ImageDraw.Draw, width: int, height: int, aurora_colors: list):
        

        for i, color in enumerate(aurora_colors):
            panel_x = 60 + i * 20
            panel_y = 60 + i * 15
            panel_width = width - 120 - i * 40
            panel_height = height - 120 - i * 30
            

            for j in range(8):
                alpha = 100 - j * 10
                if alpha > 0:
                    draw.rectangle([(panel_x + j, panel_y + j), 
                                  (panel_x + panel_width - j, panel_y + panel_height - j)], 
                                 outline=(*color, alpha), width=2)


    async def download_avatar(self, user: discord.Member) -> Image.Image:
        
        try:
            avatar_url = user.display_avatar.url
            async with aiohttp.ClientSession() as session:
                async with session.get(str(avatar_url)) as resp:
                    if resp.status == 200:
                        avatar_bytes = await resp.read()
                        avatar = Image.open(io.BytesIO(avatar_bytes))
                        avatar = avatar.convert("RGBA")

                        avatar = avatar.resize((140, 140), Image.Resampling.LANCZOS)
                        return avatar
        except Exception as e:
            print(f"Error downloading avatar: {e}")
            

        avatar = Image.new("RGBA", (140, 140), (114, 137, 218, 255))
        draw = ImageDraw.Draw(avatar)
        

        for y in range(140):
            ratio = y / 140
            r = int(114 * (1 - ratio) + 180 * ratio)
            g = int(137 * (1 - ratio) + 160 * ratio)
            b = int(218 * (1 - ratio) + 240 * ratio)
            
            line = Image.new("RGBA", (140, 1), (r, g, b, 255))
            avatar.paste(line, (0, y))
        

        if self.default_fonts['title']:

            draw.text((72, 72), user.name[0].upper(), fill=(0, 0, 0, 100), 
                     font=self.default_fonts['title'], anchor="mm")

            draw.text((70, 70), user.name[0].upper(), fill="white", 
                     font=self.default_fonts['title'], anchor="mm")
        else:
            draw.text((72, 72), user.name[0].upper(), fill=(0, 0, 0, 100), anchor="mm")
            draw.text((70, 70), user.name[0].upper(), fill="white", anchor="mm")
        
        return avatar

    def create_circular_avatar(self, avatar: Image.Image) -> Image.Image:
        
        size = avatar.size[0]
        

        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size, size), fill=255)
        

        mask = mask.filter(ImageFilter.SMOOTH)
        

        circular_avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        circular_avatar.paste(avatar, (0, 0))
        circular_avatar.putalpha(mask)
        
        return circular_avatar

    def _add_decorative_elements(self, draw: ImageDraw.Draw, width: int, height: int, accent_color: tuple):
        

        line_y1, line_y2 = 80, height - 80
        line_start, line_end = width // 3, 2 * width // 3
        

        for i in range(5):
            alpha = 200 - i * 30
            draw.line([(line_start, line_y1 + i), (line_end, line_y1 + i)], 
                     fill=(*accent_color, alpha), width=3)
            draw.line([(line_start, line_y2 + i), (line_end, line_y2 + i)], 
                     fill=(*accent_color, alpha), width=3)
        

        corner_size = 40
        corners = [
            (30, 30, 180, 270),
            (width - 30 - corner_size, 30, 270, 360),
            (30, height - 30 - corner_size, 90, 180),
            (width - 30 - corner_size, height - 30 - corner_size, 0, 90)
        ]
        
        for x, y, start_angle, end_angle in corners:
            for i in range(3):
                alpha = 200 - i * 50
                draw.arc([(x + i, y + i), (x + corner_size - i, y + corner_size - i)], 
                        start_angle, end_angle, fill=(*accent_color, alpha), width=4)
        

        diamond_size = 15
        diamond_positions = [
            (width // 4, 60),
            (3 * width // 4, 60),
            (width // 4, height - 60),
            (3 * width // 4, height - 60)
        ]
        
        for x, y in diamond_positions:
            diamond_points = [
                (x, y - diamond_size),
                (x + diamond_size, y),
                (x, y + diamond_size),
                (x - diamond_size, y)
            ]
            draw.polygon(diamond_points, fill=(*accent_color, 150), 
                        outline=(*accent_color, 255), width=2)


    def _get_template_configs(self):
        
        return {
            "modern": {
                "background_color": "#2F3136",
                "text_color": "#FFFFFF",
                "accent_color": "#5865F2",
                "welcome_message": "Welcome to {server}!",
                "subtitle": "Great to have you here, {user}!",
                "show_member_count": True,
                "show_join_date": True,
                "show_border": True,
                "show_shadow": True
            },
            "neon": {
                "background_color": "#050514",
                "text_color": "#00FFFF",
                "accent_color": "#FF00FF",
                "welcome_message": "WELCOME TO {server}",
                "subtitle": "SYSTEM ONLINE - USER {user} DETECTED",
                "show_member_count": True,
                "show_join_date": True,
                "show_border": True,
                "show_shadow": True
            },
            "glass": {
                "background_color": "#1E1E2E",
                "text_color": "#FFFFFF",
                "accent_color": "#89B4FA",
                "welcome_message": "Welcome to {server}",
                "subtitle": "Hello there, {user}!",
                "show_member_count": True,
                "show_join_date": True,
                "show_border": True,
                "show_shadow": True
            },
            "cyberpunk": {
                "background_color": "#0A0A0F",
                "text_color": "#00FF00",
                "accent_color": "#FF00FF",
                "welcome_message": "WELCOME TO {server}",
                "subtitle": "USER {user} INITIALIZED",
                "show_member_count": True,
                "show_join_date": True,
                "show_border": True,
                "show_shadow": True
            },
            "elegant": {
                "background_color": "#1A1A1A",
                "text_color": "#FFFFFF",
                "accent_color": "#D4AF37",
                "welcome_message": "Welcome to {server}",
                "subtitle": "We're honored to have you here, {user}",
                "show_member_count": True,
                "show_join_date": True,
                "show_border": True,
                "show_shadow": True
            },
            "cosmic": {
                "background_color": "#050514",
                "text_color": "#FFFFFF",
                "accent_color": "#64C8FF",
                "welcome_message": "Welcome to {server}",
                "subtitle": "Greetings, {user}!",
                "show_member_count": True,
                "show_join_date": True,
                "show_border": True,
                "show_shadow": True
            },
            "aurora": {
                "background_color": "#0F1419",
                "text_color": "#FFFFFF",
                "accent_color": "#00FF96",
                "welcome_message": "Welcome to {server}",
                "subtitle": "Welcome aboard, {user}!",
                "show_member_count": True,
                "show_join_date": True,
                "show_border": True,
                "show_shadow": True
            },
            "thez": {
                "background_color": "#0A0A0F",
                "text_color": "#FFFFFF",
                "accent_color": "#FFD700",
                "welcome_message": "Welcome to {server}!",
                "subtitle": "We're honored to have you here, {user}!",
                "show_member_count": True,
                "show_join_date": True,
                "show_border": True,
                "show_shadow": True
            }
        }

    async def _generate_thez_card(self, user: discord.Member, guild_config: Dict, width: int, height: int) -> io.BytesIO:
        

        img = Image.new("RGBA", (width, height), (10, 10, 15, 255))
        draw = ImageDraw.Draw(img)
        

        avatar = await self.download_avatar(user)
        circular_avatar = self.create_circular_avatar(avatar)
        premium_avatar = self._create_thez_premium_avatar(circular_avatar)
        

        avatar_x = 80
        avatar_y = 80
        img.paste(premium_avatar, (avatar_x, avatar_y), premium_avatar)
        

        text_x = avatar_x + premium_avatar.size[0] + 50
        

        self._add_thez_premium_background(img, draw, width, height)
        

        self._add_thez_premium_decorations(draw, width, height)
        

        self._add_thez_premium_text(draw, user, guild_config, width, height, text_x)
        

        buffer = io.BytesIO()
        img.save(buffer, format="PNG", quality=100)
        buffer.seek(0)
        return buffer

    def _create_thez_premium_avatar(self, avatar: Image.Image) -> Image.Image:
        
        size = avatar.size[0]
        glow_size = size + 80
        final_avatar = Image.new("RGBA", (glow_size, glow_size), (0, 0, 0, 0))
        

        glow_colors = [
            (255, 215, 0, 120),
            (255, 255, 255, 80),
            (138, 43, 226, 60),
            (255, 20, 147, 40)
        ]
        
        for color_idx, color in enumerate(glow_colors):
            glow_layer = Image.new("RGBA", (glow_size, glow_size), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_layer)
            
            for i in range(25):
                alpha = color[3] - i * 3
                if alpha > 0:
                    offset = color_idx * 8 + i
                    glow_draw.ellipse([(offset, offset), (glow_size - offset, glow_size - offset)], 
                                    outline=(*color[:3], alpha), width=3)
            

            glow_blur = glow_layer.filter(ImageFilter.GaussianBlur(radius=8))
            final_avatar.paste(glow_blur, (0, 0), glow_blur)
        

        diamond_draw = ImageDraw.Draw(final_avatar)
        center = glow_size // 2
        diamond_size = size // 2 + 25
        
        diamond_points = [
            (center, center - diamond_size),
            (center + diamond_size, center),
            (center, center + diamond_size),
            (center - diamond_size, center)
        ]
        

        for i in range(5):
            alpha = 200 - i * 30
            diamond_draw.polygon(diamond_points, outline=(255, 215, 0, alpha), width=3)

            diamond_points = [(x + (1 if x > center else -1) * 3, 
                             y + (1 if y > center else -1) * 3) for x, y in diamond_points]
        

        final_avatar.paste(avatar, (40, 40), avatar)
        
        return final_avatar

    def _add_thez_premium_background(self, img: Image.Image, draw: ImageDraw.Draw, width: int, height: int):
        

        gradient_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        

        for i in range(5):
            gradient_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            gradient_draw = ImageDraw.Draw(gradient_layer)
            

            center_x, center_y = width // 2 + i * 50, height // 2 + i * 30
            max_radius = max(width, height)
            
            for radius in range(0, max_radius, 20):
                alpha = max(0, 60 - radius // 10)
                colors = [
                    (255, 215, 0, alpha),
                    (138, 43, 226, alpha),
                    (255, 20, 147, alpha),
                    (0, 191, 255, alpha),
                    (255, 255, 255, alpha)
                ]
                color = colors[i % len(colors)]
                
                gradient_draw.ellipse([(center_x - radius, center_y - radius), 
                                     (center_x + radius, center_y + radius)], 
                                    outline=color, width=2)
        

        gradient_blur = gradient_overlay.filter(ImageFilter.GaussianBlur(radius=25))
        img.paste(gradient_blur, (0, 0), gradient_blur)
        

        orb_positions = [
            (150, 120), (width - 200, 180), (300, height - 200), 
            (width - 150, height - 120), (width // 2, 100), (100, height - 100)
        ]
        
        for i, (x, y) in enumerate(orb_positions):
            orb_size = 80 + i * 10
            orb = Image.new("RGBA", (orb_size, orb_size), (255, 255, 255, 40))
            

            orb_draw = ImageDraw.Draw(orb)
            for j in range(orb_size // 4):
                alpha = 80 - j * 8
                if alpha > 0:
                    orb_draw.ellipse([(j, j), (orb_size - j, orb_size - j)], 
                                   outline=(255, 215, 0, alpha), width=2)
            
            orb_blur = orb.filter(ImageFilter.GaussianBlur(radius=20))
            

            mask = Image.new("L", (orb_size, orb_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, orb_size, orb_size), fill=255)
            orb_blur.putalpha(mask)
            
            img.paste(orb_blur, (x - orb_size // 2, y - orb_size // 2), orb_blur)

    def _add_thez_premium_decorations(self, draw: ImageDraw.Draw, width: int, height: int):
        

        border_colors = [
            (255, 215, 0, 200),
            (255, 255, 255, 150),
            (138, 43, 226, 100),
            (255, 20, 147, 80)
        ]
        
        for i, color in enumerate(border_colors):
            thickness = 8 - i * 2
            draw.rectangle([(i * 3, i * 3), (width - i * 3 - 1, height - i * 3 - 1)], 
                         outline=color, width=thickness)
        

        corner_size = 60
        corners = [
            (corner_size, corner_size),
            (width - corner_size, corner_size),
            (corner_size, height - corner_size),
            (width - corner_size, height - corner_size)
        ]
        
        for i, (cx, cy) in enumerate(corners):

            for layer in range(8):
                radius = 40 - layer * 4
                alpha = 200 - layer * 20
                

                for angle in range(0, 360, 45):
                    rad = math.radians(angle + i * 90)
                    x1 = cx + radius * math.cos(rad)
                    y1 = cy + radius * math.sin(rad)
                    x2 = cx + (radius - 15) * math.cos(rad)
                    y2 = cy + (radius - 15) * math.sin(rad)
                    
                    colors = [(255, 215, 0, alpha), (255, 255, 255, alpha), (138, 43, 226, alpha)]
                    color = colors[layer % 3]
                    draw.line([(x1, y1), (x2, y2)], fill=color, width=3)

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
        
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:

            test_line = ' '.join(current_line + [word])
            if font:
                width = font.getlength(test_line)
            else:

                width = len(test_line) * 10
                
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
            
        return lines

    def _add_thez_premium_text(self, draw: ImageDraw.Draw, user: discord.Member, guild_config: Dict, width: int, height: int, text_x: int):
        

        gold = (255, 215, 0)
        white = (255, 255, 255)
        purple = (138, 43, 226)
        pink = (255, 20, 147)
        
        welcome_text = guild_config["welcome_message"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        subtitle_text = guild_config["subtitle"].replace("{server}", user.guild.name).replace("{user}", user.display_name)
        

        max_width = width - text_x - 50
        

        welcome_y = 120
        line_height = 60
        

        welcome_lines = self._wrap_text(welcome_text, self.default_fonts['title'], max_width)
        

        glow_layers = [
            (gold, 12, 250),
            (white, 8, 200),
            (purple, 6, 150),
            (pink, 4, 100)
        ]
        
        for line_idx, line in enumerate(welcome_lines):
            current_y = welcome_y + (line_idx * line_height)
            
            for color, offset, alpha in glow_layers:
                for i in range(offset):
                    glow_alpha = max(0, alpha - i * 15)
                    if glow_alpha > 0:
                        if self.default_fonts['title']:
                            draw.text((text_x + i, current_y + i), line, 
                                     fill=(*color, glow_alpha), font=self.default_fonts['title'], anchor="lm")
                        else:
                            draw.text((text_x + i, current_y + i), line, 
                                     fill=(*color, glow_alpha), anchor="lm")
            

            if self.default_fonts['title']:

                for i in range(3):
                    gradient_color = (
                        int(gold[0] * (1 - i * 0.2) + white[0] * (i * 0.2)),
                        int(gold[1] * (1 - i * 0.2) + white[1] * (i * 0.2)),
                        int(gold[2] * (1 - i * 0.2) + white[2] * (i * 0.2))
                    )
                    draw.text((text_x, current_y + i), line, 
                             fill=gradient_color, font=self.default_fonts['title'], anchor="lm")
            else:
                draw.text((text_x, current_y), line, fill=gold, anchor="lm")
        

        subtitle_y = welcome_y + (len(welcome_lines) * line_height) + 20
        

        subtitle_lines = self._wrap_text(subtitle_text, self.default_fonts['subtitle'], max_width)
        subtitle_line_height = 40
        

        for line_idx, line in enumerate(subtitle_lines):
            current_y = subtitle_y + (line_idx * subtitle_line_height)
            
            if self.default_fonts['subtitle']:

                draw.text((text_x + 3, current_y + 3), line, 
                         fill=(0, 0, 0, 120), font=self.default_fonts['subtitle'], anchor="lm")

                for i in range(4):
                    alpha = 100 - i * 20
                    if alpha > 0:
                        draw.text((text_x + i, current_y + i), line, 
                                 fill=(*white, alpha), font=self.default_fonts['subtitle'], anchor="lm")

                draw.text((text_x, current_y), line, 
                         fill=white, font=self.default_fonts['subtitle'], anchor="lm")
            else:
                draw.text((text_x + 3, current_y + 3), line, 
                         fill=(0, 0, 0, 120), anchor="lm")
                draw.text((text_x, current_y), line, fill=white, anchor="lm")
        

        member_y = subtitle_y + (len(subtitle_lines) * subtitle_line_height) + 20
        

        if guild_config.get("show_member_count", True):
            member_text = f"Member #{user.guild.member_count}"
            
            if self.default_fonts['info']:

                for i in range(3):
                    alpha = 150 - i * 40
                    if alpha > 0:
                        draw.text((text_x + i, member_y + i), member_text, 
                                 fill=(*purple, alpha), font=self.default_fonts['info'], anchor="lm")
                draw.text((text_x, member_y), member_text, 
                         fill=purple, font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x, member_y), member_text, fill=purple, anchor="lm")
        

        if guild_config.get("show_join_date", True):
            join_text = f"Joined: {user.joined_at.strftime('%B %d, %Y')}"
            join_y = member_y + 30
            
            if self.default_fonts['info']:

                for i in range(3):
                    alpha = 150 - i * 40
                    if alpha > 0:
                        draw.text((text_x + i, join_y + i), join_text, 
                                 fill=(*pink, alpha), font=self.default_fonts['info'], anchor="lm")
                draw.text((text_x, join_y), join_text, 
                         fill=pink, font=self.default_fonts['info'], anchor="lm")
            else:
                draw.text((text_x, join_y), join_text, fill=pink, anchor="lm")

    class WelcomeCardView(discord.ui.View):
        
        def __init__(self, cog, guild_id: int):
            super().__init__(timeout=300)
            self.cog = cog
            self.guild_id = guild_id
            
        @discord.ui.button(label="🎨 Customize Colors", style=discord.ButtonStyle.primary)
        async def customize_colors(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(self.ColorCustomizationModal(self.cog, self.guild_id))
            
        @discord.ui.button(label="📝 Edit Text", style=discord.ButtonStyle.secondary)
        async def edit_text(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(self.TextCustomizationModal(self.cog, self.guild_id))
            
        @discord.ui.button(label="⚙️ Settings", style=discord.ButtonStyle.secondary)
        async def settings(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed = await self.cog.create_settings_embed(self.guild_id)
            view = self.SettingsView(self.cog, self.guild_id)
            await interaction.response.edit_message(embed=embed, view=view)
            
        @discord.ui.button(label="🖼️ Preview", style=discord.ButtonStyle.success)
        async def preview_card(self, interaction: discord.Interaction, button: discord.ui.Button):
            guild_config = self.cog._get_guild_config(self.guild_id)
            if not guild_config.get("enabled", False):
                await interaction.response.send_message("Welcome cards are not enabled for this server. Use `/welcomecard setup` to enable them.", ephemeral=True)
                return


            test_user = interaction.user
            welcome_card = await self.cog.generate_welcome_card(test_user, guild_config)
            await interaction.response.send_message("Here's a preview of your welcome card:", file=discord.File(welcome_card, "welcome_card.png"), ephemeral=True)

        @discord.ui.button(label="📋 View Commands", style=discord.ButtonStyle.secondary)
        async def view_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed = discord.Embed(
                title="📋 Welcome Card Commands",
                description="Here are all available welcome card commands:",
                color=discord.Color.blue()
            )


            embed.add_field(
                name="Slash Commands",
                value=(
                    "`/welcomecard setup` - Set up welcome cards\n"
                    "`/welcomecard customize` - Customize welcome card appearance\n"
                    "`/welcomecard test` - Test welcome card with your avatar\n"
                    "`/welcomecard disable` - Disable welcome cards\n"
                    "`/welcomecard channel` - Change welcome card channel\n"
                    "`/welcomecard templates` - View available templates\n"
                    "`/welcomecard template` - Change welcome card template\n"
                    "`/welcomecard info` - Show current configuration"
                ),
                inline=False
            )


            embed.add_field(
                name="Prefix Commands",
                value=(
                    "`!welcomecard setup` - Set up welcome cards\n"
                    "`!welcomecard customize` - Customize welcome card appearance\n"
                    "`!welcomecard test` - Test welcome card with your avatar\n"
                    "`!welcomecard disable` - Disable welcome cards\n"
                    "`!welcomecard channel` - Change welcome card channel\n"
                    "`!welcomecard templates` - View available templates\n"
                    "`!welcomecard template` - Change welcome card template"
                ),
                inline=False
            )


            embed.add_field(
                name="Custom Welcome Card Commands",
                value=(
                    "`/welcomecard_custom` - Customize with custom fonts and backgrounds\n"
                    "`!welcomecard_custom` - Customize with custom fonts and backgrounds"
                ),
                inline=False
            )

            embed.set_footer(text="Tip: Use /welcomecard info to see your current configuration")


            view = discord.ui.View()
            back_button = discord.ui.Button(label="🔙 Back", style=discord.ButtonStyle.secondary)
            
            async def back_callback(interaction: discord.Interaction):
                embed = await self.cog.create_main_embed(self.guild_id)
                await interaction.response.edit_message(embed=embed, view=self)
            
            back_button.callback = back_callback
            view.add_item(back_button)

            await interaction.response.edit_message(embed=embed, view=view)

        class ColorCustomizationModal(discord.ui.Modal):
            def __init__(self, cog, guild_id: int):
                super().__init__(title="🎨 Customize Welcome Card Colors")
                self.cog = cog
                self.guild_id = guild_id
                
                guild_config = cog._get_guild_config(guild_id)
                
                self.background_color = discord.ui.TextInput(
                    label="Background Color (Hex)",
                    placeholder="#2F3136",
                    default=guild_config.get("background_color", "#2F3136"),
                    max_length=7
                )
                self.text_color = discord.ui.TextInput(
                    label="Text Color (Hex)",
                    placeholder="#FFFFFF",
                    default=guild_config.get("text_color", "#FFFFFF"),
                    max_length=7
                )
                self.accent_color = discord.ui.TextInput(
                    label="Accent Color (Hex)",
                    placeholder="#5865F2",
                    default=guild_config.get("accent_color", "#5865F2"),
                    max_length=7
                )
                self.border_color = discord.ui.TextInput(
                    label="Border Color (Hex)",
                    placeholder="#5865F2",
                    default=guild_config.get("border_color", "#5865F2"),
                    max_length=7,
                    required=False
                )
                
                self.add_item(self.background_color)
                self.add_item(self.text_color)
                self.add_item(self.accent_color)
                self.add_item(self.border_color)
                
            async def on_submit(self, interaction: discord.Interaction):
                guild_config = self.cog._get_guild_config(self.guild_id)
                
                colors = {
                    "background_color": self.background_color.value,
                    "text_color": self.text_color.value,
                    "accent_color": self.accent_color.value,
                    "border_color": self.border_color.value or guild_config.get("border_color", "#5865F2")
                }
                
                for key, color in colors.items():
                    if color and not color.startswith('#'):
                        color = '#' + color
                    try:
                        int(color.lstrip('#'), 16)
                        guild_config[key] = color
                    except ValueError:
                        await interaction.response.send_message(f"❌ Invalid hex color: {color}", ephemeral=True)
                        return
                
                self.cog._save_config()
                
                embed = discord.Embed(
                    title="✅ Colors Updated Successfully",
                    description="Welcome card colors have been updated!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Background", value=guild_config["background_color"], inline=True)
                embed.add_field(name="Text", value=guild_config["text_color"], inline=True)
                embed.add_field(name="Accent", value=guild_config["accent_color"], inline=True)
                embed.add_field(name="Border", value=guild_config["border_color"], inline=True)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
        class TextCustomizationModal(discord.ui.Modal):
            def __init__(self, cog, guild_id: int):
                super().__init__(title="📝 Customize Welcome Card Text")
                self.cog = cog
                self.guild_id = guild_id
                
                guild_config = cog._get_guild_config(guild_id)
                
                self.welcome_message = discord.ui.TextInput(
                    label="Welcome Message",
                    placeholder="Welcome to {server}!",
                    default=guild_config.get("welcome_message", "Welcome to {server}!"),
                    max_length=100
                )
                self.subtitle = discord.ui.TextInput(
                    label="Subtitle",
                    placeholder="We're glad to have you here, {user}!",
                    default=guild_config.get("subtitle", "We're glad to have you here, {user}!"),
                    max_length=150
                )
                
                self.add_item(self.welcome_message)
                self.add_item(self.subtitle)
                
            async def on_submit(self, interaction: discord.Interaction):
                guild_config = self.cog._get_guild_config(self.guild_id)
                guild_config["welcome_message"] = self.welcome_message.value
                guild_config["subtitle"] = self.subtitle.value
                self.cog._save_config()
                
                embed = discord.Embed(
                    title="✅ Text Updated Successfully",
                    description="Welcome card text has been updated!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Welcome Message", value=self.welcome_message.value, inline=False)
                embed.add_field(name="Subtitle", value=self.subtitle.value, inline=False)
                embed.add_field(name="Available Variables", value="`{server}` - Server name\n`{user}` - User display name", inline=False)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
        class SettingsView(discord.ui.View):
            def __init__(self, cog, guild_id: int):
                super().__init__(timeout=300)
                self.cog = cog
                self.guild_id = guild_id
                
            @discord.ui.button(label="🔄 Toggle Member Count", style=discord.ButtonStyle.secondary)
            async def toggle_member_count(self, interaction: discord.Interaction, button: discord.ui.Button):
                guild_config = self.cog._get_guild_config(self.guild_id)
                guild_config["show_member_count"] = not guild_config.get("show_member_count", True)
                self.cog._save_config()
                
                status = "enabled" if guild_config["show_member_count"] else "disabled"
                await interaction.response.send_message(f"✅ Member count display {status}!", ephemeral=True)
                
            @discord.ui.button(label="📅 Toggle Join Date", style=discord.ButtonStyle.secondary)
            async def toggle_join_date(self, interaction: discord.Interaction, button: discord.ui.Button):
                guild_config = self.cog._get_guild_config(self.guild_id)
                guild_config["show_join_date"] = not guild_config.get("show_join_date", True)
                self.cog._save_config()
                
                status = "enabled" if guild_config["show_join_date"] else "disabled"
                await interaction.response.send_message(f"✅ Join date display {status}!", ephemeral=True)
                
            @discord.ui.button(label="🖼️ Toggle Border", style=discord.ButtonStyle.secondary)
            async def toggle_border(self, interaction: discord.Interaction, button: discord.ui.Button):
                guild_config = self.cog._get_guild_config(self.guild_id)
                guild_config["border_enabled"] = not guild_config.get("border_enabled", True)
                self.cog._save_config()
                
                status = "enabled" if guild_config["border_enabled"] else "disabled"
                await interaction.response.send_message(f"✅ Border {status}!", ephemeral=True)
                
            @discord.ui.button(label="🌫️ Toggle Shadow", style=discord.ButtonStyle.secondary)
            async def toggle_shadow(self, interaction: discord.Interaction, button: discord.ui.Button):
                guild_config = self.cog._get_guild_config(self.guild_id)
                guild_config["shadow_enabled"] = not guild_config.get("shadow_enabled", True)
                self.cog._save_config()
                
                status = "enabled" if guild_config["shadow_enabled"] else "disabled"
                await interaction.response.send_message(f"✅ Shadow effect {status}!", ephemeral=True)
                
            @discord.ui.button(label="🔙 Back to Main", style=discord.ButtonStyle.primary)
            async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
                embed = await self.cog.create_main_embed(self.guild_id)
                view = WelcomeCardGenerator.WelcomeCardView(self.cog, self.guild_id)
                await interaction.response.edit_message(embed=embed, view=view)

    async def create_main_embed(self, guild_id: int) -> discord.Embed:
        guild_config = self._get_guild_config(guild_id)
        
        embed = discord.Embed(
            title="🎨 Welcome Card Generator",
            description="Create beautiful custom welcome cards for your server!",
            color=discord.Color.blue()
        )
        
        status = "✅ Enabled" if guild_config.get("enabled", False) else "❌ Disabled"
        embed.add_field(name="Status", value=status, inline=True)
        
        channel_id = guild_config.get("channel_id")
        if channel_id:
            embed.add_field(name="Welcome Channel", value=f"<#{channel_id}>", inline=True)
        else:
            embed.add_field(name="Welcome Channel", value="Not set", inline=True)
            
        embed.add_field(name="Template", value=guild_config.get("template", "modern").title(), inline=True)
        
        embed.add_field(
            name="🎨 Colors",
            value=f"**Background:** {guild_config.get('background_color', '#2F3136')}\n"
                  f"**Text:** {guild_config.get('text_color', '#FFFFFF')}\n"
                  f"**Accent:** {guild_config.get('accent_color', '#5865F2')}",
            inline=True
        )
        
        settings_text = []
        if guild_config.get("show_member_count", True):
            settings_text.append("✅ Member Count")
        if guild_config.get("show_join_date", True):
            settings_text.append("✅ Join Date")
        if guild_config.get("border_enabled", True):
            settings_text.append("✅ Border")
        if guild_config.get("shadow_enabled", True):
            settings_text.append("✅ Shadow")
            
        embed.add_field(
            name="⚙️ Features",
            value="\n".join(settings_text) if settings_text else "None enabled",
            inline=True
        )
        
        embed.add_field(
            name="📝 Messages",
            value=f"**Welcome:** {guild_config.get('welcome_message', 'Welcome to {server}!')[:30]}...\n"
                  f"**Subtitle:** {guild_config.get('subtitle', 'We are glad to have you here!')[:30]}...",
            inline=False
        )
        
        embed.set_footer(text="Use the buttons below to customize your welcome cards!")
        
        return embed
        
    async def create_settings_embed(self, guild_id: int) -> discord.Embed:
        guild_config = self._get_guild_config(guild_id)
        
        embed = discord.Embed(
            title="⚙️ Welcome Card Settings",
            description="Toggle various features for your welcome cards",
            color=discord.Color.orange()
        )
        
        features = [
            ("Member Count", guild_config.get("show_member_count", True)),
            ("Join Date", guild_config.get("show_join_date", True)),
            ("Border", guild_config.get("border_enabled", True)),
            ("Shadow Effect", guild_config.get("shadow_enabled", True)),
            ("Background Blur", guild_config.get("blur_background", False))
        ]
        
        for feature, enabled in features:
            status = "✅ Enabled" if enabled else "❌ Disabled"
            embed.add_field(name=feature, value=status, inline=True)
            
        embed.set_footer(text="Click the buttons below to toggle features!")
        
        return embed

    @commands.group(name="welcomecard", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def welcomecard_prefix(self, ctx):
        if ctx.invoked_subcommand is None:
            embed = await self.create_main_embed(ctx.guild.id)
            view = self.WelcomeCardView(self, ctx.guild.id)
            await ctx.send(embed=embed, view=view)

    @welcomecard_prefix.command(name="setup")
    async def setup_welcomecard_prefix(self, ctx, channel: discord.TextChannel):
        guild_config = self._get_guild_config(ctx.guild.id)
        guild_config["enabled"] = True
        guild_config["channel_id"] = channel.id
        self._save_config()
        
        embed = discord.Embed(
            title="✅ Welcome Cards Setup Complete",
            description=f"Welcome cards are now enabled for {channel.mention}!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Next Steps",
            value="• Use `!welcomecard customize` to customize your cards\n"
                  "• Use `!welcomecard test` to preview your design\n"
                  "• Use `!welcomecard disable` to turn off welcome cards",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @welcomecard_prefix.command(name="customize")
    async def customize_welcomecard_prefix(self, ctx):
        guild_config = self._get_guild_config(ctx.guild.id)
        
        if not guild_config.get("enabled", False):
            embed = discord.Embed(
                title="❌ Welcome Cards Not Enabled",
                description="Please run `!welcomecard setup` first to enable welcome cards.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
            
        embed = await self.create_main_embed(ctx.guild.id)
        view = self.WelcomeCardView(self, ctx.guild.id)
        await ctx.send(embed=embed, view=view)

    @welcomecard_prefix.command(name="test")
    async def test_welcomecard_prefix(self, ctx):
        guild_config = self._get_guild_config(ctx.guild.id)
        
        if not guild_config.get("enabled", False):
            embed = discord.Embed(
                title="❌ Welcome Cards Not Enabled",
                description="Please run `!welcomecard setup` first to enable welcome cards.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
            
        async with ctx.typing():
            try:
                card_bytes = await self.generate_welcome_card(ctx.author, guild_config)
                file = discord.File(card_bytes, filename="welcome_test.png")
                
                embed = discord.Embed(
                    title="🧪 Welcome Card Test",
                    description="Here's how your welcome card looks!",
                    color=discord.Color.blue()
                )
                embed.set_image(url="attachment://welcome_test.png")
                embed.set_footer(text="Use !welcomecard customize to make changes")
                
                await ctx.send(embed=embed, file=file)
                
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Error Generating Card",
                    description=f"An error occurred while generating the welcome card: {str(e)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)

    @welcomecard_prefix.command(name="disable")
    async def disable_welcomecard_prefix(self, ctx):
        guild_config = self._get_guild_config(ctx.guild.id)
        guild_config["enabled"] = False
        self._save_config()
        
        embed = discord.Embed(
            title="✅ Welcome Cards Disabled",
            description="Welcome cards have been disabled for this server.",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="Re-enable",
            value="Use `!welcomecard setup` to re-enable welcome cards anytime.",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @welcomecard_prefix.command(name="channel")
    async def change_channel_prefix(self, ctx, channel: discord.TextChannel):
        guild_config = self._get_guild_config(ctx.guild.id)
        
        if not guild_config.get("enabled", False):
            embed = discord.Embed(
                title="❌ Welcome Cards Not Enabled",
                description="Please run `!welcomecard setup` first to enable welcome cards.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
            
        old_channel_id = guild_config.get("channel_id")
        guild_config["channel_id"] = channel.id
        self._save_config()
        
        embed = discord.Embed(
            title="✅ Welcome Channel Updated",
            description=f"Welcome cards will now be sent to {channel.mention}",
            color=discord.Color.green()
        )
        
        if old_channel_id:
            embed.add_field(
                name="Previous Channel",
                value=f"<#{old_channel_id}>",
                inline=True
            )
            
        await ctx.send(embed=embed)

    @welcomecard_prefix.command(name="templates")
    async def view_templates_prefix(self, ctx):
        
        embed = discord.Embed(
            title="🎨 Available Templates",
            description="Choose from these gorgeous welcome card templates:",
            color=discord.Color.purple()
        )
        
        templates = [
            ("🌟 Modern", "Clean and minimalist design with geometric patterns and gradients"),
            ("⚡ Neon", "Cyberpunk-inspired with glowing neon effects and electric colors"),
            ("🔮 Glass", "Elegant glassmorphism design with blur effects and transparency"),
            ("🤖 Cyberpunk", "Futuristic matrix-style with digital glitch effects"),
            ("👑 Elegant", "Sophisticated design with ornate decorations and gold accents"),
            ("🌌 Cosmic", "Space-themed with stars, nebulas, and cosmic phenomena"),
            ("🌈 Aurora", "Northern lights inspired with flowing wave patterns"),
            ("💫 TheZ Premium", "Ultra premium design with luxury effects and diamond accents")
        ]
        
        for name, description in templates:
            embed.add_field(
                name=name,
                value=description,
                inline=False
            )
            
        embed.add_field(
            name="How to Change",
            value="Use `!welcomecard template <name>` to switch templates",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @welcomecard_prefix.command(name="template")
    async def change_template_prefix(self, ctx, template: str):
        
        template = template.lower()
        valid_templates = ["modern", "neon", "glass", "cyberpunk", "elegant", "cosmic", "aurora", "thez"]
        
        if template not in valid_templates:
            embed = discord.Embed(
                title="❌ Invalid Template",
                description="Please choose a valid template: modern, neon, glass, cyberpunk, elegant, cosmic, aurora, thez",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
            
        guild_config = self._get_guild_config(ctx.guild.id)
        
        if not guild_config.get("enabled", False):
            embed = discord.Embed(
                title="❌ Welcome Cards Not Enabled",
                description="Please run `!welcomecard setup` first to enable welcome cards.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
            
        template_configs = self._get_template_configs()
        
        if template in template_configs:
            guild_config.update(template_configs[template])
            guild_config["template"] = template
            self._save_config()
            
            embed = discord.Embed(
                title="✅ Template Changed",
                description=f"Welcome card template changed to **{template.title()}**",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Test It Out",
                value="Use `!welcomecard test` to see how it looks!",
                inline=False
            )
            
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Invalid Template",
                description="Please choose a valid template name.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, ephemeral=True)

    @app_commands.command(name="welcomecard_info", description="Show welcome card configuration")
    @app_commands.default_permissions(manage_guild=True)
    async def welcomecard_info_slash(self, interaction: discord.Interaction):
        guild_config = self._get_guild_config(interaction.guild.id)
        
        embed = discord.Embed(
            title="ℹ️ Welcome Card Configuration",
            description="Current settings for your welcome cards",
            color=discord.Color.blue()
        )
        
        status = "✅ Enabled" if guild_config.get("enabled", False) else "❌ Disabled"
        embed.add_field(name="Status", value=status, inline=True)
        
        channel_id = guild_config.get("channel_id")
        channel_text = f"<#{channel_id}>" if channel_id else "Not set"
        embed.add_field(name="Channel", value=channel_text, inline=True)
        
        embed.add_field(name="Template", value=guild_config.get("template", "modern").title(), inline=True)
        
        embed.add_field(
            name="🎨 Colors",
            value=f"**Background:** {guild_config.get('background_color', '#2F3136')}\n"
                  f"**Text:** {guild_config.get('text_color', '#FFFFFF')}\n"
                  f"**Accent:** {guild_config.get('accent_color', '#5865F2')}\n"
                  f"**Border:** {guild_config.get('border_color', '#5865F2')}",
            inline=True
        )
        
        features = []
        if guild_config.get("show_member_count", True):
            features.append("✅ Member Count")
        if guild_config.get("show_join_date", True):
            features.append("✅ Join Date")
        if guild_config.get("border_enabled", True):
            features.append("✅ Border")
        if guild_config.get("shadow_enabled", True):
            features.append("✅ Shadow")
        if guild_config.get("blur_background", False):
            features.append("✅ Background Blur")
            
        embed.add_field(
            name="🔧 Features",
            value="\n".join(features) if features else "None enabled",
            inline=True
        )
        
        welcome_message = guild_config.get('welcome_message', 'Welcome to {server}!')
        subtitle_message = guild_config.get('subtitle', "We're glad to have you here, {user}!")
        
        embed.add_field(
            name="📝 Messages",
            value=f"**Welcome:** {welcome_message}\n**Subtitle:** {subtitle_message}",
            inline=False
        )
        
        embed.set_footer(text="Use /welcomecard_customize to make changes")
        
        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_config = self._get_guild_config(member.guild.id)
        
        if not guild_config.get("enabled", False):
            return
            
        channel_id = guild_config.get("channel_id")
        if not channel_id:
            return
            
        channel = member.guild.get_channel(channel_id)
        if not channel:
            return
            
        try:
            card_bytes = await self.generate_welcome_card(member, guild_config)
            file = discord.File(card_bytes, filename=f"welcome_{member.id}.png")
            
            embed = discord.Embed(
                title="🎉 Welcome to the Server!",
                description=f"Please give a warm welcome to {member.mention}!",
                color=discord.Color.green()
            )
            embed.set_image(url=f"attachment://welcome_{member.id}.png")
            embed.timestamp = datetime.now()
            
            await channel.send(embed=embed, file=file)
            
        except Exception as e:
            print(f"Error sending welcome card for {member}: {e}")

            embed = discord.Embed(
                title="🎉 Welcome!",
                description=guild_config.get("welcome_message", "Welcome to {server}!").replace("{server}", member.guild.name).replace("{user}", member.mention),
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)

    async def cog_command_error(self, ctx, error):
        
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description="You need `Manage Server` permissions to use welcome card commands.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                title="❌ Bot Missing Permissions",
                description="I need the following permissions to work properly:\n• Send Messages\n• Embed Links\n• Attach Files",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ An Error Occurred",
                description=f"Something went wrong: {str(error)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.group(name="welcomecard_custom", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def welcomecard_custom_prefix(self, ctx):
        if ctx.invoked_subcommand is None:
            embed = await self.create_custom_embed(ctx.guild.id)
            view = self.CustomWelcomeCardView(self, ctx.guild.id)
            await ctx.send(embed=embed, view=view)

    @app_commands.command(name="welcomecard_custom", description="Customize welcome card with custom fonts and backgrounds")
    @app_commands.default_permissions(manage_guild=True)
    async def welcomecard_custom_slash(self, interaction: discord.Interaction):
        embed = await self.create_custom_embed(interaction.guild.id)
        view = self.CustomWelcomeCardView(self, interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view)

    async def create_custom_embed(self, guild_id: int) -> discord.Embed:
        guild_config = self._get_guild_config(guild_id)
        
        embed = discord.Embed(
            title="🎨 Custom Welcome Card Settings",
            description="Customize your welcome cards with custom fonts and backgrounds!",
            color=discord.Color.purple()
        )
        

        current_font = guild_config.get("custom_font", "Default (Arial)")
        embed.add_field(
            name="📝 Font Settings",
            value=f"**Current Font:** {current_font}\n"
                  f"**Font Size:** {guild_config.get('font_size', 'Default')}\n"
                  f"**Font Style:** {guild_config.get('font_style', 'Normal')}",
            inline=True
        )
        

        current_bg = guild_config.get("custom_background", "None")
        embed.add_field(
            name="🖼️ Background Settings",
            value=f"**Current Background:** {current_bg}\n"
                  f"**Background Type:** {guild_config.get('background_type', 'Gradient')}\n"
                  f"**Background Opacity:** {guild_config.get('background_opacity', '100%')}",
            inline=True
        )
        

        custom_elements = []
        if guild_config.get("custom_border", False):
            custom_elements.append("✅ Custom Border")
        if guild_config.get("custom_shadow", False):
            custom_elements.append("✅ Custom Shadow")
        if guild_config.get("custom_effects", False):
            custom_elements.append("✅ Custom Effects")
            
        embed.add_field(
            name="✨ Custom Elements",
            value="\n".join(custom_elements) if custom_elements else "No custom elements enabled",
            inline=True
        )
        
        embed.set_footer(text="Use the buttons below to customize your welcome cards!")
        
        return embed

    class CustomWelcomeCardView(discord.ui.View):
        def __init__(self, cog, guild_id: int):
            super().__init__(timeout=300)
            self.cog = cog
            self.guild_id = guild_id
            
        @discord.ui.button(label="📝 Custom Font", style=discord.ButtonStyle.primary)
        async def custom_font(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(self.CustomFontModal(self.cog, self.guild_id))
            
        @discord.ui.button(label="🖼️ Custom Background", style=discord.ButtonStyle.secondary)
        async def custom_background(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(self.CustomBackgroundModal(self.cog, self.guild_id))
            
        @discord.ui.button(label="✨ Custom Elements", style=discord.ButtonStyle.secondary)
        async def custom_elements(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(self.CustomElementsModal(self.cog, self.guild_id))
            
        @discord.ui.button(label="🔄 Preview", style=discord.ButtonStyle.success)
        async def preview_custom(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            
            guild_config = self.cog._get_guild_config(self.guild_id)
            card_bytes = await self.cog.generate_welcome_card(interaction.user, guild_config)
            
            file = discord.File(card_bytes, filename="welcome_preview.png")
            embed = discord.Embed(
                title="🖼️ Custom Welcome Card Preview",
                description="Here's how your custom welcome card will look!",
                color=discord.Color.green()
            )
            embed.set_image(url="attachment://welcome_preview.png")
            
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            
        class CustomFontModal(discord.ui.Modal):
            def __init__(self, cog, guild_id: int):
                super().__init__(title="📝 Custom Font Settings")
                self.cog = cog
                self.guild_id = guild_id
                
                guild_config = cog._get_guild_config(guild_id)
                
                self.font_name = discord.ui.TextInput(
                    label="Font Name",
                    placeholder="Enter font name (e.g., Arial, Roboto)",
                    default=guild_config.get("custom_font", "Arial"),
                    max_length=50
                )
                self.font_size = discord.ui.TextInput(
                    label="Font Size",
                    placeholder="Enter font size (e.g., 24, 36)",
                    default=str(guild_config.get("font_size", "24")),
                    max_length=3
                )
                self.font_style = discord.ui.TextInput(
                    label="Font Style",
                    placeholder="Enter font style (e.g., Bold, Italic)",
                    default=guild_config.get("font_style", "Normal"),
                    max_length=20
                )
                
                self.add_item(self.font_name)
                self.add_item(self.font_size)
                self.add_item(self.font_style)
                
            async def on_submit(self, interaction: discord.Interaction):
                guild_config = self.cog._get_guild_config(self.guild_id)
                

                guild_config["custom_font"] = self.font_name.value
                try:
                    guild_config["font_size"] = int(self.font_size.value)
                except ValueError:
                    await interaction.response.send_message("❌ Invalid font size. Please enter a number.", ephemeral=True)
                    return
                guild_config["font_style"] = self.font_style.value
                
                self.cog._save_config()
                
                embed = discord.Embed(
                    title="✅ Font Settings Updated",
                    description="Your custom font settings have been updated!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Font Name", value=self.font_name.value, inline=True)
                embed.add_field(name="Font Size", value=self.font_size.value, inline=True)
                embed.add_field(name="Font Style", value=self.font_style.value, inline=True)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
        class CustomBackgroundModal(discord.ui.Modal):
            def __init__(self, cog, guild_id: int):
                super().__init__(title="🖼️ Custom Background Settings")
                self.cog = cog
                self.guild_id = guild_id
                
                guild_config = cog._get_guild_config(guild_id)
                
                self.background_type = discord.ui.TextInput(
                    label="Background Type",
                    placeholder="Enter background type (e.g., Image, Gradient, Pattern)",
                    default=guild_config.get("background_type", "Gradient"),
                    max_length=20
                )
                self.background_url = discord.ui.TextInput(
                    label="Background URL",
                    placeholder="Enter image URL for background (if using image type)",
                    default=guild_config.get("background_url", ""),
                    max_length=200,
                    required=False
                )
                self.background_opacity = discord.ui.TextInput(
                    label="Background Opacity",
                    placeholder="Enter opacity (0-100)",
                    default=str(guild_config.get("background_opacity", "100")),
                    max_length=3
                )
                
                self.add_item(self.background_type)
                self.add_item(self.background_url)
                self.add_item(self.background_opacity)
                
            async def on_submit(self, interaction: discord.Interaction):
                guild_config = self.cog._get_guild_config(self.guild_id)
                

                guild_config["background_type"] = self.background_type.value
                if self.background_url.value:
                    guild_config["background_url"] = self.background_url.value
                try:
                    opacity = int(self.background_opacity.value)
                    if 0 <= opacity <= 100:
                        guild_config["background_opacity"] = opacity
                    else:
                        await interaction.response.send_message("❌ Invalid opacity. Please enter a number between 0 and 100.", ephemeral=True)
                        return
                except ValueError:
                    await interaction.response.send_message("❌ Invalid opacity. Please enter a number.", ephemeral=True)
                    return
                
                self.cog._save_config()
                
                embed = discord.Embed(
                    title="✅ Background Settings Updated",
                    description="Your custom background settings have been updated!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Background Type", value=self.background_type.value, inline=True)
                if self.background_url.value:
                    embed.add_field(name="Background URL", value=self.background_url.value, inline=True)
                embed.add_field(name="Background Opacity", value=f"{self.background_opacity.value}%", inline=True)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
        class CustomElementsModal(discord.ui.Modal):
            def __init__(self, cog, guild_id: int):
                super().__init__(title="✨ Custom Elements Settings")
                self.cog = cog
                self.guild_id = guild_id
                
                guild_config = cog._get_guild_config(guild_id)
                
                self.custom_border = discord.ui.TextInput(
                    label="Custom Border",
                    placeholder="Enter border style (e.g., Solid, Dashed, None)",
                    default=guild_config.get("custom_border", "Solid"),
                    max_length=20
                )
                self.custom_shadow = discord.ui.TextInput(
                    label="Custom Shadow",
                    placeholder="Enter shadow style (e.g., Soft, Hard, None)",
                    default=guild_config.get("custom_shadow", "Soft"),
                    max_length=20
                )
                self.custom_effects = discord.ui.TextInput(
                    label="Custom Effects",
                    placeholder="Enter effects (e.g., Glow, Blur, None)",
                    default=guild_config.get("custom_effects", "None"),
                    max_length=20
                )
                
                self.add_item(self.custom_border)
                self.add_item(self.custom_shadow)
                self.add_item(self.custom_effects)
                
            async def on_submit(self, interaction: discord.Interaction):
                guild_config = self.cog._get_guild_config(self.guild_id)
                

                guild_config["custom_border"] = self.custom_border.value
                guild_config["custom_shadow"] = self.custom_shadow.value
                guild_config["custom_effects"] = self.custom_effects.value
                
                self.cog._save_config()
                
                embed = discord.Embed(
                    title="✅ Custom Elements Updated",
                    description="Your custom elements settings have been updated!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Border Style", value=self.custom_border.value, inline=True)
                embed.add_field(name="Shadow Style", value=self.custom_shadow.value, inline=True)
                embed.add_field(name="Effects", value=self.custom_effects.value, inline=True)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)


def setup(bot):
    
    cog = WelcomeCardGenerator(bot)
    
    loop = asyncio.get_event_loop()
    loop.create_task(bot.add_cog(cog))
    
    return cog
