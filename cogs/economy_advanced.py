"""
Sistema de Economia Avançado para EPA BOT
Funcionalidades: Custom Roles, Trading, Achievements, Leilões, Eventos
"""

import json
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from typing import Optional
import random

from utils.embeds import EmbedBuilder
from utils.database import get_database


class EconomyAdvanced(commands.Cog):
    """Sistema de economia avançado com features premium"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = None
        self.coin_emoji = "<:epacoin2:1407389417290727434>"
        
        # Raridades de itens com cores
        self.rarities = {
            "common": {"name": "Comum", "color": 0x95a5a6, "emoji": "⚪"},
            "uncommon": {"name": "Incomum", "color": 0x2ecc71, "emoji": "🟢"},
            "rare": {"name": "Raro", "color": 0x3498db, "emoji": "🔵"},
            "epic": {"name": "Épico", "color": 0x9b59b6, "emoji": "🟣"},
            "legendary": {"name": "Lendário", "color": 0xf39c12, "emoji": "🟠"},
            "mythic": {"name": "Mítico", "color": 0xe74c3c, "emoji": "🔴"}
        }
        
        # Achievement definitions
        self.achievement_templates = {
            "first_million": {"name": "Primeiro Milhão", "description": "Acumula 1,000,000 coins", "emoji": "💰", "reward_coins": 50000, "tier": "gold"},
            "big_spender": {"name": "Grande Gastador", "description": "Gasta 500,000 coins", "emoji": "💸", "reward_coins": 25000, "tier": "silver"},
            "lucky_seven": {"name": "Sorte 7", "description": "Ganha 7 apostas seguidas", "emoji": "🍀", "reward_coins": 10000, "tier": "bronze"},
            "collector": {"name": "Colecionador", "description": "Possui 50 itens diferentes", "emoji": "🎒", "reward_coins": 30000, "tier": "gold"},
            "trader_pro": {"name": "Trader Profissional", "description": "Completa 20 trades", "emoji": "🤝", "reward_coins": 15000, "tier": "silver"},
            "auction_master": {"name": "Mestre dos Leilões", "description": "Vence 10 leilões", "emoji": "🔨", "reward_coins": 20000, "tier": "gold"},
            "daily_warrior": {"name": "Guerreiro Diário", "description": "Streak de 30 dias", "emoji": "⚔️", "reward_coins": 40000, "tier": "gold"}
        }
    
    async def cog_load(self):
        """Carregado quando o cog é inicializado"""
        try:
            self.db = await get_database()
            await self._initialize_achievements()
        except Exception as e:
            self.bot.logger.error(f"Erro ao carregar economy_advanced: {e}")
    
    async def _initialize_achievements(self):
        """Inicializa achievements no banco de dados"""
        for achievement_id, data in self.achievement_templates.items():
            await self.db.add_achievement(
                achievement_id=achievement_id,
                name=data["name"],
                description=data["description"],
                emoji=data["emoji"],
                reward_coins=data["reward_coins"],
                reward_badge=achievement_id,
                requirement_type="manual",
                requirement_value=0,
                tier=data["tier"]
            )
    
    def get_coin_display(self, amount: int = None):
        """Retorna display formatado das coins"""
        if amount is None:
            return self.coin_emoji
        return f"{amount:,} {self.coin_emoji}"
    
    # ===== CUSTOM ROLES =====
    
    @app_commands.command(name="comprar_role", description="Compra uma custom role personalizada (50,000 coins)")
    @app_commands.describe(
        nome="Nome da role (máx 32 caracteres)",
        cor="Cor em hexadecimal (ex: #FF5733) ou nome (red, blue, green, etc.)"
    )
    async def buy_custom_role(self, interaction: discord.Interaction, nome: str, cor: str = "#7289DA"):
        """Compra e cria uma custom role"""
        await interaction.response.defer()
        
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        # Verificar se já tem custom role
        existing_role = await self.db.get_custom_role(user_id, guild_id)
        if existing_role:
            embed = discord.Embed(
                title="❌ Já Tens Uma Custom Role",
                description=f"Já tens a role **{existing_role['role_name']}**!\nUsa `/editar_role` para modificá-la ou `/remover_role` para removê-la.",
                color=0xff4444
            )
            return await interaction.followup.send(embed=embed)
        
        # Verificar saldo (assumindo que existe get_balance em economy.py)
        from cogs.economy import SimpleEconomy
        economy_cog = self.bot.get_cog("SimpleEconomy")
        if not economy_cog:
            return await interaction.followup.send("❌ Sistema de economia não disponível!")
        
        balance = economy_cog.get_balance(user_id)
        price = 50000
        
        if balance < price:
            embed = discord.Embed(
                title="💸 EPA Coins Insuficientes",
                description=f"Precisas de **{self.get_coin_display(price)}** para comprar uma Custom Role!\nTens apenas **{self.get_coin_display(balance)}**.",
                color=0xff4444
            )
            return await interaction.followup.send(embed=embed)
        
        # Validar nome
        if len(nome) > 32:
            return await interaction.followup.send("❌ Nome da role deve ter no máximo 32 caracteres!")
        
        # Converter cor
        try:
            # Cores predefinidas
            color_names = {
                "red": 0xff0000, "blue": 0x0000ff, "green": 0x00ff00,
                "yellow": 0xffff00, "purple": 0x800080, "pink": 0xffc0cb,
                "orange": 0xffa500, "black": 0x000000, "white": 0xffffff,
                "cyan": 0x00ffff, "magenta": 0xff00ff, "gold": 0xffd700
            }
            
            if cor.lower() in color_names:
                color_value = discord.Color(color_names[cor.lower()])
            else:
                # Hex color
                color_hex = cor.replace("#", "")
                color_value = discord.Color(int(color_hex, 16))
        except:
            return await interaction.followup.send("❌ Cor inválida! Use formato hex (#FF5733) ou nome (red, blue, etc.)")
        
        try:
            # Criar role no Discord
            role = await interaction.guild.create_role(
                name=nome,
                color=color_value,
                reason=f"Custom Role comprada por {interaction.user}"
            )
            
            # Posicionar role logo abaixo do bot
            bot_role = interaction.guild.me.top_role
            positions = {role: bot_role.position - 1}
            await interaction.guild.edit_role_positions(positions=positions)
            
            # Adicionar role ao utilizador
            await interaction.user.add_roles(role)
            
            # Guardar na base de dados
            await self.db.create_custom_role(
                user_id=user_id,
                guild_id=guild_id,
                role_id=str(role.id),
                role_name=nome,
                role_color=str(color_value)
            )
            
            # Deduzir coins
            economy_cog.remove_money(user_id, price)
            
            embed = discord.Embed(
                title="✅ Custom Role Criada!",
                description=f"**{nome}** foi criada e atribuída!",
                color=color_value
            )
            embed.add_field(name="💰 Custo", value=self.get_coin_display(price), inline=True)
            embed.add_field(name="💳 Saldo Restante", value=self.get_coin_display(economy_cog.get_balance(user_id)), inline=True)
            embed.add_field(name="🎨 Cor", value=str(color_value), inline=True)
            embed.set_footer(text="Usa /editar_role para mudar nome ou cor!")
            
            await interaction.followup.send(embed=embed)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ Não tenho permissões para criar roles!")
        except Exception as e:
            await interaction.followup.send(f"❌ Erro ao criar role: {e}")
    
    @app_commands.command(name="editar_role", description="Edita a tua custom role (grátis)")
    @app_commands.describe(
        novo_nome="Novo nome (deixa vazio para manter)",
        nova_cor="Nova cor (deixa vazio para manter)"
    )
    async def edit_custom_role(self, interaction: discord.Interaction, novo_nome: Optional[str] = None, nova_cor: Optional[str] = None):
        """Edita custom role existente"""
        await interaction.response.defer()
        
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        # Verificar se tem custom role
        custom_role_data = await self.db.get_custom_role(user_id, guild_id)
        if not custom_role_data:
            return await interaction.followup.send("❌ Não tens uma Custom Role! Compra uma com `/comprar_role`")
        
        # Obter role do Discord
        role = interaction.guild.get_role(int(custom_role_data['role_id']))
        if not role:
            await self.db.delete_custom_role(user_id, guild_id)
            return await interaction.followup.send("❌ A tua Custom Role foi removida. Compra uma nova com `/comprar_role`")
        
        # Atualizar nome
        if novo_nome:
            if len(novo_nome) > 32:
                return await interaction.followup.send("❌ Nome deve ter no máximo 32 caracteres!")
            await role.edit(name=novo_nome)
        
        # Atualizar cor
        new_color = None
        if nova_cor:
            try:
                color_names = {
                    "red": 0xff0000, "blue": 0x0000ff, "green": 0x00ff00,
                    "yellow": 0xffff00, "purple": 0x800080, "pink": 0xffc0cb,
                    "orange": 0xffa500, "black": 0x000000, "white": 0xffffff,
                    "cyan": 0x00ffff, "magenta": 0xff00ff, "gold": 0xffd700
                }
                
                if nova_cor.lower() in color_names:
                    new_color = discord.Color(color_names[nova_cor.lower()])
                else:
                    color_hex = nova_cor.replace("#", "")
                    new_color = discord.Color(int(color_hex, 16))
                
                await role.edit(color=new_color)
            except:
                return await interaction.followup.send("❌ Cor inválida!")
        
        # Atualizar base de dados
        await self.db.create_custom_role(
            user_id=user_id,
            guild_id=guild_id,
            role_id=str(role.id),
            role_name=novo_nome or role.name,
            role_color=str(new_color or role.color)
        )
        
        embed = discord.Embed(
            title="✅ Custom Role Atualizada!",
            description=f"**{role.name}** foi atualizada!",
            color=new_color or role.color
        )
        if novo_nome:
            embed.add_field(name="📝 Novo Nome", value=novo_nome, inline=True)
        if nova_cor:
            embed.add_field(name="🎨 Nova Cor", value=str(new_color), inline=True)
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="remover_role", description="Remove a tua custom role permanentemente")
    async def remove_custom_role(self, interaction: discord.Interaction):
        """Remove custom role"""
        await interaction.response.defer()
        
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        # Verificar se tem custom role
        custom_role_data = await self.db.get_custom_role(user_id, guild_id)
        if not custom_role_data:
            return await interaction.followup.send("❌ Não tens uma Custom Role!")
        
        # Obter role do Discord
        role = interaction.guild.get_role(int(custom_role_data['role_id']))
        if role:
            try:
                await role.delete(reason=f"Custom role removida por {interaction.user}")
            except:
                pass
        
        # Remover da base de dados
        await self.db.delete_custom_role(user_id, guild_id)
        
        embed = discord.Embed(
            title="✅ Custom Role Removida",
            description="A tua Custom Role foi removida permanentemente.",
            color=0x00ff88
        )
        embed.set_footer(text="Podes comprar uma nova com /comprar_role")
        
        await interaction.followup.send(embed=embed)
    
    # ===== TRADING SYSTEM =====
    
    @app_commands.command(name="propor_trade", description="Propõe uma troca com outro utilizador")
    @app_commands.describe(
        utilizador="Utilizador com quem queres trocar",
        tuas_coins="Quantidade de coins que ofereces",
        pedes_coins="Quantidade de coins que pedes"
    )
    async def propose_trade(self, interaction: discord.Interaction, utilizador: discord.Member, tuas_coins: int = 0, pedes_coins: int = 0):
        """Propor trade entre utilizadores"""
        await interaction.response.defer()
        
        if utilizador.bot:
            return await interaction.followup.send("❌ Não podes fazer trades com bots!")
        
        if utilizador == interaction.user:
            return await interaction.followup.send("❌ Não podes fazer trade contigo mesmo!")
        
        if tuas_coins < 0 or pedes_coins < 0:
            return await interaction.followup.send("❌ Valores devem ser positivos!")
        
        if tuas_coins == 0 and pedes_coins == 0:
            return await interaction.followup.send("❌ Trade deve incluir pelo menos algo!")
        
        # Verificar saldo do sender
        from cogs.economy import SimpleEconomy
        economy_cog = self.bot.get_cog("SimpleEconomy")
        sender_balance = economy_cog.get_balance(str(interaction.user.id))
        
        if sender_balance < tuas_coins:
            return await interaction.followup.send(f"❌ Não tens {self.get_coin_display(tuas_coins)}!")
        
        # Criar trade
        trade_id = await self.db.create_trade(
            guild_id=str(interaction.guild.id),
            sender_id=str(interaction.user.id),
            receiver_id=str(utilizador.id),
            sender_coins=tuas_coins,
            sender_items="",
            receiver_coins=pedes_coins,
            receiver_items=""
        )
        
        # Criar embed
        embed = discord.Embed(
            title="🤝 Proposta de Trade",
            description=f"{interaction.user.mention} propõe um trade com {utilizador.mention}",
            color=0x3498db
        )
        
        embed.add_field(
            name=f"📤 {interaction.user.display_name} oferece",
            value=self.get_coin_display(tuas_coins) if tuas_coins > 0 else "Nada",
            inline=True
        )
        
        embed.add_field(
            name=f"📥 {utilizador.display_name} oferece",
            value=self.get_coin_display(pedes_coins) if pedes_coins > 0 else "Nada",
            inline=True
        )
        
        embed.set_footer(text=f"Trade ID: {trade_id} • Expira em 5 minutos")
        
        view = TradeView(self, trade_id, interaction.user, utilizador, economy_cog)
        await interaction.followup.send(embed=embed, view=view)
    
    @app_commands.command(name="trades_pendentes", description="Ver trades pendentes")
    async def pending_trades(self, interaction: discord.Interaction):
        """Ver trades pendentes"""
        await interaction.response.defer()
        
        trades = await self.db.get_pending_trades(str(interaction.user.id), str(interaction.guild.id))
        
        if not trades:
            return await interaction.followup.send("📭 Não tens trades pendentes!")
        
        embed = discord.Embed(
            title="🤝 Trades Pendentes",
            color=0x3498db
        )
        
        for trade in trades[:10]:  # Mostrar até 10
            sender = await self.bot.fetch_user(int(trade['sender_id']))
            receiver = await self.bot.fetch_user(int(trade['receiver_id']))
            
            if trade['sender_id'] == str(interaction.user.id):
                desc = f"Com **{receiver.name}**: Tu ofereces {self.get_coin_display(trade['sender_coins'])} por {self.get_coin_display(trade['receiver_coins'])}"
            else:
                desc = f"De **{sender.name}**: Oferece {self.get_coin_display(trade['sender_coins'])} por {self.get_coin_display(trade['receiver_coins'])}"
            
            embed.add_field(
                name=f"Trade #{trade['trade_id']}",
                value=desc,
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
    
    # ===== ACHIEVEMENTS =====
    
    @app_commands.command(name="conquistas", description="Ver as tuas conquistas/achievements")
    async def achievements(self, interaction: discord.Interaction, utilizador: Optional[discord.Member] = None):
        """Ver achievements desbloqueados"""
        await interaction.response.defer()
        
        target = utilizador or interaction.user
        achievements = await self.db.get_user_achievements(str(target.id), str(interaction.guild.id))
        
        embed = discord.Embed(
            title=f"🏆 Conquistas de {target.display_name}",
            color=0xf39c12
        )
        
        if not achievements:
            embed.description = "Nenhuma conquista desbloqueada ainda!"
        else:
            for ach in achievements[:15]:  # Máximo 15
                status = "✅ Reclamada" if ach['claimed'] else "🎁 Disponível"
                embed.add_field(
                    name=f"{ach['emoji']} {ach['name']} ({ach['tier'].upper()})",
                    value=f"{ach['description']}\n{status}",
                    inline=False
                )
        
        total_achievements = len(self.achievement_templates)
        unlocked = len(achievements)
        embed.set_footer(text=f"{unlocked}/{total_achievements} Conquistas Desbloqueadas")
        
        await interaction.followup.send(embed=embed)
    
    # ===== AUCTION SYSTEM =====
    
    @app_commands.command(name="criar_leilao", description="Cria um leilão de um item raro")
    @app_commands.describe(
        item_nome="Nome do item",
        descricao="Descrição do item",
        lance_inicial="Lance inicial (mínimo)",
        compra_ja="Preço de compra imediata (opcional)",
        duracao="Duração em horas (padrão: 24h)"
    )
    async def create_auction(self, interaction: discord.Interaction, item_nome: str, descricao: str, lance_inicial: int, compra_ja: Optional[int] = None, duracao: int = 24):
        """Criar leilão"""
        await interaction.response.defer()
        
        if lance_inicial < 1000:
            return await interaction.followup.send("❌ Lance inicial deve ser no mínimo 1,000 coins!")
        
        if duracao < 1 or duracao > 168:  # Máximo 7 dias
            return await interaction.followup.send("❌ Duração deve ser entre 1 e 168 horas!")
        
        if compra_ja and compra_ja <= lance_inicial:
            return await interaction.followup.send("❌ Preço de compra imediata deve ser maior que o lance inicial!")
        
        # Calcular fim
        ends_at = (datetime.now() + timedelta(hours=duracao)).isoformat()
        
        # Criar leilão
        auction_id = await self.db.create_auction(
            guild_id=str(interaction.guild.id),
            seller_id=str(interaction.user.id),
            item_name=item_nome,
            item_description=descricao,
            item_emoji="📦",
            item_rarity="rare",
            starting_bid=lance_inicial,
            buyout_price=compra_ja or 0,
            ends_at=ends_at
        )
        
        embed = discord.Embed(
            title="🔨 Leilão Criado!",
            description=f"**{item_nome}**\n{descricao}",
            color=0x3498db
        )
        
        embed.add_field(name="💰 Lance Inicial", value=self.get_coin_display(lance_inicial), inline=True)
        if compra_ja:
            embed.add_field(name="⚡ Compra Já", value=self.get_coin_display(compra_ja), inline=True)
        embed.add_field(name="⏱️ Termina em", value=f"{duracao}h", inline=True)
        embed.set_footer(text=f"Leilão ID: {auction_id} • Usa /dar_lance para licitar")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="leiloes", description="Ver leilões ativos")
    async def view_auctions(self, interaction: discord.Interaction):
        """Ver leilões ativos"""
        await interaction.response.defer()
        
        auctions = await self.db.get_active_auctions(str(interaction.guild.id))
        
        if not auctions:
            return await interaction.followup.send("📭 Nenhum leilão ativo no momento!")
        
        embed = discord.Embed(
            title="🔨 Leilões Ativos",
            color=0x3498db
        )
        
        for auction in auctions[:10]:
            rarity_info = self.rarities.get(auction['item_rarity'], self.rarities['common'])
            current_bid = auction['current_bid'] or auction['starting_bid']
            
            embed.add_field(
                name=f"{rarity_info['emoji']} {auction['item_name']} (ID: {auction['auction_id']})",
                value=f"Lance Atual: {self.get_coin_display(current_bid)}\nTermina: <t:{int(datetime.fromisoformat(auction['ends_at']).timestamp())}:R>",
                inline=False
            )
        
        embed.set_footer(text="Usa /dar_lance <id> <valor> para licitar")
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="dar_lance", description="Dá um lance num leilão")
    @app_commands.describe(
        leilao_id="ID do leilão",
        valor="Valor do lance"
    )
    async def place_bid(self, interaction: discord.Interaction, leilao_id: int, valor: int):
        """Dar lance em leilão"""
        await interaction.response.defer()
        
        # Obter leilão
        auction = await self.db.get_auction(leilao_id)
        
        if not auction:
            return await interaction.followup.send("❌ Leilão não encontrado!")
        
        if auction['status'] != 'active':
            return await interaction.followup.send("❌ Este leilão já terminou!")
        
        if auction['seller_id'] == str(interaction.user.id):
            return await interaction.followup.send("❌ Não podes licitar no teu próprio leilão!")
        
        # Verificar se acabou
        if datetime.fromisoformat(auction['ends_at']) < datetime.now():
            await self.db.complete_auction(leilao_id, "expired")
            return await interaction.followup.send("❌ Este leilão já expirou!")
        
        # Verificar lance mínimo
        current_bid = auction['current_bid'] or auction['starting_bid']
        min_bid = current_bid + max(100, int(current_bid * 0.05))  # 5% ou 100, o que for maior
        
        if valor < min_bid:
            return await interaction.followup.send(f"❌ Lance mínimo: {self.get_coin_display(min_bid)}")
        
        # Verificar saldo
        from cogs.economy import SimpleEconomy
        economy_cog = self.bot.get_cog("SimpleEconomy")
        balance = economy_cog.get_balance(str(interaction.user.id))
        
        if balance < valor:
            return await interaction.followup.send(f"❌ Não tens {self.get_coin_display(valor)}!")
        
        # Registar lance
        await self.db.place_bid(leilao_id, str(interaction.user.id), valor)
        
        embed = discord.Embed(
            title="✅ Lance Registado!",
            description=f"Deste um lance de **{self.get_coin_display(valor)}** no leilão **{auction['item_name']}**!",
            color=0x00ff88
        )
        
        embed.add_field(name="💰 Teu Lance", value=self.get_coin_display(valor), inline=True)
        embed.add_field(name="⏱️ Termina", value=f"<t:{int(datetime.fromisoformat(auction['ends_at']).timestamp())}:R>", inline=True)
        
        await interaction.followup.send(embed=embed)
    
    # ===== EVENTOS ESPECIAIS =====
    
    @app_commands.command(name="criar_evento", description="[ADMIN] Criar evento especial com bónus")
    @app_commands.describe(
        tipo="Tipo de evento",
        duracao="Duração em horas",
        multiplicador="Multiplicador de coins (ex: 2.0 = dobro)"
    )
    @app_commands.choices(tipo=[
        app_commands.Choice(name="🎉 Happy Hour (coins dobrados)", value="happy_hour"),
        app_commands.Choice(name="🍀 Super Sorte (apostas com bónus)", value="lucky_time"),
        app_commands.Choice(name="💰 Chuva de Ouro (todos ganham)", value="gold_rain"),
        app_commands.Choice(name="🎁 Dailies Especiais", value="special_daily")
    ])
    async def create_event(self, interaction: discord.Interaction, tipo: str, duracao: int, multiplicador: float = 2.0):
        """Criar evento especial (admin only)"""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Apenas administradores!", ephemeral=True)
        
        await interaction.response.defer()
        
        event_names = {
            "happy_hour": "🎉 Happy Hour",
            "lucky_time": "🍀 Super Sorte",
            "gold_rain": "💰 Chuva de Ouro",
            "special_daily": "🎁 Dailies Especiais"
        }
        
        descriptions = {
            "happy_hour": f"Todas as recompensas multiplicadas por {multiplicador}x!",
            "lucky_time": f"Chances de vitória aumentadas e prémios {multiplicador}x maiores!",
            "gold_rain": "Todos os membros ativos ganham coins de bónus!",
            "special_daily": f"Daily recompensas {multiplicador}x maiores!"
        }
        
        ends_at = (datetime.now() + timedelta(hours=duracao)).isoformat()
        
        event_id = await self.db.create_event(
            guild_id=str(interaction.guild.id),
            event_type=tipo,
            event_name=event_names[tipo],
            multiplier=multiplicador,
            bonus_coins=0,
            description=descriptions[tipo],
            started_by=str(interaction.user.id),
            ends_at=ends_at
        )
        
        embed = discord.Embed(
            title=f"🎊 {event_names[tipo]} ATIVADO!",
            description=descriptions[tipo],
            color=0xf39c12
        )
        
        embed.add_field(name="⏱️ Duração", value=f"{duracao} horas", inline=True)
        embed.add_field(name="📈 Multiplicador", value=f"{multiplicador}x", inline=True)
        embed.add_field(name="👑 Iniciado por", value=interaction.user.mention, inline=True)
        
        timestamp = int(datetime.fromisoformat(ends_at).timestamp())
        embed.set_footer(text=f"Termina: {timestamp} • Event ID: {event_id}")
        
        await interaction.followup.send(f"@everyone", embed=embed)
    
    @app_commands.command(name="eventos_ativos", description="Ver eventos especiais ativos")
    async def active_events(self, interaction: discord.Interaction):
        """Ver eventos ativos"""
        await interaction.response.defer()
        
        events = await self.db.get_active_events(str(interaction.guild.id))
        
        if not events:
            return await interaction.followup.send("📭 Nenhum evento ativo no momento!")
        
        embed = discord.Embed(
            title="🎊 Eventos Ativos",
            color=0xf39c12
        )
        
        for event in events:
            embed.add_field(
                name=event['event_name'],
                value=f"{event['description']}\nMultiplicador: **{event['multiplier']}x**\nTermina: <t:{int(datetime.fromisoformat(event['ends_at']).timestamp())}:R>",
                inline=False
            )
        
        await interaction.followup.send(embed=embed)


class TradeView(discord.ui.View):
    """View para aceitar/recusar trades"""
    
    def __init__(self, cog, trade_id, sender, receiver, economy_cog):
        super().__init__(timeout=300)  # 5 minutos
        self.cog = cog
        self.trade_id = trade_id
        self.sender = sender
        self.receiver = receiver
        self.economy_cog = economy_cog
    
    @discord.ui.button(label="✅ Aceitar", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.receiver:
            return await interaction.response.send_message("❌ Apenas o destinatário pode aceitar!", ephemeral=True)
        
        await interaction.response.defer()
        
        # Obter trade
        trade = await self.cog.db.get_trade(self.trade_id)
        
        if not trade or trade['status'] != 'pending':
            return await interaction.followup.send("❌ Trade já não está disponível!")
        
        # Verificar saldos
        sender_balance = self.economy_cog.get_balance(trade['sender_id'])
        receiver_balance = self.economy_cog.get_balance(trade['receiver_id'])
        
        if sender_balance < trade['sender_offer_coins']:
            await self.cog.db.update_trade_status(self.trade_id, "cancelled")
            return await interaction.followup.send("❌ O remetente não tem coins suficientes!")
        
        if receiver_balance < trade['receiver_offer_coins']:
            await self.cog.db.update_trade_status(self.trade_id, "cancelled")
            return await interaction.followup.send("❌ Não tens coins suficientes!")
        
        # Executar trade
        if trade['sender_offer_coins'] > 0:
            self.economy_cog.remove_money(trade['sender_id'], trade['sender_offer_coins'])
            self.economy_cog.add_money(trade['receiver_id'], trade['sender_offer_coins'])
        
        if trade['receiver_offer_coins'] > 0:
            self.economy_cog.remove_money(trade['receiver_id'], trade['receiver_offer_coins'])
            self.economy_cog.add_money(trade['sender_id'], trade['receiver_offer_coins'])
        
        # Atualizar status
        await self.cog.db.update_trade_status(self.trade_id, "completed")
        
        embed = discord.Embed(
            title="✅ Trade Completado!",
            description=f"Trade entre {self.sender.mention} e {self.receiver.mention} foi completado com sucesso!",
            color=0x00ff88
        )
        
        await interaction.followup.send(embed=embed)
        
        # Desativar botões
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
    
    @discord.ui.button(label="❌ Recusar", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.receiver:
            return await interaction.response.send_message("❌ Apenas o destinatário pode recusar!", ephemeral=True)
        
        await self.cog.db.update_trade_status(self.trade_id, "declined")
        
        embed = discord.Embed(
            title="❌ Trade Recusado",
            description=f"{self.receiver.mention} recusou o trade.",
            color=0xff4444
        )
        
        await interaction.response.edit_message(embed=embed, view=None)


async def setup(bot):
    await bot.add_cog(EconomyAdvanced(bot))
