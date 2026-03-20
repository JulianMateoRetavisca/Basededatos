from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pandas as pd
from flask import Flask, render_template, send_from_directory, request


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs" / "optimizacion"
ANALYSIS_SCRIPT = BASE_DIR / "analisis_optimizacion_gastos.py"


app = Flask(__name__)


def _safe_read_csv(path: Path) -> pd.DataFrame:
	if not path.exists():
		return pd.DataFrame()
	return pd.read_csv(path)


def load_dashboard_data() -> dict:
	comparison = _safe_read_csv(OUTPUT_DIR / "comparativo_escenarios.csv")
	base_detail = _safe_read_csv(OUTPUT_DIR / "solucion_base_detalle.csv")

	top_rows = []
	if not base_detail.empty and "corte_optimo" in base_detail.columns:
		cols = ["codigo", "cuenta", "valor_ajustado", "corte_optimo", "pct_corte_sobre_linea"]
		existing_cols = [c for c in cols if c in base_detail.columns]
		top_rows = (
			base_detail[existing_cols]
			.sort_values("corte_optimo", ascending=False)
			.head(10)
			.to_dict(orient="records")
		)

	memo_text = ""
	memo_path = OUTPUT_DIR / "memorando_tecnico.md"
	if memo_path.exists():
		memo_text = memo_path.read_text(encoding="utf-8")

	return {
		"comparison_rows": comparison.to_dict(orient="records") if not comparison.empty else [],
		"comparison_columns": list(comparison.columns) if not comparison.empty else [],
		"top_rows": top_rows,
		"memo_text": memo_text,
		"has_outputs": OUTPUT_DIR.exists(),
	}


@app.route("/", methods=["GET", "POST"])
def index():
	run_message = ""

	if request.method == "POST":
		try:
			proc = subprocess.run(
				[sys.executable, str(ANALYSIS_SCRIPT)],
				cwd=str(BASE_DIR),
				capture_output=True,
				text=True,
				check=True,
			)
			run_message = f"Analisis ejecutado correctamente.\n{proc.stdout.strip()}"
		except subprocess.CalledProcessError as exc:
			run_message = (
				"Error al ejecutar el analisis.\n"
				f"stdout:\n{exc.stdout}\n\n"
				f"stderr:\n{exc.stderr}"
			)

	data = load_dashboard_data()
	return render_template(
		"index.html",
		run_message=run_message,
		charts=[
			"top_recortes_base.png",
			"comparativo_escenarios.png",
			"precios_sombra_base.png",
		],
		**data,
	)


@app.route("/outputs/<path:filename>")
def outputs(filename: str):
	return send_from_directory(OUTPUT_DIR, filename)


if __name__ == "__main__":
	app.run(debug=True, host="127.0.0.1", port=5000)

