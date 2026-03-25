from copy import deepcopy
from dataclasses import dataclass, field
import difflib
from pathlib import Path

from qgis.core import QgsProcessingContext, QgsProcessingFeedback, QgsProject, QgsRasterLayer, QgsVectorLayer

from .errors import AmbiguousLayerReferenceError, ExecutionCancelledError, MissingLayerReferenceError
from .qgis_api_executor import QgisApiExecutor


@dataclass
class ExecutionReport:
    logs: list = field(default_factory=list)
    added_layers: list = field(default_factory=list)
    step_results: dict = field(default_factory=dict)
    undo_hint: str = ""
    operation_summary: list = field(default_factory=list)


class GuiAwareProcessingFeedback(QgsProcessingFeedback):
    def __init__(self, event_pump=None, progress_callback=None, is_cancelled=None):
        super().__init__()
        self._event_pump = event_pump
        self._progress_callback = progress_callback
        self._is_cancelled = is_cancelled or (lambda: False)

    def isCanceled(self):
        if self._is_cancelled():
            super().cancel()
        return super().isCanceled()

    def setProgressText(self, text):
        super().setProgressText(text)
        self._notify(text)

    def pushInfo(self, info):
        super().pushInfo(info)
        self._notify(info)

    def reportError(self, error, fatalError=False):
        super().reportError(error, fatalError)
        self._notify(error)

    def setProgress(self, progress):
        super().setProgress(progress)
        self._pump()

    def setProcessedCount(self, count):
        super().setProcessedCount(count)
        self._pump()

    def _notify(self, text: str):
        if self._progress_callback and text:
            self._progress_callback(str(text))
        self._pump()

    def _pump(self):
        if self._event_pump is not None:
            self._event_pump()


class PlanExecutor:
    def __init__(self, iface, project_context_builder, registry, style_standards=None):
        self.iface = iface
        self.project_context_builder = project_context_builder
        self.registry = registry
        self.qgis_executor = QgisApiExecutor(iface, style_standards=style_standards)

    def execute(self, plan, allow_dynamic_processing: bool = False, event_pump=None, progress_callback=None, is_cancelled=None) -> ExecutionReport:
        import processing

        report = ExecutionReport()
        step_results = {}
        context = QgsProcessingContext()
        context.setProject(QgsProject.instance())
        feedback = GuiAwareProcessingFeedback(
            event_pump=event_pump,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled,
        )

        def log(message: str):
            report.logs.append(message)
            if progress_callback:
                progress_callback(message)

        project_context = self.project_context_builder.build()
        last_result_value = None

        for index, step in enumerate(plan.steps, start=1):
            if is_cancelled and is_cancelled():
                raise ExecutionCancelledError("用户已取消执行。")
            self.registry.validate_step(step, allow_dynamic_processing=allow_dynamic_processing)
            step_key = "step_{}".format(index)
            label = step.label or step.tool_id or step.operation or step_key
            log("开始执行步骤 {}: {}".format(index, label))
            report.operation_summary.append(label)

            if step.kind == "processing":
                params = self._resolve_value(step.params, project_context, step_results, last_result_value, context)
                result = processing.run(step.tool_id, params, context=context, feedback=feedback)
                step_results[step_key] = result
                last_result_value = self._pick_primary_output(result)
                log("算法执行完成: {}".format(step.tool_id))
                added = self._add_output_layers(result, context, log)
                report.added_layers.extend(added)
            else:
                result = self.qgis_executor.execute(
                    step.operation,
                    step.args,
                    lambda value: self._resolve_value(value, project_context, step_results, last_result_value, context),
                    log,
                )
                step_results[step_key] = result
                last_result_value = result

        report.step_results = step_results
        report.undo_hint = self._build_undo_hint(plan, report)
        return report

    def find_layer_reference_issues(self, plan, allow_dynamic_processing: bool = False):
        issues = []
        project_context = self.project_context_builder.build()
        seen = set()
        for step in plan.steps:
            self.registry.validate_step(step, allow_dynamic_processing=allow_dynamic_processing)
        for value in self._iter_layer_refs(plan.steps):
            reference = str(value).strip()
            if not reference or reference in seen:
                continue
            seen.add(reference)
            try:
                self._resolve_layer_reference(reference, project_context, raise_on_partial=True)
            except (AmbiguousLayerReferenceError, MissingLayerReferenceError) as exc:
                issues.append(exc)
        return issues

    def apply_layer_selection(self, plan, reference: str, selected_layer_name: str):
        updated = deepcopy(plan)
        updated.steps = [self._replace_layer_refs(step, reference, selected_layer_name) for step in updated.steps]
        return updated

    def _resolve_value(self, value, project_context: dict, step_results: dict, last_result_value, context: QgsProcessingContext):
        if isinstance(value, dict):
            if "layer" in value:
                return self._find_layer(value["layer"], project_context)
            if "result" in value:
                ref = str(value["result"]).strip()
                if ref == "last":
                    resolved = self._resolve_layer_output(last_result_value, context)
                    return resolved if resolved is not None else last_result_value
                if "." in ref:
                    step_key, output_key = ref.split(".", 1)
                    result = step_results.get(step_key, {})
                    resolved = self._resolve_layer_output(result.get(output_key), context)
                    return resolved if resolved is not None else result.get(output_key)
                resolved = self._resolve_layer_output(step_results.get(ref), context)
                return resolved if resolved is not None else step_results.get(ref)
            if "literal" in value:
                return value["literal"]
            return {
                key: self._resolve_value(item, project_context, step_results, last_result_value, context)
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [self._resolve_value(item, project_context, step_results, last_result_value, context) for item in value]

        return value

    def _find_layer(self, layer_ref: str, project_context: dict):
        resolved = self._resolve_layer_reference(layer_ref, project_context, raise_on_partial=True)
        return QgsProject.instance().mapLayer(resolved["id"]) if resolved else None

    def _pick_primary_output(self, result: dict):
        if not isinstance(result, dict):
            return result
        for key in ("OUTPUT", "OUTPUT_LAYER", "RESULT"):
            if key in result:
                return result[key]
        for value in result.values():
            return value
        return None

    def _add_output_layers(self, result: dict, context: QgsProcessingContext, log):
        added_layers = []
        seen_layer_ids = set()
        for value in result.values():
            layer = self._resolve_layer_output(value, context)
            if layer is not None:
                if QgsProject.instance().mapLayer(layer.id()) is None:
                    QgsProject.instance().addMapLayer(layer)
                if layer.id() not in seen_layer_ids:
                    added_layers.append(layer.name())
                    log("已将结果图层加入地图: {}".format(layer.name()))
                    seen_layer_ids.add(layer.id())
        return added_layers

    def _resolve_layer_output(self, value, context: QgsProcessingContext):
        if value is None:
            return None
        if isinstance(value, (QgsVectorLayer, QgsRasterLayer)):
            return value
        if isinstance(value, str):
            layer = context.getMapLayer(value)
            if layer is not None:
                return layer
            project_layer = QgsProject.instance().mapLayer(value)
            if project_layer is not None:
                return project_layer

            path = Path(value)
            if path.exists():
                vector_layer = QgsVectorLayer(str(path), path.stem, "ogr")
                if vector_layer.isValid():
                    return vector_layer
                raster_layer = QgsRasterLayer(str(path), path.stem)
                if raster_layer.isValid():
                    return raster_layer
        return None

    def _resolve_layer_reference(self, layer_ref: str, project_context: dict, raise_on_partial: bool = True):
        if not layer_ref:
            raise MissingLayerReferenceError(layer_ref, "缺少图层引用。")

        project = QgsProject.instance()
        direct = project.mapLayer(layer_ref)
        if direct is not None:
            return {"id": direct.id(), "name": direct.name()}

        normalized = str(layer_ref).strip().lower()
        layers = project_context.get("layers", [])

        exact_matches = [layer for layer in layers if layer["name"].strip().lower() == normalized]
        if len(exact_matches) == 1:
            return exact_matches[0]

        partial_matches = [layer for layer in layers if normalized and normalized in layer["name"].strip().lower()]
        if len(partial_matches) == 1:
            return partial_matches[0]
        if len(partial_matches) > 1 and raise_on_partial:
            raise AmbiguousLayerReferenceError(
                layer_ref,
                "图层引用 '{}' 存在歧义。".format(layer_ref),
                [layer["name"] for layer in partial_matches],
            )

        suggestions = difflib.get_close_matches(
            normalized,
            [layer["name"] for layer in layers],
            n=5,
            cutoff=0.4,
        )
        raise MissingLayerReferenceError(
            layer_ref,
            "未找到图层 '{}'。".format(layer_ref),
            suggestions,
        )

    def _iter_layer_refs(self, values):
        if isinstance(values, list):
            for value in values:
                yield from self._iter_layer_refs(value)
            return
        if hasattr(values, "params"):
            yield from self._iter_layer_refs(values.params)
            yield from self._iter_layer_refs(values.args)
            return
        if isinstance(values, dict):
            if "layer" in values and isinstance(values["layer"], str):
                yield values["layer"]
            for item in values.values():
                yield from self._iter_layer_refs(item)

    def _replace_layer_refs(self, value, reference: str, selected_layer_name: str):
        if hasattr(value, "params"):
            value.params = self._replace_layer_refs(value.params, reference, selected_layer_name)
            value.args = self._replace_layer_refs(value.args, reference, selected_layer_name)
            return value
        if isinstance(value, dict):
            replaced = {}
            for key, item in value.items():
                if key == "layer" and item == reference:
                    replaced[key] = selected_layer_name
                else:
                    replaced[key] = self._replace_layer_refs(item, reference, selected_layer_name)
            return replaced
        if isinstance(value, list):
            return [self._replace_layer_refs(item, reference, selected_layer_name) for item in value]
        return value

    def _build_undo_hint(self, plan, report: ExecutionReport) -> str:
        hints = []
        if report.added_layers:
            hints.append("如需回退，可删除结果图层: {}。".format(", ".join(report.added_layers)))
        for step in plan.steps:
            if step.kind == "qgis":
                if step.operation == "rename_layer":
                    hints.append("如需回退重命名，请将图层名称改回原值。")
                elif step.operation == "set_layer_visibility":
                    hints.append("如需回退显示状态，请切换图层可见性。")
                elif step.operation == "remove_layer":
                    hints.append("删除图层后无法自动恢复，如需回退请重新加载该图层。")
                elif step.operation == "select_by_expression":
                    hints.append("如需回退选择，请执行清除选择。")
        return "\n".join(dict.fromkeys(hints))
