# Evidência dos critérios de aceite

Gerado por `execucoes/gerar-evidencias.sh` contra o host SSH real
(`tales@localhost`, chave `~/.ssh/inventario_ed25519`) em 2026-09-22 19:14 UTC.

| Cenário | Critério | Esperado | Obtido | Arquivo |
|---|---|---|---|---|
| erro de uso (4 variantes) | tabela de codigo de saida | `4` | `4` | `00-erro-de-uso.txt` |
| host conforme | CA1 | `0` | `0` | `ca1-host-conforme.json / .md` |
| desvios (baseline do parque) | CA2, CA3 | `1` | `1` | `ca2-desvios-baseline-do-parque.json / .md` |
| apenas desvio medio | tabela de codigo de saida | `2` | `2` | `ca2-apenas-desvio-medio.json` |
| endereco nao resolve | CA4 | `3` | `3` | `ca4-endereco-nao-resolve.txt` |
| host inalcancavel (timeout) | CA4 | `3` | `3` | `ca4-host-inalcancavel-timeout.txt` |
| credencial recusada | CA4 | `3` | `3` | `ca4-chave-recusada.txt` |
| execucao repetida | CA5 | `identico exceto coletado_em` | `2 alteradas / 2 em coletado_em` | `ca5-diff.txt` |
| sigilo da chave privada | CA6 | `nenhum vazamento` | `ver arquivo` | `ca6-vazamento-de-chave.txt` |
| SSH fora do ar | CA4 | `3` | `3` | `ca4-ssh-fora-do-ar.txt` |

Os arquivos `*-codigo-de-retorno.txt` trazem o código de retorno de cada cenário
com o comando que o produziu.
