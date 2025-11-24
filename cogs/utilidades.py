import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import re
from typing import Optional
import aiohttp


class UtilidadesCog(commands.Cog):
    """Cog para comandos de utilidades"""
    
    def __init__(self, bot):
        self.bot = bot
        self.lembretes_ativos = {}  # Armazenar lembretes ativos

    @app_commands.command(name="avatar", description="Mostra o avatar de um utilizador")
    @app_commands.describe(utilizador="Utilizador para ver o avatar (padrão: você)")
    async def avatar(self, interaction: discord.Interaction, utilizador: Optional[discord.Member] = None):
        """Mostra o avatar de um utilizador"""
        target = utilizador or interaction.user
        
        embed = discord.Embed(
            title=f"🖼️ Avatar de {target.display_name}",
            color=target.color if target.color != discord.Color.default() else discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        # Avatar principal
        embed.set_image(url=target.display_avatar.url)
        
        # Links para diferentes tamanhos
        avatar_url = str(target.display_avatar.url)
        links = []
        for size in [128, 256, 512, 1024]:
            size_url = avatar_url.replace("?size=1024", f"?size={size}")
            links.append(f"[{size}x{size}]({size_url})")
        
        embed.add_field(
            name="🔗 Downloads",
            value=" • ".join(links),
            inline=False
        )
        
        embed.set_footer(text=f"Solicitado por {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="emoji", description="Mostra um emoji em tamanho grande")
    @app_commands.describe(emoji="Emoji customizado do servidor para ampliar")
    async def emoji_enlarge(self, interaction: discord.Interaction, emoji: str):
        """Amplia um emoji customizado"""
        # Extrair ID do emoji customizado
        emoji_match = re.match(r'<(a?):(\w+):(\d+)>', emoji)
        
        if not emoji_match:
            return await interaction.response.send_message(
                "❌ Por favor, usa um emoji customizado do servidor!\n💡 Exemplo: `/emoji :nome_do_emoji:`",
                ephemeral=True
            )
        
        animated = emoji_match.group(1) == 'a'
        emoji_name = emoji_match.group(2)
        emoji_id = emoji_match.group(3)
        
        # URL do emoji
        extension = 'gif' if animated else 'png'
        emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{extension}?size=1024&quality=lossless"
        
        embed = discord.Embed(
            title=f"📸 Emoji: {emoji_name}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        embed.set_image(url=emoji_url)
        
        # Links para diferentes tamanhos
        links = []
        for size in [128, 256, 512, 1024]:
            size_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{extension}?size={size}"
            links.append(f"[{size}x{size}]({size_url})")
        
        embed.add_field(
            name="🔗 Downloads",
            value=" • ".join(links),
            inline=False
        )
        
        if animated:
            embed.add_field(name="✨ Tipo", value="Animado (GIF)", inline=True)
        else:
            embed.add_field(name="✨ Tipo", value="Estático (PNG)", inline=True)
        
        embed.set_footer(text=f"Solicitado por {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="emojiinfo", description="Mostra informações detalhadas de um emoji")
    @app_commands.describe(emoji="Emoji customizado para obter informações")
    async def emoji_info(self, interaction: discord.Interaction, emoji: str):
        """Mostra informações técnicas de um emoji customizado"""
        # Extrair ID do emoji customizado
        emoji_match = re.match(r'<(a?):(\w+):(\d+)>', emoji)
        
        if not emoji_match:
            return await interaction.response.send_message(
                "❌ Por favor, usa um emoji customizado do servidor!\n💡 Exemplo: `/emojiinfo :nome_do_emoji:`",
                ephemeral=True
            )
        
        animated = emoji_match.group(1) == 'a'
        emoji_name = emoji_match.group(2)
        emoji_id = emoji_match.group(3)
        
        # Tentar encontrar o emoji no servidor
        discord_emoji = discord.utils.get(interaction.guild.emojis, id=int(emoji_id))
        
        embed = discord.Embed(
            title=f"ℹ️ Informações do Emoji",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        # URL do emoji
        extension = 'gif' if animated else 'png'
        emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{extension}?size=128"
        embed.set_thumbnail(url=emoji_url)
        
        # Informações básicas
        embed.add_field(name="📛 Nome", value=f"`:{emoji_name}:`", inline=True)
        embed.add_field(name="🆔 ID", value=f"`{emoji_id}`", inline=True)
        embed.add_field(name="✨ Tipo", value="Animado" if animated else "Estático", inline=True)
        
        # Informações do servidor (se disponível)
        if discord_emoji:
            embed.add_field(name="📅 Criado em", value=discord_emoji.created_at.strftime("%d/%m/%Y %H:%M"), inline=True)
            embed.add_field(name="👤 Criador", value=discord_emoji.user.mention if discord_emoji.user else "Desconhecido", inline=True)
            embed.add_field(name="🔓 Disponível", value="Sim" if discord_emoji.available else "Não", inline=True)
            embed.add_field(name="🔐 Gerido", value="Sim" if discord_emoji.managed else "Não", inline=True)
            embed.add_field(name="📜 Requer Colons", value="Sim" if discord_emoji.require_colons else "Não", inline=True)
            
            # Roles que podem usar (se restrito)
            if discord_emoji.roles:
                roles_str = ", ".join([role.mention for role in discord_emoji.roles[:5]])
                if len(discord_emoji.roles) > 5:
                    roles_str += f" e mais {len(discord_emoji.roles) - 5}"
                embed.add_field(name="👥 Restrito a Roles", value=roles_str, inline=False)
            else:
                embed.add_field(name="👥 Restrito a Roles", value="Nenhuma (Todos podem usar)", inline=False)
        
        # URL direto
        full_emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{extension}?size=1024&quality=lossless"
        embed.add_field(name="🔗 URL Direto", value=f"[Clique aqui]({full_emoji_url})", inline=False)
        
        # Markdown
        emoji_markdown = f"`<{'a' if animated else ''}:{emoji_name}:{emoji_id}>`"
        embed.add_field(name="📝 Markdown", value=emoji_markdown, inline=False)
        
        embed.set_footer(text=f"Solicitado por {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    """Função para carregar o cog"""
    await bot.add_cog(UtilidadesCog(bot))
