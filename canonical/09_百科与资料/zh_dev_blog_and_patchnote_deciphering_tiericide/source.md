# zh_dev_blog_and_patchnote_deciphering_tiericide

<jumbotron>

--------

====== 解構層級調整 ======

--------\\原文鏈接: Deciphering Tiericide

</jumbotron>

大家好,

隨着這年來對數款裝備進行了不同層級的調整後, 現在是時候的對老玩家作回顧, 以及對新玩家介紹這調整的目的及進展了。

-----

===== 甚麼是 "Tiericide (層級調整)" 呢? =====

"Tiericide" (層級調整) 是對於艦船及裝備進行平衡調整的一個計劃, 讓裝備能在各方面有不同的優點, 而不是單純的高階級裝備全面佔優。調整目的是確保各裝備的選擇更加有意義和特色，從而使玩家更容易發現並按照其所需定位, 裝備, 價格等選擇船或裝備。

在 Rebalancing EVE, One Module at a Time 帖文中, 已經講述了 Tiericide (層級調整) 的大綱。

在該款裝備進行層級的調整時, 玩家可以期待有以下調整:
 *部份裝備有特殊定位
 *初階裝備至高階裝備有清晰的提升過程
 *裝備命名的規範，清晰指示裝備的作用和功能
 *刪除或合併不再有意義的衍生型號

----

爲了展示層級調整其實是做了怎樣的數值調整, 以下我們舉個例子:

首先, 整款裝備所有數值會全面審視一遍, 區分甚麼是主要屬性, 甚麼是副屬性, 各級裝備的用量, 遊戲內的存量, 價格, 裝備性能的範圍及極限。這時候會決定那一些衍生型號會被移除, 或添加一些新型號, 以及各衍生型號的性能層階應當如何等。對於大多數裝備, 性能層階並不是純綷線性的, 而是在各屬性領域有不同的小組分佈。
裝備性能的主要指標是其 Meta Level (衍生等級)。一些裝備會有衍生等級數值的調整以使其配合其性能級別，另一些裝備則會調整其數值以配合其衍生等級，或者兩項一起調整。

最近進行層級調整的是 裝甲增強器。其分析過程如下:

裝甲增強器 分爲以下類別:
 *包括於此次層級調整
 *電磁裝甲增強器
 *爆炸裝甲增強器
 *動能裝甲增強器
 *熱能裝甲增強器
- <fs large>不包括</fs>於此次層級調整
 *反應式裝甲增強器 (因爲只有一款)
 *可腳本式裝甲增強器 (旗艦級彎曲裝甲增強器)

每個特定於傷害抵抗的型號都被劃分為不同的 Meta Levels，以標示其性能級別。

 *裝甲增強器的主要屬性是 傷害抗性
 *計算裝備性能級別需要考慮到抗性裝備數值並不直接加法地添加至艦船抗性中, 而是以考慮其實際所扣減的傷害前後比較。每一款裝備是以其能減輕多少傷害而不是單純的抗性數值來作調整。
 *例如艦船 88% 抗性比起原本 80% 抗性性能其實提升了不是 8%, 亦不是10%, 而是 40% 的性能 : (1 - 0.8 = 0.2; 1 - 0.88 = 0.12; (0.2 - 0.12) / 0.2 = 40%)。而所有不同衍生型號都會和最基礎 Meta Level 0 : 40% 抗性裝備作比較。

----

<fs x-large>Meta Level (衍生等級) 1 裝備</fs>
 *以下是各 衍生等級1 裝備所會用到的專精前綴:
 *Ample (充裕型) - 更大容量
 *Compact (緊湊型) - 更低裝配需求
 *Enduring (持久型) - 更低電容需求, 或更長循環時間
 *Restrained (抑制型) - 更低懲罰
 *Scoped (視野型) - 更遠作用距離
 *Upgraded (改良型) - 用於那些沒有能專精項目的裝備 (例如那些只有很少加成項數的裝備)
 *Precise (精準型) - 更佳跟踪速度
 *裝甲增強器只是對自身作用, 提供一項加成, 沒有懲罰, 亦不需要裝填彈藥。則只會用到兩款命名前綴 : 一款加強裝配的, 另一項則是加強使用的。
 *裝配 : 所有裝甲增強器只需要 1MW 能量柵格, 這不會有調整。而 CPU 需求則不同, 所以會調整其 CPU 用量以創建一款 Compact (緊湊型) 裝備。
 *目前的 Prototype (尖端型) 改名爲 Prototype Compact (尖端緊湊型)。因爲過往的 Limited (限量型) 的 CPU 需求較低, 所以將會合併至緊湊型內, 以避免以往裝配此裝備的艦船會因爲調整而變成超出裝配負荷。
 *使用 : 因爲裝備並不是只在激活那一剎那提供加成，而是在整個循環時間內持續提供加成, 所以啟用電容需求及循環時間將合併一起考慮。這代表裝備的循環時間愈長, 其使用負荷就愈低。而循環時間較長的缺點是無法頻繁啟用/停止超載。Enduring (持久型) 是使用專精的前綴。其超載損傷亦會有所增加, 讓整體每單位時間超載損傷與其他型號保持一致。
 *目前的 Experimental (實驗型) 改名爲 Experimental Enduring (實驗持久型), 而 Upgraded (改良型) 將會合併在內。
 *衍生等級1 的裝備抗性將會由 40% 提升至 42%, 使其主要性能介乎於 T1 衍生等級 0 (40%), 及 T2 - 衍生等級 5 (44%) 之間。
 *其調整哲學亦與更早前 護盾增強器 的調整一致。

裝備的命名應該準確反映裝備特色, 包括:
 *裝備種類 (裝甲增強器)
 *傷害抗性類別 (電磁/爆炸/動能/熱能)
 *衍生1的專項特性 (緊湊型 / 持久型)
 *其科幻特色 (尖端型 / 實驗型)
 *科技等級 (T1 / T2)
 *故按其衍生等級組合:
 *Tech I, 衍生 0 : 種類, 傷害抗性, 科技等級
 *Tech I, 衍生 1 : 種類, 傷害抗性, 科幻色彩, 專項特色
 *Tech II, 衍生 5 : 種類, 傷害抗性, 科技等級
 *勢力型, 衍生 8 : 種類, 傷害抗性, 出產勢力
 *死亡型 : 種類, 傷害抗性, 其死亡型號不同階級的標志以表明其衍生級別 (雙數)
 *衍生 10 : C 型
 *衍生 12 : B 型
 *衍生 14 : A 型
 *衍生 16 : X 型
 *官員型 : 種類, 傷害抗性, 官員名字。其官員名字亦表示其衍生等級 (單數)。該官員的裝備在其所有不同種類裝備中都代表了同樣的衍生等級，例如 : Draclira's (德拉克里雅氏) 改良型裝備衍生等級都是 17。
 *裝甲增強器只會由甲抗海盜勢力官員艦船掉落 : 血襲者 , 薩沙, 天蛇集團
 *衍生 11 : Tairei (泰瑞), Brokara (博卡拉), Brynn (布瑞恩)
 *衍生 13 : Raysere (莱塞勒), Selynne (瑟莱尼), Tuvan (图万)
 *衍生 15 : Ahremen (阿勒门), Vizan (威赞), Setele (塞特勒)
 *衍生 17 : Draclira (德拉克里雅), Chelm (切尔姆), Cormack (科尔马克)

----

官員與其衍生等級列表

^ 衍生等級 ^ 天使 ^ 血襲者 ^ 古斯塔斯 ^ 薩沙 ^ 天蛇 ^ 三神裔 ^
| 11 | Mizuro (米茲羅) | Tairei (泰瑞) | Kaikka (卡爾卡) | Brokara (博卡拉) | Brynn (布瑞恩) | |
| 13 | Hakim (哈科姆) | Raysere (萊塞勒) | Thon (托恩) | Selynne (瑟萊尼) | Tuvan (圖萬) | |
| 15 | Gotan (戈丹) | Ahremen (阿勒門) | Vepas (威帕斯) | Vizan (威贊) | Setele (塞特勒) | |
| 17 | Tobias (托比雅斯) | Draclira (德拉克里雅) | Estamel (埃斯塔梅爾) | Chelm (切爾姆) | ack (科爾馬克) | Zorya |

 *目前的命名方案 : Armor EM Hardener I (裝甲電磁增強器 I), Limited Armor EM Hardener (限量型裝甲電磁增強器), Khanid Navy Armor EM Hardener (卡尼迪海軍裝甲電磁增強器)
 *然而這並吻合其裝備類別, 因爲其傷害抗性類型加插在裝備種類中間
 *而例如 護盾增強器 則使用了以下方案 : EM Shield Hardener I (電磁護盾增強器), Domination EM Shield Hardener (主天使電磁護盾增強器)
 *所以裝甲增強器亦會按照此方案 : EM Armor Hardener I (電磁裝甲增強器 I), Enduring EM Armor Hardener (持久型電磁裝甲增強器), Khanid Navy EM Armor Hardener (卡尼迪海軍電磁裝甲增強器)
 *相關藍圖亦會一併調整

----

裝備技能需求 : T2 需求 Hull Upgrades (船體加固理論) V 級, 其餘 III 級, 沒有改動。

----

過往的衍生等級分級並不符合新規範, 故重新調整如下:
 *衍生 2, 3, 4 -> 1
 *勢力型衍生 9 -> 8
 *C 型死亡空間 衍生 11 -> 10
 *A 型死亡空間 衍生 13 -> 14
 *X 型死亡空間 衍生 14 -> 16
 *官員 衍生 12 -> 13
 *官員 衍生 13 -> 15
 *官員 衍生 14 -> 17

----

<fs x-large>勢力型裝備</fs>
 *以往的勢力型裝備有分爲兩小類
 *衍生 8 - Domination (主天使), Republic Fleet (共和艦隊) : 抗性加成較 T2 弱 (40%), 較高 CPU 需求, 低電容需求, 較爲稀有
 *衍生 9 - 抗性加成與 T2 一樣 (44%), 較低 CPU 需求, 一般電容需求, 比衍生 8 較爲常見
 *現在所有勢力型裝備都會統一設定爲 衍生等級 8, 並且有相同的主要屬性 : 抗性加成 44%
 *舊有 衍生 8 : 保留其超低的電容需求, 增加其循環時間以讓其電容消耗更低。同時維持其超載損傷爲 6.6, 這代表 主天使 及 共和艦隊 裝甲增強器的超載損傷將會較少。與之比較, 持久型裝備亦有循環時間的上調, 但其超載損傷亦有所上調, 使其超載損傷與其他型號保持一致。
 *舊有 衍生 8 : 亦保留其高 CPU 需求, 以平衡其相對於舊有 衍生 9 型的優勢。

----

<fs x-large>死亡空間及官員型裝備</fs>
 *以往這些裝備之間的性能並沒差別。官員型裝備從價格及數量上均體現出其是新伊甸中最爲稀有的裝備，但其性能與對應的死亡空間型號卻一樣。
 *現在在不同階級之間, 官員型號會較死亡空間型號提供較高抗性加成。之間的差異是較輕微及平緩的, 並沒有調整裝備性能的上限。
 *每往上數下一衍生爲死亡空間型號的話, 其經計算的有效抗性率會增加 1%
 *每往上數下一衍生爲官員型號裝備的話, 其經計算的有效抗性率會增加 1.5%
 *例子:
 *衍生 10 : Corpus(科波斯) 熱能裝甲增強器C型 : 熱能抗性 45.8%。其抗性效率相對於 T1 裝備(40%) 高 9.7%
 *衍生 11 : Brokara's (博卡拉氏) 改良型熱能裝甲增強器 : 熱能抗性 46.7%。其抗性效率相對於 T1 裝備(40%) 高 11.2%。較上一衍生等級的性能增加 11.2% - 9.7% = 1.5%。
 *衍生 12 : Corpus(科波斯) 熱能裝甲增強器B型 : 熱能抗性 47.3%。其抗性效率相對於 T1 裝備(40%) 高 12.2%。較上一衍生等級的性能增加 12.2% - 11.1% = 1%。
 *衍生 13 : Selynne's (瑟莱尼氏) 改良型熱能裝甲增強器 : 熱能抗性 48.2%。其抗性效率相對於 T1 裝備(40%) 高 13.7%。較上一衍生等級的性能增加 13.7% - 12.2% = 1.5%。

-----

過往衍生等級 0 裝備的體積爲 20m3, 其他則是 5m3。現統一設定爲 5m3。

以上分析是對156種裝甲增強器的名稱和屬性調整的基礎。當然還考慮了其他一些細微差別，但它們太淺白或太微不足道而不再詳述。

-----

===== 進展 =====

層級調整計劃於 2012年開始對艦船作調整, 而在 2014年開始對裝備作調整

<fs large>已經進行過層級調整的裝備如下:</fs>

| Armor Hardener (裝甲增強器) | Gyrostabilizer (回轉穩定器) | Remote Shield Booster (遠程護盾回充增量器) |
| Armor Plate (裝甲附甲板) | Heat Sink (散熱器) | Remote Tracking Computer (遠程索敵計算機) |
| Armor Repair Unit (裝甲維修器) | Inertial Stabilizer (慣性穩定器) | Sensor Booster (感應增強器) |
| Auxiliary Power Core (輔助能源核心) | Magnetic Field Stabilizer (磁性力場穩定器) | Sensor Dampener (感應抑阻器) |
| Ballistic Control system (彈道控制系統) | Mining Laser (採礦激光器) | Shield Booster (護盾回充增量器) |
| Burst Jammer (ECM 脈衝波) | Mining Upgrade (採礦改良設備) | Shield Extender (護盾擴展裝置) |
| Capacitor Battery (電容電池) | Missile Guidance Computer (導彈制導計算機) | Shield Flux Coil (護盾通量線圈) |
| Capacitor Booster (電容注電器) | Missile Guidance Enhancer (導彈制導增強器) | Shield Hardener (護盾增強器) |
| Capacitor Flux Coil (護盾通量線圈) | Missile Launcher Light (輕型導彈發射器) | Shield Power Relay (護盾能源繼電器) |
| Capacitor Power Relay (電容能源繼電器) | Missile Launcher Rapid Torpedo (快速魚雷發射器) | Shield Recharger (護盾回充器) |
| Capacitor Recharger (電容回充器) | Missile Launcher XL Cruise (超大型巡航導彈發射器) | Ship Scanner (船體掃描器) |
| Cargo Scanner (貨櫃掃描器) | Missile Launcher XL Torpedo (超大型魚雷發射器) | Signal Amplifier (信號放大器) |
| CPU Enhancer (CPU 升級模塊) | Nanofiber Internal Structure (納米纖維內部構架) | Stasis Grappler (停滯捕捉光束) |
| Damage Control (損傷控制) | Overdrive Injector System (超載噴注器) | Stasis Web (停滯纏繞光束) |
| Drone Control Range Module (無人機鏈接增效器) | Power Diagnostic System (能源診斷系統) | Survey Scanner (測量掃描器) |
| Drone Damage Modules (無人機傷害增效裝置) | Precursor Weapon (先驅者武器) | Target Painter (目標標記裝置) |
| Drone Tracking Enhancer (全方位索敵增強器) | Propulsion Module (推進裝備) | Tracking Computer (索敵計算機) |
| Drone Tracking Modules (全方位索敵連接) | Reactor Control Unit (反應堆控制元件) | Tracking Enhancer (索敵增強器) |
| ECM | Reinforced Bulkhead (強化艙隔壁) | Warp Disrupt Field Generator (躍遷擾斷力場發生器) |
| Energy Neutralizer (能量中和器) | Remote Armor Repairer (遠程裝甲維修器) | Warp Scrambler (躍遷擾頻器) |
| Energy Nosferatu (掠能器) | Remote Capacitor Transmitter (遠程電容傳輸裝置) | Weapon Disruptor (躍遷擾斷器) |
| Expanded Cargohold (擴充貨櫃艙) | Remote Sensor Booster (遠程感應增強器) | |

<fs large>而還沒有進行層級調整的裝備則如下:</fs>

| Armor Coating (抗性附甲) | Missile Launcher Rapid Heavy (快速重型導彈發射器) |
| Armor Plating Energized (電壓式附甲) | Missile Launcher Rapid Light (快速輕型導彈發射器) |
| Automated Targeting System (自動鎖定系統) | Missile Launcher Rocket (火箭發射器) |
| ECM Stabilizer (信號畸變放大器) | Missile Launcher Torpedo (魚雷發射器) |
| Energy Weapon (能量武器) | Passive Targeting System (被動索敵系統) |
| Gas Cloud Harvester (氣雲採集器) | Projectile Weapon (射彈武器) |
| Hull Repair Unit (結構維修器) | Shield Boost Amplifier (護盾回充增量放大器) |
| Hybrid Weapon (混合武器) | Shield Resistance Amplifier (護盾抗性增效器) |
| Jump Drive Economizer (跳躍節能裝置) | Smart Bomb (立體炸彈) |
| Missile Launcher Cruise (巡航導彈發射器) | Warp Accelerator (躍遷加速裝置) |
| Missile Launcher Heavy (重型導彈發射器) | Warp Core Stabilizer (躍遷核心穩定器) |
| Missile Launcher Heavy Assault (重型攻擊導彈發射器) | |

而在接下來的 6月更新, Shield Resistance Amplifier (護盾抗性增效器) 將會進行層級調整。然後接着是 Armor Coating (抗性附甲), Armor Plating Energized (電壓式附甲), Shield Boost Amplifier (護盾回充增量放大器)。那就完全了裝甲及護盾這兩類了。

-----

===== 武器 =====

因爲炮台和導彈發射器的屬性項目非常多, 而且亦受其所使用的彈藥所影響, 使這兩類要作出層級調整很困難。有一些導彈發射器型號已經調整過, 而雖然當初介紹層級調整所用的例子是集束激光炮但仍然沒有一款炮台有作出過調整。按計劃來說所有炮台組別將會同一時間獲得調整。

爲了讓大家了解一下炮台的層級調整的規模, 以下是一些炮台及其彈藥的數目:
 *能量炮台 : 210
 *頻率晶體 : 200
 *射彈炮台 : 165
 *射彈彈藥 : 144
 *混合炮台 : 221
 *混合彈藥 : 224
 *總炮台+彈藥組合數目 : 27683

每一款炮台都有五項主要屬性 : 傷害增效, 最佳射程, 失準距離, 發射速度, 跟踪速度。每一款彈藥都有其傷害類別及傷害量, 而對某些彈藥來說還會影響炮台的射程或跟踪速度。除此之外, 不同炮台及彈藥有不同特定定位, 在不同情況下的表現各不相同。還沒說還有裝配需求及電容消耗要考慮。

簡單來說, 目前的炮台及彈藥種類太多, 而只有一小部份是有用的。10% 的炮台類別產生了 78% 的總炮台使用量 (594 款炮台中只有 59 款是常用的)。

現在談論細節還為時尚早，但是玩家們可以期望將來炮台和彈藥將會有重大調整。

導彈發射器和立體炸彈將緊隨其後，但它們最有可能的是整個層級調整計劃的最後兩類。

-----

===== 反饋與調整 =====

玩家或許注意到有一些在今年上旬已經調整過的裝備在 5月更新中又再次調整, 包括:
 *裝甲維修器
 *護盾回充增量器
 *護盾增強器

基於玩家們的反饋, 這些裝備的層級調整再有些微修訂。玩家們指出了有一些裝備並沒有得到按章的調整, 亦指出其他啟發進一步調整的建議。

在此必須感謝所有通過各種渠道提出建議的玩家，以及 Neugeniko 和其他在EVE論壇上討論層級調整的玩家。他們的帖子激發了 CCP 在2019年11月重拾整個層級調整的任務。

即使 CCP 沒有馬上回覆你們的反饋並不代表 CCP 沒有理論你們的意見, 玩家們所有的提示都會被 CCP 看見及加入考慮之一。所以不論是批評，讚美還是提出解決方案，都請繼續向 CCP 提出！

Fly safe!

BY EVE DEVELOPMENT TEAM