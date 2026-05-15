# EPA BOTCHI

Bot de comunidade para Discord com economia, jogos, música, moderação, tickets e utilidades.

Este branch, `main`, é a versão em português de Portugal. A versão inglesa vive no branch `en`.

## Funcionalidades

- Economia com saldo, loja, inventário, roles personalizadas, trocas, conquistas e leilões
- Jogos sociais e de aposta, com estatísticas e leaderboards
- Sistema social com XP, níveis, reputação, perfis, badges e casamentos
- Moderação com logs, filtros automáticos, strikes, anti-spam e anti-raid
- Tickets, sugestões, giveaways, lembretes, anúncios, starboard e AFK
- Música com fila, controlo de reprodução e integração com `yt-dlp`

## Requisitos

- Python 3.10 ou superior
- FFmpeg disponível no sistema ou em `FFMPEG_PATH`
- Base de dados PostgreSQL acessível, por exemplo Neon
- Token de bot do Discord

## Instalação

```bash
git clone https://github.com/Droppers02/Discord-Community-Bot.git
cd Discord-Community-Bot
pip install -r requirements.txt
```

Cria um ficheiro `.env` com pelo menos:

```env
DISCORD_TOKEN=coloca_o_teu_token_aqui
SQL_DATABASE_URL=postgresql://utilizador:palavra-passe@host/base_de_dados?sslmode=require
BOT_LANGUAGE=pt

# Opcionais
SERVER_ID=0
MOD_ROLE_ID=0
TICKET_CATEGORY_ID=0
OWNER_IDS=123456789012345678,987654321098765432
FFMPEG_PATH=ffmpeg
LOG_LEVEL=INFO
```

Também são aceites `DATABASE_URL` e `NEON_DATABASE_URL` como aliases de `SQL_DATABASE_URL`.

Arranque:

```bash
python main.py
```

## Base de Dados

- O bot usa PostgreSQL como persistência principal.
- O esquema é criado automaticamente no arranque.
- O arranque já não faz migrações automáticas de JSON/SQLite antigos.
- As pastas `data/` e `logs/` ficam no repositório apenas com `.gitkeep`; os ficheiros gerados em runtime não devem ser mantidos no projeto.

## Estrutura do Projeto

```text
EPA BOTCHI/
├── cogs/                  # Módulos de comandos
├── config/                # Configuração e i18n
├── utils/                 # Base de dados, logger, embeds, paginação
├── data/                  # Dados locais gerados em runtime
├── logs/                  # Logs gerados em runtime
├── main.py                # Ponto de entrada do bot
├── requirements.txt       # Dependências Python
└── README.md              # Documentação deste branch
```

## Desenvolvimento

- Usa `python -m compileall main.py cogs utils config` para validação rápida.
- Mantém `main` em português de Portugal e `en` em inglês.
- Evita voltar a introduzir ficheiros de estado gerados em runtime no repositório.

## Licença

Distribuído sob a licença MIT. Consulta `LICENSE` para detalhes.
