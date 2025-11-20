"""
Sistema de Base de Dados para EPA BOT
Migração de JSON para SQLite com suporte assíncrono
"""

import aiosqlite
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
import logging


class Database:
    """Classe principal para gestão da base de dados"""
    
    def __init__(self, db_path: str = "data/epa_bot.db"):
        self.db_path = db_path
        self.logger = logging.getLogger("EPA BOT.Database")
        
    async def init_db(self):
        """Inicializa a base de dados e cria as tabelas"""
        async with aiosqlite.connect(self.db_path) as db:
            # Tabela de utilizadores (economia)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    balance INTEGER DEFAULT 2500,
                    last_daily TEXT,
                    daily_streak INTEGER DEFAULT 0,
                    total_earned INTEGER DEFAULT 2500,
                    total_donated INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela de items do utilizador
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    item_data TEXT,
                    acquired_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Tabela de XP e níveis (social) com reputação integrada
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_levels (
                    user_id TEXT,
                    guild_id TEXT,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    reputation INTEGER DEFAULT 0,
                    messages_sent INTEGER DEFAULT 0,
                    last_message_at REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            
            # Tabela de reputação
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_reputation (
                    user_id TEXT,
                    guild_id TEXT,
                    reputation INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            
            # Tabela de configurações de boas-vindas
            await db.execute("""
                CREATE TABLE IF NOT EXISTS welcome_config (
                    guild_id TEXT PRIMARY KEY,
                    channel_id TEXT,
                    message TEXT,
                    enabled INTEGER DEFAULT 1,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela de tickets
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    channel_id TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    status TEXT DEFAULT 'open',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    closed_at TEXT,
                    closed_by TEXT
                )
            """)
            
            # Tabela de transações (auditoria)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user_id TEXT,
                    to_user_id TEXT,
                    amount INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela de logs de moderação
            await db.execute("""
                CREATE TABLE IF NOT EXISTS moderation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    moderator_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT,
                    duration INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela de avisos (warnings)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    moderator_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela de estatísticas de jogos
            await db.execute("""
                CREATE TABLE IF NOT EXISTS game_stats (
                    user_id TEXT NOT NULL,
                    game_type TEXT NOT NULL,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    draws INTEGER DEFAULT 0,
                    total_games INTEGER DEFAULT 0,
                    total_earnings INTEGER DEFAULT 0,
                    best_streak INTEGER DEFAULT 0,
                    current_streak INTEGER DEFAULT 0,
                    last_played TEXT,
                    PRIMARY KEY (user_id, game_type)
                )
            """)
            
            # Tabela de torneios
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tournaments (
                    tournament_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_type TEXT NOT NULL,
                    creator_id TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    prize_pool INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'open',
                    max_players INTEGER DEFAULT 8,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela de participantes em torneios
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tournament_participants (
                    tournament_id INTEGER,
                    user_id TEXT NOT NULL,
                    score INTEGER DEFAULT 0,
                    rank INTEGER,
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id)
                )
            """)
            
            # ===== SISTEMA SOCIAL EXPANDIDO =====
            
            # Tabela de badges
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_badges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    badge_id TEXT NOT NULL,
                    badge_name TEXT NOT NULL,
                    badge_emoji TEXT,
                    badge_description TEXT,
                    earned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, guild_id, badge_id)
                )
            """)
            
            # Tabela de perfis customizáveis
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT,
                    guild_id TEXT,
                    bio TEXT,
                    color TEXT DEFAULT '#5865F2',
                    banner_url TEXT,
                    favorite_game TEXT,
                    birthday TEXT,
                    pronouns TEXT,
                    custom_field_1_name TEXT,
                    custom_field_1_value TEXT,
                    custom_field_2_name TEXT,
                    custom_field_2_value TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            
            # Tabela de casamentos
            await db.execute("""
                CREATE TABLE IF NOT EXISTS marriages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    user1_id TEXT NOT NULL,
                    user2_id TEXT NOT NULL,
                    married_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    ring_tier INTEGER DEFAULT 1,
                    anniversary_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    UNIQUE(guild_id, user1_id, user2_id)
                )
            """)
            
            # Tabela de histórico de atividade
            await db.execute("""
                CREATE TABLE IF NOT EXISTS activity_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    activity_data TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela de streaks e recompensas
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_streaks (
                    user_id TEXT,
                    guild_id TEXT,
                    streak_type TEXT,
                    current_streak INTEGER DEFAULT 0,
                    best_streak INTEGER DEFAULT 0,
                    last_activity TEXT,
                    total_rewards INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id, streak_type)
                )
            """)
            
            # Criar índices para melhor performance
            await db.execute("CREATE INDEX IF NOT EXISTS idx_user_items_user ON user_items(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_transactions_from ON transactions(from_user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_transactions_to ON transactions(to_user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_mod_logs_guild ON moderation_logs(guild_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_warnings_user ON warnings(user_id, guild_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_game_stats_user ON game_stats(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_game_stats_type ON game_stats(game_type)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_tournaments_guild ON tournaments(guild_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_badges_user ON user_badges(user_id, guild_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_history(user_id, guild_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_marriages_users ON marriages(user1_id, user2_id)")
            
            await db.commit()
            self.logger.info("✅ Base de dados inicializada com sucesso")
    
    async def migrate_from_json(self):
        """Migra dados dos ficheiros JSON existentes para SQLite"""
        self.logger.info("🔄 Iniciando migração de JSON para SQLite...")
        
        # Migrar economia
        economy_file = Path("data/economy_simple.json")
        if economy_file.exists():
            with open(economy_file, 'r', encoding='utf-8') as f:
                economy_data = json.load(f)
            
            async with aiosqlite.connect(self.db_path) as db:
                for user_id, data in economy_data.get("users", {}).items():
                    await db.execute("""
                        INSERT OR REPLACE INTO users 
                        (user_id, balance, last_daily, daily_streak, total_earned, total_donated)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        user_id,
                        data.get("balance", 2500),
                        data.get("last_daily"),
                        data.get("daily_streak", 0),
                        data.get("total_earned", 2500),
                        data.get("total_donated", 0)
                    ))
                    
                    # Migrar items
                    for item in data.get("items", []):
                        await db.execute("""
                            INSERT INTO user_items (user_id, item_name, item_data)
                            VALUES (?, ?, ?)
                        """, (user_id, str(item), json.dumps(item)))
                
                await db.commit()
                self.logger.info(f"✅ Migrados {len(economy_data.get('users', {}))} utilizadores da economia")
        
        # Migrar dados sociais
        social_file = Path("data/social_data.json")
        if social_file.exists():
            with open(social_file, 'r', encoding='utf-8') as f:
                social_data = json.load(f)
            
            async with aiosqlite.connect(self.db_path) as db:
                for guild_id, users in social_data.get("guilds", {}).items():
                    for user_id, data in users.items():
                        await db.execute("""
                            INSERT OR REPLACE INTO user_levels 
                            (user_id, guild_id, xp, level, messages_sent, last_message_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            user_id,
                            guild_id,
                            data.get("xp", 0),
                            data.get("level", 1),
                            data.get("messages_sent", 0),
                            data.get("last_message", 0)
                        ))
                        
                        await db.execute("""
                            INSERT OR REPLACE INTO user_reputation 
                            (user_id, guild_id, reputation)
                            VALUES (?, ?, ?)
                        """, (user_id, guild_id, data.get("reputation", 0)))
                
                await db.commit()
                total_users = sum(len(users) for users in social_data.get("guilds", {}).values())
                self.logger.info(f"✅ Migrados {total_users} utilizadores dos dados sociais")
        
        # Migrar configurações de boas-vindas
        welcome_file = Path("data/welcome_config.json")
        if welcome_file.exists():
            with open(welcome_file, 'r', encoding='utf-8') as f:
                welcome_data = json.load(f)
            
            async with aiosqlite.connect(self.db_path) as db:
                for guild_id, config in welcome_data.get("guilds", {}).items():
                    await db.execute("""
                        INSERT OR REPLACE INTO welcome_config 
                        (guild_id, channel_id, message, enabled)
                        VALUES (?, ?, ?, ?)
                    """, (
                        guild_id,
                        config.get("channel_id"),
                        config.get("message"),
                        1 if config.get("enabled", True) else 0
                    ))
                
                await db.commit()
                self.logger.info(f"✅ Migradas {len(welcome_data.get('guilds', {}))} configurações de boas-vindas")
        
        self.logger.info("🎉 Migração concluída com sucesso!")
    
    # --- Métodos de Economia ---
    
    async def get_user_balance(self, user_id: str) -> int:
        """Obtém o saldo de um utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT balance FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 2500
    
    async def add_money(self, user_id: str, amount: int, transaction_type: str = "earn", description: str = None):
        """Adiciona dinheiro a um utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (user_id, balance, total_earned)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    balance = balance + ?,
                    total_earned = total_earned + ?,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, 2500 + amount, amount, amount, amount))
            
            # Registar transação
            await db.execute("""
                INSERT INTO transactions (to_user_id, amount, transaction_type, description)
                VALUES (?, ?, ?, ?)
            """, (user_id, amount, transaction_type, description))
            
            await db.commit()
    
    async def remove_money(self, user_id: str, amount: int, transaction_type: str = "spend", description: str = None):
        """Remove dinheiro de um utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users 
                SET balance = balance - ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (amount, user_id))
            
            # Registar transação
            await db.execute("""
                INSERT INTO transactions (from_user_id, amount, transaction_type, description)
                VALUES (?, ?, ?, ?)
            """, (user_id, amount, transaction_type, description))
            
            await db.commit()
    
    async def transfer_money(self, from_user: str, to_user: str, amount: int):
        """Transfere dinheiro entre utilizadores"""
        async with aiosqlite.connect(self.db_path) as db:
            # Remover do remetente
            await db.execute("""
                UPDATE users 
                SET balance = balance - ?, total_donated = total_donated + ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (amount, amount, from_user))
            
            # Adicionar ao destinatário
            await db.execute("""
                INSERT INTO users (user_id, balance, total_earned)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    balance = balance + ?,
                    total_earned = total_earned + ?,
                    updated_at = CURRENT_TIMESTAMP
            """, (to_user, 2500 + amount, amount, amount, amount))
            
            # Registar transação
            await db.execute("""
                INSERT INTO transactions (from_user_id, to_user_id, amount, transaction_type, description)
                VALUES (?, ?, ?, 'transfer', 'Transferência entre utilizadores')
            """, (from_user, to_user, amount))
            
            await db.commit()
    
    async def get_top_richest(self, limit: int = 10) -> List[Dict]:
        """Obtém os utilizadores mais ricos"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT user_id, balance FROM users 
                ORDER BY balance DESC LIMIT ?
            """, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [{"user_id": row[0], "balance": row[1]} for row in rows]
    
    # --- Métodos de XP/Níveis ---
    
    async def add_xp(self, user_id: str, guild_id: str, xp: int) -> Dict:
        """Adiciona XP a um utilizador e calcula nível"""
        async with aiosqlite.connect(self.db_path) as db:
            # Obter XP atual
            async with db.execute("""
                SELECT xp, level FROM user_levels 
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id)) as cursor:
                row = await cursor.fetchone()
                current_xp = row[0] if row else 0
                current_level = row[1] if row else 1
            
            new_xp = current_xp + xp
            new_level = int((new_xp / 100) ** 0.5) + 1
            leveled_up = new_level > current_level
            
            # Atualizar XP e nível
            await db.execute("""
                INSERT INTO user_levels (user_id, guild_id, xp, level, messages_sent)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET
                    xp = ?,
                    level = ?,
                    messages_sent = messages_sent + 1,
                    last_message_at = ?
            """, (user_id, guild_id, new_xp, new_level, new_xp, new_level, datetime.now().timestamp()))
            
            await db.commit()
            
            return {
                "xp": new_xp,
                "level": new_level,
                "leveled_up": leveled_up,
                "old_level": current_level
            }
    
    async def get_user_level(self, user_id: str, guild_id: str) -> Dict:
        """Obtém informações de nível de um utilizador incluindo reputação"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT xp, level, messages_sent, reputation FROM user_levels 
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {"xp": row[0], "level": row[1], "messages": row[2], "reputation": row[3]}
                return {"xp": 0, "level": 1, "messages": 0, "reputation": 0}
    
    async def update_user_level(self, user_id: str, guild_id: str, xp: int, level: int, increment_messages: bool = True):
        """Atualiza XP e nível de um utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            if increment_messages:
                await db.execute("""
                    INSERT INTO user_levels (user_id, guild_id, xp, level, messages_sent, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?)
                    ON CONFLICT(user_id, guild_id) 
                    DO UPDATE SET xp = ?, level = ?, messages_sent = messages_sent + 1, updated_at = ?
                """, (user_id, guild_id, xp, level, datetime.utcnow().isoformat(), xp, level, datetime.utcnow().isoformat()))
            else:
                await db.execute("""
                    INSERT INTO user_levels (user_id, guild_id, xp, level, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, guild_id) 
                    DO UPDATE SET xp = ?, level = ?, updated_at = ?
                """, (user_id, guild_id, xp, level, datetime.utcnow().isoformat(), xp, level, datetime.utcnow().isoformat()))
            await db.commit()
    
    async def get_leaderboard(self, guild_id: str, limit: int = 10) -> List[Dict]:
        """Obtém o leaderboard de XP"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT user_id, xp, level FROM user_levels 
                WHERE guild_id = ?
                ORDER BY xp DESC LIMIT ?
            """, (guild_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [{"user_id": row[0], "xp": row[1], "level": row[2]} for row in rows]
    
    # --- Métodos de Moderação ---
    
    async def add_warning(self, guild_id: str, user_id: str, moderator_id: str, reason: str):
        """Adiciona um aviso a um utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO warnings (guild_id, user_id, moderator_id, reason)
                VALUES (?, ?, ?, ?)
            """, (guild_id, user_id, moderator_id, reason))
            
            await db.execute("""
                INSERT INTO moderation_logs (guild_id, user_id, moderator_id, action, reason)
                VALUES (?, ?, ?, 'warn', ?)
            """, (guild_id, user_id, moderator_id, reason))
            
            await db.commit()
    
    async def get_warnings(self, guild_id: str, user_id: str) -> List[Dict]:
        """Obtém os avisos de um utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT id, moderator_id, reason, created_at FROM warnings 
                WHERE guild_id = ? AND user_id = ? AND active = 1
                ORDER BY created_at DESC
            """, (guild_id, user_id)) as cursor:
                rows = await cursor.fetchall()
                return [{
                    "id": row[0],
                    "moderator_id": row[1],
                    "reason": row[2],
                    "created_at": row[3]
                } for row in rows]
    
    async def log_moderation(self, guild_id: str, user_id: str, moderator_id: str, 
                            action: str, reason: str = None, duration: int = None):
        """Registra uma ação de moderação"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO moderation_logs (guild_id, user_id, moderator_id, action, reason, duration)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, user_id, moderator_id, action, reason, duration))
            await db.commit()
    
    # --- Métodos de Estatísticas de Jogos ---
    
    async def update_game_stats(self, user_id: str, game_type: str, result: str, earnings: int = 0):
        """Atualiza estatísticas de jogo de um utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            # Verificar se já existe
            async with db.execute(
                "SELECT * FROM game_stats WHERE user_id = ? AND game_type = ?",
                (user_id, game_type)
            ) as cursor:
                existing = await cursor.fetchone()
            
            if existing:
                wins = existing[2] + (1 if result == "win" else 0)
                losses = existing[3] + (1 if result == "loss" else 0)
                draws = existing[4] + (1 if result == "draw" else 0)
                total_games = existing[5] + 1
                total_earnings = existing[6] + earnings
                current_streak = existing[8] + 1 if result == "win" else 0
                best_streak = max(existing[7], current_streak)
                
                await db.execute("""
                    UPDATE game_stats 
                    SET wins = ?, losses = ?, draws = ?, total_games = ?,
                        total_earnings = ?, best_streak = ?, current_streak = ?,
                        last_played = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND game_type = ?
                """, (wins, losses, draws, total_games, total_earnings, 
                      best_streak, current_streak, user_id, game_type))
            else:
                wins = 1 if result == "win" else 0
                losses = 1 if result == "loss" else 0
                draws = 1 if result == "draw" else 0
                current_streak = 1 if result == "win" else 0
                
                await db.execute("""
                    INSERT INTO game_stats 
                    (user_id, game_type, wins, losses, draws, total_games, 
                     total_earnings, best_streak, current_streak, last_played)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, game_type, wins, losses, draws, earnings, 
                      current_streak, current_streak))
            
            await db.commit()
    
    async def get_game_stats(self, user_id: str, game_type: str = None):
        """Obtém estatísticas de jogo de um utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            if game_type:
                async with db.execute(
                    "SELECT * FROM game_stats WHERE user_id = ? AND game_type = ?",
                    (user_id, game_type)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {
                            "wins": row[2], "losses": row[3], "draws": row[4],
                            "total_games": row[5], "total_earnings": row[6],
                            "best_streak": row[7], "current_streak": row[8],
                            "last_played": row[9]
                        }
            else:
                async with db.execute(
                    "SELECT * FROM game_stats WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    stats = {}
                    for row in rows:
                        stats[row[1]] = {
                            "wins": row[2], "losses": row[3], "draws": row[4],
                            "total_games": row[5], "total_earnings": row[6],
                            "best_streak": row[7], "current_streak": row[8],
                            "last_played": row[9]
                        }
                    return stats
        return {}
    
    async def get_game_leaderboard(self, game_type: str, limit: int = 10):
        """Obtém leaderboard de um jogo específico"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT user_id, wins, total_games, total_earnings, best_streak
                FROM game_stats
                WHERE game_type = ?
                ORDER BY wins DESC, total_earnings DESC
                LIMIT ?
            """, (game_type, limit)) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "user_id": row[0],
                        "wins": row[1],
                        "total_games": row[2],
                        "total_earnings": row[3],
                        "best_streak": row[4]
                    }
                    for row in rows
                ]
    
    # --- Métodos do Sistema Social Expandido ---
    
    async def add_badge(self, user_id: str, guild_id: str, badge_id: str, 
                       badge_name: str, badge_emoji: str = None, badge_description: str = None):
        """Adiciona badge a um utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT OR IGNORE INTO user_badges 
                    (user_id, guild_id, badge_id, badge_name, badge_emoji, badge_description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, guild_id, badge_id, badge_name, badge_emoji, badge_description))
                await db.commit()
                return True
            except:
                return False
    
    async def get_user_badges(self, user_id: str, guild_id: str):
        """Obtém badges de um utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT badge_id, badge_name, badge_emoji, badge_description, earned_at
                FROM user_badges
                WHERE user_id = ? AND guild_id = ?
                ORDER BY earned_at DESC
            """, (user_id, guild_id)) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "name": row[1],
                        "emoji": row[2],
                        "description": row[3],
                        "earned_at": row[4]
                    }
                    for row in rows
                ]
    
    async def update_profile(self, user_id: str, guild_id: str, **kwargs):
        """Atualiza perfil de utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            # Construir query dinamicamente
            fields = []
            values = []
            for key, value in kwargs.items():
                fields.append(f"{key} = ?")
                values.append(value)
            
            if not fields:
                return
            
            values.extend([user_id, guild_id])
            
            await db.execute(f"""
                INSERT INTO user_profiles (user_id, guild_id, {', '.join(kwargs.keys())})
                VALUES (?, ?, {', '.join(['?'] * len(kwargs))})
                ON CONFLICT(user_id, guild_id) DO UPDATE SET
                {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP
            """, values)
            await db.commit()
    
    async def get_profile(self, user_id: str, guild_id: str):
        """Obtém perfil de utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT bio, color, banner_url, favorite_game, birthday, pronouns,
                       custom_field_1_name, custom_field_1_value,
                       custom_field_2_name, custom_field_2_value
                FROM user_profiles
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "bio": row[0],
                        "color": row[1],
                        "banner_url": row[2],
                        "favorite_game": row[3],
                        "birthday": row[4],
                        "pronouns": row[5],
                        "custom_field_1": {"name": row[6], "value": row[7]},
                        "custom_field_2": {"name": row[8], "value": row[9]}
                    }
                return None
    
    async def create_marriage(self, guild_id: str, user1_id: str, user2_id: str):
        """Cria casamento entre dois utilizadores"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT INTO marriages (guild_id, user1_id, user2_id)
                    VALUES (?, ?, ?)
                """, (guild_id, user1_id, user2_id))
                await db.commit()
                return True
            except:
                return False
    
    async def get_marriage(self, guild_id: str, user_id: str):
        """Obtém casamento de um utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT user1_id, user2_id, married_at, ring_tier, anniversary_count
                FROM marriages
                WHERE guild_id = ? AND (user1_id = ? OR user2_id = ?) AND status = 'active'
            """, (guild_id, user_id, user_id)) as cursor:
                row = await cursor.fetchone()
                if row:
                    partner_id = row[1] if row[0] == user_id else row[0]
                    return {
                        "partner_id": partner_id,
                        "married_at": row[2],
                        "ring_tier": row[3],
                        "anniversary_count": row[4]
                    }
                return None
    
    async def divorce(self, guild_id: str, user_id: str):
        """Remove casamento"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE marriages SET status = 'divorced'
                WHERE guild_id = ? AND (user1_id = ? OR user2_id = ?) AND status = 'active'
            """, (guild_id, user_id, user_id))
            await db.commit()
    
    async def log_activity(self, user_id: str, guild_id: str, activity_type: str, activity_data: str = None):
        """Registra atividade de utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO activity_history (user_id, guild_id, activity_type, activity_data)
                VALUES (?, ?, ?, ?)
            """, (user_id, guild_id, activity_type, activity_data))
            await db.commit()
    
    async def get_activity_history(self, user_id: str, guild_id: str, limit: int = 50):
        """Obtém histórico de atividade"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT activity_type, activity_data, timestamp
                FROM activity_history
                WHERE user_id = ? AND guild_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, guild_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "type": row[0],
                        "data": row[1],
                        "timestamp": row[2]
                    }
                    for row in rows
                ]
    
    async def update_streak(self, user_id: str, guild_id: str, streak_type: str, increment: bool = True):
        """Atualiza streak de utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT current_streak, best_streak FROM user_streaks
                WHERE user_id = ? AND guild_id = ? AND streak_type = ?
            """, (user_id, guild_id, streak_type)) as cursor:
                row = await cursor.fetchone()
            
            if row:
                current = row[0] + 1 if increment else 0
                best = max(row[1], current)
                
                await db.execute("""
                    UPDATE user_streaks
                    SET current_streak = ?, best_streak = ?, last_activity = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND guild_id = ? AND streak_type = ?
                """, (current, best, user_id, guild_id, streak_type))
            else:
                await db.execute("""
                    INSERT INTO user_streaks (user_id, guild_id, streak_type, current_streak, best_streak)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, guild_id, streak_type, 1 if increment else 0, 1 if increment else 0))
            
            await db.commit()
    
    async def get_streak(self, user_id: str, guild_id: str, streak_type: str):
        """Obtém streak de utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT current_streak, best_streak, total_rewards
                FROM user_streaks
                WHERE user_id = ? AND guild_id = ? AND streak_type = ?
            """, (user_id, guild_id, streak_type)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "current": row[0],
                        "best": row[1],
                        "total_rewards": row[2]
                    }
                return {"current": 0, "best": 0, "total_rewards": 0}


# Instância global
db_instance = None

async def get_database() -> Database:
    """Obtém a instância da base de dados"""
    global db_instance
    if db_instance is None:
        db_instance = Database()
        await db_instance.init_db()
    return db_instance

