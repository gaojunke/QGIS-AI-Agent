from qgis.core import QgsMapLayerType, QgsProject, QgsWkbTypes


class ProjectContextBuilder:
    def __init__(self):
        self._cached_context = None

    def build(self, force: bool = False):
        project = QgsProject.instance()
        if not force and self._cached_context is not None:
            return self._clone_context(self._cached_context)

        layers = []
        for layer in project.mapLayers().values():
            layer_info = {
                "id": layer.id(),
                "name": layer.name(),
                "type": self._layer_type_name(layer.type()),
                "provider": getattr(layer, "providerType", lambda: "")(),
                "source": layer.source(),
                "crs": layer.crs().authid() if layer.crs().isValid() else "",
                "feature_count": "",
            }
            if layer.type() == QgsMapLayerType.VectorLayer:
                layer_info["geometry_type"] = QgsWkbTypes.displayString(layer.wkbType())
                layer_info["fields"] = [
                    {
                        "name": field.name(),
                        "type": field.typeName(),
                    }
                    for field in layer.fields()
                ]
            else:
                layer_info["geometry_type"] = ""
                layer_info["fields"] = []
            layers.append(layer_info)

        context = {
            "project_title": project.title(),
            "layer_count": len(layers),
            "layers": layers,
        }
        self._cached_context = self._clone_context(context)
        return self._clone_context(context)

    def invalidate(self):
        self._cached_context = None

    def summary_text(self, context):
        if not context["layers"]:
            return "当前工程没有图层。"

        lines = ["工程图层:"]
        for layer in context["layers"]:
            details = [layer["type"]]
            if layer["geometry_type"]:
                details.append(layer["geometry_type"])
            if layer["crs"]:
                details.append(layer["crs"])
            lines.append("- {} [{}]".format(layer["name"], ", ".join(details)))
        return "\n".join(lines)

    def _layer_type_name(self, layer_type):
        if layer_type == QgsMapLayerType.VectorLayer:
            return "vector"
        if layer_type == QgsMapLayerType.RasterLayer:
            return "raster"
        if layer_type == QgsMapLayerType.MeshLayer:
            return "mesh"
        return "other"

    def _clone_context(self, context: dict):
        layers = []
        for layer in context.get("layers", []):
            layers.append(
                {
                    "id": layer.get("id", ""),
                    "name": layer.get("name", ""),
                    "type": layer.get("type", ""),
                    "provider": layer.get("provider", ""),
                    "source": layer.get("source", ""),
                    "crs": layer.get("crs", ""),
                    "geometry_type": layer.get("geometry_type", ""),
                    "feature_count": layer.get("feature_count", ""),
                    "fields": [dict(field) for field in layer.get("fields", [])],
                }
            )
        return {
            "project_title": context.get("project_title", ""),
            "layer_count": context.get("layer_count", len(layers)),
            "layers": layers,
        }
