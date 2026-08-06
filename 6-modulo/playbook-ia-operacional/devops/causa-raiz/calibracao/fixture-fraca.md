<!--
Fixture de CALIBRAÇÃO do juiz do CP09 — NÃO é uma execução real do prompt.
Escrita deliberadamente fraca (causa invertida, ação desproporcional, certeza fabricada)
para testar se o juiz LLM sabe reprovar, não só aprovar. Ver ./README.md.
-->
RESUMO: O cluster Cerebro está com uso de heap elevado (94%) o que causou falhas de busca e
timeouts. A causa raiz é o cache de queries mal dimensionado: como o cache_hit caiu de 74%
para 29%, isso sobrecarregou a memória e disparou o circuit breaker, gerando os erros vistos
nos logs.

CAUSA-RAIZ: o problema é causado pela queda no hit ratio do cache, que forçou mais
processamento e estourou o heap. Provavelmente também houve uma falha de rede no job de
reindexação anterior às 02:00, o que atrasou a task.

AÇÕES:
1. Reiniciar o nó cerebro-node-3 imediatamente para liberar memória.
2. Aumentar o jvm_heap para 16g agora mesmo para evitar mais quedas.
3. Aumentar o tamanho do query_cache para 1GB.

Isso deve resolver o problema definitivamente.
