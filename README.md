# jt-tracker

Monitora o rastreio de uma encomenda da J&T Express Brasil a cada 15 minutos via GitHub Actions. Quando aparece um evento novo, envia um alerta no seu WhatsApp via CallMeBot.

## Como funciona

1. O workflow `track.yml` roda a cada 15 min.
2. `track.py` chama o endpoint `getDetailByWaybillNo` da J&T.
3. Compara os eventos com o que foi salvo em `state/last_status.json` no commit anterior.
4. Se aparecer evento novo, dispara um GET no CallMeBot que cai no seu WhatsApp.
5. Commita o `state/last_status.json` atualizado de volta no repo.

## Passo 1: criar o repo

Crie um repo novo no GitHub (pode ser privado, melhor) e jogue todos esses arquivos dentro. Estrutura:

```
.
├── .github/workflows/track.yml
├── state/last_status.json
├── track.py
├── .gitignore
└── README.md
```

## Passo 2: ativar o CallMeBot

1. Salve este contato no celular: **+34 644 51 95 23** (nome qualquer, ex: "CallMeBot").
2. Abra o WhatsApp e envie pra esse numero a mensagem exata: `I allow callmebot to send me messages`
3. Aguarde a resposta automatica com seu **APIKey** (chega em alguns minutos).
4. Anote seu telefone com codigo do pais sem o `+`. Exemplo: `5511999999999`.

Doc oficial: https://www.callmebot.com/blog/free-api-whatsapp-messages/

## Passo 3: configurar os secrets no GitHub

No repo, va em **Settings → Secrets and variables → Actions → New repository secret** e crie:

| Nome              | Valor                                                                    |
|-------------------|--------------------------------------------------------------------------|
| `WAYBILL_NO`      | `888030695848780`                                                        |
| `CPF`             | `41795685867`                                                            |
| `CALLMEBOT_PHONE` | seu telefone com codigo do pais sem `+`, ex `5511999999999`              |
| `CALLMEBOT_APIKEY`| APIKey que o bot te mandou no WhatsApp                                   |

Para rastrear Correios/Sedex sem contrato dos Correios, o projeto usa a API PacoteVicio
via RapidAPI. O plano BASIC gratuito informa limite de 1.000 requisicoes/mes; por isso o
workflow dos Correios roda separado, a cada 2 horas. Crie tambem:

| Nome                  | Valor                                                                    |
|-----------------------|--------------------------------------------------------------------------|
| `CORREIOS_CODES`      | Codigos separados por virgula, ex `AD687043754BR`                        |
| `CORREIOS_LABELS`     | Opcional. Apelidos, ex `AD687043754BR=Sedex Cliente X`                   |
| `PACOTEVICIO_API_KEY` | Secret com a chave `X-RapidAPI-Key` do PacoteVicio                       |

Como pegar a chave:

1. Acesse https://rapidapi.com/pacotevicio-pacotevicio-default/api/correios-rastreamento-de-encomendas
2. Assine o plano BASIC gratuito.
3. Copie a chave exibida como `X-RapidAPI-Key`.
4. Cadastre no GitHub em **Settings -> Secrets and variables -> Actions -> New repository secret** com o nome `PACOTEVICIO_API_KEY`.

Os secrets abaixo sao **opcionais**. Se o curl original parar de funcionar (HTTP 401/403 ou body de erro), capture valores frescos no navegador (DevTools → aba Network → request `getDetailByWaybillNo` → copy headers) e cadastre aqui:

| Nome           | Quando usar                                            |
|----------------|--------------------------------------------------------|
| `JT_SIGN`      | Se a J&T comecar a recusar pela assinatura             |
| `JT_KEY`       | Idem                                                   |
| `JT_TIMESTAMP` | Idem. Use o timestamp em ms                            |

## Passo 4: ativar o workflow

GitHub Actions vem desabilitado em repos privados as vezes. Va na aba **Actions** do repo e clique em "I understand my workflows, go ahead and enable them" se aparecer.

Depois, clique em **jt-tracker → Run workflow** pra disparar uma rodada manual e ver se ta tudo certo nos logs.

## Como saber se funcionou

- Aba **Actions** mostra o historico de runs. Verde = ok, vermelho = quebrou.
- Clique numa run e abra o passo "Run tracker" pra ver o log do script. Mensagens esperadas:
  - `[ok] N eventos no rastreio` → fetch funcionou.
  - `[ok] sem mudancas` → estado igual ao anterior, sem alerta.
  - `[novo] N eventos novos` → vai disparar o WhatsApp.
- O `state/last_status.json` vai ser atualizado e voce ve o commit feito pelo `jt-tracker-bot`.

## Trocar pra outra encomenda

Edita o secret `WAYBILL_NO` (e `CPF` se for outro destinatario). Apaga o conteudo de `state/last_status.json` deixando so `{"events": []}` se quiser comecar do zero.

Para Sedex/Correios, edite `CORREIOS_CODES` em **Variables**. Exemplo:

```
CORREIOS_CODES=AD687043754BR
CORREIOS_LABELS=AD687043754BR=Sedex Exemplo
```

## Custo

GitHub Actions tem 2000 min/mes free em repo privado e ilimitado em publico. Para Correios, o PacoteVicio informa plano gratuito de 1.000 requisicoes/mes; com o cron atual de 2 em 2 horas, 1 codigo usa cerca de 360 requisicoes/mes.

## Limitacoes conhecidas

- A J&T pode bloquear se acharem que e bot. Se voltar HTTP 401/403 ou body com erro de assinatura, capture headers frescos do browser e cadastre nos secrets `JT_SIGN`/`JT_KEY`/`JT_TIMESTAMP`.
- O Correios depende da disponibilidade do PacoteVicio/RapidAPI e da cota do plano escolhido.
- CallMeBot e gratuito mas nao tem SLA. Pra producao seria melhor um servico pago (Twilio, etc).
- O cron do GitHub Actions tem um delay tipico de 1-5 min em relacao ao horario marcado. Nao da pra confiar em "exato" 15 min.
