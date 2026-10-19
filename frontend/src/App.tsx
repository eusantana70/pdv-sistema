import { useEffect, useMemo, useRef, useState } from "react";
import { api, erroAmigavel, verificarApi, PROVIDER_INFO, type StatusApi, type BackendConfig, type RelatorioDados, type UsuarioSessao } from "./api";

type Page = "sales" | "inventory" | "history" | "reports" | "users" | "settings";
type Category = "Todos" | "Bebidas" | "Alimentos" | "Padaria" | "Higiene";
type IconName =
  | "bag" | "box" | "settings" | "search" | "plus" | "minus" | "trash"
  | "pause" | "card" | "receipt" | "edit" | "close" | "chevron" | "check"
  | "alert" | "printer" | "store" | "user" | "tag" | "chart" | "logout" | "lock" | "power";

type Lote = { id: number; validade: string; quantidade: number };

type Product = {
  id: number;
  name: string;
  sku: string;
  category: Exclude<Category, "Todos">;
  price: number;
  stock: number;
  color: string;
  validade: string;
  lotes: Lote[];
};

type CartItem = Product & { quantity: number; lineId: string };

type VendaHistorico = {
  id: number;
  total: number;
  data_hora: string;
  status: string;
  nfe_status: string;
};

type OperacaoCaixa = {
  id: number;
  id_movimento: number;
  tipo: string;
  valor: number;
  data_hora: string;
  observacao: string;
};
type SystemSettings = {
  company: string;
  tradeName: string;
  cnpj: string;
  stateRegistration: string;
  email: string;
  phone: string;
  address: string;
  city: string;
  zip: string;
  emission: string;
  environment: string;
  series: string;
  printer: string;
  paperSize: string;
  autoPrint: boolean;
  printLogo: boolean;
  cutPaper: boolean;
  copies: string;
};

type FiscalState = {
  provider: string;
  ambiente: string;
  modelo: string;
  serie: string;
  proximo: string;
  mock_url: string;
  nuvem_token: string;
  nuvem_url: string;
  focus_token: string;
  focus_url: string;
  custom_token: string;
  custom_url: string;
  sefaz_cert_path: string;
};

// ---- Nota NÃO fiscal (comprovante impresso) ----
type ReciboState = {
  titulo: string;
  subtitulo: string;
  rodape: string;
  largura: "32" | "48";
  mostrarCnpj: boolean;
  mostrarItens: boolean;
  mostrarPagamentos: boolean;
  mostrarTroco: boolean;
  mostrarAtendente: boolean;
  mostrarQrcode: boolean;
  qrcodeLink: string;
  tributosFederal: number;
  tributosEstadual: number;
  mostrarTributos: boolean;
  avisoTrocas: string;
  mostrarAvisoTrocas: boolean;
};

type CaixaState = {
  aberto: boolean;
  movimentoId: number | null;
  saldo: number;
  valorInicial: number;
  online: boolean;
  ultimoFechamento: { valor: number; data: string } | null;
};

const cxFromApi = (cx: { aberto: boolean; movimento: { id: number; valor_inicial: number } | null; saldo_previsto?: number; ultimo_fechado: { id: number; valor_final: number; data_fechamento: string } | null }): CaixaState => ({
  aberto: cx.aberto,
  movimentoId: cx.movimento?.id ?? null,
  saldo: cx.aberto ? (cx.saldo_previsto ?? cx.movimento?.valor_inicial ?? 0) : 0,
  valorInicial: cx.movimento?.valor_inicial ?? 0,
  online: true,
  ultimoFechamento: cx.ultimo_fechado
    ? { valor: Number(cx.ultimo_fechado.valor_final) || 0, data: cx.ultimo_fechado.data_fechamento || "" }
    : null,
});

const pode = (usuario: UsuarioSessao | null, chave: string) => {
  if (!usuario) return false;
  const p = usuario.permissoes || [];
  return p.includes("*") || p.includes(chave);
};

// catálogo de demonstração removido: a tela nunca exibe preço/estoque fictício
// como se fosse real. Os produtos vêm do banco (POST/GET /api/produtos).

// padrão brasileiro: R$ 1.234,56
const BRL = new Intl.NumberFormat("pt-BR", {
  style: "currency", currency: "BRL", minimumFractionDigits: 2, maximumFractionDigits: 2,
});

const money = (value: number) => BRL.format(Number.isFinite(value) ? value : 0);

// percentual no padrão brasileiro: 1.234,5%
const fmtPercent = (value: number) =>
  new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(
    Number.isFinite(value) ? value : 0,
  ) + "%";

// "1.234,56" (sem R$) para exibir dentro de campos
const fmtMoeda = (value: number | string | undefined | null) => {
  const n = parseMoeda(value);
  return new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(
    Number.isFinite(n) ? n : 0,
  );
};

// placeholders: sempre marcados como exemplo, nunca como valor real do campo
const EX_MOEDA = "Ex.: 0,00";
const EX_NUM = "Ex.: 0";
const EX_PCT = "Ex.: 5";

// campo de moeda no padrão do Real: prefixo R$ fixo + máscara 1.234,56
const CampoMoeda = ({ value, onChange, placeholder, disabled, inputMode = "decimal" }: {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  disabled?: boolean;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
}) => (
  <div className="money-input">
    <input value={value} onChange={onChange} placeholder={placeholder} disabled={disabled} inputMode={inputMode} />
    <b>R$</b>
  </div>
);
const exMoeda = (valor: number | string | undefined | null) => `Ex.: ${fmtMoeda(valor)}`;

// aceita "1.234,56", "1234,56", "1234.56" ou "1234"
const parseMoeda = (value: number | string | undefined | null): number => {
  if (typeof value === "number") return value;
  const t = String(value ?? "").trim().replace(/[R$\s]/g, "");
  if (!t) return 0;
  if (t.includes(",")) return Number(t.replace(/\./g, "").replace(",", ".")) || 0;
  return Number(t) || 0;
};

// Máscara progressiva de centavos: digita 25615 -> "256,15"
// (o estado guarda o texto já formatado, então os zeros à esquerda que a própria
//  máscara gera precisam ser descartados antes de remascarar — senão vira "00025615")
const maskMoeda = (value: string | number): string => {
  const d = String(value ?? "").replace(/\D/g, "").replace(/^0+(?=\d)/, "");
  // só zeros = campo vazio (permite limpar com backspace)
  if (!d || d === "0") return "";
  const cents = d.padStart(2, "0");
  const int = cents.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, ".") || "0";
  const frac = cents.slice(-2);
  return `${int},${frac}`;
};

// para inputs não controlados (ex.: formulário de produto)
// obs.: o cursor vai SEMPRE para o fim depois da máscara — usar a posição anterior
// fazia o cursor "pular" e a próxima tecla sobrescrever o zero inicial (ex.: "c,01").
const aplicarMascara = (e: React.ChangeEvent<HTMLInputElement>) => {
  const el = e.target;
  el.value = maskMoeda(el.value);
  const fim = el.value.length;
  try { el.setSelectionRange(fim, fim); } catch { /* noop */ }
};

const fmtData = (iso: string) => {
  if (!iso) return "—";
  const [d, m, a] = iso.slice(0, 10).split("-");
  return d && m && a ? `${d}/${m}/${a}` : iso;
};

const fmtHora = (iso: string) => {
  if (!iso) return "";
  return iso.includes("T") ? iso.slice(11, 16) : "";
};

const fmtDataHora = (iso: string) => {
  if (!iso) return "—";
  const d = fmtData(iso);
  const h = fmtHora(iso);
  return h ? `${d} ${h}` : d;
};

const asCategory = (c: string): Product["category"] =>
  (["Bebidas", "Alimentos", "Padaria", "Higiene"] as const).includes(c as Product["category"])
    ? (c as Product["category"]) : "Alimentos";

function backendToFront(bp: { id: number; name: string; sku: string; category: string; price: number; stock: number; color: string; validade?: string; lotes?: { id: number; validade: string; quantidade: number }[] }): Product {
  return {
    id: bp.id, name: bp.name, sku: bp.sku,
    category: asCategory(bp.category), price: Number(bp.price),
    stock: Number(bp.stock), color: bp.color || "green",
    validade: bp.validade || "",
    lotes: (bp.lotes || []).map((l) => ({ id: l.id, validade: l.validade, quantidade: Number(l.quantidade) })),
  };
}

const hojeISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const diasPara = (validade: string): number | null => {
  if (!validade) return null;
  const [y, m, d] = validade.split("-").map(Number);
  if (!y || !m || !d) return null;
  const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
  const v = new Date(y, m - 1, d);
  return Math.round((v.getTime() - hoje.getTime()) / 86400000);
};

const urgClass = (dias: number | null) =>
  dias === null ? "" : dias < 0 ? "expired" : dias <= 5 ? "urgent" : dias <= 15 ? "warn" : "ok";

const urgText = (dias: number) =>
  dias < 0 ? `vencido há ${-dias}d` : dias === 0 ? "vence hoje" : `vence em ${dias}d`;

const paymentToBackend = (label: string): string => {
  if (label === "Crédito") return "credito";
  if (label === "Débito") return "debito";
  if (label === "PIX") return "pix";
  return "dinheiro";
};

function Icon({ name, size = 20, ...rest }: { name: IconName; size?: number } & React.SVGProps<SVGSVGElement>) {
  const paths: Record<IconName, React.ReactNode> = {
    bag: <><path d="M6 8h12l1 12H5L6 8Z" /><path d="M9 9V6a3 3 0 0 1 6 0v3" /></>,
    box: <><path d="m4 7 8-4 8 4-8 4-8-4Z" /><path d="M4 7v10l8 4 8-4V7M12 11v10" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21h-4v-.08A1.7 1.7 0 0 0 8.95 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.58 15 1.7 1.7 0 0 0 3 14H3v-4h.08A1.7 1.7 0 0 0 4.6 8.95a1.7 1.7 0 0 0-.34-1.88L4.2 7l2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.58 1.7 1.7 0 0 0 10 3h4v.08A1.7 1.7 0 0 0 15.05 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06L19.82 7l-.06.06A1.7 1.7 0 0 0 19.42 9 1.7 1.7 0 0 0 21 10v4a1.7 1.7 0 0 0-1.6 1Z" /></>,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    plus: <path d="M12 5v14M5 12h14" />,
    minus: <path d="M5 12h14" />,
    trash: <><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5" /></>,
    pause: <><rect x="6" y="4" width="4" height="16" rx="1" /><rect x="14" y="4" width="4" height="16" rx="1" /></>,
    card: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 10h18M7 15h4" /></>,
    receipt: <><path d="M6 3h12v19l-3-2-3 2-3-2-3 2V3Z" /><path d="M9 8h6M9 12h6M9 16h3" /></>,
    edit: <><path d="m14 5 5 5L9 20H4v-5L14 5Z" /><path d="m12 7 5 5" /></>,
    close: <path d="m6 6 12 12M18 6 6 18" />,
    chevron: <path d="m9 18 6-6-6-6" />,
    check: <path d="m5 12 4 4L19 6" />,
    alert: <><path d="M12 3 2.7 20h18.6L12 3Z" /><path d="M12 9v5M12 17h.01" /></>,
    printer: <><path d="M6 9V3h12v6M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" /><path d="M6 14h12v7H6z" /></>,
    store: <><path d="M3 9 5 3h14l2 6M5 13v8h14v-8M9 21v-6h6v6" /><path d="M3 9a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0" /></>,
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
    tag: <><path d="M20 13 13 20 4 11V4h7l9 9Z" /><circle cx="8.5" cy="8.5" r="1" /></>,
    chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></>,
    logout: <><path d="M10 17l5-5-5-5M15 12H3M15 4h5a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-5" /></>,
    lock: <><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /><circle cx="12" cy="15" r="1" /></>,
    power: <><path d="M12 3v9" /><path d="M6.6 6.6a8 8 0 1 0 10.8 0" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...rest}>{paths[name]}</svg>;
}

function Shortcut({ children }: { children: React.ReactNode }) {
  return <span className="shortcut">{children}</span>;
}

function AppButton({ children, variant = "secondary", className = "", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" | "ghost" }) {
  return <button className={`btn btn-${variant} ${className}`} {...props}>{children}</button>;
}

function ProductGlyph({ category, color }: Pick<Product, "category" | "color">) {
  return (
    <div className={`product-glyph tone-${color}`}>
      {category === "Bebidas" && <><div className="bottle-cap" /><div className="bottle" /></>}
      {category === "Alimentos" && <><div className="food-pack"><span /></div></>}
      {category === "Padaria" && <div className="bread"><i /><i /><i /></div>}
      {category === "Higiene" && <><div className="pump" /><div className="soap" /></>}
    </div>
  );
}

const defaultSettings: SystemSettings = {
  company: "Mercado Lumina Ltda.",
  tradeName: "Mercado Lumina",
  cnpj: "12.345.678/0001-90",
  stateRegistration: "123.456.789.112",
  email: "contato@mercadolumina.com.br",
  phone: "(11) 3456-7890",
  address: "Av. das Palmeiras, 420 — Centro",
  city: "São Paulo — SP",
  zip: "01234-000",
  emission: "NFC-e",
  environment: "Produção",
  series: "1",
  printer: "Impressora térmica 80mm",
  paperSize: "80mm",
  autoPrint: true,
  printLogo: true,
  cutPaper: true,
  copies: "1",
};

const defaultFiscal: FiscalState = {
  provider: "mock",
  ambiente: "Homologação",
  modelo: "NFC-e",
  serie: "1",
  proximo: "002848",
  mock_url: "http://localhost:3000",
  nuvem_token: "",
  nuvem_url: "https://api.nuvemfiscal.com.br/nfce",
  focus_token: "",
  focus_url: "https://api.focusnfe.com.br/v2/nfce",
  custom_token: "",
  custom_url: "",
  sefaz_cert_path: "",
};

function fiscalToBackend(f: FiscalState, s: SystemSettings, d?: { tipo: string; valor: number }): Partial<BackendConfig> {
  return {
    fiscal_provider: f.provider,
    ambiente: f.ambiente === "Produção" ? "producao" : "homologacao",
    modelo_doc: f.modelo || s.emission,
    serie: f.serie || s.series,
    mock_url: f.mock_url,
    nuvem_token: f.nuvem_token,
    nuvem_url: f.nuvem_url,
    focus_token: f.focus_token,
    focus_url: f.focus_url,
    custom_token: f.custom_token,
    custom_url: f.custom_url,
    sefaz_cert_path: f.sefaz_cert_path,
    razao_social: s.company,
    nome_fantasia: s.tradeName,
    cnpj: s.cnpj,
    ie: s.stateRegistration,
    email: s.email,
    telefone: s.phone,
    endereco: s.address,
    cidade_uf: s.city,
    cep: s.zip,
    impressora_nome: s.printer,
    impressora_largura: s.paperSize,
    impressora_vias: Number(s.copies) || 1,
    auto_print: s.autoPrint ? 1 : 0,
    exibir_logo: s.printLogo ? 1 : 0,
    corte_auto: s.cutPaper ? 1 : 0,
    desconto_tipo: d?.tipo || "nenhum",
    desconto_valor: Number(d?.valor) || 0,
  };
}

const defaultRecibo: ReciboState = {
  titulo: "",
  subtitulo: "Cupom de venda - sem valor fiscal",
  rodape: "Obrigado pela preferencia!",
  largura: "48",
  mostrarCnpj: true,
  mostrarItens: true,
  mostrarPagamentos: true,
  mostrarTroco: true,
  mostrarAtendente: false,
  mostrarQrcode: true,
  qrcodeLink: "",
  tributosFederal: 0,
  tributosEstadual: 0,
  mostrarTributos: true,
  avisoTrocas: "Eventuais trocas somente mediante notinha",
  mostrarAvisoTrocas: true,
};

const reciboToBackend = (r: ReciboState): Partial<BackendConfig> => ({
  recibo_titulo: r.titulo,
  recibo_subtitulo: r.subtitulo,
  recibo_rodape: r.rodape,
  recibo_largura: r.largura,
  recibo_mostrar_cnpj: r.mostrarCnpj ? 1 : 0,
  recibo_mostrar_itens: r.mostrarItens ? 1 : 0,
  recibo_mostrar_pagamentos: r.mostrarPagamentos ? 1 : 0,
  recibo_mostrar_troco: r.mostrarTroco ? 1 : 0,
  recibo_mostrar_atendente: r.mostrarAtendente ? 1 : 0,
  recibo_mostrar_qrcode: r.mostrarQrcode ? 1 : 0,
  recibo_qrcode_link: r.qrcodeLink,
  recibo_tributos_federal: Number(r.tributosFederal) || 0,
  recibo_tributos_estadual: Number(r.tributosEstadual) || 0,
  recibo_mostrar_tributos: r.mostrarTributos ? 1 : 0,
  recibo_aviso_trocas: r.avisoTrocas,
  recibo_mostrar_aviso_trocas: r.mostrarAvisoTrocas ? 1 : 0,
});

const FORCA = [
  { rotulo: "muito fraca", cor: "#c0483f", min: 0 },
  { rotulo: "fraca", cor: "#d3813a", min: 1 },
  { rotulo: "boa", cor: "#2c7a4b", min: 2 },
  { rotulo: "forte", cor: "#1c5e38", min: 3 },
];

/** 0..4 — letras + números + símbolo + tamanho. */
function forcaDaSenha(s: string): number {
  if (!s) return 0;
  let n = 0;
  if (s.length >= 6) n++;
  if (s.length >= 10) n++;
  if (/[a-z]/.test(s) && /[A-Z]/.test(s)) n++;
  if (/\d/.test(s) && /[^\w\s]/.test(s)) n++;
  return Math.min(n, 4);
}

/**
 * Assistente de primeiro acesso. Aparece só enquanto o sistema não tem
 * nenhum usuário — é por aqui que a instalação nova cria o administrador.
 */
function SetupWizardScreen({ onConcluido }: { onConcluido: (u: UsuarioSessao) => void }) {
  const [passo, setPasso] = useState(0);
  const [nome, setNome] = useState("");
  const [login, setLogin] = useState("admin");
  const [senha, setSenha] = useState("");
  const [confirma, setConfirma] = useState("");
  const [vendo, setVendo] = useState(false);
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  const forca = forcaDaSenha(senha);
  const nivel = FORCA[forca];

  const problemas: string[] = [];
  if (nome.trim().length < 2) problemas.push("Informe o nome do administrador.");
  if (login.trim().length < 3) problemas.push("O login precisa de pelo menos 3 caracteres.");
  if (/\s/.test(login.trim())) problemas.push("O login não pode ter espaço.");
  if (senha.length < 6) problemas.push("A senha precisa de pelo menos 6 caracteres.");
  if (senha !== confirma) problemas.push("As senhas não são iguais.");

  const avancar = () => {
    setErro("");
    if (passo === 0) return setPasso(1);
    if (problemas.length) return setErro(problemas[0]);
    setSalvando(true);
    void api
      .primeiroAcesso({ nome: nome.trim(), login: login.trim().toLowerCase(), senha, confirmar_senha: confirma })
      .then((r) => {
        try { localStorage.setItem("lumina-token", r.token); } catch { /* noop */ }
        onConcluido(r.usuario);
      })
      .catch((e) => { setErro(erroAmigavel(e)); setSalvando(false); setPasso(1); });
  };

  const passos = ["Boas-vindas", "Administrador", "Pronto"];

  return (
    <div className="login-wrap">
      <div className="login-bg" aria-hidden="true" />
      <form
        className={`login-card setup-card ${erro ? "shake" : ""}`}
        onSubmit={(e) => { e.preventDefault(); void avancar(); }}
      >
        <div className="login-brand">
          <div className="brand-mark"><Icon name="store" size={24} /></div>
          <div><strong>LUMINA</strong><span>PDV inteligente</span></div>
        </div>

        <div className="setup-steps">
          {passos.map((p, i) => (
            <div key={p} style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
              <div className={`setup-step ${i === passo ? "is-on" : ""} ${i < passo ? "is-done" : ""}`}>
                <i>{i < passo ? "✓" : i + 1}</i>
                <span>{p}</span>
              </div>
              {i < passos.length - 1 && <hr className={i < passo ? "is-done" : ""} />}
            </div>
          ))}
        </div>
        <div className="setup-bar"><div style={{ width: `${((passo + 1) / passos.length) * 100}%` }} /></div>

        {passo === 0 && (
          <>
            <h1>Vamos configurar o sistema</h1>
            <p className="login-sub">Este assistente roda uma vez só, logo após a instalação.</p>
            <ul className="setup-lista">
              <li><i><Icon name="user" size={14} /></i><div><strong>1. Criar o administrador</strong><small>O responsável pela loja — nome e senha.</small></div></li>
              <li><i><Icon name="box" size={14} /></i><div><strong>2. Cadastrar produtos</strong><small>Depois de entrar, em Estoque.</small></div></li>
              <li><i><Icon name="settings" size={14} /></i><div><strong>3. Ajustar o caixa e a impressora</strong><small>Depois de entrar, em Configurações.</small></div></li>
            </ul>
            <div className="setup-dica">
              <Icon name="alert" size={16} />
              <div>Anote a senha do administrador. <b>Não existe senha padrão</b> e, sem um administrador ativo, ninguém consegue entrar no sistema.</div>
            </div>
          </>
        )}

        {passo === 1 && (
          <>
            <h1>Criar usuário administrador</h1>
            <p className="login-sub">Este usuário tem acesso total ao sistema.</p>

            <label className="login-field">
              <span>Nome completo</span>
              <div className="login-input"><Icon name="user" size={18} /><input value={nome} onChange={(e) => setNome(e.target.value)} autoFocus autoComplete="name" placeholder="Ex.: Maria Souza" /></div>
            </label>

            <label className="login-field">
              <span>Login de acesso</span>
              <div className="login-input"><Icon name="lock" size={18} /><input value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" placeholder="Ex.: maria" /></div>
            </label>

            <label className="login-field">
              <span>Senha</span>
              <div className="login-input"><Icon name="lock" size={18} /><input type={vendo ? "text" : "password"} value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="new-password" placeholder="Mínimo de 6 caracteres" /><button type="button" onClick={() => setVendo((v) => !v)}>{vendo ? "Ocultar" : "Ver"}</button></div>
            </label>

            {senha && (
              <div className="setup-forca">
                <div><i style={{ width: `${(forca / 4) * 100}%`, background: nivel.cor }} /></div>
                <span style={{ color: nivel.cor, fontWeight: 700 }}>{nivel.rotulo}</span>
              </div>
            )}

            <label className="login-field">
              <span>Repetir a senha</span>
              <div className="login-input"><Icon name="check" size={18} /><input type={vendo ? "text" : "password"} value={confirma} onChange={(e) => setConfirma(e.target.value)} autoComplete="new-password" placeholder="Digite a mesma senha" /></div>
            </label>

            {erro && <div className="login-erro"><Icon name="alert" size={16} />{erro}</div>}
          </>
        )}

        {passo === 2 && (
          <>
            <h1>Tudo certo!</h1>
            <p className="login-sub">Confira os dados antes de abrir o caixa.</p>
            <div className="setup-resumo">
              <div><span>Administrador</span><b>{nome.trim()}</b></div>
              <div><span>Login</span><b>{login.trim().toLowerCase()}</b></div>
              <div><span>Perfil</span><b>Acesso total</b></div>
              <div><span>Dados do sistema</span><b>Em branco — você preenche depois</b></div>
            </div>
            <div className="setup-dica">
              <Icon name="alert" size={16} />
              <div>Depois de abrir, vá em <b>Configurações</b> para cadastrar os dados da empresa e o provedor fiscal.</div>
            </div>
            {erro && <div className="login-erro"><Icon name="alert" size={16} />{erro}</div>}
          </>
        )}

        <div className="setup-acoes">
          {passo > 0 && (
            <AppButton type="button" onClick={() => { setErro(""); setPasso(passo - 1); }} disabled={salvando}>Voltar</AppButton>
          )}
          <AppButton variant="primary" type="submit" disabled={salvando || (passo === 2 && problemas.length > 0)}>
            <Icon name={salvando ? "pause" : "check"} />
            {salvando ? "Criando…" : passo === 2 ? "Abrir o sistema" : "Continuar"}
          </AppButton>
        </div>

        <small className="login-foot">Passo {passo + 1} de {passos.length} · configuração inicial do PDV Lumina</small>
      </form>
    </div>
  );
}

function LoginScreen({ onEntrar }: { onEntrar: (u: UsuarioSessao) => void }) {
  const [login, setLogin] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [loading, setLoading] = useState(false);
  const [vendo, setVendo] = useState(false);

  const entrar = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!login.trim() || !senha) return setErro("Informe login e senha.");
    setLoading(true);
    setErro("");
    try {
      const r = await api.login(login.trim(), senha);
      try { localStorage.setItem("lumina-token", r.token); } catch { /* noop */ }
      onEntrar(r.usuario);
    } catch (e2) {
      setErro((e2 as Error).message || "Login ou senha inválidos.");
      setSenha("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-wrap">
      <div className="login-bg" aria-hidden="true" />
      <form className={`login-card ${erro ? "shake" : ""}`} onSubmit={entrar}>
        <div className="login-brand">
          <div className="brand-mark"><Icon name="store" size={24} /></div>
          <div><strong>LUMINA</strong><span>PDV inteligente</span></div>
        </div>
        <h1>Acessar o sistema</h1>
        <p className="login-sub">Entre com seu usuário para operar o caixa.</p>

        <label className="login-field">
          <span>Login</span>
          <div className="login-input"><Icon name="user" size={18} /><input value={login} onChange={(e) => setLogin(e.target.value)} autoFocus autoComplete="username" placeholder="Digite seu login" /></div>
        </label>

        <label className="login-field">
          <span>Senha</span>
          <div className="login-input"><Icon name="lock" size={18} /><input type={vendo ? "text" : "password"} value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" placeholder="Digite sua senha" /><button type="button" onClick={() => setVendo((v) => !v)} aria-label="Mostrar senha">{vendo ? "Ocultar" : "Ver"}</button></div>
        </label>

        {erro && <div className="login-erro"><Icon name="alert" size={16} />{erro}</div>}

        <AppButton variant="primary" type="submit" disabled={loading} className="login-btn">
          <Icon name="user" /> {loading ? "Entrando…" : "Entrar"}
        </AppButton>

        <small className="login-foot">PDV Lumina · acesso restrito a pessoas cadastradas</small>
      </form>
    </div>
  );
}

function App() {
  const [usuario, setUsuario] = useState<UsuarioSessao | null>(null);
  const [sessaoPronta, setSessaoPronta] = useState(false);
  const [precisaSetup, setPrecisaSetup] = useState(false);
  const [page, setPage] = useState<Page>("sales");
  // Sem produto de mentira: começa vazio e só mostra o que veio do banco.
// (números de demonstração em campo vazio confundem venda real com fictício)
const [products, setProducts] = useState<Product[]>(() => {
    try {
      const saved = localStorage.getItem("lumina-products");
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });
  const [cart, setCart] = useState<CartItem[]>([]);
  const [heldCart, setHeldCart] = useState<CartItem[]>([]);
  const [search, setSearch] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [saleQuantity, setSaleQuantity] = useState(1);
  const [discountOn, setDiscountOn] = useState(false);
  const [descCfg, setDescCfg] = useState<{ tipo: string; valor: number }>({ tipo: "nenhum", valor: 0 });
  const [modal, setModal] = useState<"payment" | "product" | "success" | "operations" | null>(null);
  const [editing, setEditing] = useState<Product | null>(null);
  const [toast, setToast] = useState("");
  const [payment, setPayment] = useState("Crédito");
  const [backendOnline, setBackendOnline] = useState(false);
  const [statusApi, setStatusApi] = useState<StatusApi>({ online: false, detalhe: "verificando a API...", verificadoEm: "—" });
  const [caixa, setCaixa] = useState<CaixaState>({ aberto: false, movimentoId: null, saldo: 0, valorInicial: 0, online: false, ultimoFechamento: null });
  const [lastFiscal, setLastFiscal] = useState<{ status: string; link: string } | null>(null);
  const [opValor, setOpValor] = useState("");
  const [opMotivo, setOpMotivo] = useState("");
  const [valorAbertura, setValorAbertura] = useState("");
  const [valorFechamento, setValorFechamento] = useState("");
  const [focoOperacao, setFocoOperacao] = useState<"abertura" | "fechamento" | "sangria" | "suprimento">("abertura");
  const [opsDia, setOpsDia] = useState<{ tipo: string; valor: number }[]>([]);
  const [valorRecebido, setValorRecebido] = useState("");
  const [lastTroco, setLastTroco] = useState(0);
  const [lastVendaId, setLastVendaId] = useState<number | null>(null);

  // imprime a venda; sem impressora, o backend salva em PDF e devolve o arquivo
  const imprimirDocumentoVenda = async (id: number, tipo: "fiscal" | "nao_fiscal") => {
    if (!backendOnline) return notify("Backend offline.");
    try {
      const r = await api.imprimirDocumento(id, tipo);
      if (r.modo === "pdf" && r.url) window.open(r.url, "_blank");
      notify(r.modo === "pdf" ? `Sem impressora: ${r.mensagem}` : r.mensagem);
      return r.modo;
    } catch (e) {
      notify(`Falha ao imprimir: ${erroAmigavel(e)}`);
      return "erro";
    }
  };

  const imprimirVenda = async () => {
    // respeita as chaves: cupom fiscal (NFC-e) e cupom NÃO fiscal ligados/desligados
    const id = lastVendaId;
    // abre a janela antes dos awaits (bloqueador de pop-up não impede)
    const janela = imprimirNaoFiscal && id !== null ? window.open("", "_blank") : null;
    if (imprimirNaoFiscal && id !== null) {
      const r = await api.imprimirDocumento(id, "nao_fiscal").catch((e) => {
        notify(`Falha no comprovante: ${erroAmigavel(e)}`);
        return null;
      });
      if (r) {
        if (r.modo === "pdf" && r.url) {
          if (janela) janela.location.href = r.url; else window.open(r.url, "_blank");
          notify(r.mensagem);
        } else if (janela) janela.close();
      }
    }
    if (imprimirFiscal) {
      let link = lastFiscal?.link || "";
      if (!link && id !== null && backendOnline) {
        try {
          const st = await api.fiscalStatus(id);
          setLastFiscal({ status: st.nfe_status, link: st.link });
          link = st.link || "";
        } catch { /* segue sem link */ }
      }
      if (link) {
        window.open(link, "_blank");
      } else if (id !== null) {
        await imprimirDocumentoVenda(id, "fiscal");
      } else if (backendOnline) {
        notify("Nota ainda processando — reimprima pelo Histórico.");
      }
    }
    if (!imprimirNaoFiscal && !imprimirFiscal) {
      notify("Impressão desativada nas configurações (nota fiscal e não fiscal).");
    }
    setModal(null);
    setPage("sales");
  };

  const dispensarImpressao = () => {
    setModal(null);
    setPage("sales");
  };
  const [historico, setHistorico] = useState<VendaHistorico[]>([]);
  const [historicoHoje, setHistoricoHoje] = useState<VendaHistorico[]>([]);
  const [historicoDia, setHistoricoDia] = useState<string>(() => hojeISO());
  const [historicoOps, setHistoricoOps] = useState<OperacaoCaixa[]>([]);
  const [historicoCarregando, setHistoricoCarregando] = useState(false);
  const [historicoErro, setHistoricoErro] = useState<string | null>(null);
  const [diaResumo, setDiaResumo] = useState<{ total: number; vendas: number }>({ total: 0, vendas: 0 });
  const [mesTotal, setMesTotal] = useState(0);
  const [relPeriodo, setRelPeriodo] = useState<"diario" | "semanal" | "mensal" | "personalizado">("mensal");
  const [relData, setRelData] = useState<RelatorioDados | null>(null);
  const [relConfig, setRelConfig] = useState<RelConfig>({
    periodo: "mensal", data: "", inicio: "", fim: "", agrupar: "dia",
    formas: [], categorias: [], produtos: "",
    graficoLinhas: true, graficoPizza: true, graficoBarras: false,
    campoLinhas: "total", fatiaPizza: "forma", paisagem: false,
  });
  const [relCarregando, setRelCarregando] = useState(false);
  const [relGerando, setRelGerando] = useState(false);
  const [relErro, setRelErro] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const quantityRef = useRef<HTMLInputElement>(null);

  const [settings, setSettings] = useState<SystemSettings>(defaultSettings);
  const [fiscal, setFiscal] = useState<FiscalState>(defaultFiscal);
  const [recibo, setRecibo] = useState<ReciboState>(defaultRecibo);
  const [imprimirFiscal, setImprimirFiscal] = useState(true);
  const [imprimirNaoFiscal, setImprimirNaoFiscal] = useState(true);
  const [testResults, setTestResults] = useState<Record<string, string>>({});
  const [testingProvider, setTestingProvider] = useState<string | null>(null);

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 3200);
  };

  // ---- sessão ----
  useEffect(() => {
    (async () => {
      // Primeiro acesso: enquanto não existir usuário, a tela inicial é o
      // assistente de configuração (e o token guardado é ignorado).
      try {
        const st = await api.setupStatus();
        if (!st.configurado) {
          try { localStorage.removeItem("lumina-token"); } catch { /* noop */ }
          setPrecisaSetup(true);
          setSessaoPronta(true);
          return;
        }
      } catch {
        // API fora do ar: cai no login normal, que já mostra o aviso.
      }
      try {
        const tem = (() => { try { return localStorage.getItem("lumina-token"); } catch { return null; } })();
        if (tem) setUsuario(await api.me());
      } catch {
        try { localStorage.removeItem("lumina-token"); } catch { /* noop */ }
      } finally {
        setSessaoPronta(true);
      }
    })();
  }, []);

  const sair = async () => {
    try { await api.logout(); } catch { /* noop */ }
    try { localStorage.removeItem("lumina-token"); } catch { /* noop */ }
    setUsuario(null);
    setPage("sales");
  };

  // fecha o PDV inteiro (o processo do .exe sai junto)
  const encerrarSistema = async () => {
    try { await api.encerrarSistema(); } catch { /* mesmo assim tenta sair */ }
    notify("Encerrando o PDV Lumina…");
    try { localStorage.removeItem("lumina-token"); } catch { /* noop */ }
  };

  // volta para o login quando o token expira (401 vindo da API)
  useEffect(() => {
    const aoExpirar = () => {
      setUsuario(null);
      setPage("sales");
      setToast("Sessão expirada. Faça login novamente.");
      window.setTimeout(() => setToast(""), 3500);
    };
    window.addEventListener("lumina:sessao-expirada", aoExpirar);
    return () => window.removeEventListener("lumina:sessao-expirada", aoExpirar);
  }, []);

  const ehAdmin = pode(usuario, "usuarios");

  // ---- carga inicial do backend ----
  const reloadProducts = async (avisarValidade = false) => {
    try {
      const list = await api.listarProdutos("");
      if (list.length) {
        const mapped = list.map(backendToFront);
        setProducts(mapped);
        setBackendOnline(true);
        if (avisarValidade) avisarValidades(mapped);
      }
    } catch { /* mantém cache local */ }
  };

  const avisarValidades = (list: Product[]) => {
    const porData = new Map<string, { qtd: number; dias: number }>();
    for (const p of list) {
      const lotes = p.lotes.length ? p.lotes.map((l) => ({ validade: l.validade, quantidade: l.quantidade }))
        : p.validade ? [{ validade: p.validade, quantidade: p.stock }] : [];
      for (const l of lotes) {
        const d = diasPara(l.validade);
        if (d === null || d > 15) continue;
        const e = porData.get(l.validade) || { qtd: 0, dias: d };
        e.qtd += l.quantidade;
        porData.set(l.validade, e);
      }
    }
    const datas = [...porData.entries()].sort((a, b) => a[0].localeCompare(b[0]));
    if (!datas.length) return;
    // por data (não por período), da maior para a menor urgência
    const partes = datas.slice(0, 3).map(([data, e]) =>
      e.dias < 0 ? `🔴 ${e.qtd} un. vencidas em ${fmtData(data)}` : `🟠 ${e.qtd} un. em ${fmtData(data)} (${urgText(e.dias)})`);
    if (datas.length > 3) partes.push(`+${datas.length - 3} data(s)`);
    notify(`Validades: ${partes.join(" · ")}. Ver Estoque → Ver mais.`);
  };

  // ---- histórico: mesmo padrão do estoque (estado no App + reload central) ----
  // mini-card do caixa: sempre o dia de hoje
  const reloadHistoricoHoje = async () => {
    try {
      setHistoricoHoje(await api.listarVendas(8, hojeISO()));
      setBackendOnline(true);
    } catch { /* mantém o que já está na tela */ }
  };

  // tela Histórico: dia selecionado (vendas + operações de caixa)
  const reloadHistorico = async (dia: string = historicoDia, limite = 200) => {
    setHistoricoCarregando(true);
    try {
      const [vendas, operacoes] = await Promise.all([
        api.listarVendas(limite, dia),
        api.operacoesCaixa(dia),
      ]);
      setHistorico(vendas);
      setHistoricoOps(operacoes);
      setHistoricoErro(null);
      setBackendOnline(true);
    } catch (e) {
      setHistoricoErro(erroAmigavel(e));
      const st = (e as { status?: number })?.status ?? 0;
      // só认为是 API fora quando é erro de rede (status 0) ou servidor 5xx
      if (st === 0 || st >= 500) setBackendOnline(false);
    } finally {
      setHistoricoCarregando(false);
    }
  };

  const reloadResumo = async () => {
    try {
      const t = await api.totaisDia(hojeISO());
      setDiaResumo({ total: t._geral, vendas: t._vendas });
    } catch { /* offline */ }
    try {
      const r = await api.relatorioFull("mensal");
      setMesTotal(r.total_geral);
    } catch { /* offline */ }
  };

  const carregarRelatorio = async (cfg?: RelConfig) => {
    const c = cfg || relConfig;
    setRelConfig(c);
    setRelPeriodo(c.periodo);
    if (!backendOnline) { setRelErro("Backend offline — relatório indisponível."); return; }
    setRelCarregando(true);
    setRelErro(null);
    try {
      const r = await api.dadosRelatorio({
        periodo: c.periodo,
        data: c.data,
        inicio: c.inicio,
        fim: c.fim,
        formas: c.formas,
        categorias: c.categorias,
        produtos: c.produtos.split(",").map((s) => s.trim()).filter(Boolean),
        agrupar: c.agrupar,
      });
      setRelData(r);
    } catch (e) {
      setRelErro(erroAmigavel(e));
    } finally {
      setRelCarregando(false);
    }
  };

  const gerarRelatorioPdf = async () => {
    if (!backendOnline) return notify("Backend offline.");
    setRelGerando(true);
    try {
      const r = await api.gerarRelatorioPdf({
        periodo: relConfig.periodo,
        data: relConfig.data,
        inicio: relConfig.inicio,
        fim: relConfig.fim,
        agrupar: relConfig.agrupar,
        formas: relConfig.formas,
        categorias: relConfig.categorias,
        produtos: relConfig.produtos.split(",").map((s) => s.trim()).filter(Boolean),
        grafico_linhas: relConfig.graficoLinhas,
        grafico_pizza: relConfig.graficoPizza,
        grafico_barras: relConfig.graficoBarras,
        campo_linhas: relConfig.campoLinhas,
        fatia_pizza: relConfig.fatiaPizza,
        paisagem: relConfig.paisagem,
      });
      window.open(r.url, "_blank");
      notify(`Relatório PDF gerado (${r.arquivo}, ${Math.round(r.bytes / 1024)} KB).`);
    } catch (e) {
      notify(`Falha ao gerar PDF: ${erroAmigavel(e)}`);
    } finally {
      setRelGerando(false);
    }
  };

  const cancelarVenda = async (id: number) => {
    if (!backendOnline) return notify("Backend offline.");
    if (!window.confirm(`Cancelar a venda #${id}? O estoque será estornado.`)) return;
    try {
      await api.cancelarVenda(id);
      notify(`Venda #${id} cancelada e estornada.`);
      await reloadHistorico();
      await reloadHistoricoHoje();
      await reloadProducts();
    } catch (e) {
      notify(`Falha ao cancelar: ${erroAmigavel(e)}`);
    }
  };

  useEffect(() => {
    (async () => {
      try {
        await api.health();
        setBackendOnline(true);
      } catch {
        setBackendOnline(false);
        notify("Backend offline — usando cache local.");
      }
      await reloadProducts(true);
      await reloadHistorico();
      await reloadHistoricoHoje();
      await reloadResumo();
      try {
        setCaixa(cxFromApi(await api.caixaAberto()));
      } catch { /* mantém padrão */ }
      try {
        const cfg = await api.getConfig();
        setSettings((s) => ({
          ...s,
          company: cfg.razao_social || s.company,
          tradeName: cfg.nome_fantasia || s.tradeName,
          cnpj: cfg.cnpj || s.cnpj,
          stateRegistration: cfg.ie || s.stateRegistration,
          email: cfg.email || s.email,
          phone: cfg.telefone || s.phone,
          address: cfg.endereco || s.address,
          city: cfg.cidade_uf || s.city,
          zip: cfg.cep || s.zip,
          emission: cfg.modelo_doc || s.emission,
          environment: cfg.ambiente === "producao" ? "Produção" : "Homologação",
          series: cfg.serie || s.series,
          printer: cfg.impressora_nome || s.printer,
          paperSize: cfg.impressora_largura || s.paperSize,
          autoPrint: Boolean(cfg.auto_print ?? s.autoPrint),
          printLogo: Boolean(cfg.exibir_logo ?? s.printLogo),
          cutPaper: Boolean(cfg.corte_auto ?? s.cutPaper),
          copies: String(cfg.impressora_vias ?? s.copies),
        }));
        setFiscal({
          provider: cfg.fiscal_provider || "mock",          ambiente: cfg.ambiente === "producao" ? "Produção" : "Homologação",
          modelo: cfg.modelo_doc || "NFC-e",
          serie: cfg.serie || "1",
          proximo: String(cfg.proximo_numero ?? "002848"),
          mock_url: cfg.mock_url || "http://localhost:3000",
          nuvem_token: cfg.nuvem_token || "",
          nuvem_url: cfg.nuvem_url || "https://api.nuvemfiscal.com.br/nfce",
          focus_token: cfg.focus_token || "",
          focus_url: cfg.focus_url || "https://api.focusnfe.com.br/v2/nfce",
          custom_token: cfg.custom_token || "",
          custom_url: cfg.custom_url || "",
          sefaz_cert_path: cfg.sefaz_cert_path || "",
        });
        const dt = cfg.desconto_tipo || "nenhum";
        setDescCfg({ tipo: dt, valor: Number(cfg.desconto_valor) || 0 });
        setDiscountOn(dt !== "nenhum");
        setRecibo({
          titulo: cfg.recibo_titulo ?? "",
          subtitulo: cfg.recibo_subtitulo ?? defaultRecibo.subtitulo,
          rodape: cfg.recibo_rodape ?? defaultRecibo.rodape,
          largura: String(cfg.recibo_largura) === "32" ? "32" : "48",
          mostrarCnpj: Boolean(cfg.recibo_mostrar_cnpj ?? 1),
          mostrarItens: Boolean(cfg.recibo_mostrar_itens ?? 1),
          mostrarPagamentos: Boolean(cfg.recibo_mostrar_pagamentos ?? 1),
          mostrarTroco: Boolean(cfg.recibo_mostrar_troco ?? 1),
          mostrarAtendente: Boolean(cfg.recibo_mostrar_atendente ?? 0),
          mostrarQrcode: Boolean(cfg.recibo_mostrar_qrcode ?? 1),
          qrcodeLink: cfg.recibo_qrcode_link ?? "",
          tributosFederal: Number(cfg.recibo_tributos_federal) || 0,
          tributosEstadual: Number(cfg.recibo_tributos_estadual) || 0,
          mostrarTributos: Boolean(cfg.recibo_mostrar_tributos ?? 1),
          avisoTrocas: cfg.recibo_aviso_trocas ?? defaultRecibo.avisoTrocas,
          mostrarAvisoTrocas: Boolean(cfg.recibo_mostrar_aviso_trocas ?? 1),
        });
        setImprimirFiscal(Boolean(cfg.imprimir_cupom_fiscal ?? 1));
        setImprimirNaoFiscal(Boolean(cfg.imprimir_cupom_nao_fiscal ?? 1));
      } catch { /* mantém padrão */ }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    try { localStorage.setItem("lumina-products", JSON.stringify(products)); } catch { /* noop */ }
  }, [products]);

  // abre/atualiza o histórico sempre que a tela entra (dados vêm do App, como o estoque)
  useEffect(() => {
    if (page === "history") void reloadHistorico(historicoDia);
  }, [page]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- batimento da API: detecta queda do servidor e recupera sozinho ----
  useEffect(() => {
    let vivo = true;
    const checar = async () => {
      const s = await verificarApi();
      if (!vivo) return;
      setStatusApi(s);
      setBackendOnline(s.online);
    };
    void checar();
    const t = window.setInterval(checar, 10000);
    window.addEventListener("online", checar);
    return () => {
      vivo = false;
      window.clearInterval(t);
      window.removeEventListener("online", checar);
    };
  }, []);

  // quando a API volta, recarrega histórico/estoque/resumo automaticamente
  const onlineAntes = useRef(backendOnline);
  useEffect(() => {
    if (backendOnline && !onlineAntes.current) {
      notify("API restabelecida — dados recarregados.");
      void reloadHistorico();
      void reloadHistoricoHoje();
      void reloadResumo();
      void reloadProducts();
    }
    onlineAntes.current = backendOnline;
  }, [backendOnline]); // eslint-disable-line react-hooks/exhaustive-deps

  const filteredProducts = useMemo(
    () => search.trim() ? products.filter((product) =>
      `${product.name} ${product.sku} ${product.sku.slice(-4)}`.toLowerCase().includes(search.toLowerCase())).slice(0, 7) : [],
    [products, search]
  );

  const subtotal = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const discountValue = !discountOn || descCfg.tipo === "nenhum" || subtotal <= 0 ? 0
    : descCfg.tipo === "valor" ? Math.min(Number(descCfg.valor) || 0, subtotal)
    : subtotal * (Number(descCfg.valor) || 0) / 100;
  const discountPct = subtotal > 0 ? (discountValue / subtotal) * 100 : 0;
  const discountLabel = !discountOn || discountValue <= 0 ? "" : descCfg.tipo === "valor" ? " (auto R$)" : ` (auto ${Number(descCfg.valor)}%)`;
  const total = subtotal - discountValue;
  const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);

  const toggleDesconto = () => {
    if (descCfg.tipo === "nenhum") {
      notify("Desconto automático desligado — configure em Configurações → Descontos.");
      return;
    }
    setDiscountOn((v) => {
      notify(v ? "Desconto removido." : `Desconto automático aplicado${discountLabel}.`);
      return !v;
    });
  };

  const addToCart = (product: Product, amount = 1, unitPrice?: number) => {
    if (product.stock <= 0) return notify("Produto sem estoque disponível.");
    const quantityToAdd = Math.max(1, amount);
    const price = unitPrice !== undefined && !Number.isNaN(unitPrice) && unitPrice > 0 ? Number(unitPrice.toFixed(2)) : product.price;
    const lineId = `${product.id}@${price.toFixed(2)}`;
    setCart((current) => {
      const emCarrinho = current.filter((i) => i.id === product.id).reduce((s, i) => s + i.quantity, 0);
      if (emCarrinho + quantityToAdd > product.stock) {
        notify("Quantidade máxima em estoque atingida.");
        return current;
      }
      const existing = current.find((item) => item.lineId === lineId);
      if (existing) {
        return current.map((item) => item.lineId === lineId ? { ...item, quantity: item.quantity + quantityToAdd } : item);
      }
      return [...current, { ...product, price, quantity: Math.min(quantityToAdd, product.stock), lineId }];
    });
    setSearch("");
    setSelectedIndex(0);
  };

  const changeQuantity = (lineId: string, amount: number) => {
    setCart((current) => {
      const item = current.find((i) => i.lineId === lineId);
      if (!item) return current;
      const prod = products.find((p) => p.id === item.id);
      const stock = prod ? prod.stock : item.stock;
      const others = current.filter((i) => i.id === item.id && i.lineId !== lineId).reduce((s, i) => s + i.quantity, 0);
      return current
        .map((i) => i.lineId === lineId ? { ...i, quantity: Math.min(stock - others, i.quantity + amount) } : i)
        .filter((i) => i.quantity > 0);
    });
  };

  const [lotesDraft, setLotesDraft] = useState<{ validade: string; quantidade: number }[]>([]);
  const [loteVal, setLoteVal] = useState("");
  const [loteQtd, setLoteQtd] = useState("");

  const addLoteDraft = () => {
    if (!loteVal) return notify("Informe a data do lote.");
    const q = Number(loteQtd);
    if (!q || q <= 0) return notify("Informe a quantidade do lote.");
    setLotesDraft((l) => [...l, { validade: loteVal, quantidade: q }].sort((a, b) => a.validade.localeCompare(b.validade)));
    setLoteVal("");
    setLoteQtd("");
  };

  // adiciona direto ao carrinho: sem modal, usando a quantidade da barra (− N +)
  const adicionarProduto = (product: Product, qtd?: number) => {
    const quantidade = Math.max(1, Math.floor(qtd ?? saleQuantity));
    const jaNoCarrinho = cart.filter((i) => i.id === product.id).reduce((s, i) => s + i.quantity, 0);
    if (jaNoCarrinho + quantidade > product.stock) {
      notify(`Estoque insuficiente: ${product.name} tem ${product.stock} un.`);
      setSaleQuantity(Math.max(1, product.stock - jaNoCarrinho));
      return;
    }
    addToCart(product, quantidade);
  };

  // Enter / setas: adiciona o produto destacado na lista de resultados
  const adicionarSelecionado = () => {
    const produto = filteredProducts[selectedIndex];
    if (!produto) return;
    adicionarProduto(produto);
  };

  const finishSale = async () => {
    if (!cart.length) return;
    // troco: só dinheiro com valor recebido maior que o total
    let troco = 0;
    if (payment === "Dinheiro") {
      const recebido = parseMoeda(valorRecebido);
      if (!valorRecebido.trim()) {
        notify("Informe o valor recebido em dinheiro.");
        return;
      }
      if (recebido < total) {
        notify(`Valor recebido (${money(recebido)}) menor que o total (${money(total)}).`);
        return;
      }
      troco = Number((recebido - total).toFixed(2));
    }
    // tenta vender no backend (baixa real de estoque + fiscal async)
    if (backendOnline) {
      try {
        if (!caixa.movimentoId && caixa.online) {
          const cx = await api.caixaAberto();
          if (!cx.aberto) {
            notify("Abra o caixa antes de vender (F4 → Abertura).");
            return;
          }
          setCaixa((c) => ({ ...cxFromApi(cx), saldo: cx.saldo_previsto ?? c.saldo }));
        }
        const venda = await api.criarVenda({
          id_movimento: caixa.movimentoId,
          itens: cart.map((i) => ({ id_produto: i.id, quantidade: i.quantity, valor_unitario: i.price })),
          pagamentos: [{ metodo: paymentToBackend(payment), valor: Number(total.toFixed(2)), parcelas: 1 }],
          desconto_percentual: discountPct,
        });
        setLastFiscal({ status: venda.nfe_status || "pendente", link: "" });
        setLastVendaId(venda.id);
        // busca status fiscal (pode ainda estar pendente — worker é async)
        window.setTimeout(async () => {
          try {
            const st = await api.fiscalStatus(venda.id);
            setLastFiscal({ status: st.nfe_status, link: st.link });
          } catch { /* noop */ }
        }, 2500);
        await reloadProducts();
        await reloadHistorico();
        await reloadHistoricoHoje();
        await reloadResumo();
        try {
          setCaixa(cxFromApi(await api.caixaAberto()));
        } catch { /* noop */ }
        setCart([]);
        setDiscountOn(descCfg.tipo !== "nenhum");
        setLastTroco(troco);
        setValorRecebido("");
        setModal("success");
        return;
      } catch (e) {
        setBackendOnline(false);
        const err = e as { status?: number; message?: string };
        if (!err.status) {
          // servidor fora do ar: nao vende "no falso" — evita venda que so existe na tela
          notify("API offline: a venda NÃO foi registrada. Ligue o servidor (RODAR_PDV.bat) e tente de novo.");
          return;
        }
        notify(`Falha ao registrar no servidor: ${erroAmigavel(e)}. Nada foi cobrado.`);
        return;
      }
    }
    // fallback offline (cache local) — só para leitura; sem venda espúria
    notify("API offline: venda não registrada.");
    return;
  };

  const holdSale = () => {
    if (!cart.length) return notify("Adicione produtos antes de suspender.");
    setHeldCart(cart);
    setCart([]);
    notify("Venda suspensa e salva com sucesso.");
  };

  const restoreSale = () => {
    if (!heldCart.length) return notify("Não há venda suspensa.");
    setCart(heldCart);
    setHeldCart([]);
    notify("Venda recuperada.");
  };

  const doOperacao = async (tipo: "sangria" | "suprimento") => {
    if (!caixa.aberto || !caixa.movimentoId) return notify("Abra o caixa antes de registrar operações.");
    if (!backendOnline) return notify("Backend offline.");
    const valor = parseMoeda(opValor);
    if (!valor || Number.isNaN(valor) || valor <= 0) return notify("Informe um valor maior que zero.");
    if (!opMotivo.trim()) return notify("Informe o motivo da operação.");
    if (tipo === "sangria" && valor > caixa.saldo) {
      return notify(`Sangria maior que o valor em caixa (${money(caixa.saldo)}).`);
    }
    try {
      const r = await api.operacao(caixa.movimentoId, tipo, valor, opMotivo.trim());
      setCaixa(cxFromApi(await api.caixaAberto()));
      notify(`${tipo === "sangria" ? "Sangria" : "Suprimento"} de ${money(valor)} registrada — valor em caixa ${money(r.saldo_previsto)}.`);
      setOpValor("");
      setOpMotivo("");
      setModal(null);
      void reloadResumo();
      void reloadHistorico();
    } catch (e) {
      notify(`Falha na operação: ${erroAmigavel(e)}`);
    }
  };

  const abrirOperacoes = (foco: "abertura" | "fechamento" | "sangria" | "suprimento") => {
    if (!caixa.aberto && foco !== "abertura") {
      notify("Caixa fechado — abra o caixa para registrar operações.");
    }
    setFocoOperacao(foco);
    if (!caixa.aberto) {
      setValorAbertura(maskMoeda(String(caixa.ultimoFechamento?.valor ?? 0)));
      setValorFechamento("");
    }
    setOpValor("");
    setOpMotivo("");
    setModal("operations");
    if (backendOnline) api.operacoesCaixa(hojeISO()).then(setOpsDia).catch(() => setOpsDia([]));
  };

  const doAbrirCaixa = async () => {
    if (!backendOnline) return notify("Backend offline.");
    if (caixa.aberto) return notify(`Caixa já aberto (mov. ${caixa.movimentoId ?? "—"}). Feche antes de abrir outro.`);
    const valor = parseMoeda(valorAbertura);
    if (Number.isNaN(valor) || valor < 0) return notify("Valor inicial inválido.");
    try {
      await api.abrirCaixa(valor);
      setCaixa(cxFromApi(await api.caixaAberto()));
      setValorFechamento("");
      notify(`Caixa aberto com ${money(valor)}.`);
      setModal(null);
    } catch (e) {
      notify(`Falha ao abrir: ${erroAmigavel(e)}`);
    }
  };

const doFecharCaixa = async () => {
    if (!caixa.aberto || !caixa.movimentoId) return notify("Nenhum caixa aberto.");
    const contado = parseMoeda(valorFechamento);
    if (!valorFechamento || Number.isNaN(contado) || contado < 0) return notify("Informe o valor contado no fechamento.");
    const dif = Number((contado - caixa.saldo).toFixed(2));
    const textoDif = dif === 0 ? "caixa confere" : dif > 0 ? `sobra de ${money(dif)}` : `falta de ${money(Math.abs(dif))}`;
    if (!window.confirm(
      `Fechar o caixa?\n\nPrevisto: ${money(caixa.saldo)}\nContado:  ${money(contado)}\nDiferença: ${textoDif}`
    )) return;
    try {
      await api.fecharCaixa(caixa.movimentoId, contado);
      setCaixa(cxFromApi(await api.caixaAberto()));
      setValorFechamento("");
      notify(`Caixa fechado em ${money(contado)} — ${textoDif}.`);
      setModal(null);
    } catch (e) {
      notify(`Falha ao fechar: ${erroAmigavel(e)}`);
    }
  };

  const gerarRelatorio = async (periodo: "diario" | "semanal" | "mensal") => {
    if (!backendOnline) return notify(`Relatório ${periodo} (offline): use o histórico local.`);
    try {
      const r = await api.relatorio(periodo);
      notify(`Relatório ${periodo}: ${money(r.total_geral)} em ${r.vendas} venda(s).`);
    } catch (e) {
      notify(`Falha no relatório: ${erroAmigavel(e)}`);
    }
  };

  useEffect(() => {
    if (modal !== "success") return;
    const timeout = window.setTimeout(() => { setModal(null); setPage("sales"); }, 30000);
    return () => window.clearTimeout(timeout);
  }, [modal]);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      const isFunctionKey = /^F[1-9]$/.test(event.key);
      if (isFunctionKey) event.preventDefault();
      if (event.key === "F1") { setPage("sales"); window.setTimeout(() => searchRef.current?.focus(), 0); }
      if (event.key === "F3") toggleDesconto();
      if (event.key === "F4") abrirOperacoes(focoOperacao);
      if (event.key === "F5") setPage("inventory");
      if (event.key === "F6") holdSale();
      if (event.key === "F7") restoreSale();
      if (event.key === "F8" && cart.length) setModal("payment");
      if (event.key === "F9" && cart.length) {
        if (modal === "payment") void finishSale();
        else setModal("payment");
      }
      if (event.key === "Escape") { setModal(null); }
      if (isFunctionKey) return;
      const alvo = event.target as HTMLElement;
      const emCampo = alvo.tagName === "INPUT" || alvo.tagName === "SELECT";
      if (page === "sales" && !modal && emCampo) {
        // quantidade: teclas + e - (ou = e _)
        if (event.key === "+" || event.key === "=") { event.preventDefault(); setSaleQuantity((v) => v + 1); return; }
        if (event.key === "-" || event.key === "_") { event.preventDefault(); setSaleQuantity((v) => Math.max(1, v - 1)); return; }
        if (event.key === "Enter" && filteredProducts[selectedIndex]) { event.preventDefault(); adicionarSelecionado(); return; }
        if (!["ArrowDown", "ArrowUp", "Enter", "Escape"].includes(event.key)) return;
      }
      if (page === "sales" && !modal) {
        if (event.key === "ArrowDown") { event.preventDefault(); setSelectedIndex((i) => Math.min(i + 1, filteredProducts.length - 1)); }
        if (event.key === "ArrowUp") { event.preventDefault(); setSelectedIndex((i) => Math.max(i - 1, 0)); }
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cart, heldCart, page, modal, filteredProducts, selectedIndex, discountOn, descCfg, search, saleQuantity, payment, caixa, backendOnline]);

  const saveProduct = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name"));
    const skuRaw = String(form.get("sku") || "").trim();
    const category = String(form.get("category")) as Product["category"];
    const price = parseMoeda(String(form.get("price") || ""));
    const stock = Number(form.get("stock"));
    // validade espelho = lote mais próximo ("" = indeterminada); lotes vão em PUT separado
    const validade = lotesDraft.length
      ? [...lotesDraft].sort((a, b) => a.validade.localeCompare(b.validade))[0].validade
      : "";
    // código opcional: vazio gera aleatório único no backend (sem conflito)
    const sku = skuRaw || "";
    const syncLotes = async (id: number) => {
      if (!backendOnline) return null;
      try {
        return await api.substituirLotes(id, lotesDraft);
      } catch (e) {
        notify(`Produto salvo, mas lotes falharam: ${erroAmigavel(e)}`);
        return null;
      }
    };
    if (backendOnline && !editing) {
      try {
        const bp = await api.criarProduto({
          nome: name, preco_venda: price, quantidade_estoque: stock,
          ean: sku, categoria: category, cor: "green", validade,
        });
        const lotes = await syncLotes(bp.id);
        setProducts((cur) => [...cur, { ...backendToFront(bp), lotes: lotes ?? [] }]);
        notify(`Produto cadastrado (cód. ${bp.sku}).`);
      } catch (e) {
        notify(`Falha ao salvar: ${erroAmigavel(e)}`);
        return;
      }
    } else if (backendOnline && editing) {
      try {
        const bp = await api.atualizarProduto(editing.id, {
          nome: name, preco_venda: price, quantidade_estoque: stock,
          ...(sku ? { ean: sku } : {}), categoria: category, validade,
        });
        const lotes = await syncLotes(editing.id);
        setProducts((cur) => cur.map((it) => it.id === editing.id ? { ...backendToFront(bp), lotes: lotes ?? it.lotes } : it));
        notify("Produto atualizado no servidor.");
      } catch (e) {
        notify(`Falha ao atualizar: ${erroAmigavel(e)}`);
        return;
      }
    } else {
      const product: Product = {
        id: editing?.id ?? Date.now(),
        name, sku: sku || String(Math.floor(10000000 + Math.random() * 89999999)), category, price, stock,
        color: editing?.color ?? "green", validade,
        lotes: lotesDraft.map((l, i) => ({ id: Date.now() + i, validade: l.validade, quantidade: l.quantidade })),
      };
      setProducts((current) => editing ? current.map((item) => item.id === editing.id ? product : item) : [...current, product]);
      notify(editing ? "Produto atualizado (offline)." : `Produto cadastrado (offline, cód. ${product.sku}).`);
    }
    setModal(null);
    setEditing(null);
  };

  const deleteProduct = async (id: number) => {
    if (backendOnline) {
      try {
        await api.excluirProduto(id);
        await reloadProducts();
        notify("Produto excluído no servidor.");
        return;
      } catch (e) {
        notify(`Falha ao excluir: ${erroAmigavel(e)}`);
        return;
      }
    }
    setProducts((current) => current.filter((item) => item.id !== id));
    notify("Produto excluído.");
  };

  const saveAllSettings = async () => {
    if (!backendOnline) return notify("Backend offline — configurações só locais.");
    try {
      await api.saveConfig({ ...fiscalToBackend(fiscal, settings, descCfg), ...reciboToBackend(recibo), imprimir_cupom_fiscal: imprimirFiscal ? 1 : 0, imprimir_cupom_nao_fiscal: imprimirNaoFiscal ? 1 : 0 });
      notify("Configurações salvas no servidor.");
    } catch (e) {
      notify(`Falha ao salvar: ${erroAmigavel(e)}`);
    }
  };

  const testProvider = async (providerId: string) => {
    if (!backendOnline) return notify("Backend offline.");
    setTestingProvider(providerId);
    try {
      const r = await api.testarFiscal({ ...fiscalToBackend(fiscal, settings, descCfg), fiscal_provider: providerId });
      setTestResults((t) => ({ ...t, [providerId]: `${r.ok ? "✅" : "❌"} ${r.mensagem}` }));
      notify(r.ok ? `Teste ${providerId}: OK.` : `Teste ${providerId}: falhou.`);
    } catch (e) {
      setTestResults((t) => ({ ...t, [providerId]: `❌ ${erroAmigavel(e)}` }));
    } finally {
      setTestingProvider(null);
    }
  };

  const [mockFile, setMockFile] = useState<{ id_nota: string; arquivos: string[]; pdf: string; preview: string } | null>(null);
  const [printFile, setPrintFile] = useState<{ arquivo: string; preview: string } | null>(null);
  const [previewRecibo, setPreviewRecibo] = useState<string>("Salve as configurações para ver o modelo.");
  const [carregandoPrevia, setCarregandoPrevia] = useState(false);
  const [qrPreview, setQrPreview] = useState<{ data_uri: string; biblioteca: string } | null>(null);
  const [qrErro, setQrErro] = useState<string>("");

  // gera o QR Code do link informado (qrcode/segno no servidor)
  const gerarQr = async (link: string) => {
    const alvo = link.trim();
    if (!/^https?:\/\//i.test(alvo)) { setQrPreview(null); setQrErro(alvo ? "Use um link começando com http:// ou https://" : ""); return; }
    if (!backendOnline) { setQrErro("Backend offline."); return; }
    setQrErro("");
    try {
      const r = await api.qrcodeUrl(alvo);
      setQrPreview({ data_uri: r.data_uri, biblioteca: r.biblioteca });
    } catch (e) {
      setQrPreview(null);
      setQrErro(erroAmigavel(e));
    }
  };

  // prévia do modelo da nota NÃO fiscal (usa o que está salvo no servidor)
  const atualizarPreviaRecibo = async () => {
    if (!backendOnline) return notify("Backend offline.");
    setCarregandoPrevia(true);
    try {
      const r = await api.reciboPreview();
      setPreviewRecibo(r.texto);
    } catch (e) {
      notify(`Falha na prévia: ${erroAmigavel(e)}`);
    } finally {
      setCarregandoPrevia(false);
    }
  };
  const [generating, setGenerating] = useState<string | null>(null);

  const gerarNotaTeste = async () => {
    if (!backendOnline) return notify("Backend offline.");
    setGenerating("mock-arquivo");
    try {
      await api.saveConfig({ ...fiscalToBackend(fiscal, settings, descCfg), ...reciboToBackend(recibo), imprimir_cupom_fiscal: imprimirFiscal ? 1 : 0, imprimir_cupom_nao_fiscal: imprimirNaoFiscal ? 1 : 0 });
      const r = await api.testeMockArquivo();
      setMockFile({ id_nota: r.id_nota, arquivos: r.arquivos, pdf: r.pdf, preview: r.espelho_preview });
      notify(`Nota teste ${r.id_nota} salva em data/notas_teste/.`);
    } catch (e) {
      notify(`Falha na nota teste: ${erroAmigavel(e)}`);
    } finally {
      setGenerating(null);
    }
  };

  const gerarCupomTeste = async () => {
    if (!backendOnline) return notify("Backend offline.");
    setGenerating("print-arquivo");
    try {
      await api.saveConfig({ ...fiscalToBackend(fiscal, settings, descCfg), ...reciboToBackend(recibo), imprimir_cupom_fiscal: imprimirFiscal ? 1 : 0, imprimir_cupom_nao_fiscal: imprimirNaoFiscal ? 1 : 0 });
      const r = await api.testeImpressaoArquivo();
      setPrintFile({ arquivo: r.arquivo, preview: r.preview });
      notify(`Cupom teste salvo em data/cupons/${r.arquivo}.`);
    } catch (e) {
      notify(`Falha no cupom teste: ${erroAmigavel(e)}`);
    } finally {
      setGenerating(null);
    }
  };

  if (!sessaoPronta) {
    return <div className="login-wrap"><div className="login-card"><div className="login-brand"><div className="brand-mark"><Icon name="store" size={22} /></div><div><strong>LUMINA</strong><span>PDV inteligente</span></div></div></div></div>;
  }
  if (precisaSetup) {
    return (
      <SetupWizardScreen
        onConcluido={(u) => { setPrecisaSetup(false); setUsuario(u); }}
      />
    );
  }
  if (!usuario) return <LoginScreen onEntrar={(u) => setUsuario(u)} />;

  const acesso = (p: Page, chave: string) => {
    if (pode(usuario, chave)) return null;
    return (
      <div className="page-content">
        <div className="content-card"><div className="empty-state">
          <Icon name="alert" size={30} />
          <strong>Acesso restrito</strong>
          <span>Seu perfil ({usuario.perfil_rotulo}) não tem permissão para esta tela.</span>
        </div></div>
      </div>
    );
  };
  const semAcesso =
    (page === "sales" && !pode(usuario, "vendas")) ||
    (page === "inventory" && !pode(usuario, "estoque_consulta")) ||
    (page === "history" && !pode(usuario, "historico_consulta")) ||
    (page === "reports" && !pode(usuario, "relatorios")) ||
    (page === "users" && !pode(usuario, "usuarios")) ||
    (page === "settings" && !pode(usuario, "configuracoes"));

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Icon name="store" size={22} /></div>
          <div><strong>LUMINA</strong><span>PDV inteligente</span></div>
        </div>
        <nav className="side-nav" aria-label="Navegação principal">
          {pode(usuario, "vendas") && (
            <button className={page === "sales" ? "active" : ""} onClick={() => setPage("sales")}>
              <Icon name="bag" /><span>Vendas</span><Shortcut>F1</Shortcut>
            </button>
          )}
          {pode(usuario, "estoque_consulta") && (
            <button className={page === "inventory" ? "active" : ""} onClick={() => setPage("inventory")}>
              <Icon name="box" /><span>Estoque</span><Shortcut>F5</Shortcut>
            </button>
          )}
          {pode(usuario, "historico_consulta") && (
            <button className={page === "history" ? "active" : ""} onClick={() => setPage("history")}>
              <Icon name="receipt" /><span>Histórico</span>
            </button>
          )}
          {pode(usuario, "relatorios") && (
            <button className={page === "reports" ? "active" : ""} onClick={() => { setPage("reports"); void carregarRelatorio(); }}>
              <Icon name="chart" /><span>Relatórios</span>
            </button>
          )}
          {pode(usuario, "usuarios") && (
            <button className={page === "users" ? "active" : ""} onClick={() => setPage("users")}>
              <Icon name="user" /><span>Pessoas</span>
            </button>
          )}
          {pode(usuario, "configuracoes") && (
            <button className={page === "settings" ? "active" : ""} onClick={() => setPage("settings")}>
              <Icon name="settings" /><span>Configurações</span>
            </button>
          )}
        </nav>
        <div className="sidebar-insight">
          <div className="insight-icon"><Icon name="chart" /></div>
          <span>Vendas de hoje{diaResumo.vendas ? ` · ${diaResumo.vendas} venda(s)` : ""}</span>
          <strong>{backendOnline ? money(diaResumo.total) : "—"}</strong>
          <small>Mês até agora: {backendOnline ? money(mesTotal) : "—"}</small>
        </div>
        <div className="operator">
          <div className="avatar">{(usuario?.nome || "MP").split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()}</div>
          <div><strong>{usuario?.nome || "—"}</strong><span>{usuario?.perfil_rotulo || ""}</span></div>
          <Icon name="logout" size={18} onClick={() => void sair()} style={{ cursor: "pointer" }} />
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <h1>{page === "sales" ? "Frente de caixa" : page === "inventory" ? "Gestão de estoque" : page === "history" ? "Histórico de vendas" : page === "reports" ? "Relatórios de vendas" : page === "users" ? "Pessoas e acessos" : "Configurações do sistema"}</h1>
            <p>{page === "sales" ? (cart.length ? `${cart.length} item(ns) no carrinho` : "Nenhuma venda em andamento") : page === "inventory" ? "Produtos e movimentações" : page === "history" ? "Vendas, cancelamentos e notas" : page === "reports" ? "Desempenho por período" : page === "users" ? "Cadastro de pessoas e permissões" : "Emissão e impressão fiscal"}</p>
          </div>
          <div className="topbar-meta">
            <div className="system-online" title={statusApi.detalhe}><i /> {backendOnline ? "Sistema online" : "Modo offline"} · {statusApi.verificadoEm}</div>
            <div className="date-block"><strong>{new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</strong><span>{new Date().toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })}</span></div>
          </div>
        </header>

        {!backendOnline && sessaoPronta && usuario && (
          <div className="settings-notice" style={{ margin: "0 0 14px" }}>
            <Icon name="alert" />
            <div>
              <strong>API offline</strong>
              <span>{statusApi.detalhe} Última verificação: {statusApi.verificadoEm}. Teste: http://127.0.0.1:8000/api/health</span>
            </div>
            <button onClick={() => { void verificarApi().then((s) => { setStatusApi(s); setBackendOnline(s.online); if (s.online) { void reloadHistorico(); void reloadHistoricoHoje(); void reloadResumo(); void reloadProducts(); } }); }}>Reconectar</button>
          </div>
        )}

{semAcesso ? acesso(page, "") : (
          <>
        {page === "sales" && (
          <div className="sales-layout">
            <section className="catalog">
              <div className="search-row">
                <div className="product-search-wrap">
                  <label className="search-box">
                    <Icon name="search" />
                    <input ref={searchRef} value={search} onChange={(e) => { setSearch(e.target.value); setSelectedIndex(0); }} placeholder="Digite o nome ou código de 4 dígitos" />
                    <div className="qty-stepper inline" title="Quantidade a adicionar (teclas + e -)">
                      <button onClick={() => setSaleQuantity((value) => Math.max(1, value - 1))} type="button" aria-label="Diminuir quantidade"><Icon name="minus" size={15} /></button>
                      <input ref={quantityRef} type="number" min="1" value={saleQuantity} onChange={(e) => setSaleQuantity(Math.max(1, Math.floor(Number(e.target.value)) || 1))} onFocus={() => quantityRef.current?.select()} aria-label="Quantidade de itens" />
                      <button onClick={() => setSaleQuantity((value) => value + 1)} type="button" aria-label="Aumentar quantidade"><Icon name="plus" size={15} /></button>
                    </div>
                    <Shortcut>F1</Shortcut>
                  </label>
                  {search && (
                    <div className="search-results">
                      <div className="search-results-head"><span>Produto</span><span>Disponível</span><span>Preço</span></div>
                      {filteredProducts.map((product, index) => (
                        <button key={product.id} className={selectedIndex === index ? "active" : ""} onMouseEnter={() => setSelectedIndex(index)} onClick={() => adicionarProduto(product)}>
                          <div><strong>{product.name}</strong><small>Cód. {product.sku.slice(-4)} · {product.category}</small></div>
                          <b className={product.stock <= 8 ? "low" : ""}>{product.stock} un.</b>
                          <span>{money(product.price)}<Icon name="plus" size={15} /></span>
                        </button>
                      ))}
                      {!filteredProducts.length && <div className="search-no-result"><Icon name="search" /><span>{!backendOnline ? "Sem conexão com o servidor — consulta indisponível." : products.length ? `Nenhum produto encontrado para "${search}"` : "Nenhum produto cadastrado. Cadastre em Gestão de estoque."}</span></div>}
                      <div className="search-hint"><Shortcut>↑</Shortcut><Shortcut>↓</Shortcut> navega · <Shortcut>Enter</Shortcut> adiciona {saleQuantity} un. · <Shortcut>+</Shortcut><Shortcut>-</Shortcut> muda a quantidade</div>
                    </div>
                  )}
                </div>
              </div>

              <div className="cash-overview single">
                <div className={`cash-status-card ${caixa.aberto ? "is-open" : "is-closed"}`}>
                  <div className="cash-status-top"><div className="metric-icon green"><Icon name="store" /></div><span className={`caixa-pill ${caixa.aberto ? "open" : "closed"}`}><i /> {caixa.aberto ? "Caixa aberto" : "Caixa fechado"}</span></div>
                  <p>{caixa.aberto
                    ? `Movimento de hoje ${caixa.movimentoId ?? "—"} · abertura ${money(caixa.valorInicial)}`
                    : caixa.ultimoFechamento
                      ? `Último fechamento ${money(caixa.ultimoFechamento.valor)} · ${fmtDataHora(caixa.ultimoFechamento.data)}`
                      : "Nenhum movimento ainda"}</p>
                  <div>
                    {caixa.aberto ? (
                      <>
                        <span>Valor em caixa<strong>{backendOnline ? money(caixa.saldo) : "—"}</strong></span>
                        <span>Vendas hoje<strong>{backendOnline ? diaResumo.vendas : "—"}</strong></span>
                        <span>Total do dia<strong>{backendOnline ? money(diaResumo.total) : "—"}</strong></span>
                      </>
                    ) : (
                      <>
                        <span>Último fechamento<strong>{backendOnline ? money(caixa.ultimoFechamento?.valor ?? 0) : "—"}</strong></span>
                        <span>Vendas hoje<strong>{backendOnline ? diaResumo.vendas : "—"}</strong></span>
                        <span>Total do dia<strong>{backendOnline ? money(diaResumo.total) : "—"}</strong></span>
                      </>
                    )}
                  </div>
                </div>
              </div>

              <div className="history-card full">
                <div className="history-heading"><div className="operation-icon blue"><Icon name="receipt" /></div><div><strong>Histórico de vendas — hoje</strong><span>Zera a cada dia · ver tudo no menu Histórico</span></div><button onClick={() => void reloadHistoricoHoje()}>Atualizar</button><button onClick={() => setPage("history")}>Ver tudo</button></div>
                <div className="history-list wide">
                  {!historicoHoje.length && <span className="history-empty">{backendOnline ? "Nenhuma venda hoje." : "Histórico offline."}</span>}
                  {historicoHoje.slice(0, 4).map((v) => (
                    <div className="history-row" key={v.id}>
                      <span><strong>#{v.id}</strong><small>{fmtDataHora(v.data_hora)} · {v.status}</small></span>
                      <b>{money(Number(v.total))}</b>
                      <i className={`nfe-pill ${v.nfe_status}`}>{v.nfe_status}</i>
                    </div>
                  ))}
                </div>
              </div>

              <section className="quick-operations">
                <div className="operations-heading"><div><h2>Operações do caixa</h2><p>Acessos rápidos para a rotina do operador</p></div><button onClick={() => abrirOperacoes(focoOperacao)}>Ver todas <Shortcut>F4</Shortcut></button></div>
                <div className="operation-grid">
                  <button onClick={() => abrirOperacoes("abertura")}><div className="operation-icon green"><Icon name="store" /></div><span><strong>Abertura de caixa</strong><small>{caixa.aberto ? `Aberto · mov. ${caixa.movimentoId ?? "—"}` : "Abrir novo turno"}</small></span><Icon name="chevron" size={16} /></button>
                  <button onClick={() => abrirOperacoes("fechamento")}><div className="operation-icon red"><Icon name="logout" /></div><span><strong>Fechamento</strong><small>Conferir e encerrar caixa</small></span><Icon name="chevron" size={16} /></button>
                  <button onClick={() => abrirOperacoes("sangria")}><div className="operation-icon amber"><Icon name="minus" /></div><span><strong>Sangria</strong><small>Registrar retirada</small></span><Icon name="chevron" size={16} /></button>
                  <button onClick={() => abrirOperacoes("suprimento")}><div className="operation-icon blue"><Icon name="plus" /></div><span><strong>Suprimento</strong><small>Registrar entrada</small></span><Icon name="chevron" size={16} /></button>
                </div>
              </section>

              <section className="report-strip">
                <div className="report-intro"><div className="operation-icon purple"><Icon name="chart" /></div><div><strong>Relatórios de vendas</strong><span>Consulte o desempenho do caixa por período</span></div></div>
                <div className="report-options"><button onClick={() => void gerarRelatorio("diario")}>Diário</button><button onClick={() => void gerarRelatorio("semanal")}>Semanal</button><button onClick={() => void gerarRelatorio("mensal")}>Mensal</button></div>
              </section>
            </section>

            <aside className="cart-panel">
              <div className="cart-heading">
                <div><span>Itens da venda</span><strong>{totalItems} {totalItems === 1 ? "item" : "itens"}</strong></div>
                {cart.length > 0 && <button onClick={() => setCart([])}><Icon name="trash" size={18} /> Limpar</button>}
              </div>
              <div className="cart-items">
                {!cart.length && (
                  <div className="cart-empty">
                    <div><Icon name="bag" size={28} /></div>
                    <strong>Seu carrinho está vazio</strong>
                    <span>Busque um produto pelo nome ou código para iniciar a venda.</span>
                  </div>
                )}
                {cart.map((item) => (
                  <div className="cart-item" key={item.lineId}>
                    <ProductGlyph category={item.category} color={item.color} />
                    <div className="cart-item-info"><strong>{item.name}</strong><span>{money(item.price)} / un.</span></div>
                    <div className="quantity">
                      <button onClick={() => changeQuantity(item.lineId, -1)}><Icon name="minus" size={14} /></button>
                      <b>{item.quantity}</b>
                      <button onClick={() => changeQuantity(item.lineId, 1)}><Icon name="plus" size={14} /></button>
                    </div>
                    <b>{money(item.price * item.quantity)}</b>
                  </div>
                ))}
              </div>
              <div className="cart-summary">
                <div><span>Subtotal</span><b>{money(subtotal)}</b></div>
                <button onClick={toggleDesconto}><span>Desconto{discountLabel} <Shortcut>F3</Shortcut></span><b className={discountOn && discountValue > 0 ? "discount-active" : ""}>{discountOn && discountValue > 0 ? `- ${money(discountValue)}` : "Adicionar"}</b></button>
                <div className="total-line"><span>Total</span><strong>{money(total)}</strong></div>
              </div>
              <div className="cart-actions">
                <AppButton onClick={holdSale}><Icon name="pause" /> Suspender <Shortcut>F6</Shortcut></AppButton>
                <AppButton variant="primary" disabled={!cart.length} onClick={() => setModal("payment")}><Icon name="card" /> Receber <Shortcut>F8</Shortcut></AppButton>
              </div>
            </aside>
          </div>
        )}

        {page === "inventory" && (
          <InventoryPage
            products={products}
            podeEditar={pode(usuario, "estoque_cadastro")}
            onAdd={() => { setEditing(null); setLotesDraft([]); setModal("product"); }}
            onEdit={(product) => { setEditing(product); setLotesDraft(product.lotes.map((l) => ({ validade: l.validade, quantidade: l.quantidade }))); setModal("product"); }}
            onDelete={(id) => void deleteProduct(id)}
          />
        )}

        {page === "history" && (
          <HistoryPage
            vendas={historico}
            operacoes={historicoOps}
            dia={historicoDia}
            loading={historicoCarregando}
            erro={historicoErro}
            online={backendOnline}
            onDia={(d) => { setHistoricoDia(d); void reloadHistorico(d); }}
            onRecarregar={() => void reloadHistorico()}
            onCancel={(id) => void cancelarVenda(id)}
            onImprimir={(id, tipo) => void imprimirDocumentoVenda(id, tipo)}
            podeLimpar={pode(usuario, "historico_limpar")}
            notify={notify}
          />
        )}

        {page === "reports" && (
          <ReportsPage
            dados={relData}
            config={relConfig}
            setConfig={setRelConfig}
            onAplicar={() => void carregarRelatorio()}
            onGerarPdf={() => void gerarRelatorioPdf()}
            loading={relCarregando}
            gerando={relGerando}
            erro={relErro}
            notify={notify}
            podeLimpar={pode(usuario, "historico_limpar")}
            onLimpar={() => void carregarRelatorio()}
          />
        )}

        {page === "users" && pode(usuario, "usuarios") && (
          <UsersPage usuarioAtual={usuario} onNotify={notify} />
        )}

        {page === "settings" && pode(usuario, "configuracoes") && (
          <SettingsPage
            settings={settings} setSettings={setSettings}
            fiscal={fiscal} setFiscal={setFiscal}
            descCfg={descCfg} setDescCfg={setDescCfg}
            recibo={recibo} setRecibo={setRecibo}
            qrPreview={qrPreview} qrErro={qrErro} onGerarQr={gerarQr}
            imprimirFiscal={imprimirFiscal} setImprimirFiscal={setImprimirFiscal}
            imprimirNaoFiscal={imprimirNaoFiscal} setImprimirNaoFiscal={setImprimirNaoFiscal}
            previewRecibo={previewRecibo}
            carregandoPrevia={carregandoPrevia}
            onAtualizarPrevia={atualizarPreviaRecibo}
            testResults={testResults} testingProvider={testingProvider}
            onTest={testProvider} onSave={saveAllSettings} notify={notify}
            mockFile={mockFile} printFile={printFile} generating={generating}
            onGerarNota={gerarNotaTeste} onGerarCupom={gerarCupomTeste}
            onEncerrar={encerrarSistema}
          />
        )}
          </>
        )}
      </main>

      {page === "sales" && (
        <div className="shortcut-bar">
          <span><Shortcut>F1</Shortcut> Buscar</span><span><Shortcut>F3</Shortcut> Desconto</span>
          <span><Shortcut>F4</Shortcut> Operações</span><span><Shortcut>F5</Shortcut> Estoque</span><span><Shortcut>F6</Shortcut> Suspender</span>
          <span><Shortcut>F7</Shortcut> Recuperar</span><span><Shortcut>F8</Shortcut> Receber</span><span><Shortcut>F9</Shortcut> Finalizar</span>
        </div>
      )}

      {modal === "product" && (
        <div className="modal-backdrop" onMouseDown={() => { setModal(null); setEditing(null); }}>
          <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
            <div className="modal-header"><div><span>Catálogo</span><h2>{editing ? "Editar produto" : "Novo produto"}</h2></div><button onClick={() => setModal(null)}><Icon name="close" /></button></div>
            <form onSubmit={(e) => void saveProduct(e)} className="product-form">
              <label className="field full"><span>Nome do produto</span><input name="name" required defaultValue={editing?.name} placeholder="Ex.: Café Especial 500g" /></label>
              <label className="field"><span>Código / SKU (opcional)</span><input name="sku" defaultValue={editing?.sku} placeholder="Vazio = gera sozinho" /></label>
              <label className="field"><span>Categoria</span><select name="category" defaultValue={editing?.category ?? "Alimentos"}><option>Bebidas</option><option>Alimentos</option><option>Padaria</option><option>Higiene</option></select></label>
              <label className="field"><span>Preço de venda</span><div className="money-input"><input name="price" inputMode="decimal" required defaultValue={editing ? fmtMoeda(editing.price) : ""} onChange={aplicarMascara} placeholder={EX_MOEDA} /><b>R$</b></div></label>
              <label className="field"><span>Estoque atual</span><input name="stock" type="number" min="0" required defaultValue={editing?.stock} placeholder={EX_NUM} /></label>
              <div className="field full">
                <span>Lotes de validade (opcional — vazio = indeterminada)</span>
                {lotesDraft.length > 0 && (
                  <div style={{ display: "grid", gap: 6, marginBottom: 8 }}>
                    {lotesDraft.map((l, i) => (
                      <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr auto auto", gap: 8, alignItems: "center", padding: "6px 10px", border: "1px solid #e3e7e4", borderRadius: 7, fontSize: 11 }}>
                        <span>📅 {fmtData(l.validade)} · <strong>{l.quantidade} un.</strong></span>
                        <span className="muted">{(() => { const d = diasPara(l.validade); return d === null ? "" : d < 0 ? "vencido" : d === 0 ? "hoje" : `${d}d`; })()}</span>
                        <button type="button" onClick={() => setLotesDraft((ds) => ds.filter((_, j) => j !== i))} aria-label="Remover lote"><Icon name="trash" size={15} /></button>
                      </div>
                    ))}
                  </div>
                )}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 90px auto", gap: 8 }}>
                  <input type="date" value={loteVal} onChange={(e) => setLoteVal(e.target.value)} aria-label="Data do lote" />
                  <input type="number" min="1" step="1" value={loteQtd} onChange={(e) => setLoteQtd(e.target.value)} placeholder={EX_NUM} aria-label="Quantidade do lote" />
                  <AppButton type="button" onClick={addLoteDraft}><Icon name="plus" /> Lote</AppButton>
                </div>
                <small style={{ color: "#8a958e", fontSize: 9 }}>Ex.: 100 un. no estoque, 20 vencendo dia 20 → adicione um lote de 20 na data.</small>
              </div>
              <div className="form-actions full"><AppButton type="button" onClick={() => setModal(null)}>Cancelar</AppButton><AppButton variant="primary" type="submit"><Icon name="check" /> Salvar produto</AppButton></div>
            </form>
          </div>
        </div>
      )}


      {modal === "operations" && (
        <div className="modal-backdrop" onMouseDown={() => setModal(null)}>
          <div className="modal operations-modal" onMouseDown={(e) => e.stopPropagation()}>
            <div className="modal-header"><div><span>Controle financeiro</span><h2>Operações do caixa</h2></div><button onClick={() => setModal(null)}><Icon name="close" /></button></div>
            <div className="operations-tabs">
              {([
                ["abertura", "store", "Abertura"],
                ["fechamento", "logout", "Fechamento"],
                ["sangria", "minus", "Sangria"],
                ["suprimento", "plus", "Suprimento"],
              ] as const).map(([id, ic, rot]) => (
                <button key={id} className={focoOperacao === id ? "active" : ""} onClick={() => setFocoOperacao(id)}>
                  <Icon name={ic} size={17} /><span>{rot}</span>
                </button>
              ))}
            </div>
            <div className="operations-modal-body">
              <div className={`cash-balance ${caixa.aberto ? "is-open" : "is-closed"}`}>
                <span>{caixa.aberto ? "Valor em caixa" : "Caixa fechado"}</span>
                <strong>{money(caixa.aberto ? caixa.saldo : (caixa.ultimoFechamento?.valor ?? 0))}</strong>
                <small>
                  {caixa.aberto
                    ? `mov. ${caixa.movimentoId ?? "—"} · aberto com ${money(caixa.valorInicial)} · ${usuario?.nome || ""}`
                    : `último fechamento${caixa.ultimoFechamento ? ` em ${fmtDataHora(caixa.ultimoFechamento.data)}` : ""}`}
                </small>
              </div>

              {focoOperacao === "abertura" && (
                <div className="op-panel">
                  <div className="settings-notice" style={{ margin: 0 }}><Icon name="store" /><div><strong>Abertura de caixa</strong><span>Valor em dinheiro que abre o turno (fundo de troco).</span></div></div>
                  <div className="form-grid">
                    <label className="field"><span>Valor inicial do caixa</span><CampoMoeda value={valorAbertura} onChange={(e) => setValorAbertura(maskMoeda(e.target.value))} placeholder={EX_MOEDA} disabled={caixa.aberto} /></label>
                    <div className="field"><span>&nbsp;</span>
                      <AppButton variant="primary" onClick={() => void doAbrirCaixa()} disabled={caixa.aberto || !backendOnline}>{caixa.aberto ? "Caixa já aberto" : "Abrir caixa"}</AppButton>
                    </div>
                  </div>
                  {caixa.aberto && <p className="op-note ok">Caixa aberto (mov. {caixa.movimentoId}). Feche para abrir outro turno.</p>}
                  {!caixa.ultimoFechamento && !caixa.aberto && <p className="op-note">Primeiro turno do sistema — informe o valor inicial.</p>}
                </div>
              )}

              {focoOperacao === "fechamento" && (
                <div className="op-panel">
                  <div className="settings-notice" style={{ margin: 0 }}><Icon name="logout" /><div><strong>Fechamento de caixa</strong><span>Confira o previsto com o contado. A diferença aparece antes de confirmar.</span></div></div>
                  <div className="form-grid">
                    <label className="field"><span>Previsto (R$)</span><input value={fmtMoeda(caixa.saldo)} readOnly disabled={!caixa.aberto} /></label>
                    <label className="field"><span>Contado no fechamento</span><CampoMoeda value={valorFechamento} onChange={(e) => setValorFechamento(maskMoeda(e.target.value))} placeholder={EX_MOEDA} disabled={!caixa.aberto} /></label>
                  </div>
                  {valorFechamento && parseMoeda(valorFechamento) > 0 && caixa.aberto && (
                    <p className={`op-note ${parseMoeda(valorFechamento) - caixa.saldo === 0 ? "ok" : "warn"}`}>
                      {parseMoeda(valorFechamento) - caixa.saldo === 0
                        ? "Caixa confere — pode fechar."
                        : parseMoeda(valorFechamento) - caixa.saldo > 0
                          ? `Sobra de ${money(parseMoeda(valorFechamento) - caixa.saldo)}.`
                          : `Falta de ${money(caixa.saldo - parseMoeda(valorFechamento))}.`}
                    </p>
                  )}
                  <div style={{ padding: "10px 0 0" }}><AppButton variant="primary" onClick={() => void doFecharCaixa()} disabled={!caixa.aberto || !backendOnline}>Conferir e fechar caixa</AppButton></div>
                </div>
              )}

              {(focoOperacao === "sangria" || focoOperacao === "suprimento") && (
                <div className="op-panel">
                  <div className="settings-notice" style={{ margin: 0 }}><Icon name={focoOperacao === "sangria" ? "minus" : "plus"} /><div>
                    <strong>{focoOperacao === "sangria" ? "Sangria (retirada)" : "Suprimento (entrada)"}</strong>
                    <span>{focoOperacao === "sangria" ? "Sai dinheiro do caixa. Ex.: pagamento a fornecedor." : "Entra dinheiro no caixa. Ex.: abertura de troco."}</span>
                  </div></div>
                  <div className="form-grid">
                    <label className="field"><span>Valor da operação</span><CampoMoeda value={opValor} onChange={(e) => setOpValor(maskMoeda(e.target.value))} placeholder={EX_MOEDA} disabled={!caixa.aberto} /></label>
                    <label className="field"><span>Motivo (obrigatório)</span><input value={opMotivo} onChange={(e) => setOpMotivo(e.target.value)} placeholder={focoOperacao === "sangria" ? "Ex.: pagamento fornecedor" : "Ex.: troco"} disabled={!caixa.aberto} /></label>
                  </div>
                  <div style={{ padding: "10px 0 0", display: "flex", gap: 8 }}>
                    {focoOperacao === "sangria"
                      ? <AppButton variant="danger" onClick={() => void doOperacao("sangria")} disabled={!caixa.aberto}><Icon name="minus" /> Registrar sangria</AppButton>
                      : <AppButton variant="primary" onClick={() => void doOperacao("suprimento")} disabled={!caixa.aberto}><Icon name="plus" /> Registrar suprimento</AppButton>}
                    <AppButton onClick={() => { setOpValor(""); setOpMotivo(""); }} disabled={!opValor && !opMotivo}>Limpar</AppButton>
                  </div>
                  {!caixa.aberto && <p className="op-note warn">Abra o caixa para registrar sangrias e suprimentos.</p>}
                  {focoOperacao === "sangria" && parseMoeda(opValor) > caixa.saldo && caixa.aberto && <p className="op-note warn">A sangria é maior que o valor em caixa ({money(caixa.saldo)}).</p>}
                </div>
              )}

              {opsDia.length > 0 && (
                <div className="op-summary">
                  <div><Icon name="store" /><strong>Operações de hoje</strong></div>
                  {opsDia.slice(0, 6).map((o, i) => (
                    <div className="op-summary-row" key={i}>
                      <i className={o.tipo} />
                      <span>{o.tipo === "sangria" ? "Sangria" : "Suprimento"}</span>
                      <b className={o.tipo}>{o.tipo === "sangria" ? "−" : "+"} {money(Number(o.valor))}</b>
                    </div>
                  ))}
                  <div className="op-summary-total">
                    <span>{caixa.aberto ? "Saldo após operações" : "Saldo (caixa aberto)"}</span>
                    <b>{caixa.aberto ? money(caixa.saldo) : "—"}</b>
                  </div>
                </div>
              )}

              <div className="modal-report">
                <div><Icon name="chart" /><span><strong>Gerar relatório</strong><small>Selecione o período desejado</small></span></div>
                <div><button onClick={() => void gerarRelatorio("diario")}>Diário</button><button onClick={() => void gerarRelatorio("semanal")}>Semanal</button><button onClick={() => void gerarRelatorio("mensal")}>Mensal</button></div>
              </div>
            </div>
          </div>
        </div>
      )}

      {modal === "payment" && (
        <div className="modal-backdrop" onMouseDown={() => setModal(null)}>
          <div className="modal payment-modal" onMouseDown={(e) => e.stopPropagation()}>
            <div className="modal-header"><div><span>Pagamento</span><h2>Finalizar venda</h2></div><button onClick={() => setModal(null)}><Icon name="close" /></button></div>
            <div className="payment-total"><span>Total a receber</span><strong>{money(total)}</strong></div>
            <div className="payment-methods">
              {["Crédito", "Débito", "PIX", "Dinheiro"].map((method) => <button className={payment === method ? "active" : ""} key={method} onClick={() => { setPayment(method); if (method === "Dinheiro" && !valorRecebido) setValorRecebido(maskMoeda(total.toFixed(2))); }}><Icon name={method === "PIX" ? "receipt" : "card"} /><span>{method}</span>{payment === method && <i><Icon name="check" size={13} /></i>}</button>)}
            </div>
            {payment === "Dinheiro" && (
              <div style={{ padding: "0 20px 4px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <label className="field"><span>Valor recebido</span><CampoMoeda value={valorRecebido} onChange={(e) => setValorRecebido(maskMoeda(e.target.value))} placeholder={exMoeda(total)} /></label>
                <div className="field"><span>Troco a devolver</span><div style={{ height: 40, display: "flex", alignItems: "center", padding: "0 11px", border: "1px solid #dbe1dc", borderRadius: 8, background: "#f1f6f2", fontWeight: 800, color: "#1b5c39" }}>
                  {valorRecebido && valorRecebido.trim() !== "" ? money(Math.max(0, parseMoeda(valorRecebido) - total)) : money(0)}
                </div></div>
              </div>
            )}
            {payment === "Dinheiro" && valorRecebido.trim() !== "" && parseMoeda(valorRecebido) < total && (
              <div style={{ padding: "0 20px 8px", color: "#a64f4f", fontSize: 11, fontWeight: 700 }}>Faltam {money(total - parseMoeda(valorRecebido))} para completar.</div>
            )}
            <div className="payment-info"><Icon name="printer" /><span>A nota fiscal ({fiscal.modelo || "NFC-e"} · {PROVIDER_INFO.find((p) => p.id === fiscal.provider)?.label || fiscal.provider}) será emitida {fiscal.ambiente === "Produção" ? "em produção" : "em homologação"} após a confirmação.{payment === "Dinheiro" && valorRecebido.trim() !== "" && parseMoeda(valorRecebido) >= total ? ` Troco: ${money(parseMoeda(valorRecebido) - total)}.` : ""}</span></div>
            <AppButton variant="primary" className="confirm-payment" disabled={payment === "Dinheiro" && (!valorRecebido.trim() || parseMoeda(valorRecebido) < total)} onClick={() => void finishSale()}><Icon name="check" /> Confirmar pagamento <Shortcut>F9</Shortcut></AppButton>
          </div>
        </div>
      )}

      {modal === "success" && (
        <div className="modal-backdrop success-backdrop" onMouseDown={dispensarImpressao}>
          <div className="sale-success-popup wide" onMouseDown={(e) => e.stopPropagation()}>
            <div className="success-check"><Icon name="check" size={22} /></div>
            <div><span>Venda concluída</span><h2>Pagamento aprovado</h2><p>Estoque atualizado{lastTroco > 0 ? ` · Troco a devolver: ${money(lastTroco)}` : ""}{lastFiscal ? ` · NF: ${lastFiscal.status}` : ""}.</p></div>
            <button onClick={dispensarImpressao} aria-label="Fechar"><Icon name="close" size={18} /></button>
            <div className="success-print">
              <span>Deseja imprimir a nota?</span>
              <div>
                <AppButton variant="primary" onClick={() => void imprimirVenda()}><Icon name="printer" /> Sim{imprimirNaoFiscal && imprimirFiscal ? ", cupom + nota" : imprimirNaoFiscal ? ", cupom" : imprimirFiscal ? ", nota fiscal" : ""}</AppButton>
                <AppButton onClick={dispensarImpressao}><Icon name="close" /> Não</AppButton>
              </div>
            </div>
            <i className="success-timer slow" />
          </div>
        </div>
      )}
      {toast && <div className="toast"><Icon name="check" size={18} />{toast}</div>}
    </div>
  );
}

function UsersPage({ usuarioAtual, onNotify }: { usuarioAtual: UsuarioSessao; onNotify: (m: string) => void }) {
  const [lista, setLista] = useState<{ id: number; nome: string; login: string; perfil: string; ativo?: number; criado_em?: string }[]>([]);
  const [perfis, setPerfis] = useState<{ id: string; rotulo: string; descricao: string; permissoes: string[] }[]>([]);
  const [permissoes, setPermissoes] = useState<{ chave: string; rotulo: string }[]>([]);
  const [editando, setEditando] = useState<{ id?: number; nome: string; login: string; senha: string; perfil: string } | null>(null);
  const [erro, setErro] = useState("");

  const carregar = async () => {
    try {
      setLista(await api.listarUsuarios());
    } catch (e) {
      onNotify(`Falha ao carregar pessoas: ${erroAmigavel(e)}`);
    }
  };
  useEffect(() => {
    void carregar();
    api.perfisAcesso().then((r) => { setPerfis(r.perfis); setPermissoes(r.permissoes); }).catch(() => { /* noop */ });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const salvar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editando) return;
    setErro("");
    try {
      if (editando.id) {
        await api.atualizarUsuario(editando.id, { nome: editando.nome, perfil: editando.perfil, ativo: 1, ...(editando.senha ? { senha: editando.senha } : {}) });
        onNotify("Pessoa atualizada.");
      } else {
        await api.criarUsuario({ nome: editando.nome, login: editando.login, senha: editando.senha, perfil: editando.perfil });
        onNotify("Pessoa cadastrada.");
      }
      setEditando(null);
      await carregar();
    } catch (e2) {
      setErro((e2 as Error).message);
    }
  };

  const alternarAtivo = async (u: { id: number; nome: string; ativo?: number }) => {
    if (!window.confirm(`${u.ativo ? "Desativar" : "Ativar"} o acesso de ${u.nome}?`)) return;
    try {
      await api.atualizarUsuario(u.id, { ativo: u.ativo ? 0 : 1 });
      onNotify(u.ativo ? "Acesso desativado." : "Acesso ativado.");
      await carregar();
    } catch (e) {
      onNotify(`Falha: ${erroAmigavel(e)}`);
    }
  };

  const remover = async (u: { id: number; nome: string }) => {
    if (!window.confirm(`Excluir ${u.nome}?`)) return;
    try {
      await api.excluirUsuario(u.id);
      onNotify("Pessoa excluída.");
      await carregar();
    } catch (e) {
      onNotify(`Falha: ${erroAmigavel(e)}`);
    }
  };

  const permsDoPerfil = (id: string) => perfis.find((p) => p.id === id)?.permissoes || [];

  return (
    <div className="page-content">
      <div className="metrics">
        <div className="metric"><div className="metric-icon blue"><Icon name="user" /></div><div><span>Pessoas cadastradas</span><strong>{lista.length}</strong><small>com acesso ao PDV</small></div></div>
        <div className="metric"><div className="metric-icon green"><Icon name="check" /></div><div><span>Administradores</span><strong>{lista.filter((u) => u.perfil === "admin").length}</strong><small>acesso total</small></div></div>
        <div className="metric"><div className="metric-icon amber"><Icon name="alert" /></div><div><span>Operadores</span><strong>{lista.filter((u) => u.perfil === "operador").length}</strong><small>caixa e estoque</small></div></div>
      </div>

      <section className="content-card">
        <div className="table-toolbar">
          <div><h2>Pessoas e acessos</h2><p>Cadastre operadores e defina o que cada perfil pode fazer.</p></div>
          <div className="toolbar-actions">
            <AppButton variant="primary" onClick={() => setEditando({ nome: "", login: "", senha: "", perfil: "operador" })}><Icon name="plus" /> Nova pessoa</AppButton>
          </div>
        </div>
        <div className="product-table">
          <div className="table-row table-head"><span>Pessoa</span><span>Login</span><span>Perfil</span><span>Acesso</span><span>Desde</span><span>Ações</span></div>
          {lista.map((u) => (
            <div className="table-row" key={u.id}>
              <div className="table-product"><div className="avatar" style={{ width: 34, height: 34, fontSize: 11 }}>{u.nome.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()}</div><strong>{u.nome}{u.id === usuarioAtual.id ? " (você)" : ""}</strong></div>
              <span className="muted">{u.login}</span>
              <span><b className={`perfil-pill ${u.perfil}`}>{perfis.find((p) => p.id === u.perfil)?.rotulo || u.perfil}</b></span>
              <span>{u.ativo ? "Ativo" : "Inativo"}</span>
              <span className="muted">{fmtData(u.criado_em || "")}</span>
              <div className="row-actions">
                <button aria-label="Editar" title="Editar" onClick={() => setEditando({ id: u.id, nome: u.nome, login: u.login, senha: "", perfil: u.perfil })}><Icon name="edit" size={17} /></button>
                {u.id !== usuarioAtual.id && <button aria-label={u.ativo ? "Desativar" : "Ativar"} title={u.ativo ? "Desativar acesso" : "Ativar acesso"} onClick={() => void alternarAtivo(u)}><Icon name="check" size={17} /></button>}
                {u.id !== usuarioAtual.id && <button aria-label="Excluir" title="Excluir" onClick={() => void remover(u)}><Icon name="trash" size={17} /></button>}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="content-card" style={{ marginTop: 14 }}>
        <div className="table-toolbar"><div><h2>Perfis de acesso</h2><p>O que cada perfil pode fazer no sistema.</p></div></div>
        <div className="product-table">
          <div className="table-row table-head"><span>Permissão</span><span>Administrador</span><span>Operador de caixa</span><span></span><span></span><span></span></div>
          {permissoes.map((p) => (
            <div className="table-row" key={p.chave}>
              <div className="table-product"><strong>{p.rotulo}</strong></div>
              <span>{permsDoPerfil("admin").includes("*") || permsDoPerfil("admin").includes(p.chave) ? "✓" : "—"}</span>
              <span>{permsDoPerfil("operador").includes(p.chave) ? "✓" : "—"}</span>
              <span /><span /><span />
            </div>
          ))}
        </div>
      </section>

      {editando && (
        <div className="modal-backdrop" onMouseDown={() => setEditando(null)}>
          <div className="modal small-modal" onMouseDown={(e) => e.stopPropagation()}>
            <div className="modal-header"><div><span>Acessos</span><h2>{editando.id ? "Editar pessoa" : "Nova pessoa"}</h2></div><button onClick={() => setEditando(null)}><Icon name="close" /></button></div>
            <form className="product-form" onSubmit={salvar}>
              <label className="field full"><span>Nome completo</span><input required value={editando.nome} onChange={(e) => setEditando({ ...editando, nome: e.target.value })} placeholder="Ex.: Marina P." /></label>
              <label className="field full"><span>Login</span><input required disabled={!!editando.id} value={editando.login} onChange={(e) => setEditando({ ...editando, login: e.target.value })} placeholder="login sem espaços" /></label>
              <label className="field full"><span>{editando.id ? "Nova senha (deixe vazio p/ manter)" : "Senha"}</span><input type="password" required={!editando.id} minLength={4} value={editando.senha} onChange={(e) => setEditando({ ...editando, senha: e.target.value })} placeholder="mínimo 4 caracteres" /></label>
              <label className="field full"><span>Perfil de acesso</span>
                <select value={editando.perfil} onChange={(e) => setEditando({ ...editando, perfil: e.target.value })}>
                  {perfis.map((p) => <option key={p.id} value={p.id}>{p.rotulo}</option>)}
                </select>
              </label>
              <div className="field full"><span>Este perfil pode</span>
                <div className="perms-box">
                  {permissoes.map((p) => {
                    const lista = permsDoPerfil(editando.perfil);
                    const tem = lista.includes("*") || lista.includes(p.chave);
                    return <span key={p.chave} className={tem ? "yes" : "no"}>{tem ? "✓" : "✕"} {p.rotulo}</span>;
                  })}
                </div>
              </div>
              {erro && <div className="login-erro" style={{ gridColumn: "1/-1" }}><Icon name="alert" size={16} />{erro}</div>}
              <div className="form-actions full"><AppButton type="button" onClick={() => setEditando(null)}>Cancelar</AppButton><AppButton variant="primary" type="submit"><Icon name="check" /> Salvar</AppButton></div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function LimpezaVendas({ onDone, notify }: { onDone: () => void; notify: (m: string) => void }) {
  const [escopo, setEscopo] = useState<"tudo" | "periodo">("tudo");
  const [inicio, setInicio] = useState("");
  const [fim, setFim] = useState("");
  const [prev, setPrev] = useState<{ vendas: number; total: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const verPrevia = async (e?: string, f?: string) => {
    const i = e !== undefined ? e : inicio;
    const ff = f !== undefined ? f : fim;
    if (escopo === "periodo" && (!i || !ff)) { setPrev(null); return; }
    setLoading(true);
    try {
      const p = await api.previewLimpeza(escopo === "tudo" ? "" : i, escopo === "tudo" ? "" : ff);
      setPrev({ vendas: p.vendas, total: p.total });
    } catch (err) {
      notify(`Falha na prévia: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void verPrevia(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const apagar = async () => {
    if (!prev || prev.vendas === 0) return;
    const rotulo = escopo === "tudo" ? "TODO O PERÍODO" : `de ${inicio} até ${fim}`;
    if (!window.confirm(`Apagar ${prev.vendas} venda(s) (${money(prev.total)}) ${rotulo}?\nO estoque das vendas concluídas será estornado. Não há como desfazer.`)) return;
    setLoading(true);
    try {
      const r = await api.limparVendas(escopo === "tudo" ? "" : inicio, escopo === "tudo" ? "" : fim);
      notify(`${r.removidas} venda(s) apagadas (${money(r.total)}).`);
      setPrev(null);
      onDone();
      void verPrevia();
    } catch (err) {
      notify(`Falha ao apagar: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  };
  return (
    <section className="content-card" style={{ marginTop: 18, borderColor: "#efc9c9" }}>
      <div className="table-toolbar">
        <div><h2>Limpar histórico</h2><p>Apaga vendas (com estorno de estoque). Escolha todo o período ou um intervalo.</p></div>
      </div>
      <div className="form-grid">
        <label className="field"><span>Escopo</span>
          <select value={escopo} onChange={(e) => { setEscopo(e.target.value as "tudo" | "periodo"); setPrev(null); }}>
            <option value="tudo">Todo o período</option>
            <option value="periodo">De uma data até outra</option>
          </select>
        </label>
        <div className="field"><span>Prévia</span><div style={{ minHeight: 40, display: "flex", alignItems: "center", fontWeight: 700 }}>
          {loading ? "…" : prev ? `${prev.vendas} venda(s) · ${money(prev.total)}` : "—"}
        </div></div>
        {escopo === "periodo" && (
          <>
            <label className="field"><span>De</span><input type="date" value={inicio} onChange={(e) => { setInicio(e.target.value); void verPrevia(e.target.value, fim); }} /></label>
            <label className="field"><span>Até</span><input type="date" value={fim} onChange={(e) => { setFim(e.target.value); void verPrevia(inicio, e.target.value); }} /></label>
          </>
        )}
      </div>
      <div style={{ display: "flex", gap: 8, padding: "12px 20px 20px" }}>
        <AppButton onClick={() => void verPrevia()}>Ver prévia</AppButton>
        <AppButton variant="danger" onClick={() => void apagar()} disabled={!prev || prev.vendas === 0 || loading}>
          <Icon name="trash" /> Apagar vendas
        </AppButton>
      </div>
    </section>
  );
}

function HistoryPage({ vendas, operacoes, dia, loading, erro, online, onDia, onRecarregar, onCancel, onImprimir, podeLimpar, notify }: {
  vendas: VendaHistorico[];
  operacoes: OperacaoCaixa[];
  dia: string;
  loading: boolean;
  erro: string | null;
  online: boolean;
  onDia: (dia: string) => void;
  onRecarregar: () => void;
  onCancel: (id: number) => void;
  onImprimir: (id: number, tipo: "fiscal" | "nao_fiscal") => void;
  podeLimpar: boolean;
  notify: (m: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [aba, setAba] = useState<"vendas" | "caixa">("vendas");

  const termo = query.trim().toLowerCase();
  const vis = vendas.filter((v) => !termo || String(v.id).includes(termo));
  const canceladas = vis.filter((v) => v.status === "cancelada").length;
  const total = vis.filter((v) => v.status !== "cancelada").reduce((s, v) => s + Number(v.total), 0);
  const opsVis = operacoes.filter((o) => !termo || o.observacao.toLowerCase().includes(termo) || o.tipo.includes(termo));
  const totalSangria = opsVis.filter((o) => o.tipo === "sangria").reduce((s, o) => s + Number(o.valor), 0);
  const totalSuprimento = opsVis.filter((o) => o.tipo === "suprimento").reduce((s, o) => s + Number(o.valor), 0);

  return (
    <div className="page-content">
      <div className="metrics">
        <div className="metric"><div className="metric-icon blue"><Icon name="receipt" /></div><div><span>Vendas do dia</span><strong>{vis.length}</strong><small>{fmtData(dia)}</small></div></div>
        <div className="metric"><div className="metric-icon green"><Icon name="tag" /></div><div><span>Total (exc. canceladas)</span><strong>{money(total)}</strong><small>somatório</small></div></div>
        <div className="metric"><div className="metric-icon amber"><Icon name="alert" /></div><div><span>Canceladas</span><strong>{canceladas}</strong><small>estornadas</small></div></div>
      </div>

      {erro && (
        <div className="settings-notice" style={{ marginBottom: 14 }}>
          <Icon name="alert" />
          <div>
            <strong>Erro ao carregar histórico</strong>
            <span>{erro}</span>
          </div>
          <button onClick={onRecarregar}>Tentar novamente</button>
        </div>
      )}

      <section className="content-card">
        <div className="table-toolbar">
          <div><h2>Histórico de vendas</h2><p>Por dia — amanhã a lista recomeça. Cancele com estorno, reimprima o cupom.</p></div>
          <div className="toolbar-actions">
            <label className="search-box compact"><Icon name="search" /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar #id" /></label>
            <input type="date" value={dia} onChange={(e) => onDia(e.target.value)} style={{ height: 42, padding: "0 11px", border: "1px solid #dbe1dc", borderRadius: 8, fontSize: 11 }} />
            <AppButton onClick={onRecarregar} disabled={loading}>{loading ? "Carregando…" : "Atualizar"}</AppButton>
            <AppButton onClick={() => { setQuery(""); onDia(hojeISO()); }}>Hoje</AppButton>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, padding: "0 18px" }}>
          <AppButton variant={aba === "vendas" ? "primary" : "secondary"} onClick={() => setAba("vendas")}><Icon name="receipt" /> Vendas ({vis.length})</AppButton>
          <AppButton variant={aba === "caixa" ? "primary" : "secondary"} onClick={() => setAba("caixa")}><Icon name="store" /> Operações do caixa ({opsVis.length})</AppButton>
        </div>

        {aba === "vendas" && (
          <div className="product-table">
            <div className="table-row table-head"><span>Venda</span><span>Data/hora</span><span>Total</span><span>NF</span><span>Status</span><span>Ações</span></div>
            {vis.map((v) => (
              <div className="table-row" key={v.id}>
                <div className="table-product"><strong>#{v.id}</strong></div>
                <span className="muted">{fmtDataHora(v.data_hora)}</span>
                <strong>{money(Number(v.total))}</strong>
                <span><i className={`nfe-pill ${v.nfe_status}`}>{v.nfe_status}</i></span>
                <span>{v.status}</span>
                <div className="row-actions">
                  <button aria-label="Imprimir cupom" title="Imprimir cupom (sem impressora = PDF)" onClick={() => onImprimir(v.id, "nao_fiscal")}><Icon name="printer" size={17} /></button>
                  {v.status !== "cancelada" && <button aria-label="Cancelar" title="Cancelar com estorno" onClick={() => onCancel(v.id)}><Icon name="trash" size={17} /></button>}
                </div>
              </div>
            ))}
            {!vis.length && (
              <div className="empty-state">
                <Icon name="receipt" size={30} />
                <strong>{erro ? "Não foi possível carregar" : `Nenhuma venda em ${fmtData(dia)}`}</strong>
                <span>{erro
                  ? "Verifique a conexão com o servidor e clique em Atualizar."
                  : online
                    ? "As vendas aparecem aqui assim que você fechar uma venda no caixa (F9). Troque a data acima para ver outros dias."
                    : "Backend offline —Histórico indisponível."}</span>
              </div>
            )}
          </div>
        )}
        {aba === "caixa" && (
          <div className="product-table">
            <div className="table-row table-head"><span>Operação</span><span>Hora</span><span>Valor</span><span>Motivo</span><span>Mov.</span><span></span></div>
            {opsVis.map((o) => (
              <div className="table-row" key={o.id}>
                <div className="table-product"><div className={`operation-icon ${o.tipo === "sangria" ? "amber" : "blue"}`}><Icon name={o.tipo === "sangria" ? "minus" : "plus"} size={16} /></div><strong>{o.tipo === "sangria" ? "Sangria" : "Suprimento"}</strong></div>
                <span className="muted">{fmtDataHora(o.data_hora)}</span>
                <strong style={{ color: o.tipo === "sangria" ? "#a64f4f" : "#35704a" }}>{o.tipo === "sangria" ? "−" : "+"} {money(Number(o.valor))}</strong>
                <span className="muted">{o.observacao || "—"}</span>
                <span className="muted">#{o.id_movimento}</span>
                <div className="row-actions" />
              </div>
            ))}
            {!opsVis.length && (
              <div className="empty-state">
                <Icon name="store" size={30} />
                <strong>Nenhuma operação em {fmtData(dia)}</strong>
                <span>Sangrias e suprimentos registrados no caixa aparecem nesta aba.</span>
              </div>
            )}
            {(totalSangria > 0 || totalSuprimento > 0) && (
              <div className="table-row"><span><strong>Totais do dia</strong></span><span /><span /><span style={{ color: "#a64f4f" }}>− {money(totalSangria)}</span><span style={{ color: "#35704a" }}>+ {money(totalSuprimento)}</span><span /></div>
            )}
          </div>
        )}

        {podeLimpar && <LimpezaVendas onDone={onRecarregar} notify={notify} />}
      </section>
    </div>
  );
}

const CORES_GRAFICO = ["#2a6b47", "#3d82a8", "#d99e2e", "#9e59a0", "#c7594f", "#668a4d", "#4d5a8c", "#8c7340"];

const rotuloCampo: Record<string, string> = {
  total: "Faturamento total", vendas: "Quantidade de vendas",
  dinheiro: "Dinheiro", credito: "Crédito", debito: "Débito", pix: "PIX",
};

function GraficoLinhas({ pontos, campo, titulo }: {
  pontos: RelatorioDados["serie"]; campo: string; titulo: string;
}) {
  const w = 720, h = 210, pad = { t: 12, r: 12, b: 26, l: 58 };
  const dados = pontos.map((p) => Number(p[campo as keyof typeof p] as number) || 0);
  const max = Math.max(...dados, 1);
  const px = (i: number) => pad.l + (pontos.length > 1 ? (i * (w - pad.l - pad.r)) / (pontos.length - 1) : (w - pad.l - pad.r) / 2);
  const py = (v: number) => h - pad.b - (v / max) * (h - pad.t - pad.b);
  const linha = dados.map((v, i) => `${px(i)},${py(v)}`).join(" ");
  const area = `${px(0)},${h - pad.b} ${linha} ${px(dados.length - 1)},${h - pad.b}`;
  const passo = Math.max(1, Math.ceil(pontos.length / 12));
  return (
    <div className="graf-card">
      <div className="graf-head"><strong>{titulo}</strong><span>{money(max)}</span></div>
      {!pontos.length ? <div className="graf-vazio">Sem dados no período</div> : (
        <svg viewBox={`0 0 ${w} ${h}`} className="graf-svg" role="img" aria-label={titulo}>
          {[0, .25, .5, .75, 1].map((f) => (
            <g key={f}>
              <line x1={pad.l} x2={w - pad.r} y1={py(max * f)} y2={py(max * f)} className="graf-grid" />
              <text x={pad.l - 6} y={py(max * f) + 3} className="graf-tick" textAnchor="end">
                {money(max * f).replace("R$ ", "")}
              </text>
            </g>
          ))}
          <polygon points={area} className="graf-area" />
          <polyline points={linha} className="graf-linha" />
          {dados.map((v, i) => <circle key={i} cx={px(i)} cy={py(v)} r={3} className="graf-ponto" />)}
          {pontos.map((p, i) => (i % passo === 0 || i === pontos.length - 1) && (
            <text key={p.rotulo + i} x={px(i)} y={h - 8} className="graf-tick" textAnchor="middle">
              {p.rotulo.length > 10 ? p.rotulo.slice(5) : p.rotulo}
            </text>
          ))}
        </svg>
      )}
    </div>
  );
}

function GraficoPizza({ fatias, titulo }: {
  fatias: { rotulo: string; valor: number }[]; titulo: string;
}) {
  const dados = fatias.filter((f) => f.valor > 0);
  const total = dados.reduce((s, f) => s + f.valor, 0) || 1;
  const r = 82, cx = 100, cy = 100;
  let ang = -90;
  const partes = dados.map((f, i) => {
    const ang2 = ang + (360 * f.valor) / total;
    const x1 = cx + r * Math.cos((ang * Math.PI) / 180);
    const y1 = cy + r * Math.sin((ang * Math.PI) / 180);
    const x2 = cx + r * Math.cos((ang2 * Math.PI) / 180);
    const y2 = cy + r * Math.sin((ang2 * Math.PI) / 180);
    const grande = ang2 - ang > 180 ? 1 : 0;
    const caminho = `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${grande} 1 ${x2} ${y2} Z`;
    ang = ang2;
    return { caminho, cor: CORES_GRAFICO[i % CORES_GRAFICO.length], fatia: f };
  });
  return (
    <div className="graf-card">
      <div className="graf-head"><strong>{titulo}</strong><span>{money(total)}</span></div>
      {!dados.length ? <div className="graf-vazio">Sem dados no período</div> : (
        <div className="graf-pizza-wrap">
          <svg viewBox="0 0 200 200" className="graf-svg" role="img" aria-label={titulo}>
            {partes.map((p) => <path key={p.fatia.rotulo} d={p.caminho} fill={p.cor} />)}
          </svg>
          <ul className="graf-legenda">
            {partes.map((p) => (
              <li key={p.fatia.rotulo}>
                <i style={{ background: p.cor }} />
                <span>{p.fatia.rotulo}</span>
                <b>{((p.fatia.valor / total) * 100).toFixed(1).replace(".", ",")}%</b>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function GraficoBarras({ pontos, titulo }: { pontos: { nome: string; quantidade: number }[]; titulo: string }) {
  const dados = pontos.slice(0, 10);
  const max = Math.max(...dados.map((d) => d.quantidade), 1);
  return (
    <div className="graf-card">
      <div className="graf-head"><strong>{titulo}</strong><span>{dados.length} itens</span></div>
      {!dados.length ? <div className="graf-vazio">Sem dados no período</div> : (
        <div className="graf-barras">
          {dados.map((d, i) => (
            <div key={d.nome} className="graf-barra-item" title={`${d.nome}: ${d.quantidade}`}>
              <div className="graf-barra" style={{ height: `${(d.quantidade / max) * 100}%`, background: CORES_GRAFICO[i % CORES_GRAFICO.length] }} />
              <small>{d.nome.length > 10 ? d.nome.slice(0, 9) + "…" : d.nome}</small>
              <b>{d.quantidade}</b>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

type RelConfig = {
  periodo: "diario" | "semanal" | "mensal" | "personalizado";
  data: string;
  inicio: string;
  fim: string;
  agrupar: "dia" | "hora";
  formas: string[];
  categorias: string[];
  produtos: string;
  graficoLinhas: boolean;
  graficoPizza: boolean;
  graficoBarras: boolean;
  campoLinhas: string;
  fatiaPizza: "forma" | "produto" | "categoria";
  paisagem: boolean;
};

const FORMAS = [
  { id: "dinheiro", label: "Dinheiro" },
  { id: "credito", label: "Crédito" },
  { id: "debito", label: "Débito" },
  { id: "pix", label: "PIX" },
];

function ReportsPage({ dados, config, setConfig, onAplicar, onGerarPdf, loading, gerando, erro, podeLimpar, notify, onLimpar }: {
  dados: RelatorioDados | null;
  config: RelConfig;
  setConfig: (c: RelConfig) => void;
  onAplicar: () => void;
  onGerarPdf: () => void;
  loading: boolean;
  gerando: boolean;
  erro: string | null;
  podeLimpar: boolean;
  notify: (m: string) => void;
  onLimpar: () => void;
}) {
  const [mostrarFiltros, setMostrarFiltros] = useState(false);
  const upd = <K extends keyof RelConfig>(k: K, v: RelConfig[K]) => setConfig({ ...config, [k]: v });
  const toggle = (lista: string[], v: string) => (lista.includes(v) ? lista.filter((x) => x !== v) : [...lista, v]);
  const categorias = [...new Set((dados?.por_categoria || []).map((c) => c.categoria))];
  const fatiasPizza = config.fatiaPizza === "produto"
    ? (dados?.por_produto || []).slice(0, 8).map((p) => ({ rotulo: p.nome, valor: p.total }))
    : config.fatiaPizza === "categoria"
      ? (dados?.por_categoria || []).map((c) => ({ rotulo: c.categoria, valor: c.total }))
      : (dados?.por_forma || []).map((f) => ({ rotulo: f.rotulo, valor: f.total }));

  return (
    <div className="page-content">
      <div className="rel-topo">
        <div className="rel-filtros-inline">
          <div className="report-options">
            {(["diario", "semanal", "mensal", "personalizado"] as const).map((p) => (
              <button key={p} onClick={() => upd("periodo", p)} style={config.periodo === p ? { background: "#e7f2ea", borderColor: "#9fc9ad", color: "#21613f" } : undefined}>
                {p === "diario" ? "Diário" : p === "semanal" ? "Semanal" : p === "mensal" ? "Mensal" : "Período"}
              </button>
            ))}
          </div>
          {config.periodo === "personalizado" && (
            <div className="rel-datas">
              <input type="date" value={config.inicio} onChange={(e) => upd("inicio", e.target.value)} aria-label="Data inicial" />
              <span>até</span>
              <input type="date" value={config.fim} onChange={(e) => upd("fim", e.target.value)} aria-label="Data final" />
            </div>
          )}
          <AppButton onClick={() => setMostrarFiltros((v) => !v)}>{mostrarFiltros ? "Ocultar filtros" : "Filtros e gráficos"}</AppButton>
          <AppButton variant="primary" onClick={onAplicar} disabled={loading}>{loading ? "Carregando…" : "Aplicar"}</AppButton>
          <AppButton variant="primary" onClick={onGerarPdf} disabled={gerando}>
            <Icon name="printer" /> {gerando ? "Gerando PDF…" : "Gerar relatório (PDF)"}
          </AppButton>
        </div>
      </div>

      {mostrarFiltros && (
        <section className="content-card rel-config-card">
          <div className="table-toolbar"><div><h2>Filtros e gráficos</h2><p>Escolha o que entra no relatório e como os gráficos são desenhados.</p></div></div>
          <div className="form-grid">
            <label className="field"><span>Agrupar por</span>
              <select value={config.agrupar} onChange={(e) => upd("agrupar", e.target.value as "dia" | "hora")}>
                <option value="dia">Por dia</option><option value="hora">Por hora</option>
              </select>
            </label>
            <label className="field"><span>Métrica do gráfico de linhas</span>
              <select value={config.campoLinhas} onChange={(e) => upd("campoLinhas", e.target.value)}>
                {Object.entries(rotuloCampo).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label className="field"><span>Fatias da pizza</span>
              <select value={config.fatiaPizza} onChange={(e) => upd("fatiaPizza", e.target.value as RelConfig["fatiaPizza"])}>
                <option value="forma">Por forma de pagamento</option>
                <option value="produto">Por produto</option>
                <option value="categoria">Por categoria</option>
              </select>
            </label>
            <label className="field"><span>Produto (contém)</span>
              <input value={config.produtos} onChange={(e) => upd("produtos", e.target.value)} placeholder="Ex.: BaseMax, Pão" />
            </label>
          </div>
          <div className="rel-chips">
            <span>Formas de pagamento:</span>
            {FORMAS.map((f) => (
              <button key={f.id} className={`chip ${config.formas.includes(f.id) ? "on" : ""}`} onClick={() => upd("formas", toggle(config.formas, f.id))}>{f.label}</button>
            ))}
            {categorias.map((c) => (
              <button key={c} className={`chip ${config.categorias.includes(c) ? "on" : ""}`} onClick={() => upd("categorias", toggle(config.categorias, c))}>{c}</button>
            ))}
            {config.formas.length > 0 && <button className="chip limpar" onClick={() => upd("formas", [])}>limpar formas</button>}
          </div>
          <div className="rel-toggles">
            <label className="toggle-row"><div><strong>Gráfico de linhas</strong><span>Curva de {rotuloCampo[config.campoLinhas].toLowerCase()}</span></div><input type="checkbox" checked={config.graficoLinhas} onChange={(e) => upd("graficoLinhas", e.target.checked)} /><i /></label>
            <label className="toggle-row"><div><strong>Gráfico de pizza</strong><span>{config.fatiaPizza === "forma" ? "Por forma de pagamento" : config.fatiaPizza === "produto" ? "Por produto" : "Por categoria"}</span></div><input type="checkbox" checked={config.graficoPizza} onChange={(e) => upd("graficoPizza", e.target.checked)} /><i /></label>
            <label className="toggle-row"><div><strong>Gráfico de barras</strong><span>Quantidade por produto</span></div><input type="checkbox" checked={config.graficoBarras} onChange={(e) => upd("graficoBarras", e.target.checked)} /><i /></label>
            <label className="toggle-row"><div><strong>Página em paisagem</strong><span>Mais espaço para gráficos e tabelas</span></div><input type="checkbox" checked={config.paisagem} onChange={(e) => upd("paisagem", e.target.checked)} /><i /></label>
          </div>
        </section>
      )}

      {erro && <div className="settings-notice" style={{ marginBottom: 12 }}><Icon name="alert" /><div><strong>Erro no relatório</strong><span>{erro}</span></div></div>}

      <div className="metrics">
        <div className="metric"><div className="metric-icon green"><Icon name="tag" /></div><div><span>Total vendido</span><strong>{dados ? money(dados.resumo.total) : "—"}</strong><small>{dados ? `${fmtData(dados.inicio)} a ${fmtData(dados.fim)}` : "sem dados"}</small></div></div>
        <div className="metric"><div className="metric-icon blue"><Icon name="bag" /></div><div><span>Vendas</span><strong>{dados ? dados.resumo.vendas : "—"}</strong><small>{dados ? `${dados.resumo.itens} itens` : ""}</small></div></div>
        <div className="metric"><div className="metric-icon purple"><Icon name="chart" /></div><div><span>Ticket médio</span><strong>{dados ? money(dados.resumo.ticket_medio) : "—"}</strong><small>por venda</small></div></div>
      </div>

      {dados && config.graficoLinhas && (
        <GraficoLinhas pontos={dados.serie} campo={config.campoLinhas}
          titulo={`${rotuloCampo[config.campoLinhas]} por ${config.agrupar === "hora" ? "hora" : "dia"}`} />
      )}
      {dados && config.graficoPizza && (
        <GraficoPizza fatias={fatiasPizza}
          titulo={config.fatiaPizza === "forma" ? "Participação por forma de pagamento" : config.fatiaPizza === "produto" ? "Participação por produto" : "Participação por categoria"} />
      )}
      {dados && config.graficoBarras && (
        <GraficoBarras pontos={dados.por_produto} titulo="Quantidade vendida por produto" />
      )}

      <section className="content-card">
        <div className="table-toolbar">
          <div><h2>Detalhamento</h2><p>Vendas por {config.agrupar === "hora" ? "hora" : "dia"} no período filtrado.</p></div>
        </div>
        <div className="product-table">
          <div className="table-row table-head"><span>Período</span><span>Vendas</span><span>Dinheiro</span><span>Crédito</span><span>Débito/PIX</span><span>Total</span></div>
          {(dados?.serie || []).map((d) => (
            <div className="table-row" key={d.rotulo}>
              <div className="table-product"><strong>{config.agrupar === "hora" ? `${d.rotulo}h` : fmtData(d.rotulo)}</strong></div>
              <span>{d.vendas}</span><span>{money(d.dinheiro)}</span><span>{money(d.credito)}</span>
              <span className="muted">Db {money(d.debito)} · Pix {money(d.pix)}</span>
              <strong>{money(d.total)}</strong>
            </div>
          ))}
          {dados && !dados.serie.length && <div className="search-no-result"><Icon name="chart" /><span>Nenhuma venda no período com esses filtros.</span></div>}
          {!dados && <div className="search-no-result"><Icon name="chart" /><span>{loading ? "Carregando…" : "Clique em Aplicar para carregar."}</span></div>}
        </div>
      </section>

      {dados && (dados.por_forma.length > 0 || dados.por_produto.length > 0) && (
        <div className="rel-duplo">
          <section className="content-card">
            <div className="table-toolbar"><div><h2>Por forma de pagamento</h2></div></div>
            <div className="product-table">
              {dados.por_forma.map((f) => (
                <div className="table-row" key={f.forma} style={{ gridTemplateColumns: "2fr 1fr 1fr" }}>
                  <div className="table-product"><strong>{f.rotulo}</strong></div>
                  <span>{f.vendas} venda(s)</span><strong>{money(f.total)}</strong>
                </div>
              ))}
              {!dados.por_forma.length && <div className="search-no-result"><Icon name="tag" /><span>Sem dados.</span></div>}
            </div>
          </section>
          <section className="content-card">
            <div className="table-toolbar"><div><h2>Produtos mais vendidos</h2></div></div>
            <div className="product-table">
              {dados.por_produto.slice(0, 10).map((p) => (
                <div className="table-row" key={p.nome} style={{ gridTemplateColumns: "2fr .8fr 1fr" }}>
                  <div className="table-product"><strong>{p.nome}</strong><small className="muted"> · {p.categoria || "sem categoria"}</small></div>
                  <span>{p.quantidade} un.</span><strong>{money(p.total)}</strong>
                </div>
              ))}
              {!dados.por_produto.length && <div className="search-no-result"><Icon name="bag" /><span>Sem dados.</span></div>}
            </div>
          </section>
        </div>
      )}

      {podeLimpar && <LimpezaVendas onDone={onLimpar} notify={notify} />}
    </div>
  );
}
function InventoryPage({ products, onAdd, onEdit, onDelete, podeEditar }: { products: Product[]; podeEditar: boolean; onAdd: () => void; onEdit: (product: Product) => void; onDelete: (id: number) => void }) {
  const [query, setQuery] = useState("");
  const [showValidade, setShowValidade] = useState(false);
  const visible = products.filter((item) => `${item.name} ${item.sku}`.toLowerCase().includes(query.toLowerCase()));
  const lowStock = products.filter((item) => item.stock <= 8).length;
  const comValidade = products
    .flatMap((p) => {
      const lotes = p.lotes.length ? p.lotes.map((l) => ({ validade: l.validade, quantidade: l.quantidade }))
        : p.validade ? [{ validade: p.validade, quantidade: p.stock }] : [];
      return lotes.map((l) => ({ p, validade: l.validade, qtd: l.quantidade, dias: diasPara(l.validade) }))
        .filter((x) => x.dias !== null);
    })
    .sort((a, b) => (a.dias as number) - (b.dias as number));
  const vencendo = comValidade.filter((x) => (x.dias as number) >= 0 && (x.dias as number) <= 15);
  const vencidos = comValidade.filter((x) => (x.dias as number) < 0);
  // alerta por data (não por período): agrupa quantidades por data de vencimento
  const porData = new Map<string, { qtd: number; dias: number }>();
  for (const x of [...vencidos, ...vencendo]) {
    const e = porData.get(x.validade) || { qtd: 0, dias: x.dias as number };
    e.qtd += x.qtd;
    porData.set(x.validade, e);
  }
  const datasAlerta = [...porData.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  return (
    <div className="page-content">
      {datasAlerta.length > 0 && (
        <div className="validade-alert">
          <div className="operation-icon amber"><Icon name="alert" /></div>
          <div>
            <strong>
              {datasAlerta.slice(0, 2).map(([data, e]) =>
                e.dias < 0 ? `🔴 ${e.qtd} un. vencidas em ${fmtData(data)}` : `🟠 ${e.qtd} un. em ${fmtData(data)} (${urgText(e.dias)})`).join(" · ")}
              {datasAlerta.length > 2 && ` · +${datasAlerta.length - 2} data(s)`}
            </strong>
            <span>Clique em ver mais para produtos e quantidades por data.</span>
          </div>
          <button onClick={() => setShowValidade((v) => !v)}>{showValidade ? "Ocultar" : "Ver mais"}</button>
        </div>
      )}
      {showValidade && (
        <section className="content-card" style={{ marginBottom: 18 }}>
          <div className="table-toolbar">
            <div><h2>Validades por lote</h2><p>Da maior para a menor urgência. Vendas baixam o lote mais próximo primeiro.</p></div>
          </div>
          <div className="product-table">
            <div className="table-row table-head"><span>Produto</span><span>Validade</span><span>Situação</span><span>Qtd. lote</span><span>Estoque</span><span></span></div>
            {comValidade.map(({ p, validade, qtd, dias }) => (
              <div className="table-row" key={`${p.id}-${validade}`}>
                <div className="table-product"><ProductGlyph category={p.category} color={p.color} /><strong>{p.name}</strong></div>
                <span>{fmtData(validade)}</span>
                <span><b className={`validade-badge ${urgClass(dias)}`}>{urgText(dias as number)}</b></span>
                <strong>{qtd} un.</strong>
                <span><b className={`stock-pill ${p.stock <= 8 ? "low" : ""}`}>{p.stock} un.</b></span>
                <div className="row-actions">{podeEditar && <button aria-label="Editar" title="Editar" onClick={() => onEdit(p)}><Icon name="edit" size={17} /></button>}</div>
              </div>
            ))}
            {!comValidade.length && <div className="search-no-result"><Icon name="check" /><span>Nenhum produto com validade definida.</span></div>}
          </div>
        </section>
      )}
      <div className="metrics">
        <div className="metric"><div className="metric-icon blue"><Icon name="box" /></div><div><span>Total de produtos</span><strong>{products.length}</strong><small>itens cadastrados</small></div></div>
        <div className="metric"><div className="metric-icon amber"><Icon name="alert" /></div><div><span>Estoque baixo</span><strong>{lowStock}</strong><small>requerem atenção</small></div></div>
        <div className="metric"><div className="metric-icon green"><Icon name="tag" /></div><div><span>Valor em estoque</span><strong>{money(products.reduce((sum, p) => sum + p.price * p.stock, 0))}</strong><small>preço de venda</small></div></div>
      </div>
      <section className="content-card">
        <div className="table-toolbar">
          <div><h2>Produtos</h2><p>Cadastre, edite e acompanhe o saldo disponível.</p></div>
          <div className="toolbar-actions"><label className="search-box compact"><Icon name="search" /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar produto" /></label>{podeEditar && <AppButton variant="primary" onClick={onAdd}><Icon name="plus" /> Novo produto</AppButton>}</div>
        </div>
        <div className="product-table">
          <div className="table-row table-head"><span>Produto</span><span>Categoria</span><span>Código</span><span>Preço</span><span>Estoque</span><span>Ações</span></div>
          {visible.map((product) => {
            const lotesOrd = [...product.lotes].sort((a, b) => a.validade.localeCompare(b.validade));
            const dv = lotesOrd.length ? diasPara(lotesOrd[0].validade) : diasPara(product.validade);
            const dataRef = lotesOrd.length ? lotesOrd[0].validade : product.validade;
            return (
            <div className="table-row" key={product.id}>
              <div className="table-product"><ProductGlyph category={product.category} color={product.color} /><strong>{product.name}</strong></div>
              <span><i className="category-dot" />{product.category}</span><span className="muted">#{product.sku}</span><strong>{money(product.price)}</strong>
              <span><b className={`stock-pill ${product.stock <= 8 ? "low" : ""}`}>{product.stock} un.</b>
                {dataRef
                  ? <><br /><b className={`validade-badge ${urgClass(dv)}`}>📅 {fmtData(dataRef)}{lotesOrd.length > 1 ? ` +${lotesOrd.length - 1}` : ""}</b></>
                  : <><br /><span className="muted" style={{ fontSize: 8 }}>validade indet.</span></>}
              </span>
              <div className="row-actions">{podeEditar && <><button aria-label="Editar" onClick={() => onEdit(product)}><Icon name="edit" size={17} /></button><button aria-label="Excluir" onClick={() => onDelete(product.id)}><Icon name="trash" size={17} /></button></>}</div>
            </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function SettingsPage({ settings, setSettings, fiscal, setFiscal, descCfg, setDescCfg, recibo, setRecibo, qrPreview, qrErro, onGerarQr, imprimirFiscal, setImprimirFiscal, imprimirNaoFiscal, setImprimirNaoFiscal, previewRecibo, carregandoPrevia, onAtualizarPrevia, testResults, testingProvider, onTest, onSave, notify, mockFile, printFile, generating, onGerarNota, onGerarCupom, onEncerrar }: {
  settings: SystemSettings;
  setSettings: React.Dispatch<React.SetStateAction<SystemSettings>>;
  fiscal: FiscalState;
  setFiscal: React.Dispatch<React.SetStateAction<FiscalState>>;
  descCfg: { tipo: string; valor: number };
  setDescCfg: React.Dispatch<React.SetStateAction<{ tipo: string; valor: number }>>;
  recibo: ReciboState;
  setRecibo: React.Dispatch<React.SetStateAction<ReciboState>>;
  qrPreview: { data_uri: string; biblioteca: string } | null;
  qrErro: string;
  onGerarQr: (link: string) => void;
  imprimirFiscal: boolean;
  setImprimirFiscal: (v: boolean) => void;
  imprimirNaoFiscal: boolean;
  setImprimirNaoFiscal: (v: boolean) => void;
  previewRecibo: string;
  carregandoPrevia: boolean;
  onAtualizarPrevia: () => void;
  testResults: Record<string, string>;
  testingProvider: string | null;
  onTest: (providerId: string) => void;
  onSave: () => void;
  notify: (message: string) => void;
  mockFile: { id_nota: string; arquivos: string[]; pdf: string; preview: string } | null;
  printFile: { arquivo: string; preview: string } | null;
  generating: string | null;
  onGerarNota: () => void;
  onGerarCupom: () => void;
  onEncerrar: () => void;
}) {
  const [section, setSection] = useState<"fiscal" | "recibo" | "printer" | "company" | "discount">("fiscal");
  const [confirmandoSaida, setConfirmandoSaida] = useState(false);
  // desconto: guarda só os dígitos digitados (centavos / pontos de %) para a máscara
  const [descDigitos, setDescDigitos] = useState("");
  useEffect(() => {
    setDescDigitos(descCfg.tipo === "valor" ? String(Math.round((descCfg.valor || 0) * 100)) : "");
  }, [descCfg.tipo]); // eslint-disable-line react-hooks/exhaustive-deps
  const digitos = (v: string) => v.replace(/\D/g, "").replace(/^0+(?=\d)/, "").slice(0, 9);
  const onDesc = (v: string) => {
    const d = digitos(v);
    setDescDigitos(d);
    setDescCfg((c) => ({ ...c, valor: c.tipo === "valor" ? Number(d || 0) / 100 : Number(d || 0) }));
  };
  const update = (key: string, value: string | boolean) => setSettings((current) => ({ ...current, [key]: value }));
  const updateFiscal = (key: keyof FiscalState, value: string) => setFiscal((current) => ({ ...current, [key]: value }));
  // ao abrir "Nota não fiscal", já mostra o modelo salvo no servidor
  useEffect(() => {
    if (section === "recibo") onAtualizarPrevia();
  }, [section]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="page-content settings-page">
      <div className="settings-nav">
        <span>Configurações</span>
        <button className={section === "fiscal" ? "active" : ""} onClick={() => setSection("fiscal")}><Icon name="receipt" />Nota fiscal<Icon name="chevron" size={16} /></button>
        <button className={section === "recibo" ? "active" : ""} onClick={() => setSection("recibo")}><Icon name="printer" />Nota não fiscal<Icon name="chevron" size={16} /></button>
        <button className={section === "printer" ? "active" : ""} onClick={() => setSection("printer")}><Icon name="printer" />Impressão<Icon name="chevron" size={16} /></button>
        <button className={section === "discount" ? "active" : ""} onClick={() => setSection("discount")}><Icon name="tag" />Descontos<Icon name="chevron" size={16} /></button>
        <button className={section === "company" ? "active" : ""} onClick={() => setSection("company")}><Icon name="store" />Dados da empresa<Icon name="chevron" size={16} /></button>
      </div>
      <div className="settings-content">
        {section === "fiscal" && <section className="content-card settings-card">
          <div className="section-heading"><div className="section-icon"><Icon name="receipt" /></div><div><h2>Nota fiscal</h2><p>Documento fiscal oficial (NFC-e/NF-e). Escolha o provedor que emite e teste cada API.</p></div><div className="status-badge"><i /> Serviço online</div></div>
          <div className="settings-notice"><Icon name="alert" /><div><strong>Provedor ativo: {PROVIDER_INFO.find((p) => p.id === fiscal.provider)?.label}</strong><span>Salve para trocar o emissor oficial. Teste cada API abaixo antes de oficializar.</span></div></div>
          <label className="toggle-row">
            <div><strong>Imprimir cupom fiscal</strong><span>Liga/desliga a impressão da NFC-e (documento fiscal)</span></div>
            <input type="checkbox" checked={imprimirFiscal} onChange={(e) => setImprimirFiscal(e.target.checked)} /><i />
          </label>
          {imprimirFiscal && <div className="settings-notice"><Icon name="check" /><div><strong>Cupom fiscal ATIVO</strong><span>Após cada venda o documento fiscal é aberto para impressão.</span></div></div>}
          <div className="form-grid">
            <label className="field"><span>Provedor ativo (oficial)</span><select value={fiscal.provider} onChange={(e) => updateFiscal("provider", e.target.value)}>{PROVIDER_INFO.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}</select></label>
            <label className="field"><span>Modelo de documento</span><select value={fiscal.modelo} onChange={(e) => updateFiscal("modelo", e.target.value)}><option>NFC-e</option><option>NF-e</option><option>SAT</option></select></label>
            <label className="field"><span>Ambiente de emissão</span><select value={fiscal.ambiente} onChange={(e) => updateFiscal("ambiente", e.target.value)}><option>Produção</option><option>Homologação</option></select></label>
            <label className="field"><span>Série da nota</span><input value={fiscal.serie} onChange={(e) => updateFiscal("serie", e.target.value)} /></label>
            <label className="field"><span>Próximo número</span><input value={fiscal.proximo} onChange={(e) => updateFiscal("proximo", e.target.value)} /></label>
            <label className="field"><span>Emitente (fantasia)</span><input value={settings.tradeName} onChange={(e) => update("tradeName", e.target.value)} /></label>
          </div>

          <div className="provider-grid">
            {/* 1 — Mock */}
            <div className={`provider-card ${fiscal.provider === "mock" ? "active" : ""}`}>
              <div className="provider-head"><span className="provider-num">1</span><div><strong>Mock Local</strong><small>{PROVIDER_INFO[0].desc}</small></div></div>
              <label className="field"><span>URL do mock</span><input value={fiscal.mock_url} onChange={(e) => updateFiscal("mock_url", e.target.value)} placeholder="http://localhost:3000" /></label>
              <div className="provider-actions">
                <AppButton onClick={() => onTest("mock")} disabled={testingProvider === "mock"}>{testingProvider === "mock" ? "Testando…" : "Testar"}</AppButton>
                <AppButton variant="primary" onClick={onGerarNota} disabled={generating === "mock-arquivo"}>{generating === "mock-arquivo" ? "Gerando…" : "Gerar nota"}</AppButton>
              </div>
              {testResults["mock"] && <span className="provider-result">{testResults["mock"]}</span>}
              {mockFile && <div className="provider-files">{mockFile.arquivos.map((a) => <a key={a} href={api.arquivoUrl("notas_teste", a)} target="_blank" rel="noreferrer">⬇ {a}</a>)}</div>}
              {mockFile && <div className="file-preview">{mockFile.preview}</div>}
            </div>

            {/* 2 — Nuvem Fiscal */}
            <div className={`provider-card ${fiscal.provider === "nuvem_fiscal" ? "active" : ""}`}>
              <div className="provider-head"><span className="provider-num">2</span><div><strong>Nuvem Fiscal</strong><small>{PROVIDER_INFO[1].desc}</small></div></div>
              <label className="field"><span>Token (Bearer)</span><input value={fiscal.nuvem_token} onChange={(e) => updateFiscal("nuvem_token", e.target.value)} type="password" placeholder="seu token" /></label>
              <label className="field"><span>Endpoint</span><input value={fiscal.nuvem_url} onChange={(e) => updateFiscal("nuvem_url", e.target.value)} /></label>
              <div className="provider-actions"><AppButton onClick={() => onTest("nuvem_fiscal")} disabled={testingProvider === "nuvem_fiscal"}>{testingProvider === "nuvem_fiscal" ? "Testando…" : "Testar"}</AppButton></div>
              {testResults["nuvem_fiscal"] && <span className="provider-result">{testResults["nuvem_fiscal"]}</span>}
            </div>

            {/* 3 — Focus NFe */}
            <div className={`provider-card ${fiscal.provider === "focus_nfe" ? "active" : ""}`}>
              <div className="provider-head"><span className="provider-num">3</span><div><strong>Focus NFe</strong><small>{PROVIDER_INFO[2].desc}</small></div></div>
              <label className="field"><span>Token (Basic)</span><input value={fiscal.focus_token} onChange={(e) => updateFiscal("focus_token", e.target.value)} type="password" placeholder="seu token" /></label>
              <label className="field"><span>Endpoint</span><input value={fiscal.focus_url} onChange={(e) => updateFiscal("focus_url", e.target.value)} /></label>
              <div className="provider-actions"><AppButton onClick={() => onTest("focus_nfe")} disabled={testingProvider === "focus_nfe"}>{testingProvider === "focus_nfe" ? "Testando…" : "Testar"}</AppButton></div>
              {testResults["focus_nfe"] && <span className="provider-result">{testResults["focus_nfe"]}</span>}
            </div>

            {/* 4 — SEFAZ direta */}
            <div className={`provider-card ${fiscal.provider === "sefaz_direta" ? "active" : ""}`}>
              <div className="provider-head"><span className="provider-num">4</span><div><strong>SEFAZ Direta (A1)</strong><small>{PROVIDER_INFO[3].desc}</small></div></div>
              <label className="field"><span>Certificado .pfx</span><input value={fiscal.sefaz_cert_path} onChange={(e) => updateFiscal("sefaz_cert_path", e.target.value)} placeholder="C:\certs\empresa.pfx" /></label>
              <div className="provider-actions"><AppButton onClick={() => onTest("sefaz_direta")} disabled={testingProvider === "sefaz_direta"}>{testingProvider === "sefaz_direta" ? "Testando…" : "Testar"}</AppButton></div>
              {testResults["sefaz_direta"] && <span className="provider-result">{testResults["sefaz_direta"]}</span>}
            </div>

            {/* 5 — Custom */}
            <div className={`provider-card ${fiscal.provider === "custom" ? "active" : ""}`}>
              <div className="provider-head"><span className="provider-num">5</span><div><strong>API Customizada</strong><small>{PROVIDER_INFO[4].desc}</small></div></div>
              <label className="field"><span>Token (opcional)</span><input value={fiscal.custom_token} onChange={(e) => updateFiscal("custom_token", e.target.value)} type="password" placeholder="opcional" /></label>
              <label className="field"><span>URL do endpoint</span><input value={fiscal.custom_url} onChange={(e) => updateFiscal("custom_url", e.target.value)} placeholder="https://sua-api/notas" /></label>
              <div className="provider-actions"><AppButton onClick={() => onTest("custom")} disabled={testingProvider === "custom"}>{testingProvider === "custom" ? "Testando…" : "Testar"}</AppButton></div>
              {testResults["custom"] && <span className="provider-result">{testResults["custom"]}</span>}
            </div>

            {/* Certificado (resumo) */}
            <div className="provider-card">
              <div className="provider-head"><span className="provider-num"><Icon name="check" size={13} /></span><div><strong>Certificado A1</strong><small>Emitente usado nas notas</small></div></div>
              <div className="certificate-field"><Icon name="check" /><div><strong>{fiscal.sefaz_cert_path ? "Certificado informado" : "Certificado A1 configurado"}</strong><small>{fiscal.sefaz_cert_path || "Válido até 18/11/2026"}</small></div><button type="button" onClick={() => notify("Selecione o arquivo .pfx no bloco SEFAZ Direta.")}>Trocar</button></div>
            </div>
          </div>
        </section>}

        {section === "recibo" && <section className="content-card settings-card">
          <div className="section-heading"><div className="section-icon purple"><Icon name="printer" /></div><div><h2>Nota não fiscal</h2><p>Comprovante de venda (recibo). Não substitui a nota fiscal — é o modelo impresso na térmica.</p></div><div className="status-badge"><i /> {recibo.largura} colunas</div></div>
          <div className="settings-notice"><Icon name="alert" /><div><strong>Modelo do comprovante</strong><span>O que estiver marcado abaixo é exatamente o que sai impresso. A prévia ao lado usa os dados salvos.</span></div></div>
          <label className="toggle-row">
            <div><strong>Imprimir cupom não fiscal</strong><span>Liga/desliga a impressão do comprovante de venda</span></div>
            <input type="checkbox" checked={imprimirNaoFiscal} onChange={(e) => setImprimirNaoFiscal(e.target.checked)} /><i />
          </label>
          {imprimirNaoFiscal && <div className="settings-notice"><Icon name="check" /><div><strong>Cupom não fiscal ATIVO</strong><span>Após cada venda o comprovante é aberto para impressão.</span></div></div>}
          <div className="printer-preview-layout">
            <div>
              <div className="form-grid">
                <label className="field full"><span>Título (cabeçalho)</span><input value={recibo.titulo} onChange={(e) => setRecibo({ ...recibo, titulo: e.target.value })} placeholder={settings.tradeName || "Ex.: Mercado do Zé"} /></label>
                <label className="field full"><span>Subtítulo</span><input value={recibo.subtitulo} onChange={(e) => setRecibo({ ...recibo, subtitulo: e.target.value })} placeholder="Cupom de venda - sem valor fiscal" /></label>
                <label className="field full"><span>Mensagem do rodapé</span><input value={recibo.rodape} onChange={(e) => setRecibo({ ...recibo, rodape: e.target.value })} placeholder="Obrigado pela preferência!" /></label>
                <label className="field"><span>Largura do papel</span><select value={recibo.largura} onChange={(e) => setRecibo({ ...recibo, largura: e.target.value as "32" | "48" })}><option value="48">80mm — 48 colunas</option><option value="32">58mm — 32 colunas</option></select></label>
                <label className="field"><span>Título quando vazio</span><input value={settings.tradeName} onChange={(e) => update("tradeName", e.target.value)} placeholder="Usa o nome fantasia" /></label>
              </div>
              <label className="toggle-row"><div><strong>Mostrar CNPJ e cidade</strong><span>Dados da empresa no cabeçalho</span></div><input type="checkbox" checked={recibo.mostrarCnpj} onChange={(e) => setRecibo({ ...recibo, mostrarCnpj: e.target.checked })} /><i /></label>
              <label className="toggle-row"><div><strong>Listar itens</strong><span>Produtos, quantidades e valores</span></div><input type="checkbox" checked={recibo.mostrarItens} onChange={(e) => setRecibo({ ...recibo, mostrarItens: e.target.checked })} /><i /></label>
              <label className="toggle-row"><div><strong>Mostrar pagamentos</strong><span>Forma de pagamento e troco</span></div><input type="checkbox" checked={recibo.mostrarPagamentos} onChange={(e) => setRecibo({ ...recibo, mostrarPagamentos: e.target.checked })} /><i /></label>
              <label className="toggle-row"><div><strong>Mostrar troco</strong><span>Só quando houver troco na venda</span></div><input type="checkbox" checked={recibo.mostrarTroco} onChange={(e) => setRecibo({ ...recibo, mostrarTroco: e.target.checked })} /><i /></label>
              <label className="toggle-row"><div><strong>Mostrar atendente</strong><span>Nome de quem registrou a venda</span></div><input type="checkbox" checked={recibo.mostrarAtendente} onChange={(e) => setRecibo({ ...recibo, mostrarAtendente: e.target.checked })} /><i /></label>
              <label className="toggle-row"><div><strong>Mostrar link da NFC-e</strong><span>QR Code da nota fiscal no comprovante</span></div><input type="checkbox" checked={recibo.mostrarQrcode} onChange={(e) => setRecibo({ ...recibo, mostrarQrcode: e.target.checked })} /><i /></label>
            </div>
            <div className="recibo-preview">
              <span>Modelo do comprovante</span>
              <pre>{previewRecibo}</pre>
              <div className="provider-actions">
                <AppButton onClick={onAtualizarPrevia} disabled={carregandoPrevia}>{carregandoPrevia ? "Atualizando…" : "Atualizar prévia"}</AppButton>
                <AppButton variant="primary" onClick={onGerarCupom} disabled={generating === "print-arquivo"}>{generating === "print-arquivo" ? "Gerando…" : "Gerar exemplo"}</AppButton>
              </div>
              {printFile && <div className="file-links"><a href={api.arquivoUrl("cupons", printFile.arquivo)} target="_blank" rel="noreferrer">⬇ {printFile.arquivo}</a></div>}
            </div>
          </div>

          {/* ---- QR Code fixo por link ---- */}
          <div className="qrcode-block">
            <div className="qrcode-form">
              <div className="section-heading"><div className="section-icon blue"><Icon name="receipt" /></div><div><h2>QR Code do comprovante</h2><p>Link fixo: o mesmo QR Code é impresso em todas as vendas.</p></div></div>
                            <label className="field full"><span>Link do QR Code</span><input value={recibo.qrcodeLink} onChange={(e) => setRecibo({ ...recibo, qrcodeLink: e.target.value })} onBlur={(e) => onGerarQr(e.target.value)} placeholder="https://minha-loja.com.br/consulta-venda" /></label>
              <div className="provider-actions"><AppButton onClick={() => onGerarQr(recibo.qrcodeLink)}>Gerar QR Code</AppButton></div>
              <label className="toggle-row"><div><strong>Imprimir QR Code</strong><span>Desligado = some o QR do comprovante</span></div><input type="checkbox" checked={recibo.mostrarQrcode} onChange={(e) => setRecibo({ ...recibo, mostrarQrcode: e.target.checked })} /><i /></label>
              {!recibo.qrcodeLink.trim() && <p className="provider-result">Informe um link começando com http:// ou https:// e clique em Gerar QR Code.</p>}
              {qrErro && <p className="provider-result erro">{qrErro}</p>}
            </div>
            <div className="qrcode-box">
              <span>Prévia do QR</span>
              {qrPreview
                ? <img src={qrPreview.data_uri} alt="QR Code do comprovante" />
                : <div className="qrcode-vazio">—</div>}
              <small>{recibo.qrcodeLink.trim() || "sem link"}</small>
              {qrPreview && <small>gerado com {qrPreview.biblioteca}</small>}
            </div>
          </div>

          {/* ---- tributos e trocas ---- */}
          <div className="form-grid" style={{ marginTop: 14 }}>
            <label className="field"><span>Tributos federais (%)</span><input inputMode="decimal" value={String(recibo.tributosFederal).replace(".", ",")} onChange={(e) => setRecibo({ ...recibo, tributosFederal: Math.min(100, Math.max(0, parseMoeda(e.target.value))) })} placeholder="Ex.: 0" /></label>
            <label className="field"><span>Tributos estaduais (%)</span><input inputMode="decimal" value={String(recibo.tributosEstadual).replace(".", ",")} onChange={(e) => setRecibo({ ...recibo, tributosEstadual: Math.min(100, Math.max(0, parseMoeda(e.target.value))) })} placeholder="Ex.: 0" /></label>
            <label className="field full"><span>Aviso de trocas</span><input value={recibo.avisoTrocas} onChange={(e) => setRecibo({ ...recibo, avisoTrocas: e.target.value })} placeholder="Eventuais trocas somente mediante notinha" /></label>
          </div>
          <label className="toggle-row"><div><strong>Mostrar tributos no comprovante</strong><span>Linha informativa com o percentual federal e estadual</span></div><input type="checkbox" checked={recibo.mostrarTributos} onChange={(e) => setRecibo({ ...recibo, mostrarTributos: e.target.checked })} /><i /></label>
          <label className="toggle-row"><div><strong>Mostrar aviso de trocas</strong><span>“Eventuais trocas somente mediante notinha”</span></div><input type="checkbox" checked={recibo.mostrarAvisoTrocas} onChange={(e) => setRecibo({ ...recibo, mostrarAvisoTrocas: e.target.checked })} /><i /></label>
          <div className="test-print"><Icon name="printer" /><div><strong>Como usar</strong><span>Salve as configurações para gravar o modelo. A impressão automática do comprovante é controlada em “Impressão”.</span></div><AppButton onClick={() => { onSave(); onAtualizarPrevia(); }}>Salvar modelo</AppButton></div>
        </section>}

        {section === "printer" && <section className="content-card settings-card">
          <div className="section-heading"><div className="section-icon purple"><Icon name="printer" /></div><div><h2>Impressão de documentos</h2><p>Configure a impressora térmica e o formato do cupom.</p></div><div className="status-badge"><i /> Conectada</div></div>
          <div className="printer-preview-layout">
            <div>
              <div className="form-grid printer-fields">
                <label className="field full"><span>Impressora padrão</span><select value={settings.printer} onChange={(e) => update("printer", e.target.value)}><option>Impressora térmica 80mm</option><option>Salvar como PDF</option><option>Impressora do sistema</option></select></label>
                <label className="field"><span>Largura do papel</span><select value={settings.paperSize} onChange={(e) => update("paperSize", e.target.value)}><option>80mm</option><option>58mm</option><option>A4</option></select></label>
                <label className="field"><span>Número de vias</span><select value={settings.copies} onChange={(e) => update("copies", e.target.value)}><option>1</option><option>2</option><option>3</option></select></label>
              </div>
              <label className="toggle-row"><div><strong>Impressão automática</strong><span>Imprimir ao concluir a venda</span></div><input type="checkbox" checked={settings.autoPrint} onChange={(e) => update("autoPrint", e.target.checked)} /><i /></label>
              <label className="toggle-row"><div><strong>Exibir logotipo</strong><span>Mostrar a marca no cabeçalho do cupom</span></div><input type="checkbox" checked={settings.printLogo} onChange={(e) => update("printLogo", e.target.checked)} /><i /></label>
              <label className="toggle-row"><div><strong>Corte automático</strong><span>Acionar guilhotina após impressão</span></div><input type="checkbox" checked={settings.cutPaper} onChange={(e) => update("cutPaper", e.target.checked)} /><i /></label>
            </div>
            <div className="receipt-preview"><span>Prévia do cupom</span><div><strong>LUMINA</strong><small>{settings.company}<br />CNPJ {settings.cnpj}</small><i /><b>CUPOM FISCAL</b><p>1x Café Premium <em>{money(24.9)}</em><br />1x Leite Integral <em>{money(6.49)}</em></p><i /><h3>TOTAL <b>{money(31.39)}</b></h3><small>Obrigado pela preferência</small></div></div>
          </div>
          <div className="test-print"><Icon name="printer" /><div><strong>Teste de impressão</strong><span>Gera o cupom em data/cupons/ até a impressora chegar.</span></div><AppButton onClick={onGerarCupom} disabled={generating === "print-arquivo"}>{generating === "print-arquivo" ? "Gerando…" : "Gerar cupom teste"}</AppButton></div>
          {printFile && <div className="file-links"><a href={api.arquivoUrl("cupons", printFile.arquivo)} target="_blank" rel="noreferrer">⬇ {printFile.arquivo}</a></div>}
          {printFile && <div className="file-preview">{printFile.preview}</div>}
        </section>}

        {section === "discount" && <section className="content-card settings-card">
          <div className="section-heading"><div className="section-icon"><Icon name="tag" /></div><div><h2>Desconto automático</h2><p>Aplicado sozinho em cada venda. F3 liga/desliga no caixa.</p></div><div className="status-badge"><i /> {descCfg.tipo === "nenhum" ? "Desligado" : "Ativo"}</div></div>
          <div className="settings-notice"><Icon name="alert" /><div><strong>Como funciona</strong><span>Percentual desconta % do subtotal. Valor fixo desconta R$ do subtotal (limitado a ele). O operador alterna com F3.</span></div></div>
          <div className="form-grid">
            <label className="field"><span>Tipo de desconto</span>
              <select value={descCfg.tipo} onChange={(e) => setDescCfg((d) => ({ ...d, tipo: e.target.value }))}>
                <option value="nenhum">Desligado (nenhum)</option>
                <option value="percentual">Percentual (%)</option>
                <option value="valor">Valor fixo (R$)</option>
              </select>
            </label>
            <label className="field"><span>{descCfg.tipo === "valor" ? "Valor do desconto" : "Percentual do desconto"}</span>
              {descCfg.tipo === "valor"
                ? <CampoMoeda value={maskMoeda(descDigitos)} onChange={(e) => onDesc(e.target.value)} placeholder={EX_MOEDA} />
                : <div className="money-input"><input inputMode="decimal" value={descDigitos} onChange={(e) => onDesc(e.target.value)} placeholder={EX_PCT} disabled={descCfg.tipo === "nenhum"} /><b>%</b></div>}
            </label>
          </div>
          <div className="test-print"><Icon name="tag" /><div><strong>Prévia</strong><span>{descCfg.tipo === "nenhum" ? "Sem desconto automático." : descCfg.tipo === "valor" ? `${money(Number(descCfg.valor))} por venda.` : `${fmtPercent(Number(descCfg.valor))} por venda.`}</span></div><AppButton onClick={() => notify("Salve as configurações para ativar.")}>Salvar abaixo</AppButton></div>
        </section>}

        {section === "company" && <section className="content-card settings-card">
          <div className="section-heading"><div className="section-icon"><Icon name="store" /></div><div><h2>Dados da empresa</h2><p>Informações exibidas nos documentos fiscais e relatórios.</p></div><div className="status-badge"><i /> Cadastro ativo</div></div>
          <div className="company-brand-block"><div className="company-logo"><Icon name="store" size={28} /></div><div><strong>Logotipo da empresa</strong><span>PNG ou JPG, recomendado 400 × 400</span></div><AppButton>Alterar logotipo</AppButton></div>
          <div className="form-grid">
            <label className="field"><span>Razão social</span><input value={settings.company} onChange={(e) => update("company", e.target.value)} /></label>
            <label className="field"><span>Nome fantasia</span><input value={settings.tradeName} onChange={(e) => update("tradeName", e.target.value)} /></label>
            <label className="field"><span>CNPJ</span><input value={settings.cnpj} onChange={(e) => update("cnpj", e.target.value)} /></label>
            <label className="field"><span>Inscrição estadual</span><input value={settings.stateRegistration} onChange={(e) => update("stateRegistration", e.target.value)} /></label>
            <label className="field"><span>E-mail</span><input value={settings.email} onChange={(e) => update("email", e.target.value)} /></label>
            <label className="field"><span>Telefone</span><input value={settings.phone} onChange={(e) => update("phone", e.target.value)} /></label>
            <label className="field full"><span>Endereço</span><input value={settings.address} onChange={(e) => update("address", e.target.value)} /></label>
            <label className="field"><span>Cidade / Estado</span><input value={settings.city} onChange={(e) => update("city", e.target.value)} /></label>
            <label className="field"><span>CEP</span><input value={settings.zip} onChange={(e) => update("zip", e.target.value)} /></label>
          </div>
        </section>}
        <div className="settings-actions"><span>Alterações sincronizadas com o servidor</span><AppButton variant="primary" onClick={onSave}><Icon name="check" /> Salvar configurações</AppButton></div>
        <section className="content-card settings-card">
          <div className="section-heading"><div className="section-icon"><Icon name="power" /></div><div><h2>Encerrar o sistema</h2><p>Fecha o PDV Lumina neste computador. Nenhum dado é apagado.</p></div></div>
          <div className="settings-notice"><Icon name="alert" /><div><strong>Antes de encerrar</strong><span>Feche o caixa do dia. Ao reabrir, o sistema volta exatamente como está.</span></div><AppButton onClick={() => setConfirmandoSaida(true)}>Encerrar agora</AppButton></div>
        </section>
      </div>

      {confirmandoSaida && (
        <div className="modal-overlay" onClick={() => setConfirmandoSaida(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 430 }}>
            <div className="modal-head"><h3>Encerrar o PDV Lumina?</h3><button onClick={() => setConfirmandoSaida(false)} aria-label="Fechar"><Icon name="close" /></button></div>
            <div className="modal-body" style={{ display: "grid", gap: 10 }}>
              <p style={{ margin: 0, color: "#5e6962", fontSize: 13, lineHeight: 1.6 }}>A tela vai fechar e o sistema para de responder. Para abrir de novo, é só clicar duas vezes no ícone do PDV Lumina na área de trabalho.</p>
              <div className="setup-dica"><Icon name="check" size={16} /><div>Vendas, produtos e configurações continuam salvos.</div></div>
            </div>
            <div className="form-actions full"><AppButton type="button" onClick={() => setConfirmandoSaida(false)}>Cancelar</AppButton><AppButton variant="primary" type="button" onClick={onEncerrar}><Icon name="power" /> Encerrar</AppButton></div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
