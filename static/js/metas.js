(function () {
    var MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
    var BASE_LABELS = { MESMO_MES_ANO_ANTERIOR: "Mesmo mês ano anterior", MES_ANTERIOR: "Mês anterior", NAO_APLICAVEL: "—" };

    var tbody = document.getElementById("metas-tbody");
    var filtroSetor = document.getElementById("filtro-setor");
    var filtroMes = document.getElementById("filtro-mes");
    var filtroAno = document.getElementById("filtro-ano");

    var modal = document.getElementById("meta-modal");
    var modalTitle = document.getElementById("meta-modal-title");
    var idField = document.getElementById("meta-id");
    var setorField = document.getElementById("meta-setor");
    var mesField = document.getElementById("meta-mes");
    var anoField = document.getElementById("meta-ano");
    var valorField = document.getElementById("meta-valor");
    var percentualField = document.getElementById("meta-percentual");
    var baseField = document.getElementById("meta-base");
    var blocoValorFixo = document.getElementById("bloco-valor-fixo");
    var blocoPercentual = document.getElementById("bloco-percentual");
    var previewBox = document.getElementById("preview-box");
    var confirmarZeroWrap = document.getElementById("confirmar-zero-wrap");
    var confirmarZeroCheck = document.getElementById("meta-confirmar-zero");

    var confirmModal = document.getElementById("confirm-modal");
    var confirmText = document.getElementById("confirm-modal-text");
    var confirmAction = null;

    var setores = [];
    var tipoAtual = "VALOR_FIXO";
    var previewTimer = null;
    var ultimoPreview = null;

    function abrirModal(el) { el.classList.add("open"); }
    function fecharModal(el) { el.classList.remove("open"); }

    function popularSelects() {
        [filtroMes, mesField].forEach(function (sel) {
            MESES.forEach(function (nome, idx) {
                var opt = document.createElement("option");
                opt.value = idx + 1; opt.textContent = nome;
                sel.appendChild(opt);
            });
        });
        var anoAtual = window.DM_CONFIG.anoAtual;
        [filtroAno, anoField].forEach(function (sel) {
            for (var a = anoAtual + 1; a >= anoAtual - 4; a--) {
                var opt = document.createElement("option");
                opt.value = a; opt.textContent = a;
                sel.appendChild(opt);
            }
        });
        filtroMes.value = window.DM_CONFIG.mesAtual;
        filtroAno.value = anoAtual;
        mesField.value = window.DM_CONFIG.mesAtual;
        anoField.value = anoAtual;
    }

    async function carregarSetores() {
        setores = await apiFetch("/api/setores");
        [filtroSetor, setorField].forEach(function (sel) {
            var manterTodos = sel === filtroSetor;
            sel.innerHTML = manterTodos ? '<option value="">Todos os setores</option>' : "";
            setores.forEach(function (s) {
                var opt = document.createElement("option");
                opt.value = s.id; opt.textContent = s.nome;
                sel.appendChild(opt);
            });
        });
    }

    function setTipo(tipo) {
        tipoAtual = tipo;
        document.querySelectorAll(".tipo-meta-btn").forEach(function (btn) {
            btn.classList.toggle("btn-primary", btn.dataset.tipo === tipo);
        });
        blocoValorFixo.style.display = tipo === "VALOR_FIXO" ? "block" : "none";
        blocoPercentual.style.display = tipo === "PERCENTUAL" ? "block" : "none";
        if (tipo === "PERCENTUAL") agendarPreview();
    }

    function agendarPreview() {
        clearTimeout(previewTimer);
        previewTimer = setTimeout(atualizarPreview, 400);
    }

    async function atualizarPreview() {
        if (tipoAtual !== "PERCENTUAL") return;
        var setorId = setorField.value, ano = anoField.value, mes = mesField.value;
        var percentual = percentualField.value, base = baseField.value;
        if (!setorId || !percentual) {
            previewBox.innerHTML = '<div class="text-muted">Preencha o setor e o percentual para calcular a meta automaticamente.</div>';
            confirmarZeroWrap.style.display = "none";
            return;
        }
        previewBox.innerHTML = '<div class="text-muted">Calculando meta automaticamente...</div>';
        try {
            var url = "/api/metas/preview?setor_id=" + setorId + "&ano=" + ano + "&mes=" + mes +
                "&tipo_meta=PERCENTUAL&percentual_meta=" + encodeURIComponent(percentual) + "&base_comparacao=" + base;
            var resultado = await apiFetch(url);
            ultimoPreview = resultado;
            if (resultado.tem_dados) {
                confirmarZeroWrap.style.display = "none";
                previewBox.innerHTML =
                    '<div class="flex-between"><span class="text-muted">Venda base (' + BASE_LABELS[base] + ")</span><strong>" + Fmt.brl(resultado.venda_base) + "</strong></div>" +
                    '<div class="flex-between" style="margin-top:6px;"><span class="text-muted">Crescimento</span><strong>' + (Number(percentual) >= 0 ? "+" : "") + percentual + "%</strong></div>" +
                    '<div class="flex-between" style="margin-top:6px;padding-top:8px;border-top:1px solid var(--border-soft);"><span class="text-muted">Meta calculada</span><strong style="color:var(--accent);font-size:15px;">' + Fmt.brl(resultado.valor_meta) + "</strong></div>";
            } else {
                confirmarZeroWrap.style.display = "flex";
                previewBox.innerHTML =
                    '<div style="color:var(--warning);font-weight:600;">Não foi possível calcular automaticamente a meta.</div>' +
                    '<div class="text-muted" style="margin-top:4px;">Não existem vendas registradas no período de comparação (' + BASE_LABELS[base] + ").</div>";
            }
        } catch (e) {
            previewBox.innerHTML = '<div class="text-muted">Não foi possível calcular a meta agora.</div>';
        }
    }

    function abrirModalNovo() {
        modalTitle.textContent = "Nova Meta";
        idField.value = "";
        setorField.value = setores.length ? setores[0].id : "";
        mesField.value = window.DM_CONFIG.mesAtual;
        anoField.value = window.DM_CONFIG.anoAtual;
        valorField.value = "";
        percentualField.value = "";
        baseField.value = "MESMO_MES_ANO_ANTERIOR";
        confirmarZeroCheck.checked = false;
        confirmarZeroWrap.style.display = "none";
        setTipo("VALOR_FIXO");
        abrirModal(modal);
    }

    async function abrirModalEditar(metaId) {
        var meta = await apiFetch("/api/metas/" + metaId);
        modalTitle.textContent = "Editar Meta";
        idField.value = meta.id;
        setorField.value = meta.setor_id;
        mesField.value = meta.mes;
        anoField.value = meta.ano;
        valorField.value = meta.valor_meta != null ? meta.valor_meta : "";
        percentualField.value = meta.percentual_meta != null ? meta.percentual_meta : "";
        baseField.value = meta.base_comparacao === "NAO_APLICAVEL" ? "MESMO_MES_ANO_ANTERIOR" : meta.base_comparacao;
        confirmarZeroCheck.checked = false;
        setTipo(meta.tipo_meta);
        abrirModal(modal);
    }

    async function salvarMeta() {
        var payload = {
            setor_id: Number(setorField.value),
            ano: Number(anoField.value),
            mes: Number(mesField.value),
            tipo_meta: tipoAtual,
            base_comparacao: tipoAtual === "PERCENTUAL" ? baseField.value : "NAO_APLICAVEL",
            confirmar_zero: confirmarZeroCheck.checked,
        };
        if (tipoAtual === "VALOR_FIXO") {
            var valor = Number(valorField.value);
            if (!valor || valor <= 0) { Toast.warning("Informe um valor de meta maior que zero."); return; }
            payload.valor_meta = valor;
        } else {
            if (percentualField.value === "") { Toast.warning("Informe o percentual de crescimento."); return; }
            payload.percentual_meta = Number(percentualField.value);
        }

        var id = idField.value;
        try {
            if (id) {
                await apiFetch("/api/metas/" + id, { method: "PUT", body: JSON.stringify(payload) });
                Toast.success("Meta atualizada.");
            } else {
                await apiFetch("/api/metas", { method: "POST", body: JSON.stringify(payload) });
                Toast.success("Meta criada com sucesso.");
            }
            fecharModal(modal);
            carregarMetas();
        } catch (e) { /* toast já exibido */ }
    }

    function renderLinha(meta) {
        var tr = document.createElement("tr");
        var tipoLabel = meta.tipo_meta === "VALOR_FIXO" ? "Valor fixo" : ((meta.percentual_meta >= 0 ? "+" : "") + meta.percentual_meta + "%");
        if (meta.automatica) tipoLabel += ' <span class="badge badge-auto" title="Gerada pela meta automática do setor">Automática</span>';
        tr.innerHTML =
            "<td><strong>" + meta.setor_nome + "</strong></td>" +
            "<td>" + MESES[meta.mes - 1] + "/" + meta.ano + "</td>" +
            "<td>" + tipoLabel + "</td>" +
            "<td>" + BASE_LABELS[meta.base_comparacao] + "</td>" +
            '<td class="money-value">' + (meta.tipo_meta === "VALOR_FIXO" ? Fmt.brl(meta.valor_meta) : "—") + "</td>" +
            '<td class="money-value"><strong>' + Fmt.brl(meta.valor_calculado) + "</strong></td>" +
            "<td>" + (meta.ativo ? '<span class="badge badge-success">Ativa</span>' : '<span class="badge badge-neutral">Inativa</span>') + "</td>" +
            '<td style="text-align:right;"></td>';

        var acoes = document.createElement("div");
        acoes.className = "flex gap-8";
        acoes.style.justifyContent = "flex-end";

        var btnEditar = document.createElement("button");
        btnEditar.className = "btn btn-sm btn-ghost";
        btnEditar.textContent = "Editar";
        btnEditar.addEventListener("click", function () { abrirModalEditar(meta.id); });

        var btnToggle = document.createElement("button");
        btnToggle.className = "btn btn-sm btn-ghost";
        btnToggle.textContent = meta.ativo ? "Desativar" : "Ativar";
        btnToggle.addEventListener("click", async function () {
            try {
                await apiFetch("/api/metas/" + meta.id + "/ativo", { method: "PATCH", body: JSON.stringify({ ativo: !meta.ativo }) });
                Toast.success(meta.ativo ? "Meta desativada." : "Meta ativada.");
                carregarMetas();
            } catch (e) {}
        });

        var btnExcluir = document.createElement("button");
        btnExcluir.className = "btn btn-sm btn-danger";
        btnExcluir.textContent = "Excluir";
        btnExcluir.addEventListener("click", function () {
            confirmText.textContent = "Tem certeza que deseja excluir esta meta?";
            confirmAction = async function () {
                try {
                    await apiFetch("/api/metas/" + meta.id, { method: "DELETE" });
                    Toast.success("Meta excluída.");
                    fecharModal(confirmModal);
                    carregarMetas();
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

    async function carregarMetas() {
        tbody.innerHTML = '<tr><td colspan="8"><div class="skeleton skeleton-line" style="margin:8px 0;"></div></td></tr>';
        var params = new URLSearchParams();
        if (filtroSetor.value) params.set("setor_id", filtroSetor.value);
        if (filtroAno.value) params.set("ano", filtroAno.value);
        if (filtroMes.value) params.set("mes", filtroMes.value);
        try {
            var metas = await apiFetch("/api/metas?" + params.toString());
            tbody.innerHTML = "";
            if (!metas.length) {
                tbody.innerHTML = '<tr><td colspan="8"><div class="empty-state"><div>Nenhuma meta cadastrada para este período.</div></div></td></tr>';
                return;
            }
            metas.forEach(function (m) { tbody.appendChild(renderLinha(m)); });
        } catch (e) {
            tbody.innerHTML = '<tr><td colspan="8"><div class="empty-state">Não foi possível carregar as metas.</div></td></tr>';
        }
    }

    document.getElementById("btn-nova-meta").addEventListener("click", abrirModalNovo);
    document.getElementById("meta-modal-close").addEventListener("click", function () { fecharModal(modal); });
    document.getElementById("meta-modal-cancel").addEventListener("click", function () { fecharModal(modal); });
    document.getElementById("meta-modal-save").addEventListener("click", salvarMeta);
    document.querySelectorAll(".tipo-meta-btn").forEach(function (btn) {
        btn.addEventListener("click", function () { setTipo(btn.dataset.tipo); });
    });
    [setorField, anoField, mesField, percentualField, baseField].forEach(function (el) {
        el.addEventListener("input", agendarPreview);
        el.addEventListener("change", agendarPreview);
    });

    document.getElementById("confirm-modal-cancel").addEventListener("click", function () { fecharModal(confirmModal); });
    document.getElementById("confirm-modal-ok").addEventListener("click", function () { if (confirmAction) confirmAction(); });
    [modal, confirmModal].forEach(function (overlay) {
        overlay.addEventListener("click", function (ev) { if (ev.target === overlay) fecharModal(overlay); });
    });

    filtroSetor.addEventListener("change", carregarMetas);
    filtroAno.addEventListener("change", carregarMetas);
    filtroMes.addEventListener("change", carregarMetas);

    window.recarregarMetas = carregarMetas;
    popularSelects();
    carregarSetores().then(carregarMetas);
})();
