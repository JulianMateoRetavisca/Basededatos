from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import linprog


DATA_FILE = Path("data/estados_financieros_anm_a_diciembre_2021.xls")
OUTPUT_DIR = Path("outputs/optimizacion")


@dataclass
class Scenario:
    name: str
    savings_target_pct: float
    inflation_pct: float
    max_global_cut_pct: float
    group_cut_caps: Dict[str, float]


@dataclass
class SolveResult:
    scenario: Scenario
    success: bool
    status: str
    total_expense: float
    target_value: float
    cut_value: float | None = None
    optimized_budget: float | None = None
    objective_value: float | None = None
    detail: pd.DataFrame | None = None
    constraint_table: pd.DataFrame | None = None


def load_expense_lines(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="Estado de Resultados", header=None)

    data = pd.DataFrame(
        {
            "codigo": raw[0].astype(str).str.strip(),
            "cuenta": raw[1].astype(str).str.strip(),
            "valor_2021": pd.to_numeric(raw[3], errors="coerce"),
            "valor_2020": pd.to_numeric(raw[5], errors="coerce"),
        }
    )

    # Solo se usan lineas de gasto detalladas (ej. 5.1.01, 5.3.60)
    detailed = data[data["codigo"].str.match(r"^5\.\d{1,2}\.\d{2}$", na=False)].copy()
    detailed = detailed[detailed["valor_2021"].notna()]
    detailed = detailed[detailed["valor_2021"] > 0]

    detailed["grupo"] = detailed["codigo"].str.extract(r"^(5\.\d{1,2})")
    detailed["valor_2020"] = detailed["valor_2020"].fillna(0.0)

    return detailed.reset_index(drop=True)


def classify_line(cuenta: str) -> Tuple[float, float]:
    text = cuenta.upper()

    if any(k in text for k in ["SUELDOS", "SALARIOS", "NOMINA", "PRESTACIONES", "APORTES", "CONTRIBUCIONES EFECTIVAS"]):
        return 0.95, 10.0
    if any(k in text for k in ["DETERIORO", "PROVISI", "LITIGIOS"]):
        return 0.90, 8.0
    if "TRANSFERENCIAS" in text:
        return 0.85, 6.0
    if any(k in text for k in ["FINANCIEROS", "COMISIONES", "DIVERSOS"]):
        return 0.70, 3.0
    if "GENERALES" in text:
        return 0.80, 4.0
    return 0.85, 5.0


def enrich_parameters(df: pd.DataFrame) -> pd.DataFrame:
    params = df["cuenta"].apply(classify_line)
    df = df.copy()
    df["min_ratio_operativo"] = params.apply(lambda x: x[0])
    df["peso_impacto"] = params.apply(lambda x: x[1])
    return df


def build_lp_matrices(df: pd.DataFrame, scenario: Scenario) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str], np.ndarray]:
    amounts = df["valor_ajustado"].to_numpy()
    impact = df["peso_impacto"].to_numpy()
    min_ratio = df["min_ratio_operativo"].to_numpy()

    max_cut_by_line = amounts * (1 - min_ratio)

    c = impact
    n = len(df)

    A_ub: List[np.ndarray] = []
    b_ub: List[float] = []
    names: List[str] = []

    target_value = scenario.savings_target_pct * amounts.sum()

    # Restriccion de ahorro minimo: sum(cortes) >= target  ->  -sum(cortes) <= -target
    A_ub.append(-np.ones(n))
    b_ub.append(-target_value)
    names.append("Ahorro minimo")

    # Restriccion global de continuidad operativa
    global_cap = scenario.max_global_cut_pct * amounts.sum()
    A_ub.append(np.ones(n))
    b_ub.append(global_cap)
    names.append("Corte global maximo")

    # Restricciones por grupo funcional
    for group, pct in scenario.group_cut_caps.items():
        selector = (df["grupo"] == group).to_numpy().astype(float)
        if selector.sum() == 0:
            continue
        limit = pct * amounts[selector == 1].sum()
        A_ub.append(selector)
        b_ub.append(limit)
        names.append(f"Corte maximo grupo {group}")

    A_ub_np = np.vstack(A_ub)
    b_ub_np = np.array(b_ub, dtype=float)

    bounds = np.array([(0.0, cap) for cap in max_cut_by_line], dtype=float)

    return c, A_ub_np, b_ub_np, names, bounds


def solve_scenario(base_df: pd.DataFrame, scenario: Scenario) -> SolveResult:
    df = base_df.copy()
    df["valor_ajustado"] = df["valor_2021"] * (1 + scenario.inflation_pct)

    total_expense = float(df["valor_ajustado"].sum())
    target_value = float(total_expense * scenario.savings_target_pct)

    c, A_ub, b_ub, constraint_names, bounds = build_lp_matrices(df, scenario)

    result = linprog(
        c=c,
        A_ub=A_ub,
        b_ub=b_ub,
        bounds=[tuple(x) for x in bounds],
        method="highs",
    )

    if not result.success:
        return SolveResult(
            scenario=scenario,
            success=False,
            status=result.message,
            total_expense=total_expense,
            target_value=target_value,
        )

    cuts = result.x
    df["corte_optimo"] = cuts
    df["presupuesto_optimizado"] = df["valor_ajustado"] - df["corte_optimo"]
    df["pct_corte_sobre_linea"] = np.where(df["valor_ajustado"] > 0, df["corte_optimo"] / df["valor_ajustado"], 0)

    marginals = result.ineqlin.marginals
    slacks = result.ineqlin.residual
    interpretable = []
    for name, value in zip(constraint_names, marginals):
        if name == "Ahorro minimo":
            interpretable.append(-value)
        else:
            interpretable.append(value)

    table = pd.DataFrame(
        {
            "restriccion": constraint_names,
            "rhs": b_ub,
            "holgura": slacks,
            "precio_sombra_modelo": marginals,
            "precio_sombra_interpretable": interpretable,
        }
    )

    return SolveResult(
        scenario=scenario,
        success=True,
        status=result.message,
        total_expense=total_expense,
        target_value=target_value,
        cut_value=float(df["corte_optimo"].sum()),
        optimized_budget=float(df["presupuesto_optimizado"].sum()),
        objective_value=float(result.fun),
        detail=df,
        constraint_table=table,
    )


def objective_coefficient_range(base_df: pd.DataFrame, scenario: Scenario, code: str) -> Tuple[float, float]:
    df = base_df.copy()
    df["valor_ajustado"] = df["valor_2021"] * (1 + scenario.inflation_pct)

    c, A_ub, b_ub, _, bounds = build_lp_matrices(df, scenario)
    base = linprog(c=c, A_ub=A_ub, b_ub=b_ub, bounds=[tuple(x) for x in bounds], method="highs")
    if not base.success:
        return np.nan, np.nan

    idx = df.index[df["codigo"] == code]
    if len(idx) == 0:
        return np.nan, np.nan
    i = int(idx[0])
    base_x = base.x
    base_ci = c[i]

    factors = np.linspace(0.2, 2.5, 80)
    stable = []

    for f in factors:
        c_test = c.copy()
        c_test[i] = base_ci * f
        test = linprog(c=c_test, A_ub=A_ub, b_ub=b_ub, bounds=[tuple(x) for x in bounds], method="highs")
        if not test.success:
            continue

        same_plan = np.allclose(test.x, base_x, atol=1e-3)
        if same_plan:
            stable.append(c_test[i])

    if not stable:
        return np.nan, np.nan

    return float(min(stable)), float(max(stable))


def sensitivity_budget_range(base_df: pd.DataFrame, scenario: Scenario, low: float = 0.01, high: float = 0.30) -> Tuple[float, float]:
    feasible = []
    for pct in np.linspace(low, high, 60):
        trial = Scenario(
            name="tmp",
            savings_target_pct=float(pct),
            inflation_pct=scenario.inflation_pct,
            max_global_cut_pct=scenario.max_global_cut_pct,
            group_cut_caps=scenario.group_cut_caps,
        )
        res = solve_scenario(base_df, trial)
        if res.success:
            feasible.append(pct)

    if not feasible:
        return np.nan, np.nan
    return float(min(feasible)), float(max(feasible))


def save_charts(base_result: SolveResult, scenario_results: List[SolveResult]) -> List[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []

    if base_result.detail is not None:
        top = (
            base_result.detail[["codigo", "cuenta", "corte_optimo"]]
            .sort_values("corte_optimo", ascending=False)
            .head(8)
        )
        plt.figure(figsize=(12, 6))
        plt.barh(top["codigo"] + " " + top["cuenta"].str[:28], top["corte_optimo"] / 1e9)
        plt.gca().invert_yaxis()
        plt.title("Top 8 rubros con mayor recorte optimo (escenario base)")
        plt.xlabel("Recorte (miles de millones COP)")
        plt.tight_layout()
        p1 = OUTPUT_DIR / "top_recortes_base.png"
        plt.savefig(p1, dpi=150)
        plt.close()
        saved.append(p1)

    comp = []
    for res in scenario_results:
        comp.append(
            {
                "escenario": res.scenario.name,
                "factible": "Si" if res.success else "No",
                "meta_pct": res.scenario.savings_target_pct * 100,
                "ahorro_logrado_pct": (res.cut_value / res.total_expense * 100) if (res.success and res.cut_value is not None) else np.nan,
            }
        )

    comp_df = pd.DataFrame(comp)
    plt.figure(figsize=(10, 5))
    bars = plt.bar(comp_df["escenario"], comp_df["meta_pct"], label="Meta de ahorro %")
    achieved = comp_df["ahorro_logrado_pct"].fillna(0)
    plt.scatter(comp_df["escenario"], achieved, color="black", zorder=3, label="Ahorro logrado %")
    for bar, ok in zip(bars, comp_df["factible"]):
        if ok == "No":
            bar.set_hatch("//")
    plt.ylabel("Porcentaje")
    plt.title("Comparativo de escenarios: meta vs ahorro logrado")
    plt.legend()
    plt.tight_layout()
    p2 = OUTPUT_DIR / "comparativo_escenarios.png"
    plt.savefig(p2, dpi=150)
    plt.close()
    saved.append(p2)

    if base_result.constraint_table is not None:
        ct = base_result.constraint_table.copy()
        plt.figure(figsize=(12, 5))
        plt.bar(ct["restriccion"], ct["precio_sombra_interpretable"])
        plt.xticks(rotation=30, ha="right")
        plt.ylabel("Precio sombra")
        plt.title("Precios sombra de restricciones (escenario base)")
        plt.tight_layout()
        p3 = OUTPUT_DIR / "precios_sombra_base.png"
        plt.savefig(p3, dpi=150)
        plt.close()
        saved.append(p3)

    return saved


def build_questionnaire(base_result: SolveResult, budget_range: Tuple[float, float], coef_ranges: pd.DataFrame) -> str:
    if not base_result.success or base_result.constraint_table is None:
        return "No fue posible completar el cuestionario porque el escenario base no fue factible."

    target_row = base_result.constraint_table[base_result.constraint_table["restriccion"] == "Ahorro minimo"]
    shadow = float(target_row["precio_sombra_interpretable"].iloc[0]) if not target_row.empty else np.nan

    return f"""# Cuestionario de Optimización Lineal, Sensibilidad y Dualidad

1. ¿Cuál es la función objetivo del modelo?
Respuesta: Minimizar el costo de impacto operativo total, definido como la suma ponderada de los recortes por rubro.

2. ¿Qué variable de decisión se optimiza?
Respuesta: El recorte monetario por rubro contable (una variable continua por cada código de gasto detallado).

3. ¿Cuál es la interpretación del precio sombra de la restricción de ahorro mínimo?
Respuesta: El precio sombra interpretable estimado es {shadow:.6f}. En términos prácticos, aumentar en 1 COP la meta de ahorro incrementa aproximadamente en {shadow:.6f} unidades el costo de impacto del plan óptimo, manteniendo la base activa.

4. ¿Qué implica el rango factible de meta de ahorro?
Respuesta: Para la estructura actual, el rango aproximado de factibilidad está entre {budget_range[0]*100:.2f}% y {budget_range[1]*100:.2f}% del presupuesto total. Fuera de ese rango, el modelo se vuelve inviable por restricciones operativas.

5. ¿Cómo se interpreta la sensibilidad de coeficientes de la función objetivo?
Respuesta: Los intervalos de optimalidad estimados por perturbación indican en qué rango puede variar el peso de impacto de un rubro sin cambiar el plan óptimo base.

6. ¿Qué aprendizaje de dualidad es clave para la toma de decisiones?
Respuesta: Las restricciones con precio sombra distinto de cero son cuellos de botella reales; por tanto, intervenir su política (por ejemplo, flexibilizar un tope de grupo) tiene efecto económico directo sobre la solución.

## Tabla breve de rangos de optimalidad de coeficientes

{coef_ranges.to_markdown(index=False)}
"""


def build_memorandum(base_df: pd.DataFrame, scenario_results: List[SolveResult], budget_range: Tuple[float, float], coef_ranges: pd.DataFrame, chart_paths: List[Path]) -> str:
    base = scenario_results[0]

    summary_rows = []
    for res in scenario_results:
        summary_rows.append(
            {
                "Escenario": res.scenario.name,
                "Factible": "Si" if res.success else "No",
                "Gasto total (COP)": round(res.total_expense, 2),
                "Meta ahorro (COP)": round(res.target_value, 2),
                "Ahorro optimo (COP)": round(res.cut_value, 2) if res.cut_value is not None else np.nan,
                "Presupuesto optimizado (COP)": round(res.optimized_budget, 2) if res.optimized_budget is not None else np.nan,
                "Costo impacto objetivo": round(res.objective_value, 4) if res.objective_value is not None else np.nan,
                "Estado": res.status,
            }
        )

    summary_df = pd.DataFrame(summary_rows)

    top_reductions_md = "No disponible"
    if base.success and base.detail is not None:
        top_reductions = (
            base.detail[["codigo", "cuenta", "valor_ajustado", "corte_optimo", "pct_corte_sobre_linea"]]
            .sort_values("corte_optimo", ascending=False)
            .head(10)
            .copy()
        )
        top_reductions["valor_ajustado"] = top_reductions["valor_ajustado"].round(2)
        top_reductions["corte_optimo"] = top_reductions["corte_optimo"].round(2)
        top_reductions["pct_corte_sobre_linea"] = (top_reductions["pct_corte_sobre_linea"] * 100).round(2)
        top_reductions_md = top_reductions.to_markdown(index=False)

    shadow_md = "No disponible"
    if base.constraint_table is not None:
        shadow_md = base.constraint_table.round(6).to_markdown(index=False)

    versions_md = pd.DataFrame(
        [
            {
                "Version": "v1.0",
                "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Cambio": "Implementacion inicial: ETL + LP + escenarios + sensibilidad + reporte.",
            }
        ]
    ).to_markdown(index=False)

    chart_list = "\n".join([f"- {p.as_posix()}" for p in chart_paths])

    return f"""# Memorando Tecnico: Modelo de Optimización Presupuestal

## 1. Proposito
Estandarizar un modelo de optimización lineal para analizar la base de gastos de la entidad y evaluar decisiones de ajuste presupuestal bajo distintos escenarios.

## 2. Preparacion de datos
- Fuente: data/estados_financieros_anm_a_diciembre_2021.xls, hoja Estado de Resultados.
- Universo: rubros detallados de gasto con codigos tipo 5.x.xx.
- Transformaciones: limpieza de codigos, conversion numerica, clasificacion por grupo funcional y asignacion de parametros operativos.

## 3. Formulacion del modelo
Variables de decision:
- r_i: recorte en COP para el rubro i.

Funcion objetivo:
- Minimizar sumatoria(impacto_i * r_i).

Restricciones:
- Meta de ahorro minima.
- Tope global de recorte para proteger operacion.
- Topes de recorte por grupo funcional.
- Cotas por rubro segun rigidez operativa.

## 4. Solucion base y escenarios parametricos
{summary_df.to_markdown(index=False)}

## 5. Efectos en factibilidad, costos, operacion y presupuesto
- Factibilidad: determinada por la compatibilidad entre meta de ahorro, topes operativos y capacidad de ajuste por rubro.
- Costo de impacto: medido por la funcion objetivo; menor valor indica menor afectacion operativa para lograr la meta.
- Operacion: controlada por limites por grupo y por linea.
- Presupuesto optimizado: gasto total menos recortes optimos.

## 6. Precios sombra y sensibilidad
### 6.1 Precios sombra (escenario base)
{shadow_md}

### 6.2 Rango de factibilidad de la meta de ahorro
- Minimo aproximado: {budget_range[0]*100:.2f}%
- Maximo aproximado: {budget_range[1]*100:.2f}%

### 6.3 Rangos de optimalidad de coeficientes seleccionados
{coef_ranges.to_markdown(index=False)}

## 7. Implicaciones operativas para decisores no tecnicos
- Las restricciones con precio sombra no nulo son palancas de gestion: flexibilizarlas o endurecerlas tiene impacto economico directo.
- El plan base prioriza recortes en rubros con menor impacto operativo relativo, preservando gasto rigido.
- Metas de ahorro por encima del rango factible exigen redisenar reglas de operacion, no solo "recortar mas".

## 8. Evidencia grafica
{chart_list}

## 9. Registro de versiones
{versions_md}

## 10. Mensaje institucional breve
Con base en el modelo lineal y su sensibilidad, la entidad puede fijar metas de ahorro realistas, identificar limites operativos criticos y justificar tecnicamente ajustes presupuestales con evidencia cuantitativa transparente.

## 11. Top rubros con mayor recorte optimo en escenario base
{top_reductions_md}
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    base_df = load_expense_lines(DATA_FILE)
    base_df = enrich_parameters(base_df)
    base_df.to_csv(OUTPUT_DIR / "gastos_limpios.csv", index=False, encoding="utf-8")

    scenarios = [
        Scenario(
            name="Base (8%)",
            savings_target_pct=0.08,
            inflation_pct=0.00,
            max_global_cut_pct=0.18,
            group_cut_caps={"5.1": 0.10, "5.3": 0.30, "5.4": 0.35, "5.7": 0.45, "5.8": 0.50},
        ),
        Scenario(
            name="Conservador (5%)",
            savings_target_pct=0.05,
            inflation_pct=0.00,
            max_global_cut_pct=0.12,
            group_cut_caps={"5.1": 0.08, "5.3": 0.22, "5.4": 0.28, "5.7": 0.35, "5.8": 0.40},
        ),
        Scenario(
            name="Agresivo (15%)",
            savings_target_pct=0.15,
            inflation_pct=0.00,
            max_global_cut_pct=0.18,
            group_cut_caps={"5.1": 0.10, "5.3": 0.30, "5.4": 0.35, "5.7": 0.45, "5.8": 0.50},
        ),
        Scenario(
            name="Inflacion +12% ahorro",
            savings_target_pct=0.12,
            inflation_pct=0.08,
            max_global_cut_pct=0.16,
            group_cut_caps={"5.1": 0.10, "5.3": 0.25, "5.4": 0.30, "5.7": 0.40, "5.8": 0.45},
        ),
    ]

    results = [solve_scenario(base_df, s) for s in scenarios]

    base_result = results[0]
    if base_result.success and base_result.detail is not None and base_result.constraint_table is not None:
        base_result.detail.to_csv(OUTPUT_DIR / "solucion_base_detalle.csv", index=False, encoding="utf-8")
        base_result.constraint_table.to_csv(OUTPUT_DIR / "solucion_base_sombras.csv", index=False, encoding="utf-8")

    comparison = pd.DataFrame(
        [
            {
                "escenario": r.scenario.name,
                "factible": r.success,
                "estado": r.status,
                "gasto_total": r.total_expense,
                "meta_ahorro": r.target_value,
                "ahorro_optimo": r.cut_value,
                "presupuesto_optimizado": r.optimized_budget,
                "costo_impacto": r.objective_value,
            }
            for r in results
        ]
    )
    comparison.to_csv(OUTPUT_DIR / "comparativo_escenarios.csv", index=False, encoding="utf-8")

    budget_range = sensitivity_budget_range(base_df, scenarios[0])

    # Se evalua intervalo de optimalidad para tres rubros de referencia.
    probe_codes = ["5.1.11", "5.3.47", "5.8.04"]
    coef_data = []
    for code in probe_codes:
        lo, hi = objective_coefficient_range(base_df, scenarios[0], code)
        name_series = base_df.loc[base_df["codigo"] == code, "cuenta"]
        name = name_series.iloc[0] if len(name_series) else "N/A"
        coef_data.append(
            {
                "codigo": code,
                "cuenta": name,
                "coef_min_estable": round(lo, 6) if pd.notna(lo) else np.nan,
                "coef_max_estable": round(hi, 6) if pd.notna(hi) else np.nan,
            }
        )

    coef_ranges = pd.DataFrame(coef_data)
    coef_ranges.to_csv(OUTPUT_DIR / "rangos_optimalidad_coeficientes.csv", index=False, encoding="utf-8")

    charts = save_charts(base_result, results)

    memo = build_memorandum(base_df, results, budget_range, coef_ranges, charts)
    memo_path = OUTPUT_DIR / "memorando_tecnico.md"
    memo_path.write_text(memo, encoding="utf-8")

    questionnaire = build_questionnaire(base_result, budget_range, coef_ranges)
    questionnaire_path = OUTPUT_DIR / "cuestionario_resuelto.md"
    questionnaire_path.write_text(questionnaire, encoding="utf-8")

    print("Analisis completado.")
    print(f"Resultados en: {OUTPUT_DIR.as_posix()}")
    print(f"Memorando: {memo_path.as_posix()}")
    print(f"Cuestionario: {questionnaire_path.as_posix()}")


if __name__ == "__main__":
    main()
