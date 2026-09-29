# LINE OA 對話紀錄：本機 SQLite

本專案供內部使用，由本機 Python 接收 LINE 官方帳號（OA）的 Webhook，將新訊息儲存至 SQLite。Webhook 與資料庫僅使用 Python 標準函式庫；手動圖片推送另外使用 `truststore` 驗證 HTTPS。不需要資料庫帳號、密碼、Docker 或獨立資料庫服務。

```text
LINE OA → https://reports.stack-base.com/webhook
        → Cloudflare Tunnel → http://localhost:18474/webhook
        → data/line_archive.db
```

## 功能範圍

- 記錄使用者與 OA 的一對一對話，以及 OA 已加入的群組、多人聊天室的新訊息；不包含其他使用者之間的私人聊天或過去的聊天紀錄。
- 儲存文字、訊息類型、識別碼與時間；時間採用 UTC ISO 8601 格式。
- 不下載圖片、檔案、貼圖、音訊或影片內容，不記錄 OA 主動發送的訊息，也不追蹤訊息編輯。
- 相同訊息 ID 不重複寫入。收回訊息時清除文字並保留收回標記；即使收回事件先到達，後續重送的原始訊息也不會恢復文字。
- 已實作接收與紀錄、PNG 圖片服務與個人／群組手動推送。發送步驟見 [天氣圖片測試](../README.md#傳送天氣圖片到-line)；公告、表單提醒與每日排程仍未實作。
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
