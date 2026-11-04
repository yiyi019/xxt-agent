# 🤖 Xuexitong Agent Core (学习通 Agent 专属核心包)

专为 **AI Agent、智能体调度框架（LangChain, AutoGen, CrewAI, MCP 等）以及自动化脚本** 打造的轻量级学习通课程自动化解决方案。

> 📌 **设计理念**：
> 彻底剥离繁琐且消耗资源的 GUI 界面（如 Tkinter/CustomTkinter），提供无头模式（Headless）、纯净的 Python SDK、标准 JSON 命令行接口以及大模型专属的函数调用（Function Calling）规范。

---

## 💬 Agent 一键装配提示词 (Copy-Paste Prompt for AI Agents)

> 💡 **直接复制以下内容发送给任何 AI 编程助手（如 Antigravity / Claude Code / Cursor / Windsurf 等），即可让它全自动为您完成环境安装并引导配置：**

```text
请帮我安装并配置开源学习通自动化项目：https://github.com/yiyi019/xxt-agent。
请按以下结构化流程引导我：
1. 克隆该代码仓库并安装 requirements.txt 中的依赖；
2. 检测是否已初始化；若未配置，请结构化向我询问：
   - 学习通登录手机号与密码；
   - 是否开启 DeepSeek AI 自动答题（若开启且未配 key 则询问 API Key 一次性保存，下次不再询问；若不开启则自动跳过测验）；
   - 待刷课程名称或课程排队表（支持多门课程顺序排队，单门课达到今日观看时长或任务点上限时自动平滑切换下一门）；
   - 运行模式偏好（1: 可视化 GUI 浏览器实时观看, 2: 纯后台静默 Headless, 3: 终端动态仪表盘 TUI）；
3. 执行 `python -m xxt_agent.cli wizard` 完成配置持久化，并按我选择的方式立即开始自动化刷课。全程尽量结构化引导，开箱即用。
```

---

## ✨ 核心特性

| 特性 | 说明 |
| :--- | :--- |
| **纯净轻量 (Lightweight)** | 零 GUI 依赖，支持静默无头运行（Headless），后台内存占用减少 70%+。 |
| **Agent 原生友好 (Agent-Native)** | 提供 `--json` 严格输出模式与标准退出状态码（0, 1, 2...），便于大模型 100% 精准解析。 |
| **多模型 AI 解题 (DeepSeek)** | 内置 `deepseek-v4.1-flash` 大模型支持（带多模型自动回退），针对单选、多选、判断、填空定制 Prompt。 |
| **反混淆字体解密 (FontTools)** | 动态解析超星加密混淆字体，在内存中完成字形 MD5 还原，彻底避免题目乱码。 |
| **全方位风控规避 (Stealth)** | 自动拦截前端人脸识别弹窗（支持 API 签名 + 图像微扰动绕过），注入防失焦（Anti-Blur）脚本防止切屏暂停。⚠️ 注：若遇超星服务端强制活体采集（全页遮罩且服务端不下发视频内容），需先在手机 APP 扫码完成人脸采集后再继续。 |
| **标准函数调用 Schema** | 自带 `agent_tools.json`，方便各类 Agent 平台直接注册为原生 Tool。 |

---

## 🚀 快速使用 (Agent CLI)

所有 CLI 命令均支持 `--json` 参数，Agent 可以在子进程中调用并直接获取 JSON 输出：

### 1. 检查运行环境与状态
```bash
python -m xxt_agent.cli status --json
```
**JSON 响应示例：**
```json
{
  "ok": true,
  "browser": "edge",
  "driver_path": null,
  "driver_exists": true,
  "cookies_exist": true,
  "api_key_configured": true,
  "deepseek_model": "deepseek-v4.1-flash",
  "headless_mode": true,
  "default_speed": 2.0
}
```

### 2. 获取当前账号已选课程列表
```bash
python -m xxt_agent.cli list-courses --json
```

### 3. 查看特定课程的章节完成情况
```bash
python -m xxt_agent.cli chapters --course "艺术鉴赏" --json
```

### 4. 自动执行刷课 (可指定时长与倍速)
```bash
# 刷【艺术鉴赏】课程，1.0 倍速，GUI 可视化窗口
python -m xxt_agent.cli run --course "艺术鉴赏" --gui --speed 1.0

# 启动终端动态仪表盘监控
python -m xxt_agent.cli tui --course "艺术鉴赏"
```

### 5. 课程代办排队表 (多门课自动轮转与满额自动换课)
当某门课达到今日观看时长上限（如 45/45 分钟）或任务点上限时，Agent 将自动安全关闭该课程，平滑切换至排队表中的下一门课：
```bash
# 执行排队表刷课
python -m xxt_agent.cli queue run --courses "艺术鉴赏" "音乐鉴赏" "大学生心理健康教育" --gui

# 查看/管理已配置的默认代办排队表
python -m xxt_agent.cli queue list
python -m xxt_agent.cli queue set --courses "艺术鉴赏" "音乐鉴赏"
```

### 6. 开箱即用配置向导 (Wizard)
首次使用或重新配置时，一键启动交互式引导，询问账号、AI 答题、排队课程及模式：
```bash
python -m xxt_agent.cli wizard
```

### 7. 调用 AI 题目求解器 (单题求解)
```bash
python -m xxt_agent.cli solve --question "以下哪部作品是达芬奇的代表作？" --type "单选题" --options "A:《蒙娜丽莎》" "B:《星月夜》" "C:《向日葵》" --json
```

---

## 🐧 Linux / Docker 容器与无头环境配置

在无桌面显示器的 Linux 服务器或 Docker 容器中运行时，支持通过环境变量进行定制：

| 环境变量 | 作用说明 | 示例 |
| :--- | :--- | :--- |
| `XXT_CHROME_BINARY` | 自定义 Chrome/Chromium 二进制程序路径 | `/usr/bin/google-chrome` 或 `/usr/bin/chromium-browser` |
| `XXT_PROXY` | 设置代理服务器 (亦兼容系统的 `HTTP_PROXY`) | `http://127.0.0.1:7890` |
| `XXT_COURSE_URL` | 自定义选课入口地址 (默认 `mooc1.chaoxing.com/visit/interaction`) | `https://mooc1.chaoxing.com/visit/interaction` |

内置包含 `--no-sandbox`, `--no-zygote`, `--disable-breakpad`, `--disable-crash-reporter` 等稳定性参数，容器内开箱即用。

---

## 🔒 安全与凭据保管规范

> [!WARNING]
> `config.json` 包含您的学习通账号密码与 DeepSeek API Key（已内置在 `.gitignore` 中，切勿提交至公共仓库）。
> 在多用户 Linux 服务器环境下，建议收紧配置文件访问权限：
> ```bash
> chmod 600 config.json
> ```

---

## 🐍 Python SDK 使用示例

任何 Python 智能体或脚本都可以直接导入并作为类调用：

```python
from xxt_agent import XuexitongAgent

# 使用上下文管理器自动管理浏览器资源
with XuexitongAgent() as agent:
    # 1. 查看已选课程
    courses = agent.list_courses()
    print("课程列表:", courses)

    # 2. 自动刷课 30 分钟 (1800 秒)，2 倍速
    result = agent.run_course(
        course_name="艺术鉴赏",
        duration_seconds=1800,
        speed=2.0,
        max_chapters=5
    )
    print("刷课结果:", result)

    # 3. 单独搜题
    ans = agent.solve(
        question="艺术鉴赏的核心要素包括什么？",
        q_type="简答题"
    )
    print("AI 答案:", ans)
```

---

## 🛠️ 大模型 Function Calling 工具定义

在项目目录中的 `agent_tools.json` 已内置 OpenAI / Anthropic / Gemini 兼容的 Tool Schema，包括：
- `xxt_get_status`
- `xxt_list_courses`
- `xxt_get_chapters`
- `xxt_run_course`
- `xxt_solve_question`

任意智能体框架可通过读取该 JSON 即可无缝将上述能力加载为工具。
