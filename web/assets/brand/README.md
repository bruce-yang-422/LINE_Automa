# LINE 自動化品牌素材

`light`／`dark` 指圖檔本身的亮色／暗色版本。沿用使用者提供的原檔，不重新繪製、裁切或壓縮；搬移時已驗證 SHA-256 相同。

| 原始名稱 | 歸檔名稱 | 套用位置 |
| --- | --- | --- |
| 未命名-1.png | `line-automation-logo-light.png` | 網站淺色側欄與頂部列、Apple touch icon |
| 未命名-1.ico | `line-automation-logo-light.ico` | 亮色瀏覽器頁籤、預設 favicon、Windows 控制台與桌面捷徑 |
| 未命名-2.png | `line-automation-logo-dark.png` | 備用素材；網站僅提供亮色介面，目前未使用 |
| 未命名-2.ico | `line-automation-logo-dark.ico` | 備用素材；目前未使用 |

PNG 為 1024 × 1024、RGBA；ICO 內含 16、20、24、32、40、48、64、128、256 像素尺寸。

網站圖檔走 `/assets/brand/` 的明確白名單，不開放任意路徑讀取；`/favicon.ico` 對應亮色 ICO。網站僅提供亮色介面，頁面與瀏覽器圖示固定使用亮色版本；暗色檔案保留但不對外提供。

新增或重建桌面捷徑時，`Install-ControlPanel.ps1` 自動指向此處的亮色 ICO。已開啟的控制台需重新開啟視窗才會顯示新圖示。
