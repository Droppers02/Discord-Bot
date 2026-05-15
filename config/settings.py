import os
import platform
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    """Configuração do bot"""
    
    # Tokens e IDs
    discord_token: str
    database_url: str
    openai_token: Optional[str] = None
    owner_ids: list[int] = None  # IDs dos donos do bot
    legacy_sqlite_path: str = "data/epa_bot.db"
    migrate_sqlite_on_startup: bool = True
    
    # Configurações do servidor (use IDs do seu servidor)
    server_id: int = 0  # ID do seu servidor
    mod_role_id: int = 0  # ID da role de moderador
    ticket_category_id: int = 0  # ID da categoria para tickets
    
    # Configurações de comando
    command_prefix: str = "!"
    
    # Configurações de música
    ffmpeg_path: str = "bin\\ffmpeg\\ffmpeg.exe"
    max_queue_size: int = 50
    music_timeout: int = 15  # Timeout para extração de música em segundos
    ytdl_format: str = "bestaudio"  # Formato padrão do yt-dlp
    enable_music_cache: bool = True  # Cache de URLs extraídas
    
    # Configurações de logging
    log_level: str = "INFO"
    music_debug: bool = False  # Log detalhado para música
    
    # Configurações de idioma
    language: str = "en"  # 'en' para English, 'pt' para Português

    @staticmethod
    def _parse_int_env(name: str, default: int = 0) -> int:
        raw_value = os.getenv(name)
        if raw_value is None or not raw_value.strip():
            return default

        try:
            return int(raw_value)
        except ValueError:
            print(f"[Config] Valor inválido para {name}={raw_value!r}. A usar {default}.")
            return default

    @staticmethod
    def _parse_bool_env(name: str, default: bool = False) -> bool:
        raw_value = os.getenv(name)
        if raw_value is None:
            return default

        normalized = raw_value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False

        print(f"[Config] Valor inválido para {name}={raw_value!r}. A usar {default}.")
        return default

    @staticmethod
    def _parse_owner_ids() -> list[int]:
        owner_ids = []
        owner_ids_str = os.getenv("OWNER_IDS", "")

        for raw_owner_id in owner_ids_str.split(","):
            candidate = raw_owner_id.strip()
            if not candidate:
                continue
            try:
                owner_ids.append(int(candidate))
            except ValueError:
                print(f"[Config] OWNER_IDS contém valor inválido: {candidate!r}. Entrada ignorada.")

        return owner_ids
    
    @classmethod
    def from_env(cls) -> "Config":
        """Cria configuração a partir de variáveis de ambiente"""
        owner_ids = cls._parse_owner_ids()
        
        # Detectar caminho padrão do FFmpeg baseado no sistema operacional
        if platform.system() == "Windows":
            default_ffmpeg = "bin\\ffmpeg\\ffmpeg.exe"
        else:  # Linux, macOS, Railway
            default_ffmpeg = "ffmpeg"  # Usar do PATH do sistema
        
        return cls(
            discord_token=os.getenv("DISCORD_TOKEN", ""),
            database_url=os.getenv("DATABASE_URL", os.getenv("NEON_DATABASE_URL", "")),
            openai_token=os.getenv("OPENAI_TOKEN"),
            owner_ids=owner_ids,
            legacy_sqlite_path=os.getenv("LEGACY_SQLITE_PATH", "data/epa_bot.db"),
            migrate_sqlite_on_startup=cls._parse_bool_env("MIGRATE_SQLITE_ON_STARTUP", True),
            server_id=cls._parse_int_env("SERVER_ID", 0),
            mod_role_id=cls._parse_int_env("MOD_ROLE_ID", 0),
            ticket_category_id=cls._parse_int_env("TICKET_CATEGORY_ID", 0),
            command_prefix=os.getenv("COMMAND_PREFIX", "!"),
            ffmpeg_path=os.getenv("FFMPEG_PATH", default_ffmpeg),
            max_queue_size=cls._parse_int_env("MAX_QUEUE_SIZE", 50),
            music_timeout=cls._parse_int_env("MUSIC_TIMEOUT", 15),
            ytdl_format=os.getenv("YTDL_FORMAT", "bestaudio"),
            enable_music_cache=cls._parse_bool_env("ENABLE_MUSIC_CACHE", True),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            music_debug=cls._parse_bool_env("MUSIC_DEBUG", False),
            language=os.getenv("BOT_LANGUAGE", "en")
        )
    
    def validate(self) -> bool:
        """Valida se as configurações obrigatórias estão presentes"""
        if not self.discord_token:
            raise ValueError("DISCORD_TOKEN é obrigatório")
        if not self.database_url:
            raise ValueError("DATABASE_URL é obrigatório para a versão PostgreSQL")
        return True
