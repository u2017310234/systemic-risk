import test from 'node:test';
import assert from 'node:assert/strict';
import { buildInterpretiveGraph } from '../lib/network-builder';
import { systemSnapshotSchema, type SystemSnapshot, type BankMetric } from '../lib/types';
import { pearsonCorrelation } from '../lib/utils';
import { comparableTotals } from '../lib/public-data';
import { formatUsdBn, formatPercent, formatDelta } from '../lib/format';
const bank=(id:string,value:number|null):BankMetric=>({bank_id:id,bank_name:id,region:'US',mes:-.01,lrmes:.4,covar:-.02,delta_covar:value==null?null:-value/1000,srisk_usd_bn:value,srisk_share_pct:50,market_cap_usd_bn:100,debt_usd_bn:1000});
const snap=(day:number,a:number|null,b:number|null):SystemSnapshot=>({date:`2024-01-${String(day).padStart(2,'0')}`,methodology_version:'2.0-beta-scenario',system_srisk_usd_bn:null,covered_srisk_usd_bn:a!=null&&b!=null?a+b:null,banks:[bank('A',a),bank('B',b)]});
test('nullable payload parses without replacing unknown with zero',()=>{
 assert.equal(systemSnapshotSchema.parse(snap(1,null,2)).banks[0].srisk_usd_bn,null);
 assert.equal(formatUsdBn(null),'N/A');assert.equal(formatPercent(null),'N/A');assert.equal(formatDelta(null),'N/A');
 assert.throws(()=>systemSnapshotSchema.parse({...snap(1,1,2),system_srisk_usd_bn:Infinity}));
});
test('invalid/constant/mismatched correlation is unavailable',()=>{
 assert.equal(pearsonCorrelation([1,1,1],[2,2,2]),null);
 assert.equal(pearsonCorrelation([1,2],[1,2,3]),null);
 assert.equal(pearsonCorrelation([1,NaN],[1,2]),null);
 assert.equal(pearsonCorrelation([1,2,3],[3,2,1]),-1);
});
test('same region with no time-series evidence cannot create an edge',()=>{
 const current=snap(20,1,2);assert.equal(buildInterpretiveGraph(current,[],{threshold:0}).edges.length,0);
 const history=Array.from({length:20},(_,i)=>snap(i+1,1,2));
 assert.equal(buildInterpretiveGraph(current,history,{threshold:0}).edges.length,0);
});
test('pairs align by actual dates before differencing and exclude future',()=>{
 const history=Array.from({length:25},(_,i)=>snap(i+1,i*i+1,3*(i*i+1)));
 history[4].banks[0].srisk_usd_bn=null;history[8].banks[1].srisk_usd_bn=null;
 const result=buildInterpretiveGraph(history[24],[...history].reverse(),{threshold:.9});
 assert.equal(result.edges.length,1);assert.ok(Math.abs(result.edges[0].components.sriskCorr!-1)<1e-10);
 const withFuture=[...history,snap(26,100000,0)];
 assert.deepEqual(buildInterpretiveGraph(history[24],withFuture,{threshold:.9}).edges,result.edges);
});
test('insufficient common observations yield no edge',()=>{
 const history=Array.from({length:20},(_,i)=>snap(i+1,i<10?i*i:null,i>=10?i*i:null));
 assert.equal(buildInterpretiveGraph(snap(21,1,2),history,{threshold:0}).edges.length,0);
});
test('historical percentile changes with absolute cohort risk, not z-score mean',()=>{
 const history=Array.from({length:24},(_,i)=>snap(i+1,i+1,2*(i+1)));
 assert.equal(buildInterpretiveGraph(snap(25,100,200),history).summary.networkStressIndex,100);
 assert.equal(buildInterpretiveGraph(snap(25,.1,.2),history).summary.networkStressIndex,0);
 assert.equal(buildInterpretiveGraph(snap(25,1,2),history.slice(0,5)).summary.networkStressIndex,null);
});
test('aggregate trend uses fixed current cohort, omits missing dates and versions',()=>{
 const history=[snap(1,10,20),snap(2,11,null),{...snap(3,12,22),calibration_id:'old-calibration'}];
 assert.deepEqual(comparableTotals(history,snap(4,15,25)),[{date:'2024-01-01',value:30}]);
});
test('missing metric nodes do not inflate summary edges',()=>{
 const history=Array.from({length:25},(_,i)=>snap(i+1,i*i,2*i*i));
 const result=buildInterpretiveGraph(snap(26,null,100),history,{threshold:0});
 assert.equal(result.nodes.length,1);assert.equal(result.edges.length,0);assert.equal(result.summary.renderedEdges,0);
});

import { availableSnapshotDates } from '../lib/public-data';
import { assignGraphLayout } from '../lib/graph-layout';

test('date selector uses real eligibility, not 28 observed records', () => {
  const manifest = {dates:['2025-05-15','2025-05-16'],lastUpdated:'2025-05-16',snapshots:[
    {date:'2025-05-15',bank_count:29,coverage:{srisk_count:0,expected_count:29,eligible_complete:false}},
    {date:'2025-05-16',bank_count:27,coverage:{srisk_count:27,expected_count:29,eligible_complete:true}}
  ]};
  assert.deepEqual(availableSnapshotDates(manifest),manifest.dates);
  assert.deepEqual(availableSnapshotDates(manifest,false),['2025-05-16']);
});

test('Canada nodes have a finite region anchor', () => {
  const nodes = assignGraphLayout([{id:'RBC',label:'RBC',region:'CA',srisk:1,deltaCoVar:0,riskScore:0,size:1}], 'cluster');
  assert.equal(Number.isFinite(nodes[0].x),true);
  assert.equal(Number.isFinite(nodes[0].y),true);
});
