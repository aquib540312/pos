"""Builds the actual GSTN GSTR-1 JSON schema (the format the government's
offline utility / GSP APIs accept) from our internal report data.

Pure functions only -- no DB, no network -- so the schema shape itself is
directly unit-testable. Three sections are built: "hsn" (Table 12,
HSN-wise summary, across all sales), "b2cs" (Table 7, B2C small --
unregistered-consumer sales only) and "b2b" (Table 4, invoice-wise, one
entry per registered buyer GSTIN grouped by ctin then invoice then rate).
Which section an invoice falls into is decided once, at posting time, by
whether `SalesInvoice.customer_gstin` was captured (see
app/models/sales.py) -- never re-derived from the live Customer record,
since a customer's GSTIN can change after a past invoice was filed.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HSNSummaryLine:
    hsn_code: str
    tax_rate_percent: float
    taxable_value: float
    cgst: float
    sgst: float
    igst: float
    cess: float
    invoice_count: int


@dataclass(frozen=True)
class B2CSLine:
    place_of_supply_state_code: str
    is_inter_state: bool
    tax_rate_percent: float
    taxable_value: float
    cgst: float
    sgst: float
    igst: float
    cess: float


@dataclass(frozen=True)
class B2BInvoiceRateItem:
    tax_rate_percent: float
    taxable_value: float
    cgst: float
    sgst: float
    igst: float
    cess: float


@dataclass(frozen=True)
class B2BInvoiceLine:
    buyer_gstin: str
    invoice_number: str
    invoice_date: str  # dd-mm-yyyy, GSTN's expected format
    invoice_value: float
    place_of_supply_state_code: str
    is_inter_state: bool
    rate_items: list[B2BInvoiceRateItem]


def build_gstr1_json(
    gstin: str,
    return_period: str,
    gross_turnover: float,
    hsn_lines: list[HSNSummaryLine],
    b2cs_lines: list[B2CSLine],
    b2b_lines: list[B2BInvoiceLine] | None = None,
) -> dict:
    return {
        "gstin": gstin,
        "fp": return_period,
        "gt": round(gross_turnover, 2),
        "cur_gt": round(gross_turnover, 2),
        "hsn": {
            "data": [
                {
                    "num": i + 1,
                    "hsn_sc": line.hsn_code,
                    "uqc": "OTH",
                    "qty": 0,
                    "val": round(line.taxable_value + line.cgst + line.sgst + line.igst + line.cess, 2),
                    "txval": round(line.taxable_value, 2),
                    "iamt": round(line.igst, 2),
                    "camt": round(line.cgst, 2),
                    "samt": round(line.sgst, 2),
                    "csamt": round(line.cess, 2),
                }
                for i, line in enumerate(hsn_lines)
            ]
        },
        "b2cs": [
            {
                "sply_ty": "INTER" if line.is_inter_state else "INTRA",
                "pos": line.place_of_supply_state_code,
                "typ": "OE",
                "txval": round(line.taxable_value, 2),
                "rt": line.tax_rate_percent,
                "iamt": round(line.igst, 2),
                "camt": round(line.cgst, 2),
                "samt": round(line.sgst, 2),
                "csamt": round(line.cess, 2),
            }
            for line in b2cs_lines
        ],
        "b2b": _build_b2b_section(b2b_lines or []),
    }


def _build_b2b_section(b2b_lines: list[B2BInvoiceLine]) -> list[dict]:
    by_ctin: dict[str, list[B2BInvoiceLine]] = {}
    for line in b2b_lines:
        by_ctin.setdefault(line.buyer_gstin, []).append(line)

    return [
        {
            "ctin": ctin,
            "inv": [
                {
                    "inum": line.invoice_number,
                    "idt": line.invoice_date,
                    "val": round(line.invoice_value, 2),
                    "pos": line.place_of_supply_state_code,
                    "rchrg": "N",
                    "inv_typ": "R",
                    "itms": [
                        {
                            "num": i + 1,
                            "itm_det": {
                                "txval": round(item.taxable_value, 2),
                                "rt": item.tax_rate_percent,
                                "iamt": round(item.igst, 2),
                                "camt": round(item.cgst, 2),
                                "samt": round(item.sgst, 2),
                                "csamt": round(item.cess, 2),
                            },
                        }
                        for i, item in enumerate(line.rate_items)
                    ],
                }
                for line in invoices
            ],
        }
        for ctin, invoices in by_ctin.items()
    ]
