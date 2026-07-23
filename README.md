# jt-tracker

Monitora rastreios de encomendas a cada 2 horas via GitHub Actions. Quando aparece um evento novo, envia um alerta no seu WhatsApp via CallMeBot.

## Como funciona

1. Os workflows rodam a cada 2 horas.
2. `track.py` consulta J&T/Correios via PacoteVicio, Jadlog pelo metodo publico atual e Loggi via rastreamento publico da SuperFrete.
3. Compara os eventos com o que foi salvo nos arquivos da pasta `state/` no commit anterior.
4. Se aparecer evento novo, dispara um GET no CallMeBot que cai no seu WhatsApp.
5. Commita os arquivos de estado atualizados de volta no repo.

## Passo 1: criar o repo

Crie um repo novo no GitHub (pode ser privado, melhor) e jogue todos esses arquivos dentro. Estrutura:

```
.
├── .github/workflows/track.yml
├── .github/workflows/track-correios.yml
├── state/
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

Para rastrear Correios/Sedex e J&T sem depender de scraping instavel, o projeto usa a API PacoteVicio
via RapidAPI. O plano BASIC gratuito informa limite de 1.000 requisicoes/mes; por isso o
workflow dos Correios roda separado, a cada 2 horas, e o workflow principal tambem roda a cada 2 horas
para J&T, Jadlog e Loggi. Crie tambem:

| Nome                  | Valor                                                                    |
|-----------------------|--------------------------------------------------------------------------|
| `CORREIOS_CODES`      | Codigos separados por virgula, ex `AD687043754BR`                        |
| `CORREIOS_LABELS`     | Opcional. Apelidos, ex `AD687043754BR=Sedex Cliente X`                   |
| `LOGGI_CODES`         | Codigos separados por virgula, ex `QAW7XWXS`                             |
| `LOGGI_LABELS`        | Opcional. Apelidos, ex `QAW7XWXS=Pedido Loggi`                           |
| `PACOTEVICIO_API_KEY` | Secret com a chave `X-RapidAPI-Key` do PacoteVicio para Correios e J&T   |

Como pegar a chave:

1. Acesse https://rapidapi.com/pacotevicio-pacotevicio-default/api/correios-rastreamento-de-encomendas
2. Assine o plano BASIC gratuito.
3. Na aba **Endpoints**, confirme que o exemplo usa o host `correios-rastreamento-de-encomendas.p.rapidapi.com` e copie a chave exibida como `X-RapidAPI-Key`.
4. Cadastre no GitHub em **Settings -> Secrets and variables -> Actions -> New repository secret** com o nome `PACOTEVICIO_API_KEY`.

Esta variable e **opcional**. Use apenas se quiser voltar a J&T para o endpoint oficial antigo:

| Nome          | Valor                                                  |
|---------------|--------------------------------------------------------|
| `JT_PROVIDER` | `official` para nao usar PacoteVicio na J&T            |

## Passo 4: ativar o workflow

GitHub Actions vem desabilitado em repos privados as vezes. Va na aba **Actions** do repo e clique em "I understand my workflows, go ahead and enable them" se aparecer.

Depois, clique em **jt-tracker → Run workflow** pra disparar uma rodada manual e ver se ta tudo certo nos logs.

## Como saber se funcionou

- Aba **Actions** mostra o historico de runs. Verde = ok, vermelho = quebrou.
- Clique numa run e abra o passo "Run tracker" pra ver o log do script. Mensagens esperadas:
  - `[ok] N eventos no rastreio` → fetch funcionou.
  - `[ok] sem mudancas` → estado igual ao anterior, sem alerta.
  - `[novo] N eventos novos` → vai disparar o WhatsApp.
- Os arquivos da pasta `state/` vao ser atualizados e voce ve o commit feito pelo `jt-tracker-bot`.

## Trocar pra outra encomenda

Edita a variable `WAYBILL_NO` (e o secret `CPF` se for outro destinatario). Apague o arquivo correspondente dentro de `state/` se quiser comecar do zero para uma encomenda.

Para Sedex/Correios, edite `CORREIOS_CODES` em **Variables**. Exemplo:

```
CORREIOS_CODES=AD687043754BR
CORREIOS_LABELS=AD687043754BR=Sedex Exemplo
```

Para Loggi, edite `LOGGI_CODES` em **Variables**. Exemplo:

```
LOGGI_CODES=QAW7XWXS
LOGGI_LABELS=QAW7XWXS=Pedido Loggi
```

## Custo

GitHub Actions tem 2000 min/mes free em repo privado e ilimitado em publico. Para Correios/J&T, o PacoteVicio informa plano gratuito de 1.000 requisicoes/mes; com o intervalo atual de 2 em 2 horas, 1 codigo usa cerca de 360 requisicoes/mes.

## Limitacoes conhecidas

- A J&T usa PacoteVicio por padrao quando `PACOTEVICIO_API_KEY` existe. Para voltar ao endpoint oficial antigo, defina `JT_PROVIDER=official`.
- Correios e J&T dependem da disponibilidade do PacoteVicio/RapidAPI e da cota do plano escolhido.
- A Jadlog ainda usa consulta publica propria, porque ela nao aparece na API PacoteVicio.
- A Loggi usa o rastreamento publico da SuperFrete, entao depende desse endpoint continuar publico.
- CallMeBot e gratuito mas nao tem SLA. Pra producao seria melhor um servico pago (Twilio, etc).
- O cron do GitHub Actions tem um delay tipico de 1-5 min em relacao ao horario marcado. Nao da pra confiar em "exato" de 2 em 2 horas.
