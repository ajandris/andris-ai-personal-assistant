"""Проверка, что ноутбук собирается из модуля assistant_core без расхождений."""

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_notebook", ROOT / "scripts" / "build_notebook.py")
build_notebook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_notebook)


def notebook_cells():
    return build_notebook.build_cells((ROOT / "app" / "rag" / "assistant_core.py").read_text(encoding="utf-8"))


def code_of(cells):
    return ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]


def test_every_core_function_and_class_is_in_the_notebook():
    core = ast.parse((ROOT / "app" / "rag" / "assistant_core.py").read_text(encoding="utf-8"))
    core_names = {n.name for n in core.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    notebook_code = "\n".join(code_of(notebook_cells())[1:])  # без ячейки %pip
    notebook_names = {n.name for n in ast.parse(notebook_code).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    assert core_names <= notebook_names


def test_notebook_paths_point_to_notebook_folder():
    imports_cell = code_of(notebook_cells())[1]
    assert 'DEFAULT_RECORDS_PATH = DATA_DIR / "records_rag_a.jsonl"' in imports_cell
    assert "__file__" not in imports_cell


def test_last_cell_runs_main_and_main_is_defined_before():
    cells = code_of(notebook_cells())
    assert cells[-1].strip() == "main()"
    assert "def main(" in cells[-2]


def test_notebook_has_no_api_key():
    text = "\n".join("".join(c["source"]) for c in notebook_cells())
    assert "sk-" not in text


def test_api_key_comes_from_colab_secret_not_prompt():
    functions_cell = code_of(notebook_cells())[-2]
    assert 'userdata.get(secret_name)' in functions_cell
    assert 'secret_name: str = "OPENAI_API_KEY"' in functions_cell
    assert "getpass" not in functions_cell


def notebook_helpers(zip_url="https://drive.google.com/file/d/abc/view"):
    imports_cell = code_of(build_notebook.build_cells(
        (ROOT / "app" / "rag" / "assistant_core.py").read_text(encoding="utf-8"), zip_url))[1]
    namespace = {}
    exec(imports_cell.split("DATA_DIR = data_dir_for_environment()")[0].replace("import faiss\n", ""), namespace)
    return imports_cell, namespace


def test_zip_url_is_written_into_notebook_and_local_run_uses_current_folder():
    imports_cell, namespace = notebook_helpers()
    assert 'DATA_ZIP_URL = "https://drive.google.com/file/d/abc/view"' in imports_cell
    assert "drive.mount" not in "\n".join(code_of(notebook_cells()))
    assert str(namespace["data_dir_for_environment"]()) == "."  # вне Colab


def test_download_data_unpacks_archive(tmp_path, monkeypatch):
    import sys
    import types

    data_dir = tmp_path / "data"
    (data_dir / "prompts" / "ru").mkdir(parents=True)
    for name in ("records_rag_a.jsonl", "records_rag_b1.jsonl"):
        (data_dir / name).write_text("{}", encoding="utf-8")
    (data_dir / "prompts" / "ru" / "messages.json").write_text("{}", encoding="utf-8")
    archive = build_notebook.build_data_zip(data_dir, tmp_path / "stage3_prototype_data.zip")

    def fake_download(url, output, quiet, fuzzy):
        Path(output).write_bytes(archive.read_bytes())
        return output

    monkeypatch.setitem(sys.modules, "gdown", types.SimpleNamespace(download=fake_download))
    _, namespace = notebook_helpers()
    target = tmp_path / "content" / "stage3_prototype"
    result = namespace["download_data"]("https://drive.google.com/file/d/abc/view", target)
    assert result == target
    assert (target / "records_rag_a.jsonl").exists()
    assert (target / "prompts" / "ru" / "messages.json").exists()


def test_download_data_requires_url(tmp_path):
    _, namespace = notebook_helpers(zip_url="")
    import pytest
    with pytest.raises(ValueError):
        namespace["download_data"]("", tmp_path / "empty")
