# 国家电网数据获取工具

[![Docker Build](https://github.com/Poiig/sgcc_electricity/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/Poiig/sgcc_electricity/actions/workflows/docker-publish.yml)

自动登录国家电网（95598），抓取电费余额、日/月/年度用电量、分时电量、阶梯用电等数据，存入数据库并支持通过 Web 控制台查看。可选推送到 Home Assistant。

---

## 关于本仓库（blue-eric 改进版）

> 本仓库 fork 自 [Poiig/sgcc_electricity](https://github.com/Poiig/sgcc_electricity)，遵循 Apache License 2.0。
> 在原版基础上修复了一些实际运行中遇到的问题，并增加了几项可配置功能。**代码在 `my-custom` 分支**，提供独立镜像；
> 通用的 bug 修复会以 PR 形式提交给原作者。下方「致谢」之后的内容为原作者文档。

### 与原版的区别

**问题修复**
- 验证码确认后页面元素失效（stale），实际已登录成功却被误判为登录失败
- 切换户号时下拉框偶尔为空导致该户号被跳过：自动刷新页面重试，失败时保存截图
- 配置 `USER_NAMES` 后切换户号可能匹配不到选项
- 月度/年度的总用电量、总电费被页面未加载完成时抓到的 0 覆盖
- 年度/月度页面加载慢时获取数据失败
- 登录失败、取不到户号时被记为「同步成功」且不会重试
- 户号多、同步超过 1 小时时，同步锁被误判为超时而重置
- 容器与数据库时区不一致时，Web 控制台的同步冷却时间被算成数小时

**新增配置项**（均在 `example.env` 中有说明，不配置时保持原版行为）

| 配置项 | 作用 |
|---|---|
| `USER_NAMES` | 户号显示名映射，例如 `户号1:我家住宅,户号2:充电桩` |
| `WEWORK_MSG_FORMAT` | 企业微信消息格式：`text` / `markdown`（默认）/ `markdown_v2` |
| `WEWORK_PUSH_SUMMARY` | 同步成功后是否推送数据汇总；同步失败通知、登录二维码不受影响 |
| `JOB_TIMES_PER_DAY` | 每天定时同步次数：`1` 或 `2`（默认） |
| `HA_REPUBLISH_INTERVAL_MINUTES` | 向 Home Assistant 重发数据的间隔（分钟） |
| `LLM_TIMEOUT` / `LLM_MAX_RETRIES` / `LLM_MAX_TOKENS` | 大模型识别验证码的超时、重试次数、最大输出长度；兼容只接受 `max_completion_tokens` 的模型 |
| `JOB_START_TIME=off` | 关闭内部定时同步，启动时也不登录国网，改由外部程序调用接口按需触发（见下方「外部触发同步」）；Web 控制台仍可手动同步 |
| `FETCH_RUN_RETRY_WAIT_MINUTES` | 外部触发要求整轮重试时，两轮之间等待的分钟数（默认 10） |

更换大模型厂商的方法见 [docs/LLM_CAPTCHA.md](docs/LLM_CAPTCHA.md)。

### 外部触发同步

适合由其他程序（如 [blue-eric/energy](https://github.com/blue-eric/energy) 能源日报）统一安排同步时间的场景：
设置 `JOB_START_TIME=off` 并开启 Web 控制台（`WEB_DASHBOARD=true`）后，本程序不再自己定时登录国网，由外部程序通过 HTTP 接口触发。

| 接口 | 说明 |
|---|---|
| `POST /api/fetch?source=energy&attempts=2` | 在后台启动一次同步并立即返回。`source`：调用方名称（字母、数字、`_`、`-`，默认 `manual`），记录在同步状态里；`attempts`：整轮重试次数（1~5，默认 1），登录失败、取不到户号或所有户号都失败时，等待 `FETCH_RUN_RETRY_WAIT_MINUTES` 分钟后整轮重来。已有同步在运行时返回 409，冷却时间内返回 429 |
| `GET /api/status` | 查询同步状态。`fetch` 字段中：`status` 回到 `idle` 且 `started_at` 不早于触发时间即为本次结束；`result` 为 `success`（全部成功）/ `partial`（部分户号失败）/ `failed`（失败），`detail` 为明细；同步进行中时 `heartbeat_at` 为最近一次心跳时间，调用方据此判断同步是否仍在进行 |

说明：
- 冷却时间（`FETCH_COOLDOWN_MINUTES`，默认 30 分钟）对所有来源都生效，防止频繁登录被风控
- 设置了 Web 控制台密码时，需先 `POST /api/login` 获取 token，之后的请求带上请求头 `X-Dashboard-Session: <token>`
- 部分户号失败记为 `partial`，不会整轮重试，避免重复登录
- 内部定时同步（`JOB_START_TIME` 为具体时间时）保持原有重试逻辑，不受 `attempts` 影响
- 同步锁带心跳：户号多、同步时间长也不会被误判为超时；进程异常退出 10 分钟后自动释放

### 部署（Docker）

本仓库提供两种部署方式，**推荐方式一**。

#### 方式一：使用本仓库镜像（推荐）

镜像由 GitHub Actions 根据 `my-custom` 分支自动构建，x86 / ARM 通用：

| 标签 | 说明 |
|---|---|
| `ghcr.io/blue-eric/sgcc_electricity:latest` | 最新版 |
| `ghcr.io/blue-eric/sgcc_electricity:2.1.1-be.1` 等 | 正式版本（见 [Releases](https://github.com/blue-eric/sgcc_electricity/releases)） |
| `ghcr.io/blue-eric/sgcc_electricity:20261024-1530` 等 | 每次构建的日期版本，出问题时可回退 |

只需要 `docker-compose.fork.yml` 和 `.env` 两个文件：

```bash
mkdir sgcc_electricity && cd sgcc_electricity
curl -o docker-compose.yml https://raw.githubusercontent.com/blue-eric/sgcc_electricity/my-custom/docker-compose.fork.yml
curl -o .env https://raw.githubusercontent.com/blue-eric/sgcc_electricity/my-custom/example.env
# 按注释编辑 .env 后启动
docker compose up -d
```

**群晖 Container Manager**：新建文件夹放入上面两个文件，在「项目 → 新增」中选择该文件夹即可。

更新：`docker compose pull && docker compose up -d`

#### 方式二：原作者镜像 + 挂载本仓库代码

不想用本仓库镜像时，可以继续使用原作者镜像，把本仓库的 `scripts` 目录挂载进容器覆盖自带代码：

```bash
git clone -b my-custom https://github.com/blue-eric/sgcc_electricity.git
cd sgcc_electricity
cp example.env .env
```

编辑 `docker-compose.fork.yml`：把 `image` 换成原作者镜像 `ghcr.io/poiig/sgcc_electricity:latest`，
并取消 `./scripts:/app/scripts` 这一行的注释，然后 `docker compose -f docker-compose.fork.yml up -d`。
更新时 `git pull` 后重启容器即可。

> 已经在用原版的，只需在原来的 `docker-compose.yml` 的 `volumes` 中增加一行
> `- /本仓库路径/scripts:/app/scripts`，再把 `.env` 按 `example.env` 补充新配置项即可，数据库不用动。
> 注意：原作者镜像更新后可能与本仓库代码不匹配，方式一没有这个问题。

#### 持久化

| 本地 | 容器内 | 内容 |
|---|---|---|
| `./data` | `/data` | 数据库（SQLite 时）、错误截图、日志等 |
| `./.env` | `/data/.env` | 配置文件 |
| `./scripts` | `/app/scripts` | 仅方式二需要 |

修改 `.env` 后要**重建容器**才会生效：`docker compose up -d --force-recreate`

### 已提交给原作者的修复

以下修复已（或将）以独立 PR 提交给原作者，合并后会在此标注：

| 修复 | 分支 | 状态 |
|---|---|---|
| 验证码确认后元素失效被误判为登录失败 | `fix/captcha-stale-element` | 待合并 |
| 切换户号时下拉框为空，刷新页面后重试 | `fix/switch-user-empty-dropdown` | 待合并 |
| 月度/年度总用量与总金额防止被 0 值覆盖 | `fix/db-zero-overwrite` | 待合并 |
| 年度/月度用电等待改用 `visibility_of_element_located` | `fix/yearly-monthly-wait` | 待合并 |

### 问题反馈

本仓库为个人业余维护，尽力而为。请在 [Issues](https://github.com/blue-eric/sgcc_electricity/issues) 按模板反馈，并隐藏账号、户号等敏感信息；
原版本身的问题请到 [Poiig/sgcc_electricity](https://github.com/Poiig/sgcc_electricity/issues) 反馈。

### 使用提示

- `DAILY_FETCH_DAYS` 请保持 `30`：国网页面「近 7 天」只有每日总用电量，没有峰谷平尖分时
- Web 控制台修改 `.env` 后，Docker 中需要重建容器才会生效
- 版本号规则：`2.1.1-be.N` 表示基于原作者 2.1.1 的第 N 个改进版

---

## 致谢

- [ARC-MX/sgcc_electricity_new](https://github.com/ARC-MX/sgcc_electricity_new) — 项目基础框架和数据抓取逻辑
- [renxiaoyaoo/ha-95598](https://github.com/renxiaoyaoo/ha-95598) — 点选验证码识别方案参考

本项目遵循 Apache License 2.0 协议。[更新日志](docs/CHANGELOG.md)

---

## 功能亮点

- 自动登录国家电网（支持点选/滑块验证码自动识别、二维码扫码登录）
- **Web 控制台**：浏览器查看多户用电概览、阶梯用电、日/月图表、运行日志，手动触发同步
- **Home Assistant 推送**：支持 REST API 和 MQTT Discovery 两种方式（可关闭）
- 支持每日/月度/年度分时电量（谷/平/峰/尖）采集
- 支持住宅用户阶梯用电数据（一/二/三阶已用、剩余、当前阶段）
- 数据库支持 SQLite / MySQL / PostgreSQL
- 电费余额不足通知（PushPlus / URL / 企业微信）
- 适用于国家电网覆盖省份（`linux/amd64`、`linux/arm64`）

---

## Web 控制台

启用 `WEB_DASHBOARD=true` 后，访问 `http://<主机>:8080/` 查看多户用电概览、阶梯用电、日/月图表与同步记录。

**本地运行（只读数据库）**：配置好 `.env` 中的 `DB_TYPE` 后，执行 `.\dev\run_dashboard.ps1`（Windows）或 `./dev/run_dashboard.sh`，详见 [dev/README.md](dev/README.md)。

![Web 控制台登录页](docs/attachment/login.png)

![Web 控制台监控页](docs/attachment/controller.png)

---

## Home Assistant 推送

本项目支持将抓取到的数据推送到 Home Assistant，默认启用（`ENABLE_HA_PUSH=true`），可通过 `ENABLE_HA_PUSH=false` 关闭。关闭后程序仅抓取数据并存入数据库，通过 Web 控制台查看。

### 推送方式

| 对比维度 | REST API | MQTT Discovery |
|---------|---------|---------------|
| **配置复杂度** | 需配置 template | 只需配置 MQTT 地址 |
| **实体创建** | 手动配置 template | 自动发现创建 |
| **配置说明** | [REST API 配置指南](docs/HA_CONFIG.md) | [MQTT 使用指南](docs/MQTT.md) |
| **兼容性** | 所有 HA 版本 | 需要 MQTT 集成 |
| **状态保持** | 需要缓存恢复 | retain 消息自动保持 |
| **网络开销** | HTTP 协议 | 轻量级 MQTT |

> **推荐**：MQTT Discovery 方式配置更简单，实体自动创建，详见 [MQTT 使用指南](docs/MQTT.md)。
>
> REST API 方式需要在 HA 的 `configuration.yaml` 中配置 template，详见 [REST API 配置指南](docs/HA_CONFIG.md)。

### 传感器列表

开启 HA 推送后，程序会自动在 Home Assistant 中创建以下实体（`xxxx` 为户号后四位）：

| 实体 | 说明 |
|------|------|
| `sensor.electricity_charge_balance_xxxx` | 电费余额（元） |
| `sensor.last_electricity_usage_xxxx` | 最近一天用电量（kWh） |
| `sensor.yearly_electricity_usage_xxxx` | 今年总用电量（kWh） |
| `sensor.yearly_electricity_charge_xxxx` | 今年总电费（元） |
| `sensor.month_electricity_usage_xxxx` | 上月用电量（kWh） |
| `sensor.month_electricity_charge_xxxx` | 上月电费（元） |
| `sensor.month_valley_usage_xxxx` | 当月谷时用电量（kWh，**需启用数据库**） |
| `sensor.month_flat_usage_xxxx` | 当月平时用电量（kWh，**需启用数据库**） |
| `sensor.month_peak_usage_xxxx` | 当月峰时用电量（kWh，**需启用数据库**） |
| `sensor.month_tip_usage_xxxx` | 当月尖时用电量（kWh，**需启用数据库**） |
| `sensor.prepay_balance_xxxx` | 应交金额（元） |
| `sensor.step_used_step1_xxxx` | 阶梯一阶已用电量（kWh，住宅用户） |
| `sensor.step_remain_step1_xxxx` | 阶梯一阶剩余电量（kWh，住宅用户） |
| `sensor.step_used_step2_xxxx` | 阶梯二阶已用电量（kWh，住宅用户） |
| `sensor.step_remain_step2_xxxx` | 阶梯二阶剩余电量（kWh，住宅用户） |
| `sensor.step_used_step3_xxxx` | 阶梯三阶已用电量（kWh，住宅用户） |
| `sensor.step_total_usage_xxxx` | 阶梯累计用电量（kWh，住宅用户） |
| `sensor.step_stage_xxxx` | 当前阶梯阶段（1/2/3，住宅用户） |

> MQTT Discovery 方式下实体自动创建，无需手动配置。REST API 方式需在 HA 中配置 template，详见 [REST API 配置指南](docs/HA_CONFIG.md)。

### HA 相关配置参数

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ENABLE_HA_PUSH` | `true` | 是否推送到 Home Assistant，设为 `false` 则仅抓取数据不推送 |
| `MQTT_HOST` | 空 | MQTT Broker 地址（推荐方式，填写后自动使用 MQTT Discovery） |
| `MQTT_PORT` | `1883` | MQTT 端口 |
| `MQTT_USERNAME` | 空 | MQTT 用户名 |
| `MQTT_PASSWORD` | 空 | MQTT 密码 |
| `MQTT_CLIENT_ID` | `ha_sgcc_electricity` | MQTT 客户端 ID |
| `MQTT_TOPIC_PREFIX` | `homeassistant` | MQTT Discovery 主题前缀 |
| `MQTT_DEVICE_ID` | `ha_sgcc_electricity` | MQTT 设备 ID |
| `MQTT_DEVICE_NAME` | `国家电网电费数据` | MQTT 设备名称 |
| `HASS_URL` | 空 | Home Assistant REST API 地址（MQTT 未配置时使用） |
| `HASS_TOKEN` | 空 | Home Assistant 长期访问令牌 |
| `HA_SKIP_UNCHANGED` | `false` | 传感器数值未变化时跳过更新（减少 API 调用） |

> 只要不填 `MQTT_HOST` 和 `HASS_URL`，即使 `ENABLE_HA_PUSH=true` 也不会推送。

### 将 Web 控制台嵌入 Home Assistant

通过 HA 的 **Webpage 仪表盘** 功能，可将 Web 控制台直接嵌入左侧菜单。详见 [面板集成指南](docs/HA_PANEL.md) 或 [快速指南](docs/QUICK_PANEL.md)。

---

## 安装部署

### 方式一：Home Assistant Add-on（推荐）

1. 进入 `设置` → `加载项` → `加载项商店`
2. 右上角 `...` → `仓库`，添加：`https://github.com/Poiig/sgcc_electricity`
3. 刷新页面，找到 **国家电网电费数据获取** 并安装
4. 切换到 `配置` 标签，填写手机号、密码
5. 配置推送方式：填写 `hass_url` + `hass_token`（REST API）或 `mqtt_host`（MQTT）
6. 保存配置，启动 Add-on

### 方式二：Docker Compose

```bash
mkdir sgcc_electricity && cd sgcc_electricity
curl -O https://raw.githubusercontent.com/Poiig/sgcc_electricity/master/docker-compose.yml
curl -O https://raw.githubusercontent.com/Poiig/sgcc_electricity/master/example.env
cp example.env .env && vim .env
docker compose up -d --force-recreate
```

**镜像地址：**

| 来源 | 地址 |
|------|------|
| GHCR | `ghcr.io/poiig/sgcc_electricity:latest` |
| GHCR 国内加速 | `ghcr.nju.edu.cn/poiig/sgcc_electricity:latest` |
| Docker Hub | `poiigzhao/sgcc_electricity:latest` |
| Docker Hub 国内加速 | `docker.1ms.run/poiigzhao/sgcc_electricity:latest` |

### 方式三：本地运行

详见 [本地开发指南](dev/LOCAL_DEV_GUIDE.md)

---

## 环境变量

Docker Compose 方式通过 `.env` 文件配置，完整配置项见 `example.env`。

**必填：**

| 变量 | 说明 |
|------|------|
| `PHONE_NUMBER` | 95598 登录手机号 |
| `PASSWORD` | 95598 登录密码 |

**Home Assistant 推送配置见 [Home Assistant 推送](#home-assistant-推送) 章节。**

**常用可选：**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `JOB_START_TIME` | `09:30` | 每天同步开始时间（程序会在该时间及 +12 小时各执行一次） |
| `RUN_ON_STARTUP` | `false` | Docker 启动后立即登录抓取 |
| `CAPTCHA_SOLVER` | `local` | 验证码识别（推荐 `llm`，详见下方说明） |
| `DB_TYPE` | sqlite | 数据库类型（sqlite / mysql / postgresql） |
| `LOGIN_METHOD` | password | 登录方式（password / qrcode） |
| `LOGIN_FALLBACK` | qrcode | 登录失败备选（qrcode / none） |
| `IGNORE_USER_ID` | 空 | 忽略的户号（逗号分隔） |
| `WEB_DASHBOARD` | true | 启用 Web 控制台 |
| `PUSH_TYPE` | none | 通知方式（none / pushplus / urlpush / wework） |
| `DATA_RETENTION_DAYS` | 365 | 数据库记录保留天数，0 表示永久保留 |

---

## 数据库

| `DB_TYPE` | 说明 |
|-----------|------|
| `sqlite` | **默认**。本地文件，适合单机 / Docker 部署 |
| `mysql` | 连接外部 MySQL |
| `postgresql` | 连接外部 PostgreSQL |

启用数据库后程序自动建表，详见 [数据库表结构说明](docs/DATABASE.md)。

---

## 验证码识别

| 模式 | 配置值 | 说明 |
|------|--------|------|
| 大模型视觉识别（**推荐**） | `llm` | 火山引擎豆包大模型，识别率高，支持点选 + 滑块 |
| 本地 OCR | `local` | 免费，基于 ddddocr + 图像匹配，适合点选验证码，存在识别失败的情况 |

> **推荐使用 `llm` 模式**：本地 OCR 方案基于图像匹配，受验证码样式变化影响较大，存在识别失败的情况。大模型方式识别率更高且同时支持点选和滑块验证码。
>
> 两种方式的详细配置说明见 [验证码接入指南](docs/LLM_CAPTCHA.md)。如不想处理验证码，可直接使用 `LOGIN_METHOD=qrcode` 扫码登录。

---

## 常见问题

详见 [常见问题文档](docs/FAQ.md)，涵盖验证码识别、传感器数据、数据库选择、HA 集成等常见问题。

---

## License

[Apache License 2.0](LICENSE)
