# Khắc phục sự cố Termux

### `No module named dns`
```bash
python -m pip install dnspython
```
Hoặc dùng chương trình ở chế độ thiếu DNS (các mục DNS sẽ là `dependency_missing`).

### Lệnh `python` không nhận
```bash
pkg install python -y
python --version
```

### Resume
Phải dùng lại đúng `--job-id` cũ:
```bash
python mega_checker.py scan -i emails.txt --job-id cong-viec-01 --resume
```
Không dùng ID mới nếu muốn nối tiếp tiến độ.

### Database bị lỗi/đầy dung lượng
Đóng tiến trình Mega Checker trước khi sao chép DB. Dùng:
```bash
python mega_checker.py backup
```
Không xóa file `-wal` khi chương trình đang chạy.
