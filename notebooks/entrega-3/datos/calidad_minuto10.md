# Chequeo del dataset al minuto 10

Filas: **19008** · Columnas: **35** · Clave única: **True**

## Cuántas partidas del bronce quedaron afuera, y por qué

| Región | Filas | Sin timeline en bronce | Terminan antes del corte |
|---|---|---|---|
| americas | 12672 | 0 | 93 |
| asia | 3402 | 0 | 28 |
| europe | 2934 | 0 | 16 |

## Los eventos contra el detalle de la partida

Cada evento se cuenta sobre la partida **entera** y se compara con el total que trae el detalle (`teams[].objectives` y los campos de cada jugador). Si una métrica no coincide casi nunca, el evento se está leyendo mal y esa métrica no se usa hasta corregirlo.

| Métrica | Coinciden | Comparadas | % |
|---|---|---|---|
| kills | 16098 | 19008 | 84.7 |
| towers | 19008 | 19008 | 100.0 |
| plates | 62 | 19008 | 0.3 |
| elite_monsters | 19008 | 19008 | 100.0 |
| wards_placed | 5601 | 19008 | 29.5 |
| wards_killed | 15117 | 19008 | 79.5 |
| first_blood | 18967 | 19008 | 99.8 |

## Nulos

```
first_blood_s_m10    0.000053
dtype: float64
```

`first_blood_s_m10` vacío = no hubo primera sangre antes del minuto 10. No es un dato perdido.