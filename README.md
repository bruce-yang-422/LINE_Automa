# LINE 自動化

在一台 Windows 電腦上管理多個 LINE 官方帳號（OA）：接收 Webhook 並保存對話、聊天回覆、聯絡對象與標籤、案件與對話記事本、訊息發送（立即或預約）。管理後台是網頁，透過 Cloudflare Tunnel 對外提供。

功能規格與權限以 [docs/](docs/README.md) 為準；開發進度見 [AI_AGENT_TASKS.md](AI_AGENT_TASKS.md)。

## 安裝

在專案根目錄執行一次：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-ControlPanel.ps1
```

安裝程式建立本專案的 `.venv`（需要 Python 3.11 以上及 Python Launcher）、安裝 `line-oa-archive/requirements.txt`（`truststore`、`cryptography`、`Pillow`），建立桌面「LINE 自動化控制台」捷徑，並在 `line-oa-archive/.env` 不存在時從 `.env.example` 複製一份。

### `.env`：部署設定

`.env` 放網站啟動前就需要的三項設定，格式為每行 `KEY=value`（不執行指令、不展開變數）：

| 設定 | 說明 |
| --- | --- |
| `DATABASE_PATH` | SQLite 資料庫位置；相對路徑以 `line-oa-archive/` 為基準，預設 `data/line_archive.db` |
| `PUBLIC_BASE_URL` | 對外 HTTPS 網址（Tunnel），LINE Webhook 與公開圖片使用，例如 `https://reports.example.com` |
| `ADMIN_PUBLIC_HOST` | 管理後台的對外網域，例如 `line-admin.example.com`；未設定時只能從本機控制台使用 |

LINE 服務使用的 OA 憑證與後台帳號一律在管理後台網頁設定並存入資料庫，**不寫在 `.env`**。修改上表設定後請重啟 LINE 服務。

選填：外部 Python 發送腳本用的 token，每個 OA 一行 `LINE_CHANNEL_ACCESS_TOKEN_<Bot basic ID 去掉 @ 後轉大寫>`（例如 `@123abcde` → `LINE_CHANNEL_ACCESS_TOKEN_123ABCDE`）。LINE 服務不讀取這些設定；真正的 token 只能填在 `.env`，`.env.example` 會提交到 Git，必須保持空白。見 [關鍵字訂閱](docs/功能規格/關鍵字訂閱.md)「6」。

報告中心、舊版天氣訂閱、發送範圍與操作人員模組授權已於 2026-10-05 移除（訂閱改為下方「關鍵字訂閱」）。既有資料庫不需重建：舊資料表與欄位保留但不再使用，資料庫版本仍為 2。

## 首次設定

1. 開啟桌面「LINE 自動化控制台」，按「啟動 LINE」。
2. 按「開啟管理後台」。資料庫還沒有平台管理員時，本機頁面會直接顯示「建立第一位平台管理員」：輸入 Email 與顯示名稱，取得一次性設定連結（30 分鐘有效），本人以連結設定密碼。此頁在建立後不再出現；從對外網址只會看到「系統尚未完成初始設定」。
3. 平台管理員在「組織」建立組織（類型可為公司、單位、社團、家庭、個人等）與該組織的管理員帳號，產生登入設定連結交給對方。
4. 在「LINE OA」為組織新增 OA：輸入 LINE Developers → Messaging API 的 Channel secret 與 Channel access token（加密保存）。把畫面上的 Webhook URL（`https://<PUBLIC_BASE_URL>/webhook/<OA 識別碼>`）貼回 LINE Developers，按 Verify 並開啟 Use webhook。
5. 組織管理員登入後，在「人員與權限」新增操作人員與協作人員、勾選可用 OA。

**沒有桌面的主機**：在 `line-oa-archive/` 執行 `..\.venv\Scripts\python.exe create_admin.py`，互動輸入 Email 後印出一次性設定連結。已有平台管理員時，同一指令可新增平台管理員或產生重設密碼連結（緊急復原）。指令不接受密碼參數、不寫入任何檔案。

架設主機的人若自己也要經營 OA，請為自己建立一個組織（例如類型「個人」）與管理員帳號，**使用另一個 Email**（平台管理員帳號不能同時是組織帳號），以該帳號登入操作。本機控制台身分等同平台管理員。

## 角色

| 畫面名稱 | 程式角色值 | 範圍 |
| --- | --- | --- |
| 平台管理員 | `platform_admin` | 只有「組織」與「LINE OA」兩個管理頁：建立組織與其管理員、設定 LINE OA 與組織的訊息發送模組；不進入 OA 營運畫面，必要時以「切換視角」唯讀查看，每次查看寫入該組織操作紀錄 |
| 管理員 | `org_admin` | 所屬組織的所有 OA 與人員 |
| 操作人員 | `operator` | 被授權 OA 的對話、發送、案件與記事 |
| 協作人員 | `collaborator` | 被授權 OA 的案件、記事與聯絡對象；不能傳送訊息 |

完整權限表見 [權限與角色規格](docs/功能規格/權限與角色規格.md)。

## 桌面控制台與服務

- 本機服務：Webhook／圖片 `http://127.0.0.1:18474`，管理後台 `http://127.0.0.1:18475`。
- Cloudflare Tunnel：`reports.<網域>` → `http://127.0.0.1:18474`；`line-admin.<網域>` → `http://127.0.0.1:18475`（Path 留白、不覆寫 Host Header）。不需要 Cloudflare Access；管理後台以站內帳號密碼登入，見 [網站登入](docs/功能規格/網站登入.md)。
- 控制台只管理本專案的 Python 服務，不啟停共用 Cloudflared，也不修改遠端 Tunnel 設定。「設定」欄顯示 Python 環境、`PUBLIC_BASE_URL` 與是否已有啟用中的 LINE OA。
- 重複啟動不會建立第二份服務；停止會等待進行中的請求與資料庫交易結束。關閉控制台視窗不會停止背景服務；重新開機後需再按「啟動 LINE」。
- 命令列：`.\Start.ps1`、`.\Stop.ps1`、`.\Stop.ps1 -TimeoutSeconds 60`。
- `.env`、`.venv`、資料庫、備份及 `line-oa-archive/instance/`（含 OA 憑證金鑰 `line-credentials.key`）都不納入 Git。**金鑰檔遺失就無法解密已保存的 OA 憑證**，備份資料庫時一併備份。

電腦須保持開機、不進入睡眠、網路正常，LINE 服務與 Cloudflared 都須持續執行。

## 發送

- 「建立發送」可選文字或圖片格式（單圖／多圖、圖文卡片、輪播卡片、圖文訊息），依勾選、標籤或自訂篩選條件選擇發送對象，立即或指定時間預約。預約保存內容快照，到期時重新檢查權限與對象；逾期超過 10 分鐘不補發。
- 發送結果逐一記錄 LINE 已接受、失敗、狀態不明或取消；不自動重送失敗或狀態不明的訊息。
- 圖片以隨機檔名快照放在 `line-oa-archive/published-images/`，透過 `PUBLIC_BASE_URL/images/...` 提供給 LINE；發送前會確認公開網址的內容與本機一致。
- 外部腳本產生的圖片（營業數據、天氣報告等）放在 `line-oa-archive/media/<子資料夾>/`，以 `PUBLIC_BASE_URL/media/...` 公開提供，見 [公開圖片素材](docs/功能規格/公開圖片素材.md)。
- 聯絡對象可傳關鍵字訂閱報告（主題、關鍵字與白名單／黑名單設定在 `line-oa-archive/subscribers/topics.json`），名冊輸出為 `subscribers/<主題>.json` 供 Python 發送腳本讀取，見 [關鍵字訂閱](docs/功能規格/關鍵字訂閱.md)。首次使用請將 `subscribers/topics.example.json` 複製為 `topics.json` 再修改；`topics.json` 與名冊含 LINE ID，不納入 Git。

## 介面樣式

全站使用 Tailwind CSS 4 本機編譯，入口為 `styles/app.css`，輸出 `line-oa-archive/web/app.css`（部署時需包含）；密集版面另載入 `line-oa-archive/web/density.css`（不經編譯）。修改樣式後重新建置；一般啟動不需要 Node.js：

```powershell
npm ci
npm run build:css
```

管理後台送出 CSP `style-src 'self'; script-src 'self'`：瀏覽器**不會套用** `style="..."` 行內樣式，也不執行 `onclick=` 等行內事件。樣式請寫成 class；`line-oa-archive/web/inline-styles.css` 是由舊行內樣式轉出的對照表，新程式不要再新增行內樣式。

## 測試

```powershell
Push-Location line-oa-archive
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
Pop-Location
powershell.exe -NoProfile -File .\tests\control_lifecycle.ps1
# 瀏覽器測試需要 Playwright 與 Chrome
node tests/workspace_browser.cjs
node tests/compact_browser.cjs
node tests/chat_notes_preview.cjs
```

測試使用臨時設定、資料庫與連接埠，不呼叫真實 LINE API，也不控制正式 Cloudflared。

## 文件

- [專案文件索引](docs/README.md)（功能規格、權限、UI 規範）
- [Bot 功能與資料庫說明](line-oa-archive/README.md)
- [LINE OA 申請與設定](line-oa-archive/LINE_OA申請與設定.md)
- `line-bot-sdk-python/` 只供本機參考，不納入 Git。
