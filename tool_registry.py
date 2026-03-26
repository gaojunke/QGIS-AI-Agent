from dataclasses import dataclass, field

from .i18n import choose


@dataclass(frozen=True)
class ToolDefinition:
    kind: str
    id: str
    label: str
    description: str
    aliases: tuple = field(default_factory=tuple)
    requires_confirmation: bool = False


class ToolRegistry:
    def __init__(self):
        self._processing_tools = {
            "native:intersection": ToolDefinition(
                kind="processing",
                id="native:intersection",
                label="相交",
                description="对两个矢量图层做相交分析。",
                aliases=("相交", "交集", "intersection", "intersect"),
            ),
            "native:clip": ToolDefinition(
                kind="processing",
                id="native:clip",
                label="裁剪",
                description="用覆盖图层裁剪输入图层。",
                aliases=("裁剪", "clip"),
            ),
            "native:buffer": ToolDefinition(
                kind="processing",
                id="native:buffer",
                label="缓冲区",
                description="对矢量图层生成缓冲区。",
                aliases=("缓冲", "buffer"),
            ),
            "native:dissolve": ToolDefinition(
                kind="processing",
                id="native:dissolve",
                label="溶解",
                description="对矢量图层做溶解。",
                aliases=("溶解", "融合", "dissolve"),
            ),
            "native:difference": ToolDefinition(
                kind="processing",
                id="native:difference",
                label="差异",
                description="从输入图层中擦除覆盖图层部分。",
                aliases=("擦除", "差异", "difference", "erase"),
            ),
            "native:union": ToolDefinition(
                kind="processing",
                id="native:union",
                label="联合",
                description="对两个矢量图层做联合分析。",
                aliases=("联合", "union"),
            ),
            "native:mergevectorlayers": ToolDefinition(
                kind="processing",
                id="native:mergevectorlayers",
                label="合并矢量图层",
                description="把多个矢量图层合并为一个图层。",
                aliases=("合并", "merge"),
            ),
            "native:reprojectlayer": ToolDefinition(
                kind="processing",
                id="native:reprojectlayer",
                label="重投影",
                description="将图层重投影到指定坐标系。",
                aliases=("重投影", "投影到", "reproject"),
            ),
            "native:multiparttosingleparts": ToolDefinition(
                kind="processing",
                id="native:multiparttosingleparts",
                label="多部件转单部件",
                description="将多部件要素拆分成单部件要素。",
                aliases=("多部件转单部件", "拆分多部件", "singleparts"),
            ),
            "native:fixgeometries": ToolDefinition(
                kind="processing",
                id="native:fixgeometries",
                label="修复几何",
                description="修复图层中的无效几何。",
                aliases=("修复几何", "修复拓扑", "fix geometries"),
            ),
            "native:extractbyexpression": ToolDefinition(
                kind="processing",
                id="native:extractbyexpression",
                label="按表达式提取",
                description="按表达式过滤要素并输出新图层。",
                aliases=("按表达式提取", "筛选", "过滤", "extract"),
            ),
            "native:fieldcalculator": ToolDefinition(
                kind="processing",
                id="native:fieldcalculator",
                label="字段计算器",
                description="通过表达式计算字段值，可用于面积、长度等几何属性计算。",
                aliases=("字段计算", "算面积", "计算面积", "field calculator", "area"),
            ),
        }
        self._qgis_operations = {
            "zoom_to_layer": ToolDefinition(
                kind="qgis",
                id="zoom_to_layer",
                label="缩放到图层",
                description="将地图视图缩放到指定图层。",
                aliases=("缩放到", "定位到", "zoom to"),
            ),
            "zoom_to_all_layers": ToolDefinition(
                kind="qgis",
                id="zoom_to_all_layers",
                label="缩放到全部图层",
                description="将地图视图缩放到全部图层范围。",
                aliases=("缩放到全部", "全图", "zoom full"),
            ),
            "set_active_layer": ToolDefinition(
                kind="qgis",
                id="set_active_layer",
                label="激活图层",
                description="将指定图层设为当前活动图层。",
                aliases=("激活图层", "设为当前图层", "set active layer"),
            ),
            "rename_layer": ToolDefinition(
                kind="qgis",
                id="rename_layer",
                label="重命名图层",
                description="重命名指定图层。",
                aliases=("重命名", "命名为", "rename"),
            ),
            "set_layer_visibility": ToolDefinition(
                kind="qgis",
                id="set_layer_visibility",
                label="设置图层可见性",
                description="显示或隐藏指定图层。",
                aliases=("显示图层", "隐藏图层", "显示", "隐藏"),
            ),
            "set_layer_color": ToolDefinition(
                kind="qgis",
                id="set_layer_color",
                label="设置图层颜色",
                description="将矢量图层设置为单一颜色符号。",
                aliases=("符号化", "改颜色", "设成红色", "单色渲染", "设置颜色"),
            ),
            "set_categorized_renderer": ToolDefinition(
                kind="qgis",
                id="set_categorized_renderer",
                label="按字段分类渲染",
                description="按指定字段为矢量图层生成分类符号。",
                aliases=("分类渲染", "分类符号化", "按字段渲染", "按字段分类"),
            ),
            "apply_style_standard": ToolDefinition(
                kind="qgis",
                id="apply_style_standard",
                label="按标准样式渲染",
                description="按内置标准样式包为图层应用规程配色。",
                aliases=("按标准渲染", "按规程渲染", "附录B", "附录C", "附录D", "标准配色"),
            ),
            "remove_layer": ToolDefinition(
                kind="qgis",
                id="remove_layer",
                label="删除图层",
                description="从当前工程移除指定图层。",
                aliases=("删除图层", "移除图层", "remove layer", "delete layer"),
                requires_confirmation=True,
            ),
            "open_attribute_table": ToolDefinition(
                kind="qgis",
                id="open_attribute_table",
                label="打开属性表",
                description="打开指定图层的属性表。",
                aliases=("打开属性表", "属性表", "open attribute table"),
            ),
            "open_layer_properties": ToolDefinition(
                kind="qgis",
                id="open_layer_properties",
                label="打开图层属性",
                description="打开指定图层的图层属性窗口。",
                aliases=("图层属性", "打开图层属性", "layer properties"),
            ),
            "open_field_calculator": ToolDefinition(
                kind="qgis",
                id="open_field_calculator",
                label="打开字段计算器",
                description="打开当前图层的字段计算器。",
                aliases=("字段计算器", "打开字段计算器", "field calculator"),
            ),
            "open_statistical_summary": ToolDefinition(
                kind="qgis",
                id="open_statistical_summary",
                label="打开统计摘要",
                description="打开当前图层的统计摘要面板。",
                aliases=("统计摘要", "统计信息", "statistical summary"),
            ),
            "open_project_properties": ToolDefinition(
                kind="qgis",
                id="open_project_properties",
                label="打开工程属性",
                description="打开工程属性对话框。",
                aliases=("工程属性", "项目属性", "project properties"),
            ),
            "show_layout_manager": ToolDefinition(
                kind="qgis",
                id="show_layout_manager",
                label="打开布局管理器",
                description="打开 QGIS 布局管理器。",
                aliases=("布局管理器", "打开布局管理器", "layout manager"),
            ),
            "create_print_layout": ToolDefinition(
                kind="qgis",
                id="create_print_layout",
                label="新建布局",
                description="打开新建打印布局界面。",
                aliases=("新建布局", "创建布局", "print layout"),
            ),
            "open_layout_designer": ToolDefinition(
                kind="qgis",
                id="open_layout_designer",
                label="打开布局设计器",
                description="打开指定布局设计器，或打开新建布局流程。",
                aliases=("布局设计器", "打开布局设计器", "layout designer"),
            ),
            "open_python_console": ToolDefinition(
                kind="qgis",
                id="open_python_console",
                label="打开 Python 控制台",
                description="打开 QGIS Python 控制台。",
                aliases=("python控制台", "pyqgis", "qpython", "python console"),
            ),
            "open_processing_toolbox": ToolDefinition(
                kind="qgis",
                id="open_processing_toolbox",
                label="打开处理工具箱",
                description="打开 QGIS Processing Toolbox。",
                aliases=("处理工具箱", "processing toolbox", "算法工具箱"),
            ),
            "open_model_builder": ToolDefinition(
                kind="qgis",
                id="open_model_builder",
                label="打开模型构建器",
                description="打开 QGIS Processing 图形模型构建器。",
                aliases=("模型构建器", "模型设计器", "graphical modeler", "model builder"),
            ),
            "open_script_editor": ToolDefinition(
                kind="qgis",
                id="open_script_editor",
                label="打开脚本编辑器",
                description="打开 Processing 脚本编辑器或 Python 编辑界面。",
                aliases=("脚本编辑器", "python编辑器", "编辑python", "script editor"),
            ),
            "select_by_expression": ToolDefinition(
                kind="qgis",
                id="select_by_expression",
                label="按表达式选择",
                description="在矢量图层上按表达式选择要素。",
                aliases=("按表达式选择", "选择要素", "select by expression"),
            ),
            "clear_selection": ToolDefinition(
                kind="qgis",
                id="clear_selection",
                label="清除选择",
                description="清除图层当前选择。",
                aliases=("清除选择", "取消选择", "clear selection"),
            ),
            "add_vector_layer": ToolDefinition(
                kind="qgis",
                id="add_vector_layer",
                label="加载矢量图层",
                description="从文件路径加载矢量图层。",
                aliases=("加载矢量", "打开矢量", "add vector layer"),
            ),
            "add_raster_layer": ToolDefinition(
                kind="qgis",
                id="add_raster_layer",
                label="加载栅格图层",
                description="从文件路径加载栅格图层。",
                aliases=("加载栅格", "打开栅格", "add raster layer"),
            ),
        }

    def processing_definition(self, tool_id: str):
        return self._processing_tools.get((tool_id or "").strip())

    def qgis_definition(self, operation: str):
        return self._qgis_operations.get((operation or "").strip())

    def allowed_processing_ids(self):
        return tuple(self._processing_tools.keys())

    def allowed_qgis_operations(self):
        return tuple(self._qgis_operations.keys())

    def validate_step(self, step, allow_dynamic_processing: bool = False):
        if step.kind == "processing":
            tool = self.processing_definition(step.tool_id)
            if tool is not None:
                return tool
            dynamic_tool = self._dynamic_processing_definition(step.tool_id) if allow_dynamic_processing else None
            if dynamic_tool is not None:
                return dynamic_tool
            if not allow_dynamic_processing:
                raise ValueError(choose("该 Processing 算法未在插件白名单内: {}", "This Processing algorithm is not in the plugin allowlist: {}").format(step.tool_id))
            raise ValueError(choose("当前 QGIS 中未找到 Processing 算法: {}", "The Processing algorithm was not found in the current QGIS environment: {}").format(step.tool_id))

        if step.kind == "qgis":
            tool = self.qgis_definition(step.operation)
            if tool is None:
                raise ValueError(choose("不在白名单中的 QGIS 操作: {}", "This QGIS operation is not in the allowlist: {}").format(step.operation))
            return tool

        raise ValueError(choose("未知步骤类型: {}", "Unknown step type: {}").format(step.kind))

    def enforce_on_plan(self, plan, allow_dynamic_processing: bool = False):
        requires_confirmation = bool(plan.requires_confirmation)
        for step in plan.steps:
            tool = self.validate_step(step, allow_dynamic_processing=allow_dynamic_processing)
            if tool.requires_confirmation:
                requires_confirmation = True
        plan.requires_confirmation = requires_confirmation
        return plan

    def prompt_catalog_text(self, allow_dynamic_processing: bool = False) -> str:
        lines = ["允许使用的工具白名单:"]
        lines.append("Processing:")
        for tool in self._processing_tools.values():
            lines.append("- {}: {} | aliases={}".format(tool.id, tool.description, ", ".join(tool.aliases)))
        if allow_dynamic_processing:
            lines.append("- 已开启高级模式：另外允许当前 QGIS 已安装的其他合法 Processing 算法，只要 tool_id 在运行环境中真实存在。")
        lines.append("QGIS:")
        for tool in self._qgis_operations.values():
            lines.append("- {}: {} | aliases={}".format(tool.id, tool.description, ", ".join(tool.aliases)))
        return "\n".join(lines)

    def _dynamic_processing_definition(self, tool_id: str):
        tool_id = (tool_id or "").strip()
        if not tool_id:
            return None
        try:
            from qgis.core import QgsApplication
        except Exception:
            return None

        registry = QgsApplication.processingRegistry()
        algorithm = registry.algorithmById(tool_id) if registry is not None else None
        if algorithm is None:
            return None
        return ToolDefinition(
            kind="processing",
            id=tool_id,
            label=algorithm.displayName() or tool_id,
            description=algorithm.shortDescription() or "当前 QGIS 已安装的 Processing 算法。",
            aliases=(),
        )
