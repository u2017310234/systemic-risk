import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../cloudflare-worker';
import { fetchSnapshotByDate, fetchSnapshotSeries } from '../lib/public-data';
const asset = {fetch: async (_request:Request) => Response.json({lastUpdated:'2025-05-16',dataset_kind:'historical_reconstruction',expected_next_update:null})};
test('Worker distinguishes unconfigured MCP and historical status',async()=>{
  const mcp=await worker.fetch(new Request('https://example.com/mcp'),{ASSETS:asset});
  assert.equal(mcp.status,503);
  const status=await worker.fetch(new Request('https://example.com/status.json'),{ASSETS:asset});
  const body=await status.json();
  assert.equal(body.is_stale,null);
  assert.equal(body.expected_next_update,null);
  assert.equal(body.mcp_origin_health,'not_configured');
});
test('Worker preserves upstream SSE, sessions and explicit origin failure',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async(input,init)=>{
      assert.equal(String(input),'https://backend.example/mcp');
      assert.equal(new Headers(init?.headers).get('mcp-session-id'),'abc');
      return new Response('data: hello\n\n',{headers:{'content-type':'text/event-stream','mcp-session-id':'xyz'}});
    };
    const response=await worker.fetch(new Request('https://example.com/mcp',{headers:{'mcp-session-id':'abc'}}),{ASSETS:asset,MCP_ORIGIN_URL:'https://backend.example'});
    assert.equal(response.headers.get('mcp-session-id'),'xyz');
    assert.equal(await response.text(),'data: hello\n\n');
    globalThis.fetch=async()=>{throw new Error('offline')};
    assert.equal((await worker.fetch(new Request('https://example.com/mcp'),{ASSETS:asset,MCP_ORIGIN_URL:'https://backend.example'})).status,502);
  } finally {globalThis.fetch=original;}
});
test('Unknown snapshot never silently returns future/latest data',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>Response.json({lastUpdated:'2025-05-16',dates:['2025-05-16']});
    await assert.rejects(fetchSnapshotByDate('2024-01-01'),/No snapshot/);
    assert.deepEqual((await fetchSnapshotSeries('2024-01-01')).snapshots,[]);
  } finally {globalThis.fetch=original;}
});
test('Data preflight OPTIONS returns CORS headers',async()=>{
  const response=await worker.fetch(new Request('https://example.com/data/latest.json',{method:'OPTIONS'}),{ASSETS:asset});
  assert.equal(response.status,204);assert.equal(response.headers.get('Access-Control-Allow-Origin'),'*');
});
