/**
 * Sistema de busca — JavaScript puro (sem backend)
 * Carrega o índice de artigos (artigos/indice.json) e filtra localmente
 */

(function () {
  'use strict';

  // ── Índice de artigos (carregado via fetch) ──
  let indice = [];

  async function carregarIndice() {
    try {
      const resp = await fetch('/artigos/indice.json');
      if (!resp.ok) throw new Error('Índice não encontrado');
      indice = await resp.json();
    } catch (e) {
      console.warn('Busca: não foi possível carregar índice.', e.message);
    }
  }

  // ── Normaliza texto (remove acentos, minúsculas) ──
  function normalizar(texto) {
    return (texto || '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9\s]/g, ' ')
      .trim();
  }

  // ── Pontuação de relevância ──
  function pontuar(artigo, termos) {
    const titulo = normalizar(artigo.titulo);
    const resumo = normalizar(artigo.resumo);
    const tema   = normalizar(artigo.tema);
    let pontos = 0;

    termos.forEach(function (t) {
      if (titulo.includes(t))  pontos += 10;
      if (resumo.includes(t))  pontos += 5;
      if (tema.includes(t))    pontos += 3;
    });

    return pontos;
  }

  // ── Executa a busca ──
  function buscar(query) {
    if (!query || query.trim().length < 2) return [];

    const termos = normalizar(query).split(/\s+/).filter(Boolean);

    return indice
      .map(function (artigo) {
        return { artigo: artigo, pontos: pontuar(artigo, termos) };
      })
      .filter(function (item) { return item.pontos > 0; })
      .sort(function (a, b) { return b.pontos - a.pontos; })
      .map(function (item) { return item.artigo; });
  }

  // ── Renderiza card de resultado ──
  function renderCard(artigo) {
    const data = new Date(artigo.data).toLocaleDateString('pt-BR', {
      day: '2-digit', month: 'long', year: 'numeric'
    });

    return '<div class="card-artigo">'
      + '<span class="card-tema">' + escHtml(artigo.tema) + '</span>'
      + '<h2><a href="/artigos/' + escHtml(artigo.slug) + '.html">'
      +   escHtml(artigo.titulo)
      + '</a></h2>'
      + '<p class="card-resumo">' + escHtml(artigo.resumo) + '</p>'
      + '<div class="card-meta">'
      +   '<span class="card-data">' + data + '</span>'
      +   '<a class="card-link" href="/artigos/' + escHtml(artigo.slug) + '.html">Ler artigo →</a>'
      + '</div>'
      + '</div>';
  }

  function escHtml(str) {
    return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── Inicializa busca na página de busca ──
  function initPaginaBusca() {
    const form        = document.getElementById('form-busca');
    const input       = document.getElementById('input-busca');
    const resultados  = document.getElementById('resultados-busca');
    const contagem    = document.getElementById('contagem-resultados');

    if (!form || !input || !resultados) return;

    // Pré-preenche com parâmetro ?q= da URL
    const params = new URLSearchParams(window.location.search);
    const q = params.get('q') || '';
    if (q) {
      input.value = q;
      executarBusca(q);
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      const query = input.value.trim();
      if (!query) return;
      // Atualiza URL sem recarregar
      history.replaceState(null, '', '?q=' + encodeURIComponent(query));
      executarBusca(query);
    });

    function executarBusca(query) {
      const lista = buscar(query);

      if (contagem) {
        contagem.textContent = lista.length > 0
          ? lista.length + ' resultado' + (lista.length > 1 ? 's' : '') + ' para "' + escHtml(query) + '"'
          : '';
      }

      if (lista.length === 0) {
        resultados.innerHTML = '<p class="sem-resultados">Nenhum artigo encontrado para "<strong>'
          + escHtml(query) + '</strong>".<br>Tente outros termos.</p>';
        return;
      }

      resultados.innerHTML = lista.map(renderCard).join('');
    }
  }

  // ── Inicializa busca rápida no header (se existir) ──
  function initBuscaHeader() {
    const inputHeader = document.getElementById('busca-header-input');
    if (!inputHeader) return;

    inputHeader.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && inputHeader.value.trim().length >= 2) {
        window.location.href = '/busca.html?q=' + encodeURIComponent(inputHeader.value.trim());
      }
    });
  }

  // ── Inicializa busca em linha (home/temas) ──
  function initBuscaInline() {
    const inputInline = document.getElementById('busca-inline-input');
    const btnInline   = document.getElementById('busca-inline-btn');
    if (!inputInline) return;

    function ir() {
      const q = inputInline.value.trim();
      if (q.length >= 2) {
        window.location.href = '/busca.html?q=' + encodeURIComponent(q);
      }
    }

    if (btnInline) btnInline.addEventListener('click', ir);
    inputInline.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') ir();
    });
  }

  // ── Filtro por tema na home ──
  function initFiltroTema() {
    const filtros = document.querySelectorAll('.filtros-lista a[data-tema]');
    const cards   = document.querySelectorAll('.card-artigo[data-tema]');
    if (!filtros.length) return;

    filtros.forEach(function (link) {
      link.addEventListener('click', function (e) {
        e.preventDefault();
        const tema = this.dataset.tema;

        filtros.forEach(function (f) { f.classList.remove('ativo'); });
        this.classList.add('ativo');

        cards.forEach(function (card) {
          if (tema === 'todos' || card.dataset.tema === tema) {
            card.style.display = '';
          } else {
            card.style.display = 'none';
          }
        });
      });
    });
  }

  // ── Menu mobile ──
  function initMenuMobile() {
    const toggle = document.getElementById('menu-toggle');
    const nav    = document.getElementById('nav-principal');
    if (!toggle || !nav) return;

    toggle.addEventListener('click', function () {
      nav.classList.toggle('aberto');
    });
  }

  // ── Bootstrap ──
  document.addEventListener('DOMContentLoaded', function () {
    carregarIndice().then(function () {
      initPaginaBusca();
      initBuscaInline();
      initBuscaHeader();
      initFiltroTema();
      initMenuMobile();
    });
  });

})();
