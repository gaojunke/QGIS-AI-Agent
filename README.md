# QGIS AI Agent

[![QGIS](https://img.shields.io/badge/QGIS-3.28%2B-589632)](https://qgis.org/)
[![License](https://img.shields.io/badge/license-GPLv2-blue.svg)](./LICENSE)
[![Repository](https://img.shields.io/badge/GitHub-QGIS--AI--Agent-181717)](https://github.com/gaojunke/QGIS-AI-Agent)

一个聊天式 QGIS 插件，用自然语言驱动 QGIS Processing 算法和常见图层操作，也支持普通问答。

## 作者信息

- 作者：槐中路科科
- 邮箱：`gaojunke@outlook.com`
- QQ：`996517087`

## 界面素材

- 上传到 QGIS 插件仓库前，建议补 3 张真实截图到 [`docs/screenshots`](/H:/软著/qgis插件/nl_qgis_agent/docs/screenshots)：
- `dock-panel.png`：主聊天停靠面板
- `settings-dialog.png`：模型与后端设置页
- `standard-rendering.png`：按规程渲染前后对比
- 已提供上传资产说明：[ `UPLOAD_ASSETS.md` ](/H:/软著/qgis插件/nl_qgis_agent/docs/UPLOAD_ASSETS.md)

## 当前能力

- 菜单栏和工具栏入口
- 聊天式停靠面板
- 真正的消息列表界面，底部固定输入区
- `Enter` 发送，`Shift+Enter` 换行
- 自动保存聊天记录
- 支持短会话记忆，可继承上一句或最近几句里提到的图层/结果
- 最近操作历史
- 最近操作支持点击复用到输入框
- 问答 / 执行 / 自动 三种模式
- 自动读取当前工程图层上下文，但不在界面中展示
- 上下文包含图层字段信息，便于字段感知
- 支持本地图层/工程问答，例如面积、字段、字段类型、图层列表、坐标系、要素数量
- 工具注册表和执行白名单
- 当前 QGIS 已安装的任意合法 Processing 算法都可执行
- 支持 DeepSeek、Gemini、OpenAI-compatible API 和 Ollama
- DeepSeek 支持独立 provider 分支，可选 `deepseek-chat` / `deepseek-reasoner`
- DeepSeek 支持 `thinking` 开关、tool calling 规划和 reasoning 说明展示
- 支持托管后端登录模式，登录后统一走你自己的服务器和模型额度
- 支持自定义 Skill 提示词注入
- 支持配置 MCP bridge URL，把外部上下文并入模型规划
- 支持测试连通性和自动获取模型列表
- 模型不可用时回退到规则解析
- 支持多步链式规划
- 支持问答模式，非操作性问题会直接回答且不执行 QGIS 操作
- 支持执行前解释
- 支持图层歧义确认，且在聊天消息内联选择
- 支持分层错误提示
- 支持执行状态流式更新
- 支持最近操作回退建议
- 执行 Processing 算法并将结果图层加入地图
- 发送一次就直接规划并执行
- 支持常见直接操作:
  - 缩放到图层 / 缩放到全部图层
  - 激活图层
  - 重命名图层
  - 显示 / 隐藏图层
  - 删除图层
  - 打开属性表
  - 打开图层属性
  - 打开字段计算器
  - 打开统计摘要
  - 打开工程属性
  - 打开布局管理器
  - 新建布局 / 打开布局设计器
  - 打开 Python 控制台
  - 打开处理工具箱
  - 打开模型构建器
  - 打开脚本编辑器
  - 按表达式选择 / 清除选择
  - 加载矢量图层
  - 加载栅格图层
  - 单色符号化
  - 按字段分类渲染
  - 按内置规程标准渲染
- 当前白名单 Processing 算法:
  - `native:intersection`
  - `native:clip`
  - `native:buffer`
  - `native:dissolve`
  - `native:difference`
  - `native:union`
  - `native:mergevectorlayers`
  - `native:reprojectlayer`
  - `native:multiparttosingleparts`
  - `native:fixgeometries`
  - `native:extractbyexpression`
  - `native:fieldcalculator`
- 除以上常用工具外，插件也允许调用当前 QGIS 运行环境中已安装的其他合法 Processing 算法

## 已验证的第一版命令示例

- `把道路图层和行政区图层相交`
- `对河流图层做 50 米缓冲`
- `把地块图层裁剪到研究区图层`
- `缩放到行政区图层`
- `先把道路图层缓冲 50 米，再和行政区图层相交，并把结果显示在地图上`
- `把地块图层重投影到 EPSG:3857`
- `隐藏道路图层`
- `把结果重命名为 "道路缓冲区"`
- `在地块图层中选择表达式 "area > 1000"`
- `给地块图层计算面积并保存到字段 area`
- `地块图层面积多少`
- `地块图层面积多少亩`
- `把地块图层总面积换算成公顷`
- `这是多少公顷`
- `地块图层有哪些字段，分别是什么类型`
- `当前工程有哪些图层`
- `打开布局管理器`
- `新建布局`
- `打开布局设计器`
- `打开 Python 控制台`
- `打开模型构建器`
- `打开脚本编辑器`
- `打开道路图层的图层属性`
- `打开地块图层字段计算器`
- `把地块图层符号化成红色`
- `把道路图层颜色改成 #1e88e5`
- `把地块图层按字段 dlbm 分类渲染`
- `按市级国土空间总体规划制图规范给地类图层配色`
- `把现状用地图层按附录B标准渲染`
- `把规划分区图层按附录C标准渲染`
- `把控制线图层按附录D标准渲染`

## 安装

1. 将 `nl_qgis_agent` 文件夹复制到你的 QGIS 插件目录。
2. 重启 QGIS。
3. 在插件管理器启用 `QGIS AI Agent`。

常见插件目录:

- Windows: `%APPDATA%\\QGIS\\QGIS3\\profiles\\default\\python\\plugins`

## 打包发布

- 双击根目录下的 [ `build_release.bat` ](/H:/软著/qgis插件/nl_qgis_agent/build_release.bat) 可一键清理缓存并生成发布 ZIP。
- PowerShell 脚本入口是 [ `build_release.ps1` ](/H:/软著/qgis插件/nl_qgis_agent/scripts/build_release.ps1)。
- 生成结果位于 `dist/nl_qgis_agent-版本号.zip`。

## 设置

在插件菜单里打开 `Agent Settings`:

- `Provider = Disabled`
  - 不使用模型，依赖内置规则解析
- `Provider = DeepSeek`
  - 默认预置 `Base URL = https://api.deepseek.com`
  - 填写 `API Key`
  - 默认模型为 `deepseek-chat`，也可切换到 `deepseek-reasoner`
  - 点击 `获取模型`
  - 在下拉框中选择模型
  - 点击 `测试连接`
  - 可按需开启 `DeepSeek thinking`
  - 可按需开启 `DeepSeek tool calling`
- `Provider = Managed Backend`
  - `Base URL` 填你的后端地址，例如 `http://your-server:8000`
  - 填 `Backend Username / Backend Password`
  - 点击 `登录后端`
  - 点击 `获取模型`
  - 在下拉框中选择模型
  - 保存后聊天请求会统一走你的后端
- `Provider = Gemini`
  - 默认预置 `Base URL = https://generativelanguage.googleapis.com/v1beta/openai/`
  - 填写 `API Key`
  - 默认模型为 `gemini-3-flash-preview`
  - 点击 `获取模型`
  - 在下拉框中选择模型
  - 点击 `测试连接`
- `Provider = OpenAI Compatible`
  - 例如任何兼容 `/chat/completions` 的服务
- `Provider = Ollama`
  - 例如本地 `http://localhost:11434`
- `Skills`
  - 可填写长期能力提示，例如行业规范、企业术语、工作流约束
- `MCP Bridge URLs`
  - 每行一个 HTTP URL
  - 插件会在规划前向这些地址发送 `POST JSON`
  - 建议你的 bridge 返回 `context`、`text`、`summary` 或 `content` 字段之一

## 规划输出格式

模型必须返回 JSON 计划，而不是代码。插件执行的是结构化动作，不会直接执行模型生成的 Python。

## 执行安全

- 执行器会校验步骤是否在工具白名单中
- 删除图层这类高风险操作会强制要求确认
- 模型即使返回了未注册工具，也不会执行

## 当前限制

- 执行状态是分阶段更新，不是真正的 token 级网络流式输出
- 部分 QGIS 原生窗口依赖具体版本或插件菜单动作名称，插件会优先调用官方接口，找不到时再尝试触发界面动作
- 回退建议是操作建议，不是完整事务回滚
- 字段感知已加入上下文，但复杂字段映射仍主要依赖模型能力

## 修改记录

- `0.2.0`
  - 对话框中的助手标题由“插件”改为“AI”。
  - 补充作者信息、插件描述和元数据。
  - 增强 DeepSeek 支持，加入 thinking、tool calling 和 reasoning 展示。
  - 增加图层符号化、标准样式包和按规程渲染能力。
  - 优化执行状态、取消机制、上下文缓存与错误提示。
- `0.1.0`
  - 初始版本，提供聊天式命令执行和基础问答能力。
