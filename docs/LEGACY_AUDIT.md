# Rà soát mã cũ (mega_checker.py)

Các vấn đề được xác nhận khi kiểm tra snapshot cũ:

1. Engine mạng truyền `verify=False`, vô hiệu hóa xác minh TLS.
2. Ghi nhận nhiều lỗi `requests.sessions.Session.request() got multiple values for keyword argument 'allow_redirects'`.
3. Hunter.io kiểm tra và menu API key dùng chung nhầm `HIBP_API_KEY` thay vì khóa riêng.
4. Có nhánh `if False:` khiến guard validation bị vô hiệu hóa.
5. Batch sử dụng `ProcessPoolExecutor` cho phần lớn tác vụ I/O mạng, gây overhead không cần thiết.
6. Nhiều checker dựa trên luồng password-reset/login để suy luận email có đăng ký dịch vụ hay không. Cách này không đáng tin, có thể rò thông tin tài khoản và không được đưa vào bản mới.
7. Có lỗi cache lưu dictionary nhưng code đòi bytes.
8. Lỗi mạng và timeout từng dễ bị trình bày giống trạng thái không tìm thấy.

Bản 9 không mang các checker dò tài khoản cũ sang. Nó chuyển trọng tâm sang kiểm tra email/domain minh bạch, an toàn và có thể kiểm chứng.
