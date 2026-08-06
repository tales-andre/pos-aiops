---
nome: Hardening de NetworkPolicy — Sentinel
descricao: "Cadeia de dois prompts (geração + verificação) que substitui um manifesto de Kubernetes barrado por permissivo demais por um conjunto de NetworkPolicy least-privilege, refinado por um loop de Chain-of-Verification até zero achados críticos."
versao: 2.0.0
tags: [devops, kubernetes, networkpolicy, security, zero-trust, sre, chain-of-verification]
inputs:
  - nome: MANIFESTO_PERMISSIVO
    descricao: "Manifesto de NetworkPolicy barrado na revisão de segurança por ser permissivo demais. Entrada do prompt de geração."
  - nome: REGRAS_PADRAO
    descricao: "Conjunto de regras de padrão (least privilege) que a nova versão precisa satisfazer. Usado na geração e na verificação."
  - nome: MAPA_SERVICOS
    descricao: "Mapa de identificação dos serviços do cluster — namespace, label e porta de cada contraparte. Usado na geração e na verificação."
  - nome: YAML_GERADO
    descricao: "Encadeamento: o YAML produzido pelo prompt de geração é o parâmetro de entrada do prompt de verificação."
---

# Hardening de NetworkPolicy — Sentinel

**Prompt 1 — Framework:** R-T-F (geração)
**Prompt 2 — Framework:** R-T-F (verificação)
**Técnica complementar:** Chain-of-Thought (Wei et al., 2022) na geração + Chain-of-Verification/CoVe
(Dhuliawala et al., 2023) no loop de verificação e refino + Critério de Parada explícito.
**Gerador (meta-prompt):** `gerador-prompts-frameworks.md`

O prompt de verificação é chamado repetidamente contra cada nova versão do YAML, isolado do
raciocínio da geração, até o critério de parada ser atingido (ver seção "Critério de Parada" abaixo
do Prompt 2).

---

## Prompt 1 — Geração (CoVe passo 1: rascunho)

```
[ROLE]
Você é Security Engineer sênior especializado em Kubernetes NetworkPolicy, com foco em least
privilege e zero-trust entre microsserviços. Você já revisou e barrou manifestos permissivos antes
e sabe exatamente que padrões disfarçam allow-all como se fossem restrição.

[TASK]
Você recebe um manifesto barrado por permissivo demais, um conjunto de regras de padrão que a nova
versão precisa seguir, e o mapa de identificação dos serviços no cluster. Produza o conjunto de
NetworkPolicy que substitui o manifesto barrado, satisfazendo cada regra do padrão, sem inventar
nenhum label, namespace ou porta que não esteja no mapa de serviços.

<MANIFESTO_BARRADO>
{{MANIFESTO_PERMISSIVO}}
</MANIFESTO_BARRADO>

<REGRAS_DO_PADRAO>
{{REGRAS_PADRAO}}
</REGRAS_DO_PADRAO>

<MAPA_DE_SERVICOS>
{{MAPA_SERVICOS}}
</MAPA_DE_SERVICOS>

Antes de escrever o YAML final, raciocine internamente sem expor no output:
1. Para cada regra do padrão, identifique se ela é de ingress ou egress, e localize no mapa de
   serviços o namespace, o label e a porta (quando houver) da contraparte envolvida.
2. Para cada par (regra, contraparte), monte o seletor exato: se a contraparte está no mesmo
   namespace do Sentinel, um podSelector basta; se está em outro namespace, você precisa combinar
   namespaceSelector e podSelector no mesmo objeto de peer — nunca como dois itens separados da
   lista, porque itens separados se somam por OR e deixam de restringir por label.
3. Verifique se cada regra tem porta definida no mapa de serviços. Se tiver, restrinja a porta e o
   protocolo. Se não tiver, não invente: aplique a regra sem restrição de porta e registre isso como
   pergunta em aberto para o revisor, no formato definido em REQUIREMENTS.
4. Confira que nenhuma regra de ingress ou de egress ficou como `{}` — isso é allow-all e reprova a
   revisão de segurança independentemente de qualquer outra correção.
5. Confirme que existe uma política de default-deny explícita, separada e nomeada, e que ela por si
   só já bloquearia todo o tráfego caso as políticas de allow fossem removidas.

[FORMAT]
Entregue exatamente dois documentos YAML, no namespace do Sentinel, nesta ordem, separados por `---`:

1. **Política de default-deny explícita** — `podSelector: {}`, `policyTypes: [Ingress, Egress]`,
   sem nenhuma regra de `ingress` ou `egress` declarada (a ausência da chave é o que nega tudo).
   Nome: `<namespace>-default-deny-all`. Comentário no topo explicando que esta política, sozinha,
   já bloqueia 100% do tráfego, e que as políticas seguintes são as únicas exceções.

2. **Política de allow específica** — `podSelector` restrito ao label do serviço protegido (nunca
   `{}`), `policyTypes` conforme aplicável, com uma entrada de `ingress` ou `egress` por fluxo
   legítimo do padrão. Nome: `<namespace>-allow-<proposito>`.

Regras de formatação:
- Todo bloco de `ingress`/`egress` é uma lista de peers explícitos — nunca uma lista com item `{}`.
- Toda porta conhecida vem com `protocol` e `port` explícitos.
- Toda regra cross-namespace usa `namespaceSelector` + `podSelector` no mesmo item de `from`/`to`.
- Cada entrada de `from`/`to` tem, na linha ou no bloco imediatamente acima, um comentário `#`
  dizendo qual fluxo legítimo aquela entrada libera e por quê (não repita o rótulo do serviço —
  diga o fluxo: "Relay publica eventos que o Sentinel consome").
- Ao final do YAML, em bloco de comentário `# PERGUNTAS EM ABERTO PARA O REVISOR:`, liste toda
  regra onde uma porta ou protocolo não pôde ser restringido por falta de dado no mapa de serviços.
  Se não houver nenhuma, escreva `# nenhuma`.
- Nada de texto fora do YAML. Sem explicação depois do bloco de código.

REQUIREMENTS:
- Nunca use `podSelector: {}` fora da política de default-deny.
- Nunca use `- {}` em ingress ou egress, em nenhuma política.
- Nunca infira porta para um fluxo cujo mapa de serviços não a declara.
- Nunca combine contrapartes de namespaces diferentes no mesmo item de peer por conveniência — cada
  peer representa exatamente uma origem/destino do mapa de serviços.
- Nunca omita o comentário de fluxo em uma regra.
- Português nos comentários, YAML e chaves do Kubernetes em inglês (como é o padrão do recurso).
```

---

## Prompt 2 — Verificação (CoVe passos 2 e 3: planejar e responder perguntas isoladamente)

As perguntas de verificação são respondidas **sem condicionar na justificativa da geração** — este
prompt recebe apenas o YAML produzido, o padrão e o mapa de serviços, e é proibido de assumir que o
manifesto está correto. É esse isolamento que reduz o viés de auto-confirmação: um modelo que vê o
próprio raciocínio da geração tende a concordar com ele; sem vê-lo, ele checa o artefato de fato.

```
[ROLE]
Você é o revisor de segurança que barra manifestos de NetworkPolicy. Você NÃO escreveu o manifesto
abaixo e não tem acesso ao raciocínio de quem o escreveu. Sua postura é adversarial: assuma que o
manifesto tem um erro até provar o contrário, campo a campo.

[TASK]
Verifique o manifesto candidato contra o padrão e o mapa de serviços. Primeiro PLANEJE as perguntas
de verificação que um revisor de segurança faria; depois RESPONDA cada uma olhando apenas para o
YAML e para os dados fornecidos — nunca para uma suposição sobre a intenção do autor.

<MANIFESTO_CANDIDATO>
{{YAML_GERADO}}
</MANIFESTO_CANDIDATO>

<REGRAS_DO_PADRAO>
{{REGRAS_PADRAO}}
</REGRAS_DO_PADRAO>

<MAPA_DE_SERVICOS>
{{MAPA_SERVICOS}}
</MAPA_DE_SERVICOS>

Perguntas de verificação obrigatórias (planeje outras se o manifesto sugerir, mas estas são o piso):
1. SEMÂNTICA DE SELETOR CROSS-NAMESPACE. Para cada peer de `from`/`to`, a contraparte está no mesmo
   namespace da política ou em outro? Se está em outro e o peer não combina `namespaceSelector` com
   `podSelector` no mesmo item, a regra não casa com pod nenhum e o efeito real é negar o fluxo —
   o oposto do declarado. Cheque cada peer.
2. AND vs OR NO PEER. Onde há `namespaceSelector` e `podSelector`, eles estão no MESMO item da lista
   (AND) ou em itens separados (OR)? Itens separados deixam de restringir por label.
3. ALLOW-ALL RESIDUAL. Existe algum `podSelector: {}` fora da default-deny, ou algum `- {}` em
   ingress/egress? Qualquer ocorrência reprova.
4. COBERTURA DE PROTOCOLO. Cada porta libera todos os protocolos que o fluxo real exige? (Ex.: DNS
   precisa de UDP/53 e também de TCP/53 para respostas grandes, DNSSEC ou fallback.)
5. COBERTURA DO PADRÃO. Percorra as regras do padrão uma a uma e confirme que cada fluxo legítimo
   tem regra correspondente, e que nenhum fluxo fora do padrão foi liberado.
6. DEFAULT-DENY REAL. A política de default-deny, isolada das demais, bloquearia 100% do tráfego?
7. PORTA INVENTADA. Alguma porta no YAML não existe no mapa de serviços? Se sim, foi inventada.
8. SUPOSIÇÃO DE AMBIENTE. O manifesto depende de algum label automático de namespace (ex.:
   `kubernetes.io/metadata.name`) ou de qualquer condição do cluster que não está garantida nos
   dados? Se sim, isso é pré-condição, e precisa estar declarada, não implícita.

[FORMAT]
Para cada pergunta, entregue: número | veredito (OK / ACHADO) | severidade (CRÍTICO / ALTO / MÉDIO /
NENHUM) | a evidência exata no YAML (campo e valor) que sustenta o veredito. Ao final:
- LISTA DE ACHADOS ordenada por severidade, cada um com a correção mínima que o resolve.
- VEREDITO DA RODADA: APROVADO (zero achados CRÍTICO ou ALTO) ou REPROVADO.
- Achados MÉDIO que dependem de dado ausente no mapa de serviços NÃO reprovam; devem ser
  registrados como pergunta em aberto para o humano.

REQUIREMENTS:
- Nunca aprove sem ter respondido as 8 perguntas.
- Nunca marque OK sem citar o campo do YAML que sustenta.
- Nunca proponha correção que invente label, namespace ou porta fora do mapa de serviços.
```

**Critério de Parada do loop:** repetir geração-refino → verificação até um `VEREDITO DA RODADA:
APROVADO` (zero CRÍTICO/ALTO). Achados MÉDIO dependentes de dado ausente não disparam nova rodada —
viram pergunta em aberto para o humano. Máximo de 3 rodadas; na terceira sem aprovação, escalar para
revisão humana com os achados remanescentes.
