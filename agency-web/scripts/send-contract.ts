#!/usr/bin/env node
import { loadDocuSealConfigFromEnv, sendComboContract } from "../lib/contracts.js";

function parseArgs(argv: string[]) {
  const out: Record<string, string> = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i]?.startsWith("--") && argv[i + 1]) {
      out[argv[i].slice(2)] = argv[i + 1];
      i++;
    }
  }
  return out;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const email = args.email;
  const name = args.name;

  if (!email || !name) {
    console.error("Pflicht: --email und --name");
    process.exit(1);
  }

  const config = loadDocuSealConfigFromEnv();
  const result = await sendComboContract(config, {
    customer: { email, name, company: args.company },
    metadata: { company: args.company ?? "", source: "agency-web-cli" },
  });

  console.log(JSON.stringify({ ok: true, submission: result }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
