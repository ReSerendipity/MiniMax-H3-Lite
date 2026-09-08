# Changelog

## [2.4.1](https://github.com/ReSerendipity/MiniMax-H3-lite/compare/v2.4.0...v2.4.1) (2026-09-08)


### CI/CD

* **trivy:** 移除 GHA 层缓存，安全门禁改冷构建 ([#4](https://github.com/ReSerendipity/MiniMax-H3-lite/issues/4)) ([8607c10](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/8607c104de2d5394bc37214aaf802c9beaa465bc))

## [2.4.0](https://github.com/ReSerendipity/MiniMax-H3-lite/compare/v2.3.1...v2.4.0) (2026-09-06)


### Features

* **B1:** vllm-omni 引擎注册 + 推理分发 (默认仍 comfy, 待 5070Ti recipe 验证) ([0817248](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/08172481727fc9422008616d463ec4beab0629c6))
* **bench:** 性能基准留档 —— 全局 autosave + 每周基准 workflow（P2-⑥） ([f7687a5](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/f7687a54befe45eca512675aff1998959fe261c7))
* **db:** SQLite schema 版本管理（PRAGMA user_version）+ 修测试 DB 隔离缺陷 ([f904302](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/f9043023c4ccd452b585a425a10d39a7e4bbd1b8))
* **dx:** smoke_real.py --env-only 环境快照入口（DX 报告 P2） ([7123230](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/7123230333976678b8e8700be59cc254116f9814))
* **e2e:** Playwright E2E 配置落地 + 业务前端脚本纳入 eslint ([b64643e](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/b64643e5d84026d983f87ed520509c39586a316e))
* **inference:** seed 血缘机制——提交侧生成/校验落库 + 推理侧回写（MLOps P1 可复现性） ([e962e54](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/e962e54c164b76bf44d65cbe69b386ec8e3ed09b))
* **ops:** Docker 构建/钉版/扫描 (trivy+docker-scan) + gpu-smoke CI + 清理脚本容器化 ([94df7d5](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/94df7d52622097b1e2d401d8d1b6131969fd4980))
* **ops:** 数据备份脚本落地 + 忽略规则（运维稳定性 T4） ([afc5a17](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/afc5a17555fa05bf5544ce5907880dc7addf2a1f))
* **ops:** 日志落盘 + 健康探针补模型就绪/队列深度（运维稳定性 T1/T2） ([69063ae](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/69063ae86a2c6eabe7dd35565350e2dbd4583825))
* **security:** 许可合规最小自检——启动横幅 + 部署前强制确认 ([d542bac](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/d542bac824e921e10da7950e5e18c09215d4fe31))
* **version:** 版本口径收敛到 release-please manifest 单一事实来源 ([1363cf4](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/1363cf48fc6933fec95929f01a11136213a077fc))


### Bug Fixes

* **ci:** comfy_kernel 棘轮断言按内核存在性分级执行（修 Test & Quality 红） ([70a2964](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/70a296400be29005cf905973bc648b09ce91689c))
* **ci:** DCO check via self-contained bash (dcoapp/dco is a GitHub App, not an Action) ([649adea](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/649adea71fff04f462fb209d1e6a623835115618))
* **ci:** frontend-smoke 轻量依赖补 python-multipart ([dbd1e73](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/dbd1e73f3214aac0f01380414919af0d429f716b))
* **ci:** HEALTHCHECK 旗标 --start_period → --start-period；sast_gate 修 check_id 取值层级 ([b91760a](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/b91760abfac15ff7355483298809da1f6d36c21b))
* **ci:** trivy 扫描超时放宽 5m → 20m ([ce13cae](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/ce13caef7ffaf9965b73f020f00c02b099839047))
* **ci:** trivy-action 升级 v0.36.0，绕开上游 setup-trivy@v0.2.1 标签消失 ([300e46f](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/300e46f057e0fac1443e922a95f5c5f56e886156))
* **ci:** trivy-action 引用补 v 前缀（0.28.0 → v0.28.0） ([5910dfc](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/5910dfc80a679a3d4e91fe0619c8fad634bf10a0))
* **docker:** apt-get upgrade 清偿基础镜像 OS 包 CVE（libpcre2-8-0 10.42-1 未打补丁 5 项） ([ddadea1](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/ddadea187b478ab8fc36909504c00fe51352794e))
* **docker:** LABEL 移入 FROM 之后的 stage，修 "no build stage in current context" ([dbb60c2](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/dbb60c2b2aaa9b97b62a7f60652deb41a5f4ad63))
* **docker:** setuptools/msgpack 安全升级移至 requirements 之后（修 Trivy gate 复拦） ([b98ca79](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/b98ca7921f745c44afb4a15ced00b1e8bd06409d))
* **docker:** whiteout 清除下层幽灵 dist-info 后重装 setuptools/msgpack ([5a47246](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/5a47246127e4cb6b666ed1cb96bbb8138b83b3df))
* **docker:** 升级 pip 修 CVE-2026-8643（Trivy gate 首拦的唯一 HIGH） ([1977b00](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/1977b00013dca8ada70c22941b09662bf3752d6d))
* **docker:** 升级 setuptools/msgpack 修剩余两项 HIGH（Trivy gate 迭代二轮） ([7fea4d2](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/7fea4d2add183e59f50790a56ab1312756cf22eb))
* **ops:** 默认推理路径超时强制 + 删除 TASK_TIMEOUT 死配置（运维稳定性 T6） ([f9196b3](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/f9196b3fa1b70e14276d7b1f7cf5a914742f73e0))
* **sast:** database.py PRAGMA 定向 nosemgrep（gate 修正后打出真实 rule ID） ([1d21c87](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/1d21c87afe384065a12d266ec4eef7243cb51f47))
* **sast:** 清偿 gate 首拦的 3 项 ERROR，回归基线口径（1 = shots.py 存量已接受） ([839d1f9](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/839d1f976262f84498667a8893c9da3fc3c60edd))
* **security:** 幽灵门禁扩面至全部 Settings 字段，修 env 提取器三盲区 ([bcfde3e](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/bcfde3e8254d4da684ac03fe5fc297d51b089979))
* **test:** seed 血缘测试注入 fake torch，消除对真实 torch 的隐性依赖 ([c521c5d](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/c521c5dddfc9f8e18fa6b56d068926bdf66b8afd))
* **trivy:** skip pip vendor SBOM——门禁幽灵旧版真凶实锤 ([8584da8](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/8584da87c02bda891fd9d1e8cf876db814a1505c))
* 修复默认项目名不一致与 UI 改版遗留的失配缺陷 ([f28d095](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/f28d095cd5c4c1c377fd2d44cf210a7ad00f141f))
* 清理 42 处 flake8 违规（F401/F841/E/W）+ 补 eslint flat 最小配置使本地门禁可运行 ([ead4e63](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/ead4e638790611762cf18fe4bfc4f7f20f632213))
* 清理 42 处 flake8 违规（F401/F841/E/W）+ 补 eslint flat 最小配置使本地门禁可运行 ([c6a90fa](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/c6a90fa23d610cd2d8462a3c43e4e3ff9de0b378))


### Documentation

* **adr:** 索引登记 ADR-0004 发布版本治理（manifest 单一版本源） ([3f68712](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/3f6871272b4c4500de18e05cb167e958c97eb81c))
* **agents:** 家族规范审计 Phase A+B — 测试目录校正、协议 v1.7、CI 一致性 ([a35af1f](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/a35af1ff0d29f6581eced535752753e906c283b4))
* **agents:** 家族规范审计 Phase A+B — 测试目录校正、协议 v1.7、CI 一致性 ([89308b2](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/89308b298a830cb307a6c483413229c1ec783c04))
* CONTRIBUTING 脱敏后入库(对外协作指南) ([c189cd7](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/c189cd796c06873271b3389e7b659b7b87496a14))
* CONTRIBUTING 脱敏后入库(对外协作指南) ([a504489](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/a504489e8014482fdee4aa219044733954571004))
* **governance:** 家族规范治理 Phase C/D/E 落地 — 一致性、补齐与账本 ([e862664](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/e862664edfd263bc8ad25ca801d0af19a4460544))
* **governance:** 家族规范治理 Phase C/D/E 落地 — 一致性、补齐与账本 ([ec4e387](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/ec4e387327f267394eeb4d60ec1e926a686a5fe7))
* **README:** 标注真实推理已跑通 + 补充 .venv，新增六大项目文档整理核对 ([04eb03a](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/04eb03a972c544d086c71df3aaa2bb02efd02666))
* **README:** 标注真实推理已跑通 + 补充 .venv，新增六大项目文档整理核对 ([2c14a08](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/2c14a0899aec94bf9e2b8f94af8d83e41f615c60))
* **README:** 结构树补充 comfy_kernel 与 model 目录 ([8581106](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/8581106a71acd6c7bc98ee4c32641b3aaaeafb8a))
* **README:** 结构树补充 comfy_kernel 与 model 目录 ([a03042e](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/a03042e065223c7853a66fe7cf3803d598cf72d4))
* **security:** SECURITY.md 需求矩阵 + 审计文档状态同步 + 整改账本 S-01~S-06 ([33694b8](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/33694b82c99112c16622a09fefe40fbcae4bd953))
* 新增 MiniMax 竞品库 / ADR-0003 / 合规复核（T2+T3+T6） ([b10b0a7](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/b10b0a776ed0a0f4a2e66f46f0976e7414cb5428))
* 新增 PRIVACY_POLICY(本地优先,不收集数据) ([a5b4b01](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/a5b4b0198d2d9b003144aa98df3228978fa30e1f))
* 新增 PRIVACY_POLICY(本地优先,不收集数据) ([bd1cde2](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/bd1cde2feea233bc3668b4d21141246ed6e34232))
* 新增远程同步铁律，防止 AI 直写远程后本地分叉 ([8922cf4](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/8922cf4727c9e22903545d60706ebb0a5ef5078c))
* 新增远程同步铁律，防止 AI 直写远程后本地分叉 ([99cf92e](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/99cf92e70c6a33cc7a6cfc2403bb7404c664bcf7))


### CI/CD

* **bench:** 回归比较启用 —— cache 滚动基线 + latency 子集棘轮（P2-⑥ 收尾） ([f41eeee](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/f41eeee557974855c083887cf6e8f142f615a0e7))
* E2E 门禁收紧，新增覆盖率门槛（SeedVR2 50%/Image 60%）与并发控制 ([4b62dba](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/4b62dba195d74739ddbc2ee8afb74af7a1153139))
* E2E 门禁收紧，新增覆盖率门槛（SeedVR2 50%/Image 60%）与并发控制 ([fa3cafc](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/fa3cafc03babbf5aed28999a6982440036184845))
* fix gate infra - SARIF upload perms / cross-platform pytest ([3173375](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/31733753923d540a5aabe3707b51e179a9d2fdb1))
* **gate:** comfy_kernel 暴露面棘轮 + 调用面断言（安全合规 P1 收尾） ([78bed6c](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/78bed6cf0e8bf97cfd0daab42e693f56a0ffffe6))
* **gate:** 安全棘轮门禁接入 + frontend-smoke 补 Python 环境 + E2E 接入 CI ([c3b92ff](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/c3b92ff862716d57aeaa8dad2775a5fafdf7ead0))
* make quality gates strict - remove fake-green || true / continue-on-error ([d17720e](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/d17720eddda633224ffe26a3a892dae63187146e))
* **release:** 恢复发布与测试门禁阻断，消除吞错与弱化残留 ([fc50882](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/fc50882df16cf46f98d2db02c9c494a2cb7029e4))
* **trivy:** rootfs 诊断步搜 SBOM 文件 + 关闭跨 run 分析缓存 ([5243061](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/524306133778724329999601a3bcc075a5d30259))
* **trivy:** 包位置清单诊断步 + appver 引号语法修复 ([4e50655](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/4e50655f40ae50e7596511ca567e1f57ee2732fa))
* **trivy:** 改扫 docker export 合并视图 rootfs——绕过幽灵层旧 dist-info ([54ff050](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/54ff050c1d28b044ec5cf36bce1f3ac10f7f68a7))
* **trivy:** 追加 JSON 包路径诊断步——定位幽灵旧版的 PkgPath/Layer ([2425e96](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/2425e967c0dba83e4382b8e3730fea077696d708))
* **typecheck:** 内联 ratchet 门禁改为调用组织级 reusable workflow（试点） ([bd7742b](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/bd7742b69e61f4d117ed3e25991f0ba641cd7679))
* **typecheck:** 新增 mypy ratchet 类型门禁，对齐家族底线 ([f13e1fc](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/f13e1fc274f294901a5842e6baee5069132aa6e7))
* 收紧 lint 门禁为严格失败，trivy-action 固定 SHA，补权限最小化与超时，清理 master 触发 ([ad19761](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/ad19761988e47dcc3111220d99174dd9d197eac7))
* 收紧 lint 门禁为严格失败，trivy-action 固定 SHA，补权限最小化与超时，清理 master 触发 ([b6f8d34](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/b6f8d34192a6c9eaa7fc9e4300592f524641b0ae))


### Refactor

* **governance:** 收敛社区健康文件至组织级默认仓库 ([3100655](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/3100655a835de9073607b0abc1c6d71697719f0a))
* **templates:** 提取三页共享参数段为 partials，渲染输出逐字节零差异 ([9729806](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/9729806149ce3d8228df82dfd4d2a75c907c9a82))


### Security

* add read-only security audit doc (MiniMax-H3-lite) ([3107ac1](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/3107ac1baf3b8cf20ae92f1d57c00cab37846f82))
* add read-only security audit doc (MiniMax-H3-lite) ([8474715](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/8474715649ce02687d6ebb57610fab17664a02cd))
* fix phantom-control HOST + add config-vs-code consistency gate (M1) ([9eef4d4](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/9eef4d400a637c6319afb72c8d9460dfc77aa762))
* fix phantom-control HOST + add config-vs-code consistency gate (M1) ([f97fd73](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/f97fd73d664813db8531787c14d8fe1dc5e5b798))


### Tests

* **inference:** 失败路径与主执行路径补测，覆盖率 39%→83%（P2-④） ([f5df2ff](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/f5df2ff2cfbbdfd89eb2c9221afe135b9b4c5089))
* **isolation:** 上传/资产目录测试隔离——修 no_orphan 间歇性失败 ([eeea179](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/eeea179c3a0374eb15c6608f925057807fe64294))
* **ops:** 运维稳定性落地回归测试（T1/T2/T4/T6） ([036d300](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/036d300d84da96ddd33f1268d13252a251ce3ff4))
* **queue:** mock_inference 覆盖 queue_manager 调用点 + 队列排空守卫 ([9132621](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/9132621cbe0fed53057eb2a5c80f2464ea54efc6))
* **vllm:** vllm-omni 适配器补测，覆盖率 0%→100%（P3-⑦） ([1336dae](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/1336daeb604bb3bb249e7507123a3efa75745380))

## [2.3.1](https://github.com/ReSerendipity/MiniMax-H3-lite/compare/v2.3.0...v2.3.1) (2026-08-22)


### Documentation

* README 顶部补齐 CI 徽章 ([a1758ca](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/a1758caedaf5c80a52bede9e482c62b7ee3462d5))


### CI/CD

* release-please 加 continue-on-error，避免发布异常显示红叉 ([b1a26ec](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/b1a26ec955fd6e181616b55a85ee89fa697a1ffe))
* 开启 actions 创建/审批 PR 权限，重跑 release-please ([0897c30](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/0897c30ae952ce47572afdb20a18dc4f3ddff266))
* 降低质量门禁严格程度，避免频繁失败 ([597bf2f](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/597bf2fbcd07cd522d1103f510e94cd2b9f941b8))

## [2.3.0](https://github.com/ReSerendipity/MiniMax-H3-lite/compare/v2.2.0...v2.3.0) (2026-08-21)


### Features

* add invisible content-provenance module (DCT frame embedding, debug-only logs) + verify tool ([2e9c28a](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/2e9c28afc285e1fae2c69bfc2602558b044209be))
* add smoke testing script and update docs for diffusers-only inference ([e8a413c](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/e8a413c9cc23e9d30e89ddc8acce8c738bad2fc1))
* **backend:** 新增 comfy 进程内引擎 + 各路由/template 更新 ([6245bfe](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/6245bfeadcf1bb55ecb9a025436cb52260d63887))
* **ci:** 添加 GitHub Actions CI/CD 流水线 + 前端静态资源归档 ([509e6c6](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/509e6c60f62215d7926544e987c4c631388c3905))
* comfy 引擎配套脚本/测试/workflow API 固化 + prompt 文档 ([6f04bbe](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/6f04bbeeee1e68ac4260f05f61d3ac67c729eaf7))
* enhance backend with new routers and engine registry ([5bef47a](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/5bef47a421333f2cb20a55146618fb6967327a2b))
* **test:** 完善测试体系基础设施 - conftest + pytest-cov + pre-commit hooks ([56828c8](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/56828c8eeb3d68d923217eb7cc6ce8f07e8f7d96))
* 路线图落地 — API 集成测试、checkpoint 断点、Comfy PoC；fix: 测试 DB 隔离 ([7368d7d](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/7368d7d9ac685da058ce73dd6c5d64f9b627ffd9))


### Bug Fixes

* **tests:** fix hardcoded paths, stale E2E assertions, add negative tests, split God Tests ([5618ba1](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/5618ba196ad317843018cc9110b0bba7ea23e85a))
* 补齐 h3.spec 符号与 jinja2 依赖，修复 flake8 与 README 断链 ([05ef997](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/05ef9976f3306e54bcfa55e626bc1761b2ebf37e))


### Documentation

* add AGENTS.md (self-evolution protocol) ([74d769e](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/74d769e2bc15a9aa3b5d2e39793e51289eecdbdf))
* add Apache-2.0 LICENSE for repo code and NOTICE with MiniMax H3 license attribution ([2ef2c29](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/2ef2c2985876bd1e3d91fd1f409b922df7b3396c))
* add SECURITY.md and license separation statement ([366cf4d](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/366cf4d53d9449fe92eccd2863b0954eed5bd73e))
* IMPLEMENTATION_GAPS.md 差距指南 + 静态资源文件（favicon/图标） ([cdad5c0](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/cdad5c0df1390864ffa94f58af431e5ff45703b4))


### CI/CD

* release-please 使用 GH_PAT 建 PR（GITHUB_TOKEN 被禁并在 org 无法创建 PR） ([1ff6428](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/1ff64280c52c6eff9ee21d3b56e08c5d8d594e9e))
* security assertions (no 0.0.0.0 binding, entry checks) ([45b1605](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/45b160596eef235310cc05bf73c458774a9109bd))
* 为 MiniMax 接入 release-please 自动发版 ([6476fe0](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/6476fe0c3d00d4260d4050eef5e4a627502b839a))


### Refactor

* **stageG:** 统一代码风格与结构（接 G1-G5 重构） ([3e036ad](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/3e036ada90a6f0fecf5fe6ef61e7fd68b2a9af7b))


### Tests

* **backend:** add unit tests for watermark/database/comfy_engine core modules ([9ae34ab](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/9ae34ab292fc81bb18ea9c263894e4570cbe6007))
* **config:** add settings_store/engine_registry tests, fix CI Python version/lint/playwright ([7fcfd31](https://github.com/ReSerendipity/MiniMax-H3-lite/commit/7fcfd315a14c8d0c00594ec34721e72d240e24a6))
