# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
<<<<<<< Updated upstream
| 1 | <<>> | <<>> | <<>> | <<>> | <<>> |
=======
<<<<<<< Updated upstream
| 1 | Vũ Duy Thế | Claude Code (Claude Opus 5.5) | "Viết validator cho tôi": AI đọc GUIDE/DELIVERY/RULES rồi viết `validator/validate.py` (9 lỗi luật + `--candidates` đối chiếu box ↔ pixel mask) | Luật `instance_merge` quá lỏng: ra 280 ứng viên trên seed 7007 và 86 trên lô sạch (cặp box cùng lớp chồng nhau tự nhiên) | Chạy trên lô sạch `--no-faults`, siết điều kiện (không box nào chứa ≥80% segment, 2 box giữ segment ít chồng nhau) → lô sạch 0 ứng viên, seed 7007 còn 6. Lỗi luật F1 ≈ 1.0 trên seed 7007 và 123 (`score_findings.py`), lô sạch 0 lỗi luật |
| 2 | Vũ Duy Thế | Claude Code (Claude Opus 5.5) | Soạn prompt để AI viết `REPORT.md`: bắt chạy lệnh lấy số thật, cấm đọc `_private`, cuối cùng lập bảng "số liệu → nguồn" | Chưa dùng prompt này để viết REPORT | Đối chiếu từng số trong REPORT với output lệnh/file trước khi commit |
=======
| 1 | Nhóm 7 | Codex | Cho biết pha 1 cần làm gì và thực hiện pha này. | Ban đầu định thay validator sẵn có. Đã khôi phục mã gốc để giữ chức năng tạo ứng viên của pha 2. Lần chạy đầu trên Windows ghi được JSON nhưng gặp lỗi mã hóa khi in tiếng Việt. | Codex chạy lại với UTF-8, kiểm tra hai seed bằng `score_findings.py` và kiểm tra số cảnh báo trên lô sạch. |
| 2 | Nhóm 7 | Codex | Thực hiện pha 1 và lưu riêng lỗi luật của seed 7007 vào `rules.json`. | Chưa phát hiện lỗi trong các lượt kiểm tra. | Codex kiểm tra các trường hợp box sát biên, box trùng, cảnh lẫn tập và đường dẫn ra ngoài delivery, rồi chạy validator trên hai seed và lô sạch. |
| 3 | Nhóm 7 | Codex | Ghi việc dùng AI theo RULES.md và chuẩn bị để mỗi thành viên giải thích một đoạn validator khi vấn đáp. | Chưa phát hiện sai sót khi đối chiếu phần giải thích với mã nguồn. | Codex đối chiếu các đoạn giải thích với validator. Nhóm sẽ tự chạy lại validator và đối chiếu từng phần khi ôn vấn đáp. |

Các lượt chạy của Codex được ghi riêng trong bảng. Khi thành viên tự kiểm tra, bổ sung tên người kiểm, ca thử thực tế và kết quả vào dòng tương ứng.
>>>>>>> Stashed changes
>>>>>>> Stashed changes
