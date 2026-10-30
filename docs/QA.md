# QA / kiểm thử

Chạy:

```bash
python mega_checker.py self-test
python -m unittest discover -s tests -v
```

Bộ test bao gồm cú pháp email, IDNA, gợi ý typo, che email, nhận diện disposable, lưu/đọc SQLite, thống kê, job resume và export. Các test mặc định chạy offline; không gửi truy vấn ra Internet.

Các kiểm tra thủ công trước khi phát hành:
- Android/Termux với Python đang hỗ trợ.
- Có dnspython và không có dnspython.
- Mất mạng giữa batch; chạy lại đúng job ID.
- Backup database và mở bản sao.
- Kiểm tra CSV trên Excel/Google Sheets.
- Xác nhận không có API key/email đầy đủ trong log.
