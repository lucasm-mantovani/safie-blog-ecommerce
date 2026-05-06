## 2026-05-06 — Fix: extrair_json defensivo + blindagem .gitignore + recuperação de pipeline

Mudanças em `scripts/gerar_artigo.py`:
- Adicionada função `salvar_resposta_bruta()` para forense automático em `dados/ultima_resposta_claude.txt`
- `extrair_json()` reescrita com fallback de sanitização de newlines literais dentro de strings
- Adicionada `gerar_artigo_com_retry()` com retry de geração (max 2 tentativas, prompt reforçado na 2ª)
- Instruções defensivas no template do prompt: aspas simples no HTML, escape de aspas duplas, sem newlines literais

Mudanças em `.gitignore`:
- Bloqueio de patterns de backup local: `.env.bkp*`, `*.bkp.*`, `.git/config.bkp.*`

Incidente do dia (recuperado):
- `publicar.py` com `git add -A` capturou `.env.bkp.20260505-pre-token-rotation` em commits locais
- GitHub Push Protection bloqueou push, evitando vazamento da chave Anthropic ativa
- Histórico limpo via `git reset --soft` + recommit (cherry-pick rebuild no Cripto que tinha 2 commits afetados)
- Patches dos commits originais preservados em `~/CLAUDE/_recovery/2026-05-06/`

Backup local: `scripts/gerar_artigo.py.bkp.20260506-pre-fix-extrair-json`

## 2026-05-05 — Fix: deduplicação de notícias ativada

Mudanças em `scripts/buscar_noticia.py`:
- `registrar_noticia_publicada()` passa a ser chamada após gravação de `noticia_selecionada.json`, com guard contra evergreens (url vazia)
- `ja_publicado()` reescrita com janelas reais por categoria: URL bloqueada por 15 dias, `tema_slug` por 3 dias
- try/except defensivo em volta da chamada nova

Backup: `scripts/buscar_noticia.py.bkp.20260505-pre-fix-historico`
Commit local do fix: 8f9f7dd
Validação real: 06/05 após 8h20

## 2026-05-05 — Rotação de token GitHub

Token classic 'Claude Code - SAFIE hire' (ghp_50pg...hug7, escopos exagerados) substituído por token fine-grained com permissões mínimas (apenas Contents: R/W nos 5 repos de blog). Token removido da URL do remote — autenticação agora via Keychain. Backups: .env.bkp.20260505-pre-token-rotation e .git/config.bkp.20260505-pre-token-rotation
