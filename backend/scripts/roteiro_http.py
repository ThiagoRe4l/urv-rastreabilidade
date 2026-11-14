"""Roteiro de demonstração (docs/04-plano-de-execucao.md) por HTTP, contra a API no ar.

    docker compose exec api python -m scripts.roteiro_http            # passos 1 a 9
    docker compose exec api python -m scripts.roteiro_http --verificar
    python -m scripts.roteiro_http --url http://localhost:8000         # da máquina, com o venv

Executa os nove passos com os usuários do seed, conferindo cada resposta, do cadastro do MMV
à verificação da cadeia. Também confere as tentativas barradas: chassi repetido, segunda
emissão de certificado, segunda transferência e chassi novo repetido. Para fechar o passo 9:

    docker compose exec api python -m scripts.adulterar
    docker compose exec api python -m scripts.roteiro_http --verificar   # integra=False
    docker compose exec api python -m scripts.adulterar --restaurar
    docker compose exec api python -m scripts.roteiro_http --verificar   # integra=True

Grava dados de verdade no banco (um veículo, um MMV, um consumo); chassis são sorteados a
cada execução, então o roteiro pode ser repetido. Sai com código 1 na primeira resposta
inesperada.
"""

import argparse
import secrets
import sys
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import httpx

SENHA = "demo1234"
ADMIN, AUDITOR = "admin@urv.local", "auditor@mdic.local"
OPERADOR, FISCAL = "operador@desmonte.local", "fiscal@montadora.local"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
CARACTERES_VIN = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"  # VIN não usa I, O e Q
BRASILIA = timezone(timedelta(hours=-3))


class Roteiro:
    def __init__(self, url: str) -> None:
        self.cli = httpx.Client(base_url=url.rstrip("/") + "/api/v1", timeout=30)
        self.tokens: dict[str, str] = {}
        self.checagens = 0
        self.agora = datetime.now(UTC).replace(microsecond=0)
        self.hoje = self.agora.astimezone(BRASILIA).date().isoformat()

    # --- apoio --------------------------------------------------------------------------------

    def h(self, email: str) -> dict[str, str]:
        if email not in self.tokens:
            r = self.cli.post("/auth/login", json={"email": email, "senha": SENHA})
            self.esperar(r, 200, rotulo=f"login {email}")
            self.tokens[email] = r.json()["access_token"]
        return {"Authorization": f"Bearer {self.tokens[email]}"}

    def esperar(self, r: httpx.Response, status: int, codigo: str | None = None, rotulo: str = "") -> Any:
        json = r.headers.get("content-type", "").startswith("application/json")
        corpo = r.json() if json else r.content
        if r.status_code != status or (codigo and corpo.get("codigo") != codigo):
            esperado = f"{status} {codigo or ''}".strip()
            pedido = f"{r.request.method} {r.request.url.path}"
            print(f"  FALHOU {rotulo}: {pedido} -> {r.status_code}, esperado {esperado}")
            print(f"  {r.text[:500]}")
            sys.exit(1)
        self.checagens += 1
        return corpo

    def get(self, caminho: str, email: str | None, status: int = 200, codigo: str | None = None, **kw) -> Any:
        r = self.cli.get(caminho, headers=self.h(email) if email else None, **kw)
        return self.esperar(r, status, codigo, caminho)

    def post(self, caminho: str, email: str, status: int = 201, codigo: str | None = None, **kw) -> Any:
        return self.esperar(self.cli.post(caminho, headers=self.h(email), **kw), status, codigo, caminho)

    @staticmethod
    def vin() -> str:
        return "9BW" + "".join(secrets.choice(CARACTERES_VIN) for _ in range(14))

    @staticmethod
    def passo(n: int, texto: str) -> None:
        print(f"\n{n}. {texto}")

    def etapa(self, vid: str, tipo: str, horas_atras: int) -> None:
        corpo = {
            "iniciada_em": (self.agora - timedelta(hours=horas_atras)).isoformat(),
            "concluida_em": (self.agora - timedelta(hours=horas_atras - 1)).isoformat(),
        }
        r = self.cli.put(f"/veiculos/{vid}/etapas/{tipo}", json=corpo, headers=self.h(OPERADOR))
        self.esperar(r, 200, rotulo=f"etapa {tipo}")

    def anexar(self, vid: str, tipo: str, etapa_tipo: str | None, pdf: bool = False) -> None:
        dados = {"tipo": tipo} | ({"etapa_tipo": etapa_tipo} if etapa_tipo else {})
        arquivo = ("doc.pdf", PDF, "application/pdf") if pdf else ("foto.png", PNG, "image/png")
        self.post(f"/veiculos/{vid}/anexos", OPERADOR, data=dados, files={"arquivo": arquivo})

    def verificar(self) -> dict:
        return self.get("/auditoria/verificar", AUDITOR)

    def dados_veiculo(self, chassi: str, **mudancas) -> dict:
        return {
            "chassi": chassi,
            "placa": "DEM0A26",
            "renavam": "12345678901",
            "data_entrada": self.hoje,
            "tipo": "SINISTRADO_PEQUENA_MEDIA",
            "origem_aquisicao": "LEILAO_SEGURADORA",
            "documento_entrada_tipo": "NF_ENTRADA",
            "documento_entrada_numero": "NF-DEMO-1",
            "certidao_baixa_numero": "CB-DEMO-1",
            "peso_entrada_kg": "1180.500",
            "sem_viabilidade_desmontagem": False,
            **mudancas,
        }

    # --- roteiro -------------------------------------------------------------------------------

    def executar(self) -> None:
        self.passo(1, "Administrador: desmontadora credenciada, fabricante e vínculo")
        empresas = self.get("/empresas", ADMIN)["itens"]
        desmonte = next(e for e in empresas if e["tipo"] == "DESMONTADORA")
        montadora = next(e for e in empresas if e["tipo"] == "FABRICANTE")
        assert desmonte["credenciamento_vigente"], desmonte
        assert montadora["registro_compromissos"], montadora
        vinculos = self.get("/vinculos", ADMIN)["itens"]
        assert any(
            v["geradora_id"] == desmonte["id"] and v["fabricante_id"] == montadora["id"] and v["ativo"]
            for v in vinculos
        )
        print(
            f"  {desmonte['razao_social']}: {desmonte['credenciamento_status']}"
            f" até {desmonte['credenciamento_validade']}"
        )
        print(f"  {montadora['razao_social']}: registro de compromissos; vínculo ativo")

        self.passo(2, "Fabricante cadastra um MMV")
        mmv = self.post(
            "/mmvs",
            FISCAL,
            json={
                "codigo": f"DEMO-{secrets.token_hex(3).upper()}",
                "ncm": "8703.23.10",
                "nivel": 1,
                "percentual_reciclabilidade": "92.50",
                "ja_comercializado": False,
            },
        )
        print(
            f"  MMV {mmv['codigo']}: nível {mmv['nivel']}, RM {mmv['rm']},"
            f" efeitos a partir de {mmv['efeitos_a_partir_de']}"
        )

        self.passo(3, "Desmontadora recebe o veículo, anexa nota, certidão e fotos, e classifica")
        chassi = self.vin()
        veiculo = self.post("/veiculos", OPERADOR, json=self.dados_veiculo(chassi))
        vid = veiculo["id"]
        print(f"  chassi {chassi}: tipo efetivo {veiculo['tipo']} até anexar a evidência (art. 2º §5º)")
        self.anexar(vid, "DOCUMENTO_ENTRADA", None, pdf=True)
        self.anexar(vid, "CERTIDAO_BAIXA", None, pdf=True)
        self.anexar(vid, "FOTO", "RECEPCAO")
        self.anexar(vid, "EVIDENCIA_CLASSIFICACAO", None, pdf=True)
        self.etapa(vid, "RECEPCAO", 10)
        detalhe = self.get(f"/veiculos/{vid}", OPERADOR)
        assert detalhe["tipo"] == "SINISTRADO_PEQUENA_MEDIA" and not detalhe["rebaixado"], detalhe
        print(f"  com a evidência: tipo {detalhe['tipo']}; {len(detalhe['anexos'])} anexos")

        self.passo(4, "Descontaminação, desmontagem com peças etiquetadas, pesos por material e DMR")
        self.etapa(vid, "DESCONTAMINACAO", 8)
        self.anexar(vid, "FOTO", "DESCONTAMINACAO")
        self.etapa(vid, "DESMONTAGEM", 6)
        self.anexar(vid, "FOTO", "DESMONTAGEM")
        porta = self.post(
            f"/veiculos/{vid}/pecas",
            OPERADOR,
            json={
                "nome": "Porta dianteira esquerda",
                "descricao": "Sem amassados",
                "classificacao": "REUTILIZAVEL",
                "condicao": "USADA",
                "destino": "ESTOQUE",
            },
        )
        cinto = self.post(
            f"/veiculos/{vid}/pecas",
            OPERADOR,
            json={"nome": "Cinto de segurança", "classificacao": "NAO_REUTILIZAVEL", "destino": "DESCARTE"},
        )
        r = self.cli.patch(f"/pecas/{cinto['id']}", json={"descaracterizada": True}, headers=self.h(OPERADOR))
        self.esperar(r, 200, rotulo="descaracterizar")
        publico = self.get(f"/pecas/rastreio/{porta['codigo_rastreio']}", None)  # sem token
        print(f"  etiqueta pública {porta['codigo_rastreio']}: {publico['nome']}, chassi {publico['chassi']}")
        pecas = self.get("/pecas", OPERADOR, params={"veiculo_id": vid})
        assert pecas["total"] == 2 and {p["chassi"] for p in pecas["itens"]} == {chassi}
        self.etapa(vid, "DESTRUICAO", 4)
        self.anexar(vid, "FOTO", "DESTRUICAO")
        for fracao, destino, peso in (
            ("FERROSO", "RECICLAGEM", "780.000"),
            ("NAO_FERROSO", "RECICLAGEM", "95.500"),
            ("NAO_METALICO", "RECUPERACAO_ENERGETICA", "120.000"),
            ("NAO_METALICO", "REJEITO", "60.000"),
        ):
            pesagem = {"fracao": fracao, "destino": destino, "peso_kg": peso}
            self.post(f"/veiculos/{vid}/pesagens", OPERADOR, json=pesagem)
        pesagens = self.get(f"/veiculos/{vid}/pesagens", OPERADOR)
        print(
            f"  {pesagens['total']} pesagens, {pesagens['peso_total_kg']} kg, "
            f"{pesagens['percentual_aproveitado']}% aproveitado; meta do ano: {pesagens['meta_ano']}"
        )
        dmr = self.post(
            f"/veiculos/{vid}/dmrs",
            OPERADOR,
            json={
                "numero": f"DMR-{secrets.token_hex(3).upper()}",
                "destinatario_nome": "Siderúrgica Exemplo",
                "destinatario_cnpj": "11.444.777/0001-61",
                "tipo_material": "Sucata ferrosa",
                "peso_kg": "780.000",
            },
        )
        print(f"  DMR {dmr['numero']} com MTR {dmr['mtr_numero']}")

        self.passo(5, "Responsável técnico assina o laudo; certificado emitido e crédito no saldo")
        self.get(f"/veiculos/{vid}/laudo", OPERADOR, 404, "NAO_ENCONTRADO")
        recusa = self.post(f"/veiculos/{vid}/certificado", OPERADOR, 422, "PENDENCIAS_CERTIFICADO")
        pend = recusa["pendencias"]
        print(f"  sem laudo, o certificado é recusado: {pend}")
        laudo = self.post(
            f"/veiculos/{vid}/laudo",
            OPERADOR,
            json={"responsavel_nome": "Eng. Ana Souza", "responsavel_registro": "CREA-PR 12345"},
        )
        assert self.get(f"/veiculos/{vid}/laudo", AUDITOR)["id"] == laudo["id"]
        saldo_antes = self.get("/urv/saldo", OPERADOR)["saldo"]
        cert = self.post(f"/veiculos/{vid}/certificado", OPERADOR)
        saldo_depois = self.get("/urv/saldo", OPERADOR)["saldo"]
        print(
            f"  certificado {cert['numero']}: fator {cert['fator']},"
            f" crédito {cert['credito']['quantidade']} URV; "
            f"saldo da desmontadora {saldo_antes} -> {saldo_depois}"
        )
        self.post(f"/veiculos/{vid}/certificado", OPERADOR, 409, "CERTIFICADO_JA_EMITIDO")
        print("  segunda emissão para o mesmo chassi: 409 CERTIFICADO_JA_EMITIDO")

        self.passo(6, "Desmontadora transfere o crédito ao fabricante")
        saldo_fab_antes = self.get("/urv/saldo", FISCAL)["saldo"]
        transferir = f"/urv/creditos/{cert['credito']['id']}/transferir"
        credito = self.post(transferir, OPERADOR, 200, json={"fabricante_id": montadora["id"]})
        destino = {"fabricante_id": montadora["id"]}
        self.post(transferir, OPERADOR, 409, "CREDITO_JA_TRANSFERIDO", json=destino)
        saldo_fab = self.get("/urv/saldo", FISCAL)["saldo"]
        print(
            f"  crédito {credito['status']} para {credito['titular']['razao_social']}; "
            f"saldo do fabricante {saldo_fab_antes} -> {saldo_fab}; segunda transferência: 409"
        )

        self.passo(7, "Fabricante indica os chassis vendidos; o débito é calculado e o saldo baixa")
        novos = [self.vin(), self.vin()]
        sim = self.post(
            "/urv/consumos/simular",
            FISCAL,
            200,
            json={"mmv_id": mmv["id"], "quantidade": len(novos), "preco_medio": "180000.00"},
        )
        m = sim["memoria_calculo"]
        print(
            f"  simulação: {m['formula']} = ({m['qv']} / {m['rm']}) * {m['multiplicador']}"
            f" = {sim['urv_debito']} URV"
        )
        corpo = {"mmv_id": mmv["id"], "periodo": self.hoje[:7], "preco_medio": "180000.00", "chassis": novos}
        consumo = self.post("/urv/consumos", FISCAL, json=corpo)
        saldo_final = self.get("/urv/saldo", FISCAL)["saldo"]
        print(f"  consumo de {consumo['urv_debito']} URV; saldo do fabricante {saldo_fab} -> {saldo_final}")
        self.post("/urv/consumos", FISCAL, 409, "CHASSI_JA_CONSUMIDO", json=corpo | {"chassis": [novos[0]]})
        print("  o mesmo chassi novo em outro consumo: 409 CHASSI_JA_CONSUMIDO")

        self.passo(8, "Auditor busca o chassi, vê a linha do tempo e verifica a cadeia de hashes")
        achados = self.get("/veiculos", AUDITOR, params={"chassi": chassi})["itens"]
        assert [v["id"] for v in achados] == [vid]
        det = self.get(f"/veiculos/{vid}", AUDITOR)
        completo = self.get(f"/certificados/{det['certificado_id']}", AUDITOR)
        trilha = self.get("/auditoria/eventos", AUDITOR, params={"veiculo_id": vid, "tamanho": 100})
        tipos = {e["tipo"] for e in trilha["itens"]}
        assert {"VEICULO_RECEBIDO", "ANEXO_ENVIADO", "LAUDO_ASSINADO", "CERTIFICADO_EMITIDO"} <= tipos, tipos
        do_chassi_novo = self.get("/urv/consumos", AUDITOR, params={"chassi": novos[1]})
        assert [c["id"] for c in do_chassi_novo["itens"]] == [consumo["id"]]
        print(f"  veículo {det['estado']}, {len(det['etapas'])} etapas, {len(det['anexos'])} anexos")
        print(
            f"  certificado com laudo de {completo['laudo']['responsavel_nome']},"
            f" crédito {completo['credito']['status']}"
        )
        print(f"  {trilha['total']} eventos da trilha ligados ao veículo: {', '.join(sorted(tipos))}")
        print(f"  o chassi novo {novos[1]} aparece no consumo {consumo['id']}")
        v = self.verificar()
        assert v["integra"], v
        print(f"  cadeia íntegra, {v['total']} eventos")

        self.passo(9, "Tentativa barrada: o mesmo chassi de novo (a adulteração é por scripts.adulterar)")
        disfarcado = self.dados_veiculo(f" {chassi.lower()} ", placa="XYZ9Z99", tipo="SUCATA_INSERVIVEL")
        self.post("/veiculos", OPERADOR, 409, "CHASSI_DUPLICADO", json=disfarcado)
        print("  o mesmo chassi, em minúsculas e com espaços: 409 CHASSI_DUPLICADO")
        print(f"\nRoteiro concluído: {self.checagens} respostas conferidas, todas como esperado.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--url", default="http://localhost:8000", help="Endereço da API (%(default)s)")
    parser.add_argument("--verificar", action="store_true", help="Só verifica a cadeia de hashes")
    args = parser.parse_args()
    roteiro = Roteiro(args.url)
    if args.verificar:
        v = roteiro.verificar()
        print(f"Cadeia: integra={v['integra']}, total={v['total']}, primeira_quebra={v['primeira_quebra']}")
        sys.exit(0 if v["integra"] else 2)
    roteiro.executar()


if __name__ == "__main__":
    main()
