(function () {
  "use strict";

  const contratos = JSON.parse(document.getElementById("dados-contratos").textContent);
  const indices = JSON.parse(document.getElementById("dados-indices").textContent);

  // ---------------- utilidades ----------------
  const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const dataBR = (iso) => (iso ? iso.split("-").reverse().join("/") : "-");
  const moeda = (v) => (v == null ? "-" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" }));
  const mesAno = (iso) => (iso ? iso.slice(5, 7) + "/" + iso.slice(0, 4) : "-");
  const valorContrato = (c) => (c.valor_variavel ? '<span class="variavel">Variável</span>' : moeda(c.valor_mensal));
  const urlEditar = (id) => window.URLS.editar.replace(/0\/editar$/, id + "/editar");
  const temGrupo = (c, g) => c.categoria === g;

  const css = getComputedStyle(document.documentElement);
  const cor = (v) => css.getPropertyValue(v).trim();

  // selos que aparecem ao lado do status na tabela
  const SELOS_GRUPO = [
    ["vencido", "Vencido", "selo-erro"],
    ["vencimento", "Vigência", "selo-alerta"],
    ["reajuste", "Reajuste", "selo-info"],
    ["demais", "Outros", "selo-neutro"],
  ];

  function classeStatus(s) {
    return s === "Finalizado" ? "st-ok" : "st-alerta";
  }

  function seloAlertas(c) {
    const selos = SELOS_GRUPO.filter(([g]) => temGrupo(c, g)).map(([, rot, cls]) => `<span class="selo ${cls}">${rot}</span>`);
    if (c.alertas.includes("proximo_vencimento")) selos.push(`<span class="selo selo-alerta">vence em ${c.dias_para_fim}d</span>`);
    if (c.alertas.includes("proximo_reajuste")) selos.push('<span class="selo selo-info">reajuste próximo</span>');
    return selos.join(" ");
  }

  // ---------------- tabela + filtros ----------------
  const filtros = {
    parceiro: document.getElementById("f-parceiro"),
    unidade: document.getElementById("f-unidade"),
    status: document.getElementById("f-status"),
    mes: document.getElementById("f-mes"),
    busca: document.getElementById("f-busca"),
  };
  const tbody = document.querySelector("#tabela tbody");
  let ordem = { col: "fim", asc: true };

  function aplicarFiltros() {
    const f = Object.fromEntries(Object.entries(filtros).map(([k, el]) => [k, el.value.trim()]));
    const termo = f.busca.toLowerCase();
    return contratos.filter((c) =>
      (!f.parceiro || c.parceiro === f.parceiro) &&
      (!f.unidade || c.unidade === f.unidade) &&
      (!f.status || c.status === f.status) &&
      (!f.mes || c.mes === f.mes) &&
      (!termo || [c.parceiro, c.unidade, c.status, c.observacao, c.objeto].some((v) => (v || "").toLowerCase().includes(termo)))
    );
  }

  function ordenar(lista) {
    const { col, asc } = ordem;
    return [...lista].sort((a, b) => {
      let x = a[col], y = b[col];
      if (x == null || x === "") return 1;
      if (y == null || y === "") return -1;
      const r = typeof x === "number" ? x - y : String(x).localeCompare(String(y), "pt-BR");
      return asc ? r : -r;
    });
  }

  function linhaTabela(c, comAcao = true) {
    return `<tr data-id="${c.id}">
      <td>${esc(c.mes)}</td><td class="nome">${esc(c.unidade)}</td><td class="nome"><strong>${esc(c.parceiro)}</strong></td>
      <td>${dataBR(c.inicio)}</td><td>${dataBR(c.fim)}</td><td>${mesAno(c.reajuste)}</td>
      <td><span class="status ${classeStatus(c.status)}">${esc(c.status)}</span> ${seloAlertas(c)}</td>
      <td class="texto">${esc(c.observacao)}</td><td class="texto">${esc(c.objeto)}</td>
      <td>${esc(c.tipo_contrato)}</td><td class="num">${valorContrato(c)}</td>
      ${comAcao ? `<td><a class="link-editar" href="${urlEditar(c.id)}" title="Editar">✎</a></td>` : ""}
    </tr>`;
  }

  function renderizar() {
    const lista = ordenar(aplicarFiltros());
    tbody.innerHTML = lista.map((c) => linhaTabela(c)).join("");
    document.getElementById("contador").textContent = lista.length;

    // exportação respeita os filtros aplicados
    const params = new URLSearchParams();
    Object.entries(filtros).forEach(([k, el]) => el.value.trim() && params.set(k, el.value.trim()));
    document.getElementById("btn-exportar").href = window.URLS.exportar + (params.toString() ? "?" + params : "");

    document.querySelectorAll("#tabela th[data-col]").forEach((th) => {
      th.classList.toggle("ord-asc", th.dataset.col === ordem.col && ordem.asc);
      th.classList.toggle("ord-desc", th.dataset.col === ordem.col && !ordem.asc);
    });
  }

  Object.values(filtros).forEach((el) => el.addEventListener("input", renderizar));
  document.getElementById("f-limpar").addEventListener("click", () => {
    Object.values(filtros).forEach((el) => (el.value = ""));
    renderizar();
  });
  document.querySelectorAll("#tabela th[data-col]").forEach((th) =>
    th.addEventListener("click", () => {
      ordem = { col: th.dataset.col, asc: ordem.col === th.dataset.col ? !ordem.asc : true };
      renderizar();
    })
  );
  renderizar();

  // ---------------- janela de detalhamento ----------------
  const modal = document.getElementById("modal");
  const DETALHES = {
    todos: ["Todos os contratos", () => true],
    em_dia: ["Contratos em dia", (c) => temGrupo(c, "em_dia")],
    tratativas: ["Contratos em tratativas", (c) => !temGrupo(c, "em_dia")],
    vencidos: ["Contratos vencidos", (c) => temGrupo(c, "vencido")],
    trat_venc: ["Contratos próximos do vencimento", (c) => temGrupo(c, "vencimento")],
    trat_reaj: ["Contratos próximos do reajuste", (c) => temGrupo(c, "reajuste")],
    trat_outros: ["Demais em tratativas", (c) => temGrupo(c, "demais")],
  };

  function abrirDetalhe(titulo, lista) {
    document.getElementById("modal-titulo").textContent = `${titulo} (${lista.length})`;
    document.getElementById("modal-corpo").innerHTML = lista.length
      ? `<div class="tabela-wrap"><table class="tabela"><thead><tr><th>Mês</th><th>Unidade</th><th>Parceiro</th><th>Início</th><th>Fim</th><th>Reajuste</th><th>Status</th><th>Observação</th><th>Objeto</th><th>Tipo de contrato</th><th class="num">Valor mensal</th><th></th></tr></thead>
         <tbody>${lista.map((c) => linhaTabela(c)).join("")}</tbody></table></div>`
      : '<div class="vazio">Nenhum contrato nesta categoria.</div>';
    modal.showModal();
  }

  document.querySelectorAll(".kpi[data-detalhe]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const [titulo, filtro] = DETALHES[btn.dataset.detalhe];
      abrirDetalhe(titulo, contratos.filter(filtro));
    })
  );
  modal.querySelector(".fechar").addEventListener("click", () => modal.close());
  modal.addEventListener("click", (e) => { if (e.target === modal) modal.close(); });

  // ---------------- gráficos de tratativas (vencimento e reajuste por mês) ----------------
  // escreve o número em cima de cada barra
  const rotuloNasBarras = {
    id: "rotuloNasBarras",
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      ctx.save();
      ctx.font = "700 12px 'Segoe UI', system-ui, sans-serif";
      ctx.fillStyle = cor("--texto");
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      chart.getDatasetMeta(0).data.forEach((barra, i) => {
        ctx.fillText(chart.data.datasets[0].data[i], barra.x, barra.y - 6);
      });
      ctx.restore();
    },
  };

  // Agrupa os contratos de uma categoria pelo mês de uma data ("2026-10-23" -> "Out/2026")
  const MESES_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
  const rotuloMes = (anoMes) => anoMes === "sem-data" ? "Sem data"
    : `${MESES_ABREV[Number(anoMes.slice(5, 7)) - 1]}/${anoMes.slice(0, 4)}`;

  function agruparPorMes(grupo, campoData) {
    const contagem = {};
    contratos.filter((c) => temGrupo(c, grupo)).forEach((c) => {
      const chave = c[campoData] ? c[campoData].slice(0, 7) : "sem-data";
      contagem[chave] = (contagem[chave] || 0) + 1;
    });
    const chaves = Object.keys(contagem).sort(); // ordem cronológica ("sem-data" fica por último)
    return { chaves, rotulos: chaves.map(rotuloMes), valores: chaves.map((k) => contagem[k]) };
  }

  function graficoTratativa(idCanvas, corBarra, grupo, campoData, tituloDetalhe) {
    const canvas = document.getElementById(idCanvas);
    if (!canvas) return;
    if (!window.Chart) {
      canvas.parentElement.innerHTML = '<div class="vazio">Gráfico indisponível (arquivo do Chart.js não encontrado).</div>';
      return;
    }
    const { chaves, rotulos, valores } = agruparPorMes(grupo, campoData);
    if (!valores.length) {
      canvas.parentElement.innerHTML = '<div class="vazio">Nenhum contrato nesta tratativa.</div>';
      return;
    }
    const maximo = Math.max(...valores, 1);
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: rotulos,
        datasets: [{ data: valores, backgroundColor: corBarra, hoverBackgroundColor: corBarra, borderRadius: 2, maxBarThickness: 48 }],
      },
      plugins: [rotuloNasBarras],
      options: {
        maintainAspectRatio: false,
        layout: { padding: { top: 22 } },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (ctx) => `${ctx.parsed.y} contrato(s)` } },
        },
        scales: {
          x: { grid: { display: false }, border: { color: cor("--texto") }, ticks: { color: cor("--texto"), maxRotation: 0, autoSkip: false } },
          y: {
            beginAtZero: true,
            suggestedMax: Math.ceil((maximo * 1.15) / 5) * 5,
            ticks: { precision: 0, stepSize: maximo > 10 ? 5 : 1, color: cor("--texto-2") },
            grid: { color: cor("--borda") },
            border: { display: false },
            title: { display: true, text: "Qtd. Contratos", color: cor("--texto-2") },
          },
        },
        onHover: (e, barras) => { e.native.target.style.cursor = barras.length ? "pointer" : "default"; },
        // clique na barra abre os contratos daquele mês
        onClick: (e, barras) => {
          if (!barras.length) return;
          const chave = chaves[barras[0].index];
          const lista = contratos.filter((c) => temGrupo(c, grupo) &&
            (chave === "sem-data" ? !c[campoData] : (c[campoData] || "").startsWith(chave)));
          abrirDetalhe(`${tituloDetalhe} – ${rotulos[barras[0].index]}`, lista);
        },
      },
    });
  }

  // Vencimento: agrupado pelo mês do Fim | Reajuste: agrupado pelo Mês/Ano do reajuste
  graficoTratativa("grafico-vencimento", cor("--barra-vencimento"), "vencimento", "fim", "Tratativas de vencimento");
  graficoTratativa("grafico-reajuste", cor("--barra-reajuste"), "reajuste", "reajuste", "Tratativas de reajuste");

  // ---------------- gráfico de índices ----------------
  const canvas = document.getElementById("grafico-indices");
  if (canvas && window.Chart && indices.length) {
    new Chart(canvas, {
      type: "line",
      data: {
        labels: indices.map((i) => i.rotulo),
        datasets: [
          { label: "IPCA", data: indices.map((i) => i.ipca), borderColor: cor("--serie-1"), backgroundColor: cor("--serie-1") },
          { label: "IGP-M", data: indices.map((i) => i.igpm), borderColor: cor("--serie-2"), backgroundColor: cor("--serie-2") },
          { label: "IPC/FIPE (alim. fora do domicílio)", data: indices.map((i) => i.ipc_fipe), borderColor: cor("--serie-3"), backgroundColor: cor("--serie-3") },
        ],
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        elements: { line: { borderWidth: 2, tension: 0.3 }, point: { radius: 2, hoverRadius: 5 } },
        plugins: {
          legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8, color: cor("--texto-2") } },
          tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y?.toLocaleString("pt-BR")}%` } },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: cor("--texto-2") } },
          y: { grid: { color: cor("--borda") }, ticks: { color: cor("--texto-2"), callback: (v) => v + "%" } },
        },
      },
    });
  } else if (canvas) {
    canvas.parentElement.innerHTML = '<div class="vazio">Gráfico indisponível (arquivo do Chart.js não encontrado).</div>';
  }
})();