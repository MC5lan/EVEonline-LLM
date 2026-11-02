"""内存映射 token 数据集。

token 以 uint16 存储（词表 32k < 65536），500M tokens 只占 1GB 磁盘，
读取走 memmap，不会被一次性读进内存。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch


class TokenDataset:
    def __init__(self, bin_path: str | Path, seq_len: int):
        self.path = str(bin_path)
        self.seq_len = seq_len
        self.data = np.memmap(self.path, dtype=np.uint16, mode="r")
        self.n = int(len(self.data))
        if self.n < seq_len + 2:
            raise ValueError(
                f"{self.path} 只有 {self.n} 个 token，至少需要 {seq_len + 2}。"
                "请先运行 `python -m src.tokenize encode`。"
            )

    def __len__(self) -> int:
        return self.n

    def sample_batch(self, batch_size: int, device: str | torch.device):
        """随机裁一段连续文本，返回 (x, y)，y 为右移一位的标签。"""
        ix = np.random.randint(0, self.n - self.seq_len - 1, size=batch_size)
        buf = np.empty((batch_size, self.seq_len + 1), dtype=np.int64)
        for i, off in enumerate(ix):
            buf[i] = self.data[off : off + self.seq_len + 1]
        t = torch.from_numpy(buf)
        x = t[:, :-1].to(device, non_blocking=True)
        y = t[:, 1:].to(device, non_blocking=True)
        return x, y
