/* Gauge (velocímetro) semicircular em SVG puro, sem dependências externas.
   O preenchimento visual é sempre limitado a 100%, mas o valor central mostra
   o percentual real (podendo passar de 100%). */

var Gauge = (function () {
    var STATUS_META = {
        META_BATIDA: { label: "Meta batida", cor: "var(--success)", badge: "badge-success" },
        NO_RITMO: { label: "No ritmo", cor: "var(--accent)", badge: "badge-neutral" },
        ABAIXO_DO_RITMO: { label: "Abaixo do ritmo", cor: "var(--warning)", badge: "badge-warning" },
    };

    function polar(cx, cy, r, percent) {
        var angle = Math.PI - (Math.min(Math.max(percent, 0), 100) / 100) * Math.PI;
        return { x: cx + r * Math.cos(angle), y: cy - r * Math.sin(angle) };
    }

    function build(size) {
        var w = size, h = size * 0.62;
        var cx = w / 2, cy = h * 0.94;
        var r = w * 0.42;
        var stroke = w * 0.09;

        var start = polar(cx, cy, r, 0);
        var end = polar(cx, cy, r, 100);
        var d = "M " + start.x + " " + start.y + " A " + r + " " + r + " 0 1 1 " + end.x + " " + end.y;
        var circunferencia = Math.PI * r;

        return {
            w: w, h: h, cx: cx, cy: cy, r: r, stroke: stroke, d: d, circunferencia: circunferencia,
        };
    }

    function svgMarkup(geo, uid) {
        // stroke-linecap "butt" (não "round") é essencial aqui: uma ponta arredondada
        // "vaza" por metade da espessura do traço além da posição real em percentual
        // — nesse gauge isso equivale a ~3 pontos percentuais de exagero visual, o
        // suficiente para um card em 15,0% parecer ter alcançado uma meta de 16,1%.
        return (
            '<svg viewBox="0 0 ' + geo.w + " " + geo.h + '" preserveAspectRatio="xMidYMid meet">' +
            '<path d="' + geo.d + '" fill="none" stroke="var(--border-soft)" stroke-width="' + geo.stroke + '" stroke-linecap="butt"></path>' +
            '<path id="progress-' + uid + '" d="' + geo.d + '" fill="none" stroke="var(--accent)" stroke-width="' + geo.stroke + '" ' +
            'stroke-linecap="butt" stroke-dasharray="' + geo.circunferencia + '" stroke-dashoffset="' + geo.circunferencia + '" ' +
            'style="transition: stroke-dashoffset 1000ms cubic-bezier(0.16,1,0.3,1), stroke 400ms ease;"></path>' +
            '<line id="marker-' + uid + '" x1="0" y1="0" x2="0" y2="0" stroke="var(--text-secondary)" stroke-width="2.5" stroke-linecap="butt" opacity="0.85"></line>' +
            "</svg>"
        );
    }

    var uidCounter = 0;

    function render(container, options) {
        var percentReal = Number(options.percentRealizado || 0);
        var percentEsperado = Number(options.percentEsperado || 0);
        var status = options.status || "ABAIXO_DO_RITMO";
        var size = options.size || 200;
        var modo = options.modo || "percentual"; // "percentual" | "valor"
        var valorRealizado = Number(options.valorRealizado || 0);

        var uid = "g" + (uidCounter++);
        var geo = build(size);
        var meta = STATUS_META[status] || STATUS_META.ABAIXO_DO_RITMO;

        var wrap = document.createElement("div");
        wrap.className = "gauge-wrap";
        wrap.innerHTML =
            svgMarkup(geo, uid) +
            '<div class="gauge-center">' +
            '<div class="gauge-value' + (modo === "valor" ? " gauge-value-money" : "") + '" style="color:' + meta.cor + '">0</div>' +
            "</div>";
        container.appendChild(wrap);

        var progressPath = wrap.querySelector("#progress-" + uid);
        var markerLine = wrap.querySelector("#marker-" + uid);
        var valueEl = wrap.querySelector(".gauge-value");

        progressPath.setAttribute("stroke", meta.cor);

        var pInner = polar(geo.cx, geo.cy, geo.r - geo.stroke * 0.75, percentEsperado);
        var pOuter = polar(geo.cx, geo.cy, geo.r + geo.stroke * 0.75, percentEsperado);
        markerLine.setAttribute("x1", pInner.x);
        markerLine.setAttribute("y1", pInner.y);
        markerLine.setAttribute("x2", pOuter.x);
        markerLine.setAttribute("y2", pOuter.y);

        requestAnimationFrame(function () {
            var clamped = Math.min(Math.max(percentReal, 0), 100);
            var offset = geo.circunferencia * (1 - clamped / 100);
            progressPath.style.strokeDashoffset = offset;
        });

        if (modo === "valor") {
            countUp(valueEl, valorRealizado, {
                duration: 1000,
                formatter: function (v) { return Fmt.brlCompact(v); },
            });
        } else {
            countUp(valueEl, percentReal, {
                duration: 1000,
                formatter: function (v) { return v.toFixed(1).replace(".", ",") + "%"; },
            });
        }

        return wrap;
    }

    return { render: render, STATUS_META: STATUS_META };
})();
