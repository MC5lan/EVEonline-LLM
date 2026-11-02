---
id: canon-7042651443
title: zh_dev_blog_and_patchnote_details_on_forthcoming_improvements_to_compression_mechanics
domain: 09_百科与资料
subdomain: 
type: canonical
status: drafted
sde_build: 3662168 / 2026-10-30
verified: 2026-11-01
origin: corpus\09_百科与资料\zh_dev_blog_and_patchnote_details_on_forthcoming_improvements_to_compression_mechanics.md
---
# zh_dev_blog_and_patchnote_details_on_forthcoming_improvements_to_compression_mechanics

## zh_dev_blog_and_patchnote_details_on_forthcoming_improvements_to_compression_mechanics

<jumbotron> --------

## 壓縮機制改善詳情

-----\\原文鏈接: </jumbotron> <fs x-large>大家好</fs> 如前天公佈的 Fanfest 展望 所述, 壓縮工序將會向團體採礦方式方向改變。Rorqual (長鬚鯨級) , Orca (逆戟鯨級), Porpoise (海豚級) 將有新的就地壓縮裝備, 以及氣雲和月礦亦能夠壓縮。帖文將詳述細節。 <fs x-large>先來一個 tl;dr</fs> *全新簡化的團隊就地壓礦方式。長鬚鯨、逆戟鯨和海豚級可攜帶一種「Shipboard Compression Technology (

## 全文脉络（等距抽样）

- # zh_dev_blog_and_patchnote_details_on_forthcoming_improvements_to_compression_mechanics
- 如前天公佈的 Fanfest 展望 所述, 壓縮工序將會向團體採礦方式方向改變。Rorqual (長鬚鯨級) , Orca (逆戟鯨級), Porpoise (海豚級) 將有新的就地壓縮裝備, 以及氣雲和月礦亦能夠壓縮。帖文將詳述細節。
- <fs x-large>先來一個 tl;dr</fs>  *全新簡化的團隊就地壓礦方式。長鬚鯨、逆戟鯨和海豚級可攜帶一種「Shipboard Compression Technology (艦載壓縮技術)」支援裝備，容許附近艦隊成員直接在自己的船倉裏壓縮資源。配合適當的裝備和技能, 遙距壓礦支援可以延伸至超過 200km。  *月礦和氣雲也可以壓縮。包括礦石和冰礦, 壓縮資源將會變得更容易。只要你艦隊有艦船攜帶合適壓縮模組, 你就可以直接在自己的船倉上壓縮。  *壓縮模組需要
- 調整的核心概念是「艦隊的壓縮支援功能」: 透過艦隊中裝有 Shipboard Compression Technology (艦載壓縮技術) 裝備的工業指揮艦(長鬚鯨、逆戟鯨、海豚), 艦隊所有成員都可以壓縮自己的資源。這裝備解鎖艦隊成員的資源壓縮功能。包括指揮艦自己, 所有艦隊成員在指揮艦附近都可以在太空中進行資源壓縮。在自己艦倉選取礦石, 就能直接轉換成壓縮版本。
- 這個壓縮模組需要激活中的工業核心來維持。除了大家要身處同一個艦隊以及在範圍內, 並沒有其他船種/角色的限制。壓縮模組激活時只耗電容, 不耗用燃料。
- ^ ^小行星礦石^冰礦^氣雲^基腹斷岩^衞星礦石^ |Rorqual (長鬚鯨) |旗艦級小行星礦石壓縮機|旗艦級冰礦壓縮機|旗艦級氣雲壓縮機|旗艦級基腹斷岩壓縮機|旗艦級衞星礦石壓縮機| |Orca (逆戟鯨)| 大型小行星礦石壓縮機|大型冰礦壓縮機|大型氣雲壓縮機|大型基腹斷岩壓縮機|大型衞星礦石壓縮機| |Porpoise (海豚)| 中型小行星礦石壓縮機| |中型氣雲壓縮機| | |
- *Shipboard Compression Technology (艦載壓縮技術) - 所有中型及大型壓縮裝備需求(每級解鎖一種)  *Capital Shipboard Compression Technology(旗艦級艦載壓縮技術) - 旗艦級壓縮裝備需求(每級解鎖一種)  *Fleet Compression Logistics(艦隊資源壓縮) - 增加壓縮模組的作用範圍 (每級+10%)
- ^ ^壓縮機尺寸^基礎距離(km)^技能等級5時(km)^ |Rorqual (長鬚鯨) |XL|144|216| |Orca (逆戟鯨)|L|83|125| |Porpoise (海豚)|M|44|66|
- 資源在壓縮前後的數量, 將會改成1對1, 1單位未壓縮資源轉換成1單位已壓縮資源。這樣在比較體積和價值時會更直觀。體積的轉換也更簡單明瞭, 比例如下:
- ^資源^壓縮前後數量比例^壓縮前後體積比例^ |小行星礦石|1:1|100:1| |衞星礦石|1:1|100:1| |冰礦|1:1|10:1| |氣雲|1:1|10:1|
- 每一種普礦、冰礦、月礦和氣雲都會新增一種壓縮版本。新版本的壓縮資源和原本的精煉方式一模一樣, 所需份量也一模一樣。
- 壓縮普礦、冰礦和月礦是沒有損耗的。壓縮版本和未壓縮版本的精煉產出完全相同。(氣雲壓縮則是有損的, 詳情後述)
- 原有的壓縮礦因為和這次的壓縮比例, 而要重新命名成另一款物品, 舊有的壓縮礦將會同時存在, 並且按照原有的方式運作及一樣的產出。只是將無法再獲得舊的壓縮礦石。隨著我們觀察原有壓縮礦石的存量, 日後將把剩餘壓縮礦的轉換成新式壓縮礦。
- 氣雲和冰/礦有點不同, 是不需要精煉就能直接於製造使用。壓縮氣雲不能直接用於製造。因此只有氣雲多了一個解壓縮的過程才能用來製造。這個解壓過程是有損耗的, 用來類比礦石精煉時的損失。
- 精煉廠會加上新的氣雲解壓效率加成。另外也有新的技能 Gas Decompression Efficiency (氣雲解壓縮效率研究), 進一步提升效率。可是 100% 解壓效率是不可能的, 玩家要在運輸便利和資源產出兩方便取捨。
- 壓縮氣雲可以在任何一個裝有 Standup Reprocessing Facility (屹立提煉設施) 的建築中解壓縮。精煉廠的效率是最高的, 而空間站則不能將氣體解壓。
- |基礎氣雲解壓縮效率|80%| |Athanor (阿塔諾) 氣雲解壓縮加成|+4%| |Tatara (塔塔拉)氣雲解壓縮加成|+10%| |氣雲解壓縮效率研究 (5級)|+5%| |最大氣雲解壓縮效率 (塔塔拉+技能等級5)|95%|
- <fs x-large>海豚級 - 新的「中型工業核心」裝備和一些屬性改動</fs>
- 它和現有的大型和旗艦級型號用法差不多: 艦船被固定, 增加無人機開採效率, 增加指揮脈衝強度和範圍。文末有詳細數值
- 海豚級船體移除了無人機開採量的特殊加成, 而工業指揮艦裏的冰礦無人機循環時間加成將由每級 10% 減半至每級 5%。失去的加成將移至中型工業核心上。
- 逆戟鯨級的燃料倉由 5,000 m³ 增加至 6,400 m³。這樣可以在使用工業核心來運行壓縮模組時更方便.
- 部份採礦船在某妥當裝配時, 開採效率相當高。這開採量高得使投棄集裝箱的冷卻時間會造成瓶頸。有見及此, 投棄集裝箱的容量由目前 27,500 m³ 增加至 55,000 m³.
- 在裝有屹立提煉設施的建築內, 可以繼續壓縮普礦和冰礦。建築內不能壓縮氣雲和月礦, 它們只能在透過新壓縮模組, 在太空中進行。
- 隨住POS的退役計劃, 加上以上改動，POS壓縮陣列將會失效。這陣列將不能進行資源壓縮。仍然在太空的的陣列可以解錨和精煉至原來材料。
- 工業重配置技術 - Industrial Reconfiguration (現有技能)  *SP乘數: 4x  *技能書價格: 20,000,000  *等級1:  *中型工業核心 I  *大型工業核心 I (現有裝備)  *艦載壓縮技術 - Shipboard Compression Technology  *等級4:  *中型工業核心 II  *等級5:  *大型工業核心 II (現有裝備)
- 艦載壓縮技術 - Shipboard Compression Technology  *SP乘數: 3x  *技能書價格: 150,000,000  *前置需求:  *工業重配置技術 - Industrial Reconfiguration  *等級1:  *中型小行星礦石壓縮機 I  *大型小行星礦石壓縮機 I  *等級2:  *大型冰礦石壓縮機 I  *等級3:  *中型氣雲壓縮機 I  *大型氣雲壓縮機 I  *等級4:  *大型基腹斷岩壓縮機 I  *旗艦級艦載壓縮技
- 旗艦級艦載壓縮技術 - Capital Shipboard Compression Technology  *SP乘數: 3x  *技能書價格: 150,000,000  *前置需求:  *旗艦級工業重配置技術 I - Capital Industrial Reconfiguration I  *艦載壓縮技術 IV - Shipboard Compression Technology IV  *等級1:  *旗艦級小行星礦石壓縮機 I  *等級2:  *旗艦級冰礦石壓縮機 I
- 氣雲解壓縮效率研究 - Gas Decompression Efficiency  *SP乘數: 2x  *技能書價格: 75,000,000  *前置需求:  *艦載壓縮技術 III - Shipboard Compression Technology III  *每級 +1% 氣雲解壓縮效率
