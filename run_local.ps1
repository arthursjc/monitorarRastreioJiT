[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:WAYBILL_NO      = "888030708823905,888030674620597"
$env:WAYBILL_LABELS  = "888030708823905=ZPHC Reta 120mg,888030674620597=Reta Antiga"
$env:CALLMEBOT_PHONE = "5512988416345"
$env:CALLMEBOT_APIKEY = "8084407"
$env:CPF             = "41795685867"
$env:JADLOG_CTE      = "13740300131749"
$env:JADLOG_LABELS   = "13740300131749=Meu Pedido Jadlog"

# Apaga state para forcar reenvio (comente para simular execucao normal)
Remove-Item state\*.json -Force -ErrorAction SilentlyContinue

python track.py
