# Chequeo del dataset al minuto 5

Filas: **19145** · Columnas: **35** · Clave única: **True**

## Cuántas partidas del bronce quedaron afuera, y por qué

| Región | Filas | Sin timeline en bronce | Terminan antes del corte |
|---|---|---|---|
| americas | 12765 | 0 | 0 |
| asia | 3430 | 0 | 0 |
| europe | 2950 | 0 | 0 |

## Los eventos contra el detalle de la partida

Cada evento se cuenta sobre la partida **entera** y se compara con el total que trae el detalle (`teams[].objectives` y los campos de cada jugador). Si una métrica no coincide casi nunca, el evento se está leyendo mal y esa métrica no se usa hasta corregirlo.

| Métrica | Coinciden | Comparadas | % |
|---|---|---|---|
| kills | 16227 | 19145 | 84.8 |
| towers | 19145 | 19145 | 100.0 |
| plates | 108 | 19145 | 0.6 |
| elite_monsters | 19145 | 19145 | 100.0 |
| wards_placed | 5662 | 19145 | 29.6 |
| wards_killed | 15242 | 19145 | 79.6 |
| first_blood | 19103 | 19145 | 99.8 |

## Nulos

```
first_blood_s_m5    0.01217
dtype: float64
```

`first_blood_s_m5` vacío = no hubo primera sangre antes del minuto 5. No es un dato perdido.