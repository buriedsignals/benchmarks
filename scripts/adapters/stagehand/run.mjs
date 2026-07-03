// Stagehand benchmark adapter: agentic browser workflow via OpenRouter.
// Scored stdout carries ONLY the final page-evidence dump; the instruction
// and all agent chatter go to stderr so probe terms cannot leak into scoring.
import { Stagehand } from "@browserbasehq/stagehand";

const [, , url, instruction] = process.argv;
if (!url || !instruction) {
  console.error("usage: node run.mjs <url> <instruction>");
  process.exit(2);
}
if (!process.env.OPENROUTER_API_KEY) {
  console.error("missing OPENROUTER_API_KEY");
  process.exit(2);
}

const modelName = process.env.STAGEHAND_MODEL || "openai/gpt-4o-mini";
const stagehand = new Stagehand({
  env: "LOCAL",
  model: {
    modelName,
    apiKey: process.env.OPENROUTER_API_KEY,
    baseURL: "https://openrouter.ai/api/v1",
  },
  localBrowserLaunchOptions: { headless: true },
  verbose: 0,
});

console.error(`task: ${instruction}`);
console.error(`model: ${modelName}`);

await stagehand.init();
let exitCode = 0;
try {
  const page = stagehand.context.pages()[0];
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
  const agent = stagehand.agent();
  const result = await agent.execute({ instruction, maxSteps: 12 });
  console.error(
    "agent result:",
    JSON.stringify({ success: result?.success, completed: result?.completed }).slice(0, 300),
  );
  const evidence = await page.evaluate(() => ({
    url: location.href,
    title: document.title,
    text: document.body ? document.body.innerText.slice(0, 18000) : "",
    links: Array.from(document.querySelectorAll("a"))
      .slice(0, 80)
      .map((a) => ({ text: a.innerText, href: a.href })),
  }));
  console.log(JSON.stringify(evidence, null, 2));
} catch (err) {
  console.error("adapter error:", err?.message || err);
  exitCode = 1;
} finally {
  await stagehand.close();
}
process.exit(exitCode);
