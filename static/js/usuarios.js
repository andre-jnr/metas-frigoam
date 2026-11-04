/* Cadastro de usuários (só o superusuário abre esta tela). */
(function () {
    var tbody = document.getElementById("usuarios-tbody");
    var modal = document.getElementById("usuario-modal");
    var titulo = document.getElementById("usuario-modal-titulo");
    var campoId = document.getElementById("usuario-id");
    var campoNome = document.getElementById("usuario-nome");
    var campoSenha = document.getElementById("usuario-senha");
    var senhaLabel = document.getElementById("usuario-senha-label");
    var senhaHint = document.getElementById("usuario-senha-hint");
    var checkValores = document.getElementById("usuario-valores");
    var checkSuper = document.getElementById("usuario-super");
    var checkAtivo = document.getElementById("usuario-ativo");
    var ativoWrap = document.getElementById("usuario-ativo-wrap");
    var btnSalvar = document.getElementById("usuario-modal-salvar");
    var confirmModal = document.getElementById("confirm-modal");
    var confirmTexto = document.getElementById("confirm-modal-texto");
    var acaoConfirmar = null;
    var editando = null;

    function abrir(el) { el.classList.add("open"); }
    function fechar(el) { el.classList.remove("open"); }

    function escapar(texto) {
        return String(texto).replace(/[&<>"]/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
        });
    }

    function protegido(u) {
        return u.do_env || u.usuario === window.DM_USUARIO.usuario;
    }

    // superusuário sempre vê valores: a caixa fica marcada e travada
    function sincronizarValores() {
        if (checkSuper.checked) checkValores.checked = true;
        checkValores.disabled = checkSuper.checked;
        checkValores.closest(".usuario-opcao").classList.toggle("desabilitada", checkSuper.checked);
    }

    function abrirNovo() {
        editando = null;
        titulo.textContent = "Novo usuário";
        campoId.value = "";
        campoNome.value = "";
        campoNome.disabled = false;
        campoSenha.value = "";
        campoSenha.disabled = false;
        senhaLabel.textContent = "Senha";
        senhaHint.textContent = "Pelo menos 6 caracteres.";
        checkValores.checked = false;
        checkSuper.checked = false;
        checkSuper.disabled = false;
        checkAtivo.checked = true;
        ativoWrap.style.display = "none";
        sincronizarValores();
        abrir(modal);
        campoNome.focus();
    }

    function abrirEdicao(u) {
        editando = u;
        titulo.textContent = "Editar " + u.usuario;
        campoId.value = u.id;
        campoNome.value = u.usuario;
        campoNome.disabled = true;
        campoSenha.value = "";
        senhaLabel.textContent = "Nova senha";
        if (u.do_env) {
            campoSenha.disabled = true;
            senhaHint.textContent = "A senha deste usuário é definida no arquivo .env do servidor.";
        } else {
            campoSenha.disabled = false;
            senhaHint.textContent = "Deixe em branco para manter a senha atual.";
        }
        checkValores.checked = u.pode_ver_valores;
        checkSuper.checked = u.superusuario;
        checkSuper.disabled = protegido(u);
        checkAtivo.checked = u.ativo;
        checkAtivo.disabled = protegido(u);
        ativoWrap.style.display = "";
        ativoWrap.classList.toggle("desabilitada", protegido(u));
        checkSuper.closest(".usuario-opcao").classList.toggle("desabilitada", protegido(u));
        sincronizarValores();
        abrir(modal);
    }

    async function salvar() {
        var payload = {
            pode_ver_valores: checkValores.checked,
            superusuario: checkSuper.checked,
            ativo: checkAtivo.checked,
        };
        if (campoSenha.value) payload.senha = campoSenha.value;
        btnSalvar.disabled = true;
        try {
            if (editando) {
                await apiFetch("/api/usuarios/" + editando.id, { method: "PUT", body: JSON.stringify(payload) });
                Toast.success("Usuário atualizado.");
            } else {
                payload.usuario = campoNome.value.trim();
                if (!payload.usuario) { Toast.warning("Informe o usuário."); return; }
                if (!payload.senha) { Toast.warning("Informe a senha."); return; }
                await apiFetch("/api/usuarios", { method: "POST", body: JSON.stringify(payload) });
                Toast.success("Usuário " + payload.usuario + " criado.");
            }
            fechar(modal);
            carregar();
        } catch (e) { /* erro já exibido via toast */ }
        finally { btnSalvar.disabled = false; }
    }

    function linha(u) {
        var tr = document.createElement("tr");
        var perfil = u.superusuario ? '<span class="badge badge-auto">Superusuário</span>' : '<span class="badge badge-neutral">Usuário</span>';
        var visao = u.pode_ver_valores ? '<span class="badge badge-success">Valores e %</span>' : '<span class="badge badge-warning">Só porcentagens</span>';
        var status = u.ativo ? '<span class="badge badge-success">Ativo</span>' : '<span class="badge badge-neutral">Inativo</span>';
        tr.innerHTML =
            "<td><strong>" + escapar(u.usuario) + "</strong>" + (u.usuario === window.DM_USUARIO.usuario ? ' <span class="text-muted">(você)</span>' : "") + "</td>" +
            "<td>" + perfil + "</td><td>" + visao + "</td><td>" + status + "</td>" +
            "<td>" + Fmt.dataHora(u.created_at.replace(" ", "T") + "Z") + "</td>" +
            '<td style="text-align:right;"></td>';
        var acoes = document.createElement("div");
        acoes.className = "flex gap-8";
        acoes.style.justifyContent = "flex-end";

        var btnEditar = document.createElement("button");
        btnEditar.className = "btn btn-sm btn-ghost";
        btnEditar.textContent = "Editar";
        btnEditar.addEventListener("click", function () { abrirEdicao(u); });
        acoes.appendChild(btnEditar);

        if (!protegido(u)) {
            var btnExcluir = document.createElement("button");
            btnExcluir.className = "btn btn-sm btn-danger";
            btnExcluir.textContent = "Excluir";
            btnExcluir.addEventListener("click", function () {
                confirmTexto.textContent = "Excluir o usuário " + u.usuario + "? Ele perde o acesso na hora.";
                acaoConfirmar = async function () {
                    try {
                        await apiFetch("/api/usuarios/" + u.id, { method: "DELETE" });
                        Toast.success("Usuário excluído.");
                        fechar(confirmModal);
                        carregar();
                    } catch (e) {}
                };
                abrir(confirmModal);
            });
            acoes.appendChild(btnExcluir);
        }
        tr.lastElementChild.appendChild(acoes);
        return tr;
    }

    async function carregar() {
        tbody.innerHTML = '<tr><td colspan="6"><div class="skeleton skeleton-line" style="margin:8px 0;"></div></td></tr>';
        try {
            var usuarios = await apiFetch("/api/usuarios");
            tbody.innerHTML = "";
            usuarios.forEach(function (u) { tbody.appendChild(linha(u)); });
        } catch (e) {
            tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state">Não foi possível carregar os usuários.</div></td></tr>';
        }
    }

    document.getElementById("btn-novo-usuario").addEventListener("click", abrirNovo);
    document.getElementById("usuario-modal-fechar").addEventListener("click", function () { fechar(modal); });
    document.getElementById("usuario-modal-cancelar").addEventListener("click", function () { fechar(modal); });
    btnSalvar.addEventListener("click", salvar);
    document.getElementById("usuario-form").addEventListener("submit", function (ev) { ev.preventDefault(); salvar(); });
    checkSuper.addEventListener("change", sincronizarValores);
    document.getElementById("confirm-modal-cancelar").addEventListener("click", function () { fechar(confirmModal); });
    document.getElementById("confirm-modal-ok").addEventListener("click", function () { if (acaoConfirmar) acaoConfirmar(); });
    [modal, confirmModal].forEach(function (overlay) {
        overlay.addEventListener("click", function (ev) { if (ev.target === overlay) fechar(overlay); });
    });

    carregar();
})();
