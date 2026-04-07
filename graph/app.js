/* ====================================================================
   NEYEN Crosslink Graph — app.js
   Fetches metadata from Supabase, builds a D3 force graph.
   Read-only — no writes. Data refreshes every 5 minutes.
   ==================================================================== */

const SUPABASE_URL = 'https://gsmtzdramqzcqdywboro.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdzbXR6ZHJhbXF6Y3FkeXdib3JvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM0NDg4NTIsImV4cCI6MjA4OTAyNDg1Mn0.0EWXPtw2A9darfVDBgCwyGw0oWGtHdKBokCf2c1Ku24';

const HEADERS = {
  'apikey': SUPABASE_ANON_KEY,
  'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
  'Content-Type': 'application/json'
};

const REFRESH_INTERVAL = 5 * 60 * 1000; // 5 minutes

// ===== NODE COLORS =====
const ROLE_COLORS = {
  realisation:  'var(--node-realisation)',
  exploration:  'var(--node-exploration)',
  conflict:     'var(--node-conflict)',
  symbol:       'var(--node-symbol)',
  system:       'var(--node-system)',
  pilot:        'var(--node-system)',
  origin:       'var(--node-symbol)',
  integration:  'var(--node-exploration)',
  setup:        'var(--node-default)',
};

function nodeColor(d) {
  if (d.isOrphan) return 'var(--node-orphan)';
  return ROLE_COLORS[d.narrative_role] || 'var(--node-default)';
}

function nodeRadius(d) {
  const connections = d.linkCount || 0;
  return Math.max(5, Math.min(20, 5 + connections * 2));
}

// ===== STATE =====
let simulation = null;
let svgRoot = null;
let allNodes = [];
let allLinks = [];
let orphanData = [];
let selectedNode = null;

// ===== FETCH DATA =====
// Uses graph_data() RPC (SECURITY DEFINER) since anon key can't read tables directly.
async function fetchGraphData() {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/graph_data`, {
    method: 'POST',
    headers: HEADERS,
    body: '{}'
  });
  if (!res.ok) throw new Error(`Supabase error: ${res.status}`);
  return res.json(); // { nodes: [], orphan_ids: [], total: N }
}

async function fetchOrphans() {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/orphaned_nodes`, {
    method: 'POST',
    headers: HEADERS,
    body: JSON.stringify({ p_days_threshold: 7, p_limit: 50 })
  });
  if (!res.ok) return { orphan_count: 0, orphans: [] };
  return res.json();
}

// ===== GRAPH BUILD =====
function buildGraph(graphResult, orphansResult) {
  const rows = graphResult.nodes || [];
  const orphanIds = new Set([
    ...(graphResult.orphan_ids || []),
    ...(orphansResult.orphans || []).map(o => o.id)
  ]);
  orphanData = orphansResult.orphans || [];

  const nodeMap = new Map();
  const nodes = rows.map(row => {
    // related_ids may come back as a JSON string inside the JSONB wrapper — parse it
    let relIds = row.related_ids || [];
    if (typeof relIds === 'string') { try { relIds = JSON.parse(relIds); } catch(e) { relIds = []; } }
    if (!Array.isArray(relIds)) relIds = [];
    let tags = row.tags || [];
    if (typeof tags === 'string') { try { tags = JSON.parse(tags); } catch(e) { tags = []; } }
    let entities = row.entities || [];
    if (typeof entities === 'string') { try { entities = JSON.parse(entities); } catch(e) { entities = []; } }
    const n = {
      id: row.id,
      file_name: row.file_name || row.id.slice(0, 8),
      summary: row.summary || '',
      tags,
      entities,
      narrative_role: row.narrative_role || '',
      timeline_group: row.timeline_group || '',
      created_at: row.created_at,
      related_ids: relIds,
      isOrphan: orphanIds.has(row.id),
      linkCount: 0
    };
    nodeMap.set(row.id, n);
    return n;
  });

  // Build edges — deduplicate (A→B and B→A = one edge)
  const seenEdges = new Set();
  const links = [];

  rows.forEach(row => {
    const sourceId = row.id;
    const parsedNode = nodeMap.get(sourceId);
    const relatedIds = (parsedNode && parsedNode.related_ids) || [];
    relatedIds.forEach(targetId => {
      if (!nodeMap.has(targetId)) return;
      const key = [sourceId, targetId].sort().join('__');
      if (seenEdges.has(key)) return;
      seenEdges.add(key);
      links.push({ source: sourceId, target: targetId });
      if (nodeMap.has(sourceId)) nodeMap.get(sourceId).linkCount++;
      if (nodeMap.has(targetId)) nodeMap.get(targetId).linkCount++;
    });
  });

  return { nodes, links };
}

// ===== D3 SIMULATION =====
function renderGraph(nodes, links) {
  allNodes = nodes;
  allLinks = links;

  const stage = document.getElementById('graphStage');
  const svg = d3.select('#graphSvg');
  svg.selectAll('*').remove();

  const W = stage.clientWidth;
  const H = stage.clientHeight;

  // Zoom/pan container
  const g = svg.append('g').attr('class', 'graph-root');

  const zoom = d3.zoom()
    .scaleExtent([0.1, 8])
    .on('zoom', e => g.attr('transform', e.transform));
  svg.call(zoom);

  // Store zoom ref for fit button
  svgRoot = { svg, g, zoom, W, H };

  // Force simulation
  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(d => {
      // More connected nodes pull closer
      const avg = ((d.source.linkCount || 0) + (d.target.linkCount || 0)) / 2;
      return Math.max(40, 100 - avg * 5);
    }).strength(0.6))
    .force('charge', d3.forceManyBody().strength(d => -200 - (d.linkCount || 0) * 10))
    .force('center', d3.forceCenter(W / 2, H / 2))
    .force('collision', d3.forceCollide().radius(d => nodeRadius(d) + 8).strength(0.8))
    .force('x', d3.forceX(W / 2).strength(0.04))
    .force('y', d3.forceY(H / 2).strength(0.04));

  // ---- LINKS ----
  const linkSel = g.append('g').attr('class', 'links')
    .selectAll('line')
    .data(links)
    .join('line')
    .attr('class', 'link');

  // ---- NODES ----
  const nodeSel = g.append('g').attr('class', 'nodes')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .attr('class', d => `node-group${d.isOrphan ? ' orphaned' : ''}`)
    .attr('aria-label', d => d.file_name)
    .call(d3.drag()
      .on('start', (e, d) => {
        if (!e.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x; d.fy = d.y;
      })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end', (e, d) => {
        if (!e.active) simulation.alphaTarget(0);
        d.fx = null; d.fy = null;
      })
    )
    .on('click', (e, d) => {
      e.stopPropagation();
      selectNode(d, linkSel, nodeSel);
    });

  nodeSel.append('circle')
    .attr('class', d => `node-circle${d.isOrphan ? ' orphaned' : ''}`)
    .attr('r', d => nodeRadius(d))
    .attr('fill', d => nodeColor(d))
    .attr('opacity', 0.9);

  nodeSel.append('text')
    .attr('class', 'node-label')
    .attr('y', d => nodeRadius(d) + 4)
    .text(d => d.file_name.replace(/^auto_slack_/, '').substring(0, 20));

  // Deselect on canvas click
  svg.on('click', () => deselectNode(linkSel, nodeSel));

  // Tick handler
  simulation.on('tick', () => {
    linkSel
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    nodeSel.attr('transform', d => `translate(${d.x},${d.y})`);
  });

  // Auto-fit after initial layout
  simulation.on('end', fitGraph);
}

function selectNode(d, linkSel, nodeSel) {
  selectedNode = d;

  // Highlight connected edges
  const connectedIds = new Set();
  connectedIds.add(d.id);
  linkSel.classed('highlighted', l => {
    const hit = l.source.id === d.id || l.target.id === d.id;
    if (hit) {
      connectedIds.add(l.source.id);
      connectedIds.add(l.target.id);
    }
    return hit;
  });

  // Dim unconnected nodes
  nodeSel.classed('selected', n => n.id === d.id);
  nodeSel.select('.node-circle').attr('opacity', n => connectedIds.has(n.id) ? 1 : 0.2);
  nodeSel.select('.node-label').attr('opacity', n => connectedIds.has(n.id) ? 1 : 0.2);

  showPanel(d);
}

function deselectNode(linkSel, nodeSel) {
  selectedNode = null;
  linkSel.classed('highlighted', false);
  nodeSel.classed('selected', false);
  nodeSel.select('.node-circle').attr('opacity', 0.9);
  nodeSel.select('.node-label').attr('opacity', 1);
  document.getElementById('detailPanel').classList.add('hidden');
}

function fitGraph() {
  if (!svgRoot || allNodes.length === 0) return;
  const { svg, g, zoom, W, H } = svgRoot;
  const bounds = g.node().getBBox();
  if (!bounds.width || !bounds.height) return;
  const scale = Math.min(0.9, Math.min(W / bounds.width, H / bounds.height)) * 0.85;
  const tx = W / 2 - scale * (bounds.x + bounds.width / 2);
  const ty = H / 2 - scale * (bounds.y + bounds.height / 2);
  svg.transition().duration(600).call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
}

// ===== DETAIL PANEL =====
function showPanel(d) {
  const panel = document.getElementById('detailPanel');
  document.getElementById('panelRole').textContent = d.narrative_role || 'unknown role';
  document.getElementById('panelTitle').textContent = d.file_name;
  document.getElementById('panelSummary').textContent = d.summary || 'No summary available.';
  document.getElementById('panelTimeline').textContent = d.timeline_group || '—';
  document.getElementById('panelCreated').textContent = d.created_at
    ? new Date(d.created_at).toLocaleDateString('en-GB', { day:'numeric', month:'short', year:'numeric' })
    : '—';
  document.getElementById('panelConnections').textContent = `${d.linkCount} direct link${d.linkCount !== 1 ? 's' : ''}`;

  // Tags
  const tagsEl = document.getElementById('panelTags');
  tagsEl.innerHTML = `<span class="meta-label">Tags</span> ${(d.tags || []).map(t => `<span class="tag-chip">${t}</span>`).join('') || '<span class="meta-val">—</span>'}`;

  // Entities
  const entEl = document.getElementById('panelEntities');
  entEl.innerHTML = `<span class="meta-label">Entities</span> ${(d.entities || []).map(e => `<span class="tag-chip">${e}</span>`).join('') || '<span class="meta-val">—</span>'}`;

  // Orphan warning
  const orphanRow = document.getElementById('panelOrphanRow');
  if (d.isOrphan) {
    orphanRow.style.display = 'flex';
    const orphanEntry = orphanData.find(o => o.id === d.id);
    document.getElementById('panelDaysOld').textContent = orphanEntry
      ? `${orphanEntry.days_old} days old — no crosslinks`
      : 'no crosslinks after 7+ days';
  } else {
    orphanRow.style.display = 'none';
  }

  panel.classList.remove('hidden');
}

// ===== ORPHAN TRAY =====
function renderOrphanTray(orphans) {
  const fab = document.getElementById('orphanFab');
  const tray = document.getElementById('orphanTray');
  const count = orphans.length;

  if (count === 0) {
    fab.classList.add('hidden');
    return;
  }

  document.getElementById('orphanFabCount').textContent = count;
  fab.classList.remove('hidden');

  document.getElementById('traySubtitle').textContent = `${count} entr${count === 1 ? 'y' : 'ies'} with no crosslinks after 7+ days`;
  const list = document.getElementById('trayList');
  list.innerHTML = orphans.map(o => `
    <li class="tray-item" data-id="${o.id}" role="listitem" tabindex="0" aria-label="${o.file_name}">
      <span class="tray-item-name">${o.file_name}</span>
      <span class="tray-item-age">${o.days_old}d old · ${(o.tags || []).slice(0, 3).join(', ')}</span>
    </li>
  `).join('');

  list.querySelectorAll('.tray-item').forEach(el => {
    el.addEventListener('click', () => {
      const id = el.dataset.id;
      const node = allNodes.find(n => n.id === id);
      if (node && simulation) {
        // Center on node
        const { svg, zoom, W, H } = svgRoot;
        svg.transition().duration(600).call(
          zoom.transform,
          d3.zoomIdentity.translate(W / 2 - node.x * 2, H / 2 - node.y * 2).scale(2)
        );
        // Select it
        const linkSel = d3.select('.links').selectAll('line');
        const nodeSel = d3.select('.nodes').selectAll('g');
        selectNode(node, linkSel, nodeSel);
      }
    });
    el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') el.click(); });
  });
}

// ===== UI CONTROLS =====
document.getElementById('panelClose').addEventListener('click', () => {
  document.getElementById('detailPanel').classList.add('hidden');
  if (svgRoot) {
    const linkSel = d3.select('.links').selectAll('line');
    const nodeSel = d3.select('.nodes').selectAll('g');
    deselectNode(linkSel, nodeSel);
  }
});

document.getElementById('fitBtn').addEventListener('click', fitGraph);

document.getElementById('orphanFab').addEventListener('click', () => {
  document.getElementById('orphanTray').classList.remove('hidden');
  document.getElementById('orphanFab').classList.add('hidden');
});

document.getElementById('trayClose').addEventListener('click', () => {
  document.getElementById('orphanTray').classList.add('hidden');
  document.getElementById('orphanFab').classList.remove('hidden');
});

// ===== THEME TOGGLE =====
(function() {
  const toggle = document.querySelector('[data-theme-toggle]');
  const root = document.documentElement;
  let theme = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  root.setAttribute('data-theme', theme);
  if (toggle) {
    toggle.addEventListener('click', () => {
      theme = theme === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', theme);
      toggle.setAttribute('aria-label', 'Switch to ' + (theme === 'dark' ? 'light' : 'dark') + ' mode');
      toggle.innerHTML = theme === 'dark'
        ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
        : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
    });
  }
})();

// ===== MAIN LOAD =====
async function loadData() {
  document.getElementById('loadingState').classList.remove('hidden');
  document.getElementById('emptyState').classList.add('hidden');

  try {
    const [graphResult, orphansResult] = await Promise.all([fetchGraphData(), fetchOrphans()]);
    const rows = graphResult.nodes || [];

    if (!rows.length) {
      document.getElementById('loadingState').classList.add('hidden');
      document.getElementById('emptyState').classList.remove('hidden');
      return;
    }

    const { nodes, links } = buildGraph(graphResult, orphansResult);

    // Stats bar
    const orphanCount = orphansResult.orphan_count || 0;
    document.getElementById('nodeCount').textContent = nodes.length;
    document.getElementById('edgeCount').textContent = links.length;
    document.getElementById('orphanCount').textContent = orphanCount;

    document.getElementById('loadingState').classList.add('hidden');

    renderGraph(nodes, links);
    renderOrphanTray(orphansResult.orphans || []);

  } catch (err) {
    console.error('Failed to load graph data:', err);
    document.getElementById('loadingState').innerHTML = `
      <p style="color:var(--color-text-muted)">Failed to load graph data.</p>
      <button onclick="loadData()" style="color:var(--color-primary);text-decoration:underline;cursor:pointer;font-size:var(--text-sm)">Retry</button>
    `;
  }
}

document.getElementById('refreshBtn').addEventListener('click', () => {
  if (simulation) simulation.stop();
  loadData();
});

// Auto-refresh every 5 minutes
setInterval(() => {
  if (simulation) simulation.stop();
  loadData();
}, REFRESH_INTERVAL);

// Init
loadData();
