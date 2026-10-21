# cups-print-server-samba-ad

[Português](README.md) · [English](README.en.md) · **Español (Honduras)**

Un servidor de impresión **CUPS en Linux** integrado a un dominio **Samba AD**, para quienes alquilan impresoras que se cobran por página impresa y necesitan saber quién imprimió qué, en blanco y negro o a color, sin pagar licencias de Windows Print Server. Mantiene funcionando la **impresión protegida por PIN** de Xerox, cuenta las páginas por usuario, restringe el color por grupo del AD y entrega las impresoras a las computadoras mediante GPO.

> **Aviso: datos ficticios.** Todos los nombres, dominios, direcciones IP y hostnames de este repositorio (`empresa.local`, `srv-cups`, `192.0.2.x`, `usuario.a`…) son ejemplos inventados. Nada de lo que aparece aquí proviene de un ambiente real. Vea la [sección final](#aviso-datos-ficticios).

## El problema

- El contrato de alquiler de las impresoras cobra **por cara impresa**, con precios distintos para blanco y negro y para color. Sin una contabilidad propia, la factura es una caja negra.
- No había presupuesto para licenciar un Windows Server y CALs solo para tener un servidor de impresión.
- La impresión protegida por **PIN** de Xerox (usada, por ejemplo, por Recursos Humanos) tenía que seguir funcionando.
- CUPS por sí solo no resuelve esto: la cola IPP cuenta las páginas pero **pierde el PIN**; la cola raw **conserva el PIN** pero solo cuenta 1 por trabajo; y los drivers de Windows no envían el color como atributo IPP.
- Entregar las impresoras a cada computadora, mostrando solo las que el usuario puede usar, es un trabajo manual y propenso a errores.

## Lo que entrega el proyecto

**1. Filtro de conteo de CUPS (`scripts/server/xerox-contagem`)**

- Entrega el archivo del trabajo **intacto** a la impresora (el PIN se conserva) y registra la contabilidad leyendo el encabezado del propio archivo: usuario, cola, páginas, copias, doble cara y color.
- **Control de color por grupo del AD:** quien pide color sin estar en el grupo autorizado recibe blanco y negro, sin perder el trabajo.
- **PIN obligatorio:** un trabajo sin PIN se rechaza en silencio y queda registrado.
- Un archivo de registro por mes, con campos separados por TAB, listo para alimentar reportes.

**2. Receptor de puerto TCP (`scripts/server/cups-recebe` + `configs/systemd/`)**

- Recibe el trabajo de Windows en un puerto TCP RAW (uno por cola, por ejemplo el 9101) y lo entrega a CUPS, pasando por el filtro.
- Administrado por systemd, con restricción de origen por subred.

**3. Entrega automática mediante GPO (`scripts/windows/Sync-Impressoras.ps1`)**

- Una tarea programada que se ejecuta al iniciar sesión como `SYSTEM`: lee los grupos del usuario en el AD, instala el driver V4 PS, crea el puerto y la cola con un nombre amigable, aplica **blanco y negro como predeterminado** y activa el **PIN**.
- Quita las impresoras que el usuario no puede usar y, opcionalmente, limpia las demás (Canon, XPS, Fax, etc.).
- Una impresora nueva es una línea más en `impressoras.json`.

**4. Cambio controlado de la contraseña de la cuenta de máquina (`scripts/server/troca-senha-maquina` + `configs/systemd/`)**

- Desactiva el cambio automático de Samba y lo sustituye por un cambio programado que **reinicia winbind**, verifica que los grupos sigan visibles y escribe un estado en JSON.
- Resuelve el incidente en que todos los usuarios empezaron a imprimir en blanco y negro. Vea el [doc 06](docs/06-troca-controlada-winbind.md) (en portugués).

**5. Panel web (`painel/`)**

- Una aplicación Flask interna, con inicio de sesión del AD (LDAPS) y acceso por grupo. Hoy ofrece **permisos de impresión** (quién puede usar cada impresora, por usuario, departamento, impresora y equipo; solo lectura) y **control de winbind** (salud, último cambio y botón de cambio). Vea el [doc 07](docs/07-painel-web.md) (en portugués).

**6. Documentación y lecciones aprendidas (`docs/`)**

- Decisiones y pruebas que descartaron las alternativas, problemas comunes y un estudio de caso de un incidente (winbind sin grupos tras el cambio de contraseña de la cuenta de máquina).

## Arquitectura a alto nivel

```
Impresión:
PC Windows ──► driver Xerox V4 PS ──► puerto TCP 9101 ──► cups-recebe (systemd) ──► lp
                                                                                    │
                                                                                    ▼
                                                              CUPS (cola adm-xerox) + filtro xerox-contagem
                                                               │  consulta grupos (winbind: id -nG)
                                                               │  escribe /var/log/cups-contabilidade/contagem-AAAA-MM.log
                                                               ▼
                                                  Impresora Xerox (IPP) ──► PIN liberado en el panel

Entrega de impresoras:
PC Windows ──► GPO (tarea programada al iniciar sesión, SYSTEM) ──► Sync-Impressoras.ps1
                                                                     ├─ grupos del usuario (AD, vía ADSI)
                                                                     ├─ impressoras.json (NETLOGON)
                                                                     └─ instala o quita cola, puerto y driver
```

El archivo del trabajo pasa por CUPS sin convertirse, porque el driver de Xerox incrusta el PIN, el color y la doble cara en un encabezado XML (XPIF) dentro del propio archivo. El filtro lee ese encabezado. Por qué esta es la única opción que mantiene juntos el PIN y el conteo está en [`docs/01-visao-geral-e-decisoes.md`](docs/01-visao-geral-e-decisoes.md) (en portugués).

## Requisitos previos

**Servidor de impresión**

- Una VM con **Ubuntu Server 24.04 LTS** (CUPS 2.4), con 2 vCPU, 4 GB de RAM y 32 GB de disco como punto de partida.
- El servidor **unido al dominio Samba AD** (winbind/Kerberos), de modo que `wbinfo -t` funcione e `id usuario` muestre los grupos del AD. El procedimiento para unir al dominio no está en este repositorio.
- Python 3 (ya viene con Ubuntu).

**Impresora**

- Una Xerox con impresión protegida por PIN (el proyecto usó la **AltaLink C8030**), accesible por IPP.
- Otras marcas requieren probar qué escribe el driver en el archivo del trabajo antes de reutilizar el filtro.

**Dominio y clientes**

- Samba AD (o Active Directory) con GPO y una carpeta compartida legible por los equipos (los ejemplos usan `NETLOGON`).
- PCs con Windows 10/11 unidas al dominio.
- El paquete del driver **Xerox AltaLink C8030 V4 PS** (descárguelo del sitio oficial de Xerox; este repositorio **no** incluye el driver).
- Una máquina con RSAT para crear la GPO y escribir en `NETLOGON` como administrador del dominio.

## Implementación

### 1. Servidor (Linux)

1. **Desactive `cups-browsed`**, que crea colas automáticas al abrir CUPS a la red:

   ```bash
   systemctl disable --now cups-browsed && systemctl mask cups-browsed
   ```

2. **Abra CUPS a la red y defina el `PageLogFormat`**, usando [`configs/cupsd-location.conf`](configs/cupsd-location.conf) como modelo (un `Allow` por subred de usuarios). Después: `systemctl restart cups`.
3. **Instale el filtro y la carpeta de contabilidad:**

   ```bash
   install -o root -g root -m 755 scripts/server/xerox-contagem /usr/lib/cups/filter/xerox-contagem
   mkdir -p /var/log/cups-contabilidade
   chown lp:lp /var/log/cups-contabilidade && chmod 750 /var/log/cups-contabilidade
   ```

   En la parte superior del filtro, ajuste `GRUPOS_COR` (cola → grupo de color) y `FILAS_PIN` (colas donde el PIN es obligatorio).
4. **Cree la cola** con el PPD mínimo [`configs/xerox-contagem.ppd`](configs/xerox-contagem.ppd), que tiene las dos líneas `*cupsFilter` descritas en [`docs/02-filtro-de-contagem.md`](docs/02-filtro-de-contagem.md):

   ```bash
   lpadmin -p adm-xerox -E -v ipp://192.0.2.20/ipp/print \
           -P configs/xerox-contagem.ppd \
           -L "Edificio Administrativo" -D "Xerox AltaLink C8030 - ADM" \
           -o printer-is-shared=true
   ```

5. **Cree los grupos en el AD**, en el controlador de dominio (uno de acceso y uno de color):

   ```bash
   /usr/local/samba/bin/samba-tool group add Impressora_Xerox_ADM \
       --groupou="OU=grupos,OU=EMPRESA" --group-scope=Global --group-type=Security
   /usr/local/samba/bin/samba-tool group add Impressora_Xerox_ADM_Cor \
       --groupou="OU=grupos,OU=EMPRESA" --group-scope=Global --group-type=Security
   ```

6. **Instale el receptor del puerto TCP:**

   ```bash
   install -m 755 scripts/server/cups-recebe /usr/local/bin/cups-recebe
   cp configs/systemd/cups-recebe-adm-xerox.socket configs/systemd/cups-recebe-adm-xerox@.service /etc/systemd/system/
   mkdir -p /etc/systemd/system/cups-recebe-adm-xerox.socket.d
   cp configs/systemd/ip.conf.example /etc/systemd/system/cups-recebe-adm-xerox.socket.d/ip.conf   # ajuste las subredes
   systemctl daemon-reload && systemctl enable --now cups-recebe-adm-xerox.socket
   ```

### 2. Clientes Windows (GPO)

1. Coloque el paquete del driver V4 PS (descomprimido) en una carpeta legible por **Domain Computers** (los ejemplos usan `\\empresa.local\NETLOGON\Impressoras\XeroxV4PS`).
2. Copie `scripts/windows/Sync-Impressoras.ps1` y su `impressoras.json` (a partir de [`configs/impressoras.json.example`](configs/impressoras.json.example)) a `\\empresa.local\NETLOGON\scripts\Impressoras\CUPS\`. Escriba ahí como administrador del dominio.
3. Cree un grupo de equipos para el piloto y una GPO filtrada por él, con una **tarea programada de equipo** (cuenta `SYSTEM`, disparador "al iniciar sesión cualquier usuario, retraso de 30 segundos") que ejecute el script. Todos los parámetros están en [`docs/03-entrega-por-gpo.md`](docs/03-entrega-por-gpo.md) (en portugués).
4. Agregue a los usuarios a los grupos de acceso (y, si corresponde, al de color) y pídales cerrar sesión y volver a entrar.

## Cómo validar

**Servidor**

- `id usuario.a` debe listar los grupos de impresora del AD.
- Prueba sin papel: `cupsdisable adm-xerox`, luego `nc -w 5 127.0.0.1 9101 < muestra.ps`, y revise `journalctl -u 'cups-recebe-adm-xerox@*'` y `lpstat -o adm-xerox`. Para volver a la normalidad: `cancel -a adm-xerox` y `cupsenable adm-xerox`.
- `tail -n 5 /var/log/cups-contabilidade/contagem-$(date +%Y-%m).log` muestra usuario, páginas, copias, color efectivo, color solicitado, nota y PIN de cada trabajo.

**Cliente**

- El archivo `C:\ProgramData\Impressoras-CUPS\sync.log` muestra los grupos del usuario y lo que se instaló o quitó.
- `Get-Printer` debe listar solo la impresora permitida y "Microsoft Print to PDF" (si la limpieza está activa).
- Imprima con PIN: el trabajo queda retenido en el panel de la Xerox (Trabajos > Impresión protegida). Sin PIN, el trabajo se rechaza (`rejeitado-sem-pin` en el registro). Un usuario fuera del grupo de color que pide color sale en blanco y negro (`forcado-pb`).

## Problemas comunes

| Síntoma | Causa probable | Qué hacer |
| --- | --- | --- |
| HTTP 403 al acceder a CUPS | El `<Location />` solo permite una subred | Agregue un `Allow` por subred de usuarios y reinicie CUPS |
| El trabajo sale con decenas de páginas de "códigos" y sin PIN | CUPS clasificó el archivo como `text/plain` y descartó el encabezado | Agregue `*cupsFilter: "text/plain 0 xerox-contagem"` al PPD (vea el doc 04) |
| "No llegó nada a la impresora" | El trabajo está retenido esperando el PIN | Revise el panel de la Xerox antes de culpar al driver |
| Todos los usuarios salen en blanco y negro | winbind dejó de ver los grupos (cambio de contraseña de la cuenta de máquina) | `systemctl restart winbind`; vea el [estudio de caso](docs/05-incidente-winbind-senha-de-maquina.md) y el [cambio controlado](docs/06-troca-controlada-winbind.md), que lo evita |
| La contabilidad dejó de registrar, sin error | Carpeta o registro con propietario equivocado (prueba hecha como root) | `chown lp:lp` en la carpeta y en los archivos |
| Las preferencias del driver volvieron a color y sin PIN | `Rename-Printer` restablece los valores predeterminados | Cree la cola ya con su nombre final y solo después aplique los predeterminados |
| El PowerShell "como administrador" no ve el dominio ni `NETLOGON` | El administrador local es una cuenta local | Pruebe con una tarea programada como `SYSTEM` o con el PowerShell del usuario de dominio |
| No puede quitar la cola y el driver justo después | El spooler retiene los elementos | Espere, o `Restart-Service Spooler` y aguarde ~20 s |

Más casos en [`docs/04-problemas-comuns.md`](docs/04-problemas-comuns.md) (en portugués).

## Limitaciones conocidas

- El conteo se hace **al enviar**: un trabajo cancelado después (en el panel de la impresora, o antes de liberar el PIN) se sigue contando.
- El color y las copias reflejan lo que pidió el driver, no un análisis página por página.
- El nombre del usuario viene de Windows y el servidor **no lo valida**.
- CUPS marca las colas raw y los drivers PPD como obsoletos. En CUPS 2.4 (Ubuntu 24.04) hoy no afecta, pero es un riesgo a largo plazo.
- El filtro se validó con Xerox (encabezado XPIF). Otras marcas necesitan pruebas.

## Seguridad

- El **puerto TCP del receptor no tiene autenticación** y el `cupsd.conf` no se aplica a él. Restrinja el origen por subred (`IPAddressAllow` en el socket, como en el ejemplo) y/o con firewall.
- El PIN dentro del archivo del trabajo es solo una **codificación simple**, no cifrado. Mantenga `PreserveJobFiles` desactivado en producción y la carpeta de spool protegida.
- Haga **respaldo de SYSVOL (con permisos)** antes de actualizar Samba, sobre todo si se instaló desde un tarball.
- Escriba en `NETLOGON` solo como administrador del dominio; los equipos solo necesitan lectura.
- La contraseña de la cuenta de máquina del servidor se cambia automáticamente cada 7 días (valor predeterminado de Samba) y eso puede romper la lectura de grupos: el winbind en ejecución sigue con la contraseña anterior. Desactive el cambio automático y use el [cambio controlado](docs/06-troca-controlada-winbind.md).
- El panel web debe quedar detrás de un proxy que acepte solo las redes internas y **nunca** exponerse a internet. No versione la contraseña de la cuenta de lectura ni la llave de sesión.
- Nunca versione archivos `impressoras.json` reales, registros de contabilidad, llaves ni certificados (el `.gitignore` ya los bloquea).

## Documentación y roadmap

- [`docs/01-visao-geral-e-decisoes.md`](docs/01-visao-geral-e-decisoes.md): objetivo, ambiente, decisiones y las pruebas que descartaron las alternativas.
- [`docs/02-filtro-de-contagem.md`](docs/02-filtro-de-contagem.md): cómo funciona el filtro, versiones y formato del registro.
- [`docs/03-entrega-por-gpo.md`](docs/03-entrega-por-gpo.md): puerto TCP, grupos, GPO y el script de sincronización.
- [`docs/04-problemas-comuns.md`](docs/04-problemas-comuns.md): problemas y soluciones.
- [`docs/05-incidente-winbind-senha-de-maquina.md`](docs/05-incidente-winbind-senha-de-maquina.md): estudio de caso.
- [`docs/06-troca-controlada-winbind.md`](docs/06-troca-controlada-winbind.md): causa confirmada y solución del cambio de la contraseña de la cuenta de máquina.
- [`docs/07-painel-web.md`](docs/07-painel-web.md): panel web (permisos, winbind, instalación).
- [`ROADMAP.es-HN.md`](ROADMAP.es-HN.md): mejoras futuras.

La carpeta `docs/` está disponible solo en portugués.

## Aviso: datos ficticios

Este repositorio se derivó de un proyecto real de infraestructura y **fue anonimizado antes de su publicación**. Todos los nombres de empresa, dominios, direcciones IP, hostnames, cuentas y personas que aparecen aquí son **ficticios** y sirven solo como ejemplo:

- Dominio: `empresa.local` (NetBIOS `EMPRESA`).
- Redes: `192.0.2.0/24`, `198.51.100.0/24` y `203.0.113.0/24` (rangos reservados para documentación).
- Equipos y cuentas: `dc01`, `srv-cups`, `srv-arquivos`, `usuario.a`, `usuario.b`, etc.

Los valores de `impressoras.json.example` y de los archivos en `configs/` son solo marcadores. Reemplace todo por los de su ambiente.

## Licencia

GPL-3.0. Vea el archivo [LICENSE](LICENSE). Copyright (C) 2026 Manuel Pérez.
