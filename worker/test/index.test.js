import assert from "node:assert/strict";
import test from "node:test";

import worker, {
  cleanText,
  configuredTrackings,
  diffEvents,
  extractCorreiosEvents,
  extractJadlogEvents,
  extractJtEvents,
  extractLoggiEvents,
  runAll,
} from "../src/index.js";

class MemoryKv {
  constructor() { this.values = new Map(); }
  async get(key, type) {
    const value = this.values.get(key);
    if (value === undefined) return null;
    return type === "json" ? JSON.parse(value) : value;
  }
  async put(key, value) { this.values.set(key, value); }
}

test("parsers normalizam respostas das quatro transportadoras", () => {
  assert.deepEqual(extractJtEvents({ jtexpress_object: { details: [{ pathInfo: [{ scanTime: "2026-10-20 10:00", status: "Em trânsito", customerTracking: "Unidade A" }] }] } }), [
    { time: "2026-10-20 10:00", status: "Em trânsito", desc: "Unidade A", deliveryName: "" },
  ]);
  assert.equal(extractJadlogEvents('<span class="txt-status">Em transferência<br><small class="txt-data">20/10/2026 - 11:00</small></span>')[0].status, "Em transferência");
  assert.equal(extractLoggiEvents({ provider_tracking: { tracking: { eventos: [{ data: "2026-10-20 12:00", status: "Coletado", unidade: "São Paulo" }] } } })[0].desc, "São Paulo");
  assert.equal(extractCorreiosEvents({ correios_object: { eventos: [{ dtHrCriado: "2026-10-20 13:00:00", descricaoFrontEnd: "POSTADO" }] } })[0].status, "POSTADO");
});

test("diff de eventos não repete evento já conhecido", () => {
  const oldEvents = [{ time: "1", status: "A", desc: "B" }];
  const newEvents = [...oldEvents, { time: "2", status: "C", desc: "D" }];
  assert.deepEqual(diffEvents(oldEvents, newEvents), [newEvents[1]]);
});

test("configuração cria rastreios para todas as listas", () => {
  const result = configuredTrackings({ WAYBILL_NO: "1", JADLOG_CTE: "2", LOGGI_CODES: "abc", CORREIOS_CODES: "xy123br" });
  assert.deepEqual(result.map(({ carrier, code }) => [carrier, code]), [["jt", "1"], ["jadlog", "2"], ["loggi", "ABC"], ["correios", "XY123BR"]]);
});

test("primeira execução envia o status atual uma vez e salva o histórico", async (context) => {
  const kv = new MemoryKv();
  let greenCalls = 0;
  let sentPayload;
  context.mock.method(globalThis, "fetch", async (url, options) => {
    if (String(url).includes("jtjms-br.com")) {
      return Response.json({ data: { details: [{ scanTime: "2026-10-20 10:00", status: "Coletado", customerTracking: "Origem" }] } });
    }
    greenCalls += 1;
    sentPayload = JSON.parse(options.body);
    return Response.json({ idMessage: "message-id" });
  });
  const env = {
    TRACKING_STATE: kv,
    WAYBILL_NO: "123",
    JT_PROVIDER: "official",
    CPF: "12345678900",
    WHATSAPP_PHONE: "5512999999999",
    GREEN_API_INSTANCE_ID: "1234",
    GREEN_API_TOKEN: "secret",
  };
  const firstResult = await runAll(env);
  assert.equal(firstResult[0].status, "initialized");
  assert.equal(greenCalls, 1);
  assert.match(sentPayload.message, /Monitoramento iniciado/);
  assert.match(sentPayload.message, /Coletado/);
  assert.equal(JSON.parse(kv.values.get("tracking:jt:123")).events.length, 1);

  const secondResult = await runAll(env);
  assert.equal(secondResult[0].status, "unchanged");
  assert.equal(greenCalls, 1);
});

test("primeira execução sem eventos também confirma o monitoramento", async (context) => {
  const kv = new MemoryKv();
  let sentPayload;
  context.mock.method(globalThis, "fetch", async (url, options) => {
    if (String(url).includes("jtjms-br.com")) return Response.json({ data: { details: [] } });
    sentPayload = JSON.parse(options.body);
    return Response.json({ idMessage: "message-id" });
  });
  const env = {
    TRACKING_STATE: kv,
    WAYBILL_NO: "123",
    JT_PROVIDER: "official",
    CPF: "12345678900",
    WHATSAPP_PHONE: "5512999999999",
    GREEN_API_INSTANCE_ID: "1234",
    GREEN_API_TOKEN: "secret",
  };
  const result = await runAll(env);
  assert.equal(result[0].status, "initialized");
  assert.match(sentPayload.message, /Ainda não há movimentações/);
  assert.deepEqual(JSON.parse(kv.values.get("tracking:jt:123")).events, []);
});

test("evento posterior envia WhatsApp e atualiza KV", async (context) => {
  const kv = new MemoryKv();
  await kv.put("tracking:jt:123", JSON.stringify({ events: [{ time: "1", status: "Coletado", desc: "Origem" }] }));
  let sentPayload;
  context.mock.method(globalThis, "fetch", async (url, options) => {
    if (String(url).includes("jtjms-br.com")) {
      return Response.json({ data: { details: [
        { scanTime: "2", status: "Em trânsito", customerTracking: "Destino" },
        { scanTime: "1", status: "Coletado", customerTracking: "Origem" },
      ] } });
    }
    sentPayload = JSON.parse(options.body);
    return Response.json({ idMessage: "message-id" });
  });
  const env = {
    TRACKING_STATE: kv,
    WAYBILL_NO: "123",
    JT_PROVIDER: "official",
    CPF: "12345678900",
    WHATSAPP_PHONE: "5512999999999",
    GREEN_API_INSTANCE_ID: "1234",
    GREEN_API_TOKEN: "secret",
  };
  const result = await runAll(env);
  assert.equal(result[0].status, "notified");
  assert.equal(sentPayload.chatId, "5512999999999@c.us");
  assert.match(sentPayload.message, /Em trânsito/);
  assert.equal(JSON.parse(kv.values.get("tracking:jt:123")).events.length, 2);
});

test("endpoints manuais exigem POST e token", async () => {
  const env = { RUN_TOKEN: "run-secret", TRACKING_STATE: new MemoryKv() };
  assert.equal((await worker.fetch(new Request("https://example.com/run"), env)).status, 405);
  assert.equal((await worker.fetch(new Request("https://example.com/run", { method: "POST" }), env)).status, 401);
});

test("limpeza mantém cidade legível e remove sigla", () => {
  assert.equal(cleanText("Chegada", "[SJC] pacote recebido"), "Chegada São José dos Campos pacote recebido");
});
