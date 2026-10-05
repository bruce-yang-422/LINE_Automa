# LINE OA 服務：Webhook、管理後台與 SQLite

本資料夾是 LINE 自動化平台的 Python 服務。操作與安裝見[根目錄 README](../README.md)；功能規格見 [docs/](../docs/README.md)。

```text
LINE OA → https://<PUBLIC_BASE_URL>/webhook/<OA 識別碼>
        → Cloudflare Tunnel → http://127.0.0.1:18474（app.py：Webhook、公開圖片、健康檢查）
管理後台 → https://<ADMIN_PUBLIC_HOST>
        → Cloudflare Tunnel → http://127.0.0.1:18475（admin_server.py）
資料 → data/line_archive.db（SQLite）
```

## 模組

| 檔案 | 內容 |
| --- | --- |
| `control_runtime.py` | 控制台啟動入口；讀取 `.env` 的部署設定（`DATABASE_PATH`、`PUBLIC_BASE_URL`、`ADMIN_PUBLIC_HOST`） |
| `app.py` | Webhook 接收（每個 OA 一個網址，以該 OA 的 Channel secret 驗證簽章與 destination）、公開圖片、建表 |
| `admin_server.py` | 管理 API、發送與排程執行、首次設定 |
| `site_auth.py` | 站內帳號密碼、Session、一次性設定連結 |
| `channels.py` | LINE OA 登記（憑證加密）、共用與移轉、OA 範圍 |
| `reports.py` | 組織、帳號、成員資格、權限與操作紀錄 |
| `recipients.py`、`chat.py`、`chat_notes.py`、`cases.py`、`template_packs.py`、`composer.py` | 聯絡對象、聊天、記事本、案件、範本包、訊息編輯 |
| `limits.py` | 所有數量上限的唯一定義處 |
| `create_admin.py` | 無桌面主機的平台管理員建立與緊急復原（互動式，不接受密碼參數） |

## 資料庫

- `schema.sql` 是唯一的資料結構來源；`app.initialize_database()` 僅在全新建庫時執行此檔並寫入 `PRAGMA user_version = 2`；同版重啟不重建、不補欄位、不搬移舊資料。其他版本必須先備份並重置。
- 第七階段以前的舊版資料庫沒有結構版本，服務會拒絕啟動並提示先備份、重建。
- 所有營運資料都帶 OA 範圍（`channel_id`）；組織 ID 欄位一律為 `organization_id`。
- OA 憑證以 `instance/line-credentials.key` 加密保存。**請連同資料庫一起備份金鑰檔**，遺失就無法解密已保存的憑證，只能在網頁重新輸入。
- 資料庫放在本機磁碟，啟用 WAL；執行中會有 `.db-wal`、`.db-shm`，不要只複製 `.db` 當作備份。以 SQLite 備份 API 建立一致的備份：

```powershell
python -c "import app, sqlite3; from datetime import datetime; from pathlib import Path; dest=Path('backups'); dest.mkdir(exist_ok=True); target=dest / (datetime.now().strftime('%Y%m%d_%H%M%S') + '.db'); source=sqlite3.connect(app.DATABASE_PATH); backup=sqlite3.connect(target); source.backup(backup); backup.close(); source.close(); print(target)"
```

## 接收範圍

- 記錄使用者與 OA 的一對一對話，以及 OA 已加入的群組、多人聊天室的新訊息；不包含其他使用者之間的私人聊天或過去的聊天紀錄。
- 同一 OA 內相同訊息 ID 不重複寫入；不同 OA 各自保存。收回訊息時清除文字並保留收回標記。
- 資料庫錯誤回傳 HTTP 503，供 LINE 重新傳送。
- 請告知對話參與者，並依需求訂定資料保留與存取規則。

## 直接執行（不經控制台）

```powershell
cd D:\Tools\LINE_Automation\line-oa-archive
..\.venv\Scripts\python.exe control_runtime.py --check      # 檢查環境、PUBLIC_BASE_URL 與是否已有啟用中的 OA
curl.exe http://127.0.0.1:18474/healthz                      # 服務啟動後回傳 ok
```

日常請使用桌面控制台啟停服務；`control_runtime.py` 需要控制台提供的執行識別碼。

## 驗證程式

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

測試使用暫存資料庫與假的 LINE 憑證，不呼叫真實 LINE API、不存取正式資料。

## 參考文件

- [接收 LINE 訊息](https://developers.line.biz/en/docs/messaging-api/receiving-messages/)
- [驗證 LINE Webhook 簽章](https://developers.line.biz/en/docs/messaging-api/verify-webhook-signature/)
- [Python SQLite 模組](https://docs.python.org/3/library/sqlite3.html)
