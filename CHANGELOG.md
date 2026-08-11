# Changelog

## [2.0.0](https://github.com/huangzhibo/nfctl/compare/v1.3.0...v2.0.0) (2026-08-11)


### ⚠ BREAKING CHANGES

* **pipeline:** --archive-dirs is removed from pipeline create/update; nfctl 2.x requires nf-server 4.x.

### 新功能

* **pipeline:** remove archive directory selection ([#9](https://github.com/huangzhibo/nfctl/issues/9)) ([4054a7b](https://github.com/huangzhibo/nfctl/commit/4054a7b4e87a5263729984d6faeb8cbc0b26906f))

## [1.3.0](https://github.com/huangzhibo/nfctl/compare/v1.2.0...v1.3.0) (2026-07-17)


### 新功能

* **cli:** --verbose 输出 HTTP 调试行,overview JSON 补 reconciler 信号 ([186d7d0](https://github.com/huangzhibo/nfctl/commit/186d7d0a2b830344bdef1c68e10229291ed5c75c))


### 修复

* **cli:** pipeline 超时参数帮助文本同步服务端新默认值(停滞 72h、执行上限 120h) ([e3d6e44](https://github.com/huangzhibo/nfctl/commit/e3d6e443e228988f248ecf6c2cd7f9c6a4174da9))
* **cli:** 错误路径统一 ok:false 信封与退出码,Agent 不再把失败读成成功 ([8d32451](https://github.com/huangzhibo/nfctl/commit/8d32451806b3fc8abcfc3b44f1ba4a978a59aa65))


### 文档

* **claude:** 模块表补齐 archive 命令组/progress/config 多 profile,与代码对齐 ([c7503a1](https://github.com/huangzhibo/nfctl/commit/c7503a1faa5baee4510a69e40170098ea2982a91))
* 清除 localhost 默认值等过期描述,补 profile 上手与 -v 说明 ([a0e5846](https://github.com/huangzhibo/nfctl/commit/a0e58465b10cc22a7b4b7b37be77957c1015a1c7))

## [1.2.0](https://github.com/huangzhibo/nfctl/compare/v1.1.0...v1.2.0) (2026-07-13)


### 新功能

* **cli:** pipeline 命令支持停滞/执行超时覆盖参数 ([0d93abd](https://github.com/huangzhibo/nfctl/commit/0d93abd0feb60a43e48dbe5ebcbc6ebdb8747be1))


### 修复

* **cli:** archive status 聚焦归档轴,去 restore 噪音,失败给日志指路 ([d9d038b](https://github.com/huangzhibo/nfctl/commit/d9d038ba2c032a0daeac2e37f89d3490b065a496))
* **cli:** status 的 error 行只在失败态显示,不再随 succeeded 露出 ([d6f7742](https://github.com/huangzhibo/nfctl/commit/d6f77425535d38de29446af799bd743ce8f18542))
* **cli:** 帮助文本统一"分析"口径, 不再称"工作流/主流程" ([10bf7af](https://github.com/huangzhibo/nfctl/commit/10bf7af6a9272ee30ebc4e06c4ba7ae492c75419))


### 文档

* 补齐 archive 命令组文档, 状态契约换 analysis_status 口径 ([2ce67e7](https://github.com/huangzhibo/nfctl/commit/2ce67e7398736d2b12bea900628564a20ae8ab57))

## [1.1.0](https://github.com/huangzhibo/nfctl/compare/v1.0.0...v1.1.0) (2026-07-05)


### 新功能

* **cli:** status 详情去冗余——cancelled 省略 error 行,删 needs_action 行 ([f386011](https://github.com/huangzhibo/nfctl/commit/f386011ebac157d14d227901375b1081530eca4b))

## [1.0.0](https://github.com/huangzhibo/nfctl/compare/v0.10.0...v1.0.0) (2026-07-04)


### ⚠ BREAKING CHANGES

* 仅兼容 nf-server >=3.0;CLI 契约就此稳定,发布 1.0.0。

### 新功能

* **archive:** archive 命令组补全(restore/status/cancel),cancel 硬切 --scope ([fd19914](https://github.com/huangzhibo/nfctl/commit/fd199149590ba1ceb9b4a44274efb5d864d83ae7))
* **cli:** archive now 命令,跳过归档等待期立即归档 ([547275b](https://github.com/huangzhibo/nfctl/commit/547275b6810aa4b956e31bacc5e6d31c9f889d14))
* **cli:** overview 显示 reconciler 存活(读 /health 心跳判定) ([80c9807](https://github.com/huangzhibo/nfctl/commit/80c9807d0daef8ac8ac60b7bfb76bc6e92d1d9ca))
* **cli:** 对齐 nf-server 状态契约,list 加 Archive 列与 --pp 过滤 ([e968fab](https://github.com/huangzhibo/nfctl/commit/e968fab5f9bb2c8d82061cffa0ef20e98134b0b5))
* **cli:** 版本握手——请求带 nfctl UA,426 升级指引,新版软提醒 ([2d7466b](https://github.com/huangzhibo/nfctl/commit/2d7466be389a04cddaf0fb7d91bdccd63a9e1b55))
* 对齐 nf-server 3.0 契约清仓——validate 直读 workflow_id,移除旧 server 容错 ([a11fc1a](https://github.com/huangzhibo/nfctl/commit/a11fc1a84ff6671ccd47fdbfee80d9c583d76925))

## [0.10.0](https://github.com/huangzhibo/nfctl/compare/v0.9.0...v0.10.0) (2026-07-03)


### 新功能

* **list:** -s 按展示状态 display_status 过滤,与 Status 列同口径 ([212fc54](https://github.com/huangzhibo/nfctl/commit/212fc540accb3dd45f99052eb970eda06e7380e0))

## [0.9.0](https://github.com/huangzhibo/nfctl/compare/v0.8.0...v0.9.0) (2026-06-23)


### 新功能

* **pipeline:** list 补归档列 + 新增 pipeline get 详情命令 ([0c572a1](https://github.com/huangzhibo/nfctl/commit/0c572a1cd4f0a0627852f6e4eb0638fe26f03883))


### 重构

* 展示与错误信封字段 sge_job_id 对齐 nf-server 真源字段 job_id ([0187765](https://github.com/huangzhibo/nfctl/commit/0187765015402f895f5d7717187cb03ede71947c))

## [0.8.0](https://github.com/huangzhibo/nfctl/compare/v0.7.0...v0.8.0) (2026-06-23)


### 新功能

* **pipeline:** create/update 对齐 pipeline API 全部可写字段 ([fb17564](https://github.com/huangzhibo/nfctl/commit/fb17564f37845ab4d3b66af3500ed8be342c7866))
* **query:** 展示对外统一状态并修复多行 value 对齐 ([f58dde3](https://github.com/huangzhibo/nfctl/commit/f58dde364ced3df503a766ae94f362e51893359b))
* 对齐 nf-server per-pipeline 并发挂起与 cancel scope ([9a2f576](https://github.com/huangzhibo/nfctl/commit/9a2f57635abb73a99f9e9878433cb38993782529))

## [0.7.0](https://github.com/huangzhibo/nfctl/compare/v0.6.0...v0.7.0) (2026-05-18)


### 新功能

* **query:** surface pp_status, data_number/data_path; add --data-number filter ([7161f7d](https://github.com/huangzhibo/nfctl/commit/7161f7d778f33ef77e2092da7cc448f890ccbf04))


### 修复

* **cancel:** clarify async signal semantics in success message ([0da6aae](https://github.com/huangzhibo/nfctl/commit/0da6aaebd8bd6bfdab37c6b42528b7e2ffab7e3a))


### 文档

* add manual submit scenarios to README ([878b296](https://github.com/huangzhibo/nfctl/commit/878b296d86d782c5e98d89092266725782f2a863))
* **readme:** document --data-number filter and extended -q search scope ([7b38b54](https://github.com/huangzhibo/nfctl/commit/7b38b54cbe727e469dcb510d7a708aa1cc550e7d))
* **skill:** align with agentskills spec and v1.1.0 status enums ([2dc06c3](https://github.com/huangzhibo/nfctl/commit/2dc06c3af8dd1e12f78dc9435dbc0f1a3dd58a15))
* **skill:** document --data-number filter and data_number concept ([119b5b9](https://github.com/huangzhibo/nfctl/commit/119b5b9caab5e5675b3f869978041642d35f82ad))
