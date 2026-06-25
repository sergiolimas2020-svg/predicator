const fs = require("fs");

const source = fs.readFileSync("api/ai-chat.js", "utf8");
const checks = [
  "Over de 1.5 tiros a puerta de Cody Gakpo",
  "Over 1.5 tiros a puerta de Vinicius Junior"
];

const results = [];
eval(`${source}
for (const question of checks) {
  const answer = buildAnswer(question);
  results.push({ question, answer });
}`);

let failed = false;
for (const result of results) {
  if (result.answer.includes("JUGADOR NO ENCONTRADO")) {
    failed = true;
    console.error(`FAIL: ${result.question}`);
    console.error(result.answer);
  } else {
    const firstLine = result.answer.split("\\n")[0];
    console.log(`OK: ${result.question} -> ${firstLine}`);
  }
}

if (failed) process.exit(1);
