import assert from 'node:assert/strict';
import {readFile, readdir, stat} from 'node:fs/promises';
import {resolve, relative, sep} from 'node:path';

const root = resolve('dist');
const files = [];
async function walk(directory) {
  for (const entry of await readdir(directory, {withFileTypes: true})) {
    const path = resolve(directory, entry.name);
    assert(!entry.isSymbolicLink(), `Link simbólico no pacote: ${path}`);
    if (entry.isDirectory()) await walk(path);
    else {
      assert(entry.isFile(), `Arquivo especial no pacote: ${path}`);
      files.push({path, name: relative(root, path).split(sep).join('/'), size: (await stat(path)).size});
    }
  }
}
await walk(root);
// A publicação contém somente o app e seus dados públicos.
assert(files.every(f => /^(index\.html|_headers|assets\/[^/]+|fonts\/[^/]+|photos\/[a-f0-9]{64}\.(jpg|jpeg|png)|data\.json|data\/snapshots\/[a-f0-9]+\/[^/]+\.json)$/.test(f.name)), 'Arquivo inesperado no dist; revise antes de publicar');
assert.equal(await readFile(resolve(root, '_headers'), 'utf8'), await readFile('public/_headers', 'utf8'), 'Build sem os cabeçalhos atuais');
assert(files.length <= 20000, 'Cloudflare Pages: mais de 20.000 arquivos');
assert(files.every(f => f.size <= 25 * 1048576), 'Cloudflare Pages: arquivo maior que 25 MiB');
const publicIndex = await readFile('public/data.json', 'utf8');
assert.equal(await readFile(resolve(root, 'data.json'), 'utf8'), publicIndex, 'Build com índice desatualizado');
const dataset = JSON.parse(publicIndex);
async function localFile(url) {
  assert(typeof url === 'string' && !url.startsWith('/') && !url.includes('\\'), `Caminho inválido: ${url}`);
  const path = resolve(root, url);
  assert(path.startsWith(root + sep), `Caminho fora do dist: ${url}`);
  assert((await stat(path)).isFile(), `Arquivo ausente: ${url}`);
  return path;
}
await localFile('index.html');
for (const member of [...dataset.senado, ...dataset.camara]) {
  const detail = JSON.parse(await readFile(await localFile(member.detalhesUrl), 'utf8'));
  assert.equal(detail.versao, dataset.versao);
  assert.equal(detail.mandatoId, member.mandatoId);
  if (member.foto?.arquivoLocal) await localFile(member.foto.arquivoLocal);
}
const snapshots = await readdir(resolve(root, 'data/snapshots'));
assert(snapshots.includes(dataset.versao) && snapshots.length <= 2, 'Esperadas somente a versão atual e, se disponível, a anterior');
const largest = files.reduce((a, b) => a.size > b.size ? a : b);
console.log(JSON.stringify({versao: dataset.versao, arquivos: files.length, tamanhoMiB: +(files.reduce((n, f) => n + f.size, 0) / 1048576).toFixed(2), maiorArquivo: largest.name, maiorArquivoMiB: +(largest.size / 1048576).toFixed(2), snapshots}, null, 2));
