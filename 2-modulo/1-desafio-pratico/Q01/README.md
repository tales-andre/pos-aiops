# Questão 01 — Dockerfile para o Lift

## Framework: R-T-F (Role – Task – Format)

---

## Prompt

**Role:** Você é um DevOps Engineer especialista em containerização e criação de Dockerfile com boas práticas de produção.

**Task:** Construa um Dockerfile para uma API Python/Flask na porta 8080 incluindo duas variáveis de ambiente que precisam estar presentes no runtime: `DATABASE_URL` e `API_KEY`.
Em produção o serviço sobe com `gunicorn --bind 0.0.0.0:8080 --workers 4 app:app`.
Considere a estrutura de arquivos: `lift/app.py`, `lift/lib/auth.py`, `lift/lib/storage.py` e `lift/tests/test_app.py`.
O `requirements.txt` possui o seguinte conteúdo: Flask==3.0.0 gunicorn==21.2.0 requests==2.31.0 python-dotenv==1.0.0 psycopg2-binary==2.9.9

**Format:** Gere o Dockerfile puro dessa aplicação com comentários explicando cada decisão.

---

## Modelo

**Claude Sonnet 4.5** Escolhido por ser um modelo intermediário e mais barato que o Sonnet 4.6, que acredito funcionar bem com prompts bem estruturados e tarefas simples.

---

## Output

https://claude.ai/share/c24ca5e2-a837-45cb-b507-df04b4a2bbcd

---

## Justificativa

- **Role:** a primeira linha do prompt define a persona como especialista em containers utilizando boas práticas para construir Dockerfiles, instruindo o modelo a seguir um caminho técnico.
- **Task:** Solicito detalhadamente o que deve ser construído no Dockerfile, com informações essenciais presentes na questão: API Flask na porta 8080, variáveis de ambiente de runtime (`DATABASE_URL`, `API_KEY`), comando de produção com gunicorn, estrutura do projeto e conteúdo do `requirements.txt`. Tentei ajustar o path dos arquivos para que o modelo não confundisse a estrutura.
- **Format:** Solicito apenas o dockerfile com comentários, explicando a decisão de cada linha, sem a necessidade de arquivos adicionais ou informações que não seriam relevantes para o contexto.
