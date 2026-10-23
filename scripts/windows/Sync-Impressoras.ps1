# Sync-Impressoras.ps1
# Roda como SYSTEM no logon (tarefa agendada criada por GPO).
# Instala as impressoras a que o usuario logado tem direito (grupos do AD) e
# remove as demais. Se qualquer consulta falhar, nao altera nada.
# Limpeza: para usuarios que tem direito a pelo menos uma impressora do JSON,
# remove todas as outras impressoras do PC, exceto a Microsoft Print to PDF.
# -SimularLimpeza: so registra no log o que seria removido (nao remove nada).
param(
    [string]$ConfigPath = "C:\ProgramData\Impressoras-CUPS\impressoras.json",
    [string]$Usuario = "",
    [switch]$SimularLimpeza
)

$LogPath = "C:\ProgramData\Impressoras-CUPS\sync.log"
New-Item -ItemType Directory -Force -Path (Split-Path $LogPath) | Out-Null

function Log($msg) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $msg" | Out-File -FilePath $LogPath -Append -Encoding UTF8
}

function LigarPin($nome) {
    try {
        $x = [xml](Get-PrintConfiguration -PrinterName $nome).PrintTicketXML
        $ns = New-Object Xml.XmlNamespaceManager($x.NameTable)
        $ns.AddNamespace("psf","http://schemas.microsoft.com/windows/2003/08/printing/printschemaframework")
        $f = $x.SelectSingleNode("//psf:Feature[@name='pskv11:JobPasscode']",$ns)
        if (-not $f) { Log "AVISO: opcao de PIN nao encontrada em $nome"; return }
        $f.Option.SetAttribute("name","psk:On")
        $frag = $x.CreateDocumentFragment()
        $frag.InnerXml = '<psf:ParameterInit xmlns:psf="http://schemas.microsoft.com/windows/2003/08/printing/printschemaframework" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" name="pskv11:JobPasscodeString"><psf:Value xsi:type="xsd:string"></psf:Value></psf:ParameterInit>'
        $x.DocumentElement.AppendChild($frag) | Out-Null
        Set-PrintConfiguration -PrinterName $nome -PrintTicketXml $x.OuterXml -ErrorAction Stop
        Log "PIN ligado como padrao em $nome"
    }
    catch { Log "ERRO ao ligar PIN em ${nome}: $_" }
}
function Instalar($p) {
    if (-not (Get-PrinterDriver -Name $p.driver -ErrorAction SilentlyContinue)) {
        if ($p.inf) { $alvo = Join-Path $p.pastaDriver $p.inf } else { $alvo = "$($p.pastaDriver)\*.inf" }
        $res = pnputil /add-driver "$alvo" /install 2>&1 | Out-String
        Log "pnputil: $($res.Trim())"
        Add-PrinterDriver -Name $p.driver -ErrorAction Stop
        Log "Driver registrado: $($p.driver)"
    }
    if (-not (Get-PrinterPort -Name $p.porta -ErrorAction SilentlyContinue)) {
        Add-PrinterPort -Name $p.porta -PrinterHostAddress $p.host -PortNumber $p.portaTcp -ErrorAction Stop
        Log "Porta criada: $($p.porta)"
    }
    Add-Printer -Name $p.nome -DriverName $p.driver -PortName $p.porta -ErrorAction Stop
    try { Set-PrintConfiguration -PrinterName $p.nome -Color $false -ErrorAction Stop }
    catch { Log "AVISO: nao foi possivel definir P&B como padrao em $($p.nome): $_" }
    if ($p.pin -ne $false) { LigarPin $p.nome }
    Log "Impressora instalada: $($p.nome) (padrao P&B)"
}

function Remover($p) {
    Remove-Printer -Name $p.nome -ErrorAction Stop
    Log "Impressora removida: $($p.nome)"
    $emUso = Get-Printer | Where-Object { $_.PortName -eq $p.porta }
    if (-not $emUso) {
        Remove-PrinterPort -Name $p.porta -ErrorAction SilentlyContinue
        Log "Porta removida: $($p.porta)"
    }
}

# Remove tudo que nao for impressora do JSON permitida ao usuario nem Microsoft Print to PDF.
function LimparOutras($config, $nomesPermitidos) {
    $portasConfig = @($config | ForEach-Object { $_.porta })
    $sobras = @(Get-Printer | Where-Object {
        ($nomesPermitidos -notcontains $_.Name) -and ($_.DriverName -ne 'Microsoft Print To PDF')
    })
    if (-not $sobras) { Log "Limpeza: nenhuma impressora extra encontrada."; return }

    foreach ($s in $sobras) {
        if ($SimularLimpeza) {
            Log "SIMULACAO: removeria impressora '$($s.Name)' (driver $($s.DriverName), porta $($s.PortName))"
            continue
        }
        try {
            Remove-Printer -Name $s.Name -ErrorAction Stop
            Log "Limpeza: impressora removida: $($s.Name) (driver $($s.DriverName), porta $($s.PortName))"
        }
        catch { Log "ERRO na limpeza ao remover '$($s.Name)': $_" }
    }

    # Portas de rede orfas (TCP/IP, WSD, http), exceto as do JSON
    $emUso = @(Get-Printer | ForEach-Object { $_.PortName })
    $orfas = @(Get-PrinterPort | Where-Object {
        ($_.Name -match '^(IP_|http|WSD-)' -or $_.PrinterHostAddress) -and
        ($emUso -notcontains $_.Name) -and ($portasConfig -notcontains $_.Name)
    })
    foreach ($o in $orfas) {
        if ($SimularLimpeza) { Log "SIMULACAO: removeria porta orfa '$($o.Name)'"; continue }
        try {
            Remove-PrinterPort -Name $o.Name -ErrorAction Stop
            Log "Limpeza: porta orfa removida: $($o.Name)"
        }
        catch { Log "AVISO: porta '$($o.Name)' nao removida: $_" }
    }
}

try {
    if (-not $Usuario) {
        $console = (Get-CimInstance Win32_ComputerSystem).UserName
        if (-not $console) { Log "Nenhum usuario no console; nada a fazer."; return }
        $Usuario = $console
    }
    $sam = ($Usuario -split '\\')[-1]

    $achado = ([adsisearcher]"(&(objectClass=user)(sAMAccountName=$sam))").FindOne()
    if (-not $achado) { Log "Usuario $sam nao encontrado no AD; nada alterado."; return }
    $grupos = @($achado.Properties["memberof"] | ForEach-Object { ($_ -split ',')[0] -replace '^CN=', '' })
    Log "Usuario $sam; grupos: $($grupos -join ', ')"

    $config = Get-Content -Path $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    # Grupos do COMPUTADOR (so consulta se alguma impressora do JSON define grupoPCs).
    # Se a consulta falhar, nao altera nada.
    $gruposPC = @()
    if (@($config | Where-Object { $_.grupoPCs }).Count -gt 0) {
        $pcNome = $env:COMPUTERNAME
        $pcAchado = ([adsisearcher]"(&(objectClass=computer)(sAMAccountName=$pcNome`$))").FindOne()
        if (-not $pcAchado) { Log "Computador $pcNome nao encontrado no AD; nada alterado."; return }
        $gruposPC = @($pcAchado.Properties["memberof"] | ForEach-Object { ($_ -split ',')[0] -replace '^CN=', '' })
        Log "Computador $pcNome; grupos: $($gruposPC -join ', ')"
    }

    $nomesPermitidos = @()
    foreach ($p in $config) {
        try {
            $permitido = ($grupos -contains $p.grupoAcesso) -or ($grupos -contains $p.grupoCor)
            if ($p.grupoPCs) { $permitido = $permitido -and ($gruposPC -contains $p.grupoPCs) }
            $existe = Get-Printer -Name $p.nome -ErrorAction SilentlyContinue
            if ($permitido -and -not $existe) { Instalar $p }
            elseif (-not $permitido -and $existe) { Remover $p }
            else { Log "Sem mudanca: $($p.nome) (permitido=$permitido, existe=$([bool]$existe))" }
            if ($permitido) { $nomesPermitidos += $p.nome }
        }
        catch { Log "ERRO em $($p.nome): $_" }
    }

    # Limpeza das demais impressoras: so para quem tem direito a alguma impressora do JSON
    # e somente se todas as permitidas realmente existem agora (ninguem fica sem impressora).
    if ($nomesPermitidos.Count -eq 0) {
        Log "Limpeza ignorada: usuario nao pertence a nenhum grupo de impressora."
    }
    else {
        $faltando = @($nomesPermitidos | Where-Object { -not (Get-Printer -Name $_ -ErrorAction SilentlyContinue) })
        if ($faltando) { Log "Limpeza ignorada: impressora permitida ausente ($($faltando -join ', '))." }
        else { LimparOutras $config $nomesPermitidos }
    }
}
catch { Log "ERRO geral (nada alterado alem do log): $_" }