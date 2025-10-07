# FFM

简易期货交易训练平台（Futures Flipped Market）的方案设计与实现记录。

## 当前进展
- [x] 制定整体方案：详见 [docs/architecture_plan.md](docs/architecture_plan.md)。
- [x] 初始化前后端项目结构，接入基础行情导入、回放与模拟交易接口。
- [x] 行情回放 MVP（离线数据加载、启动/暂停/单步回放、进度状态同步）。
- [x] 前端改为基于 Vue 浏览器构建与 ECharts 的纯静态页面，无需打包流程。
- [x] 模拟交易核心模块（订单管理、撮合、账户与盈亏统计）。

## 项目简介
该项目面向个人学习使用，目标是提供一个通过历史行情回放进行期货模拟交易的训练环境。前端采用 Vue 3 浏览器版本配合 Axios 与 ECharts，通过本地静态资源直接渲染 K 线主图、布林带（BOLL）与成交量等量价指标；后端使用 Flask 对接 AkShare 获取指定品种与日期区间的历史行情，并在本地 SQLite 中缓存，用于回放、指标计算与撮合逻辑实现。系统不涉及实时行情接入，也不包含权限控制，聚焦离线训练。

## 运行说明

> 💡 **Windows PowerShell 编码提示**：在执行以下命令前，请先运行 `chcp 65001` 或
> `powershell -NoProfile -Command "$PSDefaultParameterValues['Out-File:Encoding']='utf8';[Console]::OutputEncoding=[Text.Encoding]::UTF8"`
> 以避免中文输出乱码。

### 后端（Flask）

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows 使用 .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m backend  # 默认监听 http://127.0.0.1:8000
```

若希望手动控制 host/port，可在激活虚拟环境后执行：

```bash
set FLASK_APP=backend.app:create_app  # PowerShell 使用 $env:FLASK_APP="backend.app:create_app"
flask run --host 0.0.0.0 --port 8000
```

默认会使用 `backend/data/training.db` 作为 SQLite 数据库路径，可通过设置 `FFM_DATABASE_URL` 环境变量自定义位置。
静态前端资源默认读取仓库根目录下的 `frontend/`，也可以通过 `FFM_FRONTEND_DIR` 指向自定义路径。

> ⚠️ 如曾使用旧版本启动过后端，升级到当前模拟交易模块后建议删除旧的 `backend/data/training.db`，再重新启动以自动建表。

### 前端（静态页面）

无需 npm 或构建工具，后端启动后会自动托管 `frontend/` 目录下的静态资源，访问 `http://127.0.0.1:8000/` 即可打开界面。

如果希望单独部署前端，也可以使用任意静态服务器手动托管：

```bash
cd frontend
python -m http.server 5173
```

随后访问 `http://localhost:5173/index.html`。页面默认将 API 地址指向 `http://localhost:8000/api`，若后端监听地址不同，可在加载 `main.js` 前覆盖 `window.FFM_API_BASE`：

```html
<script>
  window.FFM_API_BASE = 'http://127.0.0.1:9000/api';
</script>
<script type="module" src="./main.js"></script>
```

## 下一步计划
1. 引入回放推送/策略钩子，支持策略联调与自动下单。
2. 丰富前端交互体验，补充盘口/持仓细节以及多周期切换。
3. 编写交易与指标计算的单元测试，巩固回放流程可靠性。

## 新增能力概览

- **合约管理**：`/api/contracts` 返回已导入的品种、周期与可用日期范围，方便快速选择训练集。
- **行情回放控制**：`/api/playback/*` 系列接口，可启动、暂停、恢复及按步获取下一批 K 线，前端提供速度与批量调节。
- **模拟交易引擎**：提供 `/api/orders` 下单与撤单、`/api/trades` 成交查询以及 `/api/portfolio` 账户汇总，支持限价/市价单、保证金占用与盈亏统计。
- **前端回放面板**：静态页面集成导入、合约选择、回放控制、K 线展示以及模拟交易表单，开箱即用。

## 模拟交易接口速览

- `POST /api/orders`：提交市价或限价订单，自动完成风险校验与即时撮合。
- `GET /api/orders`：查看当前及历史订单状态，支持撤单操作。
- `POST /api/orders/<id>/cancel`：撤销未成交订单。
- `GET /api/trades`：查询成交记录。
- `GET /api/portfolio`：获取账户现金、权益、保证金占用以及各合约的实时持仓盈亏。
