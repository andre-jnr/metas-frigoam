/* Produtos sem movimentação — modal aberto a partir do Detalhamento de Vendas e Metas
   por Produto. Usa o mesmo mês/ano e o mesmo tipo de comparação da tabela de produtos. */
(function () {
    var btnAbrir = document.getElementById("sem-mov-btn");
    if (!btnAbrir || !window.DM_CONFIG || !window.DM_CONFIG.setorId) return;

    var modal = document.getElementById("sem-mov-modal");
    var periodoEl = document.getElementById("sem-mov-periodo");
    var resumoEl = document.getElementById("sem-mov-resumo");
    var tbody = document.getElementById("sem-mov-tbody");
    var busca = document.getElementById("sem-mov-busca");
    var checkAntigos = document.getElementById("sem-mov-antigos");
    var btnExportar = document.getElementById("sem-mov-exportar");
    var filtroMes = document.getElementById("filtro-mes");
    var filtroAno = document.getElementById("filtro-ano");
    var tipoComparacaoSelect = document.getElementById("produtos-tipo-comparacao");

    var MAX_LINHAS = 1000; // a Loja com o cadastro completo passa de 20 mil produtos
    var dados = null;
    var requisicao = 0; // descarta respostas antigas se o usuário trocar o filtro no meio

    function formatarData(iso) {
        if (!iso) return "—";
        var partes = iso.split("-");
        return partes[2] + "/" + partes[1] + "/" + partes[0];
    }

    function escapar(texto) {
        return String(texto).replace(/[&<>"]/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
        });
    }

    function linhasVazias(mensagem) {
        tbody.innerHTML = '<tr><td colspan="3"><div class="empty-state">' + mensagem + "</div></td></tr>";
    }

    function gruposFiltrados() {
        var termo = busca.value.trim().toLowerCase();
        if (!termo) return dados.grupos;
        return dados.grupos
            .map(function (g) {
                return {
                    descricao: g.descricao,
                    produtos: g.produtos.filter(function (p) {
                        return String(p.codigo).indexOf(termo) !== -1 || p.nome.toLowerCase().indexOf(termo) !== -1;
                    }),
                };
            })
            .filter(function (g) { return g.produtos.length; });
    }

    function render() {
        if (!dados) return;
        if (!dados.disponivel) {
            resumoEl.textContent = "";
            linhasVazias(escapar(dados.motivo));
            return;
        }
        var grupos = gruposFiltrados();
        var total = grupos.reduce(function (s, g) { return s + g.produtos.length; }, 0);
        resumoEl.textContent = total + " produto(s)" + (busca.value.trim() ? " encontrados de " + dados.total : "") +
            (dados.vendidos_desde ? " · venderam pela última vez a partir de " + formatarData(dados.vendidos_desde) : " · cadastro ativo completo");
        if (!total) {
            linhasVazias(busca.value.trim() ? "Nenhum produto encontrado para essa busca." : "Todos os produtos do setor tiveram venda em pelo menos um dos períodos.");
            return;
        }
        var html = "";
        var exibidos = 0;
        grupos.forEach(function (g) {
            if (exibidos >= MAX_LINHAS) return;
            html += '<tr class="produto-row-grupo" style="cursor:default;"><td colspan="2">' + escapar(g.descricao) +
                '</td><td style="text-align:right;">' + g.produtos.length + "</td></tr>";
            g.produtos.slice(0, MAX_LINHAS - exibidos).forEach(function (p) {
                html += '<tr class="produto-row-item"><td>' + p.codigo + "</td><td>" + escapar(p.nome) +
                    '</td><td style="text-align:right;">' + formatarData(p.ultima_venda) + "</td></tr>";
                exibidos++;
            });
        });
        if (total > exibidos) {
            html += '<tr><td colspan="3"><div class="empty-state">Mostrando ' + exibidos + " de " + total +
                " produtos. Use a busca para encontrar um produto ou exporte a lista completa.</div></td></tr>";
        }
        tbody.innerHTML = html;
    }

    async function carregar() {
        var id = ++requisicao;
        dados = null;
        resumoEl.textContent = "Buscando produtos do setor...";
        periodoEl.textContent = "";
        tbody.innerHTML = '<tr><td colspan="3"><div class="skeleton skeleton-line" style="margin:8px 0;"></div><div class="skeleton skeleton-line" style="margin:8px 0;"></div></td></tr>';
        var url = "/api/dashboard/setor/" + window.DM_CONFIG.setorId + "/produtos-sem-movimentacao?ano=" + filtroAno.value +
            "&mes=" + filtroMes.value + "&tipo_comparacao=" + tipoComparacaoSelect.value +
            (checkAntigos.checked ? "&incluir_antigos=1" : "");
        try {
            var resposta = await apiFetch(url);
            if (id !== requisicao) return;
            dados = resposta;
            periodoEl.textContent =
                "Sem venda em " + formatarData(dados.periodo_atual.inicio) + " – " + formatarData(dados.periodo_atual.fim) +
                " nem em " + formatarData(dados.periodo_comparativo.inicio) + " – " + formatarData(dados.periodo_comparativo.fim);
            render();
        } catch (e) {
            if (id !== requisicao) return;
            resumoEl.textContent = "";
            linhasVazias("Não foi possível carregar os produtos sem movimentação.");
        }
    }

    function csvEscape(valor) {
        var texto = String(valor == null ? "" : valor);
        if (/[";\r\n]/.test(texto)) texto = '"' + texto.replace(/"/g, '""') + '"';
        return texto;
    }

    function exportarCsv() {
        if (!dados || !dados.disponivel) { Toast.warning("Não há lista para exportar."); return; }
        var grupos = gruposFiltrados();
        var linhas = [["Codigo", "Produto", "Grupo", "Ultima venda"]];
        grupos.forEach(function (g) {
            g.produtos.forEach(function (p) {
                linhas.push([p.codigo, p.nome, g.descricao, p.ultima_venda ? formatarData(p.ultima_venda) : ""]);
            });
        });
        if (linhas.length === 1) { Toast.warning("Não há produtos para exportar."); return; }
        var conteudo = "﻿" + linhas.map(function (l) { return l.map(csvEscape).join(";"); }).join("\r\n");
        var url = URL.createObjectURL(new Blob([conteudo], { type: "text/csv;charset=utf-8;" }));
        var link = document.createElement("a");
        link.href = url;
        link.download = "produtos_sem_movimentacao_" + filtroAno.value + "-" + String(filtroMes.value).padStart(2, "0") + ".csv";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        Toast.success("Arquivo exportado. Abra no Excel (colunas separadas por ;).");
    }

    function abrir() {
        busca.value = "";
        modal.classList.add("open");
        carregar();
    }

    function fechar() {
        modal.classList.remove("open");
        requisicao++;
    }

    btnAbrir.addEventListener("click", abrir);
    document.getElementById("sem-mov-fechar").addEventListener("click", fechar);
    modal.addEventListener("click", function (ev) { if (ev.target === modal) fechar(); });
    document.addEventListener("keydown", function (ev) { if (ev.key === "Escape" && modal.classList.contains("open")) fechar(); });
    busca.addEventListener("input", render);
    checkAntigos.addEventListener("change", carregar);
    btnExportar.addEventListener("click", exportarCsv);
})();
