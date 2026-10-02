# 資訊小幫手：LINE OA 申請與設定資料

更新日期：2026-10-02

本文件整理建立官方帳號、啟用 Messaging API 與設定 Bot 時會用到的資訊。用途涵蓋個人生活與公司內部資訊，不限於公司使用。下列文案可直接複製；實際必填欄位與選項以 LINE 後台為準。

## 帳號基本資料

| 項目 | 建議填寫內容 |
| --- | --- |
| 官方帳號名稱 | 資訊小幫手 |
| 狀態消息 | 天氣・報表・通知・提醒 |
| 使用地區 | 台灣（請依實際營運地區確認） |
| 使用語言 | 繁體中文 |
| 用途 | 個人與公司內部的資訊整理、報表通知及日常提醒 |
| 業種類別 | 依實際用途選擇後台最接近的資訊服務或其他類別；選項名稱以畫面為準 |
| 管理者姓名與電子郵件 | 填寫實際管理者資料，電子郵件需可收信 |
| 公司或經營者資料 | 依實際身分填寫，不因名稱或功能而虛構公司資料 |
| 大頭照 | 待製作；建議使用容易辨識的資訊、通知或助手圖示 |
| 帳號基本 ID、加好友連結與 QR Code | 建立帳號後由後台取得，待補 |

### 帳號簡介／服務說明

```text
資訊小幫手，整理工作與生活中的實用資訊，提供天氣報表、資料報表、公告通知與日常提醒。依設定接收指定資訊，讓重要消息更容易掌握。
```

此段為服務定位文案，適合填入簡介或服務說明欄位。天氣、報表推播與提醒仍為規劃功能，正式對外使用前應依實際完成項目調整。

### 測試階段歡迎訊息

```text
你好，歡迎加入「資訊小幫手」！

這裡將提供天氣資訊、資料報表與工作生活提醒，目前仍在建置測試中，尚未提供自動問答或訂閱指令。

你傳送給本帳號的訊息可能會由系統記錄，供測試與功能運作使用。請勿傳送密碼或不必要的敏感資料；如需了解紀錄用途或申請刪除，請聯絡帳號管理者。
```

可在 OA 後台設定加入好友的歡迎訊息；目前 Python 程式不會自動發送此文案。正式使用前補上管理者聯絡方式。

## 建立帳號與啟用 Messaging API

1. 從 [LINE 官方帳號管理後台](https://manager.line.biz/) 建立「資訊小幫手」，填寫實際管理者資料。
2. 在該帳號的設定中啟用 Messaging API。首次使用時，依畫面完成開發者資料登記。
3. 選擇代表實際服務管理者的 Provider（服務提供者）。若已有需整合的 LINE Login 等頻道，先確認是否應使用相同 Provider；不要只為了名稱方便隨意選擇。
4. 開啟 [LINE Developers Console](https://developers.line.biz/console/)，確認已產生對應的 Messaging API 頻道。
5. 取得 Channel secret 與 Channel access token，由平台管理員在管理後台「LINE OA」頁輸入後，再進行 Webhook 驗證。

目前官方流程為「先建立 OA，再從 OA 後台啟用 Messaging API」。建立一般帳號與申請認證帳號是不同事項；本文件整理 Bot 啟用所需資訊，不代表已提出帳號認證申請。

參考：[官方 Messaging API 入門流程](https://developers.line.biz/en/docs/messaging-api/getting-started/)。

## 專案連線資料

| 項目 | 設定值 |
| --- | --- |
| 程式專案 | `line-oa-archive` |
| 公開網域 | `reports.stack-base.com` |
| 對外網址 | `https://reports.stack-base.com` |
| Cloudflare Tunnel 本機服務 | `http://localhost:18474` |
| LINE Webhook URL | 管理後台「LINE OA」頁顯示，格式 `https://reports.stack-base.com/webhook/<OA 識別碼>` |
| 本機健康檢查 | `http://localhost:18474/healthz` |
| 程式監聽位址 | `127.0.0.1:18474` |
| SQLite 資料庫 | `data/line_archive.db`（相對於專案資料夾） |

這些是專案設定值，並不代表公開網域已連通。根網址目前不是公開服務介紹頁，不能直接當作隱私權政策或服務條款網址；若申請畫面需要這些網址，需先準備並發布對應文件。

### Webhook 設定步驟

1. 啟動本機 Bot，確認健康檢查回傳 `ok`。
2. 確認 Cloudflare Tunnel 將上述網域導向本機服務。
3. 在管理後台「LINE OA」新增此 OA（輸入 Channel secret 與 Channel access token），複製畫面上的 Webhook URL。
4. 在 LINE Developers 的 Messaging API 設定頁填入 Webhook URL，執行 Verify（驗證）。
5. 啟用 Use webhook（使用 Webhook）與 Webhook redelivery（重新傳送）。
6. 若需要記錄群組訊息，啟用 Allow bot to join group chats，並邀請 OA 加入目標群組。
7. 若不需要 OA 後台的自動回應，可關閉該功能，避免測試時出現額外回覆；歡迎訊息可依需要保留。
8. 傳送測試訊息，確認管理後台「LINE OA」顯示 Webhook 最近到達、聯絡對象出現在名單。群組使用前先告知成員紀錄用途。

參考：[Webhook 接收與重新傳送](https://developers.line.biz/en/docs/messaging-api/receiving-messages/)。

## 密鑰與後續通知功能

| 資料 | 用途與設定方式 |
| --- | --- |
| Channel ID | 頻道識別碼，建立後取得；目前接收程式不需額外設定 |
| Channel secret | 驗證 Webhook 簽章；平台管理員在管理後台「LINE OA」頁輸入，加密存入資料庫 |
| Channel access token | 發送訊息與查詢名稱使用；同上，於「LINE OA」頁輸入 |
| 發送對象 | 對方傳訊息或加好友後，自動出現在「聯絡對象」；不需手動填 userId／groupId |

密鑰與權杖只在管理後台輸入，不寫入 `.env`、不填進這份 Markdown，也不提交 Git。

主動通知上線前，另確認帳號的訊息額度、方案及可發送對象條件；不在本文件假定固定價格或額度。

參考：[Messaging API 官方規格](https://developers.line.biz/en/reference/messaging-api/)。

## 建立後待補資料

- [ ] 管理者姓名、電子郵件與聯絡方式已確認。
- [ ] 大頭照已上傳，名稱與狀態消息已設定。
- [ ] 已取得帳號基本 ID、加好友連結與 QR Code。
- [ ] Provider 歸屬與 Messaging API 頻道已確認。
- [ ] 頻道密鑰與權杖已在管理後台「LINE OA」頁設定，未寫入文件。
- [ ] Webhook 驗證成功，測試訊息已寫入 SQLite。
- [ ] 群組紀錄範圍、資料保留方式與刪除聯絡窗口已確認。

平台功能（聊天、聯絡對象、案件、發送與預約）見[根目錄 README](../README.md)。
