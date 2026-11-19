# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | Vũ Duy Thế | Claude Code (Claude Opus 5.5) | "Viết validator cho tôi": AI đọc GUIDE/DELIVERY/RULES rồi viết `validator/validate.py` (9 lỗi luật + `--candidates` đối chiếu box ↔ pixel mask) | Luật `instance_merge` quá lỏng: ra 280 ứng viên trên seed 7007 và 86 trên lô sạch (cặp box cùng lớp chồng nhau tự nhiên) | Chạy trên lô sạch `--no-faults`, siết điều kiện (không box nào chứa ≥80% segment, 2 box giữ segment ít chồng nhau) → lô sạch 0 ứng viên, seed 7007 còn 6. Lỗi luật F1 ≈ 1.0 trên seed 7007 và 123 (`score_findings.py`), lô sạch 0 lỗi luật |
| 2 | Vũ Duy Thế | Claude Code (Claude Opus 5.5) | Soạn prompt để AI viết `REPORT.md`: bắt chạy lệnh lấy số thật, cấm đọc `_private`, cuối cùng lập bảng "số liệu → nguồn" | Chưa dùng prompt này để viết REPORT | Đối chiếu từng số trong REPORT với output lệnh/file trước khi commit |
