# jt-monitor

Monitora encomendas J&T, Jadlog, Loggi e Correios/Sedex a cada 2 horas. A execucao acontece integralmente no Cloudflare Worker, o historico fica no Workers KV e os alertas sao enviados ao WhatsApp pela Green API.

O GitHub nao executa rastreios. Ele guarda o codigo, roda os testes e publica uma nova versao do Worker quando a pasta `worker/` muda na branch `main`.

## Arquitetura

1. O Cron Trigger da Cloudflare chama o Worker a cada 2 horas.
2. O Worker consulta as transportadoras configuradas.
3. Os eventos sao comparados com o estado salvo no binding KV `TRACKING_STATE`.
4. Eventos novos geram uma mensagem via Green API.
5. O novo estado e salvo no KV; nenhum commit automatico e criado no repositorio.

Na primeira consulta de cada codigo, o Worker salva silenciosamente o historico existente. Isso evita disparar todas as movimentacoes antigas durante a migracao.

## Configurar os rastreios

Edite as variaveis nao secretas em `worker/wrangler.toml`:

```toml
[vars]
WAYBILL_NO = "codigo-jt-1,codigo-jt-2"
WAYBILL_LABELS = "codigo-jt-1=Pedido A,codigo-jt-2=Pedido B"
JADLOG_CTE = "cte-jadlog"
JADLOG_LABELS = "cte-jadlog=Pedido Jadlog"
LOGGI_CODES = "codigo-loggi"
LOGGI_LABELS = "codigo-loggi=Pedido Loggi"
CORREIOS_CODES = "AA123456789BR"
CORREIOS_LABELS = "AA123456789BR=Pedido Sedex"
```

Listas e apelidos podem ficar vazios. O cron ignora uma transportadora sem codigos.

## Secrets do rastreador

Entre na pasta `worker`, autentique o Wrangler e cadastre cada secret pelo prompt interativo:

```bash
npx wrangler login
npx wrangler secret put CPF
npx wrangler secret put PACOTEVICIO_API_KEY
npx wrangler secret put WHATSAPP_PHONE
npx wrangler secret put GREEN_API_INSTANCE_ID
npx wrangler secret put GREEN_API_TOKEN
npx wrangler secret put RUN_TOKEN
```

Valores esperados:

| Secret | Valor |
|---|---|
| `CPF` | CPF usado nas consultas J&T, somente digitos |
| `PACOTEVICIO_API_KEY` | Chave RapidAPI usada por J&T e Correios |
| `WHATSAPP_PHONE` | Destinatario com DDI + DDD + numero, somente digitos |
| `GREEN_API_INSTANCE_ID` | `idInstance` fornecido pela Green API |
| `GREEN_API_TOKEN` | `apiTokenInstance` fornecido pela Green API |
| `RUN_TOKEN` | Token aleatorio longo para proteger `/run` e `/test-whatsapp` |

Para desenvolvimento local, copie `worker/.dev.vars.example` para `worker/.dev.vars` e preencha os valores. O arquivo real e ignorado pelo Git.

Como alternativa recomendada para deploy automatico, mantenha esses mesmos nomes nos secrets do GitHub. A action oficial sincroniza os valores como secrets do Worker durante a publicacao; eles nunca entram no `wrangler.toml`.

## Primeiro deploy

O namespace KV atual ja esta configurado em `worker/wrangler.toml`. Para validar e publicar manualmente:

```bash
cd worker
npm ci
npm test
npm run check
npm run deploy
```

Depois do deploy, o Cron Trigger `0 */2 * * *` aparece no painel da Cloudflare. Expressoes cron da Cloudflare usam UTC.

## CI/CD pelo GitHub

Cadastre estes secrets de infraestrutura no repositorio GitHub:

| Secret | Finalidade |
|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | Identifica a conta Cloudflare |
| `CLOUDFLARE_API_TOKEN` | Token com permissao para editar Workers |

Cadastre tambem os secrets de runtime listados anteriormente: `CPF`, `PACOTEVICIO_API_KEY`, `WHATSAPP_PHONE`, `GREEN_API_INSTANCE_ID`, `GREEN_API_TOKEN` e `RUN_TOKEN`.

O workflow `.github/workflows/deploy-worker.yml` executa testes e `wrangler deploy` em pushes para `main` que alterem o Worker. Pull requests executam validacao sem publicar.

Durante o deploy, a action oficial envia os secrets do GitHub diretamente para os bindings secretos do Worker. Em runtime, o rastreador le somente os valores armazenados pela Cloudflare.

O job sempre valida o endpoint publico depois do deploy. Uma mensagem real de teste so e enviada quando a execucao manual marca `test_whatsapp` ou quando a mensagem do commit contem `[test-whatsapp]`.

## Testes e execucao manual

O endpoint raiz e publico e retorna somente o status e a quantidade de codigos configurados:

```text
GET https://SEU-WORKER.workers.dev/
```

Os endpoints de acao aceitam apenas `POST` com o `RUN_TOKEN`:

```bash
curl -X POST \
  -H "Authorization: Bearer SEU_RUN_TOKEN" \
  https://SEU-WORKER.workers.dev/test-whatsapp

curl -X POST \
  -H "Authorization: Bearer SEU_RUN_TOKEN" \
  https://SEU-WORKER.workers.dev/run
```

`/test-whatsapp` testa apenas Green API. `/run` executa uma rodada completa. O antigo `/run` publico foi removido.

## Estado e comportamento

- Chaves KV seguem o formato `tracking:<transportadora>:<codigo>`.
- Estados antigos da J&T salvos pelo Worker anterior continuam sendo lidos.
- Encomendas entregues deixam de ser consultadas.
- Depois de 3 falhas consecutivas de consulta, um unico alerta de erro e enviado.
- Se o WhatsApp falhar, os eventos nao sao confirmados no KV e a notificacao sera tentada novamente no proximo cron.
- Logs ficam disponiveis na observabilidade do Worker.

## Codigo Python legado

`track.py`, `state/` e `run_local.ps1` foram mantidos como referencia e para diagnostico local. Eles nao fazem parte do agendamento nem do deploy atual.

## Limitacoes

- J&T e Correios dependem da RapidAPI/PacoteVicio e da cota contratada.
- Jadlog depende do HTML da consulta publica permanecer compativel.
- Loggi depende do endpoint publico da SuperFrete.
- Green API depende da sessao de WhatsApp continuar autorizada.
- Cron Triggers podem ter pequeno atraso em relacao ao minuto configurado.
