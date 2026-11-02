# zh_dev_blog_and_patchnote_improving_the_foundation

<jumbotron>

--------

====== 停止支援 DirectX 9 ======

-----\\原文鏈接: https://www.eveonline.com/news/view/improving-the-foundation

</jumbotron>

大家好,

早於 2016年6月, CCP 就已經公告過停止支援 DirectX 9 的計劃。於 19年前透過 Windows 98 推出的 EVE Online, 在當時使用 DirectX 9 是非常合適的。

但隨時代過去, 目前繼續爲 DirectX 9 提供支援將花費大量開發成本用於提升 EVE Online 的視覺效果。而目前亦只有不足 1% 的玩家只能使用 DirectX 9 的情況下, 是時候於 2022年停止對 DirectX 9 的支援了。

過去數年間, CCP 一直在投資 EVE 的基礎建設, 例如完成轉換至 64位元客戶端以讓 EVE 能邁進第三個十年。旅程將於 2022年 1月 11日踏出下一步, 不再提供支援 DirectX 9 的客戶端。

強列建議目前能運行 DX11 而在使用 DX9 的用戶, 於你們的登錄器設定中, "Game Client" 一項取消勾選 "Run game clients with DirectX 9"。

完成這設定後會確保 EVE 客戶端使用 DirectX 11 進行渲染。在 11月30日, 於 GPU 能支援的情況下, CCP 會預設把所有玩家調整至 DirectX 11。若然遇到有問題, 玩家仍然可以手動切換回 DirectX 9。而同時強列建議這些玩家們向 CCP 的客服 (選擇 "Techical" 分類) 查詢, 好讓 CCP 能夠查找不能夠使用 DirectX 11 的原因。手動切換至 DirectX 9 的選項將於 1月11日移除。

停止支援 DirectX 9 後, CCP 將會上調客戶端的最低硬件需求至支援 DirectX 11 的顯示卡。以 Nvidia 來說, 爲 GeForce GT 420, 而 AMD 則爲 Radeon HD 5450。首批 DirectX 11 GPU 早於 10多年前發行, 所以這調整應該不會影響絕大多數的玩家。

最低硬件需求:
 *OS: Windows 7 Service Pack 1 64-bit
 *CPU: Dual Core @ 2.0 GHz
 *RAM: 4 GB 或以上
 *顯示卡: AMD Radeon 5450 / NVIDIA GeForce 420 或以上, 配以最少 1024 MB VRAM

如果你使用的 GPU 型號很古舊, 你可以在遊戲中按下 Ctrl+F 以打開 FPS 顯示。視窗的左下角會顯示出當前客戶端以那一個版本的 DirectX 在渲染。

至於使用 MacOS 的玩家則不用擔心, 因爲原生 Mac 客戶端是使用 Metal 而非 DirectX。

DirectX 9 過去的表現非常好, 但爲了在未來實現更高性能及更沉浸式的體驗, 在此必需將之淘汱。在消除被迫支援舊圖形 API 的阻礙, 及能完全利用 DirectX 11 更現在的渲染算法, 爲 CCP 提供更好的技術基礎, 爲 EVE 各玩家提供更驚人的視覺效果。