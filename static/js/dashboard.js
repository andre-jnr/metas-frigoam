(function () {
    var filtroMes = document.getElementById("filtro-mes");
    var filtroAno = document.getElementById("filtro-ano");
    var btnAtualizar = document.getElementById("btn-atualizar");
    var autoRefreshSelect = document.getElementById("auto-refresh-select");
    var summaryGrid = document.getElementById("summary-grid");
    var setoresGrid = document.getElementById("setores-grid");
    var lastUpdateText = document.getElementById("last-update-text").querySelector("span");

    var MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
    var autoRefreshTimer = null;

    function popularFiltros() {
        MESES.forEach(function (nome, idx) {
            var opt = document.createElement("option");
            opt.value = idx + 1;
            opt.textContent = nome;
            filtroMes.appendChild(opt);
        });
        var anoAtual = window.DM_CONFIG.anoAtual;
        for (var a = anoAtual + 1; a >= anoAtual - 4; a--) {
            var opt = document.createElement("option");
            opt.value = a;
            opt.textContent = a;
            filtroAno.appendChild(opt);
        }
        filtroMes.value = window.DM_CONFIG.mesAtual;
        filtroAno.value = anoAtual;
    }

    function skeletonCards(qtd) {
        setoresGrid.innerHTML = "";
        for (var i = 0; i < qtd; i++) {
            var card = document.createElement("div");
            card.className = "surface-card setor-card-skeleton";
            card.innerHTML =
                '<div class="skeleton skeleton-line" style="width:50%;height:14px;margin-top:18px;"></div>' +
                '<div class="skeleton skeleton-circle"></div>' +
                '<div class="skeleton skeleton-line"></div>' +
                '<div class="skeleton skeleton-line" style="width:40%"></div>';
            setoresGrid.appendChild(card);
        }
    }

    function skeletonSummary() {
        summaryGrid.innerHTML = "";
        for (var i = 0; i < 3; i++) {
            var card = document.createElement("div");
            card.className = "surface-card summary-card";
            card.innerHTML = '<div class="skeleton skeleton-line" style="width:60%"></div><div class="skeleton skeleton-line" style="width:40%;height:22px;"></div>';
            summaryGrid.appendChild(card);
        }
    }

    var SUMMARY_DEFS = [
        { key: "setores_no_ritmo", label: "Setores no Ritmo", tone: "accent", icon: '<path d="M20 6 9 17l-5-5"/>' },
        { key: "setores_abaixo", label: "Setores Abaixo", tone: "warning", icon: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>' },
        { key: "metas_batidas", label: "Metas Batidas", tone: "success", icon: '<path d="m8 14 2.5 2.5L16 11"/><circle cx="12" cy="12" r="10"/>' },
    ];

    function renderSummary(resumo) {
        summaryGrid.innerHTML = "";
        SUMMARY_DEFS.forEach(function (def) {
            var card = document.createElement("div");
            card.className = "surface-card summary-card fade-in";
            var valueEl = document.createElement("div");
            valueEl.className = "summary-value";
            card.innerHTML =
                '<div class="summary-icon tone-' + def.tone + '"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + def.icon + "</svg></div>" +
                '<div class="summary-label">' + def.label + "</div>";
            card.appendChild(valueEl);
            summaryGrid.appendChild(card);

            var raw = Number(resumo[def.key] || 0);
            var suffix = "/" + resumo.total_setores;
            countUp(valueEl, raw, { duration: 700, formatter: function (v) { return Math.round(v) + suffix; } });
        });
    }

    function renderSetorCard(setor) {
        var card = document.createElement("div");
        var statusClass = "status-" + setor.status.toLowerCase().replace(/_/g, "-");
        card.className = "surface-card setor-card fade-in " + statusClass + (setor.tem_meta ? "" : " sem-meta");
        card.addEventListener("click", function () {
            window.location.href = "/setor/" + setor.id + "?ano=" + window.DM_CONFIG.anoSelecionado + "&mes=" + window.DM_CONFIG.mesSelecionado;
        });

        var meta = Gauge.STATUS_META[setor.status] || Gauge.STATUS_META.ABAIXO_DO_RITMO;
        var header = document.createElement("div");
        header.className = "setor-card-header";
        header.innerHTML =
            "<span>" + setor.nome + "</span>" +
            (setor.estrela ? '<svg class="setor-star pop" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.6L22 9.6l-5 4.7L18.2 22 12 18.3 5.8 22 7 14.3l-5-4.7 7.1-1z"/></svg>' : "");
        card.appendChild(header);

        var modo = window.DM_CONFIG.modo || "percentual";

        var gaugeContainer = document.createElement("div");
        card.appendChild(gaugeContainer);
        Gauge.render(gaugeContainer, {
            percentRealizado: setor.percentual_realizado,
            percentEsperado: setor.percentual_esperado,
            status: setor.status,
            size: 190,
            modo: modo,
            valorRealizado: Number(setor.venda_realizada),
        });

        var statusEl = document.createElement("div");
        statusEl.className = "gauge-status " + meta.badge;
        statusEl.style.marginTop = "-6px";
        statusEl.textContent = setor.tem_meta ? meta.label : "Sem meta cadastrada";
        card.appendChild(statusEl);

        var esperadoTexto, diferencaTexto, diferencaPositiva;
        if (modo === "valor") {
            esperadoTexto = Fmt.brlCompact(setor.valor_esperado);
            var difValor = Number(setor.venda_realizada) - Number(setor.valor_esperado);
            diferencaTexto = Fmt.brlCompactSigned(difValor);
            diferencaPositiva = difValor >= 0;
        } else {
            esperadoTexto = Fmt.pct(setor.percentual_esperado);
            var difPct = Number(setor.diferenca);
            diferencaTexto = Fmt.pp(difPct);
            diferencaPositiva = difPct >= 0;
        }

        var metrics = document.createElement("div");
        metrics.className = "setor-card-metrics";
        metrics.innerHTML =
            '<div class="metrics-row metrics-row-money">' +
            '<div><div class="metric-label">Realizado</div><div class="metric-value">' + Fmt.brlCompact(setor.venda_realizada) + "</div></div>" +
            '<div><div class="metric-label">Meta</div><div class="metric-value">' + Fmt.brlCompact(setor.meta_final) + "</div></div>" +
            "</div>" +
            '<div class="metrics-row">' +
            '<div><div class="metric-label">Esperado hoje</div><div class="metric-value">' + esperadoTexto + "</div></div>" +
            '<div><div class="metric-label">Diferença</div><div class="metric-value ' + (diferencaPositiva ? "positive" : "negative") + '">' + diferencaTexto + "</div></div>" +
            "</div>";
        card.appendChild(metrics);

        return card;
    }

    function renderSetores(setores) {
        setoresGrid.innerHTML = "";
        if (!setores.length) {
            setoresGrid.innerHTML =
                '<div class="empty-state" style="grid-column: 1/-1;">' +
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>' +
                "<div>Nenhum setor ativo cadastrado ainda.</div>" +
                '<a class="btn btn-primary btn-sm" href="/setores">Cadastrar setor</a>' +
                "</div>";
            return;
        }
        setores.forEach(function (setor) {
            setoresGrid.appendChild(renderSetorCard(setor));
        });
    }

    async function carregarDashboard(forcar) {
        var ano = Number(filtroAno.value);
        var mes = Number(filtroMes.value);
        window.DM_CONFIG.anoSelecionado = ano;
        window.DM_CONFIG.mesSelecionado = mes;

        if (forcar) {
            btnAtualizar.disabled = true;
            skeletonSummary();
            skeletonCards(10);
        }

        try {
            var url = "/api/dashboard?ano=" + ano + "&mes=" + mes + (forcar ? "&refresh=1" : "");
            var dados = await apiFetch(url);
            renderSummary(dados.resumo);
            renderSetores(dados.setores);
            lastUpdateText.textContent = "Última atualização: " + Fmt.dataHora(dados.atualizado_em);
            if (forcar) Toast.success("Dashboard atualizado.");
        } catch (e) {
            lastUpdateText.textContent = "Falha ao carregar dados.";
        } finally {
            btnAtualizar.disabled = false;
        }
    }

    function configurarAutoRefresh() {
        var salvo = localStorage.getItem("dm_auto_refresh") || "0";
        autoRefreshSelect.value = salvo;
        aplicarAutoRefresh(Number(salvo));
        autoRefreshSelect.addEventListener("change", function () {
            localStorage.setItem("dm_auto_refresh", autoRefreshSelect.value);
            aplicarAutoRefresh(Number(autoRefreshSelect.value));
        });
    }

    function aplicarAutoRefresh(ms) {
        if (autoRefreshTimer) clearInterval(autoRefreshTimer);
        if (ms > 0) {
            autoRefreshTimer = setInterval(function () { carregarDashboard(true); }, ms);
        }
    }

    popularFiltros();
    skeletonSummary();
    skeletonCards(10);
    carregarDashboard(false);

    filtroMes.addEventListener("change", function () { carregarDashboard(false); });
    filtroAno.addEventListener("change", function () { carregarDashboard(false); });
    btnAtualizar.addEventListener("click", function () { carregarDashboard(true); });
    configurarAutoRefresh();
})();
