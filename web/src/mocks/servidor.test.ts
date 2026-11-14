// Percorre o roteiro de demonstração de docs/04-plano-de-execucao.md contra o backend simulado,
// pelas mesmas rotas que a interface chama. Garante que o roteiro é executável com o mock ligado.

import { describe, expect, it } from "vitest";

import type * as T from "../api/types";
import { calcularDebito, criarServidor, ID_DESMONTADORA, ID_FABRICANTE, prazoReporte, regularizarAte } from "./servidor";

type Corpo = Record<string, unknown>;

function ambiente(agora = new Date(2026, 10, 13, 10, 0)) {
  const relogio = { agora };
  const servidor = criarServidor(undefined, () => new Date(relogio.agora));
  const tokens = new Map<string, string>();

  function chamar<R = Corpo>(quem: string | null, metodo: string, rota: string, corpo?: unknown) {
    const [caminho, consulta = ""] = rota.split("?");
    const r = servidor.responder({
      metodo,
      caminho,
      consulta: new URLSearchParams(consulta),
      corpo,
      token: quem ? tokens.get(quem) : null,
    });
    return { status: r.status, corpo: r.corpo as R & Partial<T.ErroApi> };
  }
  function entrar(email: string) {
    const r = chamar<T.LoginSaida>(null, "POST", "/auth/login", { email, senha: "demo1234" });
    expect(r.status).toBe(200);
    tokens.set(email, r.corpo.access_token);
    return r.corpo.usuario;
  }
  return { chamar, entrar, relogio };
}

const ADMIN = "admin@urv.local";
const OPERADOR = "operador@desmonte.local";
const FISCAL = "fiscal@montadora.local";
const AUDITOR = "auditor@mdic.local";
const CHASSI = "9BWZZZ377VT004251";

const VEICULO = {
  chassi: CHASSI,
  placa: "ABC1D23",
  renavam: "12345678901",
  data_entrada: "2026-11-13",
  tipo: "SUCATA_APROVEITAVEL",
  origem_aquisicao: "COMPRA_DIRETA",
  documento_entrada_tipo: "NF_ENTRADA",
  documento_entrada_numero: "NF-1001",
  certidao_baixa_numero: "CB-2026-77",
  peso_entrada_kg: "1180.500",
  sem_viabilidade_desmontagem: false,
};

const arquivo = (nome: string, tipo = "image/jpeg") => new File(["conteudo"], nome, { type: tipo });

describe("roteiro de demonstração no mock", () => {
  it("vai do credenciamento ao consumo e à verificação da cadeia", () => {
    const { chamar, entrar } = ambiente();

    // 1. O administrador mostra a desmontadora credenciada, o fabricante e o vínculo.
    expect(entrar(ADMIN).papel).toBe("ADMIN");
    const empresas = chamar<T.Pagina<T.Empresa>>(ADMIN, "GET", "/empresas").corpo.itens;
    expect(empresas.find((e) => e.id === ID_DESMONTADORA)?.credenciamento_vigente).toBe(true);
    expect(empresas.find((e) => e.id === ID_FABRICANTE)?.registro_compromissos).toBe(true);
    expect(chamar<T.Pagina<T.Vinculo>>(ADMIN, "GET", "/vinculos").corpo.itens[0].ativo).toBe(true);

    // 2. O fabricante cadastra um MMV.
    entrar(FISCAL);
    const mmv = chamar<T.Mmv>(FISCAL, "POST", "/mmvs", {
      codigo: "EX-SEDAN-1.0",
      ncm: "8703.22.10",
      nivel: 1,
      percentual_reciclabilidade: "85",
      ja_comercializado: false,
    });
    expect(mmv.status).toBe(201);
    expect(mmv.corpo.rm).toBe(10);
    expect(mmv.corpo.efeitos_a_partir_de).toBe("2026-11-13"); // RF-04: MMV novo vale na data do cadastro

    // 3. A desmontadora recebe o veículo, anexa documentos e fotos e classifica o tipo.
    entrar(OPERADOR);
    const criado = chamar<T.Veiculo>(OPERADOR, "POST", "/veiculos", VEICULO);
    expect(criado.status).toBe(201);
    const id = criado.corpo.id;
    // RF-07: sem evidência, entra como sucata inservível com o tipo declarado preservado.
    expect(criado.corpo.tipo).toBe("SUCATA_INSERVIVEL");
    expect(criado.corpo.tipo_declarado).toBe("SUCATA_APROVEITAVEL");

    const anexar = (tipo: T.AnexoTipo, etapa_tipo: T.EtapaTipo, nome = "foto.jpg") =>
      expect(
        chamar(OPERADOR, "POST", `/veiculos/${id}/anexos`, { arquivo: arquivo(nome), tipo, etapa_tipo }).status,
      ).toBe(201);
    const etapa = (tipo: T.EtapaTipo) =>
      expect(
        chamar(OPERADOR, "PUT", `/veiculos/${id}/etapas/${tipo}`, {
          iniciada_em: "2026-11-13T12:00:00.000Z",
          concluida_em: "2026-11-13T13:00:00.000Z",
        }).status,
      ).toBe(200);
    const detalhe = () => chamar<T.VeiculoDetalhe>(OPERADOR, "GET", `/veiculos/${id}`).corpo;

    // A emissão antes da hora é barrada com a lista do que falta (RF-15).
    const cedo = chamar(OPERADOR, "POST", `/veiculos/${id}/certificado`);
    expect(cedo.status).toBe(422);
    expect(cedo.corpo.codigo).toBe("PENDENCIAS_CERTIFICADO");
    expect(cedo.corpo.pendencias?.length).toBeGreaterThan(5);

    anexar("DOCUMENTO_ENTRADA", "RECEPCAO", "nf.pdf");
    anexar("CERTIDAO_BAIXA", "RECEPCAO");
    anexar("FOTO", "RECEPCAO");
    anexar("EVIDENCIA_CLASSIFICACAO", "RECEPCAO");
    expect(detalhe().tipo).toBe("SUCATA_APROVEITAVEL");
    etapa("RECEPCAO");
    expect(detalhe().estado).toBe("EM_PROCESSO");

    // 4. Descontaminação, desmontagem com peças etiquetadas, pesos por material e DMR.
    anexar("FOTO", "DESCONTAMINACAO");
    etapa("DESCONTAMINACAO");
    anexar("FOTO", "DESMONTAGEM");
    const reutilizavel = chamar<T.Peca>(OPERADOR, "POST", `/veiculos/${id}/pecas`, {
      nome: "Alternador",
      descricao: "",
      classificacao: "REUTILIZAVEL",
      condicao: "USADA",
      destino: "ESTOQUE",
    }).corpo;
    expect(reutilizavel.etiqueta).toMatchObject({ nome: "Alternador", chassi: CHASSI, cnpj: "11222333000181" });
    const sucata = chamar<T.Peca>(OPERADOR, "POST", `/veiculos/${id}/pecas`, {
      nome: "Airbag",
      descricao: "",
      classificacao: "NAO_REUTILIZAVEL",
      condicao: "USADA",
      destino: "DESCARTE",
    }).corpo;
    expect(detalhe().pendencias_certificado.some((p) => p.includes("Airbag"))).toBe(true);
    expect(chamar(OPERADOR, "PATCH", `/pecas/${sucata.id}`, { descaracterizada: true }).status).toBe(200);
    etapa("DESMONTAGEM");

    // A página pública da etiqueta não exige login.
    const publica = chamar<T.Rastreio>(null, "GET", `/pecas/rastreio/${reutilizavel.codigo_rastreio}`);
    expect(publica.status).toBe(200);
    expect(publica.corpo.destino).toBe("ESTOQUE");

    anexar("FOTO", "DESTRUICAO");
    const pesar = (fracao: string, destino: string, peso_kg: string) =>
      expect(chamar(OPERADOR, "POST", `/veiculos/${id}/pesagens`, { fracao, destino, peso_kg }).status).toBe(201);
    pesar("FERROSO", "RECICLAGEM", "800");
    pesar("NAO_METALICO", "REJEITO", "100");
    pesar("FLUIDOS", "RECUPERACAO_ENERGETICA", "100");
    // RF-12, art. 18 §5º: 900 kg aproveitados sobre os 1.180,5 kg de entrada (A2 da revisão).
    expect(chamar<T.Pesagens>(OPERADOR, "GET", `/veiculos/${id}/pesagens`).corpo.percentual_aproveitado).toBe("76.24");
    etapa("DESTRUICAO");
    const dmr = chamar<T.Dmr>(OPERADOR, "POST", `/veiculos/${id}/dmrs`, {
      numero: "DMR-1",
      destinatario_nome: "Siderúrgica Exemplo",
      destinatario_cnpj: "11.444.777/0001-61",
      tipo_material: "Sucata ferrosa",
      peso_kg: "800",
    });
    expect(dmr.corpo.mtr_numero).toMatch(/^MTR-SIM-/);

    // 5. Laudo, certificado e crédito no saldo.
    expect(detalhe().pendencias_certificado).toEqual(["Falta o laudo assinado pelo responsável técnico"]);
    expect(
      chamar(OPERADOR, "POST", `/veiculos/${id}/laudo`, { responsavel_nome: "Ana Souza", responsavel_registro: "CREA-PR 1" }).status,
    ).toBe(201);
    expect(detalhe().estado).toBe("LAUDO_EMITIDO");
    const cert = chamar<T.Certificado>(OPERADOR, "POST", `/veiculos/${id}/certificado`);
    expect(cert.status).toBe(201);
    expect(cert.corpo.fator).toBe("0.85"); // art. 3º §2º
    expect(cert.corpo.meta_ano).toBeNull(); // 2026: sem meta, só registro
    expect(chamar<T.Saldo>(OPERADOR, "GET", "/urv/saldo").corpo.saldo).toBe("0.85");
    expect(detalhe().pendencias_certificado).toEqual([]);
    // O detalhe do veículo aponta o certificado (PM-03 a) e o laudo tem rota própria (PM-WEB-03).
    const certificadoId = detalhe().certificado_id;
    expect(certificadoId).toBe(cert.corpo.id);
    const completo = chamar<T.CertificadoDetalhe>(OPERADOR, "GET", `/certificados/${certificadoId}`).corpo;
    expect(completo.laudo?.responsavel_nome).toBe("Ana Souza");
    expect(completo.credito?.status).toBe("DISPONIVEL");
    expect(chamar<T.Laudo>(OPERADOR, "GET", `/veiculos/${id}/laudo`).corpo.responsavel_nome).toBe("Ana Souza");
    // PM-04: segunda emissão é conflito, não pendência.
    expect(chamar(OPERADOR, "POST", `/veiculos/${id}/certificado`).status).toBe(409);

    etapa("DESTINACAO");
    expect(detalhe().estado).toBe("ENCERRADO");

    // 6. Transferência ao fabricante: direta e única.
    const credito = chamar<T.Pagina<T.Credito>>(OPERADOR, "GET", "/urv/creditos").corpo.itens[0];
    expect(credito.chassi).toBe(CHASSI);
    // A geradora só vê os fabricantes com vínculo.
    const destinos = chamar<T.Pagina<T.Empresa>>(OPERADOR, "GET", "/empresas?tipo=FABRICANTE").corpo.itens;
    expect(destinos.map((e) => e.id)).toEqual([ID_FABRICANTE]);
    const transferir = () =>
      chamar<T.Credito>(OPERADOR, "POST", `/urv/creditos/${credito.id}/transferir`, { fabricante_id: ID_FABRICANTE });
    // A8: antes da transferência o fabricante não lê o dossiê; depois, como titular, lê.
    expect(chamar(FISCAL, "GET", `/certificados/${credito.certificado_id}`).status).toBe(404);
    expect(transferir().corpo.status).toBe("TRANSFERIDO");
    expect(chamar(FISCAL, "GET", `/certificados/${credito.certificado_id}`).status).toBe(200);
    expect(chamar(FISCAL, "GET", `/veiculos/${id}/laudo`).status).toBe(200);
    expect(chamar(FISCAL, "GET", `/veiculos/${id}/dmrs`).status).toBe(200);
    expect(chamar(FISCAL, "GET", `/veiculos/${id}/pesagens`).status).toBe(403);
    const deNovo = transferir();
    expect(deNovo.status).toBe(409);
    expect(deNovo.corpo.codigo).toBe("CREDITO_JA_TRANSFERIDO");
    expect(chamar<T.Saldo>(OPERADOR, "GET", "/urv/saldo").corpo.saldo).toBe("0.00");
    expect(chamar<T.Saldo>(FISCAL, "GET", "/urv/saldo").corpo.saldo).toBe("0.85");

    // 7. O fabricante informa os chassis vendidos; o débito é simulado e depois baixado.
    const novos = ["9BWZZZ377VT100001", "9BWZZZ377VT100002", "9BWZZZ377VT100003", "9BWZZZ377VT100004"];
    const sim = chamar<T.Simulacao>(FISCAL, "POST", "/urv/consumos/simular", {
      mmv_id: mmv.corpo.id,
      quantidade: novos.length,
      preco_medio: "180000.00",
    });
    expect(sim.status).toBe(200);
    expect(sim.corpo.urv_debito).toBe("0.48"); // (4 / 10) × (180000 / 150000)
    expect(sim.corpo.saldo_apos).toBe("0.37");
    const consumo = chamar<T.Consumo>(FISCAL, "POST", "/urv/consumos", {
      mmv_id: mmv.corpo.id,
      periodo: "2026-11",
      preco_medio: "180000.00",
      chassis: novos,
    });
    expect(consumo.status).toBe(201);
    expect(consumo.corpo).toMatchObject({ urv_debito: "0.48", saldo_apos: "0.37", fora_do_prazo: false, regularizar_ate: null });
    expect(chamar<T.Saldo>(FISCAL, "GET", "/urv/saldo").corpo.saldo).toBe("0.37");
    // RF-21: um chassi novo consome uma vez.
    const repetido = chamar(FISCAL, "POST", "/urv/consumos", {
      mmv_id: mmv.corpo.id,
      periodo: "2026-11",
      preco_medio: "180000.00",
      chassis: [novos[0]],
    });
    expect(repetido.status).toBe(409);
    expect(repetido.corpo.codigo).toBe("CHASSI_JA_CONSUMIDO");

    // 8. O auditor busca o chassi, lê tudo e verifica a cadeia.
    entrar(AUDITOR);
    const achados = chamar<T.Pagina<T.Veiculo>>(AUDITOR, "GET", `/veiculos?chassi=${CHASSI}`).corpo.itens;
    expect(achados).toHaveLength(1);
    // ?veiculo_id= traz também os registros ligados ao veículo, como o crédito gerado (L-13).
    const eventos = chamar<T.Pagina<T.Evento>>(AUDITOR, "GET", `/auditoria/eventos?veiculo_id=${id}&tamanho=100`).corpo;
    expect(eventos.total).toBeGreaterThan(15);
    expect(eventos.itens.map((e) => e.tipo)).toContain("CREDITO_GERADO");
    expect(eventos.itens.map((e) => e.tipo)).not.toContain("MMV_CADASTRADO");
    expect(chamar<T.RelatorioMdic>(AUDITOR, "GET", "/relatorios/mdic?ano=2026").corpo).toMatchObject({
      registros: 1,
      certificados_emitidos: 1,
      urv_gerada: "0.85",
      urv_transferida: "0.85",
      urv_consumida: "0.48",
    });
    expect(chamar<T.Verificacao>(AUDITOR, "GET", "/auditoria/verificar").corpo.integra).toBe(true);
    // O auditor nunca escreve (art. 24 V).
    const escrita = chamar(AUDITOR, "POST", "/veiculos", VEICULO);
    expect(escrita.status).toBe(403);
    expect(escrita.corpo.codigo).toBe("AUDITOR_SOMENTE_LEITURA");

    // 9. Duas tentativas barradas: o mesmo chassi de novo e um evento adulterado.
    const duplicado = chamar(OPERADOR, "POST", "/veiculos", VEICULO);
    expect(duplicado.status).toBe(409);
    expect(duplicado.corpo.codigo).toBe("CHASSI_DUPLICADO");
    const adulterado = chamar<{ sequencia: number }>(AUDITOR, "POST", "/__mock/adulterar").corpo.sequencia;
    expect(chamar<T.Verificacao>(AUDITOR, "GET", "/auditoria/verificar").corpo).toMatchObject({
      integra: false,
      primeira_quebra: adulterado,
    });
  });

  it("aceita saldo negativo até 31/12/2027 e recusa depois (RF-19)", () => {
    const { chamar, entrar, relogio } = ambiente();
    entrar(FISCAL);
    const mmv = chamar<T.Mmv>(FISCAL, "POST", "/mmvs", {
      codigo: "EX-SUV",
      ncm: "8703.23.10",
      nivel: 2,
      percentual_reciclabilidade: "80.5",
      ja_comercializado: false,
    }).corpo;
    const consumir = (chassi: string) =>
      chamar<T.Consumo>(FISCAL, "POST", "/urv/consumos", {
        mmv_id: mmv.id,
        periodo: "2026-10",
        preco_medio: "100000",
        chassis: [chassi],
      });

    const aceito = consumir("9BWZZZ377VT200001");
    expect(aceito.status).toBe(201);
    // Nível 2: RM 5. Preço abaixo do base não reduz o débito: 1 / 5 = 0,20.
    expect(aceito.corpo).toMatchObject({ urv_debito: "0.20", saldo_apos: "-0.20", regularizar_ate: "2027-02-28" });
    // Período de outubro, registrado em 13/11, antes do décimo dia útil de novembro.
    expect(aceito.corpo).toMatchObject({ prazo_reporte: "2026-11-13", fora_do_prazo: false });
    expect(chamar<T.Saldo>(FISCAL, "GET", "/urv/saldo").corpo).toEqual({
      empresa_id: ID_FABRICANTE,
      saldo: "-0.20",
      regularizar_ate: "2027-02-28",
    });

    relogio.agora = new Date(2028, 0, 3, 9, 0);
    const recusado = consumir("9BWZZZ377VT200002");
    expect(recusado.status).toBe(409);
    expect(recusado.corpo.codigo).toBe("SALDO_INSUFICIENTE");
  });

  it("recusa consumo com MMV que ainda não produz efeitos (RF-04)", () => {
    const { chamar, entrar } = ambiente();
    entrar(FISCAL);
    const mmv = chamar<T.Mmv>(FISCAL, "POST", "/mmvs", {
      codigo: "EX-HATCH",
      ncm: "8703.21.00",
      nivel: 1,
      percentual_reciclabilidade: "85",
      ja_comercializado: true,
    }).corpo;
    expect(mmv.efeitos_a_partir_de).toBe("2027-01-01");
    const r = chamar(FISCAL, "POST", "/urv/consumos", {
      mmv_id: mmv.id,
      periodo: "2026-11",
      preco_medio: "150000",
      chassis: ["9BWZZZ377VT300001"],
    });
    expect(r.status).toBe(422);
    expect(r.corpo.codigo).toBe("MMV_SEM_EFEITOS");
  });

  it("barra transferência sem vínculo ativo (RF-17)", () => {
    const { chamar, entrar } = ambiente();
    entrar(ADMIN);
    entrar(OPERADOR);
    const vinculo = chamar<T.Pagina<T.Vinculo>>(ADMIN, "GET", "/vinculos").corpo.itens[0];
    chamar(ADMIN, "PATCH", `/vinculos/${vinculo.id}`, { ativo: false });
    // Veículo sem viabilidade de desmontagem: dispensa a etapa de desmontagem.
    const id = chamar<T.Veiculo>(OPERADOR, "POST", "/veiculos", {
      ...VEICULO,
      tipo: "SUCATA_INSERVIVEL",
      sem_viabilidade_desmontagem: true,
    }).corpo.id;
    for (const [tipo, etapa] of [
      ["DOCUMENTO_ENTRADA", "RECEPCAO"],
      ["CERTIDAO_BAIXA", "RECEPCAO"],
      ["FOTO", "RECEPCAO"],
      ["FOTO", "DESCONTAMINACAO"],
      ["FOTO", "DESTRUICAO"],
    ]) {
      chamar(OPERADOR, "POST", `/veiculos/${id}/anexos`, { arquivo: arquivo("a.jpg"), tipo, etapa_tipo: etapa });
    }
    for (const tipo of ["RECEPCAO", "DESCONTAMINACAO", "DESTRUICAO"]) {
      chamar(OPERADOR, "PUT", `/veiculos/${id}/etapas/${tipo}`, {
        iniciada_em: "2026-11-13T12:00:00.000Z",
        concluida_em: "2026-11-13T13:00:00.000Z",
      });
    }
    chamar(OPERADOR, "POST", `/veiculos/${id}/pesagens`, { fracao: "FERROSO", destino: "RECICLAGEM", peso_kg: "900" });
    chamar(OPERADOR, "POST", `/veiculos/${id}/laudo`, { responsavel_nome: "Ana", responsavel_registro: "1" });
    const cert = chamar<T.Certificado>(OPERADOR, "POST", `/veiculos/${id}/certificado`);
    expect(cert.status).toBe(201);
    expect(cert.corpo.fator).toBe("0.38");
    const r = chamar(OPERADOR, "POST", `/urv/creditos/${cert.corpo.credito!.id}/transferir`, { fabricante_id: ID_FABRICANTE });
    expect(r.status).toBe(422);
    expect(r.corpo.codigo).toBe("SEM_VINCULO");
  });
});

describe("regras de cálculo do mock", () => {
  it("calcula o débito em 0,01 com ROUND_HALF_UP (RF-18)", () => {
    expect(calcularDebito(1, 10, "150000.00", "150000.00").debito).toBe("0.10");
    expect(calcularDebito(1, 5, "90000.00", "150000.00").debito).toBe("0.20"); // max(1, pm/pb)
    expect(calcularDebito(3, 10, "175000.00", "150000.00").debito).toBe("0.35"); // 0,35 exato
    expect(calcularDebito(1, 10, "157500.00", "150000.00").debito).toBe("0.11"); // 0,105 sobe
    expect(calcularDebito(7, 5, "200000.00", "150000.00").debito).toBe("1.87"); // 1,8666…
  });

  it("acha o décimo dia útil do mês seguinte (RF-20)", () => {
    expect(prazoReporte("2026-10")).toBe("2026-11-13"); // novembro de 2026 começa em um domingo
    expect(prazoReporte("2026-12")).toBe("2027-01-14");
  });

  it("dá o último dia do terceiro mês seguinte (RF-19)", () => {
    expect(regularizarAte(new Date(2026, 10, 13))).toBe("2027-02-28");
    expect(regularizarAte(new Date(2027, 11, 31))).toBe("2028-03-31");
  });
});
