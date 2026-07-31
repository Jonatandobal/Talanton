# La primera búsqueda real

De cero a la primera tanda de mails. Una tarde de trabajo, sin consola.

## Antes de empezar: 10 minutos de configuración

### 1. Cargá Mi empresa

**Mi empresa** no es cosmética: el ICP que cargues ahí alimenta el 25% del score
—el eje de *fit*— y precarga los filtros de búsqueda. Con esto vacío, el score
puntúa igual a una PyME de 8 personas que a tu cliente ideal.

Lo mínimo:

- **Industrias objetivo**: los rubros donde ya cubriste búsquedas. Si recién
  arrancás, poné dos o tres, no diez.
- **Dotación**: el rango de empresa que te puede pagar un fee. En Argentina,
  para búsquedas de mando medio, algo entre 50 y 800 suele ser realista.
- **Seniority**: qué perfiles cubrís bien. Ahí está tu margen — un analista
  junior lo cubre RRHH publicando un aviso, un jefe de planta no.

### 2. Poné el token de Apify

Es lo que permite buscar empresas por rubro, zona y cantidad de empleados. Se crea
una cuenta en apify.com, se copia el token y se pega en Railway como
`TALANTON_APIFY_TOKEN`. Cuesta unos pocos dólares por corrida de ~1.000 empresas,
**sin abono**.

Sin esto la pantalla de búsqueda te lo va a decir en vez de devolver una lista
vacía, y podés seguir igual **importando una lista propia** —un Excel, una
exportación de tu CRM, contactos de una feria— desde *Más → Importar una lista*.

### 3. Conectá Gmail

En la pantalla de Mi empresa. Sin esto podés cargar leads pero no escribirles desde
acá. Paso a paso en [`gmail.md`](gmail.md).

---

## La búsqueda, paso a paso

### Paso 1 — Elegí un segmento en Buscar empresas

**Buscar empresas** → tres cosas y listo:

| Campo | Qué poner |
|---|---|
| **Zona** | Una provincia o región. Empezá por donde ya tenés red. |
| **Rubro** | **Uno solo**, el que mejor conocés. Es lo más importante de todo esto y explico por qué abajo. |
| **Empleados desde/hasta** | Viene precargado de tu ICP. Para búsquedas de mando medio, 50 a 500 suele ser realista. |

Eso define **a quién le podés vender**, y con eso alcanza para salir a contactar.

Debajo hay un tilde, **«sólo las que tengan una búsqueda abierta»**, que viene
apagado. Dejalo apagado la primera vez. Encenderlo es decir *«hoy quiero atacar
sólo lo caliente»*: trae bastante menos volumen, pero cada mail abre con un dato
concreto.

Es la regla que ordena todo: **la empresa es el lead, el aviso es la excusa**. Que
una empresa tenga una búsqueda estirada hace 45 días es el mejor momento para
escribirle —es una búsqueda que no está pudiendo cerrar sola— pero no tenerla no la
saca de tu mercado.

Ojo con una cosa cuando enciendas el tilde: los portales no siempre informan la
fecha, y un aviso sin fecha no cuenta como viejo. Es a propósito — suponer la
antigüedad sería inventarla, y ese número termina en un mail al cliente.

### Paso 2 — Revisá y traé

Sale una tabla de empresas: nombre, rubro, cantidad de empleados, ciudad, y una
columna **Señal** que muestra la búsqueda abierta cuando la hay y los días que
lleva. Primero las que tienen señal, después el resto. Todo viene tildado:
destildá lo que no te sirva y apretá **Traer como leads**.

Dos cosas ya no van a estar en esa lista porque se descartan solas:

- **Consultoras de selección** — son competencia, no clientes.
- **Avisos perennes** («Postulación espontánea», «Sumate a nuestro equipo») — no
  son búsquedas, son buzones de CV. Nunca se cierran, así que acumularían días
  para siempre y harían creer que la empresa está desesperada.

Abajo de la tabla, **Qué pasó detrás** cuenta cuántas trajo cada fuente y cuántas
se descartaron por cada motivo.

Si la columna **Señal** viene vacía en todas, no quiere decir que nadie esté
publicando: puede ser que los portales de avisos estén rotos.
`/buscar/diagnostico` lo dice con todas las letras — qué URL se consultó, qué
devolvió y qué selector dejó de matchear.

### Paso 3 — Conseguí los contactos

Volvé al **Panel**. Las empresas que quedaron sin mail aparecen en **Falta el
contacto**, con un botón que las busca de verdad: primero en la web de la empresa
(gratis y sin tope) y después en Hunter si lo tenés configurado (25 búsquedas
gratis por mes).

Lo que no salga de ahí se carga a mano en la ficha del lead. Detalle en
[`contactos.md`](contactos.md).

### Paso 4 — Escribí, pero no a todos

Andá a **Leads**, ordenado por score, o directamente al **Panel**, que ya te lo da
en orden y con un botón por fila.

**Arriba van a estar los que tienen más señal**: la búsqueda más estirada, varias
en simultáneo, un puesto que se repite. El borrador abre solo, con el dato concreto
de cada uno.

El tope de envío es de **40 por casilla y por día**, y no conviene subirlo.

### Paso 5 — Dejalas vigiladas y repetí

Las empresas que trajiste quedan en la base, así que la corrida diaria empieza a
contar los días de cada búsqueda **desde hoy**. Repetir la búsqueda la semana que
viene no las duplica: suma la observación nueva y, si un aviso reaparece después de
haberse cerrado, lo cuenta como reposteo —que es la señal más fuerte que maneja el
sistema—.

---

## Si el rubro es IT

Es el de más volumen en Argentina y también el más peleado: casi toda empresa de
IT tiene reclutamiento interno, y eso baja el eje de accesibilidad del score. No
lo descarta, pero cambia el ángulo.

**Lo que no vas a vender**: el perfil que el equipo interno cubre publicando en
LinkedIn. Un Semi Senior de React entra solo.

**Lo que sí**: el que el equipo interno viene intentando hace tres meses. Suele
ser una de estas cuatro formas:

- **Seniority alto en carrera técnica** — Staff, Principal, Arquitecto, Tech Lead.
- **Stack viejo o de nicho** — COBOL, mainframe, SAP ABAP, .NET Framework,
  Salesforce, Oracle. El mercado es chico y el equipo interno no tiene red ahí.
- **Perfiles híbridos** — Data Engineer con dominio de negocio, SRE con
  seguridad, especialista en ciberseguridad.
- **Fuera de Buenos Aires**, con presencialidad o hibridez obligatoria.

Por eso el tramo que conviene es **50 a 500 empleados**: por debajo de 50 no hay
presupuesto para un fee, y por encima de 500 hay un equipo de selección interno que
compite con vos por el mandato. El score ya hunde a las empresas muy grandes por ese
motivo, y lo dice con todas las letras en las razones del lead.

Talanton entiende el vocabulario de IT en los dos idiomas: «Ingeniero DevOps» y
«DevOps Engineer» cuentan como el mismo puesto —si no, un reposteo se vería como
dos búsquedas distintas— y «Tech Lead» pesa como jefatura, no como un título
suelto sin categoría.

---

## Por qué un rubro por vez

Es la parte que más rinde y la que más se saltea.

Con 50 empresas de un mismo rubro y una misma zona, tu mail puede decir algo que
sólo alguien de ese rubro diría. «Sabemos lo que cuesta conseguir un jefe de mantenimiento
industrial en el interior» le habla a una persona. «Ofrecemos servicios de
selección» no le habla a nadie.

Además, cuando mandes las 50 vas a poder leer el resultado: si respondieron
cuatro, aprendiste algo del rubro. Si mandaste 50 mails a doce rubros distintos y
respondieron cuatro, no aprendiste nada.

Y cuando encuentres el rubro que responde, ahí sí escalás.

---

## Qué esperar, con números honestos

- De 50 mails fríos **sin señal**, con un mensaje decente: entre 2 y 5 respuestas.
- De 50 mails **con señal concreta** —«hace 92 días que buscan esto y ya lo
  republicaron»—: bastante más, y sobre todo mejores. La conversación arranca en
  otro lado.
- Una parte de los mails va a rebotar. Es normal en cualquier base.

La primera tanda es tanto para aprender como para vender. Anotá en el lead qué
contestaron, aunque sea que no: eso es lo que después recalibra el score con datos
tuyos y no con mi intuición.

---

## La semana que viene

Cuando la corrida diaria lleve unos días, **Avisos** va a mostrar búsquedas con
días acumulados de verdad. Ahí el producto empieza a hacer lo suyo: el panel te
muestra solo las que se están estirando, y el mail se escribe casi solo.

Ese es el activo. Una lista de contactos la compra cualquiera; saber que una
búsqueda lleva 92 días abiertos requiere haber estado mirando desde antes.

Por eso el orden de estos pasos importa: **traer empresas y dejarlas vigiladas hoy**
vale más que mandar los 50 mails hoy.

---

## Cuánto cuesta esto

| Qué | Costo |
|---|---|
| Railway (web + Postgres + cron) | Entra en el crédito de US$5/mes del plan Hobby |
| Apify (buscar empresas) | ~US$3-5 por corrida de ~1.000 empresas, **sin abono** |
| Portales de empleo argentinos | Gratis |
| Buscar mails en la web de la empresa | Gratis, sin tope |
| Hunter.io | Gratis, 25 búsquedas/mes |
| Asistente (Claude) | Opcional, centavos por lectura de lead |

Nada de esto tiene abono mensual salvo Railway. Apify se paga por corrida: si un mes
no buscás empresas nuevas, no gastás.
