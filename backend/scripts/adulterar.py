"""Demonstração: adulterar um evento direto no banco e ver a verificação acusar.

    python -m scripts.adulterar                 # adultera o último evento
    python -m scripts.adulterar --sequencia 5   # adultera o evento 5
    python -m scripts.adulterar --restaurar     # desfaz a adulteração

Passos:
1. Verifica a cadeia (deve estar íntegra).
2. Tenta um UPDATE comum: o gatilho do banco rejeita.
3. Simula um atacante com acesso de dono da tabela: desliga o gatilho, altera o
   payload do evento (acrescenta "_adulterado": true) e religa o gatilho.
4. Verifica de novo: a cadeia acusa a quebra na sequência alterada.

`--restaurar` retira a chave "_adulterado" (o JSONB volta idêntico) e a cadeia
volta a fechar. Não use fora de ambiente de demonstração.
"""

import argparse
import sys

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.modules.auditoria.service import verificar_cadeia

GATILHO = "trg_evento_auditoria_imutavel"


def _mostrar_verificacao(session: Session, titulo: str) -> bool:
    r = verificar_cadeia(session)
    situacao = "ÍNTEGRA" if r.integra else f"QUEBRADA na sequência {r.primeira_quebra}"
    print(f"{titulo}: {r.total} eventos, cadeia {situacao}")
    return r.integra


def _sem_gatilho(session: Session, sql: str, params: dict) -> int:
    session.execute(text(f"ALTER TABLE evento_auditoria DISABLE TRIGGER {GATILHO}"))
    linhas = session.execute(text(sql), params).rowcount
    session.execute(text(f"ALTER TABLE evento_auditoria ENABLE TRIGGER {GATILHO}"))
    session.commit()
    return linhas


def adulterar(sequencia: int | None) -> int:
    with SessionLocal() as session:
        if sequencia is None:
            sequencia = session.scalar(text("SELECT max(sequencia) FROM evento_auditoria"))
        if sequencia is None:
            print("Não há eventos. Rode o seed primeiro.")
            return 1
        _mostrar_verificacao(session, "1. Antes")

        print(f"2. UPDATE direto no evento {sequencia}...")
        try:
            session.execute(
                text("UPDATE evento_auditoria SET tipo = 'ALTERADO' WHERE sequencia = :s"), {"s": sequencia}
            )
            session.commit()
            print("   ATENÇÃO: o banco aceitou o UPDATE. O gatilho não está ativo.")
        except DBAPIError as exc:
            session.rollback()
            print(f"   Rejeitado pelo banco: {str(exc.orig).splitlines()[0]}")

        print(f"3. Desligando o gatilho e alterando o payload do evento {sequencia}...")
        linhas = _sem_gatilho(
            session,
            "UPDATE evento_auditoria SET payload = payload || '{\"_adulterado\": true}'::jsonb "
            "WHERE sequencia = :s",
            {"s": sequencia},
        )
        if linhas == 0:
            print(f"   Evento {sequencia} não existe.")
            return 1

        integra = _mostrar_verificacao(session, "4. Depois")
        print("   Desfazer: python -m scripts.adulterar --restaurar")
        return 0 if not integra else 2


def restaurar() -> int:
    with SessionLocal() as session:
        linhas = _sem_gatilho(
            session,
            "UPDATE evento_auditoria SET payload = payload - '_adulterado' "
            "WHERE payload ->> '_adulterado' IS NOT NULL",
            {},
        )
        print(f"Eventos restaurados: {linhas}")
        return 0 if _mostrar_verificacao(session, "Verificação") else 2


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--sequencia", type=int, help="sequência do evento a adulterar (padrão: o último)")
    parser.add_argument("--restaurar", action="store_true", help="desfaz a adulteração de demonstração")
    args = parser.parse_args()
    sys.exit(restaurar() if args.restaurar else adulterar(args.sequencia))


if __name__ == "__main__":
    main()
