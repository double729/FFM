# FFM

简易期货交易训练平台（Futures Flipped Market）的方案设计与实现记录。

## 当前进展
- [x] 制定整体方案：详见 [docs/architecture_plan.md](docs/architecture_plan.md)。
- [x] 初始化前后端项目结构，接入基础行情导入、回放与模拟交易接口。
- [ ] 行情回放 MVP。
- [ ] 模拟交易核心模块。

## 项目简介
该项目面向个人学习使用，目标是提供一个通过历史行情回放进行期货模拟交易的训练环境。前端将使用 Vue 构建交互界面，展示 K 线主图、布林带（BOLL）与成交量等量价指标；后端使用 Flask 对接 AkShare 获取指定品种与日期区间的历史行情，并在本地 SQLite 中缓存，用于回放、指标计算与撮合逻辑实现。系统不涉及实时行情接入，也不包含权限控制，聚焦离线训练。

## 运行说明

### 后端（Flask）

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows 使用 .venv\\Scripts\\activate
pip install -r requirements.txt
export FLASK_APP=app:app
flask run --host 0.0.0.0 --port 8000
```

默认会使用 `backend/data/training.db` 作为 SQLite 数据库路径，可通过设置 `FFM_DATABASE_URL` 环境变量自定义位置。

### 前端（Vue 3 + Vite）

```bash
cd frontend
npm install
npm run dev -- --host
```

开发服务器默认会代理 `/api` 请求到 `http://localhost:8000`，确保后端已启动即可。

## 下一步计划
1. 补充接口校验、错误处理与导入状态反馈。
2. 丰富模拟交易模型，支持账户余额、保证金及盈亏计算。
3. 优化前端交互体验，提供多周期切换与指标配置。

