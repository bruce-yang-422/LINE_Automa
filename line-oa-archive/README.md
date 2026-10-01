# LINE OA 對話紀錄：本機 SQLite

管理工作台已整合全站 Apple 風格與 Tailwind 主題，提供報告／收件者詳情、授權資料搜尋及單次預約管理。樣式來源位於根目錄 `styles/app.css`，執行 `npm run build:css` 產生 `web/app.css`；部署需包含編譯檔。操作與首版範圍見[根目錄 README](../README.md)。

本專案供內部使用，由本機 Python 接收 LINE 官方帳號（OA）的 Webhook，將新訊息儲存至 SQLite。Webhook 與資料庫僅使用 Python 標準函式庫；圖片推送使用 `truststore` 驗證 HTTPS，管理服務新增站內帳密及 Session 登入，舊 Cloudflare Access 模式仍使用 `PyJWT[crypto]`。切換步驟見[網站登入與切換](../docs/功能規格/網站登入與切換.md)。透過根目錄安裝器安裝相依套件。遠端管理設定請見[根目錄 README](../README.md#在外面登入管理頁)。不需要資料庫帳號、密碼、Docker 或獨立資料庫服務。

```text
LINE OA → https://reports.stack-base.com/webhook
        → Cloudflare Tunnel → http://localhost:18474/webhook
        → data/line_archive.db
```

## 功能範圍

- 記錄使用者與 OA 的一對一對話，以及 OA 已加入的群組、多人聊天室的新訊息；不包含其他使用者之間的私人聊天或過去的聊天紀錄。
- 儲存文字、訊息類型、識別碼與時間；時間採用 UTC ISO 8601 格式。
- 不下載圖片、檔案、貼圖、音訊或影片內容，不記錄 OA 主動發送的訊息，也不追蹤訊息編輯。
- 同一 OA 內相同訊息 ID 不重複寫入；不同 OA 各自保存。收回訊息時清除文字並保留收回標記；即使收回事件先到達，後續重送的原始訊息也不會恢復文字。
- 已實作接收與紀錄、PNG 圖片服務與個人／群組手動推送。發送步驟見 [天氣圖片測試](../README.md#傳送天氣圖片到-line)；已支援文字公告及單次預約；循環排程與表單提醒尚未實作。
- 請告知對話參與者，並依公司需求訂定資料保留與存取規則。

## Windows 啟動方式

日常操作可使用專案根目錄的獨立控制台與桌面捷徑，參見 [控制台設定與操作](../README.md)。控制台啟動器會讀取本資料夾的 `.env`；以下直接執行 `app.py` 的方式仍需自行設定環境變數。

需要 Python 3.11 以上版本，以及 LINE Developers 中 Messaging API 頻道的 channel secret（頻道密鑰）。密鑰用來驗證 LINE Webhook，與資料庫登入無關。

在 PowerShell 執行：

```powershell
cd D:\Tools\LINE_Automation\line-oa-archive
$env:LINE_CHANNEL_SECRET = '請填入你的 LINE 頻道密鑰'
python app.py
```

程式會自動建立 `data/line_archive.db` 及資料表，重新啟動時保留既有紀錄。環境變數只對目前 PowerShell 工作階段與其子程序生效。

`schema.sql` 是本版完整的首次建表定義，包含組織授權、排程、收件者名稱快取與網站登入欄位。啟動不再執行舊版補欄位、角色表重建或資料回填；不支援直接套用舊版資料庫備份。`IF NOT EXISTS` 用於本版重啟，不會清除現有資料。收件者或組織刪除後，不會在下次啟動時由歷史資料重新建立。

全新安裝若 `ADMIN_ALLOWED_EMAILS` 留空，不會自動建立網站帳號。先從桌面控制台「開啟管理後台」進入本機管理頁，在「帳號與設定」新增第一個平台管理員，再用「設定登入」完成密碼設定，依[網站登入與切換](../docs/功能規格/網站登入與切換.md)啟用遠端網站登入。LINE Token、Tunnel 與網站帳號是分開設定的。

`.env.example` 供設定參考；直接執行 `app.py` 不會自動載入 `.env`。若使用此啟動方式並需要自訂資料庫位置，請在啟動前設定：

```powershell
$env:DATABASE_PATH = 'D:\Data\line_archive.db'
```

預設為 `data/line_archive.db`。相對路徑一律以 `app.py` 所在資料夾為基準，不受執行指令時的工作目錄影響。

在另一個 PowerShell 視窗檢查：

```powershell
curl.exe http://localhost:18474/healthz
```

正常時回傳 `ok`。服務只監聽本機 `127.0.0.1:18474`。

## Cloudflare Tunnel 設定

| 項目 | 設定值 |
| --- | --- |
| 公開網域 | `reports.stack-base.com` |
| 對外網址 | `https://reports.stack-base.com` |
| 本機服務 | `http://localhost:18474` |
| LINE Webhook 網址 | `https://reports.stack-base.com/webhook` |
| 本機健康檢查 | `http://localhost:18474/healthz` |

1. 在執行本機 Bot 的電腦啟動 `cloudflared`。
2. 在 Cloudflare Tunnel 的已發佈應用程式路由設定上述網域與本機服務網址。若 `localhost` 被解析為 IPv6 而無法連線，可將服務網址改為 `http://127.0.0.1:18474`。
3. 在 LINE Developers → Messaging API 設定上述 Webhook 網址，執行驗證，並啟用 Webhook 與事件重新傳送。
4. 若需接收群組訊息，啟用允許機器人加入群組的設定，再邀請 OA 加入群組。
5. 傳送新訊息後，查詢本機資料庫確認紀錄。

Webhook 不應要求 Cloudflare Access 瀏覽器互動登入；程式會驗證 LINE 簽章。此文件列出預定路由，修改程式不會自動變更 Cloudflare 或 LINE 後台設定。

## 查詢紀錄

在專案資料夾的 PowerShell 執行以下指令，以 Python 查詢最近 20 筆訊息。若設定了 `DATABASE_PATH`，此指令會使用相同設定。

```powershell
python -c "import app; from contextlib import closing; import sqlite3; conn=sqlite3.connect(app.DATABASE_PATH); rows=conn.execute('SELECT conversation_type, conversation_id, text_content, sent_at, unsent_at FROM line_messages ORDER BY received_at DESC LIMIT 20').fetchall(); conn.close(); print(*rows, sep='\n')"
```

請先啟動程式完成資料庫初始化。

## 備份與維運

- 資料庫放在本機磁碟，避免讓多台電腦直接透過網路共用資料夾讀寫同一份 `.db`。
- 每個請求使用獨立連線，啟用 WAL 模式，寫入鎖定最多等待 10 秒。資料庫錯誤回傳 HTTP 503，供 LINE 重新傳送；斷電或斷線仍可能造成紀錄缺漏。
- `data/` 與 SQLite 檔案已加入 `.gitignore`，請另行安排備份。
- 執行中可能有 `.db-wal` 與 `.db-shm` 檔案，不可任意刪除，也不要只複製 `.db` 當作執行中的完整備份。
- 可在專案資料夾使用 SQLite 備份 API 建立一致的備份（來源需已初始化）：

```powershell
python -c "import app, sqlite3; from contextlib import closing; from datetime import datetime; from pathlib import Path; dest=Path('backups'); dest.mkdir(exist_ok=True); target=dest / (datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.db'); source=sqlite3.connect(app.DATABASE_PATH); backup=sqlite3.connect(target); source.backup(backup); backup.close(); source.close(); print(target)"
```

此版本不再使用 PostgreSQL；既有 PostgreSQL 資料不會自動匯入 SQLite，也不會被刪除。

## 驗證程式

```powershell
python -m unittest discover -s tests -v
```

測試使用暫存資料庫，不存取正式資料。

## 參考文件

- [接收 LINE 訊息](https://developers.line.biz/en/docs/messaging-api/receiving-messages/)
- [驗證 LINE Webhook 簽章](https://developers.line.biz/en/docs/messaging-api/verify-webhook-signature/)
- [Python SQLite 模組](https://docs.python.org/3/library/sqlite3.html)


## 多 OA 管理

管理網站的「LINE OA 管理」提供個人／組織多 OA 設定、驗證、憑證更新與啟停。每個 OA 使用獨立 `/webhook/{channel_id}`；匯入的原始 OA 保留 `/webhook`。頂端選定 OA 後，報告、收件者、素材及預約皆限定該 OA。

原本單 OA 安裝升級：停止 LINE 服務，執行 `python upgrade_multi_oa.py --apply`，再啟動服務並從管理頁匯入既有 OA。正常啟動不執行歷史遷移。請連同資料庫保存 `instance/line-credentials.key`，否則無法解密 OA 憑證。多 OA 命令列發送必須指定 `--oa <channel_id>`。
