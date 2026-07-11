"""Builds the actual GSTN GSTR-1 JSON schema (the format the government's
offline utility / GSP APIs accept) from our internal report data.

Pure functions only -- no DB, no network -- so the schema shape itself is
directly unit-testable. Only the two sections a retail POS realistically
populates are built: "hsn" (Table 12, HSN-wise summary) and "b2cs" (Table
7, B2C small -- i.e. supplies to unregistered consumers, which is nearly
all POS retail; B2B invoice-wise reporting (Table 4) would need customer
GSTIN capture at checkout, which this system supports on the Customer
record but doesn't yet split out into per-invoice B2B GSTR-1 rows -- see
ROADMAP.md).
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


def build_gstr1_json(
    gstin: str,
    return_period: str,
    gross_turnover: float,
    hsn_lines: list[HSNSummaryLine],
    b2cs_lines: list[B2CSLine],
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
    }
