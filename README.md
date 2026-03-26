# QGIS AI Agent

[![QGIS](https://img.shields.io/badge/QGIS-3.28%2B-589632)](https://qgis.org/)
[![License](https://img.shields.io/badge/license-GPLv2-blue.svg)](./LICENSE)
[![Repository](https://img.shields.io/badge/GitHub-QGIS--AI--Agent-181717)](https://github.com/gaojunke/QGIS-AI-Agent)

面向国土空间规划、土地整治、调查监测和部分测绘场景的 QGIS 智能助手。插件以聊天面板的方式工作，将自然语言解析成安全的执行计划，再调用 QGIS Processing 算法和常见界面操作完成任务。

## 作者

- 作者：槐中路科科
- 邮箱：`gaojunke@outlook.com`
- QQ：`996517087`

## 项目定位

这个插件不是简单的“把大模型接进 QGIS”，而是围绕规划业务做了三层约束：

- 自然语言先转换成结构化计划，再执行。
- 高风险操作保留确认和错误提示。
- 结合工程上下文、短会话记忆、字段信息和规程样式，尽量减少纯聊天式误判。

## 当前亮点

- 聊天式停靠面板，支持 `Enter` 发送、`Shift+Enter` 换行
- 自动读取当前工程图层上下文，支持字段感知
- 支持本地问答，例如面积、字段、图层列表、坐标系、要素数量
- 支持问答 / 执行 / 自动 三种模式
- 支持最近操作、短会话记忆、图层歧义确认
- 支持 DeepSeek、Gemini、OpenAI Compatible、Ollama 和订阅服务 / 托管 API
- DeepSeek 支持 `thinking`、tool calling 和 reasoning 展示
- 支持图层单色渲染、分类渲染、按规程标准渲染
- 支持规则回退，模型不可用时仍可处理常见命令

## 主要功能

### 1. Processing 执行

当前白名单内置算法包括：

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

同时支持在高级模式下调用当前 QGIS 环境中其他已安装的合法 Processing 算法。

### 2. 常见 QGIS 操作

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

### 3. 符号化与规程样式

- 单色符号化
- 按字段分类渲染
- 按内置规程标准渲染
- 支持标准样式库机制，便于后续扩展更多规程

### 4. 模型与规划能力

- 结构化 JSON 计划执行
- 多步链式规划
- 模型失败时自动回退到规则解析
- 自定义 Skill 提示词注入
- MCP Bridge 外部上下文接入

## 命令示例

### 数据处理

- `把道路图层和行政区图层相交`
- `对河流图层做 50 米缓冲`
- `把地块图层裁剪到研究区图层`
- `先把道路图层缓冲 50 米，再和行政区图层相交，并把结果显示在地图上`
- `把地块图层重投影到 EPSG:3857`
- `给地块图层计算面积并保存到字段 area`

### 本地问答

- `地块图层面积多少`
- `地块图层面积多少亩`
- `把地块图层总面积换算成公顷`
- `这是多少公顷`
- `地块图层有哪些字段，分别是什么类型`
- `当前工程有哪些图层`

### 界面与图层操作

- `隐藏道路图层`
- `把结果重命名为 "道路缓冲区"`
- `打开布局管理器`
- `打开道路图层的图层属性`
- `打开地块图层字段计算器`

### 图层样式

- `把地块图层符号化成红色`
- `把道路图层颜色改成 #1e88e5`
- `把地块图层按字段 dlbm 分类渲染`
- `按市级国土空间总体规划制图规范给地类图层配色`
- `把现状用地图层按附录B标准渲染`
- `把规划分区图层按附录C标准渲染`
- `把控制线图层按附录D标准渲染`

## 安装

1. 将 `nl_qgis_agent` 文件夹复制到 QGIS 插件目录。
2. 重启 QGIS。
3. 在插件管理器启用 `QGIS AI Agent`。

常见插件目录：

- Windows: `%APPDATA%\\QGIS\\QGIS3\\profiles\\default\\python\\plugins`

## 模型配置

在插件菜单中打开 `QGIS AI Agent Settings`。

### DeepSeek

- 默认 `Base URL = https://api.deepseek.com`
- 默认模型 `deepseek-chat`
- 可切换到 `deepseek-reasoner`
- 支持 `thinking`
- 支持 tool calling 规划

### Gemini

- 默认 `Base URL = https://generativelanguage.googleapis.com/v1beta/openai/`
- 默认模型 `gemini-3-flash-preview`
- 依赖 `openai` SDK

### 其他 Provider

- `Subscription / Hosted API`
- `OpenAI Compatible`
- `Ollama`

### 订阅服务 / 托管 API

- 用户可以继续填写自己的 API Key 使用各家模型
- 也可以切换到 `Subscription / Hosted API`
- 在该模式下支持两种用法：
  - 直接粘贴你发放的 `Subscription Token`
  - 填写订阅账号和密码，点击 `Login to Get Token` 自动获取令牌

## 界面素材

上传到 QGIS 插件仓库前，建议补 3 张真实截图到 [`docs/screenshots`](/H:/软著/qgis插件/nl_qgis_agent/docs/screenshots)：

- `dock-panel.png`
- `settings-dialog.png`
- `standard-rendering.png`

上传素材说明见 [ `UPLOAD_ASSETS.md` ](/H:/软著/qgis插件/nl_qgis_agent/docs/UPLOAD_ASSETS.md)。

## 打包发布

- 双击 [ `build_release.bat` ](/H:/软著/qgis插件/nl_qgis_agent/build_release.bat) 可一键清理缓存并生成发布 ZIP
- PowerShell 入口为 [ `build_release.ps1` ](/H:/软著/qgis插件/nl_qgis_agent/scripts/build_release.ps1)
- 生成结果位于 `dist/nl_qgis_agent-版本号.zip`

## 安全说明

- 模型必须返回结构化计划，不直接执行模型生成代码
- 执行器会校验步骤是否在允许范围内
- 删除图层等高风险操作会强制确认
- 模型返回未注册工具时不会执行

## 当前限制

- 执行状态是分阶段更新，不是真正的 token 级流式输出
- 部分原生 QGIS 界面动作依赖具体版本或菜单名称
- 回退建议是操作建议，不是完整事务回滚
- 复杂字段映射和行业规则仍需要继续增强

## 发布说明

正式发布说明见 [ `RELEASE_NOTES.md` ](/H:/软著/qgis插件/nl_qgis_agent/RELEASE_NOTES.md)。
