"""Sistema de base de dados PostgreSQL para o EPA BOT."""

import os
import aiosqlite
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any

from utils.postgres_schema import ALTER_STATEMENTS, SCHEMA_STATEMENTS


class DatabaseOperation:
    """Operação lazy para compatibilidade com `await db.execute(...)` e `async with db.execute(...)`."""

    def __init__(self, database: "Database", query: str, params: tuple[Any, ...]):
        self.database = database
        self.query = query
        self.params = params
        self.cursor: Optional[aiosqlite.Cursor] = None

    async def _execute(self) -> aiosqlite.Cursor:
        connection = await self.database._ensure_connection()
        self.cursor = await connection.execute(self.query, self.params)
        return self.cursor

    def __await__(self):
        return self._execute().__await__()

    async def __aenter__(self) -> aiosqlite.Cursor:
        if self.cursor is None:
            await self._execute()
        return self.cursor

    async def __aexit__(self, exc_type, exc, tb):
        if self.cursor is not None:
            await self.cursor.close()
            self.cursor = None


class Database:
    """Classe principal para gestão da base de dados"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = (
            db_path
            or os.getenv("DATABASE_URL")
            or os.getenv("NEON_DATABASE_URL")
            or os.getenv("SQL_DATABASE_URL", "")
        )
        self.logger = logging.getLogger("EPA BOT.Database")
        self.connection: Optional[aiosqlite.Connection] = None

    async def _ensure_connection(self) -> aiosqlite.Connection:
        """Garante uma ligação persistente para queries raw usadas pelos cogs."""
        if not self.db_path:
            raise ValueError("DATABASE_URL não configurado")
        if self.connection is None:
            self.connection = await aiosqlite.connect(self.db_path)
        return self.connection

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> DatabaseOperation:
        """Compatibilidade com chamadas raw usadas por alguns cogs."""
        return DatabaseOperation(self, query, params)

    async def commit(self):
        """Commit na ligação persistente, quando existir."""
        connection = await self._ensure_connection()
        await connection.commit()

    async def close(self):
        """Fecha a ligação persistente do wrapper."""
        if self.connection is not None:
            await self.connection.close()
            self.connection = None
        
    async def init_db(self):
        """Inicializa a base de dados e cria as tabelas"""
        async with aiosqlite.connect(self.db_path) as db:
            for statement in SCHEMA_STATEMENTS:
                await db.execute(statement)
            for statement in ALTER_STATEMENTS:
                await db.execute(statement)
            await db.commit()
            self.logger.info("✅ Base de dados PostgreSQL inicializada com sucesso")

        await self._ensure_connection()

    @staticmethod
    def _timestamp_to_iso(value: Optional[float]) -> Optional[str]:
        if value is None:
            return None
        return datetime.utcfromtimestamp(value).isoformat()

    @staticmethod
    def _iso_to_timestamp(value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).timestamp()
        except ValueError:
            return None

    async def load_welcome_configs(self) -> Dict[str, Dict[str, Any]]:
        """Carrega a configuração de boas-vindas/despedidas para todas as guilds."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT guild_id, channel_id, message, enabled, config_json FROM welcome_config"
            ) as cursor:
                rows = await cursor.fetchall()

        configs: Dict[str, Dict[str, Any]] = {"guilds": {}}
        for guild_id, channel_id, message, enabled, config_json in rows:
            if config_json:
                try:
                    payload = json.loads(config_json)
                except json.JSONDecodeError:
                    payload = None
                if isinstance(payload, dict):
                    configs["guilds"][guild_id] = payload
                    continue

            legacy_payload: Dict[str, Any] = {}
            if channel_id:
                try:
                    legacy_payload["welcome_channel"] = int(channel_id)
                except (TypeError, ValueError):
                    legacy_payload["welcome_channel"] = channel_id
            if message:
                legacy_payload["welcome_message"] = message
            legacy_payload["welcome_enabled"] = bool(enabled)
            configs["guilds"][guild_id] = legacy_payload

        return configs

    async def save_welcome_config(self, guild_id: str, config: Dict[str, Any]):
        """Persiste a configuração de boas-vindas/despedidas de uma guild."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO welcome_config (guild_id, channel_id, message, enabled, config_json, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(guild_id) DO UPDATE SET
                    channel_id = EXCLUDED.channel_id,
                    message = EXCLUDED.message,
                    enabled = EXCLUDED.enabled,
                    config_json = EXCLUDED.config_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    guild_id,
                    str(config.get("welcome_channel")) if config.get("welcome_channel") else None,
                    config.get("welcome_message"),
                    1 if config.get("welcome_enabled", False) else 0,
                    json.dumps(config, ensure_ascii=False),
                ),
            )
            await db.commit()

    async def load_reminders(self) -> List[Dict[str, Any]]:
        """Carrega lembretes persistidos."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT id, user_id, channel_id, message, remind_at, created_at, recurring, interval_seconds
                FROM reminders
                ORDER BY remind_at ASC
                """
            ) as cursor:
                rows = await cursor.fetchall()

        reminders: List[Dict[str, Any]] = []
        for row in rows:
            remind_at = self._iso_to_timestamp(row[4])
            created_at = self._iso_to_timestamp(row[5])
            reminders.append({
                "id": row[0],
                "user_id": row[1],
                "channel_id": row[2],
                "message": row[3],
                "time": remind_at if remind_at is not None else datetime.utcnow().timestamp(),
                "created_at": created_at if created_at is not None else datetime.utcnow().timestamp(),
                "recurring": bool(row[6]),
                "interval": row[7] or 0,
            })

        return reminders

    async def save_reminder(self, reminder: Dict[str, Any]) -> int:
        """Insere ou atualiza um lembrete persistido."""
        async with aiosqlite.connect(self.db_path) as db:
            if reminder.get("id"):
                await db.execute(
                    """
                    UPDATE reminders
                    SET user_id = ?, channel_id = ?, message = ?, remind_at = ?, created_at = ?, recurring = ?, interval_seconds = ?
                    WHERE id = ?
                    """,
                    (
                        reminder["user_id"],
                        reminder["channel_id"],
                        reminder["message"],
                        self._timestamp_to_iso(reminder["time"]),
                        self._timestamp_to_iso(reminder.get("created_at")),
                        1 if reminder.get("recurring") else 0,
                        reminder.get("interval", 0),
                        reminder["id"],
                    ),
                )
                await db.commit()
                return reminder["id"]

            cursor = await db.execute(
                """
                INSERT INTO reminders (user_id, channel_id, message, remind_at, created_at, recurring, interval_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reminder["user_id"],
                    reminder["channel_id"],
                    reminder["message"],
                    self._timestamp_to_iso(reminder["time"]),
                    self._timestamp_to_iso(reminder.get("created_at")),
                    1 if reminder.get("recurring") else 0,
                    reminder.get("interval", 0),
                ),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def delete_reminder(self, reminder_id: int):
        """Remove um lembrete persistido."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            await db.commit()

    async def load_scheduled_announcements(self) -> List[Dict[str, Any]]:
        """Carrega anúncios agendados persistidos."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT id, channel_id, message, scheduled_for, created_by, created_at, embed_json
                FROM scheduled_announcements
                ORDER BY scheduled_for ASC
                """
            ) as cursor:
                rows = await cursor.fetchall()

        announcements: List[Dict[str, Any]] = []
        for row in rows:
            scheduled_for = self._iso_to_timestamp(row[3])
            created_at = self._iso_to_timestamp(row[5])
            try:
                embed_payload = json.loads(row[6]) if row[6] else None
            except json.JSONDecodeError:
                embed_payload = None

            announcements.append({
                "id": row[0],
                "channel_id": row[1],
                "message": row[2],
                "time": scheduled_for if scheduled_for is not None else datetime.utcnow().timestamp(),
                "created_by": row[4],
                "created_at": created_at if created_at is not None else datetime.utcnow().timestamp(),
                "embed": embed_payload,
            })

        return announcements

    async def save_scheduled_announcement(self, announcement: Dict[str, Any]) -> int:
        """Insere ou atualiza um anúncio agendado persistido."""
        async with aiosqlite.connect(self.db_path) as db:
            if announcement.get("id"):
                await db.execute(
                    """
                    UPDATE scheduled_announcements
                    SET channel_id = ?, message = ?, scheduled_for = ?, created_by = ?, created_at = ?, embed_json = ?
                    WHERE id = ?
                    """,
                    (
                        announcement["channel_id"],
                        announcement.get("message"),
                        self._timestamp_to_iso(announcement["time"]),
                        announcement.get("created_by"),
                        self._timestamp_to_iso(announcement.get("created_at")),
                        json.dumps(announcement.get("embed"), ensure_ascii=False) if announcement.get("embed") else None,
                        announcement["id"],
                    ),
                )
                await db.commit()
                return announcement["id"]

            cursor = await db.execute(
                """
                INSERT INTO scheduled_announcements (channel_id, message, scheduled_for, created_by, created_at, embed_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    announcement["channel_id"],
                    announcement.get("message"),
                    self._timestamp_to_iso(announcement["time"]),
                    announcement.get("created_by"),
                    self._timestamp_to_iso(announcement.get("created_at")),
                    json.dumps(announcement.get("embed"), ensure_ascii=False) if announcement.get("embed") else None,
                ),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def delete_scheduled_announcement(self, announcement_id: int):
        """Remove um anúncio agendado persistido."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM scheduled_announcements WHERE id = ?", (announcement_id,))
            await db.commit()
    
    # --- Métodos de Economia ---
    
    async def get_user_balance(self, user_id: str) -> int:
        """Obtém o saldo de um utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT balance FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 2500

    async def get_economy_user(self, user_id: str) -> Dict[str, Any]:
        """Obtém todos os dados económicos persistidos de um utilizador."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT balance, last_daily, last_work, last_crime, daily_streak,
                       total_earned, total_donated, lottery_week, lottery_tickets,
                       lottery_wins, total_lottery_won
                FROM users
                WHERE user_id = ?
                """,
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()

            async with db.execute(
                "SELECT item_data FROM user_items WHERE user_id = ? ORDER BY acquired_at ASC",
                (user_id,)
            ) as cursor:
                item_rows = await cursor.fetchall()

        items: List[Dict[str, Any]] = []
        for item_row in item_rows:
            try:
                items.append(json.loads(item_row[0]))
            except (TypeError, json.JSONDecodeError):
                continue

        if not row:
            return {
                "balance": 2500,
                "last_daily": None,
                "last_work": None,
                "last_crime": None,
                "daily_streak": 0,
                "total_earned": 2500,
                "total_donated": 0,
                "lottery_week": None,
                "lottery_tickets": 0,
                "lottery_wins": 0,
                "total_lottery_won": 0,
                "items": items,
            }

        return {
            "balance": row[0],
            "last_daily": row[1],
            "last_work": row[2],
            "last_crime": row[3],
            "daily_streak": row[4],
            "total_earned": row[5],
            "total_donated": row[6],
            "lottery_week": row[7],
            "lottery_tickets": row[8],
            "lottery_wins": row[9],
            "total_lottery_won": row[10],
            "items": items,
        }

    async def get_all_economy_users(self) -> Dict[str, Dict[str, Any]]:
        """Obtém todos os utilizadores económicos para rankings e manutenção."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT user_id, balance, last_daily, last_work, last_crime, daily_streak,
                       total_earned, total_donated, lottery_week, lottery_tickets,
                       lottery_wins, total_lottery_won
                FROM users
                """
            ) as cursor:
                rows = await cursor.fetchall()

            async with db.execute(
                "SELECT user_id, item_data FROM user_items ORDER BY acquired_at ASC"
            ) as cursor:
                item_rows = await cursor.fetchall()

        users: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            users[row[0]] = {
                "balance": row[1],
                "last_daily": row[2],
                "last_work": row[3],
                "last_crime": row[4],
                "daily_streak": row[5],
                "total_earned": row[6],
                "total_donated": row[7],
                "lottery_week": row[8],
                "lottery_tickets": row[9],
                "lottery_wins": row[10],
                "total_lottery_won": row[11],
                "items": [],
            }

        for user_id, item_data in item_rows:
            users.setdefault(user_id, {
                "balance": 2500,
                "last_daily": None,
                "last_work": None,
                "last_crime": None,
                "daily_streak": 0,
                "total_earned": 2500,
                "total_donated": 0,
                "lottery_week": None,
                "lottery_tickets": 0,
                "lottery_wins": 0,
                "total_lottery_won": 0,
                "items": [],
            })
            try:
                users[user_id]["items"].append(json.loads(item_data))
            except (TypeError, json.JSONDecodeError):
                continue

        return users

    async def upsert_economy_user(self, user_id: str, data: Dict[str, Any]):
        """Persiste todos os dados económicos de um utilizador."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO users (
                    user_id, balance, last_daily, last_work, last_crime, daily_streak,
                    total_earned, total_donated, lottery_week, lottery_tickets,
                    lottery_wins, total_lottery_won
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    balance = excluded.balance,
                    last_daily = excluded.last_daily,
                    last_work = excluded.last_work,
                    last_crime = excluded.last_crime,
                    daily_streak = excluded.daily_streak,
                    total_earned = excluded.total_earned,
                    total_donated = excluded.total_donated,
                    lottery_week = excluded.lottery_week,
                    lottery_tickets = excluded.lottery_tickets,
                    lottery_wins = excluded.lottery_wins,
                    total_lottery_won = excluded.total_lottery_won,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    data.get("balance", 2500),
                    data.get("last_daily"),
                    data.get("last_work"),
                    data.get("last_crime"),
                    data.get("daily_streak", 0),
                    data.get("total_earned", 2500),
                    data.get("total_donated", 0),
                    data.get("lottery_week"),
                    data.get("lottery_tickets", 0),
                    data.get("lottery_wins", 0),
                    data.get("total_lottery_won", 0),
                )
            )

            await db.execute("DELETE FROM user_items WHERE user_id = ?", (user_id,))
            for item in data.get("items", []):
                await db.execute(
                    "INSERT INTO user_items (user_id, item_name, item_data) VALUES (?, ?, ?)",
                    (user_id, str(item.get("name", "item")), json.dumps(item, ensure_ascii=False))
                )

            await db.commit()

    async def reset_economy_user(self, user_id: str):
        """Apaga dados económicos persistidos de um utilizador."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM user_items WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            await db.commit()
    
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
    
    async def remove_money(self, user_id: str, amount: int, transaction_type: str = "spend", description: str = None) -> bool:
        """Remove dinheiro de um utilizador sem permitir saldo negativo."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                UPDATE users 
                SET balance = balance - ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND balance >= ?
            """, (amount, user_id, amount))

            if cursor.rowcount == 0:
                await db.rollback()
                return False
            
            # Registar transação
            await db.execute("""
                INSERT INTO transactions (from_user_id, amount, transaction_type, description)
                VALUES (?, ?, ?, ?)
            """, (user_id, amount, transaction_type, description))
            
            await db.commit()
            return True
    
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

    async def update_user_xp(self, user_id: str, guild_id: str, xp_gain: int):
        """Incrementa XP e recalcula o nível sem incrementar mensagens."""
        current = await self.get_user_level(user_id, guild_id)
        new_xp = current["xp"] + xp_gain
        new_level = int((new_xp / 100) ** 0.5) + 1
        await self.update_user_level(user_id, guild_id, new_xp, new_level, increment_messages=False)
    
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
            timestamp = datetime.utcnow().isoformat()
            if increment_messages:
                await db.execute("""
                    INSERT INTO user_levels (user_id, guild_id, xp, level, messages_sent, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?)
                    ON CONFLICT(user_id, guild_id) 
                    DO UPDATE SET xp = ?, level = ?, messages_sent = messages_sent + 1, updated_at = ?
                """, (user_id, guild_id, xp, level, timestamp, xp, level, timestamp))
            else:
                await db.execute("""
                    INSERT INTO user_levels (user_id, guild_id, xp, level, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, guild_id) 
                    DO UPDATE SET xp = ?, level = ?, updated_at = ?
                """, (user_id, guild_id, xp, level, timestamp, xp, level, timestamp))
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

    async def get_game_leaderboard(self, limit: int = 10):
        """Obtém ranking agregado de vitórias por utilizador."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT user_id, COALESCE(SUM(wins), 0) AS total_wins
                FROM game_stats
                GROUP BY user_id
                HAVING total_wins > 0
                ORDER BY total_wins DESC
                LIMIT ?
                """,
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [{"user_id": row[0], "wins": row[1]} for row in rows]
    
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
            except aiosqlite.IntegrityError:
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
            except aiosqlite.IntegrityError:
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
    
    # ===== MÉTODOS DE ECONOMIA AVANÇADA =====
    
    async def create_custom_role(self, user_id: str, guild_id: str, role_id: str, role_name: str, role_color: str, expires_at: str = None):
        """Cria uma custom role para o utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO custom_roles (user_id, guild_id, role_id, role_name, role_color, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET
                    role_id = EXCLUDED.role_id,
                    role_name = EXCLUDED.role_name,
                    role_color = EXCLUDED.role_color,
                    expires_at = EXCLUDED.expires_at
            """, (user_id, guild_id, role_id, role_name, role_color, expires_at))
            await db.commit()
    
    async def get_custom_role(self, user_id: str, guild_id: str):
        """Obtém custom role do utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT role_id, role_name, role_color, created_at, expires_at
                FROM custom_roles
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "role_id": row[0],
                        "role_name": row[1],
                        "role_color": row[2],
                        "created_at": row[3],
                        "expires_at": row[4]
                    }
                return None
    
    async def delete_custom_role(self, user_id: str, guild_id: str):
        """Remove custom role do utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                DELETE FROM custom_roles
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))
            await db.commit()
    
    async def create_trade(self, guild_id: str, sender_id: str, receiver_id: str, sender_coins: int, sender_items: str, receiver_coins: int, receiver_items: str):
        """Cria uma proposta de trade"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO trades (guild_id, sender_id, receiver_id, sender_offer_coins, sender_offer_items, receiver_offer_coins, receiver_offer_items)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (guild_id, sender_id, receiver_id, sender_coins, sender_items, receiver_coins, receiver_items))
            await db.commit()
            return cursor.lastrowid

    async def get_next_ticket_id(self) -> int:
        """Obtém o próximo ID global de ticket persistido."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COALESCE(MAX(ticket_id), 0) + 1 FROM tickets") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 1

    async def create_ticket_record(self, ticket_id: int, guild_id: str, channel_id: str, user_id: str):
        """Regista um ticket aberto."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO tickets (ticket_id, guild_id, channel_id, user_id, status)
                VALUES (?, ?, ?, ?, 'open')
                """,
                (ticket_id, guild_id, channel_id, user_id)
            )
            await db.commit()

    async def close_ticket_record(self, channel_id: str, closed_by: str):
        """Marca um ticket como fechado."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE tickets
                SET status = 'closed', closed_at = CURRENT_TIMESTAMP, closed_by = ?
                WHERE channel_id = ? AND status = 'open'
                """,
                (closed_by, channel_id)
            )
            await db.commit()
    
    async def get_trade(self, trade_id: int):
        """Obtém detalhes de um trade"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT trade_id, guild_id, sender_id, receiver_id, sender_offer_coins, sender_offer_items,
                       receiver_offer_coins, receiver_offer_items, status, created_at, completed_at
                FROM trades
                WHERE trade_id = ?
            """, (trade_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "trade_id": row[0],
                        "guild_id": row[1],
                        "sender_id": row[2],
                        "receiver_id": row[3],
                        "sender_offer_coins": row[4],
                        "sender_offer_items": row[5],
                        "receiver_offer_coins": row[6],
                        "receiver_offer_items": row[7],
                        "status": row[8],
                        "created_at": row[9],
                        "completed_at": row[10]
                    }
                return None
    
    async def update_trade_status(self, trade_id: int, status: str):
        """Atualiza status de um trade"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE trades
                SET status = ?, completed_at = CURRENT_TIMESTAMP
                WHERE trade_id = ?
            """, (status, trade_id))
            await db.commit()
    
    async def get_pending_trades(self, user_id: str, guild_id: str):
        """Obtém trades pendentes para um utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT trade_id, sender_id, receiver_id, sender_offer_coins, receiver_offer_coins, created_at
                FROM trades
                WHERE guild_id = ? AND (sender_id = ? OR receiver_id = ?) AND status = 'pending'
                ORDER BY created_at DESC
            """, (guild_id, user_id, user_id)) as cursor:
                rows = await cursor.fetchall()
                return [{"trade_id": r[0], "sender_id": r[1], "receiver_id": r[2], "sender_coins": r[3], "receiver_coins": r[4], "created_at": r[5]} for r in rows]
    
    async def add_achievement(self, achievement_id: str, name: str, description: str, emoji: str, reward_coins: int, reward_badge: str, requirement_type: str, requirement_value: int, tier: str = "bronze"):
        """Adiciona um achievement ao sistema"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO achievements (achievement_id, name, description, emoji, reward_coins, reward_badge, requirement_type, requirement_value, tier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(achievement_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    emoji = EXCLUDED.emoji,
                    reward_coins = EXCLUDED.reward_coins,
                    reward_badge = EXCLUDED.reward_badge,
                    requirement_type = EXCLUDED.requirement_type,
                    requirement_value = EXCLUDED.requirement_value,
                    tier = EXCLUDED.tier
            """, (achievement_id, name, description, emoji, reward_coins, reward_badge, requirement_type, requirement_value, tier))
            await db.commit()
    
    async def unlock_achievement(self, user_id: str, guild_id: str, achievement_id: str):
        """Desbloqueia achievement para utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT INTO user_achievements (user_id, guild_id, achievement_id)
                    VALUES (?, ?, ?)
                """, (user_id, guild_id, achievement_id))
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False  # Já tinha desbloqueado
    
    async def get_user_achievements(self, user_id: str, guild_id: str):
        """Obtém achievements desbloqueados pelo utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT a.achievement_id, a.name, a.description, a.emoji, a.tier, ua.unlocked_at, ua.claimed
                FROM user_achievements ua
                JOIN achievements a ON ua.achievement_id = a.achievement_id
                WHERE ua.user_id = ? AND ua.guild_id = ?
                ORDER BY ua.unlocked_at DESC
            """, (user_id, guild_id)) as cursor:
                rows = await cursor.fetchall()
                return [{"id": r[0], "name": r[1], "description": r[2], "emoji": r[3], "tier": r[4], "unlocked_at": r[5], "claimed": bool(r[6])} for r in rows]
    
    async def claim_achievement_reward(self, user_id: str, guild_id: str, achievement_id: str):
        """Marca achievement como claimed"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE user_achievements
                SET claimed = 1
                WHERE user_id = ? AND guild_id = ? AND achievement_id = ?
            """, (user_id, guild_id, achievement_id))
            await db.commit()
    
    async def create_auction(self, guild_id: str, seller_id: str, item_name: str, item_description: str, item_emoji: str, item_rarity: str, starting_bid: int, buyout_price: int, ends_at: str):
        """Cria um leilão"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO auctions (guild_id, seller_id, item_name, item_description, item_emoji, item_rarity, starting_bid, buyout_price, ends_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (guild_id, seller_id, item_name, item_description, item_emoji, item_rarity, starting_bid, buyout_price, ends_at))
            await db.commit()
            return cursor.lastrowid
    
    async def place_bid(self, auction_id: int, bidder_id: str, bid_amount: int):
        """Coloca uma bid num leilão"""
        async with aiosqlite.connect(self.db_path) as db:
            # Atualizar leilão
            await db.execute("""
                UPDATE auctions
                SET current_bid = ?, current_bidder_id = ?
                WHERE auction_id = ?
            """, (bid_amount, bidder_id, auction_id))
            
            # Registar bid
            await db.execute("""
                INSERT INTO auction_bids (auction_id, bidder_id, bid_amount)
                VALUES (?, ?, ?)
            """, (auction_id, bidder_id, bid_amount))
            
            await db.commit()
    
    async def get_auction(self, auction_id: int):
        """Obtém detalhes de um leilão"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT auction_id, guild_id, seller_id, item_name, item_description, item_emoji, item_rarity,
                       starting_bid, current_bid, current_bidder_id, buyout_price, status, created_at, ends_at
                FROM auctions
                WHERE auction_id = ?
            """, (auction_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "auction_id": row[0], "guild_id": row[1], "seller_id": row[2],
                        "item_name": row[3], "item_description": row[4], "item_emoji": row[5],
                        "item_rarity": row[6], "starting_bid": row[7], "current_bid": row[8],
                        "current_bidder_id": row[9], "buyout_price": row[10], "status": row[11],
                        "created_at": row[12], "ends_at": row[13]
                    }
                return None
    
    async def get_active_auctions(self, guild_id: str):
        """Obtém leilões ativos"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT auction_id, item_name, item_emoji, item_rarity, starting_bid, current_bid, ends_at
                FROM auctions
                WHERE guild_id = ? AND status = 'active'
                ORDER BY ends_at ASC
            """, (guild_id,)) as cursor:
                rows = await cursor.fetchall()
                return [{"auction_id": r[0], "item_name": r[1], "item_emoji": r[2], "item_rarity": r[3], "starting_bid": r[4], "current_bid": r[5], "ends_at": r[6]} for r in rows]
    
    async def complete_auction(self, auction_id: int, status: str = "completed"):
        """Completa um leilão"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE auctions
                SET status = ?
                WHERE auction_id = ?
            """, (status, auction_id))
            await db.commit()
    
    async def create_event(self, guild_id: str, event_type: str, event_name: str, multiplier: float, bonus_coins: int, description: str, started_by: str, ends_at: str):
        """Cria um evento especial"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO active_events (guild_id, event_type, event_name, multiplier, bonus_coins, description, started_by, ends_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (guild_id, event_type, event_name, multiplier, bonus_coins, description, started_by, ends_at))
            await db.commit()
            return cursor.lastrowid
    
    async def get_active_events(self, guild_id: str):
        """Obtém eventos ativos"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT event_id, event_type, event_name, multiplier, bonus_coins, description, started_at, ends_at
                FROM active_events
                WHERE guild_id = ? AND datetime(ends_at) > datetime('now')
            """, (guild_id,)) as cursor:
                rows = await cursor.fetchall()
                return [{"event_id": r[0], "event_type": r[1], "event_name": r[2], "multiplier": r[3], "bonus_coins": r[4], "description": r[5], "started_at": r[6], "ends_at": r[7]} for r in rows]
    
    async def add_inventory_item(self, user_id: str, guild_id: str, item_id: str, item_name: str, item_type: str, item_rarity: str, item_data: str = None, quantity: int = 1, tradeable: bool = True):
        """Adiciona item ao inventário"""
        async with aiosqlite.connect(self.db_path) as db:
            # Verificar se já tem o item
            async with db.execute("""
                SELECT quantity FROM inventory_items
                WHERE user_id = ? AND guild_id = ? AND item_id = ?
            """, (user_id, guild_id, item_id)) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    # Incrementar quantidade
                    await db.execute("""
                        UPDATE inventory_items
                        SET quantity = quantity + ?
                        WHERE user_id = ? AND guild_id = ? AND item_id = ?
                    """, (quantity, user_id, guild_id, item_id))
                else:
                    # Adicionar novo item
                    await db.execute("""
                        INSERT INTO inventory_items (user_id, guild_id, item_id, item_name, item_type, item_rarity, item_data, quantity, tradeable)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (user_id, guild_id, item_id, item_name, item_type, item_rarity, item_data, quantity, 1 if tradeable else 0))
                
                await db.commit()
    
    async def get_user_inventory(self, user_id: str, guild_id: str):
        """Obtém inventário do utilizador"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT item_id, item_name, item_type, item_rarity, quantity, tradeable, acquired_at
                FROM inventory_items
                WHERE user_id = ? AND guild_id = ?
                ORDER BY item_rarity DESC, acquired_at DESC
            """, (user_id, guild_id)) as cursor:
                rows = await cursor.fetchall()
                return [{"item_id": r[0], "item_name": r[1], "item_type": r[2], "item_rarity": r[3], "quantity": r[4], "tradeable": bool(r[5]), "acquired_at": r[6]} for r in rows]
    
    async def remove_inventory_item(self, user_id: str, guild_id: str, item_id: str, quantity: int = 1):
        """Remove item do inventário"""
        async with aiosqlite.connect(self.db_path) as db:
            # Verificar quantidade atual
            async with db.execute("""
                SELECT quantity FROM inventory_items
                WHERE user_id = ? AND guild_id = ? AND item_id = ?
            """, (user_id, guild_id, item_id)) as cursor:
                row = await cursor.fetchone()
                
                if not row:
                    return False
                
                if row[0] <= quantity:
                    # Remover completamente
                    await db.execute("""
                        DELETE FROM inventory_items
                        WHERE user_id = ? AND guild_id = ? AND item_id = ?
                    """, (user_id, guild_id, item_id))
                else:
                    # Decrementar quantidade
                    await db.execute("""
                        UPDATE inventory_items
                        SET quantity = quantity - ?
                        WHERE user_id = ? AND guild_id = ? AND item_id = ?
                    """, (quantity, user_id, guild_id, item_id))
                
                await db.commit()
                return True


# Instância global
db_instance = None

async def get_database() -> Database:
    """Obtém a instância da base de dados"""
    global db_instance
    if db_instance is None:
        db_instance = Database()
        await db_instance.init_db()
    return db_instance

