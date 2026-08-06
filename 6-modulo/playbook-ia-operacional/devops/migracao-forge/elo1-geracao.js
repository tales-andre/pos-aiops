// Extrai o Elo 1 (Diagnóstico) de prompt.md e substitui os {{placeholders}}.
// Mesmo padrão do prompt-geracao.js do networkpolicy-sentinel (CP08): prompt.md
// continua sendo a única fonte de verdade, isto só recorta o elo certo em runtime.
const fs = require("fs");
const path = require("path");

module.exports = function ({ vars }) {
  const raw = fs.readFileSync(path.join(__dirname, "prompt.md"), "utf8");
  const marker = "## Elo 1 — Diagnóstico do estado atual";
  const start = raw.indexOf(marker);
  if (start === -1) throw new Error("Marcador do Elo 1 não encontrado em prompt.md");
  const afterMarker = raw.slice(start);
  const match = afterMarker.match(/```\n([\s\S]*?)\n```/);
  if (!match) throw new Error("Bloco de código do Elo 1 não encontrado");

  let prompt = match[1];
  for (const [key, value] of Object.entries(vars)) {
    prompt = prompt.split(`{{${key}}}`).join(value);
  }
  return prompt;
};
