(function () {
    var MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
    var filtroMes = document.getElementById("filtro-mes");
    var filtroAno = document.getElementById("filtro-ano");
    var gaugeContainer = document.getElementById("gauge-container");
    var heroMetrics = document.getElementById("hero-metrics");
    var rankingList = document.getElementById("ranking-list");
    var compareGrid = document.getElementById("compare-grid");
    var chartInstance = null;

    function popularFiltros() {
        MESES.forEach(function (nome, idx) {
            var opt = document.createElement("option");
            opt.value = idx + 1; opt.textContent = nome;
            filtroMes.appendChild(opt);
        });
        var anoAtual = window.DM_CONFIG.anoAtual;
        for (var a = anoAtual + 1; a >= anoAtual - 4; a--) {
            var opt = document.createElement("option");
            opt.value = a; opt.textContent = a;
            filtroAno.appendChild(opt);
        }
        var params = new URLSearchParams(window.location.search);
        filtroMes.value = params.get("mes") || window.DM_CONFIG.mesAtual;
        filtroAno.value = params.get("ano") || window.DM_CONFIG.anoAtual;
    }

    function renderHero(dados) {
        gaugeContainer.innerHTML = "";
        Gauge.render(gaugeContainer, {
            percentRealizado: dados.percentual_realizado,
            percentEsperado: dados.percentual_esperado,
            status: dados.status,
            size: 240,
        });
        var meta = Gauge.STATUS_META[dados.status] || Gauge.STATUS_META.ABAIXO_DO_RITMO;
        var statusEl = document.createElement("div");
        statusEl.className = "gauge-status " + meta.badge;
        statusEl.style.marginTop = "-10px";
        statusEl.style.textAlign = "center";
        statusEl.textContent = dados.tem_meta ? meta.label + (dados.estrela ? " ⭐" : "") : "Sem meta cadastrada";
        gaugeContainer.parentElement.appendChild(statusEl);

        var dif = Number(dados.diferenca);
        heroMetrics.innerHTML =
            metricBlock("Meta do mês", '<span class="money-value">' + Fmt.brl(dados.meta_final) + "</span>") +
            metricBlock("Venda realizada", '<span class="money-value">' + Fmt.brl(dados.venda_realizada) + "</span>") +
            metricBlock("Meta esperada até hoje", '<span class="money-value">' + Fmt.brl(dados.valor_esperado) + "</span> (" + Fmt.pct(dados.percentual_esperado) + ")") +
            metricBlock("Diferença", Fmt.pp(dif), dif >= 0 ? "positive" : "negative");
    }

    function metricBlock(label, value, cls) {
        return '<div class="metric-block"><div class="label">' + label + '</div><div class="value ' + (cls || "") + '">' + value + "</div></div>";
    }

    function renderChart(evolucao) {
        var ctx = document.getElementById("evolucao-chart").getContext("2d");
        var labels = evolucao.map(function (d) { return d.dia.slice(8, 10); });
        var acumulado = evolucao.map(function (d) { return Number(d.acumulado); });
        var metaAcumulada = evolucao.map(function (d) { return Number(d.meta_acumulada); });

        if (chartInstance) chartInstance.destroy();
        var corTexto = getComputedStyle(document.documentElement).getPropertyValue("--text-secondary").trim() || "#9aa5b8";
        var corGrid = getComputedStyle(document.documentElement).getPropertyValue("--border-soft").trim() || "#212a3a";

        chartInstance = new Chart(ctx, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Venda acumulada",
                        data: acumulado,
                        borderColor: "#5b8cff",
                        backgroundColor: "rgba(91,140,255,0.12)",
                        fill: true,
                        tension: 0.3,
                        pointRadius: 0,
                        borderWidth: 2.5,
                    },
                    {
                        label: "Meta acumulada",
                        data: metaAcumulada,
                        borderColor: "#6b7690",
                        borderDash: [6, 5],
                        fill: false,
                        tension: 0,
                        pointRadius: 0,
                        borderWidth: 1.75,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                animation: { duration: 700 },
                plugins: {
                    legend: { labels: { color: corTexto, usePointStyle: true, boxWidth: 8 } },
                    tooltip: {
                        callbacks: {
                            label: function (item) { return item.dataset.label + ": " + Fmt.brl(item.parsed.y); },
                        },
                    },
                },
                scales: {
                    x: { grid: { color: corGrid }, ticks: { color: corTexto } },
                    y: { grid: { color: corGrid }, ticks: { color: corTexto, callback: function (v) { return Fmt.brlCompact(v); } } },
                },
            },
        });
    }

    function renderRanking(ranking) {
        rankingList.innerHTML = "";
        if (!ranking.length) {
            rankingList.innerHTML = '<div class="text-muted">Nenhum grupo com venda no período.</div>';
            return;
        }
        var max = Math.max.apply(null, ranking.map(function (r) { return Number(r.total); }));
        ranking.forEach(function (r) {
            var row = document.createElement("div");
            row.className = "ranking-row";
            var pct = max > 0 ? (Number(r.total) / max) * 100 : 0;
            row.innerHTML =
                '<div class="ranking-name">' + r.descricao + '</div>' +
                '<div class="ranking-bar-track"><div class="ranking-bar-fill" style="width:0%"></div></div>' +
                '<div class="ranking-value money-value">' + Fmt.brlCompact(r.total) + "</div>";
            rankingList.appendChild(row);
            requestAnimationFrame(function () { row.querySelector(".ranking-bar-fill").style.width = pct + "%"; });
        });
    }

    function renderComparacao(dados) {
        var vendaAtual = Number(dados.venda_realizada);
        var vendaMesAnterior = Number(dados.comparacao.venda_mes_anterior);
        var vendaAnoAnterior = Number(dados.comparacao.venda_mesmo_mes_ano_anterior);

        function card(label, valorComparacao) {
            var delta = valorComparacao > 0 ? ((vendaAtual - valorComparacao) / valorComparacao) * 100 : null;
            var deltaHtml = delta == null ? "" : '<div class="delta" style="color:' + (delta >= 0 ? "var(--success)" : "var(--danger)") + '">' + (delta >= 0 ? "+" : "") + delta.toFixed(1).replace(".", ",") + "% neste período</div>";
            return '<div class="surface-card compare-card"><div class="label">' + label + '</div><div class="value money-value">' + Fmt.brl(valorComparacao) + "</div>" + deltaHtml + "</div>";
        }

        compareGrid.innerHTML =
            '<div class="surface-card compare-card"><div class="label">Este período</div><div class="value money-value">' + Fmt.brl(vendaAtual) + "</div></div>" +
            card("Mês anterior", vendaMesAnterior) +
            card("Mesmo mês ano anterior", vendaAnoAnterior);
    }

    async function carregar() {
        var ano = filtroAno.value, mes = filtroMes.value;
        try {
            var dados = await apiFetch("/api/dashboard/setor/" + window.DM_CONFIG.setorId + "?ano=" + ano + "&mes=" + mes);
            renderHero(dados);
            renderChart(dados.evolucao_diaria);
            renderRanking(dados.ranking_grupos);
            renderComparacao(dados);
        } catch (e) {
            heroMetrics.innerHTML = '<div class="text-muted">Não foi possível carregar os dados deste setor.</div>';
        }
    }

    popularFiltros();
    filtroMes.addEventListener("change", carregar);
    filtroAno.addEventListener("change", carregar);
    carregar();
})();
