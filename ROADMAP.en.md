# Roadmap

[Português](ROADMAP.md) · **English** · [Español (Honduras)](ROADMAP.es-HN.md)

This document shows where the project could go and what we have learned so far. Nothing below is a promise of dates: these are intentions, in rough order of priority. Suggestions are welcome through *issues*.

## Short term

**Accounting and reports**

- **Monthly report.** Read `contagem-YYYY-MM.log` and produce totals per printer, per department and per user, separating B&W and color and applying the contract's per-face rates. The report must treat columns 10 to 12 of the log as optional, ignore `rejeitado-sem-pin` lines in the totals, and not read the `.teste.log` files.
- **Department groups in AD.** Today there are only access and color groups per printer. Without department groups, the per-department report cannot be completed.
- **Web control panel (HTML).** A page reachable from a browser, with print counts always kept **monthly**, to preserve history and allow comparing months and years. It shows the company total and the total **per printer, per department and per person** (B&W x color); for each person, what they printed, with the **file names**, day and time; and a month-by-month view for comparisons. It includes a list of jobs rejected for lack of a PIN, since the RAW port cannot warn the user on screen.
- **Personal-use check.** Flag, based on file names, prints that look personal (for example, by configurable words and patterns), for **human review**, without blocking printing. Because this involves the names of each person's documents, restrict access to the panel and the accounting data to those who need it, and make the printing policy clear to users (also check the applicable privacy requirements, such as data protection laws).
- **Costs and print allowance in the panel.** Since the printers are rented, every page has a cost. The panel should let you register, **per printer**, the price of a B&W page and of a color page (which can differ from one printer to another) and calculate each month's cost: per printer, **per department** (a basis for a possible cost split) and per person. Contracts usually include an **allowance**: for example, the Xerox may print up to 1,000 color pages at one price, and from the 1,001st the price goes up. The panel should register the allowance and the overage price per printer and per color, show a **counter of the allowance used in the month** (how much has been used and how much is left) and warn when consumption nears the limit. Store the rates **with an effective date**, so past months do not change when the contract changes, and define how the overage cost is split among departments. Check the contract to see whether the allowance is per printer, per color or shared. Until it is checked against the printers' own counters, the server's count is an estimate (it is taken at submission, and canceled jobs are still counted).
- **Server health card in the panel.** Warn about the next machine account password rotation and check that winbind sees the printer groups (a test user in an access group, and Kerberos failures in the journal). See the [case study](docs/05-incidente-winbind-senha-de-maquina.md) (Portuguese).
- **Make the filter report `PAGE: total N` to CUPS**, so that `page_log` is consistent with the project's own accounting (today it shows `total 0` on queues that use the filter).
- **Check two points about the driver and the contract:** whether the job ID banner (`JobIdBannerOn`) produces an extra sheet in any scenario, and how the rental company bills each color mode (including a possible automatic mode).

**Server**

- **Decide about the automatic machine account password rotation.** Keep the Samba default (7 days) with monitoring, or turn it off (`machine password timeout = 0`, with a backup of `smb.conf`) and switch to periodic manual rotation (`net ads changetrustpw` + winbind restart + test). Before deciding, test that the manual rotation does not suffer from the same defect.
- **Register the remaining printers** (other Canon units and an HP). For each one: a `place-brand` queue, a receiver on another port, an entry in the color map and one more line in `impressoras.json`. Before reusing the filter, test what each brand's driver writes into the job file.
- **Automated tests for the filter and the receiver** with synthetic job samples (B&W, color, with and without PIN, user inside and outside the color group), to validate without a printer and without using paper.
- **SYSVOL backup routine** (with permissions) before upgrading Samba, especially if it was installed from a tarball.

**GPO and Windows clients**

- **Expand the pilot in phases.** Today the scope is the IT team, filtered by a computer group. Expand to other departments by adding computers to the group, after validating with each team.
- **Clean up per-user connections.** The script runs as `SYSTEM` and only sees the machine's printers; connections in the user's context (`\\server\queue`, `http://...`) remain. A future version should clean the logged-on user's `HKU\<SID>\Printers\Connections`.
- **Clean up the legacy.** Delete the old group, the PCL6 driver folder and the old scripts of the previous GPO from `NETLOGON`.
- **Turn off `JobIdBannerOn` in the driver default, as a precaution**, after finding the "off" key by comparing the print ticket before and after.
- **Test on a truly clean PC**, without the ghost "Internet Port" that got stuck on the test PC.
- **Go-live.** Archive and reset the test log to start accounting clean (see [doc 04](docs/04-problemas-comuns.md), Portuguese).

## Long term

- **Authentication at the printer panel through LDAP/Kerberos against Samba AD**, removing the need for a PIN and identifying each job's owner. This is the project's "ace up the sleeve": it needs a lot of testing and must not fail. Test it on a separate queue, without touching the queue that already works, and notify the rental company before touching the rented printer. The job's user must match the domain login, and Samba AD's LDAP compatibility (bind, LDAPS, certificate) must be confirmed.
- **Validate the job's user.** Today the name comes from Windows and the server does not validate it. The authentication above would solve that at the source.
- **Counting at paper output.** Today counting happens at submission, so a job canceled later is still counted. Reconcile with the printer's own counters (SNMP or Xerox accounting) to check the rental company's invoice.
- **Move away from raw queues and PPD drivers**, which CUPS marks as deprecated and which will stop working in a future version (CUPS 3.x). Evaluate an architecture that keeps PIN and counting without depending on them.
- **A button in the panel to rotate the machine account password.** It confirms the change, runs the command, tests and shows the result. With authentication, a fixed and restricted command (no free input), a record of who triggered it, and not available on a wall screen without login.
- **Panel on a dedicated screen** (for example, a Linux notebook with a browser showing several panels), so the warnings are seen without depending on someone opening the page.
- **More printer brands**, with a filter that understands each driver's header.
- **Packaging and automation** of the server setup (script or Ansible), to reproduce the environment faster.
- **Translate the `docs/` folder** into English and Honduran Spanish.

## Lessons learned

1. **Test before choosing the architecture.** Three test queues with the same PDF showed that none worked alone: IPP counts but loses the PIN, and raw keeps the PIN but counts 1 per job. The solution (a filter) only appeared after looking at what each path really delivered.
2. **Open the job file.** Turning `PreserveJobFiles` on for a moment and inspecting the file revealed that the driver already embeds PIN, color, duplex and user in an XML header. Everything the report needed was there, with no dependence on IPP attributes that Windows does not send.
3. **Understand the contract before counting.** The rental bills per face, not per sheet. That defined what the filter counts (pages x copies) and removed the worry about the driver's default duplex.
4. **The test tool must represent the real path.** `cupsfilter` on the command line does not reproduce `cupsd`'s filter chain. A test queue with `socket://127.0.0.1:...`, an `nc` capturing the output and `lp` reproduce what really happens, without using paper.
5. **Find the root cause.** One user's job came out as 40 pages of code because CUPS classified it as `text/plain` (the PostScript rule only looks at the first ~128 bytes) and discarded the header. Two `*cupsFilter` lines in the PPD fixed it; changing the driver would not have.
6. **Record what was requested and what came out.** Logging the requested color, the effective color and a note per job made it possible to tell "the user asked for B&W" from "the server forced B&W" when every user started printing in black and white.
7. **Identity dependencies need monitoring.** The automatic machine account password rotation, 7 days after joining the domain, left winbind unable to see the groups. The failure was silent and looked like a color problem. Periodic events like this deserve a warning.
8. **Fail safely and visibly.** If the log cannot be written, the job still goes to the printer; if the group lookup fails, the job comes out in B&W. But a folder with the wrong owner makes the log stop with no error, so it is worth monitoring what the filter needs in order to write.
9. **Test the client path, not just the server's.** Installing through an IPP URL and through a Samba share failed on Windows for different reasons ("Internet Port", V4 driver, error 0x80070005), and only tests on real PCs showed that. The RAW TCP port was the one that worked.
10. **Order matters on Windows.** `Rename-Printer` resets the driver preferences; creating the queue already with its final name and only then applying the defaults avoids losing the PIN and B&W.
11. **PowerShell "as administrator" may not be the domain user.** It could not see AD or `NETLOGON`. Testing as `SYSTEM`, through a scheduled task, reproduces what the GPO will run.
12. **Automation that deletes needs safeguards.** The printer cleanup only runs if the user is entitled to some printer in the list and all permitted ones exist; an AD error changes nothing; and a simulation mode logs what would be removed before removing it.
13. **A small, reversible, documented pilot.** The new GPO started with two computers, then a computer group. The old GPOs were backed up before being deleted, and deleting a GPO does not remove printers already installed on the PCs.
14. **Test the documentation by running it.** Running the step-by-step commands on a server found a bug that only existed in the repository: the receiver decoded the title as `latin-1` and broke the accents, while the production one already used UTF-8. Comparing the repository with what runs in production is worth the time.
15. **Document as you go.** The records of decisions, tests and incidents made it possible to resume the work between sessions and, now, to publish it.
