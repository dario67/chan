import Chan
from Common.CEnum import BSP_TYPE, FX_TYPE


class Eg:
    """
    策略类因为要用反射获取类名，所以类名和文件名需要一致
    一个示例策略，只交易一类买卖点，底分型形成后就开仓，直到一类卖点顶分型形成后平仓
    """

    def __init__(self, config=None):
        self.config = config
        self.is_hold = False
        self.last_buy_price = None

        self.capitalization = 100  # 总资产市值
        self.cash = 100  # 现金
        self.hold_quantity = 0  # 持股数

    def execute(self, chan: Chan = None):
        bsp_list = chan.get_bsp()  # 获取买卖点列表
        if not bsp_list:  # 为空
            return False
        last_bsp = bsp_list[-1]  # 最后一个买卖点
        # if BSP_TYPE.T1 not in last_bsp.type and BSP_TYPE.T1P not in last_bsp.type:  # 假如只做1类买卖点
        #     return False

        cur_lv_chan = chan[0]
        if cur_lv_chan[-2].fx == FX_TYPE.BOTTOM and last_bsp.is_buy and not self.is_hold:  # 底分型形成后开仓
            self.last_buy_price = cur_lv_chan[-1][-1].close  # 开仓价格为最后一根K线close

            self.hold_quantity = round(self.cash/self.last_buy_price, 2)
            self.capitalization = self.cash
            self.cash = 0
            self.is_hold = True

            print(f'{cur_lv_chan[-1][-1].time}, buy price :{self.last_buy_price}, capitalization:{self.capitalization}')
            return True
        elif cur_lv_chan[-2].fx == FX_TYPE.TOP and not last_bsp.is_buy and self.is_hold:  # 顶分型形成后平仓
            sell_price = cur_lv_chan[-1][-1].close
            self.cash = sell_price * self.hold_quantity
            self.hold_quantity = 0
            self.capitalization = self.cash
            self.is_hold = False
            print(f'{cur_lv_chan[-1][-1].time}, sell price: {sell_price}, '
                  f'profit rate: {(sell_price - self.last_buy_price) / self.last_buy_price * 100:.2f}%'
                  f', capitalization:{self.capitalization}')
            return True
        return False

    def get_result(self):

        return {
            'cash': self.cash,
            'hold_quantity': self.hold_quantity,
            'capitalization': self.capitalization,
        }
