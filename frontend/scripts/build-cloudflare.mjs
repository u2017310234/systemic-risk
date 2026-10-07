import fs from 'node:fs/promises';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
const root = process.cwd(), stage = path.join(root, '.cf-build');
await fs.rm(stage, {recursive:true, force:true});
await fs.mkdir(stage);
try {
  for (const name of ['app','components','lib','public','package.json','tsconfig.json','next-env.d.ts','postcss.config.mjs','tailwind.config.ts']) await fs.cp(path.join(root,name),path.join(stage,name),{recursive:true});
  for (const name of ['mcp','status.json','api']) await fs.rm(path.join(stage,'app',name),{recursive:true,force:true});
  await fs.symlink(path.join(root,'node_modules'),path.join(stage,'node_modules'),'dir');
  await fs.writeFile(path.join(stage,'next.config.mjs'),'export default {output:"export",trailingSlash:true,images:{unoptimized:true},experimental:{cpus:2}};\n');
  const result = spawnSync(process.execPath,[path.join(root,'node_modules/next/dist/bin/next'),'build'],{cwd:stage,stdio:'inherit',env:{...process.env,NEXT_TELEMETRY_DISABLED:'1'}});
  if (result.status !== 0) throw new Error(`Static build failed: ${result.status}`);
  await fs.rm(path.join(root,'out'),{recursive:true,force:true});
  await fs.cp(path.join(stage,'out'),path.join(root,'out'),{recursive:true});
} finally { await fs.rm(stage,{recursive:true,force:true}); }
console.log('Cloudflare assets ready: out/');
