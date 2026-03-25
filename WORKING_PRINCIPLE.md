# Natural Language QGIS Agent 工作原理

## 1. 插件定位

`Natural Language QGIS Agent` 是一个基于 QGIS Python 插件机制实现的自然语言助手。

它的目标不是直接执行模型生成的 Python 代码，而是把用户输入的自然语言拆成两类结果：

- `问答结果`
  - 只回答问题，不对当前 QGIS 工程做任何修改
- `动作计划`
  - 生成结构化步骤，再由本地执行器调用 QGIS Processing 或 PyQGIS API

这意味着插件本质上是一个：

- `聊天界面`
- `上下文采集器`
- `规划器`
- `安全执行器`

的组合系统。

## 2. 整体架构

主要模块如下：

- [plugin.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/plugin.py)
  - QGIS 插件入口，负责菜单、工具栏、面板挂载
- [ui/dock_widget.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/ui/dock_widget.py)
  - 聊天主界面，负责消息展示、发送命令、状态更新、交互按钮
- [ui/chat_widgets.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/ui/chat_widgets.py)
  - 聊天气泡、消息列表、输入框回车发送等 UI 组件
- [ui/settings_dialog.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/ui/settings_dialog.py)
  - 模型设置、模型获取、连通性测试
- [context/project_context.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/context/project_context.py)
  - 读取当前工程中的图层、字段、CRS、几何类型等上下文
- [planner/planner.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/planner/planner.py)
  - 规划主入口，决定走大模型还是规则解析
- [planner/prompt_builder.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/planner/prompt_builder.py)
  - 构造发给大模型的系统提示词和用户提示词
- [planner/rule_based_parser.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/planner/rule_based_parser.py)
  - 本地规则解析器，模型不可用时兜底
- [planner/schema.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/planner/schema.py)
  - 定义规划结果的数据结构
- [tool_registry.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/tool_registry.py)
  - 工具注册表和白名单
- [executor/processing_executor.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/executor/processing_executor.py)
  - 执行结构化步骤，调用 QGIS Processing 与结果图层处理
- [executor/qgis_api_executor.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/executor/qgis_api_executor.py)
  - 执行直接的 QGIS API 操作
- [llm/factory.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/llm/factory.py)
  - 根据 Provider 创建模型客户端
- [llm/openai_client.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/llm/openai_client.py)
  - OpenAI 兼容接口客户端
- [llm/ollama_client.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/llm/ollama_client.py)
  - Ollama 客户端
- [settings.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/settings.py)
  - 持久化保存模型设置、聊天模式、聊天历史、最近操作

## 3. 用户一次交互的完整流程

### 3.1 输入阶段

用户在聊天面板输入一句自然语言，例如：

```text
把道路图层和行政区图层相交，并把结果显示在地图上
```

聊天界面会先记录一条用户消息，然后进入处理流程。

### 3.2 上下文采集

插件通过 [project_context.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/context/project_context.py) 读取当前 QGIS 工程信息。

采集内容包括：

- 工程标题
- 图层数量
- 图层名称
- 图层 ID
- 图层类型
- 数据源
- CRS
- 几何类型
- 要素数量
- 字段名和字段类型

字段信息很重要，因为它让模型知道：

- 哪些图层是矢量图层
- 哪些字段可以用于表达式筛选
- 用户说的属性条件是否可能成立

### 3.3 规划阶段

插件会根据当前模式走不同分支：

- `自动`
  - 自动判断这是问答还是执行
- `问答`
  - 强制优先回答，不生成执行步骤
- `执行`
  - 强制优先生成动作计划

规划有两种来源：

#### 方案 A：大模型规划

如果已经配置模型，插件会：

1. 构造系统提示词
2. 注入工具白名单
3. 注入当前工程上下文
4. 要求模型输出严格 JSON

模型返回的数据不是自由文本，而是结构化结果，例如：

```json
{
  "summary": "对两个图层执行相交分析",
  "requires_confirmation": false,
  "response_text": "",
  "steps": [
    {
      "kind": "processing",
      "tool_id": "native:intersection",
      "params": {
        "INPUT": { "layer": "道路图层" },
        "OVERLAY": { "layer": "行政区图层" },
        "OUTPUT": "TEMPORARY_OUTPUT"
      }
    },
    {
      "kind": "qgis",
      "operation": "zoom_to_layer",
      "args": {
        "layer": { "result": "last" }
      }
    }
  ]
}
```

如果是普通问答，模型可以返回：

```json
{
  "summary": "问答请求",
  "requires_confirmation": false,
  "response_text": "这里是对问题的回答，并说明未对图层和工程做任何操作。",
  "steps": []
}
```

#### 方案 B：规则解析兜底

如果模型不可用、返回格式异常、连通失败，插件会回退到规则解析器。

规则解析器适合处理高频命令，例如：

- 相交
- 裁剪
- 缓冲
- 溶解
- 重投影
- 按表达式提取
- 缩放到图层
- 显示/隐藏图层
- 重命名图层

规则解析器也支持多步链式命令，例如：

```text
先把道路图层缓冲 50 米，再和行政区图层相交，并把结果显示在地图上
```

## 4. 为什么不用“模型直接写 Python 代码执行”

插件刻意避免让模型直接返回 Python 代码，原因有三点：

### 4.1 安全性

直接执行模型生成代码风险很高，可能导致：

- 删除图层
- 覆盖数据
- 误改属性
- 执行危险 API

### 4.2 可控性

结构化计划可以被插件校验：

- 是否在白名单内
- 参数是否合理
- 是否需要确认

### 4.3 可解释性

结构化步骤可以先展示给用户，例如：

- 第一步做缓冲
- 第二步做相交
- 第三步缩放到结果

这样比一段不可见代码更透明。

## 5. 工具注册表与白名单

插件通过 [tool_registry.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/tool_registry.py) 管理允许调用的能力。

白名单分两类：

### 5.1 Processing 算法

例如：

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

### 5.2 QGIS API 操作

例如：

- `zoom_to_layer`
- `zoom_to_all_layers`
- `set_active_layer`
- `rename_layer`
- `set_layer_visibility`
- `remove_layer`
- `open_attribute_table`
- `select_by_expression`
- `clear_selection`
- `add_vector_layer`
- `add_raster_layer`

执行前，插件会校验每一步是否属于白名单。

如果模型返回未注册工具，执行器会直接拒绝。

## 6. 图层引用解析与歧义处理

用户自然语言里经常不会给出完全精确的图层名。

例如：

- “道路”
- “道路图层”
- “road”

执行器在正式执行前会解析图层引用：

- 精确匹配
- 部分匹配
- 模糊建议

如果发现歧义，比如匹配到多个图层，插件不会直接猜，而是：

1. 在聊天消息中发出说明
2. 提供候选图层按钮
3. 用户点选其中一个
4. 插件把该选择写回当前计划
5. 继续执行

所以图层歧义确认现在已经是聊天内联交互，而不是系统弹窗。

## 7. 执行阶段

真正执行发生在 [processing_executor.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/executor/processing_executor.py)。

### 7.1 Processing 步骤

当步骤类型为 `processing` 时，插件会调用：

```python
processing.run(tool_id, params, context=context, feedback=feedback)
```

执行结果会被保存，并允许后续步骤通过：

- `{"result": "last"}`
- `{"result": "step_1.OUTPUT"}`

来引用上一步输出。

### 7.2 QGIS API 步骤

当步骤类型为 `qgis` 时，插件会调用 [qgis_api_executor.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/executor/qgis_api_executor.py) 中的封装操作。

例如：

- 缩放地图
- 设置活动图层
- 打开属性表
- 重命名图层
- 切换图层可见性

### 7.3 结果图层处理

如果 Processing 输出了新图层，插件会自动尝试：

- 识别输出是否为图层对象或图层路径
- 将结果图层加入当前工程
- 在日志中记录加入地图的图层名称

## 8. 问答模式如何工作

不是所有输入都应该触发 QGIS 操作。

例如：

- “你是什么模型？”
- “什么是土地整治？”
- “矢量和栅格有什么区别？”

这类请求会进入问答模式：

- 模型只生成 `response_text`
- `steps=[]`
- 插件不会调用执行器
- 界面明确显示：
  - 已回答问题
  - 未对图层和工程做任何操作

这解决了“问答类请求被误判为执行失败”的问题。

## 9. 聊天界面如何工作

面板界面并不是简单的文本框，而是一个消息列表系统。

主要特性：

- 用户消息与插件消息分开显示
- 状态消息单独高亮
- 错误消息单独高亮
- 最近操作可作为按钮显示
- 图层歧义选择可作为按钮显示
- `Enter` 发送
- `Shift+Enter` 换行

聊天记录通过 [settings.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/settings.py) 持久化保存，重新打开插件后仍可恢复。

## 10. 最近操作与复用命令

每次执行成功后，插件会记录：

- 时间
- 模式
- 原始命令
- 摘要

这些记录会显示在“最近操作”里，并以可点击按钮形式回填到输入框。

这样用户可以：

- 复用旧命令
- 稍微改几个词后重新执行
- 快速形成常见流程模板

## 11. 模型接入方式

当前支持：

- DeepSeek
- Gemini
- OpenAI-compatible
- Ollama

设置页支持：

- 配置地址
- 填写 API Key
- 自动获取模型列表
- 测试连通性

这部分逻辑在：

- [ui/settings_dialog.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/ui/settings_dialog.py)
- [llm/factory.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/llm/factory.py)
- [llm/openai_client.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/llm/openai_client.py)
- [llm/ollama_client.py](/Users/Administrator/Documents/新建文件夹/nl_qgis_agent/llm/ollama_client.py)

## 12. 错误分层

插件不会把所有问题都显示成“执行失败”。

当前会尽量区分为：

- 模型连接失败
- 模型返回格式异常
- 命令解析失败
- 图层歧义
- 未找到图层
- QGIS 算法执行失败

这样用户更容易判断：

- 是模型没配置好
- 还是命令写得不清楚
- 还是图层名没对上
- 还是 QGIS 算法本身报错

## 13. 当前限制

虽然插件已经可以完成问答、规划、执行、歧义确认和历史复用，但仍然有一些明确边界：

- 还不是通用 Agent，不会自动调用“全部 QGIS API”
- 执行能力仍受白名单约束
- 回退建议不是完整事务回滚
- 字段感知已加入上下文，但复杂表达式仍依赖模型理解
- 目前的状态更新是阶段式，不是网络 token 级流式输出

## 14. 一句话总结

这个插件的核心思想是：

**用聊天界面承载自然语言交互，用工程上下文提升理解准确率，用结构化计划替代代码执行，用白名单执行器安全地把语言意图转成 QGIS 操作。**
