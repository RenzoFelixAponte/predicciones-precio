# Captura rangos de los Excel de salida tal como se ven en Excel (imagen PNG).
# Uso: powershell -ExecutionPolicy Bypass -File src\capturas_excel.ps1
$base = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $base "informe\tesis\figuras"
$capturas = @(
    @{ archivo = "exportBIMBO.XLSX";              hoja = 1;                      rango = "A1:R16"; png = "xl_00_original.png" },
    @{ archivo = "salidas\01_limpio.xlsx";        hoja = "resumen";              rango = "A1:B17"; png = "xl_01_resumen.png" },
    @{ archivo = "salidas\01_limpio.xlsx";        hoja = "rectificadas";         rango = "A1:J12"; png = "xl_01_rectificadas.png" },
    @{ archivo = "salidas\02_senales.xlsx";       hoja = 1;                      rango = "A1:P16"; png = "xl_02_senales.png" },
    @{ archivo = "salidas\03_marcado.xlsx";       hoja = "candidatos";           rango = "A1:Q16"; png = "xl_03_marcado.png" },
    @{ archivo = "salidas\04_reglas.xlsx";        hoja = "metricas";             rango = "A1:I10"; png = "xl_04_metricas.png" },
    @{ archivo = "salidas\05_alertas_pedido.xlsx"; hoja = "metricas_por_periodo"; rango = "A1:K7";  png = "xl_05_metricas_pedido.png" },
    @{ archivo = "salidas\05_alertas_pedido.xlsx"; hoja = "alertas";              rango = "A1:R14"; png = "xl_05_alertas.png" }
)
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
try {
    foreach ($c in $capturas) {
        $wb = $xl.Workbooks.Open((Join-Path $base $c.archivo), 0, $true)
        $ws = $wb.Worksheets.Item($c.hoja)
        $ws.Activate()
        $r = $ws.Range($c.rango)
        $r.Columns.AutoFit() | Out-Null
        foreach ($col in $r.Columns) { if ($col.ColumnWidth -gt 30) { $col.ColumnWidth = 30 } }
        for ($i = 0; $i -lt 10; $i++) {          # el portapapeles a veces está ocupado
            try { $r.CopyPicture(1, 2) | Out-Null; break } catch { Start-Sleep -Milliseconds 500 }
        }
        $ch = $ws.ChartObjects().Add(0, 0, $r.Width + 4, $r.Height + 4)
        $ch.Chart.ChartArea.Format.Line.Visible = 0
        $ch.Activate(); Start-Sleep -Milliseconds 300
        $ch.Chart.Paste()
        $ch.Chart.Export((Join-Path $dest $c.png)) | Out-Null
        $ch.Delete()
        $wb.Close($false)
        "ok " + $c.png
    }
} finally { $xl.Quit(); [System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null }
