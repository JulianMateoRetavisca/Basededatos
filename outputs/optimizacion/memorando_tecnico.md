# Memorando Tecnico: Modelo de Optimización Presupuestal

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
| Escenario             | Factible   |   Gasto total (COP) |   Meta ahorro (COP) |   Ahorro optimo (COP) |   Presupuesto optimizado (COP) |   Costo impacto objetivo | Estado                                                                                         |
|:----------------------|:-----------|--------------------:|--------------------:|----------------------:|-------------------------------:|-------------------------:|:-----------------------------------------------------------------------------------------------|
| Base (8%)             | Si         |         1.9372e+11  |         1.54976e+10 |           1.54976e+10 |                    1.78223e+11 |              6.04689e+10 | Optimization terminated successfully. (HiGHS Status 7: Optimal)                                |
| Conservador (5%)      | Si         |         1.9372e+11  |         9.68601e+09 |           9.68601e+09 |                    1.84034e+11 |              3.72225e+10 | Optimization terminated successfully. (HiGHS Status 7: Optimal)                                |
| Agresivo (15%)        | No         |         1.9372e+11  |         2.9058e+10  |         nan           |                  nan           |            nan           | The problem is infeasible. (HiGHS Status 8: model_status is Infeasible; primal_status is None) |
| Inflacion +12% ahorro | No         |         2.09218e+11 |         2.51061e+10 |         nan           |                  nan           |            nan           | The problem is infeasible. (HiGHS Status 8: model_status is Infeasible; primal_status is None) |

## 5. Efectos en factibilidad, costos, operacion y presupuesto
- Factibilidad: determinada por la compatibilidad entre meta de ahorro, topes operativos y capacidad de ajuste por rubro.
- Costo de impacto: medido por la funcion objetivo; menor valor indica menor afectacion operativa para lograr la meta.
- Operacion: controlada por limites por grupo y por linea.
- Presupuesto optimizado: gasto total menos recortes optimos.

## 6. Precios sombra y sensibilidad
### 6.1 Precios sombra (escenario base)
| restriccion            |          rhs |     holgura |   precio_sombra_modelo |   precio_sombra_interpretable |
|:-----------------------|-------------:|------------:|-----------------------:|------------------------------:|
| Ahorro minimo          | -1.54976e+10 | 0           |                     -4 |                             4 |
| Corte global maximo    |  3.48696e+10 | 1.9372e+10  |                     -0 |                            -0 |
| Corte maximo grupo 5.1 |  1.56507e+10 | 1.63525e+09 |                     -0 |                            -0 |
| Corte maximo grupo 5.3 |  7.01498e+09 | 7.01498e+09 |                     -0 |                            -0 |
| Corte maximo grupo 5.4 |  2.59667e+09 | 2.59667e+09 |                     -0 |                            -0 |
| Corte maximo grupo 5.7 |  1.25983e+07 | 1.25983e+07 |                     -0 |                            -0 |
| Corte maximo grupo 5.8 |  3.19121e+09 | 1.70909e+09 |                     -0 |                            -0 |

### 6.2 Rango de factibilidad de la meta de ahorro
- Minimo aproximado: 1.00%
- Maximo aproximado: 10.83%

### 6.3 Rangos de optimalidad de coeficientes seleccionados
| codigo   | cuenta                          |   coef_min_estable |   coef_max_estable |
|:---------|:--------------------------------|-------------------:|-------------------:|
| 5.1.11   | GENERALES                       |            3.01266 |            4.9924  |
| 5.3.47   | DETERIORO DE CUENTAS POR COBRAR |            4.16202 |           20       |
| 5.8.04   | FINANCIEROS                     |            0.6     |            3.91899 |

## 7. Implicaciones operativas para decisores no tecnicos
- Las restricciones con precio sombra no nulo son palancas de gestion: flexibilizarlas o endurecerlas tiene impacto economico directo.
- El plan base prioriza recortes en rubros con menor impacto operativo relativo, preservando gasto rigido.
- Metas de ahorro por encima del rango factible exigen redisenar reglas de operacion, no solo "recortar mas".

## 8. Evidencia grafica
- outputs/optimizacion/top_recortes_base.png
- outputs/optimizacion/comparativo_escenarios.png
- outputs/optimizacion/precios_sombra_base.png

## 9. Registro de versiones
| Version   | Fecha               | Cambio                                                                  |
|:----------|:--------------------|:------------------------------------------------------------------------|
| v1.0      | 2026-03-15 20:15:27 | Implementacion inicial: ETL + LP + escenarios + sensibilidad + reporte. |

## 10. Mensaje institucional breve
Con base en el modelo lineal y su sensibilidad, la entidad puede fijar metas de ahorro realistas, identificar limites operativos criticos y justificar tecnicamente ajustes presupuestales con evidencia cuantitativa transparente.

## 11. Top rubros con mayor recorte optimo en escenario base
| codigo   | cuenta                                       |   valor_ajustado |   corte_optimo |   pct_corte_sobre_linea |
|:---------|:---------------------------------------------|-----------------:|---------------:|------------------------:|
| 5.1.11   | GENERALES                                    |      1.1717e+11  |    1.39761e+10 |                   11.93 |
| 5.8.04   | FINANCIEROS                                  |      4.53374e+09 |    1.36012e+09 |                   30    |
| 5.8.90   | GASTOS DIVERSOS                              |      3.98762e+08 |    1.19629e+08 |                   30    |
| 5.1.08   | GASTOS DE PERSONAL DIVERSOS                  |      1.31298e+08 |    3.93893e+07 |                   30    |
| 5.8.02   | COMISIONES                                   |      7.92e+06    |    2.376e+06   |                   30    |
| 5.1.01   | SUELDOS Y SALARIOS                           |      2.25892e+10 |    0           |                    0    |
| 5.1.07   | PRESTACIONES SOCIALES                        |      8.46583e+09 |    0           |                    0    |
| 5.1.04   | APORTES SOBRE LA NÓMINA                      |      1.23639e+09 |    0           |                    0    |
| 5.1.03   | CONTRIBUCIONES EFECTIVAS                     |      6.48858e+09 |    0           |                    0    |
| 5.3.60   | DEPRECIACIÓN DE PROPIEDADES, PLANTA Y EQUIPO |      5.35838e+09 |    0           |                    0    |
