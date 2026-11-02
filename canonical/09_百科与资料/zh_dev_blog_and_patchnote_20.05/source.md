# zh_dev_blog_and_patchnote_20.05

<jumbotron>

====== EVE Online 20.05 版本更新總結 ======

<image shape="circle">作者: Rabbit P MuraSaki Siki</image>\\官网公告链接: Patch Notes For 20.05 Release \\

</jumbotron>

🤝- 標注爲玩家反饋或建議的調整

------

(16/6)

===== 活動 =====Gallente Federation Day 活動開始。活動期至 28/6。
 *Federation Grand Prix 復刻。起點爲 Luminaire 的 Gallente Prime。
 *活動挑戰玩家到新伊甸各處名勝打卡。有三條不同路線供玩家挑戰。
 *首次完成 Grand Prix 路線並不計時, 並解鎖所有活動獎勵, 包括 Luminaire Zenith SKINs, Quafe Zero, Grand Prix 增效劑, 及新競賽服飾。
 *首次完成 Grand Prix 路線後, 玩家可以參與競速賽。
 *三條路線各自計算時間最快完成的頭10名玩家, 其名字會被添加至 Luminaire 的地標描述中。
 *第一條路線完全在高安星系, 第二及第三條路線需要玩家穿越低安星系, 或經 0.0 星系通過。
 *注意, 路線上或者會有玩家於星門或其他地方駐紥攻擊或以立體炸彈攻擊其他玩家。參賽者有可能損失艦船。要完成這些路線, 玩家或需要仔細的規劃及熟練躲避其他危險。
 *活動每日登錄獎勵包括技能點, SKIN, 煙花, 特殊 Gallente Federation Day 專家系統供所有玩家駕駛蓋倫特艦船。
 *蓋倫特星域會有特殊躍遷速度加成。
 *Federation Navy parades 可以於 Luminaire, Villore, Dodixie, Lirsautton, Alentene, Orvolle, Octanneve 星系找到。玩家可以前往這些星系對目標發射煙花以獲得每日技能點獎勵。
 *爲慶祝聯邦日, 新式蓋倫特工業艦 Strategic Materiel Defender SKIN 將添加至 Federal Strategic Materiel 忠誠點商店。
 *Ratillose 星系添加新蓋倫特地標。
 *特殊 Gallente Federation Day 深淵競賽於 24/6 - 27/6 舉辨, 形式爲 Thorax（托勒克斯級）混戰。

----------

(17/5)
 *廣告版輪轉廣告中加入玩家舉辦的 Anger Games 5 比賽宣傳。

------

===== 建築 & 部署 =====Upwell 建築就建築增強機制有兩大重要調整。而 FLEX 及 NPC 建築維持不變。
 *所有 Upwell 建築的護盾傷害上限移除。
 *建築的屬性頁面上仍然能找到 "護盾每秒傷害上限", 但這數值是高於建築的護盾上限。
 *在沒有傷害上限限制下, 只要有足夠火力, 玩家將可極快地掃除建築護盾。
 *中型 Upwell 建築的結構增強階段移除。這代表中型建築在被清除護盾後將只有最多一次增強階段。在增強結束並再次清除建築裝甲後, 建築將會直接進入結構可被攻擊狀態, 進攻方可繼續進攻結構。

建築的最短裝甲增強時間將調整如下:

^建築規模^蟲洞未知星系^0.0 星系^低安星系^高安星系^
|中型|2.5日 +/- 1.5小時|3.5日 +/- 1.5小時|3.5日 +/- 1.5小時|4.5日 +/- 1.5小時|
|大型|24小時 +/- 3小時|24小時 +/- 3小時|24小時 +/- 3小時|24小時 +/- 3小時|
|FLEX|N/A|沒有|N/A|N/A|

 *戰爭總部建築的結構增強時間爲 24小時。若爲中型建築, 此 24小時爲裝甲增強時間。

建築的最短結構增強時間將調整如下:

^建築規模^蟲洞未知星系^0.0 星系^低安星系^高安星系^
|中型|沒有|沒有|沒有|沒有|
|大型|1.5日 +/- 3小時|2.5日 +/- 3小時|2.5日 +/- 3小時|4.5日 +/- 3小時|
|FLEX|N/A|至少30分鐘后的下一个窗口期 +/- 30分鐘|N/A|N/A|

>與玩家商討後, CCP 決定讓中型建築在蟲洞未知星系, 故土星系, 低安, 0.0 星系的增強時間增加 24小時。CCP 亦有聆聽到玩家就退出增強的 +/- 隨機時數的關注, 所以將中型建築的裝甲增強隨機 +/- 時數由 3小時減少至 1.5小時。

Upwell 建築的 HP 量相應調整:
 *所有中型 Upwell 建築護盾量增加 100%。

^建築^護盾值^
|Astrahus| 3,600,000|
|Raitaru| 2,400,000|
|Athanor| 2,400,000|

 *所有大型及超大型 Upwell 建築護盾量增加 25%。

^建築^護盾值^
|Fortizar| 6,750,000|
|Keepstar| 33,750,000|
|Azbel| 4,500,000|
|Sotiyo| 22,500,000|
|Tatara| 4,500,000|
|'Draccous' Fortizar| 6,750,000|
|'Horizon' Fortizar| 10,125,000|
|'Marginis' Fortizar| 6,750,000|
|'Prometheus' Fortizar| 10,125,000|
|Upwell Palatine Keepstar| 67,500,000|

 *所有中型 Upwell 建築結構量下調 75%。

^建築^結構值^
|Astrahus| 1,800,000|
|Raitaru| 1,200,000|
|Athanor| 1,200,000|

===== 裝備 =====
 *Standup Point Defense Battery (屹立定點防禦炮塔) 將需要裝填 Standup Flak Round I 才能使用。

===== 技術 =====
 *MacOS 客戶端可以使用技能規劃系統。

===== UI =====
 *壓縮 & 解壓縮 視窗在完成操作時加添小量動畫效果。

===== 科研 & 工業 =====數款有關製造勢力艦船, 旗艦, 超級旗艦的組件的製造需求調整。
 *以下藍圖的每流程產出數目上調:
 *Life Support Backup Unit (生命保障備份裝置) 產出數目由 1 上調至 3。
 *Auto-Integrity Preservation Seal (自動修復儲藏裝置密封) 產出數目由 1 上調至 3。
 *以下藍圖的每流程材料需求下調:

^組件^材料需求調整項目^
|Core Temperature Regulator (核心溫度調節器)| Water (水) : 由 1250 下調至 100|
|Capital Core Temperature Regulator (旗艦核心溫度調節器)| 核心溫度調節器 : 由 250 下調至 70|
|Programmable Purification Membrane (可編程淨化薄膜)| Hermetic Membranes (密封薄膜) : 由 350 下調至 100|
|:::| Gel-Matrix Biopaste (凝膠基質生物膠) : 由 1000 下調至 300|
|Neurolink Protection Cell (神經鏈接防護單元)| Miniature Electronics (微型電子元件) : 由 2000 下調至 100|
|:::| Genetic Safeguard Filter (基因保護過濾裝置) : 由 20 下調至 5|

-----<fs x-large>勢力艦船, 旗艦, 超級旗艦藍圖的製造材料需求調整。</fs>
 *艦船回收精煉產出已按新製造需求調整。

<fs large>護衛艦</fs>
 *Life Support Backup Unit (生命保障備份裝置) 及 Auto-Integrity Preservation Seal (自動修復儲藏裝置密封) 需求下調
 *Damavik (達瑪維克級) 材料需求由 10/20 下調至 5/10。
 *Skybreaker (破天級) 材料需求由 10/20 下調至 5/10。
 *Kikimora (奇奇莫拉級) 材料需求由 20/40 下調至 10/20。

-----

<fs large>巡洋艦</fs>
 *Life Support Backup Unit (生命保障備份裝置) 及 Auto-Integrity Preservation Seal (自動修復儲藏裝置密封) 需求下調
 *Rodiva (洛迪瓦級) 材料需求由 75/150 下調至 19/30。
 *Vedmak (維德馬克級) 材料需求由 100/200 下調至 25/50。
 *Stormbringer (喚風級) 材料需求由 100/200 下調至 25/50。
 *Stratios (斯特修斯級) 材料需求由 66/132 下調至 33/66。
 *海盜勢力巡洋艦 材料需求由 60/120 下調至 30/60。
 *海軍勢力巡洋艦 材料需求由 50/100 下調至 25/50。
 *Trigger Neurolink Conduit (觸發式神經鏈接回路) 的需求由 10 下調至 4。

-----

<fs large>戰列巡洋艦</fs>
 *Life Support Backup Unit (生命保障備份裝置) 及 Auto-Integrity Preservation Seal (自動修復儲藏裝置密封) 需求下調
 *Drekavac (德雷卡瓦級) 材料需求由 220/440 下調至 55/110。
 *海軍勢力戰列巡洋艦 材料需求由 100/200 下調至 50/100。
 *Trigger Neurolink Conduit (觸發式神經鏈接回路) 的需求由 20 下調至 8。

-----

<fs large>戰列艦</fs>
 *Life Support Backup Unit (生命保障備份裝置) 及 Auto-Integrity Preservation Seal (自動修復儲藏裝置密封) 需求下調
 *Thunderchild (雷裔級) 材料需求由 400/800 下調至 100/200。
 *Leshak (勒沙克級) 材料需求由 440/880 下調至 110/220。
 *Nestor (涅斯托級) 材料需求由 264/528 下調至 132/264。
 *海盜勢力戰列艦 材料需求由 240/480 下調至 120/240。
 *海軍勢力戰列艦 材料需求由 200/400 下調至 100/200。
 *Trigger Neurolink Conduit (觸發式神經鏈接回路) 的需求由 50 下調至 16。

-----

<fs large>工業艦及貨艦</fs>
 *Life Support Backup Unit (生命保障備份裝置) 及 Auto-Integrity Preservation Seal (自動修復儲藏裝置密封) 需求下調
 *Orca (逆戟鯨級) 材料需求由 400/800 下調至 100/200。
 *所有其他貨艦, 包括 Bowhead (弓頭鯨級) 材料需求由 800/1600 下調至 200/400。
 *Orca (逆戟鯨級) 的 Core Temperature Regulator (核心溫度調節器) 需求由 50 下調至 25。
 *Tech 1 貨艦的 Trigger Neurolink Conduit (觸發式神經鏈接回路) 需求由 50 下調至 16。
 *跳躍貨艦的 Trigger Neurolink Conduit (觸發式神經鏈接回路) 需求由 100 下調至 32。

-----

<fs large>旗艦級工業艦</fs>
 *Rorqual (長鬚鯨級) 的 Life Support Backup Unit (生命保障備份裝置) 及 Auto-Integrity Preservation Seal (自動修復儲藏裝置密封) 需求由 800/1600 下調至 200/400。
Rorqual (長鬚鯨級) 所有旗艦級材料需求下調, 除了 Capital Core Temperature Regulator (旗艦級核心温度調節器) 需求維持 1 不變。
 *Capital Propulsion Engine (旗艦推進引擎) 由 9 下調至 5
 *Capital Sensor Cluster (旗艦感應器組) 由 9 下調至 5
 *Capital Armor Plates (旗艦附甲) 由 7 下調至 5
 *Capital Capacitor Battery (旗艦電容器電池) 由 11 下調至 10
 *Capital Power Generator (旗艦發電機組) 由 11 下調至 10
 *Capital Shield Emitter (旗艦護盾發射器) 由 9 下調至 5
 *Capital Jump Drive (旗艦跳躍引擎) 由 11 下調至 10
 *Capital Drone Bay (旗艦無人機掛倉) 由 6 下調至 5
 *Capital Computer System (旗艦計算機系統) 由 33 下調至 30
 *Capital Construction Parts (旗艦建設構件) 由 44 下調至 40
 *Capital Clone Vat Bay (旗艦克隆艙) 由 33 下調至 30
 *Capital Ship Maintenance Bay (旗艦船只維護倉) 由 33 下調至 15
 *Capital Corporate Hangar Bay (旗艦聯合機庫艙) 由 17 下調至 15
 *Capital Cargo Bay (旗艦貨櫃艙) 由 22 下調至 20

-----

<fs large>航空母艦</fs>
 *航空母艦 的 Life Support Backup Unit (生命保障備份裝置) 及 Auto-Integrity Preservation Seal (自動修復儲藏裝置密封) 需求由 800/1600 下調至 200/400。
 *航空母艦 的 Trigger Neurolink Conduit (觸發式神經鏈接回路) 需求由 100 下調至 32。
 *航空母艦 的 Interlink Communicator (鏈接通信器) 需求由 5 下調至 2。

-----

<fs large>無畏艦</fs>
 *包括勢力無畏艦 及 Zirnitra (澤尼塔級), 無畏艦的 Life Support Backup Unit (生命保障備份裝置) 及 Auto-Integrity Preservation Seal (自動修復儲藏裝置密封) 需求下調至 200/400。
 *無畏艦 的 Trigger Neurolink Conduit (觸發式神經鏈接回路) 需求由 100 下調至 16。
 *勢力無畏艦 的 Trigger Neurolink Conduit (觸發式神經鏈接回路) 需求由每款 100 下調至 8。
 *無畏艦 的 Interlink Communicator (鏈接通信器) 需求由 5 下調至 2。

無畏艦 所有旗艦級材料需求下調, 除了 Capital Core Temperature Regulator (旗艦級核心温度調節器) 及 Neurolink Protection Cell (神經鏈接防護單元) 需求維持 1 不變。

非勢力無畏艦 及 Zirnitra (澤尼塔級) 調整如下:
 *Capital Propulsion Engine (旗艦推進引擎) 由 10 下調至 5
 *Capital Turret Hardpoint (旗艦炮台掛點)/Launcher Hardpoint (發射器安裝座) 由 50 下調至 20
 *Capital Capacitor Battery (旗艦電容器電池) 由 7 下調至 2
 *Capital Power Generator (旗艦發電機組) 由 5 下調至 2
 *Capital Jump Drive (旗艦跳躍引擎) 由 10 下調至 2
 *Capital Construction Parts (旗艦建設構件) 由 13 下調至 2
 *Capital Ship Maintenance Bay (旗艦船只維護倉) 由 16 下調至 5
 *Capital Corporate Hangar Bay (旗艦聯合機庫艙) 由 8 下調至 2
 *Capital Siege Array (旗艦會戰能源陣列) 由 45 下調至 20

Phoenix (鳯凰級):
 *Capital Sensor Cluster (旗艦感應器組) 由 10 下調至 2
 *Capital Armor Plates (旗艦附甲) 由 4 下調至 2
 *Capital Shield Emitter (旗艦護盾發射器) 由 20 下調至 5
 *Capital Computer System (旗艦計算機系統) 由 20 下調至 4

Naglfar (納迦法級)
 *Capital Sensor Cluster (旗艦感應器組) 由 10 下調至 2
 *Capital Armor Plates (旗艦附甲) 由 10 下調至 3
 *Capital Shield Emitter (旗艦護盾發射器) 由 14 下調至 4
 *Capital Computer System (旗艦計算機系統) 由 20 下調至 4

Moros (莫洛級)
 *Capital Sensor Cluster (旗艦感應器組) 由 20 下調至 4
 *Capital Armor Plates (旗艦附甲) 由 14 下調至 2=4
 *Capital Shield Emitter (旗艦護盾發射器) 由 10 下調至 3
 *Capital Computer System (旗艦計算機系統) 由 10 下調至 2

Revelation (神示級)
 *Capital Sensor Cluster (旗艦感應器組) 由 20 下調至 4
 *Capital Armor Plates (旗艦附甲) 由 20 下調至 5
 *Capital Shield Emitter (旗艦護盾發射器) 由 4 下調至 2
 *Capital Computer System (旗艦計算機系統) 由 10 下調至 2

Caiman (凱門鰐級)
 *Capital Propulsion Engine (旗艦推進引擎) 由 8 下調至 5
 *Capital Sensor Cluster (旗艦感應器組) 由 7 下調至 4
 *Capital Armor Plates (旗艦附甲) 由 8 下調至 5
 *Capital Capacitor Battery (旗艦電容器電池) 由 8 下調至 2
 *Capital Power Generator (旗艦發電機組) 由 7 下調至 2
 *Capital Shield Emitter (旗艦護盾發射器) 由 31 下調至 5
 *Capital Jump Drive (旗艦跳躍引擎) 由 10 下調至 2
 *Capital Computer System (旗艦計算機系統) 由 14 下調至 4
 *Capital Construction Parts (旗艦建設構件) 由 16 下調至 4
 *Capital Launcher Hardpoint (發射器安裝座) 由 44 下調至 20
 *Capital Ship Maintenance Bay (旗艦船只維護倉) 由 18 下調至 5
 *Capital Corporate Hangar Bay (旗艦聯合機庫艙) 由 10 下調至 2
 *Capital Siege Array (旗艦會戰能源陣列) 由 33 下調至 20

Chemosh (基抹級)
 *Capital Propulsion Engine (旗艦推進引擎) 由 8 下調至 5
 *Capital Turret Hardpoint (旗艦炮台掛點) 由 44 下調至 20
 *Capital Sensor Cluster (旗艦感應器組) 由 7 下調至 4
 *Capital Armor Plates (旗艦附甲) 由 31 下調至 5
 *Capital Capacitor Battery (旗艦電容器電池) 由 8 下調至 2
 *Capital Power Generator (旗艦發電機組) 由 16 下調至 2
 *Capital Shield Emitter (旗艦護盾發射器) 由 9 下調至 5
 *Capital Jump Drive (旗艦跳躍引擎) 由 11 下調至 2
 *Capital Computer System (旗艦計算機系統) 由 7 下調至 4
 *Capital Construction Parts (旗艦建設構件) 由 16 下調至 4
 *Capital Ship Maintenance Bay (旗艦船只維護倉) 由 19 下調至 5
 *Capital Corporate Hangar Bay (旗艦聯合機庫艙) 由 10 下調至 2
 *Capital Siege Array (旗艦會戰能源陣列) 由 33 下調至 20

Vehement (猛烈級)
 *Capital Propulsion Engine (旗艦推進引擎) 由 98 下調至 90
 *Capital Turret Hardpoint (旗艦炮台掛點) 由 518 下調至 500
 *Capital Sensor Cluster (旗艦感應器組) 由 84 下調至 80
 *Capital Armor Plates (旗艦附甲) 由 336 下調至 300
 *Capital Capacitor Battery (旗艦電容器電池) 由 98 下調至 90
 *Capital Power Generator (旗艦發電機組) 由 182 下調至 180
 *Capital Shield Emitter (旗艦護盾發射器) 由 154 下調至 150
 *Capital Jump Drive (旗艦跳躍引擎) 由 112 下調至 110
 *Capital Computer System (旗艦計算機系統) 由 84 下調至 80
 *Capital Construction Parts (旗艦建設構件) 由 182 下調至 180
 *Capital Ship Maintenance Bay (旗艦船只維護倉) 由 224 下調至 220
 *Capital Corporate Hangar Bay (旗艦聯合機庫艙) 由 112 下調至 110
 *Capital Siege Array (旗艦會戰能源陣列) 由 392 下調至 390

Zirnitra (澤尼塔級)
 *Capital Propulsion Engine (旗艦推進引擎) 由 15 下調至 4
 *Capital Turret Hardpoint (旗艦炮台掛點) 由 30 下調至 5
 *Capital Sensor Cluster (旗艦感應器組) 由 7 下調至 2
 *Capital Armor Plates (旗艦附甲) 由 30 下調至 5
 *Capital Capacitor Battery (旗艦電容器電池) 由 7 下調至 2
 *Capital Power Generator (旗艦發電機組) 由 5 下調至 2
 *Capital Shield Emitter (旗艦護盾發射器) 由 15 下調至 2
 *Capital Jump Drive (旗艦跳躍引擎) 由 10 下調至 2
 *Capital Computer System (旗艦計算機系統) 由 15 下調至 4
 *Capital Construction Parts (旗艦建設構件) 由 13 下調至 2
 *Capital Ship Maintenance Bay (旗艦船只維護倉) 由 16 下調至 5
 *Capital Corporate Hangar Bay (旗艦聯合機庫艙) 由 18 下調至 2
 *Capital Siege Array (旗艦會戰能源陣列) 由 45 下調至 20

-----

<fs large>戰力輔助艦</fs>
 *包括勢力型號, 戰力輔助艦的 Life Support Backup Unit (生命保障備份裝置) 及 Auto-Integrity Preservation Seal (自動修復儲藏裝置密封) 需求下調至 200/400。
 *戰力輔助艦 的 Trigger Neurolink Conduit (觸發式神經鏈接回路) 需求由 75 下調至 32。
 *勢力無畏艦 的 Trigger Neurolink Conduit (觸發式神經鏈接回路) 需求由每款 72 下調至 16。

-----

<fs large>超級航空母艦</fs>
 *包括 Revenant (歸魂者級) 和 Vendetta (仇恨級), 超級航空母艦的 Life Support Backup Unit (生命保障備份裝置) 及 Auto-Integrity Preservation Seal (自動修復儲藏裝置密封) 需求下調至 400/800。
 *超級航空母艦 的 Capital Core Temperature Regulator (旗艦核心溫度調節器) 需求由 15 下調至 10。
 *超級航空母艦 的 Trigger Neurolink Conduit (觸發式神經鏈接回路) 需求由 250 下調至 64。
 *Revenant (歸魂者級) 和 Vendetta (仇恨級) 的 Trigger Neurolink Conduit (觸發式神經鏈接回路) 需求由每款 250 下調至 32。
 *超級航空母艦 的 Interlink Communicator (鏈接通信器) 需求由每款 250 下調至 125。
 *Vendetta (仇恨級) 的 Interlink Communicator (鏈接通信器) 需求由每款 250 下調至 75。

<fs large>泰坦</fs>
 *包括勢力型號, 泰坦的 Life Support Backup Unit (生命保障備份裝置) 及 Auto-Integrity Preservation Seal (自動修復儲藏裝置密封) 需求下調至 800/1600。
 *泰坦 的 Capital Core Temperature Regulator (旗艦核心溫度調節器) 需求由 40 下調至 20。
 *泰坦 的 Trigger Neurolink Conduit (觸發式神經鏈接回路) 需求由 500 下調至 128。
 *Komodo (科莫多級), Vanquisher (征服者級) 和 Molok (摩格克級) 的 Trigger Neurolink Conduit (觸發式神經鏈接回路) 需求由每款 500 下調至 64。
 *泰坦 的 Interlink Communicator (鏈接通信器) 需求由每款 500 下調至 250。

多數泰坦的旗艦級組件需求下調。

非勢力泰坦調整如下:
 *Capital Propulsion Engine (旗艦推進引擎) 由 100 下調至 80
 *Capital Jump Drive (旗艦跳躍引擎) 由 400 下調至 300
 *Capital Clone Vat Bay (旗艦克隆艙) 由 556 下調至 500
 *Capital Doomsday Weapon Mount (旗艦末日武器安裝位) 由 556 下調至 500
 *Capital Ship Maintenance Bay (旗艦船只維護倉) 由 556 下調至 500
 *Capital Corporate Hangar Bay (旗艦聯合機庫艙) 由 556 下調至 500
 *Capital Jump Bridge Array (旗艦跳躍橋接陣列) 由 556 下調至 500

Komodo (科莫多級)
 *Capital Propulsion Engine (旗艦推進引擎) 由 100 下調至 50
 *Capital Launcher Hardpoint (發射器安裝座) 由 600 下調至 300
 *Capital Sensor Cluster (旗艦感應器組) 由 600 下調至 300
 *Capital Armor Plates (旗艦附甲) 由 200 下調至 100
 *Capital Capacitor Battery (旗艦電容器電池) 由 500 下調至 250
 *Capital Power Generator (旗艦發電機組) 由 100 下調至 50
 *Capital Shield Emitter (旗艦護盾發射器) 由 600 下調至 300
 *Capital Jump Drive (旗艦跳躍引擎) 由 600 下調至 300
 *Capital Construction Parts (旗艦建設構件) 由 400 下調至 200
 *Capital Computer System (旗艦計算機系統) 由 600 下調至 300
 *Capital Clone Vat Bay (旗艦克隆艙) 由 700 下調至 635
 *Capital Doomsday Weapon Mount (旗艦末日武器安裝位) 由 700 下調至 635
 *Capital Ship Maintenance Bay (旗艦船只維護倉) 由 700 下調至 635
 *Capital Corporate Hangar Bay (旗艦聯合機庫艙) 由 700 下調至 635
 *Capital Jump Bridge Array (旗艦跳躍橋接陣列) 由 700 下調至 635

Vanquisher (征服者級)
 *Capital Propulsion Engine (旗艦推進引擎) 由 1260 下調至 1200
 *Capital Turrent Hardpoint (旗艦炮台掛點) 由 4750 下調至 4500
 *Capital Armor Plates (旗艦附甲) 由 3465 下調至 3400
 *Capital Capacitor Battery (旗艦電容器電池) 由 1260 下調至 1200
 *Capital Power Generator (旗艦發電機組) 由 1890 下調至 1800
 *Capital Shield Emitter (旗艦護盾發射器) 由 1575 下調至 1500
 *Capital Jump Drive (旗艦跳躍引擎) 由 1260 下調至 1200
 *Capital Construction Parts (旗艦建設構件) 由 1890 下調至 1800
 *Capital Computer System (旗艦計算機系統) 由 630 下調至 600
 *Capital Jump Bridge Array (旗艦跳躍橋接陣列) reduced to 620 (previously 670)

Molok (摩格克級)
 *Capital Propulsion Engine (旗艦推進引擎) 由 200 下調至 100
 *Capital Turret Hardpoint (旗艦炮台掛點) 由 600 下調至 300
 *Capital Sensor Cluster (旗艦感應器組) 由 400 下調至 200
 *Capital Armor Plates (旗艦附甲) 由 600 下調至 300
 *Capital Capacitor Battery (旗艦電容器電池) 由 600 下調至 300
 *Capital Power Generator (旗艦發電機組) 由 600 下調至 300
 *Capital Shield Emitter (旗艦護盾發射器) 由 100 下調至 50
 *Capital Jump Drive (旗艦跳躍引擎) 由 600 下調至 300
 *Capital Construction Parts (旗艦建設構件) 由 500 下調至 250
 *Capital Computer System (旗艦計算機系統) 由 400 下調至 200
 *Capital Clone Vat Bay (旗艦克隆艙) 由 670 下調至 620
 *Capital Doomsday Weapon Mount (旗艦末日武器安裝位) 由 670 下調至 620
 *Capital Ship Maintenance Bay (旗艦船只維護倉) 由 670 下調至 620
 *Capital Corporate Hangar Bay (旗艦聯合機庫艙) 由 670 下調至 620
 *Capital Jump Bridge Array (旗艦跳躍橋接陣列) 由 670 下調至 620