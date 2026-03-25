from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QAction
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsMapLayerType,
    QgsPrintLayout,
    QgsProject,
    QgsRasterLayer,
    QgsRendererCategory,
    QgsSingleSymbolRenderer,
    QgsStyle,
    QgsSymbol,
    QgsVectorLayer,
    QgsWkbTypes,
)


class QgisApiExecutor:
    def __init__(self, iface, style_standards=None):
        self.iface = iface
        self.style_standards = style_standards

    def execute(self, operation: str, args: dict, resolve_value, log):
        operation = (operation or "").strip().lower()
        if operation == "zoom_to_layer":
            layer = resolve_value(args.get("layer"))
            if layer is None:
                raise ValueError("zoom_to_layer 缺少有效图层。")
            self.iface.setActiveLayer(layer)
            self.iface.mapCanvas().setExtent(layer.extent())
            self.iface.mapCanvas().refresh()
            log("已缩放到图层: {}".format(layer.name()))
            return layer

        if operation == "zoom_to_all_layers":
            self.iface.mapCanvas().zoomToFullExtent()
            self.iface.mapCanvas().refresh()
            log("已缩放到全部图层范围。")
            return None

        if operation == "set_active_layer":
            layer = resolve_value(args.get("layer"))
            if layer is None:
                raise ValueError("set_active_layer 缺少有效图层。")
            self.iface.setActiveLayer(layer)
            log("已激活图层: {}".format(layer.name()))
            return layer

        if operation == "rename_layer":
            layer = resolve_value(args.get("layer"))
            name = resolve_value(args.get("name"))
            if layer is None or not name:
                raise ValueError("rename_layer 缺少有效图层或名称。")
            old_name = layer.name()
            layer.setName(str(name))
            log("已重命名图层: {} -> {}".format(old_name, layer.name()))
            return layer

        if operation == "set_layer_visibility":
            layer = resolve_value(args.get("layer"))
            visible = bool(resolve_value(args.get("visible")))
            if layer is None:
                raise ValueError("set_layer_visibility 缺少有效图层。")
            node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
            if node is None:
                raise ValueError("图层不在图层树中: {}".format(layer.name()))
            node.setItemVisibilityChecked(visible)
            log("{}图层: {}".format("显示" if visible else "隐藏", layer.name()))
            return layer

        if operation == "set_layer_color":
            layer = resolve_value(args.get("layer"))
            color_value = resolve_value(args.get("color"))
            if layer is None or not color_value:
                raise ValueError("set_layer_color 缺少有效图层或颜色。")
            if layer.type() != QgsMapLayerType.VectorLayer:
                raise ValueError("只有矢量图层支持单色符号化。")
            symbol = self._default_symbol_for_layer(layer)
            symbol.setColor(self._parse_color(str(color_value)))
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
            layer.triggerRepaint()
            self._refresh_layer_symbology(layer)
            log("已设置图层颜色: {} -> {}".format(layer.name(), color_value))
            return layer

        if operation == "set_categorized_renderer":
            layer = resolve_value(args.get("layer"))
            field_name = resolve_value(args.get("field"))
            ramp_name = resolve_value(args.get("color_ramp")) or "Spectral"
            if layer is None or not field_name:
                raise ValueError("set_categorized_renderer 缺少有效图层或字段名。")
            if layer.type() != QgsMapLayerType.VectorLayer:
                raise ValueError("只有矢量图层支持按字段分类渲染。")
            field_index = layer.fields().indexOf(str(field_name))
            if field_index < 0:
                raise ValueError("图层“{}”中不存在字段：{}".format(layer.name(), field_name))
            unique_values = sorted(layer.uniqueValues(field_index), key=lambda value: str(value))
            if not unique_values:
                raise ValueError("字段“{}”没有可用于分类渲染的取值。".format(field_name))
            if len(unique_values) > 60:
                raise ValueError("字段“{}”的唯一值过多（{} 个），当前版本暂不自动分类渲染。".format(field_name, len(unique_values)))

            categories = []
            total = len(unique_values)
            for index, value in enumerate(unique_values):
                symbol = self._default_symbol_for_layer(layer)
                symbol.setColor(self._category_color(index, total, str(ramp_name)))
                label = "<NULL>" if value is None else str(value)
                categories.append(QgsRendererCategory(value, symbol, label))

            layer.setRenderer(QgsCategorizedSymbolRenderer(str(field_name), categories))
            layer.triggerRepaint()
            self._refresh_layer_symbology(layer)
            log("已按字段分类渲染: {} | 字段={} | 类别数={}".format(layer.name(), field_name, len(categories)))
            return layer

        if operation == "apply_style_standard":
            if self.style_standards is None:
                raise ValueError("当前未加载标准样式库。")
            layer = resolve_value(args.get("layer"))
            standard_id = resolve_value(args.get("standard_id"))
            style_set_id = resolve_value(args.get("style_set_id"))
            match_field = resolve_value(args.get("match_field"))
            if layer is None or not standard_id or not style_set_id:
                raise ValueError("apply_style_standard 缺少图层、标准或样式集参数。")
            if layer.type() != QgsMapLayerType.VectorLayer:
                raise ValueError("当前版本只有矢量图层支持标准样式应用。")
            style_set = self.style_standards.get_style_set(str(standard_id), str(style_set_id))
            if style_set is None:
                raise ValueError("未找到标准样式集: {} / {}".format(standard_id, style_set_id))

            if style_set.get("renderer") == "standard_rule" and not match_field:
                rule = self._match_single_rule_by_layer_name(layer.name(), style_set)
                if rule is not None:
                    self._apply_single_rule_style(layer, rule)
                    log("已按标准样式应用图层样式: {} | {}".format(layer.name(), rule.get("label", "")))
                    return layer

            self._apply_standard_categorized_style(layer, style_set, match_field)
            log("已按标准样式渲染: {} | 样式集={}".format(layer.name(), style_set.get("name", style_set_id)))
            return layer

        if operation == "remove_layer":
            layer = resolve_value(args.get("layer"))
            if layer is None:
                raise ValueError("remove_layer 缺少有效图层。")
            layer_name = layer.name()
            QgsProject.instance().removeMapLayer(layer.id())
            log("已移除图层: {}".format(layer_name))
            return None

        if operation == "open_attribute_table":
            layer = resolve_value(args.get("layer"))
            if layer is None:
                raise ValueError("open_attribute_table 缺少有效图层。")
            self.iface.showAttributeTable(layer)
            log("已打开属性表: {}".format(layer.name()))
            return layer

        if operation == "open_layer_properties":
            layer = resolve_value(args.get("layer"))
            if layer is None:
                raise ValueError("open_layer_properties 缺少有效图层。")
            self.iface.setActiveLayer(layer)
            self.iface.showLayerProperties(layer)
            log("已打开图层属性: {}".format(layer.name()))
            return layer

        if operation == "open_field_calculator":
            layer = resolve_value(args.get("layer"))
            if layer is None:
                raise ValueError("open_field_calculator 缺少有效图层。")
            self.iface.setActiveLayer(layer)
            self._trigger_interface_action(
                direct_getter="actionOpenFieldCalculator",
                text_keywords=("字段计算器", "Field Calculator"),
            )
            log("已打开字段计算器: {}".format(layer.name()))
            return layer

        if operation == "open_statistical_summary":
            layer = resolve_value(args.get("layer"))
            if layer is None:
                raise ValueError("open_statistical_summary 缺少有效图层。")
            self.iface.setActiveLayer(layer)
            self._trigger_interface_action(
                direct_getter="actionOpenStatisticalSummary",
                text_keywords=("统计摘要", "Statistical Summary"),
            )
            log("已打开统计摘要: {}".format(layer.name()))
            return layer

        if operation == "open_project_properties":
            self._trigger_interface_action(
                direct_getter="actionProjectProperties",
                text_keywords=("工程属性", "项目属性", "Project Properties"),
            )
            log("已打开工程属性。")
            return None

        if operation == "show_layout_manager":
            if hasattr(self.iface, "showLayoutManager"):
                self.iface.showLayoutManager()
            else:
                self._trigger_interface_action(
                    direct_getter="actionShowLayoutManager",
                    text_keywords=("布局管理器", "Layout Manager"),
                )
            log("已打开布局管理器。")
            return None

        if operation == "create_print_layout":
            self._trigger_interface_action(
                direct_getter="actionCreatePrintLayout",
                text_keywords=("新建打印布局", "New Print Layout"),
            )
            log("已打开新建布局界面。")
            return None

        if operation == "open_layout_designer":
            layout_name = resolve_value(args.get("name"))
            if layout_name:
                layout = QgsProject.instance().layoutManager().layoutByName(str(layout_name))
                if isinstance(layout, QgsPrintLayout):
                    self.iface.openLayoutDesigner(layout)
                    log("已打开布局设计器: {}".format(layout_name))
                    return layout
            self._trigger_interface_action(
                direct_getter="actionCreatePrintLayout",
                text_keywords=("布局设计器", "Layout Designer", "新建打印布局"),
            )
            log("已打开布局设计器或新建布局入口。")
            return None

        if operation == "open_python_console":
            self._trigger_interface_action(
                direct_getter="actionShowPythonDialog",
                text_keywords=("Python 控制台", "Python Console"),
            )
            log("已打开 Python 控制台。")
            return None

        if operation == "open_processing_toolbox":
            self._trigger_interface_action(
                text_keywords=("Processing Toolbox", "处理工具箱", "工具箱"),
            )
            log("已打开处理工具箱。")
            return None

        if operation == "open_model_builder":
            self._trigger_interface_action(
                text_keywords=("Graphical Modeler", "Model Designer", "模型构建器", "模型设计器"),
            )
            log("已尝试打开模型构建器。")
            return None

        if operation == "open_script_editor":
            self._trigger_interface_action(
                text_keywords=("Script Editor", "脚本编辑器", "New Script", "新建脚本"),
            )
            log("已尝试打开脚本编辑器。")
            return None

        if operation == "select_by_expression":
            layer = resolve_value(args.get("layer"))
            expression = resolve_value(args.get("expression"))
            if layer is None or not expression:
                raise ValueError("select_by_expression 缺少有效图层或表达式。")
            if layer.type() != QgsMapLayerType.VectorLayer:
                raise ValueError("只有矢量图层支持按表达式选择。")
            layer.selectByExpression(str(expression))
            log("已按表达式选择要素: {} | {}".format(layer.name(), expression))
            return layer

        if operation == "clear_selection":
            layer = resolve_value(args.get("layer"))
            if layer is None:
                raise ValueError("clear_selection 缺少有效图层。")
            if layer.type() != QgsMapLayerType.VectorLayer:
                raise ValueError("只有矢量图层支持清除选择。")
            layer.removeSelection()
            log("已清除选择: {}".format(layer.name()))
            return layer

        if operation == "add_vector_layer":
            path = resolve_value(args.get("path"))
            name = resolve_value(args.get("name")) or "Imported Layer"
            layer = QgsVectorLayer(path, name, "ogr")
            if not layer.isValid():
                raise ValueError("无法加载矢量图层: {}".format(path))
            QgsProject.instance().addMapLayer(layer)
            log("已加载矢量图层: {}".format(layer.name()))
            return layer

        if operation == "add_raster_layer":
            path = resolve_value(args.get("path"))
            name = resolve_value(args.get("name")) or "Imported Raster"
            layer = QgsRasterLayer(path, name)
            if not layer.isValid():
                raise ValueError("无法加载栅格图层: {}".format(path))
            QgsProject.instance().addMapLayer(layer)
            log("已加载栅格图层: {}".format(layer.name()))
            return layer

        raise ValueError("暂不支持的 QGIS 操作: {}".format(operation))

    def _trigger_interface_action(self, direct_getter: str = "", text_keywords=()):
        if direct_getter and hasattr(self.iface, direct_getter):
            action = getattr(self.iface, direct_getter)()
            if isinstance(action, QAction):
                action.trigger()
                return

        keywords = [keyword.lower() for keyword in text_keywords]
        for action in self.iface.mainWindow().findChildren(QAction):
            text = (action.text() or "").lower()
            object_name = (action.objectName() or "").lower()
            if any(keyword in text or keyword in object_name for keyword in keywords):
                action.trigger()
                return

        raise ValueError("未找到可触发的界面入口: {}".format(", ".join(text_keywords)))

    def _default_symbol_for_layer(self, layer):
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        if symbol is None:
            raise ValueError("当前图层类型暂不支持自动符号化。")
        return symbol

    def _parse_color(self, color_value: str):
        text = (color_value or "").strip()
        color_map = {
            "红": "#e53935",
            "红色": "#e53935",
            "蓝": "#1e88e5",
            "蓝色": "#1e88e5",
            "绿": "#43a047",
            "绿色": "#43a047",
            "黄": "#fdd835",
            "黄色": "#fdd835",
            "橙": "#fb8c00",
            "橙色": "#fb8c00",
            "紫": "#8e24aa",
            "紫色": "#8e24aa",
            "黑": "#212121",
            "黑色": "#212121",
            "白": "#fafafa",
            "白色": "#fafafa",
            "灰": "#757575",
            "灰色": "#757575",
        }
        normalized = color_map.get(text.lower(), color_map.get(text, text))
        color = QColor(normalized)
        if not color.isValid():
            raise ValueError("无法识别颜色值: {}".format(color_value))
        return color

    def _category_color(self, index: int, total: int, ramp_name: str):
        style = QgsStyle.defaultStyle()
        ramp = style.colorRamp(ramp_name) if style is not None else None
        if ramp is not None and total > 1:
            return ramp.color(float(index) / float(total - 1))
        if ramp is not None:
            return ramp.color(0.5)
        hue = int((index * 360.0) / max(total, 1)) % 360
        return QColor.fromHsv(hue, 160, 220)

    def _refresh_layer_symbology(self, layer):
        if hasattr(self.iface, "layerTreeView") and self.iface.layerTreeView() is not None:
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())
        self.iface.mapCanvas().refresh()

    def _apply_standard_categorized_style(self, layer, style_set: dict, match_field):
        rules = style_set.get("rules", [])
        if not rules:
            raise ValueError("标准样式集中没有规则。")
        field_name = str(match_field or "").strip() or self._infer_match_field(layer, rules)
        if not field_name:
            raise ValueError("未能自动识别匹配字段，请在命令中明确指定字段。")
        field_index = layer.fields().indexOf(field_name)
        if field_index < 0:
            raise ValueError("图层“{}”中不存在字段：{}".format(layer.name(), field_name))

        rule_map = {}
        for rule in rules:
            tokens = [rule.get("label", "")]
            tokens.extend(rule.get("aliases", []))
            for token in tokens:
                normalized = self._normalize_label(token)
                if normalized:
                    rule_map[normalized] = rule

        unique_values = sorted(layer.uniqueValues(field_index), key=lambda value: str(value))
        categories = []
        for value in unique_values:
            normalized = self._normalize_label("<NULL>" if value is None else str(value))
            rule = rule_map.get(normalized)
            symbol = self._default_symbol_for_layer(layer)
            if rule is not None:
                self._apply_rule_to_symbol(symbol, rule, layer.geometryType())
            else:
                symbol.setColor(QColor("#d9d9d9"))
            label = "<NULL>" if value is None else str(value)
            categories.append(QgsRendererCategory(value, symbol, label))

        layer.setRenderer(QgsCategorizedSymbolRenderer(field_name, categories))
        layer.triggerRepaint()
        self._refresh_layer_symbology(layer)

    def _apply_single_rule_style(self, layer, rule: dict):
        symbol = self._default_symbol_for_layer(layer)
        self._apply_rule_to_symbol(symbol, rule, layer.geometryType())
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        layer.triggerRepaint()
        self._refresh_layer_symbology(layer)

    def _apply_rule_to_symbol(self, symbol, rule: dict, geometry_type):
        fill_color = rule.get("fill_color")
        stroke_color = rule.get("stroke_color")
        line_style = rule.get("line_style", "solid")

        if fill_color:
            fill = self._parse_color(fill_color)
            symbol.setColor(fill)
        for symbol_layer in symbol.symbolLayers():
            if fill_color and hasattr(symbol_layer, "setFillColor"):
                symbol_layer.setFillColor(self._parse_color(fill_color))
            if fill_color and hasattr(symbol_layer, "setColor"):
                symbol_layer.setColor(self._parse_color(fill_color))
            if stroke_color and hasattr(symbol_layer, "setStrokeColor"):
                symbol_layer.setStrokeColor(self._parse_color(stroke_color))
            if stroke_color and hasattr(symbol_layer, "setColor") and geometry_type == QgsWkbTypes.LineGeometry:
                symbol_layer.setColor(self._parse_color(stroke_color))
            if hasattr(symbol_layer, "setPenStyle"):
                symbol_layer.setPenStyle(self._pen_style(line_style))

    def _infer_match_field(self, layer, rules: list):
        expected = {self._normalize_label(rule.get("label", "")) for rule in rules if rule.get("label")}
        best_field = ""
        best_score = 0
        for field in layer.fields():
            field_index = layer.fields().indexOf(field.name())
            try:
                values = {self._normalize_label("<NULL>" if value is None else str(value)) for value in layer.uniqueValues(field_index)}
            except Exception:
                continue
            score = len(expected & values)
            if score > best_score:
                best_score = score
                best_field = field.name()
        return best_field if best_score > 0 else ""

    def _match_single_rule_by_layer_name(self, layer_name: str, style_set: dict):
        normalized = self._normalize_label(layer_name)
        for rule in style_set.get("rules", []):
            tokens = [rule.get("label", "")]
            tokens.extend(rule.get("aliases", []))
            for token in tokens:
                label = self._normalize_label(token)
                if label and (label in normalized or normalized in label):
                    return rule
        return None

    def _normalize_label(self, value: str):
        return (value or "").strip().lower().replace("（", "(").replace("）", ")").replace(" ", "")

    def _pen_style(self, style_name: str):
        mapping = {
            "solid": Qt.SolidLine,
            "dash": Qt.DashLine,
            "dot": Qt.DotLine,
        }
        return mapping.get((style_name or "solid").strip().lower(), Qt.SolidLine)
