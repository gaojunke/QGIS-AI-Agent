from qgis.core import (
    QgsDistanceArea,
    QgsMapLayerType,
    QgsProject,
    QgsUnitTypes,
    QgsWkbTypes,
)


class LocalQueryService:
    def __init__(self):
        self.last_target_layer_info = None
        self.last_query_kind = ""

    def answer(self, command_text: str, project_context: dict, request_mode: str = "auto"):
        text = (command_text or "").strip()
        self.last_target_layer_info = None
        self.last_query_kind = ""
        if not text:
            return None

        if request_mode == "execute":
            return None

        query_kind = self._detect_query_kind(text)
        self.last_query_kind = query_kind

        if query_kind == "project_layers":
            return self._answer_layer_list(project_context)

        if query_kind == "project_summary":
            return self._answer_project_summary(project_context)

        matched = self._match_layers(text, project_context.get("layers", []))
        if len(matched) > 1 and self._is_layer_info_query(text):
            names = ", ".join(layer["name"] for layer in matched[:6])
            return "你提到的图层名称存在歧义，可能是：{}。请把图层名写完整后再问。未对图层和工程做任何操作。".format(names)

        target = matched[0] if matched else self._resolve_memory_target(text, project_context, query_kind)
        self.last_target_layer_info = target

        if query_kind == "fields":
            return self._answer_fields(target, project_context)

        if query_kind == "area":
            return self._answer_area(target, project_context, text)

        if query_kind == "feature_count":
            return self._answer_feature_count(target, project_context)

        if query_kind == "crs":
            return self._answer_crs(target, project_context)

        return None

    def _answer_layer_list(self, project_context: dict):
        layers = project_context.get("layers", [])
        if not layers:
            return "当前工程没有图层。未对图层和工程做任何操作。"
        lines = ["当前工程共有 {} 个图层：".format(len(layers))]
        for layer in layers:
            details = [layer["type"]]
            if layer.get("geometry_type"):
                details.append(layer["geometry_type"])
            if layer.get("crs"):
                details.append(layer["crs"])
            lines.append("- {} [{}]".format(layer["name"], ", ".join(details)))
        lines.append("未对图层和工程做任何操作。")
        return "\n".join(lines)

    def _answer_project_summary(self, project_context: dict):
        project = QgsProject.instance()
        lines = [
            "当前工程摘要：",
            "- 工程标题：{}".format(project.title() or "未命名工程"),
            "- 图层数量：{}".format(project_context.get("layer_count", 0)),
            "- 工程坐标系：{}".format(project.crs().authid() if project.crs().isValid() else "未设置"),
        ]
        lines.append("未对图层和工程做任何操作。")
        return "\n".join(lines)

    def _answer_fields(self, target_layer_info, project_context: dict):
        if target_layer_info is None:
            return "我没有识别到你要查询哪个图层的字段。请在问题中写出图层名，例如：地块图层有哪些字段，分别是什么类型？未对图层和工程做任何操作。"
        fields = target_layer_info.get("fields", [])
        if not fields:
            return "图层“{}”没有可用字段信息，或它不是矢量图层。未对图层和工程做任何操作。".format(target_layer_info["name"])
        lines = ["图层“{}”的字段如下：".format(target_layer_info["name"])]
        for field in fields:
            lines.append("- {}: {}".format(field.get("name", ""), field.get("type", "")))
        lines.append("未对图层和工程做任何操作。")
        return "\n".join(lines)

    def _answer_feature_count(self, target_layer_info, project_context: dict):
        if target_layer_info is None:
            return "我没有识别到你要查询哪个图层的要素数量。请写出图层名，例如：地块图层有多少个要素？未对图层和工程做任何操作。"
        layer = QgsProject.instance().mapLayer(target_layer_info["id"])
        if layer is None or layer.type() != QgsMapLayerType.VectorLayer:
            return "图层“{}”不是可统计要素数量的矢量图层。未对图层和工程做任何操作。".format(target_layer_info["name"])
        feature_count = layer.featureCount()
        return "图层“{}”当前有 {} 个要素。未对图层和工程做任何操作。".format(target_layer_info["name"], feature_count)

    def _answer_crs(self, target_layer_info, project_context: dict):
        if target_layer_info is None:
            project = QgsProject.instance()
            crs = project.crs().authid() if project.crs().isValid() else "未设置"
            return "当前工程坐标系是 {}。未对图层和工程做任何操作。".format(crs)
        crs = target_layer_info.get("crs") or "未设置"
        return "图层“{}”的坐标系是 {}。未对图层和工程做任何操作。".format(target_layer_info["name"], crs)

    def _answer_area(self, target_layer_info, project_context: dict, command_text: str):
        if target_layer_info is None:
            return "我没有识别到你要查询哪个图层的面积。请写出图层名，例如：地块图层面积多少？未对图层和工程做任何操作。"

        layer = QgsProject.instance().mapLayer(target_layer_info["id"])
        if layer is None or layer.type() != QgsMapLayerType.VectorLayer:
            return "图层“{}”不是矢量图层，无法计算面积。未对图层和工程做任何操作。".format(target_layer_info["name"])

        geometry_type = QgsWkbTypes.geometryType(layer.wkbType())
        if geometry_type != QgsWkbTypes.PolygonGeometry:
            return "图层“{}”不是面图层，无法直接计算面积。未对图层和工程做任何操作。".format(target_layer_info["name"])

        calculator = QgsDistanceArea()
        calculator.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
        if QgsProject.instance().ellipsoid():
            calculator.setEllipsoid(QgsProject.instance().ellipsoid())

        total_area = 0.0
        feature_count = 0
        for feature in layer.getFeatures():
            geometry = feature.geometry()
            if geometry is None or geometry.isEmpty():
                continue
            total_area += calculator.measureArea(geometry)
            feature_count += 1

        target_unit, target_unit_label = self._extract_requested_area_unit(command_text)
        source_unit_label = self._pretty_area_unit_name(calculator.areaUnits())

        if target_unit_label == "亩":
            area_square_meters = calculator.convertAreaMeasurement(total_area, QgsUnitTypes.AreaSquareMeters)
            converted_area = area_square_meters / 666.6666666667
            return (
                "图层“{name}”的总面积约为 {area:.3f} 亩，参与统计的要素数为 {count}。"
                " 原始计算单位为 {source_unit}。未对图层和工程做任何操作。"
            ).format(
                name=target_layer_info["name"],
                area=converted_area,
                count=feature_count,
                source_unit=source_unit_label,
            )

        if target_unit is None:
            target_unit = calculator.areaUnits()
            target_unit_label = self._pretty_area_unit_name(target_unit)

        converted_area = calculator.convertAreaMeasurement(total_area, target_unit)

        if target_unit == calculator.areaUnits():
            return (
                "图层“{name}”的总面积约为 {area:.3f} {unit}，参与统计的要素数为 {count}。"
                " 未对图层和工程做任何操作。"
            ).format(name=target_layer_info["name"], area=converted_area, unit=target_unit_label, count=feature_count)

        return (
            "图层“{name}”的总面积约为 {area:.3f} {unit}，参与统计的要素数为 {count}。"
            " 原始计算单位为 {source_unit}。未对图层和工程做任何操作。"
        ).format(
            name=target_layer_info["name"],
            area=converted_area,
            unit=target_unit_label,
            count=feature_count,
            source_unit=source_unit_label,
        )

    def _match_layers(self, text: str, layers: list):
        lowered = text.lower()
        matches = []
        seen_ids = set()
        for layer in layers:
            layer_name = layer["name"]
            base_name = layer_name.replace("图层", "")
            candidates = {layer_name, layer_name.lower()}
            if len(base_name.strip()) >= 2:
                candidates.add(base_name)
                candidates.add(base_name.lower())
            positions = [lowered.find(candidate.lower()) for candidate in candidates if candidate and lowered.find(candidate.lower()) >= 0]
            if positions and layer["id"] not in seen_ids:
                matches.append((min(positions), layer))
                seen_ids.add(layer["id"])
        matches.sort(key=lambda item: item[0])
        return [item[1] for item in matches]

    def _detect_query_kind(self, text: str) -> str:
        if self._is_project_layer_list_query(text):
            return "project_layers"
        if self._is_project_summary_query(text):
            return "project_summary"
        if self._is_field_query(text):
            return "fields"
        if self._is_area_query(text):
            return "area"
        if self._is_feature_count_query(text):
            return "feature_count"
        if self._is_crs_query(text):
            return "crs"
        return ""

    def _resolve_memory_target(self, text: str, project_context: dict, query_kind: str):
        if not query_kind:
            return None
        memory = project_context.get("_conversation_memory") or {}
        if not self._should_use_memory_target(text, query_kind, memory):
            return None
        preferred_names = [
            memory.get("last_result_layer_name", ""),
            memory.get("last_layer_name", ""),
        ]
        layers = project_context.get("layers", [])
        for preferred_name in preferred_names:
            normalized = (preferred_name or "").strip().lower()
            if not normalized:
                continue
            for layer in layers:
                if layer["name"].strip().lower() == normalized:
                    return layer
        return None

    def _should_use_memory_target(self, text: str, query_kind: str, memory: dict) -> bool:
        if self._uses_previous_reference(text):
            return True
        if not memory.get("last_layer_name") and not memory.get("last_result_layer_name"):
            return False
        if query_kind and memory.get("last_query_kind") == query_kind:
            return True
        short_follow_up = len((text or "").strip()) <= 24
        follow_up_tokens = ["呢", "那", "再", "换成", "换算", "转换", "还有", "然后", "继续"]
        if short_follow_up and any(token in text for token in follow_up_tokens):
            return True
        if query_kind == "area" and any(token in text for token in ["亩", "公顷", "平方米", "平方公里", "平方千米", "英亩"]):
            return True
        return False

    def _uses_previous_reference(self, text: str) -> bool:
        tokens = ["这", "它", "这个", "该图层", "这个图层", "刚才那个", "上一步结果", "刚才的结果", "这个结果", "上一句", "上一个"]
        return any(token in text for token in tokens)

    def _is_layer_info_query(self, text: str) -> bool:
        return any(token in text for token in ["图层", "字段", "面积", "坐标系", "要素", "类型"])

    def _is_project_layer_list_query(self, text: str) -> bool:
        tokens = ["有哪些图层", "图层列表", "工程里有什么图层", "当前有哪些图层", "图层有哪些"]
        return any(token in text for token in tokens)

    def _is_project_summary_query(self, text: str) -> bool:
        tokens = ["工程信息", "工程概况", "工程摘要", "当前工程情况", "工程坐标系", "工程有几个图层", "图层数量"]
        return any(token in text for token in tokens)

    def _is_field_query(self, text: str) -> bool:
        tokens = ["有哪些字段", "字段有哪些", "字段分别是什么类型", "字段类型", "属性字段", "有哪些属性", "字段呢", "属性呢"]
        return any(token in text for token in tokens)

    def _is_area_query(self, text: str) -> bool:
        tokens = ["面积多少", "总面积", "面积多大", "面积是多少", "图层面积", "面积有多大", "面积呢"]
        if any(token in text for token in tokens):
            return True
        if "面积" in text and any(unit in text for unit in ["亩", "公顷", "平方米", "平方公里", "平方千米", "平方英里", "平方英尺"]):
            return True
        if any(unit in text for unit in ["亩", "公顷", "平方米", "平方公里", "平方千米", "平方英里", "平方英尺"]):
            return any(keyword in text for keyword in ["多少", "多大", "是多少", "换算", "转换", "合多少", "有多大", "呢"])
        return False

    def _extract_requested_area_unit(self, text: str):
        lowered = (text or "").lower()
        unit_map = [
            ((QgsUnitTypes.AreaSquareKilometers, "平方公里"), ["平方公里", "平方千米", "square kilometers", "sq km", "km2", "km²"]),
            ((QgsUnitTypes.AreaHectares, "公顷"), ["公顷", "hectare", "hectares", "ha"]),
            ((QgsUnitTypes.AreaSquareMeters, "平方米"), ["平方米", "平方公尺", "square meters", "sq m", "m2", "m²"]),
            ((QgsUnitTypes.AreaSquareFeet, "平方英尺"), ["平方英尺", "square feet", "sq ft", "ft2", "ft²"]),
            ((QgsUnitTypes.AreaSquareMiles, "平方英里"), ["平方英里", "square miles", "sq mi", "mi2", "mi²"]),
            ((QgsUnitTypes.AreaAcres, "英亩"), ["英亩", "acre", "acres"]),
        ]
        for unit_info, tokens in unit_map:
            if any(token in lowered for token in tokens):
                return unit_info
        if "亩" in lowered:
            return None, "亩"
        return None, None

    def _pretty_area_unit_name(self, unit):
        name = QgsUnitTypes.toString(unit) or ""
        normalized = name.strip().lower()
        mapping = {
            "square meters": "平方米",
            "m2": "平方米",
            "square kilometres": "平方公里",
            "square kilometers": "平方公里",
            "km2": "平方公里",
            "hectares": "公顷",
            "ha": "公顷",
            "square feet": "平方英尺",
            "ft2": "平方英尺",
            "square miles": "平方英里",
            "mi2": "平方英里",
            "acres": "英亩",
        }
        return mapping.get(normalized, name or "未知单位")

    def _is_feature_count_query(self, text: str) -> bool:
        tokens = ["多少个要素", "要素数量", "有多少要素", "有几个要素", "记录数", "要素数", "要素呢", "记录呢"]
        return any(token in text for token in tokens)

    def _is_crs_query(self, text: str) -> bool:
        tokens = ["坐标系", "投影", "crs", "epsg", "坐标系呢", "投影呢"]
        return any(token.lower() in text.lower() for token in tokens)
