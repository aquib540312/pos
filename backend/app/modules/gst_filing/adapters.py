"""GST Suvidha Provider (GSP) adapter -- e-files GSTR-1 on the government's
GSTN backend on our behalf (no business goes to GSTN directly; a licensed
GSP like ClearTax, Cygnet, MasterGST, or Taxaj sits in between).

Every GSP follows the same broad shape even though exact endpoints/auth
differ: authenticate, submit a JSON payload matching GSTN's published
GSTR-1 schema, get back a reference/ARN, poll for filed/rejected status.
`HttpGSPAdapter` implements that generic shape against a configurable
base_url + api_key; `MockGSPAdapter` is the default so the entire filing
workflow (generate -> submit -> poll -> filed) is fully exercisable
end-to-end today, without a real GSP contract.

Switching to a real provider is a config change (POS_GSP_PROVIDER=http,
POS_GSP_BASE_URL, POS_GSP_API_KEY) plus, in practice, adjusting the two
endpoint paths below to match that specific GSP's API docs -- everything
that calls this adapter (GSTFilingService) stays the same either way.
"""

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings


@dataclass(frozen=True)
class GSPSubmitResult:
    gsp_reference: str
    status: str  # submitted|filed|rejected


class GSPAdapter(Protocol):
    def submit_gstr1(self, gstin: str, return_period: str, payload: dict) -> GSPSubmitResult: ...
    def get_status(self, gsp_reference: str) -> str: ...


class MockGSPAdapter:
    """Deterministic fake GSP: submitting always "succeeds" with a
    reproducible reference, and status always reports "filed" -- lets the
    whole generate/submit/status workflow be built, tested, and demoed
    without a real GSP account."""

    def submit_gstr1(self, gstin: str, return_period: str, payload: dict) -> GSPSubmitResult:
        reference = f"MOCKGSP-{gstin}-{return_period}"
        return GSPSubmitResult(gsp_reference=reference, status="filed")

    def get_status(self, gsp_reference: str) -> str:
        return "filed"


class HttpGSPAdapter:
    """Generic REST GSP client. The two endpoint paths and auth header are
    the part you'll adjust to match your actual GSP's API documentation --
    the request/response shape here follows the common pattern (API-key
    auth, JSON submit, string status poll) most GSPs use."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def submit_gstr1(self, gstin: str, return_period: str, payload: dict) -> GSPSubmitResult:
        response = httpx.post(
            f"{self.base_url}/gstr1/submit",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"gstin": gstin, "return_period": return_period, "payload": payload},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return GSPSubmitResult(gsp_reference=data["reference"], status=data.get("status", "submitted"))

    def get_status(self, gsp_reference: str) -> str:
        response = httpx.get(
            f"{self.base_url}/gstr1/status/{gsp_reference}",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()["status"]


def get_gsp_adapter(settings: Settings) -> GSPAdapter:
    if settings.gsp_provider == "http":
        return HttpGSPAdapter(settings.gsp_base_url, settings.gsp_api_key)
    return MockGSPAdapter()
