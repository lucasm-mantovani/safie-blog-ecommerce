# CLAUDE.md — Blog-Ecommerce SAFIE

## O que é este projeto
Blog automatizado em HTML estático, publicado em **ecommerce.safie.blog.br**, com artigos gerados diariamente via Claude API.
O blog cobre direito e contabilidade aplicados ao e-commerce e comércio digital, com foco no mercado brasileiro.

## ATENÇÃO: domínios completamente separados

| Domínio | O que é | Pode alterar? |
|---|---|---|
| safie.com.br | Site institucional da SAFIE | **NUNCA** |
| safie.blog.br | Rede de blogs temáticos | Sim |
| cripto.safie.blog.br | Outro blog da rede (Blog-Cripto) | **NÃO — sessão separada** |
| ecommerce.safie.blog.br | Este blog | Sim |

**NUNCA modifique safie.com.br nem ~/CLAUDE/Blog-Cripto.**

## Estrutura de pastas

```
Blog-Ecommerce/
├── config/          # Configurações do blog (blog.json, temas.json, fontes.json)
├── dados/           # Histórico de notícias, notícia selecionada, artigo gerado
├── templates/       # Templates HTML (artigo, tema)
├── assets/
│   ├── css/         # estilo.css (identidade SAFIE)
│   ├── js/          # busca.js
│   └── img/         # favicon.svg
├── artigos/         # HTMLs gerados de cada artigo + indice.json
├── temas/           # Páginas de listagem por tema (geradas pelo publicar.py)
├── scripts/
│   ├── buscar_noticia.py   # Busca via RSS (Apify opcional)
│   ├── gerar_artigo.py     # Geração via Claude API
│   ├── publicar.py         # Geração de HTML + git push
│   └── verificar_e_rodar.sh
├── logs/            # Logs diários (não versionados)
├── rodar_diario.sh  # Orquestrador (launchd às 7h30)
├── sitemap.xml      # Atualizado automaticamente
├── robots.txt
├── .env             # Credenciais (NÃO versionado)
└── .env.template    # Modelo de credenciais (versionado, sem valores reais)
```

## Credenciais necessárias (arquivo .env)
- `ANTHROPIC_API_KEY` — geração de artigos via Claude API
- `GITHUB_TOKEN` — push automático dos artigos
- `GITHUB_REPO` — `lucasm-mantovani/safie-blog-ecommerce`
- `APIFY_TOKEN` — opcional (o blog usa RSS por padrão, Apify é fallback adicional)

**Nunca hardcode credenciais. Sempre ler de variável de ambiente.**

## Pipeline diário (rodar_diario.sh — executa às 7h30 via launchd)
1. `buscar_noticia.py` — busca via RSS (TEMAS_EVERGREEN e FONTES_AUTORIDADE em config/)
2. `gerar_artigo.py` — gera artigo via Claude API (system prompt lido do config/blog.json)
3. `publicar.py` — gera HTML, atualiza home/sitemap, commit + push GitHub

## Diferença dos scripts vs Blog-Cripto
Os scripts deste blog são **100% genéricos** — nenhum hardcode de nicho:
- `TEMAS_EVERGREEN` → lidos de `config/temas.json`
- `FONTES_AUTORIDADE` → lidos de `config/fontes.json`
- `SYSTEM_PROMPT` do Claude → construído dinamicamente a partir de `config/blog.json`
- Nome do blog nos templates → variável `{{BLOG_NOME}}`, preenchida pelo `publicar.py`

## Regras de SEO e GEO
- Título: máximo 60 caracteres, com palavra-chave principal
- Meta description: máximo 155 caracteres
- Estrutura obrigatória: resumo executivo → contexto jurídico → impacto prático → FAQ (3-5 perguntas)
- Schema.org: BlogPosting + FAQPage em JSON-LD
- URL: `https://ecommerce.safie.blog.br/artigos/AAAA-MM-DD-slug-do-artigo.html`
- Artigos: mínimo 800, máximo 1.500 palavras
- Tom: técnico, direto, sem juridiquês, sem clichês, sem travessão (—)

## Temas cobertos
1. Tributação no e-commerce (ICMS, DIFAL, Simples Nacional)
2. Direito do consumidor no digital (CDC, arrependimento, PROCON)
3. Marketplaces e plataformas digitais (responsabilidade, regulação)
4. LGPD e privacidade no e-commerce (ANPD, cookies, dados)
5. Logística e operações (fulfillment, frete, Correios)
6. Meios de pagamento no varejo digital (PIX, chargeback, split)
7. Importação e cross-border (Remessa Conforme, Shein/Shopee)

## Estado atual do projeto (2026-04-28)
- **Fases 1–5 concluídas:** pipeline 4 etapas ativo, launchd às 7h30, domínio ecommerce.safie.blog.br no ar
- **Fase 6 concluída (2026-04-28):**
  - DNS propagado e HTTP 200 confirmados
  - robots.txt + sitemap.xml funcionando
  - Schema.org BlogPosting + FAQPage em todos os artigos
  - meta robots, keywords, og:*, twitter:* no template
  - Validação manual opcional: Google Rich Results Test + PageSpeed Insights
