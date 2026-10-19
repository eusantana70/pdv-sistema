const TABELA_NCM = {
  "21050010": {
    ncmFormatado: "2105.00.10",
    descricao: "Sorvetes com leite/cacau em embalagens <= 2kg",
    cest: "23.001.00",
    ipi: 0.0325,
    icmsMG: 0.18,
    mvaST: 0.70,
    ibptFederal: 0.1558,
    ibptEstadual: 0.18,
    ibptMunicipal: 0
  },
  "21050090": {
    ncmFormatado: "2105.00.90",
    descricao: "Outros sorvetes (sem leite / base agua)",
    cest: "23.001.00",
    ipi: 0.0325,
    icmsMG: 0.18,
    mvaST: 0.70,
    ibptFederal: 0.1558,
    ibptEstadual: 0.18,
    ibptMunicipal: 0
  },
  "default": {
    ncmFormatado: null,
    descricao: "Produto nao especificado",
    cest: null,
    ipi: 0,
    icmsMG: 0.18,
    mvaST: 0.70,
    ibptFederal: 0.1345,
    ibptEstadual: 0.17,
    ibptMunicipal: 0
  }
};

const ALIQUOTAS = {
  pisCofins: {
    simples: { pis: 0, cofins: 0, obs: "Embutido no DAS, sem destaque (LC 123/2006)" },
    presumido: { pis: 0.0065, cofins: 0.03, obs: "Regime cumulativo (Lei 9.718/1998)" },
    real: { pis: 0.0165, cofins: 0.076, obs: "Regime nao-cumulativo (Leis 10.637/2002 e 10.833/2003)" }
  },
  ibs: 0.001,
  cbs: 0.009
};

function normalizarNCM(ncm) {
  if (!ncm) return "21050010";
  const d = String(ncm).replace(/\D/g, "");
  return TABELA_NCM[d] ? d : (d.length === 8 ? "default" : "21050010");
}

function round2(v) {
  return Math.round((v + Number.EPSILON) * 100) / 100;
}

function calcularItem(raw, opts = {}) {
  const uf = (opts.uf || "MG").toUpperCase();
  const regime = (opts.regime || "simples").toLowerCase();
  const comST = opts.comST !== undefined ? opts.comST : true;

  const quantidade = Number(raw.quantidade ?? raw.qtd ?? 1);
  const valorUnitario = Number(raw.valor_unitario ?? raw.valorUnitario ?? raw.preco ?? raw.valor ?? 0);
  const base = round2(quantidade * valorUnitario);

  const chaveNCM = normalizarNCM(raw.ncm ?? raw.NCM ?? raw.perfil_fiscal?.ncm);
  const ref = TABELA_NCM[chaveNCM] || TABELA_NCM.default;
  const tab = TABELA_NCM[chaveNCM] ? TABELA_NCM[chaveNCM] : { ...TABELA_NCM.default, ncmFormatado: chaveNCM };

  const aliqICMS = uf === "MG" ? ref.icmsMG : 0.18;
  let icms = { cst: "00", csosn: "102", cfop: "5102", base: base, aliquota: aliqICMS, valor: 0, st: null };

  if (comST) {
    const baseST = round2(base * (1 + ref.mvaST));
    const icmsSTPotencial = round2(baseST * aliqICMS - base * aliqICMS);
    icms = {
      cst: "60",
      csosn: "500",
      cfop: uf === "MG" ? "5405" : "5405",
      base: 0,
      aliquota: 0,
      valor: 0,
      st: {
        motivo: "ICMS recolhido anteriormente por ST (Convenio ICMS 142/2018, item 23.001.00)",
        mva: ref.mvaST,
        baseST,
        valorSTPotencial: icmsSTPotencial
      }
    };
  } else {
    icms.valor = round2(base * aliqICMS);
  }

  const vIPI = round2(base * ref.ipi);
  const regra = ALIQUOTAS.pisCofins[regime] || ALIQUOTAS.pisCofins.simples;
  const vPIS = round2(base * regra.pis);
  const vCOFINS = round2(base * regra.cofins);
  const vIBS = round2(base * ALIQUOTAS.ibs);
  const vCBS = round2(base * ALIQUOTAS.cbs);
  const vTotTrib = round2(base * (ref.ibptFederal + ref.ibptEstadual + ref.ibptMunicipal));

  return {
    descricao: raw.descricao ?? raw.nome ?? "Item",
    quantidade,
    valor_unitario: valorUnitario,
    subtotal: base,
    ncm: tab.ncmFormatado || chaveNCM,
    cest: tab.cest,
    cfop: icms.cfop,
    csosn: icms.csosn,
    cst_icms: icms.cst,
    tributos: {
      icms_base: icms.base,
      icms_aliquota: icms.aliquota,
      icms_valor: icms.valor,
      icms_st: icms.st,
      ipi_aliquota: ref.ipi,
      ipi_valor: vIPI,
      pis_aliquota: regra.pis,
      pis_valor: vPIS,
      cofins_aliquota: regra.cofins,
      cofins_valor: vCOFINS,
      ibs_aliquota: ALIQUOTAS.ibs,
      ibs_valor: vIBS,
      cbs_aliquota: ALIQUOTAS.cbs,
      cbs_valor: vCBS,
      vTotTrib_ibpt: vTotTrib
    }
  };
}

function calcularNota(itens, opts = {}) {
  const calculados = itens.map((i) => calcularItem(i, opts));
  const soma = (k) => round2(calculados.reduce((a, i) => a + (i.tributos[k] || 0), 0));
  const vProdutos = round2(calculados.reduce((a, i) => a + i.subtotal, 0));

  return {
    itens: calculados,
    totais: {
      vProdutos,
      vICMS: soma("icms_valor"),
      vIPI: soma("ipi_valor"),
      vPIS: soma("pis_valor"),
      vCOFINS: soma("cofins_valor"),
      vIBS: soma("ibs_valor"),
      vCBS: soma("cbs_valor"),
      vTotTrib: soma("vTotTrib_ibpt"),
      vNF: round2(vProdutos + soma("ipi_valor"))
    }
  };
}

module.exports = { TABELA_NCM, ALIQUOTAS, calcularItem, calcularNota, normalizarNCM };
