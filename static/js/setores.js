(function () {
    var DIAS_SEMANA = [
        { valor: 0, label: "Seg" }, { valor: 1, label: "Ter" }, { valor: 2, label: "Qua" },
        { valor: 3, label: "Qui" }, { valor: 4, label: "Sex" }, { valor: 5, label: "Sáb" }, { valor: 6, label: "Dom" },
    ];

    var tbody = document.getElementById("setores-tbody");

    var modal = document.getElementById("setor-modal");
    var modalTitle = document.getElementById("setor-modal-title");
    var idField = document.getElementById("setor-id");
    var nomeField = document.getElementById("setor-nome");
    var descricaoField = document.getElementById("setor-descricao");
    var ordemField = document.getElementById("setor-ordem");
    var gruposSearch = document.getElementById("grupos-search");
    var gruposChipsWrap = document.getElementById("grupos-chips-wrap");
    var gruposCheckboxList = document.getElementById("grupos-checkbox-list");
    var gruposCountLabel = document.getElementById("grupos-count-label");
    var pdvIncluidosField = document.getElementById("setor-pdv-incluidos");
    var pdvExcluidosField = document.getElementById("setor-pdv-excluidos");
    var diasSemanaChipsWrap = document.getElementById("dias-semana-chips");

    var confirmModal = document.getElementById("confirm-modal");
    var confirmText = document.getElementById("confirm-modal-text");
    var confirmAction = null;

    var gruposDisponiveis = [];
    var subgruposPorGrupo = {}; // { grupoCodigo(number): [{codigo, descricao}, ...] }
    var gruposSelecionados = new Set(); // grupos SEM subgrupos cadastrados (fonte da verdade para esses)
    var subgruposSelecionados = new Map(); // grupoCodigo(number) -> Set(subgrupoCodigo) (fonte da verdade p/ grupos com filhos)
    var gruposExpandidos = new Set(); // apenas estado visual (accordion)
    var diasSemanaSelecionados = new Set();

    function abrirModal(el) { el.classList.add("open"); }
    function fecharModal(el) { el.classList.remove("open"); }

    function parsearListaNumeros(texto) {
        return (texto || "")
            .split(",")
            .map(function (v) { return v.trim(); })
            .filter(function (v) { return v !== ""; })
            .map(Number)
            .filter(function (v) { return !isNaN(v); });
    }

    async function carregarGruposDisponiveis() {
        if (gruposDisponiveis.length) return;
        gruposDisponiveis = await apiFetch("/api/grupos");
    }

    async function carregarSubgruposPorGrupo() {
        if (Object.keys(subgruposPorGrupo).length) return;
        var mapa = await apiFetch("/api/grupos-subgrupos");
        subgruposPorGrupo = {};
        Object.keys(mapa).forEach(function (chave) {
            subgruposPorGrupo[Number(chave)] = mapa[chave];
        });
    }

    function grupoTemFilhos(codigo) {
        return !!(subgruposPorGrupo[codigo] && subgruposPorGrupo[codigo].length);
    }

    // Grupo "completo" = checkbox do grupo marcado (inclui produtos futuros do grupo inteiro).
    function grupoEstaCompleto(codigo) {
        if (grupoTemFilhos(codigo)) {
            var set = subgruposSelecionados.get(codigo);
            return !!set && set.size > 0 && set.size === subgruposPorGrupo[codigo].length;
        }
        return gruposSelecionados.has(codigo);
    }

    // Grupo "selecionado" = completo OU parcialmente restrito por subgrupo (ainda faz parte do setor).
    function grupoEstaSelecionado(codigo) {
        if (grupoTemFilhos(codigo)) {
            var set = subgruposSelecionados.get(codigo);
            return !!set && set.size > 0;
        }
        return gruposSelecionados.has(codigo);
    }

    function alternarGrupo(codigo, marcar) {
        if (grupoTemFilhos(codigo)) {
            if (marcar) {
                subgruposSelecionados.set(codigo, new Set(subgruposPorGrupo[codigo].map(function (s) { return s.codigo; })));
            } else {
                subgruposSelecionados.delete(codigo);
            }
        } else if (marcar) {
            gruposSelecionados.add(codigo);
        } else {
            gruposSelecionados.delete(codigo);
        }
    }

    function alternarSubgrupo(grupoCodigo, subCodigo, marcar) {
        var set = subgruposSelecionados.get(grupoCodigo);
        if (!set) { set = new Set(); subgruposSelecionados.set(grupoCodigo, set); }
        if (marcar) set.add(subCodigo);
        else set.delete(subCodigo);
    }

    function renderGruposChecklist() {
        var termo = gruposSearch.value.trim().toLowerCase();
        var filtrados = gruposDisponiveis.filter(function (g) {
            return !termo || g.descricao.toLowerCase().indexOf(termo) !== -1;
        });
        gruposCheckboxList.innerHTML = "";
        if (!filtrados.length) {
            gruposCheckboxList.innerHTML = '<div class="checkbox-item text-muted">Nenhum grupo encontrado.</div>';
            return;
        }
        filtrados.forEach(function (g) {
            var temFilhos = grupoTemFilhos(g.codigo);

            var item = document.createElement(temFilhos ? "div" : "label");
            item.className = "checkbox-item";

            var expandBtn = null;
            if (temFilhos) {
                expandBtn = document.createElement("button");
                expandBtn.type = "button";
                expandBtn.className = "grupo-expand-btn" + (gruposExpandidos.has(g.codigo) ? " expanded" : "");
                expandBtn.setAttribute("aria-label", "Expandir subgrupos");
                expandBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg>';
                expandBtn.addEventListener("click", function () {
                    if (gruposExpandidos.has(g.codigo)) gruposExpandidos.delete(g.codigo);
                    else gruposExpandidos.add(g.codigo);
                    renderGruposChecklist();
                });
                item.appendChild(expandBtn);
            }

            var checked = grupoEstaCompleto(g.codigo);
            var descricaoHtml = g.descricao + (temFilhos
                ? ' <span class="text-muted" style="font-size:11px;">(' + subgruposPorGrupo[g.codigo].length + ' subgrupos)</span>'
                : "");

            if (temFilhos) {
                var label = document.createElement("label");
                label.className = "flex gap-8";
                label.style.cssText = "align-items:center; flex:1; cursor:pointer;";
                label.innerHTML = '<input type="checkbox" ' + (checked ? "checked" : "") + "><span>" + descricaoHtml + "</span>";
                label.querySelector("input").addEventListener("change", function (ev) {
                    alternarGrupo(g.codigo, ev.target.checked);
                    renderGruposChecklist();
                    renderChips();
                });
                item.appendChild(label);
            } else {
                item.innerHTML = '<input type="checkbox" ' + (checked ? "checked" : "") + ' data-codigo="' + g.codigo + '"><span>' + descricaoHtml + "</span>";
                item.querySelector("input").addEventListener("change", function (ev) {
                    alternarGrupo(g.codigo, ev.target.checked);
                    renderChips();
                });
            }

            gruposCheckboxList.appendChild(item);

            if (temFilhos && gruposExpandidos.has(g.codigo)) {
                var setSelecionado = subgruposSelecionados.get(g.codigo) || new Set();
                subgruposPorGrupo[g.codigo].forEach(function (sub) {
                    var subItem = document.createElement("label");
                    subItem.className = "checkbox-item subgrupo-item";
                    var subChecked = setSelecionado.has(sub.codigo);
                    var descricaoSub = sub.codigo === 0 ? '<em class="text-muted">' + sub.descricao + "</em>" : sub.descricao;
                    subItem.innerHTML = '<input type="checkbox" ' + (subChecked ? "checked" : "") + "><span>" + descricaoSub + "</span>";
                    subItem.querySelector("input").addEventListener("change", function (ev) {
                        alternarSubgrupo(g.codigo, sub.codigo, ev.target.checked);
                        renderGruposChecklist();
                        renderChips();
                    });
                    gruposCheckboxList.appendChild(subItem);
                });
            }
        });
    }

    function renderChips() {
        var selecionados = gruposDisponiveis.filter(function (g) { return grupoEstaSelecionado(g.codigo); });
        gruposCountLabel.textContent = selecionados.length ? "(" + selecionados.length + " selecionados)" : "";
        if (!selecionados.length) { gruposChipsWrap.style.display = "none"; gruposChipsWrap.innerHTML = ""; return; }
        gruposChipsWrap.style.display = "flex";
        gruposChipsWrap.innerHTML = "";
        selecionados.forEach(function (g) {
            var label = g.descricao;
            if (grupoTemFilhos(g.codigo) && !grupoEstaCompleto(g.codigo)) {
                var qtd = (subgruposSelecionados.get(g.codigo) || new Set()).size;
                label += " (" + qtd + " subgrupo" + (qtd === 1 ? "" : "s") + ")";
            }
            var chip = document.createElement("span");
            chip.className = "chip";
            chip.innerHTML = label + '<button type="button" aria-label="Remover">&times;</button>';
            chip.querySelector("button").addEventListener("click", function () {
                gruposSelecionados.delete(g.codigo);
                subgruposSelecionados.delete(g.codigo);
                renderChips();
                renderGruposChecklist();
            });
            gruposChipsWrap.appendChild(chip);
        });
    }

    function renderDiasSemanaChips() {
        diasSemanaChipsWrap.innerHTML = "";
        DIAS_SEMANA.forEach(function (dia) {
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "btn btn-sm" + (diasSemanaSelecionados.has(dia.valor) ? " btn-primary" : " btn-ghost");
            btn.style.borderColor = "var(--border)";
            btn.textContent = dia.label;
            btn.addEventListener("click", function () {
                if (diasSemanaSelecionados.has(dia.valor)) diasSemanaSelecionados.delete(dia.valor);
                else diasSemanaSelecionados.add(dia.valor);
                renderDiasSemanaChips();
            });
            diasSemanaChipsWrap.appendChild(btn);
        });
    }

    async function abrirModalNovo() {
        modalTitle.textContent = "Novo Setor";
        idField.value = "";
        nomeField.value = "";
        descricaoField.value = "";
        ordemField.value = 0;
        gruposSelecionados = new Set();
        subgruposSelecionados = new Map();
        gruposExpandidos = new Set();
        diasSemanaSelecionados = new Set();
        pdvIncluidosField.value = "";
        pdvExcluidosField.value = "";
        gruposSearch.value = "";
        await carregarGruposDisponiveis();
        await carregarSubgruposPorGrupo();
        renderGruposChecklist();
        renderChips();
        renderDiasSemanaChips();
        abrirModal(modal);
        nomeField.focus();
    }

    async function abrirModalEditar(setorId) {
        modalTitle.textContent = "Editar Setor";
        var setor = await apiFetch("/api/setores/" + setorId);
        idField.value = setor.id;
        nomeField.value = setor.nome;
        descricaoField.value = setor.descricao || "";
        ordemField.value = setor.ordem_exibicao;
        diasSemanaSelecionados = new Set(setor.dias_semana_excluidos || []);
        pdvIncluidosField.value = (setor.pdv_incluidos || []).join(", ");
        pdvExcluidosField.value = (setor.pdv_excluidos || []).join(", ");
        gruposSearch.value = "";
        await carregarGruposDisponiveis();
        await carregarSubgruposPorGrupo();

        gruposSelecionados = new Set();
        subgruposSelecionados = new Map();
        gruposExpandidos = new Set();
        var narrowingPorGrupo = setor.subgrupos_por_grupo || {};
        (setor.grupo_codigos || []).forEach(function (codigo) {
            if (grupoTemFilhos(codigo)) {
                var narrowing = narrowingPorGrupo[codigo];
                if (narrowing && narrowing.length) {
                    // Setor com narrowing salvo: só os subgrupos explicitamente escolhidos.
                    subgruposSelecionados.set(codigo, new Set(narrowing));
                    gruposExpandidos.add(codigo);
                } else {
                    // Grupo "completo" (sem narrowing salvo, inclusive setores legados): todos os filhos.
                    subgruposSelecionados.set(codigo, new Set(subgruposPorGrupo[codigo].map(function (s) { return s.codigo; })));
                }
            } else {
                gruposSelecionados.add(codigo);
            }
        });

        renderGruposChecklist();
        renderChips();
        renderDiasSemanaChips();
        abrirModal(modal);
    }

    async function salvarSetor() {
        var nome = nomeField.value.trim();
        if (!nome) { Toast.warning("Informe o nome do setor."); return; }

        var pdvIncluidos = parsearListaNumeros(pdvIncluidosField.value);
        var pdvExcluidos = parsearListaNumeros(pdvExcluidosField.value);

        var grupoCodigosFinal = Array.from(gruposSelecionados);
        var subgruposPorGrupoFinal = {};
        subgruposSelecionados.forEach(function (set, grupoCodigo) {
            if (!set.size) return;
            grupoCodigosFinal.push(grupoCodigo);
            var totalFilhos = (subgruposPorGrupo[grupoCodigo] || []).length;
            if (set.size < totalFilhos) {
                subgruposPorGrupoFinal[grupoCodigo] = Array.from(set);
            }
        });

        var payload = {
            nome: nome,
            descricao: descricaoField.value.trim(),
            ordem_exibicao: Number(ordemField.value) || 0,
            grupo_codigos: grupoCodigosFinal,
            subgrupos_por_grupo: subgruposPorGrupoFinal,
            pdv_incluidos: pdvIncluidos.length ? pdvIncluidos : null,
            pdv_excluidos: pdvExcluidos.length ? pdvExcluidos : null,
            dias_semana_excluidos: diasSemanaSelecionados.size ? Array.from(diasSemanaSelecionados) : null,
        };

        if (!grupoCodigosFinal.length && !pdvIncluidos.length && !pdvExcluidos.length && !diasSemanaSelecionados.size) {
            Toast.warning("Selecione ao menos um grupo de produto ou configure um filtro de PDV.");
            return;
        }

        var id = idField.value;
        try {
            if (id) {
                await apiFetch("/api/setores/" + id, { method: "PUT", body: JSON.stringify(payload) });
                Toast.success("Setor atualizado com sucesso.");
            } else {
                await apiFetch("/api/setores", { method: "POST", body: JSON.stringify(payload) });
                Toast.success("Setor criado com sucesso.");
            }
            fecharModal(modal);
            carregarSetores();
        } catch (e) { /* erro já exibido via toast */ }
    }

    function badgeStatus(ativo) {
        return ativo ? '<span class="badge badge-success">Ativo</span>' : '<span class="badge badge-neutral">Inativo</span>';
    }

    function descreverFiltroPdv(setor) {
        var partes = [];
        if (setor.pdv_incluidos && setor.pdv_incluidos.length) partes.push("PDV " + setor.pdv_incluidos.join(", "));
        if (setor.pdv_excluidos && setor.pdv_excluidos.length) partes.push("exceto PDV " + setor.pdv_excluidos.join(", "));
        if (setor.dias_semana_excluidos && setor.dias_semana_excluidos.length) {
            var nomes = setor.dias_semana_excluidos.map(function (v) {
                var dia = DIAS_SEMANA.find(function (d) { return d.valor === v; });
                return dia ? dia.label : v;
            });
            partes.push("sem " + nomes.join("/"));
        }
        return partes.length ? '<span class="badge badge-neutral">' + partes.join(" · ") + "</span>" : '<span class="text-muted">—</span>';
    }

    function renderLinha(setor) {
        var tr = document.createElement("tr");
        tr.innerHTML =
            "<td><strong>" + setor.nome + "</strong>" + (setor.descricao ? '<div class="text-muted" style="font-size:11.5px;margin-top:2px;">' + setor.descricao + "</div>" : "") + "</td>" +
            "<td>" + (setor.grupos_count ? setor.grupos_count + " grupo" + (setor.grupos_count === 1 ? "" : "s") + (setor.tem_filtro_subgrupo ? " <span class=\"text-muted\" style=\"font-size:11px;\">(com subgrupo)</span>" : "") : '<span class="text-muted">todos os produtos</span>') + "</td>" +
            "<td>" + descreverFiltroPdv(setor) + "</td>" +
            "<td>" + badgeStatus(setor.ativo) + "</td>" +
            "<td>" + setor.ordem_exibicao + "</td>" +
            '<td style="text-align:right;"></td>';

        var acoes = document.createElement("div");
        acoes.className = "flex gap-8";
        acoes.style.justifyContent = "flex-end";

        var btnEditar = document.createElement("button");
        btnEditar.className = "btn btn-sm btn-ghost";
        btnEditar.textContent = "Editar";
        btnEditar.addEventListener("click", function () { abrirModalEditar(setor.id); });

        var btnToggle = document.createElement("button");
        btnToggle.className = "btn btn-sm btn-ghost";
        btnToggle.textContent = setor.ativo ? "Desativar" : "Ativar";
        btnToggle.addEventListener("click", async function () {
            try {
                await apiFetch("/api/setores/" + setor.id + "/ativo", { method: "PATCH", body: JSON.stringify({ ativo: !setor.ativo }) });
                Toast.success(setor.ativo ? "Setor desativado." : "Setor ativado.");
                carregarSetores();
            } catch (e) {}
        });

        var btnExcluir = document.createElement("button");
        btnExcluir.className = "btn btn-sm btn-danger";
        btnExcluir.textContent = "Excluir";
        btnExcluir.addEventListener("click", function () {
            confirmText.textContent = 'Tem certeza que deseja excluir o setor "' + setor.nome + '"? As metas e associações de grupo deste setor também serão removidas.';
            confirmAction = async function () {
                try {
                    await apiFetch("/api/setores/" + setor.id, { method: "DELETE" });
                    Toast.success("Setor excluído.");
                    fecharModal(confirmModal);
                    carregarSetores();
                } catch (e) {}
            };
            abrirModal(confirmModal);
        });

        acoes.appendChild(btnEditar);
        acoes.appendChild(btnToggle);
        acoes.appendChild(btnExcluir);
        tr.lastElementChild.appendChild(acoes);
        return tr;
    }

    async function carregarSetores() {
        tbody.innerHTML = '<tr><td colspan="6"><div class="skeleton skeleton-line" style="margin:8px 0;"></div></td></tr>';
        try {
            var setores = await apiFetch("/api/setores");
            tbody.innerHTML = "";
            if (!setores.length) {
                tbody.innerHTML =
                    '<tr><td colspan="6"><div class="empty-state">' +
                    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h18M3 12h18M3 17h18"/></svg>' +
                    "<div>Nenhum setor cadastrado ainda.</div></div></td></tr>";
                return;
            }
            setores.forEach(function (s) { tbody.appendChild(renderLinha(s)); });
        } catch (e) {
            tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state">Não foi possível carregar os setores.</div></td></tr>';
        }
    }

    document.getElementById("btn-novo-setor").addEventListener("click", abrirModalNovo);
    document.getElementById("setor-modal-close").addEventListener("click", function () { fecharModal(modal); });
    document.getElementById("setor-modal-cancel").addEventListener("click", function () { fecharModal(modal); });
    document.getElementById("setor-modal-save").addEventListener("click", salvarSetor);
    gruposSearch.addEventListener("input", renderGruposChecklist);

    document.getElementById("btn-selecionar-todos-grupos").addEventListener("click", async function () {
        await carregarGruposDisponiveis();
        await carregarSubgruposPorGrupo();
        gruposDisponiveis.forEach(function (g) { alternarGrupo(g.codigo, true); });
        renderGruposChecklist();
        renderChips();
    });
    document.getElementById("btn-limpar-grupos").addEventListener("click", function () {
        gruposSelecionados = new Set();
        subgruposSelecionados = new Map();
        renderGruposChecklist();
        renderChips();
    });

    document.getElementById("confirm-modal-cancel").addEventListener("click", function () { fecharModal(confirmModal); });
    document.getElementById("confirm-modal-ok").addEventListener("click", function () { if (confirmAction) confirmAction(); });

    [modal, confirmModal].forEach(function (overlay) {
        overlay.addEventListener("click", function (ev) { if (ev.target === overlay) fecharModal(overlay); });
    });

    carregarSetores();
})();
