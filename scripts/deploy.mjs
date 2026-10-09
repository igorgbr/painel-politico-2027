import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const project = process.env.CLOUDFLARE_PAGES_PROJECT;
for (const name of ['CLOUDFLARE_API_TOKEN', 'CLOUDFLARE_ACCOUNT_ID', 'CLOUDFLARE_PAGES_PROJECT']) {
  if (!process.env[name]?.trim()) {
    console.error(`Defina ${name} no ambiente do terminal (ver README).`);
    process.exit(1);
  }
}
if (!/^[a-f0-9]{32}$/i.test(process.env.CLOUDFLARE_ACCOUNT_ID) || !/^[a-z0-9][a-z0-9-]*$/.test(project)) {
  console.error('Account ID ou nome do projeto inválido.');
  process.exit(1);
}
function run(command, args, env = process.env) {
  const result = spawnSync(command, args, {cwd: root, stdio: 'inherit', env});
  if (result.error || result.status !== 0) {
    console.error(result.error ? `Não foi possível iniciar ${command}.` : `Etapa interrompida: ${command} (código ${result.status ?? result.signal}).`);
    process.exit(result.status || 1);
  }
}
// O token só é entregue ao Wrangler, depois que a release passar.
const checkEnv = {...process.env};
delete checkEnv.CLOUDFLARE_API_TOKEN;
run('npm', ['run', 'release:check'], checkEnv);
run(process.execPath, ['node_modules/wrangler/bin/wrangler.js', 'pages', 'deploy', 'dist', '--project-name', project, '--branch', 'main'], {...process.env, CI: 'true', WRANGLER_SEND_METRICS: 'false'});
