# Instruções para configurar IDs personalizados

## Passo 1: Copiar o arquivo de exemplo

```bash
cd config
cp utilities_config.example.json utilities_config.json
```

## Passo 2: Obter IDs do Discord

### Como obter IDs de Roles:

1. Ative o **Modo Desenvolvedor** no Discord (Configurações > Avançado > Modo Desenvolvedor)
2. Clique com botão direito numa role
3. Clique em "Copiar ID"
4. Cole no arquivo `utilities_config.json`

### Como obter IDs de Canais:

1. Com Modo Desenvolvedor ativado
2. Clique com botão direito num canal
3. Clique em "Copiar ID"
4. Cole no arquivo `utilities_config.json`

## Passo 3: Editar utilities_config.json

Abra `config/utilities_config.json` e substitua os `0` pelos IDs copiados:

```json
{
  "verification": {
    "verified_role_id": SEU_ID_AQUI
  },
  "autoroles": {
    "games": {
      "gacha": SEU_ID_AQUI,
      "csgo": SEU_ID_AQUI,
      ...
    }
  }
}
```

## Passo 4: Reiniciar o bot

Após salvar o arquivo, reinicie o bot para carregar as novas configurações.

## Notas:

- Use `0` para desativar roles/botões específicos
- O arquivo `utilities_config.json` não é commitado no git (está no .gitignore)
- Mantenha seus IDs privados e seguros
