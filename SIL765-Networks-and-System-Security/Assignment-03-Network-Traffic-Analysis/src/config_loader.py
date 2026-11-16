from pathlib import Path
import yaml


def load(config_path: str | Path | None = None) -> dict:
    if config_path is None:
        config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    config_path = Path(config_path).resolve()
    project_root = config_path.parent

    with open(config_path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    # resolve data directory to absolute
    data_dir = Path(cfg["data"]["base_dir"])
    if not data_dir.is_absolute():
        data_dir = (project_root / data_dir).resolve()
    cfg["data"]["base_dir"] = data_dir

    # build absolute paths for each CSV file
    file_list = cfg["data"].get("files") or []
    if file_list:
        cfg["data"]["abs_files"] = [data_dir / f for f in file_list]
    else:
        cfg["data"]["abs_files"] = sorted(data_dir.glob("network_analysis_data*.csv"))

    # resolve output paths
    for key in ("figures_dir",):
        p = Path(cfg["output"][key])
        if not p.is_absolute():
            p = (project_root / p).resolve()
        cfg["output"][key] = p

    cfg["output"]["figures_dir"].mkdir(parents=True, exist_ok=True)

    return cfg
