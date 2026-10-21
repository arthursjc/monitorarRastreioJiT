[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:WAYBILL_NO      = "888030708823905,888030674620597"
$env:WAYBILL_LABELS  = "888030708823905=ZPHC Reta 120mg,888030674620597=Reta Antiga"
# Defina CPF, WHATSAPP_PHONE, GREEN_API_INSTANCE_ID e GREEN_API_TOKEN no
# ambiente antes de executar. Nunca coloque credenciais neste arquivo.
$env:JADLOG_CTE      = "13740300131749"
$env:JADLOG_LABELS   = "13740300131749=Meu Pedido Jadlog"
$env:CORREIOS_CODES  = "AD687043754BR"
$env:CORREIOS_LABELS = "AD687043754BR=Sedex Exemplo"

python track.py
