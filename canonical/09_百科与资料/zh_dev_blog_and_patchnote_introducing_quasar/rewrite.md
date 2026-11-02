---
id: canon-4457020712
title: zh_dev_blog_and_patchnote_introducing_quasar
domain: 09_百科与资料
subdomain: 
type: canonical
status: drafted
sde_build: 3662168 / 2026-10-30
verified: 2026-11-01
origin: corpus\09_百科与资料\zh_dev_blog_and_patchnote_introducing_quasar.md
---
# zh_dev_blog_and_patchnote_introducing_quasar

2021年 9月 14日, 這日代表 EVE 一個時代的結束, 亦代表 EVE 技術往前邁進的起點。隨着新 NPE 內容的推出, 技能規劃 的引入, EVE Online 以全新的方式走向未來。

## 要点

- 上一次修改網絡層架構已追溯到 2011年, CCP 引入自己的 IOCP - 輸入輸出完成端口 : CarbonIO, 這亦是後來臭名昭著 time dilation 時間膨脹的基礎。然後開展了「Project Sanguine」以處理 CarbonIO 接手後的其他問題。EVE 中的每一項改善最終都是沿於與 Python 全局解釋器鎖 (GIL) 的仔細調整。簡單地說, Python 架構一次只能做一件事。EVE 採用 Stackless Python, 通過 StacklessIO 和 CarbonIO 實現 IOCP, 以及圍繞時間膨脹的合作設計, 以保持新伊甸活着的錯覺。但 GIL 是不是需要爲所有內容服務呢? CCP 該如何利用現今硬件工業以爆炸式堆疊核心數量, 而不再是追求更高的核心時脈的升級趨勢呢?
- CCP 已經有許多與 Project Sanguine 相關的實驗, 最爲人熟悉的就是 EVE : Aether Wars。目標不是從根本上改變 EVE Online 的通信模型, 而是改變模擬模型。相比之下, Project Sanguine 的目標是處理 EVE 伺服器日常中枯燥的部分。如果新伊甸不必處理那些對現場模擬相關的其他事情, 那麼在模擬近 9,000 名玩家同場作戰就可以更快。因此, Project Sanguine 就是要實現兩個目標：避免不必要的 GIL 溝通, 爲更重要的內容預留處理空間。
- 2016 年底, Project Sanguine 以 ESI 和 EVE Portal 第一次迭代出現在新伊甸宇宙中。通過這些項目, EVE Online 的服務器架構中建立了一個新的溝通模式：消息總線。利用這新的匯總方式, 重新發現了與 GIL 相關的瓶頸, 亦更清楚地了解了它們當中的處理步驟：message routing (消息路由), serialization (序列化) 和 transmission (傳輸)。如果一艘船在 1,000 艘船之間發射了一發激光, 那就有 1,000 條消息需要立即發送給整個戰場。伺服器必須將該消息副本尋址到 1,000 個目的地 (消息路由), 將該數據轉換為傳輸格式 (序列化), 然後通過線路發送數據（傳輸）。在大多數情況, CarbonIO 都能運作良好, 但速度始終受到 GIL 所限。CarbonIO 已經為 EVE Online 良好地服務了很長一段時間, 但自 2011 年以來，互聯網本身亦發生了很大變化。

## 数据来源

- 原始语料整理（无对应 SDE 条目）
