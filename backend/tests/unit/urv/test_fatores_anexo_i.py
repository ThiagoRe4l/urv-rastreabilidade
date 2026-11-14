"""Fatores de equivalência recalculados pelo Anexo I e comparados com `config_fator`. Art. 3º §2º."""

from decimal import ROUND_HALF_DOWN, Decimal

from sqlalchemy import select

from app.core.configuracao import fatores_vigentes
from app.core.decimais import quantizar
from app.models import ConfigFator, TipoVeiculo
from scripts.seed import VIGENCIA_PORTARIA

# Anexo I, item 1: pesos dos critérios.
PESO_A, PESO_C, PESO_R, PESO_D = Decimal("0.4"), Decimal("0.3"), Decimal("0.2"), Decimal("0.1")

# Anexo I, item 3: valores normalizados (Aproveitamento, Custo, Rastreabilidade, Desmontabilidade).
NORMALIZADOS: dict[TipoVeiculo, tuple[str, str, str, str]] = {
    TipoVeiculo.LICENCIADO_RODAGEM: ("1.00", "1.00", "1.00", "1.00"),
    TipoVeiculo.SUCATA_APROVEITAVEL: ("0.90", "0.80", "0.80", "0.90"),
    TipoVeiculo.SUCATA_MOTOR_INSERVIVEL: ("0.70", "0.60", "0.70", "0.80"),
    TipoVeiculo.SUCATA_INSERVIVEL: ("0.40", "0.30", "0.40", "0.50"),
    TipoVeiculo.SINISTRADO_PEQUENA_MEDIA: ("0.95", "0.90", "0.95", "0.95"),
    TipoVeiculo.SINISTRADO_GRANDE: ("0.80", "0.70", "0.85", "0.85"),
}

# Anexo I, item 2: valores de referência, de onde saem os normalizados (divididos pelos da base).
REFERENCIA: dict[TipoVeiculo, tuple[int, int, int, int]] = {
    TipoVeiculo.LICENCIADO_RODAGEM: (100, 10_000, 100, 100),
    TipoVeiculo.SUCATA_APROVEITAVEL: (90, 8_000, 80, 90),
    TipoVeiculo.SUCATA_MOTOR_INSERVIVEL: (70, 6_000, 70, 80),
    TipoVeiculo.SUCATA_INSERVIVEL: (40, 3_000, 40, 50),
    TipoVeiculo.SINISTRADO_PEQUENA_MEDIA: (95, 9_000, 95, 95),
    TipoVeiculo.SINISTRADO_GRANDE: (80, 7_000, 85, 85),
}


def fator_bruto(tipo: TipoVeiculo) -> Decimal:
    """Anexo I, item 4: 0,4 x A + 0,3 x C + 0,2 x R + 0,1 x D, sem arredondar."""
    a, c, r, d = (Decimal(v) for v in NORMALIZADOS[tipo])
    return PESO_A * a + PESO_C * c + PESO_R * r + PESO_D * d


def test_os_seis_fatores_do_anexo_i_batem_com_config_fator(db_session, dados_demo) -> None:
    configurados = {
        f.tipo_veiculo: f.fator
        for f in db_session.scalars(select(ConfigFator).where(ConfigFator.vigente_desde == VIGENCIA_PORTARIA))
    }
    assert set(configurados) == set(TipoVeiculo) == set(NORMALIZADOS)
    for tipo in TipoVeiculo:
        # Anexo I, item 5: terceira casa >= 5 arredonda a segunda para cima (ROUND_HALF_UP).
        assert quantizar(fator_bruto(tipo)) == configurados[tipo], tipo


def test_fatores_esperados_pela_portaria() -> None:
    assert {tipo: str(quantizar(fator_bruto(tipo))) for tipo in TipoVeiculo} == {
        TipoVeiculo.LICENCIADO_RODAGEM: "1.00",
        TipoVeiculo.SINISTRADO_PEQUENA_MEDIA: "0.94",
        TipoVeiculo.SUCATA_APROVEITAVEL: "0.85",
        TipoVeiculo.SINISTRADO_GRANDE: "0.79",
        TipoVeiculo.SUCATA_MOTOR_INSERVIVEL: "0.68",
        TipoVeiculo.SUCATA_INSERVIVEL: "0.38",
    }


def test_dois_fatores_dependem_do_arredondamento_meio_para_cima() -> None:
    # Os que têm terceira casa diferente de zero, isto é, os que o arredondamento altera.
    dependentes = {t: fator_bruto(t) for t in TipoVeiculo if fator_bruto(t) != quantizar(fator_bruto(t))}
    assert dependentes == {
        TipoVeiculo.SINISTRADO_PEQUENA_MEDIA: Decimal("0.935"),
        TipoVeiculo.SINISTRADO_GRANDE: Decimal("0.785"),
    }
    # Com a metade arredondada para baixo, os dois sairiam diferentes da tabela do art. 3º §2º.
    assert Decimal("0.935").quantize(Decimal("0.01"), rounding=ROUND_HALF_DOWN) == Decimal("0.93")
    assert Decimal("0.785").quantize(Decimal("0.01"), rounding=ROUND_HALF_DOWN) == Decimal("0.78")
    assert quantizar(Decimal("0.935")) == Decimal("0.94")
    assert quantizar(Decimal("0.785")) == Decimal("0.79")


def test_valores_normalizados_saem_dos_valores_de_referencia() -> None:
    base = REFERENCIA[TipoVeiculo.LICENCIADO_RODAGEM]
    for tipo, valores in REFERENCIA.items():
        normalizado = tuple(
            str(quantizar(Decimal(v) / Decimal(b))) for v, b in zip(valores, base, strict=True)
        )
        assert normalizado == NORMALIZADOS[tipo], tipo


def test_rota_de_fatores_devolve_os_do_anexo_i(db_session, dados_demo) -> None:
    vigentes = {f.tipo_veiculo: f.fator for f in fatores_vigentes(db_session, VIGENCIA_PORTARIA)}
    assert vigentes == {tipo: quantizar(fator_bruto(tipo)) for tipo in TipoVeiculo}
