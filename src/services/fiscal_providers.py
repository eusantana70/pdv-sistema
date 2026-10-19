"""Provedores fiscais separados — um por API, para testar e depois manter só o oficial.

Cada provider implementa:
    emitir(payload, cfg) -> (status, link, xml)
    testar(cfg) -> (ok, mensagem)

Providers:
- MockLocalProvider ...... http://localhost:3000/v1/notas (mock-sefaz/, ideal p/ dev)
- NuvemFiscalProvider .... api.nuvemfiscal.com.br (Bearer token)
- FocusNFeProvider ....... api.focusnfe.com.br (Basic token)
- SefazDiretaProvider .... certificado A1 (placeholder seguro: não transmite sem cert)
- CustomProvider ......... URL genérica do cliente (Bearer token)

O provider ativo é escolhido em configuracoes.fiscal_provider.
"""

from __future__ import annotations

from typing import Callable


def _post_json(url: str, body: dict, headers: dict, timeout: int = 20,
               post: Callable | None = None):
    import requests
    fn = post or requests.post
    return fn(url, json=body, headers=headers, timeout=timeout)


class MockLocalProvider:
    name = "mock"
    label = "Mock Local (teste)"

    def endpoint(self, cfg: dict) -> str:
        base = (cfg.get("mock_url") or "http://localhost:3000").rstrip("/")
        return f"{base}/v1/notas"

    def emitir(self, payload: dict, cfg: dict, post=None):
        url = self.endpoint(cfg)
        try:
            resp = _post_json(url, payload, {}, post=post)
            data = {}
            try:
                data = resp.json()
            except Exception:
                data = {}
            if 200 <= getattr(resp, "status_code", 0) < 300:
                link = str(data.get("link") or data.get("pdf_danfe") or "")
                xml = str(data.get("xml") or "")
                return ("autorizado", link, xml)
            return ("erro", "", str(data)[:800])
        except Exception as e:
            return ("erro", "", f"Mock inalcançável em {url}: {e}"[:800])

    def testar(self, cfg: dict, post=None):
        import requests
        base = (cfg.get("mock_url") or "http://localhost:3000").rstrip("/")
        fn = post or requests.get
        try:
            r = fn(f"{base}/health", timeout=8)
            if getattr(r, "status_code", 0) == 200:
                return (True, f"Mock OK em {base}.")
            return (False, f"Mock respondeu HTTP {getattr(r, 'status_code', '?')}.")
        except Exception as e:
            return (False, f"Mock inalcançável em {base}: {e}")


class NuvemFiscalProvider:
    name = "nuvem_fiscal"
    label = "Nuvem Fiscal"

    def endpoint(self, cfg: dict) -> str:
        return (cfg.get("nuvem_url") or "https://api.nuvemfiscal.com.br/nfce").rstrip("/")

    def emitir(self, payload: dict, cfg: dict, post=None):
        token = (cfg.get("nuvem_token") or "").strip()
        if not token:
            return ("pendente", "", "Token Nuvem Fiscal não configurado.")
        url = self.endpoint(cfg)
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = _post_json(url, payload, headers, post=post)
            data = {}
            try:
                data = resp.json()
            except Exception:
                data = {}
            if 200 <= getattr(resp, "status_code", 0) < 300:
                link = str(data.get("link") or data.get("pdf") or data.get("url") or "")
                xml = str(data.get("xml") or "")
                return ("autorizado", link, xml)
            return ("erro", "", str(data.get("message") or data.get("error") or data)[:800])
        except Exception as e:
            return ("erro", "", str(e)[:800])

    def testar(self, cfg: dict, post=None):
        token = (cfg.get("nuvem_token") or "").strip()
        if not token:
            return (False, "Informe o token da Nuvem Fiscal.")
        # teste leve: não emite, só valida presença + formato da URL
        url = self.endpoint(cfg)
        if not url.startswith("https://"):
            return (False, f"URL Nuvem deve ser https: {url}")
        return (True, f"Config Nuvem OK ({url}). Emissão real só no checkout.")


class FocusNFeProvider:
    name = "focus_nfe"
    label = "Focus NFe"

    def endpoint(self, cfg: dict) -> str:
        return (cfg.get("focus_url") or "https://api.focusnfe.com.br/v2/nfce").rstrip("/")

    def emitir(self, payload: dict, cfg: dict, post=None):
        import base64
        token = (cfg.get("focus_token") or "").strip()
        if not token:
            return ("pendente", "", "Token Focus NFe não configurado.")
        url = self.endpoint(cfg)
        basic = base64.b64encode(f"{token}:".encode()).decode()
        headers = {"Authorization": f"Basic {basic}"}
        try:
            resp = _post_json(url, payload, headers, post=post)
            data = {}
            try:
                data = resp.json()
            except Exception:
                data = {}
            if 200 <= getattr(resp, "status_code", 0) < 300:
                link = str(data.get("link") or data.get("caminho_danfe") or "")
                xml = str(data.get("xml") or data.get("caminho_xml") or "")
                return ("autorizado", link, xml)
            return ("erro", "", str(data)[:800])
        except Exception as e:
            return ("erro", "", str(e)[:800])

    def testar(self, cfg: dict, post=None):
        token = (cfg.get("focus_token") or "").strip()
        if not token:
            return (False, "Informe o token da Focus NFe.")
        return (True, f"Config Focus OK ({self.endpoint(cfg)}). Emissão real só no checkout.")


class SefazDiretaProvider:
    name = "sefaz_direta"
    label = "SEFAZ Direta (certificado A1)"

    def emitir(self, payload: dict, cfg: dict, post=None):
        cert = (cfg.get("sefaz_cert_path") or "").strip()
        if not cert:
            return ("pendente", "", "Certificado A1 não configurado (aba Fiscal).")
        # Transmissão SOAP/MTLS real entra aqui na fase oficial.
        return ("pendente", "",
                "SEFAZ direta preparada, mas transmissão SOAP ainda não ativa nesta build.")

    def testar(self, cfg: dict, post=None):
        from pathlib import Path
        cert = (cfg.get("sefaz_cert_path") or "").strip()
        if not cert:
            return (False, "Informe o caminho do certificado A1 (.pfx).")
        if not Path(cert).exists():
            return (False, f"Arquivo não encontrado: {cert}")
        return (True, "Certificado localizado. Transmissão será ativada na homologação.")


class CustomProvider:
    name = "custom"
    label = "API Customizada (URL própria)"

    def endpoint(self, cfg: dict) -> str:
        # compat: usa custom_url ou cai para api_nfce_url legada
        return ((cfg.get("custom_url") or cfg.get("api_nfce_url") or "").strip())

    def emitir(self, payload: dict, cfg: dict, post=None):
        url = self.endpoint(cfg)
        if not url:
            return ("pendente", "", "URL customizada não configurada.")
        token = (cfg.get("custom_token") or cfg.get("api_nfce_token") or "").strip()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            resp = _post_json(url, payload, headers, post=post)
            data = {}
            try:
                data = resp.json()
            except Exception:
                data = {}
            if 200 <= getattr(resp, "status_code", 0) < 300:
                link = str(data.get("link") or data.get("pdf") or data.get("url")
                           or data.get("cupom") or data.get("qr") or "")
                xml = str(data.get("xml") or "")
                return ("autorizado", link, xml)
            return ("erro", "", str(data)[:800])
        except Exception as e:
            return ("erro", "", str(e)[:800])

    def testar(self, cfg: dict, post=None):
        url = self.endpoint(cfg)
        if not url:
            return (False, "Informe a URL da API customizada.")
        return (True, f"URL configurada ({url}). Teste real acontece na emissão.")


PROVIDERS = {
    "mock": MockLocalProvider(),
    "nuvem_fiscal": NuvemFiscalProvider(),
    "focus_nfe": FocusNFeProvider(),
    "sefaz_direta": SefazDiretaProvider(),
    "custom": CustomProvider(),
}

PROVIDER_CHOICES = [
    {"id": "mock", "label": "Mock Local (teste)"},
    {"id": "nuvem_fiscal", "label": "Nuvem Fiscal"},
    {"id": "focus_nfe", "label": "Focus NFe"},
    {"id": "sefaz_direta", "label": "SEFAZ Direta (certificado A1)"},
    {"id": "custom", "label": "API Customizada (URL própria)"},
]


def get_provider(provider_id: str):
    return PROVIDERS.get(provider_id or "mock", PROVIDERS["mock"])


def emitir_com_provider(provider_id: str, payload: dict, cfg: dict, post=None):
    return get_provider(provider_id).emitir(payload, cfg, post=post)


def testar_provider(provider_id: str, cfg: dict, post=None):
    return get_provider(provider_id).testar(cfg, post=post)
