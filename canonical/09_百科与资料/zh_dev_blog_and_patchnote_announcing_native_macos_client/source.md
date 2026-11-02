# zh_dev_blog_and_patchnote_announcing_native_macos_client

<jumbotron>

====== CCP 宣佈開發原生 macOS 版 EVE 客戶端 ======

--------\\原文鏈接:

EVE Online to go native on macOS!

announcing native macos client

</jumbotron>

大家好。

CCP 宣佈將開發原生 macOS 版 EVE 客戶端。

macOS Big Sur 及 Apple 強大的圖像處理架構 Metal 將能透過原生 macOS 客戶端爲玩家帶來最佳的視覺體驗, 對比現有客戶端相比也會有大幅的改善及性能提升。

首階段的公測將預計於 2021年第1季開始。

-----Q : 爲甚麼要開發原生 macOS 客戶端。

A : 原生 macOS 客戶端將爲玩家帶來性能和程式穩定的提升。原生客戶端在 CCP 方的一大優勢是可以更輕鬆地對客戶端問題除錯及 debug。由於原生客戶端直接使用Metal, 而不是通過 Wine 來使用DirectX, 因此它也使 CCP 能更好地利用 macOS 提供的系統資源。
-----

Q : 那原生客戶端將支援那一個版本的 macOS 呢?

A : 在將近推出時會作最後決定。但 CCP 一般都建議 macOS 用家們一直更新其 OS 至最新版本。
-----

Q : 原生客戶端的最低配置需求是甚麼?

A : 在將近推出時會再作公佈。
-----

Q : 那 Wine 版客戶端呢?

A : CCP 將會一直支援 Mac Wine 版客戶端直至推出原生 macOS 客戶端。在原生 macOS 客戶端推出時, CCP 將會同一時間棄用 Wine 版客戶端。屆時會再提前作出公告。
-----

Q : 那 Apple Silicon (M1) 呢?

A : 目前 EVE Online Wine 版客戶端並不能於 Apple Silicon 裝置運行。CCP 正在進行研究, 但目前決定時先全力開發原生 macOS 客戶端以爲玩家長期帶來最佳遊戲體驗。

macOS 原生客戶端推出時將會透過 Rosetta2 於 Apple Silicon 裝置上運行。

未來 CCP 計劃推出原生 Apple Silicon 版客戶端而不需要透過 Rosetta2 運行。屆時程式將會以 Universal app 形式編寫。
-----

Q : 那我可以透過第三方程式於 Apple Silicon 裝置上運行 EVE Online 嗎?

A : CCP 注意到目前已經有一些第三方程式容許用戶在 Apple Silicon 裝置上運行 Wine 版程式。CCP 並不禁止相關程式的使用, 但不會爲此提供支援。
-----

Q : 我有注意到目前大多數 Wine 程式都是以 DX9 作支援, 那將來會棄用麼?

A : CCP 目前計劃着棄用 DirectX 9, 就如之前不同的帖子都有提及過。保留及維護 DirectX 9 都需要大量的資源。雖然 CCP 並不會在推出原生 macOS 客戶端同時棄用 DirectX 9, 但可預期在之不久後就會實施。
-----

Q : 我有甚麼可以幫忙麼?

A : YES! CCP 計劃於 2021年第1季推出公測版本。第一個公測版本將集中於處理渲染的問題, 找出影響體驗的程式潰問題, 測量程式運行表現。敬請留意未來的 devblog 公佈有關日期及消息。
-----

Q : 有正式推出日期麼?

A : 目前仍未有正式版本的推出日期。但 CCP 也和你們一樣期待盡早爲玩家們帶來原生的 macOS 版 EVE Online 體驗。

-----

以下是一些 WIP 截圖: