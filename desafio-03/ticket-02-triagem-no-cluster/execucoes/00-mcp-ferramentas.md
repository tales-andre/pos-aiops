# Ferramentas do mcp-server-kubernetes, com e sem a flag nao-destrutiva

Levantado por handshake MCP direto (tools/list) contra o servidor, em 22/09/2026.

## Modo padrao (24 ferramentas)

- cleanup
- exec_in_pod
- explain_resource
- install_helm_chart
- kubectl_apply
- kubectl_context
- kubectl_create
- kubectl_delete
- kubectl_describe
- kubectl_generic
- kubectl_get
- kubectl_logs
- kubectl_patch
- kubectl_reconnect
- kubectl_rollout
- kubectl_scale
- kubernetes
- list_api_resources
- node_management
- ping
- port_forward
- stop_port_forward
- uninstall_helm_chart
- upgrade_helm_chart

## Com ALLOW_ONLY_NON_DESTRUCTIVE_TOOLS=true (19 ferramentas)

- exec_in_pod
- explain_resource
- install_helm_chart
- kubectl_apply
- kubectl_context
- kubectl_create
- kubectl_describe
- kubectl_get
- kubectl_logs
- kubectl_patch
- kubectl_reconnect
- kubectl_rollout
- kubectl_scale
- kubernetes
- list_api_resources
- ping
- port_forward
- stop_port_forward
- upgrade_helm_chart

## O que a flag remove

- cleanup
- kubectl_delete
- kubectl_generic
- node_management
- uninstall_helm_chart

## O que a flag NAO remove, e ainda escreve no cluster

- kubectl_apply
- kubectl_create
- kubectl_patch
- kubectl_scale
- kubectl_rollout
- exec_in_pod
- install_helm_chart
- upgrade_helm_chart
- port_forward
