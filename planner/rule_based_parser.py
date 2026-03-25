import re

from .schema import ActionPlan, PlanStep


class RuleBasedPlanner:
    def __init__(self, registry, style_standards=None):
        self.registry = registry
        self.style_standards = style_standards

    def parse(self, command_text: str, project_context: dict, request_mode: str = "auto"):
        text = self._normalize_text(command_text)
        if not text:
            return None

        if request_mode == "qa" or (request_mode == "auto" and self._is_question(text)):
            return ActionPlan(
                summary="问答请求，无需执行 QGIS 操作。",
                requires_confirmation=False,
                steps=[],
                response_text="这是一个问答型请求。当前未对图层和工程做任何操作。若需获得更完整的专业回答，请确保已正确配置可用的大模型。",
                notes=["本回复由规则解析器生成。"],
                source="rule-based",
            )

        clauses = self._split_clauses(text)
        steps = []
        notes = []
        has_result = False

        for clause in clauses:
            parsed_steps = self._parse_clause(clause, project_context, has_result)
            if parsed_steps:
                steps.extend(parsed_steps)
                has_result = self._clause_produces_result(parsed_steps)
            else:
                notes.append("未完全解析子命令: {}".format(clause))

        if not steps:
            return None

        return ActionPlan(
            summary="按顺序执行 {} 个步骤。".format(len(steps)),
            requires_confirmation=False,
            steps=steps,
            notes=["本计划由规则解析器生成。"] + notes,
            source="rule-based",
        )

    def _parse_clause(self, clause: str, project_context: dict, has_result: bool):
        layers = project_context.get("layers") or []
        matched_layers = self._match_layers(clause, layers)
        standard = self.style_standards.find_standard(clause) if self.style_standards is not None else None
        style_set = self.style_standards.find_style_set(standard.get("standard_id", ""), clause) if standard is not None else None
        if standard is None and self.style_standards is not None:
            standard, style_set = self.style_standards.find_style_set_global(clause)
        if standard is not None and style_set is None:
            style_set = self._infer_standard_style_set(clause, standard)

        if standard is not None and style_set is not None and self._contains_any(clause, ["标准", "规程", "附录", "渲染", "配色", "符号化"]):
            target = self._single_target(matched_layers, has_result)
            if target is None:
                return None
            match_field = self._extract_context_field_name(clause, matched_layers)
            return [
                PlanStep(
                    kind="qgis",
                    label="按标准样式渲染",
                    operation="apply_style_standard",
                    args={
                        "layer": target,
                        "standard_id": standard.get("standard_id", ""),
                        "style_set_id": style_set.get("id", ""),
                        "match_field": match_field or "",
                    },
                )
            ]

        if self._contains_any(clause, ["分类渲染", "分类符号化", "按字段渲染", "按字段分类"]):
            target = self._single_target(matched_layers, has_result)
            field_name = self._extract_context_field_name(clause, matched_layers)
            if target is None or not field_name:
                return None
            return [
                PlanStep(
                    kind="qgis",
                    label="按字段分类渲染",
                    operation="set_categorized_renderer",
                    args={
                        "layer": target,
                        "field": field_name,
                        "color_ramp": self._extract_color_ramp(clause) or "Spectral",
                    },
                )
            ]

        if self._contains_any(clause, ["符号化", "渲染", "颜色", "设成", "改成"]) and not self._contains_any(
            clause, ["分类渲染", "分类符号化", "按字段渲染", "按字段分类"]
        ):
            target = self._single_target(matched_layers, has_result)
            color_value = self._extract_color(clause)
            if target is not None and color_value:
                return [
                    PlanStep(
                        kind="qgis",
                        label="设置图层颜色",
                        operation="set_layer_color",
                        args={"layer": target, "color": color_value},
                    )
                ]

        if self._contains_any(clause, ["缩放到全部", "全图", "zoom full"]):
            return [PlanStep(kind="qgis", label="缩放到全部图层", operation="zoom_to_all_layers", args={})]

        if self._contains_any(clause, ["布局管理器", "打开布局管理器", "layout manager"]):
            return [PlanStep(kind="qgis", label="打开布局管理器", operation="show_layout_manager", args={})]

        if self._contains_any(clause, ["新建布局", "创建布局", "打印布局", "print layout"]):
            return [PlanStep(kind="qgis", label="新建布局", operation="create_print_layout", args={})]

        if self._contains_any(clause, ["布局设计器", "打开布局", "layout designer"]):
            layout_name = self._extract_layout_name(clause)
            return [
                PlanStep(
                    kind="qgis",
                    label="打开布局设计器",
                    operation="open_layout_designer",
                    args={"name": layout_name} if layout_name else {},
                )
            ]

        if self._contains_any(clause, ["python控制台", "python 控制台", "pyqgis", "qpython", "python console"]):
            return [PlanStep(kind="qgis", label="打开 Python 控制台", operation="open_python_console", args={})]

        if self._contains_any(clause, ["处理工具箱", "算法工具箱", "processing toolbox"]):
            return [PlanStep(kind="qgis", label="打开处理工具箱", operation="open_processing_toolbox", args={})]

        if self._contains_any(clause, ["模型构建器", "模型设计器", "graphical modeler", "model builder"]):
            return [PlanStep(kind="qgis", label="打开模型构建器", operation="open_model_builder", args={})]

        if self._contains_any(clause, ["脚本编辑器", "python编辑器", "python 编辑器", "编辑python", "script editor"]):
            return [PlanStep(kind="qgis", label="打开脚本编辑器", operation="open_script_editor", args={})]

        if self._contains_any(clause, ["工程属性", "项目属性", "project properties"]):
            return [PlanStep(kind="qgis", label="打开工程属性", operation="open_project_properties", args={})]

        binary_specs = [
            ("native:intersection", "相交", ["相交", "交集", "intersection", "intersect"]),
            ("native:clip", "裁剪", ["裁剪", "clip"]),
            ("native:difference", "擦除", ["擦除", "差异", "difference", "erase"]),
            ("native:union", "联合", ["联合", "union"]),
        ]
        for tool_id, label, aliases in binary_specs:
            if self._contains_any(clause, aliases):
                refs = self._binary_targets(matched_layers, has_result)
                if refs is None:
                    return None
                return [
                    PlanStep(
                        kind="processing",
                        label=label,
                        tool_id=tool_id,
                        params={
                            "INPUT": refs[0],
                            "OVERLAY": refs[1],
                            "OUTPUT": "TEMPORARY_OUTPUT",
                        },
                    )
                ]

        if self._contains_any(clause, ["合并", "merge"]):
            refs = self._multi_targets(matched_layers, has_result)
            if len(refs) < 2:
                return None
            return [
                PlanStep(
                    kind="processing",
                    label="合并图层",
                    tool_id="native:mergevectorlayers",
                    params={
                        "LAYERS": refs,
                        "CRS": None,
                        "OUTPUT": "TEMPORARY_OUTPUT",
                    },
                )
            ]

        if self._contains_any(clause, ["缓冲", "buffer"]):
            target = self._single_target(matched_layers, has_result)
            if target is None:
                return None
            distance = self._extract_distance(clause)
            return [
                PlanStep(
                    kind="processing",
                    label="缓冲区",
                    tool_id="native:buffer",
                    params={
                        "INPUT": target,
                        "DISTANCE": distance,
                        "SEGMENTS": 5,
                        "END_CAP_STYLE": 0,
                        "JOIN_STYLE": 0,
                        "MITER_LIMIT": 2,
                        "DISSOLVE": False,
                        "OUTPUT": "TEMPORARY_OUTPUT",
                    },
                )
            ]

        if self._contains_any(clause, ["溶解", "融合", "dissolve"]):
            target = self._single_target(matched_layers, has_result)
            if target is None:
                return None
            return [
                PlanStep(
                    kind="processing",
                    label="溶解",
                    tool_id="native:dissolve",
                    params={
                        "INPUT": target,
                        "FIELD": [],
                        "SEPARATE_DISJOINT": False,
                        "OUTPUT": "TEMPORARY_OUTPUT",
                    },
                )
            ]

        if self._contains_any(clause, ["修复几何", "修复拓扑", "fix geometries"]):
            target = self._single_target(matched_layers, has_result)
            if target is None:
                return None
            return [
                PlanStep(
                    kind="processing",
                    label="修复几何",
                    tool_id="native:fixgeometries",
                    params={"INPUT": target, "OUTPUT": "TEMPORARY_OUTPUT"},
                )
            ]

        if self._contains_any(clause, ["多部件转单部件", "拆分多部件", "singleparts"]):
            target = self._single_target(matched_layers, has_result)
            if target is None:
                return None
            return [
                PlanStep(
                    kind="processing",
                    label="多部件转单部件",
                    tool_id="native:multiparttosingleparts",
                    params={"INPUT": target, "OUTPUT": "TEMPORARY_OUTPUT"},
                )
            ]

        if self._contains_any(clause, ["重投影", "投影到", "reproject"]):
            target = self._single_target(matched_layers, has_result)
            target_crs = self._extract_crs(clause)
            if target is None or target_crs is None:
                return None
            return [
                PlanStep(
                    kind="processing",
                    label="重投影",
                    tool_id="native:reprojectlayer",
                    params={"INPUT": target, "TARGET_CRS": target_crs, "OUTPUT": "TEMPORARY_OUTPUT"},
                )
            ]

        if self._contains_any(clause, ["按表达式提取", "筛选", "过滤", "extract"]):
            target = self._single_target(matched_layers, has_result)
            expression = self._extract_expression(clause)
            if target is None or not expression:
                return None
            return [
                PlanStep(
                    kind="processing",
                    label="按表达式提取",
                    tool_id="native:extractbyexpression",
                    params={
                        "INPUT": target,
                        "EXPRESSION": expression,
                        "OUTPUT": "TEMPORARY_OUTPUT",
                    },
                )
            ]

        if self._contains_any(clause, ["算面积", "计算面积", "面积字段", "添加面积", "保存到字段", "写入字段"]):
            target = self._single_target(matched_layers, has_result)
            if target is None:
                return None
            field_name = self._extract_field_name(clause, default_name="area")
            return [
                PlanStep(
                    kind="processing",
                    label="计算面积",
                    tool_id="native:fieldcalculator",
                    params={
                        "INPUT": target,
                        "FIELD_NAME": field_name,
                        "FIELD_TYPE": 0,
                        "FIELD_LENGTH": 20,
                        "FIELD_PRECISION": 6,
                        "FORMULA": "$area",
                        "OUTPUT": "TEMPORARY_OUTPUT",
                    },
                )
            ]

        if self._contains_any(clause, ["选择", "select by expression"]) and not self._contains_any(clause, ["清除选择"]):
            target = self._single_target(matched_layers, has_result)
            expression = self._extract_expression(clause)
            if target is None or not expression:
                return None
            return [
                PlanStep(
                    kind="qgis",
                    label="按表达式选择",
                    operation="select_by_expression",
                    args={
                        "layer": target,
                        "expression": expression,
                        "mode": "set",
                    },
                )
            ]

        if self._contains_any(clause, ["清除选择", "取消选择", "clear selection"]):
            target = self._single_target(matched_layers, has_result)
            if target is None:
                return None
            return [PlanStep(kind="qgis", label="清除选择", operation="clear_selection", args={"layer": target})]

        if self._contains_any(clause, ["打开属性表", "属性表", "open attribute table"]):
            target = self._single_target(matched_layers, has_result)
            if target is None:
                return None
            return [PlanStep(kind="qgis", label="打开属性表", operation="open_attribute_table", args={"layer": target})]

        if self._contains_any(clause, ["图层属性", "打开图层属性", "layer properties"]):
            target = self._single_target(matched_layers, has_result)
            if target is None:
                return None
            return [PlanStep(kind="qgis", label="打开图层属性", operation="open_layer_properties", args={"layer": target})]

        if self._contains_any(clause, ["字段计算器", "打开字段计算器", "field calculator"]):
            target = self._single_target(matched_layers, has_result)
            if target is None:
                return None
            return [PlanStep(kind="qgis", label="打开字段计算器", operation="open_field_calculator", args={"layer": target})]

        if self._contains_any(clause, ["统计摘要", "统计信息", "statistical summary"]):
            target = self._single_target(matched_layers, has_result)
            if target is None:
                return None
            return [PlanStep(kind="qgis", label="打开统计摘要", operation="open_statistical_summary", args={"layer": target})]

        if self._contains_any(clause, ["激活图层", "设为当前图层", "set active layer"]):
            target = self._single_target(matched_layers, has_result)
            if target is None:
                return None
            return [PlanStep(kind="qgis", label="激活图层", operation="set_active_layer", args={"layer": target})]

        if self._contains_any(clause, ["删除图层", "移除图层", "remove layer", "delete layer"]):
            target = self._single_target(matched_layers, has_result)
            if target is None:
                return None
            return [PlanStep(kind="qgis", label="删除图层", operation="remove_layer", args={"layer": target})]

        if self._contains_any(clause, ["缩放到", "定位到", "显示在地图上", "展示在地图上", "zoom to"]):
            target = self._single_target(matched_layers, has_result)
            if target is None:
                return None
            return [PlanStep(kind="qgis", label="缩放到图层", operation="zoom_to_layer", args={"layer": target})]

        visibility = self._extract_visibility(clause)
        if visibility is not None:
            target = self._single_target(matched_layers, has_result)
            if target is None:
                return None
            return [
                PlanStep(
                    kind="qgis",
                    label="设置图层可见性",
                    operation="set_layer_visibility",
                    args={"layer": target, "visible": visibility},
                )
            ]

        if self._contains_any(clause, ["重命名", "命名为", "rename"]):
            target = self._single_target(matched_layers, has_result)
            new_name = self._extract_new_name(clause)
            if target is None or not new_name:
                return None
            return [
                PlanStep(
                    kind="qgis",
                    label="重命名图层",
                    operation="rename_layer",
                    args={"layer": target, "name": new_name},
                )
            ]

        file_path = self._extract_path(clause)
        if file_path and self._contains_any(clause, ["加载矢量", "打开矢量", "shp", ".geojson", ".gpkg"]):
            return [
                PlanStep(
                    kind="qgis",
                    label="加载矢量图层",
                    operation="add_vector_layer",
                    args={"path": file_path, "name": self._extract_new_name(clause)},
                )
            ]
        if file_path and self._contains_any(clause, ["加载栅格", "打开栅格", ".tif", ".tiff", ".img"]):
            return [
                PlanStep(
                    kind="qgis",
                    label="加载栅格图层",
                    operation="add_raster_layer",
                    args={"path": file_path, "name": self._extract_new_name(clause)},
                )
            ]

        return None

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip())

    def _split_clauses(self, text: str):
        parts = re.split(r"\s*(?:然后|再|接着|随后|下一步|接下来|并把结果|并将结果)\s*", text)
        clauses = [part.strip(" ，,。；;") for part in parts if part.strip(" ，,。；;")]
        return clauses or [text]

    def _clause_produces_result(self, steps):
        for step in steps:
            if step.kind == "processing":
                return True
            if step.operation in {"add_vector_layer", "add_raster_layer", "rename_layer"}:
                return True
        return False

    def _single_target(self, matched_layers: list, has_result: bool):
        if matched_layers:
            return {"layer": matched_layers[0]["name"]}
        if has_result:
            return {"result": "last"}
        return None

    def _binary_targets(self, matched_layers: list, has_result: bool):
        if len(matched_layers) >= 2:
            return {"layer": matched_layers[0]["name"]}, {"layer": matched_layers[1]["name"]}
        if len(matched_layers) == 1 and has_result:
            return {"result": "last"}, {"layer": matched_layers[0]["name"]}
        return None

    def _multi_targets(self, matched_layers: list, has_result: bool):
        refs = [{"layer": layer["name"]} for layer in matched_layers]
        if has_result:
            refs.insert(0, {"result": "last"})
        return refs

    def _extract_distance(self, text: str) -> float:
        match = re.search(r"(\d+(?:\.\d+)?)\s*(公里|千米|km|kilometers?|米|m|meters?)?", text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = (match.group(2) or "").lower()
            if unit in {"公里", "千米", "km", "kilometer", "kilometers"}:
                return value * 1000.0
            return value
        return 100.0

    def _extract_crs(self, text: str):
        match = re.search(r"(EPSG[:：]?\s*\d+)", text, re.IGNORECASE)
        if match:
            return match.group(1).replace("：", ":").upper().replace(" ", "")
        numeric = re.search(r"\b(\d{4,6})\b", text)
        if numeric and self._contains_any(text, ["epsg", "坐标系", "投影"]):
            return "EPSG:{}".format(numeric.group(1))
        return None

    def _extract_expression(self, text: str):
        quoted = re.search(r"[\"“](.*?)[\"”]", text)
        if quoted:
            return quoted.group(1).strip()
        after_keyword = re.search(r"(?:表达式|条件)[为是:]?\s*(.+)$", text)
        if after_keyword:
            return after_keyword.group(1).strip(" 。；;")
        return None

    def _extract_new_name(self, text: str):
        quoted = re.search(r"(?:命名为|重命名为|叫做|名称为)\s*[\"“](.*?)[\"”]", text)
        if quoted:
            return quoted.group(1).strip()
        plain = re.search(r"(?:命名为|重命名为|叫做|名称为)\s*([^\s，,。；;]+)", text)
        if plain:
            return plain.group(1).strip()
        return None

    def _extract_field_name(self, text: str, default_name: str = "result"):
        quoted = re.search(r"(?:字段名|字段叫做|保存到字段|写入字段)\s*[\"“](.*?)[\"”]", text)
        if quoted:
            return quoted.group(1).strip()
        plain = re.search(r"(?:字段名|字段叫做|保存到字段|写入字段)\s*([A-Za-z_][A-Za-z0-9_]*)", text)
        if plain:
            return plain.group(1).strip()
        return default_name

    def _extract_context_field_name(self, text: str, matched_layers: list):
        quoted = re.search(r"(?:字段|按字段)\s*[\"“](.*?)[\"”]", text)
        if quoted:
            return quoted.group(1).strip()
        plain = re.search(r"(?:字段|按字段)\s*([A-Za-z_][A-Za-z0-9_]*)", text)
        if plain:
            return plain.group(1).strip()
        for layer in matched_layers:
            for field in layer.get("fields", []):
                field_name = field.get("name", "")
                if field_name and field_name.lower() in text.lower():
                    return field_name
        return None

    def _extract_layout_name(self, text: str):
        quoted = re.search(r"(?:布局|layout)\s*[\"“](.*?)[\"”]", text, re.IGNORECASE)
        if quoted:
            return quoted.group(1).strip()
        plain = re.search(r"(?:布局|layout)\s*([^\s，,。；;]+)", text, re.IGNORECASE)
        if plain:
            candidate = plain.group(1).strip()
            if candidate.lower() not in {"设计器", "manager", "designer"}:
                return candidate
        return None

    def _extract_visibility(self, text: str):
        if self._contains_any(text, ["隐藏", "关闭显示", "hide"]):
            return False
        if self._contains_any(text, ["显示", "打开显示", "show"]):
            return True
        return None

    def _extract_path(self, text: str):
        quoted = re.search(r"[\"“]([A-Za-z]:\\[^\"”]+)[\"”]", text)
        if quoted:
            return quoted.group(1).strip()
        path = re.search(r"([A-Za-z]:\\[^\s]+)", text)
        if path:
            return path.group(1).strip()
        return None

    def _extract_color(self, text: str):
        colors = {
            "红色": "红色",
            "红": "红色",
            "蓝色": "蓝色",
            "蓝": "蓝色",
            "绿色": "绿色",
            "绿": "绿色",
            "黄色": "黄色",
            "黄": "黄色",
            "橙色": "橙色",
            "橙": "橙色",
            "紫色": "紫色",
            "紫": "紫色",
            "灰色": "灰色",
            "灰": "灰色",
            "黑色": "黑色",
            "黑": "黑色",
            "白色": "白色",
            "白": "白色",
        }
        lowered = text.lower()
        hex_match = re.search(r"(#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3}))", text)
        if hex_match:
            return hex_match.group(1)
        for token, normalized in colors.items():
            if token.lower() in lowered:
                return normalized
        return None

    def _extract_color_ramp(self, text: str):
        ramps = {
            "spectral": "Spectral",
            "viridis": "Viridis",
            "magma": "Magma",
            "plasma": "Plasma",
            "turbo": "Turbo",
        }
        lowered = text.lower()
        for token, name in ramps.items():
            if token in lowered:
                return name
        return None

    def _infer_standard_style_set(self, text: str, standard: dict):
        lowered = (text or "").lower()
        preferred_tokens = []
        if any(token in lowered for token in ["控制线", "红线", "蓝线", "绿线", "黄线", "紫线"]):
            preferred_tokens = ["附录d", "控制线"]
        elif any(token in lowered for token in ["规划分区", "规划用途", "分区"]):
            preferred_tokens = ["附录c", "规划分区", "规划用途"]
        elif any(token in lowered for token in ["用地", "用海", "现状"]):
            preferred_tokens = ["附录b", "用地用海", "现状用地"]
        for style_set in standard.get("style_sets", []):
            haystack = " ".join([style_set.get("id", ""), style_set.get("name", "")] + style_set.get("aliases", [])).lower()
            if any(token in haystack for token in preferred_tokens):
                return style_set
        return standard.get("style_sets", [None])[0]

    def _contains_any(self, text: str, tokens: list) -> bool:
        lowered = text.lower()
        return any(token.lower() in lowered for token in tokens)

    def _is_question(self, text: str) -> bool:
        if "?" in text or "？" in text:
            return True
        return self._contains_any(
            text,
            ["是什么", "你是谁", "你是什么模型", "请教", "为什么", "怎么理解", "介绍一下", "解释一下", "什么是"],
        )

    def _match_layers(self, text: str, layers: list) -> list:
        lowered = text.lower()
        matches = []
        seen_ids = set()
        for layer in layers:
            layer_name = layer["name"]
            base_name = layer_name.replace("图层", "")
            candidates = {layer_name, layer_name.lower()}
            if len(base_name.strip()) >= 3:
                candidates.add(base_name)
                candidates.add(base_name.lower())
            positions = [lowered.find(candidate.lower()) for candidate in candidates if candidate and lowered.find(candidate.lower()) >= 0]
            if positions and layer["id"] not in seen_ids:
                matches.append((min(positions), layer))
                seen_ids.add(layer["id"])

        matches.sort(key=lambda item: item[0])
        return [item[1] for item in matches]
