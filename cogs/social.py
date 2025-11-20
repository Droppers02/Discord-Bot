import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import random
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import logging

from utils.embeds import EmbedBuilder
from utils.database import get_database


class SocialCog(commands.Cog):
    """Cog para funcionalidades sociais e interação"""
    
    def __init__(self, bot):
        self.bot = bot
        self.welcome_file = "data/welcome_config.json"
        self.db = None  # Será inicializado em cog_load
        self.ensure_welcome_file()
        self.load_welcome_config()
        
        # Cooldowns para XP e reputação
        self.xp_cooldowns = {}
        self.rep_cooldowns = {}
        self.levelup_notified = {}  # Evitar notificações duplicadas de level up
    
    async def cog_load(self):
        """Carregado quando o cog é inicializado"""
        try:
            self.db = await get_database()
        except Exception as e:
            self.bot.logger.error(f"Erro ao carregar database no social: {e}")

    def ensure_welcome_file(self):
        """Garantir que o arquivo de welcome existe"""
        os.makedirs("data", exist_ok=True)
        
        if not os.path.exists(self.welcome_file):
            with open(self.welcome_file, 'w', encoding='utf-8') as f:
                json.dump({"guilds": {}}, f, indent=2)

    def load_welcome_config(self):
        """Carregar configurações de boas-vindas"""
        try:
            with open(self.welcome_file, 'r', encoding='utf-8') as f:
                self.welcome_config = json.load(f)
        except:
            self.welcome_config = {"guilds": {}}

    def save_welcome_config(self):
        """Salvar configurações de boas-vindas"""
        try:
            with open(self.welcome_file, 'w', encoding='utf-8') as f:
                json.dump(self.welcome_config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.bot.logger.error(f"Erro ao salvar config de boas-vindas: {e}")

    def calculate_level(self, xp: int) -> int:
        """Calcular nível baseado no XP"""
        return int((xp / 100) ** 0.5) + 1

    def xp_for_level(self, level: int) -> int:
        """XP necessário para um nível"""
        return ((level - 1) ** 2) * 100

    @commands.Cog.listener()
    async def on_message(self, message):
        """Sistema de XP por mensagens - agora com base de dados"""
        if message.author.bot or not message.guild or not self.db:
            return
        
        user_id = str(message.author.id)
        guild_id = str(message.guild.id)
        
        # Verificar cooldown (1 XP por minuto máximo)
        cooldown_key = f"{user_id}_{guild_id}"
        now = datetime.utcnow().timestamp()
        
        if cooldown_key in self.xp_cooldowns:
            if now - self.xp_cooldowns[cooldown_key] < 60:  # 60 segundos
                return
        
        self.xp_cooldowns[cooldown_key] = now
        
        try:
            # Buscar XP/level atual da base de dados
            level_data = await self.db.get_user_level(user_id, guild_id)
            old_level = level_data["level"]
            old_xp = level_data["xp"]
            
            # XP aleatório entre 15-25
            xp_gain = random.randint(15, 25)
            new_xp = old_xp + xp_gain
            
            # Calcular novo nível
            new_level = self.calculate_level(new_xp)
            
            # Atualizar na base de dados
            await self.db.update_user_level(user_id, guild_id, new_xp, new_level)
            
            # Atualizar streak de mensagens (1 dia de streak)
            await self.db.update_streak(user_id, guild_id, "messages", 1)
            
            # Se subiu de nível, enviar notificação
            if new_level > old_level:
                # Verificar se já notificamos este level up (evitar duplicados)
                levelup_key = f"{user_id}_{guild_id}_{new_level}"
                
                if levelup_key not in self.levelup_notified:
                    self.levelup_notified[levelup_key] = now
                    
                    embed = EmbedBuilder.level_up(
                        user=message.author,
                        level=new_level,
                        xp=new_xp
                    )
                    
                    try:
                        await message.channel.send(embed=embed, delete_after=10)
                    except:
                        pass
                    
                    # Dar badge por marco de nível
                    if new_level == 10:
                        await self.db.add_badge(user_id, guild_id, "level_10", "Nível 10", "🔟", "Atingiu nível 10")
                    elif new_level == 25:
                        await self.db.add_badge(user_id, guild_id, "level_25", "Nível 25", "🎖️", "Atingiu nível 25")
                    elif new_level == 50:
                        await self.db.add_badge(user_id, guild_id, "level_50", "Nível 50", "⭐", "Atingiu nível 50")
                    elif new_level == 100:
                        await self.db.add_badge(user_id, guild_id, "level_100", "Nível 100", "👑", "Atingiu nível 100!")
                    
                    # Log de atividade
                    await self.db.log_activity(user_id, guild_id, "level_up", f"Subiu para nível {new_level}")
                
                # Limpar notificações antigas (mais de 5 minutos)
                old_keys = [k for k, v in self.levelup_notified.items() if now - v > 300]
                for k in old_keys:
                    del self.levelup_notified[k]
        
        except Exception as e:
            self.bot.logger.error(f"Erro ao processar XP: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Mensagem de boas-vindas"""
        guild_id = str(member.guild.id)
        
        if guild_id not in self.welcome_config["guilds"]:
            return
        
        config = self.welcome_config["guilds"][guild_id]
        
        if not config.get("welcome_enabled", False):
            return
        
        channel_id = config.get("welcome_channel")
        if not channel_id:
            return
        
        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return
        
        # Mensagem personalizada ou padrão
        message = config.get("welcome_message", 
            "🎉 Bem-vindo ao servidor **{server}**, {user}! Esperamos que te diviertas!")
        
        message = message.format(
            user=member.mention,
            server=member.guild.name,
            username=member.name,
            display_name=member.display_name
        )
        
        embed = discord.Embed(
            title="👋 Novo Membro!",
            description=message,
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Membro #{member.guild.member_count}")
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            self.bot.logger.error(f"Erro ao enviar boas-vindas: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Mensagem de despedida"""
        guild_id = str(member.guild.id)
        
        if guild_id not in self.welcome_config["guilds"]:
            return
        
        config = self.welcome_config["guilds"][guild_id]
        
        if not config.get("goodbye_enabled", False):
            return
        
        channel_id = config.get("goodbye_channel")
        if not channel_id:
            return
        
        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return
        
        # Mensagem personalizada ou padrão
        message = config.get("goodbye_message", 
            "😢 **{username}** saiu do servidor. Até à próxima!")
        
        message = message.format(
            username=member.name,
            display_name=member.display_name,
            server=member.guild.name
        )
        
        embed = discord.Embed(
            title="👋 Membro Saiu",
            description=message,
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Restam {member.guild.member_count} membros")
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            self.bot.logger.error(f"Erro ao enviar despedida: {e}")

    @app_commands.command(name="rank", description="Mostra o teu nível e XP")
    @app_commands.describe(utilizador="Utilizador para ver o rank (padrão: você)")
    async def rank(self, interaction: discord.Interaction, utilizador: Optional[discord.Member] = None):
        """Mostra o rank/nível de um utilizador - agora com base de dados"""
        await interaction.response.defer()
        
        target = utilizador or interaction.user
        user_id = str(target.id)
        guild_id = str(interaction.guild.id)
        
        if not self.db:
            await interaction.followup.send("❌ Base de dados não disponível!", ephemeral=True)
            return
        
        try:
            # Buscar dados da base de dados
            level_data = await self.db.get_user_level(user_id, guild_id)
            
            level = level_data["level"]
            current_xp = level_data["xp"]
            xp_for_current = self.xp_for_level(level)
            xp_for_next = self.xp_for_level(level + 1)
            xp_progress = current_xp - xp_for_current
            xp_needed = xp_for_next - xp_for_current
            
            # Garantir que os valores são positivos
            if xp_progress < 0:
                xp_progress = 0
            if xp_needed <= 0:
                xp_needed = 1
            
            # Barra de progresso
            progress_bar_length = 20
            filled = int((xp_progress / xp_needed) * progress_bar_length)
            bar = "█" * filled + "░" * (progress_bar_length - filled)
            
            embed = discord.Embed(
                title=f"📊 Rank de {target.display_name}",
                color=target.color if target.color != discord.Color.default() else discord.Color.blue()
            )
            
            embed.set_thumbnail(url=target.display_avatar.url)
            
            embed.add_field(
                name="🏆 Nível",
                value=f"**{level}**",
                inline=True
            )
            
            embed.add_field(
                name="✨ XP Total",
                value=f"**{current_xp:,}**",
                inline=True
            )
            
            embed.add_field(
                name="✨ XP Total",
                value=f"**{current_xp:,}**",
                inline=True
            )
            
            embed.add_field(
                name="📈 Reputação",
                value=f"**{level_data.get('reputation', 0)}**",
                inline=True
            )
            
            embed.add_field(
                name="📊 Progresso para Nível" + str(level + 1),
                value=f"{bar}\n{xp_progress:,}/{xp_needed:,} XP ({(xp_progress/xp_needed)*100:.1f}%)",
                inline=False
            )
            
            embed.add_field(
                name="💬 Mensagens Enviadas",
                value=f"**{level_data.get('messages', 0):,}**",
                inline=True
            )
            
            embed.add_field(
                name="💬 Mensagens Enviadas",
                value=f"**{messages:,}**",
                inline=True
            )
            
            embed.set_footer(text=f"Solicitado por {interaction.user.display_name}")
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            self.bot.logger.error(f"Erro ao buscar rank: {e}")
            await interaction.followup.send("❌ Erro ao buscar rank!", ephemeral=True)

    @app_commands.command(name="like", description="Dá um like/reputação a um utilizador")
    @app_commands.describe(utilizador="Utilizador para dar like")
    async def like(self, interaction: discord.Interaction, utilizador: discord.Member):
        """Sistema de reputação/likes"""
        if utilizador.id == interaction.user.id:
            await interaction.response.send_message("❌ Não podes dar like a ti próprio!", ephemeral=True)
            return
        
        if utilizador.bot:
            await interaction.response.send_message("❌ Não podes dar like a bots!", ephemeral=True)
            return
        
        # Verificar cooldown (1 like por hora por pessoa)
        cooldown_key = f"{interaction.user.id}_{utilizador.id}"
        now = datetime.utcnow().timestamp()
        
        if cooldown_key in self.rep_cooldowns:
            time_left = 3600 - (now - self.rep_cooldowns[cooldown_key])  # 1 hora
            if time_left > 0:
                minutes = int(time_left // 60)
                seconds = int(time_left % 60)
                await interaction.response.send_message(
                    f"❌ Tens de esperar **{minutes}m {seconds}s** para dar like a {utilizador.display_name} novamente!", 
                    ephemeral=True
                )
                return
        
        self.rep_cooldowns[cooldown_key] = now
        
        # Dar reputação (via base de dados)
        if not self.db:
            await interaction.response.send_message("❌ Base de dados não disponível!", ephemeral=True)
            return
        
        try:
            # Incrementar reputação
            await self.db.execute(
                """INSERT INTO user_levels (user_id, guild_id, reputation, xp, level)
                   VALUES (?, ?, 1, 0, 1)
                   ON CONFLICT(user_id, guild_id) 
                   DO UPDATE SET reputation = reputation + 1""",
                (str(utilizador.id), str(interaction.guild.id))
            )
            await self.db.commit()
            
            # Buscar nova reputação
            level_data = await self.db.get_user_level(str(utilizador.id), str(interaction.guild.id))
            reputation = level_data.get("reputation", 1)
            
            embed = discord.Embed(
                title="👍 Like Dado!",
                description=f"{interaction.user.mention} deu like a {utilizador.mention}!",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="✨ Nova Reputação",
                value=f"**{reputation}** likes",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            self.bot.logger.error(f"Erro ao dar like: {e}")
            await interaction.response.send_message("❌ Erro ao dar like!", ephemeral=True)

    @app_commands.command(name="leaderboard", description="Mostra o ranking do servidor")
    @app_commands.describe(tipo="Tipo de ranking (xp ou reputacao)")
    @app_commands.choices(tipo=[
        app_commands.Choice(name="XP/Nível", value="xp"),
        app_commands.Choice(name="Reputação", value="reputation")
    ])
    async def leaderboard(self, interaction: discord.Interaction, tipo: str = "xp"):
        """Mostra o ranking do servidor - agora com base de dados"""
        await interaction.response.defer()
        
        guild_id = str(interaction.guild.id)
        
        if not self.db:
            await interaction.followup.send("❌ Base de dados não disponível!", ephemeral=True)
            return
        
        try:
            # Buscar dados da base de dados
            if tipo == "xp":
                query = """SELECT user_id, xp, level 
                          FROM user_levels 
                          WHERE guild_id = ? 
                          ORDER BY xp DESC 
                          LIMIT 10"""
                title = "🏆 Ranking por XP/Nível"
            else:
                query = """SELECT user_id, reputation, level 
                          FROM user_levels 
                          WHERE guild_id = ? AND reputation > 0
                          ORDER BY reputation DESC 
                          LIMIT 10"""
                title = "👍 Ranking por Reputação"
            
            async with self.db.execute(query, (guild_id,)) as cursor:
                rows = await cursor.fetchall()
            
            embed = discord.Embed(
                title=title,
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )
            
            # Top 10
            leaderboard_text = ""
            for i, row in enumerate(rows, 1):
                try:
                    user_id = row[0]
                    user = interaction.guild.get_member(int(user_id))
                    if not user:
                        continue
                    
                    if tipo == "xp":
                        value = f"Nível {row[2]} ({row[1]:,} XP)"
                    else:
                        value = f"{row[1]} likes"
                    
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
                    leaderboard_text += f"{medal} {user.display_name}: {value}\n"
                    
                except:
                    continue
            
            if not leaderboard_text:
                leaderboard_text = "Nenhum dado encontrado!"
            
            embed.description = leaderboard_text
            embed.set_footer(text=f"Solicitado por {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            self.bot.logger.error(f"Erro ao buscar leaderboard: {e}")
            await interaction.followup.send("❌ Erro ao buscar ranking!", ephemeral=True)

    @app_commands.command(name="welcome_config", description="[ADMIN] Configura mensagens de boas-vindas")
    @app_commands.describe(
        acao="Ação a realizar",
        canal="Canal para mensagens (boas-vindas ou despedidas)",
        mensagem="Mensagem personalizada"
    )
    @app_commands.choices(acao=[
        app_commands.Choice(name="Ativar Boas-vindas", value="enable_welcome"),
        app_commands.Choice(name="Desativar Boas-vindas", value="disable_welcome"),
        app_commands.Choice(name="Ativar Despedidas", value="enable_goodbye"),
        app_commands.Choice(name="Desativar Despedidas", value="disable_goodbye"),
        app_commands.Choice(name="Definir Canal Boas-vindas", value="set_welcome_channel"),
        app_commands.Choice(name="Definir Canal Despedidas", value="set_goodbye_channel"),
        app_commands.Choice(name="Definir Mensagem Boas-vindas", value="set_welcome_message"),
        app_commands.Choice(name="Definir Mensagem Despedidas", value="set_goodbye_message")
    ])
    async def welcome_config(self, interaction: discord.Interaction, acao: str, 
                           canal: Optional[discord.TextChannel] = None, 
                           mensagem: Optional[str] = None):
        """Configurar sistema de boas-vindas (apenas admin)"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem usar este comando!", ephemeral=True)
            return
        
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.welcome_config["guilds"]:
            self.welcome_config["guilds"][guild_id] = {}
        
        config = self.welcome_config["guilds"][guild_id]
        
        if acao == "enable_welcome":
            config["welcome_enabled"] = True
            message = "✅ Mensagens de boas-vindas ativadas!"
        
        elif acao == "disable_welcome":
            config["welcome_enabled"] = False
            message = "❌ Mensagens de boas-vindas desativadas!"
        
        elif acao == "enable_goodbye":
            config["goodbye_enabled"] = True
            message = "✅ Mensagens de despedida ativadas!"
        
        elif acao == "disable_goodbye":
            config["goodbye_enabled"] = False
            message = "❌ Mensagens de despedida desativadas!"
        
        elif acao == "set_welcome_channel":
            if not canal:
                await interaction.response.send_message("❌ Precisa especificar um canal!", ephemeral=True)
                return
            config["welcome_channel"] = canal.id
            message = f"✅ Canal de boas-vindas definido para {canal.mention}!"
        
        elif acao == "set_goodbye_channel":
            if not canal:
                await interaction.response.send_message("❌ Precisa especificar um canal!", ephemeral=True)
                return
            config["goodbye_channel"] = canal.id
            message = f"✅ Canal de despedidas definido para {canal.mention}!"
        
        elif acao == "set_welcome_message":
            if not mensagem:
                await interaction.response.send_message("❌ Precisa especificar uma mensagem!", ephemeral=True)
                return
            config["welcome_message"] = mensagem
            message = "✅ Mensagem de boas-vindas definida!"
        
        elif acao == "set_goodbye_message":
            if not mensagem:
                await interaction.response.send_message("❌ Precisa especificar uma mensagem!", ephemeral=True)
                return
            config["goodbye_message"] = mensagem
            message = "✅ Mensagem de despedida definida!"
        
        self.save_welcome_config()
        
        embed = discord.Embed(
            title="⚙️ Configuração Atualizada",
            description=message,
            color=discord.Color.green()
        )
        
        # Mostrar configuração atual
        status_text = ""
        if config.get("welcome_enabled", False):
            channel = interaction.guild.get_channel(config.get("welcome_channel"))
            status_text += f"✅ Boas-vindas: {channel.mention if channel else 'Canal não definido'}\n"
        else:
            status_text += "❌ Boas-vindas: Desativadas\n"
        
        if config.get("goodbye_enabled", False):
            channel = interaction.guild.get_channel(config.get("goodbye_channel"))
            status_text += f"✅ Despedidas: {channel.mention if channel else 'Canal não definido'}\n"
        else:
            status_text += "❌ Despedidas: Desativadas\n"
        
        embed.add_field(name="Status Atual", value=status_text, inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    # ===== SISTEMA DE PERFIS CUSTOMIZÁVEIS =====
    
    @app_commands.command(name="perfil", description="Ver perfil de um utilizador")
    @app_commands.describe(utilizador="Utilizador para ver perfil (opcional)")
    async def profile(self, interaction: discord.Interaction, utilizador: Optional[discord.Member] = None):
        """Ver perfil completo de utilizador"""
        target = utilizador or interaction.user
        user_id = str(target.id)
        guild_id = str(interaction.guild.id)
        
        await interaction.response.defer()
        
        if not self.db:
            await interaction.followup.send("❌ Base de dados não disponível!", ephemeral=True)
            return
        
        # Dados de XP/Level da base de dados
        level_data = await self.db.get_user_level(user_id, guild_id)
        
        # Dados do perfil customizado
        profile = await self.db.get_profile(user_id, guild_id)
        
        # Badges
        badges = await self.db.get_user_badges(user_id, guild_id)
        
        # Marriage
        marriage = await self.db.get_marriage(guild_id, user_id)
        
        # Criar embed
        color = int(profile["color"].replace("#", ""), 16) if profile and profile.get("color") else 0x5865F2
        embed = discord.Embed(
            title=f"👤 Perfil de {target.display_name}",
            color=discord.Color(color)
        )
        
        # Banner
        if profile and profile.get("banner_url"):
            embed.set_image(url=profile["banner_url"])
        
        embed.set_thumbnail(url=target.display_avatar.url)
        
        # Bio
        if profile and profile.get("bio"):
            embed.description = f"*{profile['bio']}*"
        
        # Stats básicos (usando base de dados)
        embed.add_field(
            name="📊 Estatísticas",
            value=f"**Level:** {level_data['level']}\n"
                  f"**XP:** {level_data['xp']}\n"
                  f"**Reputação:** {level_data.get('reputation', 0)}\n"
                  f"**Mensagens:** {level_data.get('messages', 0)}",
            inline=True
        )
        
        # Info adicional
        info_text = ""
        if profile:
            if profile.get("pronouns"):
                info_text += f"**Pronomes:** {profile['pronouns']}\n"
            if profile.get("birthday"):
                info_text += f"**Aniversário:** {profile['birthday']}\n"
            if profile.get("favorite_game"):
                info_text += f"**Jogo Favorito:** {profile['favorite_game']}\n"
        
        if marriage:
            partner = interaction.guild.get_member(int(marriage["partner_id"]))
            if partner:
                ring_emoji = "💎" if marriage.get("ring_tier") == 3 else "💍"
                info_text += f"{ring_emoji} **Casado(a) com:** {partner.mention}\n"
        
        if info_text:
            embed.add_field(name="ℹ️ Informações", value=info_text, inline=True)
        
        # Badges
        if badges:
            badge_text = " ".join([f"{b['emoji']} {b['name']}" for b in badges[:5]])
            if len(badges) > 5:
                badge_text += f" +{len(badges)-5}"
            embed.add_field(name=f"🏅 Badges ({len(badges)})", value=badge_text, inline=False)
        
        # Campos customizados
        if profile:
            if profile.get("custom_field_1") and profile["custom_field_1"]["name"]:
                embed.add_field(
                    name=profile["custom_field_1"]["name"],
                    value=profile["custom_field_1"]["value"],
                    inline=True
                )
            if profile.get("custom_field_2") and profile["custom_field_2"]["name"]:
                embed.add_field(
                    name=profile["custom_field_2"]["name"],
                    value=profile["custom_field_2"]["value"],
                    inline=True
                )
        
        embed.set_footer(text=f"Membro desde {target.joined_at.strftime('%d/%m/%Y')}")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="editarperfil", description="Editar o teu perfil")
    async def edit_profile(self, interaction: discord.Interaction):
        """Editar perfil usando modal"""
        
        class ProfileModal(discord.ui.Modal, title="Editar Perfil"):
            bio = discord.ui.TextInput(
                label="Bio",
                placeholder="Escreve algo sobre ti...",
                style=discord.TextStyle.paragraph,
                required=False,
                max_length=200
            )
            
            pronouns = discord.ui.TextInput(
                label="Pronomes",
                placeholder="ele/dele, ela/dela, etc.",
                required=False,
                max_length=30
            )
            
            birthday = discord.ui.TextInput(
                label="Aniversário",
                placeholder="DD/MM",
                required=False,
                max_length=5
            )
            
            favorite_game = discord.ui.TextInput(
                label="Jogo Favorito",
                placeholder="Qual é o teu jogo favorito?",
                required=False,
                max_length=50
            )
            
            async def on_submit(modal_self, interaction: discord.Interaction):
                user_id = str(interaction.user.id)
                guild_id = str(interaction.guild.id)
                
                db = await get_database()
                await db.update_profile(
                    user_id, guild_id,
                    bio=modal_self.bio.value,
                    pronouns=modal_self.pronouns.value,
                    birthday=modal_self.birthday.value,
                    favorite_game=modal_self.favorite_game.value
                )
                
                await interaction.response.send_message(
                    "✅ Perfil atualizado com sucesso!",
                    ephemeral=True
                )
        
        await interaction.response.send_modal(ProfileModal())
    
    @app_commands.command(name="badges", description="Ver badges de um utilizador")
    @app_commands.describe(utilizador="Utilizador para ver badges (opcional)")
    async def view_badges(self, interaction: discord.Interaction, utilizador: Optional[discord.Member] = None):
        """Ver todas as badges de um utilizador"""
        target = utilizador or interaction.user
        user_id = str(target.id)
        guild_id = str(interaction.guild.id)
        
        if not self.db:
            await interaction.response.send_message("❌ Database não disponível!", ephemeral=True)
            return
        
        badges = await self.db.get_user_badges(user_id, guild_id)
        
        if not badges:
            await interaction.response.send_message(
                f"{'Tu não tens' if target == interaction.user else f'{target.display_name} não tem'} badges ainda!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"🏅 Badges de {target.display_name}",
            description=f"Total: {len(badges)} badge(s)",
            color=discord.Color.gold()
        )
        
        embed.set_thumbnail(url=target.display_avatar.url)
        
        for badge in badges:
            date = datetime.fromisoformat(badge["earned_at"]).strftime("%d/%m/%Y")
            embed.add_field(
                name=f"{badge['emoji']} {badge['name']}",
                value=f"{badge['description']}\n*Obtida em: {date}*",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    """Função para carregar o cog"""
    await bot.add_cog(SocialCog(bot))

