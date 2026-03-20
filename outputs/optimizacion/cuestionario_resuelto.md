# Cuestionario de Optimización Lineal, Sensibilidad y Dualidad

1. ¿Cuál es la función objetivo del modelo?
Respuesta: Minimizar el costo de impacto operativo total, definido como la suma ponderada de los recortes por rubro.

2. ¿Qué variable de decisión se optimiza?
Respuesta: El recorte monetario por rubro contable (una variable continua por cada código de gasto detallado).

3. ¿Cuál es la interpretación del precio sombra de la restricción de ahorro mínimo?
Respuesta: El precio sombra interpretable estimado es 4.000000. En términos prácticos, aumentar en 1 COP la meta de ahorro incrementa aproximadamente en 4.000000 unidades el costo de impacto del plan óptimo, manteniendo la base activa.

4. ¿Qué implica el rango factible de meta de ahorro?
Respuesta: Para la estructura actual, el rango aproximado de factibilidad está entre 1.00% y 10.83% del presupuesto total. Fuera de ese rango, el modelo se vuelve inviable por restricciones operativas.

5. ¿Cómo se interpreta la sensibilidad de coeficientes de la función objetivo?
Respuesta: Los intervalos de optimalidad estimados por perturbación indican en qué rango puede variar el peso de impacto de un rubro sin cambiar el plan óptimo base.

6. ¿Qué aprendizaje de dualidad es clave para la toma de decisiones?
Respuesta: Las restricciones con precio sombra distinto de cero son cuellos de botella reales; por tanto, intervenir su política (por ejemplo, flexibilizar un tope de grupo) tiene efecto económico directo sobre la solución.

## Tabla breve de rangos de optimalidad de coeficientes

| codigo   | cuenta                          |   coef_min_estable |   coef_max_estable |
|:---------|:--------------------------------|-------------------:|-------------------:|
| 5.1.11   | GENERALES                       |            3.01266 |            4.9924  |
| 5.3.47   | DETERIORO DE CUENTAS POR COBRAR |            4.16202 |           20       |
| 5.8.04   | FINANCIEROS                     |            0.6     |            3.91899 |
