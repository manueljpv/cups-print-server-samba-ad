# Roadmap

[Português](ROADMAP.md) · [English](ROADMAP.en.md) · **Español (Honduras)**

Este documento muestra hacia dónde puede ir el proyecto y lo que hemos aprendido hasta ahora. Nada de lo que sigue es una promesa de fechas: son intenciones, en orden aproximado de prioridad. Las sugerencias son bienvenidas mediante *issues*.

## Completado recientemente

- **Cambio controlado de la contraseña de la cuenta de máquina.** La causa del incidente de winbind se confirmó por reproducción y el cambio automático de Samba se sustituyó por un cambio programado, con reinicio de winbind, cuatro pruebas y un estado en JSON. Vea el [doc 06](docs/06-troca-controlada-winbind.md) (en portugués).
- **Panel web interno** con inicio de sesión del AD (LDAPS), sesiones y acceso por grupo: una página de **control de winbind**, una de **permisos de impresión** (solo lectura, por usuario, departamento, impresora y equipo) y una alerta para una pantalla de pared. Vea el [doc 07](docs/07-painel-web.md) (en portugués).
- **Varias impresoras en el registro del panel**, con grupos de acceso, de color y de equipos por impresora, con el patrón `Impressora_<Marca>_<Lugar>`.

## Corto plazo

**Contabilidad y reportes**

- **Reporte mensual.** Leer `contagem-AAAA-MM.log` y generar el total por impresora, por departamento y por usuario, separando blanco y negro de color y aplicando las tarifas por cara del contrato. El reporte debe tratar las columnas 10 a 12 del registro como opcionales, ignorar en la suma las líneas `rejeitado-sem-pin` y no leer los archivos `.teste.log`.
- **Grupos por departamento en el AD.** Hoy solo existen grupos de acceso y de color por impresora. Sin grupos por departamento, el reporte por departamento no se puede completar.
- **Panel de control web (HTML).** Una página accesible desde el navegador, con el conteo de impresiones siempre **mensual**, para conservar el historial y poder comparar meses y años. Muestra el total de la empresa y el total **por impresora, por departamento y por persona** (blanco y negro x color); para cada persona, lo que imprimió, con el **nombre de los archivos**, día y hora; y una vista mes a mes para hacer comparativos. Incluye una lista de los trabajos rechazados por falta de PIN, ya que el puerto RAW no puede avisar al usuario en pantalla.
- **Panel: etapa 2 y página de impresiones.** Botones que modifican los grupos del AD mediante una cuenta delegada (solo la pertenencia a los grupos `Impressora_*`), con auditoría de quién, cuándo y qué; cruce con el inventario (GLPI) para confirmar qué equipo es de cada usuario; revisión de accesos (quién tiene color y nunca imprimió a color, quién no imprime hace 90 días); y la página de control de impresiones (reportes, costos, franquicia), que hoy es solo un esqueleto.
- **Verificación de uso personal.** Señalar, a partir del nombre de los archivos, las impresiones que parezcan personales (por ejemplo, mediante palabras y patrones configurables), para **revisión humana**, sin bloquear la impresión. Como esto involucra el nombre de los documentos de cada persona, restrinja el acceso al panel y a los datos de contabilidad a quienes lo necesitan, y deje clara la política de impresión a los usuarios (revise también los requisitos de privacidad aplicables, como las leyes de protección de datos).
- **Costos y franquicia en el panel.** Como las impresoras son alquiladas, cada página tiene un costo. El panel debe permitir registrar, **por impresora**, el precio de la página en blanco y negro y el de la página a color (que pueden variar de una impresora a otra) y calcular el costo de cada mes: por impresora, **por departamento** (base para un posible prorrateo) y por persona. Los contratos suelen incluir una **franquicia**: por ejemplo, la Xerox puede imprimir hasta 1,000 páginas a color a un precio, y a partir de la 1,001 el valor sube. El panel debe registrar la franquicia y el precio excedente por impresora y por color, mostrar un **contador del consumo de la franquicia en el mes** (cuánto se ha usado y cuánto queda) y avisar cuando el consumo se acerque al límite. Guarde las tarifas **con fecha de vigencia**, para que los meses anteriores no cambien cuando cambie el contrato, y defina cómo se prorratea el costo excedente entre departamentos. Revise en el contrato si la franquicia es por impresora, por color o compartida. Mientras no se confirme con los contadores de la propia impresora, el conteo del servidor es una estimación (se hace al enviar, y los trabajos cancelados se siguen contando).
- **Hacer que el filtro informe `PAGE: total N` a CUPS**, para que el `page_log` sea coherente con la contabilidad propia (hoy muestra `total 0` en las colas con filtro).
- **Confirmar dos puntos del driver y del contrato:** si el ID del trabajo (`JobIdBannerOn`) genera una hoja extra en algún escenario, y cómo cobra la empresa arrendadora cada modo de color (incluyendo un posible modo automático).

**Servidor**

- **Registrar las demás impresoras** (otras Canon y una HP). Para cada una: cola `lugar-marca`, receptor en otro puerto, entrada en el mapa de color y una línea más en `impressoras.json`. Antes de reutilizar el filtro, probar qué escribe el driver de cada marca en el archivo del trabajo. Ya constan en el registro de impresoras del panel; faltan la cola, el receptor, el driver y la entrega por GPO.
- **Pruebas automatizadas del filtro y del receptor** con muestras de trabajo sintéticas (blanco y negro, color, con y sin PIN, usuario dentro y fuera del grupo de color), para validar sin impresora y sin gastar papel.
- **Rutina de respaldo de SYSVOL** (con permisos) antes de actualizar Samba, sobre todo si se instaló desde un tarball.

**GPO y clientes Windows**

- **Ampliar el piloto por fases.** Hoy el alcance es el equipo de TI, filtrado por un grupo de equipos. Ampliar a otros departamentos agregando equipos al grupo, después de validar con cada equipo de trabajo.
- **Limpiar conexiones por usuario.** El script se ejecuta como `SYSTEM` y solo ve las impresoras de la máquina; las conexiones del contexto del usuario (`\\servidor\cola`, `http://...`) permanecen. Una versión futura debe limpiar `HKU\<SID>\Printers\Connections` del usuario con sesión iniciada.
- **Limpiar lo heredado.** Borrar el grupo antiguo, la carpeta del driver PCL6 y los scripts antiguos de la GPO anterior en `NETLOGON`.
- **Desactivar `JobIdBannerOn` en el valor predeterminado del driver, por precaución**, después de descubrir la clave de "apagado" comparando el print ticket antes y después.
- **Probar en una PC realmente limpia**, sin la "Internet Port" fantasma que quedó atascada en la PC de prueba.
- **Puesta en producción.** Archivar y reiniciar el registro de pruebas para comenzar la contabilidad limpia (vea el [doc 04](docs/04-problemas-comuns.md), en portugués).

## Largo plazo

- **Autenticación en el panel de la impresora mediante LDAP/Kerberos contra Samba AD**, eliminando la necesidad del PIN e identificando al dueño de cada trabajo. Es el "as bajo la manga" del proyecto: requiere muchas pruebas y no puede fallar. Probarla en una cola aparte, sin tocar la cola que ya funciona, y avisar a la empresa arrendadora antes de tocar la impresora alquilada. El usuario del trabajo debe coincidir con el inicio de sesión del dominio, y hay que confirmar la compatibilidad LDAP de Samba AD (bind, LDAPS, certificado).
- **Validar el usuario del trabajo.** Hoy el nombre viene de Windows y el servidor no lo valida. La autenticación anterior lo resolvería desde el origen.
- **Conteo a la salida del papel.** Hoy el conteo se hace al enviar, así que un trabajo cancelado después se sigue contando. Conciliar con los contadores de la propia impresora (SNMP o contabilidad de Xerox) para verificar la factura de la arrendadora.
- **Dejar las colas raw y los drivers PPD**, que CUPS marca como obsoletos y dejarán de funcionar en una versión futura (CUPS 3.x). Evaluar una arquitectura que conserve el PIN y el conteo sin depender de ellos.
- **Una página para agregar y quitar impresoras en el panel.** Es una parte sensible que necesita su propio planeamiento, sobre todo para tratar el **driver** de cada impresora.
- **Panel en una pantalla dedicada** (por ejemplo, una laptop Linux con el navegador mostrando varios paneles), para que los avisos se vean sin depender de que alguien abra la página.
- **Más marcas de impresora**, con un filtro que entienda el encabezado de cada driver.
- **Empaquetado y automatización** de la instalación del servidor (script o Ansible), para reproducir el ambiente más rápido.
- **Traducir la carpeta `docs/`** al inglés y al español de Honduras.

## Lecciones aprendidas

1. **Pruebe antes de elegir la arquitectura.** Tres colas de prueba con el mismo PDF mostraron que ninguna servía por sí sola: la IPP cuenta pero pierde el PIN, y la raw conserva el PIN pero cuenta 1 por trabajo. La solución (un filtro) solo apareció después de ver lo que cada camino realmente entregaba.
2. **Abra el archivo del trabajo.** Activar `PreserveJobFiles` por un momento e inspeccionar el archivo reveló que el driver ya incrusta el PIN, el color, la doble cara y el usuario en un encabezado XML. Todo lo que el reporte necesitaba estaba ahí, sin depender de atributos IPP que Windows no envía.
3. **Entienda el contrato antes de contar.** El alquiler cobra por cara, no por hoja. Eso definió lo que cuenta el filtro (páginas x copias) y quitó la preocupación por la doble cara predeterminada del driver.
4. **La herramienta de prueba debe representar el camino real.** `cupsfilter` en la línea de comandos no reproduce la cadena de filtros de `cupsd`. Una cola de prueba con `socket://127.0.0.1:...`, un `nc` capturando la salida y `lp` reproducen lo que realmente ocurre, sin gastar papel.
5. **Busque la causa raíz.** El trabajo de un usuario salía con 40 páginas de código porque CUPS lo clasificó como `text/plain` (la regla de PostScript solo mira los primeros ~128 bytes) y descartó el encabezado. Dos líneas `*cupsFilter` en el PPD lo resolvieron; cambiar el driver no lo habría hecho.
6. **Registre lo que se pidió y lo que salió.** Guardar el color solicitado, el color efectivo y una nota por trabajo permitió distinguir "el usuario pidió blanco y negro" de "el servidor forzó blanco y negro" cuando todos los usuarios empezaron a salir en blanco y negro.
7. **Las dependencias de identidad necesitan monitoreo.** El cambio automático de la contraseña de la cuenta de máquina, 7 días después de unirse al dominio, dejó a winbind sin ver los grupos. El fallo fue silencioso y parecía un problema de color. Los eventos periódicos como este merecen un aviso. Esto se resolvió con el cambio controlado (vea el [doc 06](docs/06-troca-controlada-winbind.md)).
8. **Falle de forma segura y visible.** Si el registro no se puede escribir, el trabajo igual va a la impresora; si la consulta de grupos falla, el trabajo sale en blanco y negro. Pero una carpeta con propietario equivocado hace que el registro se detenga sin error, así que conviene monitorear lo que el filtro necesita para escribir.
9. **Pruebe el camino del cliente, no solo el del servidor.** Instalar por URL IPP y por recurso compartido de Samba falló en Windows por motivos distintos ("Internet Port", driver V4, error 0x80070005), y solo las pruebas en PCs reales lo mostraron. El puerto TCP RAW fue el que funcionó.
10. **El orden importa en Windows.** `Rename-Printer` restablece las preferencias del driver; crear la cola ya con su nombre final y solo después aplicar los valores predeterminados evita perder el PIN y el blanco y negro.
11. **El PowerShell "como administrador" puede no ser el usuario del dominio.** No veía el AD ni `NETLOGON`. Probar como `SYSTEM`, mediante una tarea programada, reproduce lo que ejecutará la GPO.
12. **La automatización que borra necesita salvaguardas.** La limpieza de impresoras solo se ejecuta si el usuario tiene derecho a alguna impresora del registro y todas las permitidas existen; un error del AD no cambia nada; y un modo de simulación registra lo que se quitaría antes de quitarlo.
13. **Piloto pequeño, reversible y documentado.** La GPO nueva nació para dos equipos, luego un grupo de equipos. Las GPO antiguas se respaldaron antes de borrarse, y borrar una GPO no quita las impresoras ya instaladas en las PCs.
14. **Pruebe la documentación ejecutándola.** Al correr los comandos del paso a paso en un servidor, la prueba encontró un error que solo existía en el repositorio: el receptor decodificaba el título como `latin-1` y rompía los acentos, mientras que el de producción ya usaba UTF-8. Comparar el repositorio con lo que corre en producción vale el tiempo.
15. **Documente mientras hace.** Los registros de decisiones, pruebas e incidentes permitieron retomar el trabajo entre sesiones y, ahora, publicarlo.
16. **Pruebe el servicio que está en ejecución, no solo un proceso nuevo.** `net ads testjoin` y `net ads status -P` pasaban mientras el `winbindd` en ejecución fallaba en Kerberos. La prueba que importa es la que ve lo que ve el servicio real.
17. **Dé a la herramienta de operación el mínimo de poder.** El panel inicia sesión con la contraseña del propio usuario, lee el AD con una cuenta que no puede escribir y la única acción con privilegio (cambiar la contraseña de la máquina) pasa por una regla de polkit que permite una sola unidad de systemd.
