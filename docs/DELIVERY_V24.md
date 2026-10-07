# v2.4 交付与运行说明

基线：`bf3d7dea569600974088e37593ff49090c54de40`。本包修改源码与默认演示数据；没有推送 GitHub，也没有调用线上部署。

## 上传方式

解压后，项目根目录直接包含 README.md、pyproject.toml、frontend、src、risk_mcp 和 .github。应将这些内容放到仓库根目录，不要多套一层目录，也不要只把 ZIP 文件上传后期待 GitHub 自动解压部署。

**已有仓库请按替换方式同步，必须删除本包移除的旧版 `data/history` 和旧 CSV。** 仅“上传并覆盖同名文件”会留下旧历史文件，前端会主动拒绝混合校准。先备份现有生产数据；历史演示与生产数据使用不同目录。Git 可以记录这些删除；新仓库可以直接导入整个解压目录。

`data/` 默认只含 2025-05-16 的 27 家历史重建数据。其来源、方法版本和校准标识与仓库已有 `examples/verified-disclosures-v23/reconstructed-snapshot.json` 一致。单日数据不会显示虚构走势，网络可能没有边，历史百分位可能 N/A，这是预期表现。

## Actions 修复

此前本地复现的问题是测试收集阶段无法导入 `src`。Daily workflow 原先只安装依赖文件；现改为 `python -m pip install '.[test]'`，安装项目包和测试依赖，再执行 `python -m pytest tests -q`。同时新增明确的生产输入预检及生产模式，防止“程序跑完却发布全空指标”。

定时任务只有仓库变量 `RISK_PRODUCTION_ENABLED=true` 时运行，手动运行不受该开关限制。默认样本不具备当前财报输入，手动生产运行会明确报出输入缺失。这与导入错误是不同问题：导入路径已修好，缺少真实输入需要补齐真实来源，不能靠放宽质量检查消除。

将有依据的基本面 JSON 放在 `inputs/fundamentals`，行情可以使用默认供应商或显式设置离线目录。若不希望把输入放入 Git，需在 workflow 中增加你自己的授权下载步骤，再设置 `FUNDAMENTALS_DIR` / `MARKET_INPUTS_DIR`；包内不会假定私有数据地址。

发布失败保存 `data/last-attempt.json`，workflow 上传诊断 artifact；保留旧 `current.json`。`runs/<id>` 为不可变批次，成功切换指针前检查 JSON/CSV 一致性。预检在计算前失败时可能尚无 last-attempt 文件，原因在步骤日志。Git 推送失败仍报告失败，不把本地生成当作远端发布成功。

## 当日无法计算时的处理

| 情况 | 输出 / 发布行为 |
|---|---|
| 官方交易日历显示主上市地休市 | `market_closed`；最近应完成交易日的有效结果可以满足新鲜度检查 |
| 当日尚未收市，或仍处于 120 分钟宽限内 | `not_yet_due`；检查上一应完成交易日 |
| 已应计算但无行情或无法计算 | `missing_data` 或 `fetch_or_calculation_failed`；不自动当成休市 |
| 日历库不支持该日期或交易所 | `unknown_calendar`，不计为新鲜合格 |
| 基本面/指标不可用 | 缺失保持 null；不改为零，不以别家银行替代 |
| 单银行在最新快照缺席 | 本地 MCP 查询可返回相同校准的较早有效记录，标明 `requested_date`、`as_of` 和 `previous_observation` |
| 排名、系统合计 | 只使用所选快照当日数据；不把旧值加入。当全样本缺失时，全系统合计为 null，另给已覆盖小计 |
| 所有市场休市 | 可以保留最近快照；日历检查各银行最近应完成交易日，不要求伪造当天记录 |

日历只识别主要权益上市地，不证明对应指数、FX 和供应商同时正常，也不是实时停牌服务。库版本写入报告。生产模式默认要求 27 家可计算银行中至少 80% 有足够新鲜的 SRISK；ACA、BPCE 的集团输入限制不从全样本 29 家分母隐去。质量 error、未来目标日、历史/合成数据冒充生产等会拒绝发布。研究模式保留诊断但不施加生产门槛。

MCP 仅配置远端 GitHub 源且没有本地历史时，单银行回退不会扫描整个远端历史，返回 unavailable。历史 CSV 的元信息按本地快照逐日提供；没有对应快照时明确标记元信息不可用，不套用当前配置。

## 分析接口与验证

MCP 新增：

- `get_sensitivity(bank_id, date?, market_drops?, capital_ratios?)`：固定市值与负债，默认 5 个市场跌幅 × 4 个资本率。优先使用记录中的 beta；否则仅在 0 < LRMES < 1 时按原场景反推，标注舍入限制。边界值不能识别 beta 时返回 unavailable。
- `get_change_explanation(bank_id, previous_date, current_date)`：同银行、同校准、同参数下对负债、市值、LRMES 做精确三因素 Shapley 分解，包括 SRISK 的零截断边界。贡献与变化额核对。数据只有一天时不会编造前一日。

离线 CLI：

```bash
# CSV 列：date,bank_return,index_return；配对日频收益，使用一致单位
python -m src.validation uncertainty --input paired-returns.csv --output uncertainty.json

# CSV 列：entity,forecast_date,known_at,outcome_date,score,outcome
# score 为 0..1 概率，outcome 为 0/1；这些标签由使用者真实提供
python -m src.validation evaluate --input predictions.csv --cutoff 2024-01-01 --output evaluation.json
```

不确定性使用配对循环移动块 bootstrap，默认 200 次、块长 5、95% 区间，输出 MES/LRMES，不声称覆盖财报、FX 或未来危机的不确定性。样本少于 60 行返回 unavailable，尾部样本少时提示。

时间验证按照 forecast_date 切分；训练基准只使用分割日以前已成熟的标签，排除重叠未成熟标签，拒绝 known_at 晚于预测日。输出测试 Brier 分数与训练基准概率的 Brier 分数。本工具不训练预测模型，不把 SRISK 直接当成概率，也无法自动证明用户声明的来源时点。

联动图边展示有效差分观测数、起止日、前后半窗口相关性（至少 20 对差分才显示）。只在相同校准、相同配对日期上计算；没有足够历史时没有边。这不是置信区间，也没有宣称控制共同因子后的因果传染。

## 部署参数

| 参数 | 用途 |
|---|---|
| `PUBLICATION_MODE` | research / historical / production；CLI `--mode` 同义 |
| `MIN_PUBLICATION_COVERAGE` | 生产新鲜度最低占可计算银行比例，默认 0.8 |
| `MARKET_CLOSE_GRACE_MINUTES` | 收市后宽限，默认 120 |
| `DATA_DIR` | Python 已发布数据根目录 |
| `DATA_SOURCE_DIR` | 前端构建输入根目录 |
| `MCP_ALLOWED_HOSTS` | 后端受信任 Host，逗号分隔；含部署后端主机名，可加 `host:*` |
| `MCP_ORIGIN_URL` | 前端/Worker 的 Python 后端 base URL，不带 `/mcp` |
| `NEXT_PUBLIC_SITE_URL` | 普通 Next.js 部署的自身 URL，状态接口读取本站 manifest |

Cloudflare：根目录 `frontend`，构建 `npm ci && npm run build:cloudflare`，部署 `npx wrangler deploy`。配置 Worker 变量 `MCP_ORIGIN_URL`；暂不接后端时 UI 正常，MCP 返回 503。Python 可用根目录 Dockerfile 部署到 Azure Container Apps 等平台，暴露端口 8000，并配置 MCP_ALLOWED_HOSTS。默认容器复制演示数据；生产应部署/挂载同一真实批次。前端为静态数据，数据更新后需重新构建部署。

普通 Next.js：`npm run build && npm start`。不要将 `.next` 填入 Cloudflare assets。静态导出脚本生成 `out/`，Worker 处理 `/mcp`、`/status.json` 和 `/data/`。SSE 响应流与 MCP 会话头保留。

## 验证结果与边界

本地 Linux、Python 3.12.14、Node 24.19.0（CI 配置为 Node 22）；依赖解析记录见 `requirements-tested.txt`，前端使用 package-lock.json。Python 的记录是本次测试环境的精确版本列表，可用 `pip install -c requirements-tested.txt '.[test]'` 重现；不同 Python/平台仍可能需要对应可用版本。

- Python 回归：149 项通过，包含休市、收市宽限、生产回滚、情景单调性、零边界归因、bootstrap 重现、标签时间防前视、MCP 元信息。
- 前端：19 项通过，包含 Worker SSE/会话传递、503/502、历史状态、日期不回退、相关性和覆盖一致性。
- MCP 实际函数检查通过，默认读取 27 家样本；离线 JSON/CSV 一致性通过。
- Python wheel 已构建；普通 Next.js 和 Cloudflare 静态构建及 wrangler dry-run 的最终结果记录在附带 `validation/` 日志。
- 本环境无法启动 Wrangler 本地模拟器（系统网络接口调用受限），且 Playwright 的 Chromium 下载失败。因此没有把真实浏览器视觉验收或 Cloudflare 线上运行列为已完成。
- 未请求用户的部署凭证，未发布线上站点，也未执行真实当前市场全量计算。历史样本、单元测试与 dry-run 不证明当前生产数据完整，亦不证明风险预测效果。

旧 docs/VALIDATION.md 等文件是对应历史版本的记录；当前版本范围以本文件及 validation 日志为准。
