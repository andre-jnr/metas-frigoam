/* Infraestrutura compartilhada: sidebar, tema, toasts, fetch helper, formatação. */

(function () {
    var sidebar = document.getElementById("sidebar");
    var toggleBtn = document.getElementById("sidebar-toggle-btn");
    if (localStorage.getItem("dm_sidebar_collapsed") === "1") {
        sidebar.classList.add("collapsed");
    }
    if (toggleBtn) {
        toggleBtn.addEventListener("click", function () {
            sidebar.classList.toggle("collapsed");
            localStorage.setItem("dm_sidebar_collapsed", sidebar.classList.contains("collapsed") ? "1" : "0");
        });
    }
})();

(function () {
    var btn = document.getElementById("theme-toggle-btn");
    var iconDark = document.getElementById("theme-icon-dark");
    var iconLight = document.getElementById("theme-icon-light");

    function temaAtual() {
        var salvo = localStorage.getItem("dm_theme");
        if (salvo) return salvo;
        return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    }

    function aplicarIcone(tema) {
        if (!iconDark || !iconLight) return;
        iconDark.style.display = tema === "dark" ? "block" : "none";
        iconLight.style.display = tema === "light" ? "block" : "none";
    }

    aplicarIcone(temaAtual());

    if (btn) {
        btn.addEventListener("click", function () {
            var novo = temaAtual() === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", novo);
            localStorage.setItem("dm_theme", novo);
            aplicarIcone(novo);
        });
    }
})();

(function () {
    var btn = document.getElementById("ocultar-valores-btn");
    var iconAberto = document.getElementById("olho-aberto-icon");
    var iconFechado = document.getElementById("olho-fechado-icon");
    if (!btn) return;

    function aplicarEstado(oculto) {
        document.documentElement.classList.toggle("ocultar-valores", oculto);
        iconAberto.style.display = oculto ? "none" : "block";
        iconFechado.style.display = oculto ? "block" : "none";
        btn.title = oculto ? "Mostrar valores monetários" : "Ocultar valores monetários";
    }

    aplicarEstado(localStorage.getItem("dm_ocultar_valores") === "1");

    btn.addEventListener("click", function () {
        var oculto = !document.documentElement.classList.contains("ocultar-valores");
        localStorage.setItem("dm_ocultar_valores", oculto ? "1" : "0");
        aplicarEstado(oculto);
    });
})();

(function () {
    var select = document.getElementById("filial-select");
    if (!select) return;

    fetch("/api/filiais", { headers: { "Content-Type": "application/json" } })
        .then(function (resp) { return resp.json(); })
        .then(function (filiais) {
            select.innerHTML = "";
            (filiais || []).forEach(function (f) {
                var opt = document.createElement("option");
                opt.value = f.id;
                opt.textContent = f.nome;
                if (f.ativa) opt.selected = true;
                select.appendChild(opt);
            });
        })
        .catch(function () { /* seletor fica vazio se a API falhar */ });

    select.addEventListener("change", async function () {
        var filialId = select.value;
        try {
            await apiFetch("/api/filiais/ativa", { method: "POST", body: JSON.stringify({ filial_id: filialId }) });
            Toast.success("Filial alterada. Atualizando...");
            setTimeout(function () { location.reload(); }, 400);
        } catch (e) { /* erro já exibido via toast */ }
    });
})();

var Toast = (function () {
    var container = document.getElementById("toast-container");
    var ICONS = {
        success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
        error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
        warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/></svg>',
        info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
    };

    function show(mensagem, tipo) {
        if (!container) return;
        tipo = tipo || "info";
        var el = document.createElement("div");
        el.className = "toast " + tipo;
        el.innerHTML = (ICONS[tipo] || ICONS.info) + "<span>" + mensagem + "</span>";
        container.appendChild(el);
        setTimeout(function () {
            el.classList.add("leaving");
            setTimeout(function () { el.remove(); }, 220);
        }, 4200);
    }

    return {
        success: function (msg) { show(msg, "success"); },
        error: function (msg) { show(msg, "error"); },
        warning: function (msg) { show(msg, "warning"); },
        info: function (msg) { show(msg, "info"); },
    };
})();

async function apiFetch(url, options) {
    options = options || {};
    options.headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    var resp;
    try {
        resp = await fetch(url, options);
    } catch (err) {
        Toast.error("Não foi possível conectar ao servidor. Verifique se o sistema está em execução.");
        throw err;
    }
    if (resp.status === 204) return null;
    var data = null;
    try { data = await resp.json(); } catch (e) { /* corpo vazio */ }
    if (!resp.ok) {
        var msg = (data && data.erro) || "Ocorreu um erro ao processar a solicitação.";
        Toast.error(msg);
        throw new Error(msg);
    }
    return data;
}

var Fmt = {
    brl: function (valor) {
        var n = Number(valor || 0);
        return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
    },
    brlCompact: function (valor) {
        var n = Number(valor || 0);
        var abs = Math.abs(n);
        if (abs >= 1000000) return "R$ " + (n / 1000000).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mi";
        if (abs >= 1000) return "R$ " + (n / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mil";
        return Fmt.brl(n);
    },
    pct: function (valor, casas) {
        var n = Number(valor || 0);
        return n.toLocaleString("pt-BR", { minimumFractionDigits: casas == null ? 1 : casas, maximumFractionDigits: casas == null ? 1 : casas }) + "%";
    },
    pp: function (valor) {
        var n = Number(valor || 0);
        var sinal = n > 0 ? "+" : "";
        return sinal + n.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " p.p.";
    },
    brlCompactSigned: function (valor) {
        var n = Number(valor || 0);
        var sinal = n > 0 ? "+" : "";
        return sinal + Fmt.brlCompact(n);
    },
    numero: function (valor) {
        var n = Number(valor || 0);
        return n.toLocaleString("pt-BR", { maximumFractionDigits: 3 });
    },
    numeroSinalizado: function (valor) {
        var n = Number(valor || 0);
        var sinal = n > 0 ? "+" : "";
        return sinal + Fmt.numero(n);
    },
    dataHora: function (iso) {
        if (!iso) return "--";
        var d = new Date(iso);
        if (isNaN(d.getTime())) return iso;
        return d.toLocaleDateString("pt-BR") + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    },
    mesNome: function (mes) {
        var nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
        return nomes[mes - 1] || mes;
    },
};

function countUp(el, targetValue, opts) {
    opts = opts || {};
    var duration = opts.duration || 900;
    var decimals = opts.decimals == null ? 0 : opts.decimals;
    var formatter = opts.formatter || function (v) { return v.toFixed(decimals); };
    var start = 0;
    var startTime = null;

    function step(ts) {
        if (!startTime) startTime = ts;
        var progress = Math.min((ts - startTime) / duration, 1);
        var eased = 1 - Math.pow(1 - progress, 3);
        var current = start + (targetValue - start) * eased;
        el.textContent = formatter(current);
        if (progress < 1) requestAnimationFrame(step);
        else el.textContent = formatter(targetValue);
    }
    requestAnimationFrame(step);
}
