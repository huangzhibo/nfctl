# Changelog

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
