# v2.4.1：Yahoo 日常研究路径与 CI 修复

对应 GitHub 提交 `d6ad91b952b434cc1eb7a84722db4f2716c9c498` 的两处失败。本版源码可在其上覆盖；没有直接推送远端，也没有宣称已完成真实当前市场的全样本验收。

## 先看实际验收状态

- Python：157 项回归通过，其中包含 Yahoo 响应适配、真实计算函数、JSON/CSV 发布、独立进程 MCP HTTP 工具调用的完整夹具测试。夹具测试使用合成收益和供应商响应样例，不是实时市场结果。
- 前端：19 项测试、类型检查、普通 Next.js 构建、Cloudflare 静态构建、Wrangler dry-run 通过；重新执行了干净 `npm ci`。原前端测试另外在 Node 22 上通过。
- 旧历史文件混合问题：保留 186 个历史文件可复现 `Mixed snapshot identity`；增加批次指针后，同样的覆盖上传目录可正常同步。
- **真实 Yahoo 验收失败**：本次环境对 JPM 的实际请求返回 HTTP 429 / `YFRateLimitError`，未取得行情，因此没有真实计算结果。保存了 `validation/v241/live-report.json` 与请求日志。程序按失败退出，未拿默认历史样本替代。
- 当前 GitHub 连接只有 pull 权限，无法替用户推送、触发修复后的工作流或证明线上已经成功。

因此，本包是已完成代码修复、可执行验收流程和本地回归的交付；实时供应商链路仍须在可访问 Yahoo 的运行环境中通过验收。不要将本页的测试数量解释为真实市场端到端已成功。

## 1. Daily Pipeline：恢复日常估计，保留严格历史模式

新的 Daily workflow 显式设置：

```text
FUNDAMENTALS_POLICY=yahoo_daily
PUBLICATION_BASIS=market_metrics
DATASET_KIND=research_estimate
```

`verified` 仍是程序级默认策略，供严格历史研究和既有接口兼容。Daily workflow 不再因为没有人工基本面 JSON 就在预检退出；在计算时读取 Yahoo。

日常 SRISK：

- 股价和指数：Yahoo 历史行情，剔除本地交易所尚未完成/仍在宽限内的交易日。
- 市值：最近已完成交易日的非分红复权 Close × 当前 vendor shares，按明确报价币换算 USD；不使用存在便士/英镑歧义的 marketCap 字段。
- 负债：Yahoo 季度资产负债表 `TotalLiabilitiesNetMinorityInterest`，不把 Total Debt 替代总负债。
- 负债报告期不得晚于估计日期、不得超过 200 天；报表币必须与登记口径匹配。币种、FX、股数或金额缺失时保持 null。
- 所有 vendor 基本面都记录获取时间、报告期、来源和原始输入 SHA256；`disclosure_date=null`、`point_in_time_verified=false`。报告期不会冒充披露日。
- 当前获取版本仅服务当天任务中最近已完成的市场交易日，不回填整段历史收益窗口。历史重算选择 `verified`；`yahoo_daily` 配合历史模式或旧目标日会被拒绝。
- 中国 A/H 多股类银行仍不能直接用一个 H 股代码代表集团市值；ACA/BPCE 的集团适用性限制保留。不会为了提高覆盖率猜集团规模。
- 数据采集结果保存在 `inputs/vendor-cache`，同日、同已完成交易日、6 小时内的成功观测可复用；错误观测只留证据，不抑制重试。Actions 用 cache 保存观测，并在 artifact 中保留诊断。

可用的核验输入仍优先。负债或市值失败不会阻止 MES/LRMES/CoVaR/ΔCoVaR 计算。SRISK 缺失时仍显示 null，不参与 SRISK 排名和合计。每日只更新每家银行最新的可计算日期，已发布的历史 SRISK 不会被当前基本面回填或批量抹掉。

发布按指标分别报告覆盖与新鲜度：`coverage.metric_coverage`、`publication.metric_status`、`publication.fresh_count_by_metric`。Daily 的硬门槛是 27 家可计算银行中至少 80% 的四个行情风险指标都足够新鲜；SRISK 单独披露可用性。没有行情、整体过期、未来日期或其他严重质量错误仍拒绝发布并保留上一批数据。严格 SRISK 发布仍可使用 `PUBLICATION_BASIS=srisk`。

## 2. 前端 CI：覆盖上传也不混入旧数据

GitHub 上 `data/history` 实际还保留了 185 个旧版文件，加上新演示共 186 个。上一包要求删除旧文件，对覆盖式上传不够稳健。

本包新增：

```text
data/current.json -> runs/demo-v23/
data/runs/demo-v23/latest.json
data/runs/demo-v23/history/2025-05-16.json
data/runs/demo-v23/banks/*.csv
```

前端与 MCP 只解析指针中的批次，根目录残留旧历史不再参与新版构建。首次真实研究发布会新建自己的批次，绝不复制演示记录进新校准。成功后原子切换 current.json；失败仍保留演示批次。其他已有生产校准不允许自动混接。

Core CI 将原先串在一行的 npm 操作拆成安装、测试、类型检查、Next 构建、Cloudflare 构建、dry-run 六步，下次失败可以直接定位。Node 统一为本次本地验证使用的 24 系列。

## 上传与验收

1. 在当前失败的 v2.4 仓库上解压覆盖。保留 `.github` 文件夹，确保 `data/current.json` 和 `data/runs/demo-v23` 一起上传。旧 history 文件可以保留，指针会隔离它们。
2. 等待 `Core regression checks` 通过。
3. 手动运行新增的 **Live Yahoo end-to-end acceptance** 工作流。它会真实获取 JPM、BAC 数据，计算全部指标（包括 SRISK），校验 JSON/CSV、调用真实 MCP HTTP 接口，再用同一批真实数据构建 Cloudflare 前端。任何银行缺 SRISK、数据过期、接口或前端失败均会让任务失败。artifact 名为 `live-yahoo-acceptance`。
4. 第 3 步通过只证明两家银行的完整链路，不代表 27 家全部有 SRISK；再运行 Daily Pipeline 验证全体的实际覆盖。
5. 确认每日质量报告后再设置 `RISK_PRODUCTION_ENABLED=true` 启用计划任务。发布数据后，静态前端需要重新部署才能更新。

CLI 同样可执行：

```bash
python -m pip install '.[test]'
python -m src.acceptance --banks JPM,BAC --output acceptance-data --report acceptance-report.json
cd frontend
DATA_SOURCE_DIR=../acceptance-data npm ci
DATA_SOURCE_DIR=../acceptance-data npm run build:cloudflare
npx wrangler deploy --dry-run
```

验收输出目录必须新建且为空。上游 429 不可通过关闭覆盖门槛解决；在可访问 Yahoo 的 runner 稍后重试，或更换有授权的行情数据源。不会在同一任务中高频重试规避限流。

本地完整 Daily：

```bash
FUNDAMENTALS_POLICY=yahoo_daily PUBLICATION_BASIS=market_metrics \
  python -m src.pipeline --mode production
```

**注意：本包携带的是演示指针，只应覆盖当前尚未建立新版生产批次的 v2.4 仓库。已有真实生产 `data/current.json` 时请保留生产指针，不要用演示指针替换。** 当前已核对的失败提交属于前一种情况。
