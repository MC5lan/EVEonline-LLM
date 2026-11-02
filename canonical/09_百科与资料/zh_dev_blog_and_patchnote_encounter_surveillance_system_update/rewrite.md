---
id: canon-8120710360
title: zh_dev_blog_and_patchnote_encounter_surveillance_system_update
domain: 09_百科与资料
subdomain: 
type: canonical
status: drafted
sde_build: 3662168 / 2026-10-30
verified: 2026-11-01
origin: corpus\09_百科与资料\zh_dev_blog_and_patchnote_encounter_surveillance_system_update.md
---
# zh_dev_blog_and_patchnote_encounter_surveillance_system_update

--------\\原文鏈接: Encounter Surveillance System Update

## 要点

- 統合部現正對 Encounter Surveillance System - ESS (事件監測裝置) 進行重大調整。新的 ESS 設定將會與 concord_introduces_the_dynamic_bounty_system 同時推出, 兩者配合下將會重塑目前 0.0 地區的刷怪邏輯。
- 原本的 ESS 設定是爲 0.0 地區玩家提供一個增加面對被盜取收入的風險的同時,增加星系內刷怪收入的機會。此理念非常清晰但聰明的玩家們已經指出了有幾項與 風險/獎勵 有關 以及 部署位置 的問題, 這顯示出 ESS 系統有很多可以改進的地方。直至現在, 是時候從獲得的經驗中學習, 對設計重新審視, 更聚焦於 0.0 地區創造更多衝突的機會。
- *ESS 不再是可供選擇的部署選項, 將會預設部署於所有 0.0 星系。  *ESS 的部署地點是全星系公開的，並且需要通過設立了艦船級別限制的加速軌道才能前往。  *ESS 將會自動支付其收繳的額外賞金, 玩家不需要親自去收取賞金。
- 就如目前的 ESS 般, 一部份的刷怪賞金收入將會被 ESS 收繳而非直接支付到玩家錢包。 而與目前 ESS 不一樣的是, 收繳的賞金將分開兩份儲存:
- *<fs large>主要</fs> : 大部份收繳的賞金都會儲存在這位置, 並且每 3 小時自動支付給回玩家, 但期間可隨時被入侵者提走。  *<fs large>儲備區</fs> : 這是真正的大獎。賞金的一小部份會儲存在這區, 並且一直累積直至持有特定鎖匙的玩家前往偷取。在由儲備區偷錢時, 賞金隨時間支付給玩家, 速度會緩緩上升, 到最高速度後又下降回去。玩家需要決定到底想要在提款機前等待多久, 想要偷取多少金額才離開。此鎖匙稍後由多個遊戲渠道中獲得。至於怎樣獲取, 及相關的時間設定是多少, 將會視乎新設定實裝後的玩家反應再作調整。

## 数据来源

- 原始语料整理（无对应 SDE 条目）
