# 專案審查與修復紀錄

審查涵蓋 TTX 多人網路、預測與物理、地形與圖像、終端顯示、Kard-X 戰鬥與冒險、文字沙盒、資料編輯、設定、存檔、套件與 CI。保留審查開始前的未提交修改，包括像素素材與場景轉場；未建立提交或發布版本。

## 已修復問題

| 範圍 | 問題與修正 | 主要檔案 |
| --- | --- | --- |
| 伺服器生命週期 | 用就緒事件取代固定等待；啟動錯誤回報給呼叫端；限制單一執行中的伺服器並防止外部重設；關服完整等待模擬、收包與發送執行緒，舊 handle 不會關掉新伺服器。 | `ttx/net/server.py`、`ttx/cli.py` |
| 網路廣播 | 慢速連線原本能阻塞模擬。改由各連線獨立發送最新快照，合併過時快照，避免佇列持續增加；快照在鎖內複製，不會隨遊戲狀態改變。 | `ttx/net/transport.py`、`ttx/net/server.py` |
| 封包處理 | 分段 UTF-8、非物件 JSON、非有限數值、錯誤欄位與未結束的超大封包有明確處理；指令上限 64 KiB，快照上限 16 MiB。錯誤指令不會部分修改世界，錯誤快照不會取代可用狀態。 | `ttx/net/protocol.py`、兩端網路模組 |
| 連線與出生 | 連線有逾時；戰鬥中斷線會退出等待；本機玩家消失時不會改控制其他玩家；超過十名玩家仍會尋找不同且可站立的出生位置。 | `ttx/net/client.py`、`ttx/net/server.py`、`ttx/terminal.py` |
| 戰鬥判定 | 自傷或同時擊倒雙方會結束戰鬥；HP 不會降至負值；已結束的戰鬥不能繼續出牌；敵人不能打出不在手中或魔力不足的牌。 | `kardx/game_state.py`、`kardx/player.py` |
| 戰鬥資源 | 降低最大魔力時同步限制目前魔力，負傷害不會產生 HP 或防禦；第一張攻擊牌的遺物加成也適用於 Pierce 的真實傷害，且只觸發一次。卡牌費用與角色資源在載入時檢查。 | `kardx/card.py`、`kardx/player.py`、`kardx/game_state.py` |
| 多人戰鬥進度 | 獎勵牌依伺服器累積清單加入本機牌組，相同牌名的多次獎勵仍各自保留；重複快照不會重複加入。戰敗依文字沙盒既有規則保留至少 1 HP，避免下次戰鬥無法進行。 | `ttx/net/client.py` |
| 冒險事件 | 金幣不足或缺少待升級卡牌時，整個事件選項不會先發獎勵再扣費；玩家可以重新選擇或離開。空路線與缺少敵人的戰鬥節點會提早回報。 | `kardx/adventure.py`、冒險控制器 |
| 文字沙盒 | 不可用的升級合成不會扣材料或消耗回合；負合成成本不能產生材料；明確的零道具效果不會變成一個道具；已完成任務不會被對話重新啟動；門鎖使用設定的物品，並檢查撤退房間引用。 | `kardx/sandbox.py` |
| 存檔 | 用同目錄暫存檔完成寫入後原子取代；寫入失敗保留舊檔並清理暫存檔。限制存檔槽名稱，驗證載入資料與房間、角色、卡牌引用，載入失敗保留目前進度並顯示訊息。 | `kardx/persistence.py`、`kardx/sandbox.py`、沙盒控制器 |
| 設定 | 讀取不會建立檔案或覆寫損壞設定；錯誤型別、主題與速度改用安全預設。修改才以原子寫入儲存；因寫入權限而儲存的工作目錄備援設定會在重啟後載入。 | `kardx/settings.py` |
| 顯示與輸入 | 覆寫寬字元時清除兩格關係；接受 ANSI 空參數與預設前景色；保留邊界組合字元。窄視窗會顯示目前選中的牌，切換沙盒時清除舊畫面快取，組合途中縮放視窗不會混用不同尺寸。Unix 直接讀取 tty 位元組並支援常見方向鍵序列，EOF 與 Ctrl+C 可正常退出。 | `ttx/terminal.py`、`kardx/keyboard.py`、相關視圖 |
| 地圖記憶體 | 地表高度快取改為每張地圖自行持有，舊地圖不再被全域方法快取保留。 | `ttx/world/map.py` |
| 套件驗證 | 像素素材測試改讀安裝套件資源，確實驗證 wheel；原始碼包包含素材處理工具與本紀錄。 | `tests/test_scene_features.py`、`tests/test_packaging.py`、`pyproject.toml` |

Socket 的關閉順序是先 `shutdown` 喚醒 I/O，等待發送／接收工作結束，再由連線擁有者 `close`。Winsock 文件要求避免在其他 socket 操作進行時同時關閉該 socket，這也支持本次調整的所有權順序。[Microsoft closesocket 文件](https://learn.microsoft.com/en-us/windows/win32/api/winsock/nf-winsock-closesocket)

## 驗證

- 初始測試基準：95 項測試與 14 個子測試通過。
- 修正後：198 項測試與 14 個子測試通過，新增 103 個回歸案例，涵蓋上述錯誤與資源清理。
- Python 3.12 執行完整開發環境測試；Python 3.10 在獨立環境安裝新 wheel 後執行完整測試，確認匯入路徑位於 `site-packages`。
- 建置 wheel 與原始碼包，產物位於 `dist/audit/`，保留原有 `dist/` 產物。
- 網路案例使用真實本機 TCP／socket pair，包括占用埠、關服後相同埠重新開服、十二名玩家出生、異常封包與工作執行緒清理。
- Windows 執行實測；Unix 鍵盤分支由 tty 適配器測試覆蓋，尚未做 Linux 終端人工遊玩。GitHub Actions 原有 Linux／Windows 矩陣保留。

重跑驗證：

```powershell
uv run --locked pytest -q
uv build --out-dir dist/audit
uv run --isolated --no-project --python 3.10 --with .\dist\audit\ttx-0.1.0-py3-none-any.whl --with 'pytest>=8,<10' pytest tests -q
```

## 仍存在的設計限制

多人卡牌戰鬥結果仍由客戶端回報。雖然伺服器已檢查交戰對象與獎勵只能領取一次，修改過的客戶端仍能偽造勝利；伺服器逐步驗證出牌與回合協定尚未實作，README 原有 roadmap 也列出了這項工作。

目前世界狀態仍由模組集中持有，本次用單一 runtime、生命週期限制與鎖確保一致性；未擴充為同一行程同時承載多個世界。TTX 多人世界也尚未具備完整持久化存檔；本次修復的是既有文字沙盒存檔。
