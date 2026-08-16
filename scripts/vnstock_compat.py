#!/usr/bin/env python3
"""Compatibility gate fail-closed cho vnstock_data.

Module này chỉ kiểm tra package/API và schema đã được kiểm định. Gate không đổi
schema bằng suy đoán, không gọi endpoint trong bước probe, và ghi fingerprint
provenance sau khi payload DataFrame đã được fetch.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import inspect
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from statement_adapter import StatementSchemaError, combine_statements, normalize_statement


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "vnstock_compat_registry.json"


class CompatibilityGateError(RuntimeError):
    """Payload/runtime không thuộc contract đã kiểm định."""


def load_registry(path: Path | str = REGISTRY_PATH) -> dict[str, Any]:
    """Đọc registry machine-readable, không cho phép thiếu/sai cấu trúc tối thiểu."""
    try:
        registry = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompatibilityGateError(
            "Không đọc được registry compatibility vnstock_data. "
            "Hãy khôi phục config/vnstock_compat_registry.json rồi chạy lại."
        ) from exc
    if not isinstance(registry, dict) or not registry.get("supported_version_pairs"):
        raise CompatibilityGateError(
            "Registry compatibility vnstock_data không hợp lệ. "
            "Hãy kiểm tra danh sách phiên bản đã kiểm định trước khi chạy lại."
        )
    return registry


def registry_sha256(path: Path | str = REGISTRY_PATH) -> str:
    """Hash registry bytes để payload reuse không chạy với contract cũ."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise CompatibilityGateError(
            "Không đọc được registry để kiểm tra provenance. "
            "Hãy khôi phục registry trước khi chạy lại."
        ) from exc


def _version_candidates(module: Any, registry: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """Lấy authoritative distribution version và module version riêng biệt."""
    distribution = str(registry.get("distribution", "vnstock_data"))
    try:
        dist_version = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        dist_version = None
    module_version = getattr(module, "__version__", None)
    module_version = str(module_version) if module_version is not None else None
    return dist_version, module_version


def _validate_version_pair(
    distribution_version: str | None,
    module_version: str | None,
    registry: Mapping[str, Any],
) -> None:
    pairs = registry.get("supported_version_pairs", [])
    exact = any(
        distribution_version == str(pair.get("distribution_version"))
        and module_version in {str(v) for v in pair.get("module_versions", [])}
        for pair in pairs
    )
    if not exact:
        allowed = ", ".join(
            f"{pair.get('distribution_version')}/{','.join(map(str, pair.get('module_versions', [])))}"
            for pair in pairs
        ) or "không có"
        raise CompatibilityGateError(
            "Cặp version vnstock_data chưa được kiểm định: "
            f"distribution={distribution_version or 'không xác định'}, "
            f"module={module_version or 'không xác định'}. "
            f"Registry hiện chỉ cho phép: {allowed}; hãy cài đúng virtualenv "
            "hoặc mở quy trình kiểm định nâng version."
        )


def _runtime_for_statement(registry: Mapping[str, Any] | None = None) -> dict[str, str]:
    """Đọc cặp version hiện tại mà không gọi endpoint.

    Builder và verifier dùng cùng một quyết định format. Không thử format khác
    sau khi API đã trả lỗi; lỗi gọi API phải nổi lên để fail-closed.
    """
    registry = registry or load_registry()
    try:
        module = importlib.import_module(str(registry.get("provider", "vnstock_data")))
    except (ImportError, ModuleNotFoundError) as exc:
        raise CompatibilityGateError(
            f"Không import được {registry.get('provider', 'vnstock_data')} "
            f"bằng interpreter hiện tại ({sys.executable})."
        ) from exc
    dist_version, module_version = _version_candidates(module, registry)
    _validate_version_pair(dist_version, module_version, registry)
    return {
        "distribution_version": str(dist_version),
        "module_version": str(module_version),
    }


def statement_request_kwargs(
    runtime: Mapping[str, Any],
    period: str,
    *,
    lang: str = "en",
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Trả kwargs exact theo distribution đã kiểm định.

    3.2.7 giữ lời gọi cũ. 3.2.8 yêu cầu ``time_series`` để tránh long payload
    bị hiểu nhầm là period×field. Không có fallback mù khi lời gọi thực tế lỗi.
    """
    registry = registry or load_registry()
    distribution = str(runtime.get("distribution_version") or "")
    formats = registry.get("statement_formats", {})
    spec = formats.get(distribution)
    if not isinstance(spec, Mapping):
        raise CompatibilityGateError(
            f"Chưa có statement format contract cho vnstock_data {distribution}."
        )
    kwargs: dict[str, Any] = {"period": period, "lang": lang}
    requested = spec.get("request_format")
    if requested:
        kwargs["format"] = requested
    return kwargs


def fetch_statement_frame(
    equity_api: Any,
    method_name: str,
    period: str,
    *,
    runtime: Mapping[str, Any] | None = None,
    lang: str = "en",
    registry: Mapping[str, Any] | None = None,
) -> Any:
    """Gọi một statement bằng format đã được version gate.

    ``TypeError``/lỗi server không kích hoạt thử lại bằng format khác; bên gọi
    nhận lỗi và builder dừng trước khi render.
    """
    registry = registry or load_registry()
    runtime = dict(runtime or _runtime_for_statement(registry))
    kwargs = statement_request_kwargs(runtime, period, lang=lang, registry=registry)
    member = getattr(equity_api, method_name, None)
    if not callable(member):
        raise CompatibilityGateError(f"API statement thiếu method {method_name}.")
    try:
        return member(**kwargs)
    except Exception as exc:
        raise CompatibilityGateError(
            f"Gọi vnstock_data {method_name} ({runtime.get('distribution_version')}, "
            f"format={kwargs.get('format', 'legacy-default')}) thất bại: {exc}"
        ) from exc


def _check_callable(
    obj: Any,
    path: str,
    required: list[str] | None = None,
    *,
    label: str | None = None,
) -> None:
    member = obj if path == "<callable>" else getattr(obj, path, None)
    if not callable(member):
        raise CompatibilityGateError(
            f"Thiếu API bắt buộc vnstock_data: {label or path}. "
            "Hãy cài đúng cặp version trong registry hoặc cập nhật registry sau khi kiểm định; "
            "không có fallback community."
        )
    if not required:
        return
    try:
        signature = inspect.signature(member)
    except (TypeError, ValueError):
        # Một số extension callable không expose signature; callable đã đủ cho
        # probe surface, còn lời gọi thật sẽ được builder kiểm soát fail-closed.
        return
    names = set(signature.parameters)
    accepts_kwargs = any(p.kind == p.VAR_KEYWORD for p in signature.parameters.values())
    missing = [name for name in required if name not in names and not accepts_kwargs]
    if missing:
        raise CompatibilityGateError(
            f"API {label or path} thiếu tham số bắt buộc {missing}. "
            "Hãy dùng cặp version trong registry đã kiểm định hoặc cập nhật gate "
            "cùng fixture/test khi nâng version."
        )


def probe_api_surface(
    module: Any | None = None,
    *,
    fundamental: Any | None = None,
    equity_api: Any | None = None,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Probe runtime hiện tại; không gọi endpoint.

    Probe tạo ``Fundamental()`` và kiểm tra ``instance.equity`` trước khi
    builder gọi proxy với ticker. ``equity_api`` là object đã có sau lần gọi
    bắt buộc đó; truyền nó vào giúp kiểm tra statement methods mà không phát
    sinh thêm API call.
    """
    registry = registry or load_registry()
    if module is None:
        try:
            module = importlib.import_module(str(registry.get("provider", "vnstock_data")))
        except (ImportError, ModuleNotFoundError) as exc:
            raise CompatibilityGateError(
                "Không import được vnstock_data bằng interpreter hiện tại "
                f"({sys.executable}). Hãy kích hoạt đúng virtualenv, cài Sponsor "
                "vnstock_data theo cặp version trong registry rồi chạy lại; không có fallback community."
            ) from exc

    dist_version, module_version = _version_candidates(module, registry)
    _validate_version_pair(dist_version, module_version, registry)

    surface = registry.get("api_surface", {}).get("classes", {})
    fundamental_cls = getattr(module, "Fundamental", None)
    _check_callable(fundamental_cls, "<callable>", label="Fundamental constructor")
    if fundamental is None:
        try:
            fundamental = fundamental_cls()
        except Exception as exc:
            raise CompatibilityGateError(
                "Không khởi tạo được Fundamental() để kiểm tra API instance "
                "mà không gọi endpoint. Hãy kiểm tra virtualenv/Sponsor và chạy lại; "
                "không log hoặc chép credential vào repository."
            ) from exc

    for class_name, class_spec in surface.items():
        cls = getattr(module, class_name, None)
        _check_callable(cls, "<callable>", label=f"{class_name} constructor")
        methods = class_spec.get("methods", {})
        for method_name, method_spec in methods.items():
            if class_name == "Fundamental" and method_name == "equity":
                # Unified UI exposes equity as a property returning a callable
                # proxy trên instance, không phải class method.
                _check_callable(
                    fundamental,
                    method_name,
                    list(method_spec.get("required_parameters", [])),
                    label="Fundamental().equity",
                )
            else:
                _check_callable(
                    cls,
                    method_name,
                    list(method_spec.get("required_parameters", [])),
                    label=f"{class_name}.{method_name}",
                )

    if equity_api is not None:
        methods = surface.get("Fundamental", {}).get("equity_methods", {})
        for method_name, method_spec in methods.items():
            _check_callable(
                equity_api,
                method_name,
                list(method_spec.get("required_parameters", [])),
            )

    return {
        "provider": registry.get("provider", "vnstock_data"),
        "tested_version": registry.get("tested_version"),
        # Ghi đúng distribution thực tế của payload, không gán mọi artifact về
        # phiên bản mới nhất trong registry; nhờ vậy 3.2.7 và 3.2.8 đều có thể
        # reuse với cùng registry freeze.
        "tested_distribution_version": dist_version,
        "distribution_version": dist_version,
        "module_version": module_version,
        "interpreter": sys.executable,
        "fundamental_instance_checked": True,
        "api_surface_checked": bool(equity_api is not None),
    }


_PERIOD_RE = re.compile(r"^20\d{2}(?:-?Q[1-4])?$", re.IGNORECASE)
_ITEM_COLUMNS = ("item", "name", "metric")


def _period_text(value: Any) -> str:
    text = str(value).strip()
    return text[:-2] if re.fullmatch(r"20\d{2}\.0", text) else text


def _period_like(value: Any) -> bool:
    return bool(_PERIOD_RE.fullmatch(_period_text(value)))


def _shape_mode(frame: Any) -> str:
    columns = list(getattr(frame, "columns", []))
    if {"period", "id", "value"}.issubset(columns):
        return "long_period_id_rows"
    if "period" in columns:
        return "period_column_rows"
    index = list(getattr(frame, "index", []))
    if index and all(_period_like(value) for value in index):
        return "period_index_rows"
    period_columns = [column for column in columns if _period_like(column)]
    if period_columns and any(column in columns for column in _ITEM_COLUMNS):
        return "item_by_period_wide"
    return "unknown"


def _required_fields(registry: Mapping[str, Any], statement: str) -> list[list[str]]:
    return list(
        registry.get("data_contract", {})
        .get("required_canonical_fields", {})
        .get(statement, [])
    )


def _has_finite_numeric_value(frame: Any, column: str) -> bool:
    """Một giá trị 0 hợp lệ; chỉ NaN/inf/non-numeric mới bị loại."""
    try:
        values = frame[column]
    except (KeyError, TypeError, IndexError):
        return False
    for value in values:
        if isinstance(value, bool):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(numeric):
            return True
    return False


def fingerprint_statement(
    frame: Any,
    statement: str,
    *,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fingerprint raw DataFrame và kiểm tra canonical fields exact-first."""
    registry = registry or load_registry()
    shape_mode = _shape_mode(frame)
    if shape_mode == "unknown":
        raise CompatibilityGateError(
            f"Schema {statement} không nhận dạng được (shape unknown). "
            "Gate không tự map schema mới; hãy bổ sung mapping exact, fixture và "
            "registry sau khi kiểm định rồi chạy lại."
        )
    try:
        normalized = normalize_statement(frame, statement)
    except (StatementSchemaError, TypeError, ValueError) as exc:
        raise CompatibilityGateError(
            f"Schema {statement} không thuộc contract đã kiểm định: {exc}. "
            "Hãy kiểm tra payload period/canonical fields hoặc mở quy trình nâng version."
        ) from exc

    columns = [str(column) for column in normalized.columns if column != "report_period"]
    missing_groups: list[list[str]] = []
    unavailable_groups: list[list[str]] = []
    for group in _required_fields(registry, statement):
        present = [field for field in group if field in columns]
        if not present:
            missing_groups.append(group)
        elif not any(_has_finite_numeric_value(normalized, field) for field in present):
            unavailable_groups.append(group)
    if missing_groups:
        raise CompatibilityGateError(
            f"Schema {statement} thiếu canonical field bắt buộc {missing_groups}. "
            "Không được suy diễn field thay thế; hãy kiểm định schema/provider trước khi chạy lại."
        )
    if unavailable_groups:
        raise CompatibilityGateError(
            f"Schema {statement} có canonical field nhưng không có dữ liệu khả dụng "
            f"(chỉ NaN/inf/non-numeric): {unavailable_groups}. "
            "Hãy kiểm tra payload nguồn trước khi render; không coi schema rỗng là supported."
        )

    periods = [_period_text(value) for value in normalized.index]
    period_kinds = sorted({"quarter" if "Q" in period.upper() else "year" for period in periods})
    return {
        "statement": statement,
        "shape_mode": shape_mode,
        "period_representation": {
            "source": (
                "long_period_id_value" if shape_mode == "long_period_id_rows" else
                "period_column" if shape_mode == "period_column_rows" else
                "period_index" if shape_mode == "period_index_rows" else "item_columns"
            ),
            "kinds": period_kinds,
            "count": len(periods),
            "examples": periods[:5],
        },
        "canonical_fields": columns,
        "required_canonical_fields": _required_fields(registry, statement),
        "missing_required_fields": missing_groups,
        "units_assumptions": registry.get("data_contract", {}).get("units", {}),
        "normalized_shape": [int(normalized.shape[0]), int(normalized.shape[1])],
        "status": "supported",
    }


def run_schema_gate(
    raw_frames: Mapping[str, tuple[Any, Any]],
    *,
    work_dir: Path | str,
    runtime: Mapping[str, Any] | None = None,
    registry: Mapping[str, Any] | None = None,
    registry_path: Path | str = REGISTRY_PATH,
) -> dict[str, Any]:
    """Validate fetched quarter/year frames and persist deterministic provenance."""
    registry = registry or load_registry()
    runtime = dict(runtime or probe_api_surface(registry=registry))
    required_statements = set(
        registry.get("data_contract", {}).get("required_canonical_fields", {})
    )
    provided_statements = set(raw_frames)
    missing_statements = sorted(required_statements - provided_statements)
    unknown_statements = sorted(provided_statements - required_statements)
    if missing_statements or unknown_statements:
        details = []
        if missing_statements:
            details.append(f"thiếu={missing_statements}")
        if unknown_statements:
            details.append(f"unknown={unknown_statements}")
        raise CompatibilityGateError(
            "Payload statement không khớp exact contract registry (" + ", ".join(details) + "). "
            "Hãy fetch đủ income/balance/cash_flow và không tự bỏ qua statement lạ trước khi render."
        )
    fingerprints: dict[str, Any] = {}
    for statement, pair in raw_frames.items():
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise CompatibilityGateError(
                f"Payload {statement} không có đủ cặp quarter/year DataFrame. "
                "Hãy sửa fetch contract trước khi render."
            )
        quarter, annual = pair
        q_fp = fingerprint_statement(quarter, statement, registry=registry)
        y_fp = fingerprint_statement(annual, statement, registry=registry)
        try:
            combined = combine_statements(quarter, annual, statement)
        except StatementSchemaError as exc:
            raise CompatibilityGateError(
                f"Không gộp được schema {statement}: {exc}. "
                "Gate chặn render để tránh lệch kỳ; hãy xử lý payload exact-first."
            ) from exc
        combined_fp = fingerprint_statement(combined, statement, registry=registry)
        fingerprints[statement] = {
            "quarter": q_fp,
            "year": y_fp,
            "combined": combined_fp,
        }

    payload: dict[str, Any] = {
        "gate": "vnstock_data_compatibility",
        "status": "supported",
        "registry_version": registry.get("registry_version"),
        "registry_sha256": registry_sha256(registry_path),
        "provider": registry.get("provider"),
        "tested_version": registry.get("tested_version"),
        "tested_distribution_version": runtime.get(
            "distribution_version", registry.get("authoritative_distribution_version")
        ),
        "runtime": runtime,
        "frames": fingerprints,
        "provenance": {
            "interpreter": sys.executable,
            "builder": "scripts/build_report.py",
            "api_calls": "reused fetched quarter/year payloads; no probe endpoint call",
        },
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    payload["fingerprint_sha256"] = hashlib.sha256(canonical).hexdigest()
    output = Path(work_dir) / "schema-fingerprint.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def validate_reused_schema_fingerprint(
    work_dir: Path | str,
    *,
    registry_path: Path | str = REGISTRY_PATH,
) -> dict[str, Any]:
    """Cho phép ``--reuse`` chỉ khi payload đã có fingerprint supported."""
    path = Path(work_dir) / "schema-fingerprint.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompatibilityGateError(
            "Payload --reuse thiếu schema-fingerprint.json hợp lệ. "
            "Hãy chạy lại fetch đầy đủ để gate kiểm tra schema trước khi render; "
            "không gọi API bổ sung trong nhánh reuse."
        ) from exc
    registry = load_registry(registry_path)
    current_registry_sha = registry_sha256(registry_path)
    if payload.get("status") != "supported" or payload.get("gate") != "vnstock_data_compatibility":
        raise CompatibilityGateError(
            "Fingerprint schema của payload --reuse không ở trạng thái supported. "
            "Hãy fetch lại bằng phiên bản vnstock_data đã kiểm định trước khi render."
        )
    if payload.get("registry_version") != registry.get("registry_version"):
        raise CompatibilityGateError(
            "Fingerprint --reuse dùng registry_version cũ; hãy fetch lại với registry hiện tại."
        )
    if payload.get("registry_sha256") != current_registry_sha:
        raise CompatibilityGateError(
            "Fingerprint --reuse không khớp SHA registry hiện tại; artifact hoặc registry đã thay đổi. "
            "Hãy fetch lại trước khi render."
        )
    runtime = payload.get("runtime") or {}
    runtime_distribution = runtime.get("distribution_version")
    if payload.get("tested_distribution_version") != runtime_distribution:
        raise CompatibilityGateError(
            "Fingerprint --reuse không khớp distribution version của payload. "
            "Hãy fetch lại bằng cặp version trong registry hiện tại."
        )
    allowed_pairs = {
        (str(pair.get("distribution_version")), str(module))
        for pair in registry.get("supported_version_pairs", [])
        for module in pair.get("module_versions", [])
    }
    if (str(runtime_distribution), str(runtime.get("module_version"))) not in allowed_pairs:
        raise CompatibilityGateError(
            "Fingerprint --reuse có cặp runtime version không được registry hiện tại cho phép."
        )
    stored_hash = payload.get("fingerprint_sha256")
    if not stored_hash:
        raise CompatibilityGateError(
            "Fingerprint --reuse thiếu fingerprint_sha256; artifact không xác thực được."
        )
    unsigned = dict(payload)
    unsigned.pop("fingerprint_sha256", None)
    recomputed = hashlib.sha256(
        json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if stored_hash != recomputed:
        raise CompatibilityGateError(
            "Fingerprint --reuse bị thay đổi hoặc hỏng checksum; hãy fetch lại trước khi render."
        )
    return payload


def main() -> int:
    """CLI probe dùng đúng ``sys.executable`` của lệnh gọi."""
    try:
        print(json.dumps(probe_api_surface(), ensure_ascii=False, indent=2))
        return 0
    except CompatibilityGateError as exc:
        print(f"COMPATIBILITY GATE: FAIL — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
