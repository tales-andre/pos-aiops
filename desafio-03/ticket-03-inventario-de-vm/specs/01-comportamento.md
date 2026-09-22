# Especificação de comportamento — inventário e drift de VM

Descreve **o que** a ferramenta faz, observável de fora. Decisões de **como** estão em
[`02-decisoes.md`](./02-decisoes.md).

## Invocação

```
inventario --host <endereco> --usuario <user> --chave <caminho> \
           --baseline <caminho> [--formato json|markdown|ambos] [--saida <dir>]
```

Roda na máquina de quem opera. Nada é instalado, copiado ou executado com escrita no host alvo.

## Os dois invariantes

**I1 — Só lê.** Nada é instalado, escrito ou corrigido do outro lado da conexão. Duas execuções
seguidas contra o mesmo host devolvem o mesmo veredito para cada regra, mudando entre elas apenas
`host.coletado_em`.

**I2 — A chave privada é credencial, não parâmetro.** Ela não aparece na saída, nem no log, nem em
mensagem de erro. O que circula é o **caminho** do arquivo, nunca o conteúdo.

Os dois são verificáveis de fora, e por isso viram critério de aceite.

## O inventário

Uma execução coleta os campos abaixo. Cada um que não puder ser coletado vira `null` no inventário
e alimenta um veredito `nao_verificado` na conformidade — nunca um valor inventado.

| Grupo | Campos |
|---|---|
| identificação | endereço usado na conexão, hostname que o host reporta, instante da coleta em UTC |
| sistema operacional | distribuição, versão |
| kernel | versão em execução |
| serviços | nome, tipo e estado de cada unidade — **distinguindo `service` de `socket`**, porque o baseline proíbe duas que são socket |
| swap | habilitado, e o tamanho quando estiver |
| portas em escuta | número, endereço de bind e processo dono — porque "9100 aberta para o mundo" e "9100 só no endereço interno" são conformidades diferentes |
| chaves SSH autorizadas | quantas existem e a identificação de cada uma, que é o que permite dizer se foram emitidas pela plataforma |
| ssh | configuração **efetiva** de login de root — a que vale, não a que está escrita no arquivo |
| ntp | se o relógio está sincronizado e por qual mecanismo |

## A conformidade

Uma entrada por regra do baseline, com quatro informações: **qual regra**, **o que o baseline
esperava**, **o que foi encontrado no host**, e **o veredito**.

O veredito tem três valores, não dois:

| Veredito | Quando | Campo extra |
|---|---|---|
| `conforme` | o encontrado satisfaz o esperado | — |
| `desvio` | o encontrado contraria o esperado | `severidade`, lida do baseline |
| `nao_verificado` | o dado não pôde ser coletado | `motivo` |

O terceiro existe porque a coleta entra com um usuário comum e parte do que o baseline pede só se
lê com privilégio. Reportar isso como `conforme` seria mentira, e abortar a execução inteira por
causa disso seria inútil.

**A severidade vem do baseline, não do código.** A ferramenta lê a seção `severidade` e obedece.
Mudar a política da casa não pode exigir mudar a ferramenta.

## As duas saídas

O mesmo dado, dois renderizadores. JSON porque o Roster vai consumir automaticamente quando
existir; Markdown porque o plantão lê no terminal às três da manhã.

### JSON

```json
{
  "host": {"endereco": "10.42.7.14", "hostname": "construct-node-14",
           "coletado_em": "2026-08-12T09:14:02Z"},
  "inventario": {
    "so": {"distribuicao": "ubuntu", "versao": "22.04.4"},
    "kernel": {"versao": "5.15.0-118-generic"},
    "servicos": [{"nome": "ssh.service", "tipo": "service", "estado": "active"}],
    "swap": {"habilitado": true, "tamanho": "4G"},
    "portas_em_escuta": [{"porta": 9100, "bind": "0.0.0.0", "processo": "node_exporter"}],
    "chaves_ssh": [{"identificacao": "platform@metacortex-platform"}],
    "ssh": {"login_de_root": null},
    "ntp": {"sincronizado": true, "mecanismo": "systemd-timesyncd"}
  },
  "conformidade": [
    {"regra": "kernel.versao_minima", "esperado": "6.5",
     "encontrado": "5.15.0-118-generic", "veredito": "desvio", "severidade": "medio"},
    {"regra": "ssh.login_de_root", "esperado": false,
     "encontrado": null, "veredito": "nao_verificado",
     "motivo": "exige privilegio que o usuario da coleta nao tem"}
  ],
  "resumo": {"conforme": 4, "desvio": 4, "nao_verificado": 1,
             "por_severidade": {"critico": 2, "alto": 1, "medio": 1}}
}
```

### Markdown

```markdown
# Inventário — construct-node-14 (10.42.7.14)
Coletado em 2026-08-12 09:14 UTC · baseline v1

## Desvios

| Severidade | Regra | Esperado | Encontrado |
|---|---|---|---|
| crítico | swap.habilitado | false | true (4G) |
| crítico | portas_em_escuta.somente_rede_interna | 9100 na rede interna | 9100 em 0.0.0.0 |
| alto | servicos.ativos | chrony ativo | ausente |
| médio | kernel.versao_minima | 6.5 | 5.15.0-118-generic |

## Não verificado

| Regra | Motivo |
|---|---|
| ssh.login_de_root | exige privilégio que o usuário da coleta não tem |

## Conforme
so.distribuicao · so.versao_minima · servicos.proibidos · ntp.sincronizado
```

## Código de saída

Precisa servir num pipeline, então distingue os casos que exigem ação diferente:

| Código | Significado |
|---|---|
| `0` | host conforme — nenhum desvio |
| `1` | há desvio de severidade `critico` ou `alto` |
| `2` | há desvio apenas de severidade `medio` |
| `3` | host inalcançável, credencial recusada ou SSH fora do ar |
| `4` | erro de uso — baseline ausente, argumento inválido |

O `3` é separado de propósito: pipeline que trata "não consegui olhar" como "está tudo bem" é
pior que pipeline nenhum.

## Critérios de aceite

1. **Host conforme sai sem desvio** e com código `0`.
2. **Host com desvios** sai com cada um classificado pela severidade que o baseline atribui.
3. **Regra não verificável aparece como `nao_verificado`**, visualmente distinta de `conforme`, nos
   dois formatos.
4. **Host inalcançável** — endereço errado, chave recusada, SSH fora do ar — falha com mensagem
   que diz o que houve, sem stack trace cru, e não é confundido com host conforme.
5. **Execução repetida devolve o mesmo retrato**: dois JSON consecutivos são idênticos exceto por
   `host.coletado_em`.
6. **A chave privada não aparece** em nenhuma das saídas, nem em mensagem de erro.
