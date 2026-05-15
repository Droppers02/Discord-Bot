"""
Sistema de Tickets Profissional para Discord Bot
Simples, rápido e funcional
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import asyncio
import random

from utils.embeds import EmbedBuilder
from utils.logger import bot_logger
from utils.database import get_database


class TicketCategorySelect(discord.ui.Select):
    """Dropdown para seleção de categoria do ticket"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Suporte Técnico",
                value="technical",
                description="Problemas técnicos com o bot ou servidor",
                emoji="🔧"
            ),
            discord.SelectOption(
                label="Dúvida Geral",
                value="general",
                description="Questões sobre funcionamento ou regras",
                emoji="❓"
            ),
            discord.SelectOption(
                label="Reportar Utilizador",
                value="report",
                description="Reportar comportamento inadequado",
                emoji="⚠️"
            ),
            discord.SelectOption(
                label="Sugestão",
                value="suggestion",
                description="Sugerir melhorias para o servidor",
                emoji="💡"
            ),
            discord.SelectOption(
                label="Outros Assuntos",
                value="other",
                description="Outros tipos de suporte",
                emoji="📝"
            )
        ]
        
        super().__init__(
            placeholder="🎫 Seleciona uma categoria para criar um ticket...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_category_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Callback quando categoria é selecionada"""
        # Responder IMEDIATAMENTE
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Criar ticket
            await self._create_ticket(interaction, self.values[0])
        except Exception as e:
            bot_logger.error(f"Erro no callback do ticket: {e}")
            await interaction.followup.send(
                "❌ Ocorreu um erro ao processar o teu pedido. Tenta novamente!",
                ephemeral=True
            )
    
    async def _create_ticket(self, interaction: discord.Interaction, category: str):
        """Cria novo ticket"""
        try:
            # Obter configuração do bot
            bot = interaction.client
            config = bot.config
            
            if not config.ticket_category_id:
                await interaction.followup.send(
                    "❌ **Configuração Inválida**\n\n"
                    "A categoria de tickets não está configurada.\n"
                    "Contacta um administrador!",
                    ephemeral=True
                )
                return
            
            ticket_category = interaction.guild.get_channel(config.ticket_category_id)
            
            if not ticket_category:
                await interaction.followup.send(
                    "❌ **Categoria Não Encontrada**\n\n"
                    "A categoria de tickets não existe no servidor.\n"
                    "Contacta um administrador!",
                    ephemeral=True
                )
                return
            
            # Verificar se o utilizador já tem um ticket aberto
            for channel in ticket_category.text_channels:
                if channel.permissions_for(interaction.user).read_messages:
                    # Verificar se o utilizador está nas permissões do canal
                    overwrites = channel.overwrites
                    if interaction.user in overwrites:
                        await interaction.followup.send(
                            f"❌ **Já tens um ticket aberto!**\n\n"
                            f"Fecha o teu ticket atual antes de criar outro: {channel.mention}\n"
                            f"Usa o botão 🔒 para fechar.",
                            ephemeral=True
                        )
                        return
            
            # Configurações das categorias
            categories = {
                "technical": {
                    "name": "Suporte Técnico",
                    "emoji": "🔧",
                    "color": discord.Color.blue(),
                    "description": "**Problema técnico reportado**\n\nDescreve detalhadamente o problema que estás a enfrentar.",
                    "tips": "• Explica o que aconteceu\n• Menciona passos para reproduzir\n• Anexa screenshots se possível\n• Indica quando começou"
                },
                "general": {
                    "name": "Dúvida Geral",
                    "emoji": "❓",
                    "color": discord.Color.green(),
                    "description": "**Dúvida registada**\n\nFaz a tua pergunta de forma clara.",
                    "tips": "• Sê específico na pergunta\n• Fornece contexto se necessário\n• Verifica se a dúvida já foi respondida"
                },
                "report": {
                    "name": "Report",
                    "emoji": "⚠️",
                    "color": discord.Color.red(),
                    "description": "**Report submetido**\n\nFornece todas as informações sobre o incidente.",
                    "tips": "• Menciona o utilizador reportado\n• Descreve o que aconteceu\n• Fornece provas (prints, links)\n• Reports falsos resultam em punição"
                },
                "suggestion": {
                    "name": "Sugestão",
                    "emoji": "💡",
                    "color": discord.Color.gold(),
                    "description": "**Sugestão recebida**\n\nPartilha a tua ideia connosco!",
                    "tips": "• Explica a tua sugestão claramente\n• Justifica os benefícios\n• Sê construtivo"
                },
                "other": {
                    "name": "Outros",
                    "emoji": "📝",
                    "color": discord.Color.purple(),
                    "description": "**Ticket criado**\n\nDescreve o motivo do teu contacto.",
                    "tips": "• Explica o assunto claramente\n• Fornece detalhes relevantes\n• Aguarda resposta da equipa"
                }
            }
            
            cat_info = categories.get(category, categories["other"])
            
            # Obter configuração do bot
            bot = interaction.client
            config = bot.config
            
            if not config.ticket_category_id:
                await interaction.followup.send(
                    "❌ **Configuração Inválida**\n\n"
                    "A categoria de tickets não está configurada.\n"
                    "Contacta um administrador!",
                    ephemeral=True
                )
                return
            
            ticket_category = interaction.guild.get_channel(config.ticket_category_id)
            
            if not ticket_category:
                await interaction.followup.send(
                    "❌ **Categoria Não Encontrada**\n\n"
                    "A categoria de tickets não existe no servidor.\n"
                    "Contacta um administrador!",
                    ephemeral=True
                )
                return
            
            # Gerar ID sequencial persistido
            cog = interaction.client.get_cog('Tickets')
            ticket_id = await cog.get_next_ticket_id()
            
            # Criar canal SEM overwrites (mais rápido)
            username = interaction.user.name.lower().replace(" ", "-")
            ticket_channel = await ticket_category.create_text_channel(
                name=f"🎫┃{username}-{ticket_id:04d}",
                topic=f"Ticket de {interaction.user.name} | {cat_info['name']}"
            )

            await cog.db.create_ticket_record(
                ticket_id=ticket_id,
                guild_id=str(interaction.guild.id),
                channel_id=str(ticket_channel.id),
                user_id=str(interaction.user.id)
            )
            
            # Configurar permissões DEPOIS
            await ticket_channel.set_permissions(
                interaction.guild.default_role,
                read_messages=False
            )
            await ticket_channel.set_permissions(
                interaction.user,
                read_messages=True,
                send_messages=True,
                attach_files=True,
                embed_links=True
            )
            await ticket_channel.set_permissions(
                interaction.guild.me,
                read_messages=True,
                send_messages=True,
                manage_channels=True,
                manage_permissions=True
            )
            
            # Adicionar staff se configurado
            if config.mod_role_id:
                mod_role = interaction.guild.get_role(config.mod_role_id)
                if mod_role:
                    await ticket_channel.set_permissions(
                        mod_role,
                        read_messages=True,
                        send_messages=True,
                        attach_files=True,
                        embed_links=True
                    )
            
            # Confirmar criação ao utilizador ANTES de enviar embed
            await interaction.followup.send(
                f"✅ **Ticket Criado!**\n\n"
                f"O teu ticket foi criado: {ticket_channel.mention}\n"
                f"A equipa responderá em breve.",
                ephemeral=True
            )
            
            # Embed de boas-vindas no ticket
            welcome_embed = discord.Embed(
                title=f"{cat_info['emoji']} {cat_info['name']} - Ticket #{ticket_id}",
                description=cat_info['description'],
                color=cat_info['color'],
                timestamp=datetime.now()
            )
            
            welcome_embed.add_field(
                name="👤 Utilizador",
                value=interaction.user.mention,
                inline=True
            )
            welcome_embed.add_field(
                name="📋 Categoria",
                value=cat_info['name'],
                inline=True
            )
            welcome_embed.add_field(
                name="🆔 Ticket ID",
                value=f"`{ticket_id}`",
                inline=True
            )
            welcome_embed.add_field(
                name="💡 Dicas",
                value=cat_info['tips'],
                inline=False
            )
            
            welcome_embed.set_footer(
                text="Usa o botão abaixo para fechar o ticket",
                icon_url=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            # View com botão de fechar
            control_view = TicketControlView()
            
            # Mencionar utilizador e staff
            mention_text = interaction.user.mention
            if config.mod_role_id:
                mention_text += f" <@&{config.mod_role_id}>"
            
            await ticket_channel.send(
                content=mention_text,
                embed=welcome_embed,
                view=control_view
            )
            
            bot_logger.info(f"Ticket #{ticket_id} criado por {interaction.user} - Categoria: {cat_info['name']}")
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ **Sem Permissões**\n\n"
                "O bot não tem permissões para criar canais.\n"
                "Contacta um administrador!",
                ephemeral=True
            )
        except Exception as e:
            bot_logger.error(f"Erro ao criar ticket: {e}")
            await interaction.followup.send(
                f"❌ **Erro ao Criar Ticket**\n\n"
                f"Ocorreu um erro: `{str(e)}`\n"
                f"Tenta novamente ou contacta um administrador!",
                ephemeral=True
            )


class TicketPanelView(discord.ui.View):
    """View do painel de tickets"""
    
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect())


class TicketControlView(discord.ui.View):
    """View com controlos do ticket"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="Fechar Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="close_ticket_btn"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Fecha o ticket"""
        # Verificar se é um canal de ticket
        if not interaction.channel.name.startswith("🎫"):
            await interaction.response.send_message(
                "❌ Este comando só funciona em canais de ticket!",
                ephemeral=True
            )
            return
        
        # Verificar permissões
        bot = interaction.client
        config = bot.config
        is_staff = config.mod_role_id and interaction.guild.get_role(config.mod_role_id) in interaction.user.roles
        is_admin = interaction.user.guild_permissions.administrator
        has_permission = interaction.channel.permissions_for(interaction.user).manage_channels
        
        if not (is_staff or is_admin or has_permission):
            await interaction.response.send_message(
                "❌ Apenas o criador do ticket ou a staff pode fechá-lo!",
                ephemeral=True
            )
            return
        
        # Confirmar fechamento
        confirm_embed = discord.Embed(
            title="🔒 Fechar Ticket",
            description="Tens a certeza que queres fechar este ticket?\n\n"
                       "**⚠️ O canal será apagado permanentemente!**\n"
                       "Esta ação não pode ser desfeita.",
            color=discord.Color.orange()
        )
        
        confirm_view = discord.ui.View(timeout=30)
        
        async def confirm_close(confirm_interaction: discord.Interaction):
            if confirm_interaction.user.id != interaction.user.id:
                await confirm_interaction.response.send_message(
                    "❌ Apenas quem solicitou o fechamento pode confirmar!",
                    ephemeral=True
                )
                return
            
            await confirm_interaction.response.defer()
            
            # Embed de despedida
            goodbye_embed = discord.Embed(
                title="✅ Ticket Fechado",
                description=f"Este ticket foi fechado por {interaction.user.mention}\n\n"
                           f"**O canal será apagado em 5 segundos...**\n\n"
                           f"Obrigado por usares o nosso sistema de suporte!",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            goodbye_embed.set_footer(text="EPA BOT - Sistema de Tickets")
            
            await interaction.channel.send(embed=goodbye_embed)

            ticket_cog = interaction.client.get_cog("Tickets")
            if ticket_cog and ticket_cog.db:
                await ticket_cog.db.close_ticket_record(str(interaction.channel.id), str(interaction.user.id))
            
            # Aguardar e apagar
            await asyncio.sleep(5)
            await interaction.channel.delete(reason=f"Ticket fechado por {interaction.user}")
            
            bot_logger.info(f"Ticket {interaction.channel.name} fechado por {interaction.user}")
        
        confirm_btn = discord.ui.Button(
            label="Sim, Fechar",
            style=discord.ButtonStyle.danger,
            emoji="✅"
        )
        confirm_btn.callback = confirm_close
        
        cancel_btn = discord.ui.Button(
            label="Cancelar",
            style=discord.ButtonStyle.secondary,
            emoji="❌"
        )
        
        async def cancel_close(cancel_interaction: discord.Interaction):
            await cancel_interaction.response.send_message(
                "❎ Fechamento cancelado!",
                ephemeral=True
            )
        
        cancel_btn.callback = cancel_close
        
        confirm_view.add_item(confirm_btn)
        confirm_view.add_item(cancel_btn)
        
        await interaction.response.send_message(
            embed=confirm_embed,
            view=confirm_view,
            ephemeral=True
        )


class Tickets(commands.Cog):
    """Sistema de tickets"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = None
    
    async def cog_load(self):
        """Carrega views persistentes"""
        self.db = await get_database()
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketControlView())
        bot_logger.info("Sistema de tickets carregado")
    
    async def get_next_ticket_id(self) -> int:
        """Obtém próximo ID sequencial persistido do ticket."""
        return await self.db.get_next_ticket_id()
    
    @app_commands.command(
        name="setup_tickets",
        description="[ADMIN] Configura o painel de tickets"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_tickets(self, interaction: discord.Interaction):
        """Configura painel de tickets"""
        
        embed = discord.Embed(
            title="🎫 Sistema de Tickets - EPA BOT",
            description="**Precisas de ajuda ou suporte?**\n\n"
                       "Seleciona a categoria adequada no menu abaixo.\n"
                       "Um canal privado será criado automaticamente para ti!\n\n"
                       "━━━━━━━━━━━━━━━━━━━━━━",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📋 Categorias Disponíveis",
            value="🔧 **Suporte Técnico** - Problemas técnicos\n"
                  "❓ **Dúvida Geral** - Questões sobre o servidor\n"
                  "⚠️ **Reportar** - Reportar utilizadores\n"
                  "💡 **Sugestão** - Sugerir melhorias\n"
                  "📝 **Outros** - Outros assuntos",
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Como Funciona",
            value="1️⃣ Seleciona uma categoria\n"
                  "2️⃣ Um canal privado será criado\n"
                  "3️⃣ Descreve o teu problema/questão\n"
                  "4️⃣ A equipa responderá em breve\n"
                  "5️⃣ Usa 🔒 para fechar quando resolvido",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Regras Importantes",
            value="• Respeita sempre a equipa\n"
                  "• Fornece detalhes suficientes\n"
                  "• Não abuses do sistema\n"
                  "• Spam resultará em punição",
            inline=False
        )
        
        embed.set_footer(
            text="Sistema de Tickets | Resposta em até 24h",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        
        await interaction.response.send_message(
            "✅ Painel de tickets configurado com sucesso!",
            ephemeral=True
        )
        
        await interaction.channel.send(
            embed=embed,
            view=TicketPanelView()
        )
        
        bot_logger.info(f"Painel de tickets criado por {interaction.user}")
    
    @app_commands.command(
        name="rename",
        description="[STAFF] Renomeia o canal de ticket atual"
    )
    @app_commands.describe(
        novo_nome="Novo nome para o canal (sem emoji, será adicionado automaticamente)"
    )
    async def rename_ticket(self, interaction: discord.Interaction, novo_nome: str):
        """Renomeia um ticket"""
        # Verificar se é um canal de ticket
        if not interaction.channel.name.startswith("🎫"):
            await interaction.response.send_message(
                "❌ Este comando só funciona em canais de ticket!",
                ephemeral=True
            )
            return
        
        # Verificar permissões
        config = interaction.client.config
        is_staff = config.mod_role_id and interaction.guild.get_role(config.mod_role_id) in interaction.user.roles
        is_admin = interaction.user.guild_permissions.administrator
        
        if not (is_staff or is_admin):
            await interaction.response.send_message(
                "❌ Apenas staff ou administradores podem renomear tickets!",
                ephemeral=True
            )
            return
        
        # Validar nome
        if len(novo_nome) > 90:
            await interaction.response.send_message(
                "❌ O nome é demasiado longo! Máximo 90 caracteres.",
                ephemeral=True
            )
            return
        
        # Limpar nome (remover caracteres especiais)
        nome_limpo = "".join(c for c in novo_nome if c.isalnum() or c in (' ', '-', '_')).strip()
        nome_limpo = nome_limpo.replace(" ", "-").lower()
        
        if not nome_limpo:
            await interaction.response.send_message(
                "❌ Nome inválido! Usa apenas letras, números, espaços e hífens.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Renomear canal
            nome_antigo = interaction.channel.name
            await interaction.channel.edit(name=f"🎫┃{nome_limpo}")
            
            await interaction.followup.send(
                f"✅ **Ticket Renomeado!**\n\n"
                f"**Antes:** `{nome_antigo}`\n"
                f"**Depois:** `🎫┃{nome_limpo}`",
                ephemeral=True
            )
            
            # Notificar no canal
            embed = discord.Embed(
                title="📝 Ticket Renomeado",
                description=f"{interaction.user.mention} alterou o nome deste ticket.",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Nome Anterior", value=f"`{nome_antigo}`", inline=False)
            embed.add_field(name="Novo Nome", value=f"`🎫┃{nome_limpo}`", inline=False)
            
            await interaction.channel.send(embed=embed)
            
            bot_logger.info(f"Ticket {nome_antigo} renomeado para 🎫┃{nome_limpo} por {interaction.user}")
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Não tenho permissões para renomear este canal!",
                ephemeral=True
            )
        except Exception as e:
            bot_logger.error(f"Erro ao renomear ticket: {e}")
            await interaction.followup.send(
                f"❌ Erro ao renomear: `{str(e)}`",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Tickets(bot))
