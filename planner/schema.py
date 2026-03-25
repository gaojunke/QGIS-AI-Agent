from dataclasses import dataclass, field


class PlanValidationError(ValueError):
    pass


@dataclass
class PlanStep:
    kind: str
    label: str = ""
    tool_id: str = ""
    params: dict = field(default_factory=dict)
    operation: str = ""
    args: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            raise PlanValidationError("Plan step must be an object.")

        kind = data.get("kind", "").strip().lower()
        if kind not in {"processing", "qgis"}:
            raise PlanValidationError("Unsupported step kind: {}".format(kind or "<empty>"))

        if kind == "processing" and not data.get("tool_id"):
            raise PlanValidationError("Processing step requires tool_id.")
        if kind == "qgis" and not data.get("operation"):
            raise PlanValidationError("QGIS step requires operation.")

        return cls(
            kind=kind,
            label=str(data.get("label", "")).strip(),
            tool_id=str(data.get("tool_id", "")).strip(),
            params=data.get("params") or {},
            operation=str(data.get("operation", "")).strip(),
            args=data.get("args") or {},
        )


@dataclass
class ActionPlan:
    summary: str = ""
    requires_confirmation: bool = True
    steps: list = field(default_factory=list)
    response_text: str = ""
    notes: list = field(default_factory=list)
    source: str = ""

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            raise PlanValidationError("Plan must be an object.")

        raw_steps = data.get("steps")
        if raw_steps is None:
            raw_steps = []
        if not isinstance(raw_steps, list):
            raise PlanValidationError("Plan steps must be a list.")

        notes = data.get("notes") or []
        if not isinstance(notes, list):
            notes = [str(notes)]

        response_text = str(data.get("response_text", "")).strip()
        if not raw_steps and not response_text:
            raise PlanValidationError("Plan must contain at least one step or response_text.")

        return cls(
            summary=str(data.get("summary", "")).strip(),
            requires_confirmation=bool(data.get("requires_confirmation", True)),
            steps=[PlanStep.from_dict(step) for step in raw_steps],
            response_text=response_text,
            notes=[str(item) for item in notes],
            source=str(data.get("source", "")).strip(),
        )

    def to_display_text(self) -> str:
        lines = []
        if self.summary:
            lines.append("摘要: {}".format(self.summary))
        if self.response_text:
            lines.append("回复: {}".format(self.response_text))
        lines.append("需要确认: {}".format("是" if self.requires_confirmation else "否"))
        lines.append("步骤:")
        for index, step in enumerate(self.steps, start=1):
            if step.kind == "processing":
                lines.append(
                    "{}. [processing] {} ({})".format(
                        index,
                        step.label or step.tool_id,
                        step.tool_id,
                    )
                )
                if step.params:
                    lines.append("   参数: {}".format(step.params))
            else:
                lines.append(
                    "{}. [qgis] {} ({})".format(
                        index,
                        step.label or step.operation,
                        step.operation,
                    )
                )
                if step.args:
                    lines.append("   参数: {}".format(step.args))
        if self.notes:
            lines.append("备注:")
            for note in self.notes:
                lines.append("- {}".format(note))
        return "\n".join(lines)
