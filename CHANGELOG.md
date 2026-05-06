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
