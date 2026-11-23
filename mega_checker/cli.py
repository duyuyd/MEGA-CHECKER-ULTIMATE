from __future__ import annotations
import argparse
import getpass
import json
import os
import sys
import uuid
from pathlib import Path
from . import APP_NAME, __version__
from .config import BASE_DIR, load_config, setup_logging
from .dnsintel import DomainInspector, DKIM_SELECTORS, DKIM_PROVIDER_SELECTORS, dkim_selectors_for_domain
from .dkim import (parse_dkim_signature_headers, read_header_file, read_clipboard_header_text,
                   read_email_message_file, verify_dkim_message, lookup_dkim_signatures,
                   normalize_selector)
from .validation import normalize_domain
from .hibp import HIBPError, check_breached_email, check_password_k_anonymity
from .password_lab import DEFAULT_RATE, run_password_lab
from .pipeline import check_one, read_emails, run_batch
from .storage import Store
from .validation import load_disposable_domains
from .exporters import export_html


def _print_result(result) -> None:
    d = result.to_dict()
    print(f"\n{d['masked_email']}  [{d['syntax_status'].upper()}]")
    print(f"Domain: {d['domain'] or '(không hợp lệ)'} | Loại: {d['domain_type']}")
    if d["registrable_domain"]:
        print(f"Public suffix: {d['public_suffix']} | Registrable domain: {d['registrable_domain']}")
    if d["typo_suggestion"]:
        print(f"Gợi ý: {d['typo_suggestion']}")
    print(f"Email tạm (danh sách cục bộ): {'CÓ' if d['disposable'] else 'không thấy'}")
    print(f"DNS resolver: {d.get('dns_provider') or 'unknown'}")
    print(f"MX: {d['mx_status']} {', '.join(d['mx_hosts'])}")
    print(f"SPF: {d['spf_status']} | DMARC: {d['dmarc_status']} | DKIM: {d['dkim_status']}")
    print(f"HIBP: {d['hibp_status']}")
    for warning in d["warnings"]:
        print(f"CẢNH BÁO: {warning}")
    for error in d["errors"]:
        print(f"LỖI: {error}")
    print(f"Thời gian: {d['duration_ms']} ms")


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mega-checker", description=APP_NAME)
    parser.add_argument("--config", default=str(BASE_DIR / "config.json"), help="Tệp cấu hình JSON")
    parser.add_argument("--db", default=None, help="Ghi đè đường dẫn SQLite database")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("self-test", help="Chạy bộ tự kiểm tra ngoại tuyến")

    audit = sub.add_parser("audit-dataset", help="Phân tích file email/credential ngoại tuyến; không thử đăng nhập")
    audit.add_argument("-i", "--input", required=True, help="Tệp văn bản đầu vào")
    audit.add_argument("--format", choices=("auto", "email", "combo"), default="auto", help="Định dạng dữ liệu (mặc định: auto)")
    audit.add_argument("--json", help="Lưu báo cáo tổng hợp JSON; không chứa mật khẩu")
    audit.add_argument("--max-line-bytes", type=int, default=65536, help="Giới hạn độ dài dòng: 1024–1048576")
    audit.add_argument("--access-mode", choices=("auto", "noroot", "root"), default="auto",
                       help="Quyền đọc dữ liệu: auto (No-Root trước, ROOT fallback khi bị chặn), noroot hoặc root")
    audit.add_argument("--root-input", action="store_true", help=argparse.SUPPRESS)  # legacy alias
    root_audit = sub.add_parser("root-audit", help="Kiểm tra quyền ROOT, SELinux, CPU/RAM và nhiệt độ Android (chỉ đọc)")
    root_audit.add_argument("--json", help="Lưu báo cáo thiết bị JSON")
    dkim = sub.add_parser("dkim", help="Tra DKIM từ tệp email, clipboard hoặc selector")
    dkim_source = dkim.add_mutually_exclusive_group(required=False)
    dkim_source.add_argument("--headers-file", help="Tệp .eml hoặc header DKIM-Signature (xử lý cục bộ)")
    dkim_source.add_argument("--clipboard", action="store_true", help="Đọc header đang sao chép bằng Termux:API")
    dkim_source.add_argument("--domain", help="Signing domain từ thẻ d= trong DKIM-Signature")
    dkim.add_argument("--selector", action="append", default=[], help="Selector từ thẻ s=; có thể lặp lại")
    dkim.add_argument("--probe-common", action="store_true", help="Thử một nhóm selector phổ biến; chỉ là heuristic, không toàn diện")
    dkim.add_argument("--verify", action="store_true", help="Xác minh chữ ký DKIM mật mã trên toàn bộ tệp .eml (cần dkimpy)")
    one = sub.add_parser("single", help="Kiểm tra một email/domain")
    one.add_argument("email")

    batch = sub.add_parser("scan", help="Quét danh sách email từ file")
    batch.add_argument("-i", "--input", required=True)
    batch.add_argument("-w", "--workers", type=int, default=None)
    batch.add_argument("--job-id", default="")
    batch.add_argument("--resume", action="store_true")
    batch.add_argument("--csv")
    batch.add_argument("--json")
    batch.add_argument("--html")
    batch.add_argument("--hibp", action="store_true",
                       help="Tra cứu HIBP; cần API key và quyền phù hợp")
    batch.add_argument("--confirm-authorized", action="store_true")

    exp = sub.add_parser("export", help="Xuất dữ liệu đã lưu")
    exp.add_argument("--csv")
    exp.add_argument("--json")
    exp.add_argument("--html")
    exp.add_argument("--limit", type=int, default=100000)

    sub.add_parser("stats", help="Thống kê database")
    sub.add_parser("backup", help="Sao lưu database")
    sub.add_parser("password-audit", help="Kiểm tra mật khẩu bằng HIBP k-anonymity")
    lab = sub.add_parser("password-lab", help="Phân tích mật khẩu nhập ẩn trên thiết bị",
                         description="Mặc định nhập mật khẩu ẩn và phân tích ngay trên máy.")
    source = lab.add_mutually_exclusive_group()
    source.add_argument("--length", type=int, help="Độ dài muốn tính, dùng cùng --alphabet-size")
    source.add_argument("--prompt", action="store_true", help="Nhập ẩn mật khẩu ngay trên máy")
    lab.add_argument("--alphabet-size", type=int, help="Số ký tự có thể chọn ở mỗi vị trí")
    lab.add_argument("--rate", type=int, default=DEFAULT_RATE,
                     help=f"Tốc độ mô hình theo lượt/giây (mặc định {DEFAULT_RATE})")
    sub.add_parser("config-check", help="Kiểm tra và hiển thị cấu hình đang dùng")
    sub.add_parser("menu", help="Mở menu tương tác")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _self_test() -> int:
    from .validation import validate_email, mask_email, normalize_domain
    tests = [
        ("good", validate_email("person@example.com").syntax_status == "valid"),
        ("missing_at", validate_email("person.example.com").syntax_status == "invalid"),
        ("double_at", validate_email("a@@example.com").syntax_status == "invalid"),
        ("empty_local", validate_email("@example.com").syntax_status == "invalid"),
        ("double_dot", validate_email("a..b@example.com").syntax_status == "invalid"),
        ("bad_domain_label", validate_email("a@-bad.example").syntax_status == "invalid"),
        ("typo", validate_email("a@gmial.com").typo_suggestion == "a@gmail.com"),
        ("mask", mask_email("someone@example.com") == "s*****e@example.com"),
        ("idna", normalize_domain("münich.example") == "xn--mnich-kva.example"),
    ]
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "test.db")
        sample = validate_email("person@example.com")
        sample.checked_at = "2026-01-01T00:00:00+00:00"
        store.save_result(sample)
        tests.append(("sqlite_roundtrip", store.get_result("person@example.com").syntax_status == "valid"))
        store.start_job("qa", "unit", ["one@example.com"])
        tests.append(("job_pending", store.pending_for_job("qa") == ["one@example.com"]))
        store.job_done("qa", "one@example.com")
        tests.append(("job_resume", store.pending_for_job("qa") == []))
        store.close()
    passed = sum(ok for _, ok in tests)
    for name, ok in tests:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\nSELF-TEST: {passed}/{len(tests)}")
    return 0 if passed == len(tests) else 1


def _scan_hibp(results, authorised: bool) -> None:
    if not authorised:
        raise HIBPError("Thiếu --confirm-authorized. Chỉ tra cứu email bạn sở hữu hoặc được phép kiểm toán.")
    if not os.environ.get("HIBP_API_KEY"):
        raise HIBPError("Chưa đặt biến môi trường HIBP_API_KEY.")
    for result in results:
        if result.syntax_status != "valid":
            continue
        try:
            data = check_breached_email(result.normalized_email)
            result.hibp_status = data["status"]
            result.hibp_breaches = data.get("breaches", [])
        except HIBPError as exc:
            result.hibp_status = "error"
            result.errors.append(str(exc))


def interactive_menu(config: dict | None = None, *, config_path: Path | None = None) -> int:
    print(f"\n{APP_NAME} v{__version__}")
    print("1. Kiểm tra một email")
    print("2. Quét danh sách email từ file")
    print("3. Thống kê database")
    print("4. Xuất CSV")
    print("5. Sao lưu database")
    print("6. Tính số tổ hợp theo độ dài và bảng ký tự")
    print("7. Phân tích mật khẩu nhập ẩn trên máy")
    print("0. Thoát")
    choice = input("Chọn: ").strip()
    if choice == "7":
        return run_password_lab(prompt=True)
    if choice == "6":
        try:
            length = int(input("Độ dài mật khẩu: "))
            alphabet = int(input("Số ký tự có thể chọn ở mỗi vị trí: "))
        except (EOFError, ValueError):
            print("Hãy nhập độ dài và cỡ bảng bằng số nguyên.", file=sys.stderr)
            return 2
        return run_password_lab(length=length, alphabet_size=alphabet)
    if choice == "0":
        return 0
    if choice not in {"1", "2", "3", "4", "5"}:
        print("Lựa chọn không hợp lệ.")
        return 2
    if config is None:
        try:
            config = load_config(config_path)
        except ValueError as exc:
            print(f"Cấu hình lỗi: {exc}", file=sys.stderr)
            return 2
        setup_logging(config)
    db_file = Path(config["database"])
    data_file = Path(config["disposable_domains_file"])
    backup_dir = Path(config["backup_directory"])
    if choice == "1":
        result = check_one(input("Email: ").strip(), DomainInspector(config["dns_timeout_seconds"]),
                           load_disposable_domains(data_file))
        _print_result(result)
        store = Store(db_file)
        try:
            store.save_result(result)
        finally:
            store.close()
    elif choice == "2":
        path = Path(input("Đường dẫn file: ").strip()).expanduser()
        if not path.is_file():
            print("Không tìm thấy file.")
            return 2
        store = Store(db_file)
        try:
            _, summary = run_batch(read_emails(path), store, config["workers"],
                                   job_id=uuid.uuid4().hex[:10], disposable_file=data_file,
                                   dns_timeout=config["dns_timeout_seconds"])
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        finally:
            store.close()
    elif choice == "3":
        store = Store(db_file)
        try:
            print(json.dumps(store.stats(), ensure_ascii=False, indent=2))
        finally:
            store.close()
    elif choice == "4":
        store = Store(db_file)
        try:
            print(f"Đã xuất {store.export_csv(Path('mega_results.csv'))} dòng.")
        finally:
            store.close()
    elif choice == "5":
        store = Store(db_file)
        try:
            print(f"Backup: {store.backup(backup_dir)}")
        finally:
            store.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _make_parser()
    args = parser.parse_args(argv)
    if args.command == "password-lab":
        return run_password_lab(length=args.length, alphabet_size=args.alphabet_size,
                                rate=args.rate, prompt=args.prompt)
    if args.command in (None, "menu"):
        return interactive_menu(config_path=Path(args.config))
    try:
        config = load_config(Path(args.config))
    except ValueError as exc:
        print(f"Cấu hình lỗi: {exc}", file=sys.stderr)
        return 2
    logger = setup_logging(config)
    db_file = Path(args.db).expanduser() if args.db else Path(config["database"])
    data_file = Path(config["disposable_domains_file"])

    if args.command == "self-test":
        return _self_test()
    if args.command == "root-audit":
        from .root_access import root_status, write_root_report, RootAccessError
        try:
            report = root_status()
            if args.json:
                target = write_root_report(report, args.json)
                print(f"ROOT report: {target}")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            # Lack of ROOT is a valid diagnostic outcome; No-Root remains supported.
            return 0
        except RootAccessError as exc:
            print(f"ROOT audit error: {exc}", file=sys.stderr)
            return 2
    if args.command == "audit-dataset":
        from .dataset_audit import audit_dataset, write_report
        from .root_access import open_dataset_input, RootAccessError
        try:
            selected_access = "root" if args.root_input else args.access_mode
            with open_dataset_input(args.input, selected_access) as (source_stream, actual_access):
                report = audit_dataset(Path(args.input), mode=args.format,
                                       max_line_bytes=args.max_line_bytes,
                                       input_stream=source_stream, access_mode=actual_access)
            if args.json:
                target = write_report(report, Path(args.json), source_path=Path(args.input))
                print(f"Báo cáo JSON: {target}")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        except (OSError, ValueError, RootAccessError) as exc:
            print(f"Dataset audit error: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
    if args.command == "config-check":
        safe = dict(config)
        safe["hibp_api_key"] = "Đọc từ biến môi trường HIBP_API_KEY, không lưu trong config"
        print(json.dumps(safe, ensure_ascii=False, indent=2))
        return 0
    if args.command == "dkim":
        try:
            if not any((args.headers_file, args.clipboard, args.domain)):
                print("DKIM: chọn một nguồn đầu vào.")
                print("  Tra DNS:        python mega_checker.py dkim --headers-file ~/storage/downloads/original.eml")
                print("  Xác minh thật:  python mega_checker.py dkim --verify --headers-file ~/storage/downloads/original.eml")
                print("  Clipboard:      python mega_checker.py dkim --clipboard")
                print("  Dò gợi ý:       python mega_checker.py dkim --domain gmail.com --probe-common")
                print("  Selector biết:  python mega_checker.py dkim --domain example.com --selector selector1")
                return 2

            if args.verify:
                if not args.headers_file or args.clipboard or args.domain or args.selector or args.probe_common:
                    print("--verify yêu cầu duy nhất --headers-file trỏ tới tệp .eml nguyên bản.", file=sys.stderr)
                    return 2
                raw_message = read_email_message_file(args.headers_file)
                result = verify_dkim_message(raw_message, DomainInspector(config["dns_timeout_seconds"]))
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0 if result.get("overall_status") == "pass" else 1

            if args.headers_file or args.clipboard:
                if args.selector or args.probe_common:
                    print("Không kết hợp --selector/--probe-common với --headers-file/--clipboard.", file=sys.stderr)
                    return 2
                raw_headers = (
                    read_header_file(args.headers_file)
                    if args.headers_file else read_clipboard_header_text()
                )
                signatures = parse_dkim_signature_headers(raw_headers)
                if not signatures:
                    print(json.dumps({
                        "dkim_status": "unknown",
                        "reason": "no_valid_dkim_signature_header",
                        "message": "Không tìm thấy DKIM-Signature hợp lệ có đủ d= và s=.",
                        "next_step": "Dùng tệp Original/.eml có đầy đủ header, không chỉ phần nội dung email."
                    }, ensure_ascii=False, indent=2))
                    return 2
            else:
                domain = normalize_domain(args.domain)
                if not domain:
                    print("Domain không hợp lệ. Ví dụ: --domain gmail.com", file=sys.stderr)
                    return 2
                selectors = [normalize_selector(item) for item in args.selector]
                selectors = list(dict.fromkeys(item for item in selectors if item))
                if args.probe_common:
                    for item in dkim_selectors_for_domain(domain):
                        if item not in selectors:
                            selectors.append(item)
                if not selectors:
                    print("Bạn chưa cung cấp selector. Lấy giá trị s= từ header DKIM-Signature, hoặc dùng --probe-common để thử một nhóm gợi ý.", file=sys.stderr)
                    print("Ví dụ: python mega_checker.py dkim --domain gmail.com --probe-common", file=sys.stderr)
                    print("Cách chính xác hơn: python mega_checker.py dkim --headers-file ~/storage/downloads/original.eml", file=sys.stderr)
                    return 2
                signatures = [{
                    "domain": domain, "selector": item,
                    "source": (
                        "gmail-provider-observed-hint" if args.probe_common
                        and domain in DKIM_PROVIDER_SELECTORS
                        and item in DKIM_PROVIDER_SELECTORS[domain]
                        and item not in [normalize_selector(x) for x in args.selector]
                        else "common-selector-heuristic" if args.probe_common
                        and item in DKIM_SELECTORS
                        and item not in [normalize_selector(x) for x in args.selector]
                        else "manual"
                    )
                } for item in selectors]

            result = lookup_dkim_signatures(DomainInspector(config["dns_timeout_seconds"]), signatures)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("dkim_status") in {"present", "revoked"} else 1
        except (OSError, ValueError) as exc:
            print(f"DKIM input error: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        except RuntimeError as exc:
            print(f"DKIM verifier error: {exc}", file=sys.stderr)
            return 2

    if args.command == "password-audit":
        password = getpass.getpass("Nhập mật khẩu (không lưu/không ghi log): ")
        if not password:
            print("Không có mật khẩu.")
            return 2
        try:
            print(json.dumps(check_password_k_anonymity(password), ensure_ascii=False, indent=2))
            return 0
        except HIBPError as exc:
            logger.warning("Password audit failed (%s)", type(exc).__name__)
            print(f"Lỗi: {exc}", file=sys.stderr)
            return 1

    if args.command == "single":
        result = check_one(args.email, DomainInspector(config["dns_timeout_seconds"]),
                           load_disposable_domains(data_file))
        _print_result(result)
        store = Store(db_file)
        try:
            store.save_result(result)
        finally:
            store.close()
        logger.info("Single email check completed (syntax=%s)", result.syntax_status)
        return 0 if result.syntax_status == "valid" else 2

    store = Store(db_file)
    try:
        if args.command == "scan":
            source = Path(args.input).expanduser()
            if not source.is_file():
                parser.error(f"Không tìm thấy input: {source}")
            emails = read_emails(source)
            if not emails:
                print("Không có email hợp lệ để xử lý.")
                return 2
            job_id = args.job_id or uuid.uuid4().hex[:12]
            worker_count = args.workers if args.workers is not None else config["workers"]
            results, summary = run_batch(emails, store, worker_count, job_id,
                                         args.resume, data_file, config["dns_timeout_seconds"])
            if args.hibp:
                try:
                    _scan_hibp(results, args.confirm_authorized)
                    for result in results:
                        store.save_result(result)
                except HIBPError as exc:
                    logger.warning("HIBP lookup stopped (%s)", type(exc).__name__)
                    print(f"HIBP: {exc}", file=sys.stderr)
            if args.csv:
                store.export_csv(Path(args.csv).expanduser())
            if args.json:
                store.export_json(Path(args.json).expanduser())
            if args.html:
                export_html(store.list_results(), Path(args.html).expanduser())
            logger.info("Batch completed: processed=%d errors=%d", summary["processed_now"], summary["errors"])
            print(json.dumps({"job_id": job_id, **summary}, ensure_ascii=False, indent=2))
            print(f"Đã lưu database: {db_file.resolve()}")
            return 0
        if args.command == "export":
            if not any((args.csv, args.json, args.html)):
                parser.error("Cần ít nhất một trong --csv, --json hoặc --html.")
            if args.csv:
                print(f"CSV: {store.export_csv(Path(args.csv).expanduser(), args.limit)} dòng")
            if args.json:
                print(f"JSON: {store.export_json(Path(args.json).expanduser(), args.limit)} dòng")
            if args.html:
                export_html(store.list_results(args.limit), Path(args.html).expanduser())
                print(f"HTML: {args.html}")
            return 0
        if args.command == "stats":
            print(json.dumps(store.stats(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "backup":
            print(f"Đã sao lưu: {store.backup(Path(config['backup_directory']))}")
            return 0
        parser.print_help()
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
