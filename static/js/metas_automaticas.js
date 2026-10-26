/* Metas automáticas: regras por setor + escada animada mostrando o sobe/desce da meta. */

(function () {
    var MESES_CURTOS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
    var MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
    var BASE_LABELS = { MESMO_MES_ANO_ANTERIOR: "mesmo mês do ano anterior", MES_ANTERIOR: "mês anterior" };
    var EXEMPLO_RESULTADOS = [true, true, true, false, true, false, false]; // simulação de "Como funciona"
    var INTERVALO_PASSO = 1500;

    var modal = document.getElementById("auto-modal");
    var escadaEl = document.getElementById("escada");
    var narracaoEl = document.getElementById("escada-narracao");
    var mesesEl = document.getElementById("escada-meses");
    var tituloEl = document.getElementById("escada-titulo");
    var subEl = document.getElementById("escada-sub");
    var listaEl = document.getElementById("auto-lista");
    var form = document.getElementById("auto-form");
    var formTitulo = document.getElementById("auto-form-titulo");
    var campos = {
        setor: document.getElementById("auto-setor"),
        mes: document.getElementById("auto-mes"),
        ano: document.getElementById("auto-ano"),
        inicial: document.getElementById("auto-inicial"),
        base: document.getElementById("auto-base"),
        minimo: document.getElementById("auto-minimo"),
        maximo: document.getElementById("auto-maximo"),
    };

    var regras = [];
    var setorSelecionado = null;
    var timer = null;
    var previewTimer = null;

    // ---------- escada (mesma regra de services/calculos.py) ----------
    function degrau(i) { return Math.round(i * 2.5); }

    function proximoPercentual(atual, bateu, minimo, maximo) {
        var i = 0;
        while (degrau(i) <= atual + 1e-9) i++;
        var novo;
        if (bateu) {
            novo = degrau(i);
        } else {
            i--;
            if (Math.abs(degrau(i) - atual) < 1e-9) i--;
            novo = degrau(Math.max(i, 0));
        }
        if (maximo != null) novo = Math.min(novo, maximo);
        return Math.max(novo, minimo);
    }

    function degrausEntre(min, max) {
        var lista = [];
        for (var i = 0; degrau(i) <= max; i++) {
            if (degrau(i) >= min) lista.push(degrau(i));
        }
        if (lista.indexOf(min) === -1) lista.unshift(min);
        return lista;
    }

    function fmtPct(v) { return Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "%"; }
    function rotuloMes(ano, mes) { return MESES_CURTOS[mes - 1] + "/" + String(ano).slice(2); }

    // ---------- animação ----------
    function pararAnimacao() { clearTimeout(timer); timer = null; }

    function posicionarMarcador(marcador, degrauEl, animar) {
        var x = degrauEl.offsetLeft;
        var y = degrauEl.offsetTop - marcador.offsetHeight - 6;
        if (!animar) {
            marcador.style.transition = "none";
            marcador.style.transform = "translate(" + x + "px," + y + "px)";
            void marcador.offsetWidth; // aplica a posição antes de religar a transição
            marcador.style.transition = "";
        } else {
            marcador.style.transform = "translate(" + x + "px," + y + "px)";
        }
    }

    function narracao(passos, i) {
        var p = passos[i];
        if (i === 0) return p.rotulo + ": começa em <strong>" + fmtPct(p.pct) + "</strong>";
        var anterior = passos[i - 1];
        if (p.manual) return p.rotulo + ": meta editada à mão, <strong>" + fmtPct(p.pct) + "</strong>";
        var igual = p.pct === anterior.pct;
        if (p.motivo === "BATEU") {
            return '<span class="sobe">' + p.rotulo + ": bateu a meta de " + anterior.rotulo + " → " +
                (igual ? "fica em " + fmtPct(p.pct) + " (máximo)" : "sobe para " + fmtPct(p.pct)) + "</span>";
        }
        return '<span class="desce">' + p.rotulo + ": não bateu a meta de " + anterior.rotulo + " → " +
            (igual ? "fica em " + fmtPct(p.pct) + " (mínimo)" : "volta para " + fmtPct(p.pct)) + "</span>";
    }

    function tocar(passos, minimo, maximo) {
        pararAnimacao();
        var pcts = passos.map(function (p) { return p.pct; });
        var topo = Math.max.apply(null, pcts);
        var limiteTopo = maximo != null ? maximo : proximoPercentual(proximoPercentual(topo, true, 0), true, 0);
        var niveis = degrausEntre(Math.min(minimo, Math.min.apply(null, pcts)), Math.max(limiteTopo, topo));
        pcts.forEach(function (v) { if (niveis.indexOf(v) === -1) niveis.push(v); });
        niveis.sort(function (a, b) { return a - b; });

        escadaEl.innerHTML = "";
        var degrausEl = {};
        var alturaMax = 150;
        niveis.forEach(function (nivel, idx) {
            var el = document.createElement("div");
            el.className = "escada-degrau";
            el.style.height = Math.round(28 + (alturaMax - 28) * (idx / Math.max(niveis.length - 1, 1))) + "px";
            el.textContent = fmtPct(nivel);
            escadaEl.appendChild(el);
            degrausEl[nivel] = el;
        });
        var marcador = document.createElement("div");
        marcador.className = "escada-marcador";
        escadaEl.appendChild(marcador);

        mesesEl.innerHTML = "";
        var chips = passos.map(function (p) {
            var chip = document.createElement("span");
            chip.className = "escada-mes";
            chip.innerHTML = p.rotulo + " · " + fmtPct(p.pct) + ' <span class="res"></span>';
            mesesEl.appendChild(chip);
            return chip;
        });

        function mostrar(i) {
            var p = passos[i];
            Object.keys(degrausEl).forEach(function (k) { degrausEl[k].classList.remove("atual"); });
            degrausEl[p.pct].classList.add("atual", "visitado");
            marcador.textContent = fmtPct(p.pct);
            marcador.classList.toggle("subiu", i > 0 && p.pct > passos[i - 1].pct);
            marcador.classList.toggle("desceu", i > 0 && p.pct < passos[i - 1].pct);
            posicionarMarcador(marcador, degrausEl[p.pct], i > 0);
            narracaoEl.innerHTML = narracao(passos, i);
            chips.forEach(function (c, j) {
                c.classList.toggle("atual", j === i);
                c.classList.toggle("visto", j < i);
            });
            if (i > 0 && passos[i - 1].bateu != null) {
                chips[i - 1].querySelector(".res").innerHTML = passos[i - 1].bateu
                    ? '<span class="ok" title="Bateu">✓</span>' : '<span class="nok" title="Não bateu">✗</span>';
            }
            if (i + 1 < passos.length) timer = setTimeout(function () { mostrar(i + 1); }, INTERVALO_PASSO);
        }
        mostrar(0);
    }

    function passosSimulados(ano, mes, inicial, minimo, maximo) {
        var passos = [];
        var pct = inicial;
        for (var i = 0; i <= EXEMPLO_RESULTADOS.length; i++) {
            var bateuAnterior = i > 0 ? EXEMPLO_RESULTADOS[i - 1] : null;
            if (i > 0) pct = proximoPercentual(pct, bateuAnterior, minimo, maximo);
            passos.push({
                rotulo: rotuloMes(ano, mes), pct: pct,
                motivo: i === 0 ? "INICIO" : (bateuAnterior ? "BATEU" : "NAO_BATEU"),
                bateu: i < EXEMPLO_RESULTADOS.length ? EXEMPLO_RESULTADOS[i] : null,
            });
            mes++; if (mes > 12) { mes = 1; ano++; }
        }
        return passos;
    }

    function passosReais(regra) {
        return regra.historico
            .filter(function (h) { return h.tipo_meta === "PERCENTUAL"; })
            .map(function (h) {
                return {
                    rotulo: rotuloMes(h.ano, h.mes), pct: h.percentual_meta, motivo: h.motivo,
                    manual: !h.automatica, bateu: h.bateu,
                };
            });
    }

    function tocarExemplo(valores, titulo) {
        tituloEl.textContent = titulo || "Como funciona";
        subEl.textContent = "Simulação de 8 meses começando em " + fmtPct(valores.inicial) +
            ". Bateu a meta do mês anterior: sobe um degrau. Não bateu: desce um degrau.";
        tocar(passosSimulados(valores.ano, valores.mes, valores.inicial, valores.minimo, valores.maximo),
            valores.minimo, valores.maximo);
    }

    function tocarRegra(regra) {
        var passos = passosReais(regra);
        if (passos.length < 2) {
            tocarExemplo({
                ano: regra.ano_inicio, mes: regra.mes_inicio, inicial: regra.percentual_inicial,
                minimo: regra.percentual_minimo, maximo: regra.percentual_maximo,
            }, regra.setor_nome + ": simulação");
            subEl.textContent = "Ainda não há meses fechados para este setor. Veja como a meta andaria nos próximos meses (simulação).";
            return;
        }
        tituloEl.textContent = regra.setor_nome + ": histórico real";
        subEl.textContent = "Como a meta andou desde " + MESES[regra.mes_inicio - 1].toLowerCase() + "/" + regra.ano_inicio +
            ", comparando com o " + BASE_LABELS[regra.base_comparacao] + ".";
        tocar(passos, regra.percentual_minimo, regra.percentual_maximo);
    }

    function repetir() {
        var regra = regras.find(function (r) { return r.setor_id === setorSelecionado; });
        if (form.style.display !== "none") tocarExemplo(valoresForm(), "Simulação com os valores do formulário");
        else if (regra) tocarRegra(regra);
        else tocarExemplo(padraoExemplo());
    }

    function padraoExemplo() {
        return { ano: window.DM_CONFIG.anoAtual, mes: window.DM_CONFIG.mesAtual, inicial: 5, minimo: 3, maximo: null };
    }

    // ---------- lista de regras ----------
    function metaAtual(regra) {
        var h = regra.historico;
        return h.length ? h[h.length - 1] : null;
    }

    function renderLista() {
        listaEl.innerHTML = "";
        if (!regras.length) {
            listaEl.innerHTML = '<div class="empty-state" style="padding:18px;">Nenhum setor com meta automática. Clique em "Nova regra".</div>';
            return;
        }
        regras.forEach(function (regra) {
            var atual = metaAtual(regra);
            var item = document.createElement("div");
            item.className = "auto-regra" + (regra.setor_id === setorSelecionado ? " selecionada" : "");
            item.innerHTML =
                '<div class="auto-regra-info"><strong>' + regra.setor_nome + "</strong>" +
                (atual ? ' <span class="badge badge-auto">Meta atual ' + fmtPct(atual.percentual_meta) + "</span>" : "") +
                '<div class="text-muted" style="margin-top:3px;">Desde ' + rotuloMes(regra.ano_inicio, regra.mes_inicio) +
                " · comparativo: " + BASE_LABELS[regra.base_comparacao] +
                " · início " + fmtPct(regra.percentual_inicial) +
                " · mín. " + fmtPct(regra.percentual_minimo) +
                " · máx. " + (regra.percentual_maximo != null ? fmtPct(regra.percentual_maximo) : "sem limite") + "</div></div>";

            var acoes = document.createElement("div");
            acoes.className = "flex gap-8";
            var btnVer = botao("Ver na escada", "btn-ghost", function () {
                setorSelecionado = regra.setor_id;
                fecharForm();
                renderLista();
                tocarRegra(regra);
            });
            var btnEditar = botao("Editar", "btn-ghost", function () { abrirForm(regra); });
            var btnRemover = botao("Remover", "btn-danger", async function () {
                if (!btnRemover.dataset.confirmar) {
                    btnRemover.dataset.confirmar = "1";
                    btnRemover.textContent = "Confirmar remoção";
                    return;
                }
                try {
                    await apiFetch("/api/metas-automaticas/" + regra.setor_id, { method: "DELETE" });
                    Toast.success("Meta automática removida. As metas já geradas continuam cadastradas.");
                    if (setorSelecionado === regra.setor_id) setorSelecionado = null;
                    await carregarRegras();
                    repetir();
                } catch (e) {}
            });
            [btnVer, btnEditar, btnRemover].forEach(function (b) { acoes.appendChild(b); });
            item.appendChild(acoes);
            listaEl.appendChild(item);
        });
    }

    function botao(texto, classe, onClick) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "btn btn-sm " + classe;
        b.textContent = texto;
        b.addEventListener("click", onClick);
        return b;
    }

    async function carregarRegras() {
        listaEl.innerHTML = '<div class="skeleton skeleton-line"></div>';
        try {
            regras = await apiFetch("/api/metas-automaticas");
        } catch (e) {
            regras = [];
        }
        renderLista();
    }

    // ---------- formulário ----------
    function popularSelects() {
        MESES.forEach(function (nome, idx) { campos.mes.add(new Option(nome, idx + 1)); });
        var anoAtual = window.DM_CONFIG.anoAtual;
        for (var a = anoAtual + 1; a >= anoAtual - 4; a--) campos.ano.add(new Option(a, a));
        var niveis = degrausEntre(0, 50);
        niveis.forEach(function (n) {
            if (n > 0) campos.inicial.add(new Option(fmtPct(n), n));
            campos.minimo.add(new Option(fmtPct(n), n));
            if (n > 0) campos.maximo.add(new Option(fmtPct(n), n));
        });
        campos.maximo.add(new Option("Sem limite", ""), 0);
    }

    async function popularSetores() {
        var setores = await apiFetch("/api/setores");
        campos.setor.innerHTML = "";
        setores.forEach(function (s) { campos.setor.add(new Option(s.nome, s.id)); });
    }

    function valoresForm() {
        return {
            ano: Number(campos.ano.value), mes: Number(campos.mes.value),
            inicial: Number(campos.inicial.value), minimo: Number(campos.minimo.value),
            maximo: campos.maximo.value === "" ? null : Number(campos.maximo.value),
        };
    }

    function abrirForm(regra) {
        formTitulo.textContent = regra ? "Editar regra: " + regra.setor_nome : "Nova regra";
        campos.setor.disabled = !!regra;
        campos.setor.value = regra ? regra.setor_id : campos.setor.options.length ? campos.setor.options[0].value : "";
        campos.mes.value = regra ? regra.mes_inicio : window.DM_CONFIG.mesAtual;
        campos.ano.value = regra ? regra.ano_inicio : window.DM_CONFIG.anoAtual;
        campos.inicial.value = regra ? regra.percentual_inicial : 5;
        campos.minimo.value = regra ? regra.percentual_minimo : 3;
        campos.maximo.value = regra && regra.percentual_maximo != null ? regra.percentual_maximo : "";
        campos.base.value = regra ? regra.base_comparacao : "MESMO_MES_ANO_ANTERIOR";
        form.style.display = "block";
        form.scrollIntoView({ block: "nearest" });
        tocarExemplo(valoresForm(), "Simulação com os valores do formulário");
    }

    function fecharForm() {
        form.style.display = "none";
        campos.setor.disabled = false;
    }

    async function salvar(ev) {
        ev.preventDefault();
        var v = valoresForm();
        var setorId = Number(campos.setor.value);
        if (!setorId) { Toast.warning("Selecione o setor."); return; }
        var btn = document.getElementById("auto-salvar");
        btn.disabled = true;
        btn.textContent = "Calculando metas...";
        try {
            var regra = await apiFetch("/api/metas-automaticas/" + setorId, {
                method: "PUT",
                body: JSON.stringify({
                    ano_inicio: v.ano, mes_inicio: v.mes, percentual_inicial: v.inicial,
                    percentual_minimo: v.minimo, percentual_maximo: v.maximo, base_comparacao: campos.base.value,
                }),
            });
            Toast.success("Meta automática salva para " + regra.setor_nome + ".");
            setorSelecionado = regra.setor_id;
            fecharForm();
            await carregarRegras();
            tocarRegra(regra);
            if (window.recarregarMetas) window.recarregarMetas();
        } catch (e) { /* toast já exibido */ }
        finally { btn.disabled = false; btn.textContent = "Salvar regra"; }
    }

    // ---------- modal ----------
    async function abrir() {
        modal.classList.add("open");
        setorSelecionado = null;
        fecharForm();
        tocarExemplo(padraoExemplo());
        await Promise.all([carregarRegras(), popularSetores()]);
    }

    function fechar() {
        modal.classList.remove("open");
        pararAnimacao();
    }

    document.getElementById("btn-metas-automaticas").addEventListener("click", abrir);
    document.getElementById("auto-modal-close").addEventListener("click", fechar);
    modal.addEventListener("click", function (ev) { if (ev.target === modal) fechar(); });
    document.getElementById("escada-repetir").addEventListener("click", repetir);
    document.getElementById("auto-nova").addEventListener("click", function () { abrirForm(null); });
    document.getElementById("auto-cancelar").addEventListener("click", function () { fecharForm(); repetir(); });
    form.addEventListener("submit", salvar);
    ["inicial", "minimo", "maximo", "mes", "ano"].forEach(function (k) {
        campos[k].addEventListener("change", function () {
            clearTimeout(previewTimer);
            previewTimer = setTimeout(function () { tocarExemplo(valoresForm(), "Simulação com os valores do formulário"); }, 250);
        });
    });
    window.addEventListener("resize", function () {
        var atual = escadaEl.querySelector(".escada-degrau.atual");
        var marcador = escadaEl.querySelector(".escada-marcador");
        if (atual && marcador) posicionarMarcador(marcador, atual, false);
    });

    popularSelects();
})();
