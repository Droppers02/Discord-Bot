# TODO - EPA BOTCHI

Lista curta das próximas melhorias planeadas para o branch `main`.

## Bugs e estabilidade

- Resolver bloqueios do YouTube na extração de áudio e endurecer os fallbacks do sistema de música
- Rever estabilidade do player em sessões longas e filas extensas
- Confirmar que não há crescimento indevido de memória nos fluxos de música e cache

## Base de dados e performance

- Rever queries mais pesadas para servidores grandes
- Identificar pontos restantes com persistência local em JSON que ainda mereçam migração para PostgreSQL
- Adicionar validações e observabilidade melhores para falhas de ligação à base de dados

## Música

- Suporte melhor para playlists persistentes por utilizador
- Votação para `skip`
- Histórico recente de músicas tocadas
- Integração opcional com Spotify para pesquisa/importação

## Tickets e moderação

- Templates de resposta rápida para tickets
- Prioridades e métricas de resolução em tickets
- Mais ferramentas de auditoria para ações automáticas de moderação

## Utilidades e social

- Melhorias no inventário visual e itens colecionáveis
- Missões diárias/semanais automáticas
- Mais painéis de configuração para utilidades avançadas
- Gráficos e estatísticas sociais com consultas mais eficientes
