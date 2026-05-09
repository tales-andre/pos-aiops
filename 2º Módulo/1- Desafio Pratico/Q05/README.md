# Questão 05 - Modernizar deployment legado

## Framework: B-A-B (Before – After - Bridge)

---

## Prompt

**Before:** Possuo um deployment legado que foi escrito três anos atrás e nunca mais foi atualizado. Muitos padrões e obrigações da empresa não estão presentes nesse deployment:
- Possui apenas 1 réplica (sem alta disponibilidade)
- Imagem não possui controle de versão, utilizando tag latest
- As secrets estão hardcoded no deployment
- Não possui resource requests e limits
- Não possui liveness e readiness probes
- Não possui securityContext.

Verifique o estado atual do deployment: 

apiVersion: apps/v1
kind: Deployment
metadata:
  name: chronos-api
  namespace: production
spec:
  replicas: 1
  selector:
    matchLabels:
      app: chronos-api
  template:
    metadata:
      labels:
        app: chronos-api
    spec:
      containers:
      - name: api
        image: chronos-api:latest
        ports:
        - containerPort: 8080
        env:
        - name: DB_PASSWORD
          value: "P@ssw0rd2023!"
        - name: JWT_SECRET
          value: "hvt-jwt-prod-secret"

**After:** A nova versão do deployment deve seguir os padrões da empresa:
- Possuir alta disponibilidade
- Utilizar tags de versão nas imagens, nunca utilizar versão Latest
- Secrets devem estar fora do manifest
- Deve possuir resource requests e resource limits
- Deve possuir Liveness e Readiness Probes
- securityContext: non-root
- Aplicar as melhores práticas de produção recomendadas no mercado hoje em dia.

**Bridge:** Gere a nova versão do deployment no formato yaml com comentários explicando cada mudança em relação ao deployment original.

---

## Modelo

**Sonnet 4.5** — Acredito que o Claude para escrita de códigos e manifestos tem um desempenho melhor que o Gemini, e o modelo intermediário cumpre o seu papel para uma estrutura simples de yaml.

---

## Output

https://claude.ai/share/daa32d84-34bf-4b1d-961c-2e8e5add5d7a
(resultados anexos na pasta Q05/Anexos)
Path do Yaml Atualizado: Q05/Anexos/chronos-api-deployment.yaml
Path do Resumo de Mudanças: Q05/Anexos/RESUMO_MUDANCAS.md

---

## Justificativa

- **Before:** Mostro o estado atual do meu deployment, o contexto de mais de 3 anos sem atualizações e os principais problemas.
- **After:** Informo quais as alterações devem ser realizadas no novo deployment.
- **Bridge:** Informo qual o resultado esperado do novo deployment em relação ao original e peço a inclusão de comentários para ficar claro as diferenças entre o "Before e After"

---
