const express = require("express");
const { calcularNota } = require("./tributacao");

const app = express();
const PORT = 3000;

app.use(express.json());

const notas = new Map();

function digitos(n) {
  let s = "";
  for (let i = 0; i < n; i++) s += Math.floor(Math.random() * 10);
  return s;
}

function gerarChaveAcesso() {
  const now = new Date();
  const aa = String(now.getFullYear()).slice(2);
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const cUF = "31";
  const cnpj = digitos(14);
  const mod = "65";
  const serie = "001";
  const nNF = digitos(9);
  const tpEmis = "1";
  const cNF = digitos(8);
  const parcial = `${cUF}${aa}${mm}${cnpj}${mod}${serie}${nNF}${tpEmis}${cNF}`;
  const dv = digitos(1);
  return (parcial + dv).slice(0, 44);
}

function gerarProtocolo() {
  return `131${digitos(12)}`;
}

function gerarIdNota() {
  return `nota_${Date.now().toString(36)}${digitos(4)}`;
}

function extrairItens(body) {
  if (Array.isArray(body.itens)) return body.itens;
  if (Array.isArray(body.items)) return body.items;
  if (Array.isArray(body.produtos)) return body.produtos;
  return [];
}

function gerarEspelhoTXT(nota) {
  const f2 = (n) => Number(n ?? 0).toFixed(2);
  const L = [];
  L.push("================ ESPELHO NFC-e MODELO 65 (MOCK, SEM VALOR FISCAL) ================");
  L.push("Emitente: Sorvetes Franquia MG - CNPJ 00.000.000/0001-91 - IE 000.000.000-00");
  L.push("Endereco: Av. Teste, 123 - Belo Horizonte/MG - CEP 30000-000");
  const cli = nota.cliente?.nome || nota.cliente?.name || "CONSUMIDOR FINAL (nao identificado)";
  L.push(`Destinatario: ${cli}  UF destino: ${nota.uf}  Regime: ${nota.regime_tributario}`);
  L.push(`Venda PDV: ${nota.venda_id ?? "-"}  Emissao: ${nota.autorizado_em}`);
  L.push(`ID: ${nota.id_nota}`);
  L.push(`Chave de acesso (44d): ${nota.chave_acesso}`);
  L.push(`Protocolo: ${nota.protocolo}  Status: ${nota.status.toUpperCase()}`);
  L.push("--------------------------------------------------------------------------------");
  L.push(`ITENS (${nota.itens.length}):`);
  nota.itens.forEach((it, i) => {
    const t = it.tributos || {};
    L.push(`${i + 1}. ${it.descricao}  ${it.quantidade}x R$ ${f2(it.valor_unitario)} = R$ ${f2(it.subtotal)}`);
    L.push(`   NCM ${it.ncm} | CEST ${it.cest || "-"} | CFOP ${it.cfop} | CSOSN ${it.csosn} | CST ${it.cst_icms}`);
    if (t.icms_st) {
      L.push(`   ICMS: substituido (ST) - baseST R$ ${f2(t.icms_st.baseST)} MVA ${(t.icms_st.mva * 100).toFixed(0)}% (Conv. ICMS 142/2018)`);
    } else {
      L.push(`   ICMS: base R$ ${f2(t.icms_base)} aliq ${(Number(t.icms_aliquota) * 100).toFixed(2)}% valor R$ ${f2(t.icms_valor)}`);
    }
    L.push(`   IPI ${(Number(t.ipi_aliquota) * 100).toFixed(2)}% R$ ${f2(t.ipi_valor)} | PIS R$ ${f2(t.pis_valor)} COFINS R$ ${f2(t.cofins_valor)}`);
    L.push(`   IBS 0,10% R$ ${f2(t.ibs_valor)} CBS 0,90% R$ ${f2(t.cbs_valor)} (teste 2026, sem efeito)`);
    L.push(`   Trib. aprox. IBPT (Lei 12.741/2012): R$ ${f2(t.vTotTrib_ibpt)}`);
  });
  L.push("--------------------------------------------------------------------------------");
  const tt = nota.totais;
  L.push(`vProdutos R$ ${f2(tt.vProdutos)} + vIPI R$ ${f2(tt.vIPI)} = vNF R$ ${f2(tt.vNF)}`);
  L.push(`vICMS R$ ${f2(tt.vICMS)} | vPIS R$ ${f2(tt.vPIS)} | vCOFINS R$ ${f2(tt.vCOFINS)}`);
  L.push(`vIBS R$ ${f2(tt.vIBS)} | vCBS R$ ${f2(tt.vCBS)} | vTotTrib IBPT R$ ${f2(tt.vTotTrib)}`);
  L.push("--------------------------------------------------------------------------------");
  const pags = (nota.pagamentos || []).map((p) => `${p.forma || p.metodo || "?"} R$ ${f2(p.valor)}`).join(" | ") || "(nenhum pagamento informado)";
  L.push(`Pagamentos: ${pags}`);
  L.push(`QR Code / consulta: http://localhost:${PORT}/v1/notas/${nota.id_nota}/danfe.pdf`);
  L.push(`XML: http://localhost:${PORT}/v1/notas/${nota.id_nota} (campo "xml")`);
  L.push("Base legal no campo tributos_referencia do JSON. Este espelho NAO tem valor fiscal.");
  L.push("================================================================================");
  return L.join("\n");
}

function gerarCupom48(nota) {
  const W = 48;
  const f2 = (n) => Number(n ?? 0).toFixed(2);
  const L = [];
  L.push("PDV SORVETES".padStart(30));
  L.push("Cupom - SEM VALOR FISCAL".padStart(36));
  L.push("-".repeat(W));
  L.push(`Venda ${nota.venda_id ?? "-"}  ${nota.autorizado_em}`);
  L.push(`Nota ${nota.id_nota}`);
  L.push("-".repeat(W));
  nota.itens.slice(0, 20).forEach((it) => {
    L.push(String(it.descricao).slice(0, W));
    L.push(`  ${it.quantidade}x R$ ${f2(it.valor_unitario)} = R$ ${f2(it.subtotal)}`);
  });
  if (nota.itens.length > 20) L.push(`... +${nota.itens.length - 20} item(ns)`);
  L.push("-".repeat(W));
  L.push(`TOTAL: R$ ${f2(nota.totais.vNF)}`.padStart(W));
  L.push("Pagamentos:");
  (nota.pagamentos || []).forEach((p) => {
    L.push(`  ${p.forma || p.metodo || "?"}: R$ ${f2(p.valor)}`);
  });
  L.push("-".repeat(W));
  L.push("NFC-e autorizada (MOCK):");
  L.push(`Chave ${nota.chave_acesso}`.slice(0, W));
  L.push(`Prot ${nota.protocolo}`.slice(0, W));
  L.push(`QR: localhost:${PORT}/v1/notas/${nota.id_nota}/danfe.pdf`.slice(0, W));
  L.push("");
  L.push("Obrigado pela preferencia!".padStart(36));
  return L.join("\n");
}

const EXEMPLO_REQUEST = {
  venda_id: 12,
  total: 15.0,
  uf: "MG",
  regime_tributario: "simples",
  com_st: true,
  cliente: { nome: "Consumidor Final" },
  itens: [
    { descricao: "Picole Chocolate", quantidade: 2, valor_unitario: 5.0, ncm: "21050010" },
    { descricao: "Cascão Baunilha", quantidade: 1, valor_unitario: 5.0, ncm: "21050090" }
  ],
  pagamentos: [{ forma: "pix", valor: 15.0 }]
};

app.get("/health", (req, res) => {
  res.json({ status: "ok", servico: "mock-sefaz-nfce" });
});

app.get("/", (req, res) => {
  res.type("html").send(`<h1>Mock SEFAZ NFC-e (PDV Sorvetes)</h1>
<p>Status: <a href="/health">/health</a></p>
<h2>Como ver a nota final</h2>
<ol>
<li>POST <code>/v1/notas</code> com JSON da venda &rarr; resposta inclui <code>espelho_txt</code> (nota final legivel), <code>cupom_48col</code>, <code>link</code> (PDF DANFE), <code>xml</code>, <code>chave_acesso</code>, <code>totais</code>.</li>
<li>GET <code>/v1/notas/:id</code> &rarr; JSON completo.</li>
<li>GET <code>/v1/notas/:id/txt</code> &rarr; espelho texto puro (a nota final impressa).</li>
<li>GET <code>/v1/notas/:id/cupom</code> &rarr; cupom 48 colunas (termica).</li>
<li>GET <code>/v1/notas/:id/danfe.pdf</code> &rarr; DANFE PDF mock.</li>
<li>GET <code>/v1/exemplo</code> &rarr; request de exemplo + resposta calculada sem salvar.</li>
</ol>
<h2>Exemplo de envio</h2>
<pre>curl -X POST http://localhost:${PORT}/v1/notas -H "Content-Type: application/json" -d '${JSON.stringify(EXEMPLO_REQUEST)}'</pre>
<p>Payload igual ao que o PDV monta em <code>src/services/fiscal_payload.py:11</code> (venda_id, total, itens[{descricao,quantidade,valor_unitario,ncm}], pagamentos).</p>`);
});

app.get("/v1/exemplo", (req, res) => {
  const { itens, totais } = calcularNota(EXEMPLO_REQUEST.itens, { uf: "MG", regime: "simples", comST: true });
  const fake = { id_nota: "nota_EXEMPLO", status: "autorizada", protocolo: "131000000000000", chave_acesso: "31" + "0".repeat(42), autorizado_em: new Date().toISOString(), uf: "MG", regime_tributario: "simples", cliente: EXEMPLO_REQUEST.cliente, venda_id: EXEMPLO_REQUEST.venda_id, pagamentos: EXEMPLO_REQUEST.pagamentos, itens, totais };
  res.json({ request_exemplo: EXEMPLO_REQUEST, resposta_espelho_txt: gerarEspelhoTXT(fake), resposta_cupom_48col: gerarCupom48(fake), resposta_json_campos: Object.keys(fake).concat(["link", "xml", "espelho_txt", "cupom_48col"]) });
});

app.post("/v1/notas", (req, res) => {
  const body = req.body || {};
  const rawItens = extrairItens(body);

  const itensEntrada = rawItens.length
    ? rawItens
    : [{ descricao: "Sorvete teste", quantidade: 1, valor_unitario: Number(body.total ?? body.valor ?? 10) }];

  const uf = body.uf || body.cliente?.uf || "MG";
  const regime = body.regime_tributario || body.regime || "simples";
  const comST = body.com_st !== undefined ? Boolean(body.com_st) : true;

  const { itens, totais } = calcularNota(itensEntrada, { uf, regime, comST });

  const id_nota = gerarIdNota();
  const chave_acesso = gerarChaveAcesso();
  const protocolo = gerarProtocolo();
  const autorizado_em = new Date().toISOString();

  const nota = {
    id_nota,
    status: "autorizada",
    protocolo,
    chave_acesso,
    pdf_danfe: `http://localhost:${PORT}/v1/notas/${id_nota}/danfe.pdf`,
    link: `http://localhost:${PORT}/v1/notas/${id_nota}/danfe.pdf`,
    xml: `<nfe><infNFe Id="NFe${chave_acesso}"><ide><nNF>${id_nota}</nNF></ide></infNFe></nfe>`,
    autorizado_em,
    uf,
    regime_tributario: regime,
    cliente: body.cliente ?? null,
    venda_id: body.venda_id ?? null,
    pagamentos: body.pagamentos ?? [],
    itens,
    totais,
    tributos_referencia: {
      icms_mg: "18% (Lei 6.763/1975, RICMS/MG Dec. 48.589/2023)",
      ipi_sorvete: "3,25% (TIPI Dec. 11.158/2022, NCM 2105.00.10/90)",
      mva_st: "70% regra geral MG (PMPF Port. SAIF 103/2026 prevalece)",
      ibpt_mg: "Federal 15,58% + Estadual 18% (IBPT, Lei 12.741/2012)",
      pis_cofins: "Cumulativo 0,65%/3% | Nao-cumulativo 1,65%/7,6% | Simples embutido no DAS",
      ibs_cbs_teste_2026: "IBS 0,1% + CBS 0,9% (Ato Conjunto RFB/CGIBS 04/2026, sem efeito arrecadatorio)",
      cfop_csosn: "5102+102 sem ST | 5405+500 com ST substituido (Convenio ICMS 142/2018, CEST 23.001.00)"
    }
  };

  notas.set(id_nota, nota);
  nota.espelho_txt = gerarEspelhoTXT(nota);
  nota.cupom_48col = gerarCupom48(nota);
  nota.links_doc = {
    json: `http://localhost:${PORT}/v1/notas/${id_nota}`,
    txt: `http://localhost:${PORT}/v1/notas/${id_nota}/txt`,
    cupom: `http://localhost:${PORT}/v1/notas/${id_nota}/cupom`,
    pdf: `http://localhost:${PORT}/v1/notas/${id_nota}/danfe.pdf`
  };

  res.status(201).json(nota);
});

app.get("/v1/notas/:id", (req, res) => {
  const nota = notas.get(req.params.id);
  if (!nota) {
    return res.status(404).json({ erro: "Nota nao encontrada", id: req.params.id });
  }
  res.status(200).json(nota);
});

app.get("/v1/notas/:id/txt", (req, res) => {
  const nota = notas.get(req.params.id);
  if (!nota) return res.status(404).json({ erro: "Nota nao encontrada" });
  res.type("text/plain; charset=utf-8").send(nota.espelho_txt || gerarEspelhoTXT(nota));
});

app.get("/v1/notas/:id/cupom", (req, res) => {
  const nota = notas.get(req.params.id);
  if (!nota) return res.status(404).json({ erro: "Nota nao encontrada" });
  res.type("text/plain; charset=utf-8").send(nota.cupom_48col || gerarCupom48(nota));
});

function pdfTxt(s) {
  return String(s ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/R\$/g, "R$")
    .replace(/[^\x20-\x7E]/g, "?");
}

function pdfEscape(s) {
  return pdfTxt(s).replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
}

function gerarDanfePDF(nota) {
  const f2 = (n) => Number(n ?? 0).toFixed(2);
  const L = [];
  L.push("DANFE NFC-e MODELO 65 - MOCK SEFAZ (SEM VALOR FISCAL)");
  L.push("Emitente: Sorvetes Franquia MG - CNPJ 00.000.000/0001-91 - UF MG");
  const cli = nota.cliente?.nome || nota.cliente?.name || "Consumidor Final";
  L.push(`Destinatario: ${cli}  UF: ${nota.uf}  Regime: ${nota.regime_tributario}`);
  L.push(`ID: ${nota.id_nota}  Venda: ${nota.venda_id ?? "-"}  Emissao: ${nota.autorizado_em}`);
  L.push(`Chave: ${nota.chave_acesso}`);
  L.push(`Protocolo: ${nota.protocolo}  Status: ${nota.status}`);
  L.push("------------------------------------------------------------");
  L.push(`ITENS (${nota.itens.length}) - valores em R$`);
  nota.itens.slice(0, 8).forEach((it, i) => {
    const t = it.tributos || {};
    const st = t.icms_st ? ` ST MVA ${(t.icms_st.mva * 100).toFixed(0)}% baseST ${f2(t.icms_st.baseST)}` : "";
    L.push(`${i + 1}. ${it.descricao} ${it.quantidade}x ${f2(it.valor_unitario)} = ${f2(it.subtotal)}`);
    L.push(`   NCM ${it.ncm} CEST ${it.cest || "-"} CFOP ${it.cfop} CSOSN ${it.csosn} CST ${it.cst_icms}`);
    L.push(`   ICMS base ${f2(t.icms_base)} aliq ${(Number(t.icms_aliquota) * 100).toFixed(2)}% valor ${f2(t.icms_valor)}${st}`);
    L.push(`   IPI ${(Number(t.ipi_aliquota) * 100).toFixed(2)}% ${f2(t.ipi_valor)} | PIS ${f2(t.pis_valor)} COFINS ${f2(t.cofins_valor)}`);
    L.push(`   IBS 0,10% ${f2(t.ibs_valor)} CBS 0,90% ${f2(t.cbs_valor)} | Trib IBPT ${f2(t.vTotTrib_ibpt)}`);
  });
  if (nota.itens.length > 8) L.push(`... +${nota.itens.length - 8} item(ns) - ver JSON em GET /v1/notas/${nota.id_nota}`);
  L.push("------------------------------------------------------------");
  const tt = nota.totais;
  L.push(`TOTAIS: vProdutos ${f2(tt.vProdutos)}  vIPI ${f2(tt.vIPI)}  vICMS ${f2(tt.vICMS)}`);
  L.push(`vPIS ${f2(tt.vPIS)}  vCOFINS ${f2(tt.vCOFINS)}  vIBS ${f2(tt.vIBS)}  vCBS ${f2(tt.vCBS)}`);
  L.push(`vTotTrib IBPT ${f2(tt.vTotTrib)}  vNF ${f2(tt.vNF)}`);
  const pags = (nota.pagamentos || []).map((p) => `${p.forma || p.metodo || "?"} ${f2(p.valor)}`).join(" | ") || "-";
  L.push(`Pagamentos: ${pags}`);
  L.push("Trib aprox Lei 12.741/2012 (IBPT). IBS/CBS teste 2026 sem efeito fiscal.");
  L.push("ICMS MG 18% | IPI 3,25% TIPI | CEST 23.001.00 Conv.142/2018");

  // Forma canonica: (linha) Tj + T* em linhas separadas (compat. maxima Chrome/Edge).
  const linhas = L.slice(0, 48).map((l) => `(${pdfEscape(l)}) Tj\nT*`);
  // remove o ultimo T* para nao descer alem da pagina
  const bloco = linhas.join("\n").replace(/\nT\*$/, "");
  const content = `BT /F1 10 Tf 50 780 Td 12 TL\n${bloco}\nET`;

  const objs = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>",
    `<< /Length ${Buffer.byteLength(content)} >>\nstream\n${content}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
  ];

  let pdf = "%PDF-1.4\n";
  const offsets = [];
  objs.forEach((body, i) => {
    offsets.push(Buffer.byteLength(pdf));
    pdf += `${i + 1} 0 obj\n${body}\nendobj\n`;
  });
  const xrefPos = Buffer.byteLength(pdf);
  pdf += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`;
  offsets.forEach((o) => {
    pdf += `${String(o).padStart(10, "0")} 00000 n \n`;
  });
  pdf += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xrefPos}\n%%EOF`;
  return Buffer.from(pdf);
}

app.get("/v1/notas/:id/danfe.pdf", (req, res) => {
  const nota = notas.get(req.params.id);
  if (!nota) {
    // Nunca devolve JSON num endpoint .pdf (navegador mostra pagina em branco).
    // Devolve um PDF valido com a mensagem de erro.
    const erro = {
      id_nota: req.params.id, venda_id: "-", autorizado_em: new Date().toISOString(),
      chave_acesso: "-", protocolo: "-", status: "nao encontrada",
      cliente: null, uf: "MG", regime_tributario: "-",
      itens: [{ descricao: `Nota ${req.params.id} nao encontrada neste servidor (Map em memoria; restart apaga). Crie de novo via POST /v1/notas.`, quantidade: 1, valor_unitario: 0, subtotal: 0, ncm: "-", cest: "-", cfop: "-", csosn: "-", cst_icms: "-", tributos: {} }],
      totais: { vProdutos: 0, vIPI: 0, vICMS: 0, vPIS: 0, vCOFINS: 0, vIBS: 0, vCBS: 0, vTotTrib: 0, vNF: 0 },
      pagamentos: []
    };
    const buf = gerarDanfePDF(erro);
    res.status(404).type("application/pdf");
    res.set("Content-Length", String(buf.length));
    res.set("Cache-Control", "no-store");
    return res.send(buf);
  }
  const buf = gerarDanfePDF(nota);
  res.type("application/pdf");
  res.set("Content-Length", String(buf.length));
  res.set("Cache-Control", "no-store");
  res.set("Content-Disposition", `inline; filename="danfe-${nota.id_nota}.pdf"`);
  res.send(buf);
});

app.listen(PORT, () => {
  console.log(`Mock SEFAZ rodando em http://localhost:${PORT}`);
});
