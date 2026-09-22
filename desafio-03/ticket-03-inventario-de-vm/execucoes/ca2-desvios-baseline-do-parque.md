# Inventário — DESKTOPDEVOPS (localhost)
Coletado em 2026-09-22 19:14:38 UTC · baseline v1

Resumo: **6 conforme · 4 desvio · 1 não verificado**

## Desvios

| Severidade | Regra | Esperado | Encontrado |
|---|---|---|---|
| crítico | swap.habilitado | false | true (2G) |
| crítico | portas_em_escuta.publicas_permitidas | 22 | 4369 em * |
| crítico | chaves_ssh.emitidas_por | metacortex-platform | inventario-metacortex |
| alto | servicos.ativos | ssh, containerd, node_exporter, chrony | ssh: active, containerd: active, node_exporter: ausente, chrony: ausente |

## Não verificado

| Regra | Motivo |
|---|---|
| ssh.login_de_root | exige privilegio que o usuario da coleta nao tem |

## Conforme

so.distribuicao · so.versao_minima · kernel.versao_minima · servicos.proibidos · portas_em_escuta.somente_rede_interna · ntp.sincronizado
