# NPT Local Password Lab 1.0.0 — APK độc lập

Ứng dụng Android native Java nằm trong `android/offline-password-lab/`, có package độc lập `vn.nptduy.localpasswordlab`. **Không phải MEGA Checker**; không thay đổi package hay dữ liệu MEGA.

## Tính năng chạy thật

- Tối đa **1.000.000 lượt duyệt tổ hợp ngoại tuyến** theo bảng ký tự tùy chỉnh, gồm chữ thường, chữ hoa, chữ số và Unicode được người dùng cung cấp.
- Chạy 2 chế độ: **Đo đúng 1.000.000 lượt** và **So khớp chuỗi mẫu do chính người dùng nhập**. Không cần mạng, tài khoản, mã khóa hay database.
- Hiển thị số lượt đã thực hiện, tốc độ thực đo trên CPU thiết bị, thời gian, kích thước bảng ký tự và kết quả so khớp mẫu.
- Nút **Dừng phép thử**, giới hạn 1 triệu lượt và 32 ký tự; chạy trên worker tránh chặn UI.
- Chuỗi mẫu được nhập ẩn, không tự động lưu, không xuất báo cáo, bị xóa khi hoàn thành so khớp hoặc ứng dụng về nền; chống chụp màn hình ứng dụng.
- Manifest không khai báo quyền `INTERNET`, `GET_ACCOUNTS`, `READ_CONTACTS`, Accessibility hay SMS.

**Không thể lấy hoặc xác minh mật khẩu Gmail khi chỉ có địa chỉ Gmail.** Đây không phải công cụ đăng nhập Google, không tìm được mật khẩu Gmail thật nếu không có nguồn kiểm chứng. Chỉ so sánh tổ hợp với một chuỗi mẫu do chính bạn thiết lập; không nên nhập mật khẩu Gmail thật để thử.

## Cấu trúc và kiểm thử

- `app/src/main/java/vn/nptduy/localpasswordlab/CandidateEngine.java`: engine Java thuần, giới hạn cứng 1 triệu lượt.
- `app/src/main/java/vn/nptduy/localpasswordlab/MainActivity.java`: giao diện Android riêng, nền tảng offline.
- `ci/EngineSelfTest.java`: kiểm thử engine không cần Android.
- `ci/device_test.py`: kiểm tra APK trên Android 14 emulator bằng UI tự động.
- `.github/workflows/local-password-lab.yml`: build, ký, xác minh quyền/manifest, kiểm thử Android và phát hành APK trên `main`.

## Xây dựng

```bash
gradle -p android/offline-password-lab --no-daemon :app:assembleRelease
```

APK được ký và kiểm tra trong GitHub Actions. Vào trang Releases của kho để tải `NPT-Local-Password-Lab.apk`. Nếu không cấu hình keystore riêng, mỗi lần build có chứng thư ký riêng và có thể cần gỡ phiên bản cũ khi nâng cấp. Không đưa mật khẩu hay khóa thật lên repository.
