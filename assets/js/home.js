/**
 * home.js — SAFIE E-commerce v3
 * Carrega artigos do indice.json, exibe destaque + galeria de 12.
 */

const WORKER_URL = 'https://safie-analytics.lucas-mantovani.workers.dev';
const BLOG_SLUG  = 'ecommerce';
const MAX_GALERIA = 12;

const MESES = [
  'janeiro','fevereiro','março','abril','maio','junho',
  'julho','agosto','setembro','outubro','novembro','dezembro'
];

function formatarData(iso) {
  const d = new Date(iso);
  return `${d.getDate()} de ${MESES[d.getMonth()]} de ${d.getFullYear()}`;
}

function escaparHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

function cardHtml(artigo) {
  const slug  = escaparHtml(artigo.slug);
  const img   = `/assets/img/artigos/${slug}.svg`;
  const href  = `/artigos/${slug}`;
  const tema  = escaparHtml(artigo.tema);
  const titulo = escaparHtml(artigo.titulo);
  const data  = formatarData(artigo.data);
  const resumo = escaparHtml(artigo.resumo);

  // v3: card limpo (sem faixa de imagem chapada), com .card-corpo + .card-resumo.
  // Mantém .card-artigo + data-tema para o filtro de tema (aplicarFiltro / busca.js).
  return `
<a class="card-artigo" data-tema="${escaparHtml(artigo.tema_slug)}" href="${href}">
  <div class="card-corpo">
    <span class="card-tema">${tema}</span>
    <h2 class="card-titulo-clamp">${titulo}</h2>
    <p class="card-resumo">${resumo}</p>
    <div class="card-meta">
      <span class="card-data">${data}</span>
    </div>
  </div>
</a>`;
}

function renderDestaque(artigo, isMaisLido) {
  const container = document.getElementById('destaque-container');
  if (!container || !artigo) return;

  const slug   = escaparHtml(artigo.slug);
  const img    = `/assets/img/artigos/${slug}.svg`;
  const href   = `/artigos/${slug}`;
  const badge  = isMaisLido
    ? '<span class="destaque-badge mais-lido">Mais lido do mês</span>'
    : '<span class="destaque-badge">Em destaque</span>';

  container.innerHTML = `
<section class="destaque-section">
  <a href="${href}" class="destaque-card">
    <div class="destaque-imagem-wrap">
      <img class="destaque-imagem" src="${img}" alt="${escaparHtml(artigo.titulo)}" width="800" height="450">
    </div>
    <div class="destaque-corpo">
      <div class="destaque-tags">
        ${badge}
        <span class="destaque-categoria">${escaparHtml(artigo.tema)}</span>
      </div>
      <h2 class="destaque-titulo">${escaparHtml(artigo.titulo)}</h2>
      <p class="destaque-lead">${escaparHtml(artigo.resumo)}</p>
      <span class="destaque-btn">Ler artigo completo →</span>
    </div>
  </a>
</section>`;
}

function renderGaleria(artigos) {
  const grid = document.getElementById('artigos-grid');
  if (!grid) return;
  grid.className = 'artigos-grid artigos-grid-home';
  grid.innerHTML = artigos.map(cardHtml).join('');
}

function aplicarFiltro(tema) {
  document.querySelectorAll('.filtros-lista a').forEach(a => {
    a.classList.toggle('ativo', a.dataset.tema === tema || (tema === 'todos' && a.dataset.tema === 'todos'));
  });

  const cards = document.querySelectorAll('#artigos-grid .card-artigo');
  cards.forEach(card => {
    const visivel = tema === 'todos' || card.dataset.tema === tema;
    card.style.display = visivel ? '' : 'none';
  });
}

async function init() {
  const container = document.getElementById('destaque-container');
  if (container) container.innerHTML = '<div class="destaque-skeleton"></div>';

  const [indice, destaqueInfo] = await Promise.all([
    fetch('/artigos/indice.json').then(r => r.json()).catch(() => []),
    fetch(`${WORKER_URL}/destaques/${BLOG_SLUG}`).then(r => r.json()).catch(() => ({ estado: 'A' })),
  ]);

  if (!indice || !indice.length) {
    if (container) container.innerHTML = '';
    return;
  }

  let destaqueArtigo = indice[0];
  let isMaisLido = false;

  if (destaqueInfo.estado === 'B' && destaqueInfo.artigo_slug) {
    const encontrado = indice.find(a => a.slug === destaqueInfo.artigo_slug);
    if (encontrado) { destaqueArtigo = encontrado; isMaisLido = true; }
  }

  const galeria = indice
    .filter(a => a.slug !== destaqueArtigo.slug)
    .slice(0, MAX_GALERIA);

  renderDestaque(destaqueArtigo, isMaisLido);
  renderGaleria(galeria);

  document.querySelectorAll('.filtros-lista a').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      aplicarFiltro(link.dataset.tema || 'todos');
    });
  });
}

init();
