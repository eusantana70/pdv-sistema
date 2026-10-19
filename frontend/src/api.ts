// Cliente HTTP do PDV Lumina — fala com FastAPI em /api (proxy Vite -> :8000).
// Sem dependências externas: usa fetch nativo + fallback offline.

export type Lote = { id: number; validade: string; quantidade: number };

export type BackendProduct = {
  id: number;
  name: string;
  sku: string;
  codigo4: string;
  ean: string;
  category: string;
  price: number;
  stock: number;
  color: string;
  unidade: string;
  perfil_id: number | null;
  validade: string;
  lotes: Lote[];
};

export type FiscalProviderId = "mock" | "nuvem_fiscal" | "focus_nfe" | "sefaz_direta" | "custom";

export type BackendConfig = {
  fiscal_provider: FiscalProviderId | string;
  ambiente: string;
  modelo_doc: string;
  serie: string;
  proximo_numero: number;
  razao_social: string;
  nome_fantasia: string;
  cnpj: string;
  ie: string;
  email: string;
  telefone: string;
  endereco: string;
  cidade_uf: string;
  cep: string;
  impressora_nome: string;
  impressora_largura: string;
  impressora_vias: number;
  auto_print: number | boolean;
  exibir_logo: number | boolean;
  corte_auto: number | boolean;
  mock_url: string;
  nuvem_token: string;
  nuvem_url: string;
  focus_token: string;
  focus_url: string;
  custom_token: string;
  custom_url: string;
  sefaz_cert_path: string;
  sefaz_cert_senha: string;
  desconto_tipo: string;
  desconto_valor: number;
  // nota não fiscal (comprovante impresso)
  recibo_titulo: string;
  recibo_subtitulo: string;
  recibo_rodape: string;
  recibo_largura: string;
  recibo_mostrar_cnpj: number | boolean;
  recibo_mostrar_itens: number | boolean;
  recibo_mostrar_pagamentos: number | boolean;
  recibo_mostrar_troco: number | boolean;
  recibo_mostrar_atendente: number | boolean;
  recibo_mostrar_qrcode: number | boolean;
  imprimir_cupom_fiscal: number | boolean;
  imprimir_cupom_nao_fiscal: number | boolean;
  recibo_qrcode_link: string;
  recibo_tributos_federal: number;
  recibo_tributos_estadual: number;
  recibo_aviso_trocas: string;
  recibo_mostrar_tributos: number | boolean;
  recibo_mostrar_aviso_trocas: number | boolean;
  providers_disponiveis?: { id: string; label: string }[];
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const token = (() => { try { return localStorage.getItem("lumina-token") || ""; } catch { return ""; } })();
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      ...init,
    });
  } catch {
    // API fora do ar (proxy/Vite sem backend): erro de rede, nao HTTP 500
    throw apiErro(`API offline (${path}) — o servidor não respondeu.`, 0, path);
  }
  if (!res.ok) {
    // sessao expirada/token invalido: limpa e volta para o login
    if (res.status === 401) {
      try { localStorage.removeItem("lumina-token"); } catch { /* noop */ }
      window.dispatchEvent(new Event("lumina:sessao-expirada"));
    }
    const corpo = await res.text().catch(() => "");
    let msg = `HTTP ${res.status}`;
    try {
      const j = JSON.parse(corpo) as { detail?: string | { msg?: string }[] };
      // FastAPI 422: detail vem como lista de erros de campo
      if (Array.isArray(j.detail)) {
        msg = j.detail.map((d) => d.msg || "").filter(Boolean).join(" · ") || msg;
      } else if (j.detail) {
        msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      }
    } catch {
      if (res.status >= 502 || !corpo.trim()) msg = "API offline";
    }
    throw apiErro(msg, res.status, path);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export type ErroApi = Error & { status?: number; path?: string };

const apiErro = (msg: string, status: number, path: string): ErroApi => {
  const e = new Error(msg) as ErroApi;
  e.status = status;
  e.path = path;
  return e;
};

export const erroAmigavel = (e: unknown): string => {
  const err = e as ErroApi;
  const status = err?.status ?? 0;
  const path = err?.path ?? "";
  const base = err?.message || "erro desconhecido";
  if (status === 0 || status >= 502 || /offline/i.test(base)) {
    return "API offline — o servidor do PDV parou. Rode RODAR_PDV.bat novamente.";
  }
  return path ? `${base} (${path})` : base;
};

export type StatusApi = {
  online: boolean;
  detalhe: string;
  verificadoEm: string;
};

/** Checagem direta da API (sem cache e com timeout) para o banner de status. */
export async function verificarApi(): Promise<StatusApi> {
  const verificadoEm = new Date().toLocaleTimeString("pt-BR", {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
  try {
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), 5000);
    const res = await fetch(`/api/health?t=${Date.now()}`, {
      cache: "no-store", signal: ctrl.signal, headers: { Accept: "application/json" },
    });
    window.clearTimeout(timer);
    if (res.ok) {
      const j = (await res.json().catch(() => ({}))) as { status?: string };
      if (j.status === "ok") {
        return { online: true, detalhe: "API respondendo normalmente.", verificadoEm };
      }
      return { online: false, detalhe: `API respondeu com status "${j.status ?? "?"}".`, verificadoEm };
    }
    return { online: false, detalhe: `GET /api/health → HTTP ${res.status}.`, verificadoEm };
  } catch (e) {
    const err = e as Error;
    const motivo = err?.name === "AbortError" ? "tempo esgotado (5s sem resposta)" : (err?.message || "erro de rede");
    return { online: false, detalhe: `Sem resposta do servidor: ${motivo}.`, verificadoEm };
  }
}

export type RelatorioDados = {
  inicio: string;
  fim: string;
  filtros: { formas: string[]; categorias: string[]; produtos: string[] };
  resumo: { total: number; vendas: number; itens: number; ticket_medio: number; desconto_medio: number; formas: number; produtos: number };
  serie: { rotulo: string; vendas: number; total: number; dinheiro: number; credito: number; debito: number; pix: number }[];
  por_forma: { forma: string; rotulo: string; vendas: number; total: number }[];
  por_produto: { nome: string; categoria: string; quantidade: number; total: number }[];
  por_categoria: { categoria: string; quantidade: number; total: number }[];
};

export type Usuario = {
  id: number;
  nome: string;
  login: string;
  perfil: "admin" | "operador";
  perfil_rotulo?: string;
  permissoes: string[];
  ativo?: number;
  criado_em?: string;
};

export type UsuarioSessao = Usuario & { perfil_rotulo: string };

export const api = {
  health: () => req<{ status: string }>("/health"),
  meta: () => req<{ categorias: string[] }>("/meta"),

  // ---- primeiro acesso (rota pública, some depois do primeiro ADM) ----
  setupStatus: () => req<{ configurado: boolean; setup_concluido_em: string; versao: string }>("/setup/status"),
  primeiroAcesso: (b: { nome: string; login: string; senha: string; confirmar_senha: string }) =>
    req<{ ok: boolean; token: string; usuario: UsuarioSessao }>("/setup/primeiro-acesso", {
      method: "POST",
      body: JSON.stringify(b),
    }),
  encerrarSistema: () => req<{ ok: boolean }>("/sistema/encerrar", { method: "POST", body: "{}" }),

  login: (login: string, senha: string) =>
    req<{ token: string; usuario: UsuarioSessao }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ login, senha }),
    }),
  me: () => req<UsuarioSessao>("/auth/me"),
  logout: () => req<{ ok: boolean }>("/auth/logout", { method: "POST", body: "{}" }),
  perfisAcesso: () =>
    req<{ perfis: { id: string; rotulo: string; descricao: string; permissoes: string[] }[]; permissoes: { chave: string; rotulo: string }[] }>("/auth/perfis"),
  listarUsuarios: () => req<Usuario[]>("/usuarios"),
  criarUsuario: (u: { nome: string; login: string; senha: string; perfil: string }) =>
    req<Usuario>("/usuarios", { method: "POST", body: JSON.stringify(u) }),
  atualizarUsuario: (id: number, u: Record<string, unknown>) =>
    req<Usuario>(`/usuarios/${id}`, { method: "PUT", body: JSON.stringify(u) }),
  excluirUsuario: (id: number) => req<void>(`/usuarios/${id}`, { method: "DELETE" }),

  listarProdutos: (busca = "") =>
    req<BackendProduct[]>(`/produtos?busca=${encodeURIComponent(busca)}`),
  buscarPdv: (termo: string, limite = 7) =>
    req<BackendProduct[]>(`/produtos/busca?termo=${encodeURIComponent(termo)}&limite=${limite}`),
  criarProduto: (p: { nome: string; preco_venda: number; quantidade_estoque: number; ean: string; categoria: string; unidade_medida?: string; cor?: string; validade?: string }) =>
    req<BackendProduct>("/produtos", { method: "POST", body: JSON.stringify(p) }),
  atualizarProduto: (id: number, p: Record<string, unknown>) =>
    req<BackendProduct>(`/produtos/${id}`, { method: "PUT", body: JSON.stringify(p) }),
  excluirProduto: (id: number) =>
    req<void>(`/produtos/${id}`, { method: "DELETE" }),

  caixaAberto: () => req<{ aberto: boolean; movimento: { id: number; valor_inicial: number } | null; saldo_previsto?: number; ultimo_fechado: { id: number; valor_final: number; data_fechamento: string } | null }>("/caixa/aberto"),
  operacoesCaixa: (dia = "") =>
    req<{ id: number; id_movimento: number; tipo: string; valor: number; data_hora: string; observacao: string }[]>(`/caixa-operacoes?dia=${encodeURIComponent(dia)}`),
  abrirCaixa: (valor_inicial: number) =>
    req<{ id: number }>(`/caixa/abrir`, { method: "POST", body: JSON.stringify({ valor_inicial }) }),
  fecharCaixa: (movimento_id: number, valor_final: number) =>
    req<{ ok: boolean }>(`/caixa/fechar`, { method: "POST", body: JSON.stringify({ movimento_id, valor_final }) }),
  operacao: (id_movimento: number, tipo: "sangria" | "suprimento", valor: number, observacao = "") =>
    req<{ id: number; saldo_previsto: number }>(`/caixa/operacao`, {
      method: "POST",
      body: JSON.stringify({ id_movimento, tipo, valor, observacao }),
    }),

  criarVenda: (body: {
    id_movimento: number | null;
    itens: { id_produto: number; quantidade: number; valor_unitario?: number }[];
    pagamentos: { metodo: string; valor: number; parcelas?: number }[];
    desconto_percentual: number;
  }) => req<{ id: number; total: number; nfe_status: string }>(`/vendas`, { method: "POST", body: JSON.stringify(body) }),

  relatorio: (periodo: "diario" | "semanal" | "mensal") =>
    req<{ periodo: string; total_geral: number; vendas: number }>(`/relatorios/${periodo}`),
  relatorioFull: (periodo: "diario" | "semanal" | "mensal") =>
    req<{ periodo: string; total_geral: number; vendas: number; dias: { dia: string; _geral: number; _vendas: number; dinheiro: number; credito: number; debito: number; pix: number }[] }>(`/relatorios/${periodo}`),
  importarProdutos: (body: FormData) =>
    req<{ total_enviado: number; importados: number; produtos: any[]; erros_validacao: any[]; erros_importacao: any[]; total_erros: number }>(`/produtos/importar`, {
      method: "POST",
      body: body as any,
    }),
  dadosRelatorio: (p: { periodo: string; data?: string; inicio?: string; fim?: string; formas?: string[]; categorias?: string[]; produtos?: string[]; agrupar?: string }) => {
    const q = new URLSearchParams();
    q.set("periodo", p.periodo);
    if (p.data) q.set("data", p.data);
    if (p.inicio) q.set("inicio", p.inicio);
    if (p.fim) q.set("fim", p.fim);
    if (p.formas?.length) q.set("formas", p.formas.join(","));
    if (p.categorias?.length) q.set("categorias", p.categorias.join(","));
    if (p.produtos?.length) q.set("produtos", p.produtos.join(","));
    if (p.agrupar) q.set("agrupar", p.agrupar);
    return req<RelatorioDados>(`/relatorios/dados?${q.toString()}`);
  },
  gerarRelatorioPdf: (corpo: Record<string, unknown>) =>
    req<{ ok: boolean; arquivo: string; url: string; bytes: number; resumo: RelatorioDados["resumo"] }>(
      `/relatorios/gerar-pdf`, { method: "POST", body: JSON.stringify(corpo) }),
  cancelarVenda: (id: number) =>
    req<{ ok: boolean }>(`/vendas/${id}/cancelar`, { method: "POST" }),

  fiscalStatus: (venda_id: number) =>
    req<{ nfe_status: string; link: string; xml: string }>(`/fiscal/nota/${venda_id}`),
  testeMockArquivo: () =>
    req<{ ok: boolean; id_nota: string; chave_acesso: string; protocolo: string; arquivos: string[]; pdf: string; espelho_preview: string; cupom_preview: string }>(`/fiscal/teste-mock`, { method: "POST", body: "{}" }),
  testeImpressaoArquivo: () =>
    req<{ ok: boolean; arquivo: string; preview: string }>(`/fiscal/teste-impressao`, { method: "POST", body: "{}" }),
  reciboPreview: () => req<{ texto: string; largura: number }>(`/fiscal/recibo-preview`),
  imprimirDocumento: (vendaId: number, tipo: "fiscal" | "nao_fiscal") =>
    req<{ ok: boolean; modo: "impresso" | "pdf"; tipo: string; arquivo?: string; pasta?: string; url?: string; mensagem: string }>(
      `/fiscal/imprimir/${vendaId}?tipo=${tipo}`, { method: "POST" }),
  qrcodeUrl: (link: string) =>
    req<{ data_uri: string; link: string; biblioteca: string }>(
      `/fiscal/qrcode?link=${encodeURIComponent(link || "")}`),
  arquivoUrl: (pasta: "notas_teste" | "cupons", nome: string) =>
    `/api/fiscal/arquivo/${pasta}/${encodeURIComponent(nome)}`,
  listarVendas: (limite = 20, dia = "") =>
    req<{ id: number; total: number; data_hora: string; status: string; nfe_status: string }[]>(`/vendas?limite=${limite}${dia ? `&dia=${encodeURIComponent(dia)}` : ""}`),
  previewLimpeza: (inicio = "", fim = "") =>
    req<{ vendas: number; total: number; inicio: string; fim: string }>(`/vendas-limpar/preview?inicio=${encodeURIComponent(inicio)}&fim=${encodeURIComponent(fim)}`),
  limparVendas: (inicio = "", fim = "") =>
    req<{ removidas: number; total: number }>(`/vendas-limpar`, { method: "DELETE", body: JSON.stringify({ inicio, fim }) }),
  totaisDia: (dia: string) =>
    req<{ dinheiro: number; credito: number; debito: number; pix: number; _geral: number; _vendas: number }>(`/vendas/totais?dia=${encodeURIComponent(dia)}`),
  substituirLotes: (produtoId: number, lotes: { validade: string; quantidade: number }[]) =>
    req<Lote[]>(`/produtos/${produtoId}/lotes`, { method: "PUT", body: JSON.stringify({ lotes }) }),

  getConfig: () => req<BackendConfig>("/config"),
  saveConfig: (cfg: Partial<BackendConfig>) =>
    req<BackendConfig>("/config", { method: "PUT", body: JSON.stringify(cfg) }),
  testarFiscal: (cfg: Partial<BackendConfig> & { fiscal_provider?: string }) =>
    req<{ ok: boolean; provider: string; mensagem: string }>(`/config/fiscal/testar`, {
      method: "POST",
      body: JSON.stringify(cfg),
    }),
};

export const PROVIDER_INFO: { id: FiscalProviderId; label: string; desc: string }[] = [
  { id: "mock", label: "Mock Local", desc: "mock-sefaz em localhost:3000 — ideal para testar sem SEFAZ." },
  { id: "nuvem_fiscal", label: "Nuvem Fiscal", desc: "api.nuvemfiscal.com.br com Bearer token." },
  { id: "focus_nfe", label: "Focus NFe", desc: "api.focusnfe.com.br com token Basic." },
  { id: "sefaz_direta", label: "SEFAZ Direta", desc: "Certificado A1 .pfx — transmissão oficial." },
  { id: "custom", label: "Custom", desc: "URL própria do cliente com Bearer opcional." },
];
