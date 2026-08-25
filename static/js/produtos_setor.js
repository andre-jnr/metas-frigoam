/* Detalhamento de Vendas e Metas por Produto — tabela drill-down da página de
   detalhe do setor. Self-contained: lê os mesmos filtros de mês/ano já
   existentes na página e tem seus próprios controles de comparação/métrica. */
(function () {
    var filtroMes = document.getElementById("filtro-mes");
    var filtroAno = document.getElementById("filtro-ano");
    var periodoInfo = document.getElementById("produtos-periodo-info");
    var tipoComparacaoSelect = document.getElementById("produtos-tipo-comparacao");
    var tbody = document.getElementById("produtos-tbody");
    var paginacaoWrap = document.getElementById("produtos-paginacao");
    var paginacaoInfo = document.getElementById("produtos-paginacao-info");
    var btnPagAnterior = document.getElementById("produtos-pag-anterior");
    var btnPagProxima = document.getElementById("produtos-pag-proxima");
    var btnExportar = document.getElementById("produtos-exportar-btn");
    var thComparativa = document.getElementById("th-comparativa");
    var thAtual = document.getElementById("th-atual");
    var thVariacao = document.getElementById("th-variacao");

    if (!tbody || !window.DM_CONFIG || !window.DM_CONFIG.setorId) return;

    var PAGE_SIZE = 50;
    var COLUNAS_TEXTO = { codigo: false, nome: true, venda_comparativa: false, venda_atual: false, variacao_valor: false, variacao_percentual: false };

    var estado = {
        dados: null,
        viewMode: "grupo",
        metrica: "valor",
        gruposExpandidos: new Set(),
        sortCol: "venda_atual",
        sortDir: "desc",
        pagina: 1,
        tipoComparacaoDefinidoPeloUsuario: false,
    };

    var ICONE_SETA_CIMA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
    var ICONE_SETA_BAIXO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M19 12l-7 7-7-7"/></svg>';
    var ICONE_CHEVRON = '<svg class="produto-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg>';
    var ICONE_TRACO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/></svg>';

    function formatarData(iso) {
        if (!iso) return "--";
        var partes = iso.split("-");
        return partes[2] + "/" + partes[1] + "/" + partes[0];
    }

    function formatarPercentualSinalizado(v) {
        return (v >= 0 ? "+" : "") + Fmt.pct(v);
    }

    function formatarValorPrincipal(v) {
        return estado.metrica === "quantidade" ? Fmt.numero(v) : Fmt.brlCompact(v);
    }

    function formatarVariacaoPrincipal(v) {
        return estado.metrica === "quantidade" ? Fmt.numeroSinalizado(v) : Fmt.brlCompactSigned(v);
    }

    function classeValorPrincipal() {
        return estado.metrica === "quantidade" ? "" : "money-value";
    }

    function variacaoBadgeHtml(valorTexto, formatter) {
        if (valorTexto == null) {
            return '<span class="variacao-badge neutra">' + ICONE_TRACO + "—</span>";
        }
        var valor = Number(valorTexto);
        var classe = valor > 0 ? "positiva" : valor < 0 ? "negativa" : "neutra";
        var icone = valor > 0 ? ICONE_SETA_CIMA : valor < 0 ? ICONE_SETA_BAIXO : ICONE_TRACO;
        return '<span class="variacao-badge ' + classe + '">' + icone + formatter(valor) + "</span>";
    }

    function linhaProdutoHtml(p) {
        var classeMoney = classeValorPrincipal();
        return (
            '<tr class="produto-row-item">' +
            "<td>" + p.codigo + "</td>" +
            "<td>" + p.nome + "</td>" +
            '<td class="' + classeMoney + '" style="text-align:right;">' + formatarValorPrincipal(p.venda_comparativa) + "</td>" +
            '<td class="' + classeMoney + '" style="text-align:right;">' + formatarValorPrincipal(p.venda_atual) + "</td>" +
            '<td class="' + classeMoney + '" style="text-align:right;">' + variacaoBadgeHtml(p.variacao_valor, formatarVariacaoPrincipal) + "</td>" +
            '<td style="text-align:right;">' + variacaoBadgeHtml(p.variacao_percentual, formatarPercentualSinalizado) + "</td>" +
            "</tr>"
        );
    }

    function ordenar(lista) {
        var col = estado.sortCol, dir = estado.sortDir, ehTexto = COLUNAS_TEXTO[col];
        var copia = lista.slice();
        copia.sort(function (a, b) {
            var va = a[col], vb = b[col];
            if (va == null && vb == null) return 0;
            if (va == null) return 1;
            if (vb == null) return -1;
            var cmp = ehTexto ? String(va).localeCompare(String(vb), "pt-BR") : Number(va) - Number(vb);
            return dir === "asc" ? cmp : -cmp;
        });
        return copia;
    }

    function renderCabecalhos() {
        var rotulo = estado.metrica === "quantidade" ? "Qtd." : "Venda";
        thComparativa.childNodes[0].textContent = rotulo + " Comparativa ";
        thAtual.childNodes[0].textContent = rotulo + " Atual ";
        thVariacao.childNodes[0].textContent = estado.metrica === "quantidade" ? "Variação (Qtd.) " : "Variação (R$) ";
    }

    function renderCabecalhoSort() {
        document.querySelectorAll("#produtos-table th.sortable").forEach(function (th) {
            var arrow = th.querySelector(".sort-arrow");
            if (th.dataset.sort === estado.sortCol) {
                arrow.textContent = estado.sortDir === "asc" ? "▲" : "▼";
                arrow.classList.add("active");
            } else {
                arrow.textContent = "";
                arrow.classList.remove("active");
            }
        });
    }

    function renderPorGrupo() {
        paginacaoWrap.style.display = "none";
        var grupos = estado.dados.grupos;
        if (!grupos.length) {
            tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state">Nenhum produto vendido neste período.</div></td></tr>';
            return;
        }
        var classeMoney = classeValorPrincipal();
        var html = "";
        grupos.forEach(function (g) {
            var expandido = estado.gruposExpandidos.has(g.grupo_codigo);
            html +=
                '<tr class="produto-row-grupo' + (expandido ? " expandido" : "") + '" data-grupo="' + g.grupo_codigo + '">' +
                "<td colspan=\"2\">" + ICONE_CHEVRON + g.descricao + " <span class=\"text-muted\" style=\"font-weight:600;\">(" + g.produtos.length + " produtos)</span></td>" +
                '<td class="' + classeMoney + '" style="text-align:right;">' + formatarValorPrincipal(g.venda_comparativa) + "</td>" +
                '<td class="' + classeMoney + '" style="text-align:right;">' + formatarValorPrincipal(g.venda_atual) + "</td>" +
                '<td class="' + classeMoney + '" style="text-align:right;">' + variacaoBadgeHtml(g.variacao_valor, formatarVariacaoPrincipal) + "</td>" +
                '<td style="text-align:right;">' + variacaoBadgeHtml(g.variacao_percentual, formatarPercentualSinalizado) + "</td>" +
                "</tr>";
            if (expandido) {
                ordenar(g.produtos).forEach(function (p) { html += linhaProdutoHtml(p); });
            }
        });
        tbody.innerHTML = html;

        tbody.querySelectorAll(".produto-row-grupo").forEach(function (tr) {
            tr.addEventListener("click", function () {
                var grupoCodigo = tr.dataset.grupo === "null" ? null : Number(tr.dataset.grupo);
                if (estado.gruposExpandidos.has(grupoCodigo)) estado.gruposExpandidos.delete(grupoCodigo);
                else estado.gruposExpandidos.add(grupoCodigo);
                renderPorGrupo();
            });
        });
    }

    function todosOsProdutos() {
        var todos = [];
        estado.dados.grupos.forEach(function (g) {
            g.produtos.forEach(function (p) {
                todos.push(Object.assign({ grupo_descricao: g.descricao }, p));
            });
        });
        return todos;
    }

    function renderFlat() {
        var todos = ordenar(todosOsProdutos());

        if (!todos.length) {
            paginacaoWrap.style.display = "none";
            tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state">Nenhum produto vendido neste período.</div></td></tr>';
            return;
        }

        var totalPaginas = Math.max(1, Math.ceil(todos.length / PAGE_SIZE));
        estado.pagina = Math.min(estado.pagina, totalPaginas);
        var inicio = (estado.pagina - 1) * PAGE_SIZE;
        var pagina = todos.slice(inicio, inicio + PAGE_SIZE);

        tbody.innerHTML = pagina.map(linhaProdutoHtml).join("");

        paginacaoWrap.style.display = "flex";
        paginacaoInfo.textContent = "Mostrando " + (inicio + 1) + "–" + (inicio + pagina.length) + " de " + todos.length + " produtos";
        btnPagAnterior.disabled = estado.pagina <= 1;
        btnPagProxima.disabled = estado.pagina >= totalPaginas;
    }

    function renderTabela() {
        renderCabecalhos();
        renderCabecalhoSort();
        if (estado.viewMode === "grupo") renderPorGrupo();
        else renderFlat();
    }

    function renderPeriodoInfo() {
        var d = estado.dados;
        periodoInfo.textContent =
            "Período atual: " + formatarData(d.periodo_atual.inicio) + " – " + formatarData(d.periodo_atual.fim) +
            "  ·  Comparativo: " + formatarData(d.periodo_comparativo.inicio) + " – " + formatarData(d.periodo_comparativo.fim);
    }

    async function carregar() {
        var ano = filtroAno.value, mes = filtroMes.value;
        tbody.innerHTML = '<tr><td colspan="6"><div class="skeleton skeleton-line" style="margin:8px 0;"></div></td></tr>';
        periodoInfo.textContent = "Carregando períodos...";
        paginacaoWrap.style.display = "none";

        var url = "/api/dashboard/setor/" + window.DM_CONFIG.setorId + "/produtos?ano=" + ano + "&mes=" + mes + "&metrica=" + estado.metrica;
        if (estado.tipoComparacaoDefinidoPeloUsuario) {
            url += "&tipo_comparacao=" + tipoComparacaoSelect.value;
        }

        try {
            var dados = await apiFetch(url);
            estado.dados = dados;
            estado.gruposExpandidos = new Set();
            estado.pagina = 1;
            tipoComparacaoSelect.value = dados.tipo_comparacao;
            renderPeriodoInfo();
            renderTabela();
        } catch (e) {
            periodoInfo.textContent = "";
            tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state">Não foi possível carregar o detalhamento por produto.</div></td></tr>';
        }
    }

    function csvEscape(valor) {
        var texto = String(valor == null ? "" : valor);
        if (/[";\r\n]/.test(texto)) {
            texto = '"' + texto.replace(/"/g, '""') + '"';
        }
        return texto;
    }

    function exportarCsv() {
        if (!estado.dados) { Toast.warning("Aguarde os dados carregarem antes de exportar."); return; }
        var todos = ordenar(todosOsProdutos());
        if (!todos.length) { Toast.warning("Não há produtos para exportar neste período."); return; }

        var rotulo = estado.metrica === "quantidade" ? "Qtd" : "Venda (R$)";
        var cabecalho = ["Codigo", "Produto", "Grupo", rotulo + " Comparativa", rotulo + " Atual", "Variacao", "Variacao (%)"];
        var linhas = [cabecalho];
        todos.forEach(function (p) {
            linhas.push([
                p.codigo,
                p.nome,
                p.grupo_descricao,
                String(p.venda_comparativa).replace(".", ","),
                String(p.venda_atual).replace(".", ","),
                String(p.variacao_valor).replace(".", ","),
                p.variacao_percentual == null ? "" : String(p.variacao_percentual).replace(".", ","),
            ]);
        });

        var conteudo = "﻿" + linhas.map(function (linha) {
            return linha.map(csvEscape).join(";");
        }).join("\r\n");

        var blob = new Blob([conteudo], { type: "text/csv;charset=utf-8;" });
        var url = URL.createObjectURL(blob);
        var nomeArquivo = "detalhamento_produtos_" + filtroAno.value + "-" + String(filtroMes.value).padStart(2, "0") + "_" + estado.metrica + ".csv";

        var link = document.createElement("a");
        link.href = url;
        link.download = nomeArquivo;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        Toast.success("Arquivo exportado. Abra no Excel (colunas separadas por ; e decimais com vírgula).");
    }

    document.querySelectorAll(".produtos-view-btn").forEach(function (btn) {
        if (btn.dataset.view === estado.viewMode) btn.classList.add("btn-primary");
        btn.addEventListener("click", function () {
            estado.viewMode = btn.dataset.view;
            document.querySelectorAll(".produtos-view-btn").forEach(function (b) { b.classList.toggle("btn-primary", b === btn); });
            estado.pagina = 1;
            if (estado.dados) renderTabela();
        });
    });

    document.querySelectorAll(".produtos-metrica-btn").forEach(function (btn) {
        if (btn.dataset.metrica === estado.metrica) btn.classList.add("btn-primary");
        btn.addEventListener("click", function () {
            if (btn.dataset.metrica === estado.metrica) return;
            estado.metrica = btn.dataset.metrica;
            document.querySelectorAll(".produtos-metrica-btn").forEach(function (b) { b.classList.toggle("btn-primary", b === btn); });
            carregar();
        });
    });

    document.querySelectorAll("#produtos-table th.sortable").forEach(function (th) {
        th.addEventListener("click", function () {
            var col = th.dataset.sort;
            if (estado.sortCol === col) {
                estado.sortDir = estado.sortDir === "asc" ? "desc" : "asc";
            } else {
                estado.sortCol = col;
                estado.sortDir = COLUNAS_TEXTO[col] ? "asc" : "desc";
            }
            estado.pagina = 1;
            if (estado.dados) renderTabela();
        });
    });

    tipoComparacaoSelect.addEventListener("change", function () {
        estado.tipoComparacaoDefinidoPeloUsuario = true;
        carregar();
    });

    btnExportar.addEventListener("click", exportarCsv);
    btnPagAnterior.addEventListener("click", function () { estado.pagina--; renderFlat(); });
    btnPagProxima.addEventListener("click", function () { estado.pagina++; renderFlat(); });

    filtroMes.addEventListener("change", carregar);
    filtroAno.addEventListener("change", carregar);
    carregar();
})();
