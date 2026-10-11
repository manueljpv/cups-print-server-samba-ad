# cups-print-server-samba-ad

[Português](README.md) · **English** · [Español (Honduras)](README.es-HN.md)

A **Linux CUPS print server** integrated with a **Samba AD** domain, for organizations that rent printers billed per printed page and need to know who printed what, in B&W or color, without paying for Windows Print Server licenses. It keeps Xerox **PIN-protected printing** working, counts pages per user, restricts color by AD group, and delivers printers to PCs through GPO.

> **Notice: fictitious data.** Every name, domain, IP address and hostname in this repository (`empresa.local`, `srv-cups`, `192.0.2.x`, `usuario.a`…) is an invented example. Nothing here comes from a real environment. See the [final section](#notice-fictitious-data).

## The problem

- The printer rental contract bills **per printed face**, with different prices for B&W and color. Without your own accounting, the invoice is a black box.
- There was no budget to license Windows Server and CALs just to have a print server.
- Xerox **PIN-protected printing** (used, for example, by HR) had to keep working.
- Stock CUPS cannot solve this alone: the IPP queue counts pages but **loses the PIN**; the raw queue **keeps the PIN** but counts only 1 per job; and Windows drivers do not send color as an IPP attribute.
- Delivering printers to each PC, showing only the ones the user may use, is manual and error-prone work.

## What the project delivers

**1. CUPS counting filter (`scripts/server/xerox-contagem`)**

- Hands the job file to the printer **untouched** (the PIN is preserved) and writes the accounting by reading the file's own header: user, queue, pages, copies, duplex and color.
- **Color control by AD group:** users who request color without being in the authorized group get B&W, without losing the job.
- **Mandatory PIN:** a job without a PIN is silently rejected and logged.
- One log file per month, TAB-separated, ready to feed reports.

**2. TCP port receiver (`scripts/server/cups-recebe` + `configs/systemd/`)**

- Receives the job from Windows on a RAW TCP port (one per queue, for example 9101) and hands it to CUPS, going through the filter.
- Managed by systemd, with source restriction by subnet.

**3. Automatic delivery through GPO (`scripts/windows/Sync-Impressoras.ps1`)**

- A scheduled task that runs at logon as `SYSTEM`: reads the user's groups in AD, installs the V4 PS driver, creates the port and the queue with a friendly name, applies **B&W as the default** and turns the **PIN** on.
- Removes printers the user may not use and, optionally, cleans up all the others (Canon, XPS, Fax, etc.).
- A new printer is one more entry in `impressoras.json`.

**4. Documentation and lessons learned (`docs/`)**

- Decisions and tests that ruled out the alternatives, common problems, and an incident case study (winbind without groups after the machine account password rotation).

## High-level architecture

```
Printing:
Windows PC ──► Xerox V4 PS driver ──► TCP port 9101 ──► cups-recebe (systemd) ──► lp
                                                                                    │
                                                                                    ▼
                                                              CUPS (queue adm-xerox) + filter xerox-contagem
                                                               │  checks groups (winbind: id -nG)
                                                               │  writes /var/log/cups-contabilidade/contagem-YYYY-MM.log
                                                               ▼
                                                  Xerox printer (IPP) ──► PIN released at the panel

Printer delivery:
Windows PC ──► GPO (scheduled task at logon, SYSTEM) ──► Sync-Impressoras.ps1
                                                           ├─ user's groups (AD, via ADSI)
                                                           ├─ impressoras.json (NETLOGON)
                                                           └─ installs or removes queue, port and driver
```

The job file goes through CUPS without being converted, because the Xerox driver embeds the PIN, color and duplex in an XML header (XPIF) inside the file itself. The filter reads that header. Why this is the only option that keeps PIN and counting together is in [`docs/01-visao-geral-e-decisoes.md`](docs/01-visao-geral-e-decisoes.md) (Portuguese).

## Prerequisites

**Print server**

- A VM running **Ubuntu Server 24.04 LTS** (CUPS 2.4), with 2 vCPU, 4 GB RAM and 32 GB disk as a starting point.
- The server **joined to the Samba AD domain** (winbind/Kerberos), so that `wbinfo -t` works and `id user` shows the AD groups. The domain join procedure is not covered in this repository.
- Python 3 (included with Ubuntu).

**Printer**

- A Xerox with PIN-protected printing (the project used the **AltaLink C8030**), reachable over IPP.
- Other brands require testing what the driver writes into the job file before reusing the filter.

**Domain and clients**

- Samba AD (or Active Directory) with GPO and a shared folder readable by computers (the examples use `NETLOGON`).
- Windows 10/11 PCs joined to the domain.
- The **Xerox AltaLink C8030 V4 PS** driver package (download it from Xerox's official site; this repository does **not** include the driver).
- A machine with RSAT to create the GPO and write to `NETLOGON` as a domain administrator.

## Deployment

### 1. Server (Linux)

1. **Disable `cups-browsed`**, which creates automatic queues when CUPS is opened to the network:

   ```bash
   systemctl disable --now cups-browsed && systemctl mask cups-browsed
   ```

2. **Open CUPS to the network and set `PageLogFormat`**, using [`configs/cupsd-location.conf`](configs/cupsd-location.conf) as a template (one `Allow` per user subnet). Then: `systemctl restart cups`.
3. **Install the filter and the accounting folder:**

   ```bash
   install -o root -g root -m 755 scripts/server/xerox-contagem /usr/lib/cups/filter/xerox-contagem
   mkdir -p /var/log/cups-contabilidade
   chown lp:lp /var/log/cups-contabilidade && chmod 750 /var/log/cups-contabilidade
   ```

   At the top of the filter, adjust `GRUPOS_COR` (queue → color group) and `FILAS_PIN` (queues where the PIN is mandatory).
4. **Create the queue** with the minimal PPD [`configs/xerox-contagem.ppd`](configs/xerox-contagem.ppd), which has the two `*cupsFilter` lines described in [`docs/02-filtro-de-contagem.md`](docs/02-filtro-de-contagem.md):

   ```bash
   lpadmin -p adm-xerox -E -v ipp://192.0.2.20/ipp/print \
           -P configs/xerox-contagem.ppd \
           -L "Administrative Building" -D "Xerox AltaLink C8030 - ADM" \
           -o printer-is-shared=true
   ```

5. **Create the AD groups**, on the domain controller (one for access and one for color):

   ```bash
   /usr/local/samba/bin/samba-tool group add Impressora_ADM_Xerox \
       --groupou="OU=grupos,OU=EMPRESA" --group-scope=Global --group-type=Security
   /usr/local/samba/bin/samba-tool group add Impressora_ADM_Xerox_Cor \
       --groupou="OU=grupos,OU=EMPRESA" --group-scope=Global --group-type=Security
   ```

6. **Install the TCP port receiver:**

   ```bash
   install -m 755 scripts/server/cups-recebe /usr/local/bin/cups-recebe
   cp configs/systemd/cups-recebe-adm-xerox.socket configs/systemd/cups-recebe-adm-xerox@.service /etc/systemd/system/
   mkdir -p /etc/systemd/system/cups-recebe-adm-xerox.socket.d
   cp configs/systemd/ip.conf.example /etc/systemd/system/cups-recebe-adm-xerox.socket.d/ip.conf   # adjust the subnets
   systemctl daemon-reload && systemctl enable --now cups-recebe-adm-xerox.socket
   ```

### 2. Windows clients (GPO)

1. Put the V4 PS driver package (unzipped) in a folder readable by **Domain Computers** (the examples use `\\empresa.local\NETLOGON\Impressoras\XeroxV4PS`).
2. Copy `scripts/windows/Sync-Impressoras.ps1` and your `impressoras.json` (based on [`configs/impressoras.json.example`](configs/impressoras.json.example)) to `\\empresa.local\NETLOGON\scripts\Impressoras\CUPS\`. Write there as a domain administrator.
3. Create a computer group for the pilot and a GPO filtered by it, with a **computer scheduled task** (`SYSTEM` account, trigger "at log on of any user, 30-second delay") that runs the script. All parameters are in [`docs/03-entrega-por-gpo.md`](docs/03-entrega-por-gpo.md) (Portuguese).
4. Add users to the access groups (and, where applicable, the color group) and have them log off and back on.

## How to validate

**Server**

- `id user.a` should list the printer groups from AD.
- Paper-free test: `cupsdisable adm-xerox`, then `nc -w 5 127.0.0.1 9101 < sample.ps`, and check `journalctl -u 'cups-recebe-adm-xerox@*'` and `lpstat -o adm-xerox`. To go back to normal: `cancel -a adm-xerox` and `cupsenable adm-xerox`.
- `tail -n 5 /var/log/cups-contabilidade/contagem-$(date +%Y-%m).log` shows user, pages, copies, effective color, requested color, note and PIN for each job.

**Client**

- The file `C:\ProgramData\Impressoras-CUPS\sync.log` shows the user's groups and what was installed or removed.
- `Get-Printer` should list only the permitted printer and "Microsoft Print to PDF" (if cleanup is enabled).
- Print with a PIN: the job is held at the Xerox panel (Jobs > Secure Print). Without a PIN, the job is rejected (`rejeitado-sem-pin` in the log). A user outside the color group requesting color gets B&W (`forcado-pb`).

## Common problems

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| HTTP 403 when accessing CUPS | `<Location />` allows only one subnet | Add one `Allow` per user subnet and restart CUPS |
| The job prints dozens of pages of "codes" and has no PIN | CUPS classified the file as `text/plain` and discarded the header | Add `*cupsFilter: "text/plain 0 xerox-contagem"` to the PPD (see doc 04) |
| "Nothing reached the printer" | The job is held waiting for the PIN | Check the Xerox panel before blaming the driver |
| Every user prints in B&W | winbind stopped seeing the groups (machine account password rotation) | `systemctl restart winbind`; see the [case study](docs/05-incidente-winbind-senha-de-maquina.md) |
| Accounting stopped writing, with no error | Folder or log with the wrong owner (test run as root) | `chown lp:lp` on the folder and the files |
| Driver preferences went back to color and no PIN | `Rename-Printer` resets the defaults | Create the queue already with its final name and only then apply the defaults |
| "Run as administrator" PowerShell cannot see the domain or `NETLOGON` | The local administrator is a local account | Test with a scheduled task as `SYSTEM` or with the domain user's PowerShell |
| Cannot remove the queue and the driver right after each other | The spooler is holding the items | Wait, or `Restart-Service Spooler` and wait ~20 s |

More cases in [`docs/04-problemas-comuns.md`](docs/04-problemas-comuns.md) (Portuguese).

## Known limitations

- Counting happens **at submission**: a job canceled later (at the printer panel, or before the PIN is released) is still counted.
- Color and copies reflect what the driver requested, not a page-by-page analysis.
- The user name comes from Windows and is **not validated** by the server.
- Raw queues and PPD drivers are marked as deprecated by CUPS. On CUPS 2.4 (Ubuntu 24.04) this does not affect anything today, but it is a long-term risk.
- The filter was validated with Xerox (XPIF header). Other brands need testing.

## Security

- The receiver's **TCP port has no authentication** and `cupsd.conf` does not apply to it. Restrict the source by subnet (`IPAddressAllow` on the socket, as in the example) and/or by firewall.
- The PIN inside the job file is only a **simple encoding**, not encryption. Keep `PreserveJobFiles` off in production and the spool folder protected.
- Back up **SYSVOL (with permissions)** before upgrading Samba, especially if it was installed from a tarball.
- Write to `NETLOGON` only as a domain administrator; computers only need read access.
- The server's machine account password is rotated automatically every 7 days (Samba default) and this can break group lookups. Monitor it and restart winbind if needed.
- Never commit real `impressoras.json` files, accounting logs, keys or certificates (the `.gitignore` already blocks them).

## Documentation and roadmap

- [`docs/01-visao-geral-e-decisoes.md`](docs/01-visao-geral-e-decisoes.md): goal, environment, decisions, and the tests that ruled out the alternatives.
- [`docs/02-filtro-de-contagem.md`](docs/02-filtro-de-contagem.md): how the filter works, versions and log format.
- [`docs/03-entrega-por-gpo.md`](docs/03-entrega-por-gpo.md): TCP port, groups, GPO and the sync script.
- [`docs/04-problemas-comuns.md`](docs/04-problemas-comuns.md): problems and solutions.
- [`docs/05-incidente-winbind-senha-de-maquina.md`](docs/05-incidente-winbind-senha-de-maquina.md): case study.
- [`ROADMAP.en.md`](ROADMAP.en.md): future improvements.

The `docs/` folder is available in Portuguese only.

## Notice: fictitious data

This repository was derived from a real infrastructure project and **was anonymized before publication**. Every company name, domain, IP address, hostname, account and person that appears here is **fictitious** and serves only as an example:

- Domain: `empresa.local` (NetBIOS `EMPRESA`).
- Networks: `192.0.2.0/24`, `198.51.100.0/24` and `203.0.113.0/24` (ranges reserved for documentation).
- Machines and accounts: `dc01`, `srv-cups`, `srv-arquivos`, `usuario.a`, `usuario.b`, etc.

The values in `impressoras.json.example` and in the files under `configs/` are placeholders only. Replace everything with your own environment.

## License

[GNU GPL v3.0](LICENSE).

Maintained by [@manueljpv](https://github.com/manueljpv).
