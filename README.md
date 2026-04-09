# Auto Register

高度可配置的网站自动注册框架。支持可插拔的邮箱提供者、站点注册策略和输出格式。

## 特性

- **配置驱动**：通过 YAML 配置文件定义站点的 URL、表单选择器、OAuth 参数和输出格式
- **可插拔邮箱**：内置 Mail.tm 和 1secMail，通过注册表模式扩展
- **可插拔站点策略**：每个站点独立策略文件，新增站点无需修改引擎代码
- **可配置输出**：JSON / ENV 等格式，字段映射可自定义
- **Stealth 放越权引擎**：可选启用 playwright-stealth 直接在浏览器底层规避检测
- **住宅 HTTP 代理池防封**：支持直接配置代理节点穿透数据中心黑名单

## 快速开始

### 1. 虚拟环境配置 (推荐)

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境 (Windows)
.venv\Scripts\activate
# 激活虚拟环境 (Linux/macOS)
source .venv/bin/activate
```

### 2. 安装依赖

您可以直接安装目前最新补充的 `requirements.txt`，或者通过本项目自带的构建机制安装：

```bash
pip install -r requirements.txt
# 或者
# pip install .

# 必须执行这一步以安装系统内部浏览器内核
playwright install chromium
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

### 4. 运行注册

**方式一：使用便捷脚本运行（支持循环及无头模式自动加持）**

```bash
python scripts/run.py                  # 注册 1 个
python scripts/run.py 5 30             # 循环注册最多 5 个，间隔 30 分钟
python scripts/run.py 0 30             # 无限循环，间隔 30 分钟（Ctrl+C 停止）
python scripts/run.py 2 10 --site qwen # 注册 2 个，间隔 10 分钟，并指定站点
```

**方式二：进入 src 直接运行 CLI**

```bash
cd src
python -m cli --site qwen --headless
```

## 配置

### 环境变量 (`.env`)

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AUTO_REGISTER_EMAIL_PROVIDER` | `mailtm` | 邮箱提供者 (`mailtm` / `1secmail`) |
| `TARGET_SITE` | `qwen` | 目标站点（对应 `config/` 下的 yaml 文件名） |
| `AUTO_REGISTER_NAVIGATION_TIMEOUT` | `30000` | 页面导航超时（毫秒） |
| `AUTO_REGISTER_EMAIL_TIMEOUT` | `120` | 等待激活邮件超时（秒） |
| `AUTO_REGISTER_POLL_INTERVAL` | `5` | 邮件轮询间隔（秒） |
| `USE_PLAYWRIGHT_STEALTH` | `false` | 启用底层 Stealth 浏览器注入防机器指纹检测 |
| `HTTP_PROXY_URL` | - | 网络代理地址 (Proxy URL) |
| `SAVE_DIR` | `./token` | Token 输出目录 |

### 站点配置 (`config/*.yaml`)

参见 `config/qwen.yaml` 作为完整示例。

## 扩展

### 添加新邮箱提供者

1. 在 `src/providers/` 下创建 `my_provider.py`，实现 `EmailProvider` 接口
2. 在 `src/providers/__init__.py` 的 `EMAIL_PROVIDER_REGISTRY` 中注册

### 添加新站点

1. 在 `src/sites/` 下创建站点目录和策略文件，实现 `SiteStrategy` 接口
2. 在 `src/sites/__init__.py` 的 `SITE_STRATEGY_REGISTRY` 中注册
3. 在 `config/` 下创建对应的 YAML 配置文件

### 添加新输出格式

1. 在 `src/writers/` 下创建写入器文件，实现 `OutputWriter` 接口
2. 在 `src/writers/__init__.py` 的 `OUTPUT_WRITER_REGISTRY` 中注册
