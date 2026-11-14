import { describe, expect, it } from "vitest";

import { compararDecimal, deEscala, dividirHalfUp, formatarDecimal, normalizarEntrada, paraEscala } from "./decimal";
import { metaDoAno } from "./dominio";
import { cnpjValido, fmtCnpj, fmtData } from "./formato";

describe("decimal", () => {
  it("converte para escala fixa e de volta sem float", () => {
    expect(paraEscala("0.94", 2)).toBe(94n);
    expect(paraEscala("150000.00", 2)).toBe(15000000n);
    expect(paraEscala("-0.2", 2)).toBe(-20n);
    expect(paraEscala("1.005", 2)).toBe(101n); // HALF_UP; em float daria 1.00
    expect(deEscala(-5n, 2)).toBe("-0.05");
    expect(deEscala(123456n, 3)).toBe("123.456");
    expect(() => paraEscala("abc", 2)).toThrow();
  });

  it("divide com ROUND_HALF_UP", () => {
    expect(dividirHalfUp(1n, 2n)).toBe(1n);
    expect(dividirHalfUp(-1n, 2n)).toBe(-1n);
    expect(dividirHalfUp(149n, 100n)).toBe(1n);
    expect(dividirHalfUp(150n, 100n)).toBe(2n);
  });

  it("compara e formata em pt-BR", () => {
    expect(compararDecimal("79.99", "80")).toBe(-1);
    expect(compararDecimal("80.00", "80")).toBe(0);
    expect(formatarDecimal("150000.00")).toBe("150.000,00");
    expect(formatarDecimal("-0.20")).toBe("−0,20");
    expect(formatarDecimal("90", 2)).toBe("90,00");
    expect(formatarDecimal(null)).toBe("—");
  });

  it("normaliza a entrada do usuário para o formato do contrato", () => {
    expect(normalizarEntrada("1180,5", 3)).toBe("1180.500");
    expect(normalizarEntrada("180.000,00", 2)).toBe("180000.00");
    expect(normalizarEntrada("180000.00", 2)).toBe("180000.00");
  });
});

describe("apoio de domínio", () => {
  it("dá a meta de aproveitamento do ano (RF-12)", () => {
    expect(metaDoAno(2026)).toBeNull();
    expect(metaDoAno(2027)).toBe("80");
    expect(metaDoAno(2030)).toBe("85");
    expect(metaDoAno(2032)).toBe("90");
    expect(metaDoAno(2040)).toBe("95");
  });

  it("valida e formata CNPJ e data", () => {
    expect(cnpjValido("11.222.333/0001-81")).toBe(true);
    expect(cnpjValido("11444777000161")).toBe(true);
    expect(cnpjValido("11222333000180")).toBe(false);
    expect(cnpjValido("00000000000000")).toBe(false);
    expect(fmtCnpj("11222333000181")).toBe("11.222.333/0001-81");
    expect(fmtData("2026-11-13")).toBe("13/11/2026");
  });
});
