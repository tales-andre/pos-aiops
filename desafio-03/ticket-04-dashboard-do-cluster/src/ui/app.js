/* Dashboard do cluster — DOM na mão, sem framework (decisão D1).
 *
 * Regra central de renderização: cada painel vem do servidor como um ENVELOPE,
 * que é `{ok:true, itens:[...]}` ou `{ok:false, categoria, titulo, mensagem}`.
 * Um envelope de falha vira uma faixa DENTRO daquele painel — nunca derruba a
 * página. É assim que 403 em services deixa pods funcionando.
 */

const INTERVALO_MS = 15000;

// `?ns=` permite abrir a tela já num namespace — útil para colar um link no
// chamado. Não é seletor de CLUSTER: o destino continua sendo o contexto
// corrente do kubeconfig, e só ele.
let estado = {
  namespace: new URLSearchParams(location.search).get("ns"),
  busca: new URLSearchParams(location.search).get("q") || "",
  snapshot: null,
  lidoEm: null,
};

const $ = (sel) => document.querySelector(sel);

function escapar(texto) {
  const d = document.createElement("div");
  d.textContent = texto === null || texto === undefined ? "" : String(texto);
  return d.innerHTML;
}

/* --- mensagens de painel: cada situação tem forma própria --------------- */

function avisoHTML(classe, simbolo, titulo, detalhe) {
  return (
    `<div class="aviso-painel ${classe}">` +
    `<span class="simbolo">${simbolo}</span>` +
    `<span class="texto"><span class="titulo">${escapar(titulo)}</span>` +
    (detalhe ? `<span class="detalhe">${escapar(detalhe)}</span>` : "") +
    `</span></div>`
  );
}

function falhaHTML(env) {
  const negado = env.categoria === "permissao_negada";
  return avisoHTML(
    negado ? "negado" : "erro",
    negado ? "⚠" : "✖",
    env.titulo || "falha ao ler",
    env.mensagem
  );
}

// A explicação é por painel: dizer "o namespace está vazio" no painel de eventos
// contradiz os painéis ao lado quando há pods, e a contradição faz o leitor
// desconfiar da tela inteira em vez de confiar no que ela mostra.
// Título e explicação por painel. Os dois precisam ser específicos: o texto
// genérico dizia "o namespace está vazio" no painel de eventos, contradizendo
// os painéis ao lado quando há pods — e a contradição faz o leitor desconfiar
// da tela inteira. O título genérico produzia "nenhum namespace neste
// namespace", que não quer dizer nada.
const VAZIO_POR_PAINEL = {
  namespace: [
    "nenhum namespace visível",
    "a leitura foi bem-sucedida: o cluster não tem namespaces visíveis para esta credencial.",
  ],
  evento: [
    "nenhum evento recente",
    "a leitura foi bem-sucedida: não há eventos recentes neste namespace.",
  ],
};
const VAZIO = (o) => {
  const [titulo, texto] = VAZIO_POR_PAINEL[o] || [
    `nenhum ${o} neste namespace`,
    `a leitura foi bem-sucedida: não há ${o} neste namespace.`,
  ];
  return avisoHTML("vazio", "—", titulo, texto);
};
const SEM_BUSCA = (o, t) => avisoHTML("sem-busca", "⌕", `nenhum ${o} casa com "${t}"`, "há objetos no namespace, mas nenhum com esse nome.");

/* --- render de cada painel --------------------------------------------- */

// Rótulo do estado vazio por painel. Separado de `rotuloObjeto` de propósito:
// aquele também liga o filtro de busca, e buscar por nome dentro de eventos ou
// de namespaces não é o que a spec pede.
const ROTULO_VAZIO = {
  namespaces: "namespace",
  deployments: "deployment",
  pods: "pod",
  services: "service",
  eventos: "evento",
};

function pintarPainel(id, env, desenhar, rotuloObjeto) {
  const painel = $("#painel-" + id);
  const conteudo = painel.querySelector(".conteudo");
  const contagem = painel.querySelector(".contagem");

  if (!env) {
    conteudo.innerHTML = avisoHTML("vazio", "—", "sem dados", null);
    contagem.textContent = "";
    return;
  }
  if (!env.ok) {
    conteudo.innerHTML = falhaHTML(env);
    contagem.textContent = "(indisponível)";
    return;
  }
  const todos = env.itens || [];
  const termo = estado.busca.trim().toLowerCase();
  const filtrados = termo && rotuloObjeto
    ? todos.filter((i) => (i.nome || "").toLowerCase().includes(termo))
    : todos;

  if (todos.length === 0) {
    conteudo.innerHTML = VAZIO(ROTULO_VAZIO[id] || rotuloObjeto || "objeto");
    contagem.textContent = "(0)";
    return;
  }
  if (filtrados.length === 0) {
    conteudo.innerHTML = SEM_BUSCA(rotuloObjeto || "objeto", estado.busca.trim());
    contagem.textContent = `(0 de ${todos.length})`;
    return;
  }
  contagem.textContent = termo && rotuloObjeto
    ? `(${filtrados.length} de ${todos.length})`
    : `(${filtrados.length})`;
  conteudo.innerHTML = desenhar(filtrados);
}

function classeEstado(e) {
  if (!e) return "";
  if (e === "Running" || e === "Completed" || e === "Succeeded") return "ok";
  if (e.startsWith("Running (") || e === "Pending" || e === "ContainerCreating") return "morno";
  return "ruim";
}

function desenharNamespaces(itens) {
  return (
    '<ul class="namespaces">' +
    itens
      .map(
        (n) =>
          `<li class="${n.nome === estado.namespace ? "selecionado" : ""}">` +
          `<button type="button" data-ns="${escapar(n.nome)}">${escapar(n.nome)}` +
          `<span class="fraco"> · ${escapar(n.idade)}</span></button></li>`
      )
      .join("") +
    "</ul>"
  );
}

function desenharDeployments(itens) {
  return (
    "<table><thead><tr><th>nome</th><th>prontos/desejados</th><th>idade</th></tr></thead><tbody>" +
    itens
      .map(
        (d) =>
          `<tr class="${d.saudavel ? "" : "falha"}"><td>${escapar(d.nome)}</td>` +
          `<td class="estado ${d.saudavel ? "ok" : "ruim"}">${escapar(d.texto)}</td>` +
          `<td class="fraco">${escapar(d.idade)}</td></tr>`
      )
      .join("") +
    "</tbody></table>"
  );
}

function desenharPods(itens) {
  return (
    "<table><thead><tr><th>nome</th><th>estado</th><th>pronto</th><th>restarts</th><th>idade</th></tr></thead><tbody>" +
    itens
      .map(
        (p) =>
          `<tr class="${p.em_falha ? "falha" : ""}"><td>${escapar(p.nome)}</td>` +
          `<td><span class="estado ${classeEstado(p.estado)}">${escapar(p.estado)}</span>` +
          (p.motivo ? `<span class="motivo">${escapar(p.motivo)}</span>` : "") +
          `</td><td class="fraco">${escapar(p.prontos)}</td>` +
          `<td class="${p.reinicios > 0 ? "estado ruim" : "fraco"}">${escapar(p.reinicios)}</td>` +
          `<td class="fraco">${escapar(p.idade)}</td></tr>`
      )
      .join("") +
    "</tbody></table>"
  );
}

function desenharServices(itens) {
  return (
    "<table><thead><tr><th>nome</th><th>tipo</th><th>portas</th><th>endpoint</th></tr></thead><tbody>" +
    itens
      .map((s) => {
        const tag = s.sem_endpoint
          ? '<span class="tag ruim">sem endpoint</span>'
          : `<span class="tag ok">${s.endpoints} endereço${s.endpoints === 1 ? "" : "s"}</span>`;
        return (
          `<tr class="${s.sem_endpoint ? "falha" : ""}"><td>${escapar(s.nome)}</td>` +
          `<td class="fraco">${escapar(s.tipo)}</td>` +
          `<td class="fraco">${escapar((s.portas || []).join(", ") || "-")}</td>` +
          `<td>${tag}</td></tr>`
        );
      })
      .join("") +
    "</tbody></table>"
  );
}

function desenharEventos(itens) {
  return (
    "<table><thead><tr><th>tipo</th><th>motivo</th><th>objeto</th><th>mensagem</th><th>idade</th></tr></thead><tbody>" +
    itens
      .map(
        (e) =>
          `<tr class="${e.tipo === "Warning" ? "falha" : ""}">` +
          `<td><span class="tag ${escapar(e.tipo)}">${escapar(e.tipo)}</span></td>` +
          `<td>${escapar(e.motivo)}</td><td class="fraco">${escapar(e.objeto)}</td>` +
          `<td class="msg">${escapar(e.mensagem)}</td>` +
          `<td class="fraco">${escapar(e.idade)}${e.contagem > 1 ? " x" + escapar(e.contagem) : ""}</td></tr>`
      )
      .join("") +
    "</tbody></table>"
  );
}

/* --- ciclo -------------------------------------------------------------- */

function pintarTudo() {
  const s = estado.snapshot;
  if (!s) return;

  $("#ctx-nome").textContent = s.contexto || "(desconhecido)";
  $("#ctx-servidor").textContent = s.servidor || "(desconhecido)";
  $("#ns-atual").textContent = s.namespace ? "ns: " + s.namespace : "sem namespace";

  // Faixa global: só quando TODOS os painéis falharam pela mesma causa de
  // ambiente (cluster fora do ar / credencial). 403 em um recurso não entra
  // aqui — isso é degradação parcial e aparece no painel.
  const envs = ["namespaces", "deployments", "pods", "services", "eventos"]
    .map((k) => s[k])
    .filter(Boolean);
  const cats = new Set(envs.filter((e) => !e.ok).map((e) => e.categoria));
  const faixa = $("#faixa-global");
  const grave = ["cluster_inalcancavel", "credencial_invalida"].find((c) => cats.has(c));
  if (grave && envs.every((e) => !e.ok)) {
    const ex = envs.find((e) => e.categoria === grave);
    faixa.className = "faixa erro";
    faixa.innerHTML =
      `<span><strong>${escapar(ex.titulo)}</strong> — ${escapar(ex.mensagem)}<br>` +
      `<span class="fraco">contexto <code>${escapar(s.contexto)}</code>, endereço tentado ` +
      `<code>${escapar(s.servidor)}</code></span></span>` +
      `<button type="button" id="btn-retentar">tentar de novo</button>`;
    faixa.querySelector("#btn-retentar").addEventListener("click", atualizar);
  } else {
    faixa.className = "faixa oculto";
    faixa.innerHTML = "";
  }

  pintarPainel("namespaces", s.namespaces, desenharNamespaces, null);
  pintarPainel("deployments", s.deployments, desenharDeployments, "deployment");
  pintarPainel("pods", s.pods, desenharPods, "pod");
  pintarPainel("services", s.services, desenharServices, "service");
  pintarPainel("eventos", s.eventos, desenharEventos, null);

  document.querySelectorAll("ul.namespaces button").forEach((b) => {
    b.addEventListener("click", () => {
      estado.namespace = b.dataset.ns;
      const u = new URL(location.href);
      u.searchParams.set("ns", estado.namespace);
      history.replaceState(null, "", u);
      atualizar();
    });
  });
}

function pintarRelogio() {
  const el = $("#relogio");
  if (!estado.lidoEm) {
    el.textContent = "—";
    return;
  }
  const s = Math.max(0, Math.round((Date.now() - estado.lidoEm) / 1000));
  el.textContent = s < 60 ? `atualizado há ${s}s` : `atualizado há ${Math.floor(s / 60)}min`;
}

async function atualizar() {
  const url = "/api/snapshot" + (estado.namespace ? "?ns=" + encodeURIComponent(estado.namespace) : "");
  try {
    const resp = await fetch(url, { cache: "no-store" });
    estado.snapshot = await resp.json();
    if (!estado.namespace && estado.snapshot.namespace) {
      estado.namespace = estado.snapshot.namespace;
    }
    estado.lidoEm = Date.now();
    pintarTudo();
  } catch (e) {
    // O servidor local caiu. Nem aqui a tela fica em branco.
    const faixa = $("#faixa-global");
    faixa.className = "faixa erro";
    faixa.textContent = "o servidor local do dashboard não respondeu: " + e;
  }
  pintarRelogio();
}

$("#btn-atualizar").addEventListener("click", atualizar);
$("#busca").addEventListener("input", (e) => {
  estado.busca = e.target.value;
  pintarTudo();
});
$("#intervalo").textContent = String(INTERVALO_MS / 1000);
$("#busca").value = estado.busca;

atualizar();
setInterval(atualizar, INTERVALO_MS);
setInterval(pintarRelogio, 1000);
