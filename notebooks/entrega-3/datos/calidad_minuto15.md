# Chequeo del dataset al minuto 15

Filas: **18878** · Columnas: **35** · Clave única: **True**

## Cuántas partidas del bronce quedaron afuera, y por qué

| Región | Filas | Sin timeline en bronce | Terminan antes del corte |
|---|---|---|---|
| americas | 12572 | 0 | 193 |
| asia | 3390 | 0 | 40 |
| europe | 2916 | 0 | 34 |

## Los eventos contra el detalle de la partida

Cada evento se cuenta sobre la partida **entera** y se compara con el total que trae el detalle (`teams[].objectives` y los campos de cada jugador). Si una métrica no coincide casi nunca, el evento se está leyendo mal y esa métrica no se usa hasta corregirlo.

| Métrica | Coinciden | Comparadas | % |
|---|---|---|---|
| kills | 15983 | 18878 | 84.7 |
| towers | 18878 | 18878 | 100.0 |
| plates | 50 | 18878 | 0.3 |
| elite_monsters | 18878 | 18878 | 100.0 |
| wards_placed | 5563 | 18878 | 29.5 |
| wards_killed | 15000 | 18878 | 79.5 |
| first_blood | 18837 | 18878 | 99.8 |

## Nulos

```
Ninguna columna tiene nulos.
```

`first_blood_s_m15` vacío = no hubo primera sangre antes del minuto 15. No es un dato perdido.