Ciencia de Datos: Consigna TP4 | Campus 
Descargado del campus (curso Ciencia de Datos, Unidad 4) el 2026-11-10. 

TP 4 · Una pregunta, un póster. Individual. Se presenta el miércoles 21 de octubre y se entrega por campus hasta el domingo 1 de noviembre a las 23:59. La votación de los pósters es en la clase del miércoles 4 de noviembre, en el primer bloque, antes del parcial. 
Hoy cualquier herramienta arma un gráfico prolijo en segundos. Lo que no hace sola es decidir: qué mostrar, a quién dejar afuera, en qué escala, contra qué comparar. Eso es lo que evalúa este TP. Cada una de las diez preguntas de abajo tiene una lectura obvia que los datos desmienten o matizan. El trabajo es encontrarla, medirla y contarla en un póster que cualquiera entienda sin leer tu notebook. 
### De dónde arrancás 

 | Notebook | Qué te deja 
 | Unidad 4 - Practica.ipynb | La gramática de Altair y un póster resuelto sobre una pregunta que no está en esta lista. 
El dataset es el canónico de siempre. Si no lo tenés, esta celda lo baja la primera vez: import os ARCHIVO = "fifa_canonico_2026-07-23.csv" ID_DRIVE = "1cF30_fSvxNKpK5-AKJlzUqLHZTTUf0ls" if not os.path.exists(ARCHIVO): !gdown $ID_DRIVE -O $ARCHIVO 
### Las preguntas 
Diez preguntas en cinco ejes. Elegís dos de ejes distintos. 

 | Eje | Preguntas 
 | 1 · Posición, rol y atributos técnicos | P1. ¿Los jugadores se reparten equitativamente entre todas las posiciones?
P2. ¿Qué atributos técnicos tienen mayor influencia en el valor de mercado? 
 | 2 · País, nacionalidad y geografía | P3. ¿Hay países que realmente dominen la escena futbolística?
P4. ¿Qué países parecen producir mejores arqueros? 
 | 3 · Físico y condición atlética | P5. ¿Qué tan distinta es la estatura entre posiciones defensivas y ofensivas?
P6. ¿Qué tan frecuente es encontrar jugadores con mucha técnica y mucha fuerza a la vez? 
 | 4 · Valor de mercado, salario y contratos | P7. ¿A qué edad empieza a notarse una brecha importante en los salarios?
P8. ¿Los jugadores más valiosos tienen contratos más cortos? 
 | 5 · Edad, carrera y potencial | P9. ¿Qué tan concentrado está el talento joven en unos pocos clubes?
P10. ¿Hay alguna posición donde los jugadores lleguen a su pico más tarde? 
### Qué se pide 
Por cada pregunta que elegís, un póster: una sola figura que responde la pregunta. El póster tiene que mostrar la lectura obvia y lo que la desarma, su título afirma la respuesta —no repite la pregunta— y declara qué hiciste con los datos: qué filtraste, qué agregaste y cuántos jugadores quedaron. La forma es tuya. 
### Las reglas 
- 
Todo en Altair, en una sola figura. El PNG que entregás es el que sale de chart.save(). Nada de Canva, Figma, PowerPoint ni imágenes pegadas: un póster editado fuera de Altair no es válido. 
- 
Sólo el dataset canónico. Los datos se preparan con pandas o con las transformaciones de Altair, a tu elección, siempre dentro del notebook. 
- 
El notebook corre de punta a punta: desde bajar el archivo hasta guardar el PNG. 
- 
Dos pósters obligatorios, de preguntas de ejes distintos. Podés entregar más, de otras pregunta, para tener más chances en la votación; se cuentan tus dos mejores resultados. 
- 
Es individual. Dos pósters con la misma construcción se tratan como copia. 
- 
Podés usar la herramienta que quieras para escribir código. Las decisiones —qué filtrar, qué comparar, en qué escala— tienen que estar medidas en tu notebook. Un póster sin esa medición no es válido, por más lindo que se vea. 
### Qué se entrega 
Por cada póster, dos archivos: el notebook y el PNG, con el mismo nombre: comisión, apellido y número de pregunta. Por ejemplo, TP4_5K09_Perez_P06.ipynb y TP4_5K09_Perez_P06.png. Todos los archivos van juntos en la tarea «Entrega TP4». 
El notebook de cada póster sigue este orden: 
- Una celda de texto con tu comisión, tu nombre y la pregunta. 
- La medición: las cuentas que muestran la trampa, con sus números. 
- La versión ingenua: el primer gráfico, tal como salió. 
- El póster: la celda que arma la figura completa y la guarda en PNG. 
- Un párrafo final con la respuesta y la decisión que separa la versión ingenua del póster: qué componente cambiaste y qué dato te llevó a cambiarlo
Los notebooks se suben sin salidas. En Colab: «Editar → Borrar todas las salidas», y después «Archivo → Descargar → Descargar .ipynb». Cada gráfico de Altair guarda sus datos adentro de la salida, y con las salidas puestas un notebook puede pasar el límite de 20 MB por archivo de la tarea. No se pierde nada: para corregir, el notebook se vuelve a correr de punta a punta.

### La votación — miércoles 4 de noviembre 
Cada comisión vota por separado. La cátedra elige hasta tres finalistas por pregunta en cada comisión, y se presentan sin nombre, con una letra. La clase recorre las diez preguntas, y en cada una: 
- Se proyectan los finalistas y se vota desde el celular, en la consulta de esa ronda. Está abierta un minuto. 
- Se muestra el ganador y quién lo hizo. 
- La cátedra explica por qué esos pósters llegaron a la final. 
Si hay empate, ganan los dos. Podés votar en la ronda de tu propia pregunta. Si no tenés celular, votás desde la compu de un compañero, con tu usuario. 
### Cómo se va a evaluar 

 | Parte | Puntos 
 | Dos pósters válidos, de ejes distintos | 25 cada uno 
 | Votación: un punto por cada ronda en la que votaste | hasta 10 
 | Por cada póster finalista | +15 
 | Por cada pregunta ganada, en lugar del +15 | +20 
La nota tiene un tope de 100 y se aprueba con 60. Con dos pósters válidos y la votación completa llegás a 60; un finalista lleva a 75, y dos preguntas ganadas, a 100. 
Si en tu comisión hay menos de diez rondas, los 10 puntos de la votación se reparten entre las que haya. 
Un póster es válido si cumple todo esto: 

 | Se verifica | Cómo 
 | Que corra | El notebook corre entero desde cero y produce el PNG entregado. 
 | Que sea Altair | El PNG sale de una sola figura de Altair, sin edición posterior. 
 | Que la trampa esté medida | Hay en el notebook al menos un número que muestra por qué la lectura ingenua no alcanza. 
 | Que la trampa esté en el póster | Se ve en el póster, no sólo en el texto del notebook. 
 | Que el título responda | El título afirma una respuesta; no repite la pregunta. 
 | Que los ejes sean distintos | Tus dos pósters obligatorios son de ejes distintos. 
Un póster que no es válido se puede rehacer una vez, hasta el domingo 8 de noviembre a las 23:59. Cuenta para los 25 puntos, pero ya no compite. 
Para elegir finalistas se mira, en este orden: si la trampa está detectada y desarmada; si cada parte del póster agrega algo; si se entiende sin leer el notebook; y si colores y escalas significan lo mismo en todo el póster. Lo prolijo desempata, pero no clasifica. 
Lo que practicás acá —contar con datos una historia que no es la obvia— es lo que la Entrega 4 del Integrador te pide sobre tus propios datos, con interactividad. 
Si te trabás, preguntá en el foro de Consultas. Las preguntas sobre las reglas se contestan para todos; las de cuál es la trampa, no.
Última modificación: miércoles, 21 de octubre de 2026, 14:12
