class RSI:
    # RSI（相对强弱指数）是一种衡量证券或股票在特定时期内价格变动的速度和变化量的技术分析指标，通常用于识别超买或超卖的条件。
    def __init__(self, period: int = 14):
        super(RSI, self).__init__()
        self.close_arr = []
        self.period = period
        self.diff = []
        self.up = []
        self.down = []

    def add(self, close):
        self.close_arr.append(close)
        if len(self.close_arr) == 1:
            return 50.0
        self.diff.append(self.close_arr[-1] - self.close_arr[-2])
        if len(self.diff) < self.period:
            self.up.append(sum(x for x in self.diff if x > 0)/self.period)
            self.down.append(sum(-x for x in self.diff if x < 0)/self.period)
        else:
            if self.diff[-1] > 0:
                upval = self.diff[-1]
                downval = 0.0
            else:
                upval = 0.0
                downval = -self.diff[-1]
            self.up.append((self.up[-1] * (self.period - 1) + upval) / self.period)
            self.down.append((self.down[-1] * (self.period - 1) + downval) / self.period)
        rs = self.up[-1] / self.down[-1] if self.down[-1] != 0 else 0
        rsi = 100.0 - 100.0 / (1.0 + rs)
        return rsi
