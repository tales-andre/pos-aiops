// Extrai o Prompt 1 (Geração) de prompt.md e substitui os {{placeholders}}.
// Existe só para o promptfooconfig.yaml testar a geração isoladamente, sem duplicar
// o texto do prompt — prompt.md continua sendo a única fonte de verdade.
const fs = require("fs");
const path = require("path");

module.exports = function ({ vars }) {
  const raw = fs.readFileSync(path.join(__dirname, "prompt.md"), "utf8");
  const marker = "## Prompt 1 — Geração";
  const start = raw.indexOf(marker);
  if (start === -1) throw new Error("Marcador do Prompt 1 não encontrado em prompt.md");
  const afterMarker = raw.slice(start);
  const match = afterMarker.match(/```\n([\s\S]*?)\n```/);
  if (!match) throw new Error("Bloco de código do Prompt 1 não encontrado");

  let prompt = match[1];
  for (const [key, value] of Object.entries(vars)) {
    prompt = prompt.split(`{{${key}}}`).join(value);
  }
  return prompt;
};
