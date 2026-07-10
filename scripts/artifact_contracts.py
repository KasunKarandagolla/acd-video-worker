"""Canonical artifact API for acd-video-worker.

Every stage MUST use this API rather than constructing paths independently.
All JSON writes are atomic (temporary file + rename).
No hardcoded /kaggle paths.
Repository-root resolution is deterministic.
Invalid or partial JSON cannot be treated as success.
"""
import hashlib
import json
import os
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CONTRACTS_PATH = BASE_DIR / "state" / "integration" / "pipeline_contracts.json"


def _load_contracts() -> dict:
    if CONTRACTS_PATH.is_file():
        with open(CONTRACTS_PATH) as f:
            return json.load(f)
    return {"stages": [], "artifact_index": {}}


def get_run_dir(run_id: str) -> Path:
    return BASE_DIR / "state" / "runs" / run_id


def get_artifact_path(run_id: str, artifact_name: str) -> Path:
    contracts = _load_contracts()
    index = contracts.get("artifact_index", {})
    entry = index.get(artifact_name)
    if entry:
        path_template = entry["path"]
        resolved = path_template.replace("<run_id>", run_id)
        full_path = BASE_DIR / resolved
        if full_path.exists() or not full_path.suffix:
            return full_path
        return full_path
    run_dir = get_run_dir(run_id)
    candidate = run_dir / "hermes_artifacts" / artifact_name
    if candidate.exists():
        return candidate
    candidate2 = run_dir / artifact_name
    if candidate2.exists():
        return candidate2
    return run_dir / "hermes_artifacts" / artifact_name


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(
        suffix=".tmp",
        prefix=path.stem + "_",
        dir=str(path.parent),
    )
    try:
        content = json.dumps(data, indent=2, default=str) + "\n"
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        shutil.move(tmp_path_str, str(path))
    except BaseException:
        os.close(fd)
        if Path(tmp_path_str).is_file():
            Path(tmp_path_str).unlink()
        raise


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Artifact not found: {path}")
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Invalid JSON in {path}: {e}")
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}, got {type(data).__name__}")
    return data


def _get_artifact_schema(name: str) -> dict:
    contracts = _load_contracts()
    for stage in contracts.get("stages", []):
        schemas = stage.get("output_schemas", {})
        if name in schemas:
            return schemas[name]
    return {}


def validate_artifact(name: str, data: dict) -> dict:
    schema = _get_artifact_schema(name)
    if not schema:
        return {"valid": True, "errors": []}
    required = schema.get("required", [])
    errors = []
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    props = schema.get("properties", {})
    for field, value in data.items():
        prop_schema = props.get(field, {})
        prop_type = prop_schema.get("type")
        if prop_type == "array" and not isinstance(value, list):
            errors.append(f"Field '{field}' should be array, got {type(value).__name__}")
        elif prop_type == "object" and not isinstance(value, dict):
            errors.append(f"Field '{field}' should be object, got {type(value).__name__}")
        elif prop_type == "string" and not isinstance(value, str):
            errors.append(f"Field '{field}' should be string, got {type(value).__name__}")
        enum_vals = prop_schema.get("enum")
        if enum_vals and value not in enum_vals:
            errors.append(f"Field '{field}' value '{value}' not in allowed: {enum_vals}")
    return {"valid": len(errors) == 0, "errors": errors}


def require_artifact(run_id: str, name: str) -> dict:
    path = get_artifact_path(run_id, name)
    if not path.is_file():
        raise FileNotFoundError(
            f"REQUIRED ARTIFACT MISSING: '{name}' expected at {path}. "
            f"Producer stage should have created this."
        )
    data = read_json(path)
    validation = validate_artifact(name, data)
    manifest_entry = _load_contracts().get("artifact_index", {}).get(name, {})
    producer = manifest_entry.get("producer", "unknown")
    consumers = manifest_entry.get("consumers", [])
    return {
        "artifact_name": name,
        "path": str(path),
        "producer": producer,
        "consumers": consumers,
        "data": data,
        "schema_valid": validation["valid"],
        "schema_errors": validation["errors"],
    }


def _compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_artifact_manifest(run_id: str) -> dict:
    run_dir = get_run_dir(run_id)
    manifest_path = run_dir / "artifact_manifest.json"
    contracts = _load_contracts()
    index = contracts.get("artifact_index", {})
    manifest = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat() + "Z",
        "artifacts": {},
    }
    for artifact_name, entry in index.items():
        path_template = entry["path"]
        resolved = path_template.replace("<run_id>", run_id)
        full_path = BASE_DIR / resolved
        artifact_record = {
            "artifact_name": artifact_name,
            "expected_path": str(full_path),
            "producer_stage": entry["producer"],
            "consumers": entry["consumers"],
            "exists": full_path.is_file(),
            "schema_valid": False,
            "status": "missing",
            "size": 0,
            "sha256": None,
            "created_timestamp": None,
            "validation_errors": [],
        }
        if full_path.is_file():
            try:
                with open(full_path) as f:
                    data = json.load(f)
                if not isinstance(data, dict) and full_path.suffix == ".json":
                    artifact_record["status"] = "invalid_structure"
                else:
                    artifact_record["status"] = "present"
                validation = validate_artifact(artifact_name, data) if isinstance(data, dict) else {"valid": False, "errors": ["Not a JSON object"]}
                artifact_record["schema_valid"] = validation["valid"]
                artifact_record["validation_errors"] = validation["errors"]
                if not validation["valid"]:
                    artifact_record["status"] = "schema_invalid"
            except (json.JSONDecodeError, ValueError) as e:
                artifact_record["status"] = "invalid_json"
                artifact_record["validation_errors"] = [str(e)]
            except Exception as e:
                artifact_record["status"] = "error"
                artifact_record["validation_errors"] = [str(e)]
            stat = full_path.stat()
            artifact_record["size"] = stat.st_size
            artifact_record["sha256"] = _compute_sha256(full_path)
            artifact_record["created_timestamp"] = datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat()
        manifest["artifacts"][artifact_name] = artifact_record
    atomic_write_json(manifest_path, manifest)
    return manifest


def validate_stage_inputs(stage_name: str, run_id: str) -> list:
    contracts = _load_contracts()
    stage = None
    for s in contracts.get("stages", []):
        if s["stage_name"] == stage_name:
            stage = s
            break
    if not stage:
        raise ValueError(f"Unknown stage: {stage_name}")
    results = []
    for input_path in stage.get("required_inputs", []):
        if "<run_id>" in input_path:
            resolved = Path(str(input_path).replace("<run_id>", run_id))
        else:
            resolved = BASE_DIR / input_path
        if not resolved.exists():
            results.append({
                "stage": stage_name,
                "input": input_path,
                "resolved": str(resolved),
                "status": "missing",
            })
        else:
            results.append({
                "stage": stage_name,
                "input": input_path,
                "resolved": str(resolved),
                "status": "present",
            })
    return results


def validate_stage_outputs(stage_name: str, run_id: str) -> list:
    contracts = _load_contracts()
    stage = None
    for s in contracts.get("stages", []):
        if s["stage_name"] == stage_name:
            stage = s
            break
    if not stage:
        raise ValueError(f"Unknown stage: {stage_name}")
    results = []
    for output_path in stage.get("exact_output_paths", []):
        if "<run_id>" in output_path:
            resolved = Path(str(output_path).replace("<run_id>", run_id))
        else:
            resolved = BASE_DIR / output_path
        if not resolved.exists():
            results.append({
                "stage": stage_name,
                "output": output_path,
                "resolved": str(resolved),
                "status": "missing",
            })
        else:
            results.append({
                "stage": stage_name,
                "output": output_path,
                "resolved": str(resolved),
                "status": "present",
                "size": resolved.stat().st_size,
            })
    return results


def is_synthetic_e2e() -> bool:
    return os.environ.get("PIPELINE_SYNTHETIC_E2E", "0") == "1"


def is_hermes_artifact_canary() -> bool:
    return os.environ.get("HERMES_ARTIFACT_CANARY", "0") == "1"


def is_validation_only() -> bool:
    return os.environ.get("HERMES_VALIDATE_ONLY", "0") == "1"


def get_pipeline_mode() -> str:
    if is_hermes_artifact_canary():
        return "hermes_artifact_canary"
    if is_synthetic_e2e():
        return "synthetic_e2e"
    if is_validation_only():
        return "validation_only"
    return "production"
