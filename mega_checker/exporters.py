from __future__ import annotations
import html
from pathlib import Path
from .models import EmailResult

def export_html(results: list[EmailResult], path: Path) -> None:
    rows = []
    for r in results:
        rows.append(
            "<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in (
                r.masked_email, r.syntax_status, r.domain, r.mx_status,
                r.spf_status, r.dmarc_status, r.dkim_status,
                "Yes" if r.disposable else "No", r.hibp_status
            )) + "</tr>"
        )
    document = """<!doctype html><html lang="vi"><meta charset="utf-8">
<title>Mega Checker Report</title><style>
body{font:14px system-ui;margin:24px;color:#172033}h1{font-size:24px}
table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:8px;text-align:left}
th{background:#f1f4f8}tr:nth-child(even){background:#fafafa}
</style><h1>MEGA CHECKER ULTIMATE — Báo cáo</h1>
<p>Email được che bớt để giảm lộ dữ liệu.</p><table><thead><tr>
<th>Email</th><th>Cú pháp</th><th>Domain</th><th>MX</th><th>SPF</th>
<th>DMARC</th><th>DKIM</th><th>Email tạm</th><th>HIBP</th>
</tr></thead><tbody>""" + "".join(rows) + "</tbody></table></html>"
    Path(path).write_text(document, encoding="utf-8")
